# Provider auth and billing failover

Use this reference when a multi-agent build must move between subscription/OAuth and API-key billing without losing work.

## Diagnose the failure class

- **Unsupported model for active auth mode:** model entitlement mismatch. Verify the live model under the current auth mode; do not assume config implies access.
- **Subscription or ChatGPT usage limit:** that subscription pool is exhausted. Existing API credits do not help until the CLI is explicitly switched to API-key auth.
- **API credit/billing error:** the active API-backed provider or organization lacks usable balance/authorization.

## Recovery contract

1. Stop creating new writers.
2. Inventory active processes and exact worktree status.
3. Preserve commits and uncommitted diffs; do not reset or restart from a clean branch.
4. Trace the scheduler → script/wrapper → native CLI or API call, then determine that process's actual auth mode. Inspect the job's script-only/no-agent flag, subprocess arguments and environment construction as well as the CLI status command. A scheduler provider snapshot does not override a separately launched model client; distinguish declared OAuth labels from observed auth/billing behavior before assigning a cause.
5. Locate an already-stored provider key through protected configuration. Never request that the user paste a credential if it is retrievable locally.
6. Switch the CLI's auth mode explicitly without printing the key.
7. Verify status reflects the intended API-key or OAuth mode.
8. Query the live model catalog when available, returning model IDs only.
9. Run a bounded connectivity smoke through the intended transport/model without private task context or enabled tools/MCP. Do not invoke a remediation-capable production wrapper merely to test authentication; that can perform authorized-but-unwanted real work and update durable success state. Record the model response and transport evidence without secrets.
10. Separately verify the exact operational flags and resume one authorized lane, requiring actual tool/test output. Preserve its prompts, model rigor, lock/dedup behavior, approval gates, schedule and reporting semantics; transport-only authorization is not permission to weaken them.
11. Resume remaining lanes only after the first proves healthy.
12. Keep one writer per worktree and one final integrator.

## Credential safety

Do not source an entire shared `.env` just to obtain one variable. Such files may contain spaces, malformed assignments, or shell-active content. Parse only the exact variable and pass it directly to the CLI's credential input with tracing disabled. Redact masked suffixes in user-facing logs when they add no diagnostic value.

## Reporting semantics

- `Auth configured`: status command confirms the intended mode.
- `Model reachable`: exact no-change smoke test succeeds.
- `Lane healthy`: real tool or test execution occurred.
- `Recovered`: failed lanes were resumed from preserved state under the new pool.

Do not collapse these into a premature “all agents are running” claim.
