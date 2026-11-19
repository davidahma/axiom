# Contributing

Run `make check` from a clean checkout to test the portable gate, reproduce the reference cases and build `artifacts/axiom.pyz`. The tests run the downloadable CLI in a separate directory and check all three SQLite outcomes. The [README](README.md) explains each observed outcome.

For a change to the application trial, start Docker and run `python3 trials/opendesk/run.py --report artifacts/opendesk.json`. Check the resulting evidence with `python3 trials/opendesk/verify_report.py artifacts/opendesk.json`. CI runs these same commands against an isolated deployment. All workspaces are synthetic. Forks can run both lanes without repository secrets or a model key.

## Changing an observation or verdict

Open a pull request that names the case and the expected observation at a specific checkpoint. Include a regression case for a corrected verdict. Preserve the controls that establish initial visibility, the retained workspace and the worker outcome. An intentionally faulty fixture should still produce a failure in its own report. Missing evidence should remain visible.

For a change to the portable contract, update the [integration guide](docs/gate.md) and test the process exit code, reasons, and serialized decision. Keep the policy independent of the observations.

For target-specific changes, identify the upstream revision, the interface exercised and any local instrumentation. Use synthetic workspaces throughout. Follow [the security reporting process](SECURITY.md) for sensitive findings.

## Running the secret check locally

Use [Gitleaks](https://github.com/gitleaks/gitleaks) to run `gitleaks git --redact --ignore-gitleaks-allow --log-opts="--all HEAD" .` against local history after committing, and `gitleaks git --staged --redact .` before committing. GitHub Actions also validates and scans each generated report before storing it as a short-lived artifact.

Dependabot tracks pinned GitHub Actions and the hash-locked Linux Ruff wheel. Use the [pinned Ruff version](.github/requirements.txt) for `ruff check axiom_demo examples scripts tests trials` when changing Python. To update the standalone Gitleaks binary, match the Linux x64 asset from the official release to its published SHA-256 checksum, update both values in [the installer](.github/scripts/install-gitleaks.sh), and exercise the Secret scan job.
