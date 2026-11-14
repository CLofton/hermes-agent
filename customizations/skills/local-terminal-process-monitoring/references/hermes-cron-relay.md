# Hermes cron relay for unattended work

Use when several `delegate_task` agents must keep projects moving longer than one agent's wall-clock window.

## Pattern

1. Give each writer an isolated branch/worktree and a narrow scope.
2. Require small verified commits before timeout.
3. Schedule a finite recurring cron job, usually every 30 minutes, with local delivery and continuity enabled.
4. Make its prompt self-contained: absolute paths, acceptance gates, prohibited actions, and `SALVAGE; do not reset`.
5. Add a one-shot morning report job that consumes prior relay output but independently inspects Git, tests, artifacts, deployment, and activation state.

## First step on every tick

- Inventory live subagents/background processes.
- Inspect branch, worktree, recent commits, status, and diff for each project.
- Separate committed work from dirty worktree changes.
- Never start a second writer in an active or ambiguous worktree.
- Pick one non-overlapping executable slice.

## Timeout salvage

A timed-out agent may have completed most of the task. Read its transcript tail, inspect Git state, run the claimed targeted tests, and independently review production wiring. Commit verified salvage or redispatch a narrowly scoped finisher against the same worktree. Never reset or start over merely because the final summary is missing.

## Completion standard

Define “100%” before starting. Process absence, targeted tests, and a large commit count are insufficient. Require the project's real integrated branch, zero required blockers, full gates, production-path tests, deployment/migration checks where applicable, independent review, and any mandatory UAT/approval.

## Permission boundaries

User instructions such as “all permissions” or “don't wake me” authorize autonomous internal progress but do not silently authorize:

- sending email or Slack;
- contacting candidates or making personnel decisions;
- approving spend;
- moving money or bypassing payout gates;
- fabricating historical eligibility/evidence;
- publishing learner content before source, privacy, accessibility, and approval gates.

Advance blocked work through drafts, source discovery, tests, migrations, and review packages. Record irreducible human decisions and move to another executable task.

## Owner stop: pause dispatch and terminate the exact active run

1. Discover the job with the cron management tool, then inspect `hermes cron runs <job_id> --limit 2`. Record the owning profile, exact running execution ID and prior job state. Pause with the supported cron pause control and read back `enabled=false` / `state=paused`.
2. Prefer a supported per-execution cancellation control when the installed runner exposes one. Never restart or kill the entire gateway merely to cancel one job, because that interrupts unrelated conversations and work.
3. For an in-process runner without an exposed stop command, the existing job-store lease mechanism is a version-dependent fallback, not a universal API guarantee. Before using it, inspect the installed and live runner's behavior: `cron.jobs.heartbeat_fire_claim` must reject a missing/replaced owner, and the scheduler must translate repeated ownership loss into an interrupt for that execution and discard its stale result. A separate Python process cannot cancel an in-memory agent merely by importing its registry.
4. Only after that behavior is verified, re-read the exact job and require it to remain paused with the same running execution and owner. Use the profile-bound job-store API—not raw JSON editing—to revoke its `fire_claim` with `cron.jobs.update_job(job_id, {"fire_claim": None, "paused_reason": reason})`. Abort if ownership or profile changed; do not overwrite a newer run or bypass immutable-field protections. Leave schedules, models, delivery targets and unrelated records unchanged.
5. Read back the job, then perform a bounded foreground wait using `cron.executions.get_execution(execution_id)` or the CLI execution ledger. A revoked claim alone is not proof the worker stopped. Require a terminal record with a finish timestamp and the cancellation/ownership-loss reason; if it remains running, report the unresolved active layer instead of claiming success. Do not forge completion or edit the execution ledger.
6. Save a private stop receipt linking job, execution, pause readback and terminal outcome. Require explicit owner approval to resume; resume the schedule through its normal control, never replay an old claim or automatically retry the canceled task.

## Morning report

Use `PASS / FAIL / NOT YET PROVEN`. Report commits, tests, artifacts, deployment/activation state, genuinely completed items versus work merely advanced, remaining human decisions, and the next executable action. Verify directly; do not repeat agent self-reports as fact.
