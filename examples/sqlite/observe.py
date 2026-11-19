"""Exercise a synthetic application's offboarding job and export measured reads."""

import argparse
import hashlib
import json
import re
import sqlite3
import tempfile
import uuid
from contextlib import closing
from pathlib import Path


def seed(db):
    with db:
        db.execute("CREATE TABLE tickets (tenant TEXT PRIMARY KEY, ticket TEXT)")
        db.execute("CREATE TABLE cached_answers (tenant TEXT PRIMARY KEY, answer TEXT)")
        for tenant in ("acme", "birch"):
            db.execute(
                "INSERT INTO tickets VALUES (?, ?)", (tenant, f"{tenant} ticket")
            )
            db.execute(
                "INSERT INTO cached_answers VALUES (?, ?)", (tenant, f"{tenant} answer")
            )


def offboard(db, case):
    try:
        with db:
            db.execute("DELETE FROM tickets WHERE tenant = ?", ("acme",))
            if case != "residual":
                db.execute("DELETE FROM cached_answers WHERE tenant = ?", ("acme",))
    except sqlite3.Error:
        return "unconfirmed"
    return "completed"


def read_pair(reader, query):
    def read(tenant):
        try:
            row = reader.execute(query, (tenant,)).fetchone()
        except sqlite3.Error:
            return "unavailable"
        return "absent" if row is None else "present"

    return {"subject": read("acme"), "control": read("birch")}


def observe(path, case, run_id, revision):
    uri = path.as_uri() + "?mode=ro"
    with closing(sqlite3.connect(path)) as writer:
        seed(writer)
        with (
            closing(sqlite3.connect(uri, uri=True)) as source_reader,
            closing(sqlite3.connect(uri, uri=True)) as cache_reader,
        ):
            probes = [
                (
                    "source",
                    "tickets",
                    source_reader,
                    "SELECT 1 FROM tickets WHERE tenant = ?",
                ),
                (
                    "cache",
                    "cached_answers",
                    cache_reader,
                    "SELECT 1 FROM cached_answers WHERE tenant = ?",
                ),
            ]
            observations = [
                {
                    "id": probe_id,
                    "scope": scope,
                    "checkpoint": "after_offboarding",
                    "before": read_pair(reader, query),
                }
                for probe_id, scope, reader, query in probes
            ]
            status = offboard(writer, case)
            if case == "unavailable":
                cache_reader.close()
            for item, (_, _, reader, query) in zip(observations, probes):
                item["after"] = read_pair(reader, query)

    return {
        "version": 1,
        "target": "sqlite-support",
        "revision": revision,
        "run_id": run_id,
        "offboarding": status,
        "probes": observations,
    }


def identifier(value):
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", value):
        raise argparse.ArgumentTypeError(
            "Use 1 to 128 letters, digits, dots, underscores, or hyphens. "
            "Start with a letter or digit."
        )
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case", choices=("clean", "residual", "unavailable"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--run-id", type=identifier, help="CI run identifier (default: a UUID)"
    )
    parser.add_argument(
        "--revision",
        type=identifier,
        help="tested build identifier (default: script SHA-256)",
    )
    args = parser.parse_args()
    run_id = args.run_id or uuid.uuid4().hex
    revision = args.revision or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory() as directory:
        observations = observe(
            Path(directory).resolve() / "support.db", args.case, run_id, revision
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
