---
name: multi-model-agent-routing
description: Use when designing task-aware routing across LLM models.
version: 1.0.0
author: Hermes Curator
license: MIT
metadata:
  hermes:
    tags: [llm, routing, multi-model, orchestration, moa, fallback]
    category: autonomous-ai-agents
    related_skills: [hermes-agent, claude-code, codex, opencode]
---

# Multi-Model Agent Routing

Design and validate agent systems that can access multiple LLMs and choose among them by task.

## When to Use

Load this skill when the user asks whether an agent can pick the best model automatically, wire several providers into one agent, route inexpensive work to a fast model, preserve a premium model for hard work, add fallback providers, or use multiple models for high-stakes decisions.

Also load it when evaluating an LLM gateway/router, configuring auxiliary models, designing specialist subagents, or deciding whether to hot-swap the main model versus dispatch isolated workers.

## Core distinction

Before proposing a solution, separate five capabilities that are often conflated:

1. **Model catalog access** — one provider/account exposes many model IDs.
2. **Task-slot routing** — fixed auxiliary jobs (vision, compression, title generation, MCP routing, review) each use a configured model.
3. **Prompt-level model routing** — every user request is classified and sent to a different main model.
4. **Fallback** — another provider/model is used only when the preferred route fails.
5. **Ensembling / Mixture of Agents** — multiple models answer the same hard task and an aggregator synthesizes them.

Provider routing behind an aggregator may choose the infrastructure serving a model without choosing a different model family. Never describe provider routing as task-aware model selection.

## Access surface is a separate capability

Do not assume a configured multi-model fleet has its own web interface. A fleet may exist only as local profiles, CLI workers, or routes behind a primary orchestrator. Keep these separate:

1. **Fleet configuration** — models and specialist profiles exist and are callable.
2. **Orchestrated access** — the user asks the primary agent to “use the swarm,” and it dispatches and consolidates.
3. **Direct CLI access** — the user invokes a named profile or fleet script locally.
4. **Dedicated UI** — a separately built and deployed web application for selecting or running agents.

When the user asks for an “agent swarm link,” verify that a dedicated UI was actually built and deployed before returning any URL. Search the relevant project/session state and distinguish the swarm from unrelated task, bonus, action-item, or operations command centers. If no dedicated UI exists, say so immediately and give the real access path—normally the primary agent conversation or direct CLI. Never substitute a nearby-sounding dashboard URL.

## Mandatory discovery before recommendations

Inspect the live installation rather than answering from memory:

1. Check the agent/version and whether an update is available.
2. Read the resolved main-model, auxiliary-model, delegation, fallback, and routing configuration. For a cost-reduction request, include recurring monitors, child iteration/concurrency limits, persisted cron model/provider snapshots, and active-window overrides; inexpensive children alone do not stop an expensive parent from rereading large tool outputs. Trace the actual execution path for every affected job: a script-only/no-agent job can launch a native model CLI whose model, endpoint, child environment and billing pool are independent of the scheduler's model/provider metadata. Inspect that invocation before changing settings, because a correct-looking OpenRouter label may never be consumed by the failing process.
3. Identify which providers are actually authenticated; never assume an available model can be used.
4. Check current authoritative product documentation for model slots, routing, fallback, aliases, and MoA.
5. If a documented config key appears legacy or suspicious, search the installed source for actual runtime consumers before recommending it.

Report separately:
- what is available in the current installation,
- what exists only in newer documentation/upstream,
- what needs credentials or a third-party service,
- what would require custom engineering.

## Recommended architecture

Default to a stable main orchestrator plus isolated specialist calls. **the operator's standing default is separate parallel agents for multiple independent tasks**, whether they arrive in one request or as additional requests while authorized work is active. Do not ask whether to parallelize. Never dispatch the current main model as one of the parallel lanes: the active session already occupies that model, and the parallel lane stalls at 0 bytes. Exclude the conductor's model from the lane roster and record the effective independent-lane count in the receipt (a 5-model roster with the conductor running is 4 independent lanes + conductor — fine, but never report it as 5 independent voices). First reconcile the active-task ledger, reuse an existing owner where one exists, and dispatch another agent for the new independent lane rather than repeatedly displacing the earlier task. Explicit stop, cancel, or scope-change instructions still override ongoing work. Keep trivial steps, dependency chains and shared-write targets local or sequential, using the smallest useful number of children. Give every lane a non-overlapping scope, durable evidence path, acceptance criteria and explicit no-write boundary unless it is the designated writer. For broad optimization work, use read-only specialist audits first, then one synthesizer and one accountable implementation owner. The parent verifies results and returns one consolidated update, including blocked or unfinished lanes rather than silently dropping them.

