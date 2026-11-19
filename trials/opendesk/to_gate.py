"""Translate a pinned opendesk trial report into portable gate observations."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from verify_report import unique_keys, validate

# Each scope identifies the reader and lookup implemented by this specific runner.
# Keep it independent of the release policy that will judge these observations.
PROBES = (
    ("source", "sql-observer.message-id.v1", "source_message_row", "after_offboarding"),
    (
        "summary",
        "sql-observer.ticket-summary-id.v1",
        "stored_ticket_summary",
        "after_offboarding",
    ),
    (
        "agent-read",
        "support-agent.ticket-summary.v1",
        "agent_summary",
        "after_offboarding",
    ),
    (
        "worker-summary",
        "sql-observer.ticket-summary-id.v1",
        "stored_ticket_summary",
        "after_worker",
    ),
)
STATES = {
    "FOUND": "present",
    "ABSENT_BY_ID": "absent",
    "RETURNED": "present",
    "NOT_RETURNED": "absent",
    "INCONCLUSIVE": "unavailable",
}
MAX_INPUT_BYTES = 65_536


def read_pair(phases, phase, field):
    if phase not in phases:
        return {"subject": "not_tested", "control": "not_tested"}
    rows = phases[phase]
    return {
        "subject": STATES[rows["Acme"][field]],
        "control": STATES[rows["Birch"][field]],
    }


def observations(raw):
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("Oversized trial report")
    trial = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys)
    validate(trial)
    phases = {row["phase"]: row["workspaces"] for row in trial["observations"]}
    probes = []
    for name, scope, field, checkpoint in PROBES:
        probe = {
            "id": name,
            "scope": scope,
            "checkpoint": checkpoint,
            "before": read_pair(phases, "before_offboarding", field),
            "after": read_pair(phases, checkpoint, field),
        }
        if checkpoint == "after_worker":
            # The pinned runner finishes both summary requests before offboarding.
            probe["worker"] = {
                "captured_before_offboarding": False,
                "finished_after_offboarding": False,
            }
        probes.append(probe)
    return {
        "version": 1,
        "target": "opendesk",
        "revision": trial["target"]["commit"],
        "run_id": "sha256-" + hashlib.sha256(raw).hexdigest(),
        "offboarding": "completed"
        if trial["offboarding_http_status"] == 204
        else "unconfirmed",
        "probes": probes,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() and args.report.samefile(args.output):
            raise ValueError("Output must differ from input")
        with args.report.open("rb") as source:
            converted = observations(source.read(MAX_INPUT_BYTES + 1))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", dir=args.output.parent, delete=False, encoding="utf-8"
        ) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(converted, stream, indent=2)
                stream.write("\n")
                stream.close()
                temporary.replace(args.output)
            finally:
                temporary.unlink(missing_ok=True)
    except (KeyError, TypeError, ValueError, OSError, RecursionError):
        print(
            "Cannot convert trial report. Check the pinned input and output paths.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
