---
name: hermes-update-troubleshooting
description: Use when a Hermes update fails, stalls, migrates plugins, or leaves services stale.
---

# Hermes update troubleshooting

`hermes update` does: git pull → Python deps → refresh lazy backends → **npm install (root)** → **npm install + build (web/)** → sync skills → config migration. When it prints "Update partially complete — Node.js dependencies did not refresh", the Python side is done but the Node side didn't finish, and the dashboard / TUI web UI will be stale or broken.

Load this skill when:
- User says: hermes update failed / broke / partially complete / dashboard broken after update / web UI won't load / TUI stale
- Output contains: `EBADENGINE`, `Unsupported engine`, `Web UI npm install failed`, `Node.js dependency refresh did not complete`
- User is on macOS and `node -v` returns an odd major version (21, 23, 25, 27…)
- Every `hermes` command prints "⚠ A previous `hermes update` pulled new code but did not restart running gateways" after an update
- Update exited 1 / receipt says `outcome: "partial"` with "Planned runtimes the restart phase never touched"
- Output says "Local changes detected — stashing before update…" followed by `restore hit conflicts`, or "stashed N local modification(s) and did NOT restore them" — see failure mode 8
- The update **crashed with a traceback** (not a clean partial receipt) during post-swap cleanup: `AttributeError: module '...' has no attribute '...'` or `ImportError: cannot import name '...' from 'utils'` — see failure mode 4

## Failure modes we've actually hit (1–8)

### 1. Odd-numbered Node (v21, v23, v25, v27…) → EBADENGINE cascade

Most JS packages in the Hermes tree (and npm itself) declare `engines: { node: "^22 || ^24 || >=26" }`. If Homebrew has installed an odd Node release, EVERY npm invocation fails with:

```
npm error code EBADENGINE
npm error Not compatible with your version of node/npm
npm error Required: {"node":"^22.22.0 || ^24.15.0 || >=26.0.0"}
npm error Actual:   {"node":"v25.9.0", ...}
```

**Do NOT** try `npm install -g npm@latest` — that also has an engines requirement and will also fail. **Fix the Node version, not npm.**

Fix on macOS/Homebrew:
```
brew install node@24
brew unlink node
brew link --overwrite --force node@24
node -v   # should print v24.x
```

`node@24` is keg-only, so the `link --overwrite --force` step is required — without it `node -v` will still show the old version because the `node` formula's symlinks shadow `node@24`.

Only fall back to a specific compatible npm (`npm install -g npm@11.17.0`) if the Node bump itself is blocked for some reason. Fixing Node is always the cleaner path.

### 2. Autostash short-circuit — re-running `hermes update` skips Node deps

If the first `hermes update` failed at the npm step, git has already fetched + pulled the new commits. Running `hermes update` again produces:

```
→ Local changes detected — stashing before update...
→ Restoring local changes...
✓ Already up to date!
```

**This is a lie w.r.t. Node deps.** The updater sees git is current and exits before re-running the npm install steps that failed. The web UI stays broken.

Fix — run the Node steps manually:
```
cd ~/.hermes/hermes-agent && npm install
cd ~/.hermes/hermes-agent/web && npm install && npm run build
```

If `web/node_modules` is in a mixed state from a partially-failed install, `rm -rf ~/.hermes/hermes-agent/web/node_modules` before the reinstall.

Verify web build succeeded by checking `~/.hermes/hermes-agent/hermes_cli/web_dist/assets/` has fresh JS bundles (mtime = now).

### 3. Partial receipt — dashboard unaccounted, fleet-restart marker lingers

The update completes the code/dep swap but exits 1 and prints "⚠ Planned runtimes the restart phase never touched" — usually a manually-launched dashboard (`restart_via: respawn-argv`). Consequences:

- A breadcrumb `~/.hermes/fleet_restart_pending` remains, and **every subsequent `hermes` command prints the "pulled new code but did not restart running gateways" warning** — the check short-circuits on the marker's mere existence and never inspects the actual fleet.
- The receipt (`~/.hermes/logs/update_receipts/latest.json`) records `outcome: "partial"` even when code, deps, and all gateways are fine.

