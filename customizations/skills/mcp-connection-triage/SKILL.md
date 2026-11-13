---
name: mcp-connection-triage
description: Use when MCP servers show stuck, failed, or disconnected.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [MCP, Troubleshooting, OAuth]
    related_skills: [native-mcp, mcporter, global-hermes-mcp-access]
---

# MCP Connection Triage

## When to Use

- the operator asks to "make sure all the MCPs are connected" (or any subset of them).
- A status snapshot shows servers stuck on "connecting" or failing.
- MCP tools are missing from a session and you need to determine whether it is config, auth, or liveness.

Verify and repair Hermes MCP server connections (stdio, HTTP, OAuth). Pair with the `native-mcp` skill for config-level details; this skill is the diagnose/fix loop.

## Verification procedure (do in this order)

1. `hermes mcp ls` — lists configured servers and enabled state. This is config state, not liveness.
2. Live-test every flagged server (or every server when asked to verify all): `hermes mcp test <name>`. Ground truth is `✓ Connected` plus a tool count; batch the tests in one shell loop for speed.
3. Branch on the failure signature (decision table below) instead of the status line.

## Always-on rules

- A status snapshot showing "connecting" is NOT evidence of failure — remote HTTP servers may simply be mid-handshake. Only a failed live test justifies a fix. (Mechanism: the status line is a point-in-time of an async connect, and slow proxies routinely exceed the snapshot window.)
- `hermes mcp test` prints an "Error Responses" section from its sample tool calls. A server that connects fine but whose sample calls return 4xx is often a harness/parameter quirk, not a broken integration — validate the underlying credential directly against the vendor API before declaring the MCP dead.
- A running agent process holds its connections for its own lifetime. Fresh OAuth tokens or config changes apply to FUTURE sessions only — after a fix, tell the operator the current session/gateway needs a restart or reload before the tools go live.
- Never pipe a background `hermes mcp login` through `tail` or another filter — the pipe buffers all output until the command exits, so you can't see the authorization URL if the browser fails to auto-open. Run it unfiltered and poll the process log.
- OAuth token files are credentials: check existence/paths only, never print contents.

## Failure decision table

| Test signature | Meaning | Fix |
|---|---|---|
| "MCP OAuth requires browser authorization but no interactive session is available" / "non-interactive environment and no cached tokens" | No valid cached OAuth token — the server's token store is missing or empty (never saved, or wiped) | Run `hermes mcp login <name>` from an interactive context — the browser opens automatically, the user completes authorization, then verify with `hermes mcp test <name>` |
| "Connection failed: 401 Unauthorized" | Token expired or revoked | Same `hermes mcp login <name>` re-auth path |
| Connected + tool count, but "Error Responses" 4xx on sample calls | Sample-call/harness quirk OR real API rejection | Validate the vendor API directly; HTTP 200 means the MCP is fine (e.g. Notion: `curl -H "Authorization: Bearer $TOKEN" -H "Notion-Version: 2022-06-28" https://api.notion.com/v1/users/me` — do not echo the full token in output) |
| Stdio: command not found / package not found | PATH or npm package issue under the filtered env | Fix `command`/`args` in config; keep `-y` for npx auto-install |
| HTTP: timeout / unreachable | Server down, wrong URL, or URL-embedded token rejected | curl the URL directly to separate server-down from auth-rejected |

## Plugin-owned MCP servers

Portable Agent Plugins can declare MCP servers in the plugin's `mcp.json` without adding them to `config.yaml`. Therefore `hermes mcp list` may omit a healthy plugin-owned server.

Verify in this order:
1. `hermes plugins list` — plugin is installed and enabled.
2. `hermes plugins doctor <name>` — manifest discovery and runtime registration pass.
3. Read the plugin's `mcp.json` to obtain the exact pinned command and environment; do not substitute `@latest`.
4. Start that exact command in a bounded subprocess and perform a JSON-RPC MCP handshake: `initialize` → `notifications/initialized` → `tools/list`. A server name/version plus a nonzero tool count is direct protocol evidence even when `hermes mcp list` has no row.
5. Restart or start a new Hermes session only after the handshake passes; plugin MCP registrations are session-start state.

For an `npx` stdio server, warm the pinned package once with a harmless command such as `npx -y package@version --help` before the handshake. This separates package download/runtime failures from Hermes plugin discovery failures.

## Duplicate-process leak (slowness, not connection failure)

Symptom: the Mac is slow, Activity Monitor shows a huge compressor footprint, and `ps` shows many copies of the same stdio MCP server. This is NOT a connection problem and no `hermes mcp test` will reveal it.

Diagnose by counting, not by testing:

```bash
ps -Ao command | grep -c '[r]ea mcp'
ps -Ao command | grep -c '[s]erve_memory.py'
```

Observed on this machine: 78 `npx rea-agents@6.7.0 mcp` (each with a `node` child, so 156 procs) plus 76 `serve_memory.py` accumulated in ~13 minutes of uptime — 184 procs / 4.8 GB, which drove the compressor to 21.6 GB and free RAM to 66 MB. All of them were children of the single live Hermes agent PID, so this is a spawn-without-reap leak in the stdio MCP client, not a user-started process.

Fix: `~/.hermes/scripts/reap_mcp.py` keeps the newest instance of each group and SIGTERMs the rest (then SIGKILLs stragglers). `--dry-run` reports without killing. It refuses to touch the Hermes agent/gateway process itself and never kills the last instance of a group. Installed as a silent `no_agent` cron every 15m (job name "MCP process-leak reaper").

Rules:
- Kill duplicates oldest-first and always keep the newest — the newest is the one the live session is holding.
- Never kill the Hermes agent or gateway PID; every leaked MCP server is its child and killing the parent loses the session.
- Freeing the real memory also releases the compressor: 4.8 GB of processes reclaimed ~17 GB of compressor.
- Load average spikes for a minute during the mass kill (process teardown) — that is expected, not a new problem.
- The leak recurs under tool-heavy use, so the cron guard matters more than the one-time cleanup.

## Pitfalls

- The OAuth token store location is inconsistent across skill docs and Hermes versions (`~/.hermes/mcp_oauth/<name>/` in `native-mcp`, per-profile `mcp-tokens/` in `global-hermes-mcp-access`). After any login, verify where the tokens actually landed before asserting a path to the user.
- `hermes mcp ls` showing "✓ enabled" only means the server is configured and not disabled — it says nothing about live connectivity. Never report "all connected" from `ls` alone.
- `python3` on this machine lacks PyYAML — don't parse config.yaml with `python3 -c "import yaml"`; grep/awk the `mcp_servers:` block instead.
