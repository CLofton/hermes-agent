# Closed-Loop Security Remediation

Use this reference when a recurring detector feeds a durable incident store and autonomous agents create security fixes.

## Incident identity

Separate **identity** from **evidence**.

- Dependabot aggregate identity: `source + kind + repository`.
- Secret-scanning aggregate identity: `source + kind + repository`.
- Workflow-health identity: `repository + workflow ID/name + branch` when tracking current health. Preserve run IDs as events, not root-cause incident identities.
- Endpoint identity: detector source + stable alert code + target identity where needed.

Counts, severity totals, timestamps, deployment IDs for superseded runs, and title text are evidence that updates the canonical incident. Hashing them into the fingerprint creates duplicate incidents whenever the count changes.

## Safe reconciliation

Resolve absence only when the source read was authoritative and successful.

- Successful API response with zero matching alerts: resolve matching open/acknowledged incident(s).
- Successful endpoint scan omitting a prior code: resolve that code's incident.
- API timeout, 401/403, malformed JSON, missing file, or unavailable monitor: preserve prior state and open a separate collector-health incident if warranted.
- A new observation may reopen a resolved canonical incident while preserving its history.

For legacy duplicates, dry-run first. Select a canonical record deterministically, preserve every event row, carry forward the highest severity and latest evidence, and mark superseded records resolved with a deduplication note. Never delete audit history.

## Remediation graph

1. Freeze the live alert inventory and default-branch SHA.
2. Check for active writers, existing Dependabot PRs, and overlapping worktrees.
3. Create one isolated branch per root-cause family.
4. Upgrade to safe compatible versions; avoid forced major upgrades and `audit fix --force`.
5. Run clean install, dependency audit, tests, typecheck, lint, build, secret scan, and package-floor verification.
6. Add or verify SHA-pinned CI with read-only token permissions. Declare the runtime floor when upgraded tooling requires it.
7. Obtain an independent review of the final diff. Re-review after any new commit.
8. Open a protected PR. Respect branch protection and last-push approval.
9. Merge/deploy only within the approved automation boundary.
10. Verify deployed commit, application health, and detector clearance. Only then resolve the incident.

## Evidence contract

Store or report:

- Incident IDs and grouped advisory IDs.
- Repository, default-branch SHA, remediation branch/commit, and PR URL.
- Before/after severity counts.
- Exact commands, exits, test counts, audit results, and CI URLs.
- Independent reviewer verdict and any residual risk.
- Merge/deploy SHA, production health check, detector readback, and closure note.

Candidate-branch `npm audit = 0` proves the candidate graph only. Default-branch alerts remain live until merge, and production remains unproven until deployment/readback.