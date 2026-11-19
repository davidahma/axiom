# Two workspaces on opendesk

This trial exercises the normal workspace offboarding path of [opendesk v0.4.13](https://github.com/useopendesk/opendesk/releases/tag/v0.4.13). It compares database observations with the view available to one support agent who belongs to both synthetic workspaces.

## Reproduce

From the Axiom repository root, use Python 3.11 or later and Docker Compose v2 with a running Docker daemon.

```sh
python3 trials/opendesk/run.py --report artifacts/opendesk.json
python3 trials/opendesk/verify_report.py artifacts/opendesk.json
```

The first run pulls three images pinned by digest. The trial starts a randomly named Compose project, uses an internal network with no published ports, generates ephemeral service credentials, and removes its containers and volumes on exit. The host needs no model key or database credentials. The runner accepts an output path and always creates its own local environment.

[The checked-in observation](observed.json) records an actual run. The database readback found both Acme records before offboarding and found neither afterward. The agent's subsequent Acme request returned HTTP 400 with `workspace_required`. The application visibility check is **INCONCLUSIVE** because the workspace context is no longer available. The same agent could still read Birch's summary. The terminal result **COMPLETED** covers the observations recorded on this build.

## Observations

| Step | What actually executes |
| --- | --- |
| Create | The trial registers a workspace owner and a separate support agent. The owner enables MFA and authenticates with a one-time recovery code. The owner creates Acme and Birch through opendesk, invites the same support account to both as an agent, and the agent accepts each invitation. |
| Generate | In each workspace the owner enters a synthetic inbound ticket. The agent invokes the ordinary ticket-summary endpoint. The local model stub recognises the fixture phrase in the model request and returns deterministic structured content. opendesk processes and persists it. |
| Establish the baseline | Using the real agent account, the trial reads both ticket summaries. A separate SQL role checks the source message by its primary key and the presence of the ticket's stored `custom.ai_summary` by ticket ID. It has column-level SELECT grants. The SQL lookups do not depend on a surviving workspace membership. |
| Offboard | Only after the four positive storage observations and both agent reads succeed, the MFA-authenticated owner invokes opendesk's workspace delete endpoint for Acme. The database observer performs no deletion. |
| Read again | Repeat both SQL lookups and both agent calls. Detection of a surviving Acme row, stored summary, or served synthetic answer produces **FAIL**. Inconclusive setup, a lost Birch control, or a cleanup failure makes the command exit unsuccessfully. The report uses fixed field names, roles and enumerated outcomes in place of customer content. |

The native summary is stored on the ticket. Its source in this trial is a separate inbound message. This measures logical presence at those recorded identifiers. Copies in other tables, search indexes, backups, physical storage, and other application paths are outside its coverage. Both agent-initiated summary requests finish before offboarding. **Upstream worker overlap is NOT TESTED.** The Axiom reference fixture exercises that case separately.

## Upstream boundary

The trial runs the published multi-architecture image from [the pinned release](https://github.com/useopendesk/opendesk/releases/tag/v0.4.13). The release records the image digest in `images.json`. The application source, database migrations, ticket save, membership checks, and deletion implementation come from upstream. Fixture data, the model substitute, the read-only observer, and the report belong to Axiom. For the exact behavior at this revision, see the [summary writer](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/ai/features.go), [workspace API](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/core/workspaces.go), and [offboarding operation](https://github.com/useopendesk/opendesk/blob/e0012447924c5ac8a13a51d2cd41a6496bc26fb3/internal/core/ops.go).
