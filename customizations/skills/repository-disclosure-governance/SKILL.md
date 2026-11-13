---
name: repository-disclosure-governance
description: Use when an internal repository may be shared or pushed.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [security, privacy, git, disclosure, reputation, compliance]
    related_skills: [webapp-security-audit, dependency-security-audits, github-repo-management]
---

# Repository Disclosure Governance

## When to use

Load before pushing, publishing, sharing, or externally reviewing a repository that may contain confidential business context, partner/investor information, internal QA, screenshots, source-document identifiers, credentials, or exploit-level security findings.

This is broader than a secret scan. It protects the organization and named stakeholders from technical, commercial, reputational, and material-nonpublic-information exposure.

## Core rule

A clean Gitleaks result is necessary but not sufficient. Audit current content, history, prose, metadata, and pixels before declaring a repository safe to share.

## Workflow

1. Confirm repository visibility, remotes, branch push state, and deployment/public surfaces. For the operator's clone-on-another-computer requests, resolve the exact repository owner/name, preserve its existing disclosure restrictions, and separate build/push authority from sends, credential transfer and live activation. Deliver portable source with a fresh-clone quickstart test, not a dump of the working home or private inventory.
2. Inventory current tracked files, staged additions, untracked files intended for commit, generated reports, and binaries.
3. Scan current/staged/history with a secret scanner, redacting values in output.
4. Search protected entity variants and semantically review financial, board, investor, M&A, personnel, contract, strategy, security, and commercial statements.
5. Visually inspect every new/changed screenshot and PDF for identities, URLs, credentials, tenant names, metrics, and browser state.
6. Classify each finding by severity and release surface.
7. Preserve raw evidence in access-controlled gitignored storage; remove it from the shareable tree and publish only neutral status/remediation records.
8. Add pre-commit and CI disclosure gates.
9. If sensitive artifacts existed in earlier commits on an unpushed branch, squash/rewrite before sharing, then scan reachable history again.
10. Run application, static-analysis, dependency, accessibility, disclosure, and `git diff --check` gates after remediation.

## Guard design

- Keep restricted entity names out of shareable scanner source by storing normalized phrase hashes.
- Match phrase windows across punctuation and line breaks.
- Treat binaries as unreviewed until a human/vision review approves their exact SHA-256.
- Keep full provider/source manifests private; track a sanitized manifest without direct links or provider IDs.
- Demo credentials belong in a gitignored local environment behind an explicit local-only flag.
- Pin and checksum security scanners downloaded in CI.
- Stage new files before running a tracked-file disclosure guard, otherwise the guard can miss them.
- Before a development-branch push, scan both the intended tracked tree and every commit being introduced (`gitleaks git --redact --log-opts='<target-ref>..HEAD'`). A clean staged diff does not clear inherited branch history.
- Verify the scanner actually scanned: `gitleaks protect` (working-tree mode) can report zero commits / ~0 bytes for staged-but-uncommitted content and return a vacuously clean "no leaks found". Commit the work first, then scan full history with `gitleaks git` INCLUDING the new commit, and confirm the reported scanned byte count is non-zero before declaring the tree clean.
- Reproduce apparent secret findings at the reported revision before changing scanner policy. For a proven public routing identifier, use an exact-value AND exact-path exception, retain default detection, and verify a planted-secret negative control still fails; never suppress an entire service or rule family.
- Inspect contents before classifying a filename-based assessment-bank finding. A synthetic non-disclosure regression test can be renamed descriptively while preserving its assertions and test discovery; renaming a real bank or answer-key artifact does not make it safe to publish.
- Treat assessment banks, answer keys, rationales, and human review copies as restricted even in private repositories. Keep raw banks in access-controlled gitignored storage, and make the scanner reject force-tracked bank paths and `.jsonl` content.
- Generated screenshot audits must write to an ignored candidate directory. Analyze the pristine DOM first, redact only for capture, record redaction counts/policy version, and never auto-promote candidate pixels or hashes to approved evidence.
- A policy entry alone is not approval: verify the exact on-disk SHA-256 equals the approved hash. Preserve a failing current run separately from prior approval rather than carrying a historical green verdict forward.

## Reporting

Lead with:

- whether protected entities or material nonpublic information were found;
- whether the repo/branch has already been shared;
- critical/high findings and remediation state;
- what remains blocked before push or deployment.

Do not repeat secret values or unnecessarily restate sensitive entity names in the report.

## Reference

See `references/repository-disclosure-audit.md` for the detailed classification, remediation, binary-review, and history-rewrite playbook.

See `references/generated-evidence.md` for restricted assessment-bank handling and the screenshot candidate-to-approval lifecycle.

See `references/sanitized-repository-handoff.md` for minimal-ZIP and cloneable-automation handoffs: source/state separation, ignored-config allowlisting, fresh-copy testing, extracted-archive scanning, and destination readback.

See `references/privacy-safe-regression-fixtures.md` when tests must prove anonymous public output without embedding real identities in tracked fixtures; it also defines current-tree versus Git-history verification.
