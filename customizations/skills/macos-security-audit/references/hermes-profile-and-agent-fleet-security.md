# Hermes Profile and Agent Fleet Security

Use this reference when one Mac runs many Hermes profiles, Telegram gateways, specialist models, MCP servers, Claude/Codex sessions, or a desktop agent with local-execution capability.

## 1. Inventory by class, not one raw count

Separate:
- interactive Hermes parents;
- gateway supervisors and gateway workers;
- bounded one-shot specialist workers;
- MCP watchdogs and MCP server children;
- kernels, language servers, builds, and tests;
- desktop agent main/helper/local-exec processes.

Record PID, PPID, TTY, elapsed time, command, working directory, and descendants. Preserve the current session, same-day work, recent kernels/LSPs, the gateway, and bounded workers. A static MCP threshold is misleading: derive the expected MCP tree from active agent parents plus the gateway.

If an old TTY-hosted Hermes process respawns after `SIGTERM`, its Terminal profile or parent shell may be configured to relaunch/resume it. After explicit approval, terminate or close the parent shell/TTY rather than repeatedly killing child PIDs. Re-inventory afterward.

## 2. Telegram gateway ownership

A Telegram bot token must have one polling gateway owner. Copying the same token into many profile `.env` files is both credential sprawl and a future competing-`getUpdates` failure.

Audit every profile without printing tokens:
1. Hash token values locally and group identical fingerprints.
2. Call Telegram `getMe` only to record bot ID/username and validity.
3. Verify the production gateway allowlist contains only intended user IDs and `GATEWAY_ALLOW_ALL_USERS` is false.
4. Keep the token only in the gateway-owning profile. Remove it from CLI-only specialist profiles.
5. Confirm all other profile gateways are stopped, then verify the one live gateway reaches healthy polling.

Do not infer multiple bots from multiple copied tokens; identity comes from `getMe`.

## 3. Least-privilege specialist profiles

For each profile, inventory model/provider, real authentication health, tool access, config/env modes, and credential key names only.

Defaults for isolated specialists:
- profile root `0700`;
- config, auth, token, history, and log files `0600`;
- no stored `SUDO_PASSWORD`;
- no Telegram/Slack gateway tokens unless that profile owns a gateway;
- only provider and tool credentials required by its role;
- `security.redact_secrets: true`;
- `security.allow_private_urls: false` unless explicitly required;
- Tirith enabled with an absolute executable path;
- fail closed for specialist profiles when the command guard is unavailable;
- disable lazy installs when the profile should not add packages autonomously.

After removing a stored password/token, restart gateway and other affected processes. Existing processes can retain deleted environment values in memory until restart.

Validate each model with a real exact-marker call. A config entry or successful auth-status command is not proof the model route works.

Isolate an advisory model's tools without duplicating its login store. Prefer supported configuration isolation and explicit disabling of external MCP servers; inspect the effective tool inventory rather than trusting an isolation flag. Do not copy a live `auth.json` into a scratch review home merely to preserve authentication: the new copy is another credential exposure surface even at `0600`. If authentication cannot work in place, use a supported destination sign-in or report the prerequisite; do not silently export a subscription session.

## 4. Desktop agent audit

For apps such as a local Grok/Claude/Cursor-derived agent:
- verify `codesign` authority, hardened runtime, notarization, and bundle identity;
- inspect main, helper, crashpad, renderer, network, and local-exec processes;
- list TCP listeners separately from outbound TLS connections;
- inspect Application Support directory and secret/descriptor file modes;
- identify local-execution keys and make them owner-only;
- check login persistence and external gateways;
- run a constrained health call without sharing credentials or sensitive business context.

A valid signature proves provenance, not safe permissions. A local-exec daemon with no listener is lower exposure than a wildcard listener, but its control key still requires `0600` protection.

## 5. Query-token logging pitfall

MCP endpoints sometimes authenticate with `?token=...`. HTTP client INFO logs can write the full URL even when a general redacting formatter claims secrets are protected.

Durable fix:
1. Treat both `httpx` and the MCP stack's separate `httpx2` logger as sensitive.
2. Suppress request logging to WARNING or sanitize URLs before records reach file handlers.
3. Add a regression test proving `httpx2` is configured at WARNING.
4. Redact existing affected lines.
5. Run a real model/MCP health call.
6. Re-scan the resulting logs with Gitleaks and require zero findings on leakage surfaces.

