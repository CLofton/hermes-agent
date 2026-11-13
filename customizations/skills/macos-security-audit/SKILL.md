---
name: macos-security-audit
created_by: curator
managed_by: curator
description: Use when auditing a Mac for compromise or exposure.
version: 1.0.0
tags: [macOS, security, incident-response, compromise, malware, persistence, network]
---

# macOS Security Audit

Use this class-level workflow when a user asks “have I been compromised?”, requests a security scan, or wants local attack-surface hardening.

This covers the HOST. When the alert concerns an online account rather than this Mac — a "new login" / "new device" email, or "am I being hacked?" with no host symptoms — use `account-login-alert-triage` and return here only if host evidence is actually needed.

## Contract

- Default to read-only inspection.
- Never state “clean” or “compromised” from one signal.
- Lead with the conclusion: confirmed compromise, suspicious evidence requiring escalation, or no evidence found with limitations.
- Separate active-compromise indicators from hardening gaps.
- Before state changes (firewall, killing processes, deleting files, uninstalling apps), confirm the requested scope and verify afterward. Remediation that edits the platform's own configuration goes through its supported setter (`hermes config set <dotted.key> <value>`); never script a regex or text rewrite of `config.yaml`, because a block-matching pattern with DOTALL runs to end of file and rewrites every same-shaped key after it. See `hermes-agent` before touching that file.
- Bind a brief approval such as “deploy fix” to the specific replied-to remediation; keep rotation, history rewrites, restarts, process termination, and threshold changes separate unless explicitly included. Once that scope is confirmed, execute its verification and release path rather than repeatedly asking for the same approval.
- Triage tracked secrets with a content rule set, never with filename patterns. A `.env`, `*.pem`, `credentials*.json` matcher misses the credentials that actually got committed — a service-account key in `.sa-key.json`, a live OAuth client secret in an `.env.example` meant as a placeholder. Run `gitleaks dir <root> -c <allowlist.toml>` and adjudicate each hit; expect the raw count to be dominated by docs and test fixtures, so report the small verified set, not the total.
- Treat secret formats and entropy as evidence of credential-like material, not proof a credential is live; establish validity through authorized provider evidence or label it unverified. A private repository limits exposure but does not remove it. Probe every flagged credential against its provider's read-only endpoint before recommending rotation, and read repository visibility from the API rather than assuming it: revoked keys need containment, not an account rotation, and that finding changes the whole remediation. See `references/credential-liveness-checks.md` for the provider probes, the junk-key control, the rotation stopping rule, and the commit-time guard that stops the class recurring.
- For cross-device credential requests, first resolve the intended application and authorized read/write operations; do not silently reduce an explicitly authorized read/write integration to read-only or expand task-write permission into messaging or command execution. Then bind transfer authorization to a verified device, receiving account/application, minimum scope and protected destination. For the operator's agent-to-agent API handoffs, deliver dedicated credentials through his requested Tailscale channel, never in Telegram or a shared handoff document; do not reuse the application's human-login password as the machine credential. Opening Tailscale or listing peers is not credential delivery. Report requested, transferred, installed and authentication-verified as separate states.
- Distinguish fix installation, containment, recurring prevention, and incident closure in every remediation result; one does not prove the others. Never use a post-enforcement clean scan to prove the original exposure stopped recurring.
- Before deploying reviewed code, verify the reviewer’s actual model family from dispatch metadata and bind the verdict to the exact candidate digest; a report’s self-described identity does not prove cross-family review. Adjudicate findings against executed evidence rather than adopting guessed warning causes or framework APIs. Turn accepted findings into failing regression tests, fix them, and obtain a bounded follow-up review of the changed boundary. Then compare live source hashes and required file modes with the review baseline under the shared writer lock. Preserve intervening fixes, reapply only approved changes, and rerun the combined tests; a stale candidate can undo a different security repair, and byte-identical publication can still break a shebang entry point by dropping its executable bit.
- If writer-lock acquisition times out, identify the holder and its descendants before retrying; timeout proves contention, not a stale lock or failed service. Never unlink the lock file or terminate its owner merely to deploy, because a replacement inode defeats mutual exclusion. Report the candidate as tested but not deployed until installation and live readback succeed.
- On broad approval of a replied-to recommendation list, preserve its explicit exclusions and negative recommendations, choose the narrower offered lifecycle action when sufficient, and record the scope before execution. Do not expand approval to recommendations from unrelated reports.
- Before accepting security regression results from an isolated worktree, verify the generated loader resolves representative application classes into that worktree; matching dependency lockfiles do not prove a copied class map uses the intended source. For Composer projects, regenerate with `composer dump-autoload --no-scripts`, confirm a representative class path with `ReflectionClass::getFileName()`, and rerun affected checks after any wrong-source result. Use valid synthetic file formats when testing parser limits so upload MIME rejection cannot masquerade as proof that the parser stopped safely.

