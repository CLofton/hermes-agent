---
name: session-librarian
description: "Find, resume, rename, archive, prune sessions by prompt."
version: 1.0.0
author: Hermes Agent + Teknium
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Sessions, Organization, Cleanup, Library, Productivity]
    category: productivity
    related_skills: [weekly-review-planning]
---

# Session Librarian

Manage the user's session library conversationally: find past sessions about a
topic, summarize what they decided, rename them meaningfully, split work into
parallel sessions, and propose stale ones for archive or deletion — all from a
plain-language request like *"find my sessions about Q3 pricing, keep the
useful ones, and clean up the duplicates."*

Inspired by Perplexity Computer's prompt-driven session management (Aug 2026):
the agent starts, organizes, and cleans up the user's own session library, and
always shows the plan before touching anything.

## When to Use

- "Resume previous session" / "pick up where we left off" / "did that finish?"
  (see Resume the Previous Session below)
- "What sessions do I have about X?" / "What did we decide about X?"
- "Rename these sessions to something meaningful."
- "Clean up my session library" / "archive the stale ones."
- "Fork that session into a follow-up focused on Y."
- "Split this into one session per ticket" (see Parallel workstreams below).

## The Two Surfaces

| Task | Surface |
|---|---|
| Find sessions by topic, read content, summarize decisions | `session_search` tool (FTS5 over the message store) |
| List/filter by metadata (age, source, cost, tokens, workspace) | `hermes sessions list` / `stats` via terminal |
| Rename | `hermes sessions rename <session_id> <title...>` |
| Bulk soft-hide (reversible) | `hermes sessions archive <filters>` |
| Delete (destructive) | `hermes sessions delete` / `hermes sessions prune <filters>` |
| Export before deleting anything valuable | `hermes sessions export --session-id <id> --format md` |
| Continue work in a new place | `/branch` (fork current session) or start a fresh session and cite the summary |

## Procedure

① **Discover.** Use `session_search(query=..., limit=5-10)` with topic
keywords; vary phrasing (feature name, symptom, project name). For metadata
sweeps ("sessions older than 60 days from telegram"), use
`hermes sessions list --source telegram --limit 50` instead.

② **Summarize per session.** The discovery result's `bookend_start` (goal),
match window, and `bookend_end` (resolution) usually suffice — only dump a
full session (`session_search(session_id=...)`) when the user asks for
decisions in depth. Report each as: link (`@session:` form) — one-line goal —
one-line outcome.

③ **Plan before acting (MANDATORY for anything that mutates).** Present a
plan table first: which sessions get renamed to what, which get archived,
which are proposed for deletion and why (duplicate of which keeper, stale,
empty). Wait for the user's go-ahead. Exception: a single rename the user
explicitly dictated can be done directly.

④ **Act with the safest primitive.**
- Prefer `archive` (reversible soft-hide) over `delete`/`prune`.
- Always run destructive commands with `--dry-run` first and show the output,
  then re-run with `--yes` after confirmation.
- Before deleting anything with meaningful content, offer
  `hermes sessions export --format md` as a backup.

⑤ **Report.** Renames applied, sessions archived (count + how to undo:
archived sessions remain in the DB and are listed with `--include-archived`),
anything exported, anything skipped and why.

## Resume the Previous Session

Trigger: "resume previous session", "where did we leave off", "did that finish".

① **Identify the candidate from metadata, not recency alone.** Cron and
subagent runs dominate the newest rows and bury the human thread.

```bash
sqlite3 ~/.hermes/state.db "select id, source, message_count, \
  datetime(coalesce(last_activity_at,started_at),'unixepoch','localtime') last, title \
  from sessions where source!='cron' order by coalesce(last_activity_at,started_at) desc limit 15;"
```

② **Read the tail of the best candidate before summarizing** — the goal lives
in the head, the actual stopping point lives in the tail:

```bash
sqlite3 ~/.hermes/state.db "select max(id) from messages where session_id='<full id>';"
```

then `session_search(session_id='<full id>', around_message_id=<that id>, window=6)`.
Several user-facing sessions from one day is normal (one per surface); pick the
one whose tail is unfinished, not merely the most recently touched.

③ **Report state inline; do not open with a question form.** The resume
request is answered by the state summary itself — session link, one-line goal,
the last decision, and what is explicitly unfinished. Close with a one-line
"say the word — <A>, <B>, <C>" so the user can steer without another round
trip. A blocking form as the first move stalls the turn and delivers nothing.

④ **If the previous session ended complete, say so plainly** and offer the
nearest genuinely open thread (an unbuilt plan, a failing required gate, an
undecided item) instead of inventing continuation work. Resume means rehydrate
context, not manufacture a task.

## Parallel Workstreams

For "one session per ticket, investigate each, report back": do NOT try to
drive other live sessions. Use `delegate_task` with one task per workstream —
each subagent runs in its own session automatically — then synthesize their
summaries. Mention that each delegation's transcript is itself searchable
later via `session_search`.

## Pitfalls

- **Never delete without a dry-run + explicit confirmation in this
  conversation.** A standing "clean things up" is authority to *propose*, not
  to prune.
- **`session_search` finds content, not metadata.** Age/cost/source filters
  live in the CLI; combine both when the request mixes them ("old sessions
  about pricing").
- **`session_search` rejects a truncated session id** with `session_id not
  found`. Ids shown in `hermes sessions list` table output and in discovery
  results are abbreviated — pull the full id from the DB
  (`select id from sessions where title like '...'`) and pass it verbatim.
- **`state.db` stores full message bodies and tool-call arguments, not just metadata.** When a file an earlier session wrote is gone (scratch pruned, deleted, never copied out), `messages.tool_calls` still holds the exact `write_file` content and `patch` old/new strings — recover the bytes from there instead of re-authoring the artifact. `~/.hermes/sessions/*.jsonl` holds only older sessions, so a search of that tree finds nothing for recent work; query `state.db` with `tool_calls LIKE '%<path fragment>%'`.
- **Session metadata lives in `~/.hermes/state.db`.** `~/.hermes/sessions.db`
  exists but is an empty stub, so querying it returns `no such table:
  sessions` — that error means wrong file, not missing data. The sessions
  table uses `last_activity_at` (there is no `last_active`) and a REAL epoch
  `started_at`; convert with `datetime(col,'unixepoch','localtime')`.
- **Prefer direct `sqlite3` over parsing CLI JSON for session metadata.** When
  `hermes sessions list --json` returns nothing parseable, do not keep
  reformatting the pipe — query `~/.hermes/state.db` directly; the columns are
  stable and give full untruncated ids.
- **Titles are identity for `/resume <title>`.** When renaming, keep titles
  short, unique, and prefix-friendly; warn the user if a rename collides with
  an existing title.
- **Archived ≠ deleted.** Archive hides sessions from default listings only.
  Say which one you did.
- **Cross-profile session links** (`@session:<profile>/<id>`) are read-only
  from another profile; management commands act on the current profile's DB.

## Verification

After a cleanup pass, re-run the discovery query and `hermes sessions list`
to confirm the library reflects the plan (keepers present with new titles,
archived ones gone from the default listing).
