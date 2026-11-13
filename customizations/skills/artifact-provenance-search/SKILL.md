---
name: artifact-provenance-search
description: "Find or prove absent a specific document, photo, or artifact across Gmail/Drive."
version: 1.0.0
author: Hermes Agent
license: MIT
tags: [search, retrieval, gmail, drive, evidence, provenance, negative-proof]
metadata:
  hermes:
    tags: [search, retrieval, gmail, drive, evidence, provenance]
    related_skills: [gmail-raw-api-retrieval, google-drive-bulk-ops, hr-document-lookup]
---

## When to Use
- Asked to find a specific document ("find X", "is there a signed copy of...")
- Asked to prove a document's status for a cap table, diligence, or legal file
- A counterparty claims they are missing an executed document and you must verify what you actually hold

# Artifact Provenance Search

Find one specific artifact (document, executed agreement, cap table, historical photo, or signature page) — or produce a defensible "it is not in any accessible source" that survives scrutiny. Triggers: "find X", "find it wherever it may be including archived", "is there a signed copy of...", and requests for the earliest or historical photo of a person, school, or event. the operator's standard for these findings is exact cause per item, PASS/FAIL/NOT YET PROVEN, never conjecture as evidence.

## Standing rules

1. **Resolve the underlying artifact before acting on surrounding correspondence.** When the operator pastes language such as “I need the agreement—can you send it?” and asks to give someone what they need, treat the agreement as the retrieval target; do not forward the quoted request as though it were the requested deliverable. Retrieve and verify the artifact first, then send only when the instruction clearly authorizes that delivery.
2. **Search by the document's own vocabulary first.** The document's legal/technical name and the exact figures it contains (unit counts, dollar amounts, percentages) outperform all name- or date-based guessing. A "Restricted Units Agreement" is found by `"restricted units"`, not by the equity class it grants ("Class C1") — the class name may appear in only one email.
3. **A name search returning zero files is NOT a proven absence.** Files may never have been shared to this account, or shared from a side mailbox. State the boundary: "not in c.the operator's Gmail/Drive" — and name the outside source the document likely transited (counterparty's mailbox, law firm's file).
4. **Report tiered negatives.** For each source searched: what was searched (queries + windows), what was found, and the conclusion per artifact. A bare "not found" is not a deliverable; "not in X, Y, Z — here are the queries and the residue I did find" is.
5. **Do not merge adjacent claims.** A verified founder portrait plus a verified early-school photo does not prove a photo of the founder at the school launch. Classify the requested conjunction itself as FOUND or NOT YET PROVEN, then present adjacent verified artifacts separately.
6. **When the only artifact carrying the requested name is obsolete, the namesake is the hazard.** A request phrased in the requester's words often matches exactly one old file — the one that will get forwarded by mistake and misstate the current facts. Deliver the safe nearest substitute instead, and name the stale namesake explicitly as "do not forward." A negative alone leaves the requester to grab the wrong file.

## Workflow

### 1. Frame the artifact
Extract from the user's ask: exact document name, parties, entity, figures (unit counts / $ amounts), claimed dates (draft date, exec date), and any outside party who holds it. Build the search vocabulary list: doc name + figures + party names + related terms (joinder, 83(b), executed, signed).

When the request looks voice-transcribed or contains a malformed identifier, test the literal token first, then a small set of high-probability interpretations grounded in the surrounding nouns (for example, a four-digit token near “financials” may be a fiscal year rather than a form number). Rank candidates by internal content and current business context; do not silently normalize the token or force clarification when one candidate can be proved decisively.

For financial statements, translate colloquial status words into document evidence before searching: “CPA-signed” may appear as `audited`, `reviewed`, `independent auditor’s report`, `accountant’s report`, `final`, or the CPA firm’s name rather than `signed` in the filename.

### 2. Gmail sweep (load `gmail-raw-api-retrieval` for raw API mechanics; `scripts/gapi.py` in this skill is a runnable Gmail+Drive client for when no `$GAPI`/drive wrapper is on PATH)
Run these query classes in parallel where possible:
- **Filename** (catches attachments regardless of subject): `filename:"<doc name tokens>"` for each vocabulary item — Gmail filename search covers all labels including Archive.
- **Body**: exact phrase for each vocab item (figures in quotes: `"27,612"`), party names, related terms. Note `resultSize: 0` with non-empty `messages` is normal for relevance queries — trust result presence, not the count.
- **Subject**: `subject:"<doc name>"`, `subject:joinder`, etc.
- **Agreement families**: search `executed set`, `loan documentation`, `including Exhibit A`, amendment numbers, and the original agreement date. A later executed amendment may attach a complete conformed agreement as an exhibit even when a standalone amendment PDF or local copy contains only an “(attached)” placeholder.
- **Time windows around claimed dates**: `after:MM/DD/YYYY before:MM/DD/YYYY` (no name filter) and review EVERY message in the window with flagged attachments — the circulation email may use a subject you don't predict. Also pull the full sender history across the relevant window (`from:person after:X before:Y`) to prove they never sent the artifact back.
- **Drafts**: `in:drafts (<vocab>)` — a pending reply may already exist.

Download any candidate attachments **in the same process that fetched the message** (attachment tokens are single-shot — see gmail-raw-api-retrieval). For an amended agreement, extract the downloaded file and verify that it actually contains the operative definition, schedules, and referenced exhibits before calling it complete.

