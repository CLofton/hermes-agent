#!/usr/bin/env python3
"""Recursive engineering swarm CLI.

Decomposes an Astra plan into atomic/feature/app gate graphs backed by Hermes
Kanban dependencies. Python stdlib only. Deterministic: identical plans yield
identical graph ids, edges, plan hashes, and idempotency keys.

Real CLI surface used (never the hallucinated `kanban cards` API):
  hermes kanban --board BOARD create TITLE --body BODY --assignee PROFILE \
      --parent ID... --workspace WS --idempotency-key KEY \
      --max-runtime 30m --max-retries 3 --skill SKILL \
      --created-by recursive-swarm [--initial-status blocked] --json
  hermes kanban boards list --json
  hermes kanban boards create SLUG --name NAME
  hermes kanban --board BOARD complete TASK_ID --summary TEXT --metadata JSON
  hermes kanban --board BOARD dispatch --max 4 --json
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

DEFAULT_POLICY_VERSION = "3.0.0"
ALLOWED_SENSITIVITY = {"public", "internal"}
FORBIDDEN_SENSITIVITY = {"restricted", "secret"}
EFFORTS = ("E0", "E1", "E2", "E3", "E4")
MODIFIER_ORDER = ("E", "P", "G", "H", "V")
KNOWN_FLAGS = {
    "critical", "high", "payments", "secrets", "destructive", "pii",
    "prod", "external-writes",
}
CRITICAL_FLAGS = {"critical", "payments", "secrets", "destructive", "pii"}
MANUAL_FLAGS = {"prod", "destructive", "external-writes"}
TASK_TYPE_POLICY = {
    "T1": {"name": "Mechanical edit", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T2": {"name": "Bug fix, reproducible", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T3": {"name": "Bug fix, no reproduction", "min_effort": "E1", "default_flags": (), "default_modifiers": ("P",)},
    "T4": {"name": "Tests and fixtures", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T5": {"name": "Backend/API/service feature", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T6": {"name": "Frontend/UI feature", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T7": {"name": "Data and schema", "min_effort": "E0", "default_flags": ("critical", "destructive"), "default_modifiers": ("G", "H")},
    "T8": {"name": "Integration and automation", "min_effort": "E0", "default_flags": ("external-writes",), "default_modifiers": ("E", "H")},
    "T9": {"name": "Behavior-preserving refactor", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T10": {"name": "Research and evidence", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T11": {"name": "Security/auth/permissions/secrets", "min_effort": "E0", "default_flags": ("critical", "secrets"), "default_modifiers": ("G", "H")},
    "T12": {"name": "Infra/CI/deploy/environment", "min_effort": "E0", "default_flags": (), "default_modifiers": ()},
    "T13": {"name": "Architecture and design decision", "min_effort": "E3", "default_flags": ("high",), "default_modifiers": ("G",)},
    "T14": {"name": "Agent, skill and policy engineering", "min_effort": "E0", "default_flags": ("high",), "default_modifiers": ("V",)},
}
EFFORT_CEILINGS = {
    "E0": {"max_tasks": 30, "max_runtime_minutes": 30, "max_retries": 2, "usd_ceiling": 2.0},
    "E1": {"max_tasks": 100, "max_runtime_minutes": 120, "max_retries": 3, "usd_ceiling": 8.0},
    "E2": {"max_tasks": 100, "max_runtime_minutes": 120, "max_retries": 3, "usd_ceiling": 8.0},
    "E3": {"max_tasks": 160, "max_runtime_minutes": 360, "max_retries": 3, "usd_ceiling": 25.0},
    "E4": {"max_tasks": 240, "max_runtime_minutes": 480, "max_retries": 3, "usd_ceiling": 75.0},
}
PROFILE_ROLES = {
    "default": "Astra judge/conductor",
    "qwen": "spec/review",
    "deepseek": "RED tests",
    "glmvalue": "sole implementation",
    "grokreview": "optional read-only adversarial review",
    "opus47": "optional Opus 4.7 recovery/escalation",
}
PROFILE_MODEL_PINS = {
    "astra": {"model": "gpt-6-astra", "provider": "openai-api"},
    "grokreview": {"model": "x-ai/grok-4.20", "provider": "openrouter"},
}
ROLE_SKILLS = {
    "default": "recursive-engineering-swarm",
    "qwen": "recursive-engineering-swarm",
    "deepseek": "recursive-engineering-swarm",
    "glmvalue": "recursive-engineering-swarm",
    "grokreview": "recursive-engineering-swarm",
    "opus47": "recursive-engineering-swarm",
}
# DeepSeek tests and GLM builds/integrations are repository writers;
# Qwen specs/reviews and the default judge run read-only in scratch.
WRITER_KINDS = {"tests", "build", "integration"}


# ---------------------------------------------------------------- validation

def _fail(message):
    raise ValueError(message)


def _validate_slug(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        _fail(f"{field} must be a safe slug (lowercase letters, digits, hyphens)")


def _validate_acceptance(value, field):
    if not isinstance(value, list) or not value:
        _fail(f"{field} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        _fail(f"{field} contains a blank or non-string criterion")


def _canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_json(value):
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_today(today):
    if today is None:
        return dt.date.today()
    if isinstance(today, dt.datetime):
        return today.date()
    if isinstance(today, dt.date):
        return today
    if isinstance(today, str):
        return dt.date.fromisoformat(today)
    _fail("today must be an ISO date")


def _validate_sensitivity(value):
    sensitivity = str(value or "").lower()
    if sensitivity in FORBIDDEN_SENSITIVITY:
        _fail(f"sensitivity '{sensitivity}' is forbidden for OpenRouter routing")
    if sensitivity not in ALLOWED_SENSITIVITY:
        _fail(f"sensitivity must be public or internal, got '{value}'")
    return sensitivity


def _effort_index(effort):
    if effort not in EFFORTS:
        _fail(f"effort must be one of {', '.join(EFFORTS)}")
    return EFFORTS.index(effort)


def _max_effort(left, right):
    return left if _effort_index(left) >= _effort_index(right) else right


def _canonical_modifiers(modifiers):
    values = set(modifiers)
    return [modifier for modifier in MODIFIER_ORDER if modifier in values]


def _validate_flag_list(values, field):
    if values is None:
        return []
    if not isinstance(values, list):
        _fail(f"{field} must be a list")
    flags = []
    for flag in values:
        if not isinstance(flag, str) or flag not in KNOWN_FLAGS:
            _fail(f"unknown flag: {flag}")
        flags.append(flag)
    return flags


def _validate_modifier_list(values):
    if values is None:
        return []
    if not isinstance(values, list):
        _fail("modifiers must be a list")
    modifiers = []
    for modifier in values:
        if not isinstance(modifier, str) or modifier not in MODIFIER_ORDER:
            _fail(f"unknown modifier: {modifier}")
        modifiers.append(modifier)
    return modifiers


def _validate_number(value, field, integer=False, positive=False):
    if integer:
        if type(value) is not int:
            _fail(f"{field} must be an integer")
        numeric = value
    else:
        if type(value) not in (int, float) or not math.isfinite(float(value)):
            _fail(f"{field} must be a finite nonnegative number")
        numeric = float(value)
    if positive and numeric <= 0:
        _fail(f"{field} must be positive")
    if not positive and numeric < 0:
        _fail(f"{field} must be nonnegative")
    return numeric


def _validate_limits(limits, ceilings):
    values = dict(ceilings)
    limits = limits or {}
    if not isinstance(limits, dict):
        _fail("limits must be an object")
    validators = {
        "max_tasks": lambda v: _validate_number(v, "max_tasks", integer=True, positive=True),
        "max_runtime_minutes": lambda v: _validate_number(v, "max_runtime_minutes"),
        "max_retries": lambda v: _validate_number(v, "max_retries", integer=True),
        "usd_ceiling": lambda v: _validate_number(v, "usd_ceiling"),
    }
    for field, validator in validators.items():
        if field not in limits:
            continue
        value = validator(limits[field])
        if value > ceilings[field]:
            _fail(f"{field} exceeds route ceiling of {ceilings[field]}")
        values[field] = value
    return values


def _validate_registry_dates(registry, today):
    if registry is None:
        return
    if not isinstance(registry, dict):
        _fail("registry must be an object")
    max_age = _validate_number(registry.get("max_age_days", 30), "registry.max_age_days", integer=True, positive=True)
    entries = registry.get("entries", [])
    if not isinstance(entries, list):
        _fail("registry.entries must be a list")
    for entry in entries:
        if not isinstance(entry, dict):
            _fail("registry entries must be objects")
        model_id = entry.get("id") or entry.get("model") or "<unknown>"
        checked_at = entry.get("checked_at")
        if not isinstance(checked_at, str) or not checked_at:
            _fail(f"registry entry {model_id} missing checked_at")
        checked_date = dt.date.fromisoformat(checked_at)
        if checked_date > today:
            _fail(f"registry entry {model_id} has future checked_at {checked_at}")
        age = (today - checked_date).days
        if age > max_age:
            _fail(f"registry entry {model_id} is stale: checked {age} days ago")


def _stage1_task_type(task):
    explicit = task.get("task_type")
    if explicit is not None:
        if explicit not in TASK_TYPE_POLICY:
            _fail(f"task_type must be one of {', '.join(sorted(TASK_TYPE_POLICY))}")
        return explicit, "explicit"
    files = [str(path).replace("\\", "/").lower() for path in task.get("files", []) or []]
    title = str(task.get("title", "")).lower()
    description = str(task.get("description", "")).lower()
    text = f"{title} {description}"
    path_rules = [
        ("T11", ("auth/", "permission", "secret", ".env")),
        ("T7", ("migration", ".sql", "schema.prisma", "seed")),
        ("T8", ("webhook", "integrations/", "stripe", "billing", "n8n/")),
        ("T12", (".github/workflows/", "vercel.json", "netlify.toml", "railway", "dockerfile")),
        ("T14", ("skills/", ".hermes", "policy", "router.py", "recursive_swarm.py")),
        ("T4", (".test.", "__tests__/", "fixtures/")),
        ("T1", ("docs/", ".md")),
    ]
    for task_type, needles in path_rules:
        if any(any(needle in path for needle in needles) for path in files):
            return task_type, "path"
    keyword_rules = [
        ("T1", ("typo", "formatting", "rename", "comment", "docs only")),
        ("T3", ("intermittent", "sometimes", "no repro", "cannot reproduce", "flaky")),
        ("T2", ("failing test", "repro steps", "bug", "regression")),
        ("T4", ("add tests", "test coverage", "fixtures")),
        ("T9", ("refactor", "behavior-preserving", "no behavior change")),
        ("T10", ("research", "compare", "evaluate", "spike")),
        ("T13", ("architecture", "design decision", "adr", "service boundary")),
        ("T7", ("migration", "backfill", "seed", "schema")),
        ("T8", ("webhook", "cron", "sync job", "integration")),
        ("T11", ("auth", "permission", "role check", "oauth", "api key", "secret")),
        ("T12", ("deploy", "ci ", "github actions", "env var")),
        ("T14", ("hermes skill", "prompt", "routing policy", "agent")),
        ("T6", ("ui", "page", "component", "frontend", "form")),
        ("T5", ("endpoint", "api", "backend", "service", "job", "query")),
    ]
    for task_type, needles in keyword_rules:
        if any(needle in text for needle in needles):
            return task_type, "keyword"
    _fail("task_type could not be determined by deterministic stage-1 routing")


def _stage1_effort(task):
    explicit = task.get("effort")
    if explicit is not None:
        if explicit not in EFFORTS:
            _fail(f"effort must be one of {', '.join(EFFORTS)}")
        return explicit, "explicit"
    signals = task.get("signals") or {}
    files = task.get("files") or []
    file_count = len(files) or int(signals.get("files_touched", 0) or 0)
    changed_lines = int(signals.get("estimated_changed_lines", 0) or 0)
    if signals.get("new_design_needed") or signals.get("major_ambiguity"):
        return "E4", "signals"
    if signals.get("cross_module") or signals.get("concurrency") or file_count > 6 or changed_lines > 400:
        return "E3", "signals"
    if signals.get("changes_public_interface") or signals.get("needs_test_design") or file_count > 1 or changed_lines > 50:
        return "E2", "signals"
    if changed_lines > 10 or signals.get("has_logic_change") or not signals.get("mechanical", False):
        return "E1", "signals"
    return "E0", "signals"


def _route_family(task_type, effort):
    if task_type == "T10":
        return "RE"
    if task_type == "T13" and _effort_index(effort) < _effort_index("E3"):
        _fail("task_type T13 requires effort E3 or E4")
    if task_type in {"T7", "T8", "T11"} and effort == "E0":
        return "R1"
    return {"E0": "R0", "E1": "R1", "E2": "R2", "E3": "R3", "E4": "R4"}[effort]


def _current_policy_hash():
    compact_policy = {
        "policy_version": DEFAULT_POLICY_VERSION,
        "task_types": TASK_TYPE_POLICY,
        "efforts": list(EFFORTS),
        "effort_ceilings": EFFORT_CEILINGS,
        "modifiers": list(MODIFIER_ORDER),
        "known_flags": sorted(KNOWN_FLAGS),
        "critical_flags": sorted(CRITICAL_FLAGS),
        "manual_flags": sorted(MANUAL_FLAGS),
        "roles": PROFILE_ROLES,
        "model_pins": PROFILE_MODEL_PINS,
    }
    return _sha256_json(compact_policy)


def route_task(task, policy=None, today=None):
    """Return a deterministic v3 route decision. Pure: no Hermes/API calls."""
    if not isinstance(task, dict):
        _fail("task must be a JSON object")
    today = _parse_today(today)
    _validate_registry_dates(task.get("registry"), today)
    task_id = task.get("task_id")
    _validate_slug(task_id, "task_id")
    attempt = task.get("attempt", 1)
    if type(attempt) is not int or attempt < 1:
        _fail("attempt must be a positive integer")
    sensitivity = _validate_sensitivity(task.get("sensitivity", "internal"))
    task_type, type_source = _stage1_task_type(task)
    effort, effort_source = _stage1_effort(task)
    effort = _max_effort(effort, TASK_TYPE_POLICY[task_type]["min_effort"])
    flags = set(_validate_flag_list(task.get("flags"), "flags"))
    flags.update(_validate_flag_list(task.get("requester_flags"), "requester_flags"))
    flags.update(TASK_TYPE_POLICY[task_type]["default_flags"])
    if str(task.get("environment", "")).lower() in {"prod", "production"}:
        flags.add("prod")
    modifiers = set(_validate_modifier_list(task.get("modifiers")))
    modifiers.update(TASK_TYPE_POLICY[task_type]["default_modifiers"])
    if task_type == "T12" and _effort_index(effort) >= _effort_index("E3"):
        modifiers.update({"G", "H"})
    if task_type == "T9" and effort == "E4":
        modifiers.add("G")
    if flags & CRITICAL_FLAGS:
        modifiers.add("G")
    if flags & MANUAL_FLAGS:
        modifiers.add("H")
    family = _route_family(task_type, effort)
    if family == "R4":
        modifiers.add("G")
    if family == "RE":
        modifiers -= {"P", "G"}
    modifiers = _canonical_modifiers(modifiers)
    modifier_text = "".join(modifiers)
    cell = f"{family}+{modifier_text}" if modifier_text else family
    ceilings = dict(EFFORT_CEILINGS[effort])
    limits = _validate_limits(task.get("limits"), ceilings)
    gates = {
        "astra_contract": "G" in modifiers,
        "astra_final_acceptance": "G" in modifiers,
        "manual_approval": "H" in modifiers,
        "grok_adversarial": "V" in modifiers and sensitivity in ALLOWED_SENSITIVITY,
    }
    manual_flags = sorted(flags & MANUAL_FLAGS)
    manual_action = "approve-" + "-".join(manual_flags) if manual_flags else "none"
    profile_argv = {
        profile: ["hermes", "--profile", profile, "chat", "-q", "<card-prompt>", "--quiet"]
        for profile in PROFILE_ROLES
    }
    return {
        "status": "planned",
        "policy_version": DEFAULT_POLICY_VERSION,
        "policy_hash": _current_policy_hash(),
        "task_hash": _sha256_json(task),
        "task_id": task_id,
        "attempt": attempt,
        "plan_revision": f"{task_id}-attempt-{attempt}",
        "task_type": task_type,
        "task_type_source": type_source,
        "effort": effort,
        "effort_source": effort_source,
        "family": family,
        "cell": cell,
        "modifiers": modifiers,
        "flags": sorted(flags),
        "sensitivity": sensitivity,
        "stage": 1,
        "stage1": {"deterministic": True, "type_source": type_source, "effort_source": effort_source},
        "roles": PROFILE_ROLES,
        "model_pins": PROFILE_MODEL_PINS,
        "profile_argv": profile_argv,
        "gates": gates,
        "manual_action": manual_action,
        "limits": limits,
        "ceilings": ceilings,
        "recovery": {
            "failure_classes": ["F1", "F2", "F3", "F4", "F5"],
            "f3_opus_threshold": 2,
            "opus_profile": "opus47",
            "opus_model": "Opus 4.7",
            "routine_use": False,
        },
        "spending_authority": "none",
    }


def failure_transition(state, failure_class, route, failed_unit):
    """Pure F1-F5 transition logic for one failed unit."""
    if failure_class not in {"F1", "F2", "F3", "F4", "F5"}:
        _fail("failure_class must be one of F1, F2, F3, F4, F5")
    if not isinstance(failed_unit, str) or not failed_unit.strip():
        _fail("failed_unit is required")
    current = dict(state or {})
    repair_scope = [failed_unit]
    if failure_class == "F1":
        action = "retry_failed_unit"
        use_opus = False
    elif failure_class == "F2":
        action = "repair_contract"
        use_opus = False
    elif failure_class == "F3":
        next_count = int(current.get("f3_shortfalls", 0) or 0) + 1
        current["f3_shortfalls"] = next_count
        threshold = int(((route or {}).get("recovery") or {}).get("f3_opus_threshold", 2))
        use_opus = next_count >= threshold
        action = "escalate_opus" if use_opus else "retry_failed_unit"
    elif failure_class == "F4":
        action = "replan_integration"
        use_opus = False
    else:
        action = "stop"
        use_opus = False
    return {
        "failure_class": failure_class,
        "action": action,
        "repair_scope": repair_scope,
        "state": current,
        "use_opus": use_opus,
        "opus_profile": ((route or {}).get("recovery") or {}).get("opus_profile") if use_opus else None,
    }


def _validate_route_metadata(plan):
    route = plan.get("route")
    if not isinstance(route, dict):
        _fail("v3 plans must carry route metadata")
    task = plan.get("task")
    if not isinstance(task, dict):
        _fail("v3 plans must carry task binding metadata")
    if plan.get("policy_version") != DEFAULT_POLICY_VERSION:
        _fail(f"policy_version must equal {DEFAULT_POLICY_VERSION}")
    if route.get("policy_version") != plan.get("policy_version"):
        _fail("route policy_version must match plan policy_version")
    _validate_slug(route.get("task_id"), "route.task_id")
    if type(route.get("attempt")) is not int or route.get("attempt") < 1:
        _fail("route.attempt must be a positive integer")
    if task.get("task_id") != route.get("task_id"):
        _fail("task.task_id must match route.task_id")
    if task.get("attempt") != route.get("attempt"):
        _fail("task.attempt must match route.attempt")
    if task.get("task_hash") != route.get("task_hash"):
        _fail("task.task_hash must match route.task_hash")
    if route.get("task_type") not in TASK_TYPE_POLICY:
        _fail("route.task_type is unknown")
    if route.get("effort") not in EFFORTS:
        _fail("route.effort is unknown")
    for field in ("task_hash", "policy_hash"):
        if not isinstance(route.get(field), str) or not re.fullmatch(r"[0-9a-f]{64}", route[field]):
            _fail(f"route.{field} must be a SHA-256 hex digest")
    if route["policy_hash"] != _current_policy_hash():
        _fail("route.policy_hash does not match the current routing policy")
    _validate_sensitivity(route.get("sensitivity"))
    if str(plan["app"]["sensitivity"]).lower() != route["sensitivity"]:
        _fail("route sensitivity must match app sensitivity")
    flags = set(_validate_flag_list(route.get("flags"), "route.flags"))
    modifiers = set(_validate_modifier_list(route.get("modifiers")))
    gates = route.get("gates")
    if not isinstance(gates, dict):
        _fail("route.gates is required")
    if flags & CRITICAL_FLAGS and not (gates.get("astra_contract") and gates.get("astra_final_acceptance")):
        _fail("critical flags require Astra contract and final acceptance gates")
    if flags & MANUAL_FLAGS and not gates.get("manual_approval"):
        _fail("prod/destructive/external-writes require manual approval")
    if gates.get("grok_adversarial") and "V" not in modifiers:
        _fail("Grok adversarial review requires route modifier V")
    ceilings = route.get("ceilings")
    route_limits = route.get("limits")
    if not isinstance(ceilings, dict) or not isinstance(route_limits, dict):
        _fail("route ceilings and limits are required")
    for field in ("max_tasks", "max_runtime_minutes", "max_retries", "usd_ceiling"):
        if field not in ceilings:
            _fail(f"route.ceilings.{field} is required")
        _validate_number(
            ceilings[field], f"route.ceilings.{field}",
            integer=field in {"max_tasks", "max_retries"},
            positive=field == "max_tasks",
        )
    _validate_limits(route_limits, ceilings)
    return route


def validate_plan(plan):
    """Fail closed on any malformed or forbidden plan. Raises ValueError."""
    if not isinstance(plan, dict):
        _fail("plan must be a JSON object")
    if type(plan.get("version")) is not int or plan.get("version") not in {1, 3}:
        _fail("plan.version must equal 1 or 3")
    if not isinstance(plan.get("app"), dict):
        _fail("plan must contain an app object")
    app = plan["app"]
    for field in ("id", "title", "acceptance", "sensitivity", "repo"):
        if not app.get(field):
            _fail(f"app.{field} is required")
    _validate_slug(app["id"], "app.id")
    _validate_acceptance(app["acceptance"], "app.acceptance")
    sensitivity = str(app["sensitivity"]).lower()
    if sensitivity in FORBIDDEN_SENSITIVITY:
        _fail(
            f"sensitivity '{sensitivity}' is forbidden: OpenRouter cards cannot "
            "receive restricted/secret plans"
        )
    if sensitivity not in ALLOWED_SENSITIVITY:
        _fail(f"sensitivity must be public or internal, got '{app['sensitivity']}'")
    features = plan.get("features")
    if not isinstance(features, list) or not features:
        _fail("plan must contain at least one feature")
    feature_ids = set()
    for feature in features:
        if not isinstance(feature, dict):
            _fail("each feature must be an object")
        for field in ("id", "title", "acceptance"):
            if not feature.get(field):
                _fail(f"feature.{field} is required")
        _validate_slug(feature["id"], "feature.id")
        if feature["id"] in feature_ids:
            _fail(f"duplicate feature id: {feature['id']}")
        feature_ids.add(feature["id"])
        _validate_acceptance(feature["acceptance"], f"feature '{feature['id']}' acceptance")
        units = feature.get("units")
        if not isinstance(units, list) or not units:
            _fail(f"feature '{feature.get('id')}' must contain at least one unit")
        unit_ids = set()
        for unit in units:
            if not isinstance(unit, dict):
                _fail("each unit must be an object")
            for field in ("id", "title", "acceptance"):
                if not unit.get(field):
                    _fail(f"unit.{field} is required")
            _validate_slug(unit["id"], "unit.id")
            if unit["id"] in unit_ids:
                _fail(f"duplicate unit id in feature '{feature['id']}': {unit['id']}")
            unit_ids.add(unit["id"])
            _validate_acceptance(unit["acceptance"], f"unit '{unit['id']}' acceptance")
    limits = plan.get("limits") or {}
    max_tasks = limits.get("max_tasks")
    if max_tasks is None:
        _fail("limits.max_tasks is required")
    if not isinstance(max_tasks, int) or max_tasks < 1:
        _fail("limits.max_tasks must be a positive integer")
    if plan["version"] == 3:
        for field in ("max_runtime_minutes", "max_retries", "usd_ceiling"):
            if field not in limits:
                _fail(f"limits.{field} is required for v3 plans")
            _validate_number(
                limits[field], f"limits.{field}",
                integer=field == "max_retries",
            )
        _validate_route_metadata(plan)
    return plan


def _count_nodes(plan):
    units = sum(len(f["units"]) for f in plan["features"])
    count = 4 * units + 3 * len(plan["features"]) + 5  # atomic + feature + app gates + anchor
    if plan.get("version") == 3:
        gates = plan["route"].get("gates", {})
        if gates.get("astra_contract"):
            count += 1
        if gates.get("manual_approval"):
            count += 1
        if gates.get("astra_final_acceptance"):
            count += 1
        if gates.get("grok_adversarial"):
            count += len(plan["features"]) + 1
    return count


def _check_budget(plan):
    limits = plan.get("limits") or {}
    max_tasks = limits.get("max_tasks")
    if max_tasks is not None and _count_nodes(plan) > max_tasks:
        _fail(
            f"plan requires {_count_nodes(plan)} tasks but exceeds the "
            f"task budget of {max_tasks}"
        )
    if plan.get("version") == 3:
        ceilings = plan["route"]["ceilings"]
        if max_tasks > ceilings["max_tasks"]:
            _fail(f"limits.max_tasks exceeds route max_tasks ceiling of {ceilings['max_tasks']}")
        for field in ("max_runtime_minutes", "max_retries", "usd_ceiling"):
            if field in limits:
                value = _validate_number(
                    limits[field], field, integer=(field == "max_retries")
                )
                if value > ceilings[field]:
                    _fail(f"limits.{field} exceeds route {field} ceiling of {ceilings[field]}")


# ---------------------------------------------------------------- graph build

def _plan_hash(plan):
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _node(plan_hash, node_id, assignee, writer, parents, role_card):
    key = hashlib.sha256(f"{plan_hash}:{node_id}".encode("utf-8")).hexdigest()
    return {
        "id": node_id,
        "assignee": assignee,
        "writer": writer,
        "parents": list(parents),
        "idempotency_key": key,
        "role_card": role_card,
    }


def build_graph(plan):
    """Build the deterministic atomic-feature-app gate graph for a plan."""
    validate_plan(plan)
    _check_budget(plan)
    ph = _plan_hash(plan)
    nodes = []
    by_id = {}
    route = plan.get("route") if plan.get("version") == 3 else None
    gates = route.get("gates", {}) if route else {}

    def add(node_id, assignee, writer, parents, role_card):
        node = _node(ph, node_id, assignee, writer, parents, role_card)
        if plan.get("version") == 3:
            node["policy_version"] = plan["policy_version"]
            node["route_cell"] = route["cell"]
            node["limits"] = dict(route["limits"])
            if role_card.get("blocked_gate"):
                node["blocked_gate"] = True
            if role_card.get("certification"):
                node["certification"] = role_card["certification"]
        if node_id in {"app.astra-contract", "app.judge", "app.astra-acceptance"}:
            node["model_override"] = PROFILE_MODEL_PINS["astra"]["model"]
            node["provider_override"] = PROFILE_MODEL_PINS["astra"]["provider"]
        elif assignee == "grokreview":
            node["model_override"] = PROFILE_MODEL_PINS["grokreview"]["model"]
            node["provider_override"] = PROFILE_MODEL_PINS["grokreview"]["provider"]
        nodes.append(node)
        by_id[node_id] = node
        return node_id

    app = plan["app"]
    repo = app["repo"]

    # 1. Completed conductor anchor (root; born blocked, completed by apply).
    add("app.anchor", "default", False, [], _anchor_card(plan, ph))
    dispatch_parent = "app.anchor"

    if gates.get("astra_contract"):
        add("app.astra-contract", "default", False, [dispatch_parent], _astra_gate_card("contract", plan, ph))
        dispatch_parent = "app.astra-contract"

    # Writer total order: chain every repository writer (DeepSeek tests, GLM
    # builds/integrations) in deterministic plan order via a running "chain"
    # parent, layered on top of their natural gating parents.
    chain = "app.anchor"

    def writer(node_id, assignee, parents, role_card):
        nonlocal chain
        add(node_id, assignee, True, list(parents) + [chain], role_card)
        chain = node_id

    # 2. Complete the full atomic/base layer before any feature integration.
    all_unit_reviews = []
    for feature in plan["features"]:
        for unit in feature["units"]:
            fid, uid = feature["id"], unit["id"]
            base = f"unit.{fid}.{uid}"
            add(f"{base}.spec", "qwen", False, [dispatch_parent], _unit_card("spec", fid, uid, unit, repo))
            writer(
                f"{base}.tests", "deepseek", [f"{base}.spec"],
                _unit_card("tests", fid, uid, unit, repo),
            )
            writer(
                f"{base}.build", "glmvalue", [f"{base}.tests"],
                _unit_card("build", fid, uid, unit, repo),
            )
            add(f"{base}.review", "qwen", False, [f"{base}.build"], _unit_card("review", fid, uid, unit, repo))
            all_unit_reviews.append(f"{base}.review")

    # 3. Feature gates begin only after the complete atomic/base layer passes.
    for feature in plan["features"]:
        fid = feature["id"]
        writer(
            f"feature.{fid}.tests", "deepseek", all_unit_reviews,
            _feature_card("tests", fid, feature, repo),
        )
        writer(
            f"feature.{fid}.integration", "glmvalue", [f"feature.{fid}.tests"],
            _feature_card("integration", fid, feature, repo),
        )
        add(
            f"feature.{fid}.review", "qwen", False,
            [f"feature.{fid}.integration"], _feature_card("review", fid, feature, repo),
        )
        if gates.get("grok_adversarial"):
            add(
                f"feature.{fid}.grok-review", "grokreview", False,
                [f"feature.{fid}.review"], _grok_card("feature", fid, feature["title"], repo),
            )

    # 4. Whole-app gates, gated on every feature review.
    if gates.get("grok_adversarial"):
        feature_reviews = [f"feature.{f['id']}.grok-review" for f in plan["features"]]
    else:
        feature_reviews = [f"feature.{f['id']}.review" for f in plan["features"]]
    writer("app.tests", "deepseek", feature_reviews, _app_card("tests", plan, repo))
    writer("app.integration", "glmvalue", ["app.tests"], _app_card("integration", plan, repo))
    add("app.review", "qwen", False, ["app.integration"], _app_card("review", plan, repo))
    app_judge_parent = "app.review"
    if gates.get("grok_adversarial"):
        add("app.grok-review", "grokreview", False, ["app.review"], _grok_card("app", app["id"], app["title"], repo))
        app_judge_parent = "app.grok-review"
    add("app.judge", "default", False, [app_judge_parent], _app_card("judge", plan, repo))
    final_gate_parent = "app.judge"
    if gates.get("astra_final_acceptance"):
        add("app.astra-acceptance", "default", False, ["app.judge"], _astra_gate_card("acceptance", plan, ph))
        final_gate_parent = "app.astra-acceptance"
    if gates.get("manual_approval"):
        add("app.manual-approval", "default", False, [final_gate_parent], _manual_gate_card(plan, ph))

    graph = {
        "version": plan["version"],
        "plan_hash": ph,
        "nodes": nodes,
    }
    if plan.get("version") == 3:
        graph["policy_version"] = plan["policy_version"]
        graph["route"] = route
        graph["limits"] = dict(route["limits"])
    _validate_graph_parents(graph)
    return graph


def _gate_rules_text(kind):
    if kind == "tests":
        return (
            "GATE: Complete only with kanban metadata verdict=PASS, nonempty test_files, "
            "test_sha256 as a JSON object mapping every test_files path to its 64-character SHA-256 hex digest, "
            "test_command, and nonzero red_exit_code. Executable RED "
            "evidence is mandatory; otherwise block."
        )
    if kind in ("build", "integration"):
        return (
            "GATE: Complete only with kanban metadata verdict=PASS, "
            "targeted_exit_code=0, and regression_exit_code=0."
        )
    if kind == "spec":
        return "GATE: Complete only with kanban metadata verdict=PASS; otherwise block."
    return (
        "GATE: Complete only with kanban metadata verdict=PASS and findings=[]. "
        "Block on any non-PASS evidence (FAIL / NOT YET PROVEN); "
        "downstream children remain todo."
    )


def _workspace_for(kind, repo):
    # DeepSeek tests and GLM builds/integrations mutate the repository;
    # Qwen specs/reviews and the default judge stay read-only in scratch.
    if kind in WRITER_KINDS:
        return f"dir:{repo}"
    return "scratch"


def _kind_of(node_id):
    tail = node_id.rsplit(".", 1)[-1]
    return tail if tail != "anchor" else "judge"


def _unit_card(kind, fid, uid, unit, repo):
    title = f"[unit/{kind}] {fid}.{uid}: {unit['title']}"
    instructions = _card_instructions(kind, unit["acceptance"], repo)
    return {"title": title, "instructions": instructions, "repo": repo}


def _feature_card(kind, fid, feature, repo):
    title = f"[feature/{kind}] {fid}: {feature['title']}"
    instructions = _card_instructions(kind, feature["acceptance"], repo)
    return {"title": title, "instructions": instructions, "repo": repo}


def _app_card(kind, plan, repo):
    app = plan["app"]
    title = f"[app/{kind}] {app['id']}: {app['title']}"
    instructions = _card_instructions(kind, app["acceptance"], repo)
    return {"title": title, "instructions": instructions, "repo": repo}


def _card_instructions(kind, acceptance, repo):
    lines = [f"Acceptance: {json.dumps(acceptance)}"]
    lines.append(_gate_rules_text(kind))
    lines.append(f"Workspace: {_workspace_for(kind, repo)}")
    return "\n".join(lines)


def _anchor_card(plan, ph):
    return {
        "title": f"[conductor] {plan['app']['id']}: {plan['app']['title']}",
        "instructions": (
            f"Plan hash: {ph}\n"
            f"Sensitivity: {plan['app']['sensitivity']}\n"
            f"Repo: {plan['app']['repo']}\n"
            "GATE: Completed conductor anchor. Decomposition approved."
        ),
    }


def _astra_gate_card(kind, plan, ph):
    route = plan["route"]
    gate_name = "astra_contract" if kind == "contract" else "astra_final_acceptance"
    title_kind = "contract" if kind == "contract" else "final-acceptance"
    return {
        "title": f"[app/{title_kind}] {plan['app']['id']}: {plan['app']['title']}",
        "instructions": (
            f"Plan hash: {ph}\n"
            f"Policy version: {plan['policy_version']}\n"
            f"Route: {route['cell']} ({route['task_type']}/{route['effort']})\n"
            "GATE: Complete only with metadata verdict=PASS, gate="
            f"{gate_name}, exact plan_hash, policy_version, route_cell, "
            "and findings=[]. Block on FAIL or NOT YET PROVEN."
        ),
        "repo": plan["app"]["repo"],
        "certification": {
            "gate": gate_name,
            "plan_hash": ph,
            "policy_version": plan["policy_version"],
            "route_cell": route["cell"],
        },
    }


def _manual_gate_card(plan, ph):
    route = plan["route"]
    return {
        "title": f"[manual/approval] {plan['app']['id']}: {route['manual_action']}",
        "instructions": (
            f"Plan hash: {ph}\n"
            f"Policy version: {plan['policy_version']}\n"
            f"Plan revision: {route['plan_revision']}\n"
            f"Manual action: {route['manual_action']}\n"
            "GATE: Human approval only. This card is born blocked and is not "
            "goal-dispatched. Complete only with metadata verdict=PASS, "
            "gate=manual_approval, exact plan_hash, plan_revision, action, "
            "approved_by, and approved_at."
        ),
        "repo": plan["app"]["repo"],
        "blocked_gate": True,
        "bindings": {
            "plan_revision": route["plan_revision"],
            "action": route["manual_action"],
        },
        "certification": {
            "gate": "manual_approval",
            "plan_hash": ph,
            "plan_revision": route["plan_revision"],
            "action": route["manual_action"],
        },
    }


def _grok_card(level, target_id, title, repo):
    return {
        "title": f"[{level}/grok-review] {target_id}: {title}",
        "instructions": (
            "Read-only adversarial review. Inspect the completed boundary work "
            "for counterexamples, missed acceptance criteria, and integration "
            "risks. Do not modify files. GATE: Complete only with metadata "
            "verdict=PASS and findings=[]."
        ),
        "repo": repo,
        "read_only": True,
    }


# ---------------------------------------------------------------- apply

def _task_body(node, plan_hash):
    """Card body. Create has no --node-id/--metadata flags, so the graph node
    id and plan hash ride in the body; the card TITLE is the node id and the
    human-readable title is preserved here."""
    lines = [
        f"title: {node['role_card']['title']}",
        node["role_card"]["instructions"],
        f"node_id: {node['id']}",
        f"plan_hash: {plan_hash}",
    ]
    if node.get("policy_version"):
        lines.append(f"policy_version: {node['policy_version']}")
    if node.get("route_cell"):
        lines.append(f"route_cell: {node['route_cell']}")
    for key, value in sorted((node["role_card"].get("bindings") or {}).items()):
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _create_args(node, board, parent_task_ids, plan_hash):
    limits = node.get("limits") or {}
    runtime = int(limits.get("max_runtime_minutes", 30) or 0)
    retries = int(limits.get("max_retries", 3))
    args = [
        "kanban", "--board", board, "create",
        node["id"],
        "--body", _task_body(node, plan_hash),
        "--assignee", node["assignee"],
        "--workspace", _workspace_for(_kind_of(node["id"]), _repo_of(node)),
        "--idempotency-key", node["idempotency_key"],
        "--max-runtime", f"{runtime}m",
        "--max-retries", str(retries),
        "--skill", ROLE_SKILLS[node["assignee"]],
        "--created-by", "recursive-swarm",
    ]
    if node["id"] == "app.anchor" or node.get("blocked_gate"):
        args.extend(["--initial-status", "blocked"])
    else:
        args.extend(["--goal", "--goal-max-turns", "4"])
    if node.get("model_override"):
        args.extend(["--model", node["model_override"], "--provider", node["provider_override"]])
    for parent in node["parents"]:
        args.extend(["--parent", parent_task_ids[parent]])
    args.append("--json")
    return args


def _repo_of(node):
    return node["role_card"].get("repo", "/tmp")


def apply_graph(graph, board, runner=None, apply=False, dispatch=False):
    """Apply the graph to a Kanban board. Dry-run is the default and calls nothing."""
    _validate_graph_parents(graph)
    if not apply:
        return {"mode": "dry-run", "board": board, "task_ids": {}, "created": 0}

    if runner is None:
        runner = _hermes_runner

    # Use (or create) the board.
    listing = runner(["kanban", "boards", "list", "--json"])
    boards = listing if isinstance(listing, list) else listing.get("boards", [])
    if board not in {b.get("slug") or b.get("id") or b.get("name") for b in boards}:
        runner(["kanban", "boards", "create", board, "--name", board])

    # Topological creation order (parents before children).
    order = _topo_order(graph)
    task_ids = {}
    root_to_complete = None
    for node_id in order:
        node = next(n for n in graph["nodes"] if n["id"] == node_id)
        result = runner(_create_args(node, board, task_ids, graph["plan_hash"])) or {}
        # JSON create output uses `id`, not task_id.
        task_id = result.get("id") or result.get("task_id")
        if not task_id:
            raise ValueError(f"card creation returned no id for {node_id}")
        task_ids[node_id] = task_id
        # Keep the root blocked until every graph card exists. This prevents
        # the gateway dispatcher from observing and running a partial graph.
        if node_id == "app.anchor" and result.get("status") != "done":
            root_to_complete = task_id

    if root_to_complete:
        runner([
            "kanban", "--board", board, "complete", root_to_complete,
            "--summary",
            "Conductor anchor completed: decomposition approved "
            f"(plan_hash={graph['plan_hash']}, node_id=app.anchor).",
            "--metadata", json.dumps({
                "plan_hash": graph["plan_hash"],
                "node_id": "app.anchor",
            }),
        ])

    # Dispatch exactly once, after every graph card exists.
    if dispatch:
        runner(["kanban", "--board", board, "dispatch", "--max", "4", "--json"])

    return {
        "mode": "apply",
        "board": board,
        "task_ids": task_ids,
        "created": len(task_ids),
        "plan_hash": graph["plan_hash"],
    }


def write_manifest(path, board, plan, graph, applied):
    payload = {
        "version": graph.get("version", plan.get("version", 1)),
        "board": board,
        "plan": plan,
        "graph": graph,
        "task_ids": applied["task_ids"],
    }
    if graph.get("version") == 3:
        payload["policy_version"] = graph["policy_version"]
        payload["route"] = graph["route"]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def _is_iso_timestamp(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _metadata_failures(node_id, metadata, node=None):
    kind = node_id.rsplit(".", 1)[-1]
    if kind == "anchor":
        return []
    failures = []
    if metadata.get("verdict") != "PASS":
        failures.append(f"{node_id}: verdict must be PASS")
    certification = (node or {}).get("certification") or {}
    if node_id in {"app.astra-contract", "app.astra-acceptance"}:
        expected_gate = certification.get("gate")
        exact = {
            "gate": expected_gate,
            "plan_hash": certification.get("plan_hash"),
            "policy_version": certification.get("policy_version"),
            "route_cell": certification.get("route_cell"),
        }
        if any(metadata.get(field) != value for field, value in exact.items()) or metadata.get("findings") != []:
            label = "Astra contract" if node_id == "app.astra-contract" else "Astra final acceptance"
            failures.append(f"{node_id}: {label} metadata must match exact plan hash, policy version, route cell, and findings=[]")
        return failures
    if node_id == "app.manual-approval":
        exact = {
            "gate": "manual_approval",
            "plan_hash": certification.get("plan_hash"),
            "plan_revision": certification.get("plan_revision"),
            "action": certification.get("action"),
        }
        if any(metadata.get(field) != value for field, value in exact.items()):
            failures.append(f"{node_id}: manual approval metadata must match exact plan hash, revision, and action")
        if not isinstance(metadata.get("approved_by"), str) or not metadata["approved_by"].strip():
            failures.append(f"{node_id}: manual approval metadata requires approved_by")
        if not _is_iso_timestamp(metadata.get("approved_at")):
            failures.append(f"{node_id}: manual approval metadata requires ISO approved_at")
        return failures
    if kind == "tests":
        files = metadata.get("test_files")
        if not isinstance(files, list) or not files or any(
            not isinstance(path, str) or not path.strip() for path in files
        ):
            failures.append(f"{node_id}: test_files must be a nonempty string list")
            files = []
        hashes = metadata.get("test_sha256")
        if not isinstance(hashes, dict) or set(hashes) != set(files) or any(
            not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value)
            for value in hashes.values()
        ):
            failures.append(f"{node_id}: test_sha256 must map every test file to a SHA-256 hex digest")
        command = metadata.get("test_command")
        if not isinstance(command, str) or not command.strip():
            failures.append(f"{node_id}: test_command must be a nonempty string")
        red_code = metadata.get("red_exit_code")
        if type(red_code) is not int or red_code == 0:
            failures.append(f"{node_id}: red_exit_code must be a nonzero integer")
    elif kind in {"build", "integration"}:
        for field in ("targeted_exit_code", "regression_exit_code"):
            if type(metadata.get(field)) is not int or metadata.get(field) != 0:
                failures.append(f"{node_id}: {field} must be integer 0")
    elif kind in {"review", "judge", "grok-review"}:
        if metadata.get("findings") != []:
            failures.append(f"{node_id}: findings must be an empty list")
    return failures


def _runner_snapshot(board, runner):
    """Test seam only. Production certification uses one SQLite snapshot."""
    rows = runner(["kanban", "--board", board, "list", "--json"])
    details = {}
    for row in rows:
        task_id = row.get("id") if isinstance(row, dict) else None
        if task_id:
            details[task_id] = runner(["kanban", "--board", board, "show", task_id, "--json"])
    return {"rows": rows, "details": details}


def _atomic_board_snapshot(board):
    """Read tasks and latest run metadata from one SQLite read transaction."""
    boards = _hermes_runner(["kanban", "boards", "list", "--json"])
    match = next((item for item in boards if item.get("slug") == board), None)
    if not match or not match.get("db_path"):
        raise ValueError(f"board not found or has no db_path: {board}")
    db_path = str(Path(match["db_path"]).resolve())
    source = sqlite3.connect(db_path)
    source.execute("PRAGMA query_only=ON")
    conn = sqlite3.connect(":memory:")
    source.backup(conn)
    source.close()
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(row) for row in conn.execute(
            "SELECT id, title, body, status FROM tasks WHERE status != 'archived' ORDER BY id"
        )]
        run_rows = conn.execute(
            """
            SELECT r.task_id, r.metadata
              FROM task_runs r
              JOIN (SELECT task_id, MAX(id) AS id FROM task_runs GROUP BY task_id) latest
                ON latest.id = r.id
            """
        ).fetchall()
        metadata = {}
        for row in run_rows:
            try:
                metadata[row["task_id"]] = json.loads(row["metadata"]) if row["metadata"] else {}
            except (TypeError, json.JSONDecodeError):
                metadata[row["task_id"]] = {}
        details = {
            row["id"]: {"task": row, "runs": [{"metadata": metadata.get(row["id"], {})}]}
            for row in rows
        }
        return {"rows": rows, "details": details}
    finally:
        conn.close()


def certify_manifest(manifest, runner=None, snapshot=None):
    """Deterministically deny release unless every node has required evidence."""
    failures = []
    if type(manifest.get("version")) is not int or manifest.get("version") not in {1, 3}:
        failures.append("manifest version must equal 1 or 3")
    plan = manifest.get("plan")
    try:
        validate_plan(plan)
        expected_graph = build_graph(plan)
    except (TypeError, ValueError) as exc:
        return {"verdict": "FAIL", "checked": 0, "failures": [f"invalid plan: {exc}"], "plan_hash": None}
    graph = manifest.get("graph") or {}
    if graph != expected_graph:
        failures.append("embedded graph does not match the validated plan")
    board = manifest.get("board")
    task_ids = manifest.get("task_ids") or {}
    expected_node_ids = [node["id"] for node in expected_graph["nodes"]]
    if set(task_ids) != set(expected_node_ids):
        failures.append("task-id keys do not exactly match expected graph nodes")
    values = list(task_ids.values())
    if any(not isinstance(value, str) or not value for value in values) or len(values) != len(set(values)):
        failures.append("task ids must be nonempty and unique")
    if not isinstance(board, str) or not board:
        failures.append("manifest board is required")
    if failures:
        return {
            "verdict": "FAIL", "checked": 0, "failures": failures,
            "plan_hash": expected_graph["plan_hash"],
        }

    # Production takes one immutable SQLite read snapshot. The injected runner
    # exists only for deterministic unit-test seams.
    snapshot = snapshot or (_runner_snapshot(board, runner) if runner else _atomic_board_snapshot(board))
    rows = snapshot["rows"]
    plan_hash = expected_graph["plan_hash"]
    bound_rows = {
        row.get("id"): row for row in rows
        if isinstance(row, dict)
        and f"plan_hash: {plan_hash}" in (row.get("body") or "")
    }
    if set(bound_rows) != set(values):
        failures.append("live plan-hash task set does not exactly match manifest task ids")
    expected_nodes = {node["id"]: node for node in expected_graph["nodes"]}
    for node_id, task_id in task_ids.items():
        row = bound_rows.get(task_id)
        if row is None:
            continue
        if row.get("title") != node_id or row.get("body") != _task_body(expected_nodes[node_id], plan_hash):
            failures.append(f"{node_id}: live task body/title does not exactly match expected graph")
    if failures:
        return {
            "verdict": "FAIL", "checked": 0, "failures": failures,
            "plan_hash": plan_hash,
        }

    checked = 0
    for node in expected_graph["nodes"]:
        node_id = node["id"]
        task_id = task_ids.get(node_id)
        detail = snapshot["details"].get(task_id) or {}
        checked += 1
        task = detail.get("task") or {}
        body = task.get("body") or ""
        if task.get("id") != task_id or task.get("title") != node_id:
            failures.append(f"{node_id}: live task identity mismatch")
        expected_body = _task_body(expected_nodes[node_id], plan_hash)
        if body != expected_body:
            failures.append(f"{node_id}: live task body does not exactly match expected graph")
        if task.get("status") != "done":
            failures.append(f"{node_id}: task is not done")
            continue
        runs = detail.get("runs") or []
        metadata = (runs[-1].get("metadata") or {}) if runs else {}
        if node_id == "app.anchor" and metadata.get("plan_hash") != plan_hash:
            failures.append(f"{node_id}: anchor metadata plan_hash mismatch")
        failures.extend(_metadata_failures(node_id, metadata, expected_nodes[node_id]))
    return {
        "verdict": "PASS" if not failures else "FAIL",
        "checked": checked,
        "failures": failures,
        "plan_hash": plan_hash,
    }


def _topo_order(graph):
    nodes = _validate_graph_parents(graph)
    order, seen, visiting = [], set(), set()

    def visit(node_id):
        if node_id in visiting:
            raise ValueError(f"graph has a cycle at {node_id}")
        if node_id in seen:
            return
        visiting.add(node_id)
        for parent in nodes[node_id]["parents"]:
            visit(parent)
        visiting.remove(node_id)
        seen.add(node_id)
        order.append(node_id)

    for node_id in sorted(nodes):
        visit(node_id)
    return order


def _validate_graph_parents(graph):
    raw_nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if not isinstance(raw_nodes, list):
        _fail("graph.nodes must be a list")
    nodes = {}
    for node in raw_nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            _fail("graph nodes must have string ids")
        if node["id"] in nodes:
            _fail(f"duplicate graph node id: {node['id']}")
        parents = node.get("parents")
        if not isinstance(parents, list):
            _fail(f"{node['id']}: parents must be a list")
        nodes[node["id"]] = node
    for node in raw_nodes:
        for parent in node["parents"]:
            if parent not in nodes:
                _fail(f"{node['id']}: unresolved parent {parent}")
    return nodes


def _hermes_runner(args):
    """Default runner: invokes the Hermes CLI."""
    result = subprocess.run(
        ["hermes"] + args, capture_output=True, text=True, timeout=600
    )
    if result.returncode != 0:
        raise ValueError(f"hermes {' '.join(args)} failed: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": True, "output": result.stdout}


# ---------------------------------------------------------------- conductor IO

_FENCE_RE = re.compile(r"```(?:json)?\s*\n(.*?)```", re.DOTALL)


def extract_json_object(raw):
    """Parse the first JSON object from model output, tolerating fences and
    session footers/headers."""
    if not isinstance(raw, str):
        _fail("expected raw session text")
    for match in _FENCE_RE.finditer(raw):
        candidate = match.group(1).strip()
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char == "{":
            try:
                obj, _ = decoder.raw_decode(raw[index:])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    _fail("no JSON object found in session output")


def conductor_command(prompt):
    """Exact command used to drive the default Terra coordinator profile."""
    return ["hermes", "--profile", "default", "chat", "-q", prompt, "--quiet"]


def _conductor_call(prompt):
    result = subprocess.run(
        conductor_command(prompt), capture_output=True, text=True, timeout=1800,
    )
    return result.stdout


def _write_plan(plan, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2) + "\n")
    return output


def bind_route_to_plan(plan, task, route):
    """Bind a validated route decision into a v3 app plan."""
    if not isinstance(plan, dict) or not isinstance(task, dict) or not isinstance(route, dict):
        _fail("plan, task, and route must be JSON objects")
    if route.get("task_hash") != _sha256_json(task):
        _fail("route task_hash does not match task")
    bound = json.loads(json.dumps(plan))
    bound["version"] = 3
    bound["policy_version"] = DEFAULT_POLICY_VERSION
    bound.setdefault("app", {})["sensitivity"] = route["sensitivity"]
    bound["task"] = {
        "task_id": route["task_id"],
        "attempt": route["attempt"],
        "task_hash": route["task_hash"],
    }
    bound["route"] = route
    bound["limits"] = dict(route["limits"])
    validate_plan(bound)
    return bound


def cmd_draft(args):
    plan = _draft_plan(args.app_id, args.goal, args.repo, args.sensitivity)
    if getattr(args, "task_file", None):
        task = json.loads(args.task_file.read_text())
        route = route_task(task, today=getattr(args, "today", None))
        plan = bind_route_to_plan(plan, task, route)
    _write_plan(plan, args.output)
    print(json.dumps(plan, indent=2))
    return 0


def _draft_plan(app_id, goal, repo, sensitivity="internal"):
    raw = _conductor_call(
        f"Produce a versioned JSON plan (version, app{{id,title,acceptance,"
        f"sensitivity,repo}}, features each with acceptance and units each with "
        f"acceptance, plus limits{{max_tasks}}) for app id '{app_id}' targeting repo '{repo}' and this "
        f"goal: {goal}. Sensitivity must be {sensitivity} (public or internal). "
        "Output the JSON in a fenced json block."
    )
    plan = extract_json_object(raw)
    plan.setdefault("app", {})["id"] = app_id
    plan.setdefault("app", {})["repo"] = repo
    plan["app"]["sensitivity"] = sensitivity
    plan.setdefault("limits", {})["max_tasks"] = plan.get("limits", {}).get("max_tasks", 200)
    validate_plan(plan)
    return plan


def cmd_plan(args):
    plan = json.loads(args.plan_file.read_text())
    graph = build_graph(plan)
    print(json.dumps(graph, indent=2))
    return 0


def cmd_route(args):
    task = json.loads(args.task_file.read_text())
    route = route_task(task, today=args.today)
    print(json.dumps(route, indent=2, sort_keys=True))
    return 0


def cmd_apply(args):
    plan = json.loads(args.plan_file.read_text())
    graph = build_graph(plan)
    result = apply_graph(graph, args.board, apply=args.apply, dispatch=args.dispatch)
    if args.apply:
        manifest_path = args.manifest or args.plan_file.with_suffix(".swarm.json")
        write_manifest(manifest_path, args.board, plan, graph, result)
        result["manifest"] = str(manifest_path)
    print(json.dumps(result, indent=2))
    return 0


def cmd_launch(args):
    """Conductor entrypoint: draft, apply, and start the durable graph."""
    plan = _draft_plan(args.app_id, args.goal, args.repo, args.sensitivity)
    if getattr(args, "task_file", None):
        task = json.loads(args.task_file.read_text())
        route = route_task(task, today=getattr(args, "today", None))
        plan = bind_route_to_plan(plan, task, route)
    _write_plan(plan, args.output)
    graph = build_graph(plan)
    applied = apply_graph(graph, args.board, apply=True, dispatch=True)
    manifest_path = getattr(args, "manifest", None) or args.output.with_suffix(".swarm.json")
    write_manifest(manifest_path, args.board, plan, graph, applied)
    applied["manifest"] = str(manifest_path)
    final_node = (
        "app.manual-approval" if "app.manual-approval" in applied["task_ids"] else
        "app.astra-acceptance" if "app.astra-acceptance" in applied["task_ids"] else
        "app.judge"
    )
    print(json.dumps({"apply": applied, "final_gate_task": applied["task_ids"][final_node]}, indent=2))
    return 0


def cmd_certify(args):
    manifest = json.loads(args.manifest.read_text())
    result = certify_manifest(manifest)
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS" else 1


def build_parser():
    """Parser matching the documented flags."""
    parser = argparse.ArgumentParser(prog="recursive_swarm")
    sub = parser.add_subparsers(dest="command", required=True)

    p_draft = sub.add_parser("draft")
    p_draft.add_argument("--app-id", required=True)
    p_draft.add_argument("--goal", required=True)
    p_draft.add_argument("--repo", required=True)
    p_draft.add_argument("--output", required=True, type=Path)
    p_draft.add_argument("--sensitivity", default="internal",
                         choices=["public", "internal"])
    p_draft.add_argument("--task-file", type=Path,
                         help="optional routing task JSON; binds the draft as a v3 plan")
    p_draft.add_argument("--today", help="ISO date override for deterministic registry checks")

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--plan-file", required=True, type=Path)

    p_route = sub.add_parser("route")
    p_route.add_argument("--task-file", required=True, type=Path)
    p_route.add_argument("--today", help="ISO date override for deterministic registry checks")

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--plan-file", required=True, type=Path)
    p_apply.add_argument("--board", default="recursive-swarm")
    p_apply.add_argument("--apply", action="store_true",
                         help="mutate the board (dry-run is the default)")
    p_apply.add_argument("--dispatch", action="store_true")
    p_apply.add_argument("--manifest", type=Path)

    p_launch = sub.add_parser("launch")
    p_launch.add_argument("--app-id", required=True)
    p_launch.add_argument("--goal", required=True)
    p_launch.add_argument("--repo", required=True)
    p_launch.add_argument("--output", required=True, type=Path)
    p_launch.add_argument("--sensitivity", default="internal",
                          choices=["public", "internal"])
    p_launch.add_argument("--task-file", type=Path,
                          help="optional routing task JSON; binds the launch as a v3 plan")
    p_launch.add_argument("--today", help="ISO date override for deterministic registry checks")
    p_launch.add_argument("--board", default="recursive-swarm")
    p_launch.add_argument("--manifest", type=Path)

    p_certify = sub.add_parser("certify")
    p_certify.add_argument("--manifest", required=True, type=Path)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "draft":
        return cmd_draft(args)
    if args.command == "plan":
        return cmd_plan(args)
    if args.command == "route":
        return cmd_route(args)
    if args.command == "apply":
        return cmd_apply(args)
    if args.command == "launch":
        return cmd_launch(args)
    return cmd_certify(args)


if __name__ == "__main__":
    raise SystemExit(main())
