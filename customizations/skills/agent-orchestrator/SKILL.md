---
name: agent-orchestrator
description: Use when a task may benefit from delegating bounded work to subagents or Kanban workers — choosing local vs delegate_task vs Kanban, writing task contracts, running safe parallel lanes, and independently verifying results before synthesis.
---

# Agent Orchestrator

The parent agent is an orchestrator, not a pass-through. It classifies the request, keeps or delegates each piece, sends bounded contracts, verifies results itself, and delivers one answer. Workers execute scoped work; the parent owns correctness.

## Precedence

1. User instructions and the operator's standing rules (no sends, CRM deletes, personnel decisions, or calendar writes without confirmation).
2. **Engineering work:** load `engineering-swarm` before any engineering execution. Its mode floor, task-type/effort routing, safety flags (`+G`/`+H`), cost contract, worker limits, and exact-count rules control. This skill only adds delegation mechanics; it never lowers that policy's rigor.
3. This skill.

No orchestration choice may weaken approvals, privacy/PII boundaries, secrets handling, security review, external-write or release gates, or exact-count acceptance. Never split work to evade a gate.

## Lifecycle

```text
1. Check keep-local rules
2. Classify: task type (explore | implement | verify | operate) + domain
3. Pick surface: local | delegate_task | Kanban
4. Write one task contract per lane
5. Dispatch independent lanes in parallel; gate dependent lanes
6. Track status
7. Verify in the parent (readback + deterministic checks)
8. Recover failed lanes only
9. Synthesize one answer
```

## Keep It Local When

- Simple question, lookup, or a handful of tool calls
- Output is needed for the very next step (blocking)
- Tightly coupled edits, shared hidden context, or unclear boundaries
- Writing the contract costs more than doing the work
- **The parent's acceptance test for the lane is a script.** If you will verify a lane by re-running a deterministic check, the check *is* the work — run it locally and spend the delegation budget on lanes whose judgement you cannot script. A delegated number-crunch you intend to recompute yourself adds latency plus a second set of claims to refute, and on a small child model it may return nothing at all while the local script finishes in seconds.
- The user asked the current agent to do it

Do not spawn by default. Delegate only when it materially improves speed, quality, or isolation.

## Choosing the Surface

| Need | Surface |
|---|---|
| Short, reasoning-heavy, independent lanes finishing within this session (research sweeps, parallel drafts, bounded code investigation, independent review) | `delegate_task` |
| Durable work that must survive restart, has true dependencies, needs multiple profiles, human interjection, review loops, or an audit trail | Hermes Kanban (`kanban_create`, `kanban_show`, `kanban_list`, `kanban_comment`, `kanban_request_review`) — load `kanban-orchestrator` |
| Everything else | Local |

**delegate_task rules**
- Each child is a fresh context. Pass absolute paths, revisions/hashes, and concise findings — not the conversation or raw logs.
- Concurrency, depth, iteration, and timeout limits come from the live Hermes config and the `engineering-swarm` worker limits. Read them; do not assume a fixed number.
- Treat native delegation as homogeneous unless dispatch metadata proves the child's actual model. A prompt label is not model identity.
- **Read the effective child model from `delegate_task(action='list')` before expecting output, not after.** The `model` field is the real route. If it is a small model and the lane needs SQL, git, a database and judgement, re-route that lane to a CLI agent (see `references/cli-agent-lanes.md`) rather than waiting out an attempt you will have to redo. Rate-limit failures on that route also arrive as "provider returned error" after the full retry window, with no work produced.

**Kanban rules**
- Discover real profiles first (`hermes profile list`). Never invent assignees — unknown names sit in `ready` forever.
- Canary one representative card on each route before wide fan-out; a card ID means created, not working.
- Create dependent cards with `parents=[...]` at creation time. Leave independent lanes unlinked so they fan out.
- Use idempotency keys and a persisted task-id manifest for large graphs. Report planned / created / running / completed / failed / blocked separately.
- If a Kanban command is blocked on approval, it is not a retryable failure. Fall back to `delegate_task` only if the gate permits it, and log the substitution.

## Engineering Work

