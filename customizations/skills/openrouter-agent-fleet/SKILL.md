---
name: openrouter-agent-fleet
description: Use when the operator says "use the swarm." Activate all five OpenRouter agents on a visible Kanban swarm.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [openrouter, multi-model, agents, routing]
    related_skills: [hermes-agent, multi-model-agent-routing, task-model-router]
---

# OpenRouter Agent Fleet

Use a stable GPT-5.6-Sol primary orchestrator and dispatch isolated, minimized briefs to specialist Hermes profiles. Do not hot-swap the primary conversation.

## Exact trigger contract

When the operator says **"use the swarm"** or **"use swarm"** in any Main-Hermes chat, treat that as an explicit request to activate **all five** OpenRouter specialist profiles for the task in the same message. Do not ask which agents to use and do not silently use only a subset.

Create a durable, visible Kanban swarm so the operator can watch every profile work at `http://127.0.0.1:9119/kanban` on his main Mac:

```bash
hermes kanban swarm "<self-contained goal and context>" \
  --worker secondary:"Opus lead analysis" \
  --worker glmvalue:"GLM evidence and detail" \
  --worker grokreview:"Grok adversarial review" \
  --worker kimidesign:"Kimi design and usability" \
  --worker geminifast:"Gemini fast execution and tests" \
  --verifier grokreview \
  --synthesizer secondary \
  --tenant openrouter-swarm \
  --created-by default \
  --json
hermes kanban dispatch --max 5
```

The five parallel worker cards are mandatory. Grok then verifies the combined work and Opus synthesizes the final result; those downstream cards reuse two of the same five profiles, not additional agents. Main-Hermes remains the user-facing orchestrator and must verify any factual claims, calculations, code/tests, or external side effects before reporting completion.

If the local dashboard is not running, start it locally with `hermes dashboard --no-open` and verify `http://127.0.0.1:9119/kanban` responds. Never bind it publicly just to provide remote visibility.

## Routes

- `code-default` → profile `luna` → `openai/gpt-5.6-luna`: Tier-1 code writing, editing, refactoring, and review.
- `step-up` → profile `sonnet` → `anthropic/claude-sonnet-5`: Tier-2 production code, real specs, most internal writing, and judgment-heavy analysis.
- `premium` → profile `secondary` → `anthropic/claude-opus-5`: Tier-3 architecture, complex refactors/debugging, high-stakes specs, board/external writing, and hard cross-source synthesis.
- `value` → profile `glmvalue` → `z-ai/glm-5.3-flash`: routine extraction, long-context work, parallel tool tasks; best cost/performance default worker.
- `test-logic` → profile `deepseek` → `deepseek/deepseek-v4-flash`: low-cost executable test design, code logic, debugging, and security edge cases. Text and real terminal-tool calls are verified.
- `architecture` → profile `qwen` → `qwen/qwen3.8-27b`: independent specifications, architecture, integration contracts, and feature/app-level review. Text and real terminal-tool calls are verified.
- `review` → profile `grokreview` → `x-ai/grok-4.6`: contrarian critique, strategy challenge, second opinion.
- `design` → profile `kimidesign` → `moonshotai/kimi-k3`: UI/full-stack concepts and design drafts. Text generation is verified; its Hermes tool-call smoke test was not clean, so treat it as an advisory worker and have the primary or Codex execute changes.
- `fast` → profile `geminifast` → `google/gemini-3.7-flash`: fast, inexpensive coding/tool work.
- `live-research` → profile `perplexity` → direct Perplexity `sonar-pro`: current-web research with citations. Use `sonar-deep-research` only for explicitly deep, high-latency investigations.

## Perplexity special-case lane

The normal swarm remains the mandatory five OpenRouter workers. Add Perplexity as a supplemental sixth worker only when the task materially depends on current external web evidence, vendor/pricing reconnaissance, public regulatory rules, or citation-heavy fact checking:

```bash
hermes kanban swarm "<self-contained, non-sensitive goal and context>" \
  --worker secondary:"Opus lead analysis" \
  --worker glmvalue:"GLM evidence and detail" \
  --worker grokreview:"Grok adversarial review" \
  --worker kimidesign:"Kimi design and usability" \
  --worker geminifast:"Gemini fast execution and tests" \
  --worker perplexity:"Perplexity live-web research with source URLs" \
  --verifier grokreview \
  --synthesizer secondary \
  --tenant openrouter-swarm \
  --created-by default \
  --json
```

Do not send student/employee PII, legal files, payment details, private company data, credentials, or privileged material to Perplexity. Give it a minimized public-information brief, and treat its citations as leads that Main-Hermes verifies before use.

Direct smoke/invocation:

```bash
hermes --profile perplexity chat -q "<public live-web research task>"
hermes --profile perplexity chat -m sonar-deep-research -q "<explicit deep-research task>"
```

## Command

