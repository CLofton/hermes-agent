---
name: local-terminal-process-monitoring
description: Use when local terminal jobs seem stuck or need watching.
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [terminal, processes, tmux, watchdog, monitoring]
    related_skills: [scheduled-job-routing, overnight-claude-swarm]
---

# Local Terminal Process Monitoring

Class-level workflow for inspecting interactive terminal sessions, diagnosing whether CLI work is genuinely stuck, and creating quiet completion notifications for local jobs.

## When to Use

Load this skill when the user asks:
- “Can you see all my terminals?”
- “Is anything stuck / still running?”
- “What are my agents doing?”
- “Let me know when this terminal task is done.”
- Similar questions about Terminal.app, shell TTYs, `tmux`, Claude Code, Codex, Hermes, builds, or local servers.

## Core principle

**Old, sleeping, or low-CPU is not the same as stuck.** Interactive TUIs and servers spend most of their time sleeping while waiting for input or work. Diagnose from process state, foreground descendants, and recent pane output together.

This skill answers "is this job stuck?" — not "what is eating the machine?". When the question is host-wide CPU, memory, thermals, or a handed-over `.spindump`/`sample` capture, load `macos-performance-triage` instead and rank processes by CPU time; come back here only to judge whether a specific session is genuinely wedged. Note that `ps %cpu` is a lifetime average on macOS and must not be used as evidence of current load in either skill.

## 1. Inventory terminal sessions

Collect:
- Terminal emulator processes (Terminal.app, iTerm, Warp, kitty, WezTerm, Alacritty)
- Interactive TTYs from `who` and `ps`
- For each TTY: shell, foreground child, state, elapsed time, CPU, memory, command
- `tmux list-sessions` and named panes when present

Useful process fields:

```bash
ps -axo pid=,ppid=,tty=,state=,%cpu=,%mem=,etime=,command=
who
```

Exclude the probe command itself from summaries. Count unique TTYs programmatically; do not count rows by eye.

## 2. Classify each session

Use these labels:

- **Running:** foreground child exists and pane/output is changing, or CPU/I/O activity supports active work.
- **Idle/waiting:** shell or TUI is at a clean prompt with no active task. This is healthy, not stuck.
- **Blocked:** explicit prompt requires human action (login, OAuth, password, permission, payment, 2FA, unresolved choice). Surface the exact blocker.
- **Possibly stuck:** no output/progress for a task-specific threshold, no expected wait condition, and the process remains alive. Verify twice before using this label.
- **OS-stuck/stopped:** process state contains `D` (uninterruptible I/O) or `T` (stopped). This is stronger evidence than elapsed time alone.
- **Ended without verification:** process/pane disappeared, but there is no durable completion artifact. Never call this “done.”

State notes:
- `S`/`S+` usually means sleeping/waiting and is normal for shells/TTys.
- `D` or `T` warrants attention.
- If every terminal command fails with a `cd: ... No such file or directory` error that mentions no `cd` in the command itself — or the output is the *previous* command's stderr — the shell's *persistent* working directory was deleted or renamed out from under it. Most often you did it yourself: `rm -rf <dir>` while the persisted cwd was still inside `<dir>`, which leaves the session unable to start in a valid directory. It looks like a broken environment but is not. **Prevention:** before removing or recreating a directory, `cd` to a stable parent (or run the removal with an explicit `workdir` elsewhere) — never `rm -rf` the directory the shell is sitting in. **Recovery:** one command with an explicit `workdir` (e.g. `pwd && ls`), then keep passing `workdir` on every subsequent call. Do not treat this as an environment failure and do not retry the bare command three times — it loops forever until the cwd is reset.
- After any batch operation on many directories (rename, sync, cleanup), re-verify a sample by absolute path before reporting success: external writers (backup rsyncs, other agent sessions) can mutate the tree between your write and your check, and a verified-OK state can be minutes stale.
- A server with 0% CPU can be healthy while waiting for requests.

## 3. Inspect tmux and TUI state

For each relevant session:

```bash
tmux capture-pane -pt <session> -S -200
```

Read the bottom of the pane and enough history to find:
- the task prompt actually submitted,
- a completion summary or program-specific completion marker,
- an empty input prompt,
- an auth/permission/rate-limit dialog,
- ongoing activity indicators.

Do not infer completion from process age, low CPU, or a generic word in pane history.

## 4. Continue existing Hermes CLI work safely

When the operator says to keep Terminal agents going:

1. Inventory every Hermes TTY and read enough recent history to separate active work, completed work at a prompt, and blocked work. Keep completed sessions alive if requested, but do not invent follow-up work or restart completed assignments merely to make every terminal busy.
2. Continue only unfinished lanes. Preserve the original task’s writer ownership, external-write limits, release gates, and approval boundaries in the continuation prompt.
3. Prefer submitting a verified turn to the exact existing TTY. If `hermes --resume <id>` says the session is open in another window, do not retry or bypass the session lock. Either submit through that exact terminal and verify its history advances, or start one fresh continuation session with a self-contained state summary and non-overlapping scope.
4. After launching a continuation, poll once and verify the exact task text appears. Then inspect the process tree: a parent wrapper can print a final summary while a child supervisor or worker remains active, and a background handle can still say `running` because descendants or MCP servers remain alive. Report the parent session and durable child supervisor separately.
5. For graph workflows, verify board state by status (`running`, `ready`, `blocked`, `todo`) rather than parsing a huge unfiltered board dump. A ready card becoming running plus a live worker PID is stronger evidence of continuation than an agent’s promise.

