# Bundled browser vs. system browser — the standing gap

Every browser-automation stack has two browsers: the one the package bundles
(Playwright's `chromium-NNNN`, Puppeteer's cache, Electron's engine) and the one
installed on the machine. They drift, always in the same direction.

**Mechanism:** the bundled engine only refreshes when the automation package cuts
a release. Chrome ships security fixes continuously. So a package that is
"fully up to date" can still carry a browser that is days or weeks behind, and
`npx <tool>@latest` does not close that gap.

Consequence for triage: an advisory about a bundled engine is **not** a
dependency version-range problem. Bumping the package is necessary but not
sufficient; the mitigation is which browser you launch and whether its sandbox
is on.

## Example advisory shape

A Playwright advisory covering Chrome's late-October 2026 patch batch is
representative. Chrome stable was at `156.0.8078.79/.80`; the newest Playwright
bundle (build 1248) still shipped `156.0.8078.4`. Five Critical fixes were
unaccounted for in the bundle:

| CVE | Component |
|---|---|
| CVE-2026-118306 | FileSystem |
| CVE-2026-118331 | FileAPI |
| CVE-2026-118348 | Skia |
| CVE-2026-118344 | Layout |
| CVE-2026-76024 | MediaStream |

Version-to-exposure ordering from that advisory (1.64.x clean, 1.63 missing a
known-exploited bug, 1.62/1.61 worse) is a **version-number comparison, not
independent exploit testing**. Treat it as a triage signal, never as a CVE
report you can quote as verified.

## Why the sandbox is the real control

`chromiumSandbox` "Defaults to false" in Playwright's docs. The sandbox is the
only thing standing between a browser bug and the host filesystem. Without it,
an exploit lands as the user: `.env`, SSH keys, and logged-in session tokens in
reach.

Agent-specific amplification, in order of severity:

1. A test suite visits your own site; an agent visits whatever a task, search
   result, or prompt injection sends it to. Same tool, wildly different input
   trust.
2. Playwright's own MCP server is documented as "not a security boundary."
3. `--allowed-origins` allows everything by default.
4. The Playwright Docker image runs as **root** by default, which disables the
   Chromium sandbox; upstream docs say it is not recommended for untrusted
   sites. Use a non-root user plus their seccomp profile.

## Proportion

Localhost testing against trusted content is low risk. This class of advisory is
not "the tool is malware," and exploitation of a specific bundled-browser bug
through Playwright is not commonly reported. The real change is that defaults
built for trusted testing are now pointed at the open internet through agents.
Say that plainly instead of escalating to alarm.

## Verifying a bundle's real engine version

Read the version from the app bundle, not the directory name — `chromium-1248`
tells you the Playwright build, not the Chromium version inside it:

- macOS: `Contents/Info.plist` → `CFBundleShortVersionString`
- Linux: `<build>/chrome-linux/chrome --version`

Compare that against installed Chrome/Chromium stable before deciding a stack is
current.
