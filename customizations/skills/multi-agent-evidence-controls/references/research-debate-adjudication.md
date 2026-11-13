# Research-debate adjudication

Use for consequential option comparisons where multiple agents advocate competing financing, restructuring, continuation or exit paths. This is a verification recipe, not a claim that any particular debate has reached consensus.

## 1. Prepare an evidence packet before advocacy

1. Identify the decision layers: enterprise financing, local operations, transition execution and distress contingencies. Mark compatible or sequential options; a false tournament between complementary options produces a misleading winner.
2. Give each evidence atom a stable ID, source locator, scope, period and verification status. Separate legal entity, school, campus, program and portfolio populations. Preserve the distinction between registry labels and verified operating authority.
3. Quote operative correspondence narrowly. Record missing headers, attachments, dates, conditions and final decisions; a constructive review response is neither a generic receipt nor necessarily a final approval or waiver.
4. Retrieve available decision-critical inputs before marking them unavailable. For financial workbooks, inspect all relevant tabs, exact cells, as-of dates, entity headers, adjustment columns and the reconciliation to submitted figures. Compare versions using content and source hashes rather than assuming a later-looking filename is authoritative. Check detail subtotals against summary formulas; a summary can classify intercompany assets differently. Record historical book equity/goodwill when found, but do not promote an adjusted or proposed entity-move view into current GAAP, legal-transfer or regulator acceptance.
5. List unresolved inputs explicitly. Distinguish `no source located`, `historical value located but not current`, and `current value not certified`; these support different arguments. Do not silently replace missing current cash, affected-student counts, costs, partner offers, lender terms or regulatory conditions with zero or the last available period.
6. Keep the user's preferred strategy visible as a baseline to test, not as evidence. Require advocates to state what would defeat their option and permit them to concede.

## 2. Capture genuine independent positions

Assign one actual task per requested seat. Track team, role, delegation handle, round, packet version and exclusive artifact path. Require a compact substantive output: thesis; claims with evidence IDs and qualifications; strongest objection; concession trigger; hard-constraint status; subjective scores with reasons; preferred options; missing facts; and any proposed combination.

Separate `constraint applies` from `constraint satisfied`. Use distinct statuses for demonstrated, conditional, contradicted and unknown. A law's existence does not establish that the company meets it. An unlocated adverse notice is not proof that no notice exists.

Do not let agents recursively broaden source discovery when the packet already answers their assigned question. Require the initial artifact before optional refinements so a time-limited lane can leave usable work. For evidence-only reasoning seats, supply concise source quotations and parent-computed values in the initial context and request the structured final return directly; parent archival is valid when identified as such. Do not describe this as independent fresh browsing. Require tools for any new arithmetic or a targeted source question rather than allowing invented calculations.

Include the complete schema before launch. Late steering may never reach a tool-free agent, so it cannot be the only source of required fields. Preserve a substantive return with missing scores as unscored, not an inferred ballot. Agent role labels describe AI functions, not professional credentials. Reusing a model in isolated contexts supplies separate arguments, not statistically independent expert evidence.

### Recover and archive completed returns

Use the completed tool return or its canonical result payload, not a truncated live-log preview. If the full completed return must be recovered locally, inspect the active profile's state database read-only: open SQLite with `file:<resolved-state-db>?mode=ro`, inspect `PRAGMA table_info(async_delegations)`, and select only `state, result_json` for the exact completed `delegation_id` with a bound parameter. Require state `completed`; never update runtime state or poll unfinished children through the database. Verify the local schema before relying on this optional recovery path.

Preserve the entire raw payload and each original summary string. If a JSON response is followed by runtime metadata, use `json.JSONDecoder().raw_decode` to identify its JSON span, archive that span without rewriting values, and retain the trailing material separately. Record the source delegation, task index, assigned seat, literal reported seat and artifact hash. An identifier mismatch is a provenance defect to flag, not a token to silently repair. A completion summary that differs from a saved substantive artifact must not replace it without explicit adjudication.

## 3. Audit the argument before accepting its evidence

For every completed seat:

