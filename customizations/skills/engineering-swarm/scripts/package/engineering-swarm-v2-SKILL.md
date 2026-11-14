---
name: engineering-swarm
description: Use when routing engineering work by task and effort.
version: 2.2.3
---

# Engineering Swarm

the operator designated this Engineering Swarm package as the controlling engineering-routing policy. Prefer this effort-by-task policy over the older fixed Astra-conductor recursive swarm. Source package is an OFFLINE planner, not a live controller.

## Operating modes — rigor levels (pick one per task; spec §0)
easy / medium / hard / expert are **rigor levels, not model rosters** (v2.2, 2026-09-08). A mode may only *raise* rigor, width, budget/time ceilings or gates — it never removes a mandatory recipe, premium gate, human interrupt, secret rule, idempotency rule or verification requirement. **Model selection is fully decoupled from the mode**: every tier is filled from the tier registry (`policy.json` `tiers`) and each model dispatches on its own provider account.

Choose via the task JSON `"mode"` field or `router.py --mode <name>` (default: `easy`, per spec §0 rule 1).
- **easy** — routine workflows, cron jobs, simple setup: least expensive verified route, one owner, no advanced knobs.
- **medium** — normal product/engineering changes: matrix as written, independent test design + cross-family review for E2, default width 4.
- **hard** — cross-module, high-risk, ambiguous, production-adjacent: raises effort one level when uncertainty is material (no reproduction, prior failed attempt), explicit contract, stronger reviewer, R3/R4 when E3+.
- **expert** — foundational architecture, security/data/schema, policy/routing, irreversible writes: premium judge for +G contract/acceptance, +H before irreversible actions, decompose into E1–E2 bounded items under one milestone contract.

**A user-selected mode is a floor, not a ceiling (rule 5).** The router derives a floor from task type/effort/flags — T7/T11/T13/T14 or critical T8 → expert; E3+, no-repro bug, cross-module, concurrency or new design → hard; normal code change → medium; mechanical/test/research → easy — and plans at the *higher* of selected and derived, logging the raise in the plan's `mode.raise_reason`. It never lowers below the user's choice.

**Safety flags win over mode (rule 6):** `critical`, `payments`, `secrets`, `destructive`, `pii` still add `+G`; `prod`, `destructive`, `external-writes` still add `+H`.

## Cost contract
- Routine coordination uses GPT-5.6 Sol, not Astra. Execute mechanical checks with code, not model loops.
- E0: local or qualified flash; E1: flash; E2: mid; E3: high; E4: premium planning followed by separately routed bounded items.
- Reserve Astra for critical contract, bounded failed-candidate replan, fresh exact-revision acceptance, and genuinely foundational design. Keep premium personal/company security judgment intact.
- Route from T1–T14 task type and E0–E4 effort; preserve path-derived critical, secrets, PII, payments, destructive, prod and external-write flags. Never split work to evade a gate.
- Reviewer and implementer use different model families. One writer per target. Only failed nodes retry; cap attempts, time, context and concurrency.
- Pass absolute workspace/file paths, revisions, hashes, concise findings and evidence references—not the whole conversation or raw logs—to workers and premium judges. A missing assigned file means stop, not search home/Downloads. For public-document reading alone, prefer a document-only call with no filesystem tools or private session context.
- Verify the actual model in dispatch/completion metadata before accepting a tier-specific gate. A prompt saying “Astra” or an artifact labeling itself “premium judge” is not model-identity evidence; native delegation may use a configured lower-tier model. Preserve its findings as that model’s review, correct inaccurate attribution, and require genuine premium acceptance when the route calls for it.
- Re-run exact-revision acceptance in the parent before exposure. A reviewer’s APPROVE or an earlier green run must become HOLD if a fresh run fails; preserve the failure evidence and invalidate installers’ machine-readable gate, not just a prose status.
- Worker starting limits: E0 15 iterations/600 seconds, E1 30/1800, E2 50/7200, E3 80/21600. Native default homogeneous delegation is bounded at 50 iterations, 4 children, 600 seconds, depth 1; explicitly scoped long nodes need route-specific limits.

