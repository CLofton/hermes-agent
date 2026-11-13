---
name: grok-collaboration
description: Use when configuring or collaborating across Grok surfaces.
version: 0.3.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [Grok, Collaboration, Multi-Agent]
    related_skills: [hermes-agent]
---

# Grok Collaboration

Use Grok as an independent second agent through distinct surfaces: the official Grok Build CLI (`grok`), a Hermes Grok profile (`hermes -p grok`), Cursor Agent CLI (`agent`), or the Cursor-hosted Grok Bot desktop/cloud product. Do not conflate their authentication, configuration, model defaults, flags, or credential types. Keep collaboration local; do not expose credentials or create a public HTTP bridge.

## When to Use

- the operator asks Hermes and Grok to collaborate, debate, review, or divide work.
- A task benefits from xAI/Grok's independent opinion or X-search access.
- Don't use for routine work where a second paid model adds no value.

## Prerequisites

- Identify the intended surface before dispatch:
  - Official Grok Build CLI: `grok --version`, then `grok models`; require an authenticated result and confirm the requested model is listed.
  - Hermes profile: `hermes profile show grok`; confirm its provider/model, then run an explicit one-shot smoke.
  - Cursor Agent CLI: `agent --version`, `agent status`, then `agent models`; require authenticated status before a one-shot smoke.
  - Grok Bot desktop/cloud: authenticate with the Cursor account in the app; it has no separate Grok Bot login and is not the same surface as either CLI.
- Classify every credential before storing or testing it:
  - An xAI management key is only for xAI Management API operations such as key inventory, validation, ACLs, rotation, and team administration. Never use it as an inference or CLI key.
  - An xAI inference key belongs in `XAI_API_KEY`; Hermes provider `xai` and Grok Build can use it.
  - A Cursor API key belongs in `CURSOR_API_KEY`; it authenticates Cursor Agent CLI and Cursor APIs, not Hermes or Grok Build.
- The requested task contains no context that the operator has prohibited sharing with Grok.

## Procedure

1. Read the current official documentation for the selected surface before setup: Hermes provider docs for a Hermes profile, xAI Build docs for `grok`, and Cursor CLI or Grok Bot docs for Cursor surfaces.
2. Configure secrets without replaying them into command arguments, shell history, agent prompts, or tool logs. Prefer the vendor's login/setup flow. For API-key automation, use a local masked prompt that writes an owner-only file (`0600`), then load that file only inside the target child process rather than globally exporting every credential.
3. Select and verify one surface:
   - Official Grok Build CLI: `grok -m grok-4.6 -p "Reply exactly: GROK_OK"`. Here `-p` means a single prompt.
   - Hermes Grok profile: `hermes -p grok chat -q "Reply exactly: GROK_OK" --provider xai -m grok-4.6 --max-turns 1 --oneshot -Q`.
   - Cursor Agent CLI: after `agent status` and `agent models` pass, run `agent -p "Reply exactly: CURSOR_OK" --mode ask`.
4. If one secured key must serve both Hermes and Grok Build, keep the canonical xAI value in the Hermes profile's protected `.env` and use a shell function or wrapper that sources it in a subshell immediately before executing the real `grok` binary. Verify from a fresh interactive shell; do not copy the key into a second plaintext command or config.
5. Only after the smoke passes, send a self-contained brief with task, necessary context, constraints, evidence requirements, and required output. Pin the model explicitly when model identity matters.
6. Require Grok to cite tool-backed evidence for factual or operational claims.
7. Treat Grok's answer as an independent recommendation, not verified truth.
8. Verify consequential claims or side effects with Hermes tools before reporting success.
9. Reconcile disagreements explicitly; surface the recommended decision, risks, and time sensitivity.

## Pitfalls

- Never infer authentication across surfaces — Hermes, Grok Build, Cursor Agent CLI, and Grok Bot keep separate auth and configuration state even when they ultimately use related accounts.
- Validate any generated shell-integration line in a fresh interactive and non-interactive shell before retaining it; an integration command that blocks during shell startup can make every later smoke appear to hang. Roll back the generated line and keep a narrow wrapper when integration is unnecessary.
- Do not use legacy `grok -z`; current Grok Build uses `-p/--single` for a headless single prompt.
- Treat `grok models` output that says unauthenticated as a failed prerequisite even if it also prints a default model — model discovery is not a successful dispatch.
- Grok knows only the context passed in the prompt plus the selected surface's own memory and tools.
- Never ask both agents to mutate the same files concurrently without separate worktrees.
- Do not include passwords, tokens, or secret values in the command or prompt.
- The shared Hermes Kanban is the preferred durable handoff mechanism when initiated outside a delegated child context.

## Verification

- Record the selected surface, credential class (never the value), provider, explicit model, exit code, and exact smoke marker.
- Verify each configured surface independently; passing Hermes and Grok Build does not prove Cursor Agent CLI or Grok Bot is ready.
- For a model-default upgrade, verify both the stored config and a new one-shot session without `-m`; existing sessions retain their loaded model.
- Any claimed external changes have independent readback verification.
