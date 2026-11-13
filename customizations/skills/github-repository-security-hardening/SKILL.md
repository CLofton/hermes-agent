---
name: github-repository-security-hardening
created_by: curator
managed_by: curator
description: Use when hardening or evaluating GitHub repository security controls.
version: 1.2.0
tags: [github, security, branch-protection, dependabot, secret-scanning, actions]
---

# GitHub Repository Security Hardening

Use this class-level workflow when a user asks to secure private repositories, enable branch protection or rulesets, turn on Dependabot/secret scanning, restrict Actions permissions, or require pinned Actions.

## Contract

- Discover repository owner, visibility, default branch, authenticated-user permissions, organization ownership, workflows, and security feature state before mutation.
- Treat repository transfer, visibility changes, paid-plan upgrades, history rewrites, force-pushes, and secret rotation as separate high-impact decisions.
- Add configuration files and baseline workflows before enforcing protections that could block direct writes.
- Never claim a setting changed from a successful write alone; read back the exact endpoint and verify the effective state.
- For repositories without admin access, do not attempt self-elevation. Identify admins and create an auditable access request or draft a message for explicit approval.
- Separate repository administration, organization policy authority and paid-feature entitlement; success in one does not establish the others.
- When the operator asks to turn protections on, distinguish discovered, planned, applied and read-back-verified changes. A saved change contract or successful inventory is not an enabled guardrail; after an interruption, report unapplied settings as pending.
- Preserve the user's original acceptance criteria through corrective passes. Removing automatic publication can be valid containment, but a proposal-only draft does not complete a requested automatic repair pipeline. Report containment, draft-sharing approval, functional completion and production acceptance separately; keep unresolved criteria open even when the reduced candidate's tests pass.
- For an authorized third-party trial, keep installation, credentials, hooks and logs in a disposable environment until acceptance. Shadow mode is not a privacy guarantee: inspect outbound payloads before using any real conversation or company data.

## Safe sequence

1. Confirm GitHub authentication with a real API request, not only cached auth status.
2. Paginate the full repository inventory and reconcile the count before accepting a report's claimed portfolio size. For each repository, capture visibility, owner, archive status, default branch, current permissions, workflows, Dependabot config, Actions defaults, SHA pinning, branch protection/rulesets and `security_and_analysis`. Separate the requested scope from the subset this identity can administer; do not silently broaden a sampled report into an organization-wide mutation.
3. Add `.github/dependabot.yml` before branch protection. For mixed ecosystems, configure each package ecosystem explicitly.
4. Add any fallback security workflow before enforcing SHA pinning, and pin every third-party Action to a verified full 40-character commit SHA.
5. Enable Dependabot alerts, then automated security fixes/security updates.
6. Check feature entitlement and billing implications before enabling native secret scanning, push protection or Code Security. A private repository's disabled flag does not prove an existing paid license. Obtain approval for a new charge or trial; do not change visibility to unlock a free feature. Continue separately authorized, no-upgrade controls rather than calling the whole task blocked.
7. Set default `GITHUB_TOKEN` permission to `read` and prevent workflows from approving pull requests unless a documented workflow requires it.
8. Require SHA-pinned Actions.
9. Protect the default branch with pull-request review, at least one approval, stale-review dismissal, last-push approval, conversation resolution, blocked force pushes/deletion and administrator enforcement as authorized. Inspect existing bypass allowances and restrictions; preserve them or explicitly approve their removal, and disclose retained exceptions. Check merge-strategy and contributor/bot readiness before requiring linear history or signed commits. Require only exact check contexts observed green and configured to run on applicable PRs; never require a deployment, comment-triggered review, or path-filtered job that an ordinary PR cannot produce.
10. Read back every setting, inspect resulting workflow runs/PR checks, and report PASS / FAIL / BLOCKED BY PLAN / BLOCKED BY PERMISSION.

## Closed-loop vulnerability remediation

When Dependabot or another GitHub detector raises incidents continuously, treat detection, remediation, and closure as a controlled state machine—not as a stream of unrelated alerts.

1. **Stable identity:** fingerprint an incident from immutable identity fields such as repository + alert family (or repository + workflow + branch). Never include changing counts, timestamps, titles, or severity totals in the identity; those are mutable evidence on the same incident.
2. **Root-cause grouping:** group several advisory records that share one dependency graph into one remediation workstream. Keep the full advisory inventory as evidence, but do not spawn competing writers or PRs per CVE when one upgrade resolves the family.
3. **States:** use `open` → `acknowledged/in progress` → `resolved`. A local patch, commit, or PR is not resolution.
4. **Reconciliation:** clear or resolve a finding only after a successful authoritative read proves it is absent. API error, timeout, malformed response, missing scope, or unavailable endpoint must preserve the prior state.
5. **Audit preservation:** never delete historical incident/event records during deduplication. Retain one canonical incident, merge or retain occurrence history, and mark superseded records resolved with an audit note.
6. **Guarded delivery graph:** baseline → isolated patch → local tests/audit → independent review → SHA-pinned read-only CI → required human review → merge/deploy → production health/readback → detector clears.
7. **Automation boundary:** auto-merge only dependency-only patch/minor changes with no application/schema/auth/infrastructure change, zero high/critical findings, green local and CI gates, independent PASS, proven rollback, and production readback. Otherwise stop at a verified PR and name the required decision.
8. **Reproducibility:** when dependency updates raise runtime floors, declare the supported runtime (`engines`, tool-version file, or equivalent) and run CI on that declared version.
9. **No false closure:** distinguish candidate-branch audit results from default-branch and deployed-production results. Report all three separately until the default branch and detector confirm clearance.

