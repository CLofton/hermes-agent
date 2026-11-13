# Independent verification swarm for a deliverable pack

Use when a pack of documents/workbooks is about to go to an external reviewer (banker, auditor, client) and the question is "is this actually right?" — not "who can write more of it".

The failure this prevents: the author's own recompute always agrees with the author's own definitions. A pack can be internally consistent, beautifully formatted, and still carry a material error that only a differently-aimed reader finds.

## Lane 0 — deterministic recompute (parent runs it, always)

A single script that re-derives every headline number **from the source files**, not from the deliverable, and asserts against what the deliverable claims. Print `CHECK / CLAIMED / RECOMPUTED / PASS-FAIL` per row and exit non-zero on any failure.

What it must cover:

- Row and population counts (exact), and the count of each derived category.
- Money totals and distribution counts (per quarter, per entity, per cause).
- Every figure quoted in prose, not only the ones in tables.
- Page counts of any "one page" document.
- A contamination check on any parsed dataset.

Two harness bugs that produce false greens, both seen in practice:

- **A generous relative tolerance lets wrong counts pass.** Compare integers exactly; reserve tolerance for floats.
- **`max_row - N` row arithmetic.** Header plus totals rows vary per sheet; assert the count you expect and let the failure tell you which is wrong, rather than assuming an offset.

## Lane A — numeric audit (independent recompute)

Reviewer recomputes the same numbers in its own code from the sources. Redundant with lane 0 by design: two independent implementations disagreeing is information. Brief it to treat the deliverable as claims, and to add the checks lane 0 did not think of.

## Lane B — methodology and overreach audit

Not arithmetic. Attacks definitions and logic: is a "cost" column actually a profile median lookup rather than a per-item estimate; is a derived field labelled as derived; is a rate framed as the thing it is not (a completion rate read as a placement rate); does a summary line contradict its own detail tab; which sentences survive only because the reader did not check. Ask for the three most challengeable sentences, verbatim.

## Lane C — buyer red-team

Roles the actual reviewer. Give it the verbatim request text for each item and the deliverables, and force a verdict per item: `ACCEPT` / `SEND BACK` / `ESCALATE`, the single objection it would raise in its own voice, the one thing it would ask for next that is not already offered, and whether the format matches the ask (one page where one page was requested). Then a ranked send-readiness order and the one item it would not send at all.

This lane finds the class of defect the other two miss: documents that are honest about their gaps while the gap sits in the item that was actually requested.

## Output contract (every reviewer lane)

```
Write <findings path> with: a table of every check with PASS / FAIL / NOT EVIDENCED,
severity BLOCKER / MATERIAL / MINOR on failures, and file/cell or recomputed-number
evidence per row. Then print exactly one final line:
CONFIDENCE: <0-100>
justified in one sentence on the line above.
```

- Without that findings file the lane's work is unrecoverable from its chat.
- Without the single confidence line the results cannot be aggregated.
- A lane that writes analysis but no file, or omits the confidence line, is an incomplete lane — report it as such rather than inferring a number.

## Launch mechanics (verified working)

```bash
claude -p "$(cat lane_brief.md)" --model opus --allowedTools "Read,Bash,Write,Glob,Grep" > lane_a_cli.txt 2>&1 &
codex exec -s workspace-write -C "$WORKDIR" --skip-git-repo-check "$(cat lane_brief.md)" > lane_b.txt 2>&1 &
wait
```

- **Canary each CLI before building a fan-out on it.** One-line prompt, expect one-line reply. An unauthenticated CLI fails instantly and looks like a lane failure five minutes later.
- **`claude -p` is silent until it exits; `codex exec` streams a verbose log.** For the silent one the findings file is the only progress signal, so make writing it the lane's first action, not its last.
- **Different models on one provider is not independence.** Say which families you actually used; do not describe two Claude lanes and a Codex lane as three independent providers.
- Run them detached with completion notification and keep working on the deterministic lane meanwhile.

## Synthesis

1. Count `PASS` / `FAIL` / `NOT EVIDENCED` per lane; list every `BLOCKER` and `MATERIAL` finding on one screen.
2. Verify each finding yourself before acting — reviewers overstate as well as catch (one called 12 rows "column-shifted" when two cells held trailing contamination).
3. Fix material findings, re-run lane 0, and rebuild the artifacts. A finding you accept but do not fix must be reported to the user as a known defect, not buried.
4. Re-score from the new artifacts and state the movement plainly ("was X, now Y, because Z"). Never carry a pre-fix confidence forward.
5. Separate what the swarm fixed from what no swarm can fix: missing source documents, absent signatures, and gaps in the requested item itself are client inputs, not editing problems. Say that explicitly so the user does not commission another review round hoping it resolves.
