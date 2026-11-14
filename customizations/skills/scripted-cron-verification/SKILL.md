---
name: scripted-cron-verification
description: "Verify scripted cron jobs actually ran (3-source check)."
version: 1.0.0
author: Hermes
license: MIT
metadata:
  hermes:
    tags: [cron, verification, debugging, hermes, operations]
    related_skills: [hermes-brain-backup]
---

# Scripted Cron Job Verification

## When to Use
- the operator asks "is this working?" / "did the cron run?" about a scheduled job.
- A cron job that wraps a `script:` produces no visible results (sheet not updated, file missing, downstream job starved).
- Before declaring a scheduled pipeline healthy after any incident.

## Core Rule
The job record's `last_status: ok` reflects the AGENT TURN, not the wrapped script's exit
code. A script job can crash (non-zero exit, auth failure, timeout) while the agent turn
still completes — often by posting the failure message — and the record still reads `ok`.
Never diagnose from `last_status` alone.

## The 3-Source Check (in order)
1. **Job record** — `cronjob_manage action=list`, find the job: `last_run_at`,
   `last_status`, `last_error`, `next_run_at`. No `last_run_at` + future `next_run_at` =
   it never fired (scheduler problem, not script problem). `last_error` on a `no_agent`
   job carries the script's stdout/stderr directly.
2. **Run output file** — `~/.hermes/cron/output/<job_id>/<YYYY-MM-DD_HH-MM-SS>.md`.
   For `script:` jobs whose script exits non-zero, a "## Script Error" section carries the
   script's stderr/traceback EVEN WHEN the agent turn reports `ok`. The agent's final reply
   ("## Response" section) is what got delivered to the user — compare it to what the user
   says they actually received.
3. **The script's own success artifact** — the state file it writes, the file it updates,
   the table it appends: the STRONGEST proof of success. If its timestamp is OLDER than
   `last_run_at`, that run failed regardless of what (1) and (2) say. Prefer designing
   scripts to write a small state file (`last_run`, totals) exactly so this check is one
   `json.load` away.

## Delivery proof is a SEPARATE check
A job can run perfectly and still reach nobody. Run proof and delivery proof are
different questions with different evidence:

1. **Ground truth is the delivery ledger**, not the job record:
   `~/.hermes/cron/deliveries.db` — `deliveries.status` (`pending`/`delivering`/
   `delivered`/`failed`/`unknown`/`suppressed`) and `delivery_tombstones` for
   terminal outcomes. Read it with
   `sqlite3 -header ~/.hermes/cron/deliveries.db "select execution_id,status,created_at,substr(error,1,120) from deliveries order by rowid desc limit 5;"`.
2. **`last_status: ok`, `last_delivery_error: null`, and even
   `executions.delivery_outcome = 'delivered'` do NOT prove delivery.** The
   execution row records the run's own claim; it can read `delivered` while no
   delivery row exists and the gateway log shows a refusal.
3. **A notification fired while the target chat is mid-turn is refused, not
   dropped.** `~/.hermes/logs/gateway.log` shows
   `Watch pattern notification — injecting ...` followed by
   `Watch notification not admitted for <platform> chat=<id>: admission_conflict`.
   It is requeued with backoff and lands only after the occupying turn ends.
   Repeated `admission_conflict` lines mean *still queued* — never report them
   as delivered.
4. **You cannot prove delivery from inside an active agent turn on that same
   chat**: the turn holds the admission lane, so the probe is guaranteed to be
   refused. Fire the probe, end the turn, and read the ledger afterwards.

Corollary for design: an empty-stdout success on a silent job proves nothing at
all, because nothing was ever sent. Verify the delivery path with a throwaway
`no_agent` probe that prints one fixed line, confirm its `delivered` row in the
ledger, then delete the probe job and its script.

## Failure triage: classify before changing code

Fixing a failing scheduled job starts with classification, not editing. The class determines
whether the fix is code, data, credential, or nothing at all:

