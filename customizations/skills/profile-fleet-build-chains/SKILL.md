---
name: profile-fleet-build-chains
description: Use when executing multi-item builds across a profile fleet.
version: 1.0.0
author: Nous Research
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [multi-agent, kanban, worktrees, build]
---

# Profile Fleet Build Chains

Execute a decomposed build (N items, each its own PR) by dispatching Hermes profile sessions as workers inside isolated git worktrees. Each item runs a node chain (e.g. test-design -> implement -> cross-family review); the controller (this agent) orchestrates, verifies, and — only with the operator's explicit go — pushes/merges.

## When to use
- A merged spec or plan decomposes into 2+ bounded items with disjoint owned-file sets
- the operator wants multiple models/families on the same repo with cross-family review
- The work must stop at commit-local (deploy is a separate gated step)

## Setup (once per repo)
1. Confirm base revision: `git fetch origin main && git rev-parse origin/main`. Never build on a dirty main checkout.
2. One worktree per item: `git worktree add ~/Downloads/<task>/wt-<item> -b feat/<branch> <base-sha>`.
3. Shared controller dir: `~/Downloads/<task>/{briefs,runs,reviews,routing}`. Briefs via `write_file` (heredocs trip the terminal consent layer); runner script via `write_file` + `chmod +x` (a written script is NOT executable — exit 126 otherwise).

## Dispatch (the worker command)
```
terminal background=true:  cd <worktree> && hermes -p <profile> chat --query-file <brief.md> --oneshot --max-turns <N> > <runs>/<item>-<node>.out 2>&1
```
- `--query-file` for any brief over ~2KB: long `-q "$(cat ...)"` prompts can silently drop into the interactive TUI and exit without working. `-q` is fine for short prompts.
- Probe every profile with a 2-turn `DISPATCH_OK` test BEFORE a batch launch — a profile whose model ID is invalid fails with HTTP 400 after minutes of nothing.
- Unique profile per concurrent node; fixer and re-reviewer of the same item must be DIFFERENT model families (cross-family rule).
- Launch bounded worker nodes with completion notification and record their process/session IDs in the controller ledger. Consume completion events rather than adding a polling worker; preserve the node's logs and source revision for verification.
- Require artifact-first writing with a bounded discovery allowance. On a turn-limit exit, inspect structured termination metadata and actual files, then run the remaining checks on the supported runtime before deciding whether another worker is needed; source can be complete even when the final narrative was never emitted. Resume only demonstrated gaps within the routed retry ceiling, not the entire implementation.
- Workers face their own consent/approval layers: protected files (e.g. CLAUDE.md) and some tools (execute_code) get blocked mid-run. Briefs must state the fallback (e.g. "document in docs/<x>.md, not CLAUDE.md") so the worker doesn't stall or report false completion.

## Node chain shape (per item)
1. **TD** (test design, independent): writes ONLY test files from the contract; tests must be red where the contract is unmet.
2. **IM** (implementer): makes TD's tests pass without editing existing independent or parent tests. Freeze their hashes before dispatch and compare after every repair. A suspected bad assertion goes to the controller for contract-based adjudication; preserve the failing run, document any authorized oracle correction, and prove the corrected test still catches the defect. Verify loop: targeted tests green plus the repository's configured checks with zero NEW errors.
3. **RV** (cross-family reviewer): reviews diff + source (NOT the implementer's report), runs tests itself, does 3 mutation spot-checks (break -> RED -> revert), checks scope/copy/kill-switch, writes `reviews/<item>-review.md`, final line `VERDICT: PASS|FAIL` with numbered file:line findings.
4. **Fix round(s)**: reproduce each reviewer finding in a regression before repair; one bounded node per FAIL, brief = the numbered findings and evidence paths. Retry only failed work. Reuse a PASS only while its source, contract, dependency revisions and relevant runtime remain unchanged; otherwise invalidate that gate. Archive each review pass separately and respect the routed retry/replan ceiling.
5. Deterministic one-line fixes (a stray constant, a doc line) the controller can verify itself should be applied directly with patch + a test run, not dispatched to a model loop. But do NOT edit a worktree while a reviewer is running (its `git status` check breaks).

## Parent acceptance before handoff
- Pin and record the actual interpreter/toolchain before testing; run unit tests, subprocess CLI tests and mutation checks with that same executable rather than trusting a bare command name.
- Reconcile aggregate test discovery with the owned test-file inventory; a green discovery command can silently omit a team's directory.
- Verify a frozen candidate, not a moving writer tree: run independent tests, owner tests, reviewer regressions, every promised entry point and targeted mutations on an isolated copy, then confirm the source hashes are unchanged.
- Treat green suites as necessary, not sufficient. For +G, obtain fresh final judgment on the exact candidate and real execution receipts; a final HOLD reopens only a bounded, explicitly recorded repair/replan, never permits a completion claim.
- Keep build verification, observed business outcomes and activation authority separate in the delivery. Synthetic demonstrations do not prove live operational results; local acceptance does not authorize sends, schedules, financial writes or production changes.

Detailed verification and numerical-oracle procedures are in `references/pitfalls.md`.

## Stop gate and merge (only after the operator's explicit go)
- Everything stops at `git add <owned files> && git commit` in the item worktree. No push/PR/migrate in any worker brief.
- Merge order: island files first, biggest fan-out last. Per item: rebase onto latest `origin/main` (it moves while the fleet runs), re-run the item test set POST-REBASE, push, `gh pr create` with the review trail in the body (verdicts, findings resolved, commits), squash-merge, delete branch, verify the Vercel deploy reaches `Ready`.
- Push: verify the remote branch doesn't exist first (`git ls-remote --heads origin <branch>`) and use a PLAIN `git push -u` — `git push -f` trips the destructive-consent block, and batched commands that contain it get blocked wholesale. Run pushes as standalone commands.
- Worktree hygiene: inventory a dirty tree before review and preserve uncommitted work whose ownership is uncertain. `git restore`, `git clean` and resets can discard work; never label them non-destructive or use them to manufacture a clean gate. Review an isolated committed candidate, or obtain authority for narrowly scoped cleanup after preserving the affected work.
- Post-merge ops items (env vars, duplicate cron kills) are reported to the operator as named follow-ups, never silently done in a PR.

## Premium gate (+G) substitution
When the routing plan names a judge model with no authenticated provider on this machine, substitute the declared cross-family judge (e.g. grokreview/xAI standing in for an OpenAI premium), LOG the substitution in the contract review, and keep cross-family vs the implementer. Judges often write their output to stdout instead of the review file the next gate (acceptance) reads — save the stdout body to the expected path before running the acceptance node.

See `references/pitfalls.md` for the consolidated failure catalog (each with the fix).