### 3. Drive sweep
- `name contains "<vocab>" and trashed=false` AND `trashed=true` for each term; paginate with `pageToken`.
- Folder contents of any related folder (`'<folderId>' in parents`) — a filing folder often holds the executed version even when name search didn't surface it (search returns copies in every folder; dedupe by id).
- **Native Docs/Sheets: `alt=media` 403s** — use `GET /files/{id}/export?mimeType=...` for natives.
- Read anything borderline with a real content check (extract docx XML / PDF text / xlsx via openpyxl) before classifying — filename is a hint, content is the classification. For PDFs, `pdftotext -layout in.pdf out.txt` returns the text layer even when a document-reader tool refuses the file for a couple of OCR-needed pages, and `grep -n` on the output answers "does this document actually cover X" in one step. Files: `scripts/gapi.py` (Gmail+Drive client), see its `dmedia`/`dexport` subcommands for pulling the binaries and native docs first.
- For CPA financials, verify the internal entity, period end, report level (`audit`, `review`, or `compilation`), firm attribution, opinion/conclusion language, and report date. A typed CPA-firm signature block on an independent auditor’s report is evidence of issuance; do not require a wet signature unless the requester or regulator explicitly requires one.
- When multiple Drive copies appear, download the likely finals and compare cryptographic hashes. Identical hashes establish byte-for-byte duplicates; choose the clearest canonical Drive location instead of presenting every copy as a separate artifact.

#### Historical photos and visual artifacts
1. Establish the event vocabulary and lineage first: old company/school names, location aliases, license or school codes, founder name variants, and the likely launch window. Search those terms as both names and `fullText`; visual files often have generic camera names while their parent folders carry the useful context.
2. Search images/videos by time boundaries and inspect `imageMediaMetadata.time`, `modifiedTime`, and folder names. Migrated archives may have a recent `createdTime` but retain the original capture or modification time; never sort historical media by Drive creation time alone.
3. Traverse exact legacy folders recursively with `'<folderId>' in parents`, reconstruct each candidate's ancestor path, and group by event/cohort folder before downloading. Paths such as `OLD / <program> / <location> / <cohort date>` are stronger provenance than a generic filename like `IMG_0840.JPG`.
4. Generate labeled contact sheets for candidate batches (source folder, filename, original timestamp, Drive ID) and compare them visually. When identifying a person, put the known reference portrait and candidate crop in one side-by-side image; separate vision calls do not provide a reliable direct face comparison.
5. Treat visual identity as evidence with a confidence level, not a fact. Require multiple stable facial features to agree, and reject context-only inference (for example, a male portrait on a dental-office wall is not automatically the founder).
6. Preserve the earliest verified candidate as both a canonical Drive link and a stable local copy. If the requested scene is not proved, deliver the earliest verified adjacent artifacts separately—for example, founder portrait, first-school logo, earliest class photo—with exact dates and an explicit NOT YET PROVEN statement.

### 4. Related-artifact corroboration (the highest-value step for negatives)
Find documents of the SAME FAMILY and diff: if the org's only executed agreements on file are for persons A and B, and the cap table shows only the original class, that residue is evidence about C and D. Also check any existing diligence/internal input lists (e.g. a LIBERATE-style manual-inputs sheet) for an already-open item on the same gap — it saves re-proving and gives the answer an owner.

### 5. Deliverable
Per artifact: FOUND (path/URL + content-verified) / NOT FOUND in <sources> (queries listed, residue noted, outside source named) / NOT YET PROVEN (what would settle it). For "not found" findings in a diligence context, also flag the timing collision with related events (e.g. a separation agreement that supersedes an unsigned grant) — that's often the actual answer the requester needs.

For a found artifact, lead with the result and include both a clickable canonical URL and a stable local copy when the user is likely to open or forward it. State only the minimum verification facts that distinguish it (for documents: entity, period, report level, issuer, report date; for media: subject/event, original timestamp, folder lineage, and identity confidence). Avoid narrating the search unless ambiguity or negative coverage matters.

For a negative, the deliverable is a decision, not a shrug: the tiered negative, the nearest authoritative substitute that is safe to send today, and the statement of what the requester should expect to receive from whom (which system, owner, or vendor actually holds the current version). Write the send-ready draft only when the substitute is content-verified; label every gap rather than filling it.

## Pitfalls
- **Gmail `resultSize: 0` is not coverage** — relevance-based queries return hits with a zero count; never report "0 results" from the count field alone.
- **Circulation from the counterparty's mailbox never appears in the operator's inbox** — when a draft was "circulated" by an outside party on a specific date, that date proves nothing about local records; search the window for evidence of *response*, and say the draft itself lives in their file.
- **Don't stop at the first named-file hit** — the org may hold a short amendment shell that references missing exhibits while a later “executed set” email contains the complete conformed agreement. Enumerate candidates, dedupe exact copies by hash, and classify completeness from extracted content rather than filename or signature pages alone.
- **Local Downloads grep over ~2700 files can hit the 120s tool timeout** — prefer `search_files` (ripgrep) with narrow patterns over recursive `grep -r`.
- **Record negatives into the standing diligence/manual-inputs artifacts** when the finding feeds one — future agents re-run the search otherwise.
