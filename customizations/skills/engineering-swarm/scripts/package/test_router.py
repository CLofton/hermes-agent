#!/usr/bin/env python3
"""Verification for the Hermes engineering swarm v2 package.

Each test class maps to an acceptance criterion in SPEC.md §15. Run:
    python3 -m unittest -v test_router.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import unittest
from copy import deepcopy

import router

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = dt.date(2026, 9, 8)
EFFORTS = router.EFFORTS


def load(name: str):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return json.load(fh)


POLICY = load("policy.json")
EXAMPLE = load("task.example.json")
TASK_TYPES = [t for t in POLICY["task_types"] if t.startswith("T")]


def task(task_id="t1", files=(), title="", description="", signals=None, flags=(), env=None, limits=None,
         opinions=None, items=None, effort_hint=None):
    t = {"task_id": task_id, "title": title, "description": description, "files": list(files),
         "signals": {"mechanical": False, **(signals or {})}, "requester_flags": list(flags)}
    if env:
        t["environment"] = env
    if limits is not None:
        t["limits"] = limits
    if opinions:
        t["opinions"] = opinions
    if items:
        t["items"] = items
    if effort_hint:
        t["effort_hint"] = effort_hint
    return t


# ----------------------------------------------------------------------------- criterion 1

class TestMatrixEnumeration(unittest.TestCase):
    """Every (T, E) cell resolves to a valid route family, an explicit re-route, or an explicit floor."""

    def test_seventy_cells_exist(self):
        cells = [(t, e) for t in TASK_TYPES for e in EFFORTS]
        self.assertEqual(len(cells), 70)
        for t, e in cells:
            self.assertIn(e, POLICY["matrix"][t], f"missing cell {t}.{e}")

    def test_every_cell_resolves_or_reroutes(self):
        grammar = re.compile(r"^(R[0-4](\+[EPGHV]+)?|RE|->T\d+(\|T\d+)*|->reroute|\^E[0-4])$")
        for t in TASK_TYPES:
            for e in EFFORTS:
                raw = POLICY["matrix"][t][e]
                self.assertRegex(raw, grammar, f"{t}.{e}={raw}")
                res = router.resolve_cell(t, e, [], POLICY, signals={"behavior_preserving": True})
                self.assertIn(res["status"], ("ok", "reroute_required"), f"{t}.{e}")
                if res["status"] == "ok":
                    self.assertIn(res["family"], POLICY["route_templates"])
                    self.assertRegex(res["cell"], r"^(R[0-4]|RE)(\+[EPGHV]+)?$")

    def test_reroute_alternatives_are_chosen_by_signal(self):
        a = router.resolve_cell("T1", "E2", [], POLICY, signals={"behavior_preserving": True})
        b = router.resolve_cell("T1", "E2", [], POLICY, signals={"behavior_preserving": False})
        self.assertEqual(a["task_type"], "T9")
        self.assertEqual(b["task_type"], "T5")
        self.assertEqual(a["history"][0]["rule"], "->T9|T5")

    def test_floor_cell_raises_effort(self):
        res = router.resolve_cell("T3", "E0", [], POLICY)
        self.assertEqual(res["effort"], "E1")
        self.assertEqual(res["cell"], "R1+P")

    def test_architecture_at_low_effort_is_a_reclassification(self):
        for e in ("E0", "E1", "E2"):
            self.assertEqual(router.resolve_cell("T13", e, [], POLICY)["status"], "reroute_required")
        self.assertEqual(router.resolve_cell("T13", "E3", [], POLICY)["cell"], "R4+G")

    def test_matrix_matches_task_type_metadata(self):
        for t, row in POLICY["task_types"].items():
            for e in EFFORTS:
                res = router.resolve_cell(t, e, [], POLICY, signals={})
                if res["status"] != "ok":
                    continue
                for m in row.get("modifiers", []):
                    if res["family"] == "RE" and m in "PG":
                        continue
                    self.assertIn(m, res["modifiers"], f"{t}.{e} missing row modifier {m}")
                for m in row.get("modifiers_by_effort", {}).get(res["effort"], []):
                    self.assertIn(m, res["modifiers"], f"{t}.{e} missing effort modifier {m}")


# ----------------------------------------------------------------------------- criterion 2

class TestGatesAndFlags(unittest.TestCase):
    """Critical rows always gated; flags add G and H in any cell."""

    def test_t7_and_t11_carry_G_and_H_at_every_effort(self):
        for t in ("T7", "T11"):
            for e in EFFORTS:
                res = router.resolve_cell(t, e, [], POLICY)
                self.assertEqual(res["status"], "ok")
                self.assertIn("G", res["modifiers"], f"{t}.{e}")
                self.assertIn("H", res["modifiers"], f"{t}.{e}")

    def test_G_flags_add_premium_gate_in_any_cell(self):
        for flag in POLICY["flag_effects"]["G"]:
            for t in TASK_TYPES:
                for e in EFFORTS:
                    res = router.resolve_cell(t, e, [flag], POLICY, signals={"behavior_preserving": False})
                    if res["status"] != "ok" or res["family"] == "RE":
                        continue
                    self.assertIn("G", res["modifiers"], f"{flag} on {t}.{e}")

    def test_H_flags_add_human_interrupt_in_any_cell(self):
        for flag in POLICY["flag_effects"]["H"]:
            for t in TASK_TYPES:
                for e in EFFORTS:
                    res = router.resolve_cell(t, e, [flag], POLICY, signals={"behavior_preserving": False})
                    if res["status"] != "ok":
                        continue
                    self.assertIn("H", res["modifiers"], f"{flag} on {t}.{e}")

    def test_infra_gets_H_only_with_prod_flag_at_low_effort(self):
        self.assertNotIn("H", router.resolve_cell("T12", "E1", [], POLICY)["modifiers"])
        self.assertIn("H", router.resolve_cell("T12", "E1", ["prod"], POLICY)["modifiers"])
        self.assertIn("G", router.resolve_cell("T12", "E3", [], POLICY)["modifiers"])

    def test_two_line_authorization_fix_requires_the_gate(self):
        t = task(files=["src/auth/session.ts"], title="Fix role check", signals={"estimated_changed_lines": 2, "mechanical": False},
                 opinions={"stage3": {"task_type": "T11", "effort": "E1"}}, limits={"task_ceiling_usd": 10})
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["status"], "planned")
        self.assertEqual(r["route"]["task_type"], "T11")
        self.assertTrue(r["gates"]["premium_contract"] and r["gates"]["premium_acceptance"] and r["gates"]["human_interrupt"])
        self.assertGreater(r["budget"]["gate_reserve_usd"], 0)


# ----------------------------------------------------------------------------- criterion 3

class TestNeverLower(unittest.TestCase):
    """No stage and no fixture can remove a flag or lower effort below a critical row's floor."""

    def test_opinions_cannot_remove_flags(self):
        t = task(files=["prisma/migrations/0042_add_index.sql"], title="add index",
                 opinions={"stage2": {"task_type": "T1", "effort": "E0", "flags": []},
                           "stage3": {"task_type": "T1", "effort": "E0", "flags": []}})
        r = router.plan(t, POLICY, today=TODAY, )
        self.assertEqual(r["route"]["task_type"], "T7", "path-derived critical type is locked")
        self.assertTrue({"critical", "destructive"} <= set(r["route"]["flags"]))
        self.assertIn("G", r["route"]["modifiers"])
        self.assertIn("H", r["route"]["modifiers"])

    def test_opinions_cannot_lower_effort_on_critical_rows(self):
        t = task(files=["src/auth/rbac.ts", "src/auth/policy.ts"], title="rework permission model",
                 signals={"changes_public_interface": True, "estimated_changed_lines": 300},
                 opinions={"stage2": {"task_type": "T11", "effort": "E0"}, "stage3": {"task_type": "T11", "effort": "E0"}})
        s1 = router.stage1_classify(t, POLICY)
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["route"]["task_type"], "T11")
        self.assertGreaterEqual(EFFORTS.index(r["route"]["effort"]), EFFORTS.index(s1["effort"]))

    def test_requester_hint_only_raises(self):
        lower = task(files=["src/lib/format.ts"], title="typo in comment", signals={"mechanical": True, "estimated_changed_lines": 1},
                     effort_hint="E3", opinions={"stage3": {"task_type": "T1", "effort": "E3"}})
        s1 = router.stage1_classify(lower, POLICY)
        self.assertEqual(s1["effort"], "E3")
        raise_hint_ignored = task(files=["src/auth/rbac.ts"], title="permission fix", signals={"estimated_changed_lines": 120, "changes_public_interface": True},
                                  effort_hint="E0")
        self.assertEqual(router.stage1_classify(raise_hint_ignored, POLICY)["effort"], "E2")

    def test_stage1_never_drops_environment_flag(self):
        t = task(files=["src/lib/x.ts"], title="small fix", env="production", opinions={"stage3": {"task_type": "T2", "effort": "E1"}})
        r = router.plan(t, POLICY, today=TODAY)
        self.assertIn("prod", r["route"]["flags"])
        self.assertIn("H", r["route"]["modifiers"])


