---
name: native-mcp
description: Built-in MCP (Model Context Protocol) client that connects to external MCP servers, discovers their tools, and registers them as native Hermes Agent tools. Supports stdio and HTTP transports with automatic reconnection, security filtering, and zero-config tool injection.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [MCP, Tools, Integrations]
    related_skills: [mcporter]
---

# Native MCP Client

Hermes Agent has a built-in MCP client that connects to MCP servers at startup, discovers their tools, and makes them available as first-class tools the agent can call directly. No bridge CLI needed -- tools from MCP servers appear alongside built-in tools like `terminal`, `read_file`, etc.

## When to Use

Use this whenever you want to:
- Connect to MCP servers and use their tools from within Hermes Agent
- Add external capabilities (filesystem access, GitHub, databases, APIs) via MCP
- Run local stdio-based MCP servers (npx, uvx, or any command)
- Connect to remote HTTP/StreamableHTTP MCP servers
- Have MCP tools auto-discovered and available in every conversation

For ad-hoc, one-off MCP tool calls from the terminal without configuring anything, see the `mcporter` skill instead.

## Prerequisites

- **mcp Python package** -- optional dependency; install with `pip install mcp`. If not installed, MCP support is silently disabled.
- **Node.js** -- required for `npx`-based MCP servers (most community servers)
- **uv** -- required for `uvx`-based MCP servers (Python-based servers)

Install the MCP SDK:

```bash
pip install mcp
# or, if using uv:
uv pip install mcp
```

## Quick Start

First confirm from the exact product's current documentation that the integration direction is **Hermes → external MCP server**. Do not infer MCP from a product name, an “agent bridge” label, or a key prefix; some phone and wearable integrations instead call Hermes' OpenAI-compatible API and use separate licence and Hermes bearer keys.

Then check whether the capability is already packaged as an enabled Hermes agent plugin
with an `mcp.json`. If so, use `hermes plugins install/enable <name>` and start a fresh
session; do not also add the upstream server under `mcp_servers`, because duplicate
registrations can pin different package versions and expose two authorities for the same
tools.

For capabilities without an agent plugin, add MCP servers to `~/.hermes/config.yaml`
under the `mcp_servers` key:

```yaml
mcp_servers:
  time:
    command: "uvx"
    args: ["mcp-server-time"]
```

Restart Hermes Agent. On startup it will:
1. Connect to the server
2. Discover available tools
3. Register them with the prefix `mcp_time_*`
4. Inject them into all platform toolsets

You can then use the tools naturally -- just ask the agent to get the current time.

## Configuration Reference

Each entry under `mcp_servers` is a server name mapped to its config. There are two transport types: **stdio** (command-based) and **HTTP** (url-based).

### Stdio Transport (command + args)

```yaml
mcp_servers:
  server_name:
    command: "npx"             # (required) executable to run
    args: ["-y", "pkg-name"]   # (optional) command arguments, default: []
    env:                       # (optional) environment variables for the subprocess
      SOME_API_KEY: "value"
    timeout: 120               # (optional) per-tool-call timeout in seconds, default: 120
    connect_timeout: 60        # (optional) initial connection timeout in seconds, default: 60
```

### HTTP Transport (url)

```yaml
mcp_servers:
  server_name:
    url: "https://my-server.example.com/mcp"   # (required) server URL
    headers:                                     # (optional) HTTP headers
      Authorization: "Bearer sk-..."
    timeout: 180               # (optional) per-tool-call timeout in seconds, default: 120
    connect_timeout: 60        # (optional) initial connection timeout in seconds, default: 60
```

### All Config Options

| Option            | Type   | Default | Description                                       |
|-------------------|--------|---------|---------------------------------------------------|
| `command`         | string | --      | Executable to run (stdio transport, required)     |
| `args`            | list   | `[]`    | Arguments passed to the command                   |
| `env`             | dict   | `{}`    | Extra environment variables for the subprocess    |
| `url`             | string | --      | Server URL (HTTP transport, required)             |
| `headers`         | dict   | `{}`    | HTTP headers sent with every request              |
| `timeout`         | int    | `120`   | Per-tool-call timeout in seconds                  |
| `connect_timeout` | int    | `60`    | Timeout for initial connection and discovery      |

