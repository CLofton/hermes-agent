# Bounded scheduled remediation

## Diagnose before changing limits

1. Read the job's live configuration and actual executable. For Hermes, use `hermes cron runs <job-id>` and inspect the referenced wrapper; do not infer execution from the job's descriptive model field.
2. Classify each failed run from its own saved output and timestamps: collector/auth failure, model turn exhaustion, wrapper timeout, scheduler kill, or remediation/test failure. The latest alert's error does not establish the cause of earlier failures.
3. Compare scheduler, wrapper, subprocess and model limits. A larger inner budget cannot override an outer kill; reserve time for a clean checkpoint and final receipt before the outer deadline.
4. Inventory the work required within one run, including discovery, reviews, tests, pushes and readbacks. Treat too much work per tick as a scope problem first, not automatic justification for more turns.

## Inspect retry and checkpoint semantics

- Trace exactly when success fingerprints, per-resource checkpoints and retry timestamps are written. Missing a final receipt does not mean no external work occurred; reconcile exact resources before retrying writes.
- Compare retry-age thresholds with the schedule cadence in code. If every normal tick already exceeds the threshold, repeated model invocation may be scheduled behavior rather than a failure-only loop.
- Select unfinished or materially changed resources from authoritative checkpoints. Do not copy a failed run's fingerprint into the success state merely to silence alerts.
- Preserve worker changes as evidence and check compilation/tests before adoption; scheduler termination can leave an incomplete patch beside valid earlier commits.

## Recommend the smallest safe change

Prefer a smaller actionable batch, durable per-unit checkpoints, and a wrapper deadline below the scheduler kill. Preserve cadence, single-writer locking, exact-revision review, CI, human merge/release approval and send restrictions. Distinguish `partial`, `blocked`, and `failed` from `complete`; a partial-work receipt must not become a clean security bill of health.

Ask before pausing security coverage, widening global budgets, or changing authorization boundaries. Verify the exact changed job after an approved write, then exercise its real execution path before calling the repair complete.

## Reconcile stale alerts

Age or lack of re-observation is a revalidation signal, not resolution evidence. Re-read the authoritative live condition before closure. Report unobservable resources as coverage gaps, not as clean results, and do not bulk-close stale incidents solely because their last-seen timestamp is old.
