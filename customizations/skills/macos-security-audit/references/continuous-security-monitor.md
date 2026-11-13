# Continuous macOS security monitor pattern

Use this pattern when turning a one-time hardening pass into persistent monitoring.

## Two cadences

- Fast scan every 5–15 minutes: firewall/stealth state, listeners, agent inventory, risky autonomy flags, credential-file modes, and sensitive-export modes.
- Full daily scan: package audits, tracked secret-like files, supply-chain IOCs, cloud-link metadata, and a redacted executive summary.

## launchd contract

- Install a user LaunchAgent under `~/Library/LaunchAgents/` for read-only fast scans.
- Use `RunAtLoad` plus `StartInterval`; write stdout/stderr to owner-only logs.
- The scanner may return nonzero to signal findings when run manually, but the LaunchAgent wrapper must convert findings into report data and exit zero. Reserve nonzero for scanner execution failure.
- Validate the plist, bootstrap it into `gui/$(id -u)`, kick it once, and verify `runs`, `last exit code`, report modification time, and empty stderr before declaring success.

## Agent inventory

Count and report separately:
- interactive Hermes/Claude/Codex/OpenCode parents;
- MCP watchdogs and servers;
- kernels/LSP/build/test descendants;
- gateways and scheduled workers.

High parent/MCP counts are an exposure and resource problem, not proof of hostile activity. Never automatically kill an agent from count alone. Use age plus descendant activity and preserve current/delegated work.

## Sensitive local data

- File modes: sensitive exports should be `0600`; archive directories should be `0700`.
- FileVault protects data at rest while the Mac is off, but does not replace file permissions or retention controls.
- If building an encrypted archive, prefer an AES-256 APFS sparsebundle, verify copies with SHA-256, and never auto-delete sources until Legal/Compliance approves a retention schedule.
- Keep archive credentials in Keychain when available. If an owner-only key file is the approved fallback, make the limitation explicit and set `0600`.

## Concurrent report publication

When multiple scheduled processes publish a report that another process reads:

1. Reproduce the truncate/read race using synthetic data and a separate writer process; require the non-atomic control to observe torn reads so the test cannot pass vacuously.
2. Write a temporary file in the destination directory with restrictive permissions, flush and fsync it, then publish with `os.replace`. Route every report-writing call site through the same helper and clean temporary files on failure.
3. Test exact content, owner-only permissions, no leftover temporary files, and concurrent readers observing only complete documents.
4. Preserve exit-code and freshness checks; atomic publication does not fix subprocess timeout or stale-report failures. Capture their redacted diagnostic detail separately under the stable finding identity.

## Reporting safety

- Report secret key names, locations, providers, fingerprints, and equality results only—never values.
- Bound a recursive content search before running it. Grepping a Hermes home or projects tree for a credential value without excluding `cache/`, `logs/`, `.git`, and `node_modules` can hit a single cached page of megabytes, flood the transcript past its capture limit, and time out while the actual match is never read. Filter by file glob (`--include='.env*'`) or pass `rg --glob '!cache' --glob '!node_modules'`.
- A tracked `.env*` filename is a review lead, not proof of a leak. Confirm with a redacted current/history scanner and distinguish examples, public client identifiers, revoked keys, and live secrets.
- Cloud CLIs can include platform-generated tokens or deployment metadata in broad list output. Capture provider JSON inside a subprocess, reduce it to approved fields, and print only the sanitized summary; do not dump raw site/project objects into session logs. If raw output is already persisted, restrict the spillover/log file to `0600`.
- Dependency totals must distinguish unique deployable projects from duplicate clones, PR checkouts, and agent worktrees. Report both raw scan instances and deduplicated application risk so copied lockfiles do not inflate the executive severity count.

## Recurring permission enforcement

A one-time `chmod 0600` pass does not hold: exports, profile databases, logs, and generated reports can be recreated with the process umask and return as `0644`.

