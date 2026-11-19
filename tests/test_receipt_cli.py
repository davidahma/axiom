"""Exercise the complete receipt handoff from outside the source checkout."""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from axiom_demo.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "sqlite"


class ReceiptCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.cli = Path(temp.name) / "axiom.pyz"
        subprocess.run(
            [sys.executable, ROOT / "scripts/build_zipapp.py", "--output", cls.cli],
            check=True,
        )

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.policy = self.work / "policy.json"
        shutil.copyfile(EXAMPLE / "policy.json", self.policy)

    def invoke(self, *args, code=0):
        result = subprocess.run(
            [sys.executable, "-I", *args],
            cwd=self.work,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout

    def request(self, name, *items):
        path = self.work / (name + ".json")
        stdout = self.invoke(
            self.cli,
            "request",
            "--revision",
            "test-build",
            "--run-id",
            "job-suite",
            "--context",
            "staging",
            "--policy",
            self.policy,
            "--output",
            path,
            *items,
        )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertIn(digest, stdout)
        return path, digest

    def observe(self, request, case, name):
        path = self.work / (name + ".json")
        self.invoke(
            EXAMPLE / "observe.py",
            "--request",
            request,
            "--revision",
            "test-build",
            "--case",
            case,
            "--output",
            path,
        )
        return path

    def inputs(self, request, digest, evidence):
        return [
            "--request",
            request,
            "--expect-request",
            digest,
            "--evidence",
            evidence,
            "--policy",
            self.policy,
        ]

    def test_two_requests_one_build_reject_swapped_clean_run_and_wrong_case_anchor(
        self,
    ):
        a, anchor_a = self.request("case-a")
        b, anchor_b = self.request("case-b")
        self.assertNotEqual(anchor_a, anchor_b)
        residual = self.observe(a, "residual", "leftover")
        clean = self.observe(b, "clean", "clean")
        for name, inputs, code, disposition in (
            ("a", self.inputs(a, anchor_a, residual), 1, "RESIDUAL_FOUND"),
            ("b", self.inputs(b, anchor_b, clean), 0, "READY_FOR_REVIEW"),
        ):
            receipt = self.work / f"receipt-{name}.json"
            self.assertIn(
                disposition,
                self.invoke(
                    self.cli, "receipt", *inputs, "--output", receipt, code=code
                ),
            )
            self.assertIn(
                disposition,
                self.invoke(
                    self.cli, "verify-receipt", *inputs, "--receipt", receipt, code=code
                ),
            )
            self.assertEqual(json.loads(receipt.read_bytes())["context"], "staging")
        for inputs in (
            self.inputs(a, anchor_a, clean),
            self.inputs(b, anchor_a, clean),
        ):
            self.invoke(
                self.cli, "receipt", *inputs, "--output", "swapped.json", code=3
            )
            self.assertFalse((self.work / "swapped.json").exists())

    def test_case_owner_can_pin_one_job_even_if_two_harnesses_used_the_same_request(
        self,
    ):
        path, anchor = self.request("case")
        first = self.observe(path, "residual", "first")
        second = self.observe(path, "clean", "second")
        expected_job = json.loads(first.read_bytes())["job"]["id"]
        self.invoke(
            self.cli,
            "receipt",
            *self.inputs(path, anchor, first),
            "--expect-job",
            expected_job,
            "--output",
            "first-receipt.json",
            code=1,
        )
        self.invoke(
            self.cli,
            "receipt",
            *self.inputs(path, anchor, second),
            "--expect-job",
            expected_job,
            "--output",
            "second-receipt.json",
            code=3,
        )
        self.assertFalse((self.work / "second-receipt.json").exists())

    def test_receipt_creation_and_replay_admit_at_most_five_minutes_of_clock_skew(self):
        request, anchor = self.request("case")
        evidence = self.observe(request, "clean", "observations")
        observed_at = datetime.fromisoformat(
            json.loads(evidence.read_bytes())["job"]["observed_at"]
        )
        inputs = list(map(str, self.inputs(request, anchor, evidence)))
        original = self.work / "original.json"
        self.invoke(self.cli, "receipt", *inputs, "--output", original)
        original_bytes = original.read_bytes()
        with (
            patch("axiom_demo.receipt_cli.datetime", wraps=datetime) as clock,
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            for seconds, code in ((300, 0), (301, 3), (86400, 3), (-86400, 0)):
                with self.subTest(seconds=seconds):
                    clock.now.return_value = observed_at - timedelta(seconds=seconds)
                    output = self.work / f"receipt-{seconds}.json"
                    self.assertEqual(
                        main(["receipt", *inputs, "--output", str(output)]), code
                    )
                    self.assertEqual(
                        main(["verify-receipt", *inputs, "--receipt", str(original)]),
                        code,
                    )
                    if code == 0:
                        self.assertEqual(output.read_bytes(), original_bytes)
                    else:
                        self.assertFalse(output.exists())

    def test_replay_requires_original_document_and_rejects_edit_to_stored_decision(
        self,
    ):
        path, anchor = self.request("case", "--statement", "provider")
        evidence = self.observe(path, "clean", "reads")
        inputs = self.inputs(path, anchor, evidence)
        document = self.work / "provider.txt"
        document.write_bytes(b"PRIVATE SYNTHETIC ORIGINAL WORDING")
        descriptor = self.work / "statement.json"
        descriptor.write_text(
            json.dumps(
                {
                    "version": 1,
                    "id": "provider",
                    "kind": "provider_statement",
                    "issuer": "example-processor",
                    "outcome": "reported_deleted",
                    "request_sha256": anchor,
                    "document_sha256": hashlib.sha256(
                        document.read_bytes()
                    ).hexdigest(),
                }
            )
        )
        receipt = self.work / "receipt.json"
        self.invoke(self.cli, "receipt", *inputs, "--output", "missing.json", code=2)
        inputs.extend(["--record", descriptor, document])
        stdout = self.invoke(self.cli, "receipt", *inputs, "--output", receipt)
        original = receipt.read_bytes()
        self.assertNotIn("PRIVATE SYNTHETIC", stdout)
        self.assertNotIn(b"PRIVATE SYNTHETIC", original)
        self.invoke(self.cli, "verify-receipt", *inputs, "--receipt", receipt)
        for key, change in (
            ("version", True),
            ("context", "customer"),
            ("technical_verdict", "FAIL"),
        ):
            modified = json.loads(original)
            modified[key] = change
            receipt.write_text(json.dumps(modified))
            self.invoke(
                self.cli, "verify-receipt", *inputs, "--receipt", receipt, code=3
            )
        receipt.write_bytes(original)
        document.write_bytes(b"replacement")
        self.invoke(self.cli, "verify-receipt", *inputs, "--receipt", receipt, code=3)

    def test_fresh_outputs_and_old_staging_report_cannot_be_relabelled(self):
        path, anchor = self.request("case")
        evidence = self.observe(path, "unavailable", "evidence")
        inputs = self.inputs(path, anchor, evidence)
        self.invoke(self.cli, "receipt", *inputs, "--output", "decision.json", code=2)
        self.invoke(
            self.cli, "verify-receipt", *inputs, "--receipt", "decision.json", code=2
        )
        original = path.read_bytes()
        self.invoke(self.cli, "receipt", *inputs, "--output", path, code=3)
        self.invoke(
            self.cli,
            "request",
            "--context",
            "staging",
            "--policy",
            self.policy,
            "--revision",
            "test-build",
            "--run-id",
            "job-suite",
            "--output",
            path,
            code=3,
        )
        self.assertEqual(path.read_bytes(), original)
        legacy = json.loads(evidence.read_bytes())["observations"]
        evidence.write_text(json.dumps(legacy))
        self.invoke(self.cli, "receipt", *inputs, "--output", "unbound.json", code=3)
        self.assertFalse((self.work / "unbound.json").exists())

    def test_concurrent_issuance_has_one_winner_and_complete_manifest(self):
        args = [
            sys.executable,
            "-I",
            self.cli,
            "request",
            "--context",
            "staging",
            "--policy",
            self.policy,
            "--revision",
            "race",
            "--run-id",
            "race",
            "--output",
            self.work / "single.json",
        ]
        with (
            subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as one,
            subprocess.Popen(
                args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ) as two,
        ):
            first, second = one.communicate()[0], two.communicate()[0]
            self.assertEqual(sorted([one.returncode, two.returncode]), [0, 3])
            raw = (self.work / "single.json").read_bytes()
            self.assertEqual(json.loads(raw)["revision"], "race")
            self.assertIn(hashlib.sha256(raw).hexdigest().encode(), first + second)

    @unittest.skipUnless(shutil.which("ssh-keygen"), "optional OpenSSH signing recipe")
    def test_documented_signature_accepts_only_matching_bytes_and_authorized_identity(
        self,
    ):
        path, anchor = self.request("case")
        evidence = self.observe(path, "residual", "reads")
        receipt = self.work / "receipt.json"
        self.invoke(
            self.cli,
            "receipt",
            *self.inputs(path, anchor, evidence),
            "--output",
            receipt,
            code=1,
        )
        key = self.work / "test-only-key"

        def ssh(*args, data=None):
            return subprocess.run(
                ["ssh-keygen", *args],
                cwd=self.work,
                input=data,
                capture_output=True,
                check=False,
            ).returncode

        self.assertEqual(ssh("-q", "-t", "ed25519", "-N", "", "-f", key), 0)
        trusted = self.work / "allowed_signers"
        trusted.write_text("reviewer " + key.with_suffix(".pub").read_text())
        self.assertEqual(
            ssh("-Y", "sign", "-f", key, "-n", "axiom-receipt-v1", receipt), 0
        )

        def verify(identity, data):
            return ssh(
                "-Y",
                "verify",
                "-f",
                trusted,
                "-I",
                identity,
                "-n",
                "axiom-receipt-v1",
                "-s",
                "receipt.json.sig",
                data=data,
            )

        raw = receipt.read_bytes()
        self.assertEqual(verify("reviewer", raw), 0)
        self.assertNotEqual(verify("other", raw), 0)
        self.assertNotEqual(verify("reviewer", raw + b" "), 0)
