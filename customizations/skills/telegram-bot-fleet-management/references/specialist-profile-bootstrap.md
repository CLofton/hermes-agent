# Specialist Telegram profile bootstrap

Use this recipe when one owner wants several simultaneous Hermes conversations with genuinely different roles or model families.

## Architecture decision

- Separate conversation only, same behavior: one bot in multiple chats may be enough.
- Separate role/model/memory and simultaneous direct messages: use one Hermes profile **and one unique Telegram bot token per identity**.
- Never attach one polling token to two profiles. Competing `getUpdates` consumers make delivery nondeterministic.

A balanced five-role default:

| Role | Purpose | Good source profile shape |
|---|---|---|
| Strategy | Decisions, architecture, operating models | reasoning/spec profile |
| Builder | Code, models, dashboards, verified artifacts | main engineering profile |
| Research | Primary-source research and evidence briefs | research profile |
| Reviewer | Independent adversarial QA and risk | different model family from builder |
| Creative | Campaigns, visual/product concepts | creative/design profile |

Keep the front-door bot separate from these specialists.

## 1. Inventory without exposing credentials

Enumerate profile `.env` files locally. For each nonempty `TELEGRAM_BOT_TOKEN`, compute only a short SHA-256 fingerprint and record profile, file mode and whether the token is present. Never print the token. Abort if two existing profiles already share a fingerprint.

## 2. Create profiles without messaging channels

```bash
hermes profile create telegram-strategy --clone-from <strategy-source> \
  --description 'Strategic planning, architecture, and executive decision support.'
hermes profile create telegram-builder --clone-from <builder-source> \
  --description 'Hands-on execution, coding, analysis, and artifact delivery.'
hermes profile create telegram-research --clone-from <research-source> \
  --description 'Deep research, source synthesis, and evidence-backed briefs.'
hermes profile create telegram-reviewer --clone-from <review-source> \
  --description 'Independent critique, risk review, and adversarial quality control.'
hermes profile create telegram-creative --clone-from <creative-source> \
  --description 'Creative concepts, visual direction, campaigns, and product ideation.'
```

Do not use `--clone-channels`. Read back each profile with `hermes profile show` and run a fresh exact-marker one-shot on every profile before moving to Telegram setup.

## 3. Define BotFather identities

Choose exact display names and usernames before creation. BotFather work belongs to the owner's personal Telegram session. If any username is unavailable, revise the approved mapping before token installation; do not silently bind a near-match because later identity validation should fail closed.

## 4. Secure local token-entry contract

Use one local interactive configurator with hidden `getpass` prompts. It must:

1. Reject token-looking argv and never accept tokens from chat or environment variables.
2. Read all existing fleet fingerprints without logging credential values.
3. Collect and validate all proposed tokens with Telegram `getMe` before writing any file.
4. Require exact expected username, `is_bot=true` and a positive numeric bot ID.
5. Reject duplicate full fingerprints among new tokens and existing fleet tokens.
6. Snapshot every destination `.env`, create owner-only timestamped backups, stage all replacements, recheck snapshots, then atomically replace files.
7. Update only:

```dotenv
TELEGRAM_BOT_TOKEN=<hidden validated token>
TELEGRAM_ALLOWED_USERS=<the operator Telegram user ID>
TELEGRAM_HOME_CHANNEL=<the operator Telegram user ID>
TELEGRAM_HOME_CHANNEL_NAME=the operator
```

8. Preserve unrelated comments, assignments and multiline values; chmod final files `0600`.
9. Roll back completed replacements after handled failure or interruption. Document that power loss/SIGKILL across several independent files is not globally atomic and may require restoring the private backups.
10. Print only profile, username, numeric bot ID and short fingerprint.

Unit-test username mismatch, duplicate tokens, pre-write failure, mid-commit rollback, unrelated-content preservation, symlink/hardlink refusal and file modes with synthetic credentials and mocked Telegram responses.

## 5. Activation and completion gate

After credentials are installed:

1. Confirm the multiplexed gateway assigned each bot to exactly one profile.
2. Validate every bot again with `getMe`; inspect webhook/polling state and pending updates.
3. Reconcile expected profile set = unique token fingerprint set = validated username set.
4. Send one message from the operator to each bot and require a role-appropriate response from the intended model/profile.
5. Report profile, username, model, gateway state and round-trip PASS/FAIL without exposing tokens.

Profiles created and model-smoked but lacking BotFather tokens are **prepared**, not ready. Tokens configured but lacking a real round trip are **configured**, not verified.