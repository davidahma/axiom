# Gate an offboarding job with SQLite observations

This example checks a support application's ticket table and answer cache immediately after a synthetic tenant leaves. Each table has one row per tenant. Acme leaves and Birch stays. The observer reads the same two tenant keys on separate read-only database connections before and after the job commits. The JSON contains the read outcomes, a revision, and a run ID. Ticket text, cached answers, and tenant keys stay in the temporary database.

Run these commands from the repository root with Python 3.11 or newer:

```sh
python3 examples/sqlite/observe.py --case residual --output artifacts/sqlite-run.json &&
  python3 -m axiom_demo gate --policy examples/sqlite/policy.json --observations artifacts/sqlite-run.json
```

| `--case` | What the application or observer does | Expected gate verdict |
| --- | --- | --- |
| `clean` | The job deletes Acme's ticket and cached answer. Both Birch rows remain readable. | PASS |
| `residual` | The job commits the ticket deletion and skips the cache. The observer reads Acme's cache row after offboarding. | FAIL |
| `unavailable` | The job commits both deletions. The cache reader loses its connection before the second read. | INCONCLUSIVE |

By default the producer generates a unique run ID and uses the script's SHA-256 digest as its revision. In CI, pass the job's run identifier and tested build to the producer with `--run-id` and `--revision`. Give those same values to the gate with `--expect-run` and `--expect-revision` so a leftover observation file from a different run or build cannot satisfy the check.

## Bind the reads to a particular request

Issue the request before the job starts. These commands use a new directory so each file belongs to this attempt.

```sh
run_dir=$(mktemp -d)
python3 -m axiom_demo request --policy examples/sqlite/policy.json \
  --context staging --revision build-42 --run-id ci-17 --output "$run_dir/request.json"
python3 examples/sqlite/observe.py --case clean --revision build-42 \
  --request "$run_dir/request.json" --output "$run_dir/job.json"
```

Keep the SHA-256 value printed by `request` in the offboarding ticket. Paste that value at the `read` prompt when creating the receipt. For this synthetic job both storage reads pass.

```sh
read -r TICKET_REQUEST_SHA256
python3 -m axiom_demo receipt --request "$run_dir/request.json" \
  --expect-request "$TICKET_REQUEST_SHA256" --policy examples/sqlite/policy.json \
  --evidence "$run_dir/job.json" --output "$run_dir/receipt.json"
```

The producer accepts a `staging` request for `sqlite-support`. It takes the run ID from the issued request and checks the requested revision against the build identifier you supply. Each request gets its own pair of synthetic tenants in SQLite. The native deletion job resolves its subject against that registration and commits its completion row in the same transaction as the deletions. After the storage checks, a read-only connection retrieves the job ID, request digest, start time and completion state from the committed row. Its readback time marks the end of the observation window. The local tenant keys stay in SQLite.

Try `--case residual` with a fresh request to see the cached answer survive. Passing the first request's evidence to the second request fails the digest check even if both runs used the same build. A failed transaction leaves the rows in place and produces no new job packet.

## Adapt it to your application

Start with two synthetic tenants whose records you can identify on every surface you intend to check. In [the observation script](observe.py), replace the two reads with your database or application calls and invoke your offboarding job at the same point. Record `completed` after your application confirms completion. Record a failed read as `unavailable`, and keep the surviving tenant's read on the same route as the departing tenant's. Set `revision` to the build you exercised.

In [the policy](policy.json), declare the target, each required probe and its checkpoint before running your test. Keep this file under review alongside the CI job. These two checks cover committed rows in named tables immediately after deletion. An application endpoint, backups, and later worker writes would each need their own observations.
