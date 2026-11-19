"""Validate a trial report resubmitted for publication, including its outcome."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

TARGET = {
    "version": "v0.4.13",
    "commit": "e0012447924c5ac8a13a51d2cd41a6496bc26fb3",
    "image": "sha256:e0fca3427eec675426c6c96766267d7980c861b52f630afc906fcf0c7dca0fe1",
}
METADATA = {
    "report_version": 1,
    "case": "upstream_opendesk_workspace_offboarding",
    "target": TARGET,
    "roles": {
        "offboarding": "workspace owner with MFA",
        "application_read": "agent in both workspaces at baseline",
        "storage_read": "axiom_observer (column-level SELECT)",
    },
    "worker_overlap": {
        "result": "NOT_TESTED",
        "reason": "This trial invokes the agent summary endpoint synchronously.",
    },
    "exclusions": [
        "physical media",
        "backups",
        "other stored copies",
        "other API paths",
        "future writes",
    ],
}
HEALTHY = {
    "source_message_row": "FOUND",
    "stored_ticket_summary": "FOUND",
    "agent_summary": "RETURNED",
    "agent_http_status": 200,
}
PHASES = ("before_offboarding", "after_offboarding")
STAGES = ("startup", "seeding", "baseline", "offboarding", "observation", "cleanup")


def require(condition):
    if not condition:
        raise ValueError("Invalid or inconsistent upstream evidence")


def outcome(observations):
    if not observations:
        return "INCONCLUSIVE"
    if any(row != HEALTHY for row in observations[0]["workspaces"].values()):
        return "INCONCLUSIVE"
    if len(observations) != 2:
        return "INCONCLUSIVE"
    after = observations[1]["workspaces"]
    acme = after["Acme"]
    if (
        "FOUND" in (acme["source_message_row"], acme["stored_ticket_summary"])
        or acme["agent_summary"] == "RETURNED"
    ):
        return "FAIL"
    if after["Birch"] != HEALTHY:
        return "INCONCLUSIVE"
    return "COMPLETED"


def validate(report):
    require(
        set(report)
        == set(METADATA)
        | {
            "outcome",
            "interrupted_at",
            "offboarding_http_status",
            "observations",
        }
    )
    for key, value in METADATA.items():
        require(report[key] == value)
    require(type(report["report_version"]) is int)
    observations = report["observations"]
    require(isinstance(observations, list) and len(observations) <= 2)
    for index, item in enumerate(observations):
        require(
            set(item) == {"phase", "observed_at", "workspaces"}
            and item["phase"] == PHASES[index]
        )
        date = datetime.fromisoformat(item["observed_at"])
        require(
            date.tzinfo == UTC
            and date.isoformat(timespec="seconds") == item["observed_at"]
        )
        require(set(item["workspaces"]) == {"Acme", "Birch"})
        for row in item["workspaces"].values():
            require(set(row) == set(HEALTHY))
            for surface in ("source_message_row", "stored_ticket_summary"):
                require(row[surface] in ("FOUND", "ABSENT_BY_ID"))
            require(
                type(row["agent_http_status"]) is int
                and row["agent_http_status"] in (200, 400, 401, 403, 404)
            )
            if row["agent_http_status"] == 200:
                require(row["agent_summary"] in ("RETURNED", "NOT_RETURNED"))
            else:
                require(row["agent_summary"] == "INCONCLUSIVE")
    interrupted = report["interrupted_at"]
    require(interrupted is None or interrupted in STAGES)
    status = report["offboarding_http_status"]
    require(status is None or (type(status) is int and status == 204))
    if len(observations) == 2:
        require(status == 204 and interrupted in (None, "cleanup"))
        require(observations[0]["observed_at"] <= observations[1]["observed_at"])
    if status == 204:
        require(
            observations
            and all(row == HEALTHY for row in observations[0]["workspaces"].values())
        )
        if len(observations) == 1:
            require(interrupted in ("observation", "cleanup"))
    elif observations:
        require(interrupted in ("baseline", "offboarding", "cleanup"))
        if interrupted == "offboarding":
            require(
                all(row == HEALTHY for row in observations[0]["workspaces"].values())
            )
    else:
        require(interrupted in ("startup", "seeding", "baseline", "cleanup"))
    result = outcome(observations)
    if interrupted is not None and result != "FAIL":
        result = "INCONCLUSIVE"
    require(result == report["outcome"])


def unique_keys(pairs):
    output = {}
    for key, value in pairs:
        require(key not in output)
        output[key] = value
    return output


if __name__ == "__main__":
    try:
        validate(
            json.loads(Path(sys.argv[1]).read_text(), object_pairs_hook=unique_keys)
        )
    except (IndexError, KeyError, TypeError, ValueError, OSError):
        sys.exit("Invalid upstream report")
    print("Upstream report matches its pinned, content-free contract.")
