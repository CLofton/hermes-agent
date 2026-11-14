# Recovering a dormant Telegram bot safely

Use this when a bot token still validates but no gateway owns it, especially when several similarly named bots exist.

## Recovery sequence

1. **Disambiguate the identity.** Compare the secured inventory against Telegram `getMe`; report only username, numeric ID, and a short token fingerprint. Inspect `getWebhookInfo` for webhook state and pending-update count.
2. **Find the prior owner.** Compare token fingerprints across profile `.env` files. Never print tokens. If no profile owns the fingerprint, treat the bot as unassigned rather than attaching it to the main gateway.
3. **Inspect the dormant queue before polling.** Call `getUpdates` without advancing `offset` and summarize sender, chat type, timestamp, and short text preview. A dormant queue can contain stale `/model`, `/yolo`, `/repair`, or other commands that must not replay on startup.
4. **Quarantine stale updates when authorized.** Once the owner has asked to restore the bot, acknowledge only the already-inspected stale range by advancing `offset` to `last_update_id + 1`. Read back `getWebhookInfo.pending_update_count == 0` before starting the gateway. Do not delete an active queue blindly.
5. **Create a least-privilege profile.** Give the bot its own Hermes profile, its own unique Telegram token, an explicit user allowlist/home channel, owner-only `.env` permissions (`0600`), a scoped SOUL, fail-closed command scanning, and no lazy installs. Copy only the model credential and tools the role needs.
6. **Prove the model before the gateway.** Run a one-shot exact-marker chat through the profile. A config file or zero exit code alone does not prove the selected provider/model works.
7. **Install one gateway owner.** Install/start the profile-specific launchd service. Never run two polling consumers for one token.
8. **Verify the live path.** Require all of: launchd reports supervised, the profile log records `Telegram polling confirmed healthy`, the log records `Connected to Telegram (polling mode)`, `getMe` still matches the expected username, webhook remains intentionally configured/unconfigured, and pending updates remain zero.
9. **Do not send a test message without explicit authorization.** Connection/readback evidence is enough for restoration; let the owner initiate the first live conversation.

## Common pitfall

A profile-creation banner may generically warn that no API key exists even when a cloned `.env` contains the intended provider key. Verify non-secret key presence and then run the exact-marker model probe; do not trust or argue with the banner alone.