# ----------------------------------------------------------------------------- criterion 4

class TestMonotonicCeilings(unittest.TestCase):
    """Ceilings, gate reserves, time ceilings and Hermes limits are non-decreasing in E."""

    def levels(self, key, upto=5, sub=None):
        vals = []
        for e in EFFORTS[:upto]:
            v = POLICY["effort_levels"][e][key]
            vals.append(v[sub] if sub else v)
        return vals

    def test_implementation_ceilings(self):
        c = self.levels("ceiling_usd")
        self.assertEqual(c, sorted(c))
        self.assertEqual(c, [0.5, 2.0, 8.0, 25.0, 75.0])

    def test_gate_reserves_E0_to_E3_and_E4_included(self):
        g = self.levels("gate_reserve_usd", upto=4)
        self.assertEqual(g, sorted(g))
        self.assertTrue(POLICY["effort_levels"]["E4"]["gate_included_in_ceiling"])
        for e in EFFORTS[:4]:
            self.assertGreaterEqual(router.gate_reserve_usd(e, POLICY), POLICY["effort_levels"][e]["gate_reserve_usd"])
        self.assertEqual(router.gate_reserve_usd("E4", POLICY), 0.0)

    def test_time_ceilings(self):
        t = self.levels("time_ceiling_min", upto=4)
        self.assertEqual(t, sorted(t))
        self.assertIsNone(POLICY["effort_levels"]["E4"]["time_ceiling_min"])
        self.assertEqual(POLICY["effort_levels"]["E4"]["plan_time_ceiling_min"], 60)

    def test_hermes_limits(self):
        it = self.levels("hermes", upto=4, sub="iterations")
        to = self.levels("hermes", upto=4, sub="child_timeout_seconds")
        self.assertEqual(it, sorted(it))
        self.assertEqual(to, sorted(to))
        for e in EFFORTS[:4]:
            self.assertEqual(POLICY["effort_levels"][e]["hermes"]["child_timeout_seconds"], POLICY["effort_levels"][e]["time_ceiling_min"] * 60)

    def test_computed_gate_reserve_at_standard_prices_is_under_a_dollar_for_small_items(self):
        grm = POLICY["gate_reserve_model"]
        ctx = grm["expected_context_tokens"]["E1"]
        pair = 2 * router.call_cost("gpt-6-astra", ctx["in"], ctx["out"], POLICY)
        self.assertAlmostEqual(pair, 0.55, places=2)
        self.assertLess(pair * grm["safety_factor"], 1.0)


