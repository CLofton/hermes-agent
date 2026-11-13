---
name: cross-profile-skill-propagation
description: Use when syncing skills or reviewed plugins across Hermes profiles.
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [skills, profiles, propagation, sync, hash-verification]
    related_skills: [local-terminal-process-monitoring, hermes-agent]
---

# Cross-Profile Skill and Plugin Propagation

the operator's Hermes fleet has one default profile plus a changing set of named profile roots.
A skill or agent-plugin change that touches only the default root is NOT system-wide.
Enumerate the profile roots live for every rollout, freeze that set as the expected target
list, and update and verify every member; never carry a profile count forward from an
earlier run. Keep **profiles** and **machines** as separate scopes: an `N/N` profile
rollout on one host is not an all-machines rollout. Inventory remote hosts independently
and report unreachable/offline hosts as blocked rather than silently counting them.

## 1. Inventory before touching anything

- Discover copies by content and resolved skill identity, not one assumed directory shape. Search every profile's skill roots for `SKILL.md`, classify exact copies of the target separately from similarly named recursive/local-execution variants, and freeze every canonical and legacy-path copy. A profile can contain both categorized and flat copies; updating one expected path per profile can leave a second active copy stale.
- Count locations from that frozen copy manifest and report copies separately from profiles. Never assume one copy per profile or carry either count forward.
- Hash the canonical file(s) in the default profile AND the source of truth (often a
  file in `~/Downloads`). Confirm they match before assuming nothing is out of date:
  `shasum -a 256 <file>` and compare the 16-char prefix.
- **Multi-file directory verification:** do NOT `tar -C dir -cf - . | shasum` — tar
  captures mtimes, which change on every `cp`, so a successful copy reports a
  mismatch and every location fails verification (observed: 0/69 "OK" on a clean
  rollout). Use a content hash — per-file sha256 of path+content, then hash the
  sorted listing — which is mtime-independent:
  ```bash
  content_hash() { (cd "$1" && find . -type f | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256 | cut -c1-16); }
  ```
  Slow (~1-2 min for an 11MB/300-file skill x 69 profiles); a Python `shasum`-per-file
  loop is slower still and can exceed the 300s execute_code cap — prefer the shell
  function in terminal.
- Check for **name collisions** before any rename: `ls -d ~/.hermes/profiles/*/skills/<category>/<new-name>` — if the target name already exists anywhere, stop and ask rather than `mv` over it.
- Before any hash, copy, or transaction-directory creation, traverse every frozen target with `lstat`/no-follow and refuse every symlink, including links under caches or ignored/protected subtrees. Report the original live path and stop; dereferencing first can read or copy credential data outside the declared target.
- Classify embedded sensitive data separately from disposable metadata. A nested literal `~` subtree can be a serialized home containing browser cookies, login databases, or web data; never copy it into staged trees or rollback backups. If it must survive a directory replacement, preserve it through a journaled same-filesystem hold-and-restore. Allow only explicitly reviewed cache names as disposable.

## 2. Propagate (update or rename)

- **Update:** freeze the live target-root list first. Fail closed if Python optimization is active (`not __debug__` or nonempty `PYTHONOPTIMIZE`) so safety assertions cannot disappear. Complete symlink/sensitive-data/writer preflight before creating transaction state. For each root, copy the canonical directory to a uniquely named hidden sibling, hash that staged copy, and only then atomically rename it into place. If any location fails before completion, remove the staged directories and roll back destinations created by this run; a partial rollout is not system-wide.
- For an existing directory update, remove or archive the exact target before the atomic
  rename. A bare `cp -R` into an existing target nests the source as a subdirectory.
  When one location mismatches, compare sorted relative file lists before content to
  distinguish nested copies from real drift.
- After copying, enforce any intended read-only policy and verify it separately from the
  content hash: require the expected file count, no writable bits, and the canonical
  path+content digest at every location. Permissions are release state, not content.
- Report `ok/fail` against the frozen expected total and include the full canonical
  digest. Never infer fleet completion from a default-profile load check alone.
- **Rename:** `mv` each directory, then copy the canonical SKILL.md (frontmatter `name:`
  must match the directory name — update the `name:` and `# Title` line as part of the
  same sync), then re-verify hashes. Verify per-location inside the loop, not after.
- Use the `write_file`/`patch` tools for SKILL.md content edits (frontmatter-aware),
  `cp`/`mv` in terminal for bulk byte-identical propagation.

## 3. Reviewed agent-plugin rollout

When the capability ships as a Hermes agent plugin, prefer the reviewed Hermes catalog
package over the upstream project's generic setup command. The catalog adapter can pin a
version, bundle a Hermes-safe skill, and avoid a duplicate `mcp_servers` entry; running
both setup paths creates competing registrations and version drift.

1. Canary one noncritical profile with supported commands:
   `hermes --profile <name> plugins install <plugin>` → inspect the exact catalog SHA,
   package pin, declared MCP/skills, and disclosure → `plugins enable <plugin>` → read
   back `plugins list --plain --no-bundled`.
