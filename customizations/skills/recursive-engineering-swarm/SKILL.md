---
name: recursive-engineering-swarm
description: Automate atomic, feature, and app engineering swarms.
version: 0.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [engineering, swarm, kanban, tdd, openrouter]
    related_skills: [multi-model-agent-routing, openrouter-agent-fleet, kanban-orchestrator]
---

# Recursive Engineering Swarm

For new engineering work, load `engineering-swarm-v2` first: the operator designated the supplied effort-by-task package as the controlling cost-routing policy. This legacy runner is not the complete v2 controller and must not be used to justify Astra conducting routine implementation or verification loops. Preserve existing graph recovery/certification, but classify its routing compatibility before creating new work.

Create a deterministic, dependency-gated Hermes Kanban graph spanning atomic units, feature integration, and whole-app certification. GPT-5.6 Terra coordinates; GPT-6 Astra is pinned for critical contracts, governed recovery, and final certification; Qwen specifies/reviews; DeepSeek writes RED tests; GLM is the sole implementation profile. V3 adds compact task-type/effort routing and policy-bound gates without weakening the original graph/apply/certify invariants.

## When to Use

- Use for a real software feature or application with an approved controlling goal.
- Use when work should survive restarts and expose a durable board audit trail.
- Do not use for one-file trivial changes or restricted/secret material routed through OpenRouter.

## Prerequisites

- Profiles `default`, `qwen`, `deepseek`, and `glmvalue` exist and have passed text/tool smoke tests.
- Optional profiles: `grokreview` for read-only adversarial review and `opus47` for F3 recovery escalation only after the configured threshold.
- Hermes Kanban is initialized and its gateway dispatcher is healthy.
- The target repository is clean or intentionally isolated before `apply`.

## How to Run

Use `terminal` with the deterministic CLI:

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/recursive-engineering-swarm/scripts/recursive_swarm.py route \
  --task-file /absolute/task.json

python3 ~/.hermes/skills/autonomous-ai-agents/recursive-engineering-swarm/scripts/recursive_swarm.py draft \
  --app-id example-app --goal "Build the approved feature" --repo /absolute/repo \
  --task-file /absolute/task.json --output /absolute/plan.json

python3 ~/.hermes/skills/autonomous-ai-agents/recursive-engineering-swarm/scripts/recursive_swarm.py plan \
  --plan-file /absolute/plan.json

python3 ~/.hermes/skills/autonomous-ai-agents/recursive-engineering-swarm/scripts/recursive_swarm.py apply \
  --plan-file /absolute/plan.json --board example-app --apply --dispatch

python3 ~/.hermes/skills/autonomous-ai-agents/recursive-engineering-swarm/scripts/recursive_swarm.py certify \
  --manifest /absolute/plan.swarm.json
```

`route` is dry-run and emits deterministic JSON only. It accepts task types `T1`-`T14`, effort `E0`-`E4`, modifiers `E/P/G/H/V`, public/internal sensitivity, and finite ceilings for task count, runtime, retries, and USD. It emits argv arrays only, never shell command strings. `plan` is dry-run and never changes Kanban. `apply` is the only board-writing command.

For a one-command start, use `launch` with the same values plus `--task-file TASK.json`. It routes and binds the v3 policy, drafts through Astra, creates the complete dependency graph behind a blocked conductor root, opens the root only after every card exists, and dispatches the first eligible work. Critical routes end at fresh Astra acceptance; routes carrying `H` end at a blocked manual approval gate that cannot auto-dispatch.

## Procedure

1. Preflight the repository, active workers, branches/worktrees, open PRs, and existing board. Completion: one canonical writer target is identified.
2. Run `route` for v3 work, then pass the same task with `draft --task-file TASK.json` (or `launch --task-file TASK.json`) so the route is cryptographically bound into the v3 plan. Completion: every feature has at least one atomic unit, explicit acceptance criteria, and v3 plans carry `policy_version` plus route metadata.
3. Run `plan` and inspect node count, route metadata, roles, dependency edges, sensitivity, and canonical writer chain. Completion: dry-run returns a stable graph with no side effects.
4. Run `apply --apply --dispatch`. Completion: idempotent Kanban cards exist and only root-ready work dispatches.
5. Monitor blocked cards. Goal-mode completion judges enforce the card contract; Qwen/Astra reviewers must block instead of completing on FAIL or NOT YET PROVEN.
6. Run `certify` against the generated `.swarm.json` manifest. Completion: every task is done and required RED, GREEN, review, and judge metadata validates deterministically.
7. Release only after `certify` returns PASS, the final Astra app judge passes, and deterministic CI/deployment/readback gates pass.

## Invariants

- Qwen unit specifications may pipeline ahead read-only.
- DeepSeek test mutation and GLM implementation mutation form one total writer chain in the canonical repository.
- Every build waits on RED evidence from its test parent.
- Feature work waits on the complete app-wide atomic/base layer; app work waits on all feature reviews.
- Idempotency keys derive from plan hash plus stable node ID. In v3, task input, route decision, and policy version are part of the plan hash, so changed routing inputs produce new idempotency keys.
- Dispatcher retries only the failed card; passed siblings remain preserved.
- `restricted` and `secret` plans are rejected before any OpenRouter dispatch.
- Critical flags (`critical`, `payments`, `secrets`, `destructive`, `pii`) require Astra contract and final acceptance gates. Astra is the premium judge; do not substitute Sol.
- `prod`, `destructive`, and `external-writes` require an exact-plan manual approval card downstream of final review/acceptance, born blocked and not goal-dispatched.
- Grok 4.20 review is optional, read-only, public/internal only, and enabled only by policy/modifier routing. Opus 4.7 is recovery-only after F3 implementation shortfalls reach the route threshold.

## Pitfalls

- A Kanban `done` status alone does not prove PASS. `certify` fails closed when required evidence metadata is absent or invalid.
- Model task summaries are proposals. CI, hashes, security scans, and production readback remain deterministic gates.
- Shared repository writes are serialized; do not assign another implementation profile without redesigning the writer chain.
- USD ceilings are routing ceilings, not spending authority. This workflow also enforces task-count, runtime, turn, and retry ceilings; inspect usage receipts before increasing limits.

## Verification

Run:

```bash
python3 ~/.hermes/skills/autonomous-ai-agents/recursive-engineering-swarm/scripts/test_recursive_swarm.py
```

PASS requires all unit tests, an isolated-HERMES_HOME Kanban smoke test, profile readback, and a dry-run/apply idempotency check.