## Audit phases

### 1. Platform posture

Check live state with system tools:
- macOS version/build and pending updates;
- SIP, Gatekeeper, FileVault;
- application firewall and stealth mode;
- XProtect/MRT versions and scan settings;
- MDM/configuration profiles;
- screen-lock timing.

Treat disabled firewall or pending patches as exposure—not proof of compromise.

### 2. Accounts and remote access

- Enumerate local users and admin-group membership.
- Review recent logins and current sessions; distinguish local pseudo-terminals from remote source hosts.
- Inspect SSH authorized keys/config and whether ports 22/5900/3283 listen.
- Check Tailscale/other remote-access peers and flag only unknown identities/devices.
- Before transferring credentials, separate tailnet presence, TCP reachability, verified SSH host identity, account authentication, protected-file installation and receiving-application authentication. Diagnose only the layer actually tested: an unsuccessful TCP probe does not establish that Remote Login is disabled or that the host rejected the connection, because routing, filtering and timeout can produce the same result. Do not prescribe enabling a service until its state is established; request only the missing host/account evidence needed for the next verification step.

### 3. Processes and network

- Capture full command lines, parent PIDs, start times, CPU/memory.
- List listening and established TCP sockets.
- Resolve unfamiliar remote IPs and map them back to the owning process/product.
- Prioritize binaries launched from writable temporary directories, encoded shell pipelines, miners, tunneling tools, and unknown unsigned executables.
- Identify wildcard listeners (`*:`) separately from localhost listeners. Development servers exposed on `*` are attack surface even when legitimate.

### 4. Persistence

Inspect:
- user/system LaunchAgents and LaunchDaemons;
- cron and shell startup files;
- login items/background task management where authorization permits;
- input methods, Internet plug-ins, privileged helper tools.

For each item record label, program/arguments, owner, mode, modification time, signature/notarization, and whether it matches an installed product.

### 5. Application/download integrity

- Verify application and installer signatures with `codesign` and `spctl`.
- A valid known-team signature is strong provenance evidence.
- **Read the published installer before you run it, then reproduce only its download step.** Fetch the script to disk, read it end to end, and execute the checksum-verified fetch yourself instead of piping it to a shell. Published installers routinely append `export PATH` lines to `.zshrc`/`.profile`, install a second companion binary, and choose an install directory you did not intend; a manual `curl` of the release asset plus the `checksums.txt` comparison yields the identical artifact with none of that side effect. Grep the script for `https?://`, `sudo`, `chmod`, `mkdir`, `mv`, and shell-profile writes to see the full footprint in one pass.
- An `adhoc` / linker-signed binary (`codesign -dv` reports `Signature=adhoc`, `Identifier=a.out`) carries no publisher identity at all. For such artifacts the release checksums are the only provenance available, so verify them before first execution, and say so explicitly when the tool is being proposed for anything beyond a sandboxed trial.
- Route new AI/security tooling at an already-authenticated local CLI (`codex`, `claude`, `ollama`) rather than minting a metered API key, and set the tool's own hard cost ceiling (`--cost-ceiling`, budget flag) before the first run. Confirm which backend it selected from its own doctor/status output — auto-detection silently picks up subscription auth, which is the difference between a $5 pilot and an unbounded bill.
- A broken resource seal is not automatically malware: inspect changed paths. Runtime-created `__pycache__` files inside a signed bundle indicate bad packaging or mutation; recommend official reinstall rather than declaring compromise.
- Inventory high-permission browser extensions (`cookies`, `debugger`, `nativeMessaging`, `webRequest`, downloads). Flag unrecognized extensions first.

### 6. Apple malware evidence

- Confirm XProtect launch/background scans.
- Search unified logs specifically for XProtectRemediator/MRT malware, infection, or remediation outcomes.
- Generic `XPBehavioralDetection` telemetry and “Forwarding detection succeeded” are routine scan telemetry, not a malware verdict.
- If an on-demand XProtect check requires administrator authorization, report that limitation; do not substitute telemetry volume for scan results.

## Decision framework

Confirmed compromise requires evidence such as:
- unknown persistence tied to an untrusted binary;
- unauthorized account/key/profile;
- malicious process plus unexplained command-and-control traffic;
- XProtect/EDR confirmed detection;
- credential theft or unauthorized session evidence.