- Keep the security scanner read-only, but run a separate narrowly-scoped permission guard for known sensitive extensions and credential paths.
- The guard may only remove group/world permission bits; it must not move, delete, or rewrite target contents. Permit narrowly bounded content inspection only for an explicitly reviewed exclusion such as a public-only PEM bundle; never infer credential validity or log secret material.
- Protect parent profile/state directories with `0700` so newly-created child files remain non-traversable even before the next guard run.
- Run at startup and every few minutes, exit zero on successful enforcement, and test that a `0644` fixture becomes `0600`.
- Re-scan after the guard runs and require zero group/world-accessible eligible sensitive files; preserve stricter owner permissions rather than forcing every file to exactly `0600`.

### Permission-coverage releases

Follow [permission-coverage-release.md](permission-coverage-release.md) for scope census, descriptor-safe enforcement, exact-baseline review, backup, deployment, and readback. Keep those release controls in that reference rather than duplicating them here.

## Proving a rule can ever pass

A detector that keys on a literal process or binary name breaks silently when the launcher is renamed: the pattern matches nothing, the rule reports zero supervisors/children on every healthy group, and the alert becomes permanent noise.

- When a finding repeats thousands of times on a host whose topology has not changed, suspect the rule before the host. An unchanged fingerprint with five digits of occurrences is a rule that cannot pass.
- Before writing a new rule, search the tree for tests asserting the name it matches. A test file that exists and currently fails is the signature of a fix that was staged and never shipped; apply it rather than writing a second implementation.
- Verify the rule against live data after the fix — classify the current process table and require zero findings on the healthy topology, not just green unit tests.

## Diagnosing a chronic spawn or retry storm

When a monitor reports orphaned or duplicated children, the alert size is usually not the leak size. Measure before and after, and prove the storm is over rather than that one pass was cleaned.

1. Group children by `ppid`, then by server identity rather than raw count: five copies of each of six servers is one duplicate set re-spawned five times, not thirty unrelated processes.
2. Count the warnings by minute to separate a one-off burst from a chronic loop: `grep "$(date +%F)" <log> | grep "<message>" | cut -c12-16 | sort | uniq -c | awk '$1>5'`. A repeating set of minutes with a fixed gap is a periodic sweep; a single dense block is a startup event. The cadence is what tells you whether a config change or a code fix is the lever.
3. Verify a config flag is actually honored before shipping it as the remedy. A setting already disabled on most entries while the failing path keeps touching them proves the path ignores that flag, and "disable more entries" is then a no-op that reads like a fix. Withdraw the recommendation explicitly instead of shipping it.
4. Re-check child count and RSS after cleanup and again after several sweep intervals. Steady children and flat RSS show the leak is not recurring; an immediate re-clone shows the parent respawns and the fix belongs upstream.
5. Note which of your own diagnostic commands can create the symptom: a CLI status probe that connects to every configured server, disabled ones included, emits the same warnings you are investigating. Exclude your own invocation window from the cadence analysis before blaming the daemon.

## Central incident store and alerting

For multiple recurring collectors, normalize findings into one redacted SQLite incident store instead of sending every raw report.

- Give each finding a stable source/kind/identity and keep changing exception details in redacted evidence; hashing variable error text into identity fragments one failure into many incidents.
- Clear both `resolved_at` and the obsolete resolution note when a resolved incident fires again. Test reopen and absence-based closure against a disposable database so an open record cannot falsely claim it is resolved.
- Trace the collector's ordering before enabling automatic reconciliation. If it clamps file permissions before measuring them, the clean result is post-treatment evidence—not proof that unsafe creation has stopped. Keep that source out of automatic closure until the creation path and observation method support it.
- For an approved manual closure, run a fresh check, verify the exact source and incident have not re-fired, back up the state, update only the intended record, and read it back. Document unresolved attribution or alternative failure paths rather than claiming every cause is eliminated.
- Permit severity escalation but never silent downgrade.
- Store every occurrence as evidence while tracking open, acknowledged, and resolved incident state.
- Emit only new high/critical incidents to messaging; mark delivery time so the next pass is silent.
- Keep containment human-approved. Monitoring may chmod known sensitive files, but it must not kill agents, revoke credentials, or alter cloud resources automatically.
- Test end to end with an authorized synthetic incident: first pass emits, second pass is silent, messaging delivery succeeds, then resolve the simulation so it does not pollute the live queue.
