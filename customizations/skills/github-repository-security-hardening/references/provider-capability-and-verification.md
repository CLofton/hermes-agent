# Provider capability and verification notes

## Useful REST endpoints

For `OWNER/REPO` and its default branch:

- Repository/security state: `GET /repos/OWNER/REPO`
- Dependabot alerts enable/read: `PUT|GET /repos/OWNER/REPO/vulnerability-alerts`
- Automated fixes enable/read: `PUT|GET /repos/OWNER/REPO/automated-security-fixes`
- Secret scanning and push protection: `PATCH /repos/OWNER/REPO` with explicit `security_and_analysis` statuses, then `GET` the repository
- Actions policy/SHA pinning: `PUT|GET /repos/OWNER/REPO/actions/permissions`
- Default workflow token: `PUT|GET /repos/OWNER/REPO/actions/permissions/workflow`
- Branch protection: `PUT|GET /repos/OWNER/REPO/branches/BRANCH/protection`
- Rulesets: `POST|GET /repos/OWNER/REPO/rulesets`
- Repository admins: `GET /repos/OWNER/REPO/collaborators?affiliation=all` and filter `permissions.admin`
- Organization admins: `GET /orgs/ORG/members?role=admin`

## Interpretation

- `204` from vulnerability-alert readback means enabled.
- `automated-security-fixes` should read back `enabled: true` and `paused: false`.
- `security_and_analysis` can be absent even for an admin when the feature is unsupported. Preserve the provider's exact 4xx message.
- A private personal repository can return 403 with “Upgrade to GitHub Pro or make this repository public” for both branch protection and rulesets. Never recommend public visibility for internal code merely to unlock security controls.
- A 404 on protection means no protection only when the caller has sufficient visibility; otherwise classify as permission-not-proven.
- Bind required checks to observed GitHub App IDs when available. Send either `contexts` or app-bound `checks` in `required_status_checks`, not both; an API schema can reject both with HTTP 422. Read back the exact context/App pairs.
- GitHub check-suite objects do not have a workflow `name`. For exact-workflow CI verification, use Actions run records bound to the expected workflow path/ID and head SHA; distinguish approval-needed, pending, failure, and success. Test with actual API-shaped fixtures.
- A pending Copilot request can disappear because the review completed. Accept a completed substantive review only when its commit ID matches the exact head; absence from requested reviewers alone is not failure or success. Keep requested, completed and approving verdicts distinct: a substantive changes-requested review proves execution, not merge readiness.
- `sha_pinning_required: true` is effective only if every workflow references external Actions by full SHA. Audit before enabling on workflow-heavy repositories.
- Discover portfolio scope with `gh api --paginate --slurp 'orgs/ORG/repos?per_page=100&type=all'`; flatten the page arrays, deduplicate repository identity and count in code. A CLI's default-sized list is not the organization total. Keep archived repositories separate.
- Read `GET /user/memberships/orgs/ORG` separately from repository `permissions.admin`. A member can administer selected repositories yet receive 403 on organization Actions policies; adding a token scope alone does not grant the missing organization role.
- A current branch tip's check runs are evidence of exact context names, not sufficient proof that every context belongs in a PR gate. Cross-check workflow events, job conditions, matrix names and path filters. Exclude deploy-only and comment-triggered jobs from mandatory PR checks.
- `enforce_admins: true` does not establish that all review exceptions vanished. Inspect `required_pull_request_reviews.bypass_pull_request_allowances` and ruleset bypass actors independently, then report the effective exceptions.
- Default workflow-token permissions do not override explicit workflow/job `permissions`. Inspect those declarations before changing the default; an explicit elevated workflow remains a separate review item.
- Separate native scanning activation from credential remediation. Turning scanning on does not revoke a published key, prove that a custom key format is detected, or establish that a previously exposed endpoint is safe.

## Mutation ordering

1. Add Dependabot/config workflows.
2. Verify the commits/PR checks.
3. Restrict Actions defaults and require SHA pinning.
4. Enable branch protection last.

This avoids locking the agent out of direct configuration writes midway through hardening.

## Automated patch-publisher trust boundaries

- Treat `pull_request_review` as PR-merge-ref context, not automatically trusted default-branch workflow code. Fetching helpers at `github.workflow_sha` does not repair an untrusted workflow origin. Keep credential-bearing processing on a documented trusted trigger and immutable trusted source revision.
- Validate every effective patch path, not just `diff --git` headers. A patch with a harmless `diff --git` path but protected `---`/`+++` paths can be accepted and applied to the protected file by Git. Exercise actual `git apply` in a disposable repository; reject inconsistent rename/copy/hunk metadata, symlinks and forbidden paths.
- Bind artifact metadata to independently resolved repository, PR, original head, base and branch—not values copied from the artifact itself. Recompute bytes/hashes and use an atomic expected-head publication API where a concurrent branch rewind must be rejected; non-force push alone is not an exact-head compare-and-swap.
- `--allowedTools` is an auto-approval list, not necessarily the complete tool surface. Restrict the actual tools and prevent PR-controlled hooks, settings, plugins or MCP startup in credential-bearing model processes. Read/Edit/Write tools still need a filesystem boundary: removing Bash does not prevent a model from modifying files that later Git, Python or shell steps consume.
- Validate the actual artifact directory immediately before upload, not merely the patch or an unused helper. Use a fresh output location outside the untrusted worker's writable scope, require the exact expected regular-file set, and reject extra files and links. `mkdir -p` followed by writing two expected files leaves any worker-prepopulated files in place; exercise that case with a harmless canary before trusting artifact isolation.
- Never approve a parked historical privileged auto-editor merely because a replacement workflow has been hardened. The old run remains bound to its old definition; use a fresh validated run. Temporarily disabling an unsafe auto-editor is separate from disabling independent code review or CI.
- Treat reviewer conclusions as hypotheses: a reviewer can wrongly clear a parser bypass or trust origin. Prefer executed counterexamples and official event/API documentation over consensus.

## Access-request pattern

When the authenticated user has push but not admin:

1. Identify repository/org admins through API.
2. Open a narrowly scoped issue that names the requested permission and controls it unlocks.
3. Request those admins as reviewers on the security-config PR.
4. If Slack/email is preferred, draft the exact message and obtain explicit sending approval.
5. Re-read repository permissions before attempting admin-only writes.