Do not merely chmod the log: owner-only secrets are still available to every model/tool running as that user.

## 6. Secret triage and cleanup

A broad profile Gitleaks scan will flag hundreds of documentation examples. Bucket findings first:
- approved stores: `.env`, `auth.json`, active MCP token stores, dedicated `secrets/`;
- leakage surfaces: logs, shell/history files, pastes, cron output, standalone key text files, backup auth/token files, generated reports;
- documentation/examples: review separately and do not rewrite blindly.

For leakage surfaces:
1. Preserve a restricted evidence copy in an encrypted or `0700` quarantine.
2. Redact exact detected lines without printing values.
3. Move obsolete auth/token backups out of the model profile.
4. Replace hardcoded script tokens with environment lookup; compile/test the scripts.
5. Scan pastes, logs, cron output, and scripts independently until each returns zero findings.
6. Rotate only credentials confirmed exposed beyond approved local stores or still active after a known leak.

## Cross-device credential coordination and recovery handoffs

1. Discover the actual local connection before repeatedly asking for host details. On a Mac, use the installed Tailscale CLI's `status` to identify peers; opening the Tailscale app and verifying connectivity is a separate operation from transferring a credential.
2. When the operator authorizes asking other agents, locate the exact group and bot identities from existing metadata and validate the destination. Request only credential names, purpose, minimum scope, Tailscale hostname/IP, receiving OS user/application and protected path. Never include credentials in that message. A bot API accepting a message does not prove the other agent received or acted on it; obtain a reply or ask the operator to relay from his account when bot-to-bot delivery is unavailable.
3. Treat agent replies as requirements to verify, not permission to export arbitrary secrets. Match requested credentials to the operator's authorized task and independently verify the device/account. Prefer destination-local credentials; if transfer is needed, use an authenticated channel over the private network with host identity verification and owner-only storage. Never disable host-key verification or send an entire credential inventory for one service.
4. If a secret is pasted into chat, do not echo it, place it in an attachment or retrieve it later from transcript history. Recommend secure replacement and obtain the required rotation authorization. Preserve the distinction between exposure and confirmed misuse.
5. When asked for a file to send another agent, create a versioned, credential-free recovery document rather than embedding a token or promising remote execution. Include verified bot username and numeric ID, owner identity, runtime discovery, existing gateway ownership, secure missing-credential request, inference smoke test, supervised startup, rollback and explicit acceptance checks. Label receiving-host runtime and service names unknown until inspected; Hermes commands are not automatically valid for another runtime.
6. Require a single update consumer for a Telegram token across hosts. Preserve pending updates and active webhook/polling ownership; a setup file must not authorize blind queue deletion or unrelated gateway shutdowns.
7. Verify service health, exact bot identity and provider inference separately. Reserve full gateway restoration for a fresh owner-initiated inbound message and correct outbound reply; otherwise report service restored with end-to-end test pending. A delivered recovery document proves only the handoff, not restoration or credential installation.

## 7. Continuous controls

Monitor profile security alongside host security:
- duplicate messaging credential fingerprints;
- command-guard path/availability;
- profile and credential modes;
- specialist fail-open/lazy-install drift;
- agent parent/MCP ratios;
- risky autonomy flags;
- desktop-agent local-exec secret permissions;
- recurring sensitive exports created with `0644`.

A separate permission guard may safely enforce `0600` on known sensitive export and credential classes. Keep automated containment of processes, accounts, or cloud systems disabled until response actions are explicitly tested and approved.

## 8. Multi-model swarm completion discipline

For a fixed-roster local swarm, launch each approved profile independently and write each lane to a separate owner-only output artifact. Keep roles distinct (for example: architecture, financial/data accuracy, adversarial security, UX/accessibility, and test/release gates) and prohibit concurrent mutation of the same checkout.

Count a lane as complete only when:
1. the intended profile/model actually ran;
2. its output artifact is non-empty and substantive;
3. the artifact is read and incorporated into the synthesis; and
4. consequential claims are independently verified by the primary agent.

A background wrapper exiting with an indeterminate status or an empty redirected file is a failed lane, not a successful agent. Preserve completed lanes, replace only the missing lane with another approved model/profile, and disclose the substitution. Do not restart the whole swarm or inflate the count by treating the primary synthesizer as a missing specialist unless that was the declared design from the start.
