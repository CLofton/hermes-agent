#!/usr/bin/env python3
"""Audit the local browser-automation stack for vulnerable Playwright / Chromium builds.

Detects, without side effects:
  * Node Playwright + @playwright/test versions in every repo under the scan roots
  * Python Playwright versions in site-packages and Hermes venvs
  * Bundled Chromium / Chrome-for-Testing builds in the shared ms-playwright cache
  * The installed Google Chrome version vs Chrome-for-Testing stable
  * Config smells in project sources (bundled Chromium against the open web,
    chromiumSandbox explicitly disabled, unpinned @playwright/mcp@latest)

Exit code: 0 = PASS/WARN only, 1 = FAIL (out-of-date package, no current build),
2 = usage/internal error.

Usage:
  python3 audit_browser_stack.py [--roots ~/Downloads,~/dev] [--json] [--quiet]
"""
from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import sys
from pathlib import Path

# --- Policy floor -----------------------------------------------------------
# Bump these only after verifying the release notes, not just the version number.
MIN_PLAYWRIGHT = "1.64.1"      # first release with the post-Oct-2026 Chromium patches
MIN_CHROMIUM_BUILD = 1248      # chromium-1248 == the 1.64.1 browser bundle
MIN_PY_FOR_CURRENT = (3, 10)   # Playwright >=1.64 refuses to install on 3.9
MIN_MCP = "0.0.40"             # fixes CVE-2025-9611 (DNS rebinding of local MCP tools)

DEFAULT_ROOTS = ["~/Downloads", "~/dev", "~/projects", "~/code", "~/Documents", "~/work"]
CACHE_DIRS = ["~/Library/Caches/ms-playwright", "~/.cache/ms-playwright"]
CHROME_APP = "/Applications/Google Chrome.app"
PRUNE = {".git", "vendor", "dist", "build", ".next", ".venv", "venv", "target", "Pods"}


def vtuple(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:4])


def vlt(a: str, b: str) -> bool:
    """True when version a < version b (numeric, tolerant of suffixes)."""
    return vtuple(a) < vtuple(b)


def read_version(path: Path) -> str | None:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore")).get("version")
    except Exception:
        return None


