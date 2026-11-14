# High-volume Kanban graph deployment

Use this recipe when the user requests an exact large worker count or a long evidence pipeline.

## 1. Compile and dry-run before creating cards

Generate a machine-readable node specification with: logical seat number, title, assignee, phase, idempotency key, parent seat numbers, skills, runtime, and completion contract. Validate in code:

- requested seat count equals generated seat count;
- idempotency keys and logical seat numbers are unique;
- every assignee exists;
- every parent is an earlier node and the graph is acyclic;
- the one-writer rule holds;
- every source partition is covered exactly once;
- every source node reaches the final package through the dependency graph.

The dry run must execute zero Kanban or external-source writes. Save its receipt before dispatch.

## 1b. Keep graph control artifacts durable

Store the graph contract, dry-run receipt, task-ID manifest, and dispatcher checkpoint outside idle-pruned scratch workspaces (for example under a durable Kanban control directory or as task attachments). If card bodies point to an absolute contract path, verify that path will survive for the graph's full lifetime, bind it by digest, and repeat the essential privacy/scope rules in each body so one missing file cannot deadlock later phases. Re-create a missing control file only from its verified digest/source, then resume affected cards; never silently substitute a different contract.

Track **logical seats** separately from recovery children that workers may spawn. A title-prefix count can exceed the requested worker count after continuation cards appear. Report original logical seats, recovery/continuation cards, total cards, and substantive completed seats as separate numbers.

## 2. Prove each execution route

For every profile/model family used:

1. Run a tiny direct `DISPATCH_OK` one-shot to prove authentication/model availability.
2. Create one canary card using the exact workspace kind, forced skills, sensitivity boundary, and output schema planned for that lane.
3. Read the canary back with `hermes kanban show <id> --json`; require a claimed run and substantive completion.

A configured profile, a successful direct chat, or a created card is insufficient alone. Forced skills are profile-local: a route can pass model authentication and still crash before work because the named skill is unavailable.

## 3. Create parents before children

Create nodes in topological order. Capture every returned task ID and pass real parent IDs during child creation; never link an already-ready child afterward. Use deterministic idempotency keys so rerunning an interrupted dispatcher reuses cards instead of duplicating them. Persist a manifest mapping logical seats to task IDs after every successful create.

## 4. Verify deployment as live state

Read back a representative node from every phase plus the first and final nodes. Verify title, assignee, skills, parents, workspace, status, runtime, and body contract. Report separate counts for planned, created, ready, running, done, blocked, and failed. "Created" is preparation, not deployed evidence; only substantive completed runs count as agents delivered.

Do not treat one `hermes kanban list --json` response as an exhaustive census for a large or expanding graph: list output can be bounded while recovery children and later review cards continue to exist. Reconcile state from the persisted logical-seat→task-ID manifest plus direct `hermes kanban show <id> --json` reads; maintain a second append-only registry for dynamically added repair/re-review cards. A title-prefix count is a dashboard signal, not proof that every known task was observed.

A watchdog timeout or restart is an operational event, not a workflow failure. Before restarting it, direct-read the final task and all currently running/blocked IDs; preserve workers, then resume monitoring from the manifests. The watchdog must never infer approval from aggregate `done` counts.

## 5. Recover without corrupting the graph

When a route fails:

1. Preserve the failed run and error in the audit trail.
2. Smoke-test the replacement route with the real skills.
3. Follow a role-safe fallback map prepared before launch: evidence collectors may move to another read-capable route, but reviewers must remain cross-family from the writer and the sole writer must remain unique. Never blanket-reassign every blocked card to one profile; that can silently erase independence and separation-of-duties gates.
4. `reassign --reclaim` only affected cards.
5. Re-list current statuses before unblocking. Status can advance between list and unblock; a batch command may return nonzero because one card is no longer blocked even though other cards need recovery.
6. Unblock the current blocked set individually or in status-homogeneous batches, then re-list and require zero blocked cards before reporting recovery.
7. Keep descendants parent-gated; unblock roots only unless a child has an independent external blocker.
8. For long graphs, run a deterministic watchdog that reports status transitions and recovers only cards allowed by the fallback map. The watchdog must stop on the exact final task state, not on aggregate counts, and its completion is not approval—the parent still reads the final verdict and artifact hashes.

Never convert a provider-auth crash, missing-skill startup failure, watchdog exit, or empty placeholder handoff into a completed seat.

## 6. Extend the graph on review failure

A reviewer reaching `done` is not an acceptance gate. Parse and persist `PASS / FAIL / NOT YET PROVEN` plus the exact candidate digest. Before synthesis or final delivery, require a verdict registry in which every mandatory review for the same exact revision is `PASS`.

When any reviewer returns `FAIL`:

1. Wait for the other independent reviewers so one repair writer receives the consolidated findings.
2. Create one repair card owned by the designated writer, parented by the failed reviews and original candidate.
3. Before the repair can finish and race downstream, add the repair and fresh exact-revision review cards as parents of synthesis and final-delivery tasks.
4. Any artifact edit invalidates every earlier artifact review, including earlier passes; rerun correctness, visual, privacy/security and source-coverage reviews against the new hashes.
5. If the failure is missing source evidence, create bounded retrieval/adjudication parents before the repair. Artifact editing cannot manufacture provenance or turn `NOT YET PROVEN` into `PASS`.
6. Preserve the rejected candidate, review receipts and hashes. Never overwrite a failed verdict with a later prose comment.

A status-only DAG that gates on `done` can release a reviewed-but-failed artifact; verdict-aware dependencies and exact-revision hashes are required.