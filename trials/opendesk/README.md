# Two workspaces on opendesk

This trial exercises the normal workspace offboarding path of [opendesk v0.4.13](https://github.com/useopendesk/opendesk/releases/tag/v0.4.13). It compares database observations with the view available to one support agent who belongs to both synthetic workspaces.

## Reproduce

From the Axiom repository root, use Python 3.11 or later and Docker Compose v2 with a running Docker daemon.

```sh
python3 trials/opendesk/run.py --report artifacts/opendesk.json
python3 trials/opendesk/verify_report.py artifacts/opendesk.json
```

The first run pulls three images pinned by digest. The trial starts a randomly named Compose project, uses an internal network with no published ports, generates ephemeral service credentials, and removes its containers and volumes on exit. The host needs no model key or database credentials. The runner accepts an output path and always creates its own local environment.

The runner allows 15 minutes for startup and image downloads, 60 seconds per Compose execution, and 90 seconds for cleanup. A read timeout leaves the affected probe inconclusive. A cleanup timeout records the cleanup interruption and prints the project name for the operator. The HTTP client sends one request to the app container and reports any redirect as an HTTP error.

[The checked-in observation](observed.json) records an actual run. The database readback found both Acme records before offboarding and found neither afterward. The agent's subsequent Acme request returned HTTP 400 with `workspace_required`. The application visibility check is **INCONCLUSIVE** because the workspace context is no longer available. The same agent could still read Birch's summary. The terminal result **COMPLETED** covers the observations recorded on this build.

## Apply the offboarding policy

From the repository root, run the gate on the version 2 trial you just generated.

```sh
python3 trials/opendesk/to_gate.py artifacts/opendesk.json --output artifacts/opendesk-observations.json
python3 -m axiom_demo gate --policy trials/opendesk/policy-v2.json \
  --observations artifacts/opendesk-observations.json --output artifacts/opendesk-decision.json
```

On the pinned build the gate exits **2 (INCONCLUSIVE)**. Two checks pass. The database observer saw the Acme source message and summary disappear while the Birch records remained readable. The agent-read check stays inconclusive because the HTTP 400 prevented the caller from testing whether Acme's answer would be returned. The worker-summary check stays inconclusive because no writer was held across deletion in this trial. Its post-worker readings are both `not_tested`.

To replay [the version 1 run](observed.json) without Docker, use that file as the adapter input and [the version 1 policy](policy.json) as the gate policy. Its storage probe checked for a summary key and its agent probe compared the complete answer. The adapter preserves those original scope IDs. The v2 policy requires the new marker-based measurements.

The adapter validates the pinned trial report, converts each workspace read, and carries the upstream commit into `revision`. Its `run_id` identifies the exact input file by SHA-256. An interrupted read leaves the corresponding observations untested. HTTP 204 confirms the offboarding operation. Database and application observations determine the gate decision. The trial command also checks setup and teardown, so keep its exit status in CI alongside the gate.

## Observations

| Step | What actually executes |
| --- | --- |
| Create | The trial registers a workspace owner and a separate support agent. The owner enables MFA and authenticates with a one-time recovery code. The owner creates Acme and Birch through opendesk, invites the same support account to both as an agent, and the agent accepts each invitation. |
| Generate | In each workspace the owner enters a synthetic inbound ticket. The agent invokes the ordinary ticket-summary endpoint. The local model stub recognises the fixture phrase in the model request and returns deterministic structured content. opendesk processes and persists it. |
| Establish the baseline | Using the real agent account, the trial reads both ticket summaries. A separate SQL role checks the source message by primary key and reads the summary field on the named ticket. The storage and agent reads look for each tenant's synthetic marker in the summary text and key points. The SQL role has column-level SELECT grants. |
| Offboard | Only after the four positive storage observations and both agent reads succeed, the MFA-authenticated owner invokes opendesk's workspace delete endpoint for Acme. The database observer performs no deletion. |
| Read again | Repeat both SQL lookups and both agent calls. Detection of a surviving Acme row, stored summary, or served synthetic answer produces **FAIL**. Inconclusive setup, a lost Birch control, or a cleanup failure makes the command exit unsuccessfully. The report uses fixed field names, roles and enumerated outcomes in place of customer content. |

Version 2 records each read separately. A read error marks that read inconclusive, and an unattempted read stays untested. A later timeout cannot erase an earlier observed leftover. On a successful HTTP response the observer checks that the ticket ID matches and `custom` is an object. A missing, null or empty summary can establish absence on that ticket. Unexpected response shapes and unrelated nonempty summary text remain inconclusive. On either surface, the fixture marker in a longer summary still counts as present. These checks follow opendesk's [ticket response type](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/domain/types.go) and [summary writer](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/ai/features.go).

The native summary is stored on the ticket. Its source in this trial is a separate inbound message. This measures logical presence at those recorded identifiers. Copies in other tables, search indexes, backups, physical storage, and other application paths are outside its coverage. Both agent-initiated summary requests finish before offboarding. **Upstream worker overlap is NOT TESTED.** The Axiom reference fixture exercises that case separately.

## Upstream boundary

The trial runs the published multi-architecture image from [the pinned release](https://github.com/useopendesk/opendesk/releases/tag/v0.4.13). The release records the image digest in `images.json`. The application source, database migrations, ticket save, membership checks, and deletion implementation come from upstream. Fixture data, the model substitute, the read-only observer, and the report belong to Axiom. For the exact behavior at this revision, see the [summary writer](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/ai/features.go), [workspace API](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/core/workspaces.go), and [offboarding operation](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/core/ops.go).

## Trial image review

The Compose project accepts synthetic inputs on its own internal network and publishes no host ports. Each service runs as a non-root user with a read-only root filesystem, dropped Linux capabilities, and process and memory limits. PostgreSQL starts directly as its database OS user. The runner removes the containers and their data volumes after the trial.

The November 19, 2026 Grype package inventory for the pinned Linux amd64 images returned the following counts. A match identifies an installed package version listed in an advisory. Runtime reachability and other architectures were outside the scan.

| Trial image | Critical matches | High matches |
| --- | ---: | ---: |
| opendesk v0.4.13 | 1 | 0 |
| pgvector pg17 (PostgreSQL 17.12) | 12 | 206 |
| CPython 3.12.16 slim | 0 | 78 |

The pinned opendesk binary includes an affected Brotli decoder. The trial client sends synthetic JSON to fixed API routes. Six pgvector Critical matches concern the Go runtime embedded in `gosu`, which the non-root database startup skips. The Python patch update removed the two Critical matches in the previous model-stub image. Keep these images scoped to the disposable trial. Axiom’s portable CLI uses the Python standard library and ships none of these container images. [Go Brotli advisory](https://pkg.go.dev/vuln/GO-2026-6888) · [Compose configuration and image digests](compose.yaml)