```bash
# Fixed role routes (10 named roles)
python3 ~/.hermes/skills/autonomous-ai-agents/openrouter-agent-fleet/scripts/fleet.py --list
python3 ~/.hermes/skills/autonomous-ai-agents/openrouter-agent-fleet/scripts/fleet.py --role value "<self-contained task>"

# ANY of the full OpenRouter catalog (437 models) — discovered 2026-09-11
python3 .../fleet.py --catalog                 # stats
python3 .../fleet.py --search "<id or name>"   # find a model, returns price + context
python3 .../fleet.py --model "provider/slug" --profile <p> "<task>"   # dispatch any model
```

## Full OpenRouter catalog (all models dispatchable)

`scripts/openrouter-catalog.json` is a discovery snapshot with model IDs, prices, context limits, and modalities. It complements the hand-verified tier registry in the engineering-swarm policy; it does not re-tier models or prove that a route is currently available.

- Refresh it from `https://openrouter.ai/api/v1/models` before changing permanent routes, then keep the controlling package and profile copies byte-identical.
- `--model` prints the snapshot price and dispatches an exact model ID through OpenRouter. Treat that output as planning data until a live canary completes on the same profile, provider, tool restriction, and model ID.
- Re-read live model metadata immediately before every bulk launch. A `:free` suffix does not guarantee current availability or usable quota; free routes can be withdrawn or rate-limited while the local snapshot remains valid JSON.
- For exact-count bulk work, prefer a cheap open-weight paid route with an explicit live input/output price ceiling when free-route instability would risk an ambiguous partial population. Estimate cost from the frozen prompt size, but state that client-side estimates are not provider-enforced caps.
- On 404/429 or a changed price, preserve completed identities and canary a different exact route. Never silently remove `:free`, switch to a paid slug, or relabel the replacement as the same model.

## Evidence-heavy and production-surface swarms

For a large investigation or public production-app audit, separate evidence collection from model fan-out:

1. Collect once through an approved bounded route, then reduce the result to a frozen sanitized bundle with stable evidence IDs, hashes, scope, omissions, and redacted token/cookie/header values. Never make every worker independently retrieve the live surface or raw HR, legal, finance, student, payment, or private source records; correlated traffic and inconsistent snapshots defeat both safety and reconciliation.
2. For production read-only testing, let deterministic probes perform the bounded HTTP/browser work and give model workers only the frozen bundle. Do not expose browser, web, terminal, file-write, form, account, messaging, or load-generation tools to analysis-only workers.
3. Prove isolation with a canary on the exact operational route. A reliable Hermes one-shot shape is `hermes --profile <profile> chat -q '<bounded prompt>' --quiet -m <exact-model> -t skills --safe-mode --max-turns 1 --source tool`. `--safe-mode` removes the profile default, so always pass `-m`; `-t none` is not a valid empty-toolset substitute. Read the resulting session and require the expected model metadata, exactly the user/assistant exchange, and zero tool calls before fan-out.
4. When even a skills-only schema is unnecessary, prefer a text-only provider adapter that sends `tools: []`, `tool_choice: none`, one completion, no streaming, and no automatic fallback. Mark an identity durably before any possibly sent request; an ambiguous post-dispatch failure must block that identity rather than trigger a duplicate invocation.
5. Canary every model family and provider path before assigning work. Authentication or a stale catalog entry does not prove current capacity. Run wide work in conservative batches, freeze one prompt/input hash per identity, and persist attempt logs plus one receipt per successful independent invocation.
6. For research lanes that write artifacts, require artifact-first execution: write the schema-valid skeleton after loading assigned IDs, checkpoint completed items during retrieval, and reserve the final third of the turn budget for file completion and readback. If a worker exhausts turns after producing a complete draft only in its transcript, resume that same session with an artifact-only instruction; do not repeat the research.
7. Treat Kanban deployment as unproven until a canary completes through the same owner-admission path. If owner admission fails, block/reclaim those cards and switch to a durable direct-profile controller with disjoint output files and a persisted manifest; do not keep respawning the same broken control path.
8. Accept a nonzero worker exit only when the parent validates the required artifact's exact ID coverage, schema, and evidence rules. The exit code is an execution signal, not the deliverable; deterministic probes and parent synthesis never fill missing agent seats.

## Rules

1. Keep Main-Hermes as the only front-door Telegram bot. Do not start specialist gateways; their gateways remain stopped to avoid duplicate polling and fragmented memory.
2. Minimize context. Never send credentials, student/employee PII, legal matters, payment details, or other restricted records through OpenRouter profiles.
3. Use `premium` for high-stakes work; `value` for bulk routine work; `review` for adversarial challenge; `design` for drafts; `fast` for low-latency execution.
4. Specialist output is a proposal. Primary Hermes verifies facts, calculations, code/tests, and external side effects.
5. For repository edits, prefer Codex/worktrees over multiple profiles editing the same files.
6. Model rankings change. Refresh `~/.hermes/data/openrouter-benchmarks.json` with `~/.hermes/scripts/fetch_openrouter_benchmarks.py` before changing permanent routes.
7. Other Macs can run the same profile layout, but control each through its existing Hermes Telegram gateway; never reuse one Telegram token across simultaneously polling gateways.
8. For the recursive engineering workflow, use DeepSeek at atomic test/logic nodes and Qwen at feature/app integration nodes. Keep both explicit/manual until representative project evaluations pass; do not silently replace the established default routes from one smoke test.
