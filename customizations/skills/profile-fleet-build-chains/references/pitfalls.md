# Profile-fleet failure catalog (each: failure -> fix)

## Dispatch layer
- **`nohup ... &` in terminal -> refused.** The consent layer rejects shell-level background wrappers. Use `terminal background=true` with a bare command.
- **`./script.sh` exit 126 (permission denied).** `write_file` does not set +x. `chmod +x` after every write_file of a runner script.
- **Completion tracking:** record each launched node's process/session ID, owned scope and evidence paths; on completion inspect termination metadata and artifacts before scheduling dependent work. A process exit is not a task verdict.
- **Long `-q` prompt silently enters TUI.** Symptom: output shows the Hermes welcome banner, "Goodbye", zero work, exit 0 or 2. Fix: `--query-file <path>` for long briefs.
- **Profile with invalid model ID.** Fails with `HTTP 400: <model> is not a valid model ID` after a full round-trip. Probe all profiles with a 2-turn DISPATCH_OK test before batch launch; substitute a working profile of the same family and log it.
- **Turn-boundary kills.** Background procs started near a turn boundary can die with no log. Verify aliveness early (`pgrep`) and relaunch from the log state; node chains are idempotent per-node so a relaunch of the missing node is safe.

## Worker layer
- **Protected-file write blocked (CLAUDE.md, config).** Worker stalls or reports the step undone. Brief must name the fallback location up front.
- **execute_code blocked by approvals** in some worker profiles. The worker copes (uses terminal) but burns turns — keep max-turns generous.
- **Iteration-budget exhaustion:** inspect the actual diff and run the prescribed checks before launching a completion node; the worker may have saved working code before exhausting its final response budget. Preserve the nonzero exit in the ledger and never relabel it as successful execution merely because some files exist.
- **Reviewer never emits VERDICT** (32 min, 111 calls, approval-blocked exploration). Treat as a failed node: re-run with a fresh profile and `--query-file`; never parse a mid-stream "looks like PASS" as the verdict.
- **Foreign contamination in worktrees:** preserve and identify unrelated changes before review; committing the current item's files does not make other uncommitted work disposable. Prefer a fresh worktree from the candidate revision. Restore/clean/reset operations require scoped authority and are not a shortcut around ownership or consent.

## Review / fix layer
- **Fixer misses the obvious.** A model fix round can leave a forbidden string in a test mock that a 10-second grep would catch. Controller spot-checks the reviewer's red lines (greps, file:line reads) AFTER each fix round and applies one-line mechanical fixes directly — but only after the reviewer's run finishes (mid-run edits break its `git status` check).
- **FAIL verdicts are progress.** Every FAIL this class produced carried numbered file:line findings + exact fixes + mutation-checked PASS on the good parts. The fix round brief = the findings verbatim; the re-review brief = "verify these N findings resolved + fast re-run of the full gate". Typically 1-2 fix rounds to PASS.
- **Rebase AFTER fixes, before push.** Main moves while the fleet runs (other merges land). Rebase, then re-run the item test set — merged sibling items can shift shared files (e.g. a reminder-eligibility module) that your tests mock.
- **Premium judge writes to stdout, not the review file.** The acceptance gate reads the file. Save the judge's stdout body (strip the session footer) to the expected path before running acceptance.

## Frozen-candidate verification recipe
1. Record the selected executable and version, for example `<python> -c 'import sys; print(sys.executable); print(sys.version)'`. Use `sys.executable` in Python subprocess tests so the CLI does not silently run under a different interpreter.
2. Inventory test files before discovery. Run `<python> -m unittest discover -s <test-root> -v` and reconcile discovered modules with every team directory. Add missing package markers or invoke each directory explicitly; do not report an aggregate that skipped a team.
3. Hash the contract and existing independent, parent and owner tests before a repair. Compare afterwards; an unauthorized assertion change blocks acceptance even when the suite turns green.
4. Copy only the candidate source, fixtures and tests into an isolated scratch directory, excluding caches and credentials. Run the complete baseline there before mutations; a pre-existing failure cannot count as a caught mutation.
5. Exercise each promised entry point and output format with explicitly synthetic fixtures. Assert returned semantics and provenance, not merely exit zero. Preserve actual stdout/stderr as receipts.
6. Break one discriminating behavior per workflow in separate disposable copies and require the relevant test to fail with an assertion, not an import or setup error. Never mutate the live writer tree. State the coverage honestly: targeted mutation checks are not comprehensive mutation coverage.
7. Test side-effect boundaries directly and narrowly. For pure report functions, load fixtures first, then fail on file/network/process calls, check input immutability and repeated-output equality, and reject nonfinite JSON. Label such checks by their actual scope; a static import scan is not a security certification.
8. Bind fresh final judgment to the candidate hashes and execution receipts. Reproduce any new HOLD findings before repair, retain the previous verdict, and rerun acceptance on the new hashes rather than overwriting the rejection history.

## Exact numerical test oracles
- Compute money expectations independently with `Fraction(decimal_string)` or a deliberately sufficient local Decimal context; using default-precision Decimal arithmetic in both implementation and expected values can conceal the same rounding defect or reject a correct fix.
- Preserve the original inputs and assertions when correcting an oracle. Record the mathematical reason, use exact equality rather than widening tolerance, and show the test fails against the defective implementation.
- Include values beyond default Decimal precision, multiple-row sums, mixed-sign cancellation and explicit zero thresholds. Test null separately from zero because truthiness erases supplied evidence.
- Separate exact sums/differences from rounded percentage display; a display choice must not silently alter the decision threshold or global numeric context.

## Push / merge layer
- **`git push -f` and batched pushes -> consent BLOCKED.** The destructive-consent layer blocks force pushes and multi-command batches containing them; the batch dies wholesale including the innocuous parts. Check `git ls-remote --heads origin <branch>` first; a never-pushed branch needs a plain `git push -u`. Run pushes as standalone single commands.
- **Merge order matters.** Island-file items first; the biggest fan-out (shared services + many pages) last, rebased onto everything. Expect 0 conflicts when the spec's owned-file sets were truly disjoint.
- **Deploy verification is part of the gate.** After each squash-merge, `vercel ls <project> --prod` must show a new `Ready` deployment before the item counts as shipped.
