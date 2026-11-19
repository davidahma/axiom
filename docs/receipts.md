# Review a deletion request

A customer has asked a vendor to remove its support data. Before signing a response, the reviewer needs to know which request the deletion job processed, which copies were checked, and what remains open. An Axiom receipt brings together the application's measured reads, the original files supplied by providers, and any declared backup expiry.

## Try a complete case

From the repository root, run `make receipt-example` with Python 3.11+. The example issues a staging request, offboards a synthetic tenant, generates a receipt, replays it, and writes `artifacts/receipt-example.zip`. You can also download `axiom.pyz` and the example ZIP from the [release](https://github.com/davidahma/axiom/releases/tag/v0.3.0).

| Evidence in the example | What the reviewer can say |
| --- | --- |
| Source and answer-cache reads | Both records were present before offboarding and absent afterward. The retained tenant stayed visible on both reads. |
| Provider statement | The fictional provider reports deletion. Axiom checks the supplied document’s bytes against the description of the evidence. The reviewer decides whether its issuer, scope and wording support the claim. |
| Backup schedule | The fixture lists an expiry date. Evidence of actual backup deletion is outstanding. |

The technical verdict is **PASS**. The review status is **OPEN_ITEMS**. Replaying a valid receipt returns the same review status, including a nonzero exit when something remains open.

Extract the example into a fresh directory beside the CLI. Set `EXPECTED_REQUEST_SHA256` to the digest printed in the release notes or in the reference job's GitHub Actions summary. The ZIP includes a copy for inspecting the fixture. For a real review, use the digest already saved in the original ticket.

```sh
unzip receipt-example.zip -d case
cd case
python3 ../axiom.pyz verify-receipt \
  --request request.json --expect-request "$EXPECTED_REQUEST_SHA256" \
  --policy policy.json --evidence evidence.json --receipt receipt.json \
  --record provider.json provider.txt --record backups.json backups.txt
```

## Bind a case before the job starts

1. **Accept the instruction.** The case owner establishes the customer's authority, the data covered, deadlines, any retention obligations, and the responsible signer in the private case system. The case owner selects a reviewed probe policy and declares any required provider statements or backup schedules.
2. **Issue one manifest per attempt.** Give Axiom the actual target revision and run ID. Save the printed SHA-256 in that case **before dispatching the deletion job**. The manifest has its own random request ID, so two attempts on the same revision and run have different digests. Keep the identity-to-request mapping in the case system. Roles and tenant names belong there too when they would identify a customer.
3. **Collect observations.** The application's trusted job resolves that request to the intended tenant, records the request digest with the job, and confirms completion through its own state. The observer reads back that job record and measures the subject and retained control at the required checkpoints. The SQLite example commits the job record and deletions in one database transaction. An observer working with another system must implement its own equivalent correlation.
4. **Review and retain.** Compare against the digest from step 2. Keep the inputs and the new receipt together under the case's access and retention policy. An accountable reviewer decides what the organization can sign. A retry gets a fresh manifest and an explicit link to the previous attempt in the case system. If the application returns a job ID at dispatch, save it in the case too. Pass `--expect-job ID` to both receipt commands to distinguish that job even if two workers reused the same manifest.

For a staging run with no external exhibits, run these commands from the repository root. Use a fresh `case/` directory for the attempt.

```sh
python3 -m axiom_demo request --context staging --run-id attempt-1 --revision build-42 \
  --policy examples/sqlite/policy.json --output case/request.json
# Save the printed digest in the case system and set EXPECTED_REQUEST_SHA256 to that value.
python3 examples/sqlite/observe.py --request case/request.json --revision build-42 \
  --case residual --output case/evidence.json
python3 -m axiom_demo receipt --request case/request.json --expect-request "$EXPECTED_REQUEST_SHA256" \
  --policy examples/sqlite/policy.json --evidence case/evidence.json --output case/receipt.json
```

The final command exits 1 and identifies the surviving cache row. The example accepts only `staging` requests. The CLI also accepts `--context customer` for an organization's own producer. Context, timestamps and observed reads come from the participating systems. The label alone cannot establish where the job ran. The existing opendesk trial has no native request binding and is eligible only for the staging gate. [SQLite producer](../examples/sqlite/) · [opendesk trial](../trials/opendesk/README.md)

## What crosses each boundary

| Input | Who supplies it | What Axiom checks |
| --- | --- | --- |
| Request manifest and expected digest | Case owner, prior to dispatch | Fresh request ID, selected target, policy digest, context, revision, run ID and required external records. The expected digest is supplied independently at review time. |
| Job evidence | Application and observer | Job ID and matching request digest, ordered UTC timestamps, matching target/build/run, probe scope and checkpoints, positive baselines and retained controls. The original gate computes the technical verdict. |
| Supplemental evidence | Case owner or provider | One declared ID per item, matching request and document digests, issuer label, and the stated outcome or expiry. Original document contents stay outside the receipt. |
| Review receipt | Axiom | Replay recomputes every result. Each input digest covers the file's exact bytes. Receipt comparison checks the complete JSON value and types. |

An observation envelope has three top-level fields, `version` (1), `job` and `observations`. The job has `id`, `request_sha256`, `started_at` and `observed_at`. Use UTC timestamps at second precision, such as `2030-01-15T12:00:00Z`. The nested observations use the [existing gate format](gate.md). Bare staging reports cannot be turned into request evidence by the CLI. A producer with authority to fabricate job records or readings could still make false claims.

## Add a provider statement or backup schedule

Declare the requirement at issuance with `--statement provider` or `--schedule backups`. At receipt generation and replay, use `--record DESCRIPTOR ORIGINAL_DOCUMENT` once for each supplied item. The descriptor is a small UTF-8 JSON file with these fields.

| Field | Value |
| --- | --- |
| `version`, `id`, `kind` | Version 1, the ID declared in the manifest, and either `provider_statement` or `retention_schedule`. |
| `request_sha256`, `document_sha256` | Lowercase SHA-256 digests of the exact issued manifest and original attachment. |
| `issuer` | A non-sensitive identifier for the organization or system named as the source. |
| `outcome` | For statements only. Use `reported_deleted`, `reported_retained` or `unresolved`. A negative or unclear statement leaves review open. |
| `expires_on` | For schedules only. Use an ISO calendar date such as `2030-01-31`. A schedule stays open after that date. |

The reviewer should read the original document and verify its issuer and applicability to this customer. Axiom checks file identity and repeats the operator's classification. It does not interpret prose or validate a provider signature. Keep attachments private. Only synthetic exhibits are included in Axiom releases. Missing required records stay visible in the receipt. To document a later deletion, retain the original receipt in the case and add a separately evidenced follow-up.

## Read the return code

| Code | Review status | Meaning |
| --- | --- | --- |
| 0 | `READY_FOR_REVIEW` | The named reads passed and any required statements report deletion. A reviewer can consider the evidence. |
| 1 | `RESIDUAL_FOUND` | A required, attributable post-offboarding read found data. Other open items are preserved. |
| 2 | `OPEN_ITEMS` | A probe is inconclusive, an exhibit is missing, a provider reports retention or uncertainty, or a backup has only a schedule. |
| 3 | Invalid invocation, input, output or replay | Check the case digest, policy, run identity, timing, attachment bytes and receipt. Axiom creates requests and receipts only at new paths. |

`verify-receipt` prints a confirmation when the replay matches. Codes 1 and 2 still describe the reproduced result. Review stays limited to the declared systems and observation window. Offline copies, model training data and later writes need their own evidence when relevant.

## Sign a reviewed receipt

An organization that uses OpenSSH signing can attach a detached signature to the exact receipt bytes. A reviewer with a separately trusted allowed-signers file can authenticate the signer before replaying the evidence. The following commands use an existing authorized signing key and the identity registered in the reviewer's trust file. The test suite exercises the recipe with a disposable key. [OpenSSH signing and verification](https://man.openbsd.org/ssh-keygen)

```sh
ssh-keygen -Y sign -f "$SIGNING_KEY" -n axiom-receipt-v1 receipt.json
ssh-keygen -Y verify -f "$TRUSTED_ALLOWED_SIGNERS" -I "$AUTHORIZED_SIGNER" \
  -n axiom-receipt-v1 -s receipt.json.sig < receipt.json
```

A signature identifies the key that endorsed those bytes. A reviewer still needs to examine the evidence, exceptions and uncovered systems.

## Why a vendor might attach this to a certificate

EU GDPR Article 28(3)(g)–(h) addresses processor contracts, the controller's choice of deletion or return after services end, existing copies, and information for demonstrating compliance and supporting audits. Where the parties use the Commission's standard controller–processor clauses and the controller chooses deletion, clause 10(d) calls for the processor to certify deletion to the controller. An individual's erasure request under Article 17 is a distinct process. The organization determines which duties and contractual deadlines apply and what it can certify. Axiom supplies a technical evidence attachment. [GDPR Articles 17 and 28](https://eur-lex.europa.eu/eli/reg/2016/679) · [Commission Decision 2021/915, clause 10(d)](https://eur-lex.europa.eu/eli/dec_impl/2021/915/oj/eng/pdf)
