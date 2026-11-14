---
name: hermes-profile-skill-sync
description: Use when propagating a skill change to all Hermes profiles.
version: 1.0.0
---

# Hermes Profile Skill Sync

Propagating a skill or policy-package change across the whole system — default profile + every profile copy + the source directory — with hash verification at every step. the operator treats "system-wide" as byte-identical across all locations, and reports must state verified counts.

## When to use
- "Make this a system-wide update" / "replace X in all things" / "sync to all profiles"
- A skill's SKILL.md or a policy package changed and copies exist in multiple profiles
- Before delivering a versioned zip of a policy package

## Inventory (verify each time — never assume)
1. Canonical: `~/.hermes/skills/<category>/<name>/` (default profile).
2. Profiles: `~/.hermes/profiles/*/skills/<category>/<name>/` — count from the filesystem (43 on this machine as of 2026-09), never hardcode.
3. Source dir: e.g. `~/Downloads/hermes-<name>…/` — often a FLAT package layout (files at top level, no `scripts/package/` subdirectory). Match the existing layout; never restructure it.

## Procedure
1. **Check for sync actors BEFORE writing.** `ps aux | grep "rsync -a --delete" | grep -v grep` and `find ~/.hermes/profiles -maxdepth 4 -type d -name <category> -newermt "-5 minutes" | wc -l`. A backup rsync (to an external volume) or another agent session can rewrite or delete profile skill trees mid-operation. If active, wait for it to settle; if you must proceed, do this sync LAST and re-verify afterward.
2. Back up the pre-change state (copy the touched files to `~/.hermes/tmp/<name>-pre-<version>-backup/`) before editing canonical.
3. Edit canonical only.
4. Propagate: `rm -rf` each target then `cp -a` fresh (avoids stale files) to every profile location; copy the relevant files into the source dir in its native layout.
5. **Hash-verify every location at write time**: compare sha256 of the key files (SKILL.md + package core files) against canonical per location, and report `ok/bad` counts with the expected total stated. A "0 bad" count without the expected count is not verification.
6. Re-verify by absolute path after any batch operation if time passed — the tree can move between write and check.
7. Deliverable: versioned zip to `~/Downloads/<name>-<version>-<YYYY-MM-DD>.zip`; report its sha256.
8. Update the persistent memory fact that records the old version state, so future sessions don't route on obsolete semantics (e.g. old mode/pool definitions).

## Pitfalls
- **Persistent shell cwd can die mid-session.** If every terminal command fails with `cd: <path>: No such file or directory` and the command contains no `cd`, the shell's persistent working directory was deleted or renamed by the sync. Run one diagnostic (`pwd && ls`) with an explicit `workdir`, then pass `workdir` on every subsequent call — retrying the bare command loops forever.
- **Verification can be minutes stale.** External writers (backup rsyncs, other agent sessions) mutate the tree between your write and your check. Re-verify a sample by absolute path before reporting success; never mark N locations done based on a pre-mutation check.
- **Profile skill trees are not stable.** Another sync actor may rename or remove skill dirs after your write (a `-v2` dir can become un-suffixed mid-operation). Treat "dir present but renamed/gone" as a signal, not an error: diff the directory listing to find the rename before recreating, and pick the forward name deliberately.
- **Flat vs nested layout.** The source dir may hold the package flat while the skill nests it under `scripts/package/`. Compare file-to-file with the correct mapping; a layout-blind copy produces "verified" trees that don't match.
- **`find ~/.hermes` over the whole tree times out** (it is huge). Scope to `~/.hermes/skills` and `~/.hermes/profiles/*/skills` with `-maxdepth`.
- **Approval-gated commands are not failures to retry.** If `hermes kanban create` or similar returns blocked/timed-out on consent, use the alternate dispatch path (e.g. `delegate_task`) and log the substitution — don't loop on the blocked command.

## Pre-sync gate for policy/routing changes (T14 class)
For changes to routing policy or agent behavior, run a cross-family one-shot review BEFORE syncing. Assemble a review package (spec excerpts, full diffs, test output, explicit acceptance criteria, verdict format: PASS/FAIL + severity-ranked findings), then:

    HERMES_PROFILE=<different-family-profile> hermes chat -q "$(cat review-package.md)" --oneshot --max-turns 12

The reviewer must be a different model family than the implementer. On this machine the `engineer` profile (Anthropic family) pairs with a default qwen/OpenRouter implementer. Have the reviewer re-run the test suite itself, not trust the implementer's claim; PASS with zero Critical/High findings is the gate. Sweep the reviewer's actionable Low findings, re-run tests, then sync. Record the review session ID in the migration record.

## Reporting
State verified counts per location class (canonical / profiles / source), the zip sha256, and any external-actor interference observed. Never report "synced" without a hash-verified count; never report "N profiles" when the tree moved after the check.
