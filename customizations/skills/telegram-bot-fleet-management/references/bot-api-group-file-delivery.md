# Bot API group file delivery + multi-profile skill sync

Proven recipes from the "share the spec/keys with all agents" task class.

## sendDocument to a group (token-safe)

1. Read the bot token from `~/.hermes/.env` inside the Python script; never echo it or let it appear in tool output. Verify with `getMe` first (it returns the bot username, not the token).
2. Build `sendDocument` as hand-rolled multipart/form-data (chat_id, caption, document parts) — no `requests` dependency; use `urllib.request` with a `Content-Type: multipart/form-data; boundary=...` header. `socket.setdefaulttimeout(30)`; retry once on timeout.
3. Delivery evidence = the JSON `ok: true` plus the returned `message_id`. Report the message ID, not just "sent".

### Pitfalls
- `getChatMemberList` returns **HTTP 404** for a bot that is not a group admin — do not try to enumerate members this way. `getChat` still returns title/type/permissions; deliver to the chat_id directly.
- Captions with special characters: pass through multipart as-is (not URL-encoded as a whole body).

## Multi-profile skill sync ("deliver to all profiles")

Canonical copy lives in `~/.hermes/skills/<category>/<name>/`. Mirror into every profile and verify:

```bash
SRC=~/.hermes/skills/<category>/<name>
for p in ~/.hermes/profiles/*/; do
  dst="$p/skills/<category>"; mkdir -p "$dst"
  rm -rf "$dst/<name>"; cp -R "$SRC" "$dst/"
  # hash-verify 2+ representative files per profile (SKILL.md + core script/spec)
done
```

- A copy that exited 0 is not done — report per-profile sha256 readback as `SYNCED_OK=N MISMATCHES=0`.
- Keep the user's "controlling package" copy (e.g. under `~/Downloads/`) byte-identical to the skill's package dir: hash-compare every file, refresh whichever side is newer, then zip for distribution excluding `__pycache__`/`*.pyc` and include the archive SHA-256 in the delivery message.

## Verification standard

- **Delivered** = Telegram `ok:true` + message ID (files), or per-profile hash readback (skills).
- **Transferred** = credential written owner-only (0600) on the target AND a provider smoke call passing.
- Anything else is a blocked-status report with the exact unblock step.
