---
name: shared-repository-fleet-management
description: Use when managing shared Git repo fleets for agents.
version: 1.0.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [git, repositories, profiles, cron, fleet]
    related_skills: [local-repo-setup-verification, scheduled-job-routing, cross-profile-skill-propagation]
---

# Shared Repository Fleet Management

## When to Use

Use this skill when several same-host agents or Hermes profiles need a canonical set of Git repositories, when “every repository” must be inventoried and reconciled, or when that fleet needs a safe recurring updater.

Use one canonical repository root when many same-host Hermes profiles need the same source code. Do not duplicate clones per profile: freeze the live profile set, prove every profile can read the shared absolute path, and state explicitly that same-host profile coverage is not all-machines coverage.

## Procedure

### 1. Define the inventory contract before cloning

Choose authoritative sources rather than scanning arbitrary URLs in skill prose.

- For a company GitHub organization, query the organization directly and include every non-archived repository with a nonempty default branch unless the user specifies a narrower rule:
  ```bash
  gh repo list <org> --limit 500 \
    --json nameWithOwner,isArchived,defaultBranchRef,visibility,url,pushedAt
  ```
- Fail closed if the result reaches the query limit; pagination/completeness must be proven before claiming “every repo.”
- Record archived and empty/no-default-branch repositories as explicit exclusions with their source metadata.
- Add runtime dependencies only from bounded installed Git roots—agent source, default-profile plugins, installed skill-source repos, and required local MCP servers. Never treat example URLs, unrelated home clones, backups, review worktrees, or profile duplicates as fleet membership.
- Normalize and deduplicate identities case-insensitively as `owner/repo`; use collision-safe directories such as `owner--repo`.
- Freeze live profiles from `hermes profile list` or actual profile homes. Recount on every rebuild.

The manifest must carry schema version, collection timestamp, inventory-complete status, frozen profiles, category counts, original organization snapshot, exclusions, and for each repository: identity, category, canonical URL, default branch, directory, metadata, and inclusion source.

### 2. Build one shared, shallow fleet

Store the fleet under a stable absolute root such as `~/.hermes/shared/repos/` and document that all same-user profiles access it directly.

For missing repositories, clone atomically on the same filesystem:

```bash
git clone --depth 1 --single-branch --branch <default> <url> <staging>/clone
```

Before renaming staging into place, verify:

- origin normalizes to the manifest identity;
- HEAD is attached to the recorded default branch;
- repository is shallow;
- worktree is clean;
- destination did not appear during cloning.

Never populate the fleet by copying an existing worktree: untracked files, local configuration, and secrets can travel with it. Preserve failed staging directories for evidence unless cleanup is separately authorized.

### 3. Update conservatively

Use a deterministic script with an exclusive nonblocking lock and persistent JSONL receipts. For every existing clone:

1. Verify it is a standalone clone, not a symlink or linked worktree.
2. Verify origin identity, clean status, attached default branch, and required compatibility metadata.
3. `git fetch --prune origin`.
4. Compute ahead/behind state against `origin/<default>`.
5. Permit only `git merge --ff-only origin/<default>` when the local branch is not ahead or diverged.
6. Recheck clean status and branch after network I/O and before the merge.

Never reset, clean, stash, force-checkout, change remotes, or push. Dirty, detached, wrong-branch, origin-mismatch, ahead, diverged, or malformed clones are unsafe skips and must make the run nonzero. Continue processing independent repositories so one failure does not hide fleet-wide status. Full success should be silent; failures should print one concise summary and point to the receipt log.

Use an allowlist of sanitized Git failure categories in logs; never persist raw credential-helper output or credential-bearing URLs.

### 4. Test before scheduling

Tests must use local bare repositories and cover:

- URL normalization, deduplication, manifest count reconciliation, and exact organization inclusion/exclusion reconciliation;
- atomic shallow clone and idempotent clean fast-forward;
- dirty, detached, wrong-branch, origin mismatch, locally ahead, and diverged safety stops;
- lock contention, failed clone preservation, retry-once behavior for clearly transient failures, and sanitized failure output;
- any declared filesystem compatibility exception.

Run the real updater once after tests. A script or cron configuration is not complete until the real manifest run exits zero and exact clone count equals the manifest identity set.

### 5. Schedule exactly one script-only job

For a deterministic updater, use a Hermes `no_agent=true` cron with the script under `~/.hermes/scripts/`. Before creation, search all default/profile cron stores by normalized name and script; update an exact match rather than creating a duplicate, and stop on ambiguous duplicates.

Prefer local success delivery and an explicit failure target. Set workdir to the shared root and `attach_to_session=false`. Read back the exact job ID, enabled state, schedule, no-agent mode, script, workdir, success delivery, failure delivery, and attachment setting.

### 6. Final acceptance

Generate machine-readable verification and require all of the following:

- authoritative inventory collection completed and reconciled;
- manifest identities and directories are unique;
- canonical clone directories equal the manifest directory set exactly;
- every clone passes origin, branch, clean, shallow, and compatibility checks;
- every frozen same-host profile can resolve and read the root and clones;
- tests pass and the real updater exits zero with successes equal to manifest count;
- exactly one cron matches and its full configuration reads back correctly;
- source working trees used for discovery are unchanged.

Report exact totals by category, exclusions, profile coverage, tests, updater result, cron ID/schedule, disk usage, and any limits. Keep “scheduled execution observed” separate from “cron configuration verified.”

## Filesystem compatibility

For repositories that intentionally track case-fold-colliding paths on a case-insensitive filesystem, do not weaken cleanliness globally or normalize filenames. Use a single-repository, manifest-declared exception with strict tree and index verification. See [references/case-insensitive-filesystems.md](references/case-insensitive-filesystems.md).
