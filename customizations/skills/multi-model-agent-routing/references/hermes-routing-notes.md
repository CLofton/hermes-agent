# Hermes multi-model routing notes

Validated against Hermes documentation and a live installation review on 2026-08-26. Re-check current docs and installed source before changing configuration; model catalogs and routing features evolve quickly.

## Capability map

| Capability | Purpose | Do not confuse with |
|---|---|---|
| Main model | Runs the conversation and tool loop | Automatic per-prompt model selection |
| Auxiliary models | Fixed task-specific slots such as vision, compression, title generation, MCP helpers, review, and web extraction | Main-agent routing |
| Fallback providers | Fail over when the primary route errors or lacks capacity | Choosing a better model for the task |
| Provider routing | Chooses a serving provider behind OpenRouter/Nous Portal, often by price/latency/throughput | Choosing a different model family |
| Model aliases and `/model --once` | Manual model selection or one-turn escalation | Automatic routing |
| Delegation / one-shot workers | Isolated specialist model execution | Mid-session main-model swapping |
| Mixture of Agents | Parallel reference models plus aggregator | Cheap default processing |
| Custom OpenAI-compatible endpoint | Lets an external router sit in front of Hermes | Native Hermes routing policy |

## Current authoritative documentation

- Configuring models: https://hermes-agent.nousresearch.com/docs/user-guide/configuring-models
- Configuration reference: https://hermes-agent.nousresearch.com/docs/user-guide/configuration
- Provider integrations: https://hermes-agent.nousresearch.com/docs/integrations/providers
- Provider routing: https://hermes-agent.nousresearch.com/docs/user-guide/features/provider-routing
- Fallback providers: https://hermes-agent.nousresearch.com/docs/user-guide/features/fallback-providers
- CLI commands and MoA: https://hermes-agent.nousresearch.com/docs/reference/cli-commands

Treat these URLs as pointers, not frozen truth. Fetch them live.

## Live validation commands

```bash
hermes --version
hermes config
hermes config check
hermes config get model --json
hermes config get auxiliary --json
hermes config get delegation --json
hermes config get fallback_providers --json
hermes config get smart_model_routing --json
hermes model --help
```

If a routing key is questionable, search the installed source for runtime reads—not just setup/migration writers or tests. A key that appears only in setup code is not evidence of active behavior.

## Findings worth preserving

- Hermes explicitly distinguishes one main model from auxiliary task slots.
- Mid-session model changes reset prompt caching; one-turn switches can break the cache both when switching out and when restoring.
- New sessions read persisted model configuration; already-running sessions retain their model unless explicitly switched.
- Fallback chains preserve availability but do not classify task fitness.
- OpenRouter/Nous Portal provider-routing options optimize serving providers by price, latency, or throughput for a selected model.
- Mixture-of-Agents presets provide deliberate multi-model synthesis for selected prompts.
- An OpenAI-compatible local proxy can perform prompt-level routing. The Hermes docs currently mention ClawRouter, which classifies query complexity and routes via BlockRun. It requires a funded USDC wallet and sends requests through BlockRun’s backend, so privacy review is mandatory.

## Recommended validation sequence

1. Update Hermes separately from routing changes; verify normal sessions first.
2. Configure and test each provider individually.
3. Assign low-risk auxiliary slots.
4. Add fallback providers and force a test failure.
5. Add isolated specialist workers.
6. Evaluate MoA on a small high-stakes benchmark.
7. Shadow-test any automatic router before enabling dispatch.
8. Confirm sensitive-data routes remain on approved providers.

## Session-specific example architecture

A chief-of-staff agent can keep a stable strong orchestrator while using:

- a fast model for compression, titles, extraction, and MCP selection;
- a writing/reasoning specialist for document judgment and adversarial review;
- a coding specialist in an isolated worker;
- MoA only for consequential strategy or ambiguous decisions;
- direct-provider allowlists for employee, student, finance, legal, and investor information.

The durable lesson is architectural: preserve a stable parent and route specialist work outward instead of repeatedly hot-swapping the parent model.
