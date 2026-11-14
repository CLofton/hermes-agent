#!/usr/bin/env python3
"""Read-only triage helpers for security-finding remediation.

    triage.py mcp                list gateway MCP children grouped by identity
    triage.py creds <env-file>   classify credential-shaped entries by provider
    triage.py secrets <dir>      gitleaks sweep with a vendored-code allowlist

Nothing here writes, kills, or rotates. Measurement only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter

# name -> (url, header template, real-value prefix)
PROVIDERS = {
    "ANTHROPIC_API_KEY": ("https://api.anthropic.com/v1/models", "x-api-key: {v}", "sk-ant"),
    "OPENAI_API_KEY": ("https://api.openai.com/v1/models", "Authorization: Bearer {v}", "sk-"),
    "ELEVENLABS_API_KEY": ("https://api.elevenlabs.io/v1/user", "xi-api-key: {v}", ""),
    "RESEND_API_KEY": ("https://api.resend.com/domains", "Authorization: Bearer {v}", "re_"),
    "SMARTSHEET_API_TOKEN": ("https://api.smartsheet.com/2.0/users/me", "Authorization: Bearer {v}", ""),
    "HOOTSUITE_ACCESS_TOKEN": ("https://platform.hootsuite.com/v1/me", "Authorization: Bearer {v}", ""),
}

LAUNCHERS = {"node", "npx", "npm", "python", "python3", "sh", "bash", "zsh", "env", "exec"}
GENERIC = {"index.js", "main.py", "cli.js", "server.js", "__main__.py"}
SUPERVISOR = re.compile(r"mcp_death_supervisor|process_supervisor\.sh", re.I)


def mcp_identity(command: str) -> str | None:
    """Server identity, ignoring the interpreter that launched it."""
    for token in reversed(str(command or "").split()):
        if not token.startswith(("/", "~")) and "/" not in token:
            continue
        name = os.path.basename(token.rstrip("/"))
        if name in LAUNCHERS or name.startswith("-") or not name:
            continue
        if name in GENERIC:
            parts = [p for p in token.split("/")
                     if p and p not in {"dist", "build", "src", "bin", ".bin", "lib"} and p != name]
            name = parts[-1] if parts else name
        return name
    return None


GATEWAY_HINT = re.compile(r"gateway\s+run|hermes\s+serve", re.I)


def _parse_ps(ps_output: str, exclude_pids: set[int]) -> list[tuple[int, int, str]]:
    rows = []
    for line in ps_output.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, ppid, cmd = int(parts[0]), int(parts[1]), parts[2]
        if pid in exclude_pids:
            continue
        rows.append((pid, ppid, cmd))
    return rows


def gateway_pid(ps_output: str | None = None) -> int | None:
    """The agent gateway's pid, or None when it is not running.

    Deliberately NOT "the process with the most children": on macOS that is
    launchd, and grouping its children produced a 300-line system inventory the
    first time this ran. Match the command line, then fall back to the parent
    holding the most MCP-identified children.
    """
    out = ps_output
    if out is None:
        out = subprocess.run(["ps", "-ax", "-o", "pid=,ppid=,command="],
                             capture_output=True, text=True).stdout
    rows = _parse_ps(out, set())
    # Several processes can match the hint: launchd spawns an osascript wrapper
    # whose command line also contains "gateway run", and the wrapper has no MCP
    # children. Prefer the candidate that actually owns some.
    owned: Counter[int] = Counter()
    for _pid, ppid, cmd in rows:
        if mcp_identity(cmd) and not SUPERVISOR.search(cmd):
            owned[ppid] += 1
    hinted = [pid for pid, _ppid, cmd in rows if GATEWAY_HINT.search(cmd)]
    for pid in sorted(hinted, key=lambda p: -owned.get(p, 0)):
        if owned.get(pid):
            return pid
    if hinted:
        return hinted[0]
    return owned.most_common(1)[0][0] if owned else None


def mcp_children(ps_output: str | None = None, exclude_pids: set[int] | None = None,
                 parent: int | None = None) -> dict[str, int]:
    """Count MCP-server children under the gateway, by identity.

    ``exclude_pids`` must include the caller and its ancestors: an agent shell
    is usually itself a child of the gateway this reports on.
    """
    exclude_pids = exclude_pids or set()
    out = ps_output
    if out is None:
        out = subprocess.run(["ps", "-ax", "-o", "pid=,ppid=,command="],
                             capture_output=True, text=True).stdout
    rows = _parse_ps(out, exclude_pids)
    gateway = parent if parent is not None else gateway_pid(out)
    counts: Counter[str] = Counter()
    for _pid, ppid, cmd in rows:
        if ppid != gateway or SUPERVISOR.search(cmd):
            continue
        ident = mcp_identity(cmd)
        if ident:
            counts[ident] += 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def parse_env(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            m = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$", line)
            if not m:
                continue
            value = m.group(2).strip().strip('"').strip("'")
            if value:
                values[m.group(1)] = value
    return values


def classify_credentials(values: dict[str, str]) -> list[dict[str, object]]:
    """Which entries look like credentials, and can we address them by provider."""
    found = []
    for key, value in values.items():
        if not value:
            continue
        if not re.search(r"(KEY|TOKEN|SECRET)", key, re.I):
            continue
        if re.search(r"(your|changeme|placeholder|example|<|dummy)", value, re.I):
            continue
        url, _header, prefix = PROVIDERS.get(key, (None, None, ""))
        found.append({"name": key, "length": len(value), "provider": url is not None,
                      "prefix_ok": bool(prefix) and value.startswith(prefix)})
    return found


def liveness(name: str, value: str, timeout: int = 20) -> str:
    """Provider verdict for one credential. One read-only request."""
    entry = PROVIDERS.get(name)
    if not entry:
        return "NOT TESTABLE"
    url, header, _ = entry
    cmd = ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
           "--max-time", str(timeout), url, "-H", header.format(v=value)]
    try:
        code = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10).stdout.strip()
    except Exception as exc:  # noqa: BLE001 - a probe reports, never raises
        return f"ERROR {exc}"
    return {"200": "LIVE", "401": "DEAD", "403": "LIVE but denied"}.get(code, f"HTTP {code}")


GITLEAKS_CONFIG = """[extend]
useDefault = true

