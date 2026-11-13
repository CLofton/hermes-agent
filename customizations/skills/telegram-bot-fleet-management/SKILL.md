---
name: telegram-bot-fleet-management
description: Use when securely managing a fleet of Telegram bots.
version: 1.0.0
author: Hermes Curator
license: MIT
metadata:
  hermes:
    tags: [telegram, botfather, bot-api, fleet, credentials, gateway]
    category: autonomous-ai-agents
    related_skills: [hermes-agent, macos-computer-use]
---

# Telegram Bot Fleet Management

Securely inventory and operate multiple Telegram bots owned by one user. This covers BotFather discovery, token acquisition, validation, local storage, health checks, and routing bots to distinct agent profiles.

## When to use

- The user asks to control all of their Telegram bots.
- Several bots exist but only one token is configured in Hermes.
- Multiple Hermes profiles accidentally share one bot token.
- A bot fleet needs health checks, command menus, message routing, or gateway assignments.
- The user wants a local agent such as Grok connected to or kept separate from Telegram.

## Core distinctions

1. A Telegram bot token controls one bot identity; it does not grant access to the user's personal Telegram account.
2. A bot can only see chats it has joined and updates Telegram delivers under its privacy/admin settings.
3. Bots cannot use BotFather to retrieve other bots' credentials. BotFather management requires the owner's personal Telegram session.
4. A local model profile or desktop agent is not a Telegram bot unless explicitly wired to a unique bot token.
5. Two polling gateways cannot safely share one token; Telegram will produce competing `getUpdates` consumers.
6. A forwarded contact card or phone number is not a Telegram authorization identity; the bot must receive a DM from that account to learn its numeric user ID.

## Pair an additional phone or account to an existing gateway

1. Confirm the request is to authorize another Telegram account on the existing bot, not create another bot/profile. Preserve the existing bot token, approved users and home channel.
2. Do not add a phone number or contact-card value to `TELEGRAM_ALLOWED_USERS`; Telegram gateway authorization uses the sender's numeric Telegram user ID, and adapters may discard contact-card fields.
3. Ask the new account to open the exact existing bot username and send `/start`. Telegram authorization uses the sender's numeric user ID, so a public `t.me/<username>` page is not sufficient evidence.
4. Check `hermes pairing list`. If DM pairing is active, match and approve only the exact pending account. If `TELEGRAM_ALLOWED_USERS` is already set, the adapter may block the unknown sender before creating a pairing record; inspect only recent gateway authorization lines for the blocked numeric user ID rather than waiting for a code that cannot appear.
5. Validate that numeric ID against the configured bot with Bot API `getChat`, performed locally without printing the token, and require the returned username to match the requested account exactly. Never infer identity from a display name or from timing alone.
6. Add the validated numeric ID while preserving every existing approved user. Back up the credential file, write atomically, keep mode `0600`, and obtain explicit approval before any gateway restart that could interrupt active turns.
7. After reload, require one fresh inbound message from the new account and one successful bot reply through the supervised gateway. A config write, pairing code, process PID, or restart alone is not a verified connection.
8. Keep the original account authorized unless the user explicitly asks to replace it.

## Safe inventory workflow

1. Check existing profile configs by token fingerprint, never by printing tokens. Treat a token in a profile `.env` as an operational profile assignment, not proof that the gateway is presently healthy.
2. Check the owner-only bot credential registry by fingerprint and exact username. Classify every identity as **profile-assigned**, **stored/unassigned**, or **BotFather-only**; a cached identity is not an active Hermes bot.
3. Validate configured bots with Bot API `getMe` and inspect `getWebhookInfo`. Resolve aliases and nicknames to the exact returned `@username`; never infer that similarly named bots or profiles are the same identity.
4. For a request that only asks for usernames or links, do not retrieve or expose tokens. Return clickable `https://t.me/<username>` links, separate active/profile-assigned bots from stored identities, and state the exact count and inventory source.
5. Do not label a local registry list as “all bots.” If the owner asks for all BotFather bots, use their authenticated Telegram Desktop session and `/mybots` or `/token` to enumerate identities; only that owner-session inventory supports a BotFather-complete claim.
6. Retrieve each token only when validation or configuration requires it, without transcribing it into model-visible output.
7. Validate each retrieved token with `getMe` and require the returned username to match the selected BotFather bot.
8. Store the fleet in one owner-only credential inventory (`0600`) or separate profile `.env` files.
9. Delete temporary screenshots, OCR files, clipboard contents, and debug artifacts containing credentials.
10. For a complete fleet audit, re-run `getMe` for every stored bot and verify the validated identity set equals the BotFather identity set. Report missing, extra, inactive, and unassigned identities separately rather than collapsing them into one status.

