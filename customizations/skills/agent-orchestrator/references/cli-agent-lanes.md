# Running a coding lane as a CLI agent

Use when a lane must edit files, run a database or test suite, and commit to a branch. Native delegation can be routed to a small model without the parent noticing; a CLI coding agent gets a capable model with a real shell, and the parent keeps the publish step.

## 1. Prepare the workspace before launching anything

The parent does this, so the lane never needs network access for setup:

```bash
BASE=~/.hermes/cache/scratch                     # per the runtime's scratch convention
d="$BASE/cd-<lane>"
git clone -q <local-reference-clone> "$d"        # or: gh repo clone <owner>/<repo> "$d"
git -C "$d" remote set-url origin https://github.com/<owner>/<repo>.git
git -C "$d" checkout -q -b agent/<lane-name> main
/opt/homebrew/bin/python3.x -m venv "$d/.venv"   # the interpreter the repo needs, not the system one
"$d/.venv/bin/pip" -q install -r "$d/requirements.txt"
printf '%s\n' 'PROMPT.md' 'codex-run.log' >> "$d/.git/info/exclude"
```

- **One directory per lane, absolute path.** A relative clone target lands every lane in the parent's cwd.
- Write the lane's contract to `PROMPT.md` inside that directory and exclude it from git. Keep the brief in the file, not in the launch command, so the lane can re-read it and the parent can diff it.
- Never put a credential in the prompt or the repo. If the lane needs a database, it creates its own; the connection string stays in a chmod-600 file it deletes at the end.
- The lane inherits the machine's global git identity, which is usually not the parent's. Either set `user.name`/`user.email` on each lane command, or record the identity now: you will need it to tell lane commits from foreign ones before rebasing or squashing.

## 2. Canary the route, then fan out two at a time

```bash
codex exec -m <model> --skip-git-repo-check -s read-only \
  -C "$d" "Reply with exactly: CANARY-OK"
```

- A canary proves the model slug and the account work before four lanes depend on them. Expect it to report a plausible token count — the instruction set loads even for a one-word reply — so a canary is not free.
- Run **two lanes at a time**, not four. Subscription and per-account caps fail as "provider returned error" after the full retry window, and a wide batch loses everything at once.
- If the machine has a large rules tree (`AGENTS.md` files scattered under the home directory), the agent enumerates them as workspace rules and burns context before reaching the repo: pass the CLI's rule-skipping flag (`--ignore-rules` for codex) so the lane starts at the repo's own README.

- **Check what model native delegation actually routes to before depending on it.** `delegate_task(action='list')` reports each child's real `model`. In this environment children ran on `prism-ml/ternary-bonsai-2-27b`; all three siblings rate-limited out with "Provider returned error" after burning their full retry windows (~45 minutes each, no artifact, no partial). Two separate batches died identically before the pattern was obvious.
- Corollary: a whole fan-out on one route is a single point of failure. When the first lane reports a provider error, do not dispatch a fourth — take that lane yourself, or move to a CLI agent in a different model family (claude, codex). Three failures on the same route is evidence about the route, not about the tasks.
- A stopped or interrupted lane still yields useful partial findings. Mine them, but verify every figure before adopting: in this run roughly half of one interrupted report was wrong (a price contradicted by the provider's own published page) and half was genuinely new and worth keeping. Record the rejected figures and the reason, so they are not reused later as if verified.

## 3. Launch in the background with notification

```bash
cd "$d" && codex exec -m <model> -C . -s danger-full-access --color never \
  "$(cat PROMPT.md)" 2>&1 | tee codex-run.log
```

Run it detached with completion notification so the parent is not blocked. A permissive sandbox mode is a deliberate choice for a lane that must spawn a database and commit; it is only acceptable because the workspace is a throwaway clone of a known repo and the parent reviews every diff.

## 4. What the prompt must contain

1. **Read-first list**, in order, ending at the files the lane will touch.
2. **The branch name**, and "commit there; do not push, do not open a pull request, do not merge".
3. **Owned scope** (exact paths) and **forbidden scope** (every path another lane owns, plus anything the owner completes afterwards).
4. **The exact local service recipe** with the lane's own port and data directory, and the command whose output it must paste as evidence.
5. **A required positive control** for anything that emits "no failures" by default (a deliberately broken fixture the check must catch).
6. **Finish protocol**: files added, commands run, real output pasted, what is incomplete, and "if a step is impossible in this sandbox, say so — never fabricate a result".
7. **A batch instruction** for long extractions: commit after the first slice, then expand, so a timeout loses one slice and not the work.

## 5. Acceptance: exit code plus artifact

An exit 0 means the process ended, not that the lane worked.

```bash
git -C "$d" log --oneline main..HEAD          # commits, or none
git -C "$d" diff --stat main..HEAD            # files and sizes
git -C "$d" status --short                    # uncommitted leftovers
wc -l <artifact files>                        # zero-line outputs are a failed lane
```

Re-run the lane's stated verification yourself. A lane can exit 0 while every entity file it produced is 0 bytes, and its own closing line may say so — read the artifact, not the summary.

### Publishing the lane's branch (the parent's step, not the lane's)

1. `git fetch origin` and check whether the default branch moved while the lane ran. A green measured on the lane's original base is stale the moment anything merged.
2. Rebase the lane branch onto the current default — reviewers ask for linear history, not merge commits — and re-run **the whole suite**, not only the lane's files.
3. Expect the test count to change and quote the split: discovery walks the completed tree, so tests that landed on the default branch are now collected beside the lane's (`Ran 41` = the lane's 24 plus 17 from an adapter that merged meanwhile, not a lane that added 17).
4. `git push --force-with-lease origin <branch>`, then open the pull request with the re-run evidence.

