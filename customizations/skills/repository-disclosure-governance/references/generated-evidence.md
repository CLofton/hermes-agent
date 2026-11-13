# Generated evidence and restricted assessment artifacts

## Raw assessment material

Keep stems, option text, keys, rationales, source packets, and human key-marked review copies outside the tracked tree in access-controlled gitignored storage. `.gitignore` is not a security boundary: disclosure tooling must reject these paths if force-added and must scan `.jsonl` as text.

Safe validator output contains only stable record IDs, counts, hashes, schema status, and violation codes. Do not emit correct-option IDs, labels, positions, or text into general logs/artifacts.

## Screenshot evidence lifecycle

1. Measure the pristine DOM and required loaded state.
2. Fail closed on spinners, missing frames, missing expected controls, console/page errors, accessibility violations, or normative touch-target failures.
3. Redact only after measurement, immediately before capture.
4. Write new images and blocked-run JSON to ignored candidate paths.
5. Record candidate hashes, redaction policy/count, commit/tree state, fixture, browser/tool versions, and truncation totals.
6. Human/vision review the exact candidate bytes.
7. Promote candidates and update approved hashes only as a separate authorized action.
8. Verify current bytes equal policy hashes. A policy key without hash equality is not approval.

Keep current failed evidence distinct from previous approval. Never overwrite canonical approved evidence automatically, and never let historical green state turn a current failed run green.
