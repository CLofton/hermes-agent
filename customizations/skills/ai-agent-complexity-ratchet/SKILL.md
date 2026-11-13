---
name: ai-agent-complexity-ratchet
description: When building software with AI coding agents (Claude Code, Codex, etc.), enforce the "complexity ratchet" — every PR adds tests, docs, and evals so quality can only go up. Target 90%+ test coverage. From Garry Tan's essay May 2026.
platforms: [linux, macos, windows]
---

# The AI Agent Complexity Ratchet

When delegating coding work to AI agents (Claude Code, Codex, OpenCode, Conductor sessions), enforce the ratchet — a mechanism where every coding turn raises the quality floor and never lowers it.

Source: Garry Tan, "The AI Agent Complexity Ratchet: Why 90% Test Coverage Is Required" (May 11, 2026, 7th in his AI coding series).

## When To Use

Use this skill on ANY agent-driven coding task — solo dev or team — where:
- A codebase will keep growing (not a throwaway spike)
- AI agents will keep contributing on future turns
- Quality matters (production, customer-facing, security-sensitive)

Do NOT skip when "moving fast." Skipping the ratchet is why most vibecoded projects die at moderate complexity.

## The Three Things Every Turn Must Add

Every agent coding session must leave behind:

1. **Tests** — automated checks that encode what "correct" means. Run on every change. Fail loudly on regression.
2. **Documentation** — not just what the code does, but WHY the decision was made (tradeoffs, failure modes, prior bugs avoided).
3. **Evaluation results** — structured quality scores so the next version can be measured as better or worse.

If any of the three is missing, the ratchet has a tooth missing. The system can regress on the next turn.

## The 90% Coverage Target — Non-Negotiable

- Below 70% coverage: Defect Removal Efficiency (DRE) sits at 65-75%.
- At 85-95% coverage: DRE jumps to 92-97%. **Non-linear knee in the curve.**
- 90% is the threshold that turns chaos into a ratchet.

The classic objection: "the last 20% costs disproportionately more effort." That was true for humans. **AI agents don't experience effort.** They write the fourteenth edge-case test cheerfully. The wall that stopped human teams at 70% no longer applies.

> "Getting to 90% used to be a heroic effort. Now it's a Tuesday."

## What's Testable (Wider Than You Think)

The ratchet applies to anything a computer can observe:

- **OS level:** process trees, file system state, network sockets, cron job firing, migration outcomes.
- **Terminal level:** keystrokes, output, interactive prompts. Use TTY harnesses to spawn agents inside a pseudo-terminal and watch behavior.
- **Browser level:** rendered pages, button states, form fill-in, navigation events.
- **API level:** valid JSON, correct schema, status codes.
- **Behavioral level (AI agents):** did the agent ask before acting? Did it stop when told? Did it follow the skill protocol? Did it fire an interactive question or just dump output?

If you can harness it, you can observe it. If you can observe it, you can assert on it. If you can assert on it, you can ratchet it.

## The Three-Layer Response to Every Bug

When a bug surfaces (Garry's example: Claude Code skipping interactive plan reviews):

1. **STOP gates** in the skill/prompt instructions. Explicit "you MUST ask the user before X" with anti-rationalization clauses that name the specific failure mode so the model can't talk itself into the shortcut.
2. **Anti-shortcut clause** — one sentence that closes the exact loophole the model was exploiting (e.g. "the plan file is the OUTPUT of the review, not a substitute for it").
3. **Gate-tier floor test** — a test that catches the regression next time. For agent behavior: TTY harness that watches the terminal output in real time.

## Tests as Institutional Memory

Senior engineers leave. They retire, get poached, burn out. Knowledge dies with them. Classic comment: `// DO NOT CHANGE — ask Dave (Dave left 3 years ago)`.

**The agent's context window doesn't quit.** Tests + docs + evals = durable institutional memory any model can load on any future turn.

For a one-person project, tests are the ONLY institutional memory you have.

## Why Most Vibecoded Projects Die

Karpathy's "vibecoding" works fine. The death pattern:
- Skip tests → no regression signal → every new feature has a chance of breaking an old one
- Skip docs → next turn the agent doesn't know why constraints exist → repeats old bugs
- Skip evals → can't tell if quality is going up or down → quality drifts down
- By v0.5 it's a haunted house. Developer writes a "vibecoding doesn't work" blog post.

AI coding works fine. They just didn't build the ratchet.

## Process Rules For Hermes / Delegated Coding Sessions

When delegating to Claude Code / Codex / OpenCode / Conductor:

1. **Every PR ships with tests.** No exceptions. If the agent shipped code without tests, reject and reroll.
2. **Pre-merge gate: coverage ≥ 90%** on touched files (project-wide target, ratcheting toward 90% if currently lower).
3. **Every bug fix triples up:** prompt fix + anti-shortcut clause + new test. Not just "fix the bug."
4. **Every skill instruction gets a corresponding behavior test** when possible (TTY harness or eval harness).
5. **Tag each test with the lesson learned** in a comment: `// Locked after holder-confusion bug v1 → v2 (Apr 2026)`.
6. **Cross-model eval** for non-deterministic outputs: have GPT-5.5 and Claude both score; track the score over time as the eval baseline.

## Concrete Workflow Per Coding Task

When Hermes (or any agent) gets a coding task:

```
1. Read the existing test suite + docs + eval results into context.
2. Plan the change. Identify what behavior contract will change.
3. Write failing tests FIRST that encode the new contract.
4. Write the code to make the tests pass.
5. Run the full suite — nothing previously passing may now fail.
6. Update docs with the why (not just the what).
7. If output is non-deterministic, add an eval case + record score.
8. Ship the PR with all three artifacts.
```

## Red Flags That Mean Skip Is Happening

- Agent says "tests pass" but didn't add any new tests for the new code.
- Agent fixes a bug by editing one line, no test added — the bug WILL recur.
- New feature ships with 0% coverage on the new file.
- Skill instruction is added but no behavioral test guards it.
- Coverage dropped after a PR merged — STOP, this means the ratchet pawl is broken.

## The Big Idea (One Sentence)

> A system that can only get better, never worse — because tests, docs, and evals lock in every lesson learned, and AI agents make 90% coverage cost-free.

## References

- Garry Tan, "The AI Agent Complexity Ratchet" — https://x.com/garrytan/status/2054064931515855118
- Capers Jones, *Applied Software Measurement* (90% coverage → 92-97% DRE).
- DO-178C avionics standard (Level A: MC/DC coverage for flight-critical software).
- Mockus, Nagappan, Dinh-Trong — Windows Vista coverage study.
- GStack: https://github.com/garrytan/gstack (701k LOC, 37 contributors, ratcheting)
- GBrain: https://github.com/garrytan/gbrain (knowledge system, 25 contributors)

## Related Skills

- `test-driven-development` — RED-GREEN-REFACTOR enforces step 3-4 of the workflow above.
- `requesting-code-review` — pre-commit gates layer on top of the ratchet.
- `reviewing-existing-code` — when retrofitting ratchet onto an existing codebase.
- `subagent-driven-development` — when spawning Claude Code / Codex sessions, attach this skill so they ratchet.
- `claude-code-skill-authoring` — when authoring a new skill, build the behavioral test alongside.