Before any force-push, list authorship across the branch: `git log --format='%h %ae %s' origin/<branch>..HEAD`, and confirm which commits are the lane's and what they touch. A lane committing under the machine identity looks foreign; a careless squash or reset then discards real work while looking like cleanup.

If the forge rejects the push server-side (`remote: fatal error in commit_refs`, an HTTP rejection with no hook message), do not retry in a loop. Probe a throwaway branch to separate repo-wide from branch-specific, try the other transport (https vs ssh) to separate auth from server-side, and check `permissions`, `rulesets`, `branches/<name>/protection` and `archived` through the API. Then produce `git bundle create <file> origin/main..HEAD` and `git diff origin/main..HEAD > <file>.diff`, verify the diff applies to a fresh clone of the current default, and hand both to the owner. Verified work stranded locally is a blocker to report, never a delivery.

## 6. Shaping an honest partial into a publishable artifact

When the analysis is sound but the rows are blocked on unevidenced facts:

- Delete the empty output files and make the builder refuse to emit an empty one, so a later dry-run cannot report success over nothing.
- Add a README inside the delivery folder stating what the folder is **not** (e.g. not loadable), what it proves, and the exact inputs that would unblock it.
- Open the pull request as a **draft**, so no owner-side load or publish step runs against it.
- Put the blocked inputs in the PR body as questions for a named owner, not as a vague "needs more data".
- Commit the parent's cleanup as its own commit with the reason in the message; the diff then shows what was changed and why.

## 7. Recovery

### Bash launcher pitfalls that silently produce empty lanes

Two failure modes each cost a full 45-minute lane run and produced a report that looked like a refusal rather than a bug:

1. **`&&` precedence swallows the background split.** In `cd dir && prep && (claude ...) & (codex ...) & wait`, the `&` splits the whole `&&` list, so only the first subshell inherits the `cd` and the prepared files; the second runs in the original cwd against a file that does not exist yet and receives an empty prompt. The CLI then politely asks "What would you like me to work on?" and exits 0. Symptom: a lane log a few hundred bytes long containing that question, while `ps` still shows the process.
2. **A cleanup glob eats the input.** `rm -f rereview_*.md` matches the brief itself when the brief is named `rereview_brief.md`. The subsequent `cat` fails, the prompt is empty, and if the shell is chained with `&&` the lane never launches at all.

Guard both by construction, not by care:

- Read the brief ONCE into a shell variable, echo its character count, and refuse to launch below a floor (400 chars works): `PROMPT="$(cat "$BRIEF")"; [ ${#PROMPT} -lt 400 ] && die "brief fragment"`.
- Never clean with a glob that can match an input. Delete explicit filenames, or clean in a separate step before the brief exists.
- Put `cd` inside each lane's subshell rather than relying on an earlier `&&`.
- Have each lane write its own log and record `wait` exit codes per lane.
- Add a `--selftest` that sends a two-word prompt through one lane and asserts the reply text. A launcher whose selftest has never passed is not proven.

A repaired launcher meeting all of the above lives at `<scratch>/run_lanes.sh` (usage: `run_lanes.sh <brief.md> <outprefix> [claude:opus codex:default]`, plus `--selftest`). Prefer it over writing a new inline chain.

- A lane that produced nothing (no commits, no files) is a route failure, not a contract failure: stop it before re-dispatching, fix the route or the workspace, and retry only that lane.
- A lane that produced analysis but no artifact is a contract failure: narrow the scope (one slice, one check) rather than repeating the same instruction.
- Preserve the failed lane's transcript path in the final report; it is the only record of what the route actually did.