When the operator asks for “top frontier models,” use the strongest currently authenticated and approved models for orchestration, synthesis, and independent judgment, while still routing bounded implementation to a suitable specialist. Verify live model access before fan-out and never hardcode a transient model ranking as permanent doctrine.

When the user treats the profiles as one swarm, a request to any member should route back through that orchestrator: all relevant specialists may contribute, but they receive distinct lanes and one designated integrator owns writes. Before dispatching, perform a project-lock preflight across the durable board, active workers/processes, git branches/worktrees, open PRs, and recent sessions. See `references/swarm-governance-and-project-locks.md`.

Default flow:

```text
User request
  → stable main/orchestrator model
  → classify task and sensitivity
  → handle directly OR dispatch isolated specialist model(s)
  → verify specialist output with tools/evidence
  → orchestrator returns one consistent response
```

Prefer this over changing the main model repeatedly inside a long conversation. Mid-session model changes can invalidate prompt caches, force the full conversation to be reread, change tool-call behavior, and create inconsistent voice.

### Suggested routing dimensions

Classify on more than “easy vs hard”:

- Task type: factual lookup, tool execution, writing, coding, vision, long-context analysis, strategic judgment
- Complexity and uncertainty
- Required context window
- Tool-calling reliability
- Latency target
- Cost ceiling
- Data sensitivity and approved providers
- Need for independent review or model diversity

### Example policy

| Task class | Route |
|---|---|
| Compression, titles, extraction, MCP selection | Fast inexpensive auxiliary model |
| Routine operational tool use | Reliable main agent model |
| Complex prose or document judgment | Strong writing/reasoning specialist |
| Coding implementation or review | Coding-specialized model in an isolated worker |
| Large document corpus | Long-context specialist |
| High-stakes or ambiguous decision | Two or more independent references plus aggregator |
| Sensitive HR/student/financial/legal data | Direct approved providers only |

Treat model names as configuration, not permanent doctrine. Capabilities, prices, and availability change.

## Provider auth, billing, and fan-out preflight

Authentication mode, model entitlement, and billing pool are separate routing dimensions. Before launching a costly parallel fleet:

1. Identify the exact auth mode each worker CLI is using (subscription/OAuth versus API key).
2. Run a no-change smoke test with the exact model, provider, repository, MCP overrides, and execution flags planned for workers.
3. Start one real lane and require actual tool/test output before expanding the fan-out.
4. Treat a process ID or successful startup as `NOT YET PROVEN`, not healthy execution.
5. If a billing pool fails, preserve branches, worktrees, commits, and uncommitted diffs; switch auth deliberately and resume the same lanes rather than spawning duplicate writers.
6. Verify the new auth mode and smoke test again before reporting recovery. Keep transport verification separate from mission verification: a bounded no-tools/no-MCP connectivity response can prove model reachability without running a remediation-capable security job, requesting reviews, changing incidents or advancing success fingerprints. Preserve model quality, prompts, tool/approval controls, locks, deduplication and schedules unless the user separately authorizes changes; report a staged fix as staged until the reviewed live invocation is installed and read back.
7. Do not source broad shared environment files merely to retrieve one credential; extract the exact key through a protected helper so malformed or shell-active lines cannot execute.

Distinguish unsupported-model errors, subscription usage limits, and API-credit exhaustion—they require different remediations. See `references/provider-auth-and-billing-failover.md`.

## Implementation options

### 1. Native auxiliary slots

Use when the platform already supports per-task model assignments. This is the lowest-risk and highest-leverage first step. Assign cheap/fast models to repetitive side jobs and reserve the main model for agentic reasoning.

### 2. Isolated subagents or one-shot workers

Use a stable parent agent to dispatch a self-contained prompt to a specialist model. The child receives only the minimum context and tools needed. Require a structured result and let the parent verify external side effects.

This preserves the parent conversation’s identity and cache while enabling task-aware model choice.

### 3. Mixture of Agents

Use selectively for consequential strategy, difficult analysis, or adversarial review. Configure diverse reference models and a separate aggregator. Do not run MoA on routine tasks; latency and cost multiply with every reference.

### 4. External automatic router

An OpenAI-compatible routing proxy can classify prompts and select models automatically. Before using one, review:

- whether prompts leave the local machine,
- retention/training policy,
- supported tools and parameters,
- payment method,
- observability and route explanations,
- ability to constrain sensitive tasks to approved providers,
- failure and fallback behavior.

A cost optimizer is not automatically a quality or privacy optimizer.

