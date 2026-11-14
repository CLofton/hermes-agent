# MIGRATION — v2.1 (pool availability modes) → v2.2 (rigor modes, spec §0)

Date: 2026-09-08 · Approver: the operator (decisions: Option A — drop pools; system-wide
replacement of engineering-swarm-v2). Milestone contract:
`~/.hermes/tmp/engineering-swarm-v2.2-milestone-contract.md`. Pre-change backup:
`~/.hermes/tmp/engineering-swarm-pre-v2.2-backup/` (policy.json, router.py, test_router.py).

## What changed

1. **Mode semantics**: easy/medium/hard/expert are now RIGOR levels per SPEC §0
   ("Operating mode overrides"), not model rosters. `policy.json` `modes` now holds
   `rank`, `use_when`, `override_behavior`, `minimum_proof` (verbatim from the spec
   table). All `pools`, `openrouter_slugs`, `roles` (per-mode), and `judge_fallback`
   entries were removed from `modes`.
2. **Model selection decoupled from mode**: `_pick`/`pick_model` always draw from the
   tier registry (`policy.json tiers.*.candidates`); `dispatch_target` always uses the
   model's own provider account. Pool-membership checks, the openrouter-slug dispatch
   branch, and the `mode_pool_violation` status are deleted. A model with no
   dispatchable route now fails closed as `dispatch_refused`.
3. **Floor, not ceiling (rule 5)**: `resolve_mode` computes effective =
   max(selected, derived). Derivation (rule 1–4): T7/T11/T13/T14 or critical T8 →
   expert; E3/E4, no-repro bug, cross-module, concurrency, new design, or critical
   flag → hard; normal code change (T2/T3/T5/T6/T8/T9/T12) → medium; T1/T4/T10 → easy.
   Raises are logged in `mode.raise_reason`. The router never lowers below the
   user-selected mode.
4. **Effort raise on material uncertainty**: hard/expert raise effort one level
   (capped E4) when a bug has no reproduction or a prior attempt failed; logged in
   `mode.effort_raises` and the route rationale.
5. **Default mode**: `expert` → `easy` (spec §0 rule 1). Rigor is still enforced by
   task-type/flag derivation, so a critical task planned at the default gets expert
   rigor + all gates.
6. **Safety flags win (rule 6)**: unchanged gate logic, now explicitly tested under
   every rigor mode.
7. **policy_version**: 2.1.0 → 2.2.0. Old pool definitions preserved under
   `modes_changelog.removed_pool_definitions` (reference only; the router no longer
   reads them).
8. **Tests**: `TestModes` (11 pool tests) replaced by `TestRigorModes` (11 rigor
   tests: ranks declared, decoupling proof — identical model sets across all four
   modes — own-provider dispatch, default=easy, task-level mode honored, floor
   semantics on critical T8, gates+recipe identical across modes, hard effort raise
   on missing repro, expert T14 premium gates, dispatch_refused on malformed
   registry, unknown mode refused). `route.example.json` regenerated (now v2.2.0,
   default-mode plan). Full suite: 66 tests PASS.

## Behavior deltas to be aware of
- A task that previously ran on the "hard" model pool (Opus/GPT/Grok via OpenRouter)
  now runs on the tier-registry models at hard RIGOR. To pin specific models, name
  them in the registry tier roles — that is now the only model-selection mechanism.
- "medium mode" no longer means "Grok drives + open-source workers" (the session
  selection of 2026-09-08 ~21:15 CDT was a pool choice; after this migration the word
  means the §0 rigor level).
- Plans now carry `mode.{selected, derived, effective, rank, raise_reason,
  effort_raises}` in place of `mode.pool_source` and pool `substitutions`.

## Rollback
Restore the three backed-up files from `~/.hermes/tmp/engineering-swarm-pre-v2.2-backup/`
(policy.json, router.py, test_router.py), regenerate `route.example.json` with the old
router (`--mode expert`), and re-sync the 45 skill locations. Old pool definitions are
also embedded in `policy.json` `modes_changelog` if the backup is lost.

## Verification evidence (2026-09-08)
- `python3 -m unittest discover -s . -p test_router.py` → Ran 66 tests, OK.
- `router.py task.example.json --mode {easy,medium,hard,expert} --today 2026-09-08` →
  all `planned`; model sets byte-identical across modes (decoupling verified).
- `--mode quantum` → clean PolicyError, exit 1.
- SPEC.md untouched: SHA-256 399f64cc25d973bf… (the operator's attached file).

## Cross-family premium review (expert minimum proof)
Reviewer: Anthropic claude-opus-5 (profile `engineer`), fresh session
20260908_235152_a656c9 — a different family from the implementer (qwen/
OpenRouter). 25 tool calls: re-ran the 66-test suite itself, inspected
policy.json, diffed against SPEC §0, verified the SPEC hash.
**Verdict: PASS.** All 8 acceptance criteria met with evidence; zero
Critical/High findings. Three Low findings:
- (a) review-package diff summary was lossy for the policy.json modes block
  (shipped file correct; doc-only issue) — no code change.
- (b) stale vestiges: four `_pick_ctx(policy, "expert", {"pools": {}...})`
  fallbacks + one `mode_pool_violation` comment — **swept post-review**
  (now `modes.default` fallbacks + `dispatch_refused` comment); 66/66 re-green.
- (c) expert mode also raises effort on material uncertainty while SPEC §0
  assigns that behavior to the hard row and "decompose into E1–E2 bounded
  items" to expert. Conservative direction (raises rigor only, logged, no gate
  removed); accepted as-is, flagged for spec alignment at next revision.


## Open (not part of this milestone)
- Re-sync of the 43 profile skill locations (an external profile-sync actor was
  actively rewriting them during implementation; re-run after it settles).
- The runtime controller (TaskState store, event log, ledger) is still unbuilt per
  SKILL.md "Binding and status" — passing offline tests do not establish it.