## Exact-count swarm execution
When the operator requests an exact number of agents, treat the count as an acceptance criterion:
1. Create one unique assignment and durable receipt path per requested identity before dispatch. Record provider, actual model, prompt hash, input artifact hash, start/end time, exit status, verdict and findings.
2. Count only successful independent model invocations as agents. Deterministic scripts, the parent orchestrator, aggregation passes and copied/synthetic receipts are verification infrastructure—not substitute workers. Never describe local checks as filling missing agent seats.
3. Launch in bounded batches at conservative concurrency. Persist each valid receipt immediately so a provider cap, transport failure or process timeout loses only in-flight lanes.
4. On provider failure, preserve completed lanes and retry only unfinished identities. Health-probe the exact provider route before each recovery batch, not just once: a route can pass a probe, complete several lanes, then hit a subscription or transport cap. Use small batches/conservative concurrency and checkpoint at every result so the next provider resumes only the remaining set. Diagnose structured CLI envelopes as well as stderr—some CLIs exit nonzero with an empty stderr while the actionable DNS/API error is in stdout JSON.
5. Keep one canonical manifest. Normalize recovery outputs into it only after schema validation and model-identity evidence; retain the original attempt trail separately rather than rewriting failed attempts into successes. Provider substitution is lane-level: preserve the same identity, assignment, artifact hash and receipt schema, while recording the actual provider/model that completed it.
6. Before saying complete, verify in code: requested identity set equals validated receipt set, every receipt came from a launched model invocation, provider/model counts reconcile to the total, all assignments are covered, and the source artifact hash is unchanged.
7. Do not close from a background-job heartbeat or an intermediate aggregate. Stop obsolete recovery jobs, poll them to an exited state, suppress stale notifications where possible, and deliver only after the canonical manifest and final report both validate. During a long run, report only the canonical counters—validated, failed, active/queued—and label every report or conclusion provisional until the exact-count gate passes; repeated heartbeat output is not new completion evidence. If the user says to finish after a premature closure, reset the canonical status to `IN_PROGRESS`, replace provisional deliverables only after full validation, and continue rather than defending the partial result. If providers remain unavailable, report the exact completed-agent count and the deterministic fallback separately—never call the requested swarm finished.
8. Treat native delegation as homogeneous unless dispatch metadata proves otherwise. Before a wide fan-out, run one canary on the exact route, then inspect the live child list to record the actual model. The parent model, requested rigor, or a replacement label does not prove a different route; a replacement launched through the same inherited surface normally shares the same provider limit and can fail in the same way.
9. On HTTP 429, read the failed lane's transcript for the exact model and provider retry window. Do not call an immediate redispatch on the same inherited route a provider substitution; either wait through the stated reset window or use an execution surface that can explicitly pin and verify a different authenticated provider/model. Canary-test the alternate execution surface for both model availability and account capacity before launching recovery lanes—successful authentication does not prove usable credits. Preserve the failed attempt and retry only that lane.
10. Prove tool isolation on the exact batch command, not by prompt wording. A model told “do not call tools” can still use its profile tools; use the execution surface's supported restricted/safe mode, a query file instead of shell interpolation, a one-turn ceiling, and then inspect the canary transcript for zero tool events before fan-out. A canary proves only that exact profile/model/provider/toolset/CLI path and does not count toward the requested population.
11. Parse streaming metadata by lifecycle, not by assuming every event is complete. A stream's initial model event may carry an empty session identifier while the terminal result carries the real one; allow the initial value to be empty only when the final nonempty identifier and every human-readable session line agree. Require exact model metadata, zero-exit completion, valid token types, no tool events, and one unique terminal session per identity. Label local agent session IDs as local provenance—not provider response attestation.
12. If a validator rejects an otherwise completed invocation, do not redispatch that identity. Freeze stdout/stderr, prompt, marker, process log, input hash and executable hashes; fix the parser under tests and cross-family review; then use a deterministic zero-model-call recovery that accepts only one zero-exit, non-timeout process with valid output and unique terminal identity. Record any executable-contract migration append-only, verify unchanged input/manifest hashes, and resume only after recovered receipts validate.
13. Create the durable dispatch marker immediately before process launch and before any possible provider request. A marker without a valid receipt blocks automatic retry because delivery is ambiguous; a completed receipt lets resume skip that identity. Report recovered receipts separately so the final reconciliation shows fresh versus salvaged completions without changing the total.
14. When an identity times out without a terminal result, do not blindly retry it to fill the requested count. Inspect the saved stream and session record for assistant/tool messages, token usage, API-call count and terminal state; preserve the failed attempt even when those signals show no completed worker. If ambiguity still blocks retry, add one replacement identity carrying the exact same assignment through a reviewed append-only manifest/config migration. Final validation must require the requested number of successful unique receipts, allow only explicitly pinned failed infrastructure attempts outside that receipt set, verify their original markers/process logs/streams by hash, and report successful agents, replacements and failed attempts separately. Never count the failed attempt or the migration as an agent.
15. If a completed worker's output is structurally valid and only a wholly derived aggregate field disagrees with its validated child records, do not redispatch it. Preserve the raw model output, apply one deterministic normalization rule (for example FAIL > NOT_YET_PROVEN > PASS), record the exact raw/normalized value and rule, bind both into the signed receipt, and replay the transform during validation. Reject every non-derived or multi-field repair; infrastructure may normalize schema arithmetic, not rewrite findings.
16. Test concurrent controllers against deterministic submission and identity-set semantics, never worker start/completion order. Instrument submission order or assert unordered batch membership, then rerun the complete suite in several fresh processes; thread scheduling can let an order-dependent test pass once and fail on the next run.

