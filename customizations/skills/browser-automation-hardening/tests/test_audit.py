#!/usr/bin/env python3
"""Tests for audit_browser_stack.py — run: python3 tests/test_audit.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_browser_stack as A  # noqa: E402


def make_node_repo(root: Path, pkg: str, version: str) -> Path:
    d = root / "repo" / "node_modules" / pkg
    d.mkdir(parents=True, exist_ok=True)
    (d / "package.json").write_text(json.dumps({"name": pkg, "version": version}))
    return d


class TestVersionMath(unittest.TestCase):
    def test_vlt_basic(self):
        self.assertTrue(A.vlt("1.59.1", "1.64.1"))
        self.assertFalse(A.vlt("1.64.1", "1.64.1"))
        self.assertFalse(A.vlt("1.64.2", "1.64.1"))
        self.assertTrue(A.vlt("1.9.2", "1.10.0"))

    def test_vtuple_ignores_suffix(self):
        self.assertEqual(A.vtuple("1.64.1-beta"), (1, 64, 1))


class TestNodeScan(unittest.TestCase):
    def test_finds_and_flags(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_node_repo(root / "a", "playwright", "1.59.1")
            make_node_repo(root / "b", "playwright", "1.64.1")
            make_node_repo(root / "c", "@playwright/test", "1.63.0")
            found = A.scan_node([root], max_depth=6)
            versions = sorted(f["version"] for f in found)
            self.assertEqual(versions, ["1.59.1", "1.63.0", "1.64.1"])
            self.assertEqual(sum(1 for f in found if f["package"] == "@playwright/test"), 1)

    def test_does_not_descend_into_node_modules(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_node_repo(root, "playwright", "1.64.1")
            make_node_repo(root / "repo" / "node_modules" / "other", "playwright", "1.50.0")
            found = A.scan_node([root], max_depth=8)
            self.assertEqual([f["version"] for f in found], ["1.64.1"])

    def test_missing_roots_are_soft(self):
        self.assertEqual(A.scan_node([Path("/nonexistent/xyz")], 3), [])


class TestEvaluate(unittest.TestCase):
    def pk(self, v, path="/x"):
        return {"kind": "node", "package": "playwright", "version": v, "path": path}

    def test_fail_on_old_package(self):
        v, fails, _ = A.evaluate([self.pk("1.59.1")], [],
                                 [{"build": 1248, "version": "156.0.8078.4"}], None)
        self.assertEqual(v, "FAIL")
        self.assertTrue(any("1.59.1" in f for f in fails))

    def test_fail_when_no_current_build(self):
        v, fails, _ = A.evaluate([self.pk("1.64.1")], [],
                                 [{"build": 1243, "version": "156.0.8078.4"}], None)
        self.assertEqual(v, "FAIL")
        self.assertTrue(any("chromium build" in f for f in fails))

    def test_pass_clean(self):
        v, fails, warns = A.evaluate([self.pk("1.64.1")], [],
                                     [{"build": 1248, "version": "156.0.8078.4"}],
                                     {"version": "156.0.8078.4"})
        self.assertEqual((v, fails, warns), ("PASS", [], []))

    def test_warn_when_bundle_lags_chrome(self):
        v, fails, warns = A.evaluate([self.pk("1.64.1")], [],
                                     [{"build": 1248, "version": "156.0.8078.4"}],
                                     {"version": "156.0.8078.80"})
        self.assertEqual(v, "WARN")
        self.assertTrue(warns)

    def test_empty_stack_fails(self):
        v, _, _ = A.evaluate([], [], [], None)
        self.assertEqual(v, "FAIL")


class TestRootsAndPolicy(unittest.TestCase):
    def test_default_roots_include_downloads(self):
        self.assertTrue(any("Downloads" in r for r in A.DEFAULT_ROOTS))

    def test_policy_floor_is_post_oct_2026(self):
        self.assertFalse(A.vlt(A.MIN_PLAYWRIGHT, "1.64.1"))

    def test_smells_detect_disabled_sandbox(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "browse.js"
            f.write_text("chromium.launch({ chromiumSandbox: false })")
            hits = A.source_smells([Path(td)], max_depth=3)
            self.assertTrue(any("sandbox disabled" in h["issue"] for h in hits))


if __name__ == "__main__":
    unittest.main(verbosity=2)
