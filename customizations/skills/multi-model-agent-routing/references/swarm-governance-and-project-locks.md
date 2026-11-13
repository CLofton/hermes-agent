# Swarm governance and project locks

Use this when a user expects a set of agent profiles to act as one organized team rather than independent assistants.

## Authority model

- **User:** ultimate authority and override.
- **Main orchestrator:** swarm boss; receives or learns about requests made to any member, owns the task graph, assigns lanes, resolves conflicts, and returns one final answer.
- **Specialists:** execute bounded lanes and report artifacts/evidence to the orchestrator.
- **Integrator:** the only active writer to the final branch, production system, database, or external record.
- **Judge/reviewer:** read-only unless the orchestrator creates a separate fix lane.

## Project-lock preflight

Before creating a writer lane, check:

1. Durable Kanban/issue board for same project or outcome.
2. Active subagents, CLIs, background processes, and scheduled jobs.
3. Git branches, worktrees, remote branch movement, open PRs, and deployment activity.
4. Recent sessions for a matching spec, correction, or in-flight handoff.
5. External target state when the task writes to SaaS, production, or a shared document.

Record: project, repo/target, spec, accountable owner, active writer, worktree/branch, reviewers, judge, dependencies, deployment authority, and current gate.

If another writer exists, do not start a competing edit. Route research/review around the existing writer or pause and reconcile through the orchestrator.

## Organized whole-swarm participation

“All agents participate” means meaningful, non-overlapping contribution—not duplicated side effects. Example lanes:

- requirements/data analysis
- source research
- independent test design A/B
- implementation candidate A/B in isolated worktrees
- UX/design review
- adversarial/security review
- judge-model selection
- final integration and verification

Small tasks may combine lanes, but never combine author and final judge without an independent challenge pass.

## Handoff contract

Every specialist returns:

- status: PASS / FAIL / NOT YET PROVEN
- task and scope completed
- exact artifact paths/URLs/IDs
- evidence and commands/tests actually run
- blockers and assumptions
- side effects performed
- recommended next lane

Self-reported external writes require orchestrator readback before success is reported.

## Conflict recovery

When duplicate implementations already exist:

1. Freeze new writes.
2. Fetch current remote/production state.
3. Preserve each candidate in its branch/worktree; never overwrite one blindly.
4. Run the same acceptance suite against each candidate.
5. Use an independent judge to select or specify a synthesis.
6. Assign one integrator, retest, merge/deploy once, and verify readback.
7. Capture why the lock failed and add a regression/preflight check.

## Comprehension verification

Copying a skill to profiles is not enough. Verify:

1. Every intended profile discovers the skill.
2. Distributed files match the canonical artifact when exact replication is intended.
3. Every profile answers a short structured comprehension test covering spec, tests, build isolation, judge independence, approval authority, single-writer rule, and reporting cadence.
4. Parse outputs programmatically and inspect representative content; labels alone are insufficient.
