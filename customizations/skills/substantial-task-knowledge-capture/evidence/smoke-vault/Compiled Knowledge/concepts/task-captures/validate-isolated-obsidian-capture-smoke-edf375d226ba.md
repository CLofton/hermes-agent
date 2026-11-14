---
title: "Validate isolated Obsidian capture smoke"
created: 2026-09-07
updated: 2026-09-07
type: concept
tags: [agent-operations, knowledge-management, provenance, automation]
sources: ["Compiled Knowledge/raw/tasks/2026/2026-09-07/e2e-smoke-001-edf375d226ba.md"]
confidence: high
contested: false
contradictions: []
---

# Validate isolated Obsidian capture smoke

Source: [[Compiled Knowledge/raw/tasks/2026/2026-09-07/e2e-smoke-001-edf375d226ba|curated source summary]]
Verification: [[Compiled Knowledge/output/task-capture-receipts/2026-09-07-e2e-smoke-001-edf375d226ba|capture receipt]]

## Decision

1. **Use an isolated vault** — Prevent test writes to the live knowledge graph

## Artifact

- `evidence/smoke-vault` — Preserved isolated E2E vault

## Result

The isolated pipeline writes a linked graph and receipt deterministically.

## Reusable lesson

Run both first-write and identical no-op checks before enabling a live capture.

## Linked entities

- [[Compiled Knowledge/entities/capture-references/e2e-smoke-001-edf375d226ba-hermes-agent|Hermes Agent]]
- [[Compiled Knowledge/entities/capture-references/e2e-smoke-001-edf375d226ba-obsidian|Obsidian]]

## Authority boundary

This compiled note is a retrieval aid, not a system of record and not authorization to act. Re-read live sources before consequential action.
