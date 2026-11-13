# Case-insensitive filesystem compatibility

Git can track both `README.md` and `readme.md`, while a case-insensitive filesystem materializes only one worktree path. A correct clone can therefore appear dirty immediately even when hooks and filters are disabled.

## Diagnose before adding an exception

Require all of this evidence:

```bash
git ls-tree -r --name-only -z HEAD
git ls-files -s -- <path-a> <path-b>
git status --porcelain=v1 --untracked-files=all
git diff -- <reported-path>
```

Confirm that:

- two distinct tracked paths case-fold to the same name;
- the paths have distinct index/blob identities when expected;
- the dirty state appears immediately after a fresh clone;
- no hook, filter, user edit, or unrelated dirty path explains it.

## Narrow manifest contract

Declare the exception only on the affected repository, for example:

```json
{
  "case_insensitive_fs_skip_worktree": ["README.md"],
  "case_fold_collisions": [["README.md", "readme.md"]]
}
```

Validation must require:

- a nonempty deduplicated list of safe relative paths—no absolute paths, `..`, or NUL;
- distinct exact paths in each collision pair that case-fold equally;
- every skipped path is covered by a declared pair;
- the repository tree contains both exact paths;
- the exception is allowlisted to the reviewed repository identity, not available to arbitrary manifests.

## Fresh clone behavior

Only during a fresh clone created by the updater:

1. Verify each declared path is tracked.
2. Verify both exact collision paths from `git ls-tree -r --name-only -z HEAD`.
3. Set the narrow index bit:
   ```bash
   git update-index --skip-worktree -- <declared-path>
   ```
4. Read the index bits back and require exactly the declared set.
5. Require clean status under the explicit policy before atomic rename.

For existing clones, verify the exact bits but never silently add or repair them. Missing, extra, or stale bits are an unsafe skip. Recheck the collision and bits before fetch, against the incoming tree before fast-forward, and again after merge.

## Limits

`skip-worktree` hides worktree differences at the declared path. A clean status proves cleanliness only under the documented exception; it cannot prove both colliding blobs were materialized or detect edits hidden at that path. Keep every other path under normal status checks, preserve the original failed clone as evidence, and require a dedicated regression fixture on the target filesystem.
