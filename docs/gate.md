# Use Axiom in your offboarding test

Start with one question your release owner needs answered. For example, after the offboarding job commits, can the support service still read any cached answer for the departing tenant? Use synthetic records in staging. Choose the lookup and reader the application uses and give them a stable scope ID. If the read changes from a support role to an administrator, assign a new scope ID.

Axiom reads two local JSON files. Your team owns the policy and the observer. The gate checks the supplied observations against that policy. It works offline, requires no credentials, and makes no requests to your application.

## Declare a requirement

Keep the policy under review, separately from the code that produces observations. If CI is checking changes from a contributor, take the required policy and gate executable from a trusted revision.

```json
{
  "version": 1,
  "target": "staging-support",
  "probes": [
    {"id": "cache", "scope": "support-answer.by-tenant.v1", "checkpoint": "after_offboarding"}
  ]
}
```

A probe ID names one required check. Its scope identifies what is read, how it is looked up, and which role performs the read. Its checkpoint is either `after_offboarding` or `after_worker`. Declare separate IDs if you need both checkpoints.

## Collect observations in the application test

Seed synthetic markers for a departing tenant (the subject) and a retained tenant (the control). Verify both are initially visible. Run the real offboarding job. Record what happened when you repeat the same reads. An acknowledgment that only schedules cleanup leaves completion unconfirmed until the application reports that cleanup finished.

```json
{
  "version": 1,
  "target": "staging-support",
  "revision": "build-42",
  "run_id": "ci-731-attempt-1",
  "offboarding": "completed",
  "probes": [
    {
      "id": "cache",
      "scope": "support-answer.by-tenant.v1",
      "checkpoint": "after_offboarding",
      "before": {"subject": "present", "control": "present"},
      "after": {"subject": "absent", "control": "present"}
    }
  ]
}
```

| Read state | When to record it |
| --- | --- |
| `present` | A successful read found the named subject or control record, or returned its attributable marker. |
| `absent` | That read completed successfully and the record or marker was absent within its scope. |
| `unavailable` | The read could not establish presence or absence. Examples include a lost connection, an authorization error and a route that no longer accepts the workspace. |
| `not_tested` | The test did not exercise this read. |

For an `after_worker` observation, also include a `worker` object on that probe. Record `captured_before_offboarding` and `finished_after_offboarding` as booleans. Each flag is true only when the producer observed that event for the **same job**. Take the final reads after that job finishes. A sleep alone cannot establish the ordering. Either missing observation, represented by a false flag, leaves the worker check inconclusive unless there is also an observed residual.

Write `offboarding` as `completed` or `unconfirmed`. Use opaque, non-sensitive identifiers. Target, revision, run ID, probe IDs and scope IDs start with an ASCII letter or digit, followed by up to 127 ASCII letters, digits, dots, underscores or hyphens. These identifiers appear in the decision. Keep customer names, excerpts, raw requests, credentials and other payloads out of the files. The gate accepts UTF-8 JSON in regular files, at most 1 MiB per file and up to 256 unique probe IDs. It rejects unsupported versions, duplicate keys, unknown fields and malformed observations.

## Run the CI decision

Use Python 3.11+ with the release archive. From a source checkout you can substitute `python3 -m axiom_demo` for `python3 axiom.pyz`. Build the same archive locally with `make bundle`. For v0.3.1 and later, first [verify the archive against its signed build provenance](../SECURITY.md#verify-a-release-download). To check a downloaded archive against the release checksum, place both files together and run `sha256sum -c axiom.pyz.sha256` on Linux or `shasum -a 256 -c axiom.pyz.sha256` on macOS.

```sh
python3 axiom.pyz gate --policy ci/offboarding-policy.json \
  --observations "$RUN_DIR/observations.json" --output "$RUN_DIR/decision.json" \
  --expect-run "$TEST_RUN_ID" --expect-revision "$TESTED_REVISION"
```

Set both expected values from your job environment. For GitHub Actions, one run ID can have multiple attempts. A suitable ID is `${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}`. Pass the tested artifact's revision and use a fresh output directory for each attempt. The SQLite example accepts matching `--run-id` and `--revision` arguments. [Example producer](../examples/sqlite/)

| Exit | Decision | Release owner action |
| --- | --- | --- |
| 0 | PASS | Every required probe observed both positive baselines, an absent subject and a healthy control after confirmed offboarding. Any required worker overlap was observed. |
| 1 | FAIL | At least one in-scope read found the subject after confirmed offboarding. Inspect that surface and rerun after correcting the cleanup. |
| 2 | INCONCLUSIVE | Resolve the listed gaps. Check access, control visibility, job completion, scope changes, worker ordering and missing probes. |
| 3 | Invalid invocation, evidence or output | Correct the input or path and rerun. A decision at a previously used output path could belong to an earlier attempt. |

Only exit 0 passes a deployment gate. For exits 0, 1 and 2, optional `--output` writes a decision with the target, revision, run ID, overall verdict and one row per required probe in policy order. Each row names its scope, checkpoint, verdict and reasons. The decision records SHA-256 digests of the exact policy and observation bytes, including whitespace. Replaying those same files yields the same decision. Preserve all three files together if a reviewer needs to reproduce it.

An omitted required probe produces `missing_probe`. A changed scope or checkpoint produces a gap. If that changed read found the subject after confirmed offboarding, `observed_after_subject_present_outside_policy` flags the finding for follow-up. Evidence for an undeclared ID, a different target, or a mismatched expected run or revision exits 3. When offboarding is unconfirmed, the available observations cannot establish post-deletion survival.

These checks depend on the fidelity of the application test. The producer must identify the correct subject and control and exercise its declared reader, timing, and scope. The file digests support replay. They do not authenticate the observer. [See how this distinction plays out on opendesk](../trials/opendesk/README.md)
