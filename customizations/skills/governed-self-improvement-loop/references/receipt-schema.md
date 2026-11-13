# Canonical Task Receipt Schema

The analyzer accepts one JSON object, a JSON array of objects, or JSONL. Unknown fields are ignored and never emitted. Producers must deidentify statements before writing receipts.

## Required receipt fields

```json
{
  "schema_version": "1.0",
  "receipt_id": "stable-source-id",
  "occurred_at": "2026-09-06T10:00:00-05:00",
  "task_type": "external-write",
  "outcome": "SUCCESS",
  "verified": true,
  "lesson_events": [],
  "issues": [],
  "memory_checks": []
}
```

- `receipt_id`: required and unique. Output pseudonymizes it with SHA-256.
- `occurred_at`: required ISO-8601 timestamp with timezone.
- `task_type`: stable deidentified slug.
- `outcome`: `SUCCESS`, `PARTIAL`, or `FAILURE`.
- `verified`: `true` only when the task's acceptance criteria were checked against the target.
- For `PARTIAL` or `FAILURE`, optional `failure_code` and `failure_severity` classify the process defect.

## Lesson event

```json
{
  "key": "external-write-readback",
  "statement": "Verify an external write by reading back the exact target.",
  "target_skill": "example-skill",
  "verified": true,
  "recurrence": "PASS",
  "severity": "MEDIUM"
}
```

- `key`: same correction or lesson across receipts. Different statements under one key are a contradiction.
- `statement`: concise, reusable, deidentified procedural lesson.
- `target_skill`: valid lowercase skill slug or `general`.
- `verified`: evidence was directly checked, not inferred.
- `recurrence`: `PASS`, `FAIL`, or `NOT_TESTED`. PASS means a later applicable task followed the correction; FAIL means the same defect recurred.
- `severity`: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, or `INFO`.

## Issue

```json
{
  "kind": "process-failure",
  "summary": "Write was not read back from the target.",
  "severity": "MEDIUM",
  "status": "OPEN"
}
```

Resolved issues are excluded. Open Critical, High, and Medium issues block PASS.

## Memory check

```json
{
  "key": "system-of-record-rule",
  "status": "STALE",
  "severity": "MEDIUM",
  "summary": "The claim has not been verified against the current source."
}
```

Status is `CURRENT`, `STALE`, `CONTRADICTED`, or `NOT_YET_PROVEN`. Any non-current Critical, High, or Medium check blocks PASS. The analyzer proposes no memory mutation.

## Data minimization

Never include names, contact details, credentials, raw messages, transcripts, student/employee/customer records, legal material, or regulated data. Use stable abstract keys and procedural statements. Common email, phone, path, and secret patterns are redacted as defense in depth, not as permission to ingest private data.