## Local toolkit verification
For local reporting CLIs and multi-workflow toolkits, load [the verification checklist](references/local-toolkit-verification.md) before test design and final packaging. It covers numerical boundaries, source-freeze discipline, ordinary CLI side effects, and safe artifact allowlists.

## Offline routing
Read `scripts/package/HERMES_START_HERE.md`, then the relevant sections of `scripts/package/SPEC.md` (§0 first). Before claiming the installed package is synchronized with the controlling source package, compare their manifests or file hashes. If the controlling path is inaccessible, update and verify the active installed package only when authorized, label the source copy unsynchronized, and do not claim package-wide completion. Execute:

    python3 <skill-dir>/scripts/package/router.py /absolute/task.json --policy <skill-dir>/scripts/package/policy.json
    python3 -m unittest discover -s <skill-dir>/scripts/package -p test_router.py

Use actual current date for execution; a pinned date is only for reproducible fixture tests. Router outputs a plan, not execution authority. Never paste policy.json into Hermes config.

## Binding and status
The registry in policy.json contains unconfirmed direct-provider settings, an unspecified local model, and price/account fields. Do not dispatch emitted cards blindly. Resolve each planned model to an authenticated tested provider, preserve family/tier, explicitly disclose substitutions, and obey sensitivity boundaries.

The full v2 runtime requires durable TaskState, semantic acceptance gates, append-only events, atomic budget reservations, provider usage reconciliation, checkpoints and a pilot. These are NOT established by passing offline router tests or changing model defaults. Do not claim universal automatic routing or spend enforcement until real end-to-end controller tests prove it.

Existing windows retain their loaded model; new config is not a live-window migration. Use the supported /model command in an idle window to switch, or start a fresh session. Never terminate active work merely to lower cost.

### Model roster upgrades

