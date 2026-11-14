#!/usr/bin/env python3
"""Offline planner for the Hermes engineering swarm v2.

Reads a task description and policy.json, and emits a concrete, acyclic task
graph with tier/model assignments, budget checks, a critical-path dispatch
order and the Hermes Kanban card shapes the controller would create.

It makes no API calls, creates no Hermes tasks, reads no credentials and
establishes no spending authority. Stage 2 and stage 3 of the router (the
local classifier and the coordination model) are represented offline by
`opinions` supplied in the task JSON, so the disagreement logic is testable
without a model.

Usage:
    python3 router.py task.json [--policy policy.json] [--today YYYY-MM-DD]
                      [--attempt N] [--out route.json] [--mode easy|medium|hard|expert]

Operating modes (spec §0, policy.json `modes`): easy / medium / hard / expert
are RIGOR levels, not model rosters. The mode may only raise rigor, width,
budget/time ceilings or gates; it never removes a mandatory recipe, premium
gate, human interrupt, secret rule, idempotency rule or verification
requirement. Model selection is fully decoupled from the mode: every tier is
filled from the tier registry and dispatched on the model's own provider
account. A user-selected mode is a floor, not a ceiling — the router may raise
it (from task type, effort, missing reproduction, cross-module or prior
failures) but never lowers it. Safety flags (critical, payments, secrets,
destructive, pii, prod, external-writes) win over the mode and always add
their +G / +H gates.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import re
import sys
from copy import deepcopy
from typing import Any

EFFORTS = ["E0", "E1", "E2", "E3", "E4"]
MODIFIER_ORDER = "EPGHV"
CRITICAL_ROWS = ("T7", "T11")  # critical by construction (spec §3)
MODEL_NODES = {"EVID", "REPRO", "CON", "PCON", "TD", "IM", "RV", "PRE", "PACC"}
CONTROLLER_NODES = {"ROUTE", "SPLIT", "CK", "INT", "VER", "DEL"}
HUMAN_NODES = {"HUM"}
# Time phases (spec §4, §9). The item's time ceiling applies to IMPLEMENTATION_NODES only.
# Reproduction (+P) is planning time with its own ceiling of the same size as the item's.
PLANNING_NODES = {"ROUTE", "EVID", "REPRO", "CON", "PCON", "SPLIT"}
IMPLEMENTATION_NODES = {"TD", "IM", "RV", "CK", "INT", "VER", "DEL"}
GATE_NODES = {"PACC", "PRE", "HUM"}


class PolicyError(Exception):
    """The policy or task is malformed."""


class RouteRefused(Exception):
    """The planner refuses to produce a dispatchable plan."""

    def __init__(self, status: str, payload: dict[str, Any]):
        super().__init__(status)
        self.status = status
        self.payload = payload


@dataclasses.dataclass
class PlanContext:
    """Policy plus the active availability mode; carries the substitution log."""

    policy: dict[str, Any]
    mode: str
    mode_cfg: dict[str, Any]
    substitutions: list[dict[str, Any]] = dataclasses.field(default_factory=list)


# --------------------------------------------------------------------------- loading

def load_policy(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_task(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- helpers

def effort_index(effort: str) -> int:
    if effort not in EFFORTS:
        raise PolicyError(f"unknown effort {effort!r}")
    return EFFORTS.index(effort)


def max_effort(a: str, b: str) -> str:
    return a if effort_index(a) >= effort_index(b) else b


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a CODEOWNERS-style glob to a regex. `**` spans directories, `*` does not."""
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    body = "".join(out)
    # A pattern without a slash matches a basename anywhere in the tree.
    if "/" not in pattern:
        return re.compile(rf"(?:^|.*/){body}$")
    return re.compile(rf"^{body}$")


def match_path(pattern: str, path: str) -> bool:
    return glob_to_regex(pattern).match(path.replace("\\", "/")) is not None


def canonical_modifiers(mods) -> str:
    return "".join(m for m in MODIFIER_ORDER if m in set(mods))


def cell_code(family: str, mods) -> str:
    m = canonical_modifiers(mods)
    return f"{family}+{m}" if m else family


def parse_cell(cell: str) -> tuple[str, set[str]]:
    m = re.fullmatch(r"(R[0-4]|RE)(?:\+([EPGHV]+))?", cell)
    if not m:
        raise PolicyError(f"unparseable cell {cell!r}")
    return m.group(1), set(m.group(2) or "")


# --------------------------------------------------------------------------- stage 1

