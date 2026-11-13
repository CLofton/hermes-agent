---
name: browser-automation-hardening
description: "Use when installing, auditing, or hardening Playwright/browser automation — detects vulnerable bundled Chromium and enforces sandboxed real-Chrome launches."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [security, playwright, browser, chromium, sandbox, cve, audit]
    related_skills: [dependency-security-audits, scripted-cron-verification]
---

# Browser Automation Hardening

Playwright's bundled Chromium moves only when Playwright ships a release, so a
"latest" install can still carry a Chromium that is weeks behind Chrome stable.
Its `chromiumSandbox` also **defaults to false**, which turns a browser RCE into
code running as the user. This skill keeps the local stack audited and forces
the safe launch configuration.

## When to use

- Installing or upgrading Playwright, Puppeteer, `@playwright/test`, or `@playwright/mcp`
- Writing any script or agent that drives a browser against the open web
- A security advisory lands about Chrome/Chromium/Playwright
- Before shipping a repo that vendors a browser into CI or a container

## Contract

1. **Bundled Chromium is for localhost and trusted pages only.** For anything
   that can reach the open web, launch real Chrome with the sandbox on:

   ```js
   const browser = await chromium.launch({ channel: 'chrome', chromiumSandbox: true });
   ```

   Python: `p.chromium.launch(channel="chrome", chromium_sandbox=True)`.

2. **Never ship `chromiumSandbox: false`** except for a throwaway container with
   no credentials and no mounted home directory.
3. **Pin tools.** `npx @playwright/mcp@latest` runs whatever was published most
   recently; pin an explicit version instead. `@playwright/mcp` must be >= 0.0.40
   (CVE-2025-9611, DNS rebinding of local MCP tools).
4. **Browsing agents run without real access.** Non-root container or VM, no
   `.env`, no SSH keys, no mounted `$HOME`, throwaway profile.
5. **Playwright's MCP server is not a security boundary** — treat every page it
   loads as attacker-controlled when the agent can choose URLs.

## Audit procedure

Run the deterministic auditor. It is read-only and covers node installs across
repos, Python installs, the shared browser cache, installed Chrome, and config
smells in source.

```sh
python3 ~/.hermes/skills/security/browser-automation-hardening/scripts/audit_browser_stack.py \
  --roots ~/Downloads,~/projects --max-depth 4
```

- `VERDICT: FAIL` → some install is below the policy floor, or no current
  chromium build exists in the cache. Exit 1.
- `VERDICT: WARN` → versions are acceptable but something advisory needs eyes
  (e.g. bundled Chromium lags installed Chrome).
- `--json` for machine consumption, `--quiet` for the verdict line alone,
  `--no-smells` to skip the source scan when it is slow.

Tests: `python3 ~/.hermes/skills/security/browser-automation-hardening/tests/test_audit.py`

## Upgrading (macOS, this machine)

System Python is 3.9, and Playwright >= 1.64 requires >= 3.10 — so `pip install -U
playwright` silently stays on 1.60. Use the dedicated venv:

```sh
python3.13 -m venv ~/.hermes/venvs/playwright          # once
~/.hermes/venvs/playwright/bin/pip install -U playwright
~/.hermes/venvs/playwright/bin/playwright install chromium   # fills shared cache
```

**The version that actually matters is the one Hermes imports, not the one `pip`
reports.** On this Mac that is the lease-managed uv env:
`~/.hermes/installs/<id>/environments/<id>/venv`. It has **no pip**; use uv, then
prove it from that interpreter:

```sh
PY=~/.hermes/installs/7c1b4aa2e21cae5b/environments/a613d97a3aa0489ebb22ad105684b8cb/venv/bin/python
uv pip install --python "$PY" playwright==1.64.1
$PY -c "import importlib.metadata as m; print(m.version('playwright'))"   # playwright has no __version__
$PY -m playwright install chromium                                        # no-op when 1248 is cached
```

Smoke it end to end before reporting: `p.chromium.launch(headless=True).version`
(bundled) and `p.chromium.launch(headless=True, channel="chrome").version`
(installed Chrome). `~/.hermes/hermes-agent/venv/bin/python` resolves to the same
site-packages via its `.pth`, so upgrading one covers both.

### Updating Chrome itself when stable moves ahead

