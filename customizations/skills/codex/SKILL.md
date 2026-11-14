---
name: codex
description: "Delegate coding to OpenAI Codex CLI (features, PRs)."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, Codex, OpenAI, Code-Review, Refactoring]
    related_skills: [claude-code, hermes-agent]
---

# Codex CLI

Delegate coding tasks to [Codex](https://github.com/openai/codex) via the Hermes terminal. Codex is OpenAI's autonomous coding agent CLI.

## When to use

- Building features
- Refactoring
- PR reviews
- Batch issue fixing

Requires an authenticated Codex CLI and a scoped workspace. Prefer a Git repository; isolated scratch work may use `--skip-git-repo-check`.

## Controlling safety rules

Preserve sandbox and approval controls. Use `--sandbox read-only` or `--sandbox workspace-write`; never disable them to work around authentication, access or approval failures. Legacy yolo/dangerous-bypass examples below are not authorization to use those modes. Do not auto-merge, send, deploy or push without current task authorization and release gates. Temporary files belong under the workspace or `$TMPDIR`, not literal `/tmp`. Pass absolute task paths; stop if missing rather than searching unrelated home folders.

**Worktree Git-metadata gate.** A linked worktree often has a `.git` pointer to metadata outside a `workspace-write` sandbox. Tell Codex to leave the normal worktree diff uncommitted when that metadata is not writable; never let it create an alternate Git directory/repository and present a commit there as the worktree's revision. After every claimed commit, the parent must read the actual worktree's `git rev-parse HEAD`, `git status --short --branch`, and `git log -1`; if the intended commit is absent, preserve the diff, complete review/checks, and commit through the parent on the real branch. A valid commit object in a side repository is an artifact, not delivery.

## Current subscription model preference

the operator requested `gpt-6.1-sol` for Codex on 2026-10-16. Codex CLI0.163.0 completed a real ChatGPT-auth smoke with runtime model metadata `gpt-6.1-sol`. Official OpenAI model documentation says GPT-5.5 retired from ChatGPT-auth Codex on2026-10-14; historical recommendations below to fall back to gpt-5.5 are stale for subscription runs. Prefer the verified configured default or explicit `-m gpt-6.1-sol`, and check live availability after future changes. Do not quietly substitute another model if it is unavailable.

## Prerequisites

- Codex installed: `npm install -g @openai/codex`
- OpenAI auth configured: either `OPENAI_API_KEY` or Codex OAuth credentials
  from the Codex CLI login flow
- Prefer a Git repository. For isolated scratch/control smokes, pass `--skip-git-repo-check`; do not create a throwaway repo solely to satisfy the check.
- Use `pty=true` for interactive Codex runs. In Hermes, PTY is valid only with `background=true`: launch a tracked process, then `process_manage wait` for a bounded one-shot or `poll`/`log` for a long task. Do not retry the invalid foreground-PTY shape.

For Hermes itself, `model.provider: openai-codex` uses Hermes-managed Codex
OAuth from `~/.hermes/auth.json` after `hermes auth add openai-codex`. For the
standalone Codex CLI, a valid CLI OAuth session may live under
`~/.codex/auth.json`; do not treat a missing `OPENAI_API_KEY` alone as proof
that Codex auth is missing.

## ChatGPT workspace and credit routing

Treat the ChatGPT consumer workspace and the standalone Codex CLI credential as separate state until a live run proves access:

1. Read the visible workspace selector when supplied. A checkmark proves only which workspace that app instance displays; it does not prove the Mac CLI changed workspaces.
2. If the selector is on the operator’s phone, instruct him to tap the intended workspace. Do not claim the Mac can control the phone or silently substitute a desktop workspace switch.
3. After the user switches, test the CLI in an isolated scratch Git repository with the configured subscription model and a read-only prompt, for example:
   ```bash
   codex -m gpt-6.1-sol --sandbox read-only exec --skip-git-repo-check 'Reply only CODEX_READY'
   ```
   Record the exit code and runtime model. A successful real Codex task proves the CLI currently has usable credits; it does not independently prove the selected workspace name.
4. If the CLI still reports exhausted workspace credits, use the supported Codex login/refresh flow with the user handling any browser choice, password, or verification step. Never edit OAuth tokens or account/workspace identifiers by hand.
5. Do not block unrelated work on the workspace change. Continue with approved alternate models while the CLI credit path is being repaired, then move new eligible work to Codex after a live smoke passes.

## One-Shot Tasks

Launch the one-shot as a tracked background PTY, then wait for its real exit:

```
terminal(command="codex exec --sandbox workspace-write 'Add dark mode toggle to settings'",
         workdir="~/project", background=true, pty=true)
process_manage(action="wait", session_id="<id>", timeout=600)
```

For a read-only scratch/control smoke, keep the workspace under `$TMPDIR` and skip the repository check:

```
terminal(command="codex exec -m gpt-6.1-sol --sandbox read-only --skip-git-repo-check 'Reply exactly: CODEX_CONTROL_OK'",
         workdir="$TMPDIR", background=true, pty=true)
process_manage(action="wait", session_id="<id>", timeout=120)
```

Accept control only when the process exits zero and the output reports the requested runtime model plus the exact marker. A version string or successful authentication alone does not prove usable workspace credits.

## Background Mode (Long Tasks)

```
# Start in background with PTY
terminal(command="codex exec --full-auto 'Refactor the auth module'", workdir="~/project", background=true, pty=true)
# Returns session_id

# Monitor progress
process(action="poll", session_id="<id>")
process(action="log", session_id="<id>")

# Send input if Codex asks a question
process(action="submit", session_id="<id>", data="yes")

# Kill if needed
process(action="kill", session_id="<id>")
```

## Key Flags

| Flag | Effect |
|------|--------|
| `exec "prompt"` | One-shot execution, exits when done |
| `--skip-git-repo-check` | Allow running outside a git repo (e.g. scratch dirs) |
| `--sandbox <mode>` | Sandbox policy: `read-only`, `workspace-write`, `danger-full-access` |
| `--dangerously-bypass-approvals-and-sandbox` | The actual "yolo" flag — bypasses both approval prompts AND sandbox. Use for autonomous multi-hour runs from tmux. |
| `-m, --model <name>` | Model selection. With ChatGPT-account auth, `gpt-5-codex` is **rejected** (400 invalid_request_error). Omit `-m` to use the account default, or use `-m gpt-5` if your plan supports it. With an `OPENAI_API_KEY`, `gpt-5-codex` works. |
| `-c key=value` | Override config (TOML-parsed). E.g. `-c model="o3"` or `-c sandbox_permissions=["disk-full-read-access"]` |
| `-i, --image <file>` | Attach image(s) to the prompt |
| `--oss` | Use open-source provider (local LM Studio / Ollama) |

**Flag-name gotchas from May 2026 session:**
- `--ask-for-approval never` does NOT exist on `codex exec` — it's a top-level flag and `codex exec --help` will reject it. To skip approvals in exec mode, use `--dangerously-bypass-approvals-and-sandbox` instead. The CLI hint "to pass '--ask-for-approval' as a value, use '-- --ask-for-approval'" is misleading; it doesn't actually accept that flag at all.
- `--full-auto` / `--yolo` from older docs may be deprecated in 0.130+. The current "I trust this agent, just go" flag is `--dangerously-bypass-approvals-and-sandbox`.
- When stdin is closed, `codex exec` will print `Reading additional input from stdin...` and then complain. Always pass the prompt as a positional arg, not via pipe, unless you're explicitly piping content.

## Autonomous Multi-Hour Delegation (tmux pattern)

When Claude Code's auth is broken or you need a non-Anthropic fallback for a long autonomous coding job, the spec format is portable — write `/tmp/<task>.md` exactly as you would for Claude Code, then launch Codex in tmux.

**The Claude Code 401 → Codex swap is a recurring pattern.** `claude auth status` can report a valid login while `claude -p` returns `401 Invalid authentication credentials` — the CLI token state diverges from API gateway acceptance. When this happens mid-session, do not wait for the user to complete a browser re-login (they may be AFK). Kill the dead Claude Code tmux, relaunch with `codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox` against the same `/tmp/<task>.md`, and surface the swap to the user in one line.

## Monitoring an autonomous Codex tmux run (terminal-state detection)

When you launch Codex via tmux and need to be notified when it's done (typical pattern: spec at `/tmp/<task>.md`, multi-hour run, user is AFK), set up a background poll. **Crucial pitfall:** Codex's diff output literally contains the word `error:` inside strings like `return NextResponse.json({ error: "..." })` and `error.message`. A naïve grep monitor that watches for `error:` will fire false-positive terminal alerts every few minutes as Codex writes API route diffs.

**Bad pattern (false-positives constantly):**
```bash
if tmux capture-pane -t <session> -p -S -15 | grep -qE "DONE\.|error:|ERROR|Failed"; then ...
```

**Good pattern (only fires on actual terminal state):**
```bash
if tmux capture-pane -t <session> -p -S -25 | grep -qE "^DONE\.$|^PR: https://github.com|Failed to authenticate"; then ...
```

Anchor to line-start (`^DONE\.$`) for the success marker since Codex's final-report block prints `DONE.` on its own line. Match the literal PR URL prefix `^PR: https://` for the auto-merge path. Match `Failed to authenticate` for the credential-died case. Do **not** include bare `error:` / `Error:` / `ERROR:` — those appear inside source-code strings and HTTP response shapes in any web project diff.

If the monitor false-triggers anyway, immediately scrollback the pane (`tmux capture-pane -p -S -100`) to confirm the agent's actual state before reporting "done" to the user. The terminal-state-reached signal is necessary but not sufficient — always verify before declaring done.

## tmux launch pattern

```bash
tmux new-session -d -s <task-name> -x 220 -y 60
tmux send-keys -t <task-name> "cd /path/to/repo" Enter
sleep 1
tmux send-keys -t <task-name> \
  "codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
    'Read /tmp/<task>.md and execute the entire task end-to-end. \
    Multi-hour autonomous. Work step by step. Open the PR and merge via gh. \
    Print the final report when done.' 2>&1 | tee /tmp/<task>.log" Enter
```

Notes:
- **No model flag** unless you've verified the account/plan supports it. Account default is safest.
- **Subscription model:** use `gpt-6.1-sol`, the current verified ChatGPT-auth model for the operator. Do not follow historical `gpt-5.5`, `gpt-5.4`, `gpt-5`, or `gpt-6-astra` fallback notes; validate future model changes with a live isolated smoke instead of changing shared configuration during concurrent work.
- **Stream to a tee log** so you can `tail -f /tmp/<task>.log` from another shell while the tmux session runs. The pane scrollback is finite.
- **Monitor cadence: every 2-3 min for the first 15 min**, then every 10-15 min after that. Look for tool-exec output (Codex prints `exec` blocks with the command and result) — that's progress.
- **Codex auto-merges via `gh pr merge --squash --auto`** if you tell it to; same pattern as Claude Code.

## PR Reviews

Clone to a temp directory for safe review:

```
terminal(command="REVIEW=$(mktemp -d) && git clone https://github.com/user/repo.git $REVIEW && cd $REVIEW && gh pr checkout 42 && codex review --base origin/main", pty=true)
```

## Parallel Issue Fixing with Worktrees

```
# Create worktrees
terminal(command="git worktree add -b fix/issue-78 /tmp/issue-78 main", workdir="~/project")
terminal(command="git worktree add -b fix/issue-99 /tmp/issue-99 main", workdir="~/project")

# Launch Codex in each
terminal(command="codex --yolo exec 'Fix issue #78: <description>. Commit when done.'", workdir="/tmp/issue-78", background=true, pty=true)
terminal(command="codex --yolo exec 'Fix issue #99: <description>. Commit when done.'", workdir="/tmp/issue-99", background=true, pty=true)

# Monitor
process(action="list")

# After completion, push and create PRs
terminal(command="cd /tmp/issue-78 && git push -u origin fix/issue-78")
terminal(command="gh pr create --repo user/repo --head fix/issue-78 --title 'fix: ...' --body '...'")

# Cleanup
terminal(command="git worktree remove /tmp/issue-78", workdir="~/project")
```

## Batch PR Reviews

```
# Fetch all PR refs
terminal(command="git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'", workdir="~/project")

# Review multiple PRs in parallel
terminal(command="codex exec 'Review PR #86. git diff origin/main...origin/pr/86'", workdir="~/project", background=true, pty=true)
terminal(command="codex exec 'Review PR #87. git diff origin/main...origin/pr/87'", workdir="~/project", background=true, pty=true)

# Post results
terminal(command="gh pr comment 86 --body '<review>'", workdir="~/project")
```

## Rules

1. **Use tracked PTYs correctly** — with Hermes, `pty=true` requires `background=true`; wait or poll the returned process handle and verify its exit.
2. **Prefer a Git repo, skip only for bounded scratch probes** — use `--skip-git-repo-check` for isolated read-only/control smokes rather than creating an unnecessary repository.
3. **Use `exec` for one-shots** — `codex exec "prompt"` runs and exits cleanly
4. **`--full-auto` for building** — auto-approves changes within the sandbox
5. **Background for long tasks** — use `background=true` and monitor with `process` tool
6. **Don't interfere** — monitor with `poll`/`log`, be patient with long-running tasks
7. **Parallel is fine** — run multiple Codex processes at once for batch work
