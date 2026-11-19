"""Exercise the downloadable CLI from an adopter directory outside the checkout."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

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
                (ROOT / "axiom_demo" / "fixture.py")
                .read_bytes()
                .replace(b"\r\n", b"\n")
            ).hexdigest(),
        )

    def copy_checkout(self, name):
        checkout = self.work / name
        (checkout / "scripts").mkdir(parents=True)
        shutil.copyfile(
            ROOT / "scripts/build_zipapp.py", checkout / "scripts/build_zipapp.py"
        )
        shutil.copyfile(ROOT / "LICENSE", checkout / "LICENSE")
        shutil.copytree(
            ROOT / "axiom_demo",
            checkout / "axiom_demo",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        return checkout

    def test_package_omits_local_files_and_is_identical_from_crlf_checkout(self):
        checkout = self.copy_checkout("crlf-checkout")
        for source in [checkout / "LICENSE", *(checkout / "axiom_demo").glob("*.py")]:
            content = source.read_bytes().replace(b"\r\n", b"\n")
            source.write_bytes(content.replace(b"\n", b"\r\n"))
        (checkout / "axiom_demo/local_debug.py").write_text("local_only = True\n")
        output = checkout / "portable.pyz"
        self.invoke(
            checkout / "scripts/build_zipapp.py", "--output", output, check=True
        )
        with ZipFile(output) as archive:
            self.assertNotIn("axiom_demo/local_debug.py", archive.namelist())
            self.assertIn("axiom_demo/inputs.py", archive.namelist())
        self.assertEqual(output.read_bytes(), self.cli.read_bytes())

    def test_output_cannot_replace_a_source_or_leave_a_partial_build(self):
        checkout = self.copy_checkout("alias-checkout")
        script = checkout / "scripts/build_zipapp.py"
        source = checkout / "axiom_demo/gate.py"
        original = source.read_bytes()
        hard = checkout / "hardlink.pyz"
        os.link(source, hard)
        symbolic = checkout / "symlink.pyz"
        symbolic.symlink_to(source)
        for alias in (source, symbolic, hard, script):
            with self.subTest(alias=alias.name):
                self.assertNotEqual(
                    self.invoke(script, "--output", alias).returncode, 0
                )
                self.assertEqual(source.read_bytes(), original)
                self.assertTrue(hard.samefile(source))
                self.assertTrue(symbolic.is_symlink())
        build = checkout / "portable.pyz"
        self.invoke(script, "--output", build, check=True)
        source.unlink()
        self.assertNotEqual(self.invoke(script, "--output", build).returncode, 0)
        self.assertEqual(build.read_bytes(), self.cli.read_bytes())