### 5. Custom policy router

Use when task type, organizational sensitivity, and executive stakes matter more than generic complexity. Keep policy explicit and auditable. Log the chosen route and reason without logging sensitive prompt content.

Separate offline planning, runtime execution, and enforced spending. Run a supplied package's tests and inspect its placeholders before binding it; an emitted graph or reservation formula does not prove a live controller or dollar cap. Verify real isolated execution, semantic acceptance, exact-revision gates and provider-usage reconciliation before claiming operational readiness. Keep unfinished controller work labeled as unproven rather than documenting it as a validated workflow.

A practical policy should support:
- allowlists by data class,
- per-route budgets/timeouts,
- fallback chains,
- escalation to MoA,
- deterministic overrides,
- route-quality evaluation.

## Hermes-specific guidance

For Hermes Agent, load the protected `hermes-agent` skill and verify the latest docs before acting. Typical primitives include:

- Main model selected per session
- Auxiliary model slots
- Per-job model/provider overrides for cron
- Delegation model/provider overrides
- Fallback providers for errors
- Model aliases and one-turn model switches
- Mixture-of-Agents presets
- OpenAI-compatible custom endpoints for external routers

Do not treat `smart_model_routing.enabled` as proof that prompt-level routing works. Verify that the installed version has a live runtime consumer and that current docs describe the behavior. A setup-written or migrated config key may be inert or legacy.

For a stable primary agent plus a separately controllable OpenRouter worker, use an isolated Hermes profile, secure the provider key only in that profile, query OpenRouter's live model catalog before choosing a model, and test both explicit-provider routing and the profile's default route. See `references/hermes-openrouter-secondary-profile.md`.

For a multi-profile fleet selected from live benchmarks, use the discovery, credential-minimization, exact-marker smoke tests, and concurrent validation procedure in `references/openrouter-benchmark-fleet-validation.md`. A successful text reply does not prove tool-call reliability; classify a model as advisory-only until a real tool call returns the expected marker.

When changing every Hermes profile to one provider/model, treat profiles as independent configuration islands, include configless profile directories, and verify the unforced default route plus a real tool call before restarting every active gateway. Use `references/hermes-fleet-model-migration.md`; do not claim an inert routing key changed runtime behavior merely because the config writer accepted it.

### One-shot profile dispatch (verified command shape)

For non-Kanban lanes (proposal / review / panel seats), the working dispatch shape is:

```bash
hermes --profile <p> chat $([ -n "$mid" ] && echo -m "$mid") --query-file <brief> -Q --max-turns 3 --run-budget 420 --yolo > <out>.log 2>&1
```

- The `chat` subcommand after `--profile` is mandatory — omitting it makes hermes parse the brief path as a subcommand (`'<path>' is not a hermes command`); the classic bug when copying a working dispatch into a shell helper function.
- `--query-file` for any brief containing JSON, quotes, or more than ~1-2KB of text (nothing is shell-interpreted); `-q` only for small plain-text queries.
- Scale `--max-turns` (5-6) and `--run-budget` (600s) with expected output size: a 2-turn budget produces a sub-1KB "ran out of steps" stub on ~56-node full-JSON outputs.
- Launch multi-lane runs from a runner script via `terminal(background=true, notify=true)` — the terminal tool rejects inline `&` in a foreground command. Lane output is buffered until completion: 0-byte log + live process means still running, not failed.

See `references/hermes-routing-notes.md` for a concise product-specific reference and validation checklist.

## Safety and governance

- Classify data sensitivity before routing.
- Keep student, employee, financial, legal, and investor data on explicitly approved providers.
- Do not send sensitive context to a third-party router merely because it is inexpensive.
- Minimize child context; avoid copying the full conversation into every specialist call.
- Treat model output as unverified, regardless of model prestige.
- Verify external writes and consequential calculations with tools or deterministic checks.
- Give each messaging bot credential exactly one gateway owner; CLI-only specialists must not inherit Telegram/Slack gateway tokens.
- Never persist an administrator password in a specialist profile. Keep profile roots owner-only and pass only role-required provider/tool credentials.
- Enable command scanning by absolute path and prefer fail-closed behavior for external specialist models; disable lazy installs unless package installation is part of the role.
- Treat CLI sandboxing and MCP isolation as separate controls. A read-only worker can still initialize every configured MCP server, trigger authentication requests, or leak request URLs into logs. For high-stakes and security-review lanes, explicitly disable each inherited MCP server, use a non-sensitive exact-marker smoke, confirm no MCP startup/auth event occurred, bound concurrency, verify workers exit, and scan leakage surfaces after configuration changes.

