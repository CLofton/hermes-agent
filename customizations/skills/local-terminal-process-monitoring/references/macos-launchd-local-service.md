# Persistent localhost services with macOS launchd

Use this recipe for a dashboard, local API, or other long-running user service that must start at login, restart after crashes, stay bound to localhost, and use the intended Hermes profile.

## LaunchAgent contract

Create `~/Library/LaunchAgents/<reverse-dns-label>.plist` with:

- `Label`: stable unique service label.
- `ProgramArguments`: absolute executable and arguments; do not depend on shell aliases. For Homebrew-managed runtimes, prefer the stable `/opt/homebrew/opt/<formula>/...` path over a versioned `Cellar` path, because `brew upgrade` removes the old Cellar directory while launchd retains the loaded executable path.
- `WorkingDirectory`: explicit working directory.
- `RunAtLoad=true` and `KeepAlive=true`.
- `StandardOutPath` and `StandardErrorPath`: persistent logs in an existing directory.
- `EnvironmentVariables`:
  - `HOME` set explicitly.
  - `PATH` including the app/venv directories plus system paths.
  - `HERMES_HOME` set explicitly for Hermes processes. This prevents a sticky active profile from routing writes into the wrong profile or emitting a profile-fallback warning.

For a private local service, bind `127.0.0.1`, not `0.0.0.0` or a LAN address.

## Install or reload

```bash
plutil -lint ~/Library/LaunchAgents/<label>.plist
launchctl bootout gui/$(id -u)/<label> 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist
launchctl kickstart -k gui/$(id -u)/<label>
```

A reload can briefly race after `bootout`: `bootstrap` may return macOS error 5 while the old registration is still disappearing. Do not switch to root or redesign the service immediately. Diagnose first:

```bash
launchctl print gui/$(id -u)/<label>
/usr/bin/log show --last 10m --style compact \
  --predicate 'process == "launchd" AND eventMessage CONTAINS[c] "<label>"'
```

If the service is absent and the plist still passes `plutil`, re-enable and retry bootstrap once:

```bash
launchctl enable gui/$(id -u)/<label>
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/<label>.plist
launchctl kickstart -k gui/$(id -u)/<label>
```

This retry pattern is validated; do not loop indefinitely. If it still fails, inspect plist ownership, executable existence/permissions, quarantine attributes, and launchd logs.

## Runtime upgrades and plist reloads

A package upgrade changes files on disk but does not replace an already running process. After upgrading a runtime or tunnel binary:

1. Read the live PID and executable image with `lsof -a -p <pid> -d txt`; a new CLI version is not proof the service is patched.
2. If `ProgramArguments` changed, run `plutil -lint`, then `bootout` and `bootstrap`. `kickstart -k` restarts the currently loaded job definition; it does not reload a modified plist and can keep retrying a removed version-pinned path.
3. Verify the replacement process resolves to the patched Cellar image, then test the exact health route and listener.

A supervised Hermes gateway may intentionally block `launchctl bootstrap` to prevent self-restart loops. Do not switch verbs to bypass that guard. Perform the authorized reload from a separate user shell. If Homebrew already removed the old binary and a `KeepAlive` service is down, a narrowly scoped compatibility symlink from the loaded old executable path to the patched `opt` executable is an emergency availability bridge only: verify with `lsof` that the new process maps the patched image, then reload the plist from a separate shell and remove the shim. Never use the shim as the permanent configuration.

## Verification gates

Do not call installation complete from a successful plist write or `bootstrap` alone. Require all of these:

1. `launchctl print gui/$(id -u)/<label>` shows `state = running` and a PID.
2. The intended environment appears in the launchd readback, especially `HERMES_HOME` for profile-aware services.
3. The exact application route returns the expected HTTP status, not merely the root path.
4. `lsof -nP -iTCP:<port> -sTCP:LISTEN` shows the intended interface, ideally `127.0.0.1:<port>`.
5. New logs show the application readiness marker and no fresh profile-fallback or bind warning.
6. Where practical, kill/restart once or log out/in later to prove `KeepAlive`/`RunAtLoad`; otherwise state that login-start persistence is configured but not reboot-tested.

## Browser-terminal verification and transport retirement

For a selected browser transport, test the actual authenticated reverse-proxy path, not only the terminal backend:

1. Verify the terminal and authentication proxy bind only to `127.0.0.1` with `lsof -nP -iTCP:<port> -sTCP:LISTEN`.
2. Require unauthenticated requests to `/`, `/token`, and `/ws` to fail; test incorrect credentials as well as missing credentials.
3. Require authenticated HTTP success and a successful same-origin WebSocket upgrade. Test a hostile Origin independently; a failed upgrade alone may be a proxy outage rather than working origin enforcement.
4. Run a harmless command with an unpredictable result marker, disconnect, then read the same shell variable after reconnecting. Assert the evaluated result, not the echoed input command. Keep raw shell output and login material out of reports.
5. Repeat over the final HTTPS hostname with normal certificate verification. Distinguish a TCP connection, TLS handshake, application authentication, and interactive session; each proves a different layer.
6. Finish with the phone-side connection. Provide the URL or host, username, private credential retrieval path, and exact session-attach command; do not place passwords in URLs or send private keys through chat.

When the user selects a different transport, retire only the services created for the superseded approach. Read `tailscale serve status --json` first and remove only the relevant route, not unrelated Serve configuration. For dedicated LaunchAgents, `launchctl bootout gui/$(id -u)/<label>` stops the service and `launchctl disable gui/$(id -u)/<label>` prevents login restart. Verify the route is gone and its listeners are absent. Preserve the tmux server/socket and verify the session with `tmux -L <socket> list-sessions`; stopping its attached web client need not terminate the shell. Keep configuration for rollback unless deletion was requested.

## Security-audit reporting

Audit the running service and optional components separately. A clean repository-root `npm audit` does not prove nested bridges or workspaces are clean. If an optional component has findings:

- state the severity and count,
- verify whether it is configured, running, or externally exposed,
- do not describe it as remediated unless its own audit passes after the change,
- avoid broad dependency upgrades when the component is dormant unless the task includes remediation.

Report active exposure first, then dormant dependency debt as a needs-attention item.