## 5. “Tell me when it finishes” watchdog

For deterministic local completion checks, prefer a Hermes `cronjob` with `no_agent=true` and a script in `~/.hermes/scripts/`.

The watcher must:
1. Print **nothing** while incomplete; empty stdout means no notification.
2. Print exactly one concise notification after verified completion.
3. Persist a `notified` sentinel before printing so later ticks stay silent.
4. Treat a missing session as unknown, not success.
5. Use a finite repeat window for temporary watches when practical.
6. Pass the script as a script path, not a shell command containing arguments. If execution needs flags, put the fixed invocation in a dedicated wrapper and register that wrapper's filename; otherwise the scheduler may look for a nonexistent file whose name includes the flags.
7. Verify both the script's behavior and the scheduler entrypoint. A direct dry-run plus successful job creation proves neither scheduled execution nor delivery. Read back the registered path, then inspect the scheduled run receipt and the exact resulting state before claiming completion; never trigger a real side effect merely to test scheduling.

Before scheduling, execute the watcher against the live incomplete task and verify stdout is empty. This catches false-positive completion logic.

Treat a bounded watcher's deadline as a monitor timeout, not evidence that the underlying work made no progress. Before calling a worker stuck, compare log modification time or size twice, inspect its latest heartbeat, and verify the PID state; automatic heartbeats alone are weaker than changing logs or durable artifacts. When the user says to try again, start one fresh bounded watcher from current state rather than stopping at the timeout or stacking duplicate watchers.

See `references/tmux-completion-watchdog.md` for a reusable Python template and tests.

## 5. Relay long-running work across agent windows

After a worker times out, inventory its exact output directory and Git diff before relaunching. Recover saved artifacts and rerun the relevant checks; a transcript claiming a file was written does not prove it still exists. Continue only the unfinished stage with one writer, rather than repeating discovery or announcing another full restart. Distinguish a tested candidate, independent review, installation, and verified live behavior in every progress report; the operator expects the working deliverable, not repeated launch notices.

For unattended work that exceeds a single Hermes subagent window, use a finite recurring cron relay rather than interpreting a timeout as failure or a stopped process as completion. Each tick must inspect active workers and Git state, salvage idle/timed-out worktrees without reset, verify existing changes, and choose a non-overlapping continuation. Pair local-only overnight ticks with a one-shot morning report that independently verifies live state.

Broad “all permissions” language does not erase standing boundaries around external communications, personnel decisions, publication, or money movement; write those prohibitions into the relay prompt. See `references/hermes-cron-relay.md` for the validated pattern.

## Completion matching pitfall

Never search the entire pane for generic terms such as `done` or `completed`. Welcome banners, release notes, help text, and examples often contain those words.

Safer pattern:
- anchor on the exact task text or a unique task ID,
- inspect only output occurring after that anchor,
- require the program’s real completion marker or a durable output artifact,
- test both an incomplete fixture and a complete fixture.

If the program supports an exit code, output file, commit, test result, or API status, prefer that durable signal over terminal text.

## Closing a terminal client

For a request to close a named app, inventory exact running application names first; Termius and Terminal.app are separate targets. Quit only the requested client gracefully, then recheck the exact application process after shutdown has had time to finish. An immediate post-quit listing may still show a process that is exiting; recheck before escalating to force termination. Do not kill its remote jobs, tmux server, SSH service, or unrelated terminal windows unless requested.

Treat delayed discovery output as evidence from before the quit, not proof the app reopened. Prefer the later explicit post-action verification and absorb stale completion notices silently when they add no new state.

## User-requested pause and resume

Treat a pause as a reversible stop to autonomous execution, not deletion or completion. For a request to stop computer/browser control:

1. List jobs and correlate the current execution ledger, dispatch time, job instructions and recent tool activity. Do not choose the job merely because its failure notice appeared last; browser permissions identify a candidate, not proof of desktop activity. A job can still show `state=scheduled` and yesterday's `last_run_at` while a current execution is running.
2. Once the target is identified, save its prior state and pause that exact schedule immediately, before deeper diagnosis. Leave unrelated jobs, security monitoring, the user's browser and the messaging gateway untouched. If attribution remains ambiguous, state that uncertainty rather than claiming a culprit was proven.
3. Inspect and stop the current execution separately. Do not treat a session-local process list as a complete inventory: a cron agent can run inside the gateway without a separate worker PID. Inspect an `osascript` process's actual command before terminating it; it may supervise the gateway rather than manipulate the desktop.
4. Verify both the persisted pause and the exact execution's terminal state. Report these two results separately; never mark work complete to silence it. Keep the final confirmation short: job name, active-run outcome, future-run state and preserved scope.

