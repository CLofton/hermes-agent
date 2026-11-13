# Sanitized Repository Handoff

Use this workflow when someone asks for a repository ZIP or other direct source handoff, especially when the canonical checkout is too large or contains unrelated credentials/assets.

## Deliverable contract

A handoff ZIP is not ready because it compressed successfully. It must be:

- sufficient to build and test the requested artifact;
- stripped of credentials, history, dependencies, caches, and unrelated bulk assets;
- documented with source branch/commit and explicit exclusions;
- rebuilt from the sanitized copy;
- rescanned after extraction from the final ZIP;
- delivered to the exact active recipient and read back from the destination.

## Proven workflow

1. **Resolve the recipient exactly.** Search the directory and reject deleted or ambiguous lookalikes. Use recent first-party correspondence to disambiguate similarly named people.
2. **Record canonical source state.** Capture private repository URL/visibility, branch, latest commit, and whether anything has been pushed or deployed.
3. **Measure before packaging.** Check checkout, `.git`, dependency, generated-output, and asset-library sizes. Never blindly ZIP a multi-gigabyte working copy.
4. **Build an allowlisted source handoff.** Start from `git ls-files`, then deliberately add required ignored runtime configuration files. Exclude at minimum:
   - `.git/`
   - `.env*` and credentials
   - `node_modules/`, `vendor/`, virtual environments
   - `_site/`, build outputs, and caches
   - unrelated legacy upload/media libraries
5. **Include only required binary assets.** Derive them from the actual pages/components being handed off. Document any excluded canonical asset library and where it remains available.
6. **Sanitize the copied tree, not the canonical checkout.** Blank/remove tokens and unrelated files in the handoff copy. Do not expose matching secrets in logs or reports.
7. **Add `HANDOFF.md`.** State branch/commit, inclusions, exclusions, install/build/test commands, and release guardrails.
8. **Prove the sanitized copy works.** Install dependencies or temporarily link known-good local dependencies, run the real build and acceptance tests, then remove dependencies, caches, and generated output before compression.
9. **Scan the package tree.** Run Gitleaks (or equivalent) on the sanitized source after cleanup. Treat findings in copied configuration, inactive includes, wiki pages, or caches as real until removed or safely sanitized.
10. **Create a versioned ZIP.** Never use `FINAL`. Extract it into a fresh directory and assert:
    - required files exist;
    - blocked paths do not exist;
    - the extracted tree passes the secret scan;
    - archive byte size and SHA-256 are recorded.
11. **Deliver with context.** Name the sender/requestor, branch/commit, build/test result, preview-only restrictions, and action requested from the recipient.
12. **Verify external state.** For Slack, confirm the file ID, filename, byte size, target DM/channel share, and attached message by calling `files.info` plus `conversations.history` (or equivalent readback). A successful upload API response alone is insufficient.

## Slack external-upload sequence

For a bot with file-upload scope:

1. `conversations.open` with the active recipient user ID.
2. `files.getUploadURLExternal` with explicit filename and byte length.
3. POST the exact bytes to the returned upload URL.
4. `files.completeUploadExternal` with explicit title, DM channel, and initial comment.
5. Read back `files.info`; require the expected private share channel and exact size.
6. Read back channel history; require a message containing that file ID and the intended handoff text.

Never print or interpolate the Slack token into shell output. Read it inside a short local script from the credential store.

## Common failure modes converted into controls

- **`git ls-files` omitted a required ignored config:** maintain an explicit allowlist of runtime configs and assert each exists before testing.
- **A clean diff scan masked secrets in copied base files:** scan the complete handoff tree, not only the feature diff.
- **Build/test passed only in the canonical checkout:** rebuild inside the sanitized copy before compression.
- **Caches reintroduced secrets after a test build:** delete generated/cache/dependency directories, then scan again.
- **ZIP contents differed from the scanned folder:** extract and rescan the exact final archive.
- **Upload succeeded but recipient did not receive the file:** verify both file share metadata and destination history.

## Cloneable automation handoff

- Resolve the exact repository owner/name with the user before publishing when several plausible repositories exist. Recheck visibility and the selected repository's privacy contract; private visibility does not authorize copying personal inventories into a team installer.
- Separate portable implementation from private runtime state. Package source, synthetic fixtures, sanitized configuration templates, tests and setup instructions; keep credentials, raw messages/tasks, personal cron definitions and histories out of Git. Document deliberate exclusions so a source clone is not mistaken for a live-account migration.
- Record any expansion from inventory-only to build-and-push authority without dropping independent no-send or rollout restrictions. Build permission does not activate dormant jobs or authorize executing imported task text.
- Verify the pushed commit by reading the remote, then exercise the documented quickstart from a fresh clone with a disposable home. Existing-checkout tests do not prove another computer can run the package.
- Report code completeness, remote publication, live authentication, shadow-duration evidence and production cutover as separate states; a demo cannot satisfy a multi-day operational acceptance gate.

## Status language

- **PASS:** sanitized copy builds/tests, source and extracted ZIP scans pass, archive structure is verified, and delivery is read back from the exact recipient destination.
- **FAIL:** any credential finding, missing build dependency/source, wrong recipient, malformed archive, or unverified delivery.
- **NOT YET PROVEN:** only the canonical checkout was tested, only the pre-ZIP folder was scanned, or external delivery was not read back.
