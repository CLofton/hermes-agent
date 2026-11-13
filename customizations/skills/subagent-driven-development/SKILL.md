---
name: subagent-driven-development
description: "Execute plans via delegate_task subagents (2-stage review)."
version: 1.1.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [delegation, subagent, implementation, workflow, parallel]
    related_skills: [writing-plans, requesting-code-review, test-driven-development]
---

# Subagent-Driven Development

## Overview

Execute implementation plans by dispatching fresh subagents per task with systematic two-stage review.

**Core principle:** Fresh subagent per task + two-stage review (spec then quality) = high quality, fast iteration.

## When to Use

Use this skill when:
- You have an implementation plan (from writing-plans skill or user requirements)
- Tasks are mostly independent
- Quality and spec compliance are important
- You want automated review between tasks

**vs. manual execution:**
- Fresh context per task (no confusion from accumulated state)
- Automated review process catches issues early
- Consistent quality checks across all tasks
- Subagents can ask questions before starting work

## The Process

### 1. Read and Parse Plan

Read the plan file. Extract ALL tasks with their full text and context upfront. Create a todo list:

```python
# Read the plan
read_file("docs/plans/feature-plan.md")

# Create todo list with all tasks
todo([
    {"id": "task-1", "content": "Create User model with email field", "status": "pending"},
    {"id": "task-2", "content": "Add password hashing utility", "status": "pending"},
    {"id": "task-3", "content": "Create login endpoint", "status": "pending"},
])
```

**Key:** Read the plan ONCE. Extract everything. Don't make subagents read the plan file — provide the full task text directly in context.

### 2. Per-Task Workflow

For EACH task in the plan:

#### Step 1: Dispatch Implementer Subagent

Use `delegate_task` with complete context:

```python
delegate_task(
    goal="Implement Task 1: Create User model with email and password_hash fields",
    context="""
    TASK FROM PLAN:
    - Create: src/models/user.py
    - Add User class with email (str) and password_hash (str) fields
    - Use bcrypt for password hashing
    - Include __repr__ for debugging

    FOLLOW TDD:
    1. Write failing test in tests/models/test_user.py
    2. Run: pytest tests/models/test_user.py -v (verify FAIL)
    3. Write minimal implementation
    4. Run: pytest tests/models/test_user.py -v (verify PASS)
    5. Run: pytest tests/ -q (verify no regressions)
    6. Commit: git add -A && git commit -m "feat: add User model with password hashing"

    PROJECT CONTEXT:
    - Python 3.11, Flask app in src/app.py
    - Existing models in src/models/
    - Tests use pytest, run from project root
    - bcrypt already in requirements.txt
    """,
    toolsets=['terminal', 'file']
)
```

#### Step 2: Dispatch Spec Compliance Reviewer

After the implementer completes, verify against the original spec:

```python
delegate_task(
    goal="Review if implementation matches the spec from the plan",
    context="""
    ORIGINAL TASK SPEC:
    - Create src/models/user.py with User class
    - Fields: email (str), password_hash (str)
    - Use bcrypt for password hashing
    - Include __repr__

    CHECK:
    - [ ] All requirements from spec implemented?
    - [ ] File paths match spec?
    - [ ] Function signatures match spec?
    - [ ] Behavior matches expected?
    - [ ] Nothing extra added (no scope creep)?

    OUTPUT: PASS or list of specific spec gaps to fix.
    """,
    toolsets=['file']
)
```

**If spec issues found:** Fix gaps, then re-run spec review. Continue only when spec-compliant.

#### Step 3: Dispatch Code Quality Reviewer

After spec compliance passes:

```python
delegate_task(
    goal="Review code quality for Task 1 implementation",
    context="""
    FILES TO REVIEW:
    - src/models/user.py
    - tests/models/test_user.py

    CHECK:
    - [ ] Follows project conventions and style?
    - [ ] Proper error handling?
    - [ ] Clear variable/function names?
    - [ ] Adequate test coverage?
    - [ ] No obvious bugs or missed edge cases?
    - [ ] No security issues?

    OUTPUT FORMAT:
    - Critical Issues: [must fix before proceeding]
    - Important Issues: [should fix]
    - Minor Issues: [optional]
    - Verdict: APPROVED or REQUEST_CHANGES
    """,
    toolsets=['file']
)
```

**If quality issues found:** Fix issues, re-review. Continue only when approved.

#### Step 4: Mark Complete

```python
todo([{"id": "task-1", "content": "Create User model with email field", "status": "completed"}], merge=True)
```

## delegate_task hard timeouts and salvage

`delegate_task` (the Hermes built-in) has **two independent ceilings** per subagent invocation, and either one will cut work short mid-task:

1. **Wall-clock timeout** — ~10 minutes, hard. Symptom: `status: "timeout"`, `exit_reason: "timeout"`, no `summary`, but a real `api_calls` count.
2. **Tool-call cap** — 50 tool calls (`max_iterations`). Symptom: `status: "completed"` (misleading!), `exit_reason: "max_iterations"`, `api_calls: 50`, and a `summary` that openly lists punted TODOs. The subagent gets to write a final report but ran out of room to finish.

