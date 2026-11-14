# Hermes OpenRouter secondary profile

Use this pattern when the primary Hermes conversation must remain on its current model while a controllable second agent runs through OpenRouter.

## Architecture

- Keep the primary session/model stable.
- Create an isolated Hermes profile for the secondary agent.
- Keep its gateway stopped unless it has a unique messaging token; profiles sharing one Telegram token cannot poll concurrently.
- Invoke the secondary profile in one-shot mode for isolated work, or resume its session ID for continuity and steering.
- Treat its answer as a proposal; the primary verifies evidence and external side effects.

## Setup sequence

1. Inspect existing profiles and authenticated providers.
2. Create or clone a secondary profile with a role description.
3. Store `OPENROUTER_API_KEY` only in that profile's protected `.env`; set mode `0600`. Never place the key in SKILL.md, config examples, shell history, screenshots, or tool output.
4. Validate the key with OpenRouter's `/api/v1/auth/key` endpoint without printing it.
5. Query `/api/v1/models` live and select by exact model ID, price, context, and `tools`/`tool_choice` support.
6. Configure the profile model.
7. Test an explicit call with `--provider openrouter`.
8. Test the same profile without a provider override. This catches a profile that only works when manually forced.
9. Resume the returned session ID and verify continuity before calling the worker persistent.

## Availability and billing pitfalls

- Model pages and search results can lag reality. A `:free` slug may be retired while a paid slug remains. The live models API is authoritative for current availability.
- HTTP 402 after a valid auth check means billing/credits or the request's maximum-token reservation is insufficient; it does not mean the key is invalid.
- Do not retry paid models repeatedly after 402. Add credits, lower the maximum-token request when supported, or choose a currently listed free model.
- Free model catalogs are volatile. Never hardcode one model as permanent doctrine; re-query before setup and periodically thereafter.
- Verify tool support in `supported_parameters`, not from marketing prose.

## Control pattern

```bash
secondary chat -q "<self-contained task>" --provider openrouter --quiet
secondary --resume <session_id> chat -q "<follow-up>" --provider openrouter --quiet
```

The primary should pass minimum necessary context, include output requirements, and independently verify consequential claims. Keep restricted student, employee, legal, financial, and credential data off third-party routes unless explicitly approved.

## Secret exposure response

If a key was pasted into chat, store it once without echoing it, redact it from logs/output, and recommend rotation. Never preserve the literal key in memory or a skill.