After loading `engineering-swarm` and taking its route:
- **Separation when warranted** (medium+ mode, E2+, or any safety flag): distinct owner (implementer), tester (independent test design), and reviewer. Reviewer and implementer use different model families.
- **One writer per target.** Parallel implementation only with disjoint write scopes; use separate worktrees where available.
- Mechanical checks run as code (tests, lint, type-check, hash/readback), not model loops.
- `+H` routes (prod, destructive, external-writes, release) stop for the operator before the irreversible step, regardless of reviewer APPROVE.

## Task Contract

Never dispatch "go handle this." Every lane gets:

- **Goal** — one outcome, one sentence
- **Inputs** — absolute paths, revisions, hashes, prior findings
- **Owned scope** — files/systems the worker may change
- **Forbidden scope** — what it must not touch, plus sensitivity boundary (PII, secrets, external writes)
- **Blocking or sidecar**
- **Expected output** — artifact path and schema (status, changes, evidence, open issues)
- **Verification** — the exact command or readback the parent will run
- **Limits** — iterations, time, and stop conditions (missing assigned file = stop and report, not search)
- **Evidence labels, mandated in the contract, when the lane produces research rather than code.** Require every substantive claim be tagged `EVIDENCE` (with inline source), `PRACTICE CONSENSUS`, `DESIGN` (the lane's own instructional/architectural suggestion), or `NOT SOURCED` (with what was searched), plus a closing list of unresolved gaps. This is what makes a lane honest instead of authoritative-sounding: well-behaved lanes then refuse to dress a designed intervention up as proven practice, and the `NOT SOURCED` list hands you the research agenda for free. Do not let a lane collapse `DESIGN` into `EVIDENCE` — that single substitution is how an invented dosage or cut score reaches a published document.
- **The domain's known false conclusions, stated as mechanics.** When a lane reviews specialist work, name the relationships that make the tempting answer wrong, or a weaker model returns it confidently and you spend the verification budget refuting it instead of using it. Two lines did this work on a forecast review — "enrollments are driven by media ÷ cost-per-enrollment and leads are derived backwards, so raising lead-to-enroll adds zero revenue" and "tuition is non-refundable and revenue is recognised across class weeks, so retention adds no recognised revenue" — and both lanes then correctly excluded those levers instead of reporting them as seven-figure opportunities. The same applies to arithmetic the parent intends to recompute: put the identity in the contract so the lane's numbers are checkable rather than merely plausible.

## Safe Parallelism

Parallelize: read-only exploration, disjoint write scopes, independent reviews, verification alongside non-overlapping work.

Do not parallelize: same-file edits, lanes whose output feeds the next step, work depending on unshared context, or any batch that would exceed configured or provider limits. On wide fan-outs, launch in bounded batches and checkpoint each result.

### Lanes that deliver through pull requests into one repo

When several lanes contribute to a shared repository, the contract carries the git rules explicitly or the lanes collide in ways nobody ordered:

- **One clone per lane, at an absolute path written into the contract.** Native delegation children inherit the parent's working directory, so a contract saying `gh repo clone <repo> <relative-dir>` puts every lane in the same place, and they fight over one index. Pin `<absolute-lane-dir>` per lane and confirm no two lanes share a checkout before fan-out.
- **Name the exact directory a lane may write** — one folder per lane — and add the path the *owner* completes afterwards to its forbidden scope. A worker will happily create the report folder that the platform generates after loading, and then fight the owner over it.
- **The lane commits to its branch and stops; the parent publishes.** Default to "do not push, do not open a pull request" in the contract: the parent reads the diff, re-runs the stated verification at that revision, and only then pushes and opens the PR. A lane that publishes its own work has graded its own exam, and merges stay the human's step either way. When a lane's closing summary contradicts its exit code, believe the artifact and the diff — an exit 0 with empty output files is a failed lane.
- **Generated artefacts belong to whoever owns the generator.** A lane must not hand-edit or regenerate a shared generated file (`schema.json` from `build_schema.py`, `setup.sql` from `build_ddl.py`, a lockfile): every lane touching it turns into a merge conflict in a file none of them claimed. If a lane believes the generator is wrong, it reports that with evidence instead of editing the output.
- **A lane that needs a stateful service gets a private instance on an explicit port**, not a shared fixed one; a fixed container name or port makes parallel lanes take turns or fail on bind.
- Independent lanes sharing one repo still need **disjoint paths**, so the four PRs can be reviewed in any order. If two lanes must touch the same file, they are one lane.

For a lane that must edit code, run a database and commit, prefer a CLI agent under a supervised contract over native delegation — `references/cli-agent-lanes.md` carries the launch recipe, the canary, and the flags that keep one lane from scanning the whole machine.

For evidence-heavy lanes, make the artifact the first action rather than the final action:

1. Write a schema-valid skeleton containing the exact assigned IDs before source discovery.
2. Checkpoint each completed item or small batch as evidence arrives. Reserve the final third of the turn budget for completing and reading back the artifact; stop expanding searches at that boundary.
3. On turn exhaustion, inspect both the file and transcript. If the transcript contains a complete drafted artifact but the file is missing, resume the same session with an artifact-only instruction and prohibit new research. This preserves the worker's context and avoids paying to rediscover evidence.
4. A nonzero exit can still leave a valid artifact. Count the lane only after deterministic ID/schema/evidence validation; do not discard good work merely because the final prose response or process exit was imperfect.
5. For a shared rate-limited MCP, collect source partitions once into sanitized local bundles, then fan out offline analysis. Many workers independently hitting the same proxy creates correlated throttling, inconsistent snapshots and privacy exposure.

## Status Model

`pending` → `in_progress` → `needs_review` → `completed`, with `blocked` and `abandoned` as explicit exits. A blocked lane is not a completed lane with gaps. Only `completed` lanes that passed parent verification count.

## Acceptance — Self-Reports Are Unverified

A worker saying "done, tests pass" is a claim, not evidence. Before accepting, the parent:

1. Reads back the actual artifact (file contents, diff, record, card state via `kanban_show`).
2. Re-runs the stated verification deterministically at the exact revision **and against the current head of the branch it will merge into**, including the repository's own gates — the loader/scanner/lint/in-sync checks the repo enforces, not just the lane's unit tests. A governance gate can be merged while a lane is still working, and it then rejects an artefact the lane verified honestly minutes earlier (a delivery whose generator file is fine data and a policy violation by placement). Run the gate yourself before publishing; the lane cannot have known about a rule that did not exist when it started. A merge landing mid-run invalidates a green you measured on the older base, and the failure mode is silent: every lane reports success against a tree nobody will merge. Fetch, merge the default branch, re-run, then publish; update the lane's own description when the merge changes what the checks find. A fresh failure overrides any earlier green run or reviewer APPROVE → `HOLD`.
3. Confirms the worker stayed inside owned scope (diff paths vs contract).
4. Checks completeness against the contract and conflicts with other lanes — by merging them, not by reading them. Two passes in a scratch clone: each lane's branch onto the current default (record conflicts), then **all lanes merged into one throwaway branch with the suites run there**. Per-branch `mergeable` flags answer only the text question; lanes that each merge cleanly still break each other through a shared package `__init__.py`, an overlapping test path, a common fixture or lockfile. Expect "merges cleanly but the merged tree fails" as a normal outcome, and never report a multi-lane delivery as ready on per-branch flags alone.
5. Confirms actual model/route from dispatch metadata when a tier-specific gate depends on it.
6. For exact-count requests, verifies in code that validated receipts equal the requested identity set (per `engineering-swarm`). Scripts, aggregators, and the parent never fill worker seats.
7. **Verifies the load-bearing citations of a research lane, not just the file.** A cited document is not self-verifying: a lane reading a secondary summary routinely transposes two percentages, restates a channel-specific share as a broader category, or attaches a real statistic to the wrong population. Fetch the primary source for every claim the recommendation actually hangs on — the figure in the executive summary, the regulation text, the standard's clause — and record a verdict per claim (exact / corrected / unsourced). Expect roughly one defect per half-dozen checks even from a strong lane, and carry the correction into the artifact with a note saying what changed, because the next reader will otherwise re-derive trust in the wrong number. Then read the *artifacts* the lanes wrote rather than their chat summaries; a lane can describe a table it never wrote.

   **Verify a lane's quoted evidence mechanically before calling it fabricated.** A strict whole-string containment test against the source reported 90 of 112 quotes as "not found", and the correct conclusion was that the lane was right and the test was wrong: a quote differs from its source by punctuation, curly quotes, an ellipsis, a truncation to a fixed character budget, or a dropped citation prefix. Normalise both sides (lowercase, punctuation to spaces, collapse whitespace) and match a prefix of the first four or five significant words; that test agreed on all 112. Two rules follow: never accuse a lane of inventing evidence on the strength of an unnormalised match, and never accept a quote with no match at all — a lane whose quotes cannot be found by a lenient test is the one that actually fabricated.
8. **Verifies the effect, not the write — especially of its own repairs.** A write that lands in the wrong row, or a lookup that misses and writes `0`, passes any "did this cell change" check while leaving the defect exactly where it was. A school restored by the parent read back as `0` enrollments and was reported as an empty school when its build block held 5.39, and the residual was then quoted as 0.0016 against a true 7.08. Print the key the lookup attempted and the key set it searched; never interpret a zero, and after any repair re-read the quantity the repair was supposed to move, from a recalculated copy rather than the object you just wrote.

9. **Vendor claims are self-reports too.** A launch post, a release tweet and a benchmark chart are claims, not evidence. Read the release notes' own benchmark table and check the headline against it: the announcement frequently claims more than the table supports, and the table's confidence intervals may show no significant difference at all. Identify which metric actually moved — cost and latency often improve while quality stays flat — and look for the comparison arm's provider errors and excluded runs before repeating a number. Then read the changed defaults as behaviour changes, not footnotes: a new default model, a new cloud dependency, a lowered step or time limit. Pin to the previous minor for production and measure on your own workloads before adopting.

10. **A lane that contradicts the framing you gave it is the finding, not a contract violation.** When a contract states a hypothesis ("most of these rows look like practitioner regulation rather than school obligations"), acceptance must test the lane's answer against it explicitly and say whether it survived. In one triage the parent's stated hypothesis was wrong in the majority direction — 64 of 112 rows were obligations the parent's own classifier had failed to read — and accepting the lanes meant discarding the parent's explanation rather than defending it. Report the reversal in the same message that carries the numbers: a hypothesis quietly dropped leaves the wrong explanation in circulation, and the next reader will re-derive it. Stating a hypothesis in the contract is worth doing precisely because it makes being wrong visible.

## Verification swarm for a deliverable pack

When the artifact is a pack of documents or workbooks rather than code, verification is its own fan-out: **lane 0 (deterministic, run by the parent)** plus two or three **independent reviewer lanes** on different lenses, ideally different model families. Reviewers must not be the authors of the thing they review, and must not be told the answer is good.

- Give every reviewer the same fixed verdict vocabulary — `PASS` / `FAIL` / `NOT EVIDENCED`, plus `BLOCKER` / `MATERIAL` / `MINOR` on failures — and require one findings file at a known path plus a single closing `CONFIDENCE: <0-100>` line. A lane that omits the findings file or the confidence line has not completed its contract; say so rather than parsing its chat.
- Run the deterministic lane yourself even when delegation is available: if you plan to recompute a number to accept a lane, the recompute is the work (see Keep It Local When). The harness is also where your own errors surface — compare counts exactly, and be suspicious of a generous float tolerance that lets a wrong count pass.
- Reviewer output is a claim too. Triage findings: verify each `FAIL` yourself before rewriting an artifact, and expect overstatement in both directions (one lane called 12 contaminated rows "shifted columns" when the real defect was trailing contamination in two cells).
- Recompute the score after fixes, from the new artifacts. Never restate the pre-fix confidence as if it still applied.
- **Re-review a repair pass with a fresh lane, and hand it the repair log.** State what was changed and why, then ask explicitly whether each change is correct and complete — not what else is wrong. A lane told only "audit this" re-derives the original defects and spends its budget rediscovering what was just fixed; a lane given the log attacks the repairs themselves and finds the ones that silently failed. Instruct it to state whether a finding is new, a consequence of a listed repair, or out of scope.

Lane designs, launch mechanics and the synthesis recipe: `references/verification-swarm.md`.

## Recovery

1. Diagnose the exact failure point from transcript/metadata (rate limit, scope violation, bad contract, real defect).
1a. **A command blocked on an approval gate did not run — it is a consent timeout, not a failure.** Nothing executed, so never retry it, rephrase it, or reach the same outcome by another command. Verify on disk what state the tree is actually in (the rename did not happen, the tree is clean, HEAD still matches the remote), then re-plan the step **without the destructive part**. Most such commands only needed approval because ordinary work was bundled with an irreversible operation: an `--amend` plus `push --force` behind a rename is an additive commit and a fast-forward push if you separate them. Bundling is also why the harmless half never ran.
2. **When lanes share a checkout, stop the whole batch before diagnosing.** Children that inherited one working directory can corrupt each other's index while you investigate, and a lane interrupted in flight produces nothing you can trust anyway. Stop them, then audit the shared tree (`git branch -a`, `git log`, `git status --short`) to see whether anything salvageable exists: an empty result means a clean re-dispatch, and each lane gets its own directory next time. Say plainly which lanes returned nothing rather than reporting them as "failed" alongside real defects.
2b. **A lane that died usually left the working tree untouched — prove it before re-dispatching.** When `delegate_task(action='list')` is empty and no completion message arrived, do not wait: inspect disk. Compare the target file against the backup the contract told the lane to take; identical byte counts mean it made no edit at all, which is a clean re-dispatch. Also re-parse the target (`ast.parse`, lint, or the domain's loader) to prove the lane did not leave it half-rewritten, and check whether the promised output artifact exists. A lane that dies after step 0 of its contract costs nothing to repeat; one that dies mid-rewrite costs a restore first. The transcript tail tells you which — read the last few tool results, not the lane's absence.
3. Preserve completed lanes and the failed-attempt trail; retry only unfinished lanes, with capped attempts.
3a. **An iteration-capped lane returns `completed` with a TRUNCATED warning and can leave an artifact its own summary disowns.** Read that flag as a first-class status: the file may exist, be well-formed, and still be the pre-patch version. The lane is usually honest about this ("the current v10 is not accepted and should not be used") — believe it, and do not upgrade a truncated lane to done because the artifact path resolves.

   The cheap recovery is to **finish the job with the lane's own scripts** rather than re-dispatch: a lane that capped while fusing or verifying has normally already written the generator, so re-running it is one command. Look through the lane's working directory for its build/fuse scripts and per-step logs, re-run the generator, recalculate, then verify the acceptance criteria yourself. One parent pass regenerated a fused workbook from the lane's patched script and verified the full check suite — cheaper than another twenty-minute lane.

   **Trust the delivered artifact over the lane's intermediate logs.** Per-step logs can print a check `PASS` beside a multi-million variance, because the check was measuring something other than the column shown. Recompute the acceptance quantities from the final file, and treat a log that contradicts its own labels as evidence the check — not the number — was mis-specified.
4. On HTTP 429, honor the provider reset window or move to a verified different route — a redispatch on the same inherited route is not a substitution.
4a. **Correlated failure counts once.** Siblings dispatched in a single `delegate_task` call normally share one provider and often one model, so when every lane dies with the same provider error the batch has suffered *one* infrastructure fault, not N task failures. A whole fan-out is therefore a single point of failure. Once the first sibling reports a provider error, stop dispatching into that route: pin a different provider/model for at most one retry, or take the lanes yourself when you already hold the tools and the evidence they needed. Three siblings that each burned their full retry window before failing is the signal to stop delegating that batch, not to send a fourth. Report the substitution plainly — an audit delivered directly after a dead lane is a real result, and saying so is more honest than implying the work was delegated.

**Where the route actually lives — check this before blaming the contracts.** Every native `delegate_task` lane inherits one configured child model, set in `~/.hermes/config.yaml` under `delegation.model`, with `fallback_providers` as the availability backstop. A weak or rate-limited model pinned there fails *every* lane identically, however good the task contracts are, and the symptom is always the same: long durations, "provider returned error" or "unresponsive … stale attempts", `api_calls` of 1-12, and zero findings. `delegate_task(action='list')` shows the model actually in use. Repair, with the config backed up first:

```bash
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.bak.$(date +%H%M%S)
# set delegation.model to a strong model, and give fallback_providers at least two entries
```

Confirm the new value took by reading it back out of the file, then re-dispatch. Choose the child model by the work: an audit that must hold a 5,000-row cross-tab in view needs a strong model, not a small fast one — and a lane whose output you intend to recompute arithmetically yourself should not be delegated at all (see Keep It Local When).
4b. **When the requirement changes mid-flight, steer the live lane — do not dispatch a second writer at the same artifact.** A lane already writing the target file is the cheapest executor of a new constraint: `delegate_task(action='steer', subagent_id=..., message=...)` appends the new instruction to its next tool result, and the lane keeps whatever work is already done. Firing a fresh writer at the same workbook or file instead loses the in-flight work and puts two writers on one target, which is the failure this skill warns about everywhere else. Two things to check on the way out: the steer response says *queued*, not applied, and a lane that reaches its final tool result before the next delivery boundary reports the text back as `missed_steer` — so verify the artifact contains the change rather than trusting that the message landed. When two constraints in the same steer conflict (a cost cut that also has to hold a margin), say so in the steer and ask the lane to report the conflict rather than silently picking one.

**The standing shape for "audit and then fix this artifact": N read-only auditors, then exactly one writer.** Fan out two or three independent reviewers on different lenses (mechanics, domain methodology, structure/plausibility) with explicit instructions that they must not modify the file, let their findings land, then commission a single writer — or do the write yourself — against the consolidated list. Two writers on one workbook produce a file neither of them can explain, and version-number collisions on top of that (a `v28` rewritten under you) make the result unverifiable. If the auditors disagree about a number, that disagreement is the finding; resolve it in the parent before the writer runs.

5. Fill small gaps locally when cheaper than redispatch — but **check the constraint before overriding a worker's refusal to produce.** A lane that withholds rows as unevidenced is usually right, and the way to lose that is to "just add the obvious ones": read the required fields in the schema/format doc first, because a `required` string with no source in reach is exactly why the lane stopped. Overruling a correct refusal invents data that lands in git history.
6. Fix the contract if the failure was a vague or misrouted assignment. When the owner revises the contract document in response to your lanes' work — a spec written expressly to answer the PRs — send a **correction contract**, not a reopened goal: name each failing test, quote the changed rule text verbatim, state which mechanism to adopt, and repeat what must not change (the generator, the examples, the sources). Read the revision first for which of your findings it accepted and which it overruled, and record the retractions; a lane told only "make it pass" re-derives the superseded rule from its own old control and reports green on the wrong semantics.
7. Never report complete from a heartbeat or partial aggregate; label partial results provisional.

## Synthesis

Deliver one answer, not forwarded fragments. Lead with outcome and verified numbers, flag unresolved conflicts and blocked lanes, separate verified facts from unverified worker claims, and state any gate awaiting the operator's approval.

**On a multi-increment build, end a turn with the next increment done, not with a report and a question.** When the remaining work is already known and needs no permission — run the loop over the other 29 regions, apply the reviewed overrides, regenerate the register, commit — do it before reporting, and report what changed. A turn that closes with a summary plus "say the word and I'll…" spends the owner's next message on permission he did not withhold, and the repeated "keep going" / "retry" that follows is the cost. Reserve the closing question for a decision only he can make: an irreversible write, a merge, a judgement about the business, or spending a gate. Everything else is execution.

**When he says more budget was added, that is a signal he believes you are stalled — go do the work, do not narrate why you stopped.** "I added credits", "retry", "keep going" are not questions about allocation; they mean the previous turn ended without progress. Re-read what you last promised, then take the next real step and show its output.