Both have the same salvage move; the difference is only the trigger. Long-running tasks (large-surface refactors, multi-file rewrites, 50+ fetcher implementations) WILL hit one of them.

**Critical: subagents commit incrementally as they work.** When you see a timeout, do NOT redispatch or treat as failure. First:

1. `git log --oneline -10` in the workdir — count new commits since dispatch.
2. `git status --short` — check for uncommitted changes that represent in-flight work.
3. `git diff HEAD~N` (N = number of new commits) — read what they shipped.
4. Run any tests or smoke checks the spec demanded.

In a real session: 3 parallel `delegate_task` calls all timed out at 600s. All 3 had committed substantial work (one had 4 commits including a self-correcting fix-up pass). 95% of the requested work was done; the timeout just cut off final reporting and a `git push`. The orchestrator then committed the remaining uncommitted diff manually with a clear message and moved on.

In another session: a Phase B feature delegation hit `max_iterations` at 50 calls. The subagent had landed 3 clean commits (DB column, API route, tests — all passing) but had explicitly punted the admin UI button AND skipped `npm run build`. The summary said so honestly. The orchestrator ran the build, caught a TypeScript error the subagent's pattern-matching had introduced (`candidate.interviews` didn't exist on the type — the real list lived in a separate `interviews` state variable), fixed it, added the UI button, and shipped a 4th commit. Total: ~5 minutes to finish what would have been ~15 minutes to redispatch.

**Anti-pattern:** treating timeout OR max_iterations as "must redispatch from scratch." Forces the subagent to re-read context, re-explore, re-implement. Burns hours and risks merge conflicts with the partial work that did land.

### Sizing tasks to fit the budget

- Single fetcher / single small file → safely fits in 10 min
- 12 fetchers in one file → on the edge, may timeout near the end
- 12 KPIs × 4 programs = 48 fetchers → WILL timeout, plan for partial completion
- Multi-file architectural refactor → split into 3+ subagent calls or accept salvage workflow

When the work clearly exceeds 10 min, structure the spec so the subagent commits after each logical chunk (every 3-5 fetchers, every file, every passing test). That way the timeout cuts off at most one chunk's worth of progress.

### Build / test verification is an ORCHESTRATOR responsibility

Under cap pressure (approaching wall-clock or iteration ceiling), subagents will skip the final `npm run build` / `pytest` / `cargo check` even when the spec demanded it. They'll honestly report it as "not run" in the summary, but the work isn't actually verified.

**Rule:** when a subagent returns with `exit_reason: "max_iterations"` or `"timeout"`, the orchestrator runs the build and the new tests itself before declaring the task done. Don't trust "build status: not run" as a soft warning — treat it as "must verify now."

Common subagent failure mode caught only at orchestrator-side build: TypeScript type errors from pattern-matched edits that look right but reference fields/state that doesn't exist on the actual type. The subagent's grep-and-patch didn't load enough of the surrounding type definition.

## Subagent permission landmines

`--permission-mode acceptEdits` does NOT auto-approve Bash commands. The subagent will refuse `curl`, `npm`, `git commit`, and similar commands with a "permission denied" message and either ask you (in interactive mode) or silently stop (in `-p` mode).

For non-interactive `delegate_task` and `claude -p` dispatches, you must explicitly allow the needed Bash patterns:

```python
delegate_task(
    goal=...,
    context=...,
    toolsets=['terminal', 'file'],
    # NOT yet exposed to delegate_task — see workarounds below
)
```

`delegate_task` doesn't surface `--allowedTools` directly. Two workarounds:

1. **Pre-approve at the project level** by writing `.claude/settings.local.json` in the workdir BEFORE dispatch:
   ```json
   {"permissions": {"allow": ["Bash(curl http://localhost:*)", "Bash(npm *)", "Bash(git *)", "Read", "Edit", "Write"]}}
   ```
   The subagent inherits this on startup.

2. **Direct `claude -p` invocation** when you need fine-grained control:
   ```bash
   claude -p "..." --permission-mode acceptEdits \
     --allowedTools "Read, Edit, Write, Bash(curl *), Bash(npm *), Bash(git *)"
   ```
   Then poll the background process from your orchestrator.

In a real session: a subagent burned 3 minutes telling the orchestrator "I'm blocked from running `curl localhost:3030`" before falling back to the second workaround. The repo-level `.claude/settings.local.json` was the fix.

## Final Review

After ALL tasks are complete, dispatch a final integration reviewer:

```python
delegate_task(
    goal="Review the entire implementation for consistency and integration issues",
    context="""
    All tasks from the plan are complete. Review the full implementation:
    - Do all components work together?
    - Any inconsistencies between tasks?
    - All tests passing?
    - Ready for merge?
    """,
    toolsets=['terminal', 'file']
)
```

### 4. Verify and Commit

```bash
# Run full test suite
pytest tests/ -q

# Review all changes
git diff --stat

# Final commit if needed
git add -A && git commit -m "feat: complete [feature name] implementation"
```