“No evidence found” is appropriate when independent surfaces are clean, but always state untested areas (root-only scan, memory forensics, full-disk content, EDR absence).

## Hardening actions

When explicitly requested:
- enable firewall and stealth mode through the supported macOS firewall tool;
- stop externally exposed development servers or rebind them to `127.0.0.1`;
- preserve Apple system listeners unless the user specifically disables the associated service;
- do not kill localhost-only databases/dev tools merely because they listen;
- verify firewall state and re-run the listener inventory afterward.

### Execute a checklist request in permission tiers

When the user says “do this checklist,” treat that as approval for the named hardening scope, but do not blur distinct gates. Work in this order so useful changes land before an interactive blocker:

1. **Baseline readback:** inspect OS/build, pending updates, FileVault, firewall/stealth, SIP, Gatekeeper, update policy, screen lock, sharing listeners, automatic login, backup destinations, profiles, browsers, and requested security apps.
2. **User-scoped changes:** apply reversible preferences that need no administrator authorization, then read each value back. On current macOS, known working examples include AirDrop `Contacts Only`, five-minute screensaver idle, immediate password requirement, and showing all filename extensions; see `references/macos-security-audit-checklist.md`.
3. **Administrator changes:** group firewall stealth mode, `pmset`, privileged installers, and system/network extensions into the smallest coherent authorization step. Never request or type the password; the user must approve the native macOS prompt. A canceled or unanswered prompt leaves those items `NOT YET PROVEN`.
4. **Account/recovery changes:** handle Find My, Advanced Data Protection, recovery contacts/keys, two-factor authentication, and hardware security keys separately. Do not enable Advanced Data Protection until the user confirms a recovery method, because Apple cannot recover that encrypted data.
5. **Hardware/downtime changes:** Time Machine requires a chosen disk; OS updates that restart the Mac require separate restart approval. Prefer a security/minor update on the current macOS train unless the user explicitly authorizes a major-version migration.
6. **Interactive privacy/browser review:** use supported System Settings and browser UI for privacy grants, Safari protections, Chrome cookie controls, and extension removal. Do not force-write sandboxed Safari preferences or edit a live Chrome profile’s JSON files; those writes can be rejected or overwritten.
7. **Final verification:** report each item as verified, blocked on authorization, awaiting a user decision, requiring hardware, or requiring restart. Never compress those states into “done.”

Installing an app is not activating its protection. For LuLu, verify its privileged helper/network extension is present and enabled, not merely that `LuLu.app` exists or a process launched. BlockBlock and OverSight Homebrew casks invoke privileged installers; treat a downloaded cask or copied installer as staged, not installed, until the app/helper and required login or privacy settings read back successfully.

### AI-agent process sprawl

Treat interactive agent parents, MCP watchdogs, MCP servers, kernels, language servers, and the gateway as different classes. A raw process count is not enough to decide what is stale.

Before terminating an agent parent:
1. Record PID, PPID, TTY, elapsed time, working directory, and descendant count.
2. Inspect descendants. Recent kernels, language servers, builds, or test runners are evidence of active work; preserve that parent even if it is old.
3. Preserve the current session, same-day sessions, the gateway, and any bounded delegated work still running.
4. Classify as stale only when the parent is old and has no recent working descendant beyond idle MCP/watchdog infrastructure.
5. Send `SIGTERM`, wait briefly, then re-inventory. Watchdogs may clean up asynchronously after the parent receives the signal; do not escalate to `SIGKILL` until verification shows the PID still exists.
6. Verify both remaining parent agents and MCP/watchdog totals after cleanup.

Never decide the kill set from parent PID alone. An agent's own tool shell is normally a child of the gateway, so a `ppid == <gateway>` sweep includes the process performing the cleanup and the session dies mid-sweep. Filter on command identity, exclude the current process and its ancestry, and re-read counts afterwards. Keep the oldest process per server identity — that is the one the parent registered — and expect a wrapper that is already blocked on a child to ignore `SIGTERM` and need a follow-up `SIGKILL`. Report the measured leak (children and RSS before and after), not the alert's integer: the real leak can be an order of magnitude larger than the finding states, and one duplicate set re-spawned per retry pass multiplies fast.