# ----------------------------------------------------------------------------- criterion 5

class TestExpansion(unittest.TestCase):
    """Expanded graphs are acyclic, IDs unique per attempt, expansion idempotent."""

    def test_example_graph_is_acyclic_with_unique_ids(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        ids = [n["id"] for n in r["graph"]["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))
        router.topo_order(r["graph"])  # raises on a cycle

    def test_expansion_is_idempotent(self):
        a = router.plan(EXAMPLE, POLICY, today=TODAY)
        b = router.plan(EXAMPLE, POLICY, today=TODAY)
        self.assertEqual(json.dumps(a["graph"], sort_keys=True), json.dumps(b["graph"], sort_keys=True))
        self.assertEqual(a["dispatch_order"], b["dispatch_order"])

    def test_attempt_changes_every_id(self):
        a = router.plan(EXAMPLE, POLICY, today=TODAY, attempt=1)
        b = router.plan(EXAMPLE, POLICY, today=TODAY, attempt=2)
        self.assertTrue(set(n["id"] for n in a["graph"]["nodes"]).isdisjoint(n["id"] for n in b["graph"]["nodes"]))

    def test_planned_route_fans_out_and_joins(self):
        t = task(files=["src/api/reports.ts", "src/api/exports.ts", "src/jobs/nightly.ts", "src/ui/Reports.tsx",
                        "src/ui/Export.tsx", "src/lib/csv.ts", "src/lib/pdf.ts"],
                 title="new reporting module", signals={"new_design_needed": True},
                 items=[{"name": "api", "effort": "E2", "files": ["src/api/reports.ts", "src/api/exports.ts"]},
                        {"name": "ui", "effort": "E2", "files": ["src/ui/Reports.tsx", "src/ui/Export.tsx"]},
                        {"name": "csv", "effort": "E1", "files": ["src/lib/csv.ts"]}],
                 opinions={"stage3": {"task_type": "T5", "effort": "E4"}}, limits={"task_ceiling_usd": 200})
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["status"], "planned")
        self.assertEqual(r["route"]["family"], "R4")
        self.assertIn("G", r["route"]["modifiers"], "R4 forces the premium gate")
        nodes = {n["id"]: n for n in r["graph"]["nodes"]}
        ims = [n for n in nodes.values() if n["node"] == "IM"]
        self.assertEqual(len(ims), 3)
        self.assertEqual({n["effort"] for n in ims}, {"E2", "E1"})
        for im in ims:  # every item joins INT
            self.assertTrue(any(a == im["id"].replace("IM", "CK") and nodes[b]["node"] == "INT" for a, b in r["graph"]["edges"]))
        self.assertEqual(r["graph"]["items"], 3)

    def test_reviewer_is_a_different_family_from_implementer(self):
        for e in ("E1", "E2", "E3"):
            t = task(files=["src/api/x.ts"], title="endpoint work", opinions={"stage3": {"task_type": "T5", "effort": e}},
                     signals={"estimated_changed_lines": {"E1": 20, "E2": 120, "E3": 500}[e]}, limits={"task_ceiling_usd": 100})
            r = router.plan(t, POLICY, today=TODAY)
            self.assertEqual(r["route"]["effort"], e, r["route"])
            nodes = {n["id"]: n for n in r["graph"]["nodes"]}
            for n in nodes.values():
                if n["node"] == "RV":
                    self.assertNotEqual(n["family"], nodes[n["id"].replace("RV", "IM")]["family"], f"{e}: same-family review")

    def test_direct_route_has_no_model_review(self):
        t = task(files=["docs/README.md"], title="fix typo", signals={"mechanical": True, "estimated_changed_lines": 1})
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["route"]["cell"], "R0")
        self.assertEqual(r["route"]["effort"], "E0")
        self.assertFalse([n for n in r["graph"]["nodes"] if n["node"] in ("RV", "TD", "CON")])
        self.assertEqual([n for n in r["graph"]["nodes"] if n["node"] == "IM"][0]["tier"], "L")

    def test_evidence_only_route(self):
        t = task(title="Research: compare two queue libraries", description="should we use A or B",
                 opinions={"stage3": {"task_type": "T10", "effort": "E1"}})
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["route"]["cell"], "RE")
        kinds = [n["node"] for n in r["graph"]["nodes"]]
        self.assertEqual(kinds, ["ROUTE", "EVID", "RV", "DEL"])

    def test_no_repro_route_reproduces_first(self):
        t = task(files=["src/jobs/sync.ts"], title="sync job sometimes skips rows", signals={"estimated_changed_lines": 40},
                 opinions={"stage3": {"task_type": "T3", "effort": "E1"}})
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["route"]["cell"], "R1+P")
        self.assertEqual(r["dispatch_order"][1].split(":")[-1], "REPRO")


