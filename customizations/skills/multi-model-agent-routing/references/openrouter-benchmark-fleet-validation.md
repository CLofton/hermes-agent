# OpenRouter benchmark-driven fleet validation

Use this procedure when choosing and validating several OpenRouter-backed specialist agents. Rankings and prices are time-sensitive; preserve the API timestamp with every comparison.

## 1. Pull live evidence

Use an authenticated OpenRouter key without printing it.

- `GET https://openrouter.ai/api/v1/benchmarks?source=artificial-analysis&task_type=intelligence&max_results=100`
- Repeat with `task_type=coding` and `task_type=agentic`.
- For design work, query `source=design-arena` with `arena=models` or `arena=agents`; inspect categories rather than one blended rank.
- `GET https://openrouter.ai/api/v1/models` to confirm the deployable model ID, context length, exact pricing, and `supported_parameters` such as `tools`, `tool_choice`, reasoning, and structured output.

Do not configure from a dated benchmark permaslug until it is matched to a currently deployable model ID. Do not select on one score: consider task fit, cost, latency, context, tool support, data sensitivity, and provider reliability.

## 2. Build isolated profiles

Keep the stable primary orchestrator unchanged. Create one profile per durable role, not per temporary task. Examples of role classes: premium reasoner, value worker, adversarial reviewer, design adviser, fast tool worker.

For third-party specialists:

1. Clone only the minimum configuration and skills needed.
2. Replace the profile `.env` with only the OpenRouter key unless another credential is explicitly required.
3. Set mode `0600` on every profile credential file.
4. Keep specialist gateways stopped. Use the main agent as the messaging front door and dispatch workers locally.
5. Across multiple computers, every simultaneously polling Telegram gateway needs a unique bot token.

This sharply limits the impact of a prompt leak or unreliable model.

## 3. Validate capabilities separately

Run two exact-marker smoke tests per model:

1. Text: `Reply with exactly: MODEL_TEXT_OK`.
2. Tool: require one harmless real tool call, such as terminal `printf MODEL_TOOL_OK`, followed by the exact same final marker.

Pass only when the expected marker is present. A process exit code of zero is insufficient: some models emit malformed control tokens or end without a usable answer. If text passes and tool use fails, retain the model only as an advisory/draft worker; the orchestrator or a verified executor performs all actions.

Also test the profile's default provider route, not only an explicit `--provider openrouter` invocation.

## 4. Prove concurrency

Dispatch independent, self-contained prompts to all profiles in one parallel batch. Record:

- requested agent count,
- completed count,
- peak concurrent count actually launched,
- failures or malformed outputs,
- wall time and cost when available.

A good demonstration gives each model a distinct role on the same challenge, then has the primary orchestrator reconcile contradictions and verify the deliverable. The durable operating rule is:

> Parallelize research, ideation, critique, and read-only analysis. Serialize writes to the same file, branch, CRM, or production system.

## 5. Promotion policy

Promote a route only after representative tasks pass, not after a novelty demo. Run automatic routing in shadow/manual mode first. Keep a manual premium override and an advisory-only flag. Re-fetch live benchmarks before changing permanent route assignments.