def scan_node(roots: list[Path], max_depth: int) -> list[dict]:
    """Find every installed node Playwright package without descending node_modules."""
    found = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, _files in os.walk(root, followlinks=False):
            p = Path(dirpath)
            depth = len(p.parts) - base_depth
            if depth >= max_depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d not in PRUNE]
            if p.name != "node_modules":
                continue
            for pkg, label in (("playwright", "playwright"), ("@playwright/test", "@playwright/test")):
                pj = p / pkg / "package.json"
                if pj.is_file():
                    key = str(pj.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    v = read_version(pj)
                    if v:
                        found.append({"kind": "node", "package": label, "version": v,
                                      "path": str(pj.parent)})
            dirnames[:] = []  # never walk inside node_modules
    return sorted(found, key=lambda d: (vtuple(d["version"]), d["path"]))


def scan_python() -> list[dict]:
    """Python Playwright versions from every interpreter we can locate cheaply."""
    found = []
    candidates = []
    for pat in ("/opt/homebrew/lib/python3.*/site-packages",
                "/usr/local/lib/python3.*/site-packages",
                os.path.expanduser("~/Library/Python/3.*/lib/python/site-packages")):
        candidates.extend(Path("/").glob(pat.lstrip("/")))
    venvs = Path(os.path.expanduser("~/.hermes/venvs"))
    if venvs.is_dir():
        for v in venvs.iterdir():
            for sp in v.glob("lib/python3.*/site-packages"):
                candidates.append(sp)
    for sp in candidates:
        dist = next(iter(sp.glob("playwright-*.dist-info")), None)
        if not dist:
            continue
        m = re.match(r"playwright-([0-9][^-]*)\.dist-info", dist.name)
        version = m.group(1) if m else None
        if version:
            found.append({"kind": "python", "package": "playwright",
                          "version": version, "path": str(sp)})
    return sorted(found, key=lambda d: (vtuple(d["version"]), d["path"]))


def bundled_version(build_dir: Path) -> str | None:
    for plist in build_dir.rglob("Contents/Info.plist"):
        if "Chromium" in plist.parts or "Chrome for Testing" in str(plist):
            try:
                with open(plist, "rb") as fh:
                    return plistlib.load(fh).get("CFBundleShortVersionString")
            except Exception:
                continue
    return None


def scan_browser_builds() -> list[dict]:
    builds = []
    for cd in CACHE_DIRS:
        cdir = Path(os.path.expanduser(cd))
        if not cdir.is_dir():
            continue
        for d in cdir.iterdir():
            m = re.fullmatch(r"chromium(?:-headless_shell)?-(\d+)", d.name)
            if not (d.is_dir() and m):
                continue
            builds.append({"kind": "browser-build", "package": d.name,
                           "build": int(m.group(1)), "version": bundled_version(d),
                           "path": str(d)})
    return sorted(builds, key=lambda d: d["build"])


def installed_chrome() -> dict | None:
    plist = Path(CHROME_APP) / "Contents/Info.plist"
    if not plist.is_file():
        return None
    try:
        with open(plist, "rb") as fh:
            data = plistlib.load(fh)
    except Exception:
        return None
    return {"kind": "chrome", "package": "Google Chrome",
            "version": data.get("CFBundleShortVersionString"), "path": CHROME_APP}


def source_smells(roots: list[Path], max_depth: int) -> list[dict]:
    """Flag config patterns that defeat the sandbox. Advisory only."""
    hits = []
    pats = [
        (re.compile(r"chromiumSandbox\s*:\s*false"), "sandbox disabled in config"),
        (re.compile(r"channel\s*:\s*['\"]chromium['\"]"), "explicitly selecting bundled Chromium"),
        (re.compile(r"@playwright/mcp@latest"), "unpinned @playwright/mcp"),
        (re.compile(r"--allowed-origins[^\n]*\*"), "MCP allowed-origins wildcard"),
    ]
    for root in roots:
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, files in os.walk(root, followlinks=False):
            p = Path(dirpath)
            if len(p.parts) - base_depth >= max_depth:
                dirnames[:] = []
            dirnames[:] = [d for d in dirnames if d not in PRUNE and d != "node_modules"]
            for fn in files:
                if not fn.endswith((".js", ".mjs", ".cjs", ".ts", ".json", ".md", ".sh", ".yml", ".yaml")):
                    continue
                f = p / fn
                try:
                    if f.stat().st_size > 400_000:
                        continue
                    text = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for rx, why in pats:
                    if rx.search(text):
                        hits.append({"file": str(f), "issue": why})
    return hits[:100]


def evaluate(node, py, builds, chrome, min_pw=MIN_PLAYWRIGHT,
             min_build=MIN_CHROMIUM_BUILD) -> tuple[str, list[str], list[str]]:
    fails, warns = [], []
    for pkg in node + py:
        if vlt(pkg["version"], min_pw):
            fails.append(f"{pkg['package']} {pkg['version']} < {min_pw} at {pkg['path']}")
    if py:
        for pkg in py:
            if not pkg["path"].startswith(os.path.expanduser("~/.hermes/venvs")) and vlt(pkg["version"], min_pw):
                warns.append(f"system interpreter below 3.10 caps Python Playwright at {pkg['version']} "
                             f"({pkg['path']}) — use ~/.hermes/venvs/playwright for {min_pw}")
    current = [b for b in builds if b["build"] >= min_build]
    if not current:
        worst = max((b["build"] for b in builds), default=0)
        fails.append(f"no chromium build >= {min_build} in ms-playwright cache (newest {worst})")
    if chrome and chrome.get("version"):
        newest_bundle = max((b.get("version") or "0") for b in current) if current else None
        if newest_bundle and vlt(newest_bundle, chrome["version"]):
            warns.append(f"bundled Chromium {newest_bundle} lags installed Chrome {chrome['version']} "
                         "— bundled build is fine for localhost, use channel:'chrome' for the open web")
        for b in current:
            if b.get("version") and vlt(b["version"], chrome["version"]):
                pass
    verdict = "FAIL" if fails else ("WARN" if warns else "PASS")
    return verdict, fails, warns


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="only print the verdict line")
    ap.add_argument("--no-smells", action="store_true")
    args = ap.parse_args(argv)

    roots = [Path(os.path.expanduser(r.strip())) for r in args.roots.split(",") if r.strip()]
    node = scan_node(roots, args.max_depth)
    py = scan_python()
    builds = scan_browser_builds()
    chrome = installed_chrome()
    smells = [] if args.no_smells else source_smells(roots, args.max_depth)
    verdict, fails, warns = evaluate(node, py, builds, chrome)

    report = {"verdict": verdict, "failures": fails, "warnings": warns,
              "policy": {"min_playwright": MIN_PLAYWRIGHT, "min_chromium_build": MIN_CHROMIUM_BUILD},
              "node": node, "python": py, "builds": builds, "chrome": chrome, "smells": smells}

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if verdict != "FAIL" else 1

    if not args.quiet:
        print(f"Browser stack audit — roots: {', '.join(str(r) for r in roots)}")
        print(f"policy: Playwright >= {MIN_PLAYWRIGHT}, chromium build >= {MIN_CHROMIUM_BUILD}\n")
        print(f"node installs ({len(node)}):")
        for n in node:
            flag = "OUTDATED" if vlt(n["version"], MIN_PLAYWRIGHT) else "ok"
            print(f"  {n['version']:<9} {flag:<9} {n['path']}")
        print(f"\npython installs ({len(py)}):")
        for p in py:
            flag = "OUTDATED" if vlt(p["version"], MIN_PLAYWRIGHT) else "ok"
            print(f"  {p['version']:<9} {flag:<9} {p['path']}")
        print(f"\nbrowser builds: newest chromium-{max((b['build'] for b in builds), default=0)}"
              f"{' / ' + str(max((b.get('version') or '0') for b in builds)) if builds else ''}")
        if chrome:
            print(f"installed Chrome: {chrome['version']}")
        if smells:
            print(f"\nconfig smells ({len(smells)}):")
            for s in smells:
                print(f"  {s['issue']:<40} {s['file']}")
        print()
    for f in fails:
        print(f"FAIL  {f}")
    for w in warns:
        print(f"WARN  {w}")
    print(f"VERDICT: {verdict}")
    return 0 if verdict != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
