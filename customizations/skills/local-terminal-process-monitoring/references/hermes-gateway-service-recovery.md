# Hermes gateway service recovery

Use when a messaging gateway appears alive-but-silent or completely unresponsive.

## Diagnose in this order

1. Run `hermes gateway status`.
2. On macOS, inspect `launchctl list ai.hermes.gateway` to distinguish a running service, a present-but-unloaded definition, and a crashed process.
3. Inspect newest gateway logs for the last inbound message and platform connection—not merely process liveness.
4. Classify the exit:
   - planned `SIGTERM` plus `Gateway stopped` / `gateway.exit_clean` means clean shutdown;
   - traceback plus nonzero exit means crash;
   - live PID with stale polling/inbound timestamps means zombie polling.

## Recovery

- If the definition exists but launchd unloaded it, run `hermes gateway start`; the CLI reloads and starts the service.
- If a live gateway is zombie-polling, restart only after checking for active work that would be interrupted.
- Do not call a cleanly stopped, unloaded service “stuck.”

## Verification gates

Require all applicable signals:

- `hermes gateway status` shows a launchd-supervised PID.
- Telegram logs show fresh `Telegram polling confirmed healthy: getUpdates progressing`.
- Telegram logs show fresh `Connected to Telegram (polling mode)` and `✓ telegram connected`.
- Gateway logs show `Gateway running with N platform(s)`.

A successful start command alone is insufficient; read back status and fresh logs.