1. Query the live provider catalog and record the exact slug, release/canonical identifier, context limit, supported controls, and pricing; version numbers alone do not establish recency.
2. Smoke the intended operational paths separately. A direct-provider success does not prove an OpenRouter route, and an OpenRouter success does not prove a direct-provider profile.
3. Freeze every affected profile and resolve its effective pre-change main, delegation, auxiliary and Kanban-worker routes through the installed runtime. Do not equate an unchanged config subtree with unchanged behavior: absent delegation pins inherit the new parent; auxiliary `auto` follows main; NULL card reasoning inherits the assignee profile; an old `model.context_length` pin constrains the replacement model.
4. Update the policy registry, enabled tier candidates, profile defaults, fallback route, documentation, and focused roster tests as one change. Keep historical models disabled or remove them from dispatchable candidates. When specialized workers must remain stable, pin only the affected prior effective model/provider/reasoning routes and exact model overrides; do not stamp every roster model or built-in auxiliary default into every profile, because overbroad preservation pins become a second routing policy that silently drifts.
5. Stage the complete fleet in a disposable mirror, run deterministic route-resolution fixtures plus config semantic-diff checks, test atomic apply/rollback and drift refusal, then require a different-family review. The reviewer must inspect runtime inheritance effects, not only textual diffs.
6. Read back every affected live profile and run one default-model one-shot without explicit `-m`, provider, reasoning, resume, safe-mode or ignore-user-config flags. Verify actual model/provider/transport/reasoning and no fallback; canary delegated and auxiliary paths separately when their bindings changed.
7. Run JSON parsing and the full router suite. Report context-window and price trade-offs, not only the model name.
8. Treat specialized consumers such as X-search as separate integrations; do not change their model merely because the worker roster changed without a compatibility smoke.

## Jev judgment nodes (2026-09-20)
Load `jev-decision-api` before calling Jev. Jev (TypeSafe System One) makes **advisory structured judgments** — noul/choice/score with probabilities and confidence. It is a second opinion, never a gate: deterministic checks (tests, lint, sha/readback) remain the gates per the cost contract above.

Where it fits the v2.2 pipeline (also shown in `scripts/package/HERMES_START_HERE.md` under “Advisory pipeline”):
- **Pre-route (after ROUTE, optional):** one batched call over the task digest — choice on task type sanity, noul on "requires extended reasoning beyond the stated effort", score on ambiguity. A low-confidence or disagreeing answer raises effort one level (log as in `mode.raise_reason`); it never lowers.
- **Failure triage (F1-F5):** on a failed node, one call over the failure digest — choice over the five failure classes; if Jev's class disagrees with the controller's classification, both go to the premium judge / human, not auto-retry.
- **Review pre-screen (RV/PACC input):** one batched call over the diff digest — noul per risk axis (touches auth/secrets/money/PII, behavior change without test, public API change). High-probability hits add to the reviewer's checklist; they do not auto-block.
- **Spec/acceptance audit (E4 items):** score per milestone-contract clause (covered / partially / not), combined in code; uncovered clauses block the item.
Rules: one call per decision point with all questions batched (fan-out); send digests built by code, never raw logs or whole transcripts; pin `jev-1.13.0` once thresholds are tuned; log model id, usage tokens, and the question set in the task receipt; Jev cost (~$42/Btok input, output free) is charged to overhead unless it changes an item outcome. Do not use Jev for code generation, counting, math, date arithmetic, or exact lookups — those stay in code.
Proven: App 162 Overview rebuild (2026-09-20) — Jev pre/post judgment drove and validated a presentation rebuild; receipt in `~/.hermes/tmp/board-org-chart/app162-deploy/`.

## v2.2 migration note (2026-09-08)
Pool/roster availability modes (v2.1) were removed per the operator's decision: mode is rigor only, models come from the tier registry. Old pool definitions are preserved in `policy.json` `modes_changelog.removed_pool_definitions` for rollback. See `scripts/package/MIGRATION.md`.


T14 policy v2.2.3: MAIN/default and H coordination use `gpt-5.6-sol`, provider `openai-codex` (ChatGPT subscription), reasoning `high`. Model-specific dispatch emits all three fields and direct worker `--reasoning high`; Kanban cards inherit profile base effort (medium or restricted-direct none); bare subscription Sol resolves exact high, and four evidenced non-subscription namespaces have exact prior-base counters (create has no reasoning flag). No API key or OpenRouter Sol slug is used. Delegated worker selection, cross-family review, premium gates, delegation limits and fallback chains remain authoritative. Offline plans do not prove account availability or live enforcement.
