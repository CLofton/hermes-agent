#!/usr/bin/env python3
import importlib.util
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).with_name("recursive_swarm.py")
spec = importlib.util.spec_from_file_location("recursive_swarm", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

TODAY = dt.date(2026, 9, 8)


def valid_plan():
    return {
        "version": 1,
        "app": {
            "id": "sample-app",
            "title": "Sample App",
            "acceptance": ["All workflows pass"],
            "sensitivity": "internal",
            "repo": "/tmp/sample-app",
        },
        "features": [
            {
                "id": "accounts",
                "title": "Accounts",
                "acceptance": ["Users can sign in"],
                "units": [
                    {"id": "validate", "title": "Validate input", "acceptance": ["Invalid input is rejected"]},
                    {"id": "session", "title": "Create session", "acceptance": ["Valid input creates a session"]},
                ],
            },
            {
                "id": "profile",
                "title": "Profile",
                "acceptance": ["Profile renders"],
                "units": [
                    {"id": "read", "title": "Read profile", "acceptance": ["Authorized user sees profile"]},
                ],
            },
        ],
        "limits": {"max_tasks": 100},
    }


def valid_route_task(**overrides):
    task = {
        "task_id": "swarm-v3",
        "title": "Upgrade the recursive swarm skill",
        "description": "Add v3 routing policy and gates.",
        "task_type": "T14",
        "effort": "E2",
        "attempt": 1,
        "sensitivity": "internal",
        "files": ["skills/recursive-engineering-swarm/scripts/recursive_swarm.py"],
        "flags": ["high"],
        "modifiers": ["V"],
        "limits": {
            "max_tasks": 100,
            "max_runtime_minutes": 120,
            "max_retries": 3,
            "usd_ceiling": 8.0,
        },
    }
    for key, value in overrides.items():
        if value is None:
            task.pop(key, None)
        else:
            task[key] = value
    return task


def valid_route(**overrides):
    return module.route_task(valid_route_task(**overrides), today=TODAY)


def valid_v3_plan(route=None):
    route = route or valid_route()
    plan = valid_plan()
    plan["version"] = 3
    plan["policy_version"] = module.DEFAULT_POLICY_VERSION
    plan["task"] = {
        "task_id": route["task_id"],
        "attempt": route["attempt"],
        "task_hash": route["task_hash"],
    }
    plan["route"] = route
    plan["limits"] = {
        "max_tasks": 100,
        "max_runtime_minutes": route["limits"]["max_runtime_minutes"],
        "max_retries": route["limits"]["max_retries"],
        "usd_ceiling": route["limits"]["usd_ceiling"],
    }
    return plan


def complete_metadata_for_graph(graph):
    metadata = {}
    route = graph.get("route") or {}
    for node in graph["nodes"]:
        node_id = node["id"]
        kind = node_id.rsplit(".", 1)[-1]
        if node_id == "app.anchor":
            metadata[node_id] = {"verdict": "PASS", "plan_hash": graph["plan_hash"]}
        elif node_id == "app.astra-contract":
            metadata[node_id] = {
                "verdict": "PASS",
                "gate": "astra_contract",
                "plan_hash": graph["plan_hash"],
                "policy_version": graph["policy_version"],
                "route_cell": route["cell"],
                "findings": [],
            }
        elif node_id == "app.astra-acceptance":
            metadata[node_id] = {
                "verdict": "PASS",
                "gate": "astra_final_acceptance",
                "plan_hash": graph["plan_hash"],
                "policy_version": graph["policy_version"],
                "route_cell": route["cell"],
                "findings": [],
            }
        elif node_id == "app.manual-approval":
            metadata[node_id] = {
                "verdict": "PASS",
                "gate": "manual_approval",
                "plan_hash": graph["plan_hash"],
                "plan_revision": route["plan_revision"],
                "action": route["manual_action"],
                "approved_by": "the operator",
                "approved_at": "2026-09-08T12:00:00Z",
            }
        elif kind == "tests":
            metadata[node_id] = {
                "verdict": "PASS",
                "test_files": ["tests/test_x.py"],
                "test_sha256": {"tests/test_x.py": "a" * 64},
                "test_command": "pytest",
                "red_exit_code": 1,
            }
        elif kind in {"build", "integration"}:
            metadata[node_id] = {
                "verdict": "PASS",
                "targeted_exit_code": 0,
                "regression_exit_code": 0,
            }
        else:
            metadata[node_id] = {"verdict": "PASS", "findings": []}
    return metadata


class RecursiveSwarmTests(unittest.TestCase):
    def test_validation_fails_closed(self):
        plan = valid_plan()
        plan["app"]["sensitivity"] = "restricted"
        with self.assertRaisesRegex(ValueError, "OpenRouter"):
            module.validate_plan(plan)
        plan = valid_plan()
        plan["features"][0]["units"] = []
        with self.assertRaisesRegex(ValueError, "unit"):
            module.validate_plan(plan)

    def test_validation_rejects_duplicate_or_unsafe_ids_and_blank_acceptance(self):
        plan = valid_plan()
        plan["features"][1]["id"] = "accounts"
        with self.assertRaisesRegex(ValueError, "duplicate feature"):
            module.validate_plan(plan)
        plan = valid_plan()
        plan["features"][0]["units"][1]["id"] = "validate"
        with self.assertRaisesRegex(ValueError, "duplicate unit"):
            module.validate_plan(plan)
        plan = valid_plan()
        plan["features"][0]["id"] = "unsafe id"
        with self.assertRaisesRegex(ValueError, "safe slug"):
            module.validate_plan(plan)
        plan = valid_plan()
        plan["app"]["acceptance"] = [""]
        with self.assertRaisesRegex(ValueError, "blank"):
            module.validate_plan(plan)
        plan = valid_plan()
        del plan["limits"]
        with self.assertRaisesRegex(ValueError, "max_tasks is required"):
            module.validate_plan(plan)
        plan = valid_plan()
        del plan["version"]
        with self.assertRaisesRegex(ValueError, "version must equal 1"):
            module.validate_plan(plan)
        plan = valid_plan()
        plan["version"] = 999
        with self.assertRaisesRegex(ValueError, "version must equal 1"):
            module.validate_plan(plan)
        for invalid_version in (True, 1.0):
            plan = valid_plan()
            plan["version"] = invalid_version
            with self.assertRaisesRegex(ValueError, "version must equal 1"):
                module.validate_plan(plan)

    def test_graph_has_atomic_feature_and_app_gates(self):
        graph = module.build_graph(valid_plan())
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertIn("unit.accounts.validate.spec", nodes)
        self.assertIn("feature.accounts.review", nodes)
        self.assertIn("app.judge", nodes)
        self.assertEqual(nodes["unit.accounts.validate.tests"]["assignee"], "deepseek")
        self.assertEqual(nodes["unit.accounts.validate.build"]["assignee"], "glmvalue")
        self.assertEqual(nodes["app.judge"]["assignee"], "default")
        self.assertIn("unit.accounts.validate.review", nodes["feature.accounts.tests"]["parents"])
        self.assertIn("unit.profile.read.review", nodes["feature.accounts.tests"]["parents"])
        self.assertIn("feature.accounts.review", nodes["app.tests"]["parents"])

        order = [node["id"] for node in graph["nodes"]]
        last_atomic_build = max(i for i, node_id in enumerate(order) if node_id.startswith("unit.") and node_id.endswith(".build"))
        first_feature_test = min(i for i, node_id in enumerate(order) if node_id.startswith("feature.") and node_id.endswith(".tests"))
        self.assertLess(last_atomic_build, first_feature_test)

    def test_all_repository_writers_are_totally_ordered(self):
        graph = module.build_graph(valid_plan())
        nodes = {node["id"]: node for node in graph["nodes"]}
        writers = [node for node in graph["nodes"] if node["writer"]]

        def ancestors(node_id):
            seen = set()
            stack = list(nodes[node_id]["parents"])
            while stack:
                current = stack.pop()
                if current in seen:
                    continue
                seen.add(current)
                stack.extend(nodes[current]["parents"])
            return seen

        for index, left in enumerate(writers):
            for right in writers[index + 1:]:
                self.assertTrue(
                    left["id"] in ancestors(right["id"]) or right["id"] in ancestors(left["id"]),
                    f"writers are unordered: {left['id']} and {right['id']}",
                )

    def test_graph_is_deterministic(self):
        first = module.build_graph(valid_plan())
        second = module.build_graph(json.loads(json.dumps(valid_plan())))
        self.assertEqual(first, second)
        self.assertEqual(first["plan_hash"], second["plan_hash"])
        self.assertTrue(all(node["idempotency_key"] for node in first["nodes"]))

    def test_task_budget_fails_before_graph_creation(self):
        plan = valid_plan()
        plan["limits"] = {"max_tasks": 4}
        with self.assertRaisesRegex(ValueError, "task budget"):
            module.build_graph(plan)

    def test_task_budget_counts_anchor_as_an_app_node(self):
        plan = valid_plan()
        plan["features"] = [plan["features"][0]]
        plan["features"][0]["units"] = [plan["features"][0]["units"][0]]
        plan["limits"] = {"max_tasks": 11}
        with self.assertRaisesRegex(ValueError, "requires 12 tasks"):
            module.build_graph(plan)

    def test_dry_run_does_not_call_runner(self):
        runner = Mock(side_effect=AssertionError("runner should not execute"))
        result = module.apply_graph(module.build_graph(valid_plan()), "sample-board", runner=runner, apply=False)
        self.assertEqual(result["mode"], "dry-run")
        runner.assert_not_called()

    def test_apply_maps_parent_node_ids_to_real_task_ids_and_is_idempotent(self):
        calls = []
        ids = {}

        def runner(args):
            calls.append(args)
            if "boards" in args and "list" in args:
                return [{"slug": "sample-board"}]
            if "create" in args:
                key = args[args.index("--idempotency-key") + 1]
                task_id = ids.setdefault(key, f"t_{len(ids) + 1}")
                return {"id": task_id, "status": "blocked" if "app.anchor" in args else "todo"}
            if "complete" in args or "dispatch" in args:
                return {"ok": True}
            raise AssertionError(args)

        graph = module.build_graph(valid_plan())
        first = module.apply_graph(graph, "sample-board", runner=runner, apply=True)
        second = module.apply_graph(graph, "sample-board", runner=runner, apply=True)
        self.assertEqual(first["task_ids"], second["task_ids"])
        create_calls = [call for call in calls if "create" in call]
        child_call = next(call for call in create_calls if "unit.accounts.validate.tests" in call)
        self.assertIn("--parent", child_call)
        parent_values = [child_call[i + 1] for i, item in enumerate(child_call) if item == "--parent"]
        self.assertTrue(all(value.startswith("t_") for value in parent_values))

    def test_apply_uses_real_hermes_kanban_cli_shape(self):
        calls = []

        def runner(args):
            calls.append(args)
            if args == ["kanban", "boards", "list", "--json"]:
                return [{"slug": "sample-board"}]
            if "create" in args:
                return {"id": f"t_{len(calls)}", "status": "blocked" if "--initial-status" in args else "todo"}
            if "complete" in args or "dispatch" in args:
                return {"ok": True}
            raise AssertionError(args)

        result = module.apply_graph(module.build_graph(valid_plan()), "sample-board", runner=runner, apply=True, dispatch=True)
        self.assertTrue(result["task_ids"])
        create_call = next(call for call in calls if "unit.accounts.validate.tests" in " ".join(call))
        self.assertEqual(create_call[:4], ["kanban", "--board", "sample-board", "create"])
        self.assertIn("--body", create_call)
        self.assertIn("--json", create_call)
        self.assertIn("--goal", create_call)
        self.assertEqual(create_call[create_call.index("--goal-max-turns") + 1], "4")
        self.assertNotIn("cards", create_call)
        self.assertNotIn("--node-id", create_call)
        self.assertNotIn("--metadata", create_call)
        self.assertIn("dir:/tmp/sample-app", create_call)
        self.assertIn(["kanban", "--board", "sample-board", "dispatch", "--max", "4", "--json"], calls)
        complete_index = next(i for i, call in enumerate(calls) if "complete" in call)
        create_indices = [i for i, call in enumerate(calls) if "create" in call and "boards" not in call]
        self.assertGreater(complete_index, max(create_indices))

    def test_repository_path_with_spaces_is_preserved(self):
        plan = valid_plan()
        plan["app"]["repo"] = "/tmp/repo with spaces"
        graph = module.build_graph(plan)
        node = next(n for n in graph["nodes"] if n["id"] == "unit.accounts.validate.tests")
        parent_ids = {parent: f"t_{index}" for index, parent in enumerate(node["parents"])}
        args = module._create_args(node, "board", parent_ids, graph["plan_hash"])
        self.assertIn("dir:/tmp/repo with spaces", args)

    def test_root_is_completed_once_and_existing_done_root_is_not_recompleted(self):
        completes = []

        def runner(args):
            if args == ["kanban", "boards", "list", "--json"]:
                return [{"slug": "sample-board"}]
            if "create" in args:
                node_text = " ".join(args)
                if "app.anchor" in node_text:
                    return {"id": "t_root", "status": "done"}
                return {"id": "t_" + str(abs(hash(node_text))), "status": "todo"}
            if "complete" in args:
                completes.append(args)
                return {"ok": True}
            return {"ok": True}

        module.apply_graph(module.build_graph(valid_plan()), "sample-board", runner=runner, apply=True)
        self.assertEqual(completes, [])

    def test_cli_parser_matches_documented_flags(self):
        parser = module.build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            plan_path.write_text(json.dumps(valid_plan()))
            args = parser.parse_args(["plan", "--plan-file", str(plan_path)])
            self.assertEqual(args.plan_file, plan_path)
            args = parser.parse_args([
                "draft", "--app-id", "x", "--goal", "goal", "--repo", "/tmp/x",
                "--output", str(Path(tmp) / "out.json"),
            ])
            self.assertEqual(args.app_id, "x")
            manifest = Path(tmp) / "run.swarm.json"
            args = parser.parse_args(["certify", "--manifest", str(manifest)])
            self.assertEqual(args.manifest, manifest)

    def test_conductor_command_uses_default_profile_chat_surface(self):
        command = module.conductor_command("PROMPT")
        self.assertEqual(command, ["hermes", "--profile", "default", "chat", "-q", "PROMPT", "--quiet"])

    def test_certification_fails_missing_evidence_and_passes_complete_evidence(self):
        graph = module.build_graph(valid_plan())
        task_ids = {node["id"]: f"t_{index}" for index, node in enumerate(graph["nodes"])}
        manifest = {"version": 1, "board": "sample", "plan": valid_plan(), "graph": graph, "task_ids": task_ids}
        metadata = {}
        for node in graph["nodes"]:
            kind = node["id"].rsplit(".", 1)[-1]
            if kind == "anchor":
                metadata[node["id"]] = {"verdict": "PASS", "plan_hash": graph["plan_hash"]}
            elif kind == "tests":
                metadata[node["id"]] = {
                    "verdict": "PASS", "test_files": ["tests/test_x.py"],
                    "test_sha256": {"tests/test_x.py": "a" * 64}, "test_command": "pytest",
                    "red_exit_code": 1,
                }
            elif kind in {"build", "integration"}:
                metadata[node["id"]] = {
                    "verdict": "PASS", "targeted_exit_code": 0, "regression_exit_code": 0,
                }
            else:
                metadata[node["id"]] = {"verdict": "PASS", "findings": []}

        def runner(args):
            if "list" in args:
                return [
                    {"id": task_ids[node["id"]], "title": node["id"],
                     "body": module._task_body(node, graph["plan_hash"])}
                    for node in graph["nodes"]
                ]
            task_id = args[-2]
            node_id = next(node for node, tid in task_ids.items() if tid == task_id)
            node = next(item for item in graph["nodes"] if item["id"] == node_id)
            return {
                "task": {"id": task_id, "title": node_id, "status": "done",
                         "body": module._task_body(node, graph["plan_hash"])},
                "runs": [{"metadata": metadata[node_id]}],
            }

        metadata["unit.accounts.validate.tests"].pop("red_exit_code")
        failed = module.certify_manifest(manifest, runner=runner)
        self.assertEqual(failed["verdict"], "FAIL")
        self.assertTrue(any("red_exit_code" in item for item in failed["failures"]))
        metadata["unit.accounts.validate.tests"]["red_exit_code"] = 1
        passed = module.certify_manifest(manifest, runner=runner)
        self.assertEqual(passed["verdict"], "PASS")
        self.assertEqual(passed["checked"], len(graph["nodes"]))

        bad_cases = [
            ("test_files", "anything"),
            ("test_sha256", True),
            ("test_command", 123),
            ("red_exit_code", True),
        ]
        for field, value in bad_cases:
            original = metadata["unit.accounts.validate.tests"][field]
            metadata["unit.accounts.validate.tests"][field] = value
            self.assertEqual(module.certify_manifest(manifest, runner=runner)["verdict"], "FAIL")
            metadata["unit.accounts.validate.tests"][field] = original
        metadata["unit.accounts.validate.build"]["targeted_exit_code"] = False
        self.assertEqual(module.certify_manifest(manifest, runner=runner)["verdict"], "FAIL")
        metadata["unit.accounts.validate.build"]["targeted_exit_code"] = 0

    def test_certification_rejects_truncated_or_tampered_manifest(self):
        plan = valid_plan()
        graph = module.build_graph(plan)
        manifest = {"version": 1, "board": "sample", "plan": plan, "graph": graph, "task_ids": {}}
        result = module.certify_manifest(manifest, runner=Mock())
        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(result["failures"])

        manifest = {
            "version": 1, "board": "sample", "plan": plan,
            "graph": {"version": 1, "plan_hash": graph["plan_hash"], "nodes": graph["nodes"][:1]},
            "task_ids": {"app.anchor": "t_root"},
        }
        result = module.certify_manifest(manifest, runner=Mock())
        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(any("graph" in item for item in result["failures"]))

        # Full live task bodies are cryptographically bound to the expected
        # acceptance/gate instructions, not just marker substrings.
        task_ids = {node["id"]: f"t_{index}" for index, node in enumerate(graph["nodes"])}
        manifest = {"version": 1, "board": "sample", "plan": plan, "graph": graph, "task_ids": task_ids}

        def tampered_runner(args):
            if "list" in args:
                return [
                    {"id": task_ids[node["id"]], "title": node["id"],
                     "body": f"plan_hash: {graph['plan_hash']}\nnode_id: {node['id']}"}
                    for node in graph["nodes"]
                ]
            task_id = args[-2]
            node_id = next(node for node, tid in task_ids.items() if tid == task_id)
            return {"task": {"id": task_id, "title": node_id, "status": "done", "body": "tampered"}, "runs": []}

        result = module.certify_manifest(manifest, runner=tampered_runner)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(any("body" in item for item in result["failures"]))

        for invalid_version in (True, 1.0):
            bad = dict(manifest)
            bad["version"] = invalid_version
            result = module.certify_manifest(bad, runner=Mock())
            self.assertEqual(result["verdict"], "FAIL")

    def test_certification_rechecks_exact_body_from_show_to_close_toctou(self):
        plan = valid_plan()
        graph = module.build_graph(plan)
        task_ids = {node["id"]: f"t_{index}" for index, node in enumerate(graph["nodes"])}
        manifest = {"version": 1, "board": "sample", "plan": plan, "graph": graph, "task_ids": task_ids}

        def runner(args):
            if "list" in args:
                return [
                    {"id": task_ids[node["id"]], "title": node["id"],
                     "body": module._task_body(node, graph["plan_hash"])}
                    for node in graph["nodes"]
                ]
            task_id = args[-2]
            node_id = next(node for node, tid in task_ids.items() if tid == task_id)
            return {
                "task": {"id": task_id, "title": node_id, "status": "done",
                         "body": f"plan_hash: {graph['plan_hash']}\nnode_id: {node_id}"},
                "runs": [{"metadata": {"verdict": "PASS"}}],
            }

        result = module.certify_manifest(manifest, runner=runner)
        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(any("body" in item for item in result["failures"]))

    def test_launch_does_not_run_a_premature_second_conductor_judge(self):
        args = Namespace(
            app_id="sample-app", goal="goal", repo="/tmp/sample-app",
            sensitivity="internal", output=Path("/tmp/unused-plan.json"), board="sample-board",
        )
        with patch.object(module, "_draft_plan", return_value=valid_plan()), \
             patch.object(module, "_write_plan"), \
             patch.object(module, "apply_graph", return_value={"mode": "apply", "task_ids": {"app.judge": "t_judge"}}), \
             patch.object(module, "_conductor_call") as conductor, redirect_stdout(StringIO()):
            module.cmd_launch(args)
        conductor.assert_not_called()

    def test_real_kanban_apply_is_idempotent_in_isolated_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            plan = valid_plan()
            plan["app"]["repo"] = str(repo)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan))
            env = dict(os.environ, HERMES_HOME=str(root / "hermes-home"))
            env.pop("HERMES_DELEGATED_CHILD_CONTEXT", None)
            command = [
                sys.executable, str(SCRIPT), "apply", "--plan-file", str(plan_path),
                "--board", "recursive-smoke", "--apply",
            ]
            first = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(first.returncode, 0, first.stderr)
            second = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
            self.assertEqual(second.returncode, 0, second.stderr)
            listed = subprocess.run(
                ["hermes", "kanban", "--board", "recursive-smoke", "list", "--json"],
                env=env, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(listed.returncode, 0, listed.stderr)
            tasks = json.loads(listed.stdout)
            self.assertEqual(len(tasks), 23)
            self.assertEqual(sum(task["status"] == "done" for task in tasks), 1)
            self.assertEqual(sum(task["status"] == "ready" for task in tasks), 3)
            manifest_path = plan_path.with_suffix(".swarm.json")
            self.assertTrue(manifest_path.exists())
            certified = subprocess.run(
                [sys.executable, str(SCRIPT), "certify", "--manifest", str(manifest_path)],
                env=env, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(certified.returncode, 1, certified.stderr)
            self.assertTrue(certified.stdout, certified.stderr)
            self.assertEqual(json.loads(certified.stdout)["verdict"], "FAIL")

    def test_conductor_json_parser_tolerates_session_footer(self):
        raw = 'session header\n```json\n{"version":1,"app":{"id":"x"},"features":[]}\n```\nsession_id: abc'
        self.assertEqual(module.extract_json_object(raw)["version"], 1)

    def test_route_rejects_injection_and_emits_argv_arrays(self):
        with self.assertRaisesRegex(ValueError, "task_id must be a safe slug"):
            module.route_task(valid_route_task(task_id="bad; rm -rf"), today=TODAY)

        route = valid_route()
        for argv in route["profile_argv"].values():
            self.assertIsInstance(argv, list)
            self.assertTrue(all(isinstance(part, str) and part for part in argv))
            self.assertNotIn(";", " ".join(argv))
        self.assertNotIn("command", json.dumps(route).lower())

    def test_route_validates_attempt_flags_type_effort_and_limits(self):
        bad_cases = [
            ({"attempt": 0}, "attempt"),
            ({"flags": ["unknown"]}, "unknown flag"),
            ({"task_type": "T99"}, "task_type"),
            ({"effort": "E9"}, "effort"),
            ({"limits": {"max_tasks": 10, "max_runtime_minutes": -1, "max_retries": 1, "usd_ceiling": 1.0}}, "max_runtime"),
            ({"limits": {"max_tasks": 10, "max_runtime_minutes": 10, "max_retries": 1, "usd_ceiling": float("inf")}}, "usd_ceiling"),
        ]
        for overrides, pattern in bad_cases:
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(ValueError, pattern):
                    module.route_task(valid_route_task(**overrides), today=TODAY)

    def test_route_rejects_future_and_stale_registry_entries(self):
        registry = {"max_age_days": 30, "entries": [{"id": "grok-4.20", "checked_at": "2026-09-09"}]}
        with self.assertRaisesRegex(ValueError, "future"):
            module.route_task(valid_route_task(registry=registry), today=TODAY)

        registry = {"max_age_days": 30, "entries": [{"id": "grok-4.20", "checked_at": "2026-07-01"}]}
        with self.assertRaisesRegex(ValueError, "stale"):
            module.route_task(valid_route_task(registry=registry), today=TODAY)

    def test_v3_rejects_tampered_policy_hash(self):
        plan = valid_v3_plan()
        plan["route"]["policy_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "policy_hash"):
            module.build_graph(plan)

    def test_policy_hash_changes_when_policy_values_change(self):
        before = module._current_policy_hash()
        with patch.dict(module.EFFORT_CEILINGS["E2"], {"usd_ceiling": 9.0}):
            self.assertNotEqual(before, module._current_policy_hash())

    def test_route_task_policy_changes_rebind_plan_hash_and_idempotency(self):
        first_route = valid_route()
        second_route = valid_route(title="Upgrade the recursive swarm skill safely")
        self.assertNotEqual(first_route["task_hash"], second_route["task_hash"])

        first = module.build_graph(valid_v3_plan(first_route))
        second = module.build_graph(valid_v3_plan(second_route))
        self.assertEqual(first["version"], 3)
        self.assertEqual(first["policy_version"], module.DEFAULT_POLICY_VERSION)
        self.assertNotEqual(first["plan_hash"], second["plan_hash"])
        first_keys = {node["id"]: node["idempotency_key"] for node in first["nodes"]}
        second_keys = {node["id"]: node["idempotency_key"] for node in second["nodes"]}
        self.assertNotEqual(first_keys["app.tests"], second_keys["app.tests"])

    def test_v3_critical_route_adds_astra_contract_manual_and_acceptance_gates(self):
        route = valid_route(task_type="T11", effort="E1", flags=["critical", "secrets"])
        graph = module.build_graph(valid_v3_plan(route))
        nodes = {node["id"]: node for node in graph["nodes"]}

        self.assertTrue(graph["route"]["gates"]["astra_contract"])
        self.assertTrue(graph["route"]["gates"]["astra_final_acceptance"])
        self.assertTrue(graph["route"]["gates"]["manual_approval"])
        self.assertEqual(nodes["app.astra-contract"]["assignee"], "default")
        self.assertEqual(nodes["app.astra-acceptance"]["assignee"], "default")
        self.assertEqual(nodes["app.manual-approval"]["assignee"], "default")
        self.assertIn("app.anchor", nodes["app.astra-contract"]["parents"])
        self.assertIn("app.astra-contract", nodes["unit.accounts.validate.spec"]["parents"])
        self.assertIn("app.judge", nodes["app.astra-acceptance"]["parents"])
        self.assertEqual(nodes["app.manual-approval"]["parents"], ["app.astra-acceptance"])
        self.assertFalse(any("app.manual-approval" in node["parents"] for node in graph["nodes"]))

    def test_astra_and_grok_cards_pin_exact_models_independent_of_profile_defaults(self):
        graph = module.build_graph(valid_v3_plan(valid_route(
            task_type="T14", effort="E3", flags=["critical"], modifiers=["V"]
        )))
        nodes = {node["id"]: node for node in graph["nodes"]}
        for node_id in ("app.astra-contract", "app.judge", "app.astra-acceptance"):
            self.assertEqual(nodes[node_id]["model_override"], "gpt-6-astra")
            self.assertEqual(nodes[node_id]["provider_override"], "openai-api")
            parent_ids = {parent: f"t_{index}" for index, parent in enumerate(nodes[node_id]["parents"])}
            args = module._create_args(nodes[node_id], "board", parent_ids, graph["plan_hash"])
            self.assertEqual(args[args.index("--model") + 1], "gpt-6-astra")
            self.assertEqual(args[args.index("--provider") + 1], "openai-api")
        self.assertEqual(nodes["app.grok-review"]["model_override"], "x-ai/grok-4.20")
        self.assertEqual(nodes["app.grok-review"]["provider_override"], "openrouter")

    def test_manual_gate_is_blocked_scoped_and_not_goal_dispatched(self):
        route = valid_route(task_type="T8", effort="E1", flags=["external-writes"], modifiers=["E"])
        graph = module.build_graph(valid_v3_plan(route))
        node = next(item for item in graph["nodes"] if item["id"] == "app.manual-approval")
        parent_ids = {parent: f"t_{index}" for index, parent in enumerate(node["parents"])}
        args = module._create_args(node, "board", parent_ids, graph["plan_hash"])
        body = args[args.index("--body") + 1]

        self.assertIn("--initial-status", args)
        self.assertNotIn("--goal", args)
        self.assertIn(f"plan_hash: {graph['plan_hash']}", body)
        self.assertIn(f"plan_revision: {route['plan_revision']}", body)
        self.assertIn(f"action: {route['manual_action']}", body)

    def test_optional_grok_review_is_read_only_and_never_default_or_restricted(self):
        default_graph = module.build_graph(valid_v3_plan(valid_route(task_type="T5", effort="E2", flags=[], modifiers=[])))
        self.assertFalse(any(node["assignee"] == "grokreview" for node in default_graph["nodes"]))

        grok_graph = module.build_graph(valid_v3_plan(valid_route(task_type="T14", effort="E3", flags=["high"], modifiers=["V"])))
        grok_nodes = [node for node in grok_graph["nodes"] if node["assignee"] == "grokreview"]
        self.assertTrue(grok_nodes)
        self.assertTrue(all(not node["writer"] for node in grok_nodes))
        self.assertIn("feature.accounts.grok-review", {node["id"] for node in grok_nodes})
        self.assertIn("app.grok-review", {node["id"] for node in grok_nodes})

        with self.assertRaisesRegex(ValueError, "restricted"):
            module.route_task(valid_route_task(sensitivity="restricted"), today=TODAY)

    def test_opus_recovery_only_after_f3_threshold_and_repairs_failed_unit(self):
        route = valid_route(task_type="T5", effort="E2", flags=[], modifiers=[])
        state = {"f3_shortfalls": 0}
        first = module.failure_transition(state, "F3", route, failed_unit="unit.accounts.validate")
        self.assertEqual(state, {"f3_shortfalls": 0})
        self.assertEqual(first["action"], "retry_failed_unit")
        self.assertEqual(first["repair_scope"], ["unit.accounts.validate"])
        self.assertFalse(first["use_opus"])

        second = module.failure_transition({"f3_shortfalls": route["recovery"]["f3_opus_threshold"] - 1}, "F3", route, failed_unit="unit.accounts.validate")
        self.assertEqual(second["action"], "escalate_opus")
        self.assertEqual(second["repair_scope"], ["unit.accounts.validate"])
        self.assertTrue(second["use_opus"])
        self.assertEqual(second["opus_profile"], "opus47")

        self.assertEqual(module.failure_transition({}, "F1", route, failed_unit="u")["action"], "retry_failed_unit")
        self.assertEqual(module.failure_transition({}, "F2", route, failed_unit="u")["action"], "repair_contract")
        self.assertEqual(module.failure_transition({}, "F4", route, failed_unit="u")["action"], "replan_integration")
        self.assertEqual(module.failure_transition({}, "F5", route, failed_unit="u")["action"], "stop")
        with self.assertRaisesRegex(ValueError, "failure_class"):
            module.failure_transition({}, "FX", route, failed_unit="u")

    def test_v3_declared_limits_fail_closed_before_graph_creation(self):
        route = valid_route()
        plan = valid_v3_plan(route)
        plan["limits"]["usd_ceiling"] = route["ceilings"]["usd_ceiling"] + 0.01
        with self.assertRaisesRegex(ValueError, "usd_ceiling"):
            module.build_graph(plan)

    def test_topology_rejects_unresolved_parents(self):
        graph = module.build_graph(valid_plan())
        graph["nodes"].append({
            "id": "app.orphan",
            "assignee": "qwen",
            "writer": False,
            "parents": ["missing.parent"],
            "idempotency_key": "k",
            "role_card": {"title": "orphan", "instructions": "orphan"},
        })
        with self.assertRaisesRegex(ValueError, "unresolved parent"):
            module._topo_order(graph)

    def test_topology_rejects_cycles(self):
        graph = {"nodes": [
            {"id": "a", "parents": ["b"]},
            {"id": "b", "parents": ["a"]},
        ]}
        with self.assertRaisesRegex(ValueError, "cycle"):
            module._topo_order(graph)

    def test_test_gate_instructions_require_sha256_map_shape(self):
        text = module._gate_rules_text("tests")
        self.assertIn("JSON object mapping every test_files path", text)

    def test_v3_preserves_red_before_build_and_full_barriers(self):
        graph = module.build_graph(valid_v3_plan(valid_route(task_type="T5", effort="E2", flags=[], modifiers=[])))
        nodes = {node["id"]: node for node in graph["nodes"]}

        for node in graph["nodes"]:
            if node["id"].startswith("unit.") and node["id"].endswith(".build"):
                test_id = node["id"].removesuffix(".build") + ".tests"
                self.assertEqual(nodes[test_id]["assignee"], "deepseek")
                self.assertIn(test_id, node["parents"])

        unit_reviews = {node["id"] for node in graph["nodes"] if node["id"].startswith("unit.") and node["id"].endswith(".review")}
        for node in graph["nodes"]:
            if node["id"].startswith("feature.") and node["id"].endswith(".tests"):
                self.assertTrue(unit_reviews <= set(node["parents"]))

        feature_reviews = {node["id"] for node in graph["nodes"] if node["id"].startswith("feature.") and node["id"].endswith(".review")}
        self.assertTrue(feature_reviews <= set(nodes["app.tests"]["parents"]))

    def test_v3_certification_requires_exact_gate_metadata(self):
        route = valid_route(task_type="T11", effort="E1", flags=["critical", "secrets"])
        plan = valid_v3_plan(route)
        graph = module.build_graph(plan)
        task_ids = {node["id"]: f"t_{index}" for index, node in enumerate(graph["nodes"])}
        metadata = complete_metadata_for_graph(graph)
        manifest = {"version": 3, "board": "sample", "plan": plan, "graph": graph, "task_ids": task_ids}

        def runner(args):
            if "list" in args:
                return [
                    {"id": task_ids[node["id"]], "title": node["id"],
                     "body": module._task_body(node, graph["plan_hash"])}
                    for node in graph["nodes"]
                ]
            task_id = args[-2]
            node_id = next(node for node, tid in task_ids.items() if tid == task_id)
            node = next(item for item in graph["nodes"] if item["id"] == node_id)
            return {
                "task": {"id": task_id, "title": node_id, "status": "done",
                         "body": module._task_body(node, graph["plan_hash"])},
                "runs": [{"metadata": metadata[node_id]}],
            }

        metadata["app.manual-approval"]["action"] = "different-action"
        failed = module.certify_manifest(manifest, runner=runner)
        self.assertEqual(failed["verdict"], "FAIL")
        self.assertTrue(any("manual approval metadata" in item for item in failed["failures"]))

        metadata["app.manual-approval"]["action"] = route["manual_action"]
        passed = module.certify_manifest(manifest, runner=runner)
        self.assertEqual(passed["verdict"], "PASS")

    def test_route_cli_subcommand_emits_deterministic_json(self):
        parser = module.build_parser()
        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "task.json"
            task_path.write_text(json.dumps(valid_route_task()))
            args = parser.parse_args(["route", "--task-file", str(task_path), "--today", "2026-09-08"])
            stdout = StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(module.cmd_route(args), 0)
            first = json.loads(stdout.getvalue())
            stdout = StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(module.cmd_route(args), 0)
            self.assertEqual(first, json.loads(stdout.getvalue()))
            self.assertEqual(first["policy_version"], module.DEFAULT_POLICY_VERSION)

    def test_route_can_be_bound_into_a_valid_v3_plan(self):
        route = valid_route(task_type="T11", effort="E1", flags=["critical", "secrets"])
        plan = module.bind_route_to_plan(valid_plan(), valid_route_task(
            task_type="T11", effort="E1", flags=["critical", "secrets"]
        ), route)
        self.assertEqual(plan["version"], 3)
        self.assertEqual(plan["policy_version"], module.DEFAULT_POLICY_VERSION)
        self.assertEqual(plan["route"], route)
        self.assertEqual(plan["task"]["task_hash"], route["task_hash"])
        module.validate_plan(plan)

    def test_draft_parser_accepts_task_file_and_today_for_v3_binding(self):
        parser = module.build_parser()
        args = parser.parse_args([
            "draft", "--app-id", "sample-app", "--goal", "goal",
            "--repo", "/tmp/sample-app", "--output", "/tmp/plan.json",
            "--task-file", "/tmp/task.json", "--today", "2026-09-08",
        ])
        self.assertEqual(args.task_file, Path("/tmp/task.json"))
        self.assertEqual(args.today, "2026-09-08")


if __name__ == "__main__":
    unittest.main(verbosity=2)