[allowlist]
description = "vendored dependencies and build output"
paths = ['''node_modules/''', '''/\\.git/''', '''/vendor/''', '''/dist/''', '''/build/''']
"""


def secrets_sweep(path: str) -> dict[str, object]:
    """gitleaks content-rule sweep; counts by rule and repo."""
    with tempfile.TemporaryDirectory() as tmp:
        config = os.path.join(tmp, "gitleaks.toml")
        report = os.path.join(tmp, "report.json")
        with open(config, "w", encoding="utf-8") as handle:
            handle.write(GITLEAKS_CONFIG)
        subprocess.run(["gitleaks", "dir", path, "-c", config, "--no-banner", "--redact",
                        "--report-format", "json", "--report-path", report, "--exit-code", "0"],
                       capture_output=True, text=True)
        try:
            with open(report, encoding="utf-8") as handle:
                findings = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {"error": "no report", "findings": 0}
    by_rule = Counter(f.get("RuleID", "?") for f in findings)
    by_repo = Counter((f.get("File") or "").split("/")[0] for f in findings)
    return {"findings": len(findings),
            "by_rule": dict(by_rule.most_common(10)),
            "by_repo": dict(by_repo.most_common(10))}


def _ancestors() -> set[int]:
    seen, pid = set(), os.getpid()
    while pid and pid != 1 and pid not in seen:
        seen.add(pid)
        try:
            pid = int(subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)],
                                     capture_output=True, text=True).stdout.strip() or 0)
        except ValueError:
            break
    return seen


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "mcp":
        ps = subprocess.run(["ps", "-ax", "-o", "pid=,ppid=,command="],
                            capture_output=True, text=True).stdout
        gateway = gateway_pid(ps)
        if gateway is None:
            print("no agent gateway found")
            return 1
        print(f"gateway pid {gateway}")
        for name, count in mcp_children(ps, exclude_pids=_ancestors(), parent=gateway).items():
            print(f"{count:4d}  {name}")
        return 0
    if argv[1] == "creds" and len(argv) > 2:
        for row in classify_credentials(parse_env(argv[2])):
            print(f"{row['name']:26s} len={row['length']:<4d} provider={row['provider']}")
        return 0
    if argv[1] == "secrets" and len(argv) > 2:
        print(json.dumps(secrets_sweep(argv[2]), indent=2))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
