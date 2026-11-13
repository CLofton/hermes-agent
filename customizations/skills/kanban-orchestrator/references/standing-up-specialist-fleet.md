# Standing up a specialist fleet from scratch

When the user has only a `default` profile (or asks for a fresh team) and approves a specialist build-out, this is the exact CLI sequence. No interactive prompts to navigate.

## Step 1 — Discover what's there

```bash
hermes profile list      # shows profiles + current models
hermes kanban assignees  # shows which profiles have ever been used on the board
hermes kanban boards     # board health check
```

If only `default` exists, you need to create the specialists. The dispatcher silently drops cards assigned to nonexistent profiles, so this MUST happen before any `kanban_create` that names them.

## Step 2 — Create each specialist with a `--description`

The `--description` is what the kanban **decomposer** uses to route work by role. Skip it and routing degrades to keyword matching on profile name. One- to two-sentence sentences are plenty.

```bash
hermes profile create researcher --description "Web research, sourcing, market scans, candidate searches, competitive intel. Good for: vendor research, regulatory lookups, news/blog monitoring."

hermes profile create engineer --description "Code work on user's repos. Good for: bug fixes, new features, deploy debugging, PR review, security audits, schema changes."

hermes profile create analyst --description "Data analysis: HubSpot/BigQuery/Google Sheets/financial workbooks. Good for: ad-hoc analysis, KPI reports, funnel velocity, sheets formula audits."

hermes profile create writer --description "Drafting: board prep memos, exec briefs, decision memos, copy. Good for: turning analyst findings into CEO-ready prose, board deck narratives, SOP rewrites."
```

Each `hermes profile create` outputs:
- Path: `~/.hermes/profiles/<name>/`
- Wrapper script: `~/.local/bin/<name>` (so `<name> chat` works as shorthand)
- Warning: profile has no API keys yet (will inherit from shell env unless explicitly set)

## Step 3 — Assign a model to each profile

Models are NOT set during `create`. You must do it explicitly per profile:

```bash
hermes -p researcher config set model claude-sonnet-4-5
hermes -p engineer config set model claude-opus-4-7
hermes -p analyst config set model claude-sonnet-4-5
hermes -p writer config set model claude-sonnet-4-5
```

`-p <profile>` is the global flag to scope a hermes command to a specific profile. `config set <key> <value>` writes to `~/.hermes/profiles/<name>/config.yaml`.

Sensible default mix for cost vs. capability:
- **Opus for code** (engineer): correctness matters, opus catches subtle bugs sonnet misses.
- **Sonnet for everything else** (researcher, analyst, writer): plenty good for prose, analysis, web research. ~3-5x cheaper than opus per token.

## Step 4 — Verify the fleet

```bash
hermes profile list
```

Expected output: all profiles show their assigned model. Gateway will be `stopped` for non-default profiles — that's correct. Specialists spin up on demand when the kanban dispatcher claims a task for them; they're not always-on.

## Step 5 — Smoke-test by creating one card per profile

Before queuing real work, prove the dispatcher can spawn each specialist:

```bash
hermes kanban create "smoke test: researcher reachable" --assignee researcher --body "Just respond with 'hello' and call kanban_complete."
```

Watch with `hermes kanban watch` or `hermes kanban tail <id>`. If the card stays `ready` and never moves to `running` for >2 min, the dispatcher isn't picking it up — check `hermes gateway status` (dispatcher lives in the gateway).

## Gotchas

- **`hermes config set` requires `-p <profile>` for non-default profiles.** Plain `hermes config set model ...` writes to the *active* profile's config. Always prefix with `-p` for explicit targeting.
- **`hermes config get` does not exist.** Use `hermes -p <profile> config show | grep model` instead.
- **API keys inherit from shell env.** If `ANTHROPIC_API_KEY` is in your shell, all new profiles use it. If you want per-profile keys, run `<profile> setup` or write to `~/.hermes/profiles/<name>/.env`.
- **Don't rename profiles after they own kanban cards.** The board joins by profile name; renaming orphans the history. Use `hermes profile rename` only on idle profiles.
- **Profile create syncs 87 bundled skills by default.** Use `--no-skills` if you want a stripped-down profile (rare; usually you want the skill library).

## When the user already has a fleet

Skip Steps 2-3. Just run Step 1, cache the list, and proceed to decomposition. Re-creating profiles is destructive only via `hermes profile delete` — `create` errors out if the name exists.

## CLI vs Python tool form for `kanban_create`

The main skill body shows `kanban_create(...)` as Python because workers run inside an agent loop. Orchestrator chat sessions with terminal access can use either:

```bash
# Shell form (good for one-off cards in a chat session)
hermes kanban create "title" \
  --assignee researcher \
  --body "..." \
  --priority 100 \
  --parent t_abc123 \
  --json

# Python form (good for programmatic fan-out inside execute_code or a worker)
task_id = kanban_create(
    title="title",
    assignee="researcher",
    body="...",
    parents=["t_abc123"],
)["task_id"]
```

Both end up in the same SQLite. The shell form's `--parent` flag is repeatable for multi-parent synthesis cards:

```bash
hermes kanban create "synthesis" --assignee writer \
  --parent t_aaa --parent t_bbb --parent t_ccc --parent t_ddd
```

The Python form takes a list: `parents=["t_aaa", "t_bbb", ...]`.
