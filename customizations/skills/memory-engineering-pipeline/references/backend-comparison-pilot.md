# Comparing two memory backends on evidence

Run this when asked whether to switch memory systems. The failure mode it
prevents is choosing on vendor benchmarks and vibes instead of on our own
queries.

## Shape of a trustworthy comparison

Two systems, **one corpus**, **one query set**, **deterministic scoring**.
Anything where the model judges the answer is a demo, not a measurement.

```
<pilot-root>/
  corpus/seed/     authored documents with real ground truth
  corpus/live/     daily sanitized session captures
  queries.json     16+ queries: expect + markers
  results/         one scored snapshot per day
  pilot.py         ingest | capture | run | report
  pilot_daily.py   silent daily driver, final report on the last day
```

## Isolation (do this before ingesting anything)

- Give each system its own store. Never point a comparison at the live brain:
  a bad ingest silently pollutes production memory and the scores.
- **GBrain:** `gbrain sources add <id> --path <dir> --force` creates a
  **non-federated** source by default — it is only read when named via
  `--source <id>`. Verify with `gbrain sources list --json` that
  `federated: false`.
- **MemPalace:** pass `--palace <pilot-root>/palace` on every command; the
  default palace is `~/.mempalace/palace` and will mix with real data.

## Ingest commands that work non-interactively

```bash
# MemPalace — init is INTERACTIVE without --yes and dies with EOFError in a script
timeout 600 mempalace --palace "$P/palace" init "$P/corpus" --yes --auto-mine --no-llm
mempalace --palace "$P/palace" mine "$P/corpus"          # incremental, subsequent runs

# GBrain
gbrain sources add memory-pilot --path "$P/corpus" --force
gbrain sync --source memory-pilot --no-embed
```

`gbrain sync` fails when its configured embedding model needs a key it does not
have (e.g. `ZEROENTROPY_API_KEY`). `--no-embed` gives the documented keyless
keyword/tsvector arm. Do not silently substitute a paid provider — that spends
money and egress text; surface it as a decision.

## Fairness rules that decide whether the result means anything

1. **Score markers against the full retrieved document**, resolved from the
   corpus by source id — not against whatever snippet a CLI prints. CLIs
   truncate differently; snippet length otherwise decides the winner.
2. **State the arm honestly.** A keyless/keyword arm losing is not "the tool
   loses" — report it as the configured-arm result and name what the other arm
   would cost.
3. **Hold versions fixed for the whole run.** An upgrade mid-pilot invalidates
   the comparison; note the available upgrade and defer it.
4. **Include a seeded corpus.** A pure live corpus has no ground truth, so
   every query becomes a judgment call. Author 12-16 documents from durable
   knowledge, then let live capture add volume.

## Query set that discriminates

Similar-looking documents on easy topics score 100% for both systems and
decide nothing. Include at least one of each:

- **supersession** — a later document corrects an earlier one ("is X still
  pending?")
- **temporal** — the same entity has an updated state
- **needle** — the answer buried mid-document, not in the first paragraph
- **near-duplicate** — an abandoned design that contradicts the shipped one
  ("is the cadence daily or four-hourly?")

Markers must be strings that appear **only** in the correct document, otherwise
a near-miss scores as a hit.

## Metrics and pre-committed decision rule

- `hit@5` — all markers present in the union of the top-5 retrieved documents
- `top-1 exact` — highest-ranked document is the expected one
- latency and error count per arm

Decide the threshold **before** the run (e.g. ≥5 pt hit@5 or ≥10 pt top-1 lead
switches; smaller means keep the single system). Post-hoc thresholds always
find a reason to switch.

## Capturing live sessions

Hermes conversation text lives in `~/.hermes/state.db` — `messages` table
(`session_id`, `role`, `content`, `timestamp` as REAL epoch). The JSONL export
under `~/.hermes/sessions/` is stale; a capture script that globs it silently
produces zero records. Query the DB read-only:
`sqlite3 "file:$HOME/.hermes/state.db?mode=ro"`.

Redact before writing: emails, phone numbers, SSNs, card numbers, key-shaped
strings (`sk-`, `ghp_`, `xoxb-`, `AKIA`), and long hex digests. **Names are not
redacted by a regex** — get an explicit decision on live capture rather than
assuming the corpus is sanitized.

## Scheduling it

A `no_agent` cron with a shell wrapper in `~/.hermes/scripts/` that pins `PATH`
(`~/.local/bin` for uv tools, `~/.bun/bin` for bun tools) and execs the venv
python. Cron runs with a minimal environment; a script that works in an
interactive shell and fails at 7:30am is almost always PATH or interpreter.

Emit **nothing** on ordinary days and the full comparison on the final day —
seven daily progress messages are noise that trains the user to ignore the
report that matters. Verify the silent path with a clean environment before
installing the job: `env -i /bin/bash -c '<wrapper>'` must exit 0 with no stdout.