# ----------------------------------------------------------------------------- criterion 6

class TestFailureTransitions(unittest.TestCase):
    """Failure-class edges match spec §8."""

    def base(self, effort="E2", **kw):
        s = {"effort": effort, "origin_effort": effort, "attempt": 1, "f1_count": 0, "f3_count": 0,
             "replans_used": 0, "milestone_replans_used": 0}
        s.update(kw)
        return s

    def test_F1_retries_once_then_stops(self):
        first = router.next_after_failure(self.base(), "F1", POLICY)
        self.assertEqual((first["edge"], first["stop"], first["counts_candidate"]), ("ITEM", False, False))
        second = router.next_after_failure(first["state"], "F1", POLICY)
        self.assertEqual((second["edge"], second["stop"]), ("STOP", True))

    def test_F2_returns_to_contract_without_escalation(self):
        r = router.next_after_failure(self.base(), "F2", POLICY)
        self.assertEqual(r["edge"], "CON")
        self.assertFalse(r["counts_candidate"])
        self.assertEqual(r["state"]["effort"], "E2")
        r2 = router.next_after_failure(self.base(), "F2", POLICY, implementation_also_wrong=True)
        self.assertTrue(r2["counts_candidate"])

    def test_F3_escalates_then_replans_once_then_stops(self):
        s = self.base("E2")
        r1 = router.next_after_failure(s, "F3", POLICY)
        self.assertEqual((r1["edge"], r1["state"]["effort"], r1["counts_candidate"]), ("ITEM", "E3", True))
        r2 = router.next_after_failure(r1["state"], "F3", POLICY)
        self.assertEqual(r2["edge"], "PRE")
        self.assertEqual(r2["state"]["replans_used"], 1)
        r3 = router.next_after_failure(r2["state"], "F3", POLICY)
        self.assertTrue(r3["stop"])
        self.assertEqual(r3["edge"], "STOP")

    def test_F3_from_E3_retries_at_top_tier_before_replan(self):
        r1 = router.next_after_failure(self.base("E3"), "F3", POLICY)
        self.assertEqual((r1["edge"], r1["state"]["effort"]), ("ITEM", "E3"))
        r2 = router.next_after_failure(r1["state"], "F3", POLICY)
        self.assertEqual(r2["edge"], "PRE")

    def test_trivial_items_hit_the_two_attempt_hard_stop_without_a_replan(self):
        r1 = router.next_after_failure(self.base("E0"), "F3", POLICY)
        self.assertEqual((r1["edge"], r1["state"]["effort"]), ("ITEM", "E1"))
        r2 = router.next_after_failure(r1["state"], "F3", POLICY)
        self.assertTrue(r2["stop"], "hard stop of 2 attempts for an E0 item")
        self.assertEqual(r2["state"]["replans_used"], 0)

    def test_F4_repartitions_once_without_counting_a_candidate(self):
        r1 = router.next_after_failure(self.base(), "F4", POLICY)
        self.assertEqual((r1["edge"], r1["counts_candidate"], r1["stop"]), ("SPLIT", False, False))
        r2 = router.next_after_failure(r1["state"], "F4", POLICY)
        self.assertTrue(r2["stop"])

    def test_F5_stops_for_a_human(self):
        r = router.next_after_failure(self.base(), "F5", POLICY)
        self.assertEqual((r["edge"], r["stop"], r["counts_candidate"]), ("STOP", True, False))

    def test_transition_is_pure(self):
        s = self.base()
        snapshot = deepcopy(s)
        router.next_after_failure(s, "F3", POLICY)
        self.assertEqual(s, snapshot)