2. Treat install, enable, dependency download, MCP launch, and tool discovery as separate
   states. An enable message that says MCP activation is deferred proves only the config
   write; start a new session before testing tools.
3. For a large same-host fleet, freeze the profile list and pre-enabled set. Stage a
   byte-identical copy of the canary's reviewed plugin directory at every target, verify
   a path+content digest and file count, publish by atomic rename with rollback backups,
   then use `hermes --profile <name> plugins enable <plugin>` only for profiles that were
   not already enabled. On any failure, disable only profiles changed by the run and
   restore the exact backups.
4. Do not restart dozens of running gateways merely to make deferred MCP tools appear;
   restarts can interrupt active work. Record activation as owed to the next session
   unless the user separately authorizes a coordinated restart window.
5. Final acceptance is three-part: every frozen target has the canonical plugin digest,
   every target config reads enabled, and a fresh-session canary discovers at least one
   expected tool/skill. Prefer a harmless no-target/list probe; an expected domain error
   such as `target_unavailable` proves the MCP transport and registration responded but
   does not prove an analysis engine or real target works. Report those counts separately.

## 4. Shared operational repositories across profiles

For repositories every profile on one host should use, prefer one canonical shared root
(e.g. `~/.hermes/shared/repos`) over cloning the same repository into every profile.
All same-user profiles can resolve that absolute path, so per-profile copies create drift,
waste disk, and multiply update failures. Still freeze the live profile list and verify
read/execute access from every profile home; host readability does not prove access from
profile-specific sandboxes, so report those as separate checks.

Build the repository manifest from authoritative sources in this order:

1. Query the owning GitHub organization/account and include every repository matching the
   user's stated lifecycle rule (for example, non-archived repositories with a non-empty
   default branch). Persist the full query snapshot and reconcile the included and excluded
   identity sets in code.
2. Add only locally installed runtime sources with a concrete Git origin, such as the Hermes
   source, enabled default-profile plugins, installed skill-library source repositories, and
   required local MCP servers. Deduplicate owner/repo case-insensitively.
3. Do **not** turn arbitrary GitHub URLs mentioned in SKILL.md examples, reference material,
   archived skills, temporary worktrees, review clones, backups, or security-remediation
   folders into managed repositories — textual mention is not an operational dependency.

Use a deterministic manifest with canonical owner/repo identity, URL, recorded default
branch, category, collision-safe directory name, and inclusion evidence. Keep archived or
empty repositories in explicit exclusion evidence rather than silently dropping them.
For large fleets, create atomic shallow single-branch clones to limit disk use. The updater
must take an exclusive lock, fetch/prune, and fast-forward only clean clones attached to the
recorded default branch with a matching origin. Dirty, detached, locally ahead/diverged, or
origin-mismatched clones are unsafe skips: never reset, clean, stash, force-checkout, rewrite
remotes, or push from the fleet updater. Log structured per-repository receipts and return
nonzero on any hard failure or unsafe skip so scheduled health remains honest.

Schedule this deterministic updater as a script-only/no-agent Hermes cron. Before creation,
match existing jobs by normalized name and script to avoid duplicates; after creation, read
back the exact ID, schedule, active state, script, workdir, delivery, failure-delivery, and
session-attachment fields. A configured schedule is not proof of execution, so distinguish
cron readback from an observed successful scheduled run.

## 5. External writers are real — verify, then stop if the tree moves

Other processes actively rewrite `~/.hermes`:
- A standing backup rsyncs `~/.hermes/ → /Volumes/HermesBackup/` with `--delete`
  (backup direction: it reads source, does not mutate it — confirm direction via
  `ps -p <pid> -o command=` before blaming it).
- Other agent sessions and gateways rename, reorganize, and re-sync profile skill
  trees concurrently. A directory verified OK two minutes earlier can be gone.

Rules:
- If a just-verified location disappears or changes mid-work, re-inventory the whole
  set once. If the whole category moved, an external actor is mid-sync: STOP writing,
  document the state in `~/.hermes/tmp/` (timeline + open decisions), and report to
  the operator rather than fighting a moving tree.
- After propagation, a final `skill_view(name=...)` proves the default-profile copy
  loads; a per-profile hash loop proves the rest. Both are required for "system-wide".

## 6. Stale terminal cwd after renames

The terminal tool's persistent cwd survives across calls. If you `cd` into a directory
and later operations rename/delete it, every subsequent terminal command fails with a
`cd: No such file or directory` that mentions no `cd`. Fix: run one command with an
explicit `workdir` (e.g. `/Users/operator`), which resets the persistent cwd.

## 7. Definition of done

For skills, report: `N/N locations hash-verified (SHA prefix <16>)` plus the one-line
load check. For plugins, report digest count, enabled-config count, and fresh-session tool
or skill discovery separately. Never claim system-wide from a partial count, and never
claim all machines from one host's profile count. If an external actor is still moving
the tree, say exactly which locations are verified and which are in flux — do not average
it away.
