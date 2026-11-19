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

## Adapt it to your application

Start with two synthetic tenants whose records you can identify on every surface you intend to check. In [the observation script](observe.py), replace the two reads with your database or application calls and invoke your offboarding job at the same point. Record `completed` after your application confirms completion. Record a failed read as `unavailable`, and keep the surviving tenant's read on the same route as the departing tenant's. Set `revision` to the build you exercised.

In [the policy](policy.json), declare the target, each required probe and its checkpoint before running your test. Keep this file under review alongside the CI job. These two checks cover committed rows in named tables immediately after deletion. An application endpoint, backups, and later worker writes would each need their own observations.
