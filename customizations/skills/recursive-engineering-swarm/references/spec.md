# Recursive Engineering Swarm — Controlling Specification

## Goal
Automate GPT-6 Astra decomposition into the smallest testable units and promote passing work through atomic, feature, and whole-app gates using durable Hermes Kanban dependencies.

## Roles
- `default` / GPT-5.6 Terra: conductor and coordinator. Critical contract and final app-judge cards are pinned to GPT-6 Astra directly, independent of the default profile. Astra is the governed judge; Sol is not used routinely.
- `qwen` / Qwen3.8 27B: atomic micro-specs and read-only architecture reviews.
- `deepseek` / DeepSeek V4 Flash: executable tests and required RED evidence.
- `glmvalue` / GLM-5.3 Flash: sole source implementation and integration writer.
- `grokreview` / Grok 4.20: optional read-only adversarial review at feature/app boundaries, public/internal only, off by default.
- `opus47` / Opus 4.7: optional recovery escalation only after typed F3 implementation shortfalls reach the route threshold.

## Input contract
A versioned JSON plan contains app id/title/acceptance/sensitivity/repo and features. Every feature contains acceptance criteria and one or more atomic units with acceptance criteria. Only public/internal sensitivity is permitted.

Version 1 plans remain supported. Version 3 plans additionally carry `policy_version="3.0.0"`, `task` binding metadata, and a deterministic `route` object. Route decisions are part of the canonical plan hash and therefore part of every idempotency key.

## V3 routing policy
- Task types are `T1`-`T14`; effort levels are `E0`-`E4`; modifiers are `E`, `P`, `G`, `H`, and `V`.
- Stage 1 routing is deterministic from explicit fields, paths, keywords, and simple size/ambiguity signals. It makes no API calls and emits JSON only.
- Validated roles are fixed: `default` = Terra coordinator with Astra-pinned critical judge gates, `qwen` = spec/review, `deepseek` = RED tests, `glmvalue` = sole implementation, `grokreview` = optional read-only adversarial review, `opus47` = optional F3 recovery escalation.
- Critical flags (`critical`, `payments`, `secrets`, `destructive`, `pii`) require Astra contract and Astra final acceptance gates.
- Manual flags (`prod`, `destructive`, `external-writes`) require a manual approval card scoped to exact plan hash, plan revision, and action.
- A registry is optional. If present, entries with future `checked_at` dates or stale dates beyond the declared max age are rejected.
- Route output uses argv arrays only and never shell command strings.

## Graph contract
1. Completed conductor anchor.
2. Optional v3 Astra contract upstream of worker cards when selected. The blocked manual approval gate is downstream of final Astra acceptance (or the app judge when no premium acceptance applies), so approval is scoped to the completed plan revision and exact action.
3. Every atomic unit: Qwen spec → DeepSeek RED tests → GLM build/GREEN → Qwen review.
4. Every feature: DeepSeek integration tests → GLM integration → Qwen review, gated on the complete app-wide atomic/base layer so no feature integration starts early.
5. Optional Grok read-only adversarial review follows feature/app review boundaries when modifier/policy routing selects it.
6. Whole app: DeepSeek system tests → GLM app integration → Qwen architecture review → fresh Astra final judge, gated on every feature review or Grok review.
7. Optional v3 Astra final acceptance follows the app judge when critical/premium routing selects it.
8. All DeepSeek/GLM repository mutations form one total order. Read-only Qwen/Astra/Grok tasks may pipeline only when their parents are complete.
9. Every graph parent must resolve to a real node. All cards are created blocked or protected by parents/goal-mode; dispatch happens once after full graph creation and root opening.

## Gate contract
- Goal-mode Kanban judges guard worker completion against each card contract.
- Test tasks report metadata: `verdict=PASS`, test paths/hashes/command, and nonzero RED exit evidence.
- Build tasks report metadata: `verdict=PASS`, targeted exit 0, and regression exit 0.
- Review/judge tasks report `verdict=PASS` and an empty findings list, or block on FAIL/NOT YET PROVEN.
- Astra contract/final acceptance gates report exact `gate`, `plan_hash`, `policy_version`, `route_cell`, and `findings=[]`.
- Manual approval gates report exact `gate=manual_approval`, `plan_hash`, `plan_revision`, `action`, plus nonblank `approved_by` and ISO `approved_at`.
- The generated run manifest feeds a deterministic final `certify` command. Missing/invalid evidence denies release even if a worker incorrectly reached `done`.
- Kanban handles card retries; only failed cards requeue. F1 retries the failed unit, F2 repairs the contract, F3 retries the failed unit until the configured Opus threshold, F4 replans integration, and F5 stops.

## Safety and cost
- Dry-run is default; only `apply` mutates the board.
- Idempotent apply must create no duplicate cards.
- OpenRouter cards cannot receive restricted/secret plans.
- Per-route task-count, runtime, retry, and USD ceiling metadata is mandatory for v3. Exceeding declared ceilings fails closed before graph creation. USD ceilings are routing ceilings, not spending authority.
- No deploy, merge, production write, or external message is authorized by this workflow.

## Acceptance criteria
- Identical plan produces identical graph IDs, edges, and idempotency keys.
- Missing features/units/acceptance criteria or forbidden sensitivity fails closed.
- Every build has a DeepSeek test ancestor and every integration waits for lower-level reviews.
- Writer tasks form a total dependency order.
- Dry-run invokes no Kanban mutation.
- Reapplying creates no duplicates.
- Real isolated Kanban smoke proves parent gating and final graph shape.
- Deterministic certification fails on missing evidence and passes only with complete RED/GREEN/review/judge metadata.
- V3 changed task/policy/route inputs change the plan hash and idempotency keys.
- V3 critical/manual gates are blocked or gated exactly as routed and require exact certification metadata.
- Optional Grok review is read-only and never runs for restricted/secret data.
- Opus recovery is not routine; it appears only after typed F3 shortfalls hit the configured threshold.
- Qwen/DeepSeek/GLM/Astra profiles resolve to intended models and specialist gateways remain stopped.