def stage1_classify(task: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Deterministic classification from paths, keywords and signals. Costs nothing."""
    files = [f.replace("\\", "/") for f in task.get("files", [])]
    text = f"{task.get('title', '')} {task.get('description', '')}".lower()
    signals = task.get("signals", {})
    rationale: list[str] = []

    # Path -> type and flags
    path_types: dict[str, int] = {}
    flags: set[str] = set()
    for entry in policy["impact_map"]:
        pattern = entry["pattern"]
        matched = [f for f in files if match_path(pattern, f)]
        if not matched:
            continue
        if entry.get("only_if_all_files_match") and len(matched) != len(files):
            continue
        for fl in entry.get("flags", []):
            flags.add(fl)
        if entry.get("task_type"):
            path_types[entry["task_type"]] = path_types.get(entry["task_type"], 0) + len(matched)
            rationale.append(f"path {pattern} -> {entry['task_type']} {entry.get('flags', [])}")

    path_type = None
    for t in policy["type_precedence"]:
        if t in path_types:
            path_type = t
            break
    if path_type is None and path_types:
        path_type = max(path_types, key=path_types.get)

    # Keywords -> type
    keyword_type = None
    for rule in policy["keyword_rules"]:
        if any(k in text for k in rule["any"]):
            keyword_type = rule["task_type"]
            rationale.append(f"keyword {rule['any']} -> {keyword_type}")
            break

    # Decide type. Path-derived critical/high rows win; otherwise keywords; otherwise path.
    if path_type in policy["type_precedence"]:
        task_type, type_source = path_type, "path"
    elif keyword_type:
        task_type, type_source = keyword_type, "keyword"
    elif path_type:
        task_type, type_source = path_type, "path"
    else:
        task_type, type_source = None, None

    inconclusive = task_type is None

    # Flags: defaults for the type, requester flags (known ones), environment.
    if task_type:
        flags.update(policy["task_types"][task_type].get("default_flags", []))
    for fl in task.get("requester_flags", []):
        if fl in policy["flags_known"]:
            flags.add(fl)
    if str(task.get("environment", "")).lower() in ("prod", "production"):
        flags.add("prod")

    effort, effort_rationale = estimate_effort(signals, files, task_type, policy)
    rationale.extend(effort_rationale)

    # Row floor and requester hint (raise only).
    if task_type:
        floor = policy["task_types"][task_type].get("min_effort", "E0")
        if effort_index(floor) > effort_index(effort):
            rationale.append(f"row floor {task_type} >= {floor}")
            effort = floor
    hint = task.get("effort_hint")
    if hint in EFFORTS and effort_index(hint) > effort_index(effort):
        rationale.append(f"requester raised effort to {hint}")
        effort = hint

    return {
        "task_type": task_type,
        "type_source": type_source,
        "path_derived_type": path_type,
        "effort": effort,
        "flags": sorted(flags),
        "rationale": rationale,
        "inconclusive": inconclusive,
    }


def estimate_effort(signals: dict[str, Any], files: list[str], task_type: str | None,
                    policy: dict[str, Any]) -> tuple[str, list[str]]:
    h = policy["effort_heuristics"]
    n_files = len(files) if files else int(signals.get("files_touched", 0) or 0)
    lines = int(signals.get("estimated_changed_lines", 0) or 0)
    why: list[str] = []
    if any(signals.get(s) for s in h["E4_triggers"]):
        why.append("E4: design or ambiguity trigger")
        return "E4", why
    if any(signals.get(s) for s in h["E3_triggers"]) or n_files > h["E3_thresholds"]["files_gt"] \
            or lines > h["E3_thresholds"]["changed_lines_gt"]:
        why.append("E3: cross-module/concurrency trigger or size over E2 thresholds")
        return "E3", why
    e2 = h["E2_thresholds"]
    if n_files > e2["files_gt"] or lines > e2["changed_lines_gt"] or any(signals.get(s) for s in e2["or_signals"]):
        why.append("E2: several files, interface change, or independent test design needed")
        return "E2", why
    e1 = h["E1_thresholds"]
    if lines > e1["changed_lines_gt"] or any(signals.get(s) for s in e1["or_signals"]) \
            or not signals.get("mechanical", False):
        why.append("E1: small non-mechanical change")
        return "E1", why
    why.append("E0: mechanical and deterministic")
    return "E0", why


# --------------------------------------------------------------------------- stages 2 and 3 (offline)

def apply_opinions(stage1: dict[str, Any], task: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Merge offline stage-2/stage-3 opinions under the never-lower rules."""
    route = deepcopy(stage1)
    route["stage"] = "1"
    route["stage3_required"] = False
    opinions = task.get("opinions", {}) or {}
    s2, s3 = opinions.get("stage2"), opinions.get("stage3")
    g_flags = set(policy["flag_effects"]["G"])
    flags = set(route["flags"])
    floor_effort = route["effort"]
    path_locked = route["path_derived_type"] in policy["type_precedence"]

    def adopt(op: dict[str, Any], stage: str) -> None:
        nonlocal flags
        if op.get("task_type") and not path_locked:
            route["task_type"] = op["task_type"]
            route["type_source"] = f"stage{stage}"
        if op.get("effort") in EFFORTS:
            proposed = op["effort"]
            # Critical rows: never below the stage-1 floor. Others: opinions may lower to the row floor.
            if route["task_type"] in CRITICAL_ROWS:
                proposed = max_effort(proposed, floor_effort)
            row_floor = policy["task_types"][route["task_type"]].get("min_effort", "E0") if route["task_type"] else "E0"
            route["effort"] = max_effort(proposed, row_floor)
        for fl in op.get("flags", []) or []:
            if fl in policy["flags_known"]:
                flags.add(fl)
        route["stage"] = stage
        route["rationale"].append(f"stage {stage}: {op.get('rationale', 'opinion adopted')}")

    if route["inconclusive"]:
        if s2 and s2.get("task_type"):
            adopt(s2, "2")
            route["inconclusive"] = False
        else:
            route["stage3_required"] = True

    disagreement = bool(s2) and (
        (s2.get("task_type") and s2["task_type"] != route["task_type"])
        or (s2.get("effort") and s2["effort"] != route["effort"])
    )
    if route["task_type"]:
        flags.update(policy["task_types"][route["task_type"]].get("default_flags", []))
    critical = bool(flags & g_flags)
    need_s3 = disagreement or effort_index(route["effort"]) >= 3 or critical or route["stage3_required"]

    if need_s3:
        if s3:
            adopt(s3, "3")
            route["stage3_required"] = False
        else:
            route["stage3_required"] = True
            # Conservative merge: the higher of stage 1 and stage 2 efforts, stage-1 type.
            if s2 and s2.get("effort") in EFFORTS:
                route["effort"] = max_effort(route["effort"], s2["effort"])
            route["rationale"].append("stage 3 required (disagreement, E3+, or critical flag); no opinion supplied, conservative merge used")

    if route["task_type"] is None:
        raise RouteRefused("unclassified", {"reason": "no path, keyword or opinion determined a task type", "route": route})

    # Flags never shrink.
    flags.update(stage1["flags"])
    route["flags"] = sorted(flags)
    return route


# --------------------------------------------------------------------------- matrix

def resolve_cell(task_type: str, effort: str, flags, policy: dict[str, Any],
                 signals: dict[str, Any] | None = None) -> dict[str, Any]:
    signals = signals or {}
    history: list[dict[str, str]] = []
    t, e = task_type, effort
    for _ in range(4):
        cell = policy["matrix"][t][e]
        if cell.startswith("^"):
            new_e = cell[1:]
            history.append({"from": f"{t}.{e}", "rule": cell, "to": f"{t}.{new_e}"})
            e = new_e
            continue
        if cell == "->reroute":
            return {"status": "reroute_required", "task_type": t, "effort": e, "history": history,
                    "reason": "request described as one kind of work but sized like another; reclassify"}
        if cell.startswith("->"):
            targets = cell[2:].split("|")
            if len(targets) == 1:
                new_t = targets[0]
            else:
                choice = policy["reroute_choice"]["|".join(targets)]
                new_t = choice["true"] if signals.get(choice["signal"]) else choice["false"]
            history.append({"from": f"{t}.{e}", "rule": cell, "to": f"{new_t}.{e}"})
            t = new_t
            continue
        family, mods = parse_cell(cell)
        tt = policy["task_types"][t]
        mods |= set(tt.get("modifiers", []))
        mods |= set(tt.get("modifiers_by_effort", {}).get(e, []))
        for mod, cond in tt.get("conditional_modifiers", {}).items():
            if cond.startswith("flag:") and cond[5:] in set(flags):
                mods.add(mod)
        for mod, trig in policy["flag_effects"].items():
            if set(flags) & set(trig):
                mods.add(mod)
        mods |= set(policy["route_templates"][family].get("forces_modifiers", []))
        # Modifiers only make sense with the nodes they attach to.
        if family == "RE":
            mods -= {"P", "G"}
        return {"status": "ok", "task_type": t, "effort": e, "family": family, "modifiers": canonical_modifiers(mods),
                "cell": cell_code(family, mods), "matrix_cell": cell, "history": history}
    raise PolicyError(f"re-route loop for {task_type}.{effort}")


# --------------------------------------------------------------------------- models, tiers and modes

def model_info(model_id: str, policy: dict[str, Any]) -> dict[str, Any]:
    try:
        return policy["registry"][model_id]
    except KeyError as exc:
        raise PolicyError(f"model {model_id!r} not in registry") from exc


def _pick_ctx(policy: dict[str, Any], mode: str, mode_cfg: dict[str, Any],
              subs: list[dict[str, Any]]) -> PlanContext:
    return PlanContext(policy=policy, mode=mode, mode_cfg=mode_cfg, substitutions=subs)


MODE_RANK = {"easy": 0, "medium": 1, "hard": 2, "expert": 3}
# Task types that force expert rigor (spec §0 rule 4): foundational architecture,
# security/data/schema, policy/routing. T8 is expert only when it carries the
# critical flag (checked via the resolved flags, not here).
EXPERT_TASK_TYPES = ("T7", "T11", "T13", "T14")
# Task types that are normal code changes -> medium floor (spec §0 rule 2).
CODE_TASK_TYPES = ("T2", "T3", "T5", "T6", "T8", "T9", "T12")
# Mechanical/research rows that stay at the easy floor (spec §0 rule 1).
EASY_TASK_TYPES = ("T1", "T4", "T10")


def _registry_candidates(tier: str, policy: dict[str, Any]) -> list[str]:
    """The tier's candidate list. Model selection is decoupled from the mode, so this
    is always the tier registry's candidates (enabled only)."""
    return [m for m in policy["tiers"][tier].get("candidates", []) if model_info(m, policy).get("enabled", True)]


def _pick(ctx: PlanContext, tier: str, role: str, exclude_family: str | None = None) -> str:
    """Pick a registered model for a tier/role from the tier registry. The mode never
    constrains the model here; only the `different_family` review rule can fall up a
    tier. Fails closed if no candidate fits the family exclusion."""
    roles = ctx.policy["tiers"][tier].get("roles", {})
    named = roles.get(role)
    if named and named != "different_family" and model_info(named, ctx.policy).get("enabled", True):
        if exclude_family is None or model_info(named, ctx.policy)["family"] != exclude_family:
            return named
    for m in _registry_candidates(tier, ctx.policy):
        if exclude_family is None or model_info(m, ctx.policy)["family"] != exclude_family:
            return m
    # Fall back one tier up rather than reviewing with the same family.
    order = ["L", "F", "M", "H", "P"]
    idx = order.index(tier)
    if idx + 1 < len(order):
        return _pick(ctx, order[idx + 1], role, exclude_family)
    raise PolicyError(
        f"no enabled model in tier {tier} for role {role}"
        + (f" outside family {exclude_family}" if exclude_family else "")
        + "; the plan fails closed")


def _record_substitution(ctx: PlanContext, role: str, tier: str, preferred: str, chosen: str, reason: str) -> None:
    if preferred == chosen:
        return
    ctx.substitutions.append({"role": role, "tier": tier, "preferred": preferred,
                              "chosen": chosen, "mode": ctx.mode, "reason": reason})


def pick_model(tier: str, role: str, policy: dict[str, Any], exclude_family: str | None = None,
               ctx: PlanContext | None = None) -> str:
    """Backward-compatible entry point. Model selection is always from the tier
    registry; the mode never constrains it."""
    ctx = ctx or _pick_ctx(policy, policy.get("modes", {}).get("default", "easy"), {}, [])
    return _pick(ctx, tier, role, exclude_family)


def premium_model(ctx: PlanContext) -> str:
    """The premium judge: the declared P judge from the tier registry. The mode never
    changes the model; if the P judge is disabled the declared alternate is used and
    logged."""
    p = ctx.policy["tiers"]["P"]
    named = p["roles"]["judge"]
    if model_info(named, ctx.policy).get("enabled", True):
        return named
    alt = p.get("alternate")
    if alt and model_info(alt, ctx.policy).get("enabled", True):
        _record_substitution(ctx, "judge", "P", named, alt,
                             f"P judge {named} disabled; declared alternate {alt} (logged, never silent)")
        return alt
    raise PolicyError("premium judge disabled with no enabled declared alternate; the plan fails closed")


def coordination_model(ctx: PlanContext) -> str:
    """Stage-3 planning/coordination model from the tier registry (spec §2.2 stage 3)."""
    model = ctx.policy["tiers"]["H"].get("coordination", "gpt-5.6-sol")
    if model != "gpt-5.6-sol":
        raise PolicyError("H coordination must use gpt-5.6-sol")
    return model


def dispatch_spec(ctx: PlanContext, model_id: str) -> dict[str, str] | None:
    """Explicit offline dispatch contract, including model-specific reasoning."""
    target = dispatch_target(ctx, model_id)
    if target is None:
        return None
    provider, model = target
    result = {"provider": provider, "model": model}
    effort = model_info(model_id, ctx.policy).get("hermes", {}).get("reasoning_effort")
    if effort:
        result["reasoning_effort"] = effort
    if model_id == "gpt-5.6-sol" and result != {
            "provider": "openai-codex", "model": "gpt-5.6-sol", "reasoning_effort": "high"}:
        raise PolicyError("Sol dispatch must use ChatGPT openai-codex at high reasoning")
    return result


def coordination_dispatch(ctx: PlanContext) -> dict[str, str]:
    spec = dispatch_spec(ctx, coordination_model(ctx))
    if spec is None:
        raise PolicyError("H coordination has no dispatch route")
    declared = ctx.policy["tiers"]["H"].get("coordination_dispatch", spec)
    if declared != spec:
        raise PolicyError("H coordination dispatch disagrees with registry")
    return spec


def mode_roles(ctx: PlanContext) -> dict[str, str]:
    """Read-only report of the tier-registry roles actually in play (no substitution
    log writes). The mode does not alter these — model selection is decoupled from it."""
    return {"coordination_model": coordination_model(ctx),
            "coordination_dispatch": coordination_dispatch(ctx),
            "premium_judge": ctx.policy["tiers"]["P"]["roles"]["judge"]}


def dispatch_target(ctx: PlanContext, model_id: str) -> tuple[str, str] | None:
    """(provider, model) to dispatch on. Model selection is decoupled from the mode, so
    every model dispatches on its own provider account. Returns None only if the entry
    has no usable hermes model (malformed registry) — the plan then fails closed."""
    entry = model_info(model_id, ctx.policy)
    hermes = entry.get("hermes", {})
    if not hermes.get("model"):
        return None
    return entry.get("provider"), hermes["model"]


def mode_rank(mode: str) -> int:
    if mode not in MODE_RANK:
        raise PolicyError(f"unknown mode {mode!r} (available: {', '.join(MODE_RANK)})")
    return MODE_RANK[mode]


def rank_name(rank: int) -> str:
    for name, r in MODE_RANK.items():
        if r == rank:
            return name
    raise PolicyError(f"unknown mode rank {rank!r}")


def derive_mode(task_type: str, effort: str, flags: set[str], signals: dict[str, Any]) -> str:
    """The rigor level the task TYPE/FLAGS warrant (spec §0 rules 1-4). This is a floor
    the user may raise but not lower.

    - expert: T7/T11/T13/T14, or critical T8 (rule 4)
    - hard:   E3 predicted, bug with no reproduction, cross-module, concurrency, or a
              new design (rule 3)
    - medium: normal code change (rule 2)
    - easy:   mechanical, test, or research work (rule 1)
    """
    sig = signals or {}
    if task_type in EXPERT_TASK_TYPES:
        return "expert"
    if task_type == "T8" and "critical" in flags:
        return "expert"
    no_repro_bug = task_type == "T3" or (task_type == "T2" and sig.get("has_reproduction") is False)
    if effort in ("E3", "E4") or no_repro_bug or sig.get("cross_module") or sig.get("concurrency") \
            or sig.get("new_design_needed") or "critical" in flags:
        return "hard"
    if task_type in CODE_TASK_TYPES:
        return "medium"
    return "easy"


def resolve_mode(task: dict[str, Any], policy: dict[str, Any], mode: str | None,
                 task_type: str, effort: str, flags: set[str]) -> dict[str, str]:
    """User mode is a floor, not a ceiling (rule 5). Effective = max(selected, derived).
    Never lowered. Returns selected/derived/effective with a raise reason."""
    modes = policy.get("modes", {})
    valid = {k for k, v in modes.items() if isinstance(v, dict) and "rank" in v}
    selected = mode or task.get("mode") or modes.get("default", "easy")
    if selected not in valid:
        raise PolicyError(f"unknown mode {selected!r} (available: {', '.join(sorted(valid))})")
    derived = derive_mode(task_type, effort, set(flags or []), task.get("signals", {}))
    selected_rank, derived_rank = MODE_RANK[selected], MODE_RANK[derived]
    if derived_rank > selected_rank:
        effective = derived
        reason = (f"{derived} rigor required by task type {task_type} / effort {effort} / flags "
                  f"{sorted(flags or [])}; user mode {selected} raised (floor, not ceiling)")
    else:
        effective = selected
        reason = None
    return {"selected": selected, "derived": derived, "effective": effective, "raise_reason": reason}


def check_registry_freshness(model_ids, policy: dict[str, Any], today: dt.date) -> list[str]:
    max_age = int(policy["scheduling"]["registry_max_age_days"])
    stale = []
    for m in sorted(set(model_ids)):
        checked = model_info(m, policy)["price"].get("checked_at")
        if not checked:
            stale.append(f"{m}: no checked_at")
            continue
        age = (today - dt.date.fromisoformat(checked)).days
        if age > max_age:
            stale.append(f"{m}: price checked {age} days ago (max {max_age})")
    return stale


# --------------------------------------------------------------------------- budget

def call_cost(model_id: str, tokens_in: int, tokens_out: int, policy: dict[str, Any]) -> float:
    price = model_info(model_id, policy)["price"]
    return tokens_in * price["input"] / 1e6 + tokens_out * price["output"] / 1e6


def gate_reserve_usd(effort: str, policy: dict[str, Any], ctx: PlanContext | None = None) -> float:
    lvl = policy["effort_levels"][effort]
    if lvl.get("gate_included_in_ceiling"):
        return 0.0
    static = float(lvl["gate_reserve_usd"])
    grm = policy["gate_reserve_model"]
    tokens = grm["expected_context_tokens"][effort]
    pctx = ctx or _pick_ctx(policy, policy.get("modes", {}).get("default", "easy"), {}, [])
    computed = grm["calls"] * call_cost(premium_model(pctx), tokens["in"], tokens["out"], policy) * grm["safety_factor"]
    return round(max(static, computed), 4)


def budget_plan(task: dict[str, Any], effort: str, modifiers: str, policy: dict[str, Any],
                first_model: str | None, ctx: PlanContext | None = None) -> dict[str, Any]:
    ctx = ctx or _pick_ctx(policy, policy.get("modes", {}).get("default", "easy"), {}, [])
    lvl = policy["effort_levels"][effort]
    ceiling = float(lvl["ceiling_usd"])
    reserve_fraction = float(policy["reservation"]["verification_recovery_fraction"])
    gate = gate_reserve_usd(effort, policy, ctx) if "G" in modifiers else 0.0
    tokens = policy["gate_reserve_model"]["expected_context_tokens"][effort]
    evidence = call_cost(pick_model("F", "evidence", policy, ctx=ctx), tokens["in"], tokens["out"], policy) if "E" in modifiers else 0.0
    planned_total = round(ceiling + gate + evidence, 4)

    limits = task.get("limits", {}) or {}
    provided = [float(v) for k, v in limits.items() if k in ("task_ceiling_usd", "project_remaining_usd", "daily_remaining_usd") and v is not None]
    effective_limit = min(provided) if provided else None

    next_call_upper = call_cost(first_model, tokens["in"], tokens["out"], policy) if first_model else 0.0
    spent = float(limits.get("spent_usd", 0.0) or 0.0)
    in_flight = float(limits.get("in_flight_reservations_usd", 0.0) or 0.0)
    predispatch_ok = effective_limit is None or (spent + in_flight + next_call_upper <= effective_limit)
    within = effective_limit is None or planned_total <= effective_limit

    return {
        "effort": effort,
        "implementation_ceiling_usd": ceiling,
        "verification_recovery_reservation_usd": round(ceiling * reserve_fraction, 4),
        "gate_reserve_usd": gate,
        "evidence_estimate_usd": round(evidence, 4),
        "planned_total_usd": planned_total,
        "effective_limit_usd": effective_limit,
        "within_limit": within,
        "next_call_upper_bound_usd": round(next_call_upper, 4),
        "predispatch_check": policy["reservation"]["predispatch_check"],
        "predispatch_check_ok": predispatch_ok,
        "spending_authority": "none granted by this planner; the user's existing limits always win",
    }


# --------------------------------------------------------------------------- graph expansion

def _duration(node: str, effort: str, policy: dict[str, Any]) -> int:
    table = policy["scheduling"]["node_duration_min"]
    val = table.get(node, 0)
    if isinstance(val, dict):
        return int(val.get(effort, 0))
    return int(val)


def expand_graph(task: dict[str, Any], attempt: int, resolved: dict[str, Any], policy: dict[str, Any],
                 ctx: PlanContext | None = None) -> dict[str, Any]:
    ctx = ctx or _pick_ctx(policy, policy.get("modes", {}).get("default", "easy"), {}, [])
    task_id = task["task_id"]
    family, mods, effort = resolved["family"], set(resolved["modifiers"]), resolved["effort"]
    template = policy["route_templates"][family]
    lvl = policy["effort_levels"][effort]
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[tuple[str, str]] = []

    def nid(node: str, item: int | None = None) -> str:
        return f"{task_id}:{attempt}:{node}" + (f"[{item}]" if item is not None else "")

    def add(node: str, tier: str | None, model: str | None, role: str, eff: str, item: int | None = None,
            **extra: Any) -> str:
        i = nid(node, item)
        if i in nodes:
            raise PolicyError(f"duplicate node id {i}")
        info = model_info(model, policy) if model else None
        lv = policy["effort_levels"][eff]
        nodes[i] = {
            "id": i, "node": node, "tier": tier, "model": model,
            "provider": info["provider"] if info else None,
            "family": info["family"] if info else None,
            "role": role, "effort": eff, "item": item,
            "duration_min": _duration(node, eff, policy),
            "hermes_limits": lv["hermes"] if node in MODEL_NODES else None,
            **extra,
        }
        return i

    def link(a: str, b: str) -> None:
        edges.append((a, b))

    route_id = add("ROUTE", None, None, "controller", effort)

    # Evidence-only family.
    if family == "RE":
        ev_model = pick_model("F", "evidence", policy, ctx=ctx)
        ev = add("EVID", "F", ev_model, "evidence", effort)
        rv = add("RV", "F", pick_model("F", "reviewer", policy, exclude_family=model_info(ev_model, policy)["family"], ctx=ctx),
                 "claims_check", effort)
        d = add("DEL", None, None, "controller", effort)
        link(route_id, ev); link(ev, rv); link(rv, d)
        return {"nodes": list(nodes.values()), "edges": [list(e) for e in edges], "items": 0}

    pre_contract: list[str] = []
    if "E" in mods:
        pre_contract.append(add("EVID", "F", pick_model("F", "evidence", policy, ctx=ctx), "evidence", effort))
    if "P" in mods:
        t = lvl["implementer_tier"] if lvl["implementer_tier"] != "P" else "H"
        pre_contract.append(add("REPRO", t, pick_model(t, "implementer", policy, ctx=ctx), "reproduce", effort))
    for p in pre_contract:
        link(route_id, p)

    # Contract node (R0 keeps the contract inline in the request).
    contract_id = None
    if family != "R0":
        if "G" in mods or family == "R4":
            contract_id = add("PCON", "P", premium_model(ctx), "premium_contract", effort, fresh_session=False)
        else:
            t = lvl["implementer_tier"]
            contract_id = add("CON", t, pick_model(t, "implementer", policy, ctx=ctx), "contract", effort)
        for p in (pre_contract or [route_id]):
            link(p, contract_id)
    head = contract_id or (pre_contract[-1] if pre_contract else route_id)
    if family == "R0" and pre_contract:
        head = pre_contract[-1]

    # Items.
    if family == "R4":
        split_id = add("SPLIT", None, None, "controller", effort)
        link(head, split_id)
        head = split_id
        items = task.get("items") or [{"name": f"item-{i+1}", "effort": "E2"} for i in range(int(task.get("planned_items", 3)))]
    else:
        items = [{"name": task.get("title", "item"), "effort": effort}]

    item_nodes = set(template["item_nodes"])
    ck_ids: list[str] = []
    for idx, item in enumerate(items):
        ie = item.get("effort", effort)
        if ie not in EFFORTS:
            raise PolicyError(f"item effort {ie!r}")
        ilvl = policy["effort_levels"][ie]
        item_idx = idx if family == "R4" else None
        impl_tier = ilvl["implementer_tier"] if ilvl["implementer_tier"] != "P" else "H"
        if impl_tier == "L" and task.get("signals", {}).get("local_available", True) is False:
            impl_tier = ilvl.get("implementer_alt_tier") or "F"
        impl_model = pick_model(impl_tier, "implementer", policy, ctx=ctx)
        im = add("IM", impl_tier, impl_model, "implement", ie, item_idx, owned_files=item.get("files"), name=item.get("name"))
        link(head, im)
        last = im
        td = None
        if "TD" in item_nodes:
            td_tier = ilvl.get("test_design_tier") or "F"
            td = add("TD", td_tier, pick_model(td_tier, "test_design", policy, ctx=ctx), "test_design", ie, item_idx)
            link(head, td)
        if "RV" in item_nodes:
            rv_tier = ilvl.get("reviewer_tier") or "F"
            rv_model = pick_model(rv_tier, "reviewer", policy, exclude_family=model_info(impl_model, policy)["family"], ctx=ctx)
            rv = add("RV", rv_tier, rv_model, "review", ie, item_idx, reviews=impl_model)
            link(im, rv)
            if td:
                link(td, rv)
            last = rv
        elif td:
            link(td, last)
        ck = add("CK", None, None, "controller", ie, item_idx)
        link(last, ck)
        ck_ids.append(ck)

    integ = add("INT", None, None, "controller", effort)
    for ck in ck_ids:
        link(ck, integ)
    ver = add("VER", None, None, "controller", effort, eval_replay=("V" in mods),
              recipe=policy["recipes"][policy["task_types"][resolved["task_type"]]["recipe"]])
    link(integ, ver)
    tail = ver
    if "G" in mods:
        pacc = add("PACC", "P", premium_model(ctx), "premium_acceptance", effort, fresh_session=True)
        link(tail, pacc)
        tail = pacc
    if "H" in mods:
        hum = add("HUM", "human", None, "human_interrupt", effort)
        link(tail, hum)
        tail = hum
    d = add("DEL", None, None, "controller", effort)
    link(tail, d)
    return {"nodes": list(nodes.values()), "edges": [list(e) for e in edges], "items": len(items) if family == "R4" else 1}


def topo_order(graph: dict[str, Any]) -> list[str]:
    ids = [n["id"] for n in graph["nodes"]]
    indeg = {i: 0 for i in ids}
    succ: dict[str, list[str]] = {i: [] for i in ids}
    for a, b in graph["edges"]:
        if a not in indeg or b not in indeg:
            raise PolicyError(f"edge references unknown node: {a} -> {b}")
        indeg[b] += 1
        succ[a].append(b)
    ready = [i for i in ids if indeg[i] == 0]
    out: list[str] = []
    while ready:
        n = ready.pop(0)
        out.append(n)
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    if len(out) != len(ids):
        raise PolicyError("graph has a cycle")
    return out


def critical_path_order(graph: dict[str, Any]) -> dict[str, Any]:
    """Longest-remaining-path-first dispatch order (G9)."""
    by_id = {n["id"]: n for n in graph["nodes"]}
    succ: dict[str, list[str]] = {i: [] for i in by_id}
    pred: dict[str, list[str]] = {i: [] for i in by_id}
    for a, b in graph["edges"]:
        succ[a].append(b)
        pred[b].append(a)
    order = topo_order(graph)
    remaining: dict[str, int] = {}
    for n in reversed(order):
        remaining[n] = by_id[n]["duration_min"] + max((remaining[s] for s in succ[n]), default=0)
    # Kahn with priority on remaining path.
    indeg = {i: len(pred[i]) for i in by_id}
    ready = [i for i in by_id if indeg[i] == 0]
    dispatch: list[str] = []
    while ready:
        ready.sort(key=lambda i: (-remaining[i], i))
        n = ready.pop(0)
        dispatch.append(n)
        for s in succ[n]:
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    critical_path_min = max(remaining.values()) if remaining else 0

    # Time decomposition (spec §4, §9): walk the critical path and attribute each node's minutes to a
    # phase. The item's time ceiling covers the implementation phase; planning and gate time sit outside
    # it, the way the gate reserve sits outside the money ceiling. The three phases sum to the total.
    phases = {"planning_min": 0, "implementation_min": 0, "gate_min": 0}
    path: list[str] = []
    if remaining:
        cur = max((i for i in by_id if not pred[i]), key=lambda i: (remaining[i], i))
        while cur:
            path.append(cur)
            kind = by_id[cur]["node"]
            phase = ("planning_min" if kind in PLANNING_NODES else
                     "implementation_min" if kind in IMPLEMENTATION_NODES else "gate_min")
            phases[phase] += by_id[cur]["duration_min"]
            cur = max(succ[cur], key=lambda s: (remaining[s], s)) if succ[cur] else None
    return {"dispatch_order": dispatch, "remaining_path_min": remaining, "critical_path_min": critical_path_min,
            "critical_path": path, **phases}


# --------------------------------------------------------------------------- failure transitions (spec §8)

def next_after_failure(state: dict[str, Any], failure_class: str, policy: dict[str, Any],
                       implementation_also_wrong: bool = False) -> dict[str, Any]:
    """Pure transition function keyed on failure class. `state` is copied, never mutated."""
    s = deepcopy(state)
    s.setdefault("attempt", 1)
    s.setdefault("f1_count", 0)
    s.setdefault("f3_count", 0)
    s.setdefault("replans_used", 0)
    s.setdefault("milestone_replans_used", 0)
    s.setdefault("origin_effort", s["effort"])
    fc = policy["failure_classes"][failure_class]
    hard_stop = int(policy["effort_levels"][s["origin_effort"]]["hard_stop_attempts"])

    def result(edge: str, counts: bool, reason: str, stop: bool = False) -> dict[str, Any]:
        return {"failure_class": failure_class, "edge": edge, "stop": stop, "counts_candidate": counts,
                "charged_to": fc.get("charged_to"), "reason": reason, "state": s}

    if failure_class == "F1":
        s["f1_count"] += 1
        if s["f1_count"] > int(fc["max_per_item"]):
            return result("STOP", False, "second environment failure on the same item: the harness is the problem", stop=True)
        return result("ITEM", False, "retry once at the same tier after fixing the environment")

    if failure_class == "F2":
        counts = bool(implementation_also_wrong)
        if counts:
            s["f3_count"] += 1
        return result("CON", counts, "back to the contract node at the current cell's planning tier; not a model escalation")

    if failure_class == "F3":
        s["f3_count"] += 1
        s["attempt"] += 1
        if s["attempt"] > hard_stop:
            return result("STOP", True, f"hard stop: {hard_stop} attempts for an item that started at {s['origin_effort']}", stop=True)
        if s["f3_count"] == 1:
            lvl = policy["effort_levels"][s["effort"]]
            nxt = lvl.get("escalate_to")
            if nxt in EFFORTS:
                s["effort"] = nxt
                return result("ITEM", True, f"escalate implementer one tier to {nxt}")
            return result("ITEM", True, "second attempt at the top implementer tier")
        if s["f3_count"] == 2:
            if s["replans_used"] == 0:
                s["replans_used"] = 1
                return result("PRE", True, "two failed candidates: premium replan, once")
            return result("STOP", True, "replan already used", stop=True)
        return result("STOP", True, "third implementation failure: stop and preserve evidence", stop=True)

    if failure_class == "F4":
        s["milestone_replans_used"] += 1
        if s["milestone_replans_used"] > 1:
            return result("STOP", False, "milestone replan already consumed by an earlier collision or premium replan", stop=True)
        return result("SPLIT", False, "re-partition owned files; serialize the collision point")

    if failure_class == "F5":
        return result("STOP", False, "external blocker: checkpoint and report to a human", stop=True)

    raise PolicyError(f"unknown failure class {failure_class!r}")


# --------------------------------------------------------------------------- Hermes cards

def _profile_for(node: dict[str, Any], policy: dict[str, Any]) -> str:
    if node["node"] == "RV":
        return "eng-reviewer"
    if node["node"] in ("PCON", "PACC", "PRE"):
        return policy["tiers"]["P"]["profile"]
    if node["tier"] in policy["tiers"]:
        return policy["tiers"][node["tier"]]["profile"]
    return "eng-integrator"


def emit_cards(graph: dict[str, Any], policy: dict[str, Any], task: dict[str, Any],
               ctx: PlanContext | None = None) -> dict[str, Any]:
    ctx = ctx or _pick_ctx(policy, policy.get("modes", {}).get("default", "easy"), {}, [])
    by_id = {n["id"]: n for n in graph["nodes"]}
    parents: dict[str, list[str]] = {i: [] for i in by_id}
    for a, b in graph["edges"]:
        parents[b].append(a)
    cards, steps = [], []
    for n in graph["nodes"]:
        if n["node"] in CONTROLLER_NODES:
            steps.append({"node_id": n["id"], "node": n["node"], "parents": parents[n["id"]],
                          "recipe": n.get("recipe"), "eval_replay": n.get("eval_replay")})
            continue
        key = n["id"]
        title = f"{n['node']} {n['role']} for {task['task_id']}" + (f" item {n['item']}" if n.get("item") is not None else "")
        if n["node"] in HUMAN_NODES:
            cards.append({"node_id": n["id"], "title": title, "assignee": "human", "model": None, "provider": None,
                          "parents": parents[n["id"]], "idempotency_key": key,
                          "presents": ["contract", "diff summary with anchors", "verdicts and check evidence",
                                       "exact revision", "exact action", "rollback path"],
                          "decision": ["approve", "reject"], "scope": "exact revision and exact action"})
            continue
        info = model_info(n["model"], policy)
        disp = dispatch_target(ctx, n["model"])
        limits = n.get("hermes_limits") or {}
        parent_flags = " ".join(f"--parent <id of {p}>" for p in parents[n["id"]])
        if disp is None:
            # No dispatch route for this model (malformed registry entry); the plan reports dispatch_refused.
            cards.append({"node_id": n["id"], "title": title, "assignee": _profile_for(n, policy),
                          "model": n["model"], "provider": None, "family": info["family"],
                          "parents": parents[n["id"]], "idempotency_key": key, "dispatch": None})
            continue
        disp_provider, disp_model = disp
        spec = dispatch_spec(ctx, n["model"])
        reasoning = spec.get("reasoning_effort")
        reasoning_flag = ""  # kanban create has no reasoning flag; verified profile default binds it
        cli = (f'hermes kanban create "{title}" --assignee {_profile_for(n, policy)} '
               f'--model {disp_model} --provider {disp_provider} '
               f'{reasoning_flag}{parent_flags} --idempotency-key "{key}" --json').replace("  ", " ")
        cards.append({"node_id": n["id"], "title": title, "assignee": _profile_for(n, policy),
                      "model": n["model"], "provider": disp_provider, "family": info["family"],
                      "reasoning_effort": reasoning, "dispatch": spec,
                      "worker_argv": ["hermes", "-m", disp_model, "--provider", disp_provider] + (["--reasoning", reasoning] if reasoning else []),
                      "reasoning_binding": "assignee profile agent.reasoning_effort" if reasoning else "assignee profile prior base effort with exact Sol namespace overrides",
                      "parents": parents[n["id"]], "idempotency_key": key,
                      "child_timeout_seconds": limits.get("child_timeout_seconds"),
                      "iterations": limits.get("iterations"),
                      "fresh_session": n.get("fresh_session"),
                      "contract_delivery": ".hermes.md in the item worktree",
                      "cli": cli})
    return {"hermes_cards": cards, "controller_steps": steps}


# --------------------------------------------------------------------------- plan

def plan(task: dict[str, Any], policy: dict[str, Any], today: dt.date | None = None, attempt: int = 1,
         mode: str | None = None) -> dict[str, Any]:
    today = today or dt.date.today()
    if "task_id" not in task:
        raise PolicyError("task needs a task_id")
    base = {"policy_version": policy["policy_version"], "task_id": task["task_id"], "attempt": attempt,
            "planned_at": today.isoformat()}
    try:
        s1 = stage1_classify(task, policy)
        route = apply_opinions(s1, task, policy)
    except RouteRefused as exc:
        return {**base, "status": exc.status, **exc.payload}

    # Mode resolution (spec §0): user mode is a floor, flags/types derive a floor,
    # effective = the higher of the two. Never lowered.
    mode_info = resolve_mode(task, policy, mode, route["task_type"], route["effort"], route["flags"])
    effective = mode_info["effective"]

    # Hard/expert override behavior (spec §0): raise effort one level when uncertainty
    # is material (no reproduction for a bug fix, or a prior failed attempt). Capped at
    # E4, deterministic, and recorded.
    effort_raises: list[dict[str, str]] = []
    effort = route["effort"]
    if effective in ("hard", "expert"):
        sig = task.get("signals", {}) or {}
        no_repro = route["task_type"] in ("T2", "T3") and sig.get("has_reproduction") is False
        prior_failure = attempt > 1
        if (no_repro or prior_failure) and effort != "E4":
            new_effort = EFFORTS[effort_index(effort) + 1]
            why = []
            if no_repro:
                why.append("no reproduction for a bug fix")
            if prior_failure:
                why.append(f"prior failed attempt (attempt {attempt})")
            effort_raises.append({"from": effort, "to": new_effort,
                                  "reason": f"{effective} mode: uncertainty is material ({'; '.join(why)}); effort raised one level"})
            route["rationale"].append(f"{effective} mode raised effort {effort} -> {new_effort}")
            effort = new_effort

    ctx = _pick_ctx(policy, effective, {}, [])
    resolved = resolve_cell(route["task_type"], effort, route["flags"], policy, task.get("signals", {}))
    if resolved["status"] != "ok":
        return {**base, "status": "reroute_required", "route": route, "resolution": resolved}
    route["task_type"], route["effort"] = resolved["task_type"], resolved["effort"]

    graph = expand_graph(task, attempt, resolved, policy, ctx)
    order = critical_path_order(graph)
    models = [n["model"] for n in graph["nodes"] if n.get("model")]
    stale = check_registry_freshness(models, policy, today)
    if stale:
        return {**base, "status": "refused_stale_registry", "stale": stale, "route": route, "cell": resolved["cell"]}

    first_model = next((graph_node["model"] for nid_ in order["dispatch_order"]
                        for graph_node in graph["nodes"] if graph_node["id"] == nid_ and graph_node.get("model")), None)
    budget = budget_plan(task, resolved["effort"], resolved["modifiers"], policy, first_model, ctx)
    cards = emit_cards(graph, policy, task, ctx)

    lvl = policy["effort_levels"][resolved["effort"]]
    time_ceiling = lvl.get("time_ceiling_min") or lvl.get("plan_time_ceiling_min")
    warnings = []
    if route.get("stage3_required"):
        warnings.append("stage 3 (coordination model) opinion required before dispatch")
    if resolved["effort"] != "E4" and time_ceiling and order["implementation_min"] > time_ceiling:
        warnings.append(f"estimated implementation path {order['implementation_min']} min exceeds the {resolved['effort']} time ceiling {time_ceiling} min")
    if resolved["effort"] == "E4" and time_ceiling and order["planning_min"] > time_ceiling:
        warnings.append(f"estimated planning path {order['planning_min']} min exceeds the plan time ceiling {time_ceiling} min")
    status = "planned" if budget["within_limit"] and budget["predispatch_check_ok"] else "over_limit"
    if status == "over_limit":
        warnings.append("planned total exceeds the effective limit: reduce scope or stop with a checkpoint; never drop tests, the recipe or a mandatory gate")

    # Fail closed if any planned model has no dispatchable provider route (malformed
    # registry entry). There are no pools to leave: model selection is decoupled from
    # the mode, so every model dispatches on its own provider account.
    violations = []
    for n in graph["nodes"]:
        if not n.get("model"):
            continue
        if dispatch_target(ctx, n["model"]) is None:
            violations.append(f"{n['node']} {n['model']} has no dispatchable provider route")
    if violations:
        return {**base, "status": "dispatch_refused", "mode": effective, "violations": violations,
                "route": {**route, "cell": resolved["cell"]}, "reason":
                        "a planned model has no dispatchable provider route; fix the registry entry rather than dispatch blind"}

    return {
        **base,
        "status": status,
        "mode": {**mode_info, "rank": MODE_RANK[effective],
                 **mode_roles(ctx), "substitutions": ctx.substitutions,
                 "effort_raises": effort_raises,
                 "note": "mode is a rigor level (spec §0): it may only raise rigor, never remove a mandatory recipe, gate or verification. Model selection is decoupled from the mode."},
        "route": {**route, "cell": resolved["cell"], "matrix_cell": resolved["matrix_cell"], "family": resolved["family"],
                  "modifiers": resolved["modifiers"], "reroute_history": resolved["history"]},
        "budget": budget,
        "time": {"critical_path_min": order["critical_path_min"], "critical_path": order["critical_path"],
                 "planning_min": order["planning_min"],
                 "implementation_min": order["implementation_min"], "gate_min": order["gate_min"],
                 "time_ceiling_min": time_ceiling,
                 "ceiling_applies_to": "implementation path (test design, implement, review, checks, integrate, verify)",
                 "note": "planning time (evidence, reproduction, contract) and gate time (premium sessions, human waits) are tracked outside the item's ceiling, as the gate reserve sits outside the money ceiling; reproduction has its own ceiling of the same size"},
        "graph": graph,
        "dispatch_order": order["dispatch_order"],
        "remaining_path_min": order["remaining_path_min"],
        **cards,
        "recipe": policy["recipes"][policy["task_types"][resolved["task_type"]]["recipe"]],
        "gates": {"premium_contract": "G" in resolved["modifiers"], "premium_acceptance": "G" in resolved["modifiers"],
                  "human_interrupt": "H" in resolved["modifiers"], "eval_replay": "V" in resolved["modifiers"]},
        "warnings": warnings,
        "disclaimer": "Offline plan. No API calls, provider accounts or Hermes tasks were created. Spending authority comes only from the user's existing limits.",
    }


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task", help="task JSON file")
    ap.add_argument("--policy", default="policy.json")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD for registry freshness (default: today)")
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--out", default=None, help="write the route JSON here instead of stdout")
    ap.add_argument("--mode", default=None, help="rigor mode: easy, medium, hard or expert (spec §0; default: the task's 'mode' field or policy modes.default). A floor, not a ceiling — the router may raise it from task type, effort or flags, never lower it.")
    args = ap.parse_args(argv)
    policy = load_policy(args.policy)
    task = load_task(args.task)
    today = dt.date.fromisoformat(args.today) if args.today else None
    result = plan(task, policy, today=today, attempt=args.attempt, mode=args.mode)
    text = json.dumps(result, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"{result['status']}: {result.get('route', {}).get('cell', '-')} -> {args.out}")
    else:
        print(text)
    return 0 if result["status"] == "planned" else 2


if __name__ == "__main__":
    sys.exit(main())