| Symptom | Class | Where the fix lives |
| --- | --- | --- |
| `HTTP 401` from a vendor API | **credential** | the secret file, not the script |
| `TimeoutExpired` on a wrapped CLI | **launcher/env** | the CLI entry point + a preflight |
| `HTTP 403` on a site that answers curl | **request fingerprint** | the script's headers |
| Intermittent single-call failure inside a loop | **shared state** | re-read/retry, not logic |
| Exit 2 / explicit FAIL output | **fail-closed by design** | nothing — the gate is working |
| `can't reach the model provider`, interrupted model response | **transient provider** | nothing; verify the model slug still exists first |

Rules for each:

- **Cluster the fleet before touching any job.** When many jobs are red in the same window, count them
  by root cause first: a dead vendor credential, one shared token file, or one broken browser
  dependency typically explains most of them. Fix and verify the shared cause, then re-run the
  dependents — their errors are symptoms, and reporting 15 separate incidents misrepresents the
  blast radius as 15 problems when it is three.
- **Fix upstream-to-downstream when jobs chain.** A refresh job feeding a forecast/dashboard job must
  go green first; re-running the downstream job against a stale source produces a green exit code
  over bad data. State explicitly which job you verified at the head of the chain.

- **A 401 is a credential class until proven otherwise.** Probe the same credential through the
  platform's own integration (its MCP tool) — if the script AND the MCP both 401, the credential
  is dead and no amount of code change fixes it. Report it as a blocker for the user and name the
  exact file + key to replace; never rotate, guess, or fabricate a secret. Conversely, if the MCP
  works and the script fails, it is a path/lookup bug in the script.
- **Distinguish a live failure from a stale one.** `last_error` persists after a later success, so
  `last_error != null` alone overstates the blast radius. Sort by `last_run_at` age and report the
  age: a job that errored 100h ago and has since succeeded is history, not an incident.
- **Re-run the script directly to get the whole traceback.** The delivery copy in
  `~/.hermes/cron/output/<job_id>/` truncates and mangles absolute paths, so the useful frame is
  usually cut. Run `python3 ~/.hermes/scripts/<name>.py` yourself before theorising.
- **A job that now completes with a failed self-check is NOT fixed.** Exit 0 plus
  `0/N verified`, `0/N match`, or an unchanged read-back means the work did not land. Say
  "runs but does not do the work" and keep it open; never upgrade it to fixed on the exit code.
- **Make the script diagnosable as part of the fix.** A bare `HTTP 500` or `Unauthorized` is
  untriable. `except HTTPError as e: raise RuntimeError(f"HTTP {e.code} from {url}: {e.read()[:600]}")`
  turned an opaque 500 into the exact upstream message (a missing spreadsheet column header) on the
  first run. Wrap every external call this way when the fix is otherwise blocked.
- **Re-run through the scheduler, not only by hand.** A manual `python3` run proves the script, not
  the cron path; finish with `cronjob_manage action=run` and read the outcome file.

## Pitfalls
- `script:` takes a **filename relative to `~/.hermes/scripts/`**, never an absolute or
  `~/` path — creation is rejected otherwise. Put the script there and pass just the
  basename.
- `no_agent` jobs deliver stdout verbatim and send **nothing at all** when stdout is
  empty. For watchdog jobs the wrapper must stay silent on success and print only the
  alert body on failure; a wrapper that always prints turns into a daily nag.
- `.fire-*.lock` files under `~/.hermes/cron/` prove the SCHEDULER fired the job at that
  minute — not that the script succeeded. Don't use them as health evidence.
- A run-output file exists for every completed agent turn; an absent file for the expected
  timestamp means the turn never finished (gateway restart, model error) — check
  `last_fire_error` in the job record.
- When the check finds failure: read the traceback in the run output and fix the ROOT
  cause (auth failures → the matching re-auth skill, e.g. google-oauth-refresh-token-regen;
  quota/rate-limit → pacing; data-shape → the script's selftest). Then verify the fix by
  `cronjob_manage action=run` (fires in background; confirm the state artifact advanced)
  before telling the user it's healthy. A manual one-off run of the script is fine for
  debugging but does NOT prove the cron path works — only a `run` action or the next real
  tick does.
- `last_status: ok` + delivered success message + stale state artifact = the script wrote
  the success path without doing the work (e.g. diffed against stale in-memory state).
  Re-read the script's idempotency/diff logic: it must diff against values it just READ,
  not values it computed.