# ----------------------------------------------------------------------------- criterion 7

class TestDispatchOrder(unittest.TestCase):
    """Longest-remaining-path first."""

    def test_long_item_dispatches_before_short_items(self):
        t = task(files=["a.ts", "b.ts", "c.ts", "d.ts"], title="milestone", signals={"new_design_needed": True},
                 items=[{"name": "short-1", "effort": "E1"}, {"name": "short-2", "effort": "E1"},
                        {"name": "long", "effort": "E3"}, {"name": "short-3", "effort": "E1"}],
                 opinions={"stage3": {"task_type": "T5", "effort": "E4"}}, limits={"task_ceiling_usd": 500})
        r = router.plan(t, POLICY, today=TODAY)
        ims = [n for n in r["dispatch_order"] if ":IM[" in n]
        self.assertEqual(ims[0], f"{t['task_id']}:1:IM[2]", "the E3 item leads")
        # test design of the long item is dispatched before implementation of the short ones
        td_long = r["dispatch_order"].index(f"{t['task_id']}:1:TD[2]")
        im_short = r["dispatch_order"].index(f"{t['task_id']}:1:IM[0]")
        self.assertLess(td_long, im_short)

    def test_dispatch_order_respects_dependencies(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        pos = {n: i for i, n in enumerate(r["dispatch_order"])}
        for a, b in r["graph"]["edges"]:
            self.assertLess(pos[a], pos[b])

    def test_time_phases_add_up_along_the_critical_path(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        t = r["time"]
        self.assertEqual(t["planning_min"] + t["implementation_min"] + t["gate_min"], t["critical_path_min"])
        self.assertLessEqual(t["implementation_min"], t["time_ceiling_min"])


# ----------------------------------------------------------------------------- criterion 8

class TestV1Example(unittest.TestCase):
    """The v1 payment-webhook example routes to R2+EGH within $25."""

    def test_example_routes_as_specified(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        self.assertEqual(r["status"], "planned")
        self.assertEqual(r["route"]["task_type"], "T8")
        self.assertEqual(r["route"]["effort"], "E2")
        self.assertEqual(r["route"]["cell"], "R2+EGH")
        self.assertIn("payments", r["route"]["flags"])
        self.assertIn("external-writes", r["route"]["flags"])
        b = r["budget"]
        self.assertEqual(b["implementation_ceiling_usd"], 8.0)
        self.assertEqual(b["gate_reserve_usd"], 3.0)
        self.assertLessEqual(b["planned_total_usd"], 25.0)
        self.assertTrue(b["within_limit"] and b["predispatch_check_ok"])
        self.assertEqual(b["effective_limit_usd"], 25.0, "the user-supplied ceiling is not raised to the E4 value")

    def test_example_graph_matches_appendix_b(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        kinds = [n["node"] for n in r["graph"]["nodes"]]
        for k in ("EVID", "PCON", "TD", "IM", "RV", "INT", "VER", "PACC", "HUM", "DEL"):
            self.assertIn(k, kinds)
        nodes = {n["node"]: n for n in r["graph"]["nodes"]}
        self.assertEqual(nodes["EVID"]["model"], "gemini-3.8-flash")
        self.assertEqual(nodes["PCON"]["model"], "gpt-6-astra")
        self.assertEqual(nodes["PACC"]["model"], "gpt-6-astra")
        self.assertTrue(nodes["PACC"]["fresh_session"])
        self.assertEqual(nodes["IM"]["tier"], "M")
        self.assertNotEqual(nodes["RV"]["family"], nodes["IM"]["family"])
        self.assertIn("idempotency proven: same event twice -> one effect", r["recipe"])
        edges = {(a.split(":")[-1], b.split(":")[-1]) for a, b in r["graph"]["edges"]}
        self.assertIn(("PCON", "TD"), edges)
        self.assertIn(("PCON", "IM"), edges)
        self.assertIn(("PACC", "HUM"), edges)

    def test_committed_route_example_is_current(self):
        with open(os.path.join(HERE, "route.example.json"), encoding="utf-8") as fh:
            committed = json.load(fh)
        fresh = router.plan(EXAMPLE, POLICY, today=dt.date.fromisoformat(committed["planned_at"]))
        self.assertEqual(json.dumps(committed, sort_keys=True), json.dumps(fresh, sort_keys=True))


# ----------------------------------------------------------------------------- criterion 9

class TestRegistryFreshness(unittest.TestCase):
    """Every price has checked_at; stale entries refuse dispatch."""

    def test_grok_46_is_enabled_in_flash_and_mid_without_optional_duplicate(self):
        self.assertIs(POLICY["registry"]["grok-4.6"]["enabled"], True)
        for tier in ("F", "M"):
            with self.subTest(tier=tier):
                self.assertEqual(POLICY["tiers"][tier]["candidates"].count("grok-4.6"), 1)
                self.assertIn("grok-4.6", router._registry_candidates(tier, POLICY))
        self.assertNotIn("grok-4.6", POLICY["tiers"]["F"].get("optional_candidates", []))

    def test_grok_420_is_absent_from_worker_rosters_and_enabled_candidates(self):
        for tier, config in POLICY["tiers"].items():
            with self.subTest(tier=tier):
                self.assertNotIn("grok-4.20", config.get("candidates", []))
                self.assertNotIn("grok-4.20", config.get("optional_candidates", []))
                self.assertNotIn("grok-4.20", router._registry_candidates(tier, POLICY))

    def test_retained_grok_420_registry_entry_must_be_disabled(self):
        if "grok-4.20" in POLICY["registry"]:
            self.assertIs(POLICY["registry"]["grok-4.20"].get("enabled"), False)

    def test_every_price_has_checked_at_and_source(self):
        for m, entry in POLICY["registry"].items():
            if m.startswith("_"):
                continue
            self.assertIn("checked_at", entry["price"], m)
            dt.date.fromisoformat(entry["price"]["checked_at"])
            self.assertTrue(entry["price"].get("source"), m)
            self.assertIn("verified", entry["price"], m)

    def test_fresh_registry_plans_and_stale_registry_refuses(self):
        max_age = POLICY["scheduling"]["registry_max_age_days"]
        checked = dt.date.fromisoformat(POLICY["registry"]["gpt-6-astra"]["price"]["checked_at"])
        ok = router.plan(EXAMPLE, POLICY, today=checked + dt.timedelta(days=max_age))
        self.assertEqual(ok["status"], "planned")
        stale = router.plan(EXAMPLE, POLICY, today=checked + dt.timedelta(days=max_age + 1))
        self.assertEqual(stale["status"], "refused_stale_registry")
        self.assertTrue(stale["stale"])

    def test_disabled_models_are_never_assigned(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        for n in r["graph"]["nodes"]:
            if n["model"]:
                self.assertTrue(POLICY["registry"][n["model"]].get("enabled", True), n["model"])

    def test_premium_alternate_is_cross_family_and_never_silent(self):
        p = POLICY["tiers"]["P"]
        alt = p.get("alternate")
        self.assertTrue(alt, "a premium alternate must be declared")
        self.assertNotEqual(POLICY["registry"][alt]["family"], POLICY["registry"][p["roles"]["judge"]]["family"])
        self.assertEqual(POLICY["registry"][alt]["tier"], "P")
        self.assertTrue(p["log_substitution"])
        self.assertFalse(p["silent_substitution"])

    def test_v1_openai_prices_are_corrected(self):
        for m, v1 in (("gpt-5.6-terra", (2.0, 12.0)), ("gpt-5.6-sol", (4.0, 20.0)), ("gpt-6-astra", (10.0, 50.0))):
            price = {**POLICY["registry"], **POLICY.get("historical_registry", {})}[m]["price"]
            self.assertAlmostEqual(price["input"] * 2, v1[0])
            self.assertAlmostEqual(price["output"] * 2, v1[1])
            self.assertTrue(price["verified"])


# ----------------------------------------------------------------------------- criterion 10

class TestNoSecrets(unittest.TestCase):
    """No file in the package contains a key, token, or unsourced price."""

    PATTERNS = [
        r"sk-[A-Za-z0-9_-]{20,}", r"sk-ant-[A-Za-z0-9_-]{20,}", r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{20,}",
        r"xox[abpr]-[A-Za-z0-9-]{10,}", r"AIza[0-9A-Za-z_-]{30,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"]",
    ]

    def test_no_secret_like_strings(self):
        for name in os.listdir(HERE):
            if not name.endswith((".json", ".py", ".md", ".mmd")):
                continue
            with open(os.path.join(HERE, name), encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
            for pat in self.PATTERNS:
                self.assertIsNone(re.search(pat, text), f"{name} matches {pat}")

    def test_key_refs_are_references_not_values(self):
        for m, entry in POLICY["registry"].items():
            if m.startswith("_"):
                continue
            ref = entry.get("key_ref")
            if ref is None:
                continue
            self.assertRegex(ref, r"^(env|keychain):[A-Z0-9_a-z-]+$", m)


# ----------------------------------------------------------------------------- criterion 11

class TestMermaidFilesMatchSpec(unittest.TestCase):
    """workflow.top.mmd and workflow.item.mmd are the §6 diagrams from SPEC.md, byte for byte."""

    def blocks(self):
        with open(os.path.join(HERE, "SPEC.md"), encoding="utf-8") as fh:
            spec = fh.read()
        return re.findall(r"```mermaid\n(.*?)```", spec, re.S)

    def test_files_match_spec_blocks(self):
        blocks = self.blocks()
        self.assertGreaterEqual(len(blocks), 2)
        for fname, block in (("workflow.top.mmd", blocks[0]), ("workflow.item.mmd", blocks[1])):
            with open(os.path.join(HERE, fname), encoding="utf-8") as fh:
                self.assertEqual(fh.read().strip(), block.strip(), fname)

    def test_diagram_nodes_cover_the_router_catalog(self):
        with open(os.path.join(HERE, "workflow.top.mmd"), encoding="utf-8") as fh:
            top = fh.read()
        for node_id in ("ROUTE", "EVID", "REPRO", "PCON", "CON", "SPLIT", "ITEM", "INT", "VER", "FC", "PRE", "PACC", "HUM", "DEL", "STOP"):
            self.assertIn(node_id, top, node_id)


# ----------------------------------------------------------------------------- criterion 12

class TestOffline(unittest.TestCase):
    """The package creates no API calls, provider accounts or live Hermes tasks."""

    def test_router_imports_no_network_or_subprocess_modules(self):
        with open(os.path.join(HERE, "router.py"), encoding="utf-8") as fh:
            src = fh.read()
        for mod in ("requests", "urllib", "http.client", "socket", "subprocess", "httpx", "aiohttp", "openai", "anthropic"):
            self.assertNotRegex(src, rf"^\s*(import|from)\s+{re.escape(mod)}\b", mod)

    def test_cards_are_shapes_not_executions(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        for card in r["hermes_cards"]:
            self.assertEqual(card["idempotency_key"], card["node_id"])
            if card["assignee"] != "human":
                self.assertIn("--idempotency-key", card["cli"])
                self.assertIn("--json", card["cli"])
                self.assertIn("--model", card["cli"])
                self.assertIn("--provider", card["cli"])
                self.assertIsNotNone(card["child_timeout_seconds"])
        self.assertIn("No API calls", r["disclaimer"])

    def test_over_limit_is_reported_not_worked_around(self):
        t = deepcopy(EXAMPLE)
        t["limits"]["task_ceiling_usd"] = 5
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["status"], "over_limit")
        self.assertTrue(r["gates"]["premium_contract"], "the gate is never dropped to make the bill fit")
        self.assertFalse(r["budget"]["within_limit"])


# ----------------------------------------------------------------------------- criterion 13 (extended): availability modes

class TestRigorModes(unittest.TestCase):
    """v2.2 (spec §0): easy/medium/hard/expert are RIGOR levels, not model rosters.
    Model selection is fully decoupled from the mode (always the tier registry); a
    user-selected mode is a floor, not a ceiling; safety flags always win over mode
    and a mode never removes a mandatory gate, recipe or verification requirement."""

    MODES = ("easy", "medium", "hard", "expert")

    def _plan(self, mode, task=None, attempt=1):
        return router.plan(task or EXAMPLE, POLICY, today=TODAY, mode=mode, attempt=attempt)

    def _nodes_models(self, r):
        return [(n["node"], n["tier"], n["model"]) for n in r["graph"]["nodes"] if n.get("model")]

    def test_all_four_rigor_modes_are_declared_with_ranks(self):
        modes = POLICY["modes"]
        self.assertEqual({m: modes[m]["rank"] for m in self.MODES},
                         {"easy": 0, "medium": 1, "hard": 2, "expert": 3})
        for m in self.MODES:
            for field in ("use_when", "override_behavior", "minimum_proof"):
                self.assertTrue(modes[m][field], f"{m} missing {field}")
        self.assertNotIn("pools", modes["easy"], "pool definitions must be gone in v2.2")

    def test_example_plans_cleanly_in_every_mode(self):
        for mode in self.MODES:
            r = self._plan(mode)
            self.assertEqual(r["status"], "planned", f"{mode}: {r.get('violations') or r}")
            self.assertEqual(r["mode"]["selected"], mode)
            self.assertIn(r["mode"]["effective"], self.MODES)
            self.assertGreaterEqual(r["mode"]["rank"], router.MODE_RANK[mode],
                                    f"{mode}: effective mode must never be LOWER than selected")

    def test_model_selection_is_decoupled_from_mode(self):
        # No raise triggers on the example (T8, E2, reproduction flag irrelevant to T8):
        # every mode must plan the exact same models.
        models_by_mode = {}
        for mode in self.MODES:
            r = self._plan(mode)
            models_by_mode[mode] = self._nodes_models(r)
        self.assertEqual(models_by_mode["easy"], models_by_mode["medium"])
        self.assertEqual(models_by_mode["medium"], models_by_mode["hard"])
        self.assertEqual(models_by_mode["hard"], models_by_mode["expert"])

    def test_every_model_dispatches_on_its_own_provider(self):
        for mode in self.MODES:
            r = self._plan(mode)
            ctx = router.PlanContext(POLICY, r["mode"]["effective"], {}, [])
            for n in r["graph"]["nodes"]:
                if not n.get("model"):
                    continue
                target = router.dispatch_target(ctx, n["model"])
                self.assertIsNotNone(target, f"{mode} {n['node']} {n['model']}")
                self.assertEqual(target[0], POLICY["registry"][n["model"]]["provider"])

    def test_default_mode_is_easy(self):
        r = router.plan(EXAMPLE, POLICY, today=TODAY)
        self.assertEqual(r["mode"]["selected"], POLICY["modes"]["default"] == "easy" and "easy")

    def test_task_level_mode_field_is_honored(self):
        t = deepcopy(EXAMPLE)
        t["mode"] = "medium"
        r = router.plan(t, POLICY, today=TODAY)
        self.assertEqual(r["mode"]["selected"], "medium")

    def test_mode_is_floor_not_ceiling_critical_t8(self):
        # Critical integration work under easy: effective must be expert (rule 4),
        # never lowered to easy.
        t = task("t-floor", files=["src/integrations/payouts/sync.py"], title="payments sync job",
                 description="cron job syncing payouts to Sage Intacct",
                 signals={"estimated_changed_lines": 80}, flags=("critical",), env="production")
        r = self._plan("easy", t)
        self.assertEqual(r["mode"]["selected"], "easy")
        self.assertEqual(r["mode"]["effective"], "expert")
        self.assertTrue(r["mode"]["raise_reason"])
        self.assertTrue(r["gates"]["premium_contract"])
        self.assertTrue(r["gates"]["premium_acceptance"])
        self.assertTrue(r["gates"]["human_interrupt"])
        nodes = {n["node"] for n in r["graph"]["nodes"]}
        self.assertIn("PCON", nodes)
        self.assertIn("PACC", nodes)
        self.assertIn("HUM", nodes)

    def test_mode_never_removes_a_mandatory_gate_or_recipe(self):
        gates_by_mode = {}
        for mode in self.MODES:
            r = self._plan(mode)
            gates_by_mode[mode] = (r["gates"], r["recipe"],
                                   sorted(n["node"] for n in r["graph"]["nodes"]))
        self.assertEqual(gates_by_mode["easy"], gates_by_mode["medium"])
        self.assertEqual(gates_by_mode["medium"], gates_by_mode["hard"])
        self.assertEqual(gates_by_mode["hard"], gates_by_mode["expert"])

    def test_hard_mode_raises_effort_on_missing_reproduction(self):
        t = task("t-norepro", files=["src/api/handler.py"], title="fix intermittent failure",
                 description="intermittent webhook drop, no repro",
                 signals={"has_reproduction": False})
        r = self._plan("hard", t)
        self.assertEqual(r["status"], "planned")
        self.assertEqual(len(r["mode"]["effort_raises"]), 1)
        self.assertEqual(r["mode"]["effort_raises"][0]["from"], "E1")
        self.assertEqual(r["mode"]["effort_raises"][0]["to"], "E2")
        self.assertEqual(r["route"]["effort"], "E2")

    def test_expert_mode_policy_task_carries_premium_gates(self):
        # T14 (router/policy work) at E3 -> R3+GV: premium contract + acceptance +
        # eval replay, effective expert, even though the user asked for easy.
        t = task("t-t14", files=["src/routing/router.py"], title="update routing policy",
                 description="change the routing policy matrix",
                 signals={"cross_module": True})
        r = self._plan("easy", t)
        self.assertEqual(r["mode"]["effective"], "expert")
        self.assertTrue(r["gates"]["premium_contract"])
        self.assertTrue(r["gates"]["premium_acceptance"])
        self.assertTrue(r["gates"]["eval_replay"])
        nodes = {n["node"] for n in r["graph"]["nodes"]}
        self.assertIn("PCON", nodes)
        self.assertIn("PACC", nodes)

    def test_dispatch_refused_on_malformed_registry_entry(self):
        pol = deepcopy(POLICY)
        pol["registry"]["broken-model"] = {
            "name": "Broken", "family": "broken", "provider": "openrouter",
            "price": {"input": 1.0, "output": 2.0, "checked_at": TODAY.isoformat()},
            "hermes": {"model": ""}, "enabled": True}
        pol["tiers"]["F"]["roles"]["implementer"] = "broken-model"
        t = task("t-broken", files=[], title="fix bug: wrong total on the report page",
                 description="the report total is wrong", signals={"estimated_changed_lines": 30})
        r = router.plan(t, pol, today=TODAY, mode="easy")
        self.assertEqual(r["status"], "dispatch_refused")
        self.assertTrue(any("broken-model" in v for v in r["violations"]))

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(router.PolicyError):
            router.plan(EXAMPLE, POLICY, today=TODAY, mode="quantum")


if __name__ == "__main__":
    unittest.main(verbosity=2)