Fix — verify the fleet first, remove the marker second (never the reverse):
1. Every gateway's `gateway_state.json` (`~/.hermes/gateway_state.json` and `~/.hermes/profiles/<p>/gateway_state.json`) stamps `code_sha` / `code_version` — compare against `git rev-parse HEAD` in `~/.hermes/hermes-agent`.
2. Dashboard: check the process start time is post-update and that the served frontend matches `hermes_cli/web_dist/assets/`. The port can change across updates — read it from the launchd job PID (`launchctl list | grep hermes` + `lsof -iTCP -sTCP:LISTEN -P | grep <pid>`), never assume a fixed port. With auth enabled, `curl http://127.0.0.1:<port>/` returns a 302 to the login flow instead of the app shell — a 302 to `/auth/login` whose login page follows to 200 counts as healthy (compare the served `assets/index-*.js` name against the build dir only when auth isn't in the way).
3. Only when all green: `rm ~/.hermes/fleet_restart_pending`.

Note: the updater often restarts the dashboard itself (`respawn-argv` with the recorded args) — verify via the new PID's start time, not the old PID from the plan.

Multi-profile fleets: gateways run per profile (`hermes -p <p> gateway stop/start`; launchd units `ai.hermes.gateway-<p>`). Restart and verify EVERY profile's gateway, not just default — a sibling left behind serves stale `sys.modules`. In a multiplexed fleet (`gateway.multiplex_profiles` on), per-profile gateways are often redundant: when the update log says "Stopped N manual gateway process(es) / Restart manually", run `hermes -p <p> gateway status` for each profile BEFORE starting anything — if it answers "Gateway is running via the default-profile multiplexer", there is nothing to restart (the profile's `gateway_state.json` may still carry a stale pre-multiplex `code_sha` + dead PID — that file is a leftover, not a live gateway). Confirm the profile appears in `served_profiles` in `~/.hermes/gateway_state.json`; starting a standalone `hermes -p <p> gateway run` for an already-multiplexed profile creates a duplicate adapter connection, not a fix.

### 4. Mid-swap stale-`__pycache__` race — the update CRASHES during post-swap cleanup, fleet never restarts

A big swap (a facade/sibling refactor that moves symbols between modules) can leave the RUNNING pre-pull process holding a mixed `sys.modules` graph: the new `dashboard_procs` calls a symbol the old in-memory `main_dashboard` doesn't expose yet. The run **crashes with a traceback** in the post-swap phase (`_finish_dashboard_update_cleanup` / `_kill_stale_dashboard_processes`) and again at atexit:

```
AttributeError: module 'hermes_cli.main_dashboard' has no attribute '_loaded_launchd_backend_jobs'
...
ImportError: cannot import name 'file_signature' from 'utils'
```

**This is NOT a broken checkout — both symbols exist on disk.** The crash is a stale-`__pycache__` / stale in-memory module artifact of the swap itself. Consequences: the code swap completed, but the fleet restart was never reached, so (a) every gateway is still stamped at the pre-update `code_sha`, and (b) `~/.hermes/fleet_restart_pending` is left behind.