Note: A server config must have either `command` (stdio) or `url` (HTTP), not both.

## How It Works

### Startup Discovery

When Hermes Agent starts, `discover_mcp_tools()` is called during tool initialization:

1. Reads `mcp_servers` from `~/.hermes/config.yaml`
2. For each server, spawns a connection in a dedicated background event loop
3. Initializes the MCP session and calls `list_tools()` to discover available tools
4. Registers each tool in the Hermes tool registry

### Tool Naming Convention

MCP tools are registered with the naming pattern:

```
mcp_{server_name}_{tool_name}
```

Hyphens and dots in names are replaced with underscores for LLM API compatibility.

Examples:
- Server `filesystem`, tool `read_file` → `mcp_filesystem_read_file`
- Server `github`, tool `list-issues` → `mcp_github_list_issues`
- Server `my-api`, tool `fetch.data` → `mcp_my_api_fetch_data`

### Auto-Injection

After discovery, MCP tools are automatically injected into all `hermes-*` platform toolsets (CLI, Discord, Telegram, etc.). This means MCP tools are available in every conversation without any additional configuration.

### Connection Lifecycle

- Each server runs as a long-lived asyncio Task in a background daemon thread
- Connections persist for the lifetime of the agent process
- If a connection drops, automatic reconnection with exponential backoff kicks in (up to 5 retries, max 60s backoff)
- On agent shutdown, all connections are gracefully closed

### Idempotency

`discover_mcp_tools()` is idempotent -- calling it multiple times only connects to servers that aren't already connected. Failed servers are retried on subsequent calls.

## Transport Types

### Stdio Transport

The most common transport. Hermes launches the MCP server as a subprocess and communicates over stdin/stdout.

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"]
```

The subprocess inherits a **filtered** environment (see Security section below) plus any variables you specify in `env`.

### HTTP / StreamableHTTP Transport

For remote or shared MCP servers. Requires the `mcp` package to include HTTP client support (`mcp.client.streamable_http`).

```yaml
mcp_servers:
  remote_api:
    url: "https://mcp.example.com/mcp"
    headers:
      Authorization: "Bearer sk-..."
```

If HTTP support is not available in your installed `mcp` version, the server will fail with an ImportError and other servers will continue normally.

## Security

### Environment Variable Filtering

For stdio servers, Hermes does NOT pass your full shell environment to MCP subprocesses. Only safe baseline variables are inherited:

- `PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM`, `SHELL`, `TMPDIR`
- Any `XDG_*` variables

All other environment variables (API keys, tokens, secrets) are excluded unless you explicitly add them via the `env` config key. This prevents accidental credential leakage to untrusted MCP servers.

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      # Only this token is passed to the subprocess
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_..."
```

### Credential Stripping in Error Messages

If an MCP tool call fails, any credential-like patterns in the error message are automatically redacted before being shown to the LLM. This covers:

- GitHub PATs (`ghp_...`)
- OpenAI-style keys (`sk-...`)
- Bearer tokens
- Generic `token=`, `key=`, `API_KEY=`, `password=`, `secret=` patterns

## OAuth Authentication (Remote HTTP Servers)

Some remote MCP servers (e.g., Circleback, others using MCP spec 2025-03-26) require OAuth 2.1 with dynamic client registration instead of static bearer tokens. Hermes supports this natively.

### Config Format

```yaml
mcp_servers:
  circleback:
    url: "https://app.circleback.ai/api/mcp"
    auth: oauth
    oauth:                              # all fields optional
      client_id: "pre-registered-id"    # skip dynamic registration
      client_secret: "secret"           # confidential clients only
      scope: "read write"               # default: server-provided
      redirect_port: 0                  # 0 = auto-pick free port
      client_name: "My Custom Client"   # default: "Hermes Agent"
```

Minimum config (most OAuth servers): just `url` + `auth: oauth`.

### Initial Authorization (Browser Required)

OAuth requires a one-time interactive browser login. Tokens are cached in `~/.hermes/mcp_oauth/` and auto-refresh after that.

For remote OAuth servers, separate configuration from authorization when operating through a headless/gateway session:

