---
name: inspecting-hermes-desktop-dom
description: "Read the live Hermes desktop DOM/CSS over CDP."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [desktop, electron, cdp, dom, ui-verification, self-inspection]
    related_skills: [node-inspect-debugger, systematic-debugging, dogfood]
---

# Inspecting the live Hermes desktop DOM

## Overview

When you are developing `apps/desktop` and the user is running that same app
(`hgui` / `npm run dev`), you can read the **live rendered DOM** of the window
they are looking at — computed styles, geometry, which CSS rule actually won,
console output — instead of inferring it from `.tsx` and being wrong.

Dev-server runs open a Chrome DevTools Protocol port on `127.0.0.1:9222`
automatically. The renderer is a Chromium page, so everything DevTools can read,
a script can read.

**This does not replace looking at it.** CDP answers *factual* questions ("what
is the computed padding", "did this element render", "which selector matches").
It cannot tell you whether the result looks good. Colour balance, spacing feel,
and "is this ugly" still need the user's eyes or a screenshot. Answer facts with
CDP; hand aesthetics to the user.

## When to Use

- Verifying a UI change actually took effect in the running app
- "Why is this element still X?" — find the winning rule before editing anything
- Locating a stable selector for a component you're about to change
- Checking a design token's computed value on a real node
- Reading renderer console errors the user mentions but can't copy out

**Don't use for:** perf profiling or heap work (`node-inspect-debugger`,
`debugging-hermes-desktop`), or anything where the real question is "does this
look right".

## Identify the actual Hermes surface first

Discover the CDP target URL before applying desktop assumptions. A page titled Hermes Agent Dashboard at `127.0.0.1:9119/chat` is the web dashboard (`web/` and `hermes_cli/web_routers/`), not `apps/desktop`. Read `web/AGENTS.md`: primary chat is the real Ink TUI embedded through xterm/PT Y, not a React composer to rebuild.

Treat DB-backed session lookup and live draft existence as different contracts. TUI session.create announces a stored ID before the first prompt persists its row; a domain 404 on latest-descendant can therefore be normal for an unspoken draft. Never make one such lookup failure disable every pane. Quarantine failed panes without changing their saved transport identity, allow independent new slots, and fail closed on recent-session selection while ownership is unresolved. Do not bypass the 404 by calling attach-or-spawn: an expired transport can silently become a new conversation. Restoring that exact draft requires an authenticated, profile-scoped retained-only transport check. Keep regression tests for missing draft, missing explicit resume, 403/500, and no connection to the quarantined attach token; use unique UUIDs in multi-pane test fixtures.

For concurrent dashboard panes, preserve paired attach/channel identities and isolate keyboard focus from layout visibility. A keepalive PTY keeps its original publisher channel; regenerating only the channel loses status. Use structured parent-session events, not terminal text or socket-open, for work status. Parallel tool progress does not prove an approval or clarification resolved. A successful `message.complete` proves turn completion, not task completion. Do not label lastSuccessfulComplete green automatically. Ordinary requests lack an authoritative task-outcome contract; keep them neutral unless explicitly confirmed by the user, and clear confirmation on new activity, pending input, stale snapshots, or disconnect. If offering a manual completion control, disclose that limitation rather than claiming automatic task detection. Goal done is stronger but must be bound to the current request, not a historical goal. Test computed border colors, not only class strings: competing default border utilities can mask status colors.

For session dragging, use profile-scoped versioned custom MIME, not text/plain (which collides with terminal file/text drops). Handle session drops in capture phase before xterm, preserve occupied slots, and focus an already-open canonical session instead of making another writer. Exercise a real Chromium drag gesture in isolated fixtures. Multiple /api/events subscribers may share one channel; fixture publishers must fan out to every subscriber, like the backend does.

For dashboard attachments, use native file inputs and owning-terminal bracketed paste without Return; `/image ...` plus Return can submit an existing draft. Validate actual dropped-path grammar: JSON.stringify is not decoded as JSON by the native path parser, so literal double quotes/backslashes can break resolution. Guard target generation and interactive readiness again after asynchronous uploads.

Use disposable Chromium with explicit API/WS fixtures for layout, chooser, and six-pane targeting tests; label those as mocked-transport browser tests, not live-backend certification. Never navigate or reload the user's active chat to run tests. Production dashboard reads index.html per request, so frontend assets can be rolled out without restarting Python; preserve old hashed chunks for existing tabs and swap index last.

## The port

Open on `127.0.0.1:9222` for any dev-server run. Closed in exactly two cases
(`apps/desktop/electron/dev-cdp.ts`):

