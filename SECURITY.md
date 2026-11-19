# Security

For the maintained tenant offboarding toolkit, use [Setrya’s security policy](https://github.com/davidahma/setrya/blob/main/SECURITY.md). The guidance below applies to historical Axiom releases.

## Report a vulnerability

For a vulnerability in Axiom, submit a [private vulnerability report](https://github.com/davidahma/axiom/security/advisories/new). Include the Axiom commit, the affected component, the expected behavior and the security impact. Use a synthetic workspace to describe the issue. If the affected code belongs to a target application, use that project’s private disclosure channel.

Keep tenant data, raw reports from live systems, credentials and access tokens out of public issues, pull requests and CI logs. If a credential has been exposed, revoke or rotate it with its issuer immediately.

## Docker trial dependencies

The portable CLI uses the Python standard library. The optional OpenDesk trial pulls three container images and runs synthetic data on an internal Docker network. Its image review lists the remaining advisories, the affected architectures and the evidence for the Brotli finding. [Trial image review](trials/opendesk/README.md#trial-image-review)

## Receipt trust and privacy

Keep the original request digest in an access-controlled case system before dispatch. Restrict changes to the policy, producer, application job records and signing keys. Replay depends on these sources. Use opaque identifiers and choose the audience and retention period for originals, descriptors and receipts separately. For signatures, obtain the allowed signing keys through a trusted channel. [Evidence boundaries](docs/receipts.md)

## Credentials in a contribution

GitHub push protection can stop supported secret patterns during a push. The separate **Secret scan** CI check runs Gitleaks on the fetched Git history, including the checked-out change. Before uploading a report, CI validates its evidence format and scans the file. A clean scan covers the enabled detectors and files they inspected.

If a push is blocked, remove the secret from the affected local commits before retrying. [GitHub push protection](https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection)

## Verify a release download

Starting with v0.3.1, the GitHub Actions workflow publishes signed build provenance for each release asset after the tests, upstream trial and secret scan succeed on `main`. The signing job downloads those files from that run. The attestation identifies the workflow and the exact Git commit. It covers the release software and examples. A customer receipt has its own review and optional signature.

Obtain the expected full Git commit from your approved release record or independently reviewed merged PR. With an authenticated GitHub CLI, run the following command **before executing the downloaded CLI**. Substitute the ZIP or another release filename to verify that asset. The release notes also name the producing run and commit. [GitHub attestation verification](https://cli.github.com/manual/gh_attestation_verify)

```sh
gh attestation verify axiom.pyz --repo davidahma/axiom \
  --signer-workflow davidahma/axiom/.github/workflows/checks.yml \
  --source-ref refs/heads/main --source-digest "$EXPECTED_COMMIT" \
  --deny-self-hosted-runners
```

Earlier releases carry ordinary checksums. For those versions, a separately trusted source revision and a matching local rebuild can corroborate the CLI bytes.
