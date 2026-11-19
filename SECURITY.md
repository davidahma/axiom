# Security

## Report a vulnerability

For a vulnerability in Axiom, submit a [private vulnerability report](https://github.com/davidahma/axiom/security/advisories/new). Include the Axiom commit, the affected component, the expected behavior and the security impact. Use a synthetic workspace to describe the issue. If the affected code belongs to a target application, use that project’s private disclosure channel.

Keep tenant data, raw reports from live systems, credentials and access tokens out of public issues, pull requests and CI logs. If a credential has been exposed, revoke or rotate it with its issuer immediately.

## Receipt trust and privacy

Keep the original request digest in an access-controlled case system before dispatch. Restrict changes to the policy, producer, application job records and signing keys. Replay depends on these sources. Use opaque identifiers and choose the audience and retention period for originals, descriptors and receipts separately. For signatures, obtain the allowed signing keys through a trusted channel. [Evidence boundaries](docs/receipts.md)

## Credentials in a contribution

GitHub push protection can stop supported secret patterns during a push. The separate **Secret scan** CI check runs Gitleaks on the fetched Git history, including the checked-out change. Before uploading a report, CI validates its evidence format and scans the file. A clean scan covers the enabled detectors and files they inspected.

If a push is blocked, remove the secret from the affected local commits before retrying. [GitHub push protection](https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection)
