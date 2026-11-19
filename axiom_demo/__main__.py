"""Run the reference cases or validate an exported report."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from .report import (
    CASES,
    PHASES,
    ROLES,
    InvalidReport,
    assess,
    reproduced_reference_cases,
    validate,
)


def save(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=path.parent, delete=False, encoding="utf-8"
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(report, stream, indent=2)
            stream.write("\n")
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidReport("Duplicate JSON field.")
        result[key] = value
    return result


def demo(path):
    from . import fixture

    cases = []
    for mode in CASES:
        case = fixture.run_case(mode)
        cases.append({**case, "assessment": assess(case)})
    report = validate(
        {
            "schema_version": 1,
            "fixture_sha256": hashlib.sha256(
                Path(fixture.__file__).read_bytes()
            ).hexdigest(),
            "read_roles": ROLES,
            "cases": cases,
        }
    )
    save(report, path)
    print("AXIOM   Tenant offboarding in a controlled support system")
    print(
        f"{'Case':<14}{'Checkpoint':<18}{'Acme source':<15}{'Acme summary':<15}{'Agent read':<16}Birch control"
    )
    for case in cases:
        for phase in PHASES:
            states = {
                (r["subject"], r["surface"]): r["state"]
                for r in case["observations"]
                if r["phase"] == phase
            }
            control = all(
                states["birch", surface]
                == ("returned" if surface == "support" else "present")
                for surface in ROLES
            )
            print(
                f"{case['case']:<14}{phase:<18}{states['acme', 'source']:<15}{states['acme', 'summary']:<15}"
                f"{states['acme', 'support']:<16}{'healthy' if control else 'incomplete'}"
            )
        assessment = case["assessment"]
        details = ", ".join([*assessment["failures"], *assessment["gaps"]])
        print(
            f"  {assessment['verdict']}   worker={case['worker']['terminal']}"
            + (f"   {details}" if details else "")
        )
    print(f"Report: {path}")
    if not reproduced_reference_cases(cases):
        print(
            "Reference outcomes differed from the expected sequence.", file=sys.stderr
        )
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    jobs = parser.add_subparsers(dest="command", required=True)
    run = jobs.add_parser("demo", help="run three isolated reference cases")
    run.add_argument("--output", type=Path, default=Path("artifacts/demo-report.json"))
    check = jobs.add_parser(
        "validate", help="recompute reference verdicts without running the demo"
    )
    check.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    if args.command == "demo":
        return demo(args.output)
    try:
        with args.report.open(encoding="utf-8") as stream:
            validate(json.load(stream, object_pairs_hook=unique_fields))
    except (ValueError, OSError, RecursionError) as error:
        print(f"Invalid report ({type(error).__name__}).", file=sys.stderr)
        return 1
    print("Report valid. All recorded verdicts match the observations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