For a validated multi-profile host audit, including duplicate bot tokens, MCP-to-parent process ratios, desktop-agent local-exec helpers, and query-token log leakage, see the `macos-security-audit` reference `references/hermes-profile-and-agent-fleet-security.md`.

## Spec → tests → builds → judge workflow

For the operator's engineering work, use the least expensive qualified route by task type and effort. Use Terra-class coordination for routine orchestration; run mechanical extraction, counting, checks and state transitions as code. Reserve Astra-class premium calls for critical contracts, bounded replanning after evidenced implementation failures, foundational decisions and fresh exact-revision acceptance—not every window, polling loop or routine reviewer. Preserve independent premium security judgment. Load the user-designated engineering routing policy before assigning lanes; do not substitute the older fixed premium-conductor workflow.

Decompose recursively through three certification levels:

1. **Atomic/base unit:** define the smallest independently testable contract, then run micro-spec → independent tests → expected RED → build → deterministic verification → independent judge.
2. **Feature integration:** connect only passing atomic units; test contracts, data flow, auth, empty/error states, accessibility, security/privacy, regressions, and rollback.
3. **Whole application:** connect only passing features; test end-to-end journeys, cross-feature behavior, roles, reconciliation, performance, deployment, monitoring, rollback, and exact production readback.

Use open-weight workers for bulk bounded work: DeepSeek for atomic tests, code logic, debugging, and security challenge; Qwen for specifications, architecture, integration contracts, and feature/app review; GLM for routine execution. Do not run three copies of every model: use one lane from several model families for consequential nodes to gain error diversity, one low-cost lane for routine nodes, and escalate only after an objective gate fails. If one node fails, repair only that node and preserve passing siblings.

Operating sequence:

1. The orchestrator drafts a detailed controlling spec with acceptance criteria and secures required human architecture/data approvals.
2. Two or more models independently propose tests without seeing each other's work.
3. Record expected RED failures against the current implementation.
4. Build candidates only in isolated worktrees/branches. A second full build is optional for narrow changes only when an independent alternative design/review provides equivalent challenge and the waiver is recorded.
5. A model that authored no candidate judges spec compliance, tests, architecture, data correctness, security, maintainability, UX, and rollback safety.
6. One integrator synthesizes the selected result and reruns the required checks. Verify the committed artifact after hooks run, because formatters/refactoring hooks can change reviewed source; exercise standalone worker/test helpers without an application bootstrap to catch introduced framework dependencies. Before updating an existing PR, fetch and preserve intervening commits, reconcile overlaps, compare the final tree, and rerun affected checks. Bind remote CI and reviewer verdicts to the exact pushed SHA; verify production readback only when deployment is authorized.
7. The orchestrator provides the user one consolidated status; specialist messages and conflicting implementations never become separate user-facing deliverables. Match completion notices to the execution ledger before acting: if the result was already read and incorporated, absorb it without another unchanged status message. Exit code zero is not a new approval, and an explicitly draft-only verdict is never production acceptance.

Use PASS / FAIL / NOT YET PROVEN and cite real evidence. Never count labels, exit code, or self-report alone as comprehension or implementation proof; verify skill discovery, exact artifacts where applicable, and a behavioral smoke test.

### Deterministic recursive certification

Treat model-managed progression and release certification as separate gates. A goal judge can keep a worker iterating, but it cannot substitute for a deterministic release check because a worker may complete with missing or malformed evidence.

For any manifest-driven recursive swarm:

1. Validate the exact integer schema version, required IDs, nonblank acceptance criteria, sensitivity class, and task ceiling before graph construction.
2. Regenerate the expected graph from the validated plan; never trust an embedded graph as the authority.
3. Require exact, unique node and task-ID sets, and bind each live task to the expected complete title/body—not marker substrings—so truncation or instruction replacement fails closed.
4. Validate evidence by exact type and structure: path lists are nonempty strings, SHA-256 maps cover every path with 64 hex characters, RED exit codes are real nonzero integers, GREEN exit codes are real integer zero, and booleans never satisfy integer fields.
5. Certify from one consistent board snapshot. Use a database-native snapshot or backup transaction rather than sequential list/show reads, because a task can change after its individual read and before the final verdict.
6. Deny release on any missing task, extra task, body mismatch, incomplete run, invalid metadata, or snapshot error. Keep merge, deployment, and production writes outside the swarm unless separately authorized.
7. Derive idempotency keys from the hash of the complete validated plan, including full policy values and route inputs—not just a policy version or key list—because changed ceilings or role assignments must create a new graph identity.
8. Emit subprocess argv arrays only and validate user-controlled IDs as safe slugs; never generate shell command strings from task IDs, titles, model IDs, or provider names because a later controller may execute them through a shell.
9. Place irreversible-action approval after verification and premium acceptance, scoped to the exact final revision and action. Keep architecture/contract approval as a separate pre-implementation gate; combining them either authorizes an unknown revision too early or blocks safe implementation unnecessarily.
10. Reject cycles with a recursion-stack/visiting check before the completed/seen check, and mark a node seen only after its parents finish; marking it seen on entry silently accepts back-edges.