## Task Granularity

**Each task = 2-5 minutes of focused work.**

**Too big:**
- "Implement user authentication system"

**Right size:**
- "Create User model with email and password fields"
- "Add password hashing function"
- "Create login endpoint"
- "Add JWT token generation"
- "Create registration endpoint"

## Red Flags — Never Do These

- Start implementation without a plan
- Skip reviews (spec compliance OR code quality)
- Proceed with unfixed critical/important issues
- Dispatch multiple implementation subagents for tasks that touch the same files
- Make subagent read the plan file (provide full text in context instead)
- Skip scene-setting context (subagent needs to understand where the task fits)
- Ignore subagent questions (answer before letting them proceed)
- Accept "close enough" on spec compliance
- Skip review loops (reviewer found issues → implementer fixes → review again)
- Let implementer self-review replace actual review (both are needed)
- **Start code quality review before spec compliance is PASS** (wrong order)
- Move to next task while either review has open issues

## Handling Issues

### If Subagent Asks Questions

- Answer clearly and completely
- Provide additional context if needed
- Don't rush them into implementation

### If Reviewer Finds Issues

- Implementer subagent (or a new one) fixes them
- Reviewer reviews again
- Repeat until approved
- Don't skip the re-review

### If Subagent Fails a Task

- Dispatch a new fix subagent with specific instructions about what went wrong
- Don't try to fix manually in the controller session (context pollution)

## Efficiency Notes

**Why fresh subagent per task:**
- Prevents context pollution from accumulated state
- Each subagent gets clean, focused context
- No confusion from prior tasks' code or reasoning

**Why two-stage review:**
- Spec review catches under/over-building early
- Quality review ensures the implementation is well-built
- Catches issues before they compound across tasks

**Cost trade-off:**
- More subagent invocations (implementer + 2 reviewers per task)
- But catches issues early (cheaper than debugging compounded problems later)

## Integration with Other Skills

### With writing-plans

This skill EXECUTES plans created by the writing-plans skill:
1. User requirements → writing-plans → implementation plan
2. Implementation plan → subagent-driven-development → working code

### With test-driven-development

Implementer subagents should follow TDD:
1. Write failing test first
2. Implement minimal code
3. Verify test passes
4. Commit

Include TDD instructions in every implementer context.

### With requesting-code-review

The two-stage review process IS the code review. For final integration review, use the requesting-code-review skill's review dimensions.

### With systematic-debugging

If a subagent encounters bugs during implementation:
1. Follow systematic-debugging process
2. Find root cause before fixing
3. Write regression test
4. Resume implementation

## Example Workflow

```
[Read plan: docs/plans/auth-feature.md]
[Create todo list with 5 tasks]

--- Task 1: Create User model ---
[Dispatch implementer subagent]
  Implementer: "Should email be unique?"
  You: "Yes, email must be unique"
  Implementer: Implemented, 3/3 tests passing, committed.

[Dispatch spec reviewer]
  Spec reviewer: ✅ PASS — all requirements met

[Dispatch quality reviewer]
  Quality reviewer: ✅ APPROVED — clean code, good tests

[Mark Task 1 complete]

--- Task 2: Password hashing ---
[Dispatch implementer subagent]
  Implementer: No questions, implemented, 5/5 tests passing.

[Dispatch spec reviewer]
  Spec reviewer: ❌ Missing: password strength validation (spec says "min 8 chars")

[Implementer fixes]
  Implementer: Added validation, 7/7 tests passing.

[Dispatch spec reviewer again]
  Spec reviewer: ✅ PASS

[Dispatch quality reviewer]
  Quality reviewer: Important: Magic number 8, extract to constant
  Implementer: Extracted MIN_PASSWORD_LENGTH constant
  Quality reviewer: ✅ APPROVED

[Mark Task 2 complete]

... (continue for all tasks)

[After all tasks: dispatch final integration reviewer]
[Run full test suite: all passing]
[Done!]
```

## Remember

```
Fresh subagent per task
Two-stage review every time
Spec compliance FIRST
Code quality SECOND
Never skip reviews
Catch issues early
```

**Quality is not an accident. It's the result of systematic process.**

## Further reading (load when relevant)

When the orchestration involves significant context usage, long review loops, or complex validation checkpoints, load these references for the specific discipline:

- **`references/context-budget-discipline.md`** — Four-tier context degradation model (PEAK / GOOD / DEGRADING / POOR), read-depth rules that scale with context window size, and early warning signs of silent degradation. Load when a run will clearly consume significant context (multi-phase plans, many subagents, large artifacts).
- **`references/gates-taxonomy.md`** — The four canonical gate types (Pre-flight, Revision, Escalation, Abort) with behavior, recovery, and examples. Load when designing or reviewing any workflow that has validation checkpoints — use the vocabulary explicitly so each gate has defined entry, failure behavior, and resumption rules.

Both references adapted from gsd-build/get-shit-done (MIT © 2025 Lex Christopherson).
