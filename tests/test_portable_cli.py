"""Exercise the downloadable CLI from an adopter directory outside the checkout."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "sqlite"


class PortableCLITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.work = Path(temp.name)
        cls.cli = cls.work / "axiom.pyz"
        cls.invoke(
            ROOT / "scripts" / "build_zipapp.py", "--output", cls.cli, check=True
        )

    @classmethod
    def invoke(cls, *args, check=False):
        return subprocess.run(
            [sys.executable, "-I", *args],
            cwd=cls.work,
            capture_output=True,
            text=True,
            check=check,
        )

    def test_three_measured_customer_jobs_through_bundled_cli(self):
        for case, code, verdict in (
            ("clean", 0, "PASS"),
            ("residual", 1, "FAIL"),
            ("unavailable", 2, "INCONCLUSIVE"),
        ):
            with self.subTest(case=case):
                observations = self.work / f"{case}-observations.json"
                report = self.work / f"{case}-decision.json"
                self.invoke(
                    EXAMPLE / "observe.py",
                    "--case",
                    case,
                    "--output",
                    observations,
                    "--run-id",
                    case,
                    "--revision",
                    "staging-42",
                    check=True,
                )
                run = self.invoke(
                    self.cli,
                    "gate",
                    "--policy",
                    EXAMPLE / "policy.json",
                    "--observations",
                    observations,
                    "--output",
                    report,
                    "--expect-run",
                    case,
                    "--expect-revision",
                    "staging-42",
                )
                self.assertEqual(run.returncode, code, run.stderr + run.stdout)
                decision = json.loads(report.read_bytes())
                self.assertEqual(decision["verdict"], verdict)
                self.assertEqual(
                    {row["id"]: row["verdict"] for row in decision["probes"]},
                    {"source": "PASS", "cache": verdict},
                )
                self.assertEqual(
                    decision["observations_sha256"],
                    hashlib.sha256(observations.read_bytes()).hexdigest(),
                )
                self.assertIn(verdict, run.stdout)

    def test_bundle_reproducible_and_old_commands_work(self):
        other = self.work / "second.pyz"
        self.invoke(ROOT / "scripts" / "build_zipapp.py", "--output", other, check=True)
        self.assertEqual(self.cli.read_bytes(), other.read_bytes())
        report = self.work / "demo.json"
        self.invoke(self.cli, "demo", "--output", report, check=True)
        self.invoke(self.cli, "validate", report, check=True)
        self.assertEqual(
            json.loads(report.read_bytes())["fixture_sha256"],
            hashlib.sha256(
                (ROOT / "axiom_demo" / "fixture.py").read_bytes()
            ).hexdigest(),
        )