- **packaged builds** — always, and no environment value overrides it;
- **no `HERMES_DESKTOP_DEV_SERVER`** — an unpackaged `electron .` against
  `dist/` is how the packaged app gets smoke tested, so it behaves like one.

`HERMES_DESKTOP_CDP_PORT` moves the port (`=9333`) or disables it (`=off`).

Check before doing anything else:

```bash
curl -s --max-time 3 http://127.0.0.1:${HERMES_DESKTOP_CDP_PORT:-9222}/json/version
```

Empty → no port. Do not guess another port silently.

**Never relaunch the user's app to get a port.** That destroys their session and
their state. Launch your own isolated instance instead (below).

## Reading the DOM

`apps/desktop/scripts/eval.mjs` is the one-liner:

```bash
cd apps/desktop
node scripts/eval.mjs "document.querySelectorAll('[data-slot]').length"
```

For multi-step work use the shared client — it has target discovery and
promise-aware eval:

```js
import { CDP, SELECTORS } from './scripts/perf/lib/cdp.mjs'

const cdp = await CDP.connect({ port: 9222, match: '5174' })
const out = await cdp.eval(`JSON.stringify({
  radius: getComputedStyle(document.documentElement).getPropertyValue('--radius-scalar').trim(),
  composer: !!document.querySelector('[data-slot="composer-rich-input"]')
})`)
cdp.close()
```

`SELECTORS` in `scripts/perf/lib/cdp.mjs` holds the stable `data-slot` hooks
(composer, thread viewport, assistant message, turn pair, profile rail). Prefer
them over inventing a `querySelector` — they are updated as a unit when
components move.

## The question this is best at: which rule won?

Editing every call site because a style "isn't applying" is the classic waste.
Read the real node first:

```js
const el = document.querySelector('[data-slot="aui_assistant-message-root"] a')
JSON.stringify({
  ownClasses: el.className,
  weight: getComputedStyle(el).fontWeight,
  parents: (() => {
    const out = []
    let n = el
    while ((n = n.parentElement) && out.length < 6) out.push(n.className)
    return out
  })()
})
```

If the node carries no class of its own, the value is **inherited** — sweeping
call sites will not fix it, and you need the ancestor rule. A plugin stylesheet
(e.g. `@tailwindcss/typography`'s `prose a { font-weight: 500 }`) routinely beats
a utility class; override on the shared class, not at each usage.

## Your own isolated instance

When there is no port, or you must not disturb the user's window:

```bash
cd apps/desktop
HERMES_HOME=/tmp/cdp-probe-home \
HERMES_DESKTOP_DEV_SERVER=http://127.0.0.1:5174 \
HERMES_DESKTOP_CDP_PORT=9333 \
  npx electron . --user-data-dir=/tmp/cdp-probe-userdata
```

The separate `--user-data-dir` dodges Electron's single-instance lock, so it
cannot collide with a running `hgui`; the separate `HERMES_HOME` keeps it away
from real sessions. Pick a port other than 9222 for the same reason. Run it in
the background and kill it when done.

`npm run perf:serve` does the same with a temp `HERMES_HOME` baked in, if you
also want the perf harness.

## Pitfalls

- **Never kill the user's dev server or app to "free" anything.** A mid-serve
  kill nukes Chromium's socket pool, and the resulting `ERR_NETWORK_CHANGED`
  gets blamed on whatever you just changed.
- **A throwaway `HERMES_HOME` has no backend.** The app logs `ECONNREFUSED` for
  `hermes:api` and may exit on its own. The renderer still mounts and the DOM is
  readable — read promptly, and don't mistake a self-exited probe for a broken
  port. Chromium logs `DevTools listening on ws://127.0.0.1:<port>/…` when it
  binds; that line is the proof the port opened.
- **Poll, don't probe once.** A just-launched app needs a second or two before
  the port answers.
- **Never dump the whole DOM.** The desktop renders hundreds of nodes and
  `outerHTML` will bury your context. Project down to a small JSON object inside
  the evaluated expression.
- **Pass `match` to `CDP.connect`.** Without it you may attach to the pet
  overlay, quick-entry window, or a devtools target instead of the main window.
- **`cdp.eval` returns the value; raw `Runtime.evaluate` double-nests it**
  (`.result.result.value`). Use the wrapper.
- **`import.meta.env.DEV` is `true` under `vite dev`** in this repo. The note in
  `apps/desktop/scripts/profile-typing-lag.md` claiming otherwise is stale.
