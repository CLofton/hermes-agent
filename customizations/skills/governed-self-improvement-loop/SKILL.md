---
name: governed-self-improvement-loop
description: Govern repeated lessons through proposal-only reports.
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [governance, self-improvement, audit, recurrence]
    related_skills: [memory-engineering-pipeline]
---

# Governed Self-Improvement Loop

Convert deidentified task receipts into deterministic weekly evidence, recurrence tests, and human-review skill proposals. The loop never edits skills, memory, configuration, or approval boundaries.

## When to Use

- Audit repeated task corrections and verified outcomes.
- Measure whether a correction recurred after it was learned.
- Identify contradictory lessons, stale memory claims, and process failures.
- Produce a weekly PASS / NEEDS ATTENTION / NOT YET PROVEN report.

Do not use this loop to capture raw tasks, inspect message transcripts, or approve/apply a proposed change.

## Prerequisites

- Python 3.9 or newer.
- Canonical JSON/JSONL receipts matching `references/receipt-schema.md`.
- Deidentified lesson statements. The engine redacts common identifiers and secrets, but receipt producers remain responsible for excluding regulated or private raw data.

## How to Run

Use `terminal(command="python3 ~/.hermes/scripts/governed_self_improvement.py run", timeout=120)`.

For an explicit source:

`terminal(command="python3 ~/.hermes/scripts/governed_self_improvement.py run --input ~/.hermes/task-receipts", timeout=120)`

The default report root is `~/Documents/Obsidian Vault/Self Improvement/`.

## Scoring and Status

Candidate score is deterministic and totals 100:

- Evidence: up to 30 points, 10 per distinct receipt.
- Verification: up to 25 points by verified-receipt rate.
- Recurrence: up to 25 points by tested pass rate.
- Consistency: 10 points when no contradictory statement shares the key.
- Recency: up to 10 points for evidence observed within 90 days.

A proposal requires score 75+, three distinct verified receipts, two recurrence tests, zero recurrence failures, and zero contradiction. The output is still proposal-only.

Overall status:

- **PASS:** at least three valid receipts, at least two recurrence tests, and zero open Critical, High, or Medium defects.
- **NEEDS ATTENTION:** any Critical, High, or Medium defect, malformed input, failed recurrence test, contradiction, stale/contradicted memory check, or material process failure.
- **NOT YET PROVEN:** no blocking defect, but evidence or recurrence coverage is below threshold.

## Procedure

1. Point the engine only at canonical task-receipt files. Completion: discovery lists JSON/JSONL inputs without reading sessions, email, Slack, or raw transcripts.
2. Run deterministic analysis. Completion: stdout returns a run ID, status, and exact counts.
3. Read `latest.md` and proposal files under the immutable run directory. Completion: every proposal says human review required and applied: no.
4. Resolve blocking defects in their source systems; do not edit the report to manufacture PASS. Completion: the next run independently observes zero Critical/High/Medium defects.
5. If report publication must be undone, use the rollback command from `audit-receipt.json`. Completion: the run is archived under `rolled-back/`, prior `latest.*` is restored, and a rollback receipt exists.

## Audit and Rollback

Each run records SHA-256 input and artifact manifests without source paths. It snapshots the previous mutable `latest.md` and `latest.json` into the run before replacement. Rollback verifies artifact integrity, restores the snapshot, archives the run, and writes a separate receipt; source receipts, skills, and memory remain unchanged.

## Pitfalls

- Reusing a lesson key for different claims creates a contradiction and blocks PASS.
- `NOT_TESTED` is not a recurrence pass.
- A script exit code of 0 can still mean NOT YET PROVEN; parse stdout status.
- Input file hashes reveal equality across runs but not file paths or contents.
- Never schedule an LLM agent to reinterpret scores. Schedule this deterministic script in no-agent mode.
- The existing weekly memory audit is broader and recently timed out waiting on inference; this loop is a bounded pre-audit, not a replacement.

## Verification

Run `terminal(command="python3 ~/.hermes/scripts/tests/test_governed_self_improvement.py -v", timeout=120)` and require all tests to pass. Then run an E2E smoke in a temporary directory and verify report creation, proposal-only behavior, artifact hashes, and rollback restoration. PASS is prohibited while any Critical, High, or Medium defect remains.

## Recommended Schedule

Run weekly Sunday at 3:00 AM local time in no-agent mode, before the 3:30 AM memory-engineering audit. Keep cron creation with the parent operator; this skill does not create or change schedules.