1. Persist the server first with `hermes config set mcp_servers.<name>.url <url>` and `hermes config set mcp_servers.<name>.auth oauth`; optionally set bounded `timeout` and `connect_timeout` values.
2. Before starting the finite-lived OAuth callback, ask the user to confirm they are at the browser that will receive it. Do not open authorization windows early; expiry is configured-but-unauthenticated state, not successful setup.
3. Run `hermes mcp login <name>` in a tracked interactive PTY. Capture the authorization URL without exposing token files.
4. The user completes the provider login and consent in their browser. Never type, request in chat, or automate passwords or 2FA. If no authenticated browser/vault path exists, stop at this human gate.
4. Do not answer a still-open redirect-code prompt with `y`: it is parsed as a pasted redirect and ignored. Submit only the real redirect URL/code, or `skip` to abort that OAuth attempt.
5. Verify `hermes mcp test <name>` returns `Connected` plus a nonzero tool count; `hermes mcp list` proves only saved configuration.
6. Restart/reload the gateway or start a new session so newly discovered tools enter the live tool registry.

A read-only MCP can still consume billable API units. Before the first data call, state the unit/cost boundary, use the smallest report/row limit that answers the question, and expand only with scoped authorization.

**Known issue**: `hermes mcp add <name> --url <url> --auth oauth` may open the chat UI instead of running the subcommand. Workarounds:

**Option A — Standalone script** (most reliable):

```python
#!/usr/bin/env python3
# Save as e.g. ~/Desktop/mcp_oauth_setup.py and run: python3 ~/Desktop/mcp_oauth_setup.py
import sys
sys.path.insert(0, "/path/to/.hermes/hermes-agent")  # adjust path
from tools.mcp_oauth import build_oauth_auth

auth = build_oauth_auth(
    server_name="circleback",  # must match config.yaml key
    server_url="https://app.circleback.ai/api/mcp",
)
if auth:
    print("✅ OAuth tokens saved. Restart Hermes to use.")
else:
    print("❌ OAuth setup failed.")
```

**Option B — Full path to hermes binary**:

```bash
/full/path/to/.local/bin/hermes mcp add circleback \
  --url "https://app.circleback.ai/api/mcp" --auth oauth
```

**Option C — Add config manually, then test**:

1. Add the `url` + `auth: oauth` entry to `~/.hermes/config.yaml` manually
2. Run `hermes mcp test <name>` — it will trigger the OAuth flow on first connection

### Diagnosing OAuth Failures

| Error | Meaning | Fix |
|-------|---------|-----|
| "Protected resource X does not match expected Y" | URL path mismatch in OAuth resource indicator (see bug below) | Apply the `mcp_oauth.py` patch below, then re-run `hermes mcp test <name>` |
| "non-interactive environment and no cached tokens" | Agent session can't open a browser | Run the OAuth flow from an interactive terminal first |
| "Connection failed: 401 Unauthorized" | Tokens expired or never obtained | Re-run the OAuth flow interactively |
| "OAuthNonInteractiveError: callback timed out" | Browser auth wasn't completed within 5 min | Re-run and complete browser login promptly |

### Known Bug: OAuth "Protected resource does not match" (as of April 2026)

**Symptom**: `hermes mcp test <name>` returns:
```
Protected resource https://example.com/api/mcp does not match expected https://example.com
```

**Root cause**: In `tools/mcp_oauth.py`, the `build_oauth_auth()` function strips the URL path before passing it to `OAuthClientProvider`:
```python
# BUG — strips path, causing resource indicator mismatch
parsed = urlparse(server_url)
base_url = f"{parsed.scheme}://{parsed.netloc}"
provider = OAuthClientProvider(server_url=base_url, ...)
```

Servers like Circleback declare the full URL (`https://app.circleback.ai/api/mcp`) as their protected resource, but the stripped URL (`https://app.circleback.ai`) doesn't match.

**Fix**: In `tools/mcp_oauth.py`, pass `server_url` directly instead of stripping it:
```python
# FIX — pass full URL so resource indicator matches
provider = OAuthClientProvider(server_url=server_url, ...)
```

This is a one-line change around line 469-473 of `mcp_oauth.py`. After patching, `hermes mcp test <name>` will trigger the browser OAuth flow correctly.

