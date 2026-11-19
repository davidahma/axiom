"""Check offboarding evidence, issue and replay receipts, or run the reference demo."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

from . import gate, receipt_cli
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
                files("axiom_demo").joinpath("fixture.py").read_bytes()
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


def read_gate_input(path, label, *, opener=None):
    try:
        with open(path, "rb", opener=opener) as stream:
            raw = stream.read(gate.MAX_INPUT_BYTES + 1)
    except OSError:
        raise InvalidReport(f"Could not read {label} input.") from None
    if len(raw) > gate.MAX_INPUT_BYTES:
        raise InvalidReport(f"The {label} input exceeds the 1 MiB limit.")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_fields)
    except (ValueError, RecursionError):
        raise InvalidReport(
            f"Invalid {label} JSON. Use UTF-8 and unique fields."
        ) from None
    return data, hashlib.sha256(raw).hexdigest()


def run_gate(args):
    try:
        policy, policy_digest = read_gate_input(args.policy, "policy")
        observations, data_digest = read_gate_input(args.observations, "observations")
        report = gate.evaluate(
            policy,
            observations,
            expect_run=args.expect_run,
            expect_revision=args.expect_revision,
        )
        report["policy_sha256"] = policy_digest
        report["observations_sha256"] = data_digest
        if args.output is not None:
            if args.output.exists() and any(
                args.output.samefile(path) for path in (args.policy, args.observations)
            ):
                raise InvalidReport("Output must be separate from both inputs.")
            save(report, args.output)
    except InvalidReport as error:
        print(f"Invalid gate input. {error}", file=sys.stderr)
        return 3
    except OSError:
        print("Could not write gate report.", file=sys.stderr)
        return 3
    for probe in report["probes"]:
        print(
            probe["verdict"],
            probe["id"],
            probe["scope"],
            probe["checkpoint"],
            *probe["reasons"],
        )
    print(f"Gate {report['verdict']}")
    return gate.EXIT_CODES[report["verdict"]]


class GateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(3, "Invalid arguments. Use the command's --help for usage.\n")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser_class = (
        GateArgumentParser
        if argv and argv[0] in ("gate", *receipt_cli.COMMANDS)
        else argparse.ArgumentParser
    )
    parser = parser_class(description=__doc__)
    jobs = parser.add_subparsers(dest="command", required=True)
    receipt_cli.add_commands(jobs)
    staging = jobs.add_parser(
        "gate", help="check staging observations against a policy"
    )
    staging.add_argument("--policy", type=Path, required=True)
    staging.add_argument("--observations", type=Path, required=True)
    staging.add_argument("--output", type=Path, help="write a content-free JSON report")
    staging.add_argument("--expect-run", help="require this observation run identifier")
    staging.add_argument(
        "--expect-revision", help="require this observed target revision"
    )
    run = jobs.add_parser("demo", help="run three isolated reference cases")
    run.add_argument("--output", type=Path, default=Path("artifacts/demo-report.json"))
    check = jobs.add_parser(
        "validate", help="recompute reference verdicts without running the demo"
    )
    check.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    if args.command in receipt_cli.COMMANDS:
        return receipt_cli.run(args, read_gate_input)
    if args.command == "gate":
        return run_gate(args)
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
