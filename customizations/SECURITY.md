# Security notes

## Disclosure review

This tree was reviewed before publication. The review covered:

1. **Automated secret scan** — private keys, AWS/GCP keys, OpenAI/Anthropic keys,
   GitHub PATs, Slack tokens, Telegram bot tokens, JWTs, HubSpot PATs, bearer
   headers, PEM blocks. Result: zero live credentials. Remaining matches are
   documentation placeholders (`sk-xxx...xxxx`, `person@example.com`).
2. **PII and identity scan** — emails, phone numbers, SSN-shaped strings,
   account-number-shaped strings, personal names, company name, internal
   hostnames and `*.ts.net` nodes. Result: zero after deterministic substitution.
3. **Binary review** — one PNG, visually inspected, confirmed to be a flow
   diagram with no credentials, identities, URLs or real data.
4. **History scan** — the publishing commit was scanned with `gitleaks git`,
   including the commit itself, with a non-zero scanned byte count.

## What was removed during sanitization

The source tree contained material that must never be published. It was excluded,
not filtered:

- **A captured Chrome profile** (172 MB) sitting inside
  `engineering-swarm/scripts/package/~/.hermes/chrome-debug/` — including
  `Cookies`, `Login Data`, `Web Data` and `Local State`. This was an accidental
  copy of a real browser profile, produced by a mis-scoped `cp`. Saved logins and
  session cookies in a skill directory is a standing local risk independent of
  publication; delete it from any machine that has it.
- Business, financial, personnel, compliance and customer skills.
- `.env` files, `auth.json`, tokens, and anything under `secrets/`.
- Test caches, `node_modules`, and VCS internals.

## Guard

`scripts/check-disclosure.sh` re-runs the deterministic checks and fails the build
on any regression. Run it before adding anything:

```bash
./scripts/check-disclosure.sh
```

## Reporting

If you find anything in this tree that looks like a credential, personal datum or
confidential business detail, open an issue marked `security` without quoting the
value, and it will be removed and the history rewritten.

## Upstream

This is not a security boundary for Hermes Agent itself. Report vulnerabilities in
Hermes to [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
under its security policy.
