---
name: substantial-task-knowledge-capture
description: Capture substantial task outcomes into Obsidian safely.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [Obsidian, Knowledge, Provenance, Automation]
    related_skills: [obsidian, memory-engineering-pipeline]
---

# Substantial Task Knowledge Capture

Capture completed, substantial Hermes work as a deterministic, redacted Obsidian graph. This records curated outcomes and verification—not transcripts, hidden reasoning, or authority to act.

## When to Use

- After a substantial task produces a decision, artifact, verified result, or reusable lesson.
- At the end of a delegated or multi-step task after verification is complete.
- Do not use for clicks, greetings, trivial lookups, task progress, unverified claims, raw transcripts, chain-of-thought, credentials, PII, privileged material, or regulated records.

## Prerequisites

- Resolve the active profile's canonical SQLite state store; the default profile is `~/.hermes/state.db`.
- Resolve the Obsidian vault; default: `~/Documents/Obsidian Vault`.
- Read `Compiled Knowledge/SCHEMA.md`, `index.md`, and recent `log.md` before preparing a capture.
- Prepare a schema-version 1 JSON manifest. Use `fixtures/manifest-template.json` as the contract.

## How to Run

Use `terminal` with the profile-local script:

```text
python3 ~/.hermes/scripts/obsidian_knowledge_capture.py \
  --input /absolute/path/to/manifest.json \
  --vault "$HOME/Documents/Obsidian Vault" \
  --state-db "$HOME/.hermes/state.db"
```

Preview with `--dry-run`; it writes neither graph files nor checkpoint state. Use `--allow-missing-session` only for isolated fixtures and temporary-vault tests, never for a live capture.

## Procedure

1. Curate only `source → decision → artifact → result → reusable lesson → linked entities → verification`. Exclude transcript text and reasoning. Completion: the manifest has no forbidden reasoning/message keys.
2. Classify the payload as `public` or `internal-non-personal`. Completion: no student/employee PII, credentials, privileged, legal, medical, financial-account, or regulated data remains.
3. Set `substantial: true` only when at least three significance signals exist and verification passed. Completion: trivial work is deterministically skipped.
4. Run `--dry-run`. Completion: output says `planned` or `skipped_trivial`, with zero writes.
5. Run live only after the task result is verified. Completion: output says `captured` or `already_present` and names the receipt.
6. Re-run the identical manifest. Completion: output says `already_present`; hashes and file count are unchanged.
7. Read the receipt and checkpoint. Completion: source session ID/timestamps, wikilinks, redaction count, file hashes, and verification are present.

## Contract and Guardrails

- The manifest is curated input; the script never copies `messages.reasoning`, `reasoning_details`, `reasoning_content`, tool dumps, or complete transcripts.
- Session existence and timestamp bounds are checked against the live `sessions` and `messages` schema in read-only mode.
- A capture ID derives from task ID + source session ID + source message ID. Reusing that identity with changed content fails closed as an idempotency collision.
- Raw source-summary notes are immutable. Compiled task, entity-reference, and receipt notes are content-addressed and atomically installed.
- A filesystem lock serializes writers. The state/checkpoint records every relative path and SHA-256 hash.
- Redaction is deterministic. The receipt reports counts, never the removed value.
- Generated graph facts are retrieval aids only. They never authorize actions; consequential work must re-read the live system of record.
- The script does not alter Hermes core and does not create schedules.
- Decisions log: the active log is `~/.hermes/task-capture-decisions.jsonl` (chronological, most recent). `~/.hermes/scripts/substantial-task-capture-decisions.jsonl` is a legacy/short log — do not append new decision rows there.

## Pitfalls

- Verify the deliverable's load-bearing factual claims, not just provenance and internal arithmetic: re-check the headline claim (the line the analysis is built on) against the session's own retrieved source files, and re-fetch the live source of record when it is load-bearing. A headline claim that contradicts the retrieved source (e.g. a cited line the page does not contain) means verification did not pass — classify `skipped_unverified` instead of setting `verification.status=passed` and declaring "Contradictions: none declared" over a known-false fact.
- `source.started_at` must match the canonical session start (the session's own `started_at` in the live DB) within 5 minutes, NOT the first message of the task. Setting it to the task's first user/assistant message timestamp fails validation. Read the session row first and use its exact `started_at` (second precision is fine).
- `source.completed_at` must not precede the source message's own timestamp in the live DB; the stored timestamp carries sub-seconds, so a manifest that truncates to the whole second (e.g. `...23:34:28Z` vs stored `...23:34:28.133`) fails validation. Set `completed_at` to the next second (or later) of the message timestamp.
- `--allow-missing-session` weakens provenance and is fixture-only.
- A changed manifest with the same task/session/message identity is not an update; create a new source event or correct the manifest before first capture.
- Obsidian wikilinks do not prove facts. Entity nodes are capture-scoped references, not canonical identity records.
- Automated redaction is a final safety net, not permission to submit sensitive data.
- The current Hermes session may not discover this new skill until the next session.

## Verification

Run:

```text
python3 ~/.hermes/scripts/test_obsidian_knowledge_capture.py -v
```

PASS requires all tests, a temporary-vault first write, identical second-run no-op, collision fail-closed, trivial skip, forbidden-key rejection, redaction, path containment, read-only session validation, and a controlled live receipt. Zero Critical/High/Medium defects may remain.