### Token Storage

OAuth tokens are persisted as flat files in `~/.hermes/mcp-tokens/` (NOT `mcp_oauth/`): `<server>.json` (access_token, refresh_token, expires_at), `<server>.client.json` (DCR client registration), `<server>.meta.json` (discovery doc). They survive restarts. To force re-auth, delete `<server>.json` and re-run `hermes mcp login <server>`.

To prove the token maps to the right account without exposing it, read `<server>.json` in a script and POST a read-only `tools/call` (e.g. `list_accounts`) to the server URL with `Authorization: Bearer <access_token>` and `MCP-Protocol-Version: 2025-06-18`; the SSE `_meta.acting_email` shows the authenticated identity.

Servers advertising `client_id_metadata_document_supported: true` (e.g. Superhuman at `https://mcp.mail.superhuman.com/mcp`) accept Hermes' hosted client-metadata URL as `client_id` — no pre-registration needed, so plain `hermes mcp login <name>` works end to end.

### Using a server you just added, in the same session

Tool discovery runs once at agent startup, so a server added mid-session has no `mcp_<server>_*` tools yet. Do not report the connection as broken and do not restart the gateway mid-turn. Drive it directly instead, using the cached token Hermes already wrote:

1. `hermes mcp test <name>` proves auth + discovery and prints every tool name and description — that is also your schema reference when deciding filters.
2. POST JSON-RPC (`initialize` → `tools/call`) to the server URL with `Authorization: Bearer <access_token>`, `MCP-Protocol-Version: 2025-06-18`, `Accept: application/json, text/event-stream`. Responses are SSE — parse the `data:` line, and prefer `result.structuredContent` over `result.content[0].text`.
3. Tell the user the tools appear as first-class tools from the next session onward, and that a restart is needed to get them there.

Argument-name trap: MCP arguments that are Python keywords (e.g. `from`) cannot be passed as kwargs — use `**{'from': [...]}`. When in doubt, read `inputSchema` from `tools/list` rather than guessing.

A working client for a real server of this shape (Superhuman Mail, including pagination and label read-back) ships in the `clean-inbox` skill as `scripts/superhuman_mcp.py`; its operating checklist is the `superhuman-mcp-mailbox` support file in that same skill.

## Troubleshooting

### "MCP SDK not available -- skipping MCP tool discovery"

The `mcp` Python package is not installed. Install it:

```bash
pip install mcp
```

### "No MCP servers configured"

No `mcp_servers` key in `~/.hermes/config.yaml`, or it's empty. Add at least one server.

### "Failed to connect to MCP server 'X'"

Common causes:
- **Command not found**: The `command` binary isn't on PATH. Ensure `npx`, `uvx`, or the relevant command is installed.
- **Package not found**: For npx servers, the npm package may not exist or may need `-y` in args to auto-install.
- **Timeout**: The server took too long to start. Increase `connect_timeout`.
- **Port conflict**: For HTTP servers, the URL may be unreachable.

### "MCP server 'X' requires HTTP transport but mcp.client.streamable_http is not available"

Your `mcp` package version doesn't include HTTP client support. Upgrade:

```bash
pip install --upgrade mcp
```

### Tools not appearing

- Check that the server is listed under `mcp_servers` (not `mcp` or `servers`)
- Ensure the YAML indentation is correct
- Look at Hermes Agent startup logs for connection messages
- Tool names are prefixed with `mcp_{server}_{tool}` -- look for that pattern

### Connection keeps dropping

The client retries up to 5 times with exponential backoff (1s, 2s, 4s, 8s, 16s, capped at 60s). If the server is fundamentally unreachable, it gives up after 5 attempts. Check the server process and network connectivity.

## Examples

### Time Server (uvx)

```yaml
mcp_servers:
  time:
    command: "uvx"
    args: ["mcp-server-time"]
```

Registers tools like `mcp_time_get_current_time`.

### Filesystem Server (npx)

```yaml
mcp_servers:
  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/documents"]
    timeout: 30
```

Registers tools like `mcp_filesystem_read_file`, `mcp_filesystem_write_file`, `mcp_filesystem_list_directory`.

### GitHub Server with Authentication

