---
name: security-finding-remediation
description: Use when fixing findings from a security monitor or scanner.
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [security, remediation, credentials, gitleaks, mcp, macos]
metadata:
  hermes:
    tags: [security, remediation, credentials, gitleaks, mcp, macos]
    related_skills: [macos-security-audit, github-repository-security-hardening, account-credential-lookup]
---

# Security Finding Remediation

Turning alert rows into verified changes without breaking the machine. Use this
for the remediation half; `macos-security-audit` covers the audit half.

## When to Use

- A security monitor, cron job, or scanner delivered findings to fix
- A credential is believed exposed in a repo, logs, or a config file
- A detector keeps re-firing on a condition that looks wrong
- Dependency-audit counts need to be turned into an actual plan

Not for the initial audit (`macos-security-audit`) or for account compromise
triage (`account-login-alert-triage`).

## Contract

- **A finding is a claim, not a fact.** Re-measure the live state before fixing.
  Monitors go stale, scan roots go unreadable, and counts are often lower bounds.
- **Never rotate a credential before proving it is live**, and never declare one
  dead from its format. Exchange it with the provider's own API.
- **Separate the four states** in every report: fixed / contained / blocked /
  awaiting decision. Never compress them into "done".
- Approval covers the named scope of the finding it replied to. Rotation, history
  rewrites, force-pushes, and process termination stay separate asks unless the
  user explicitly included them.

## Order of work

1. **Reproduce** the finding from live evidence, not the report file.
2. **Classify** it: real exposure / detector defect / dependency debt / noise.
3. **Contain** with a reversible action before attempting the real fix.
4. **Fix** only the class you can prove. Ship a guard so it cannot recur.
5. **Verify** by re-running the detector and reading the artifact back.

## Hard-won rules

### Config edits
Never regex-edit `~/.hermes/config.yaml`. A `(?s)` pattern turns `.*` into the
rest of the file and silently rewrites every sibling key. Use
`hermes config set <dotted.key> <value>`. Verify a backup exists *before* the
edit — a `cp` in the same compound command may not have landed.

### Credential liveness
Test with the provider's cheapest read endpoint and compare against a junk-key
control. `401`/`400 "API key is invalid"` = dead. Anything ambiguous is
**unverified**, not dead. Formats prove nothing.

### Secrets in git
Filename heuristics (`.env*`, `*.pem`, `credentials*.json`) miss `.sa-key.json`
and populated `.env.example` files. Use **gitleaks content rules** for the real
inventory, then triage by rule and repo. Most hits are fixtures and docs;
report the ratio so the finding is not inflated.

### Killing processes
When the target processes are children of the agent gateway, **your own shell is
in that set**. Enumerate by command identity, exclude your pid and your
ancestors, `SIGTERM`, wait, verify, then `SIGKILL` strays. Never kill by ppid
alone.

### Detector defects
A rule matching a renamed artifact fires forever and hides real ones — an
`mcp_death_supervisor` check reported "0 supervisors" on every healthy group
after the supervisor became `process_supervisor.sh`, 16k times. Fix the rule,
run the suite, and check it against live data before closing the incident.

### Dependency findings
Aggregate counts across vendored clones are not actionable. Quantify per
project, drop upstream forks you do not deploy, and treat the rest as upgrade
work with a test cycle — never a bulk `npm audit fix` on repos under review.

### Scanner verdicts
A scanner's "clean" is a claim. Keep a canary fixture with known-obvious flaws
and require any new tool to flag it before you point it at real code.

## Verification

Re-run the detector, confirm the alert code is gone, and read the state back
from the system (git, filesystem, provider API) — not from your own summary.

`scripts/triage.py` does the read-only measurement: MCP children by identity,
credential classification from an env file, and a gitleaks sweep with a vendored
-code allowlist. `scripts/test_triage.py` covers it offline.
