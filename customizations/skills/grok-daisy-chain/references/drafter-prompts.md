# Drafter prompt template (one per lens)

Copy this template per drafter, substituting `<LENS-PARAGRAPH>` and `<OUTFILE>`.

```
You are drafting a PRODUCT+ENGINEERING SPEC for <TASK>.

Read the full source brief at: <BRIEF_PATH>

Your lens: <LENS NAME>. <1-2 sentence lens description that forces a distinct
organizing principle — e.g. RELIABILITY-FIRST: every item needs a root-cause
hypothesis, a deterministic acceptance test, and an alerting requirement;
UX-FIRST: every item needs before/after behavior + approved copy + a success
metric; PRAGMATISM-FIRST: phases of small shippable PRs, code vs no-code flag,
prefer plumbing existing schema over new columns.>

Rules:
- Cover ALL open issues in the brief, grouped by your recommended build order / phases
- Mark each item: P0/P1/P2, owner (engineer vs config vs ops vs marketing), effort S/M/L
- Be specific to the real stack named in the brief
- Do NOT re-spec items marked "Verified DONE" in the brief
- Do NOT invent numbers beyond what the brief states
- Output: ONLY a complete markdown spec document, starting with a title line. No preamble, no commentary.
```

## Running them (Hermes side)

```bash
cd ~/Downloads/<task>-spec-chain && nohup /Users/operator/.local/bin/grok \
  -p "$(cat /tmp/grok_drafter_X.md)" --cwd ~/Downloads/<task>-spec-chain \
  > drafts/draft-X-<lens>.md 2>/tmp/grok_X.err; echo "X exit=$?" >> drafts/draft-X-<lens>.md
```

- One `terminal` background call per drafter, `notify=true`, timeout 1800.
- Launch all 3 in ONE turn (independent -> batch them).
- Verify completion: file non-empty, contains the `X exit=0` marker, and has
  substantive markdown (not an error dump). Check `2>/tmp/grok_X.err` if empty.