Create the full dependency graph while its root remains blocked, then open the root only after every card exists; otherwise a dispatcher can observe and execute a partial graph. Enforce the user's hierarchy globally: finish the complete atomic/base layer before feature integration, and finish all feature integrations before whole-app certification.

## Evaluation plan

Before enabling automatic routing globally:

1. Build a representative task set across routine, coding, writing, long-context, and high-stakes work.
2. Record expected route, minimum quality, latency ceiling, and cost ceiling.
3. Run the router in shadow mode: classify and log the proposed route while the current main model still handles the task.
4. Compare route decisions and outputs against a strong baseline.
5. Add regression cases for every user correction or misroute.
6. Enable automatic dispatch only after the confusion matrix and quality results are acceptable.
7. Retain a manual override and a “force premium/MoA” path.

## Verification checklist

- Multiple providers/models are authenticated and callable under the intended billing mode.
- Each worker CLI reports the expected auth mode; subscription/OAuth and API-key pools are not assumed interchangeable.
- One real lane reaches tool execution before a large fan-out begins.
- Each model passes separate exact-marker tests for plain text and required tool calls; exit code alone is not proof.
- Every profile assigned a card with `--skill` can actually discover and preload that custom skill in its own profile-scoped skill root; verify an exact-marker `-s <skill>` smoke for each role because profiles are independent islands.
- Critical-card model/provider pins override mutable profile defaults; verify the emitted card arguments and the recorded worker override so a coordinator model cannot silently replace the premium judge.
- Run one live controlled graph through the same deterministic certifier before declaring a new metadata contract proven; worker summaries can satisfy a human reader while failing strict evidence-shape validation.
- Advisory-only models are prevented from making or claiming external writes.
- Auxiliary slots resolve to the intended models.
- Fallback is tested by forcing a recoverable primary failure.
- Specialist workers receive the intended provider/model and minimal context.
- Sensitive-data rules prevent disallowed routes.
- The response records or exposes route choice for debugging.
- Prompt-cache and total-token costs are measured, not assumed.
- Existing sessions versus new sessions behavior is understood.

## Pitfalls

- Confusing access to many models with automatic selection among them.
- Calling fallback “routing”; fallback reacts to failure, not task fit.
- Switching the main model repeatedly and ignoring prompt-cache resets.
- Routing solely by prompt length or a simplistic “easy/hard” classifier.
- Assuming the most expensive model is best at tool use.
- Letting a third-party router see sensitive data without review.
- Hardcoding today’s model rankings into a permanent skill.
- Recommending a config key because it exists without proving runtime use.
- Updating the agent and routing configuration simultaneously without a rollback or verification plan.
- Treating a zero exit code, malformed control-token output, a process ID, or a plain-text success as proof that a model can use tools under the intended billing pool.
- Launching a large parallel fan-out before one real lane proves model entitlement, auth mode, billing, and tool execution.
- Assuming API credits automatically apply while a CLI remains authenticated through a separate ChatGPT/subscription pool.
- Giving every specialist a messaging gateway or broad business credentials when a key-only isolated worker is sufficient.
- Assuming a custom skill installed in the default profile exists in specialist profiles; explicitly distribute or install it per profile and verify preloading before dispatch.
- Letting multiple agents edit the same production system or branch concurrently; parallelize ideas and reads, serialize writes.
- Treating every multi-part request as a swarm: fan out only independent substantial lanes, because delegation overhead can exceed the work for trivial steps.
- Ending after parallel audits: require one structured issue register, one implementation owner, deterministic gates, and production readback before calling optimization complete.
- Dispatching before checking whether another session, agent, branch, or PR already owns the project. Similar task prompts can produce two valid but divergent implementations; detect and reconcile existing work before any new writer starts.
- Treating “the whole swarm participates” as “every model independently performs every side effect.” Give every useful specialist a lane, but keep one accountable owner, one active writer per target, and one final integrator.
- Conflating a configured agent fleet with a dedicated web UI, or returning an unrelated “command center” link without verifying it controls those agents.