See `references/closed-loop-security-remediation.md` for the detailed identity, reconciliation, PR, and evidence patterns.

## Capability fallbacks

- A private repository owned by a personal account may reject both branch protection and rulesets without GitHub Pro. Do not make it public to unlock controls. Present paid-plan upgrade versus private transfer to the company organization as an explicit decision; recommend the company organization for company-owned code after checking integrations and collaborator access.
- Native secret scanning can also be unavailable by plan. A pinned Gitleaks workflow is a useful changed-commit fallback, but it is not equivalent to native pre-receive push protection.
- If repository-admin access is missing, identify current admins, open an auditable access-request issue when the user asked to obtain access, and request review from admins on security-config PRs. Do not claim access until the repository permissions endpoint reports `admin: true`.

## Gitleaks workflow interpretation

`fetch-depth: 0` makes history available, but `gitleaks/gitleaks-action` chooses event-specific log ranges. On a normal push it can run with `--log-opts=-1`, scanning only the changed commit. Inspect logs before calling it a full-history scan. Use a separate redacted local `gitleaks git` audit for historical exposure; use CI for changed-commit prevention unless the repository has a reviewed baseline.

## Evaluating a third-party repository before adoption

Use this path when a repository is promoted in a social post, README, newsletter, or vendor claim and the user asks whether it is popular, safe, or worth installing.

1. Resolve the canonical repository from the primary post or project site. Reject lookalikes and typo-squatted packages.
2. Read live repository metadata rather than repeating the post's numbers: stars, forks, watchers, open issues, creation date, latest push, license, releases, contributors, and maintainer concentration.
3. Treat stars as traction, not trust. Corroborate them with forks, contributors, issue/PR activity, release history, and realistic growth. Explicitly correct claims such as “one developer” when contribution history contradicts them.
4. Clone source without executing it. Inspect manifests, lockfiles, build scripts, install commands, CI workflows, release jobs, network destinations, telemetry, credential handling, persistence, shell/process execution, local-file access, and destructive capabilities.
5. Test the security boundary, not only the code style: default bind address, authentication, CORS/origin policy, SSRF/private-network access, sandboxing, privilege level, secret/session export, and whether dangerous capabilities require explicit opt-in.
6. Check supply-chain integrity: SHA-pinned Actions, read-only workflow permissions, dependency audit coverage, signed tags/commits, checksums, artifact attestations/provenance, reproducible builds, and whether the latest release CI is green. Do not recommend a release still building or lacking artifacts as production-ready.
7. Run a redacted secret scan when practical. Classify findings before reporting; test fixtures such as WebSocket handshake keys are common false positives.
8. Separate “no obvious malware found” from “safe.” Untrusted-code execution, missing OS sandboxing, unauthenticated control ports, unsigned binaries, and credential-bearing browser state remain material risks even in legitimate projects.
9. Compare against the user's existing stack. A legitimate project may still be unnecessary, incomplete, or too risky for logged-in sessions, PII, or production credentials.
10. Conclude with one of: **Adopt**, **Pilot with controls**, or **Reject**. For a pilot, prescribe isolation, a pinned commit, restricted network/filesystem access, no production credentials, safe protocol binding, and explicit success criteria.

Never install or execute the project merely to answer a safety question. Source inspection and authoritative metadata come first; run code only when justified and isolated.

See `references/third-party-project-evaluation.md` for the evidence checklist, isolated agent-plugin trial sequence, credential-isolating live probes and decision rubric.

## Verification output

For each repository report:
- ownership/visibility/default branch;
- admin capability;
- Dependabot config, alerts, and automated-fix state;
- secret scanning and push protection;
- Actions allowed policy, SHA pinning, token default, PR-approval permission;
- branch protection/ruleset details;
- configuration PR/check URLs;
- blockers and the exact decision/owner needed.

See `references/provider-capability-and-verification.md` for API endpoints, readback fields, and plan/permission interpretation.
See `references/third-party-project-evaluation.md` for social-post verification, popularity analysis, source inspection, supply-chain review, and controlled-pilot guidance.
See `references/closed-loop-security-remediation.md` for durable incident deduplication, reconciliation, and verified closure.