Before changing process-classification or startup-settling rules:
1. Add negative and preservation tests for prompt text masquerading as identity, launcher options with values, interactive subcommands, nested REPLs, and an old unsupervised process joined by a young sibling.
2. Parse execution identity separately from free text. Consume known launcher option values before identifying the script; a preload path such as `node --require /tmp/hermes /opt/mcp-server/index.js` must not override the actual server identity.
3. Parse supported global options before classifying a subcommand. Test `hermes --profile staff auth login`, `hermes -p staff auth login`, and `hermes --profile=staff auth login` as helpers, while preserving `hermes chat` and profile-prefixed chat as independent interactive sessions. Use the installed CLI's option grammar rather than assuming every option takes a value.
4. Apply startup grace only when every relevant member has a known young age: test the oldest member with `max(age)`, not the youngest with `min(age)`, so a new sibling cannot renew an old unsupervised process's grace period. Retain alert behavior for missing ages, expired grace, and persistent orphan groups.
5. Aggregate multiple reasons for the same unhealthy process group into one finding without dropping any reason; counting reasons as separate groups inflates topology alerts.
6. Run the combined regression suite and independent review. Convert only fixed-defect characterization assertions to corrected behavior; keep unrelated expected-failure pins visible and report them separately. Passing synthetic cases are acceptance evidence, not proof that an unreviewed parser is safe.

Continuous monitors should alert on unexpected agent parents, risky autonomy flags, wildcard listeners, firewall drift, credential permissions, duplicate messaging credentials across profiles, unavailable command guards, and desktop-agent local-execution helpers. Scale MCP/watchdog thresholds to the number of active agent parents plus the gateway; a fixed process threshold creates false positives during legitimate parallel work. For a periodic `launchd` job, wrap the scanner so findings are treated as report data and the wrapper exits zero; otherwise expected findings look like service crashes and can trigger misleading retries. Keep the scanner read-only, use a separate narrow permission guard for recurring `0644` sensitive files, and deduplicate recurring alerts through a redacted incident store. See `references/continuous-security-monitor.md`.

A rule that matches a literal process name must be re-verified whenever the launcher is renamed: a supervisor that moved from a Python script to a shell helper leaves the rule matching nothing, so it reports zero on every healthy group and can never pass. Treat any finding with thousands of occurrences on an unchanged host as a broken rule until proven otherwise, and check whether a test asserting the new name already exists and is failing — that means the fix was staged and never shipped.

### Frontier-model security council

For the operator and the company, keep lightweight deterministic detection continuously active and use frontier models as a separate judgment layer—not as the detector. On a daily proactive cadence and whenever a new Critical/High, authorization, credential, PII, supply-chain, remote-code, or production-exposure finding appears:

1. Verify each intended model with a live, exact-marker call; cached login status does not prove the inference endpoint accepts the session.
2. Select the strongest currently authenticated and approved models at runtime rather than freezing a model ranking in the workflow.
3. Give two independent advisory lanes only a minimal redacted evidence packet. Never include credentials, private communications, regulated records, or raw user data.
4. Restrict advisory lanes to read-only tools. One orchestrator reconciles findings against deterministic evidence, and one designated writer owns any later remediation.
5. Treat consensus as a hypothesis, not proof. Require live reproduction/readback before severity, closure, merge, or deployment claims.
6. If a frontier lane is unavailable, mark independent review `NOT YET PROVEN`; do not weaken permissions or approval gates to preserve the schedule.
7. Keep destructive actions, secret rotation, firewall or permission changes, spending, personnel decisions, and downtime behind explicit human approval.
8. Treat cron credentials as profile-scoped: a smoke under `hermes -p <profile>` does not prove a default-profile cron pin can authenticate. If the owning profile lacks the provider secret, prefer a no-agent wrapper that invokes an already authenticated subscription CLI with locks, redacted inputs, and fail-closed state over copying credentials between profiles.

Do not spend frontier calls on an unchanged empty incident queue; the deterministic monitor remains the always-on control and wakes the expensive council only when judgment adds value.

For multi-profile Hermes fleets and desktop agents, follow `references/hermes-profile-and-agent-fleet-security.md`. It covers single-gateway Telegram ownership, least-privilege profile secrets, process respawn behavior, Tirith verification, Grok/desktop-agent provenance, query-token log leakage, redacted evidence handling, and fixed-roster swarm completion discipline.

Administrator actions may trigger a macOS authorization dialog. Never request or handle the password. If the user cancels, report the action as blocked and do not claim success or loop the prompt.

## Output

1. Conclusion and confidence.
2. Evidence checked clean.
3. Suspicious findings requiring investigation.
4. Hardening gaps.
5. Immediate actions, ordered by urgency.
6. Explicit limitations.

See `references/macos-security-audit-checklist.md` for the reusable evidence checklist and interpretation notes.