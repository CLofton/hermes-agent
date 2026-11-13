---
name: hermes-brain-backup
description: "Hermes brain backup system: scripts, restore, cron job."
---

# Hermes Brain Backup

Two-layer backup of the Hermes brain (~/.hermes), automated nightly at 3am CT.

## What exists (built 2026-09-08)

- **Script:** `~/.hermes/scripts/brain_backup.py` — commands: `push` (offsite), `local` (full mirror), `verify`, `weekly` (dated core tarball, Sunday), `core` (stage+encrypt only).
- **Watchdog wrapper:** `~/.hermes/scripts/brain_backup_nightly.sh` — silent on success, one alert line on failure. Cron job: "Nightly Brain Backup (Hermes core + full local mirror)" (job_id 60615ca8d027, 0 3 * * *, no_agent, delivers to the operator's Telegram only on failure).
- **Offsite (L1):** encrypted core brain -> private repo `github.com/<your-account>/hermes-brain-backup`. Core = SOUL.md, config.yaml, memories/, memory_store.db, skills/, cron/, plans/, state/, the operator-daily-todos.md + per-profile (config/skills/memories/cron/SOUL). Credentials (.env, secrets/, auth tokens) NEVER included. age-encrypted in <95MB parts (GitHub 100MB file limit). Orphan-branch force-push keeps remote at one snapshot's size.
- **Local full (L2):** rsync mirror of all of ~/.hermes -> `/Volumes/HermesBackup/hermes-current` (APFS volume on the internal SSD, created via `diskutil apfs addVolume disk3 APFS HermesBackup`). Excludes: cache, tmp, logs, chrome profiles, hermes-agent app, backups/. SQLite DBs copied via `sqlite3` online backup, not rsync.
- **Keys:** private key `~/.hermes/secrets/age-key-hermes-backup.txt` (0600), pubkey `~/.hermes/secrets/age-pub-hermes-backup.txt`. The private key is the ONLY way to decrypt — it never leaves the machine.

## Restore

Offsite core brain:
```bash
# clone the repo, then (age files CANNOT be concatenated before decrypting):
for f in brain-latest.part-*.age; do /opt/homebrew/bin/age -d -i ~/.hermes/secrets/age-key-hermes-backup.txt "$f"; done | tar xzf -
```
Full local mirror: everything under `/Volumes/HermesBackup/hermes-current/` — copy back over ~/.hermes (stop the gateway first).

## Pitfalls
- macOS system python is 3.9 — no `copytree(ignore_patterns=)`, no `Path.is_mounted()`; the script's `copytree_no_sockets` handles sockets (live gateway sockets live in state/) and globs manually.
- **Make core staging safe against live-tree and permission hazards.** The watchdog runs `push` first, so any staging failure also blocks `local` and `verify` and can freeze both backup layers.
  1. Preserve skill symlinks with `shutil.copytree(..., symlinks=True)`; following relative or dangling links causes `ENOENT` and can inline external skill trees into the snapshot.
  2. Ignore `*.db-wal`, `*.db-shm`, and `*.db-journal`; live SQLite sidecars can vanish after directory scan and are not valid standalone backups. Keep the per-file tolerant fallback for other vanish-mid-copy races.
  3. Before deleting `CORE_STAGE`, make only staged directories owner-readable/writable/executable without following symlinks, then call `shutil.rmtree`. `copytree` preserves source modes, so a copied `0555` skill directory makes child unlink fail even when its files are merely `0444`. Use the same cleanup helper for stale-stage removal and post-archive cleanup; never chmod the source tree or alter archived member modes.
  Test both cleanup paths with a temporary `0555` directory and `0444` file, assert the test fails with plain `rmtree`, and verify source and tar member modes remain unchanged.
  After any script fix, run `push`, `local`, and `verify`; run `weekly` when a scheduled weekly snapshot was missed. Confirm `last-backup.txt` advanced, read back the remote `main` commit, and require a later cron run to reach a durable `ok` state before calling the scheduler healed.
- GitHub rejects single files >100MB; keep parts <95MB. `age`-encrypted files can't be `cat`'d together before decryption — decrypt each part, then pipe the decrypted stream.
- The offsite git dir uses fresh orphan branches per push (`snap-<ts>`) and prunes old ones; don't switch it to normal commits or old blobs accumulate and pushes start failing the 100MB check.
- `verify` = file presence + `PRAGMA integrity_check` on state.db, kanban.db, memory_store.db in the mirror.
- When the watchdog alert shows only the final traceback lines, inspect the saved cron run artifact before editing; the wrapper intentionally compresses failures with `tail -3`, which can hide whether cleanup failed before or after archive creation.
- Do not accept an interrupted direct cron invocation as verification. If the command owner exits before the scheduler records a terminal state, the run becomes `unknown`; rerun through a tracked process and verify the durable cron status separately.
- rsync exit 23 = files vanished mid-copy. This happens in practice: other Hermes sessions/agents actively rewrite ~/.hermes/skills (whole directories appearing and disappearing). The script tolerates rc 23 with a warning; it is NOT a backup failure — the nightly re-sync heals it. Only rc 23-tolerant runs count as success for the watchdog.
- If /Volumes/HermesBackup is missing (SSD replaced), recreate: `diskutil apfs addVolume disk3 APFS HermesBackup`.
- Time Machine is still NOT configured — the HermesBackup volume is on the SAME SSD it protects. For a true whole-machine safety net the operator still needs an external drive.
- iCloud Desktop&Documents sync is ON (obsidian vault + memory mirror files are covered); ~/.hermes itself is never seen by iCloud.
