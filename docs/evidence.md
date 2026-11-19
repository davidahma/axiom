# Reading an Axiom report

This page describes the controlled worker experiment. To interpret a CI decision on application-supplied evidence, use the [portable gate contract](gate.md).

The reference report answers two questions independently. Did the system exhibit an offboarding failure? Did the experiment produce the observations needed to tell? An observed failure can coexist with a gap in another check.

## Evidence contract, version 1

| Field | Meaning |
| --- | --- |
| `schema_version` | Version of the controlled-fixture report. The opendesk trial has a separate format and records its own upstream build. |
| `fixture_sha256` | Digest of the fixture source file used by the runner. The Git revision identifies the rest of the checkout. The digest alone does not authenticate the producer. |
| `read_roles` | Read-only storage connections inspect the source and summary. A support credential exercises the HTTP endpoint. |
| `cases[].observations` | One timestamped observation per workspace, surface, and checkpoint. Source/summary reads record presence by ID. Support reads record whether the expected marker was returned. |
| `cases[].worker` | Whether the worker captured its input before deletion and how its write attempt ended. |
| `cases[].assessment` | The computed verdict and the exact checks with a finding or an evidence gap. |

Every reference case has 18 observations: three checkpoints × two workspaces × three surfaces. After a successful baseline, a returned Acme marker or a surviving Acme row counts as a failure. An attributable later match also counts when the baseline is incomplete; in that case the run establishes current presence while the timing of its return is uncertain. An unexpected stale write counts even if a different read path filters the result.

A missing observation matrix makes the report invalid. An attempted read that lacked access is a recorded `unavailable` observation. A missing positive baseline, unusable control, or unobserved worker produces an evidence gap. `FAIL` takes precedence over gaps, then `INCONCLUSIVE`, then `PASS`. A PASS applies to the exercised roles, records, and observation window.

The timestamps describe when the observer recorded each group of reads. Ordering comes from the worker and offboarding checkpoints. Validation rejects unknown fields, duplicate JSON keys, malformed timestamps, incomplete matrices, and verdicts that disagree with the observations.

## Following a result back to code

1. [The fixture](../axiom_demo/fixture.py) stores each summary with its workspace and source ID. A separate read-only SQLite connection checks those records. The HTTP support service independently looks up and returns the workspace answer.
2. [The evaluator](../axiom_demo/report.py) consumes the observations. The case name does not select the verdict.
3. [The demo](../axiom_demo/__main__.py) checks that the failure, correction, and missing-baseline scenarios produced their expected signatures. It writes the report before checking those signatures so unexpected outcomes remain inspectable.
4. [The upstream observation](../trials/opendesk/observed.json) records the application image, native offboarding response, storage readback, and support-agent status for an independently maintained application.

The reference JSON contains fixed workspace aliases, states, roles, UTC timestamps, and a fixture digest. It excludes source text, generated answers, credentials, and raw HTTP bodies. The validator checks internal consistency. Independent execution against the pinned system is the way to reproduce the observations.