For version-checked in-flight cancellation and its evidence gates, use `references/hermes-cron-relay.md`. Preserve the prior states in a local resume manifest, but never restore an old active execution claim when resuming.

Report the layers independently: pausing schedules does not terminate an in-flight worker, disabling dispatch in a config file does not prove a running dispatcher reloaded it, and an empty task-board running column does not prove there are no standalone agents. If a gateway refuses to stop itself, respect the lifecycle guard and give the separate-terminal stop command rather than bypassing it through detached scripts. State any remaining live surface and that scheduled security coverage is paused when applicable.

Require explicit resumption after an owner pause. A later unrelated task or delayed process-completion notice does not authorize restarting paused schedules or swarms. Restore only the recorded scope when resumption is approved.

## Messaging gateway services

A silent Hermes Telegram/Slack gateway may be a process problem, a platform polling problem, or an unloaded service. Check the service manager and fresh platform activity before choosing a recovery action. A cleanly stopped launchd job is not a zombie and should be started, not repeatedly restarted.

See `references/hermes-gateway-service-recovery.md` for the macOS launchd diagnostic sequence, recovery decision tree, and readback gates.

## Persistent localhost services on macOS

For dashboards and local APIs that must start at login and restart after crashes, use a user LaunchAgent with explicit `HOME`, `PATH`, and profile-aware `HERMES_HOME`. Verify launchd state, the exact HTTP route, loopback-only binding, and fresh logs before reporting success. Treat a one-time bootstrap error immediately after `bootout` as a diagnose-then-bounded-retry case, not a reason to escalate straight to root.

See `references/macos-launchd-local-service.md` for the plist contract, recovery sequence, verification gates, and security-audit reporting rules.

## Reporting format

Lead with exceptions:
- 🔴 **Stuck/failed** — exact process/session and evidence
- 🟡 **Blocked** — exact action needed
- 🟢 **Healthy** — running or idle counts

State what can and cannot be inferred. Offer to inspect or terminate sessions, but do not kill anything without explicit user direction.

## Phone terminal access

Establish the viewing device and target before installing anything: local Terminal windows, phone access, agent logs, and an interactive shell are different deliverables. Do not satisfy a phone-access request by opening Terminal.app on the Mac. Distinguish viewing output from interactive control; a timed-out clarification is not consent to write access, while an explicit request for interactive control should not trigger the same question again.

For the operator's interactive phone access, prefer his selected Termius client and inspect the Mac's SSH prerequisites before building a browser terminal. The phone needs the client; the Mac needs an SSH server, not a second Termius installation. Preserve existing tmux sessions when changing transports. Do not describe an SSH connection recipe as completed until authentication, a command, and reconnection have actually succeeded from the phone.

Make the phone handoff usable without access to a laptop-only credential file: provide the verified host, port, username, trusted host-key fingerprint, and exact tmux attach command together; direct the user to enter authentication privately in the selected client. Do not paste a password/private key into chat, transfer it to a cloud vault without approval, or call a service ready while the user has no usable login path. Distinguish a new persistent shell from control of existing agent terminals, because creating a tmux session does not migrate running processes into it.

Verify network scope separately from login scope: a shared tailnet is not owner-only, and macOS Remote Login is not automatically restricted to Tailscale interfaces. Check user restrictions and reachable listeners; do not claim tailnet-only access merely because the client uses a Tailscale address. Verify the SSH host-key fingerprint through a trusted local read before asking the user to accept it. Keep passwords/private keys out of chat and command arguments.

Use a browser terminal only when that transport is selected. Keep its backend loopback-only behind authentication and private HTTPS; never proxy an auth-free dashboard directly to the tailnet. See `references/macos-launchd-local-service.md` for browser-terminal verification and safe transport retirement.

For interactive access, ttyd `-W -O` behind Caddy `basic_auth` can attach to an isolated `tmux -L <socket> new-session -A` session. Keep ttyd and Caddy bound to 127.0.0.1, retain password hashes in a 0600 Caddyfile, disable Caddy admin, and never put passwords in argv or URLs. Verify unauthenticated HTTP/token/WebSocket rejection, hostile-Origin denial, actual command execution and same-shell reconnection before claiming the local endpoint works. ttyd may close hostile-Origin upgrades, which Caddy translates to 502; require ttyd's explicit origin-denial log plus a successful allowed-origin control, not the 502 alone.

Treat Tailscale Serve enablement, TLS certificate issuance, authenticated WebSocket access, and phone-side control as separate verification gates. A successful Serve command is configuration evidence, not working HTTPS. Diagnose a TLS stall with fresh Tailscale certificate/ACME logs rather than disabling certificate validation or creating a public tunnel. Report local tests separately from phone tests; do not call phone access live until the phone connection succeeds. A persistent tmux session does not attach to existing Terminal.app tabs or arbitrary agent PTYs. LaunchAgent persistence is configured, not reboot-tested, until exercised across login/restart.

## Safety and privacy

- Process command lines may contain sensitive arguments. Redact tokens, passwords, API keys, and private URLs.
- Never type passwords, complete OAuth/2FA, or approve payments on the user’s behalf.
- Do not continuously monitor without the user requesting a watch.
- Do not declare success until the completion signal is verified.
