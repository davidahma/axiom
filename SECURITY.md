# Security

## Report a vulnerability

For a vulnerability in Axiom, submit a [private vulnerability report](https://github.com/davidahma/axiom/security/advisories/new). Include the Axiom commit, the affected component, the expected behavior and the security impact. Use a synthetic workspace to describe the issue. If the affected code belongs to a target application, use that project’s private disclosure channel.

Keep tenant data, raw reports from live systems, credentials and access tokens out of public issues, pull requests and CI logs. If a credential has been exposed, revoke or rotate it with its issuer immediately.

## Credentials in a contribution

GitHub push protection can stop supported secret patterns during a push. The separate **Secret scan** CI check runs Gitleaks on the fetched Git history, including the checked-out change. Before uploading a report, CI validates its evidence format and scans the file. A clean scan covers the enabled detectors and files they inspected.

If a push is blocked, remove the secret from the affected local commits before retrying. [GitHub push protection](https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection)
