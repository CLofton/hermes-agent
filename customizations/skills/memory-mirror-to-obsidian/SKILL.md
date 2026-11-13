---
name: memory-mirror-to-obsidian
description: Mirror Hermes' internal memory (user profile + agent notes) to the operator's Obsidian vault so he can read, edit, and back up what the agent has learned. Run this whenever memory is updated, on a daily cron, or when the operator asks to "show me what you remember" / "back up your memory" / "sync memory to Obsidian".
---

# Memory Mirror → Obsidian

the operator wants a human-readable, editable copy of my (Hermes') memory inside his Obsidian vault. This skill keeps `Memory/User Profile.md` and `Memory/Hermes Notes.md` in sync with the actual `memory` tool storage.

The internal `memory` tool remains the source of truth that's auto-injected into my system prompt. The Obsidian files are a mirror — for the operator's visibility, editing, search, and backup.

## When to use

- After any `memory(action='add'|'replace'|'remove')` call → re-mirror immediately
- On a daily cron at 2:30am CT (after the meeting backfill, before he wakes up)
- When the operator says "show me what you remember" or "what's in your memory"
- When the operator says "back up your memory" / "sync memory" / "mirror memory"
- Before any significant memory rewrite (so the prior state is preserved as a backup commit)

## Vault paths

```
$OBSIDIAN_VAULT_PATH/Memory/User Profile.md   # mirrors target='user'
$OBSIDIAN_VAULT_PATH/Memory/Hermes Notes.md   # mirrors target='memory'
$OBSIDIAN_VAULT_PATH/Memory/_history/         # timestamped snapshots before each rewrite
$OBSIDIAN_VAULT_PATH/Memory/README.md         # explainer for the operator
```

`OBSIDIAN_VAULT_PATH` defaults to `/Users/operator/Documents/Obsidian Vault`.

## Procedure

### 1. Read current memory state

**Preferred path — from system prompt (interactive sessions):**
The memory contents are visible in my system prompt under the headers:
```
══════════════════════════════════════════════
MEMORY (your personal notes) [pct — used/cap chars]
══════════════════════════════════════════════
<content>

══════════════════════════════════════════════
USER PROFILE (who the user is) [pct — used/cap chars]
══════════════════════════════════════════════
<content>
```

**Fallback path — from disk (cron runs, missing prompt section):**
On scheduled cron runs the MEMORY / USER PROFILE sections may not appear in the system prompt. If you don't see them, read the source-of-truth files directly:

```bash
/Users/operator/.hermes/memories/USER.md    # target='user'
/Users/operator/.hermes/memories/MEMORY.md  # target='memory'
```

These are the actual files the memory tool writes to — reading them is equivalent to reading the prompt section, and is what should be used whenever the prompt section is absent. Do NOT skip the mirror or emit `[SILENT]` just because the prompt section is missing.

Entries are separated by `§` (section sign) on their own line. Parse them out individually and trim whitespace. The `read_file` tool shows line numbers prefixed as `N|` — strip that formatting before parsing.

**Char caps (as of 2026):** USER cap ≈ 2000, MEMORY cap ≈ 4000. Use these when computing `char_usage` percentages for the frontmatter if the prompt didn't provide them.

### 2. Snapshot before write

Before overwriting either mirror file, copy the existing version into `$VAULT/Memory/_history/`:

```bash
ts=$(date '+%Y-%m-%d-%H%M')
cp "$VAULT/Memory/User Profile.md" "$VAULT/Memory/_history/User Profile - $ts.md" 2>/dev/null || true
cp "$VAULT/Memory/Hermes Notes.md" "$VAULT/Memory/_history/Hermes Notes - $ts.md" 2>/dev/null || true
```

Keep last 30 snapshots; prune older ones:

```bash
ls -t "$VAULT/Memory/_history/" | tail -n +61 | while read f; do rm "$VAULT/Memory/_history/$f"; done
# (60 because each rewrite saves both files)
```

### 3. Write the mirror files

**User Profile.md** format:

```markdown
---
type: hermes-memory-mirror
target: user
last_synced: YYYY-MM-DD HH:MM CT
char_usage: <used>/<cap> (<pct>%)
---

# User Profile

> ⚠️ This file is **mirrored** from Hermes' internal memory tool. Edits here are NOT automatically written back to the agent — to update what Hermes remembers, talk to Hermes directly. This file is a **read-only backup + viewer**.
>
> Source of truth: `memory(target='user')`. Mirror refreshed daily at 2:30am CT and on every memory change.

---

## Entries

1. <first entry>

2. <second entry>

3. <third entry>

...

---

**Tags:** #hermes-memory #user-profile
```

**Hermes Notes.md** uses the same format but with `target: memory` and "# Hermes' Notes" as the H1.

### 4. Maintain README.md

Write `$VAULT/Memory/README.md` once (don't overwrite if exists):

```markdown
# Hermes Memory

This folder contains a human-readable mirror of Hermes' internal memory system.

## Files

- **User Profile.md** — what Hermes knows about the operator (preferences, communication style, role, key reports). Mirrors `memory(target='user')`.
- **Hermes Notes.md** — Hermes' working notes (environment facts, project conventions, tool quirks, lessons learned). Mirrors `memory(target='memory')`.
- **_history/** — timestamped snapshots before each rewrite (last 30 kept).

## How updates work

- Hermes' real memory lives in `~/.hermes/memory.json`. That's what gets injected into every prompt.
- These mirror files are refreshed:
  1. Whenever Hermes writes to memory in a session
  2. Daily at 2:30am CT via cron
- **Editing these files does not change Hermes' memory.** To update what Hermes remembers, talk to Hermes ("forget X", "remember that Y", "actually it's Z not W").

## Why mirror?

- Visibility — see exactly what's been recorded
- Backup — survives accidental memory wipe
- Search — Obsidian's full-text search across all memory + meetings + notes
- Graph view — memory entries can wikilink to people, topics, and meetings

---

**Tags:** #hermes-memory
```

### 5. Update Home dashboard

Add a Memory section to `$VAULT/Home.md`:

```markdown
## 🧠 Memory

Last synced: <timestamp>

- [[Memory/User Profile|What Hermes knows about you]] (<entry count> entries)
- [[Memory/Hermes Notes|Hermes' working notes]] (<entry count> entries)
- [[Memory/README|How memory mirroring works]]
```

(This integrates with the existing Home.md rebuild from the meeting-notes-to-gbrain skill.)

## Pitfalls

1. **Don't write back from Obsidian.** This is a one-way mirror. If the operator wants to change memory, he tells me — I call the `memory` tool. Auto-syncing edits *into* memory would create chaos and infinite loops.
2. **Snapshot before write.** Always. The history folder is cheap insurance against accidental overwrites or buggy parses.
3. **Memory format may evolve.** Today entries are `§`-separated paragraphs. If that changes, update the parser.
4. **Don't include private/sensitive flags as tags.** The vault is local but synced through whatever the operator has set up — be conservative on what gets surfaced as searchable.
5. **Char usage is informational only.** Don't truncate based on it during mirror — display the actual content.
6. **Keep the warning banner.** People naturally try to edit visible files. The "edits don't persist" warning at the top is critical context.
7. **`execute_code` is blocked in cron mode.** Cron sessions reject `execute_code` (arbitrary local Python) as a policy safeguard — don't reach for it to do the snapshot/write dance. Use `terminal` for the `cp` / prune, and `write_file` for the two mirror files. Everything this skill needs fits in those two tools.
8. **Cron delivery is automatic — never emit `[SILENT]` on success.** The wrapper prompt says "respond `[SILENT]` if nothing new to report," but a successful mirror IS the report. End with the one-line status (`User profile: N entries. Notes: M entries. Snapshot saved at $ts.`) so the delivery log shows the run happened. Reserve `[SILENT]` for the rare case where both source files are unreadable AND no snapshot was taken.