**Distinguish from a genuine half-applied checkout** before touching anything:
- Symbol exists on disk but the run crashed → stale-module race → fix below.
- Symbol actually missing on disk (a fresh interpreter also can't import it) → real half-pull; re-`git pull` / restore, NOT the pycache fix.

Fix:
```
# 1. Prove the on-disk code is consistent in a FRESH interpreter (never the crashing process):
cd ~/.hermes/hermes-agent && venv/bin/python -c "import hermes_cli.main_dashboard as m, utils as u; print(hasattr(m,'<new_symbol>'), hasattr(u,'<new_symbol2>'))"
# 2. Clear the stale bytecode for each swapped facade/sibling:
rm -f hermes_cli/__pycache__/<mod>.cpython-311.pyc
# 3. Re-run the update. Code is already current, so it short-circuits the swap ("Already up to date")
#    but RUNS the pending fleet restart the crashed run never finished → exit 0, marker cleared.
hermes update
```

**This re-run is the fix, not a no-op** — unlike failure mode 2, where re-running short-circuits and does NOT redo the pending Node deps. The deciding factor is what the pending work is: if `~/.hermes/fleet_restart_pending` exists AND the gateway stamps are stale, re-running picks up the fleet restart and completes it; if the only pending work is Node deps (no marker), re-running is a lie and you must run the npm steps by hand. Verify the fleet afterward exactly as in mode 3 (all stamps = `git rev-parse HEAD`, fresh PIDs, marker gone).

The update completes the code/dep swap but exits 1 and prints "⚠ Planned runtimes the restart phase never touched" — usually a manually-launched dashboard (`restart_via: respawn-argv`). Consequences:

- A breadcrumb `~/.hermes/fleet_restart_pending` remains, and **every subsequent `hermes` command prints the "pulled new code but did not restart running gateways" warning** — the check short-circuits on the marker's mere existence and never inspects the actual fleet.
- The receipt (`~/.hermes/logs/update_receipts/latest.json`) records `outcome: "partial"` even when code, deps, and all gateways are fine.

Fix — verify the fleet first, remove the marker second (never the reverse):
1. Every gateway's `gateway_state.json` (`~/.hermes/gateway_state.json` and `~/.hermes/profiles/<p>/gateway_state.json`) stamps `code_sha` / `code_version` — compare against `git rev-parse HEAD` in `~/.hermes/hermes-agent`.
2. Dashboard: check the process start time is post-update and that the served frontend matches `hermes_cli/web_dist/assets/`. The port can change across updates — read it from the launchd job PID (`launchctl list | grep hermes` + `lsof -iTCP -sTCP:LISTEN -P | grep <pid>`), never assume a fixed port. With auth enabled, `curl http://127.0.0.1:<port>/` returns a 302 to the login flow instead of the app shell — a 302 to `/auth/login` whose login page follows to 200 counts as healthy (compare the served `assets/index-*.js` name against the build dir only when auth isn't in the way).
3. Only when all green: `rm ~/.hermes/fleet_restart_pending`.

Note: the updater often restarts the dashboard itself (`respawn-argv` with the recorded args) — verify via the new PID's start time, not the old PID from the plan.

Multi-profile fleets: gateways run per profile (`hermes -p <p> gateway stop/start`; launchd units `ai.hermes.gateway-<p>`). Restart and verify EVERY profile's gateway, not just default — a sibling left behind serves stale `sys.modules`. In a multiplexed fleet (`gateway.multiplex_profiles` on), per-profile gateways are often redundant: when the update log says "Stopped N manual gateway process(es) / Restart manually", run `hermes -p <p> gateway status` for each profile BEFORE starting anything — if it answers "Gateway is running via the default-profile multiplexer", there is nothing to restart (the profile's `gateway_state.json` may still carry a stale pre-multiplex `code_sha` + dead PID — that file is a leftover, not a live gateway). Confirm the profile appears in `served_profiles` in `~/.hermes/gateway_state.json`; starting a standalone `hermes -p <p> gateway run` for an already-multiplexed profile creates a duplicate adapter connection, not a fix.

### 5. Multiplex migration stuck "interrupted" — gateway restarted on EVERY update, warning "has not confirmed serving" (2026-09-26, macOS/launchd shim hosts)

Symptoms: after an update (or `hermes gateway migrate --multiplex`), the gateway IS up and serving everything (state file: `gateway_state: running`, full `served_profiles`, platforms connected, cron ticking), but the output ends with "⚠ Migration applied, but the default gateway has not confirmed serving: <all profiles>" and "Re-run hermes gateway migrate --multiplex once it is healthy". `~/.hermes/gateway_migration.json` exists. Re-running the migrate command SIGTERMs the healthy gateway AGAIN and fails the same way — it is NOT a boot race, stop re-running.

**Upstream: NousResearch/hermes-agent #124120** (canonical; #123881 dup; original report #124029 closed). Five independent repros (2026-09-26, incl. a contributor's 70-profile macOS host). 8 candidate fix PRs; #127302 most complete as of 2026-09-29. Check for a merged fix before re-doing the manual workaround — if `looks_like_gateway_runtime_command_line` accepts the shim cmdline on current HEAD, the migration confirms normally and no workaround is needed.

Root cause (verified 2026-09-26 on this Mac): the standard launchd launch chain is `osascript → sh shim (.hermes/bin/hermes) → python3 -I -c <bootstrap> --run-module hermes_cli.stderr_timestamp → python3 -I -c <bootstrap> gateway run --external-supervisor`. The canonical identity matcher `gateway/status.py::_gateway_command_subcommand` REFUSES all `python -c <src>` cmdlines BY DESIGN (#107002: trailing argv is inline-source data, not process identity). So `looks_like_gateway_runtime_command_line(live_cmdline)` is False for the real gateway process, and in `_record_matches_live_gateway_pid` the cmdline gate runs BEFORE the `_host_gateway_serves_home` escape hatch (which WOULD pass — the host_attach registry proves the PID serves the home). Net: `live_default_gateway_pid()` → None, `recorded_served_profiles()` → None, the 90s `_wait_for_served` can never pass, the manifest is never cleared, and `plan.interrupted` stays True forever.

Churn mechanism: `gateway_migrate.py::maybe_auto_migrate_after_update` treats a manifest on disk as `resuming=True` — so EVERY future `hermes update` re-applies the migration (SIGTERM + restart + failed 90s confirm) on an already-converged host. That's why the warning appeared mid-update.

Diagnosis in <2 min (fresh venv interpreter):
```bash
cd ~/.hermes/hermes-agent && venv/bin/python -c "
import json, pathlib
import gateway.status as gs
home = pathlib.Path.home()/'.hermes'
rec = json.loads((home/'gateway_state.json').read_text())
pid = rec['pid']
cl = gs._read_process_cmdline(pid)
print('live:', pid, '| looks_like_runtime:', gs.looks_like_gateway_runtime_command_line(cl))
print('host_serves:', gs._host_gateway_serves_home(pid, home))
"
# looks_like_runtime=False AND host_serves=True = this bug, confirmed.
```

Fix — converge the host by hand (do NOT patch core matcher code locally; upstream fix is the right channel; do NOT delete the manifest without this verification first):
1. Prove functional convergence: state file `gateway_state=running` + `served_profiles` ⊇ all profiles + `launchctl list` shows only the default `ai.hermes.gateway` unit (no per-profile units left) + gateway log shows platforms connected + cron ticking all profiles.
2. `mv ~/.hermes/gateway_migration.json ~/.hermes/logs/gateway_migration.json.converged-$(date +%Y%m%d)` (it records no installed units to restore — the migration's goal state is already achieved; a future fresh apply writes its own manifest before its first destructive step, so nothing is weakened).
3. Verify: `hermes gateway migrate --multiplex --dry-run` must print "✓ The default gateway is already multiplexed (flag on)." — then `plan.interrupted` is False, `already_multiplexed` is True, and update hooks no-op.

Pitfall: the plan table showing `gateway pid: -` for a launchd gateway is NORMAL (launchd gateways may have no gateway.pid file) — don't mistake it for a dead gateway; the state file's pid + `ps` is ground truth.

### 6. Oversized state.db: separate retention from compaction

A large `state.db` warning does not by itself prove auto-pruning is disabled. Retention bounds future growth; FTS compaction reclaims existing disk space.

Procedure:
1. Read the effective profile config and verify `sessions.auto_prune`, `retention_days`, `vacuum_after_prune`, and `min_interval_hours` before changing anything. Do not repeat a generic Doctor recommendation as fact when the setting is already enabled.
2. Run `hermes sessions stats` and record session count, message count, and database size.
3. If auto-prune is disabled, enable it with an explicit retention policy and validate the config. If already enabled, leave it intact and report that retained, active, pinned, or otherwise ineligible sessions can still keep the database large.
4. Use `hermes sessions optimize-storage --yes` only for physical compaction. First run it without `--force`; its live-writer refusal is a safety gate, not an error to bypass.
5. If it lists gateway, Desktop, cron, or agent holders, schedule a maintenance window and stop every listed writer before retrying. Never use `--force` against a live multi-profile fleet: rewriting under active writers can make all agents refuse turns.
6. Verify with `hermes sessions stats` and `hermes doctor`. Treat a size-only warning as informational when the retention policy is already active and health checks pass.

### 7. Large backup stalls and core-to-plugin migrations

A release upgrade can spend longer creating the full backup than updating code when `state.db` is several gigabytes. Do not blindly rerun the same full backup after a timeout.

Procedure:
1. Read the tail of `~/.hermes/logs/update.log` and confirm whether the updater already wrote a named pre-update snapshot.
2. Confirm no update process is still running and the checkout/version did not change.
3. Only after both checks, rerun the update with `--no-backup`; the existing snapshot is the rollback point. Prefer the stable release channel when a plugin declares a minimum Hermes version:
   ```bash
   hermes update --channel stable --no-backup --yes --no-gateway-restart
   ```
4. Read the complete update output before restarting. When a provider or integration moved from core into a plugin, install and enable that plugin for every profile that was using it **before** the restart; otherwise the restart turns a successful code upgrade into a memory/observability outage.
5. Verify `hermes --version`, `hermes config check`, and each migrated plugin with `hermes plugins doctor <name>` plus `hermes plugins list`.
6. A gateway process cannot safely restart itself. If the command is blocked from inside the gateway, stop retrying aliases such as `launchctl kickstart`; finish all pre-restart verification and ask the user to send `/restart` or run `hermes gateway restart` from an external shell. The block exists because SIGTERM propagates to the command child.

Pitfalls:
- **Never treat a timed-out update call as proof that the update failed or succeeded** — the update can be in backup, swap, dependency, or restart phase; branch from the log and live process state.
- **Do not use `--no-backup` merely to save time** — use it only after a fresh rollback snapshot is proven or the user explicitly accepted no backup.
- **Do not restart before repairing reported core-to-plugin migrations** — an old in-memory gateway can hide the missing plugin until restart, making the break appear later.

### 8. Agent-driven update from inside the gateway + stash-restore conflicts

When the agent itself runs inside the gateway it is updating, do the swap without a self-restart and hand only the last step to the user:

```bash
hermes update --check          # gap
hermes update --plan           # which services will be restarted
cd ~/.hermes/hermes-agent && git diff > ~/.hermes/logs/pre-update-backups/local-changes-$(date +%Y%m%d-%H%M).patch
hermes update --yes --no-gateway-restart 2>&1 | tee ~/.hermes/logs/update-run-$(date +%Y%m%d-%H%M).log   # background + notify + persist_on_release
```

- `--no-gateway-restart` is the correct choice here: the updater's `launchctl kickstart -k` would SIGTERM the process running the update, and the turn's answer would never reach the user. The receipt then records `outcome: "partial"` with skip reason `--no-gateway-restart: deferred, marker kept` — that is expected, not a failed swap. Confirm it succeeded by comparing `pre_update.sha` / `post_update.sha` and `hermes --version` against `git rev-parse HEAD`.
- Restart the dashboard yourself — it is a sibling launchd service, so `launchctl kickstart -k gui/$(id -u)/ai.hermes.dashboard` is safe mid-turn. Verify the NEW PID's start time is post-build (`ps -o lstart= -p <pid>`), the port still listens (`lsof -iTCP -sTCP:LISTEN -P -n -a -p <pid>`), and `curl` returns 302 to the login flow whose page is 200.
- The gateway is the one runtime you must not restart yourself. End the turn with the verified result and ask the user to send `/restart`.

**Stash-restore conflicts reset the WHOLE tree.** When any parked file conflicts, the updater reports `restore hit conflicts`, lists the conflicting files, and resets the working tree to clean — edits that would have applied cleanly are dropped too, and the receipt shows `local_changes_stash: ok false, detail "parked: <ref> (restore hit conflicts)"`. Re-apply only the edits you actually want, one file at a time, then prove them on the new base:

```bash
cd ~/.hermes/hermes-agent
git diff "<stash-ref>^1" "<stash-ref>" -- <path> > /tmp/one.patch
git apply --3way /tmp/one.patch
venv/bin/python -m pytest <the accompanying test file> -o 'addopts=' -q
```

- Use the `<ref>^1 <ref>` form: `git stash show -p <ref> -- <path>` fails with "Too many revisions specified" because a stash is a merge commit.
- Compare against upstream before re-applying anything: a long gap usually rewrites the file, and force-applying an old local patch can silently revert newer upstream logic. Read the hunk and confirm the local intent is still absent from `HEAD`.
- Expect the conflicting set to be lockfiles and `package.json` engine pins. Check whether upstream's own `engines` already accept the installed Node major before restoring them — usually they do, so leave them parked and tell the user, rather than reintroducing drift.
- Keep the stash ref until the user decides; dropping it destroys the only copy of the parked edits. Extract every parked edit to a `.patch` under `~/.hermes/logs/` *before* the update, because git refs are the only surviving copy once the tree is reset.

## Standard playbook (copy/paste order)

```
# 1. Check Node version. If odd (21/23/25/27), fix first:
node -v
brew install node@24 && brew unlink node && brew link --overwrite --force node@24

# 1b. Save the current commit as a backup ref before the pull:
cd ~/.hermes/hermes-agent && git branch -f pre-update-backup-$(date +%Y%m%d) HEAD

# 2. Run the update. First check the gap with `hermes update --check`:
#    if it is far behind (hundreds of commits), run in the background with
#    notify + tee to a log (npm install + web build exceed foreground timeouts):
hermes update 2>&1 | tee ~/.hermes/logs/update-run-$(date +%Y%m%d).log

# 3. Verify the receipt / "partially complete" — if Node deps did not refresh (or a previous partial attempt caused the "Already up to date" short-circuit), force the Node side:
cd ~/.hermes/hermes-agent && npm install
cd ~/.hermes/hermes-agent/web && npm install && npm run build

# 4. Offer the storage optimization if it prompted (~60% state.db reclaim):
hermes sessions optimize-storage
```

## Preflight and verification safeguards

- Run `hermes update --help` and `hermes update --plan` before updating; current updaters may restart services and migrate configuration/sync bundled skills across profiles. Check that scope against the user's authorization before execution.
- Inspect `hermes --version` and git status for carried commits as well as uncommitted changes. Autostash preserves uncommitted edits, NOT necessarily local commits: the updater can reset divergent history to origin/main. Record the old commit ID and preserve it with a backup ref before updating; do not promise all customizations survive.
- After updating, verify `hermes --version`, `hermes update --check`, running-service versions with `hermes update --plan`, and the dashboard HTTP response. Read the full update log to confirm dependency installation and web build actually ran.
- The authoritative post-update checks are the per-profile `gateway_state.json` `code_sha`/`code_version` stamps and `~/.hermes/logs/update_receipts/latest.json` (steps, skips WITH reasons, `runtime_outcomes`). `hermes gateway status` warnings are advisory; the stamps are ground truth.
- If a carried commit disappears, inspect `git show --stat <old-id>` and `git cherry HEAD <old-id>`; report the precise lost customization. Do not blindly reapply an old compiled bundle over new upstream code.

## Pitfalls

- **Don't `npm install -g npm@latest` when EBADENGINE fires** — modern npm has the same engines block; you'll get the same error a level up. Fix Node.
- **`brew link node@24` without `--overwrite --force` is a no-op** when the main `node` formula is still linked. You'll think you switched but `node -v` will show the old version.
- **The "Already up to date!" message is not proof the update succeeded** if the previous run failed at npm. Always check: did the current run actually print the "→ Updating Node.js dependencies..." block? If not, run the Node steps manually.
- **`npm audit` warnings (7 vulns etc.) after a clean install are upstream noise**, not a Hermes bug. Not blocking. Only run `npm audit fix` if the user asks.
- **`hermes sessions optimize-storage` is a foreground long-running command** with an interactive y/N prompt. Pipe `yes |` and run it in the background with notify_on_complete if you're driving it programmatically.
- **An `AttributeError: module '...' has no attribute '...'` / `ImportError: cannot import name '...'` traceback during a swap is usually a stale-`__pycache__`/stale-module race, not a broken checkout** — the symbols are on disk. Prove it in a FRESH venv interpreter (`venv/bin/python -c "import ...; print(hasattr(...))"`), `rm -f` the stale `.pyc` for the swapped modules, and re-run `hermes update` to finish the pending fleet restart. Don't re-pull or "fix" on-disk code that's already correct.
- **Do not diagnose the "pulled new code but did not restart running gateways" warning from the marker alone.** It can be driven by `~/.hermes/fleet_restart_pending` OR by a live gateway whose `gateway_state.json` `code_sha` trails `git rev-parse HEAD`. Check both. If the state is `draining` and the gateway log says a SIGUSR1 restart is deferred for an active work unit, do not send repeated restart signals; let the bounded drain finish, then verify a new PID, matching code stamp, fresh platform-health lines, and normal `running` state. Remove a leftover marker only after those checks.
- **A custom local patch that did not itself conflict can still vanish after an update** — the restore is all-or-nothing, so one conflicting lockfile resets every parked edit. Re-apply per file from the stash (`git diff <ref>^1 <ref> -- <path>`), run its test, and report which edits you restored versus left parked; see failure mode 8.
- **Exit code 1 / `outcome: "partial"` is not always a failed update** — read the receipt: if the only failing entry is a manually-launched serve/dashboard runtime marked `unaccounted`, the code swap itself succeeded. Verify that runtime directly instead of re-running the update (which will short-circuit at "Already up to date" — see failure mode 2).
- **The trailing "Refreshing cua-driver" step can fail without failing the update** — re-run the exact install one-liner the update output prints. If the installer then reports the prebuilt release failing signature verification, that is an upstream release defect: the installer correctly keeps the previous binary, so verify the old one still works (`cua-driver --version`) and report it as upstream, not a local failure. Never "fix" this by weakening verification.
