"""Create and replay a synthetic deletion case using the portable CLI."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SQLITE = ROOT / "examples" / "sqlite"


def run(*args, cwd, expect=0):
    completed = subprocess.run([sys.executable, "-I", *args], cwd=cwd, check=False)
    if completed.returncode != expect:
        raise SystemExit(f"Expected exit {expect}, received {completed.returncode}.")


def record(folder, request_hash, item, kind, issuer, body, **extra):
    document = folder / f"{item}.txt"
    document.write_bytes(body.encode("utf-8"))
    descriptor = {
        "version": 1,
        "id": item,
        "kind": kind,
        "request_sha256": request_hash,
        "issuer": issuer,
        "document_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
        **extra,
    }
    (folder / f"{item}.json").write_text(
        json.dumps(descriptor, indent=2) + "\n", encoding="utf-8"
    )


def make_example(cli, archive_path):
    with tempfile.TemporaryDirectory() as work:
        case = Path(work)
        policy = case / "policy.json"
        shutil.copyfile(SQLITE / "policy.json", policy)
        # Identify the actual producer code in the synthetic job.
        revision = hashlib.sha256((SQLITE / "observe.py").read_bytes()).hexdigest()
        run(
            cli,
            "request",
            "--context",
            "staging",
            "--revision",
            revision,
            "--run-id",
            "receipt-example",
            "--policy",
            policy,
            "--statement",
            "provider",
            "--schedule",
            "backups",
            "--output",
            "request.json",
            cwd=case,
        )
        request_hash = hashlib.sha256((case / "request.json").read_bytes()).hexdigest()
        # Stand-in for a private case system saving the digest BEFORE dispatch.
        (case / "request.sha256").write_text(request_hash + "\n", encoding="ascii")
        run(
            SQLITE / "observe.py",
            "--request",
            "request.json",
            "--revision",
            revision,
            "--case",
            "clean",
            "--output",
            "evidence.json",
            cwd=case,
        )

        record(
            case,
            request_hash,
            "provider",
            "provider_statement",
            "fixture-provider",
            f"Synthetic provider statement for request {request_hash}.\n"
            "The fixture provider reports that it removed its support copy.\n",
            outcome="reported_deleted",
        )
        record(
            case,
            request_hash,
            "backups",
            "retention_schedule",
            "fixture-backups",
            f"Synthetic backup schedule for request {request_hash}.\n"
            "Expiry is scheduled for 2030-01-31. This fixture contains no backup deletion event.\n",
            expires_on="2030-01-31",
        )
        inputs = [
            "--request",
            "request.json",
            "--expect-request",
            request_hash,
            "--policy",
            "policy.json",
            "--evidence",
            "evidence.json",
            "--record",
            "provider.json",
            "provider.txt",
            "--record",
            "backups.json",
            "backups.txt",
        ]
        run(cli, "receipt", *inputs, "--output", "receipt.json", cwd=case, expect=2)
        run(
            cli,
            "verify-receipt",
            *inputs,
            "--receipt",
            "receipt.json",
            cwd=case,
            expect=2,
        )
        result = json.loads((case / "receipt.json").read_bytes())
        if (
            result["technical_verdict"] != "PASS"
            or result["review_status"] != "OPEN_ITEMS"
            or {row["id"]: row["status"] for row in result["items"]}
            != {"provider": "PROVIDER_REPORTED", "backups": "SCHEDULED"}
        ):
            raise SystemExit("Unexpected reference receipt findings.")

        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=archive_path.parent, delete=False) as tmp:
            temporary = Path(tmp.name)
        try:
            with ZipFile(temporary, "w") as archive:
                for name in (
                    "request.json",
                    "request.sha256",
                    "policy.json",
                    "evidence.json",
                    "provider.json",
                    "provider.txt",
                    "backups.json",
                    "backups.txt",
                    "receipt.json",
                ):
                    archive.write(case / name, name)
            os.replace(temporary, archive_path)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path, default=ROOT / "artifacts" / "axiom.pyz")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts" / "receipt-example.zip"
    )
    args = parser.parse_args()
    make_example(args.cli.resolve(), args.output.resolve())
