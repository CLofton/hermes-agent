# Repository Disclosure Audit Playbook

## Scope matrix

Audit each surface independently:

| Surface | Why it matters |
|---|---|
| Current tracked tree | What a new clone receives |
| Staged/untracked intended files | New content may not be visible to `git ls-files` until staged |
| Reachable Git history/all refs | Deleting at HEAD does not purge prior commits |
| Markdown/JSON reports | Generated prose often contains candid internal analysis and absolute paths |
| Screenshots/PDFs/binaries | Secrets and identities may exist only as pixels |
| Deployment manifests/examples | Ingest endpoints, hostnames, IDs, and realistic placeholder credentials leak here |
| Repository visibility/remotes | Determines whether remediation must include rotation and incident handling |

## Classification

- Critical: live credentials/private keys, regulated data, PII, or material nonpublic information.
- High: private source inventories, partner/investor details, exploit-level findings, uncorrected compliance defects, answer-key patterns, or candid commercial/product critiques.
- Medium: employee/demo identities, personal paths, internal URLs/IDs, operational metadata, or abuse-prone public ingest endpoints.
- Low: public facts that still need neutral wording, source attribution, or aggregation review.

A fact being public does not make every combination safe. Public identity plus nonpublic relationship details, negative internal commentary, performance data, or defects can create a new sensitive disclosure.

## Remediation without evidence destruction

1. Copy raw audit evidence into an access-controlled, gitignored directory.
2. Verify the private copy exists.
3. Remove raw reports from the shareable tree.
4. Replace them with a neutral release-status document stating gates and remediation state, not exploit recipes or embarrassing quotes.
5. Keep a sanitized tracked source manifest and a full private manifest.
6. Regenerate screenshots with synthetic identities and empty credential fields.
7. Visually review regenerated binaries before approving their hashes.

## Durable scanner pattern

A repository disclosure scanner should fail on:

- restricted entity/advisor names represented by normalized phrase hashes;
- direct private Drive/document links and provider IDs;
- personal absolute paths;
- predictable demo credentials;
- named employee/demo mailboxes outside an allowlist;
- phone numbers and private-key material;
- new or changed binary artifacts lacking a manually approved SHA-256.

Phrase matching must cover punctuation and line breaks and should support names longer than three words. Do not put protected plaintext names into a public scanner policy when hashes are sufficient.

## History handling

For an unpushed feature branch containing sensitive earlier commits:

- preserve a private backup if needed;
- rebase onto the intended current base if required;
- squash/rewrite the unpushed branch so sensitive files never appear in its reachable commits;
- expire/remove only local unreachable objects if policy requires it;
- rerun history-wide Gitleaks and business-disclosure searches.

Never rewrite a shared branch without explicit coordination.

## Verification evidence

Record counts and scope, not secret values:

- tracked files scanned;
- refs/commits scanned;
- binary artifacts visually reviewed;
- actionable findings by severity;
- scanner versions and checksum verification;
- final working-tree, staged-diff, and reachable-history results;
- whether anything was pushed or deployed.
