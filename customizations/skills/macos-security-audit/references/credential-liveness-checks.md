# Credential liveness checks

Purpose: turn "a secret-shaped value sits in a tracked file" into a decision — rotation, containment, or nothing — using provider evidence rather than entropy judgment.

## Find candidates by content, not by filename

A detector that matches names (`.env*`, `*.pem`, `credentials*.json`, `service-account*.json`) cannot see a credential that lives in a normally-named file. Two live credentials in one fleet sat in `.sa-key.json` (a GCP service-account key) and a Twilio plugin's `.env.example` (a real HubSpot client secret) — both invisible to the filename matcher, both surfaced immediately by a content rule set. Run `gitleaks dir <root> -c <allowlist.toml> --report-format json` and adjudicate from the report.

Triage by **rule id**, not by file or by total:

- Worth reading: `private-key`, `github-pat`, `stripe-access-token`, `gcp-api-key`, `hubspot-api-key`, `linkedin-client-secret`, `vault-service-token`, `mattermost-access-token`.
- Expect noise: `generic-api-key` and `curl-auth-header` run into the thousands across docs, tests and generated fixtures. A four-figure total is normal and is not a finding.
- A `private-key` hit is only real when the block is full length (~1700 chars for RSA); a few dozen characters is a fixture or a placeholder. Test material under `tests/`, `spec/`, `fixtures/` and vendor plugin directories is the common non-finding — read the path before reading the key.

## Probe before recommending anything

One read-only GET against the provider's own API with the candidate value. `curl -sS -o /dev/null -w '%{http_code}' --max-time 20` is enough.

| Credential | Probe |
| --- | --- |
| Anthropic API key | `GET https://api.anthropic.com/v1/models`, headers `x-api-key: <key>` and `anthropic-version: 2023-06-01` |
| OpenAI key | `GET https://api.openai.com/v1/models`, `Authorization: Bearer <key>` |
| ElevenLabs | `GET https://api.elevenlabs.io/v1/user`, header `xi-api-key: <key>` |
| Resend | `GET https://api.resend.com/domains`, `Authorization: Bearer <key>` |
| Smartsheet | `GET https://api.smartsheet.com/2.0/users/me`, `Authorization: Bearer <key>` |
| Hootsuite | `GET https://platform.hootsuite.com/v1/me`, `Authorization: Bearer <key>` |
| Twilio | `GET https://api.twilio.com/2010-04-01/Accounts.json`, basic auth `<ACCOUNT_SID>:<AUTH_TOKEN>` |
| GitHub | `GET https://api.github.com/user`, `Authorization: Bearer <token>` |
| GCP service-account JSON | Load it and request a token: `service_account.Credentials.from_service_account_file(path, scopes=["https://www.googleapis.com/auth/cloud-platform"])`, then `.refresh(Request())` |

A service-account key is testable without any resource permission. A token being issued proves the key is live even when every API call it makes returns `403`; a narrow role lowers the blast radius, it does not change the rotation decision. A dead one answers `invalid_grant: account not found`, which also tells you the key belongs to a decommissioned or third-party project rather than yours.

Reading the answers:

- `200` is live. `401` is revoked. `403` may be valid-but-unscoped — investigate before calling it dead.
- Providers disagree on the status for an invalid key: Resend answers `400 "API key is invalid"` where others answer `401`, and several use `400` for genuinely malformed requests. Re-send the identical request with a junk key as a control; if the response body matches, the credential is invalid, not the call.
- Print name, length, prefix and status code only. Never the value.

## Decide from the evidence

- **All dead** → the file is stale history. Untrack it, ignore the pattern, no rotation, no incident. Never spend an account rotation on a revoked key.
- **Any live** → rotation is the only real fix and untracking is hygiene alongside it.
- Resolve repository visibility from the API before describing exposure (`gh repo view <org>/<repo> --json visibility,isPrivate`). A private repo limits reach to collaborators; it does not make a live credential safe.
- Age is a severity signal, not a mitigation: a credential sitting on a default branch for years has been readable by every collaborator who ever cloned it.

## Rotation is the irreversible step

- Never rotate an account-level credential (Twilio primary auth token, shared service key) without an inventory of consumers. It breaks every integration that reads it, including ones outside the repository where it was found, and the inventory is usually incomplete.
- When it does proceed, sequence so failure comes last: create the secondary/rotated credential, update consumers, verify them, then promote.
- If the consumer inventory is incomplete, stop at the repo-side change and report rotation as an open decision with its blast radius stated.
- Check the deployed surface before assuming the repo file is what productions reads: serverless and platform env stores are copied at deploy time, so untracking a file does not change a running function.

## Shipping the repo-side fix

- If the organization repository rejects a direct push, fork and open the pull request from the fork; a fork PR still cannot set assignees or reviewers without triage rights, so name the reviewers in the PR body and report that the request failed.
- Untracking stops future commits only. Say plainly that history still holds the value and that a purge is a separate, coordinated decision — never let an untrack PR imply the secret is gone.

## Ship the recurrence guard with the untrack

A tracked-secret finding is a process failure, so the fix is commit-time scanning, not a cleaner 2 AM report. `gitleaks git --staged` in a `pre-commit` hook blocks the commit that would introduce the value; the same binary in CI (`gitleaks/gitleaks-action`, or a pinned release in a plain step) covers everyone who never installs the hook.

- **Verify the hook by its behavior, never by its exit status.** Stage a synthetic credential and confirm the commit is *blocked*, then commit a clean file in the same repository. A hook that exits 0 on everything and a working hook look identical from the outside.
- Hooks are per-clone and die with the checkout; the CI job is what protects the next person. Install both, and count the installed set rather than assuming a loop that wrote N files made N working hooks.
- Exempt vendored and build output in `.gitleaks.toml` (`node_modules/`, `/dist/`, `/build/`, `*.min.js`) or the first run buries the signal. First-party source stays in scope.
- A full `gitleaks dir` scan over a fleet of checkouts takes many minutes; run it as a tracked background job and report findings by rule and repository, not as a raw file list.
