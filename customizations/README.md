# Agent customizations for Hermes Agent

Skills and operating method built on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent)
by one operator running a real business on it. Published as a working reference, not
as an official part of Hermes.

Everything here is **sanitized**: no credentials, no customer or employee data, no
internal hostnames, no company-specific numbers. See [SECURITY.md](SECURITY.md) and
[`scripts/check-disclosure.sh`](scripts/check-disclosure.sh), which is the same gate
this tree had to pass before it was published.

## What's in here

| Area | Skills |
|---|---|
| **Orchestration** | `agent-orchestrator`, `engineering-swarm`, `engineering-swarm-local-execution`, `recursive-engineering-swarm`, `subagent-driven-development`, `multi-agent-evidence-controls`, `merge-reconciler`, `agent-merge-conflict-arbiter` |
| **Model routing** | `multi-model-agent-routing`, `openrouter-agent-fleet`, `engineering-swarm/scripts/package` (tier registry + routing engine) |
| **Kanban fleet** | `kanban-orchestrator`, `kanban-worker`, `kanban-codex-lane` |
| **CLI delegation** | `claude-code`, `codex`, `grok`, `grok-collaboration`, `grok-daisy-chain` |
| **Fleet operations** | `profile-fleet-build-chains`, `cross-profile-skill-propagation`, `hermes-profile-skill-sync`, `shared-repository-fleet-management`, `telegram-bot-fleet-management` |
| **Hermes internals** | `hermes-agent-skill-authoring`, `hermes-update-troubleshooting`, `debugging-hermes-tui-commands`, `inspecting-hermes-desktop-dom`, `session-librarian`, `hermes-brain-backup` |
| **Memory** | `memory-engineering-pipeline`, `memory-mirror-to-obsidian`, `governed-self-improvement-loop`, `substantial-task-knowledge-capture` |
| **Security** | `repository-disclosure-governance`, `security-finding-remediation`, `browser-automation-hardening`, `github-repository-security-hardening`, `macos-security-audit`, `vulnerability-wire-monitoring` |
| **Reliability** | `local-terminal-process-monitoring`, `network-egress-diagnostics`, `scripted-cron-verification`, `webhook-subscriptions`, `alert-driven-remediation-operations`, `mcp-connection-triage` |
| **Evidence** | `artifact-provenance-search`, `system-of-record-reconciliation`, `native-mcp` |

`MANIFEST.json` lists every file with a SHA-256 of its skill directory.

## The flagship: `engineering-swarm`

A routing and verification engine for multi-agent engineering work. It decides the
*mode* (rigor floor) from task type and blast radius, then routes each lane to a
model tier, and requires independent review before a change is accepted.

```bash
cd skills/engineering-swarm/scripts/package
python3 router.py task.example.json --policy policy.json      # route a task
python3 -m unittest test_router                                # 69 tests
```

The router **refuses to route on a stale price registry** (`refused_stale_registry`)
rather than silently costing money on month-old pricing. `SPEC.md` is the design
document; `MIGRATION.md` and `HERMES_START_HERE.md` cover operations.

## Installing

```bash
# one skill
cp -R skills/engineering-swarm ~/.hermes/skills/autonomous-ai-agents/

# everything
cp -R skills/* ~/.hermes/skills/
```

Skills are picked up on the next Hermes session. Category folders here are flat by
skill name; Hermes groups by directory, so drop each one under a category you like.

## What is deliberately excluded

The author runs a company on Hermes. These were held back, because publishing them
would disclose confidential business information rather than transferable method:

- finance, compensation, board and investor material
- compliance and regulatory correspondence
- customer, student and employee data skills
- anything embedding account identifiers, internal URLs or vendor account numbers

Their *methods* show up in the included skills — that is the transferable part.

## Security posture

- Every text file passed an automated scan for credentials, emails, phone numbers,
  internal hosts, account identifiers and company/person names; substitutions are
  applied deterministically by `build.py`.
- No binaries were published unreviewed. The one image
  (`engineering-swarm/scripts/package/mermaid-diagram.png`) was visually reviewed:
  it is a flow diagram with no credentials, identities, URLs or real data.
- A captured browser profile (cookies, saved logins) was found inside a skill
  directory during audit and excluded. See `SECURITY.md`.

## License

MIT, matching upstream Hermes Agent.
