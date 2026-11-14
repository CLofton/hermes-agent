"""Offline tests: no network, no process kills, no writes outside tmp."""
import importlib.util
import pathlib
import sys

SCRIPT = pathlib.Path(__file__).resolve().parent / "triage.py"
spec = importlib.util.spec_from_file_location("triage", SCRIPT)
triage = importlib.util.module_from_spec(spec)
sys.modules["triage"] = triage
spec.loader.exec_module(triage)

PS = """  100     1 /Applications/Thing.app
  200   100 /usr/bin/python3 gateway run
  201   200 node /x/node_modules/.bin/mcp-hubspot
  202   200 node /x/node_modules/.bin/mcp-hubspot
  203   200 node /y/aircall-mcp-server/dist/index.js
  204   200 /bin/sh /h/hermes_cli/process_supervisor.sh 100
  205   200 /bin/sh -c something unrelated
  301     1 /usr/sbin/cfprefsd agent
  302     1 /usr/sbin/distnoted agent
"""


def test_identity_ignores_the_launcher():
    assert triage.mcp_identity("node /y/aircall-mcp-server/dist/index.js") == "aircall-mcp-server"
    assert triage.mcp_identity("npx -y clickup-mcp-server") is None


def test_gateway_is_matched_by_command_not_by_child_count():
    # pid 1 has more children than the gateway; picking it produced a system inventory.
    assert triage.gateway_pid(PS) == 200


def test_groups_by_identity_and_skips_supervisor():
    assert triage.mcp_children(PS) == {"mcp-hubspot": 2, "aircall-mcp-server": 1}


def test_excluded_pids_are_never_counted():
    counts = triage.mcp_children(PS, exclude_pids={201, 202})
    assert "mcp-hubspot" not in counts
    assert counts.get("aircall-mcp-server") == 1


def test_no_gateway_returns_none():
    assert triage.gateway_pid("  1 0 launchd\n") is None


def test_env_parsing_strips_quotes_and_ignores_blanks(tmp_path):
    env = tmp_path / "x.env"
    env.write_text('A="quoted"\nB=\'single\'\nEMPTY=\n# comment\nC=plain\n')
    assert triage.parse_env(str(env)) == {"A": "quoted", "B": "single", "C": "plain"}


def test_placeholders_and_empties_are_not_credentials():
    rows = triage.classify_credentials({
        "ANTHROPIC_API_KEY": "sk-ant-realvalue123",
        "OTHER_TOKEN": "your-token-here",
        "SECRET": "",
        "UNRELATED": "x",
    })
    assert {r["name"] for r in rows} == {"ANTHROPIC_API_KEY"}
    row = rows[0]
    assert row["provider"] is True and row["prefix_ok"] is True
