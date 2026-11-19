"""Run the pinned opendesk trial in a newly allocated, disposable Compose project."""

import argparse
import base64
import hmac
import json
import os
import secrets
import struct
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from verify_report import HEALTHY, METADATA, outcome, validate

HERE = Path(__file__).resolve().parent
SUPPORT_EMAIL = "agent@example.test"
CASES = {
    "Acme": ("copper compass", "Route returns to the copper-compass desk."),
    "Birch": ("violet sail", "Route returns to the violet-sail desk."),
}


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


class Stack:
    def __init__(self):
        self.project = "axiom-od-" + secrets.token_hex(6)
        self.env = os.environ.copy()
        for name in (
            "DATABASE_PASSWORD",
            "AUTH_SECRET",
            "CREDENTIALS_KEY",
            "NATS_TOKEN",
            "MODEL_KEY",
        ):
            self.env["TRIAL_" + name] = secrets.token_hex(32)

    def compose(self, *args, stdin=None, capture=False):
        command = [
            "docker",
            "compose",
            "-f",
            str(HERE / "compose.yaml"),
            "-p",
            self.project,
            *args,
        ]
        result = subprocess.run(
            command,
            input=stdin,
            env=self.env,
            text=True,
            check=True,
            stdout=subprocess.PIPE if capture else sys.stderr,
        )
        return result.stdout.strip() if capture else None

    def sql(self, role, statement):
        return self.compose(
            "exec",
            "-T",
            "database",
            "psql",
            "-XqAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            role,
            "-d",
            "opendesk",
            stdin=statement,
            capture=True,
        )


class API:
    def __init__(self, stack):
        self.stack = stack

    def request(
        self,
        method,
        path,
        body=None,
        token=None,
        workspace=None,
        allowed=(200, 201, 204),
    ):
        wire = {
            "method": method,
            "path": path,
            "body": body,
            "token": token,
            "workspace": workspace,
        }
        result = self.stack.compose(
            "exec",
            "-T",
            "model",
            "python",
            "-B",
            "/stub/transport.py",
            stdin=json.dumps(wire),
            capture=True,
        )
        status, value = json.loads(result)
        if status not in allowed:
            code = value.get("code", "unclassified")
            raise RuntimeError(f"{method} {path} returned HTTP {status} ({code})")
        return status, value

    def mutate(self, path, body, token=None, workspace=None):
        return self.request("POST", path, body, token, workspace)[1]


def account(api, email, name):
    password = secrets.token_urlsafe(28) + "aA9!"
    user = api.mutate(
        "/auth/register", {"email": email, "password": password, "name": name}
    )
    return user["access_token"], password