1. Read the saved artifact; validate identity and required fields. A successful child exit or a hash alone does not verify its claims.
2. Extract material factual propositions and identify the precise source that supports each. Flag absolute language such as `only`, `mandatory`, `zero cost`, `guaranteed`, `dominated` and `fully protected` for explicit proof.
3. Run the arithmetic separately as code. Keep hypothetical inputs visibly separate from observed values and exclude synthetic test fixtures from the client packet.
4. Preserve the original submission. Record each error in a claim ledger with source, correction and decision impact; do not silently rewrite an advocate's position into a stronger one.
5. Publish a versioned evidence correction sheet without declaring an option winner. Supply all corrections to rebuttal participants and final voters, including seats whose openings predated the correction. Distinguish source retrieval from operative-text review: a table of contents, matching title or source presence does not verify the cited rule, exception or condition. Require an audit to identify the passages actually read and the checks not executed; a time-limited `no critical blockers` report with unread provisions is partial coverage, not a full pass. Close material gaps with targeted body-text reads and deterministic calculations before circulating the common decision packet.
6. Inspect every ledger-edit result, then reconcile persisted pending/running/completed/failed counts with actual task handles and substantive artifacts. Do not advance totals from intended writes.

## 4. Financial invariants to check

### Capital amount, ratio and instrument

For eligible current assets A, current liabilities L, target ratio t, added eligible cash F and new current liabilities D:

`post_ratio = (A + F) / (L + D)`

With D = 0, the simple ratio gap is `max(0, t*L - A)`. A separate cash-coverage gap is not the same test. A round proposed financing amount is not thereby the exact statutory minimum.

Distinguish equity, long-term debt, current debt, collection of a current receivable and collection of a noncurrent receivable. They affect current assets, liabilities and net worth differently. Include current maturities when relevant. Do not claim that only equity can improve a ratio, or that improving a ratio proves net worth, goodwill, asset eligibility, reporting-date or liquidity-runway compliance. Label each result as an observed balance, hypothetical post-funding balance or verified funded balance; a passing pro forma must not be reported as the existing books' ratio or proof the funding occurred. A smaller tranche may fail to reproduce the proposed ratio while still meeting the actual threshold.

Apply each state's exclusions and actual legal-entity scope. Do not add the same shared-entity deficiency once per state, count another entity's cash automatically, or count money as both retained regulatory liquidity and spent transition cash. A current contribution cannot rewrite an earlier fiscal-year balance sheet.

### Financing costs and buffers

`simple_carry_cost = principal * annual_rate * months / 12`

Calculate incremental-tranche cost from the incremental principal, not the whole facility. Label rates, durations, buffers and stop-loss thresholds as assumptions unless sourced. Do not convert an invented buffer into a regulatory requirement or a quantified 'bad month' without an actual cash-flow scenario.

### Refund and exit cash

For cash C, recorded obligations O, cash refunds R, recorded liability genuinely extinguished X, and additional unaccrued cash expense K:

`new_headroom = (C - O) + X - R - K`

Headroom is unchanged only when `R + K = X` under those accounting assumptions; an inequality can improve or worsen it. Avoid counting K twice if it is already part of the liability discharged. Deferred tuition is not necessarily the full legal refund obligation.

A successful teach-out may satisfy contracts before cessation. Do not automatically refund all tuition to every student who completed the program, assume every prior graduate is affected, or make third-party transfer the unique route to satisfying student obligations. Determine the applicable population, exceptions, ordinary refund rights and residual services.

A lawful completed exit may remove prospective local requirements without curing the historic balance-sheet deficit. That does not establish release from remaining-state, lender or prior-liability constraints.

### Sale proceeds and operating value

Use the seller's cash-flow sign convention consistently: a negative sale price means the seller pays the buyer. Liability relief may justify that payment, but it is not cash recovery. Compute net proceeds after retained obligations, holdbacks and costs; a sale or indemnity does not itself prove discharge of liabilities.

Do not infer avoidable cash burn from negative allocated EBITDA. Separate contribution, allocated overhead, avoidable costs, stranded costs and future cohort economics. Contribution before G&A means before general and administrative expenses, not before GAAP accounting; accrual contribution is not necessarily bank receipts. Derive each candidate's break-even from its own scope and comparable horizon rather than applying a whole-portfolio overhead-avoidability threshold to individual sites or cohorts. Positive historical contribution does not prove future starts are profitable. Unequal reporting periods do not establish year-over-year growth or consecutive full-year losses. School counts do not establish student counts, refund totals or market rank.