```yaml
mcp_servers:
  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxxxxxxxxxxxxxxxxxxx"
    timeout: 60
```

Registers tools like `mcp_github_list_issues`, `mcp_github_create_pull_request`, etc.

### Remote HTTP Server

```yaml
mcp_servers:
  company_api:
    url: "https://mcp.mycompany.com/v1/mcp"
    headers:
      Authorization: "Bearer sk-xxxxxxxxxxxxxxxxxxxx"
      X-Team-Id: "engineering"
    timeout: 180
    connect_timeout: 30
```

### Multiple Servers

```yaml
mcp_servers:
  time:
    command: "uvx"
    args: ["mcp-server-time"]

  filesystem:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

  github:
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxxxxxxxxxxxxxxxxxxx"

  company_api:
    url: "https://mcp.internal.company.com/mcp"
    headers:
      Authorization: "Bearer sk-xxxxxxxxxxxxxxxxxxxx"
    timeout: 300
```

All tools from all servers are registered and available simultaneously. Each server's tools are prefixed with its name to avoid collisions.

## Direct Python diagnostic compatibility

Before writing an ad-hoc MCP probe, inspect the installed SDK's transport signature rather than guessing an older import. Newer SDKs can expose `streamable_http_client(..., http_client=...)` with an `httpx2.AsyncClient`, not `streamablehttp_client(headers=...)` with `httpx`. Inspect tool schemas via `tool.model_dump(mode="json", by_alias=True)` so Python snake-case attributes do not get confused with wire keys such as `inputSchema`. Keep authentication values out of diagnostics. Do not upgrade the shared SDK merely to make an old probe work.

## Changing a remote server's URL or key

- Store the bearer key in `~/.hermes/.env` (mode 600) as `<SERVER>_API_KEY` and reference it in `config.yaml` as `Authorization: Bearer ${MCP_<SERVER>_API_KEY}`. `hermes mcp test` expands it, so the key never lands in config or transcripts.
- Change only the URL with `hermes config set mcp_servers.<name>.url <url>`; back up `config.yaml` and `.env` first.
- `hermes mcp test <name>` proves auth + discovery (`Connected` plus a tool count). Tool *names* change between endpoints, so compare the discovered list against the previous session's — a different tool count means the endpoint really switched.
- The running gateway keeps the endpoint it loaded at startup. Slash-command reload exists only in the TUI; on Telegram/CLI the change lands after a supervised gateway restart (`launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway`). Never restart mid-turn — the reply dies with the process; report first, restart on the next turn.
- Prove the key maps to the right account with one read-only call over raw JSON-RPC (initialize → notifications/initialized → tools/call) against the URL, not just `tools/list`.

## Sampling (Server-Initiated LLM Requests)

Hermes supports MCP's `sampling/createMessage` capability — MCP servers can request LLM completions through the agent during tool execution. This enables agent-in-the-loop workflows (data analysis, content generation, decision-making).

Sampling is **enabled by default**. Configure per server:

```yaml
mcp_servers:
  my_server:
    command: "npx"
    args: ["-y", "my-mcp-server"]
    sampling:
      enabled: true           # default: true
      model: "gemini-3-flash" # model override (optional)
      max_tokens_cap: 4096    # max tokens per request
      timeout: 30             # LLM call timeout (seconds)
      max_rpm: 10             # max requests per minute
      allowed_models: []      # model whitelist (empty = all)
      max_tool_rounds: 5      # tool loop limit (0 = disable)
      log_level: "info"       # audit verbosity
```

Servers can also include `tools` in sampling requests for multi-turn tool-augmented workflows. The `max_tool_rounds` config prevents infinite tool loops. Per-server audit metrics (requests, errors, tokens, tool use count) are tracked via `get_mcp_status()`.

Disable sampling for untrusted servers with `sampling: { enabled: false }`.

## Notes

- MCP tools are called synchronously from the agent's perspective but run asynchronously on a dedicated background event loop
- Tool results are returned as JSON with either `{"result": "..."}` or `{"error": "..."}`
- The native MCP client is independent of `mcporter` -- you can use both simultaneously
- Server connections are persistent and shared across all conversations in the same agent process
- Adding or removing servers requires restarting the agent (no hot-reload currently)
