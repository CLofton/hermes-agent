# Privacy-Safe Regression Fixtures

Use this when tests must prove that public output does not reveal a partner, customer, employee, student, investor, or source record.

## Fixture rule

- Never copy real names, organizations, domains, locations, message IDs, CRM IDs, headers, or source metadata into tracked tests—even in a private repository.
- Prefer synthetic examples such as `person@example.com`, `example.com`, generic dates, and fake fixed-shape IDs.
- If an exact denylist is necessary, keep raw values in access-controlled gitignored storage or store normalized phrase hashes in the shareable scanner.
- Do not print protected values in logs or review summaries; report counts and file paths.

## Required test layers

1. **Exact public contract:** assert exact approved quote/copy and exact generic attribution—not substring containment.
2. **Structural anonymity:** reject comments, links, images, `cite=`, source/contact/record data attributes, and duplicate attributions.
3. **Generic metadata patterns:** cover email addresses; `http(s)://`, protocol-relative, `www.`, and bare domains; ISO and slash dates; long hex/source IDs.
4. **Parser robustness:** make tag checks case-insensitive and whitespace/newline tolerant.
5. **Dual surface:** run the same contract against source markup and freshly rendered output.
6. **Adversarial tests:** inject extra claims, comments, uppercase/multiline tags, URLs, dates, and hidden metadata; verify each mutation fails.
7. **Artifact boundary:** confirm test files and private evidence are absent from the published artifact.

## Verification sequence

- Before remediation, run an ephemeral local scan using the protected values and record only the match count (RED).
- Remove real fixtures and replace them with generic patterns/adversarial mutations.
- Scan all current tracked files; distinguish genuine identity matches from generic geography or directory-content false positives without weakening the protected-value set.
- Run targeted tests, production build, link/proof checks, artifact-exclusion check, and `git diff --check`.
- Obtain an independent privacy review, then apply and retest bounded hardening findings.
- After deployment, read back the exact live section and confirm copy, attribution, count, and absence of links/images/comments/source metadata.

## Git-history boundary

Removing a value from the current tree does not remove it from earlier commits, pull-request diffs, cached views, forks, or clones. Report current-tree cleanliness and history cleanliness separately.

- If the branch has not been shared, rewrite/squash before pushing and rescan reachable history.
- If already pushed, do not claim full purge after a normal follow-up commit.
- History rewrites and hosted-platform purge requests can disrupt collaborators and may not clear pull-request refs automatically. Require explicit approval, coordinate the rewrite, and follow the host's sensitive-data removal process before public release when historical exposure matters.
