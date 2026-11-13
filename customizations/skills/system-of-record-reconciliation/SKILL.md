---
name: system-of-record-reconciliation
description: Use when reconciling two systems of record row by row.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [data-quality, migration, reconciliation, evidence]
    related_skills: [jev-decision-api, data-model-conformance-testing]
---

# System-of-record reconciliation

## When to Use

- Two systems hold the same entities and you must decide, field by field, which value is correct.
- "Push all the data from X into Y" — a legacy app being retired, a spreadsheet a team still edits, a warehouse mirror, or a successor populated at cutover.
- A migration, cutover or sync left two copies that disagree.
- Someone asks you to resolve conflicts between a source of record and its successor.

Do **not** use this for schema/contract validation (see `data-model-conformance-testing`) or for a single-field lookup where one API call answers it.

## The stance that prevents the damage

**The target is almost never empty, and it is often ahead of the legacy source.** The instinct to "push all the legacy data" produces a regression: successors accumulate fixes the legacy system never saw. Measure before writing. In one reconciliation the target already held 271 of 281 records and was *correct* on 204 of 308 disagreements.

Establish these three facts before writing anything:

1. Do the record identities match? Join on the stable uuid, not the human code — codes are frequently re-keyed (see pitfalls).
2. What does the target already hold per field? A value the target has and the source lacks is a deliberate sync result, not a hole.
3. Who writes the target, and from where? If a scheduled sync feeds it, its values may trace back to the very source you were told to distrust.

## Procedure

### 1. Export both sides completely

Pull every row and every column, not a sample. Record exact counts for both sides and the join-key overlap; the three numbers are your acceptance baseline later.

### 2. Classify the drift into four buckets — before counting conflicts

For every shared record and field, assign exactly one:

| Bucket | Meaning | Action |
|---|---|---|
| `format_only` | Same fact, different encoding | None — never write |
| `app_ahead` | Target has a value, source is empty | Keep target |
| `source_gap` | Source has a value, target is empty | Safe to fill |
| `real_conflict` | Both have values that genuinely disagree | Adjudicate |

The raw string diff over-reports badly. A first-pass diff reported 345 conflicts; semantic canonicalisation cut it to 308 and the difference was entirely encoding. **Never report a conflict count taken from an uncanonicalised diff.**

### 3. Fill the blanks — this needs no adjudication

Blanks in the target that the source can fill are additive and safe. Two exclusions, both deliberate:

- **Never back-date audit stamps** (`created_at`, `updated_at`). A later sync writing an older timestamp destroys the target's own change history. Report them as skipped-by-policy instead.
- Re-check emptiness at write time and skip any cell the target has populated since you read it.

### 4. Adjudicate real conflicts by evidence strength

Work down this ladder and stop at the first rung that answers:

| Rung | Evidence | Notes |
|---|---|---|
| 1 | **Independent source of the same fact** | A warehouse table, a CRM record, a census, a geocoded location. Strongest — settles without judgment. |
| 2 | **Employment / validity reality** | Does the named owner still work here, and do they hold the job title the field names? A school assigned to a departed employee is wrong regardless of recency. |
| 3 | **Change-log provenance** | Who wrote this value, and when. A value written by a named human after cutover outranks one nobody ever logged. |
| 4 | **Newest logged transition** | For state machines (stage, status), the latest recorded transition wins — and see the stale-field pitfall. |
| 5 | **Calibrated model judgment** | See the Jev policy below. |
| 6 | **Human** | Everything the ladder cannot reach. Report it with its probability, do not guess. |

Codify rungs 1–4 in code so each decision carries a checkable reason string. That reason is the artifact — it is what makes a 45-row write auditable months later.

### 5. Write only the source-wins decisions, then verify the effect

Apply only cells where the ladder says the source value is correct. After writing, verify by **re-reading the value and re-running the whole classification**, then reconcile the arithmetic:

```
conflicts_after == conflicts_fixed + decided_keep_target + still_open + unexplained
```

`unexplained` must be zero. If it is not, a write landed on the wrong record or a decision was recorded twice. Do not report "resolved N" without this equation balancing.

Note that "resolved" includes decisions to keep the target value — those conflicts still appear in a raw re-diff. Say so explicitly, or the next reader will think nothing happened.

### 6. Write the correction into the target's own change log

A corrected value with no audit row is indistinguishable from a silent edit: the target's per-record history panel shows the new value against a blank actor or the last automated sync, and the human reviewing it cannot tell a reconciliation from a bug.

Write one history row per corrected cell — entity key, field, old value, new value, actor, timestamp — in the same pass as the value write, and make the actor string say what it was (system, date, whose approval). Do this in the same pass because the *old* value only exists in your classification output; retrofitting the log later means reconstructing values you have already overwritten.

Count the history rows you add and read one back. The drawer is the artifact a human actually opens.

## Judgment policy

**the operator's standing rule: accept a Jev answer at ≥ 0.80 probability, otherwise leave it for a human.** Record the probability on every model-decided row. Below the bar, the correct output is an open item with its number, never a quiet coin-flip.

Before reaching for a model, ask whether the cases are really N decisions. Identical disagreements collapse into one rule-level question — see `jev-decision-api` ("Batch by shared cause, not by row").

## Pitfalls

- **A synced copy inside the target is not independent evidence.** If the target's value was written by a sync from the source you were told to distrust, it corroborates nothing. Check the `changed_by` actor: a sync stamp means the value is downstream, and you must find a genuinely external source or leave the item open.
- **Both systems' change logs may record the same events.** After a cutover, the successor's log is often seeded from the legacy log. Identical timestamps, actor and old→new mean the *stored field* has fallen behind its own log — the target's current value is stale and the legacy value is correct. Verify by comparing the log entry to the stored value, not system against system.
- **Human codes get re-keyed; uuids do not.** Two records showing different codes for the same entity are a code migration, not a disagreement. Resolve against an external carrier of the code, and expect it to settle wholesale in one direction.
- **Canonicalise before comparing.** At minimum: month names vs ISO dates (`August` = `2025-08-01 00:00:00`), state-machine synonyms (`Active` = `Already started`), `/`-vs-ISO date order, one-string-is-a-prefix truncation, and invisible characters. Zero-width spaces (`\u200b`) inside text fields create phantom diffs where the visible text is identical.
- **`UNASSIGNED` is absence, not a value.** A real current owner beats `UNASSIGNED`; treat it as `app_ahead`, not a conflict.
- **Owner and assignment fields need job-title checks, not recency.** Match the candidate against the live roster *and* confirm the title matches the role the field names — a field called regional_trainer holding a Lead Instructor is a data error even if that person is active.
- **Name matching must handle surname-initial forms.** `Haylee S.` maps to `Stephens, Haylee`; a first-name/surname assumption misses it and silently downgrades real evidence to "unknown".
- **Reporting a conflict total from a sample understates it.** Counts are cheap; re-pull everything before quoting a number.

## Verification checklist

- [ ] Both sides exported in full; counts and join-key overlap recorded.
- [ ] Drift canonicalised before any conflict count was quoted.
- [ ] Every write has a method and a reason string (no bare verdicts).
- [ ] Blanks filled, audit stamps left alone.
- [ ] Post-write re-read confirms each written value.
- [ ] Reconciliation equation balances with zero unexplained.
- [ ] Every corrected cell has a history row naming old value, new value, actor and time.
- [ ] Open items reported individually with their probability.

## References

- `references/drift-classification.md` — the canonicalisation table and the classifier skeleton that produces the four buckets.
- `references/source-export.md` — extracting the complete dataset from a client-rendered app (bundle-embedded keys, schema discovery, authenticated session tokens).