def verified_owner(api):
    email = "owner@example.test"
    token, password = account(api, email, "Demo Owner")
    seed = api.mutate("/auth/totp/setup", {}, token)["secret"]
    key = base64.b32decode(seed + "=" * (-len(seed) % 8))
    digest = hmac.digest(key, struct.pack(">Q", int(time.time()) // 30), "sha1")
    offset = digest[-1] & 15
    number = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFF_FFFF
    recovery = api.mutate(
        "/auth/totp/enable", {"code": f"{number % 1_000_000:06d}"}, token
    )
    login = api.mutate("/auth/login", {"email": email, "password": password})
    return api.mutate(
        "/auth/mfa",
        {
            "mfa_token": login["mfa_token"],
            "code": recovery["recovery_codes"][0],
        },
    )["access_token"]


def seed(api, owner, agent, label):
    workspace = str(UUID(api.mutate("/workspaces", {"name": label}, owner)["id"]))
    invitation = api.mutate(
        "/invitations", {"email": SUPPORT_EMAIL, "role": "agent"}, owner, workspace
    )
    link = api.mutate(
        "/invitations/" + invitation["id"] + "/link", {}, owner, workspace
    )
    invite_token = parse_qs(urlsplit(link["url"]).query)["token"][0]
    api.mutate("/invitations/accept", {"token": invite_token}, agent)
    marker, summary = CASES[label]
    ticket = api.mutate(
        "/tickets",
        {
            "subject": "Returns desk handoff",
            "channel": "api",
            "kind": "reply",
            "direction": "inbound",
            "contact": {"name": "Demo Contact", "email": "contact@example.test"},
            "body_html": "<p>Use the "
            + marker
            + " reference for the returns desk.</p>",
        },
        owner,
        workspace,
    )
    ticket_id = str(UUID(ticket["id"]))
    messages = api.request(
        "GET", "/tickets/" + ticket_id + "/messages", token=agent, workspace=workspace
    )[1]
    source_ids = [
        item["id"] for item in messages["data"] if marker in item["body_text"]
    ]
    if len(source_ids) != 1:
        raise RuntimeError("Could not establish an unambiguous source message")
    answer = api.mutate("/tickets/" + ticket_id + "/ai/summary", {}, agent, workspace)
    if answer.get("summary") != summary:
        raise RuntimeError(
            "Summary endpoint did not return the expected synthetic derivative"
        )
    return workspace, ticket_id, str(UUID(source_ids[0]))


def observe(stack, api, agent, label, ids):
    workspace, ticket, message = ids
    # Each bound identifier was parsed as UUID above. Look up the records by
    # their own primary keys so workspace visibility cannot hide a leftover.
    counts = stack.sql(
        "axiom_observer",
        f"""
        SELECT
          (SELECT count(*) FROM messages WHERE id = '{message}'::uuid),
          (SELECT count(*) FROM tickets WHERE id = '{ticket}'::uuid AND custom ? 'ai_summary');
    """,
    )
    source, summary = map(int, counts.split("|"))
    status, value = api.request(
        "GET",
        "/tickets/" + ticket,
        token=agent,
        workspace=workspace,
        allowed=(200, 400, 401, 403, 404),
    )
    if status == 400 and value.get("code") != "workspace_required":
        raise RuntimeError("Unexpected support-path validation error")
    if status == 200:
        shown = value.get("custom", {}).get("ai_summary", {}).get("text")
        agent_result = "RETURNED" if shown == CASES[label][1] else "NOT_RETURNED"
    else:
        agent_result = "INCONCLUSIVE"
    return {
        "source_message_row": "FOUND" if source else "ABSENT_BY_ID",
        "stored_ticket_summary": "FOUND" if summary else "ABSENT_BY_ID",
        "agent_summary": agent_result,
        "agent_http_status": status,
    }


def run(stack, report):
    stack.compose("up", "--detach", "--wait", "--wait-timeout", "150")
    api = API(stack)
    stack.sql(
        "opendesk",
        """
        CREATE ROLE axiom_observer LOGIN;
        GRANT SELECT (id) ON messages TO axiom_observer;
        GRANT SELECT (id, custom) ON tickets TO axiom_observer;
    """,
    )
    report["interrupted_at"] = "seeding"
    owner = verified_owner(api)
    agent, _ = account(api, SUPPORT_EMAIL, "Demo Agent")
    ids = {label: seed(api, owner, agent, label) for label in CASES}

    def checkpoint(phase):
        return {
            "phase": phase,
            "observed_at": now(),
            "workspaces": {
                label: observe(stack, api, agent, label, item)
                for label, item in ids.items()
            },
        }

    report["interrupted_at"] = "baseline"
    baseline = checkpoint("before_offboarding")
    report["observations"].append(baseline)
    if any(row != HEALTHY for row in baseline["workspaces"].values()):
        return
    report["interrupted_at"] = "offboarding"
    status, _ = api.request(
        "DELETE",
        "/workspace",
        {"confirm_name": "Acme"},
        owner,
        ids["Acme"][0],
        allowed=(204,),
    )
    report["offboarding_http_status"] = status
    report["interrupted_at"] = "observation"
    report["observations"].append(checkpoint("after_offboarding"))
    report["interrupted_at"] = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    stack = Stack()
    evidence = {
        **METADATA,
        "outcome": "INCONCLUSIVE",
        "interrupted_at": "startup",
        "observations": [],
        "offboarding_http_status": None,
    }
    try:
        run(stack, evidence)
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        subprocess.SubprocessError,
    ) as exc:
        print(
            f"Trial interrupted at {evidence['interrupted_at']} ({type(exc).__name__})",
            file=sys.stderr,
        )
    finally:
        try:
            stack.compose("down", "--volumes", "--remove-orphans")
        except (OSError, subprocess.SubprocessError):
            print(
                f"Cleanup failed for disposable project {stack.project}",
                file=sys.stderr,
            )
            evidence["interrupted_at"] = "cleanup"
    evidence["outcome"] = outcome(evidence["observations"])
    if evidence["interrupted_at"] and evidence["outcome"] != "FAIL":
        evidence["outcome"] = "INCONCLUSIVE"
    validate(evidence)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=args.report.parent, delete=False
    ) as output:
        json.dump(evidence, output, indent=2)
        output.write("\n")
    Path(output.name).replace(args.report)
    print(f"{evidence['outcome']}: {args.report}")
    return 0 if evidence["outcome"] == "COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