The bundled `GoogleUpdater` accepts no `--help`/`--update` switch ("Unknown
command line switch"), so a forced update means the official DMG:

```sh
curl -fL -o ~/.hermes/cache/scratch/googlechrome.dmg \
  https://dl.google.com/chrome/mac/universal/stable/GGRO/googlechrome.dmg
hdiutil attach -nobrowse -readonly ~/.hermes/cache/scratch/googlechrome.dmg
defaults read "/Volumes/Google Chrome/Google Chrome.app/Contents/Info.plist" CFBundleShortVersionString
osascript -e 'tell application "Google Chrome" to quit'   # a quit can leave a 0-window process; SIGTERM it
mv "/Applications/Google Chrome.app" "/Applications/Google Chrome-old.app"
ditto "/Volumes/Google Chrome/Google Chrome.app" "/Applications/Google Chrome.app"
codesign -dv --verbose=2 "/Applications/Google Chrome.app" 2>&1 | grep TeamIdentifier   # EQHXZ8M8AV = Google LLC
open -a "Google Chrome" && osascript -e 'tell application "Google Chrome" to get version'
```

Rename the old bundle before copying (`ditto` over a running app can hit
ETXTBSY); delete the backup only after the new version reports. Quitting Chrome
kills the `--remote-debugging-port=9222 --user-data-dir=~/chrome-profile`
automation instance too — relaunch it and confirm `curl -s
http://127.0.0.1:9222/json/version` reports the new version, or every
`browser_exec` call fails with `BU_CDP_URL unreachable`.

Per-repo node upgrades: bump `playwright` and `@playwright/test` in
`package.json`, then `npm install`. **Never run this in a worktree with unmerged
conflicts** (`git status` shows `UU`/`DU`) — upgrade the primary clone on a clean
branch first, or the conflicts get worse. Read-only check for dirty worktrees:

```sh
git -C <repo> status --porcelain | grep -E '^(UU|DU|AA|DD)' && echo "skip: mid-conflict"
```

### Policy floor

| Component | Floor | Why |
|---|---|---|
| `playwright` / `@playwright/test` | 1.64.1 | Last release before the Oct-2026 Chromium gaps; 1.63 and below miss CVE-2026-87491 (known exploited) |
| chromium build in cache | 1248 | The 1.64.1 bundle |
| `@playwright/mcp` | 0.0.40 | CVE-2025-9611 |
| Google Chrome | current stable | Bundled builds never keep up |

The floor lives as constants at the top of `scripts/audit_browser_stack.py`.
Bump it only after reading release notes, not just the version number.

## Pitfalls

- **`pip uninstall` here hits the wrong environment.** Hermes exports
  `PYTHONPATH` pointing at its own venv, so `/usr/bin/python3 -m pip uninstall
  playwright` reports "Uninstalling playwright-1.64.1" and strips the Hermes
  runtime env while the stale user-site copy survives untouched. To retire the
  system-user install, move
  `~/Library/Python/3.9/lib/python/site-packages/playwright{,-<ver>.dist-info}`
  to a backup dir directly, then re-verify the Hermes env (`uv pip install
  --python "$PY" playwright==1.64.1`) before re-running the auditor.
- **"Latest" is not a fix.** Installing the newest Playwright browser bundle still
  shipped Chromium 156.0.8078.4 — the exact build flagged in the advisory — because
  the bundle only refreshes on Playwright's release cadence. Confirm the bundled
  version from the app's `Contents/Info.plist` (`CFBundleShortVersionString`), not
  from the `chromium-NNNN` directory name, then treat the launching rules above as
  the actual mitigation.
- **An upgrade that silently does nothing.** `pip install -U <pkg>` can be capped by
  the interpreter, so `pip index versions` reports your installed version as the
  newest and looks like "already up to date." Before concluding that, check PyPI's
  `requires_python` for the latest release (`pypi.org/pypi/<pkg>/json`); if it
  excludes your interpreter, install into a venv on a supported Python instead of
  accepting the cap. Homebrew-managed Pythons refuse user installs outright (PEP
  668), so a venv is the only route there.
- **Never scan `$HOME` broadly.** A recursive filesystem sweep over the home
  directory times out and yields nothing usable. Use `search_files` for targeted
  lookups, and for the audit pass bounded `--roots` (project dirs only) — the
  auditor prunes `node_modules` itself, checking the package inside each one and
  stopping descent there.
- **Do not bulk-bump dependency versions across worktrees.** Repos mid-merge
  (`UU`/`DU` in `git status --porcelain`) must be left alone until resolved, and a
  fleet-wide bump is a code change with PRs attached — report the list and the
  recommended subset, then get approval per repo.

## Honest limits

Version comparison is not a CVE scan. The floor assumes a bundled Chromium at or
above the patches shipped with the newest Playwright release; if a repo pins
Playwright and never reinstalls browsers, its on-disk build can still be old —
the audit reports cache builds separately for that reason.

Depth on the bundled-vs-system browser gap (mechanism, sandbox reasoning,
proportionality, how to read a bundle's real engine version):
`references/bundled-browser-gap.md`.

## Reporting

Give the operator: verdict, count of out-of-date installs, newest chromium build on
disk, installed Chrome version, and the fix. No rebuild narration.

For ongoing coverage, wire the silent watchdog: a `no_agent` cron pointing at a
wrapper that prints nothing on PASS/WARN and a short FAIL summary otherwise (see
`scripted-cron-verification` for the cron script-path rule). Detection decays
without a scheduled run.