## Multiple specialist identities

When the operator asks for several Telegram “channels” so he can talk to multiple versions of Hermes, treat the request as distinct **bot identities backed by distinct Hermes profiles**, not merely several chats with one bot. If he does not name a count, default to five useful roles: strategy, builder, research, reviewer and creative; present the mapping and let him override it before BotFather creation when he is available.

1. Inventory existing bot-token fingerprints and profile names first. Preserve the main front-door bot and any established specialist bot.
2. Create role profiles with `hermes profile create <name> --clone-from <source> --description '…'` and never pass `--clone-channels`; the command deliberately leaves messaging tokens behind so polling consumers cannot collide.
3. Add the role identity to each profile's existing `SOUL.md` without replacing its privacy, approval, model-routing or release rules. A specialist role narrows emphasis; it never widens permissions.
4. Verify each profile before requesting Telegram credentials: `hermes profile show <name>` plus a fresh one-shot that returns a role-specific marker. Profile creation is not bot readiness.
5. Choose exact BotFather usernames up front. The owner must create or select those bots in the personal BotFather session; bots and the Bot API cannot create other bot identities.
6. Accept tokens only through a local masked prompt or protected setup UI—never chat, argv, logs, screenshots or a handoff file. Prevalidate every token with `getMe`, require an exact username match, reject duplicate full SHA-256 fingerprints against the entire profile fleet, and perform all validation before the first write.
7. Update only `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, `TELEGRAM_HOME_CHANNEL` and `TELEGRAM_HOME_CHANNEL_NAME` in each destination `.env`; preserve unrelated bytes, create owner-only backups, write atomically, chmod `0600`, and roll back handled partial failures.
8. Let the multiplexed gateway connect the new profiles only after unique tokens are stored. Verify unique fingerprints, `getMe`, webhook/polling state, gateway assignment and one real the operator↔bot round trip for every identity before calling the fleet ready.

Use `references/specialist-profile-bootstrap.md` for the role matrix, commands, secure token-entry contract and verification checklist.

## macOS BotFather UI technique

Telegram Desktop uses custom-rendered controls that may not appear in the accessibility tree. A validated fallback is:

- Raise the Telegram window with `AXRaise` and make it frontmost.
- Send `/token`; its picker shows the full bot fleet and exact usernames.
- Capture a local screenshot and use macOS Vision OCR only to locate button bounding boxes.
- Click via CoreGraphics after converting Retina screenshot pixels to logical points.
- On the token code block, open the context menu and select **Copy Code**. Clipboard copy is materially safer and more accurate than OCR-transcribing credentials.
- Read the clipboard inside a local script, validate with `getMe`, store securely, then immediately clear the clipboard.
- Never return OCR text or screenshots containing tokens to the conversation.

Details and failure-resistant steps are in `references/botfather-macos-token-capture.md`.

For restoring an existing but silent bot, including safe handling of queued stale commands before polling starts, follow `references/dormant-bot-recovery.md`.

## Fleet health contract

For each bot report only non-secret metadata:

- username and numeric bot ID
- display name
- `getMe` success/failure
- webhook configured or polling expected
- pending update count
- token fingerprint (short SHA-256 prefix), never the token
- assigned profile/gateway

A fleet is ready only when every token validates, usernames are unique, credential-file mode is `0600`, and temporary secret artifacts are gone.

## Operating guardrails

- Do not send messages, edit commands, delete messages, change privacy, rotate tokens, or alter webhooks without explicit user authorization for that action.
- Never paste tokens into chat, skills, memory, source control, command output, or shared documents.
- If a token appears in a screenshot or chat, recommend rotation after the new local configuration is ready.
- Before starting several gateways, assign one unique token per profile and verify no duplicate fingerprints.
- Keep a single front-door bot plus local specialist dispatch as the default architecture; create separate public identities only when operationally necessary.

## Remote-agent assistance preference and controls

the operator prefers direct operation of his remote bot hosts through Tailscale. When access is blocked, he wants a versioned, credential-free file he can forward to the receiving agent to complete setup, rather than only chat instructions.

- Discover live peers and verify which host owns the intended bot before connection or credential transfer; a similar device nickname is insufficient.
- Distinguish tailnet reachability, SSH reachability, authenticated access, gateway restoration and a real Telegram round trip. A ping proves only reachability; an SSH timeout does not prove Remote Login is disabled.
- When a Tailscale ping succeeds but SSH times out, report the exact unblock step (enable Remote Login on the target) and stop — do not retry-loop and do not fall back to sending credentials through chat.
- Scope the credential set to the named workflow before transferring anything (e.g. a model-routing swarm needs only `OPENROUTER_API_KEY`; business-system and bot tokens are out of scope). "Share the keys" means the minimum set the workflow requires — confirm the scope, not the values.
- When asked to "share the skill/file with everyone" and the claimed artifact is not on this machine, verify the file actually exists locally (disk search + session history) before acting — another agent's "saved and verified" claim is not evidence. Reconstruct or ask rather than fabricating the file.
- Include restricted Remote Login, destination OS username, approved public-key authentication, independent host-fingerprint verification, rollback and exact readback criteria in the handoff file. Do not include passwords, API keys or bot tokens.
- Request credential names, purpose, minimum scopes and receiving host/account/path in shared agent chats, never secret values. Telegram bot-to-bot mentions may not arrive; ask the operator to relay rather than treating silence as a response.
- Transfer only specifically authorized credentials over authenticated, identity-verified access. Never disable host-key checks, send the entire bot inventory, copy complete subscription auth stores, enable public tunnels or grant passwordless sudo to accelerate recovery.
- Report remote control as blocked until authentication succeeds. A generated file, posted request or reachable peer is not verified operating access.

## Group file delivery and multi-profile sync

Recipe for delivering a spec/package to a Telegram group via the Bot API (token-safe), and for syncing a skill into every local Hermes profile with hash verification. Details in `references/bot-api-group-file-delivery.md`.

## Routing a task to a specific named bot (via Kanban)

When the operator says "assign X to <bot>" and the bot is one of his fleet Telegram bots, that bot is a specific Hermes profile's gateway. Route the work through the shared Kanban, not by messaging the bot in a chat.

1. **Map bot → profile.** A named bot is whichever profile's `.env` holds a `TELEGRAM_BOT_TOKEN`. Find it: `grep -l 'TELEGRAM_BOT_TOKEN=' ~/.hermes/profiles/*/.env`. Do NOT guess from the bot's display name, and do NOT burn a call on `getMe` for identity — the token's presence in a profile's `.env` IS the operational mapping, and `getMe` can stall on a consent gate. Use `getMe` only when you must verify the live identity and the gate allows it.
2. **Write the handoff brief** to `~/.hermes/profiles/<profile>/handoffs/<slug>.md`. Make it self-contained: goal, exact contacts/payloads, the hard gates (approval-before-send, quiet hours, no-promise/no-overclaim rules), safety boundaries, and a definition of done. Carry the gates inline — the bot cannot see the current conversation, so anything not in the brief is gone.
3. **Create the Kanban card** assigned to that profile: `hermes kanban create "<title>" --assignee <profile> --body "<one-paragraph summary + absolute path to the brief>"`.
4. **Dispatch:** run `hermes kanban dispatch --dry-run --max 1` first to confirm the right card would spawn, then the real `hermes kanban dispatch --max 1`. Verify with `hermes kanban show <id>` that status is `running`.
5. Report the card id + running status; the bot reports results back through Telegram.

A Kanban card assigned to the owning profile, with the brief in its `handoffs/` dir, is the durable, auditable handoff. A one-off chat message to the bot is neither — do not use it as the assignment.

## New-bot routing inheritance

When the operator creates another bot, consult the approved shared-memory routing preference `mem-4471928ca89727dd88ef49bc527574ec` (source: the operator's direct request, 2026-10-16). Preserve the new bot's identity and existing text, and append the approved MODEL ROUTING RULES through normal protected-file controls. Writing uses Claude Code then voice review; coding/scripts/data/terminal uses Codex; browser/desktop keeps native tools; CLI failure falls back to the bot with disclosure. Requested CLI defaults are `claude-opus-5-5` and `gpt-6.1-sol`; verify current account availability. Keep all privacy, approval and release gates. Updated-profile clones inherit the block; a shared-memory record alone does not automatically configure an arbitrary blank or remote bot. Never grant restricted profiles additional tools or memory access merely to satisfy routing.

## Recommended architecture

```text
User → Main Telegram bot → stable Hermes orchestrator
                         ├─ local Grok specialist
                         ├─ OpenRouter secondary profile
                         ├─ coding/research specialists
                         └─ verified response back through Main bot
```

This avoids polling conflicts, fragmented memory, and unnecessary bot sprawl while preserving the option to dedicate unique bots to special audiences.