## 5. Legal and operational overreach checks

- Read the full controlling provision and its incorporated definitions before treating one subsection as the only compliance route. Record alternative/deemed-compliance pathways separately from baseline tests, with the actual qualification evidence still required; neither omit an alternative nor assume the company qualifies. Preserve distinct exemption branches instead of combining their conditions into an invented cumulative test.
- Distinguish a statutory remedy from a running case-specific penalty; establish the legal predicate before stating its consequence. A served enforcement order can be necessary for one specific penalty without being necessary for the underlying statutory, contractual or regulatory obligation to bind.
- Distinguish minimum pre-cessation notice/planning lead times from a deadline running from today; do not invent a completion or partner-search window.
- Keep proposed formation, application and effective-approval dates separate; incorporation is not licensing and an application target is not a guaranteed approval date.
- Apply security-release provisions to the actual instrument; a statutory cash-deposit rule is not necessarily a surety-bond or ordinary-operating-cash rule.
- Preserve all earlier operative commitments when considering a later milestone; do not recommend waiting until a later application target without checking preceding obligations.
- Do not rank a full cash refund as universally best for students; compare lawful completion, credential continuity, transfers, refunds and individual circumstances.

## 6. Rebuttal, voting and delivery

Build compact role-specific rebuttal briefs from actual returned fields: the team's member positions, a bounded set of named rival arguments, source-artifact locators and the shared corrected-evidence version. Keep full raw returns available by reference rather than duplicating every team's full openings into each packet; repeated corpus payloads waste context and obscure the objections the next agent must answer. Preserve excerpts verbatim and label them as challenged arguments, not accepted facts. Validate the brief schema and member/rival coverage in code before dispatch.

Circulate a common corrected finalist packet. Give every voter material evidence discovered after its opening and retain the original packet version so earlier ignorance is not misreported as disregard of known facts. Require each voter to answer the strongest opposing argument, identify any corrected claim that changes the vote, and state acceptance, conditional acceptance or dissent on the exact proposal. A spokesperson's concession is not unanimous team approval. A stable conditional policy is not unconditional agreement to execute it. If rankings, support booleans and prose conflict, preserve the contradiction and request an explicit final ballot; do not infer an acceptance or silently normalize a free-text choice into a valid option ID.

Aggregate ballots mechanically, with the full expected denominator and uncompleted seats visible. Apply legal/student-protection gates before subjective score aggregation. Stop bounded debate when the remaining obstacle is missing evidence rather than an unanswered argument; report the conditional winner, dissent, and information that could reverse it instead of inventing unanimity.

Deliver an editable Word explanation and Excel argument/evidence/vote matrix. Include the strongest losing cases, corrections, conditional coalitions and exact participant coverage. Keep individual artifacts and versioned source/correction manifests as supporting evidence. A recommendation does not authorize communications, borrowing, capital movements, enrollment changes, refunds, filings or closures.

### Verify a paired Word/Excel outcome package

1. Generate both formats from one option manifest and a shared recommendation statement; preserve old versions instead of overwriting the decision history. Count expected Word/Excel pairs programmatically and reject missing or duplicate option IDs.
2. Keep editable unsupported inputs blank and guard dependent formulas with a completeness check that returns `NOT YET PROVEN`. Distinguish observed values, scenario assumptions and policy thresholds in the cell notes and brief; an explicit zero requires evidence or an explicitly labeled illustration.
3. Render Word files with LibreOffice and recalculate Excel files with a real spreadsheet engine. Put document and workbook PDF proofs in different directories or give them distinct names—paired source files often share a basename, so a single PDF output directory silently overwrites one proof with the other.
4. Reopen recalculated workbooks with `data_only=True` for inspection only; preserve the formula-bearing version for delivery. Check expected scenario results, missing-input behavior, formula error cells and unintended external workbook links. Exercise each different outcome formula with separately labeled synthetic fixtures and exclude those fixtures from delivery.
5. Check the rendered documents for layout and substantive recommendation consistency, then build the ZIP from an explicit allowlist of final Word files and recalculated Excel files. Verify archive integrity, expected pair counts and member hashes; do not zip the whole workspace, which can contain stale recommendations, unreviewed drafts, private source material or synthetic test data.
