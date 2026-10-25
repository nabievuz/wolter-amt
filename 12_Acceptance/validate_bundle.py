#!/usr/bin/env python3
"""Wolter AMT Project OS bundle validator.

Reads files only. Never deploys, calls an API or changes anything.

Usage:
  python3 validate_bundle.py                      # full bundle check (configs + docs + traceability)
  python3 validate_bundle.py --json               # machine-readable result
  python3 validate_bundle.py --self-test          # config/doc mutations and profile scenarios must behave as declared
  python3 validate_bundle.py --write-report       # regenerate 12_Acceptance/VALIDATION_REPORT.md from a real run
  python3 validate_bundle.py --context-pack F3 [--out build/F3/CONTEXT_PACK.md]   # builder reading pack of a phase
  python3 validate_bundle.py --profile F6_STEP1 --readiness path/to/readiness.yaml [--now 2026-11-01T00:00:00Z]
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

from handoff_checks import handoff_rules, probe_results

HEADER = "# Project OS configuration template; unresolved readiness blocks the relevant live profile."
BUSINESS_AGENTS = {"cmo", "media-buyer", "creative-studio", "cro", "funnel-analyst", "reviewer"}
ENGINEERING_ROLES = {"eng-planner", "eng-architect", "eng-implementer", "eng-verifier"}
RBAC_ROLES = ["owner", "ads_approver", "sales_lead", "fleet_operator", "content_contributor", "viewer"]
HUMAN_ACCOUNTABLE = {"owner", "sales_lead", "fleet_operator", "technical_operator", "finance_owner", "privacy_owner", "independent_reviewer"}
COMMAND_STATES = ["pending_review", "pending_approval", "approved", "claimed", "executing", "succeeded", "rejected",
                  "expired", "cancelled", "failed_confirmed", "uncertain", "reconciling", "manual_resolution",
                  "awaiting_manual", "done_manual"]
GLOBAL_MODES = ["shadow", "enabled", "read_only", "killed"]
PIPELINE_MODES = ["L0_shadow", "L1_approve_each", "L2_auto_within_guardrails"]
DATA_STATUS = ["valid", "no_activity", "no_spend", "spend_zero_qualified", "insufficient_sample", "not_mature",
               "incomparable_baseline", "missing_data", "stale_data"]
LIFECYCLE = ["specified", "implemented", "verified_in_staging", "merged", "released", "deployed", "observed",
             "technically_accepted", "business_accepted"]
TERMINAL = ["rejected", "inconclusive", "rolled_back", "cancelled", "not_applicable"]
REQUIRED_NEVER_AUTO = {"campaign_create", "campaign_activate", "adset_duplicate", "offer_change", "landing_pr_merge",
                       "events_manager_change", "amo_pipeline_change_proposal", "role_change", "kill_switch",
                       "control_resume", "pipeline_mode_change", "takeover_scope_change", "trust_graduation",
                       "budget_override", "upgrade_proposal_approval", "upgrade_release", "harness_handover",
                       "protected_surface_change", "engineering_budget_change"}
READINESS_NS = ("ops", "recovery", "business", "sales", "sale", "fleet", "offers", "privacy", "tracking", "vendor",
                "budget", "models", "config", "workflow", "engineering", "capacity", "verification", "release",
                "evolution", "auto_release")
RESIDUE_PATTERNS = [
    (r"(?<![\w.])[vV][1-3](?![\w.])", "bundle version label"),
    (r"[_-][vV][1-3](?![\d])", "versioned name"),
    (r"V[1-3]_", "versioned file reference"),
    (r"Versiya\s*\d", "bundle version line"),
    (r"\b2\.0\.0\b", "bundle semver"),
    (r"Project OS v\d", "Project OS version"),
    (r"(?<![\w-])U(0[1-9]|1[0-2])(?![\w-])", "upgrade package ID"),
    (r"USD ?15000|USD ?150000|\$15000|\$150000", "money written 100x"),
    (r"kernel_version|project_os_version", "version-carrying machine field"),
    (r"thinking_models_v\d|premortem_v\d|V\d_[A-Z_]+|VERSION\.json", "removed versioned file"),
    (r"schema_version:\s*2\b", "old schema version"),
]
RESIDUE_ALLOW = re.compile(r"(/v\d+/|api/v\d)|((Langfuse|cgroups?|cgroup2|Node|Ubuntu|API|Graph|OTLP|OTel|HTTP|TLS|IPv|byadsco|Hermes|Paperclip|Caddy|ClickHouse|MinIO|Redis|Remotion|Next\.js|Postgres(QL)?|python|pnpm)\s*(≥\s*)?v?\d)", re.I)


class UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


# S09: YAML fragments in files maintained by a parallel change-set stream, fixed there; each waived fragment is reported as a
# warning and an entry that no longer matches a fragment fails S09 (remove it once the fix is merged)
S09_MERGE_PENDING = ()   # lane merge done (CS-M1): must stay empty — S09 fails if a waiver is added back


class Report:
    def __init__(self):
        self.errors: list[tuple[str, str]] = []
        self.warnings: list[tuple[str, str]] = []
        self.facts: dict = {}
        self.checked: set[str] = set()

    def check(self, rule: str, ok: bool, msg: str):
        self.checked.add(rule)
        if not ok:
            self.errors.append((rule, msg))

    def warn(self, rule: str, msg: str):
        self.warnings.append((rule, msg))

    @property
    def failed_rules(self):
        return {r for r, _ in self.errors}


# ---------------------------------------------------------------- helpers

def iso_duration(text: str) -> dt.timedelta:
    m = re.fullmatch(r"P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", text or "")
    if not m or text in ("P", "PT"):
        raise ValueError(f"bad ISO-8601 duration: {text}")
    w, d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return dt.timedelta(weeks=w, days=d, hours=h, minutes=mi, seconds=s)


def parse_ts(value) -> dt.datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def profile_closure(profiles: dict, name: str, seen=None) -> set[str]:
    seen = set() if seen is None else seen
    if name in seen:
        return seen
    seen.add(name)
    for parent in profiles[name].get("requires", []):
        profile_closure(profiles, parent, seen)
    return seen


PERSON_REF = re.compile(r"^person:[A-Za-z0-9_.-]+$")


def evaluate_profile(readiness: dict, profile: str, now: dt.datetime) -> tuple[bool, list[str]]:
    """Offline profile check. Role membership at approved_at is verified at runtime by amt-control."""
    profiles = readiness["profiles"]
    if profile not in profiles:
        return False, [f"unknown profile {profile}"]
    closure = profile_closure(profiles, profile)
    problems = []
    for rec in readiness["requirements"]:
        if rec["gate"] not in closure:
            continue
        key, status = rec["key"], rec.get("status")
        approver = rec.get("approved_by")
        preparer = rec.get("evidence_prepared_by")
        if status in ("approved", "not_applicable"):
            if not (isinstance(approver, str) and PERSON_REF.match(approver)):
                problems.append(f"{key}: approved_by must be a person reference, not {approver!r}")
                continue
            if preparer and approver == preparer:
                problems.append(f"{key}: approver prepared the evidence")
                continue
        if status == "approved":
            ap_at, ev_at = parse_ts(rec.get("approved_at")), parse_ts(rec.get("evidence_at"))
            if rec.get("value") is None or not rec.get("evidence_ref") or ap_at is None or ev_at is None:
                problems.append(f"{key}: approved without value, evidence_ref, evidence_at or approved_at")
                continue
            if not (ev_at <= ap_at <= now):
                problems.append(f"{key}: timestamps out of order (evidence_at <= approved_at <= now)")
            age = rec.get("max_evidence_age")
            if age and ev_at + iso_duration(age) < now:
                problems.append(f"{key}: evidence older than {age}")
            vu = parse_ts(rec.get("valid_until"))
            if vu is not None and vu < now:
                problems.append(f"{key}: valid_until passed")
            signed = {c.get("role"): c for c in rec.get("co_signatures") or [] if isinstance(c, dict)}
            for role in rec.get("co_signers") or []:
                c = signed.get(role)
                at = parse_ts(c.get("at")) if c else None
                if not c or not PERSON_REF.match(str(c.get("person", ""))) or c.get("person") == preparer or at is None or at > now:
                    problems.append(f"{key}: missing or invalid co-signature for {role}")
        elif status == "not_applicable":
            if rec.get("criticality") != "optional":
                problems.append(f"{key}: not_applicable on a critical requirement")
            elif not rec.get("evidence_ref"):
                problems.append(f"{key}: not_applicable without rationale")
        else:
            problems.append(f"{key}: {status}")
    # an approvable value refused while a profile condition holds (readiness.yaml rules.value_constraints, OPEN_ITEMS section 4)
    by_key = {x["key"]: x for x in readiness["requirements"]}

    def holds_value(v, wanted):   # REVIEW_A1 #12: a refused value is found in any value shape ({mode: x}, [x], "x")
        if isinstance(v, dict):
            return any(holds_value(x, wanted) for x in v.values())
        if isinstance(v, (list, tuple)):
            return any(holds_value(x, wanted) for x in v)
        return str(v).strip() == str(wanted)

    def field_values(v, fld):
        if isinstance(v, dict):
            return ([v[fld]] if fld in v else []) + [y for x in v.values() if isinstance(x, (dict, list)) for y in field_values(x, fld)]
        if isinstance(v, list):
            return [y for x in v for y in field_values(x, fld)]
        return []
    for vc in (readiness.get("rules") or {}).get("value_constraints") or []:
        rec = by_key.get(vc.get("key"))
        if not rec or rec["gate"] not in closure or rec.get("status") != "approved":
            continue
        if "max" in vc:   # numeric bound on one field of the approved value (REVIEW_A1 #22)
            over = [x for x in field_values(rec.get("value"), vc.get("field")) if not (isinstance(x, (int, float)) and x <= vc["max"])]
            if over:
                problems.append(f"{rec['key']}: {vc.get('field')} {over} exceeds {vc['max']} ({vc.get('conflict')}): {' '.join(str(vc.get('reason', '')).split())}")
            continue
        cond = vc.get("refused_while") or {}
        if not holds_value(rec.get("value"), vc.get("value")):
            continue
        try:
            holds = cond.get("profile") in profiles and cond.get("closure_contains") in profile_closure(profiles, cond["profile"])
        except KeyError:
            holds = True   # an unresolvable condition never makes the refused value acceptable
        if holds:
            problems.append(f"{rec['key']}: value {vc.get('value')} is refused while {cond.get('closure_contains')} is in closure({cond.get('profile')}) "
                            f"({vc.get('conflict')}): {' '.join(str(vc.get('reason', '')).split())}")
    return not problems, problems


def _path_parts(path: str) -> list:
    """Split 'a.b[2].c', 'a[key.with.dots]' or 'list[key=value]' (select the list item whose `key` equals value)."""
    parts = []
    for token in re.findall(r"[^.\[\]]+|\[[^\]]+\]", path):
        if token.startswith("["):
            inner = token[1:-1]
            if inner.isdigit():
                parts.append(int(inner))
            elif "=" in inner:
                field, _, wanted = inner.partition("=")
                parts.append(("select", field, wanted))
            else:
                parts.append(inner)
        else:
            parts.append(token)
    return parts


def _step(cur, part):
    if isinstance(part, tuple):
        _, field, wanted = part
        hits = [i for i, item in enumerate(cur) if isinstance(item, dict) and str(item.get(field)) == wanted]
        if len(hits) != 1:
            raise KeyError(f"[{field}={wanted}] matched {len(hits)} items")
        return hits[0]
    return part


def get_path(obj, path: str):
    cur = obj
    for part in _path_parts(path):
        cur = cur[_step(cur, part)]
    return cur


def set_path(obj, path: str, value, op: str = "set"):
    parts = _path_parts(path)
    cur = obj
    for part in parts[:-1]:
        cur = cur[_step(cur, part)]
    key = _step(cur, parts[-1])
    if op == "set":
        cur[key] = value
    elif op == "delete":
        del cur[key]
    elif op == "append":
        cur[key].append(value)
    elif op == "remove":
        cur[key].remove(value)
    else:
        raise ValueError(op)


def schedule_time(schedule: list, sid: str) -> str | None:
    for row in schedule:
        if row.get("id") == sid:
            m = re.search(r"(\d{2}:\d{2})", str(row.get("when", "")))
            return m.group(1) if m else None
    return None


def cron_time(cron: str) -> str | None:
    parts = (cron or "").split()
    if len(parts) != 5 or not parts[0].isdigit() or not parts[1].isdigit():
        return None
    return f"{int(parts[1]):02d}:{int(parts[0]):02d}"


CRON_DOW = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def schedule_offset(cron: str, when: str) -> dt.timedelta | None:
    """Offset of a schedule slot ('daily HH:MM' or '<dow> HH:MM' of operations.yaml#schedule) from the start of a daily or
    weekly trigger cron; None when the slot cannot be placed against that trigger."""
    parts = (cron or "").split()
    m = re.match(r"\s*(daily|mon|tue|wed|thu|fri|sat|sun)\s+(\d{2}):(\d{2})", when or "")
    if len(parts) != 5 or not parts[0].isdigit() or not parts[1].isdigit() or parts[2] != "*" or parts[3] != "*" or not m:
        return None
    start = dt.timedelta(hours=int(parts[1]), minutes=int(parts[0]))
    slot = dt.timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    if parts[4] == "*" and m.group(1) == "daily":
        return (slot - start) % dt.timedelta(days=1)
    if re.fullmatch(r"[0-6]", parts[4]) and m.group(1) != "daily":
        cron_dow = (int(parts[4]) - 1) % 7   # cron 0 = Sunday, 1 = Monday
        return (dt.timedelta(days=CRON_DOW[m.group(1)] - cron_dow) + slot - start) % dt.timedelta(days=7)
    return None


def cron_period(cron: str) -> dt.timedelta | None:
    """Trigger period of a daily ('m h * * *'), weekly ('m h * * d') or monthly ('m h D * *', shortest month: 28 days) cron; None for anything else."""
    parts = (cron or "").split()
    if len(parts) == 5 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit() and parts[3] == "*" and parts[4] == "*":
        return dt.timedelta(days=28)
    if len(parts) != 5 or not parts[0].isdigit() or not parts[1].isdigit() or parts[2] != "*" or parts[3] != "*":
        return None
    if parts[4] == "*":
        return dt.timedelta(days=1)
    return dt.timedelta(days=7) if re.fullmatch(r"[0-6]", parts[4]) else None


# ---------------------------------------------------------------- loading

def parse_hujson(text: str):
    """HuJSON (JSON with // comments and trailing commas) -> Python object."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True; out.append(ch)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(ch)
        i += 1
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", "".join(out)))


def load_configs(root: Path, report: Report) -> dict:
    folder = root / "09_Config_Templates"
    index = json.loads((folder / "bundle-index.json").read_text(encoding="utf-8"))
    configs = {"_index": index}
    on_disk = {p.name for p in folder.glob("*.yaml")}
    report.check("S01", set(index["files"]) == on_disk, f"bundle-index files differ from disk: {sorted(set(index['files']) ^ on_disk)}")
    for name in index["files"]:
        path = folder / name
        try:
            text = path.read_text(encoding="utf-8")
            report.check("S02", text.startswith(HEADER), f"{name}: missing standard header line")
            obj = yaml.load(text, Loader=UniqueLoader)
            report.check("S03", isinstance(obj, dict) and obj.get("schema_version") == 1, f"{name}: schema_version must be 1")
            configs[name] = obj
        except (OSError, ValueError, yaml.YAMLError) as exc:
            report.check("S04", False, f"{name}: cannot load ({exc})")
    wf_dir = folder / "workflows"
    configs["_workflows"] = {}
    for name in index.get("workflows", []):
        try:
            configs["_workflows"][name] = yaml.load((wf_dir / name).read_text(encoding="utf-8"), Loader=UniqueLoader)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            report.check("S05", False, f"workflows/{name}: cannot load ({exc})")
    report.check("S05", {p.name for p in wf_dir.glob("*.yaml")} == set(index.get("workflows", [])), "workflow index differs from disk")
    configs["_schemas"] = {}
    for name in index.get("schemas", []):
        try:
            configs["_schemas"][name] = json.loads((folder / "schemas" / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report.check("S06", False, f"schemas/{name}: cannot load ({exc})")
    configs["_env"] = (folder / "env.example").read_text(encoding="utf-8")
    # the closed ALERT_ / REMINDER_ code set of 03_Architecture/TELEGRAM.md section 6.2 (T11)
    try:
        tg = (root / "03_Architecture" / "TELEGRAM.md").read_text(encoding="utf-8")
        sec = tg.split("### 6.2", 1)[1].split("### 6.3", 1)[0] if "### 6.2" in tg else ""
        configs["_alert_codes"] = sorted(set(re.findall(r"^\|\s*`((?:ALERT|REMINDER)_[A-Z0-9_]+)`\s*\|", sec, re.M)))
    except OSError:
        configs["_alert_codes"] = []
    configs["_policy_templates"] = {}
    for name in index.get("policy_templates", []):
        try:
            configs["_policy_templates"][name] = parse_hujson((folder / name).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            report.check("S08", False, f"{name}: cannot load ({exc})")
    report.check("S08", {p.name for p in folder.glob("*.hujson")} == set(index.get("policy_templates", [])), "policy template index differs from disk")
    try:
        configs["_context_packs"] = load_packs(root)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        configs["_context_packs"] = None
        report.check("C01", False, f"{PACKS_FILE}: cannot load ({exc})")
    return configs


# ---------------------------------------------------------------- config rules

def config_rules(c: dict, report: Report):
    def has(*names):
        return all(n in c for n in names)

    # S09 YAML hygiene: in a list of strings, a one-key mapping is a plain scalar that an unquoted ": " turned into a mapping
    def _mixed(o, path):
        if isinstance(o, list):
            if any(isinstance(x, str) for x in o):
                for i, x in enumerate(o):
                    if isinstance(x, dict) and len(x) == 1:
                        yield f"{path}[{i}]"
            for i, x in enumerate(o):
                yield from _mixed(x, f"{path}[{i}]")
        elif isinstance(o, dict):
            for k, v in o.items():
                yield from _mixed(v, f"{path}.{k}")
    mixed = [p for name, obj in c.items() if name.endswith(".yaml") for p in _mixed(obj, name)]
    mixed += [p for name, obj in (c.get("_workflows") or {}).items() for p in _mixed(obj, f"workflows/{name}")]
    report.check("S09", not mixed, f"string lists contain one-key mappings (quote the item; an unquoted ': ' made it a mapping): {mixed[:5]}")
    # a YAML 1.1 boolean word used as a key (on, off, yes, no, y, n) loads as True/False and silently loses the key name
    def _boolkeys(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(k, bool):
                    yield f"{path}.{k}"
                yield from _boolkeys(v, f"{path}.{k}")
        elif isinstance(o, list):
            for i, x in enumerate(o):
                yield from _boolkeys(x, f"{path}[{i}]")
    boolk = [p for name, obj in c.items() if name.endswith(".yaml") for p in _boolkeys(obj, name)]
    boolk += [p for name, obj in (c.get("_workflows") or {}).items() for p in _boolkeys(obj, f"workflows/{name}")]
    report.check("S09", not boolk, f"YAML keys that load as booleans (on/off/yes/no; rename or quote the key): {boolk[:5]}")
    # S09 (REVIEW_A2 #13, P-50 class) an unquoted ', ' in a flow collection splits a text, and an unquoted ' #' cuts it at a
    # comment: a null-valued key with a space or parenthesis is a split-off fragment, and a string whose parentheses or
    # brackets do not balance is a fragment or a cut value
    def _frag(o, path):
        if isinstance(o, dict):
            for k, val in o.items():
                if (val is None and isinstance(k, str) and re.search(r"[\s()]", k)) or (isinstance(val, str) and (val.count("(") != val.count(")") or val.count("[") != val.count("]"))):
                    yield f"{path}.{k}"
                yield from _frag(val, f"{path}.{k}")
        elif isinstance(o, list):
            for i, x in enumerate(o):
                p9 = f"{path}[id={x['id']}]" if isinstance(x, dict) and isinstance(x.get("id"), str) else f"{path}[{i}]"
                if isinstance(x, str) and (x.count("(") != x.count(")") or x.count("[") != x.count("]")):
                    yield p9
                yield from _frag(x, p9)
    frags = [p for name, obj in c.items() if name.endswith(".yaml") for p in _frag(obj, name)]
    frags += [p for name, obj in (c.get("_workflows") or {}).items() for p in _frag(obj, f"workflows/{name}")]
    for p in frags:
        if p.startswith(S09_MERGE_PENDING):
            report.warn("S09", f"merge-pending YAML fragment (fixed in a parallel change set): {p[:140]}")
    stale9 = [w for w in S09_MERGE_PENDING if not any(p.startswith(w) for p in frags)]
    report.check("S09", not stale9, f"S09_MERGE_PENDING entries {stale9} no longer match a YAML fragment; remove them")
    report.check("S09", not S09_MERGE_PENDING, "S09_MERGE_PENDING must be empty after the lane merge (CS-M1); quote the fragment instead of waiving it")
    own9 = [p[:120] for p in frags if not p.startswith(S09_MERGE_PENDING)]
    report.check("S09", not own9, f"an unquoted ', ' or ' #' split or cut a YAML text (quote it): {own9[:5]}")

    # money (Q08, Q10, Q33, Q37)
    if has("budgets.yaml"):
        b = c["budgets.yaml"]
        o, a = b["openrouter"], b["ads"]
        shares = o["shares_minor"]
        report.check("M01", o["key_hard_cap_minor"] == 15000, "AI/media cap must be 15000 USD minor (USD 150)")
        report.check("M02", all(type(v) is int and v >= 0 for v in shares.values()) and sum(shares.values()) == o["key_hard_cap_minor"], "OpenRouter shares must be non-negative integers summing to the key cap")
        report.check("M03", a["monthly_cap_minor"] == 150000, "Meta cap must be 150000 USD minor (USD 1 500)")
        report.check("M04", a.get("provider_spend_limit_required") is True and a.get("protective_pause_is_additional") is True, "Q37: provider spending limit mandatory; protective pause only additional")
        report.check("M05", a["max_rolling24h_change_pct"] == 20, "rolling-24h budget movement must be 20%")
        report.check("M06", o.get("reservation_required") is True, "LLM reservation required")
        report.check("M07", 0 < o.get("build_eval_max_pct", 0) <= 40, "build eval share must be <= 40%")
        report.check("M08", "new_owner_q_changing_Q10" in o.get("build_eval_over_limit_options", []) and not any("raise" in str(x) for x in o.get("build_eval_over_limit_options", [])), "HG-F4-04 options may not raise the key cap without a new owner Q")
    # approval policy (Q08, Q32, Q38, Q42, Q25)
    if has("approval-policy.yaml"):
        p = c["approval-policy.yaml"]
        cs = p["change_set"]
        report.check("A01", cs["approval_ttl_hours"] == 12 and cs["auto_approve_on_timeout"] is False and cs["daily_batch_time"] == "10:00", "Q32/Q38: TTL 12h, no auto-approve, 10:00 batch")
        tr = p["trust_ramp"]
        g = tr["graduation"]
        report.check("A02", g["consecutive_clean_items"] == 10 and g["incident_free_days"] == 14 and g["inconclusive_counts_as_clean"] is False and g["requires_owner_confirmation"] is True and g.get("shadow_items_count") is False and tr.get("initial_level") == "L1_approve_each", "Trust Ramp graduation 10 clean + 14 days, owner confirms, inconclusive and shadow items not clean, trust axis starts at L1")
        never = set(tr["never_auto"])
        report.check("A03", REQUIRED_NEVER_AUTO <= never, f"never_auto missing: {sorted(REQUIRED_NEVER_AUTO - never)}")
        # A14 Trust Ramp decision mechanics (P-42): met is computed by a deterministic workflow step, only a countable met
        # increments the streak (inconclusive resets as the interim stricter reading), budget_change graduates per direction,
        # incidents are defined, and the level transitions are closed with every raise owned by the owner
        se = g.get("streak_effects") or {}
        want_se = {"met_countable", "met_uncountable", "not_met", "inconclusive", "harmful", "rejected", "edit_decrease", "expired", "cancelled",
                   "failed_confirmed", "terminal_without_outcome", "shadow"}   # REVIEW_A1 #5: every terminal result has an effect
        step_ref = str(g.get("outcome_step", ""))
        wfid, _, sid = step_ref.partition(".")
        wf = c.get("_workflows", {}).get(f"{wfid}.yaml") or {}
        ostep = next((s for s in wf.get("steps", []) if s.get("id") == sid), {})
        report.check("A14", g.get("decision_rule") == "TRUST_RAMP_GRADUATION" and g.get("outcome_computed_by") == "deterministic"
                     and (ostep.get("executor") or {}).get("type") == "deterministic" and bool(g.get("met_rule")) and "(never ?)" in str(g.get("countable_item", ""))
                     and "outcome_band_max_relative_width" in str(g.get("countable_item", "")) and want_se <= set(se)
                     and [k for k, v in se.items() if v == "increment"] == ["met_countable"] and se.get("shadow") == "not_counted"
                     and all(v == "reset" for k, v in se.items() if k not in ("met_countable", "shadow")) and "budget_change" in (g.get("direction_split_actions") or [])
                     and bool(g.get("incident_definition")) and bool(g.get("streak_order"))
                     and (g.get("harm_rule") or {}).get("computed_by") == "outcome_classify"
                     and (g.get("harm_rule") or {}).get("against_direction_margin_ref") == "business.acceptance"
                     and (g.get("harm_rule") or {}).get("guardrail_breach_ref") == "business.acceptance" and bool((g.get("harm_rule") or {}).get("linked_incident"))
                     and (g.get("harm_flag") or {}).get("direction") == "one_way" and "met" in str((g.get("harm_flag") or {}).get("applies_to", ""))
                     and "direction" in str(tr.get("trust_key", "")) and "direction_split_actions" in str(tr.get("trust_key", "")) and "never grants" in str(tr.get("trust_key", ""))
                     and "trust key" in str(tr.get("effective_level", ""))
                     and "WF-O02" in str((g.get("harm_flag") or {}).get("effect_on_write", "")),
                     f"approval-policy.yaml#trust_ramp.graduation: deterministic outcome step ({step_ref}: {(ostep.get('executor') or {}).get('type')}), met_rule, countable_item with the band bound, "
                     "streak_effects (only met_countable increments, shadow not_counted, everything else resets), budget_change direction split, incident_definition, streak_order, "
                     "harm_rule computed by outcome_classify (harm margin and guardrails in business.acceptance, linked incident) and a one-way harm_flag that opens WF-O02 (P-54), "
                     "trust_key with the direction split and effective_level by trust key (P-55)")
        levels = list(tr.get("levels") or [])
        rank = {lv: i for i, lv in enumerate(levels)}
        trans = tr.get("transitions") or []
        bad_t = [x for x in trans if x.get("axis") not in ("pipeline_mode", "trust_level") or x.get("from") not in rank or x.get("to") not in rank
                 or x.get("actor") not in ("owner", "amt-control") or not x.get("guard")
                 or (rank.get(x.get("to"), 0) > rank.get(x.get("from"), 0) and x.get("actor") != "owner")
                 or (x.get("axis") == "trust_level" and "L0_shadow" in (x.get("from"), x.get("to")))
                 or (rank.get(x.get("to"), 0) - rank.get(x.get("from"), 0) > 1)]
        covered = {(x.get("axis"), x.get("from"), x.get("to")) for x in trans}
        need_t = {("pipeline_mode", "L0_shadow", "L1_approve_each"), ("pipeline_mode", "L1_approve_each", "L2_auto_within_guardrails"),
                  ("pipeline_mode", "L1_approve_each", "L0_shadow"), ("trust_level", "L1_approve_each", "L2_auto_within_guardrails"),
                  ("trust_level", "L2_auto_within_guardrails", "L1_approve_each")}
        # A15 change spacing and experiment lock (P-43): budget increases are spaced per entity by an owner value; decreases,
        # pauses, protective pauses and urgent items stay open; a running experiment blocks confounding changes in its pipeline
        # but never a pause or kill; an overlapping command makes the outcome inconclusive
        sp_ = cs.get("change_spacing") or {}
        el_ = cs.get("experiment_lock") or {}
        ex_ = " ".join(map(str, sp_.get("exempt") or []))
        al_ = " ".join(map(str, el_.get("allows") or []))
        bl_ = set(el_.get("blocks") or [])
        report.check("A15", sp_.get("min_interval_hours_ref") == "budget.ads_limits" and "budget_change increase" in (sp_.get("applies_to") or [])
                     and all(x in ex_ for x in ("decrease", "entity_pause", "protective_pause", "urgent"))
                     and {"budget_change increase", "creative_activate", "adset_duplicate"} <= bl_ and all(x in al_ for x in ("decrease", "entity_pause", "protective_pause", "kill"))
                     and not (bl_ & {"entity_pause", "protective_pause", "kill_switch", "budget_change decrease"}) and bool(g.get("overlap_rule"))
                     and isinstance(el_.get("release"), dict) and {"compensate_then_end", "reconciling", "manual_resolution"} <= set((el_.get("release") or {}).get("holds_while") or [])
                     and "remote evidence" in str((el_.get("release") or {}).get("requires", "")) and (el_.get("release") or {}).get("override") == "none"
                     and not any("increase" in str(x) for x in (sp_.get("exempt") or [])) and "never an increase" in str(sp_.get("urgent_definition", ""))
                     and {"protective_pause", "kill", "earlier_commands_with_open_effect_window"} <= set(g.get("overlap_includes") or []),
                     "approval-policy.yaml#change_set.change_spacing (owner min interval for increases, decreases/pauses/protective/urgent exempt), "
                     "#change_set.experiment_lock (blocks increases, creative and structure changes, allows decreases, pauses, protective pause and kill; release only after the arms are confirmed stopped, held while compensating, reconciling or in manual_resolution, no override) and trust_ramp.graduation.overlap_rule")
        # A16 re-activation after a protective pause is owner-only and never automatic on every path (REVIEW_A2 #2, REVIEW_A3 #2):
        # the approval-policy case of entity_activate and creative_activate, the trust ramp case exclusion, the approver alias
        # narrowing and the WF-B03 S04 case agree; ads_approver, L2 and a generic case cannot approve it
        rap = "re_activation_after_protective_pause"
        actions16 = p.get("actions") or {}
        ok16 = all(((actions16.get(a) or {}).get("cases") or {}).get(rap, {}).get("approvers") == ["owner"]
                   and ((actions16.get(a) or {}).get("cases") or {}).get(rap, {}).get("never_auto") is True
                   and ((actions16.get(a) or {}).get("cases") or {}).get(rap, {}).get("max_level") == "never_auto"
                   and bool(((actions16.get(a) or {}).get("cases") or {}).get(rap, {}).get("applies_when")) for a in ("entity_activate", "creative_activate"))
        ok16 &= rap in (p["trust_ramp"].get("never_auto_cases") or [])
        alias16 = ((c.get("workflow-policy.yaml", {}).get("human_aliases") or {}).get("approver_per_policy") or {})
        ok16 &= "cases" in str(alias16.get("case_narrowing", "")) and rap in str(alias16.get("case_narrowing", ""))
        b03 = (c.get("_workflows", {}).get("WF-B03.yaml") or {})
        s04 = next((st for st in b03.get("steps", []) if st.get("id") == "S04"), {})
        case04 = next((bc for bc in ((s04.get("approval") or {}).get("by_cause") or []) if bc.get("cause") == rap), {})
        ok16 &= case04.get("approvers") == ["owner"] and case04.get("never_auto") is True and {"entity_activate", "creative_activate"} <= set(case04.get("policy_actions") or [])
        report.check("A16", ok16, "re-activation after protective_pause must be owner-only never_auto in approval-policy actions.<entity_activate|creative_activate>.cases, trust_ramp.never_auto_cases, the approver_per_policy case_narrowing and WF-B03 S04")
        auto_need = {("trust_level", "L2_auto_within_guardrails", "L1_approve_each", "demotion"), ("pipeline_mode", "L1_approve_each", "L0_shadow", "kill_criteria_l0"),
                     ("pipeline_mode", "L2_auto_within_guardrails", "L0_shadow", "kill_criteria_l0")}
        auto_have = {(x.get("axis"), x.get("from"), x.get("to"), x.get("cause")) for x in trans if x.get("actor") == "amt-control"}
        report.check("A14", g.get("outcome_step") == "WF-B07.S02" and auto_need <= auto_have,
                     f"approval-policy.yaml#trust_ramp: outcome_step must be WF-B07.S02 and the automatic safe-direction moves must stay with amt-control {sorted(auto_need - auto_have)} (REVIEW_A1 #10)")
        report.check("A14", not bad_t and need_t <= covered and bool(tr.get("illegal_transitions")),
                     f"approval-policy.yaml#trust_ramp.transitions: axis pipeline_mode|trust_level, known levels, guard, actor owner|amt-control, every raise by the owner, one level per step, "
                     f"trust axis never L0; missing {sorted(need_t - covered)}; bad {bad_t[:2]}; illegal_transitions listed")
        actions = p["actions"]
        for name in never:
            report.check("A04", name in actions, f"never_auto action {name} not defined")
            if name in actions:
                report.check("A04", actions[name].get("max_level") == "never_auto" and actions[name].get("approvers") == ["owner"], f"{name}: never_auto actions are owner-only with max_level never_auto")
        for name, spec in actions.items():
            report.check("A05", "review_required" in spec, f"{name}: review_required missing")
        report.check("A06", set(p["agents"]) == BUSINESS_AGENTS, "approval-policy agents must be the six business agents")
        report.check("A07", p["rate_limits"].get("amocrm_global_rps_ceiling") == 7, "Q25: amoCRM ceiling must be 7 req/s")
        hl = p["creative_review"]["human_language_check"]
        report.check("A08", hl["first_copy_artifacts"] == 20 and hl["count_scope"] == "live_eligible_copy_artifacts", "Q42: first 20 live-eligible copies checked by a human")
        slots = p["creative_review"].get("model_slots", {})
        report.check("A09", slots.get("reviewer.language") == "sonnet_class_or_proven_equal_on_uz_ru_holdout" and slots.get("reviewer.policy_checklist") == "cheaper_allowed", "Q42: Reviewer language slot Sonnet-class (or proven equal); checklist slot may be cheaper")
        report.check("A10", "review.get_subject" in p["agents"]["reviewer"]["tools"], "Reviewer must read subjects via review.get_subject")
        pp = actions.get("protective_pause", {})
        report.check("A11", pp.get("operations") == ["pause"] and pp.get("scope") == "managed_entities_only" and pp.get("additional_to") == "provider_spending_limit", "protective_pause is pause-only, managed entities only, additional to the provider limit")
        cr = p["creative_review"]
        gates_ok = cr.get("independent_reviewer_required") is True and cr.get("human_check_substitutes_reviewer") is False
        for name in ("asset_upload", "ad_create", "creative_activate"):
            spec = actions.get(name, {})
            gates_ok &= spec.get("review_required") is True and "independent_reviewer_pass" in spec.get("requires", [])
        report.check("A13", gates_ok, "independent Reviewer gate cannot be bypassed or replaced by a human check (Q03/Q42)")
        if has("roles.yaml"):
            flags = set(c["roles.yaml"]["flags"])
            report.check("A12", hl["checker_flag"] in flags, "language checker flag must exist in roles.yaml")
        for wf_name, wf in c.get("_workflows", {}).items():
            for step in wf.get("steps", []):
                appr = step.get("approval") or {}
                named = [appr["policy_action"]] if appr.get("policy_action") else []
                for case in appr.get("by_cause", []):
                    named += case.get("policy_actions", [])
                for pa in named:
                    report.check("W03", pa in actions, f"{wf_name} {step['id']}: unknown policy_action {pa}")
                never = set(p["trust_ramp"]["never_auto"])
                cases = [{"policy_actions": [appr["policy_action"]], "never_auto": appr.get("never_auto")}] if appr.get("policy_action") else appr.get("by_cause", [])
                for case in cases:
                    hit = set(case.get("policy_actions", [])) & never
                    if hit:
                        flag = case.get("never_auto", appr.get("never_auto"))
                        report.check("W03", flag is True, f"{wf_name} {step['id']}: case approving NEVER_AUTO {sorted(hit)} is not marked never_auto")
                for ca in step.get("command_actions", []) + ([step["command_action"]] if step.get("command_action") else []):
                    report.check("W06", ca in actions, f"{wf_name} {step['id']}: unknown command action {ca}")
            # W07 data_status names used in a definition exist in business-policy.yaml#data_status_values
            ds_known = set(c.get("business-policy.yaml", {}).get("data_status_values", []))
            if ds_known:
                wf_text = json.dumps(wf, ensure_ascii=False)
                used_ds = {m for grp in re.findall(r"data_status[^\"]*?\(([a-z_|]+)\)", wf_text) for m in grp.split("|")}
                report.check("W07", used_ds <= ds_known, f"{wf_name}: unknown data_status values {sorted(used_ds - ds_known)}")
            # every action a workflow may dispatch has a human approval path with exactly that action in the same workflow (owner-only actions are never hidden under another action)
            dispatched = {a for st in wf.get("steps", []) for a in st.get("command_actions", []) + ([st["command_action"]] if st.get("command_action") else [])}
            approved = set()
            for st in wf.get("steps", []):
                ap_ = st.get("approval") or {}
                approved |= ({ap_["policy_action"]} if ap_.get("policy_action") else set()) | {a for case in ap_.get("by_cause", []) for a in case.get("policy_actions", [])}
            needs_human = {a for a in dispatched if actions.get(a, {}).get("approvers")}
            report.check("W06", needs_human <= approved, f"{wf_name}: dispatched actions without their own approval path: {sorted(needs_human - approved)}")
    # execution / kill / restore
    if has("execution-policy.yaml"):
        e = c["execution-policy.yaml"]
        report.check("X01", e["command_states"] == COMMAND_STATES, "command state enum changed")
        report.check("X02", e["global_modes"] == GLOBAL_MODES and e["pipeline_modes"] == PIPELINE_MODES, "mode enums changed")
        report.check("X03", e["restore"]["start_mode"] == "killed", "restore must start killed")
        r = e["resume"]
        report.check("X04", r["after_global_kill"].startswith("min(") and "L1_approve_each" in r["after_global_kill"] and r["preserve_global_shadow"] is True, "resume after kill is min(previous, L1) and keeps global shadow")
        report.check("X05", r["released_entities_require_owner_retakeover"] is True and r["auto_retakeover_on_resume"] is False, "released entities need owner re-takeover")
        report.check("X06", e["maintenance_hold"]["is_kill"] is False and e["maintenance_hold"]["restore_previous_modes_on_release"] is True, "maintenance hold is not a kill")
        report.check("X07", e["kill_default_mode"] == "A" and "protective_pause" in e["kill_allows"], "kill default A; protective pause allowed")
        if has("readiness.yaml"):
            profs = set(c["readiness.yaml"]["profiles"])
            bad = {k: v for k, v in e["capability_requires_profile"].items() if v not in profs}
            report.check("X08", not bad, f"capability profiles unknown: {bad}")
            # X09 every capability is enabled in exactly one way (release capabilities_enabled or an owner raising transition)
            ce = e.get("capability_enablement", {})
            listed = list(ce.get("release_enabled", [])) + list((ce.get("transition_enabled") or {}).keys())
            report.check("X09", sorted(listed) == sorted(e["capability_requires_profile"]) and len(listed) == len(set(listed)) and ce.get("lowering_is_never_a_gate") is True,
                         f"capability_enablement must list every capability once: missing {sorted(set(e['capability_requires_profile']) - set(listed))}, extra {sorted(set(listed) - set(e['capability_requires_profile']))}")
    th = c.get("tracking-health.yaml", {})
    report.check("O01", th.get("fail_days_to_read_only") == 2 and th.get("fail_day_scope") == "any_gate_check" and (th.get("fail_streak") or {}).get("resets_on") == "all_gate_checks_pass_day", "Q37: any gate check fail on 2 fail days -> read_only; only an all-pass day resets the streak")
    qo = c.get("business-policy.yaml", {}).get("qualified_optimization_rule", {})
    report.check("O02", qo.get("owner_volume_floor_per_month") == 200 and qo.get("otherwise") == "optimize_for_Lead_with_qualified_as_guardrail", "Q29.1: QualifiedLead only above max(~200 lead/month, current official requirement); otherwise Lead")
    # O08 Q29.1 is measured per pipeline on a named event and window, re-measured monthly, switches up only after 2 consecutive
    # passes and back at the first miss (never a looser band), and only the owner switches (P-45)
    sched_ids_o = {r.get("id") for r in (c.get("operations.yaml", {}).get("schedule") or [])}
    rem = str(qo.get("remeasure", ""))
    up_ = qo.get("up_switch") if isinstance(qo.get("up_switch"), dict) else {}
    report.check("O08", qo.get("decision_rule") == "Q29_1_VOLUME" and qo.get("grain") == "per_pipeline" and "crm_confirmed" in str(qo.get("counted_event", ""))
                 and qo.get("window") == "previous_calendar_month" and qo.get("remeasure_schedule_id") == "qualified_volume_check" and "qualified_volume_check" in sched_ids_o
                 and qo.get("remeasure_schedule_id", "~") in rem and qo.get("threshold") == "max_floor_vendor"
                 and up_.get("consecutive_passes") == 2 and up_.get("threshold") == "max_floor_vendor"
                 and {"account_eligibility_evidence", "all_vendor_conditions"} <= set(up_.get("requires") or [])
                 and qo.get("down_switch") == {"measurements_below": 1, "threshold": "max_floor_vendor"}
                 and "owner events_manager_change" in str(qo.get("switch_actor", "")),
                 "business-policy.yaml#qualified_optimization_rule: per_pipeline grain, crm_confirmed counted event, previous_calendar_month window (the owner floor stays exact), "
                 "remeasure_schedule_id qualified_volume_check, up_switch {consecutive_passes: 2, threshold: max_floor_vendor, requires eligibility and vendor conditions}, "
                 "down_switch exactly {measurements_below: 1, threshold: max_floor_vendor} (no looser band), owner-only switch (P-45, P-56)")
    # O03-O06 lock the 2026-10-23 owner decisions on the host, backup, ingress and Jev in config
    ls = c.get("operations.yaml", {}).get("local_snapshot", {})
    if ls:
        pur = str(ls.get("pre_upgrade_run", ""))
        report.check("O03", ls.get("offsite_copy") is False and ls.get("retention_days") == 7 and "unencrypted" in str(ls.get("format", ""))
                     and "every upgrade" in pur and "schema-changing" not in pur and "pre-upgrade" in pur
                     and "catchup" in str(ls.get("target", "")) and str((ls.get("order") or [""])[0]).startswith("amt "),
                     "Q55: local snapshot only (no offsite copy), 7 days, unencrypted, taken before every upgrade (not only schema-changing ones); one directory per run (nightly, pre-upgrade, catchup); the amt dump comes first and is the consistency point")
    pv = c.get("privacy-policy.yaml", {})
    if pv:
        ds = {d.get("dataset"): d for d in pv.get("datasets", [])}
        hosts = " ".join(str(d.get("host", "")) for d in ds.values())
        wi = ds.get("webhook_inbox", {})
        report.check("O04", pv.get("at_rest_disk_encryption") is False and "Storage Box" not in hosts and "AMT PC" in str(ds.get("backups", {}).get("host", ""))
                     and "webhook_raw_inbox" not in ds and bool(wi) and "never written" in str(wi.get("fields", "")) and "disk encryption" not in str(wi.get("key", "")),
                     "Q54/Q55/Q62: disk unencrypted, backups only on the AMT PC, webhook PII never written to disk")
    svc = c.get("runtime-isolation.yaml", {}).get("services", [])
    if svc:
        def local_only(sv):
            lst = str(sv.get("listen", "")).strip()
            if sv.get("service_id") == "sshd":
                return lst.startswith("tailscale0") and "BindToDevice=tailscale0" in lst   # owner-confirmed: sshd only on the Tailscale interface
            if sv.get("service_id") == "tailscaled":
                return lst.startswith("tailscale0")
            return lst in ("none", "pinned in F4") or lst.startswith(("127.0.0.1:", "private ", "unix:", "/run/")) or lst in ("private socket", "private endpoint")
        open_listen = [f"{sv.get('service_id')}={sv.get('listen')}" for sv in svc if not local_only(sv)]
        ids = {sv.get("service_id") for sv in svc}
        known_fields = {"service_id", "unit", "uid", "listen", "db_role", "credential_file", "egress", "ack_class", "optional", "note"}
        stray = [f"{sv.get('service_id')}:{sorted(set(sv) - known_fields)}" for sv in svc if set(sv) - known_fields]
        report.check("S07", not stray, f"service registry rows carry unknown fields (an unquoted comma in a YAML flow mapping splits a value into a new key): {stray}")
        report.check("O05", not open_listen and {"cloudflared", "tailscaled", "sshd"} <= ids, f"Q57/Q58: no service listens outside loopback/sockets (tailscaled on tailscale0; sshd socket bound with BindToDevice=tailscale0); cloudflared, tailscaled and sshd registered: {open_listen}")
    tp = (c.get("_policy_templates") or {}).get("tailscale-policy.hujson")
    if "_policy_templates" in c:
        tp = tp or {}
        rules_ = (tp.get("acls") or []) + (tp.get("grants") or [])
        amt_src = [r for r in rules_ if any("tag:amt" in str(s) for s in r.get("src", []))]
        acl_ports = {p for r in tp.get("acls") or [] for d in r.get("dst", []) for p in re.findall(r"^tag:amt:(.+)$", str(d))}
        grant_open = [r for r in tp.get("grants") or [] if any("tag:amt" in str(d) for d in r.get("dst", [])) and set(map(str, r.get("ip", []))) - {"tcp:22", "22"}]
        deny_test = any(t_.get("src") == "tag:amt" and t_.get("deny") for t_ in tp.get("tests") or [])
        report.check("O07", bool(tp) and "tag:amt" in (tp.get("tagOwners") or {}) and not amt_src and acl_ports <= {"22"} and not grant_open and not tp.get("ssh") and deny_test,
                     "Q58: tailnet policy template - only the owner applies tag:amt, the only rule is owner -> tag:amt:22, no rule has tag:amt as source, no Tailscale SSH rule, tests assert the AMT node is denied")
    ps = c.get("approval-policy.yaml", {}).get("creative_review", {}).get("pre_screen")
    if ps is not None:
        prefs = ps.get("provider_preferences") or {}
        ok_ps = (ps.get("model") == "typesafe/jev-1.14" and ps.get("model_alias_allowed") is False and ps.get("router_allowed") is False
                 and ps.get("via") == "llm-proxy" and ps.get("called_by") == "gateway" and prefs.get("data_collection") == "deny"
                 and "not called" in str((ps.get("local_pii_guard") or {}).get("on_hit", "")) and ps.get("capability") == "review.pre_screen"
                 and ps.get("sees_lead_pii") is False and ps.get("effect") == "stricter_only" and ps.get("unavailable") == "wait" and ps.get("snapshot_mismatch") == "wait"
                 and set(ps.get("checks", [])) == {"meta_policy", "special_ad_category", "pii_leakage"} and ps.get("scope_ref") == "models.pre_screen")
        rk = {x["key"]: x for x in c.get("readiness.yaml", {}).get("requirements", [])}.get("models.pre_screen", {})
        ep = c.get("execution-policy.yaml", {})
        own_profile = (ep.get("capability_requires_profile") or {}).get("review.pre_screen") == "PRE_SCREEN" and "review.pre_screen" in ((ep.get("capability_enablement") or {}).get("release_enabled") or [])
        inherited = [n for n, pr in (c.get("readiness.yaml", {}).get("profiles") or {}).items() if "PRE_SCREEN" in (pr.get("requires") or [])]
        report.check("O06", ok_ps and own_profile and not inherited and rk.get("gate") == "PRE_SCREEN" and rk.get("accountable_role") == "owner",
                     f"Q61: Jev pre-screen pinned to typesafe/jev-1.14 via llm-proxy, no alias/router, data_collection deny, local PII guard before the call, no lead PII, stricter-only, waits when unavailable; own capability review.pre_screen and profile PRE_SCREEN that nothing inherits {inherited}")
    if has("kill-criteria.yaml"):
        k = c["kill-criteria.yaml"]
        kc1 = next((r for r in k["rules"] if r["id"] == "KC-01"), {})
        report.check("K01", kc1.get("worse_pct") == 25 and kc1.get("consecutive_weeks") == 2 and "pipeline_L0_shadow" in kc1.get("actions", []), "Q31: KC-01 >25% for 2 weeks -> L0")
        report.check("K02", k["resume"]["released_entities_require_owner_retakeover"] is True and k["resume"]["auto_retakeover_on_resume"] is False, "kill-criteria resume must not re-take released entities")
        if has("business-policy.yaml"):
            report.check("K03", c["business-policy.yaml"]["data_status_values"] == DATA_STATUS and set(k["data_status_actions"]) == set(DATA_STATUS), "data_status vocabulary must be identical in business-policy and kill-criteria")
        # K05 KC streak state machine (kill-criteria.yaml#streak): every data_status has an effect that matches data_status_actions,
        # states/transitions are closed, only the owner resume leaves `triggered`, and the exposure streak is bounded by KC-01
        st = k.get("streak") or {}
        eff = st.get("week_effects") or {}
        want_keys = (set(DATA_STATUS) - {"valid"}) | {"valid_worse", "valid_not_worse"}
        action_effect = {"count_exposure_and_bad_week": "increment", "inconclusive_streak_kept_exposure_clock_continues": "hold",
                         "not_evaluated": "hold", "blocked_and_alert": "blocked"}
        mism = sorted(s for s, a in (k.get("data_status_actions") or {}).items() if s != "valid" and eff.get(s) != action_effect.get(a))
        report.check("K05", set(eff) == want_keys and set(eff.values()) <= {"increment", "reset", "hold", "blocked"}
                     and eff.get("valid_worse") == "increment" and eff.get("valid_not_worse") == "reset" and not mism,
                     f"kill-criteria.yaml#streak.week_effects must map every data_status (valid split into valid_worse/valid_not_worse) to increment|reset|hold|blocked consistently with data_status_actions; mismatched {mism}")
        states, trans = set(st.get("states") or []), st.get("transitions") or []
        services = {str(sv.get("service_id")) for sv in (c.get("runtime-isolation.yaml", {}).get("services") or [])}
        bad_tr = [tr for tr in trans if tr.get("from") not in states or tr.get("to") not in states or not tr.get("guard")
                  or not (tr.get("actor") in services or tr.get("actor") in HUMAN_ACCOUNTABLE)]
        exits = {s for s in states if any(tr.get("from") == s and tr.get("to") != s for tr in trans)}
        out_of_triggered = {tr.get("actor") for tr in trans if tr.get("from") == "triggered" and tr.get("to") != "triggered"}
        exit_rules = {tr.get("rule") for tr in trans if tr.get("from") == "triggered" and tr.get("to") == "clear"}
        bp = st.get("blocked_policy") or {}
        report.check("K05", bp.get("cut_off") == "none" and bp.get("catch_up") == "every_sync_cycle" and bp.get("increases_blocked_while_blocked") is True
                     and str(bp.get("alert", "")).startswith("ALERT_") and bool(bp.get("alert_after")),
                     "kill-criteria.yaml#streak.blocked_policy: a blocked week is evaluated whenever its data arrives (no cut-off), increases stay blocked meanwhile, and an alert is routed (REVIEW_A1 #15)")
        lsb = st.get("low_sample_bound") or {}
        report.check("K05", "KC-01" in (lsb.get("applies_to") or []) and "max(qualified, min_sample)" in str(lsb.get("rule", "")) and bool(lsb.get("min_sample_unit")),
                     "kill-criteria.yaml#streak.low_sample_bound: KC-01 below min_sample increments when spend / max(qualified, min_sample) exceeds the threshold; min_sample unit stated (REVIEW_A1 #8)")
        report.check("K05", set(st.get("applies_to") or []) <= exit_rules,
                     f"kill-criteria.yaml#streak: every rule in applies_to needs its own owner exit from triggered (REVIEW_A1 #6); exits for {sorted(map(str, exit_rules))}")
        kc_ids = {r.get("id") for r in k.get("rules", [])}
        pin = {"valid_worse": "increment", "spend_zero_qualified": "increment", "valid_not_worse": "reset", "insufficient_sample": "hold", "not_mature": "hold",
               "incomparable_baseline": "hold", "no_activity": "hold", "no_spend": "hold", "missing_data": "blocked", "stale_data": "blocked"}
        dsa = k.get("data_status_actions") or {}
        report.check("K05", all(eff.get(s) == e for s, e in pin.items()) and dsa.get("spend_zero_qualified") == "count_exposure_and_bad_week"
                     and dsa.get("missing_data") == "blocked_and_alert" and dsa.get("stale_data") == "blocked_and_alert",
                     f"kill-criteria.yaml#streak.week_effects must keep the P-40 semantics {pin} and data_status_actions for spend_zero_qualified / missing / stale (REVIEW_A1 #10)")
        sem_bad = []
        for tr_ in trans:
            e, fr, to = tr_.get("on_effect"), tr_.get("from"), tr_.get("to")
            if e in ("hold", "blocked") and fr != to:
                sem_bad.append(tr_)
            elif e == "reset" and (to != "clear" or fr == "triggered"):
                sem_bad.append(tr_)
            elif e == "increment" and (fr == "triggered" or to not in ("counting", "triggered")):
                sem_bad.append(tr_)
            elif e == "owner_clear" and (fr != "triggered" or to != "clear" or tr_.get("actor") != "owner"):
                sem_bad.append(tr_)
            elif e not in ("increment", "reset", "hold", "blocked", "owner_clear"):
                sem_bad.append(tr_)
        covered_e = {(tr_.get("from"), tr_.get("on_effect")) for tr_ in trans}
        need_e = {(s, e) for s in ("clear", "counting") for e in ("increment", "reset", "hold", "blocked")}
        bound = (k.get("low_data") or {}).get("bad_week_streak_bound")
        rvc = [vc for vc in ((c.get("readiness.yaml", {}).get("rules") or {}).get("value_constraints") or [])
               if vc.get("key") == "business.exposure" and vc.get("field") == "bad_week_streak"]
        kc1c = next((r for r in k.get("rules", []) if r.get("id") == "KC-01"), {}).get("consecutive_weeks")
        report.check("K05", not sem_bad and need_e <= covered_e and isinstance(bound, dict) and bound.get("max_ref") == "rules[id=KC-01].consecutive_weeks"
                     and bound.get("counts") == "streak.counter" and bound.get("on_reach") == "handback" and any(vc.get("max") == kc1c for vc in rvc),
                     f"kill-criteria.yaml#streak.transitions: on_effect semantics (hold/blocked keep the state, reset goes to clear, increment counts, only owner_clear leaves triggered) {sem_bad[:2]}, "
                     f"every (state, effect) covered {sorted(need_e - covered_e)}; low_data.bad_week_streak_bound structured and readiness value_constraints business.exposure bad_week_streak max = KC-01 consecutive_weeks (REVIEW_A1 #10, #22)")
        report.check("K05", {"clear", "counting", "triggered"} <= states and not bad_tr and exits == states - set(st.get("terminal") or [])
                     and out_of_triggered == {"owner"} and set(st.get("applies_to") or []) <= kc_ids and st.get("blocked_rule") and st.get("hold_rule")
                     and st.get("measurement_revision") and bool(st.get("illegal")) and "consecutive_weeks" in str((k.get("low_data") or {}).get("bad_week_streak_bound", "")),
                     f"kill-criteria.yaml#streak: closed states/transitions with guard and a registry or human actor {bad_tr[:2]}, every non-terminal state has an exit, "
                     f"only the owner leaves triggered ({sorted(map(str, out_of_triggered))}), hold/blocked/revision rules, illegal list and the exposure streak bound")
        tr_keys = {"from", "to", "on_effect", "guard", "actor", "rule"}
        odd_tr = [x for x in st.get("transitions") or [] if not isinstance(x, dict) or set(x) - tr_keys or not (isinstance(x.get("guard"), str) and x.get("guard"))]
        report.check("K05", not odd_tr, f"kill-criteria.yaml#streak.transitions: entries with keys outside {sorted(tr_keys)} or without a guard text (a split-off fragment changes the state machine): {odd_tr[:2]}")
        # K06 the Step 1 -> Step 2 rule is pre-registered: verdict_rule in business.acceptance (gate F5_GO, inherited by F6_STEP1),
        # approved before HG-F6-01, with an extension unit, a max_weeks reference, hold at the maximum and the approver bound
        s1 = k.get("step1_timing") or {}
        rd = c.get("readiness.yaml", {})
        acc = {x["key"]: x for x in rd.get("requirements", [])}.get("business.acceptance", {})
        try:
            pre_live = acc.get("gate") in profile_closure(rd.get("profiles") or {}, "F6_STEP1")
        except KeyError:
            pre_live = False
        report.check("K06", s1.get("decision_rule") == "STEP1_TO_STEP2" and s1.get("verdict_rule_ref") == "business.acceptance" and pre_live
                     and s1.get("pre_registered_before") == "HG-F6-01" and bool(s1.get("extension_unit")) and s1.get("max_weeks_ref") == "business.acceptance"
                     and "never auto" in str(s1.get("at_max", "")) and bool(s1.get("approver_bound")) and bool(s1.get("evaluations_record"))
                     and s1.get("extension_unit_weeks") == 1 and "event_week" in str(s1.get("extension_unit", "")) and "unadjusted repeated looks are not allowed" in str(s1.get("looks_rule", "")),
                     "kill-criteria.yaml#step1_timing: Step 2 rule pre-registered (business.acceptance verdict_rule, gated before F6_STEP1, approved before HG-F6-01), "
                     "extension unit, max_weeks reference, hold at the maximum and never auto-advance, approver bound, evaluations record")
    # K04 shared statistical decision spec (decision-statistics.yaml): every rule names the required parameters in a valid
    # value form, and every consumer it lists carries decision_rule: <id>; every decision_rule used anywhere is defined
    if has("decision-statistics.yaml"):
        ds = c["decision-statistics.yaml"]
        req = list(ds.get("required_parameters") or [])
        report.check("K04", {"method", "mde", "alpha", "power", "min_exposure", "max_extension", "non_inferiority_margin"} <= set(req),
                     "decision-statistics.yaml#required_parameters must include method, mde, alpha, power, min_exposure, max_extension, non_inferiority_margin")
        must = {"KC-01", "KC-02", "STEP1_TO_STEP2", "TRUST_RAMP_GRADUATION", "SHADOW_WEEK", "EXPERIMENT", "Q29_1_VOLUME"}   # REVIEW_A1 #12: equals required_rules
        rr = set(ds.get("required_rules") or [])
        report.check("K04", must <= rr and rr <= set(ds.get("decision_rules") or {}),
                     f"decision-statistics.yaml#required_rules must cover {sorted(must)} and each must be defined; missing {sorted((must - rr) | (rr - set(ds.get('decision_rules') or {})))}")
        rk = {x["key"] for x in c.get("readiness.yaml", {}).get("requirements", [])}
        drules = ds.get("decision_rules") or {}
        for rid, rule in drules.items():
            rule = rule or {}
            bad = []
            for par in req:
                v = rule.get(par)
                sv = str(v).strip() if v is not None else ""
                m = re.match(r"readiness:([a-z_]+\.[a-z_]+)", sv)
                if not sv or (sv.startswith("readiness:") and not (m and m.group(1) in rk)) or (sv.startswith("not_applicable") and not sv.partition(":")[2].strip()):
                    bad.append(par)
                elif par in ("mde", "alpha", "power", "min_exposure", "max_extension", "non_inferiority_margin") and not sv.startswith(("readiness:", "not_applicable")) \
                        and not re.search(r"(✅|★|◇|\bQ\d{2}|\bP-\d{2})", sv):
                    bad.append(f"{par} (literal without a ✅/Q, ★ or ◇/P source)")
            report.check("K04", not bad and bool(rule.get("owner_refs")) and bool(rule.get("consumers")),
                         f"decision-statistics.yaml#decision_rules.{rid}: parameters {bad} missing or not literal / readiness:<known key> / 'not_applicable: <reason>'; owner_refs and consumers required")
            for cons in rule.get("consumers") or []:
                f, _, path = str(cons).partition("#")
                if not f.endswith(".yaml"):
                    continue   # document consumers are checked by the document rules
                obj = c.get(f) if f in c else c.get("_workflows", {}).get(f.rsplit("/", 1)[-1])
                try:
                    node = get_path(obj, path) if obj is not None else None
                except (KeyError, IndexError, TypeError):
                    node = None
                report.check("K04", isinstance(node, dict) and node.get("decision_rule") == rid,
                             f"decision rule {rid}: consumer {cons} does not resolve to a node with decision_rule: {rid}")
        used = set()
        listed_nodes = set()
        for rid_, rule_ in drules.items():
            for cons in (rule_ or {}).get("consumers") or []:
                f_, _, path_ = str(cons).partition("#")
                obj_ = c.get(f_) if f_ in c else c.get("_workflows", {}).get(f_.rsplit("/", 1)[-1])
                try:
                    listed_nodes.add(id(get_path(obj_, path_))) if obj_ is not None and f_.endswith(".yaml") else None
                except (KeyError, IndexError, TypeError):
                    pass
        unlisted = []

        def walk(o):
            if isinstance(o, dict):
                if "decision_rule" in o:
                    used.add(str(o["decision_rule"]))
                    if id(o) not in listed_nodes:
                        unlisted.append(str(o["decision_rule"]))
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        for name, obj in c.items():
            if not name.startswith("_"):
                walk(obj)
        for wf in c.get("_workflows", {}).values():
            walk(wf)
        report.check("K04", used <= set(drules), f"decision_rule ids used but not defined in decision-statistics.yaml: {sorted(used - set(drules))}")
        report.check("K04", not unlisted, f"config nodes apply decision rules {unlisted} but are not listed among that rule's consumers (two-way link, REVIEW_A1 #12)")
        # K07 the F5 shadow criterion has a minimum sample and a bounded extension (P-44)
        sw = drules.get("SHADOW_WEEK")
        if sw is not None:
            me = str((sw or {}).get("min_exposure", ""))
            mr = (sw or {}).get("material_rule") or {}
            report.check("K07", (sw or {}).get("max_extensions") == 2 and (sw or {}).get("extension_unit") == "P7D"
                         and str((sw or {}).get("max_extension", "")).startswith("two extensions of P7D"),
                         "decision-statistics.yaml#decision_rules.SHADOW_WEEK: max_extensions 2, extension_unit P7D and a max_extension text that states the same bound (REVIEW_A1 #12)")
            report.check("K07", (sw or {}).get("zero_harmful_windows") == ["days_5_to_7", "last_3_days_of_final_window"]
                         and mr.get("statistic") == "wilson_lower_bound" and isinstance(mr.get("min_items"), int) and isinstance(mr.get("lower_bound_at_least"), (int, float))
                         and "harmful" in str((sw or {}).get("reasonless_ratings", "")),
                         "decision-statistics.yaml#decision_rules.SHADOW_WEEK: zero_harmful_windows = [days_5_to_7, last_3_days_of_final_window], material_rule (Wilson lower bound with min_items), reasonless_ratings (P-54)")
            report.check("K07", bool(re.search(r"min_rated_items \d+", me)) and bool(re.search(r"min_material_items \d+", me))
                         and "P7D" in str((sw or {}).get("max_extension", "")) and "HG-F5-02" in str((sw or {}).get("max_extension", "")),
                         "decision-statistics.yaml#decision_rules.SHADOW_WEEK: min_exposure names min_rated_items N and min_material_items M; max_extension is bounded P7D steps ending at HG-F5-02")
    # readiness model
    if has("readiness.yaml"):
        readiness_rules(c["readiness.yaml"], report)
        keys = {r["key"] for r in c["readiness.yaml"]["requirements"]}
        refs = set()
        for name, obj in c.items():
            if name.startswith("_") or name == "readiness.yaml":
                continue
            refs |= set(re.findall(r"readiness:([a-z_]+\.[a-z_]+)", yaml.safe_dump(obj)))
            refs |= collect_ref_values(obj)
        for wf in c.get("_workflows", {}).values():
            refs |= set(re.findall(r"readiness:([a-z_]+\.[a-z_]+)", yaml.safe_dump(wf)))
        missing = sorted(r for r in refs if r not in keys)
        report.check("R10", not missing, f"readiness references to unknown keys: {missing}")
    # roles / RBAC
    if has("roles.yaml"):
        ro = c["roles.yaml"]
        report.check("B01", ro["roles"] == RBAC_ROLES and set(ro["role_permissions"]) == set(RBAC_ROLES), "RBAC roles must be the six Telegram roles")
        flags = set(ro["flags"])
        for role, spec in ro["role_permissions"].items():
            report.check("B02", set(spec.get("default_flags", [])) <= flags, f"{role}: unknown default flag")
        report.check("B03", ro.get("at_least_one_active_owner_required") is True and ro.get("export_must_not_reseed") is True, "owner presence and no reseed")
    # services / isolation / release
    if has("runtime-isolation.yaml", "release-policy.yaml"):
        ri, rp = c["runtime-isolation.yaml"], c["release-policy.yaml"]
        report.check("V01", set(ri["agents"]) == BUSINESS_AGENTS and set(ri["engineering_roles"]) == ENGINEERING_ROLES, "agent and engineering role registries")
        uids = [v["uid"] for v in ri["agents"].values()] + [v["uid"] for v in ri["engineering_roles"].values()]
        report.check("V02", len(uids) == len(set(uids)), "every agent/engineering role needs its own UID")
        services = {s["service_id"]: s for s in ri["services"]}
        report.check("V03", len(services) == len(ri["services"]), "duplicate service_id")
        wg = {s for s, v in services.items() if v["ack_class"] == "write_gate"}
        fg = {s for s, v in services.items() if v["ack_class"] == "function_gate"}
        report.check("V04", set(rp["write_gate_acks"]) == wg and set(rp["function_gate_acks"]) == fg, "release ACK lists must equal the registry ack_class sets")
        ra = rp.get("release_approval", {})
        need_bind = {"manifest_digest", "verification_id", "verdict", "evaluator_revision", "proposal_revision", "policy_revision", "role_revision", "control_epoch"}
        report.check("V10", need_bind <= set(ra.get("bound_to", [])), f"release approval binding incomplete: missing {sorted(need_bind - set(ra.get('bound_to', [])))}")
        if has("evolution-policy.yaml"):
            ur = c["evolution-policy.yaml"].get("gates", {}).get("upgrade_release", {})
            report.check("V10", ur.get("binds_ref") == "release-policy.yaml#release_approval.bound_to" and "binds" not in ur, "evolution-policy upgrade_release must reference the single release-policy binding list")
        report.check("V05", rp["artifact_identity"] == "build_once_promote" and rp["tag_ruleset"]["create_update_delete"] == ["owner"] and rp["tag_ruleset"]["signed_annotated_tag_required"] is True and ra.get("record") == "release_approvals" and ra.get("required_from") == "F1" and "manifest_digest" in ra.get("bound_to", []) and ra.get("tag_only_release") == "never", "release identity, owner-only signed tags and a release_approvals record from F1 (never tag-only)")
        report.check("V06", rp["out_of_scope"]["release_controller_holds_dokploy_or_landing_credentials"] is False, "Q46.4: release controller has no landing/Dokploy credentials")
        report.check("V07", ri.get("provider_keys_on_agents") is False and ri.get("same_uid_tokens_count_as_isolation") is False, "agents hold no provider keys; same-UID tokens are not isolation")
    if "environments.yaml" in c:
        envs = c["environments.yaml"]["environments"]
        prod = envs.get("prod", {})
        clash = []
        for name, env in envs.items():
            if name == "prod":
                continue
            env_names = set(c["environments.yaml"]["environments"])
            env_line = next((l for l in str(c.get("_env", "")).splitlines() if l.startswith("AMT_ENV=")), "")
            listed_envs = set(re.findall(r"[a-z_]+", env_line.split("]", 1)[-1].split("(")[0])) if env_line else set()
            report.check("V11", bool(env_line) and listed_envs == env_names, f"env.example AMT_ENV lists {sorted(listed_envs)} but environments.yaml has {sorted(env_names)}")
            def lead(v):
                s = str(v).strip()
                return s.split()[0].strip(",;:()[]{}'\"") if s else s
            def toks(v):   # every token of the value (split on spaces and '=', surrounding punctuation removed)
                return {t.strip(",;:.()[]{}'\"`") for t in re.split(r"[\s=]+", str(v))} - {""}
            def prod_ids(v):   # the production leading token plus every path- or id-like token of the production value
                return {lead(v)} | {t for t in toks(v) if re.search(r"[/.:_#]|\d", t)}
            def shares(a, b):
                # path- or id-like production tokens are searched as substrings of the raw value, so an annotation glued to it
                # (shared:/x, path=/x, `/x`, /x., /x/) cannot hide a shared path; bare names (amt, main) need token equality
                raw = re.sub(r"/{2,}", "/", str(b))
                ids = prod_ids(a)
                pathlike = {re.sub(r"/{2,}", "/", t).rstrip("/.") for t in ids if re.search(r"[/.:_#]|\d", t)} - {""}   # both sides normalised
                return any(p in raw for p in pathlike) or bool((ids - {t for t in ids if re.search(r"[/.:_#]|\d", t)}) & toks(b))
            for field in c["environments.yaml"]["must_not_intersect_with_prod"]:
                a, b = prod.get(field), env.get(field)
                if field not in env or field not in prod:
                    clash.append(f"{name}.{field} (undeclared)")   # an absent field would pass vacuously
                elif a not in (None, "none") and b not in (None, "none") and shares(a, b):
                    clash.append(f"{name}.{field}")
            for field in c["environments.yaml"].get("must_declare", []):
                if field not in env or field not in prod:
                    clash.append(f"{name}.{field} (undeclared)")
        report.check("V09", not clash, f"non-production environments reuse production resources or leave an isolation field undeclared: {clash}")
    # env names only
    env = c.get("_env", "")
    bad = []
    for line in env.splitlines():
        m = re.match(r"([A-Z0-9_]+)=(\S*)(.*)$", line)
        if m and m.group(2) and "[secret" in m.group(3):
            bad.append(m.group(1))
    report.check("V08", not bad, f"env.example secret variables must be empty: {bad}")
    # schedule consistency
    if has("operations.yaml"):
        sched = c["operations.yaml"]["schedule"]
        if has("capacity-policy.yaml"):
            col = c["capacity-policy.yaml"]["collection"]
            report.check("T01", (col["ask"], col["remind"], col["escalate"]) == (schedule_time(sched, "fleet_ask"), schedule_time(sched, "fleet_remind"), schedule_time(sched, "fleet_escalate")), "fleet times differ between capacity-policy and operations.schedule")
            report.check("T02", col["batch_cutoff"] == schedule_time(sched, "batch_cutoff"), "batch cutoff differs")
        if has("approval-policy.yaml"):
            report.check("T03", c["approval-policy.yaml"]["change_set"]["daily_batch_time"] == schedule_time(sched, "change_set"), "change set time differs")
        if has("tracking-health.yaml"):
            report.check("T04", str(c["tracking-health.yaml"]["job_time"]).startswith(schedule_time(sched, "tracking_health") or "--"), "tracking job time differs")
        if has("kill-criteria.yaml"):
            report.check("T05", (schedule_time(sched, "kill_criteria") or "--") in c["kill-criteria.yaml"]["schedule"], "kill-criteria time differs")
        wf = c.get("_workflows", {})
        for wf_name, sid in (("WF-O01.yaml", "fleet_ask"), ("WF-B03.yaml", "media_buyer_daily"), ("WF-B06.yaml", "kill_criteria"), ("WF-E03.yaml", "dependency_check"), ("WF-O03.yaml", "restore_check")):
            if wf_name in wf:
                report.check("T06", cron_time(wf[wf_name]["trigger"].get("schedule")) == schedule_time(sched, sid), f"{wf_name} cron differs from operations.schedule {sid}")
        sbk = (wf.get("WF-O01.yaml", {}).get("trigger") or {}).get("schedules_by_key", {})
        if sbk:
            report.check("T06", cron_time(sbk.get("fleet")) == schedule_time(sched, "fleet_ask") and cron_time(sbk.get("sale_readiness")) == schedule_time(sched, "sale_ready"), "WF-O01 per-key crons differ from operations.schedule fleet_ask/sale_ready")
            esc = (wf.get("WF-O01.yaml", {}).get("limits") or {}).get("escalation", [])
            report.check("T08", {e.get("key") for e in esc} >= set(sbk), "WF-O01: every schedules_by_key key needs its own escalation")
        # T08 an escalation whose channel names a schedule slot "(<schedule id> HH:MM)" (and every keyed escalation) lands
        # exactly there: run start (the key's cron for a keyed escalation, else the trigger cron) + after = HH:MM = the
        # operations.schedule time of that id
        for wf_name, wf_def in wf.items():
            trig8 = wf_def.get("trigger") or {}
            sbk8 = trig8.get("schedules_by_key") or {}
            for e in (wf_def.get("limits") or {}).get("escalation") or []:
                named = re.search(r"\(([a-z_]+) (\d{2}:\d{2})\)", str(e.get("channel", "")))
                if e.get("key") is None and not named:
                    continue
                start = cron_time(sbk8.get(e["key"])) if e.get("key") is not None else cron_time(trig8.get("schedule"))
                ok_esc = bool(named and start) and (e.get("key") is None or e["key"] in sbk8)
                if ok_esc:
                    try:
                        h, mi = map(int, start.split(":"))
                        t8 = dt.datetime(2026, 1, 1, h, mi) + iso_duration(str(e["after"]))
                        ok_esc = t8.strftime("%H:%M") == named.group(2) == schedule_time(sched, named.group(1))
                    except ValueError:
                        ok_esc = False
                report.check("T08", ok_esc, f"{wf_name} escalation {e}: run start + after must land on the schedule slot its channel names ('(<schedule id> HH:MM)') and on that operations.schedule time")
        if has("sale-readiness.yaml"):
            cad = re.search(r"(\d{2}:\d{2})", str(c["sale-readiness.yaml"].get("cadence", "")))
            report.check("T09", bool(cad) and cad.group(1) == schedule_time(sched, "sale_ready_cutoff"), "sale-readiness.yaml cadence cutoff differs from operations.schedule sale_ready_cutoff")
    # T11 every operations.yaml#schedule entry says what runs it (workflow-policy.yaml#schedule_execution): a workflow
    # (its step and its schedule timer resolve) or a deterministic job of a registry service with a missed-run alert
    if has("operations.yaml", "workflow-policy.yaml"):
        sched_rows = c["operations.yaml"].get("schedule") or []
        sx = c["workflow-policy.yaml"].get("schedule_execution") or {}
        tcat_all = c["workflow-policy.yaml"].get("timer_catalog") or {}
        wf_by = {wf.get("workflow_id"): wf for wf in (c.get("_workflows") or {}).values()}
        svc = {str(sv.get("service_id")) for sv in (c.get("runtime-isolation.yaml", {}).get("services") or [])}
        humans_ok = set(c.get("roles.yaml", {}).get("roles") or []) | set(c.get("roles.yaml", {}).get("responsibility_assignments") or {})
        ids_sched = [r.get("id") for r in sched_rows]
        alerts11 = set(c.get("_alert_codes") or [])
        report.check("T11", bool(alerts11), "03_Architecture/TELEGRAM.md section 6.2 alert catalog not found (T11 checks every missed_run_alert against it)")
        report.check("T11", set(c["workflow-policy.yaml"].get("schedule_protective") or []) <= set(ids_sched), "workflow-policy.yaml#schedule_protective names ids that are not in operations.yaml#schedule")
        report.check("T11", set(ids_sched) == set(sx), f"schedule ids without schedule_execution {sorted(set(ids_sched) - set(sx))}; schedule_execution ids not in operations.yaml#schedule {sorted(set(sx) - set(ids_sched))}")
        for row in sched_rows:
            sid, e = row.get("id"), sx.get(row.get("id")) or {}
            if not e:
                continue
            if e.get("missed_run_alert") is not None:
                report.check("T11", e["missed_run_alert"] in alerts11, f"schedule {sid}: missed_run_alert {e['missed_run_alert']} is not an alert code of TELEGRAM.md section 6.2")
            prot_ids = set(c["workflow-policy.yaml"].get("schedule_protective") or [])
            if e.get("workflow") and sid in prot_ids:
                wf_p = wf_by.get(e["workflow"]) or {}
                report.check("T11", str(e.get("missed_run_alert", "")).startswith("ALERT_") and bool(e.get("step")) and not ((wf_p.get("input") or {}).get("freshness")),
                             f"schedule {sid} is protective: its workflow entry needs a step, a missed_run_alert, and a workflow with no start freshness (stale data is recorded inside the step, the run never fails to start)")
            if e.get("workflow"):
                wf_ = wf_by.get(e["workflow"])
                ok = wf_ is not None and not e.get("job") and bool(e.get("step") or e.get("timer"))
                if ok and e.get("step"):
                    ok = e["step"] in {st.get("id") for st in wf_.get("steps", [])}
                if ok and e.get("timer"):
                    t_ = tcat_all.get(e["timer"]) or {}
                    ok = e["timer"] in ((wf_.get("continuation") or {}).get("timers") or []) and t_.get("kind") == "schedule" and t_.get("ref") == sid
                elif ok:   # no timer: the schedule starts the run (trigger.source_refs) or the step declares that it follows the slot (schedule_refs)
                    st_ = next((st for st in wf_.get("steps", []) if st.get("id") == e.get("step")), {})
                    ok = sid in ((wf_.get("trigger") or {}).get("source_refs") or []) or sid in (st_.get("schedule_refs") or [])
                report.check("T11", ok, f"schedule {sid}: schedule_execution {e} must name an existing workflow with one of its steps and/or a schedule timer of it that refers to {sid}; without a timer {sid} must be in that workflow's trigger.source_refs or the step's schedule_refs")
            else:
                ok = e.get("job") in svc and str(e.get("missed_run_alert", "")).startswith("ALERT_") and (e.get("human") is None or e["human"] in humans_ok)
                who = str(row.get("who", ""))
                ok = ok and (e.get("job") in who or (e.get("human") or "#") in who)
                report.check("T11", ok, f"schedule {sid}: schedule_execution {e} must name a workflow, or a job of a registry service named in `who` with a missed_run_alert")
        # converse: a step that declares a schedule slot is the step schedule_execution maps that slot to
        for wf_ in wf_by.values():
            for st in wf_.get("steps", []):
                for sr in st.get("schedule_refs") or []:
                    e = sx.get(sr) or {}
                    report.check("T11", e.get("workflow") == wf_.get("workflow_id") and e.get("step") == st.get("id"),
                                 f"{wf_.get('workflow_id')} {st.get('id')}: schedule_refs {sr} is not mapped to this step in workflow-policy.yaml#schedule_execution")
    # evolution policy
    if has("evolution-policy.yaml"):
        ev = c["evolution-policy.yaml"]
        report.check("E01", ev["promotion"]["auto_release"]["enabled"] is False, "auto-release must stay disabled (Q11; OD-03)")
        report.check("E02", ev["separation_of_duties"]["author_can_verify_own_candidate"] is False and ev["separation_of_duties"]["author_can_release"] is False, "separation of duties")
        report.check("E03", ev["outcome"]["lifecycle"] == LIFECYCLE and ev["outcome"]["terminal"] == TERMINAL and ev["outcome"]["inconclusive_allows_scale_or_autonomy"] is False, "lifecycle vocabulary")
        prot = " ".join(map(str, ev["protected_surfaces"]))
        for needle in ("approval-policy.yaml", "execution-policy.yaml", "budgets.yaml", "release-controller", "INVARIANTS", "DECISION_LOG", "validate_bundle"):
            report.check("E04", needle in prot, f"protected surfaces must include {needle}")
        no_eng = " ".join(map(str, ev.get("engineering_may_not_change", [])))
        tmpl = sorted(k for k in c if k.endswith(".yaml"))
        uncovered = [n for n in tmpl if f"config/{n}" not in prot and f"config/{n}" not in no_eng]
        report.check("E07", not uncovered, f"config templates neither protected nor engineering_may_not_change: {uncovered}")
    if has("resource-policy.yaml") and has("runtime-isolation.yaml"):
        sl = c["resource-policy.yaml"].get("slices", {})
        assigned = [x for v in sl.values() for x in v]
        ids = [str(sv["service_id"]) for sv in c["runtime-isolation.yaml"].get("services", [])]
        dup = sorted({x for x in assigned if assigned.count(x) > 1})
        report.check("E08", sorted(set(assigned)) == sorted(ids) and not dup, f"resource-policy slices must hold every service_id exactly once: missing {sorted(set(ids) - set(assigned))}, unknown {sorted(set(assigned) - set(ids))}, duplicate {dup}")
    if has("engineering-budget.yaml"):
        eb = c["engineering-budget.yaml"]
        report.check("E05", eb["shares_runtime_ai_cap"] is False and eb["shares_ads_cap"] is False and eb["paid_engineering_enabled"] is False, "engineering budget separate and disabled until OD-02")
    if has("execution-policy.yaml"):
        cond = c["execution-policy.yaml"].get("capability_extra_conditions", {}).get("release.auto", "")
        report.check("E06", "auto_release.enabled == true" in cond, "release.auto also requires evolution-policy auto_release.enabled")
    # workflow definitions
    workflow_rules(c, report)


def collect_ref_values(obj) -> set[str]:
    found = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and ("readiness" in k and (k.endswith("_ref") or k.endswith("_refs") or k.endswith("readiness"))):
                vals = v if isinstance(v, list) else [v]
                found |= {x for x in vals if isinstance(x, str) and re.fullmatch(r"[a-z_]+\.[a-z_]+", x)}
            found |= collect_ref_values(v)
    elif isinstance(obj, list):
        for v in obj:
            found |= collect_ref_values(v)
    return found


def readiness_rules(r: dict, report: Report):
    profiles = r["profiles"]
    report.check("R01", all(set(p.get("requires", [])) <= set(profiles) for p in profiles.values()), "profile requires unknown profile")
    # cycle check
    state = {}

    def visit(n):
        if state.get(n) == 1:
            return False
        if state.get(n) == 2:
            return True
        state[n] = 1
        ok = all(visit(m) for m in profiles[n].get("requires", []) if m in profiles)
        state[n] = 2
        return ok
    report.check("R02", all(visit(n) for n in profiles), "profile DAG has a cycle")
    keys = [x["key"] for x in r["requirements"]]
    report.check("R03", len(keys) == len(set(keys)), "duplicate readiness key")
    accountable = set(r["accountable_roles"])
    report.check("R04", accountable <= HUMAN_ACCOUNTABLE, "accountable_roles must be human roles")
    for rec in r["requirements"]:
        k = rec["key"]
        report.check("R05", isinstance(rec.get("gate"), str) and rec["gate"] in profiles, f"{k}: exactly one known gate profile required")
        report.check("R06", rec["accountable_role"] in accountable and all(cs in accountable for cs in rec.get("co_signers", [])), f"{k}: accountable/co-signers must be human roles")
        report.check("R07", rec.get("criticality") in ("critical", "optional"), f"{k}: criticality")
        report.check("R08", rec.get("status") in r["record_states"], f"{k}: unknown status")
        if rec.get("status") == "not_applicable":
            report.check("R09", rec.get("criticality") == "optional", f"{k}: not_applicable only for optional requirements")
        if rec.get("max_evidence_age"):
            try:
                iso_duration(rec["max_evidence_age"])
            except ValueError as exc:
                report.check("R11", False, f"{k}: {exc}")
        if r.get("bundle_state") == "template":
            report.check("R12", rec.get("status") == "pending" and rec.get("approved_by") is None, f"{k}: template must not carry approvals")
    ages = {"budget.ads_fresh_check": "P1D", "sale.readiness": "P1D", "ops.ads_handback_roster": "P7D", "ops.sale_handback_roster": "P7D", "recovery.restore_check": "P30D", "recovery.full_drill": "P92D"}
    by_key = {x["key"]: x for x in r["requirements"]}
    for k, age in ages.items():
        report.check("R13", by_key.get(k, {}).get("max_evidence_age") == age, f"{k}: max_evidence_age must be {age}")
    for k in ("auto_release.decision_ref", "evolution.fe_acceptance", "engineering.independent_reviewer", "vendor.runner_isolation_final", "vendor.meta_cap", "budget.ads_fresh_check", "recovery.full_drill"):
        report.check("R15", by_key.get(k, {}).get("criticality") == "critical", f"{k}: must be critical (never not_applicable)")
    report.check("R14", r.get("record_fields", [])[-3:] == ["approved_at", "co_signatures", "valid_until"] and "evidence_prepared_by" in r.get("record_fields", []), "readiness record fields must carry evidence_prepared_by and co_signatures")
    # R20 value constraints are well formed, and the C-28 combination (class_e_frozen offered while FE_RELEASE is in closure(F5_GO), P-11) is encoded
    vcs = (r.get("rules") or {}).get("value_constraints") or []
    for vc in vcs:
        cond = vc.get("refused_while") or {}
        numeric = "max" in vc
        report.check("R20", vc.get("key") in by_key and re.fullmatch(r"C-\d{2}", str(vc.get("conflict", ""))) and bool(vc.get("reason"))
                     and ((numeric and bool(vc.get("field")) and isinstance(vc.get("max"), (int, float)))
                          or (not numeric and bool(vc.get("value")) and cond.get("profile") in profiles and cond.get("closure_contains") in profiles)),
                     f"value constraint {vc}: needs a known key, a C-NN conflict, a reason and either {{value, refused_while {{profile, closure_contains}}}} or {{field, max}}")
    av = (r.get("rules") or {}).get("approvable_values") or {}
    report.check("R20", {"person_ref", "class_e_frozen"} <= set(av.get("engineering.independent_reviewer") or []) and all(k in by_key for k in av),
                 "readiness.yaml#rules.approvable_values must list the OD-12 options person_ref and class_e_frozen for engineering.independent_reviewer (data, not description text)")
    rev = by_key.get("engineering.independent_reviewer", {})
    try:
        fe_before_go = "F5_GO" in profiles and "FE_RELEASE" in profile_closure(profiles, "F5_GO")
    except KeyError:   # unknown profile names are reported by the DAG rules
        fe_before_go = False
    if ("class_e_frozen" in (av.get("engineering.independent_reviewer") or []) or "class_e_frozen" in str(rev.get("description", ""))) and fe_before_go:
        report.check("R20", any(vc.get("key") == rev.get("key") and vc.get("value") == "class_e_frozen"
                                and (vc.get("refused_while") or {}) == {"profile": "F5_GO", "closure_contains": "FE_RELEASE"} for vc in vcs),
                     "engineering.independent_reviewer offers class_e_frozen while FE_RELEASE is in closure(F5_GO) (P-11): class E config and secret-rotation "
                     "releases would be refused and F6_STEP1 unreachable; rules.value_constraints must refuse it (C-28)")
    report.facts["readiness_keys"] = len(keys)
    report.facts["profiles"] = len(profiles)


    # R19 agents prepare evidence only for keys whose gate inherits F4_AGENTS (agents.run); earlier keys are builder-prepared
    agent_slugs = {"cmo", "media-buyer", "creative-studio", "cro", "funnel-analyst", "reviewer"}
    if r.get("profiles") and r.get("requirements"):
        def inherits_agents(gate):
            try:
                return gate != "F4_AGENTS" and "F4_AGENTS" in profile_closure(r["profiles"], gate)
            except KeyError:   # unknown profile names are reported by the DAG rules
                return True
        early = [x["key"] for x in r["requirements"] if x.get("prepared_by") in agent_slugs and x.get("gate") in r["profiles"]
                 and not inherits_agents(x["gate"])]
        report.check("R19", not early, f"agent preparers for keys gated before agents.run (F4_AGENTS): {early}")


def workflow_rules(c: dict, report: Report):
    wfs = c.get("_workflows", {})
    schema = c.get("_schemas", {}).get("workflow-definition.schema.json")
    ids = set()
    try:
        import jsonschema  # required dependency (>= 4.18 for Draft 2020-12)
        validator = jsonschema.Draft202012Validator(schema) if schema else None
    except ImportError:
        validator = None
        report.check("W00", False, "jsonschema is required for workflow schema validation (pip install 'jsonschema>=4.18')")
    except AttributeError:   # jsonschema < 4 (for example Ubuntu 22.04 python3-jsonschema 3.2) has no Draft 2020-12 validator
        validator = None
        report.check("W00", False, "jsonschema >= 4.18 is required (Draft 2020-12); the installed version has no Draft202012Validator")
    for name, wf in wfs.items():
        wid = wf.get("workflow_id")
        report.check("W01", f"{wid}.yaml" == name and wid not in ids, f"{name}: workflow_id must match file name and be unique")
        ids.add(wid)
        if validator:
            errs = sorted(validator.iter_errors(wf), key=lambda e: list(e.path))
            report.check("W02", not errs, f"{name}: schema errors {[e.message for e in errs[:3]]}")
    pol = c.get("workflow-policy.yaml", {})
    # W08 executor, principal and trigger-source refs resolve to a registry by type (runtime-isolation.yaml services,
    # agents, engineering_roles; roles.yaml roles, responsibility_assignments, flags; workflow-policy.yaml
    # #external_participants and #human_aliases); a free string is never an executor
    ri, roles_cfg = c.get("runtime-isolation.yaml", {}), c.get("roles.yaml", {})
    svc_ids = {str(sv.get("service_id")) for sv in (ri.get("services") or [])}
    agent_ids = set(ri.get("agents") or {}) | set(ri.get("engineering_roles") or {})
    human_roles = set(roles_cfg.get("roles") or []) | set(roles_cfg.get("responsibility_assignments") or {})
    flag_ids = set(roles_cfg.get("flags") or {})
    ext = pol.get("external_participants") or {}
    aliases = pol.get("human_aliases") or {}
    for pid, spec in ext.items():
        spec = spec if isinstance(spec, dict) else {}
        stray = sorted(str(k) for k, v in spec.items() if v is None or k not in ("host", "owner", "role", "executes_steps", "registry_ref"))
        report.check("W08", not stray and all(isinstance(spec.get(k), str) and spec.get(k) for k in ("host", "owner", "role"))
                     and isinstance(spec.get("executes_steps"), bool) and spec.get("owner") in human_roles,
                     f"workflow-policy.yaml#external_participants.{pid}: needs host, owner (a role or assignment), role and executes_steps; stray or null keys {stray} (an unquoted comma splits a YAML flow mapping)")
    for aid, spec in aliases.items():
        spec = spec if isinstance(spec, dict) else {}
        fl = spec.get("flag")
        report.check("W08", bool(spec.get("any_of")) and set(spec.get("any_of") or []) <= human_roles and bool(spec.get("resolution"))
                     and (fl is None or fl == "from_executor" or fl in flag_ids),
                     f"workflow-policy.yaml#human_aliases.{aid}: any_of must list roles.yaml roles or assignments, flag must be a roles.yaml flag or from_executor, resolution is required")
    humans = human_roles | set(aliases)
    principals = svc_ids | agent_ids | humans | set(ext)
    source_ids = principals | set(pol.get("catalog") or []) | {r.get("id") for r in (c.get("operations.yaml", {}).get("schedule") or [])} \
        | set(((pol.get("signals") or {}).get("catalog")) or {}) | set(pol.get("timer_catalog") or {})

    def config_ref_ok(ref: str) -> bool:
        fname, _, path = ref.partition("#")
        if fname not in c or not path:
            return False
        try:
            get_path(c[fname], path)
            return True
        except (KeyError, IndexError, TypeError, ValueError):
            return False
    for name, wf in wfs.items():
        for st in wf.get("steps", []):
            ex = st.get("executor") or {}
            t, ref, rf = ex.get("type"), ex.get("ref"), ex.get("requires_flag")
            if t == "deterministic":
                ok = ref in svc_ids or (ref in ext and (ext.get(ref) or {}).get("executes_steps") is True)
            elif t == "agent":
                ok = ref in agent_ids
            else:
                ok = ref in humans
            report.check("W08", ok, f"{name} {st.get('id')}: executor {t}:{ref} does not resolve (deterministic -> service_id or external participant with executes_steps; agent -> agents/engineering_roles; human -> role, assignment or human alias)")
            needs_flag = (aliases.get(ref) or {}).get("flag") == "from_executor"
            report.check("W08", (rf is None or (t == "human" and rf in flag_ids)) and (rf is not None or not needs_flag),
                         f"{name} {st.get('id')}: requires_flag {rf} must be a roles.yaml flag on a human step; alias {ref} requires one")
            to = (st.get("handoff") or {}).get("to")
            if to is not None:
                report.check("W08", to in principals, f"{name} {st.get('id')}: handoff.to {to} is not a registered service, agent, role or alias")
        auth = wf.get("authorization") or {}
        for who in list(auth.get("may_start") or []) + list(auth.get("may_cancel") or []):
            report.check("W08", who in principals, f"{name}: authorization principal {who} is not a registered service, agent, role, alias or external participant")
        for esc in (wf.get("limits") or {}).get("escalation") or []:
            report.check("W08", esc.get("to") in humans, f"{name}: escalation.to {esc.get('to')} must be one human role, assignment or alias (split 'a and b' into two entries)")
        for sref in (wf.get("trigger") or {}).get("source_refs") or []:
            report.check("W08", sref in source_ids or config_ref_ok(str(sref)),
                         f"{name}: trigger.source_refs {sref} is not a registry id (service, agent, role, alias, external participant, workflow, schedule id, signal, timer) or a resolvable <config>.yaml#<path>")
    # W17 handoff rejection (workflow-policy.yaml#handoff_rejection, #pinned_handoff_routes): every handoff names a bounded
    # rejection route; producer_retry re-runs this step or an upstream producer at most max_rounds (<= max_rounds_cap) times
    # within max_attempts_per_step; an escalation goes to a principal that can act (may_cancel or may_start), never to the
    # producer or receiver agent; a run with an earlier external effect or child arms never ends without its compensation;
    # security codes end the run and notify the owner; every definition equals its pinned route
    hr = pol.get("handoff_rejection") or {}
    routes_all = {"producer_retry", "escalate", "end_run", "compensate_then_end"}
    cap17 = hr.get("max_rounds_cap")
    sec17 = set(hr.get("security_codes") or [])
    report.check("W17", set(hr.get("routes") or {}) == routes_all and all(hr.get(k) for k in ("rule", "after_max", "timeout_exit", "notify", "escalate_to"))
                 and isinstance(cap17, int) and 1 <= cap17 <= 2 and {"unauthorized_action", "protected_touch_without_class", "authority_change_undeclared"} <= sec17
                 and "compensation" in str((hr.get("routes") or {}).get("compensate_then_end", "")) and "external effect" in str((hr.get("routes") or {}).get("end_run", "")),
                 "workflow-policy.yaml#handoff_rejection must define the four routes (end_run only without external effects, compensate_then_end with compensation), after_max, timeout_exit, notify, escalate_to, max_rounds_cap 1..2 and the security codes")
    esc_ok = humans | agent_ids
    pins17 = {(x.get("workflow"), x.get("step")): x for x in pol.get("pinned_handoff_routes") or []}
    seen17 = set()

    def ov_key(ov):
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in ov.items()))
    for name, wf in wfs.items():
        wid = wf.get("workflow_id")
        by_id = {st.get("id"): st for st in wf.get("steps", [])}
        attempts = int(((wf.get("limits") or {}).get("max_attempts_per_step")) or 1)
        auth = wf.get("authorization") or {}
        can_act = set(auth.get("may_cancel") or []) | set(auth.get("may_start") or [])
        comp = str(((wf.get("continuation") or {}).get("compensation")) or "").strip()
        has_comp = bool(comp) and comp.lower() not in ("none", "null", "not_applicable")

        def ups17(sid, seen=None):
            seen = set() if seen is None else seen
            for d in (by_id.get(sid) or {}).get("depends_on") or []:
                if d not in seen:
                    seen.add(d)
                    ups17(d, seen)
            return seen
        for st in wf.get("steps", []):
            h = st.get("handoff")
            if not h:
                continue
            o, sid = h.get("on_reject") or {}, st.get("id")
            codes = set(h.get("reject_codes") or [])
            report.check("W17", bool(o) and bool(codes), f"{name} {sid}: handoff needs reject_codes and on_reject (a rejection without a route loops or stalls)")
            if not o:
                continue
            route, ovs = o.get("route"), o.get("overrides") or []
            ups = ups17(sid)
            prod = o.get("producer_step", sid)
            if route == "producer_retry":
                report.check("W17", prod == sid or prod in ups, f"{name} {sid}: on_reject.producer_step {prod} must be this step or an upstream step")
                mr = o.get("max_rounds")
                report.check("W17", isinstance(mr, int) and 1 <= mr <= (cap17 or 0) and 1 + mr <= attempts and o.get("after_max") in ("escalate", "end_run", "compensate_then_end"),
                             f"{name} {sid}: producer_retry needs 1 <= max_rounds <= max_rounds_cap ({cap17}) and 1 + max_rounds <= max_attempts_per_step ({attempts}) and after_max escalate|end_run|compensate_then_end")
            else:
                report.check("W17", route in routes_all and not ({"max_rounds", "after_max", "producer_step"} & set(o)),
                             f"{name} {sid}: on_reject.route {route}: max_rounds, after_max and producer_step belong to producer_retry only")
            # a run with an earlier external effect or child arms never ends without compensation (REVIEW_A3 #1)
            live = any((by_id.get(u) or {}).get("external_effect") in ("reversible", "irreversible") or (by_id.get(u) or {}).get("starts") for u in ups)
            ends = [route, o.get("after_max")] + [ov.get("route") for ov in ovs]
            report.check("W17", not (live and "end_run" in ends), f"{name} {sid}: an earlier step had an external effect or started children, so a rejection may not end_run; use compensate_then_end")
            report.check("W17", "compensate_then_end" not in ends or has_comp, f"{name} {sid}: compensate_then_end needs continuation.compensation")
            # escalation targets can act and are neither the producer nor the receiver agent
            prod_agent = ((by_id.get(prod) or {}).get("executor") or {}).get("ref")
            targets = ([o.get("escalate_to")] if route == "escalate" or o.get("after_max") == "escalate" else []) + \
                      [ov.get("escalate_to") or o.get("escalate_to") for ov in ovs if ov.get("route") == "escalate"]
            for t in targets:
                report.check("W17", t in esc_ok and t in can_act and t not in (prod_agent, h.get("to")) or (t == h.get("to") and t in humans and t in can_act),
                             f"{name} {sid}: escalate_to {t} must be able to act (in may_cancel or may_start) and must not be the producer agent {prod_agent}")
            seen_codes = set()
            for ov in ovs:
                oc = set(ov.get("codes") or [])
                ok_ov = oc <= codes and not (oc & seen_codes)
                if ov.get("route") == "producer_retry":
                    ok_ov &= ov.get("producer_step") in ups | {sid} and route == "producer_retry"
                if ov.get("notify") is not None:
                    ok_ov &= ov.get("notify") in humans and ov.get("route") in ("end_run", "compensate_then_end")
                report.check("W17", ok_ov, f"{name} {sid}: on_reject override {sorted(oc)} must name this handoff's reject_codes once; a producer_retry override needs an upstream producer_step under a producer_retry handoff; notify is a human role on an ending route")
                seen_codes |= oc
            for code in sorted(codes & sec17):
                hit = [ov for ov in ovs if code in (ov.get("codes") or [])]
                report.check("W17", len(hit) == 1 and hit[0].get("route") in ("end_run", "compensate_then_end") and hit[0].get("notify") == "owner",
                             f"{name} {sid}: security code {code} must end the run at once and notify the owner")
            pin = pins17.get((wid, sid))
            seen17.add((wid, sid))
            if pin is None:
                report.check("W17", False, f"{name} {sid}: handoff route is not pinned in workflow-policy.yaml#pinned_handoff_routes")
                continue
            same = all(pin.get(k) == o.get(k) for k in ("route", "producer_step", "max_rounds", "after_max", "escalate_to")) and \
                sorted(ov_key(x) for x in pin.get("overrides") or []) == sorted(ov_key(x) for x in ovs)
            report.check("W17", same, f"{name} {sid}: on_reject {o} differs from its pinned route {pin}")
    report.check("W17", seen17 == set(pins17), f"pinned_handoff_routes names handoffs that do not exist: {sorted(set(pins17) - seen17)}")
    # W13 parent/child starts (workflow-policy.yaml#pinned_starts, #pinned_may_start, #child_guard, #child_lifecycle): every
    # `starts` entry equals its pin (await, on_parent_end, fixed inputs) and lies at or below its authorizing human step; the
    # child takes parent_run, lists exactly its starters, lets only its pinned principals start it, carries the guard and gets
    # all required inputs; cancel_open children can be cancelled by amt-workflow; business parents and children consume kill;
    # the start graph is acyclic
    wf_by_id13 = {wf.get("workflow_id"): wf for wf in wfs.values()}
    cl13 = pol.get("child_lifecycle") or {}
    report.check("W13", all(cl13.get(k) for k in ("on_parent_end", "experiment_stop", "handover", "kill", "start_refused")) and cl13.get("cancel_actor") == "amt-workflow"
                 and "urgent_entry" in str(cl13.get("experiment_stop", "")) and "never counts as done" in str(cl13.get("start_refused", "")),
                 "workflow-policy.yaml#child_lifecycle must define on_parent_end, experiment_stop (reverts through urgent_entry), handover, kill, start_refused and cancel_actor amt-workflow")
    pins13 = {(x.get("workflow"), x.get("step"), x.get("child")): x for x in pol.get("pinned_starts") or []}
    guard13 = str(pol.get("child_guard") or "")
    pms13 = pol.get("pinned_may_start") or {}
    started_by, seen13, edges13, cancel_open_children = {}, set(), {}, set()
    for name, wf in wfs.items():
        wid = wf.get("workflow_id")
        by_id = {st.get("id"): st for st in wf.get("steps", [])}

        def ups13(sid, seen=None):
            seen = set() if seen is None else seen
            for d in (by_id.get(sid) or {}).get("depends_on") or []:
                if d not in seen:
                    seen.add(d)
                    ups13(d, seen)
            return seen
        for st in wf.get("steps", []):
            for ch in st.get("starts") or []:
                cw = ch.get("workflow")
                tgt = wf_by_id13.get(cw)
                started_by.setdefault(cw, set()).add(wid)
                edges13.setdefault(wid, set()).add(cw)
                if ch.get("on_parent_end") == "cancel_open":
                    cancel_open_children.add(cw)
                ok = tgt is not None
                if ok:
                    tt, ta, ti = tgt.get("trigger") or {}, tgt.get("authorization") or {}, tgt.get("input") or {}
                    req, opt, given = set(ti.get("required_fields") or []), set(ti.get("optional_fields") or []), set(ch.get("input") or [])
                    ok = ("parent_run" in (tt.get("kinds") or []) and wid in (tt.get("parent_workflows") or [])
                          and "amt-workflow" in (ta.get("may_start") or []) and req <= given and given <= req | opt
                          and set(ch.get("input_values") or {}) <= given)
                report.check("W13", ok, f"{name} {st.get('id')}: starts {cw} but the child must exist, take parent_run, list {wid} in parent_workflows, let amt-workflow start it, and receive all its required input fields (and only its input fields)")
                if ch.get("await") == "child_completed":
                    report.check("W13", "child_run_completed" in ((wf.get("continuation") or {}).get("signals") or []),
                                 f"{name} {st.get('id')}: waits for {cw} to complete but does not consume child_run_completed")
                pin = pins13.get((wid, st.get("id"), cw))
                seen13.add((wid, st.get("id"), cw))
                hs = (pin or {}).get("after_human_step")
                hstep = by_id.get(hs) or {}
                ok_pin = pin is not None and pin.get("await") == ch.get("await") and pin.get("on_parent_end") == ch.get("on_parent_end") \
                    and (pin.get("input_values") or {}) == (ch.get("input_values") or {}) \
                    and (hstep.get("executor") or {}).get("type") == "human" and (hs in ups13(st.get("id")) or hs == st.get("id"))
                report.check("W13", ok_pin, f"{name} {st.get('id')}: start of {cw} must equal its pinned_starts entry {pin} and lie at or below the authorizing human step {hs}")
                if (pin or {}).get("waits_for_signal"):
                    report.check("W13", pin["waits_for_signal"] in ((wf.get("continuation") or {}).get("signals") or []),
                                 f"{name} {st.get('id')}: the start of {cw} waits for {pin['waits_for_signal']}, which the parent does not consume")
    report.check("W13", seen13 == set(pins13), f"pinned_starts entries without a matching start: {sorted(set(pins13) - seen13)}")
    for name, wf in wfs.items():
        wid = wf.get("workflow_id")
        tt, ta = wf.get("trigger") or {}, wf.get("authorization") or {}
        parents = set(tt.get("parent_workflows") or [])
        if "parent_run" in (tt.get("kinds") or []) or parents:
            report.check("W13", "parent_run" in (tt.get("kinds") or []) and bool(parents) and parents == started_by.get(wid, set()),
                         f"{name}: parent_workflows {sorted(parents)} must equal the workflows whose steps start it {sorted(started_by.get(wid, set()))}, with parent_run in trigger.kinds")
            report.check("W13", guard13 and guard13 in [str(x) for x in ta.get("preconditions") or []],
                         f"{name}: a parent_run child must carry the child_guard precondition exactly")
            report.check("W13", wid in pms13 and list(ta.get("may_start") or []) == list(pms13.get(wid) or []),
                         f"{name}: may_start {ta.get('may_start')} must equal pinned_may_start {pms13.get(wid)}")
        if wid in cancel_open_children:
            report.check("W13", "amt-workflow" in (ta.get("may_cancel") or []), f"{name}: a cancel_open start can reach it, so amt-workflow must be in may_cancel (child_lifecycle.cancel_actor)")
        if str(wid).startswith("WF-B") and (wid in started_by or wid in edges13):
            report.check("W13", "kill" in ((wf.get("continuation") or {}).get("signals") or []), f"{name}: a business parent or child must consume kill (child_lifecycle.kill)")
    # acyclic start graph (no self start, no loop)
    def cyc13(n, stack, done):
        if n in stack:
            return True
        if n in done:
            return False
        stack.add(n)
        hit = any(cyc13(m, stack, done) for m in edges13.get(n, ()))
        stack.discard(n)
        done.add(n)
        return hit
    report.check("W13", not any(cyc13(n, set(), set()) for n in list(edges13)), f"the parent/child start graph has a cycle: {edges13}")
    # M09 per-run cost cap (workflow-policy.yaml#cost_caps): a definition with an agent step charges its requests to
    # ai_runtime (runtime agents) or engineering (engineering roles) and names max_minor or a max_minor_ref readiness key
    # that exists; every extra bound ref exists; the policy states rule, accounting, on_reach, loop_breaker, value_source, ads
    cc = pol.get("cost_caps") or {}
    report.check("M09", all(cc.get(k) for k in ("rule", "accounting", "on_reach", "loop_breaker", "value_source", "ads")),
                 "workflow-policy.yaml#cost_caps must state rule, accounting, on_reach, loop_breaker, value_source and ads")
    rk09 = {r.get("key") for r in (c.get("readiness.yaml", {}).get("requirements") or [])}
    eng_roles = set((c.get("runtime-isolation.yaml", {}) or {}).get("engineering_roles") or {})
    for name, wf in wfs.items():
        agent_refs = {(st.get("executor") or {}).get("ref") for st in wf.get("steps", []) if (st.get("executor") or {}).get("type") == "agent"}
        if not agent_refs:
            continue
        cost = (wf.get("limits") or {}).get("cost") or {}
        want = "engineering" if agent_refs <= eng_roles else "ai_runtime"
        mm, ref = cost.get("max_minor"), str(cost.get("max_minor_ref") or "")
        ok = cost.get("budget_account") == want and (isinstance(mm, int) or (ref.startswith("readiness:") and ref.split(":", 1)[1] in rk09))
        ok = ok and all(str(e).startswith("readiness:") and str(e).split(":", 1)[1] in rk09 for e in cost.get("extra_bound_refs") or [])
        report.check("M09", ok, f"{name}: has agent steps {sorted(agent_refs)}, so limits.cost needs budget_account {want} and a per-run cap (max_minor or a max_minor_ref readiness key that exists); extra_bound_refs must exist")
    # W19 deterministic handoff validation (workflow-policy.yaml#handoff_validation): the gateway checks the envelope,
    # the analysis envelope (THINKING_MODELS §3.4), the run pin, freshness, the round bound and the payload on
    # workflow.submit_output; every payload_kind has a payload rule; c07_report keeps the Q24 / P-30 bounds
    hv = pol.get("handoff_validation") or {}
    schemas = c.get("_schemas", {}) or {}
    want_checks = {"envelope_schema", "analysis_size", "definition_pin", "input_freshness", "round_bound", "payload_schema", "pii_and_text"}
    report.check("W19", hv.get("at") == "workflow.submit_output" and {x.get("id") for x in hv.get("checks") or []} == want_checks
                 and all(x.get("rule") for x in hv.get("checks") or []) and "invalid_args" in str(hv.get("on_fail", ""))
                 and isinstance(hv.get("analysis_max_chars"), int) and hv.get("analysis_max_chars") > 0,
                 f"workflow-policy.yaml#handoff_validation must run on workflow.submit_output with checks {sorted(want_checks)}, on_fail invalid_args and an integer analysis_max_chars")
    hs = schemas.get("handoff.schema.json") or {}
    an = ((hs.get("properties") or {}).get("analysis")) or {}
    env = schemas.get("analysis-envelope.schema.json") or {}
    report.check("W19", "analysis-envelope.schema.json" in json.dumps(an) and bool(env)
                 and (((env.get("properties") or {}).get("handoff")) or {}).get("maxItems") == 7,
                 "handoff.schema.json#analysis must reference analysis-envelope.schema.json (indexed), whose handoff list keeps the library bound of 7 items")
    kinds = set((((hs.get("properties") or {}).get("payload_kind")) or {}).get("enum") or [])
    ps = hv.get("payload_schemas") or {}
    meaning = set(hv.get("payload_kinds_meaning") or {})
    report.check("W19", bool(kinds) and set(ps) == kinds and all(v in meaning or v in schemas for v in ps.values()),
                 f"handoff_validation.payload_schemas must map every handoff payload_kind {sorted(kinds - set(ps))} to an indexed schema or a payload_kinds_meaning rule")
    tb = (hv.get("text_artifact_bounds") or {})
    report.check("W19", all(k in tb for k, v in ps.items() if v == "text_artifact")
                 and (tb.get("c07_report") or {}).get("bluf_max_words") == 250 and (tb.get("c07_report") or {}).get("bluf_max_chars") == 2000,
                 "every text_artifact payload needs text_artifact_bounds; c07_report keeps BLUF <= 250 words (Q24) and <= 2 000 characters (P-30)")
    # W18 command aggregation (workflow-policy.yaml#command_aggregation, #outcome_start): open and terminal command states
    # partition execution-policy.yaml#command_states; every aggregating step has a role; each role's completion condition and
    # ordered rules equal the pinned semantics (an all-expired approval fails, an all-failed dispatch fails, a stuck item never
    # holds the run past reconciliation); a failed risk-reducing item becomes urgent; WF-B07 starts per command, never from a
    # parent run step
    ca = pol.get("command_aggregation") or {}
    cstates = set(((c.get("execution-policy.yaml", {}) or {}).get("command_states")) or [])
    open_s, term_s, succ_s = set(ca.get("open_command_states") or []), set(ca.get("terminal_command_states") or []), set(ca.get("success_states") or [])
    report.check("W18", bool(ca) and (open_s | term_s) == cstates and not (open_s & term_s) and succ_s == {"succeeded", "done_manual"} and succ_s <= term_s,
                 "workflow-policy.yaml#command_aggregation: open and terminal command states must partition execution-policy.yaml#command_states; success_states = succeeded, done_manual")
    want18 = {
        "approval": ("every_item_decided", [("any_approved", {"any_in": ["approved"]}, "completed"),
                                            ("none_approved_expired", {"none_in": ["approved"], "any_in": ["expired"]}, "failed"),
                                            ("all_rejected", {"all_in": ["rejected", "cancelled"], "any_in": ["rejected"]}, "rejected"),
                                            ("all_cancelled", {"all_in": ["cancelled"]}, "cancelled")]),
        "dispatch": ("no_item_before_attempt", [("compensation_failed", {"compensation_in": ["failed_confirmed"]}, "failed"),
                                                ("any_progress", {"any_in": ["succeeded", "done_manual", "uncertain", "reconciling", "manual_resolution"]}, "completed"),
                                                ("all_failed", {"all_in": ["failed_confirmed", "expired"]}, "failed"),
                                                ("all_cancelled", {"all_in": ["cancelled"]}, "cancelled")]),
        "reconciliation": ("every_item_terminal_or_handed_off", [("compensation_failed", {"compensation_in": ["failed_confirmed"]}, "failed"),
                                                                 ("reconciled", {"all_in": ["succeeded", "done_manual", "failed_confirmed", "rejected", "expired", "cancelled", "manual_resolution"]}, "completed")]),
    }
    for role, (cw, rules18) in want18.items():
        blk = ca.get(role) or {}
        got = [(r.get("id"), r.get("when"), r.get("step")) for r in blk.get("rules") or []]
        report.check("W18", blk.get("complete_when") == cw and got == rules18,
                     f"workflow-policy.yaml#command_aggregation.{role}: complete_when must be {cw} and the ordered rules {[(a, b) for a, _, b in rules18]} with their pinned conditions")
    report.check("W18", "urgent_entry" in str(ca.get("failed_risk_reducing", "")) and bool(ca.get("dispositions")),
                 "workflow-policy.yaml#command_aggregation: a failed pause or decrease becomes an urgent item (failed_risk_reducing) and dispositions are defined")
    roles18 = ca.get("roles") or {}
    report.check("W18", roles18 == {"WF-B02": {"S09": "approval", "S10": "dispatch", "S07": "approval", "S11": "dispatch"},
                                    "WF-B03": {"S04": "approval", "S05": "dispatch", "S06": "reconciliation"}},
                 "workflow-policy.yaml#command_aggregation.roles must name the WF-B02 approval/dispatch steps and the WF-B03 approval, dispatch and reconciliation steps")
    for name, wf in wfs.items():
        wid = wf.get("workflow_id")
        r_ = roles18.get(wid) or {}
        for st in wf.get("steps", []):
            sid = st.get("id")
            if st.get("command_actions"):
                report.check("W18", r_.get(sid) == "dispatch" and "command_aggregation" in " ".join(str(o) for o in st.get("outputs") or []),
                             f"{name} {sid}: a dispatching step must have role dispatch in command_aggregation.roles and record per-item dispositions (outputs)")
            elif r_.get(sid) == "dispatch":
                report.check("W18", False, f"{name} {sid}: role dispatch but the step dispatches nothing")
            if r_.get(sid) == "approval":
                report.check("W18", (st.get("executor") or {}).get("type") == "human" and bool(st.get("approval")), f"{name} {sid}: role approval needs a human approval step")
            for ch in st.get("starts") or []:
                report.check("W18", ch.get("workflow") != (pol.get("outcome_start") or {}).get("workflow"),
                             f"{name} {sid}: starts {ch.get('workflow')}, which outcome_start runs per command on its own transition, never from a parent run step")
    os18 = pol.get("outcome_start") or {}
    b07 = wf_by_id13.get(os18.get("workflow")) or {}
    report.check("W18", os18.get("never_from") == "parent_run_step" and os18.get("started_by") == "amt-workflow" and "succeeded or done_manual" in str(os18.get("start_event", ""))
                 and ((b07.get("trigger") or {}).get("kinds") or []) == ["event"] and not ((b07.get("trigger") or {}).get("parent_workflows")),
                 "workflow-policy.yaml#outcome_start: WF-B07 starts per command on its own succeeded/done_manual transition (trigger kinds [event], no parent workflows), started by amt-workflow, never from a parent run step")
    # W08 (pinned): executor_constraints fix the executor type/ref/flag of steps that owner decisions or ◇ rows rely on; an
    # alias with a fixed flag accepts no other requires_flag; a flag exclusion (flag_exclusions) is honoured by plain roles and aliases
    flag_ex = pol.get("flag_exclusions") or {}
    for con in pol.get("executor_constraints") or []:
        wf_c = next((wf for wf in wfs.values() if wf.get("workflow_id") == con.get("workflow")), None)
        st_c = next((st for st in (wf_c or {}).get("steps", []) if st.get("id") == con.get("step")), None)
        ex_c = (st_c or {}).get("executor") or {}
        ok_con = st_c is not None and bool(con.get("why")) and ex_c.get("type") == con.get("type") and (not con.get("ref") or ex_c.get("ref") == con.get("ref")) \
            and (not con.get("requires_flag") or ex_c.get("requires_flag") == con.get("requires_flag"))
        report.check("W08", ok_con, f"{con.get('workflow')} {con.get('step')}: executor {ex_c} breaks executor_constraints {con.get('type')}:{con.get('ref')} flag {con.get('requires_flag')} ({con.get('why')})")
    for name, wf in wfs.items():
        for st in wf.get("steps", []):
            ex = st.get("executor") or {}
            rf, al = ex.get("requires_flag"), aliases.get(ex.get("ref")) or {}
            if rf and al.get("flag") not in (None, "from_executor"):
                report.check("W08", al.get("flag") == rf, f"{name} {st.get('id')}: alias {ex.get('ref')} always requires flag {al.get('flag')}, so requires_flag {rf} conflicts")
            if rf and rf in flag_ex:
                excl = set((flag_ex[rf] or {}).get("roles") or [])
                if ex.get("ref") in excl:
                    report.check("W08", False, f"{name} {st.get('id')}: {ex.get('ref')} may not perform {rf} steps ({(flag_ex[rf] or {}).get('until')})")
                elif set(al.get("any_of") or []) & excl:
                    report.check("W08", al.get("applies_flag_exclusions") is True, f"{name} {st.get('id')}: alias {ex.get('ref')} lists {sorted(set(al.get('any_of') or []) & excl)}, excluded from {rf}; the alias must apply workflow-policy.yaml#flag_exclusions")
    # W15 conditional steps: `when` names an upstream step and a value that step can produce
    sev_ids = set(c.get("operations.yaml", {}).get("severities") or {})
    for name, wf in wfs.items():
        by_id = {st.get("id"): st for st in wf.get("steps", [])}

        def upstream(sid, seen=None):
            seen = set() if seen is None else seen
            for d in (by_id.get(sid) or {}).get("depends_on") or []:
                if d not in seen:
                    seen.add(d)
                    upstream(d, seen)
            return seen
        for st in wf.get("steps", []):
            wh = st.get("when")
            if not wh:
                continue
            conds = wh.get("any_of") if isinstance(wh, dict) and "any_of" in wh else [wh]
            report.check("W15", not (isinstance(wh, dict) and "any_of" in wh and set(wh) != {"any_of"}),
                         f"{name} {st.get('id')}: when mixes any_of with other keys {sorted(set(wh) - {'any_of'})}")
            for w in conds:
                src = by_id.get(w.get("step"))
                ok = src is not None and w.get("step") in upstream(st.get("id"))
                vals = set(w.get("in") or [])
                if ok and w.get("output") == "cause":
                    ok = vals <= {b.get("cause") for b in ((src.get("approval") or {}).get("by_cause") or [])}
                elif ok and w.get("output") == "severity":
                    ok = vals <= sev_ids
                elif ok:   # the field is a declared structured output of the source step (output_fields), not a word of its prose
                    ok = str(w.get("output")) in (src.get("output_fields") or [])
                report.check("W15", ok, f"{name} {st.get('id')}: when {w} must name an upstream step and a value it produces (approval.by_cause cause, operations.yaml#severities, or one of its output_fields)")
            # a step that collects human handback ACKs must open whenever a handback trigger is active (FR-GOV-10, Q31):
            # one of its conditions is `handback_triggers` non_empty on an upstream step that declares that output
            if st.get("acks"):
                report.check("W15", any(w.get("output") == "handback_triggers" and w.get("non_empty") is True for w in conds),
                             f"{name} {st.get('id')}: collects handback ACKs but its when {wh} can skip it while a handback trigger is active; add a handback_triggers non_empty condition (any_of)")
    # pinned conditions (workflow-policy.yaml#required_conditions) and unconditional protective steps (executor_constraints
    # unconditional: true): the conditions ◇ rows rely on cannot be rewritten, and containment is never conditional
    for rc in pol.get("required_conditions") or []:
        wf_rc = next((wf for wf in wfs.values() if wf.get("workflow_id") == rc.get("workflow")), None)
        st_rc = next((st for st in (wf_rc or {}).get("steps", []) if st.get("id") == rc.get("step")), None)
        report.check("W15", st_rc is not None and bool(rc.get("why")) and st_rc.get("when") == rc.get("when"),
                     f"{rc.get('workflow')} {rc.get('step')}: when {(st_rc or {}).get('when')} differs from the pinned condition {rc.get('when')} ({rc.get('why')})")
    for con in pol.get("executor_constraints") or []:
        if con.get("unconditional"):
            wf_u = next((wf for wf in wfs.values() if wf.get("workflow_id") == con.get("workflow")), None)
            st_u = next((st for st in (wf_u or {}).get("steps", []) if st.get("id") == con.get("step")), None)
            report.check("W15", st_u is not None and not st_u.get("when"), f"{con.get('workflow')} {con.get('step')}: an unconditional protective step may not carry a when ({con.get('why')})")
    # handback ACK coverage: every configured handback source has an ACK-collecting human step (kill-criteria KC rules with
    # human_handback, kill-criteria low_data.handback_ack_required, budgets ads.foreign_spend_behavior with a handback)
    kc_cfg = c.get("kill-criteria.yaml", {}) or {}
    need_hb = set()
    if any("human_handback" in (r.get("actions") or []) for r in kc_cfg.get("rules") or []):
        need_hb.add("kill_criteria")
    if ((kc_cfg.get("low_data") or {}).get("handback_ack_required")) is True:
        need_hb.add("zero_qualified_exposure")
    if "handback" in str(((c.get("budgets.yaml", {}) or {}).get("ads") or {}).get("foreign_spend_behavior", "")):
        need_hb.add("foreign_spend")
    have_hb = {a.get("trigger") for wf in wfs.values() for st in wf.get("steps", []) if (st.get("executor") or {}).get("type") == "human" for a in st.get("acks") or []}
    report.check("W15", need_hb <= have_hb, f"handback sources {sorted(need_hb - have_hb)} have no human step that collects their handback_acks (acks)")
    # W11 approval and dispatch ownership (workflow-policy.yaml#dispatch_ownership): approvals only on human steps; command
    # dispatch only on deterministic steps of the dispatcher service, after an upstream human approval of that action in
    # the same workflow; one owner per action case; an action owned elsewhere only through by_cause.approved_in
    pa_actions = (c.get("approval-policy.yaml", {}) or {}).get("actions") or {}
    human_aliases = set(pol.get("human_aliases") or {})
    dsp = pol.get("dispatch_ownership") or {}
    owners = {}
    for act, spec in (dsp.get("actions") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        ws = set((spec.get("cases") or {}).values()) | ({spec["owner"]} if spec.get("owner") else set())
        report.check("W11", bool(ws) and not (spec.get("owner") and spec.get("cases")) and act in pa_actions,
                     f"workflow-policy.yaml#dispatch_ownership.actions.{act}: needs an approval-policy action and exactly one of owner or cases")
        owners[act] = ws
    wf_by_id = {wf.get("workflow_id"): wf for wf in wfs.values()}

    def human_approvals(wf, only=None):
        got = set()
        for st in wf.get("steps", []):
            if only is not None and st.get("id") not in only:
                continue
            ap = st.get("approval") or {}
            if (st.get("executor") or {}).get("type") != "human" or not ap:
                continue
            got |= ({ap["policy_action"]} if ap.get("policy_action") else set()) | {
                a for case in ap.get("by_cause", []) if not case.get("approved_in") for a in case.get("policy_actions", [])}
        return got
    dispatched_by = {}
    for name, wf in wfs.items():
        wid = wf.get("workflow_id")
        by_id = {st.get("id"): st for st in wf.get("steps", [])}

        def ups(sid, seen=None):
            seen = set() if seen is None else seen
            for d in (by_id.get(sid) or {}).get("depends_on") or []:
                if d not in seen:
                    seen.add(d)
                    ups(d, seen)
            return seen
        for st in wf.get("steps", []):
            ex, appr = st.get("executor") or {}, st.get("approval") or {}
            if appr:
                report.check("W11", ex.get("type") == "human", f"{name} {st.get('id')}: an approval sits on a {ex.get('type')} step; approvals belong on a human step")
            acts = list(st.get("command_actions") or [])
            if acts:
                report.check("W11", ex.get("type") == "deterministic" and ex.get("ref") == dsp.get("dispatcher_service"),
                             f"{name} {st.get('id')}: command dispatch must run on the {dsp.get('dispatcher_service')} service, not {ex.get('type')}:{ex.get('ref')}")
                approved_up = human_approvals(wf, ups(st.get("id")))
                for a in acts:
                    dispatched_by.setdefault(a, set()).add(wid)
                    report.check("W11", wid in owners.get(a, set()), f"{name} {st.get('id')}: dispatches {a} but dispatch_ownership gives it to {sorted(owners.get(a, set())) or 'nobody'}")
                    spec_a = ((dsp.get("actions") or {}).get(a)) or {}
                    if spec_a.get("cases") or spec_a.get("case"):   # one owner per action case: the step names the case it serves
                        served = (st.get("serves_cases") or {}).get(a)
                        owner_of_case = (spec_a.get("cases") or {}).get(served) if spec_a.get("cases") else (spec_a.get("owner") if served == spec_a.get("case") else None)
                        report.check("W11", owner_of_case == wid, f"{name} {st.get('id')}: dispatches {a} for case {served}, which dispatch_ownership gives to {owner_of_case or 'nobody'}")
                    report.check("W11", not (pa_actions.get(a) or {}).get("approvers") or a in approved_up,
                                 f"{name} {st.get('id')}: dispatches {a} without an upstream human approval step of the same workflow that names it")
            if appr.get("policy_action") in owners:   # a single policy_action may not approve a command action owned elsewhere
                report.check("W11", wid in owners[appr["policy_action"]], f"{name} {st.get('id')}: approves {appr['policy_action']} owned by {sorted(owners[appr['policy_action']])} as a plain policy_action; use a by_cause case with approved_in")
            if appr and ex.get("type") == "human":   # the executor can approve every case it lists; owner-only actions need the owner
                elig = set((pol.get("human_aliases") or {}).get(ex.get("ref"), {}).get("any_of") or [ex.get("ref")])
                acts_cases = ([{"policy_actions": [appr["policy_action"]]}] if appr.get("policy_action") else []) + [x for x in (appr.get("by_cause") or []) if not x.get("approved_in")]
                for case in acts_cases:
                    need = set(case.get("approvers") or [r for a in case.get("policy_actions", []) for r in (pa_actions.get(a) or {}).get("approvers") or []])
                    owner_only = [a for a in case.get("policy_actions", []) if ((pa_actions.get(a) or {}).get("approvers") or []) == ["owner"]] or (["case"] if case.get("approvers") == ["owner"] else [])
                    report.check("W11", (not need or bool(elig & need)) and (not owner_only or "owner" in elig),
                                 f"{name} {st.get('id')}: executor {ex.get('ref')} ({sorted(elig)}) cannot approve case {case.get('cause', case.get('policy_actions'))} (approvers {sorted(need)}; owner-only {owner_only})")
            for case in appr.get("by_cause", []) or []:
                foreign = [a for a in case.get("policy_actions", []) if a in owners and wid not in owners[a]]
                tgt = case.get("approved_in")
                if case.get("approvers"):   # a case may narrow the policy approvers, never widen them
                    report.check("W11", all(set(case["approvers"]) <= set((pa_actions.get(a) or {}).get("approvers") or []) for a in case.get("policy_actions", [])),
                                 f"{name} {st.get('id')}: case {case.get('cause')} approvers {case['approvers']} must be a subset of every action's approval-policy approvers")
                if foreign:
                    allowed = set().union(*(owners[a] for a in foreign))
                    report.check("W11", tgt in allowed and set(foreign) <= human_approvals(wf_by_id.get(tgt) or {}),
                                 f"{name} {st.get('id')}: case {case.get('cause')} approves {foreign} owned by {sorted(allowed)}; name the owner in approved_in and approve them there")
                    # the target case that takes the decision is at least as strict as this one (REVIEW_A2 blocker #2)
                    src_na = case.get("never_auto", appr.get("never_auto")) is True
                    src_ap = set(case.get("approvers") or ([] if ex.get("ref") in human_aliases else [ex.get("ref")]) or
                                 [r for a in foreign for r in (pa_actions.get(a) or {}).get("approvers") or []])
                    tcases = [(tst, tc) for tst in (wf_by_id.get(tgt) or {}).get("steps", []) if (tst.get("executor") or {}).get("type") == "human"
                              for tc in ((tst.get("approval") or {}).get("by_cause") or []) if tc.get("cause") == case.get("approved_case")]
                    ok_t = bool(case.get("approved_case")) and len(tcases) == 1
                    if ok_t:
                        tst, tc = tcases[0]
                        t_na = tc.get("never_auto", (tst.get("approval") or {}).get("never_auto")) is True
                        t_ap = set(tc.get("approvers") or [r for a in tc.get("policy_actions", []) for r in (pa_actions.get(a) or {}).get("approvers") or []])
                        ok_t = set(foreign) <= set(tc.get("policy_actions") or []) and (t_na or not src_na) and t_ap <= src_ap
                    report.check("W11", ok_t, f"{name} {st.get('id')}: case {case.get('cause')} is decided in {tgt} case {case.get('approved_case')}, which must exist once and keep the same actions, never_auto {src_na} and approvers within {sorted(src_ap)}")
                else:
                    report.check("W11", tgt is None and not case.get("approved_case"), f"{name} {st.get('id')}: case {case.get('cause')} names approved_in {tgt} but approves nothing owned elsewhere")
    # urgent entry (Q38 "urgent ... darhol alohida"): a pause or decrease outside the day's rounds starts its own round of
    # the owner workflow through a gateway-produced signal; only pauses and budget decreases may enter that way
    if dsp:
        ue = dsp.get("urgent_entry") or {}
        uwf = wf_by_id.get(ue.get("workflow")) or {}
        cat_ue = (((pol.get("signals") or {}).get("catalog")) or {}).get(ue.get("signal")) or {}
        acts_ue = set(ue.get("actions") or [])
        ok_ue = (bool(ue.get("signal")) and ((uwf.get("trigger") or {}).get("signals_by_key") or {}).get(ue.get("key")) == ue.get("signal")
                 and ue.get("key") in ((uwf.get("trigger") or {}).get("signal_windows") or {})
                 and any(pr.get("service") == "gateway" for pr in cat_ue.get("producers") or [])
                 and bool(acts_ue) and acts_ue <= {"entity_pause", "budget_change"} and all(ue.get("workflow") in owners.get(a, set()) for a in acts_ue)
                 and ("budget_change" not in acts_ue or ue.get("direction") == "decrease_only"))
        report.check("W11", ok_ue, f"workflow-policy.yaml#dispatch_ownership.urgent_entry {ue}: the owner workflow must start a round on a gateway-produced signal key with a window, and only pauses or budget decreases it owns may enter that way (Q38)")
    for a, ws in owners.items():
        report.check("W11", dispatched_by.get(a, set()) == ws, f"dispatch_ownership.{a}: owners {sorted(ws)} but dispatched by {sorted(dispatched_by.get(a, set()))}")
    for a in dispatched_by:
        report.check("W11", a in owners, f"{a} is dispatched but has no dispatch_ownership entry")
    # W20 human-step timeout semantics (step.on_timeout): a human step whose timeout is also an escalation threshold declares
    # what the timeout means; when that escalation goes to someone other than the step's executor, the step stays open
    # (wait_and_escalate) so the escalation target can still complete it - unless it is an approval with TTL expiry
    for name, wf in wfs.items():
        escs = (wf.get("limits") or {}).get("escalation") or []
        for st in wf.get("steps", []):
            ex = st.get("executor") or {}
            if ex.get("type") != "human":
                continue
            hit = [e for e in escs if str(e.get("after")) == str(st.get("timeout"))]
            if not hit:
                continue
            ot = st.get("on_timeout") or {}
            report.check("W20", bool(ot.get("action")), f"{name} {st.get('id')}: timeout {st.get('timeout')} is also an escalation threshold; declare on_timeout (what the timeout means for the run)")
            others = [e for e in hit if e.get("to") != ex.get("ref")]
            if ot and others and not st.get("approval"):
                report.check("W20", ot.get("action") == "wait_and_escalate",
                             f"{name} {st.get('id')}: the escalation at {st.get('timeout')} goes to {sorted({e.get('to') for e in others})}, so the step must stay open (wait_and_escalate), not {ot.get('action')}")
            if ot and st.get("approval"):
                report.check("W20", ot.get("action") in ("expire_item_and_close", "wait_and_escalate"), f"{name} {st.get('id')}: an approval step times out by TTL expiry or keeps waiting, not {ot.get('action')}")
    # W21 human task completion: a human step without an approval names the signals that complete it (completes_on); each
    # is consumed by the workflow and catalogued, and at least one has a producer that does not wait for this step
    cat_all = ((pol.get("signals") or {}).get("catalog")) or {}
    wf_by_id21 = {wf.get("workflow_id"): wf for wf in wfs.values()}

    def downstream(wf, sid):
        out, frontier = set(), {sid}
        while frontier:
            nxt = {st.get("id") for st in wf.get("steps", []) if set(st.get("depends_on") or []) & frontier} - out
            out |= nxt
            frontier = nxt
        return out
    for name, wf in wfs.items():
        wid, sigs = wf.get("workflow_id"), set((wf.get("continuation") or {}).get("signals") or [])
        for st in wf.get("steps", []):
            if (st.get("executor") or {}).get("type") != "human" or st.get("approval"):
                continue
            co = st.get("completes_on") or []
            report.check("W21", bool(co), f"{name} {st.get('id')}: a human task without an approval must name the signal(s) that complete it (completes_on)")
            for k in co:
                report.check("W21", k in sigs and k in cat_all, f"{name} {st.get('id')}: completes_on {k} must be in continuation.signals and signals.catalog")
            down = downstream(wf, st.get("id"))
            free = any(not (str(pr.get("workflow_step", "")).startswith(f"{wid}.") and str(pr.get("workflow_step")).split(".", 1)[1] in down)
                       for k in co for pr in ((cat_all.get(k) or {}).get("producers") or []))
            report.check("W21", not co or free, f"{name} {st.get('id')}: every producer of {co} waits for this step (deadlock)")
    ads21 = (c.get("budgets.yaml") or {}).get("ads") or {}
    if ads21.get("cap_update_workflow"):
        cw, sw = wf_by_id21.get(ads21.get("cap_update_workflow")) or {}, ads21.get("cap_update_switch_signal")
        owner_steps = [st for st in cw.get("steps", []) if (st.get("executor") or {}).get("type") == "human" and sw in (st.get("completes_on") or [])]
        emitters = [st for st in cw.get("steps", []) if sw in (st.get("emits") or [])]
        ok_sw = bool(sw) and bool(owner_steps) and bool(emitters) and all(e.get("id") not in downstream(cw, o.get("id")) for o in owner_steps for e in emitters)
        report.check("W21", ok_sw, f"budgets.yaml#ads.cap_update_switch_signal {sw}: the owner step of {ads21.get('cap_update_workflow')} must complete on it and a step that does not wait for the owner must emit it (switch without the callback)")
    # W16 every step feeds a later step except the declared end steps (completion.end_steps): no dead-end branch
    for name, wf in wfs.items():
        steps = wf.get("steps", [])
        used = {d for st in steps for d in st.get("depends_on") or []}
        sinks = {st.get("id") for st in steps if st.get("id") not in used}
        declared = set((wf.get("completion") or {}).get("end_steps") or [])
        ids16 = [st.get("id") for st in steps]
        unknown16 = sorted({d for st in steps for d in st.get("depends_on") or []} - set(ids16))
        report.check("W16", not unknown16 and len(ids16) == len(set(ids16)), f"{name}: depends_on names unknown steps {unknown16} or a step id repeats")
        state16, cyc16 = {}, []

        def visit16(sid):
            state16[sid] = 1
            for d in next((x.get("depends_on") or [] for x in steps if x.get("id") == sid), []):
                if state16.get(d) == 1:
                    cyc16.append((sid, d))
                elif d in ids16 and not state16.get(d):
                    visit16(d)
            state16[sid] = 2
        for sid in ids16:
            if not state16.get(sid):
                visit16(sid)
        report.check("W16", not cyc16, f"{name}: dependency cycle through {cyc16} (the run can never progress)")
        roots16 = [st.get("id") for st in steps if not st.get("depends_on")]
        report.check("W16", len(roots16) >= 1, f"{name}: no step without dependencies (no start step)")
        for req in pol.get("required_edges") or []:
            if req.get("workflow") != wf.get("workflow_id"):
                continue
            report.check("W16", bool(req.get("why")), f"workflow-policy.yaml#required_edges {req}: every pinned edge states the claim it protects (why)")
            st_r = next((x for x in steps if x.get("id") == req.get("step")), None)
            ups_r, front = set(), set((st_r or {}).get("depends_on") or [])
            while front:
                ups_r |= front
                front = {d for x in steps if x.get("id") in front for d in x.get("depends_on") or []} - ups_r
            ok_r = st_r is not None and set(req.get("must_depend_on") or []) <= set(st_r.get("depends_on") or []) and not (set(req.get("must_not_reach") or []) & ups_r)
            report.check("W16", ok_r, f"{name} {req.get('step')}: required edges {req.get('must_depend_on')} / never upstream {req.get('must_not_reach')} broken ({req.get('why')})")
        report.check("W16", sinks == declared, f"{name}: outputs of {sorted(sinks - declared)} are consumed by no later step and are not declared end steps; declared end steps {sorted(declared - sinks)} feed later steps")
    # W14 an ISO max_duration covers the longest dependency path of ISO step timeouts (readiness:/input: bounds count as 0);
    # a step that schedule_execution anchors to a schedule timer starts no earlier than that slot (offset from the trigger)
    sx14 = (c.get("workflow-policy.yaml") or {}).get("schedule_execution") or {}
    tcat14 = (c.get("workflow-policy.yaml") or {}).get("timer_catalog") or {}
    sched14 = {r.get("id"): r for r in (c.get("operations.yaml", {}).get("schedule") or [])}
    for name, wf in wfs.items():
        try:
            cap = iso_duration(str((wf.get("limits") or {}).get("max_duration", "")))
        except ValueError:
            continue
        by_id, memo = {st.get("id"): st for st in wf.get("steps", [])}, {}
        anchors = {}
        for sid14, e14 in sx14.items():
            if e14.get("workflow") == wf.get("workflow_id") and e14.get("step") and (tcat14.get(e14.get("timer")) or {}).get("ref") == sid14:
                off = schedule_offset((wf.get("trigger") or {}).get("schedule"), str((sched14.get(sid14) or {}).get("when", "")))
                if off is not None:
                    anchors[e14["step"]] = max(anchors.get(e14["step"], dt.timedelta(0)), off)

        def path_len(sid, stack=()):
            if sid in memo:
                return memo[sid]
            if sid in stack or sid not in by_id:
                return dt.timedelta(0)
            try:
                own = iso_duration(str(by_id[sid].get("timeout", "")))
            except ValueError:
                own = dt.timedelta(0)
            memo[sid] = own + max([anchors.get(sid, dt.timedelta(0))] + [path_len(d, stack + (sid,)) for d in by_id[sid].get("depends_on") or []])
            return memo[sid]
        longest = max((path_len(sid) for sid in by_id), default=dt.timedelta(0))
        report.check("W14", cap >= longest, f"{name}: max_duration {wf['limits']['max_duration']} is shorter than its longest step-timeout path ({longest}, schedule anchors {sorted(anchors)} included); the run would be cut before its own steps may finish")
    # W09 concurrency vs run lifetime (workflow-policy.yaml#concurrency_semantics): a scheduled run that can outlive its
    # trigger period must not block the next trigger, and an observation longer than the period never sits inside it
    pol = c.get("workflow-policy.yaml", {})
    cs = pol.get("concurrency_semantics") or {}
    open_states = set(pol.get("run_states") or []) - {"completed", "failed", "cancelled"}
    counted = set(cs.get("counted_run_states") or [])
    report.check("W09", bool(cs) and counted <= set(pol.get("run_states") or []) and open_states <= counted
                 and cs.get("on_limit_default") in (cs.get("on_limit_values") or []),
                 f"workflow-policy.yaml#concurrency_semantics must count every open run state {sorted(open_states - counted)} and name the on_limit values with a default")
    for name, wf in wfs.items():
        lim, trig = wf.get("limits") or {}, wf.get("trigger") or {}
        conc = lim.get("concurrency") or {}
        if conc.get("on_limit") is not None:
            report.check("W09", conc["on_limit"] in (cs.get("on_limit_values") or []), f"{name}: unknown concurrency.on_limit {conc['on_limit']}")
        period = cron_period(trig.get("schedule"))
        if period is None:
            continue
        md = str(lim.get("max_duration", ""))
        report.check("W09", not md.startswith("readiness:"), f"{name}: a scheduled definition needs an ISO max_duration; {md} is an observation horizon that belongs in its own workflow (long_observation_rule)")
        if conc.get("global") is None:
            key9 = str(trig.get("correlation_key", ""))
            grain9 = [d for k, d in (("business_date", 1), ("date", 1), ("iso_week", 7), ("business_month", 28)) if re.search(rf"(?<![a-z_]){k}(?![a-z_])", key9)]
            report.check("W09", bool(grain9) and min(grain9) <= period.days,
                         f"{name}: scheduled with global null, so its correlation_key {key9!r} must change every {period.days}-day trigger period (business_date or date daily, iso_week weekly, business_month monthly)")
            continue
        try:
            life = iso_duration(md)
        except ValueError:
            report.check("W09", False, f"{name}: scheduled with global {conc['global']} needs an ISO max_duration, not {md} (an observation horizon belongs in its own workflow)")
            continue
        alive = -(-life // period)
        report.check("W09", conc["global"] >= alive or conc.get("on_limit") in ("queue", "skip_with_audit"),
                     f"{name}: max_duration {md} keeps up to {alive} runs open per {period.days}-day trigger but global is {conc['global']} and on_limit is {conc.get('on_limit', 'default')}")
    # W10 signal and timer choreography (workflow-policy.yaml#signals.catalog, #timer_catalog): every consumed signal has a
    # resolvable producer, every catalog entry is consumed, emits match producers, every timer is catalogued and resolvable
    catalog = ((pol.get("signals") or {}).get("catalog")) or {}
    tcat = pol.get("timer_catalog") or {}
    services = {str(sv.get("service_id")) for sv in (c.get("runtime-isolation.yaml", {}).get("services") or [])}
    externals = set(pol.get("external_participants") or {})
    sched_ids = {r.get("id") for r in (c.get("operations.yaml", {}).get("schedule") or [])}
    rkeys = {r["key"] for r in (c.get("readiness.yaml", {}).get("requirements") or [])}
    step_emits = {f"{wf.get('workflow_id')}.{st.get('id')}": set(st.get("emits") or []) for wf in wfs.values() for st in wf.get("steps", [])}
    consumed, used_timers = {}, set()
    # closed entry shapes: a key outside the shape is a split-off fragment or a field no rule reads (REVIEW_A2 #13)
    sig_keys, tim_keys = {"producers", "transport", "payload", "dedup"}, {"kind", "ref", "base", "after"}
    for sig, ent in catalog.items():
        report.check("W10", isinstance(ent, dict) and set(ent) <= sig_keys and all(isinstance(ent.get(k), str) and ent.get(k) for k in ("payload", "dedup")),
                     f"signals.catalog.{sig}: keys {sorted(set(ent or {}) - sig_keys)} outside {sorted(sig_keys)}, or payload/dedup not a non-empty text")
    for tid, ent in tcat.items():
        report.check("W10", isinstance(ent, dict) and set(ent) <= tim_keys, f"timer_catalog.{tid}: keys {sorted(set(ent or {}) - tim_keys)} outside {sorted(tim_keys)}")
    for name, wf in wfs.items():
        trig, cont = wf.get("trigger") or {}, wf.get("continuation") or {}
        for kind in list(cont.get("signals") or []) + list((trig.get("signals_by_key") or {}).values()):
            consumed.setdefault(kind, set()).add(name)
            report.check("W10", kind in catalog, f"{name}: consumes signal {kind} that workflow-policy.yaml#signals.catalog does not define (no producer)")
        fields = set((wf.get("input") or {}).get("required_fields") or []) | set((wf.get("input") or {}).get("optional_fields") or [])
        for t in cont.get("timers") or []:
            used_timers.add(t)
            spec = tcat.get(t)
            if not spec:
                report.check("W10", False, f"{name}: timer {t} is not in workflow-policy.yaml#timer_catalog")
                continue
            k, ref = spec.get("kind"), spec.get("ref")
            ok_t = (k == "schedule" and ref in sched_ids) or (k == "readiness" and ref in rkeys) or (k == "input" and ref in fields) or (k == "relative" and bool(spec.get("base")) and bool(spec.get("after")))
            report.check("W10", ok_t, f"{name}: timer {t} ({k} {ref}) does not resolve to a schedule id, readiness key, input field or relative base")
        for st in wf.get("steps", []):
            for kind in st.get("emits") or []:
                prods = [x.get("workflow_step") for x in (catalog.get(kind) or {}).get("producers", [])]
                report.check("W10", f"{wf.get('workflow_id')}.{st.get('id')}" in prods, f"{name} {st.get('id')}: emits {kind} but the catalog does not name this step as a producer")
    for kind, spec in catalog.items():
        report.check("W10", kind in consumed, f"signal {kind} is catalogued but no workflow consumes it")
        prods = (spec or {}).get("producers") or []
        report.check("W10", bool(prods) and bool((spec or {}).get("transport")), f"signal {kind}: producers and transport are required")
        for pr in prods:
            ok_p = (pr.get("service") in services) or (pr.get("external") in externals) or (pr.get("workflow_step") in step_emits and kind in step_emits.get(pr.get("workflow_step"), set()))
            report.check("W10", ok_p, f"signal {kind}: producer {pr} is not a registry service, an external participant or a step that emits it")
    # pinned producers: a detection signal comes only from a step on the service that can see the data (or listed services)
    exec_of = {f"{wf.get('workflow_id')}.{st.get('id')}": (st.get("executor") or {}).get("ref") for wf in wfs.values() for st in wf.get("steps", [])}
    for kind, cons in (pol.get("signal_producer_constraints") or {}).items():
        prods = ((catalog.get(kind) or {}).get("producers")) or []
        ok_c = bool(prods) and kind in catalog
        for pr in prods:
            if pr.get("workflow_step"):
                ok_c &= exec_of.get(pr["workflow_step"]) == cons.get("step_service")
            else:
                ok_c &= pr.get("service") in (cons.get("also_services") or [])
        report.check("W10", ok_c, f"signal {kind}: producers {prods} must be steps on {cons.get('step_service')} or {cons.get('also_services') or 'no other service'} (workflow-policy.yaml#signal_producer_constraints)")
    for t in tcat:
        report.check("W10", t in used_timers, f"timer {t} is catalogued but no workflow uses it")
    report.facts["signals"] = len(catalog)
    report.facts["workflows"] = len(wfs)


# ---------------------------------------------------------------- document rules

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def slug(text: str) -> str:
    text = re.sub(r"[`*_]", "", text.strip().lower())
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def owner_decision_rows(text: str) -> list[dict]:
    """Rows of the owner-decision tables (DECISION_LOG sections A–E and I): id, occurrence, status, sha256 of the decision text."""
    import hashlib
    out, sec, seen = [], "", {}
    for line in text.splitlines():
        m = re.match(r"^## ([A-Z])\.", line)
        if m:
            sec = m.group(1)
        elif line.startswith("## "):
            sec = ""
        if sec in ("A", "B", "C", "D", "E", "I") and line.startswith("| Q"):
            cells = [x.strip() for x in line.strip().strip("|").split("|")]
            n = seen.get(cells[0], 0) + 1
            seen[cells[0]] = n
            out.append({"id": cells[0], "n": n, "status": cells[2], "sha256": hashlib.sha256(cells[1].encode("utf-8")).hexdigest()})
    return out


def decision_item_sections(text: str) -> tuple[str, str]:
    """Separate explicitly closed owner questions from the full open-decision table."""
    section = text.split("## 1. Owner qarorlari", 1)[-1].split("\n## 2.", 1)[0]
    open_rows, marker, closed_rows = section.partition("### Shu sessiyada yopilgan qarorlar")
    return open_rows, closed_rows if marker else ""


def doc_rules(root: Path, c: dict, report: Report):
    # D37 open owner decisions carry a latest decision date and an overdue rule (L2-20, P-165)
    oi_text = (root / "00_Decisions" / "OPEN_ITEMS.md").read_text(encoding="utf-8")
    od_hdr = "| ID | Savol | Variantlar | Builder tavsiyasi | Bloklaydi | Kerak sana | Muddati o‘tsa |"
    report.check("D37", od_hdr in oi_text, "OPEN_ITEMS §1 table must keep the columns Kerak sana and Muddati o‘tsa")
    oi_open, oi_closed = decision_item_sections(oi_text)
    for line in oi_open.splitlines():
        if line.startswith("| OD-"):
            cc = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            due_ok = len(cc) == 7 and (bool(re.search(r"\d{4}-\d{2}-\d{2}", cc[5])) or cc[5] == "bloklamaydi")
            over_ok = len(cc) == 7 and cc[6].lower().startswith(("bloklaydi", "qattiqroq", "bloklamaydi", "joriy holat davom etadi"))
            report.check("D37", due_ok and over_ok, f"OPEN_ITEMS {cc[0]}: needs 7 cells, a latest decision date (YYYY-MM-DD or bloklamaydi) and an overdue rule (bloklaydi / qattiqroq / joriy holat davom etadi)")
    for line in oi_closed.splitlines():
        if line.startswith("| OD-"):
            cc = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            report.check("D37", len(cc) == 2 and bool(re.search(r"\bQ[0-9]+(?:\.[0-9]+)?\b", cc[1])),
                         f"closed OPEN_ITEMS {cc[0]} must have ID and an explicit owner Q decision reference")
    md_files = sorted(p for p in root.rglob("*.md"))
    texts = {p: p.read_text(encoding="utf-8") for p in md_files}
    yaml_texts = {p: p.read_text(encoding="utf-8") for p in (root / "09_Config_Templates").rglob("*.yaml")}
    all_texts = {**texts, **yaml_texts}
    json_texts = {p: p.read_text(encoding="utf-8") for p in root.rglob("*.json") if "fixtures" not in p.parts}
    rel = lambda p: str(p.relative_to(root))
    # D01 links
    for p, t in texts.items():
        for target in LINK_RE.findall(t):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            path, _, anchor = target.partition("#")
            dest = (p.parent / path).resolve()
            report.check("D01", dest.exists(), f"{rel(p)}: broken link {target}")
            if anchor and dest.exists() and dest.suffix == ".md":
                heads = {slug(h) for h in re.findall(r"^#+\s+(.*)$", dest.read_text(encoding="utf-8"), re.M)}
                if slug(anchor) not in heads and not re.fullmatch(r"\d+", anchor):
                    report.warn("D02", f"{rel(p)}: anchor #{anchor} not found in {path}")
    # D03 definitions
    def rows(file: Path, pattern: str) -> set[str]:
        if not file.exists():
            return set()
        return set(re.findall(pattern, file.read_text(encoding="utf-8"), re.M))

    phases = root / "05_Build_Phases"
    hg_def = rows(phases / "PHASES.md", r"^\|\s*\**(HG-[A-Z0-9]+-[0-9A-Z]+)\**(?:\s*\([^)|]*\))?\s*\|") | rows(phases / "FE_Evolution.md", r"^\|\s*\**(HG-FE-\d+)\**(?:\s*\([^)|]*\))?\s*\|")
    at_def = set()
    for f in phases.glob("F*.md"):
        at_def |= rows(f, r"^\|\s*\**((?:F[0-7]|FE)-AT-[0-9A-Za-z]+)\**\s*\|")
    acc = root / "12_Acceptance"
    uat_def = rows(acc / "PRODUCTION_ACCEPTANCE.md", r"^\|\s*\**((?:UAT-\d+|EVO-AT\d+))\**\s*\|")
    wft_def = rows(acc / "WORKFLOW_TESTS.md", r"^\|\s*\**(WF-TEST-[A-Z0-9-]+)\**\s*\|")
    dec = root / "00_Decisions"
    dl = (dec / "DECISION_LOG.md").read_text(encoding="utf-8")
    q_def = set()
    for first in re.findall(r"^\|\s*([^|]+?)\s*\|", dl, re.M):
        q_def |= set(re.findall(r"Q\d+(?:\.\d+)?", first))
    p_def = set(re.findall(r"^\|\s*(P-\d+)\s*\|", dl, re.M))
    oi = (dec / "OPEN_ITEMS.md").read_text(encoding="utf-8")
    od_def = set(re.findall(r"^\|\s*(OD-\d+)\s*\|", oi, re.M))
    inv = (root / "11_Production_Contracts" / "INVARIANTS.md").read_text(encoding="utf-8")
    i_def = set(re.findall(r"(?:^|\|\s*|\*\*|^#+\s*|^-\s*)(I(?:0[1-9]|[12]\d))\b", inv, re.M))
    adr_files = {m.group(1) for f in (root / "04_ADR").glob("ADR-*.md") if (m := re.match(r"(ADR-\d{3})", f.name))}
    report.facts.update(hg=len(hg_def), phase_at=len(at_def), uat_evo=len(uat_def), wf_tests=len(wft_def), q_ids=len(q_def), invariants=len(i_def), adrs=len(adr_files))
    # W04 workflow tests are defined and every per-workflow test is referenced by its workflow
    all_tests = at_def | uat_def | wft_def
    for name, wf in c.get("_workflows", {}).items():
        wid = wf.get("workflow_id", "")
        listed = set(wf.get("tests", []))
        report.check("W04", listed <= all_tests, f"{name}: tests not defined anywhere: {sorted(listed - all_tests)}")
        own = {t for t in wft_def if t.startswith(f"WF-TEST-{wid[3:]}-")}   # test ids drop the WF- prefix (WF-TEST-O03-E2E for WF-O03)
        report.check("W04", own <= listed, f"{name}: WORKFLOW_TESTS defines {sorted(own - listed)} but the workflow does not list them")
    checks = [
        ("D03", r"\bHG-[A-Z0-9]+-[0-9A-Z]+\b", hg_def, "HUMAN_GATE"),
        ("D04", r"\b(?:F[0-7]|FE)-AT-[0-9]+[A-Za-z]?\b", at_def, "phase acceptance test"),
        ("D05", r"\b(?:UAT-\d{2}|EVO-AT\d{2})\b", uat_def, "UAT/EVO-AT"),
        ("D06", r"\bWF-TEST-[A-Z0-9]+(?:-[A-Z0-9]+)*\b", wft_def, "workflow test"),
        ("D07", r"(?<![\w.-])P-\d{2,3}\b", p_def, "proposal"),   # two- and three-digit proposal ids
        ("D08", r"\bOD-\d{2}\b", od_def, "owner decision"),
        ("D09", r"(?<![\w.])Q\d{2}(?:\.\d)?(?![\w.])", q_def, "owner decision Q-ID"),
        ("D10", r"(?<![\w-])I(?:0[1-9]|[12]\d)(?![\w-])", i_def, "invariant"),
        ("D11", r"\bADR-\d{3}\b", adr_files, "ADR"),
    ]
    for rule, pattern, defined, label in checks:
        missing = {}
        for p, t in all_texts.items():
            for m in re.finditer(pattern + r"(-\*|\*)?", t):
                ref, wildcard = m.group(0), m.group(m.lastindex) if m.lastindex else None
                base = ref[: -len(wildcard)] if wildcard else ref
                if wildcard:
                    if not any(d.startswith(base.rstrip("-")) for d in defined):
                        missing.setdefault(ref, rel(p))
                elif base not in defined:
                    missing.setdefault(base, rel(p))
        report.check(rule, not missing, f"undefined {label} IDs: " + ", ".join(f"{k} ({v})" for k, v in sorted(missing.items())[:25]))
    # D34 conflict-register IDs (C-NN) are defined in OPEN_ITEMS section 4
    c_def = set(re.findall(r"^\|\s*(C-\d+)\s*\|", oi, re.M))
    c_missing = {}
    for p, t in all_texts.items():
        for m in re.finditer(r"(?<![\w.-])C-\d{2}\b", t):
            if m.group(0) not in c_def:
                c_missing.setdefault(m.group(0), rel(p))
    # D35 the gateway guard, the action table note, the GT test and the ops-bot callback carry the protective re-activation case
    gg = (root / "03_Architecture" / "GUARDRAIL_GATEWAY.md").read_text(encoding="utf-8")
    tg = (root / "03_Architecture" / "TELEGRAM.md").read_text(encoding="utf-8")
    g14 = next((l for l in gg.splitlines() if l.startswith("| 14 |")), "")
    gt51 = next((l for l in gg.splitlines() if l.startswith("| GT-51 |")), "")
    cb = next((l for l in tg.splitlines() if l.startswith("| Change set qarori |")), "")
    rap_ = "re_activation_after_protective_pause"
    report.check("D35", rap_ in g14 and "owner" in g14 and "L2" in g14 and rap_ in gt51 and "ads_approver" in gt51 and rap_ in cb and "owner" in cb,
                 "GUARDRAIL_GATEWAY guard 14, GT-51 and the TELEGRAM change-set callback must route re_activation_after_protective_pause to the owner only")
    report.check("D34", not c_missing, "undefined conflict-register IDs: " + ", ".join(f"{k} ({v})" for k, v in sorted(c_missing.items())))
    # K06 (document) CONFIG_CONTRACT 4.1 carries the pre-registered verdict_rule schema
    cc_text = (root / "11_Production_Contracts" / "CONFIG_CONTRACT.md").read_text(encoding="utf-8")
    vr = re.search(r"```yaml\nbusiness\.acceptance\.verdict_rule:.*?```", cc_text, re.S)
    vr_fields = set(re.findall(r"^  ([a-z_]+):", vr.group(0), re.M)) if vr else set()
    need_vr = {"primary", "decision", "margin_pct", "target_effect_pct", "alpha", "alpha_sided", "power", "test", "verdict_map", "looks", "alpha_spending",
               "min_qualified", "guardrails", "extension_unit_weeks", "max_weeks"}   # REVIEW_A1 #7: the test is pre-registered, not only its parameters
    sub = {m.group(1) for m in re.finditer(r"^    ([a-z_]+):", vr.group(0), re.M)} if vr else set()
    report.check("K06", {"statistic", "variance_model", "baseline_uncertainty", "sufficient", "insufficient", "inconclusive"} <= sub
                 and bool(vr) and "unadjusted repeated looks are not allowed" in vr.group(0),
                 "CONFIG_CONTRACT 4.1 verdict_rule must pre-register test {statistic, variance_model, baseline_uncertainty}, verdict_map {sufficient, insufficient, inconclusive} and forbid unadjusted repeated looks")
    report.check("K06", need_vr <= vr_fields, f"CONFIG_CONTRACT 4.1 business.acceptance.verdict_rule schema lacks {sorted(need_vr - vr_fields)}")
    # K07 (document) EVALS section 6 states the same shadow minimums as decision-statistics.yaml SHADOW_WEEK
    sw = ((c.get("decision-statistics.yaml") or {}).get("decision_rules") or {}).get("SHADOW_WEEK")
    if sw is not None:
        ev_text = (root / "07_Evals" / "EVALS.md").read_text(encoding="utf-8")
        me = str(sw.get("min_exposure", ""))
        for fld in ("min_rated_items", "min_material_items"):
            want = re.findall(fld + r" (\d+)", me)
            found = set(re.findall(fld + r": (\d+)", ev_text))
            report.check("K07", bool(want) and found == set(want), f"EVALS.md section 6 {fld} {sorted(found)} differs from decision-statistics.yaml SHADOW_WEEK {want}")
        f5_text = (root / "05_Build_Phases" / "F5_Eval_Shadow.md").read_text(encoding="utf-8")
        for name, txt in (("EVALS.md", ev_text), ("F5_Eval_Shadow.md", f5_text)):
            report.check("K07", "5–7-kunlarda" in txt and "oynaning oxirgi 3 kunida" in txt and "yakuniy" in txt,
                         f"{name}: the zero-harmful window must name days 5-7 and the last 3 days of the final (possibly extended) window, like SHADOW_WEEK.zero_harmful_windows")
    # K04 (document consumers) a document that applies a shared decision rule names decision-statistics.yaml and the rule id
    for rid, rule in ((c.get("decision-statistics.yaml") or {}).get("decision_rules") or {}).items():
        for cons in (rule or {}).get("consumers") or []:
            f = str(cons).partition("#")[0]
            if f.endswith(".md"):
                doc = root / f
                text = doc.read_text(encoding="utf-8") if doc.exists() else ""
                report.check("K04", "decision-statistics.yaml" in text and rid in text, f"decision rule {rid}: document consumer {f} must cite decision-statistics.yaml and {rid}")
    # D18 incident IDs live in their own namespace (INC-NN, defined in INCIDENTS.md); a hyphenated I-NN would collide with invariants
    inc_file = root / "06_Runbooks" / "INCIDENTS.md"
    inc_def = rows(inc_file, r"^\|\s*\**(INC-\d{2})\b")
    bad, undefined = {}, {}
    for p, t in all_texts.items():
        for m in re.finditer(r"(?<![\w-])I-\d{2}(?!\w)", t):
            bad.setdefault(m.group(0), rel(p))
        for m in re.finditer(r"(?<![\w-])INC-\d{2}(?!\d)", t):
            if m.group(0) not in inc_def:
                undefined.setdefault(m.group(0), rel(p))
    report.check("D18", not bad, "incident IDs must use INC-NN: " + ", ".join(f"{k} ({v})" for k, v in sorted(bad.items())[:20]))
    report.check("D18", not undefined, "undefined incident IDs: " + ", ".join(f"{k} ({v})" for k, v in sorted(undefined.items())[:20]))
    report.facts["incidents"] = len(inc_def)
    # D19 owner decision texts equal the lock file (an edit needs a deliberate lock update)
    lock_path = root / "00_Decisions" / "OWNER_DECISIONS.lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        current = {(r["id"], r["n"]): r for r in owner_decision_rows((root / "00_Decisions" / "DECISION_LOG.md").read_text(encoding="utf-8"))}
        locked = {(r["id"], r["n"]): r for r in lock.get("rows", [])}
        changed = sorted(f"{k[0]}#{k[1]}" for k in locked.keys() & current.keys() if (locked[k]["sha256"], locked[k]["status"]) != (current[k]["sha256"], current[k]["status"]))
        report.check("D19", not changed, f"owner decision text or status differs from OWNER_DECISIONS.lock.json: {changed}")
        report.check("D19", locked.keys() == current.keys(), f"owner decision rows added or removed without a lock update: +{sorted(current.keys() - locked.keys())} -{sorted(locked.keys() - current.keys())}")
        report.facts["owner_decision_rows"] = len(current)
    else:
        report.check("D19", False, "00_Decisions/OWNER_DECISIONS.lock.json is missing")
    # D17 TEAM §7.1 action table lists exactly the approval-policy actions
    team = root / "02_Team_Charter" / "TEAM.md"
    acts = set(c.get("approval-policy.yaml", {}).get("actions", {}))
    if team.exists() and acts:
        tt = team.read_text(encoding="utf-8")
        sec = tt.split("### 7.1", 1)[1].split("\n### ", 1)[0] if "### 7.1" in tt else ""
        listed = set()
        for line in sec.splitlines():
            if line.startswith("| `"):
                listed |= set(re.findall(r"`([a-z_]+)`", line.split("|")[1]))
        report.check("D17", listed == acts, f"TEAM §7.1 action table differs from approval-policy actions: +{sorted(listed - acts)} -{sorted(acts - listed)}")
    # D12 readiness keys in backticks
    if "readiness.yaml" in c:
        keys = {r["key"] for r in c["readiness.yaml"]["requirements"]}
        known_other = set(c.get("execution-policy.yaml", {}).get("capability_requires_profile", {}))
        for agent in c.get("approval-policy.yaml", {}).get("agents", {}).values():
            known_other |= {t.rstrip("*").rstrip(".") for t in agent["tools"]}
        known_other |= set(c.get("approval-policy.yaml", {}).get("internal_auto_tools", []))
        bridge = c.get("runtime-isolation.yaml", {}).get("paperclip_bridge", {})
        known_other |= set(bridge.get("allowed_ops", [])) | set(bridge.get("denied_ops", []))
        unknown = {}
        for p, t in texts.items():
            for tok in re.findall(r"`([a-z_]+\.[a-z0-9_]+)`", t):
                ns = tok.split(".")[0]
                if ns in READINESS_NS and tok not in keys and tok not in known_other and not re.search(r"\.(ya?ml|md|json|py|sh|env)$", tok):
                    unknown.setdefault(tok, rel(p))
        report.check("D12", not unknown, "unknown readiness-like keys: " + ", ".join(f"{k} ({v})" for k, v in sorted(unknown.items())[:25]))
    # T07 schedule times quoted in role/ops/phase tables equal operations.yaml#schedule
    sched = c.get("operations.yaml", {}).get("schedule", [])
    times = {row["id"]: schedule_time(sched, row["id"]) for row in sched}
    for rel_path in ("02_Team_Charter/TEAM.md", "06_Runbooks/DAILY_WEEKLY_OPS.md", "05_Build_Phases/F4_Agents.md"):
        f = root / rel_path
        if not f.exists():
            continue
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.startswith("|"):
                continue
            for sid, hhmm in times.items():
                if hhmm and re.search(r"`" + re.escape(sid) + r"`", line):
                    shown = re.findall(r"\b\d{2}:\d{2}\b", line)
                    if shown and hhmm not in shown:
                        report.check("T07", False, f"{rel_path}:{n} `{sid}` shows {shown} but operations.yaml#schedule says {hhmm}")
    report.checked.add("T07")
    # T10 every operations.yaml#schedule id appears in the schedule tables of TEAM, DAILY_WEEKLY_OPS and F4_Agents (copies must be complete)
    sched_ids = {row["id"] for row in sched}
    for rel_path in ("02_Team_Charter/TEAM.md", "06_Runbooks/DAILY_WEEKLY_OPS.md", "05_Build_Phases/F4_Agents.md"):
        f = root / rel_path
        if not f.exists() or not sched_ids:
            continue
        shown_ids = set()
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.startswith("|"):
                shown_ids |= set(re.findall(r"`([a-z_]+)`", line))
        missing_ids = sorted(sched_ids - shown_ids)
        report.check("T10", not missing_ids, f"{rel_path}: schedule table misses operations.yaml#schedule ids {missing_ids}")
    # D13 agent tool tables equal the allowlist (F4-AT-17)
    roles = {"CMO.md": "cmo", "MEDIA_BUYER.md": "media-buyer", "CREATIVE_STUDIO.md": "creative-studio", "CRO.md": "cro", "FUNNEL_ANALYST.md": "funnel-analyst", "REVIEWER.md": "reviewer"}
    allow = c.get("approval-policy.yaml", {}).get("agents", {})
    for fname, agent_slug in roles.items():
        f = root / "02_Team_Charter" / "agents" / fname
        if f.exists() and agent_slug in allow:
            listed = set(re.findall(r"^\| `([a-z_]+\.[a-z_.*]+)` \|", f.read_text(encoding="utf-8"), re.M))
            tools = set(allow[agent_slug]["tools"])
            report.check("D13", listed == tools, f"{fname}: tool table differs from approval-policy agents.{agent_slug}.tools: +{sorted(listed - tools)} -{sorted(tools - listed)}")
    # D14 GUARDRAIL_GATEWAY §2 agent tool table equals the allowlist
    gg = root / "03_Architecture" / "GUARDRAIL_GATEWAY.md"
    if gg.exists() and allow:
        seen = set()
        for line in gg.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*`([a-z-]+)`\s*\|\s*`[a-z-]+`\s*\|(.*)\|\s*$", line)
            if m and m.group(1) in allow:
                seen.add(m.group(1))
                listed = set(re.findall(r"`([a-z_]+\.[a-z_.*]+)`", m.group(2)))
                tools = set(allow[m.group(1)]["tools"])
                report.check("D14", listed == tools, f"GUARDRAIL_GATEWAY §2 {m.group(1)}: +{sorted(listed - tools)} -{sorted(tools - listed)}")
        report.check("D14", seen == set(allow), f"GUARDRAIL_GATEWAY §2 has no row for {sorted(set(allow) - seen)}")
    # D20 GUARDRAIL §5.1 action table equals approval-policy actions (approvers, max level, review_required, two-step)
    acts_cfg = c.get("approval-policy.yaml", {}).get("actions", {})
    if gg.exists() and acts_cfg:
        sec51 = gg.read_text(encoding="utf-8").split("### 5.1", 1)[-1].split("\n### ", 1)[0]
        seen51 = {}
        for line in sec51.splitlines():
            m = re.match(r"^\|\s*`([a-z_]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|", line)
            if m and m.group(1) in acts_cfg:
                seen51[m.group(1)] = [x.strip() for x in m.groups()[1:]]
        report.check("D20", set(seen51) == set(acts_cfg), f"GUARDRAIL §5.1 rows differ from approval-policy actions: +{sorted(set(seen51) - set(acts_cfg))} -{sorted(set(acts_cfg) - set(seen51))}")
        for name, (appr_cell, max_cell, rev_cell, two_cell) in seen51.items():
            spec = acts_cfg[name]
            shown_appr = [] if appr_cell.startswith("—") else [x.strip().strip("`") for x in appr_cell.split(",")]
            ok_appr = shown_appr == list(spec.get("approvers") or [])
            ok_max = (max_cell == spec.get("max_level")) or (spec.get("max_level") is None and max_cell in ("auto", "pre-authorized"))
            ok_rev = rev_cell == str(spec.get("review_required")).lower()
            ok_two = (two_cell == "—" and not spec.get("two_step")) or two_cell == spec.get("two_step")
            report.check("D20", ok_appr and ok_max and ok_rev and ok_two, f"GUARDRAIL §5.1 {name}: {appr_cell} | {max_cell} | {rev_cell} | {two_cell} differs from config")
    # D21 ARCHITECTURE §3.1 service table equals runtime-isolation.yaml#services
    arch = root / "03_Architecture" / "ARCHITECTURE.md"
    services = c.get("runtime-isolation.yaml", {}).get("services", [])
    if arch.exists() and services:
        sec31 = arch.read_text(encoding="utf-8").split("### 3.1", 1)[-1].split("\n### ", 1)[0]
        table = {}
        for line in sec31.splitlines():
            if line.startswith("| `"):
                cells = [x.strip().replace("`", "").replace("\\|", "|") for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                table[cells[0]] = cells
        fields = ("service_id", "unit", "uid", "listen", "db_role", "credential_file", "egress", "ack_class")
        reg = {str(sv["service_id"]): [str(sv[f]) for f in fields] for sv in services}
        report.check("D21", set(table) == set(reg), f"ARCHITECTURE §3.1 rows differ from the registry: +{sorted(set(table) - set(reg))} -{sorted(set(reg) - set(table))}")
        for sid in set(table) & set(reg):
            report.check("D21", table[sid] == reg[sid], f"ARCHITECTURE §3.1 {sid}: {table[sid]} != registry {reg[sid]}")
    # D32 the Reviewer subject_type enum is one list (REVIEWER schema, GUARDRAIL §9.2/§9.3, DATA_MODEL review_subjects) and the Jev pre-screen uses only its members
    rv, gw, dm = root / "02_Team_Charter" / "agents" / "REVIEWER.md", root / "03_Architecture" / "GUARDRAIL_GATEWAY.md", root / "03_Architecture" / "DATA_MODEL.md"
    if rv.exists() and gw.exists() and dm.exists():
        def enum_from_json(text):
            m = re.search(r'"subject_type":\s*"([^"]+)"', text)
            return {x.strip() for x in m.group(1).split("|")} if m else set()
        rv_set, gw_set = enum_from_json(rv.read_text(encoding="utf-8")), enum_from_json(gw.read_text(encoding="utf-8"))
        m = re.search(r"`subject_type` \(([^)]*)\)", dm.read_text(encoding="utf-8"))
        dm_set = set(re.findall(r"`([a-z_]+)`", m.group(1))) if m else set()
        sec92 = gw.read_text(encoding="utf-8").split("### 9.2", 1)[-1].split("\n### ", 1)[0]
        tbl = set(re.findall(r"^\| `([a-z_]+)` \|", sec92, re.M)) - {"subject_type"}
        pre = set((c.get("approval-policy.yaml", {}).get("creative_review", {}).get("pre_screen") or {}).get("subject_types", []))
        report.check("D32", rv_set and rv_set == gw_set == dm_set == tbl and pre <= rv_set, f"Reviewer subject_type enum differs: REVIEWER {sorted(rv_set)} GUARDRAIL json {sorted(gw_set)} table {sorted(tbl)} DATA_MODEL {sorted(dm_set)}; pre_screen {sorted(pre)}")
    # D33 the owner bootstrap never shares the builder checkout with amt-build (P-05: a dependency hook running as amt-build must not edit files the builder runs with sudo)
    f0 = root / "05_Build_Phases" / "F0_Server.md"
    if f0.exists():
        f0t = f0.read_text(encoding="utf-8")
        boot_path = root / "05_Build_Phases" / "SERVER_ADOPTION.md"
        boot = boot_path.read_text(encoding="utf-8") if boot_path.exists() else ""
        shared = re.findall(r"^.*(?:chgrp[^\n]*amt-build[^\n]*/srv/builder|/srv/builder[^\n]*chmod[^\n]*g\+[rwsx]|chmod[^\n]*g\+s[^\n]*/srv/builder).*$", boot, re.M)
        report.check("D33", "install -d -m 700 -o builder -g builder /srv/builder" in boot and not shared and "git -C /srv/builder/wolter-amt archive" in f0t,
                     f"F0: /srv/builder must be builder-only (0700), never group-shared or setgid for amt-build, and builds run on a clean git archive export: {shared[:3]}")
    # D22 every amt-kill invocation in the docs uses only kill_cli arguments
    kc = c.get("execution-policy.yaml", {}).get("kill_cli", {})
    allowed_args = set(re.findall(r"--[a-z-]+(?:\s+[a-z_]+)?", " ".join(str(kc.get(k, "")) for k in ("kill", "status", "self_test"))))
    if kc:
        bad_kill = {}
        for p_, t in texts.items():
            for m in re.finditer(r"amt-kill((?:\s+--[a-z-]+(?:\s+[A-Za-z_|]+)?)+)", t):
                for arg in re.findall(r"--[a-z-]+(?:\s+[A-Za-z_|]+)?", m.group(1)):
                    parts = arg.split()
                    values = parts[1].split("|") if len(parts) > 1 else [None]
                    for v in values:
                        cand = parts[0] + (" " + v if v else "")
                        if cand not in allowed_args and parts[0] not in allowed_args:
                            bad_kill.setdefault(cand, rel(p_))
        report.check("D22", not bad_kill, "amt-kill arguments outside execution-policy.yaml#kill_cli: " + ", ".join(f"{k} ({v})" for k, v in sorted(bad_kill.items())))
    # D23 Telegram command table and roles.yaml command lists name the same commands
    tg = root / "03_Architecture" / "TELEGRAM.md"
    ro_cfg = c.get("roles.yaml", {}).get("role_permissions", {})
    if tg.exists() and ro_cfg:
        tg_cmds = set()
        for line in tg.read_text(encoding="utf-8").splitlines():
            if line.startswith("| `/"):
                for m in re.finditer(r"`/([a-z_]+)(?: (raise|engineering))?", line.split("|")[1]):
                    tg_cmds.add(m.group(1) + ("_" + m.group(2) if m.group(2) else ""))
        role_cmds = {x for v in ro_cfg.values() for x in v.get("commands", [])}
        report.check("D23", tg_cmds == role_cmds, f"TELEGRAM commands vs roles.yaml: telegram only {sorted(tg_cmds - role_cmds)}, roles only {sorted(role_cmds - tg_cmds)}")
    # D24 ARCHITECTURE §10.1 control-op matrix equals runtime-isolation.yaml#control_socket_peers
    peers_cfg = c.get("runtime-isolation.yaml", {}).get("control_socket_peers", {})
    if arch.exists() and peers_cfg:
        sec101 = arch.read_text(encoding="utf-8").split("### 10.1", 1)[-1].split("\n### ", 1)[0]
        want_pairs = {(op, peer) for peer, ops in peers_cfg.items() for op in ops}
        got_pairs = set()
        for line in sec101.splitlines():
            if not line.startswith("| `"):
                continue
            cells = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            ops = re.findall(r"`([a-z0-9_]+)`", cells[0])
            peers = list(peers_cfg) if "barcha peer" in cells[1] else re.findall(r"`([a-z:-]+)`", cells[1])
            got_pairs |= {(op, peer) for op in ops for peer in peers}
        report.check("D24", got_pairs == want_pairs, f"ARCHITECTURE §10.1 op/peer matrix differs from control_socket_peers: +{sorted(got_pairs - want_pairs)} -{sorted(want_pairs - got_pairs)}")
    # D25 every protective-control table lists exactly operations.yaml#protective_controls
    pc_ids = {str(x["id"]) for x in c.get("operations.yaml", {}).get("protective_controls", [])}
    if pc_ids:
        for rel_path in ("03_Architecture/ARCHITECTURE.md", "03_Architecture/SECURITY.md", "04_ADR/ADR-030-kill-modes-and-protective-controls.md",
                         "06_Runbooks/KILL_SWITCH.md", "11_Production_Contracts/OPERATING_ENVELOPE.md"):
            f = root / rel_path
            if not f.exists():
                continue
            listed, in_table = set(), False
            for line in f.read_text(encoding="utf-8").splitlines():
                if re.match(r"^\|\s*id\s*\|\s*trigger\s*\|", line, re.I):
                    in_table = True
                    continue
                if in_table and line.startswith("|"):
                    m = re.match(r"^\|\s*`([a-z0-9_]+)`", line)
                    if m:
                        listed.add(m.group(1))
                    continue
                in_table = False
            report.check("D25", listed == pc_ids, f"{rel_path}: protective-control table differs from operations.yaml: +{sorted(listed - pc_ids)} -{sorted(pc_ids - listed)}")
    # D26 every mutating /role subcommand in TELEGRAM maps to an op in role_change.includes
    rc = c.get("approval-policy.yaml", {}).get("actions", {}).get("role_change", {})
    if tg.exists() and rc:
        role_line = next((l for l in tg.read_text(encoding="utf-8").splitlines() if l.startswith("| `/role ")), "")
        first = re.split(r"(?<!\\)\|", role_line.strip().strip("|"))[0] if role_line else ""
        subs = set()
        for seg in re.findall(r"`/role ([^`]+)`", first):
            words = seg.replace("\\|", "|").split()
            if words and words[0] == "flag" and len(words) > 1:
                subs |= {"flag " + x for x in words[1].split("|")}
            elif words:
                subs |= set(words[0].split("|"))
        subs.discard("list")
        cmd_ops = rc.get("command_ops") or {}
        report.check("D26", subs == set(cmd_ops), f"TELEGRAM /role subcommands differ from role_change.command_ops: +{sorted(subs - set(cmd_ops))} -{sorted(set(cmd_ops) - subs)}")
        report.check("D26", set(cmd_ops.values()) | {"membership_expiry"} == set(rc.get("includes", [])), "role_change.includes must be exactly the command ops plus membership_expiry")
    # D27 every AUDIT_FINDINGS fixed_in path exists
    af = root / "00_Decisions" / "AUDIT_FINDINGS.json"
    if af.exists():
        missing_fix = {}
        for it in json.loads(af.read_text(encoding="utf-8")).get("findings", []):
            for v in it.get("fixed_in") or []:
                for part in re.split(r"[;,]\s*", str(v)):
                    fp = part.split("#")[0].split(" ")[0].strip()
                    if fp and not fp.startswith("http") and not (root / fp).exists():
                        missing_fix.setdefault(fp, it.get("id"))
        report.check("D27", not missing_fix, "AUDIT_FINDINGS fixed_in paths that do not exist: " + ", ".join(f"{k} ({v})" for k, v in sorted(missing_fix.items())))
    # D28 OBSERVABILITY §6.2 slice table equals resource-policy.yaml#slices
    obs = root / "03_Architecture" / "OBSERVABILITY.md"
    slices_cfg = c.get("resource-policy.yaml", {}).get("slices", {})
    if obs.exists() and slices_cfg and services:
        sids = {str(sv["service_id"]) for sv in services}
        sec62 = obs.read_text(encoding="utf-8").split("### 6.2", 1)[-1].split("\n### ", 1)[0]
        got_slices = {}
        for line in sec62.splitlines():
            m = re.match(r"^\| `([a-z]+)` \|([^|]*)\|", line)
            if m and m.group(1) in slices_cfg:
                got_slices[m.group(1)] = {x for x in re.findall(r"`([a-z0-9-]+)`", m.group(2)) if x in sids}
        report.check("D28", got_slices == {k: set(v) for k, v in slices_cfg.items()}, f"OBSERVABILITY §6.2 slice table differs from resource-policy.yaml#slices: {got_slices}")
    # D29 an evidence age written next to a readiness key in any doc equals readiness.yaml max_evidence_age
    ages = {x["key"]: x.get("max_evidence_age") for x in c.get("readiness.yaml", {}).get("requirements", [])}
    if ages:
        bad_age = {}
        for p_, t in texts.items():
            for m in re.finditer(r"`([a-z_]+\.[a-z0-9_]+)`\s*\(\s*`?(?:max_evidence_age:\s*)?(P\d+[DWM])`?", t):
                if m.group(1) in ages and ages[m.group(1)] != m.group(2):
                    bad_age.setdefault(f"{m.group(1)} {m.group(2)}", rel(p_))
        report.check("D29", not bad_age, "evidence ages that differ from readiness.yaml: " + ", ".join(f"{k} ({v})" for k, v in sorted(bad_age.items())))
    # D30 every config file that is a protected surface has the "PR + E" change path in CONFIG_CONTRACT §1
    prot = {m.group(1) for x in c.get("evolution-policy.yaml", {}).get("protected_surfaces", []) for m in [re.match(r"config/([a-z-]+\.yaml)", str(x))] if m}
    cc30 = root / "11_Production_Contracts" / "CONFIG_CONTRACT.md"
    if cc30.exists() and prot:
        paths = {}
        for line in cc30.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\| \[([a-z-]+\.yaml)\]\(\.\./09_Config_Templates/[a-z-]+\.yaml\) \|", line)
            if m:
                paths[m.group(1)] = re.split(r"(?<!\\)\|", line)[3]
        wrong = sorted(f for f in prot if "PR + E" not in paths.get(f, ""))
        report.check("D30", not wrong, f"CONFIG_CONTRACT §1 change path lacks 'PR + E' for protected configs: {wrong}")
    # D31 maintenance release is never described as restoring all previous modes (protective controls raised during the hold persist)
    stale_mr = sorted({rel(p_) for p_, t in texts.items() for line in t.splitlines()
                       if re.search(r"oldingi rejimlar (tiklanadi|qaytadi)|hold’dan oldingi holatni tiklaydi", line) and "maintenance" in line.lower()})
    report.check("D31", not stale_mr, f"maintenance release described as restoring all previous modes: {stale_mr}")
    # D15 skill Tool scope: a role is instructed to call a tool only where the skill lists it; D16 charters name only own tools
    known_tools = set().union(*(set(v.get("tools", [])) for v in allow.values())) if allow else set()
    known_tools |= set(c.get("approval-policy.yaml", {}).get("internal_auto_tools", []))
    if known_tools:
        namespaces = sorted({t.split(".")[0] for t in known_tools})
        tool_re = re.compile(r"(?<![\w/.-])((?:%s)\.[a-z0-9_]+(?:\.[a-z0-9_]+)*(?:\.\*)?)" % "|".join(map(re.escape, namespaces)))
        skill_files = {f.parent.name: f for f in (root / "08_Skills").glob("*/SKILL.md")}
        loads = {}
        for fname, agent_slug in roles.items():
            f = root / "02_Team_Charter" / "agents" / fname
            if not f.exists() or agent_slug not in allow:
                continue
            text = f.read_text(encoding="utf-8")
            m = re.search(r"^Skill’lar:\s*(.+)$", text, re.M)
            named_skills = set(re.findall(r"\b([a-z]+(?:-[a-z]+)+)\b", m.group(1))) & set(skill_files) if m else set()
            loads[agent_slug] = named_skills
            report.check("D15", bool(m) and "thinking-kernel" in named_skills, f"{fname}: no 'Skill’lar:' line loading thinking-kernel")
            extra = {x for x in tool_re.findall(text) if x in known_tools} - set(allow[agent_slug]["tools"])
            report.check("D16", not extra, f"{fname}: charter or prompt names tools outside agents.{agent_slug}.tools: {sorted(extra)}")
        for sk, f in sorted(skill_files.items()):
            body, sep, scope = f.read_text(encoding="utf-8").partition("\n## Tool scope")
            mentioned = {x for x in tool_re.findall(body) if x in known_tools}
            scope_rows = re.findall(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*(call|citation)\s*\|", scope, re.M)
            listed = {t for t, _, _ in scope_rows}
            report.check("D15", not mentioned or bool(sep), f"{sk}: names tools but has no Tool scope section")
            report.check("D15", mentioned <= listed, f"{sk}: tools named outside its Tool scope table: {sorted(mentioned - listed)}")
            for tool, roles_cell, mention in scope_rows:
                report.check("D15", tool in known_tools, f"{sk}: Tool scope names unknown tool {tool}")
                if roles_cell.strip() in ("—", "-"):
                    report.check("D15", mention == "citation", f"{sk}: {tool} has no instructed role but is marked {mention}")
                    continue
                for role in (x.strip() for x in roles_cell.split(",")):
                    report.check("D15", role in allow and tool in allow[role]["tools"], f"{sk}: {role} is instructed to use {tool} without holding it")
                    report.check("D15", sk in loads.get(role, set()), f"{sk}: {role} is listed in Tool scope but its charter does not load the skill")
    # R16 CONFIG_CONTRACT readiness table matches readiness.yaml (gate, criticality, signers, max_evidence_age)
    cc = root / "11_Production_Contracts" / "CONFIG_CONTRACT.md"
    reqs = {x["key"]: x for x in c.get("readiness.yaml", {}).get("requirements", [])}
    if cc.exists() and reqs:
        cc_rows = {}
        for line in cc.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*`([a-z_]+\.[a-z0-9_.]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|", line)
            if m and m.group(1) in reqs and re.match(r"\s*[A-Z][A-Z0-9_]+", m.group(2)):
                cc_rows[m.group(1)] = [x.strip() for x in m.groups()[1:]]
        for k, x in reqs.items():
            if k not in cc_rows:
                report.check("R16", False, f"CONFIG_CONTRACT §4 has no row for readiness key {k}")
                continue
            gate_cell, crit, signers = cc_rows[k]
            gate = re.match(r"[A-Z0-9_]+", gate_cell).group(0)
            age = re.search(r"max_evidence_age:\s*(P\w+)", gate_cell)
            got = (gate, crit, sorted(s.strip() for s in signers.split("+")), age.group(1) if age else None)
            want = (x["gate"], x["criticality"], sorted([x["accountable_role"]] + list(x.get("co_signers") or [])), x.get("max_evidence_age"))
            report.check("R16", got == want, f"CONFIG_CONTRACT §4 {k}: {got} != readiness.yaml {want}")
        report.checked.add("R16")
    evc = root / "11_Production_Contracts" / "EVOLUTION_CONTRACT.md"
    if evc.exists() and reqs:
        for line in evc.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|[^|]*\|\s*`([a-z_]+\.[a-z0-9_.]+)`\s*(\((optional|critical)\))?\s*\|\s*([A-Z][A-Z0-9_]+)\s*\|", line)
            if m and m.group(1) in reqs:
                x = reqs[m.group(1)]
                crit = m.group(3) or "critical"
                report.check("R18", (m.group(4), crit) == (x["gate"], x["criticality"]), f"EVOLUTION_CONTRACT {m.group(1)}: {m.group(4)}/{crit} != readiness.yaml {x['gate']}/{x['criticality']}")
        report.checked.add("R18")
        rf_line = next((l for l in cc.read_text(encoding="utf-8").splitlines() if l.startswith("Yozuv maydonlari (`readiness.yaml#record_fields`)")), "")
        listed_fields = re.findall(r"`([a-z_]+)`", rf_line.split(":", 1)[1]) if ":" in rf_line else []
        report.check("R17", listed_fields == list(c.get("readiness.yaml", {}).get("record_fields", [])), f"CONFIG_CONTRACT record field list differs from readiness.yaml#record_fields: {listed_fields}")
    # Z01 version residue
    hits = []
    for p, t in {**all_texts, **json_texts}.items():
        if p.name == "THINKING_MODELS.md":
            continue
        for n, line in enumerate(t.splitlines(), 1):
            url_spans = [u.span() for u in re.finditer(r"https?://[^\s)>\]]+", line)]
            for pattern, label in RESIDUE_PATTERNS:
                for m in re.finditer(pattern, line):
                    if any(a <= m.start() < b for a, b in url_spans):
                        continue
                    ctx = line[max(0, m.start() - 25): m.end() + 5]
                    if RESIDUE_ALLOW.search(ctx):
                        continue
                    hits.append(f"{rel(p)}:{n} {label}: {line.strip()[:80]}")
    report.check("Z01", not hits, "version residue: " + " | ".join(hits[:20]))
    report.facts["markdown_files"] = len(md_files)


def defined_test_ids(root: Path) -> set[str]:
    ids = set()
    for f in (root / "05_Build_Phases").glob("F*.md"):
        ids |= set(re.findall(r"^\|\s*\**((?:F[0-7]|FE)-AT-[0-9A-Za-z]+)\**\s*\|", f.read_text(encoding="utf-8"), re.M))
    acc = root / "12_Acceptance"
    ids |= set(re.findall(r"^\|\s*\**((?:UAT-\d+|EVO-AT\d+))\**\s*\|", (acc / "PRODUCTION_ACCEPTANCE.md").read_text(encoding="utf-8"), re.M))
    ids |= set(re.findall(r"^\|\s*\**(WF-TEST-[A-Z0-9-]+)\**\s*\|", (acc / "WORKFLOW_TESTS.md").read_text(encoding="utf-8"), re.M))
    return ids


def traceability_rules(root: Path, report: Report, configs: dict | None = None):
    path = root / "12_Acceptance" / "REQUIREMENT_TRACEABILITY.json"
    try:
        tr = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.check("Q01", False, f"traceability unreadable: {exc}")
        return
    prd = (root / "01_PRD" / "PRD.md").read_text(encoding="utf-8")
    prd_ids = set(re.findall(r"^\|\s*\**((?:FR|NFR)-[A-Z]*-?\d+|EVO-R\d{2})\**\s*\|", prd, re.M))
    req_ids = {r["id"] for r in tr.get("requirements", [])}
    report.check("Q02", prd_ids <= req_ids, f"PRD requirements missing in traceability: {sorted(prd_ids - req_ids)[:20]}")
    report.check("Q03", all(r.get("tests") for r in tr.get("requirements", [])), "every requirement needs at least one test")
    for r in tr.get("requirements", []):
        for ref in r.get("canonical", []):
            report.check("Q04", (root / ref.split("#")[0]).exists(), f"{r['id']}: canonical ref missing {ref}")
    inv = tr.get("invariants", {})
    report.check("Q05", all((inv.get(f"I{n:02d}") or {}).get("tests") for n in range(1, 26)), "every invariant I01-I25 needs tests")
    tests = defined_test_ids(root)
    used = {t for r in tr.get("requirements", []) for t in r.get("tests", [])} | {t for v in inv.values() for t in v.get("tests", [])}
    report.check("Q06", used <= tests, f"traceability cites undefined tests: {sorted(used - tests)[:20]}")
    wf_listed = {t for wf in (configs or {}).get("_workflows", {}).values() for t in wf.get("tests", [])}
    wf_bound = {t for t in tests if t in wf_listed or any(w.endswith("*") and t.startswith(w.rstrip("*")) for w in wf_listed)}
    unbound = tests - used - wf_bound
    report.check("Q07", not unbound, f"defined tests bound to no requirement, invariant or workflow: {sorted(unbound)[:25]}")
    test_re = r"(?:(?:F[0-7]|FE)-AT-[0-9A-Za-z]+|UAT-\d+|EVO-AT\d+|WF-TEST-[A-Z0-9-]+\*?)"
    prd_tests = {}
    for line in prd.splitlines():
        m = re.match(r"^\|\s*\**((?:FR|NFR)-[A-Z]*-?\d+|EVO-R\d{2})\**\s*\|", line)
        if m:
            prd_tests[m.group(1)] = set(re.findall(test_re, line.strip().strip("|").split("|")[-1]))
    for r in tr.get("requirements", []):
        report.check("Q08", set(r.get("tests", [])) == prd_tests.get(r["id"], set()), f"{r['id']}: PRD test column differs from traceability")
    inv_doc = (root / "11_Production_Contracts" / "INVARIANTS.md").read_text(encoding="utf-8")
    for block in re.split(r"\n(?=I[0-2]\d\. )", inv_doc):
        m = re.match(r"(I[0-2]\d)\. ", block)
        t = re.search(r"Tekshiruv:([^\n]*)", block) if m else None
        if m and m.group(1) in inv:
            report.check("Q08", t is not None and set(re.findall(test_re, t.group(1))) == set(inv[m.group(1)].get("tests", [])), f"{m.group(1)}: INVARIANTS Tekshiruv differs from traceability")
    for wf_name, wf in (configs or {}).get("_workflows", {}).items():
        refs = set(wf.get("requirement_refs", []))
        report.check("W05", refs <= prd_ids, f"{wf_name}: requirement_refs not in PRD: {sorted(refs - prd_ids)}")
    report.facts["requirements"] = len(req_ids)


# ---------------------------------------------------------------- builder context packs (CLAUDE.md §0; rules C01-C03)

PACKS_FILE = Path("05_Build_Phases") / "CONTEXT_PACKS.yaml"


def load_packs(root: Path):
    f = root / PACKS_FILE
    return yaml.load(f.read_text(encoding="utf-8"), Loader=UniqueLoader) if f.exists() else None


def estimate_tokens(text: str, est: dict) -> int:
    """Conservative token estimate per paragraph: Uzbek prose, English prose or structured text (CONTEXT_PACKS.yaml#estimator)."""
    total = 0.0
    for block in re.split(r"\n\s*\n", text):
        if not block.strip():
            continue
        marks = (block.count("‘") + block.count("’")) * 1000 / max(1, len(block))
        if marks >= est["uzbek_marker_per_1000_chars"]:
            ratio = est["uzbek_prose_chars_per_token"]
        elif re.match(r"^\s*[{\[]|^\s*[a-z_]+:\s", block):
            ratio = est["structured_chars_per_token"]
        else:
            ratio = est["english_prose_chars_per_token"]
        total += len(block) / ratio
    return int(total + 0.999)


def md_section(text: str, heading: str) -> str | None:
    """Section from a Markdown heading to the next heading of the same or a higher level; '#' lines inside fenced code are not headings."""
    lines, fence = text.splitlines(), False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        m = None if fence else re.match(r"^(#+)\s+(.*)$", line)
        if m and m.group(2).strip() == heading:
            level, out, inner = len(m.group(1)), [line], False
            for nxt in lines[i + 1:]:
                if nxt.lstrip().startswith("```"):
                    inner = not inner
                n = None if inner else re.match(r"^(#+)\s", nxt)
                if n and len(n.group(1)) <= level:
                    break
                out.append(nxt)
            return "\n".join(out).rstrip()
    return None


def _plain(cell: str, limit: int) -> str:
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    t = re.sub(r"\*\*|`", "", t).strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def decision_digest(root: Path) -> list[str]:
    dl = (root / "00_Decisions" / "DECISION_LOG.md").read_text(encoding="utf-8")
    out, sec = ["## Qarorlar digest’i (avtomatik; asl matn — DECISION_LOG.md)", ""], ""
    for line in dl.splitlines():
        m = re.match(r"^## ([A-Z])\.", line)
        if m:
            sec = m.group(1)
        elif line.startswith("## "):
            sec = "P" if "◇" in line else ""
        cells = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip())[1:-1]] if line.startswith("|") else []
        if sec in ("A", "B", "C", "D", "E", "I") and line.startswith("| Q") and len(cells) >= 3:
            out.append(f"- {cells[0]} {cells[2]} — {_plain(cells[1], 170)}")
        elif sec == "G" and len(cells) >= 2 and not cells[0].startswith(("Soha", "---")):
            out.append(f"- ★ {_plain(cells[0], 40)} — {_plain(cells[1], 170)}")
        elif sec == "P" and line.startswith("| P-") and len(cells) >= 5:
            out.append(f"- {cells[0]} ({_plain(cells[4], 30)}) — {_plain(cells[2], 120)}")
    oi = (root / "00_Decisions" / "OPEN_ITEMS.md").read_text(encoding="utf-8")
    out += ["", "## Ochiq owner qarorlari (⧗)", ""]
    oi_open, oi_closed = decision_item_sections(oi)
    for line in oi_open.splitlines():
        if line.startswith("| OD-"):
            cells = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if len(cells) < 5:
                continue  # D37 reports the malformed open row; digest rendering must not crash.
            due = re.search(r"\d{4}-\d{2}-\d{2}", cells[5]) if len(cells) > 5 else None
            out.append(f"- {cells[0]} — {_plain(cells[1], 110)} → bloklaydi: {_plain(cells[4], 60)}" + (f"; kerak: {due.group(0)}" if due else ""))
    if oi_closed:
        out += ["", "## Yopilgan owner savollari (asl Q qarori ustun)", ""]
        for line in oi_closed.splitlines():
            if line.startswith("| OD-"):
                cells = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
                if len(cells) == 2:
                    out.append(f"- {cells[0]} yopildi — {_plain(cells[1], 170)}")
    return out


def pack_sources(root: Path) -> dict:
    """Files every pack reads, loaded once per validator run."""
    try:
        reqs = {r["key"]: r for r in yaml.safe_load((root / "09_Config_Templates" / "readiness.yaml").read_text(encoding="utf-8"))["requirements"]}
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        reqs = {}
    return {"claude": (root / "CLAUDE.md").read_text(encoding="utf-8"),
            "phases_md": (root / "05_Build_Phases" / "PHASES.md").read_text(encoding="utf-8"),
            "fe_md": (root / "05_Build_Phases" / "FE_Evolution.md").read_text(encoding="utf-8"),
            "inv": (root / "11_Production_Contracts" / "INVARIANTS.md").read_text(encoding="utf-8"),
            "digest": decision_digest(root), "reqs": reqs}


def render_pack(root: Path, packs: dict, phase: str, src: dict | None = None) -> tuple[str, int, list[str]]:
    """Render one phase pack; returns (markdown, estimated tokens, problems)."""
    src = src or pack_sources(root)
    spec, common, problems = packs["packs"][phase], packs["common"], []
    out = [f"# Context pack — {phase}", "",
           f"Avtomatik yaratilgan (`python3 12_Acceptance/validate_bundle.py --context-pack {phase}`); qo‘lda tahrirlanmaydi. Kanonik manbalar va ustuvorlik — [CLAUDE.md §0](../CLAUDE.md); bu paket faqat o‘qish tartibi.", ""]
    claude = src["claude"]
    for h in common["claude_md_sections"]:
        sec = md_section(claude, h)
        if sec is None:
            problems.append(f"CLAUDE.md has no section '{h}'")
        else:
            out += [sec.replace("\n## ", "\n### ").replace("## ", "### ", 1), ""]
    phases_md = src["phases_md"]
    for h in common["phases_md_sections"]:
        sec = md_section(phases_md, h)
        if sec is None:
            problems.append(f"PHASES.md has no section '{h}'")
        else:
            out += [sec, ""]
    hg = [l for l in phases_md.splitlines() if re.match(r"^\|\s*\**HG-", l) and (re.split(r"(?<!\\)\|", l)[2].strip() in (spec["hg_phase"], "doimiy"))]
    if spec["hg_phase"] == "FE":
        hg += [l for l in src["fe_md"].splitlines() if l.startswith("| HG-FE-")]
    if not hg:
        problems.append(f"no HUMAN_GATE rows for {spec['hg_phase']}")
    out += ["## HUMAN_GATE’lar (PHASES §4.1: shu faza va doimiy)", "", "| HG | Faza | Owner nima qiladi | Qaytariladigan narsa | Bloklaydi |", "|---|---|---|---|---|"] + hg + [""]
    out += src["digest"] + [""]
    pf = root / spec["phase_file"]
    if not pf.exists():
        problems.append(f"phase file {spec['phase_file']} missing")
        phase_text = ""
    else:
        phase_text = pf.read_text(encoding="utf-8")
    inv = src["inv"]
    named = sorted(set(re.findall(r"(?<![\w-])(I(?:0[1-9]|[12]\d))(?![\w-])", phase_text)))
    if named:
        out += ["## Faza fayli nomlagan invariantlar (birinchi jumla; to‘liq matn — INVARIANTS.md)", ""]
        for i_id in named:
            m = re.search(r"^" + i_id + r"\. (.+)$", inv, re.M)
            if m:
                out.append(f"- {i_id}. {_plain(m.group(1).split('. ')[0], 260)}")
        out.append("")
    reqs = src["reqs"]
    keys = sorted(k for k in set(re.findall(r"`([a-z_]+\.[a-z0-9_]+)`", phase_text)) if k in reqs)
    if keys:
        out += ["## Faza fayli nomlagan readiness kalitlari (readiness.yaml)", ""]
        out += [f"- `{k}` — gate {reqs[k]['gate']}, {reqs[k]['criticality']}, {reqs[k]['accountable_role']}" for k in keys] + [""]
    for h in spec.get("exclude_sections") or []:
        sec = md_section(phase_text, h)
        if sec is None:
            problems.append(f"{spec['phase_file']} has no section '{h}' to exclude")
            continue
        phase_text = phase_text.replace(sec, f"## {h}\n\n_(Pack’ga kiritilmagan — kerak bo‘lsa {spec['phase_file']} faylidagi shu bo‘limni oching.)_", 1)
    out += [f"## Faza fayli: {spec['phase_file']}", "", phase_text]
    text = "\n".join(out)
    return text, estimate_tokens(text, packs["estimator"]), problems


def pack_rules(root: Path, c: dict, report: Report):
    packs = c.get("_context_packs")
    if packs is None:
        report.check("C01", False, f"{PACKS_FILE} is missing (CLAUDE.md §0 reading packs)")
        return
    phases = sorted(f.stem.split("_")[0] for f in (root / "05_Build_Phases").glob("F*_*.md")
                    if re.fullmatch(r"F(?:[0-9]+|E)", f.stem.split("_")[0]))
    report.check("C01", set(phases) <= set(packs.get("packs") or {}), f"phases without a context pack: {sorted(set(phases) - set(packs.get('packs') or {}))}")
    budget = packs.get("budget_tokens") or 0
    sizes, src = {}, pack_sources(root)
    for phase in sorted(packs.get("packs") or {}):
        try:
            _, tokens, problems = render_pack(root, packs, phase, src)
        except (KeyError, TypeError) as exc:
            report.check("C03", False, f"pack {phase}: malformed definition ({exc})")
            continue
        sizes[phase] = tokens
        report.check("C02", 0 < budget <= 60000 and tokens <= budget, f"pack {phase}: ~{tokens} estimated tokens exceeds the budget {budget} (CONTEXT_PACKS.yaml)")
        report.check("C03", not problems, f"pack {phase}: {problems}")
    report.facts["context_pack_max_tokens"] = max(sizes.values()) if sizes else 0


# ---------------------------------------------------------------- runner

def report_rules(root: Path, report: Report):
    """Q09: VALIDATION_REPORT.md lists exactly the rules of this run and the current fixture counts (it is regenerated, never hand-edited)."""
    if os.environ.get("AMT_REPORT_GENERATION") == "1":
        report.checked.add("Q09")
        return
    vr = root / "12_Acceptance" / "VALIDATION_REPORT.md"
    if not vr.exists():
        report.check("Q09", False, "12_Acceptance/VALIDATION_REPORT.md is missing")
        return
    text = vr.read_text(encoding="utf-8")
    sec3 = text.split("## 3.", 1)[-1].split("\n## ", 1)[0]
    listed = {rid for line in sec3.splitlines() if line.startswith("| ") for rid in re.findall(r"\b[A-Z]\d{2}\b", line.split("|")[-2] if line.count("|") >= 3 else "")}
    current = report.checked | {"Q09"}
    report.check("Q09", listed == current, f"VALIDATION_REPORT §3 rule list differs from this run: +{sorted(listed - current)} -{sorted(current - listed)}")
    fx = yaml.safe_load((root / "12_Acceptance" / "fixtures" / "mutations.yaml").read_text(encoding="utf-8"))
    for kind, n in (("FX", len(fx.get("mutations", []))), ("PS", len(fx.get("profile_scenarios", []))), ("DM", len(fx.get("doc_mutations", []))),
                    ("HC", report.facts.get("handoff_schema_cases", 0) + report.facts.get("handoff_semantic_cases", 0))):
        m = re.search(r"^\| " + kind + r" \|[^|]*\| (\d+) \| (\d+) \|", text, re.M)
        report.check("Q09", bool(m) and int(m.group(1)) == n == int(m.group(2)), f"VALIDATION_REPORT {kind} count differs from fixtures/mutations.yaml ({n})")


def validate(root: Path, docs: bool = True, configs: dict | None = None) -> Report:
    report = Report()
    c = configs if configs is not None else load_configs(root, report)
    config_rules(c, report)
    agent_hiring_rules(root, c, report)
    pack_rules(root, c, report)
    state_machine_rules(c, report)
    if docs:
        state_machine_doc_rules(root, c, report)
    platform_rules(root, c, report, docs=docs)
    handoff_rules(root, c, report, docs=docs)
    if docs:
        doc_rules(root, c, report)
        traceability_rules(root, report, c)
        report_rules(root, report)
    return report



# ---------------------------------------------------------------- autonomous agent hire envelope (E09, Q68, P-167)

HIRE_FORBIDDEN = {"browser_automation", "dm_or_comment_replies", "organic_social", "new_integration", "new_credential", "new_egress",
                  "lead_pii_access", "hiring_agents", "approval_authority", "never_auto_actions", "budget_override", "review_verdicts",
                  "code_or_config_release"}
HIRE_DENIED = {"review.*", "media.*", "landing.open_pr", "offers.propose_pr", "amo.write_tags", "amo.write_fields", "amo.read_leads",
               "workflow.start", "experiment.*", "change_set.record_outcome"}
HIRE_CHECKS = {"requester_in_requesters", "slug_new_and_not_a_base_role", "scope_paid_meta_ads", "tools_subset_of_allowed_and_disjoint_from_denied",
               "no_forbidden_capability", "pii_fields_empty", "model_allowed", "share_fits_reserve", "reports_to_cmo", "can_hire_false"}


def agent_hiring_rules(root: Path, c: dict, report: Report):
    """E09: the Q68 envelope keeps every created agent inside the owner decisions Q68 did not change."""
    import fnmatch
    h = c.get("agent-hiring.yaml")
    report.check("E09", isinstance(h, dict), "agent-hiring.yaml (Q68 envelope) must exist")
    if not isinstance(h, dict):
        return
    env = h.get("envelope") or {}
    ap = c.get("approval-policy.yaml", {})
    role_tools = {t for a in (ap.get("agents") or {}).values() for t in a.get("tools", [])}
    tool_schemas = {p.name[: -len(".schema.json")] for p in (root / "09_Config_Templates" / "schemas" / "tools").glob("*.schema.json")}
    report.check("E09", h.get("enabled") is True and "Q68" in (h.get("decision_refs") or []), "agent-hiring.yaml: enabled with decision_refs Q68")
    report.check("E09", h.get("requesters") == ["cmo"] and env.get("reports_to") == "cmo", "agent-hiring.yaml: only the CMO requests a hire and every created agent reports to the CMO")
    report.check("E09", h.get("approval") == "none" and h.get("workflow") == "WF-E05", "agent-hiring.yaml: approval none (✅ Q68) and workflow WF-E05")
    report.check("E09", env.get("scope") == "paid_meta_ads_only", "agent-hiring.yaml: envelope.scope must stay paid_meta_ads_only (Q14)")
    report.check("E09", HIRE_FORBIDDEN <= set(env.get("forbidden_capabilities") or []),
                 f"agent-hiring.yaml: forbidden_capabilities must keep {sorted(HIRE_FORBIDDEN - set(env.get('forbidden_capabilities') or []))}")
    report.check("E09", HIRE_DENIED <= set(env.get("denied_tools") or []),
                 f"agent-hiring.yaml: denied_tools must keep {sorted(HIRE_DENIED - set(env.get('denied_tools') or []))}")
    allowed = list(env.get("allowed_tools") or [])
    bad = [t for t in allowed if t not in role_tools or any(fnmatch.fnmatch(t, d) or t == d for d in env.get("denied_tools") or [])]
    report.check("E09", bool(allowed) and not bad, f"agent-hiring.yaml: allowed_tools must be existing role tools outside denied_tools: {bad}")
    no_schema = [t for t in allowed if not t.endswith(".*") and t not in tool_schemas]
    report.check("E09", not no_schema, f"agent-hiring.yaml: allowed tools without a schemas/tools argument schema: {no_schema}")
    report.check("E09", env.get("pii_fields") == [] and env.get("can_hire") is False and env.get("trust_level_max") == "L1_approve_each",
                 "agent-hiring.yaml: pii_fields [] (Q28), can_hire false, trust_level_max L1_approve_each (Q08/Q32)")
    bud = env.get("budget") or {}
    report.check("E09", bud.get("share_source") == "reserve" and "reserve" in ((c.get("budgets.yaml", {}).get("openrouter") or {}).get("shares_minor") or {}),
                 "agent-hiring.yaml: a created agent is funded only from budgets.yaml shares_minor.reserve")
    report.check("E09", HIRE_CHECKS <= set(h.get("checks") or []) and any("agent.hire" in str(x) for x in h.get("verification") or []),
                 f"agent-hiring.yaml: checks must keep {sorted(HIRE_CHECKS - set(h.get('checks') or []))} and verification must test agent.hire with the new token")
    denied_ops = set(((c.get("runtime-isolation.yaml", {}).get("paperclip_bridge")) or {}).get("denied_ops") or [])
    report.check("E09", {"agent.hire", "agent.create"} <= denied_ops, "runtime-isolation.yaml#paperclip_bridge: agents never call agent.hire or agent.create (the platform creates)")
    bridge = (c.get("runtime-isolation.yaml", {}).get("paperclip_bridge")) or {}
    report.check("E09", not ({"agent.hire", "agent.create"} & set(bridge.get("allowed_ops") or [])),
                 "runtime-isolation.yaml#paperclip_bridge.allowed_ops must not grant agent.hire or agent.create to agents")
    pops = [o for o in bridge.get("platform_ops") or [] if isinstance(o, dict) and o.get("op") == "agent.create"]
    pc = h.get("paperclip") or {}
    report.check("E09", len(pops) == 1 and str(pops[0].get("caller", "")).startswith("gateway, only as WF-E05 S03")
                 and pc.get("create_call") == "board_create" and pc.get("require_board_approval_for_new_agents") is True and pc.get("heartbeat_enabled") is False,
                 "agent-hiring.yaml#paperclip and paperclip_bridge.platform_ops: one board create path, gateway as WF-E05 S03 only; "
                 "Paperclip requireBoardApprovalForNewAgents stays on and heartbeat off (VR-46)")
    ret = (ap.get("actions") or {}).get("agent_retire") or {}
    report.check("E09", ret.get("approvers") == ["owner"] and ret.get("max_level") == "never_auto" and ret.get("two_step") == "typed_code",
                 "approval-policy.yaml#actions.agent_retire: owner, typed code, never_auto")
    wf = (c.get("_workflows") or {}).get("WF-E05.yaml") or {}
    st = {s.get("id"): s for s in wf.get("steps") or []}
    ok_wf = (bool(st) and (st.get("S02", {}).get("executor") or {}).get("type") == "deterministic"
             and "S02" in (st.get("S03", {}).get("depends_on") or []) and "S03" in (st.get("S04", {}).get("depends_on") or [])
             and (st.get("S05", {}).get("executor") or {}).get("ref") == "ops-bot"
             and (wf.get("authorization") or {}).get("may_start") == h.get("requesters"))
    report.check("E09", ok_wf, "WF-E05: deterministic envelope check S02 before creation S03, verification S04 after it, owner notice S05 by ops-bot, may_start = requesters")

# ---------------------------------------------------------------- state machines (W12, L1-07)

SM_DOC = Path("03_Architecture") / "STATE_MACHINES.md"


def _sm_md(text) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().replace("|", "\\|")


def state_machine_rules(c: dict, report: Report):
    """W12: workflow-policy.yaml#state_machines (run, step, handoff) is closed and complete, and keeps its pinned claims."""
    pol = c.get("workflow-policy.yaml", {})
    sm = pol.get("state_machines") or {}
    report.check("W12", bool(sm) and all(k in sm for k in ("run", "step", "handoff", "allowed_actors", "pinned")),
                 "workflow-policy.yaml#state_machines needs run, step, handoff, allowed_actors and pinned")
    if not sm:
        return
    actors = set(sm.get("allowed_actors") or [])
    edges = {}
    for name in ("run", "step", "handoff"):
        m = sm.get(name) or {}
        states = list(pol.get(m.get("states_ref", ""), []) or [])
        S = set(states)
        term = set(m.get("terminal") or [])
        tr = list(m.get("transitions") or [])
        post = list(m.get("post_terminal") or [])
        report.check("W12", bool(S) and m.get("initial") in S and term and term <= S,
                     f"state_machines.{name}: states_ref, initial and terminal must name declared {m.get('states_ref')} states")
        out = {s: 0 for s in S}
        for t in tr + post:
            f, to, a, g = t.get("from"), t.get("to"), t.get("actor"), t.get("guard")
            report.check("W12", f in S and to in S, f"state_machines.{name}: {f} -> {to} uses an undeclared state")
            report.check("W12", a in actors, f"state_machines.{name}: {f} -> {to} actor {a} is not in allowed_actors (agents act only as a claimed executor)")
            report.check("W12", isinstance(g, str) and len(g.strip()) >= 10, f"state_machines.{name}: {f} -> {to} needs a guard")
            if f in out:
                out[f] += 1
            edges[f"{name}:{f}->{to}"] = t
        for t in tr:
            report.check("W12", t.get("from") not in term, f"state_machines.{name}: terminal state {t.get('from')} has an exit ({t.get('from')} -> {t.get('to')}); only post_terminal may leave a terminal state")
        for t in post:
            report.check("W12", t.get("from") in term and t.get("to") in term, f"state_machines.{name}: post_terminal {t.get('from')} -> {t.get('to')} must join two terminal states")
        for s in sorted(S - term):
            report.check("W12", out.get(s, 0) > 0, f"state_machines.{name}: non-terminal state {s} has no exit")
        seen, todo = set(), [m.get("initial")]
        while todo:
            s = todo.pop()
            if s in seen:
                continue
            seen.add(s)
            todo += [t.get("to") for t in tr + post if t.get("from") == s]
        report.check("W12", S <= seen, f"state_machines.{name}: states not reachable from {m.get('initial')}: {sorted(S - seen)}")
        for il in m.get("illegal") or []:
            hits = [t for t in tr + post if t.get("from") == il.get("from") and il.get("to") in ("*", t.get("to"))
                    and (not il.get("actor") or il.get("actor") == t.get("actor"))]
            report.check("W12", not hits and bool(il.get("why")), f"state_machines.{name}: illegal {il.get('from')} -> {il.get('to')} is present as a transition or has no reason")
    pin = sm.get("pinned") or {}
    report.check("W12", sorted((sm.get("run") or {}).get("terminal") or []) == sorted(pin.get("run_terminal") or ["?"]) == ["cancelled", "completed", "failed"],
                 "state_machines.run.terminal must stay [completed, failed, cancelled] (P-166)")
    for e in pin.get("forbidden_edges") or []:
        report.check("W12", e not in edges, f"state_machines: forbidden edge {e} is a transition (P-166)")
    for e, terms in (pin.get("guard_terms") or {}).items():
        g = str((edges.get(e) or {}).get("guard", ""))
        report.check("W12", e in edges and all(x in g for x in terms), f"state_machines: {e} guard must state {terms} (P-166)")
    for e, a in (pin.get("actor_of") or {}).items():
        report.check("W12", (edges.get(e) or {}).get("actor") == a, f"state_machines: {e} actor must be {a} (P-166)")
    need_pins = {"run:reconciling->completed", "run:reconciling->cancelled", "step:running->ready", "handoff:rejected->accepted"}
    report.check("W12", need_pins <= set(pin.get("forbidden_edges") or []), f"state_machines.pinned.forbidden_edges must keep {sorted(need_pins)}")


def render_state_machines(c: dict) -> str:
    pol, ex = c.get("workflow-policy.yaml", {}), c.get("execution-policy.yaml", {})
    ap, kc = c.get("approval-policy.yaml", {}), c.get("kill-criteria.yaml", {})
    sm = pol.get("state_machines") or {}
    L = ["# Holat mashinalari", "",
         "Bu fayl qo‘lda yozilmaydi: [validate_bundle.py](../12_Acceptance/validate_bundle.py) `--write-state-machines` uni config’lardan yaratadi, "
         "validator W12 esa jadval config’ga aynan mosligini va mashinalar yopiq hamda to‘liq ekanini tekshiradi (L1-07, ◇ P-166). "
         "Har holatning yozuvchisi `amt-workflow` ([WORKFLOW_CONTRACT §3](../11_Production_Contracts/WORKFLOW_CONTRACT.md)); «Kim» ustuni o‘tishni kim keltirib chiqarishini ko‘rsatadi. "
         "Manbalar: [workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml) `state_machines`, `command_aggregation`; "
         "[execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) `command_states`, `extra_transitions`, kill va resume; "
         "[approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) `trust_ramp`; [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml) `streak`; "
         "command o‘tishlarining to‘liq jadvali — [DATA_MODEL §6.2](DATA_MODEL.md).", ""]
    titles = {"run": "1. Run", "step": "2. Step", "handoff": "3. Handoff"}
    for name in ("run", "step", "handoff"):
        m = sm.get(name) or {}
        L += [f"## {titles[name]}", "", f"Holatlar: {', '.join('`' + s + '`' for s in pol.get(m.get('states_ref', ''), []) or [])}. "
              f"Boshlang‘ich: `{m.get('initial')}`. Yakuniy: {', '.join('`' + s + '`' for s in m.get('terminal') or [])}.", "",
              "| # | Oldingi | Keyingi | Kim | Guard |", "|---|---|---|---|---|"]
        for i, t in enumerate(list(m.get("transitions") or []) + list(m.get("post_terminal") or []), 1):
            L.append(f"| {i} | `{t.get('from')}` | `{t.get('to')}` | {t.get('actor')} | {_sm_md(t.get('guard'))} |")
        L += ["", "Taqiqlangan o‘tishlar:", "", "| Oldingi | Keyingi | Kim | Sabab |", "|---|---|---|---|"]
        for il in m.get("illegal") or []:
            L.append(f"| `{il.get('from')}` | `{il.get('to')}` | {il.get('actor') or 'har kim'} | {_sm_md(il.get('why'))} |")
        L.append("")
    L += ["## 4. Command", "", f"Holatlar: {', '.join('`' + s + '`' for s in ex.get('command_states') or [])}. "
          "Asosiy o‘tishlar, yozuvchi funksiyalar va guard’lar — [DATA_MODEL §6.2](DATA_MODEL.md); qo‘shimcha o‘tishlar `execution-policy.yaml#extra_transitions`:", ""]
    L += [f"- `{_sm_md(x)}`" for x in ex.get("extra_transitions") or []]
    ca = pol.get("command_aggregation") or {}
    L += ["", "## 5. Change-set item va step natijasi", "",
          "Change-set item — bitta command revision’i; item holati uning command holati. Bir nechta command’li step natijasi "
          "`workflow-policy.yaml#command_aggregation` qoidalari bo‘yicha (yuqoridan pastga, birinchi mos qoida):", "",
          f"Ochiq command holatlari: {', '.join('`' + s + '`' for s in ca.get('open_command_states') or [])}; yakuniy: "
          f"{', '.join('`' + s + '`' for s in ca.get('terminal_command_states') or [])}; muvaffaqiyat: {', '.join('`' + s + '`' for s in ca.get('success_states') or [])}.", "",
          "| Step roli | Qoida | Shart | Step | Run |", "|---|---|---|---|---|"]
    for role in ("approval", "dispatch", "reconciliation"):
        for r in (ca.get(role) or {}).get("rules") or []:
            L.append(f"| {role} | `{r.get('id')}` | {_sm_md(r.get('when'))} | `{r.get('step')}` | {_sm_md(r.get('run', '—'))} |")
    tr = ap.get("trust_ramp") or {}
    L += ["", "## 6. Trust Ramp (L0 / L1 / L2)", "", f"Darajalar: {', '.join('`' + s + '`' for s in tr.get('levels') or [])}; boshlang‘ich: `{tr.get('initial_level')}`.", "",
          "| # | O‘q | Sabab | Oldingi | Keyingi | Kim | Guard |", "|---|---|---|---|---|---|---|"]
    for i, t in enumerate(tr.get("transitions") or [], 1):
        L.append(f"| {i} | {t.get('axis')} | `{t.get('cause')}` | `{t.get('from')}` | `{t.get('to')}` | {t.get('actor')} | {_sm_md(t.get('guard'))} |")
    L += ["", "Taqiqlangan:", ""] + [f"- {_sm_md(x)}" for x in tr.get("illegal_transitions") or []]
    st = kc.get("streak") or {}
    _ls = lambda x: ", ".join(f"`{s}`" for s in x) if isinstance(x, list) and x else ("yo‘q (seriya qayta tiklanadi)" if isinstance(x, list) else _sm_md(x))
    L += ["", "## 7. Kill criteria seriyasi (KC-01 / KC-02)", "", f"Holatlar: {_ls(st.get('states'))}; yakuniy: {_ls(st.get('terminal'))}.", "",
          "| # | Oldingi | Keyingi | Hafta ta’siri | Kim | Guard |", "|---|---|---|---|---|---|"]
    for i, t in enumerate(st.get("transitions") or [], 1):
        L.append(f"| {i} | `{t.get('from')}` | `{t.get('to')}` | `{t.get('on_effect', '—')}` | {t.get('actor')} | {_sm_md(t.get('guard') or t.get('rule') or '—')} |")
    L += ["", "Taqiqlangan:", ""] + [f"- {_sm_md(x)}" for x in st.get("illegal") or []]
    L += ["", "## 8. Kill rejimlari va resume", "",
          f"Global rejimlar: {', '.join('`' + s + '`' for s in ex.get('global_modes') or [])}; pipeline rejimlari: {', '.join('`' + s + '`' for s in ex.get('pipeline_modes') or [])}; "
          f"standart kill rejimi: `{ex.get('kill_default_mode')}`.", "", "| Kill rejimi | Nima to‘xtaydi |", "|---|---|"]
    L += [f"| `{k}` | {_sm_md(v)} |" for k, v in (ex.get("kill_modes") or {}).items()]
    L += ["", f"Kill paytida ruxsat etiladi: {', '.join('`' + s + '`' for s in ex.get('kill_allows') or [])}; rad etiladi: {', '.join('`' + s + '`' for s in ex.get('kill_rejects') or [])}.", "",
          "| Resume qoidasi | Qiymat |", "|---|---|"]
    L += [f"| `{k}` | {_sm_md(v)} |" for k, v in (ex.get("resume") or {}).items()]
    L += ["", "| Rejim sabablari | Qoida |", "|---|---|"]
    L += [f"| `{k}` | {_sm_md(v)} |" for k, v in (ex.get("mode_causes") or {}).items()]
    return "\n".join(L) + "\n"


def state_machine_doc_rules(root: Path, c: dict, report: Report):
    p = root / SM_DOC
    report.check("W12", p.exists() and p.read_text(encoding="utf-8") == render_state_machines(c),
                 f"{SM_DOC} must equal the rendering of the configs (run validate_bundle.py --write-state-machines)")


def self_test(root: Path) -> tuple[bool, list[str]]:
    base_report = Report()
    base = load_configs(root, base_report)
    fx = yaml.safe_load((root / "12_Acceptance" / "fixtures" / "mutations.yaml").read_text(encoding="utf-8"))
    out, ok = [], True
    clean = validate(root, docs=False, configs=copy.deepcopy(base))
    if clean.errors:
        ok = False
        out.append(f"baseline config FAIL: {clean.errors[:5]}")
    for m in fx["mutations"]:
        cfg = copy.deepcopy(base)
        target = cfg["_workflows"][m["file"][len("workflows/"):]] if m["file"].startswith("workflows/") else cfg[m["file"]]
        set_path(target, m["path"], m.get("value"), m.get("op", "set"))
        for extra in m.get("also", []):   # a fixture may need a second change, in the same file or (with `file`) in another one
            tgt = target
            if extra.get("file"):
                tgt = cfg["_workflows"][extra["file"][len("workflows/"):]] if extra["file"].startswith("workflows/") else cfg[extra["file"]]
            set_path(tgt, extra["path"], extra.get("value"), extra.get("op", "set"))
        rep = validate(root, docs=False, configs=cfg)
        caught = (m["expect_rule"] in rep.failed_rules) != (m.get("expect") == "pass")
        ok &= caught
        out.append(f"{'ok ' if caught else 'MISS'} {m['id']}: {m['description']} -> {m['expect_rule']}{' still passes' if m.get('expect') == 'pass' else ''}")
    now = dt.datetime(2026, 12, 1, tzinfo=dt.timezone.utc)
    for sc in fx.get("profile_scenarios", []):
        r = copy.deepcopy(base["readiness.yaml"])
        approve = set()
        for item in sc.get("approve", []):
            if item.startswith("ALL_FOR:"):
                closure = profile_closure(r["profiles"], item.split(":", 1)[1])
                approve |= {x["key"] for x in r["requirements"] if x["gate"] in closure}
            else:
                approve.add(item)
        approve -= set(sc.get("leave_pending", []))
        for rec in r["requirements"]:
            if rec["key"] in approve:
                rec.update(status="approved", value="test-value", approved_by=sc.get("approved_by", "person:test-owner"),
                           approved_at=sc.get("approved_at", "2026-11-30T13:00:00Z"), evidence_ref="evidence:test",
                           evidence_at=sc.get("evidence_at", "2026-11-30T12:00:00Z"), evidence_prepared_by="agent:builder",
                           co_signatures=[{"role": role, "person": "person:test-cosigner", "at": "2026-11-30T14:00:00Z"} for role in rec.get("co_signers") or []])
                if rec["key"] in sc.get("null_value_for", []):
                    rec["value"] = None
                if rec["key"] in sc.get("drop_cosign_for", []):
                    rec["co_signatures"] = []
                if rec["key"] in (sc.get("values") or {}):
                    rec["value"] = sc["values"][rec["key"]]
            for na in sc.get("not_applicable", []):
                if rec["key"] == na:
                    rec.update(status="not_applicable", approved_by="person:test-owner", evidence_ref="rationale:test")
        passed, problems = evaluate_profile(r, sc["profile"], now)
        good = passed == (sc["expect"] == "pass")
        ok &= good
        out.append(f"{'ok ' if good else 'MISS'} {sc['id']}: {sc['description']} -> expect {sc['expect']}, got {'pass' if passed else 'fail'}")
    for p in probe_results(root, base):
        good = bool(p["pass"])
        ok &= good
        out.append(f"{'ok ' if good else 'MISS'} {p['id']}: {p['message']} -> {p['rule']}")
    baseline_full = validate(root) if fx.get("doc_mutations") else None
    todo = []
    for m in fx.get("doc_mutations", []):
        if m["expect_rule"] in baseline_full.failed_rules:
            ok = False
            out.append(f"MISS {m['id']}: rule {m['expect_rule']} already fails on the unmodified bundle")
            continue
        todo.append((str(root), m))
    # each doc mutation runs on its own temporary copy, so they are independent; with the fork start method they run in
    # parallel worker processes (same checks, same order of results); elsewhere sequentially
    import multiprocessing as mp
    workers = min(4, os.cpu_count() or 1)
    if workers > 1 and len(todo) > 4 and mp.get_start_method(allow_none=True) in (None, "fork") and sys.platform.startswith("linux"):
        with mp.get_context("fork").Pool(workers) as pool:
            results = pool.map(_run_doc_mutation, todo)
    else:
        results = [_run_doc_mutation(t) for t in todo]
    for (m, found, caught) in results:
        ok &= caught
        out.append(f"{'ok ' if caught else 'MISS'} {m['id']}: {m['description']} -> {m['expect_rule']}" + ("" if found else " (find text not present)"))
    return ok, out


def _run_doc_mutation(task):
    root, m = Path(task[0]), task[1]
    with tempfile.TemporaryDirectory() as tmp:
        copy_root = Path(tmp) / "bundle"
        shutil.copytree(root, copy_root, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        target = copy_root / m["file"]
        text = target.read_text(encoding="utf-8")
        found = m["find"] in text
        target.write_text(text.replace(m["find"], m["replace"], 1), encoding="utf-8")
        rep = validate(copy_root)
        return m, found, found and m["expect_rule"] in rep.failed_rules


# ---------------------------------------------------------------- platform, integration and cost rules (family G)

CAPI_STATES = {"queued", "sending", "sent", "retry_wait", "uncertain", "needs_review", "rejected", "dropped_uncertain", "skipped_no_consent",
               "skipped_too_old", "skipped_test", "skipped_unknown_prior_send"}
CAPI_TERMINAL = {"sent", "rejected", "dropped_uncertain", "skipped_no_consent", "skipped_too_old", "skipped_test", "skipped_unknown_prior_send"}
CAPI_RESULT_STATES = {"accepted": "sent", "retryable_error": "retry_wait", "connect_error": "retry_wait", "no_response": "uncertain",
                      "unclassified_error": "uncertain", "batch_rejected": "uncertain", "permanent_error": "needs_review",
                      "config_error": "retry_wait", "auth_error": "retry_wait"}   # REVIEW_B12 #1/#2: no resend of a possibly stored event
PII_FIELD_NAMES = {"name", "phone", "ph", "email", "em", "client_ip_address", "client_user_agent", "ip", "user_agent", "fbc", "fbp",
                   "payload", "ciphertext", "address", "comment"}
MONEY_NAME_RE = re.compile(r"(?:budget|amount|price|cost|spend|money)|_(?:usd|uzs|eur)$", re.I)
RAW_SQL_KEYS = {"sql", "raw_sql", "query_sql", "statement", "where", "where_clause", "clause", "filter_sql", "sql_where", "order_sql", "having", "raw_query"}
RENDER_PARAM_PATTERN = "^[A-Za-z0-9\\u00C0-\\u024F\\u0400-\\u04FF \\u2018\\u2019\\u201C\\u201D\\u00AB\\u00BB'\".,;!?()+%&*#=_\\u2013\\u2014-]*$"
PII_TOKENS = {"phone", "tel", "msisdn", "name", "email", "mail", "ip", "ua", "useragent", "fbc", "fbp", "payload", "cipher", "ciphertext",
              "address", "comment", "birth", "dob", "passport", "contact", "firstname", "lastname", "surname"}
SDK_RETRIED_HTTP = {"408", "409", "429"}   # with every 5xx: statuses agent clients resend on their own (VR-41)
LLM_UPSTREAM_MAP = {   # budgets.yaml#openrouter.upstream_contract.result_codes (VR-42, P-97): every upstream outcome -> its no-retry proxy code
    "http_408": "upstream_unavailable", "http_429": "upstream_unavailable", "http_5xx": "upstream_unavailable",
    "connect_error": "upstream_unavailable", "no_response_before_deadline": "upstream_unavailable",
    "http_200_error_body": "upstream_unavailable", "sse_error_event": "upstream_unavailable",
    "http_402": "allowance_exhausted", "http_403_limit_source": "allowance_exhausted",
    "http_403_guardrail_or_moderation": "upstream_refused", "http_4xx_other": "upstream_refused"}
RETRY_CLAIM_RE = re.compile(r"\b\d+\s*marta\b|\bqayta\s+(?:urinadi|yuboradi|uriniladi)\b")   # a §10.1 Retry cell that says the proxy resends


def pii_field(field: str) -> bool:
    """A field name that looks like lead PII (token match, so 'pipeline' is not 'ip'): phone_e164, client_ip, customer_name, user_data ..."""
    f = field.lower()
    toks = set(re.split(r"[^a-z0-9]+", f)) | {f.replace("_", "")}
    return bool(toks & PII_TOKENS) or "user_data" in f or "user_agent" in f or f in PII_FIELD_NAMES


ALERT_CODE_RE = re.compile(r"(?<![A-Z0-9_])((?:ALERT|REMINDER)_[A-Z0-9_]*[A-Z0-9])")


EGRESS_DESTINATIONS = [("graph.facebook.com", "meta"), ("amocrm.ru", "amocrm"), ("openrouter", "openrouter"), ("github", "github"),
                       ("google drive", "google drive"), ("umami", "umami"), ("clarity", "clarity"), ("telegram", "telegram"),
                       ("cloudflare", "cloudflare"), ("tailscale", "tailscale"), ("independent monitor", "monitor"),
                       ("package proxy", "package"), ("engineering llm", "engineering llm"), ("go.wolter.uz", "go.wolter.uz")]


def egress_destinations(egress: str) -> list[tuple[str, str]]:
    """Closed list of off-host destinations named in a registry egress string; items marked (local) are local services, not destinations."""
    items, depth, cur = [], 0, ""
    for ch in egress:
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    text = " ".join(i for i in items if "(local)" not in i).lower()
    return [(k, v) for k, v in EGRESS_DESTINATIONS if k in text]


def flow_mapping_fragments(line: str) -> list[str]:
    """Top-level segments of one-line YAML flow mappings that are not 'key: value' (outside quotes and comments)."""
    out, i, n = [], 0, len(line)
    quote = None
    while i < n:
        ch = line[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        elif ch == "{" and (line[:i].rstrip() == "" or line[:i].rstrip()[-1] in ":-[,"):   # a flow mapping starts a value, not prose
            depth, j, seg, segs, q2 = 1, i + 1, "", [], None
            while j < n and depth:
                cj = line[j]
                if q2:
                    if cj == q2:
                        q2 = None
                    seg += cj
                elif cj in "'\"":
                    q2 = cj
                    seg += cj
                elif cj in "{[":
                    depth += 1
                    seg += cj
                elif cj in "}]":
                    depth -= 1
                    if depth:
                        seg += cj
                elif cj == "," and depth == 1:
                    segs.append(seg)
                    seg = ""
                else:
                    seg += cj
                j += 1
            if depth == 0:
                segs.append(seg)
                out += [s.strip() for s in segs if s.strip() and not re.match(r"^[^:]+:(\s|$)", s.strip())]
            i = j
            continue
        i += 1
    return out


def alert_catalog(root: Path) -> list[str]:
    """Codes defined in the canonical alert catalog (TELEGRAM.md §6.2), in table order."""
    tg = root / "03_Architecture" / "TELEGRAM.md"
    if not tg.exists():
        return []
    sec = tg.read_text(encoding="utf-8").split("### 6.2", 1)[-1].split("\n### ", 1)[0]
    return re.findall(r"^\|\s*`((?:ALERT|REMINDER)_[A-Z0-9_]+)`\s*\|", sec, re.M)


def alert_catalog_rows(root: Path) -> dict:
    """TELEGRAM.md §6.2 rows: code -> cells (Kod, Trigger, Severity, Qabul qiluvchi, ACK ref, Tugmalar, INCIDENTS)."""
    tg = root / "03_Architecture" / "TELEGRAM.md"
    if not tg.exists():
        return {}
    sec = tg.read_text(encoding="utf-8").split("### 6.2", 1)[-1].split("\n### ", 1)[0]
    rows = {}
    for line in sec.splitlines():
        m = re.match(r"^\|\s*`((?:ALERT|REMINDER)_[A-Z0-9_]+)`\s*\|", line)
        if m:
            rows[m.group(1)] = [x.strip() for x in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
    return rows


def incident_ids(root: Path) -> set[str]:
    inc = root / "06_Runbooks" / "INCIDENTS.md"
    return set(re.findall(r"^\|\s*\**(INC-\d{2})\b", inc.read_text(encoding="utf-8"), re.M)) if inc.exists() else set()


def _dur_g(v, default=dt.timedelta(days=9999)):
    """ISO duration or a huge default (so a missing or malformed bound fails an upper-bound check)."""
    try:
        return iso_duration(str(v))
    except ValueError:
        return default


def get_path_safe(obj, path: str):
    try:
        return get_path(obj, path)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def platform_rules(root: Path, c: dict, report: Report, docs: bool = True):
    """Family G: platform, integration and cost contracts (host-side detection of silent integration failures)."""
    catalog = alert_catalog(root)
    codes = set(catalog)
    services = {str(sv.get("service_id")) for sv in (c.get("runtime-isolation.yaml", {}).get("services") or [])}
    incidents = incident_ids(root)
    ops = c.get("operations.yaml", {})
    # G01 the alert catalog is closed and well formed (TELEGRAM.md §6.2; REVIEW_B12 #8): every ALERT_/REMINDER_ code used anywhere in the
    # bundle is defined once; every row has 7 cells, a severity from operations.yaml#severities only, recipients, and defined runbooks
    cat_rows = alert_catalog_rows(root)
    sev_names = set((ops.get("severities") or {}).keys())
    if docs:
        dup = sorted({x for x in catalog if catalog.count(x) > 1})
        report.check("G01", bool(catalog) and not dup, f"TELEGRAM.md §6.2 alert catalog is empty or defines codes twice: {dup}")
        bad_rows = []
        for code, cells in cat_rows.items():
            sev_words = set(re.findall(r"\b(critical|degraded|info|warning|warn|notice|low|medium|high|minor|major)\b", cells[2] if len(cells) > 2 else ""))
            inc_cell = cells[6] if len(cells) > 6 else ""
            inc_refs = set(re.findall(r"INC-\d{2}", inc_cell))
            if len(cells) != 7 or not sev_words or not sev_words <= sev_names or not cells[3] or not (inc_cell == "—" or (inc_refs and inc_refs <= incidents)):
                bad_rows.append(code)
        report.check("G01", not bad_rows, f"TELEGRAM.md §6.2 rows need 7 cells, a severity from operations.yaml#severities only {sorted(sev_names)}, recipients and defined INCIDENTS refs: {bad_rows[:10]}")
        skip = {Path("12_Acceptance") / "VALIDATION_REPORT.md", Path("12_Acceptance") / "validate_bundle.py"}
        undefined = {}
        for f in sorted(root.rglob("*")):
            rel_f = f.relative_to(root)
            if not f.is_file() or f.suffix not in (".md", ".yaml", ".json", ".hujson", ".example") or rel_f in skip or rel_f.parts[:2] == ("12_Acceptance", "fixtures"):
                continue
            for m in ALERT_CODE_RE.finditer(f.read_text(encoding="utf-8")):
                if m.group(1) not in codes:
                    undefined.setdefault(m.group(1), str(rel_f))
        report.check("G01", not undefined, "alert codes used but not defined in TELEGRAM.md §6.2: " + ", ".join(f"{k} ({v})" for k, v in sorted(undefined.items())[:20]))
    # G02 a dead or unreachable monitor is reported by the host (operations.yaml#host_loss.monitor_unreachable_alert; P-70, REVIEW_B12
    # #8/#15/#19): after the lease of the heartbeat interval in force plus a margin and before the capi_terminal_before lag alert, raised
    # by the heartbeat sender over ops-bot as a critical alert that reaches the monitor's accountable person, with re-alert and hysteresis
    hl = ops.get("host_loss") or {}
    mua = hl.get("monitor_unreachable_alert")
    reg = c.get("runtime-isolation.yaml", {}).get("services") or []
    monitor_senders = [str(sv.get("service_id")) for sv in reg if "independent monitor" in str(sv.get("egress", "")).lower()]
    mon_dep = next((d for d in (c.get("runtime-isolation.yaml", {}).get("external_dependencies") or []) if isinstance(d, dict) and d.get("kind") == "off_host_monitor"), {})
    ok, msg = isinstance(mua, dict), "operations.yaml#host_loss.monitor_unreachable_alert is required (the CAPI dispatch lease stops dispatch while the monitor is unreachable)"
    if ok:
        try:
            margin, lease = iso_duration(str(mua.get("after_margin"))), 2 * iso_duration(str(hl.get("heartbeat_interval")))
            lag_m = re.search(r"\bP(?:\d+D)?T(?:\d+H)?(?:\d+M)?(?:\d+S)?\b", str(hl.get("capi_terminal_before_lag_alert", "")))
            lag = iso_duration(lag_m.group(0)) if lag_m else None
            ok = mua.get("after") == "lease_plus_margin" and dt.timedelta(0) < margin <= dt.timedelta(minutes=5) and lag is not None and lease + margin < lag
            msg = f"monitor_unreachable_alert.after must be lease_plus_margin with 0 < after_margin <= PT5M and lease + margin below the capi_terminal_before lag alert {lag}: {mua.get('after')}, {mua.get('after_margin')}"
        except ValueError as exc:
            ok, msg = False, f"monitor_unreachable_alert timing is not ISO 8601: {exc}"
    report.check("G02", ok, msg)
    if isinstance(mua, dict):
        row = cat_rows.get(str(mua.get("alert")), [])
        try:
            ok_h = iso_duration(str(mua.get("re_alert_every"))) <= dt.timedelta(hours=1) and 1 <= int(mua.get("clears_after_acks")) <= 10
        except (TypeError, ValueError):
            ok_h = False
        report.check("G02", len(monitor_senders) == 1 and mua.get("raised_by") == monitor_senders[0] and mua.get("channel") == "ops-bot"
                     and mua.get("alert") in codes and mua.get("runbook") in incidents and ok_h and bool(mua.get("silent_double_fault"))
                     and len(row) > 3 and row[2] == "critical" and str(mon_dep.get("accountable", "")) in row[3],
                     f"monitor_unreachable_alert must be raised by the heartbeat sender {monitor_senders} over ops-bot as a catalogued critical alert that reaches {mon_dep.get('accountable')}, "
                     f"with a runbook, re_alert_every <= PT1H, clears_after_acks 1-10 and the silent double fault stated: {mua.get('raised_by')}, {mua.get('channel')}, {row[2:4] if len(row) > 3 else row}")
    # G03 external dependencies (runtime-isolation.yaml#external_dependencies): an accountable human, env-declared credentials and,
    # per kind, the contract AMT relies on (off-host monitor: store before ACK, authenticated ACK echo, >= 8 days, independent hosting)
    deps = c.get("runtime-isolation.yaml", {}).get("external_dependencies")
    env_names = set(re.findall(r"^([A-Z0-9_]+)=", str(c.get("_env", "")), re.M))
    roles_cfg = c.get("roles.yaml", {})
    people_roles = set(roles_cfg.get("roles") or []) | set((roles_cfg.get("responsibility_assignments") or {}).keys())
    rkeys = {r.get("key") for r in (c.get("readiness.yaml", {}).get("requirements") or [])}
    deps = deps if isinstance(deps, list) else []
    report.check("G03", any(isinstance(d, dict) and d.get("kind") == "off_host_monitor" for d in deps),
                 "runtime-isolation.yaml#external_dependencies must declare the off-host monitor that the CAPI dispatch lease and host-loss rule 1 depend on")
    seen_dep = set()
    for d in deps:
        d = d if isinstance(d, dict) else {}
        did, creds = d.get("id"), d.get("credentials") or []
        report.check("G03", did and did not in seen_dep, f"external dependency {did} is unnamed or declared twice")
        seen_dep.add(did)
        report.check("G03", d.get("operator") == "owner" and d.get("accountable") in people_roles and d.get("readiness_ref") in rkeys,
                     f"external dependency {did}: operator must be the owner, accountable a role or responsibility, readiness_ref a readiness key")
        report.check("G03", bool(creds) and set(creds) <= env_names and (d.get("endpoint_env") is None or d.get("endpoint_env") in env_names),
                     f"external dependency {did}: credentials and endpoint must be env.example names: {sorted(set(creds) - env_names)}")
        kind = d.get("kind")
        if kind == "off_host_monitor":
            ct = d.get("contract") or {}
            try:
                retention = int(ct.get("retention_days_min") or 0)
            except (TypeError, ValueError):
                retention = 0
            ref = str(ct.get("host_side_detection_ref", ""))
            ok_ref = ref.startswith("operations.yaml#") and isinstance(get_path_safe(c.get("operations.yaml", {}), ref.split("#", 1)[1]), dict)
            report.check("G03", ct.get("store_before_ack") is True and ct.get("ack_auth") == "hmac_sha256" and {"observed_at", "nonce"} <= set(ct.get("ack_echo") or [])
                         and retention >= 8 and {"not_amt_pc", "not_production_dokploy_landing_host"} <= set(d.get("hosting_constraints") or []) and ok_ref
                         and ref == "operations.yaml#host_loss.monitor_unreachable_alert",
                         f"external dependency {did}: the monitor contract needs store_before_ack, an HMAC-SHA256 observed_at+nonce ACK echo, >= 8 days retention, hosting off the AMT PC and the production landing host, "
                         f"and host_side_detection_ref = operations.yaml#host_loss.monitor_unreachable_alert ({ref})")
            report.check("G03", "INDEPENDENT_MONITOR_ACK_KEY" in creds and ct.get("ack_key_rotation") == "dual_key_window" and "INDEPENDENT_MONITOR_ACK_KEY_NEXT" in creds
                         and ct.get("heartbeat_auth") in creds,
                         f"external dependency {did}: the ACK key must be a listed credential with a dual-key rotation window (INDEPENDENT_MONITOR_ACK_KEY_NEXT) and the heartbeat authenticated by a listed credential (REVIEW_B12 #7/#18)")
        elif kind == "cross_host_read":
            reader = d.get("reader")
            egress = next((str(sv.get("egress", "")) for sv in (c.get("runtime-isolation.yaml", {}).get("services") or []) if sv.get("service_id") == reader), "")
            pii_hit = sorted(f for f in (d.get("fields") or []) if pii_field(str(f)))
            hd = d.get("hardening") if isinstance(d.get("hardening"), dict) else {}
            try:
                ok_hd = 1 <= int(hd.get("page_size_max")) <= 1000 and int(hd.get("response_bytes_max")) > 0
            except (TypeError, ValueError):
                ok_hd = False
            report.check("G03", reader in services and bool(d.get("host")) and str(d.get("host")) in egress and d.get("pii") is False and bool(d.get("fields")) and not pii_hit
                         and str(d.get("endpoint", "")).startswith("GET ") and bool(d.get("cursor")),
                         f"external dependency {did}: a cross-host read needs a registry reader whose egress names {d.get('host')}, a GET endpoint ({d.get('endpoint')}), a cursor and a PII-free field list (PII-like fields: {pii_hit})")
            report.check("G03", ok_hd and bool(hd.get("rate_limit_per_token")) and hd.get("token_compare") == "constant_time_hash" and bool(hd.get("edge_rule")) and bool(d.get("conflict_ref")),
                         f"external dependency {did}: the read endpoint needs bounded pages (1-1000) and response bytes, a per-token rate limit, a constant-time token-hash compare, an edge rule and its OPEN_ITEMS conflict ref (REVIEW_B12 #5/#17)")
        else:
            report.check("G03", False, f"external dependency {did}: unknown kind {kind}")
    # G04 integration watch (operations.yaml#integration_watch) and the amoCRM webhook delivery contract (#amo_webhook_contract, VR-36;
    # P-72, P-74, P-75, REVIEW_B12 #3/#7/#15/#16/#17): every watch runs only in registry services that hold a DB role (they write the
    # durable alert), raises a catalogued alert that reaches technical_operator, and keeps the values its P-row claims as upper bounds
    watch = ops.get("integration_watch")
    watch = watch if isinstance(watch, list) else []
    sevs = set((ops.get("severities") or {}).keys())
    db_role = {str(sv.get("service_id")): str(sv.get("db_role", "none")) for sv in reg}
    by_id = {w.get("id"): w for w in watch if isinstance(w, dict)}
    report.check("G04", {"amo_webhook_liveness", "meta_token_health", "landing_delivery_pull", "amo_token_visibility"} <= set(by_id) and len(by_id) == len(watch),
                 f"operations.yaml#integration_watch must hold unique amo_webhook_liveness, meta_token_health, landing_delivery_pull and amo_token_visibility watches: {sorted(by_id)}")
    atv = by_id.get("amo_token_visibility") or {}
    report.check("G04", (atv.get("runs_in") or []) == ["sync-worker"] and atv.get("alert") == "ALERT_AMO_VISIBILITY_GAP"
                 and _dur_g(atv.get("visibility_grace")) <= dt.timedelta(hours=1) and _dur_g(atv.get("critical_after")) <= dt.timedelta(hours=4),
                 "integration_watch[amo_token_visibility] (REVIEW_B12 #4): sync-worker checks within visibility_grace <= PT1H that every crm_confirmed landing lead is readable through AMO_TOKEN, "
                 "ALERT_AMO_VISIBILITY_GAP, critical_after <= PT4H")

    def _dur(v, default=None):
        try:
            return iso_duration(str(v))
        except ValueError:
            return default

    for wid, w in by_id.items():
        runs = w.get("runs_in") or []
        row = cat_rows.get(str(w.get("alert")), [])
        ok_crit = w.get("critical_after") is None or _dur(w.get("critical_after")) is not None
        report.check("G04", bool(runs) and set(runs) <= services and all(db_role.get(s, "none") != "none" for s in runs) and w.get("alert") in codes
                     and w.get("severity") in sevs and w.get("runbook") in incidents and ok_crit and len(row) > 3 and "technical_operator" in row[3],
                     f"integration_watch {wid}: runs only in registry services with a DB role {[(s, db_role.get(s)) for s in runs]}, raises a catalogued alert {w.get('alert')} that reaches technical_operator, "
                     f"with a severity in operations.yaml#severities, a defined runbook {w.get('runbook')} and an ISO critical_after")
        toks, degr, via = w.get("tokens") or {}, w.get("degrades") or {}, w.get("probe_via") or {}
        report.check("G04", set(toks) <= set(runs) and set(degr) <= set(runs) and set(toks.values()) <= env_names and set(via) <= set(runs) and set(via.values()) <= services,
                     f"integration_watch {wid}: tokens, degraded capabilities and probe_via must belong to listed services and name env.example tokens and registry services: {toks}, {via}")
    mth = by_id.get("meta_token_health") or {}
    report.check("G04", (mth.get("tokens") or {}) == {"executor": "META_WRITE_TOKEN", "capi-bridge": "META_CAPI_TOKEN", "sync-worker": "META_READ_TOKEN"}
                 and (mth.get("probe_via") or {}) == {"sync-worker": "meta-ads-mcp"} and _dur(mth.get("every"), dt.timedelta(days=999)) <= dt.timedelta(minutes=15)
                 and mth.get("severity") == "critical" and mth.get("alert") == "ALERT_META_TOKEN_INVALID",
                 "integration_watch[meta_token_health] must probe the write token in executor, the CAPI token in capi-bridge and the read token from sync-worker through meta-ads-mcp, at least every PT15M, as a critical ALERT_META_TOKEN_INVALID")
    awl = by_id.get("amo_webhook_liveness") or {}
    sub = awl.get("subscription_read") if isinstance(awl.get("subscription_read"), dict) else {}
    try:
        ok_awl = _dur(awl.get("window"), dt.timedelta(days=999)) <= dt.timedelta(hours=1) and 1 <= int(awl.get("min_events")) <= 3 \
            and _dur(awl.get("window"), dt.timedelta(days=999)) <= _dur(awl.get("critical_after"), dt.timedelta(0)) <= dt.timedelta(hours=4)
    except (TypeError, ValueError):
        ok_awl = False
    report.check("G04", ok_awl and awl.get("alert") == "ALERT_WEBHOOK_SILENT" and _dur(sub.get("every"), dt.timedelta(days=999)) <= dt.timedelta(days=1)
                 and sub.get("on_failure") in codes and awl.get("on_sync_auth_error") in codes,
                 "integration_watch[amo_webhook_liveness]: window <= PT1H, 1 <= min_events <= 3, window <= critical_after <= PT4H (the P-72 values are upper bounds), ALERT_WEBHOOK_SILENT, "
                 "a daily subscription read with a catalogued failure alert, and a catalogued alert for a sync auth error (a revoked token makes the sync find nothing)")
    ldp = by_id.get("landing_delivery_pull") or {}
    reader = next((d.get("reader") for d in (c.get("runtime-isolation.yaml", {}).get("external_dependencies") or []) if isinstance(d, dict) and d.get("kind") == "cross_host_read"), None)
    try:
        ok_ldp = 1 <= int(ldp.get("consecutive_failures")) <= 5 and _dur(ldp.get("critical_after"), dt.timedelta(days=999)) <= dt.timedelta(hours=1)
    except (TypeError, ValueError):
        ok_ldp = False
    report.check("G04", ok_ldp and (ldp.get("runs_in") or []) == [reader],
                 f"integration_watch[landing_delivery_pull]: 1 <= consecutive_failures <= 5, critical_after <= PT1H, and it runs in the delivery reader {reader}")
    awc = ops.get("amo_webhook_contract") if isinstance(ops.get("amo_webhook_contract"), dict) else {}
    ocf = awc.get("on_commit_failure") if isinstance(awc.get("on_commit_failure"), dict) else {}
    try:
        ok_awc = int(awc.get("vendor_reply_timeout_ms")) == 2000 and 0 < int(awc.get("reply_budget_ms")) < 2000 and 500 <= int(ocf.get("reply_status")) <= 599
    except (TypeError, ValueError):
        ok_awc = False
    report.check("G04", ok_awc and awc.get("reply_budget_measured") == "end_to_end_external" and ocf.get("never_reply_2xx_before_commit") is True and ocf.get("never_time_out") is True
                 and [str(x) for x in (awc.get("vendor_retry_after") or [])] == ["PT5M", "PT15M", "PT15M", "PT1H"] and (awc.get("subscribed_events") or []) == ["add_lead", "status_lead"]
                 and bool(awc.get("retry_tradeoff")) and bool(awc.get("challenge_free_path")),
                 "operations.yaml#amo_webhook_contract: the VR-36 vendor values (2000 ms timeout, retries PT5M/PT15M/PT15M/PT1H), a reply budget below 2000 ms measured end to end, a 5xx reply on commit failure "
                 "(never 2xx before the commit, never a timeout), exactly add_lead and status_lead, and the stated retry trade-off")
    # G05 CAPI delivery (pipelines.yaml#capi_delivery, TRACKING_CAPI.md §5.3, DATA_MODEL.md §3.4; L3-07, L3-13, REVIEW_B12 #1/#2/#7/#10/#12):
    # nothing that may already be stored is resent - one event per request until F2 dedup evidence, a fixed result -> state map,
    # request-level faults hold instead of rejecting, a Graph-response map whose resending rows are verified in F2, a breaker,
    # no TLS early data or client retry, and the docs and vendor facts say the same
    cdel = c.get("pipelines.yaml", {}).get("capi_delivery")
    cdel = cdel if isinstance(cdel, dict) else {}
    st, term, rt = set(cdel.get("states") or []), set(cdel.get("terminal") or []), cdel.get("result_transitions") or {}
    report.check("G05", st == CAPI_STATES and term == CAPI_TERMINAL and rt == CAPI_RESULT_STATES,
                 f"pipelines.yaml#capi_delivery: states, terminal states and result_transitions must equal the canonical map (no resend of a possibly stored event, holds for auth/config faults): "
                 f"{sorted((k, rt.get(k), v) for k, v in CAPI_RESULT_STATES.items() if rt.get(k) != v) + sorted((k, rt[k], None) for k in set(rt) - set(CAPI_RESULT_STATES))}")
    report.check("G05", cdel.get("batch_policy") == "realtime_single" and cdel.get("batch_max_events") == 1 and "dedup_evidence_ref" in cdel
                 and cdel.get("permanent_error_requires_single_event") is True,
                 "pipelines.yaml#capi_delivery: batch_policy must stay realtime_single with batch_max_events 1 until F2 dedup evidence and an owner decision (VR-33, VR-37)")
    report.check("G05", set(cdel.get("counted_results") or []) == {"retryable_error", "connect_error"} and set(cdel.get("uncounted_results") or []) == {"auth_error", "config_error"},
                 "pipelines.yaml#capi_delivery: only retryable_error and connect_error spend attempts; auth_error and config_error are uncounted holds")
    vem = cdel.get("vendor_error_map") if isinstance(cdel.get("vendor_error_map"), list) else []
    resending = {k for k, v in CAPI_RESULT_STATES.items() if v in ("retry_wait", "needs_review")}
    vem_res = [r.get("result") for r in vem if isinstance(r, dict)]
    unverified = [r.get("result") for r in vem if isinstance(r, dict) and r.get("result") in resending
                  and not (r.get("basis") and str(r.get("verify_in", "")).startswith("F2-AT-25"))]
    report.check("G05", bool(vem) and set(vem_res) <= set(CAPI_RESULT_STATES) and (set(CAPI_RESULT_STATES) - {"batch_rejected"}) <= set(vem_res)
                 and all(isinstance(r, dict) and r.get("match") for r in vem) and not unverified and cdel.get("unmatched_result") == "unclassified_error",
                 f"pipelines.yaml#capi_delivery.vendor_error_map must classify every result, each resending row needs a basis and an F2-AT-25 case {unverified}, and an unmatched response is unclassified_error")
    br = cdel.get("permanent_error_breaker") if isinstance(cdel.get("permanent_error_breaker"), dict) else {}
    try:
        ok_br = 2 <= int(br.get("consecutive")) <= 10 and bool(iso_duration(str(br.get("cooldown"))))
    except (TypeError, ValueError):
        ok_br = False
    report.check("G05", ok_br and br.get("same_error_code") is True and br.get("on_trip") == "hold_queue" and br.get("alert") == "ALERT_CAPI_FAILED",
                 "pipelines.yaml#capi_delivery.permanent_error_breaker must hold the queue after 2-10 consecutive same-code permanent errors, with an ISO cooldown and ALERT_CAPI_FAILED")
    nre = cdel.get("needs_review_exits") if isinstance(cdel.get("needs_review_exits"), dict) else {}
    tr_ = cdel.get("transport") if isinstance(cdel.get("transport"), dict) else {}
    report.check("G05", nre.get("reject") == "rejected" and nre.get("requeue") == "queued" and {"no_response", "unclassified_error", "batch_rejected"} <= set(nre.get("requeue_forbidden_after") or [])
                 and tr_.get("tls_early_data") is False and tr_.get("client_auto_retry") is False,
                 "pipelines.yaml#capi_delivery: needs_review exits to rejected or queued, never requeues an event that may be stored, and the transport has no TLS early data and no client retry")
    ur = cdel.get("uncertain_resolution") if isinstance(cdel.get("uncertain_resolution"), dict) else {}
    cer = ((c.get("tracking-health.yaml", {}).get("checks") or {}).get("capi_error_rate") or {}).get("counts") or {}
    report.check("G05", cdel.get("age_check") == "at_batch_build" and cdel.get("send_age_margin_ref") == "vendor.meta_capi.send_age_margin"
                 and ur.get("on_evidence") == "sent" and ur.get("on_hold_expiry") == "dropped_uncertain" and ur.get("never_resend") is True
                 and ur.get("hold_ref") == "vendor.meta_capi.uncertain_hold" and ur.get("soft_deadline_ref") == "vendor.meta_capi.request_timeout" and bool(ur.get("evidence"))
                 and {"capi_error_rate", "reconciliation_report"} <= set(ur.get("counted_in") or []) and cdel.get("after_no_response") == "single_event_requests_until_one_accepted"
                 and {"rejected", "dropped_uncertain"} <= set(cer.get("final") or []) and {"uncertain", "needs_review"} <= set(cer.get("unresolved") or []),
                 "pipelines.yaml#capi_delivery: age checked at batch build with vendor.meta_capi.send_age_margin; an uncertain attempt ends sent (own late response) or dropped_uncertain at the "
                 "vendor.meta_capi.uncertain_hold hard deadline after the request_timeout soft deadline, never resent and counted; after_no_response keeps single-event requests; capi_error_rate counts the loss")
    if docs:
        capi_doc = root / "03_Architecture" / "TRACKING_CAPI.md"
        sec53 = capi_doc.read_text(encoding="utf-8").split("### 5.3", 1)[-1].split("\n### ", 1)[0] if capi_doc.exists() else ""
        m_res = re.search(r"`capi_attempts\.result`:\s*`([^`]+)`", sec53)
        doc_res = {x.strip() for x in m_res.group(1).split("|")} if m_res else set()
        doc_states = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|", sec53, re.M))
        dm = root / "03_Architecture" / "DATA_MODEL.md"
        m_dm = re.search(r"`result` \(([^)]*?) — `pipelines\.yaml#capi_delivery`\)", dm.read_text(encoding="utf-8")) if dm.exists() else None
        dm_res = set(re.findall(r"`([a-z_]+)`", m_dm.group(1))) if m_dm else set()
        report.check("G05", doc_res == set(rt) and doc_states == st and dm_res == set(rt),
                     f"TRACKING_CAPI §5.3 / DATA_MODEL §3.4 enums differ from pipelines.yaml#capi_delivery: results {sorted(doc_res ^ set(rt))}, states {sorted(doc_states ^ st)}, DATA_MODEL {sorted(dm_res ^ set(rt))}")
        rf = (root / "10_Reference" / "RESEARCH_FACTS.md").read_text(encoding="utf-8")
        vr37 = next((l for l in rf.splitlines() if l.startswith("| VR-37 |")), "")
        vr33 = next((l for l in rf.splitlines() if l.startswith("| VR-33 |")), "")
        report.check("G05", "still accepted" in vr37 and "realtime_single" in vr37 and "fbp / external_id" in vr33,
                     "RESEARCH_FACTS VR-37 must record that valid events of an erroring batch are still accepted (and the realtime_single consequence); VR-33 must scope the single-source sentence to the fbp / external_id method")

    # G06 off-host flow inventory (privacy-policy.yaml#off_host_flows, P-33, P-76; REVIEW_B12 #5/#8): every row is a closed record that
    # names who performs it and how data moves; every off-host destination in a service's registry egress (a closed destination list)
    # is covered by a row that service performs, a local-only service has no off-host destination, and a row that exposes lead custom
    # fields or was added after P-33 points at a defined OPEN_ITEMS §4 conflict
    pp = c.get("privacy-policy.yaml", {})
    flows = pp.get("off_host_flows") if isinstance(pp.get("off_host_flows"), list) else []
    local_only = set(pp.get("local_only_egress") or [])
    allowed_keys, required_keys = {"flow", "to", "direction", "by", "data", "condition", "open_item", "conflict_ref"}, {"flow", "to", "direction", "by", "data"}
    oi_ids, c_ids = set(), set()
    if docs and (root / "00_Decisions" / "OPEN_ITEMS.md").exists():
        oi_text = (root / "00_Decisions" / "OPEN_ITEMS.md").read_text(encoding="utf-8")
        oi_ids = set(re.findall(r"^\|\s*(OI-\d+)\s*\|", oi_text, re.M))
        c_ids = set(re.findall(r"^\|\s*(C-\d+)\s*\|", oi_text, re.M))
    report.check("G06", bool(flows), "privacy-policy.yaml#off_host_flows is empty or not a list")
    covered, flow_names = set(), set()
    for r in flows:
        r = r if isinstance(r, dict) else {"flow": repr(r)}
        by = r.get("by") if isinstance(r.get("by"), list) else []
        empty = sorted(str(k) for k, v in r.items() if v is None or v == "" or v == [])
        unknown_by = sorted(set(by) - services - {"builder", "owner", "unassigned"})
        report.check("G06", set(r) <= allowed_keys and required_keys <= set(r) and not empty and r.get("direction") in ("send", "read", "transport")
                     and bool(by) and not unknown_by and r.get("flow") not in flow_names,
                     f"off_host_flows row {r.get('flow')!r}: keys outside {sorted(allowed_keys)} {sorted(str(k) for k in set(r) - allowed_keys)} (an unquoted comma in a flow mapping makes such a key), "
                     f"missing {sorted(required_keys - set(r))}, empty {empty}, direction {r.get('direction')!r} (send|read|transport), by {unknown_by} not a registry service or builder/owner, or a repeated flow name")
        flow_names.add(r.get("flow"))
        if "unassigned" in by:
            report.check("G06", by == ["unassigned"] and bool(r.get("open_item")) and (not docs or r.get("open_item") in oi_ids),
                         f"off_host_flows row {r.get('flow')!r}: an unassigned performer needs open_item naming an OI defined in OPEN_ITEMS.md (got {r.get('open_item')!r})")
        if re.search(r"amt_client_ip|amt_client_ua|amt_fbc|amt_fbp", str(r.get("data", ""))) or r.get("conflict_ref"):
            report.check("G06", bool(r.get("conflict_ref")) and (not docs or r.get("conflict_ref") in c_ids),
                         f"off_host_flows row {r.get('flow')!r}: a flow that exposes lead custom fields (or carries a conflict) needs conflict_ref naming a C-NN defined in OPEN_ITEMS §4 (got {r.get('conflict_ref')!r})")
        covered |= set(by)
    report.check("G06", local_only <= services and not (local_only & covered),
                 f"privacy-policy.yaml#local_only_egress must list registry services that no flow row names: {sorted(local_only - services)} {sorted(local_only & covered)}")
    for sv in c.get("runtime-isolation.yaml", {}).get("services") or []:
        sid, eg = str(sv.get("service_id")), str(sv.get("egress", "")).strip()
        if eg.lower().startswith("none"):
            continue
        report.check("G06", sid in covered or sid in local_only,
                     f"service {sid} has egress {eg[:70]!r} but no privacy-policy.yaml#off_host_flows row names it in by (add the flow, or list the service in local_only_egress if it reaches only local services)")
        dests = egress_destinations(eg)
        rows_by = [r for r in flows if isinstance(r, dict) and sid in (r.get("by") or [])]
        missing = sorted(dname for key, dname in dests if not any(dname in (str(r.get("to", "")) + " " + str(r.get("flow", ""))).lower() for r in rows_by))
        report.check("G06", not (sid in local_only and dests) and not missing,
                     f"service {sid}: off-host destinations in its egress {[d for _, d in dests]} need a flow row it performs ({missing} uncovered) and a local_only_egress service may have none")
    # a cross-host read declared in runtime-isolation carries the same conflict ref as its flow row
    for d in c.get("runtime-isolation.yaml", {}).get("external_dependencies") or []:
        if isinstance(d, dict) and d.get("kind") == "cross_host_read" and d.get("host"):
            row = next((r for r in flows if isinstance(r, dict) and str(d.get("host")) in str(r.get("to", ""))), {})
            report.check("G06", bool(row) and row.get("conflict_ref") == d.get("conflict_ref") and d.get("reader") in (row.get("by") or []),
                         f"cross-host read {d.get('id')}: its off_host_flows row must name the reader and the same conflict_ref ({d.get('conflict_ref')} vs {row.get('conflict_ref') if row else None})")
    # G07 no prose fragment became a YAML key: an unquoted comma inside a flow mapping ({what: a (b, c) d}) silently turns the rest of
    # the value into keys with null values, so the configuration says less than the text that was written
    pending_lane_a = set()   # lane merge done (CS-M1): workflow-policy.yaml payload strings are quoted (CS-16)
    def _stray(obj, path, out):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if v is None and isinstance(k, str) and (re.search(r"\s", k.strip()) or "(" in k or ")" in k):
                    out.append(f"{path}.{k}")
                _stray(v, f"{path}.{k}", out)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                _stray(v, f"{path}[{i}]", out)
    targets = {name: cfg for name, cfg in c.items() if name.endswith(".yaml") and name not in pending_lane_a}
    targets.update({f"workflows/{name}": wf for name, wf in (c.get("_workflows") or {}).items()})
    for name, cfg in sorted(targets.items()):
        hits = []
        _stray(cfg, "", hits)
        report.check("G07", not hits, f"{name}: prose became null-valued keys (quote the value that holds a comma): {hits[:5]}")
    # one-word fragments too (REVIEW_B12 #8, probe G07-a): in the raw text every top-level segment of a one-line flow mapping is key: value
    folder = root / "09_Config_Templates"
    for f in sorted(list(folder.glob("*.yaml")) + list((folder / "workflows").glob("*.yaml"))):
        if f.name in pending_lane_a:
            continue
        bad_seg = [f"{f.name}:{n}" for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1) if flow_mapping_fragments(line)]
        report.check("G07", not bad_seg, f"one-line flow mappings with a segment that is not key: value (an unquoted comma split a value): {bad_seg[:5]}")

    # G08 user-rights tokens (VR-16; P-77, REVIEW_B12 #4/#8): an amoCRM token carries the rights - including the lead visibility - of
    # the user who issued it and its scope cannot be narrowed, so env.example marks it [user-rights], no line anywhere claims a narrow
    # token scope, the credential inventory records the issuing user's role, HG-F2-04 issues it as the least-privileged user that
    # still sees every lead of every AMT pipeline (never "admin sifatida" by default), and F2-AT-27 proves completeness
    env_text = str(c.get("_env", ""))
    marked = set(re.findall(r"^([A-Z0-9_]+)=.*\[user-rights\]", env_text, re.M))
    narrow = re.compile(r"\b(?:narrow|limited|tor|cheklangan)[\s-]+(?:lead[\s-]+(?:create|yaratish)[\s-]+)?scope\b|\blead-create scope\b|\bscope[\s-]+(?:limited|narrowed)\b", re.I)
    tok_line = re.compile(r"AMO_TOKEN|LANDING_CRM_CREDENTIAL|amoCRM[^|.;]{0,40}token|token[^|.;]{0,40}amoCRM", re.I)
    must = {"AMO_TOKEN", "LANDING_CRM_CREDENTIAL"}
    env_comments = {m.group(1): m.group(2) for m in re.finditer(r"^([A-Z0-9_]+)=[^#\n]*#(.*)$", env_text, re.M)}
    report.check("G08", must <= marked and not any(narrow.search(env_comments.get(v, "")) for v in marked),
                 f"env.example: amoCRM tokens {sorted(must - marked)} must be marked [user-rights] (VR-16) and no [user-rights] comment may claim a narrow token scope")
    if docs:
        sec = (root / "03_Architecture" / "SECURITY.md").read_text(encoding="utf-8") if (root / "03_Architecture" / "SECURITY.md").exists() else ""
        cc = (root / "11_Production_Contracts" / "CONFIG_CONTRACT.md").read_text(encoding="utf-8") if (root / "11_Production_Contracts" / "CONFIG_CONTRACT.md").exists() else ""
        sec10 = sec.split("## 10.", 1)[-1].split("\n## ", 1)[0] if "## 10." in sec else ""
        bad_rows = []
        for v in sorted(marked):
            rows = [l for l in sec10.split("\n") if l.startswith("|") and f"`{v}`" in l]
            if not rows or not all("issuing_user_role" in l and not narrow.search(l) for l in rows):
                bad_rows.append(v)
        block = cc.split("ops.credential_inventory:", 1)[-1].split("```", 1)[0] if "ops.credential_inventory:" in cc else ""
        report.check("G08", not bad_rows and "issuing_user_role:" in block,
                     f"SECURITY.md §10 rows of [user-rights] tokens {bad_rows} must name issuing_user_role and claim no narrow scope; CONFIG_CONTRACT ops.credential_inventory needs issuing_user_role")
        claims = []
        for f in sorted(root.rglob("*")):
            rel_f = f.relative_to(root)
            if not f.is_file() or f.suffix not in (".md", ".example") or rel_f.parts[0] == "00_Decisions" or rel_f.name == "VALIDATION_REPORT.md":
                continue
            for n, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
                if tok_line.search(line) and narrow.search(line):
                    claims.append(f"{rel_f}:{n}")
        phases = (root / "05_Build_Phases" / "PHASES.md").read_text(encoding="utf-8")
        hg04 = next((l for l in phases.split("\n") if l.startswith("| HG-F2-04 |")), "")
        f2 = (root / "05_Build_Phases" / "F2_Landing_Tracking.md").read_text(encoding="utf-8")
        at27 = next((l for l in f2.split("\n") if l.startswith("| F2-AT-27 |")), "")
        report.check("G08", not claims and "eng kam huquqli" in hg04 and "barcha lead’larni ko‘rish" in hg04 and not re.search(r"admin sifatida\s*\**\s*long-lived", hg04)
                     and "to‘liqlik" in at27 and "admin eksport" in at27,
                     f"amoCRM tokens: no document may claim a narrow token scope {claims[:5]}; HG-F2-04 issues the token as the least-privileged user that sees every lead of every AMT pipeline "
                     "(not 'admin sifatida long-lived token'); F2-AT-27 compares per-pipeline counts with an admin export (REVIEW_B12 #4)")

    # G09 llm-proxy error contract (GUARDRAIL_GATEWAY.md §10.1, budgets.yaml#openrouter.upstream_contract,
    # runtime-isolation.yaml#runner_contract.llm_client; P-79, P-97, REVIEW_B12 #20 and probes G09-a/b): no proxy code uses a status that
    # agent clients resend on their own (408, 409, 429, 5xx; VR-41); every upstream outcome maps to exactly its canonical no-retry code
    # (VR-42; no fallback, Q44.3) and an unlisted one is refused; no Retry cell says the proxy resends; the pinned adapters run with their own
    # retries off and every client timeout above the proxy deadline; the copies in ADR-003 and F1 name every code and F1-AT-28 every class
    uc09 = (((c.get("budgets.yaml") or {}).get("openrouter") or {}).get("upstream_contract")) or {}
    rc09 = uc09.get("result_codes") if isinstance(uc09.get("result_codes"), dict) else {}
    pairs09 = [(o, code) for code, outs in rc09.items() for o in (outs if isinstance(outs, list) else [None])]
    got09 = dict(pairs09)
    lc09 = (((c.get("runtime-isolation.yaml") or {}).get("runner_contract") or {}).get("llm_client")) or {}
    rkeys09 = {r.get("key") for r in ((c.get("readiness.yaml") or {}).get("requirements") or [])}
    report.check("G09", got09 == LLM_UPSTREAM_MAP and len(pairs09) == len(got09) and uc09.get("proxy_retries") == 0
                 and uc09.get("unmatched_result") == "upstream_refused" and uc09.get("reservation_on_error") == "retain_reservation_until_reconciled"
                 and uc09.get("deadline_readiness_ref") in rkeys09 and uc09.get("adapter_client_ref") == "runtime-isolation.yaml#runner_contract.llm_client"
                 and uc09.get("test") == "F1-AT-28" and "no error field" in str(uc09.get("success_rule", "")) and "finish_reason" in str(uc09.get("success_rule", ""))
                 and "never drops the connection" in str(uc09.get("stream_error_rule", "")) and "smallest client timeout" in str(uc09.get("upstream_deadline_rule", ""))
                 and lc09.get("max_retries") == 0 and lc09.get("retry_watchdog") == "unset" and lc09.get("timeouts_above_proxy_deadline") is True
                 and lc09.get("test") == "F1-AT-28",
                 f"budgets.yaml#openrouter.upstream_contract must map each upstream outcome once, exactly as {LLM_UPSTREAM_MAP} (got {got09}), with proxy_retries 0, "
                 "unmatched_result upstream_refused, reservation_on_error retain_reservation_until_reconciled, a readiness deadline_readiness_ref, the adapter_client_ref, "
                 "the success, stream and deadline rules and test F1-AT-28; runtime-isolation.yaml#runner_contract.llm_client needs max_retries 0, retry_watchdog unset, "
                 "timeouts_above_proxy_deadline true and test F1-AT-28 (VR-41, VR-42, P-97)")
    if docs:
        gw = root / "03_Architecture" / "GUARDRAIL_GATEWAY.md"
        sec101 = gw.read_text(encoding="utf-8").split("### 10.1", 1)[-1].split("\n## ", 1)[0] if gw.exists() else ""
        rows = re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*(\d{3})\s*\|", sec101, re.M)
        codes_101 = {code for code, _ in rows}
        bad_http = sorted(f"{code}={http}" for code, http in rows if http in SDK_RETRIED_HTTP or http.startswith("5"))
        cells09 = {}
        for line in sec101.split("\n"):
            m09 = re.match(r"^\|\s*`([a-z_]+)`\s*\|", line)
            if m09:
                cells09[m09.group(1)] = [x.strip() for x in line.strip().strip("|").split("|")]
        claims09 = sorted(code for code, cl in cells09.items() if len(cl) < 4 or RETRY_CLAIM_RE.search(cl[3]))
        ua = cells09.get("upstream_unavailable") or ["", "", "", ""]
        ur = cells09.get("upstream_refused") or ["", "", "", ""]
        ae = cells09.get("allowance_exhausted") or ["", "", "", ""]
        row_gaps = sorted(f"upstream_unavailable:{t}" for t in ("408", "429", "5xx", "504", "200", "`error`", "SSE", "ulanish", "upstream_deadline") if t not in ua[2])
        row_gaps += sorted(f"upstream_refused:{t}" for t in ("limit_source`siz 403", "guardrail", "moderation", "unmatched_result") if t not in ur[2])
        row_gaps += sorted(f"allowance_exhausted:{t}" for t in ("402", "limit_source`li 403") if t not in ae[2])
        row_gaps += [] if "proxy o‘zi qayta urinmaydi" in ua[3] else ["upstream_unavailable: Retry cell must say 'proxy o‘zi qayta urinmaydi'"]
        row_gaps += [] if ur[3].startswith("yo‘q") and "proxy qayta urinmaydi" in ur[3] else ["upstream_refused: Retry cell must be 'yo‘q; proxy qayta urinmaydi'"]
        row_gaps += [f"§10.1 text: {t}" for t in ("408, 409, 429 va 5xx ishlatilmaydi", "max_retries: 0", "upstream_contract", "terminal xato event", "upstream_deadline") if t not in sec101]
        copies = {"04_ADR/ADR-003-openrouter-single-key-watchdog.md": None, "05_Build_Phases/F1_Platform.md": None}
        missing = {}
        for rel in copies:
            f = root / rel
            text = f.read_text(encoding="utf-8") if f.exists() else ""
            miss = sorted(code for code in codes_101 if f"`{code}`" not in text) + [t for t in ("408", "SSE", "max_retries: 0") if t not in text]
            if miss:
                missing[rel] = miss
        f1t = (root / "05_Build_Phases" / "F1_Platform.md").read_text(encoding="utf-8") if (root / "05_Build_Phases" / "F1_Platform.md").exists() else ""
        at28 = next((l for l in f1t.split("\n") if l.startswith("| F1-AT-28 |")), "")
        at28_gaps = [t for t in ("408", "504", "`error`", "SSE", "limit_source", "moderation", "max_retries: 0", "API_TIMEOUT_MS", "upstream_deadline",
                                 "429 bo‘roni", "upstream_refused", "allowance_exhausted", "ulanish uzilmaydi") if t not in at28]
        rf = root / "10_Reference" / "RESEARCH_FACTS.md"
        rft = rf.read_text(encoding="utf-8") if rf.exists() else ""
        vr41 = next((l for l in rft.split("\n") if l.startswith("| VR-41 |")), "")
        vr42 = next((l for l in rft.split("\n") if l.startswith("| VR-42 |")), "")
        vr_gaps = [f"VR-41:{t}" for t in ("408", "CLAUDE_CODE_MAX_RETRIES", "CLAUDE_CODE_RETRY_WATCHDOG", "API_TIMEOUT_MS") if t not in vr41]
        vr_gaps += [f"VR-42:{t}" for t in ("limit_source", "finish_reason", "`200 OK`", "504") if t not in vr42]
        report.check("G09", bool(rows) and {"upstream_unavailable", "upstream_refused", "allowance_exhausted"} <= codes_101 and not bad_http and not claims09
                     and not row_gaps and not missing and not at28_gaps and not vr_gaps,
                     f"GUARDRAIL §10.1 llm-proxy codes: client-resent HTTP statuses {bad_http}, Retry cells claiming the proxy resends {claims09}, "
                     f"upstream/limit rows and text gaps {row_gaps}, copies missing codes or terms {missing}, F1-AT-28 gaps {at28_gaps}, vendor fact gaps {vr_gaps} "
                     "(REVIEW_B12 #20, probes G09-a/b)")

    # G10 gateway guard 4 argument schemas (09_Config_Templates/schemas/tools, L3-11): every concrete allowlisted tool has a named
    # Draft 2020-12 schema that is closed (an open object must say where it is validated), keeps money as integer *_minor beside a
    # currency, bounds every string, takes no raw SQL and resolves every $ref; the bundle index, the release identity
    # (tool_schema_digest) and the protected surfaces name the set; Hermes output, which never passes the gateway, has its own filter
    base_id = "https://wolter.uz/amt/schemas/tools/"
    sdir = root / "09_Config_Templates" / "schemas" / "tools"
    on_disk = {p.name for p in sdir.glob("*.schema.json")} if sdir.exists() else set()
    index_ts = set((c.get("_index") or {}).get("tool_schemas") or [])
    report.check("G10", bool(on_disk) and on_disk == index_ts and "_common.schema.json" in on_disk,
                 f"bundle-index.json tool_schemas differ from schemas/tools/ (or _common.schema.json is missing): {sorted(on_disk ^ index_ts)}")
    ap = c.get("approval-policy.yaml", {})
    mgroups = ap.get("meta_read_groups") or {}
    concrete = set()
    for spec in (ap.get("agents") or {}).values():
        for t in (spec or {}).get("tools") or []:
            t = str(t)
            if t == "meta_read.*":
                concrete |= {str(x) for x in ap.get("meta_read_allowlist") or []}
            elif t.startswith("meta_read.") and t.split(".", 1)[1] in mgroups:
                concrete |= {str(x) for x in mgroups.get(t.split(".", 1)[1]) or []}
            else:
                concrete.add(t)
    missing = sorted(t for t in concrete if f"{t}.schema.json" not in on_disk)
    report.check("G10", not missing, f"allowlisted tools without a schemas/tools/<tool>.schema.json argument schema: {missing}")
    tdocs = {}
    for n in sorted(on_disk):
        try:
            tdocs[n] = json.loads((sdir / n).read_text(encoding="utf-8"))
        except ValueError as exc:
            report.check("G10", False, f"schemas/tools/{n}: cannot load ({exc})")
    common_defs = set((tdocs.get("_common.schema.json") or {}).get("$defs") or {})
    handoff_props = set(((c.get("_schemas") or {}).get("handoff.schema.json") or {}).get("properties") or {})

    def _schema_problems(node, path, doc, out, overlay=False):
        """REVIEW_B12 #6/#8/#22: closed objects (additionalProperties false, or a typed map with propertyNames and maxProperties), bounded
        strings (maxLength; format alone does not bound), arrays with items and maxItems, integer *_minor money, no float money, the
        common currency type, no raw SQL keys, resolvable $refs; if/then/else refine the parent and are not checked for closure."""
        if isinstance(node, dict):
            types = node.get("type") if isinstance(node.get("type"), list) else [node.get("type")]
            if not overlay and ("object" in types or "properties" in node):
                apv = node.get("additionalProperties")
                typed_map = isinstance(apv, dict) and bool(apv) and isinstance(node.get("propertyNames"), dict) and isinstance(node.get("maxProperties"), int) and node["maxProperties"] <= 100
                if not (apv is False or typed_map or (path == "" and node.get("oneOf"))):
                    out.append(f"{path}: open object (additionalProperties must be false, or a typed map with propertyNames and maxProperties)")
            props = node.get("properties") or {}
            if isinstance(props, dict):
                for k, v in props.items():
                    if k.endswith("_minor") and not (isinstance(v, dict) and (v.get("type") == "integer" or str(v.get("$ref", "")).endswith("/money_minor"))):
                        out.append(f"{path}.{k}: money is not an integer minor unit")
                    if MONEY_NAME_RE.search(k) and not k.endswith("_minor"):
                        out.append(f"{path}.{k}: money outside an integer *_minor field")
                    if k.lower() in RAW_SQL_KEYS:
                        out.append(f"{path}.{k}: raw SQL")
                    if k == "currency" and not (isinstance(v, dict) and v.get("$ref") == "_common.schema.json#/$defs/currency"):
                        out.append(f"{path}.currency: must be the common ISO 4217 currency type")
                if any(k.endswith("_minor") for k in props) and "currency" not in props:
                    out.append(f"{path}: *_minor without a currency")
            if "string" in types and not any(x in node for x in ("enum", "const")) and not (isinstance(node.get("maxLength"), int) and node["maxLength"] <= 2000):
                out.append(f"{path}: string without maxLength <= 2000 (format alone is an annotation)")
            if "array" in types and not (isinstance(node.get("items"), dict) and node["items"] and isinstance(node.get("maxItems"), int) and node["maxItems"] <= 1000):
                out.append(f"{path}: array without items or maxItems <= 1000")
            ref = node.get("$ref")
            if isinstance(ref, str):
                tail = ref.rsplit("/", 1)[-1]
                ok_ref = ((ref.startswith("_common.schema.json#/$defs/") and tail in common_defs) or (ref.startswith("#/$defs/") and tail in (doc.get("$defs") or {}))
                          or (ref.startswith("../handoff.schema.json#/properties/") and tail in handoff_props))
                if not ok_ref:
                    out.append(f"{path}: unresolved $ref {ref}")
            for k, v in node.items():
                if k != "not":   # a negative subschema describes what is refused, not an accepted value
                    _schema_problems(v, f"{path}.{k}", doc, out, overlay=overlay or k in ("if", "then", "else"))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                _schema_problems(v, f"{path}[{i}]", doc, out, overlay)

    try:
        import jsonschema as _js
        meta_check = _js.Draft202012Validator.check_schema
    except (ImportError, AttributeError):   # W00 already reports a missing or old jsonschema
        meta_check = None
    for n, doc in sorted(tdocs.items()):
        out = []
        if n != "_common.schema.json":
            branches = doc.get("oneOf") if isinstance(doc.get("oneOf"), list) else []
            closed_branches = bool(branches) and all(isinstance(b, dict) and b.get("type") == "object" and b.get("additionalProperties") is False for b in branches)
            if not (doc.get("type") == "object" and (doc.get("additionalProperties") is False or (closed_branches and "additionalProperties" not in doc))):
                out.append("top level must be a closed object (or a oneOf of closed objects)")
        if doc.get("$schema") != "https://json-schema.org/draft/2020-12/schema" or doc.get("$id") != base_id + n:
            out.append(f"$schema must be Draft 2020-12 and $id {base_id + n}")
        _schema_problems(doc, "", doc, out)
        if meta_check:
            try:
                meta_check(doc)
            except Exception as exc:   # jsonschema.SchemaError
                out.append(f"not a valid Draft 2020-12 schema: {str(exc).splitlines()[0]}")
        report.check("G10", not out, f"schemas/tools/{n}: {out[:4]}")
    # the shared types keep the bounds P-80 claims (REVIEW_B12 #6/#22, probes G10-a/c/d/e): uuid, date and datetime bounded by pattern and
    # length, currency rendered from the account currency, render parameters from an allow-listed character set without encodings or
    # '..', integer ranges for money metrics; render tools take only that type; wh.query is exactly view/columns/filters/order_by/limit
    # with limit <= 5000 and bounded filter values; workflow.start is closed per agent-startable workflow on its exact input fields
    cd_ = (tdocs.get("_common.schema.json") or {}).get("$defs") or {}
    def _bounded(defn, maxlen):
        return isinstance(defn, dict) and bool(defn.get("pattern")) and isinstance(defn.get("maxLength"), int) and defn["maxLength"] <= maxlen
    rp = cd_.get("render_param") or {}
    rp_not = json.dumps(rp.get("not") or {})
    ee_ = cd_.get("expected_effect") or {}
    report.check("G10", _bounded(cd_.get("uuid"), 36) and _bounded(cd_.get("date"), 10) and _bounded(cd_.get("datetime"), 32)
                 and (cd_.get("currency") or {}).get("pattern") == "^[A-Z]{3}$" and (cd_.get("currency") or {}).get("maxLength") == 3
                 and (cd_.get("currency") or {}).get("x-amt-const-from") == "budgets.yaml#ads.account_currency"
                 and rp.get("pattern") == RENDER_PARAM_PATTERN and "%[0-9A-Fa-f]{2}" in rp_not and "\\\\.\\\\." in rp_not
                 and (ee_.get("additionalProperties") is False) and ((ee_.get("if") or {}).get("properties") or {}).get("metric", {}).get("pattern") == "_minor$"
                 and all(((ee_.get("then") or {}).get("properties") or {}).get(k, {}).get("type") == "integer" for k in ("range_low", "range_high")),
                 "schemas/tools/_common.schema.json: uuid/date/datetime need pattern + maxLength, currency the ISO pattern with x-amt-const-from budgets.yaml#ads.account_currency, "
                 "render_param the allow-listed pattern with the percent-encoding and '..' refusal, expected_effect closed with integer ranges for *_minor metrics")
    for rn in ("render.html_to_png.schema.json", "render.video_template.schema.json"):
        prm = (((tdocs.get(rn) or {}).get("properties") or {}).get("params") or {})
        report.check("G10", prm.get("additionalProperties") == {"$ref": "_common.schema.json#/$defs/render_param"},
                     f"schemas/tools/{rn}: params values must be the common render_param type (no own pattern, no escape)")
    whq = (tdocs.get("wh.query.schema.json") or {}).get("properties") or {}
    fprops = (((whq.get("filters") or {}).get("items") or {}).get("properties") or {})
    report.check("G10", set(whq) == {"view", "columns", "filters", "order_by", "limit"} and (whq.get("limit") or {}).get("maximum") is not None
                 and int((whq.get("limit") or {}).get("maximum") or 10**9) <= 5000 and set(fprops) == {"column", "op", "value"} and "oneOf" in (fprops.get("value") or {}),
                 f"schemas/tools/wh.query.schema.json: exactly view, columns, filters, order_by and limit (no raw SQL clause), limit <= 5000, bounded filter values: {sorted(whq)}")
    wfs_ = c.get("_workflows") or {}
    agent_ids = set((c.get("approval-policy.yaml", {}).get("agents") or {}).keys())
    startable = {wf.get("workflow_id"): wf for wf in wfs_.values() if set((wf.get("authorization") or {}).get("may_start") or []) & agent_ids}
    br_ = {}
    for b in (tdocs.get("workflow.start.schema.json") or {}).get("oneOf") or []:
        wid_ = (((b or {}).get("properties") or {}).get("workflow_id") or {}).get("const")
        br_[wid_] = ((b.get("properties") or {}).get("input") or {})
    norm = lambda fields: [re.sub(r"\(.*\)$", "", str(x)) for x in fields or []]
    bad_br = sorted(w for w, wf in startable.items() if w not in br_ or br_[w].get("additionalProperties") is not False
                    or set((br_[w].get("properties") or {})) != set(norm((wf.get("input") or {}).get("required_fields")) + norm((wf.get("input") or {}).get("optional_fields")))
                    or set(br_[w].get("required") or []) != set(norm((wf.get("input") or {}).get("required_fields"))))
    report.check("G10", set(br_) == set(startable) and not bad_br,
                 f"schemas/tools/workflow.start.schema.json: one closed branch per agent-startable workflow {sorted(startable)} with exactly its input fields (got {sorted(k for k in br_ if k)}; mismatched {bad_br})")
    vf = set(c.get("release-policy.yaml", {}).get("version_fields") or [])
    prot_txt = " ".join(map(str, c.get("evolution-policy.yaml", {}).get("protected_surfaces") or []))
    of = c.get("runtime-isolation.yaml", {}).get("cmo_telegram_outbound_filter")
    of = of if isinstance(of, dict) else {}
    try:
        of_ok = 0 < int(of.get("max_chars")) <= 4096
    except (TypeError, ValueError):
        of_ok = False
    report.check("G10", "tool_schema_digest" in vf and "config/schemas/tools/" in prot_txt and of_ok and of.get("on_hit") == "drop_and_alert"
                 and {"credential_formats", "lead_pii_patterns"} <= set(of.get("blocks") or []) and bool(of.get("hook")) and bool(of.get("allow_from")) and bool(of.get("notify_chat"))
                 and (not docs or of.get("alert") in codes),
                 "release-policy.yaml version_fields needs tool_schema_digest, evolution-policy.yaml protected_surfaces config/schemas/tools/**, and runtime-isolation.yaml cmo_telegram_outbound_filter "
                 "max_chars <= 4096 (Telegram), blocks, on_hit drop_and_alert and a catalogued alert")
    if docs:
        gwt = (root / "03_Architecture" / "GUARDRAIL_GATEWAY.md").read_text(encoding="utf-8") if (root / "03_Architecture" / "GUARDRAIL_GATEWAY.md").exists() else ""
        g4 = next((l for l in gwt.split("\n") if l.startswith("| 4 | Argument va qiymat |")), "")
        report.check("G10", "schemas/tools/" in g4, "GUARDRAIL_GATEWAY.md §3 guard 4 must name the argument schemas it enforces (schemas/tools/<tool>.schema.json)")
    def doc_row(rel, test_id):
        """The table row of one test id in a phase file ('' when absent)."""
        f = root / rel
        text = f.read_text(encoding="utf-8") if f.exists() else ""
        return next((l for l in text.split("\n") if l.startswith(f"| {test_id} |")), "")
    # G11 runtime demand and unit-cost model (schemas/cost-model.schema.json, L4-03, P-81): the F4 model is a checked artefact — a valid
    # Draft 2020-12 schema whose agent set equals the budgets.yaml shares (reserve is never pre-assigned), whose inputs carry a kernel
    # evidence tag (D/T/X, never '?') with evidence refs, and whose totals compare p90 with every share and the key cap; F1-AT-13 records
    # the unit cost per call, F4-AT-19 consumes the model and DATA_MODEL ai_requests keeps the token split and the run/step attribution
    cm = (c.get("_schemas") or {}).get("cost-model.schema.json")
    share_agents = set(((c.get("budgets.yaml") or {}).get("openrouter") or {}).get("shares_minor") or {}) - {"reserve"}
    report.check("G11", isinstance(cm, dict), "09_Config_Templates/schemas/cost-model.schema.json must be listed in bundle-index.json schemas (F4 runtime demand model)")
    if isinstance(cm, dict):
        try:
            import jsonschema
            jsonschema.Draft202012Validator.check_schema(cm)
            schema_ok, schema_msg = True, ""
        except (ImportError, AttributeError):
            schema_ok, schema_msg = True, ""   # W00 reports the missing or old jsonschema
        except Exception as exc:  # jsonschema.exceptions.SchemaError
            schema_ok, schema_msg = False, getattr(exc, "message", str(exc))[:200]
        report.check("G11", schema_ok, f"cost-model.schema.json is not a valid Draft 2020-12 schema: {schema_msg}")
        defs = cm.get("$defs") or {}
        row = defs.get("row") or {}
        agents = set(((row.get("properties") or {}).get("agent") or {}).get("enum") or [])
        report.check("G11", agents == share_agents,
                     f"cost-model.schema.json row agents {sorted(agents)} must equal the budgets.yaml shares without reserve {sorted(share_agents)}")
        basis = defs.get("basis") or {}
        tags = [set(((basis.get("properties") or {}).get(k) or {}).get("enum") or []) for k in ("volume", "tokens")]
        report.check("G11", all(t == {"D", "T", "X"} for t in tags) and "evidence_refs" in (basis.get("required") or []),
                     "cost-model.schema.json basis: volume and tokens take only the kernel tags D, T, X (an unknown is a T range, never '?') and evidence_refs is required")
        need_row = {"source", "agent", "model_class", "runs_per_month", "calls_per_run", "input_tokens_per_call", "output_tokens_per_call",
                    "cache_hit_ratio", "usd_minor_per_month", "basis"}
        totals_req = set((defs.get("totals") or {}).get("required") or [])
        report.check("G11", need_row <= set(row.get("required") or []) and {"per_agent", "key_usd_minor", "agents_over_share_p90", "key_over_cap_p90"} <= totals_req
                     and row.get("additionalProperties") is False,
                     f"cost-model.schema.json: a closed row needs {sorted(need_row - set(row.get('required') or []))} and totals need per_agent, key_usd_minor, agents_over_share_p90, key_over_cap_p90")
        ib11 = defs.get("int_band") or {}
        ibp11 = ib11.get("properties") or {}
        rp11 = row.get("properties") or {}
        chr11 = rp11.get("cache_hit_ratio") or {}
        tp11 = (defs.get("totals") or {}).get("properties") or {}
        band_fields = ("runs_per_month", "calls_per_run", "input_tokens_per_call", "output_tokens_per_call", "usd_minor_per_month")
        report.check("G11", ib11.get("type") == "object" and ib11.get("additionalProperties") is False and {"p50", "p90"} <= set(ib11.get("required") or [])
                     and all((ibp11.get(k) or {}).get("type") == "integer" and (ibp11.get(k) or {}).get("minimum") == 0 for k in ("p50", "p90"))
                     and all((rp11.get(k) or {}).get("$ref") == "#/$defs/int_band" for k in band_fields) and (tp11.get("key_usd_minor") or {}).get("$ref") == "#/$defs/int_band"
                     and chr11.get("type") == "number" and chr11.get("minimum") == 0 and chr11.get("maximum") == 1,
                     "cost-model.schema.json: int_band must be a closed object with required integer p50 and p90 (minimum 0); every count, token and usd_minor field of a "
                     "row and totals.key_usd_minor must use it; cache_hit_ratio is a number in [0, 1] (no fractional money, no band without p90; rule strength, P-98)")
    if docs:
        f113, f419 = doc_row("05_Build_Phases/F1_Platform.md", "F1-AT-13"), doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-19")
        dm = (root / "03_Architecture" / "DATA_MODEL.md").read_text(encoding="utf-8") if (root / "03_Architecture" / "DATA_MODEL.md").exists() else ""
        air = next((l for l in dm.split("\n") if l.startswith("`ai_requests` —")), "")
        report.check("G11", "UNIT_COST.md" in f113 and "cached_input_tokens" in f113 and "cost-model.json" in f419
                     and all(x in air for x in ("`input_tokens`", "`cached_input_tokens`", "`cache_write_tokens`", "`output_tokens`", "`run_id`", "`step_id`")),
                     "F1-AT-13 must record the unit cost per call (UNIT_COST.md, cached_input_tokens), F4-AT-19 must consume build/F4/cost-model.json, and DATA_MODEL "
                     "ai_requests must keep input/cached/cache-write/output tokens with run_id and step_id")
    # G12 provider pin and prompt cache (budgets.yaml#openrouter.provider_policy, L4-04, P-82): Claude requests go only to Anthropic
    # first-party and no family may fall back to another provider (Q44.3), data collection is denied (Q44★), cache_control passes
    # through unchanged and cache prices enter the upper-bound reservation only on a path F1-AT-29 proved; ADR-003 and F1 copy it
    pp = (((c.get("budgets.yaml") or {}).get("openrouter") or {}).get("provider_policy")) or {}
    cf, of_ = pp.get("claude_family") or {}, pp.get("other_families") or {}
    report.check("G12", cf.get("order") == ["anthropic"] and cf.get("allow_fallbacks") is False and of_.get("allow_fallbacks") is False
                 and of_.get("provider") == "pinned_in_models_assignments"
                 and pp.get("data_collection") == "deny" and pp.get("cache_control") == "pass_through" and pp.get("cache_aware_reservation") == "never",
                 "budgets.yaml#openrouter.provider_policy: Claude order [anthropic] with allow_fallbacks false, other families pinned_in_models_assignments with allow_fallbacks false (Q44.3), "
                 "data_collection deny (Q44★), cache_control pass_through, cache_aware_reservation never (a hold is never priced at the cache-read rate, REVIEW_B34 #1, P-99)")
    if docs:
        adr3 = (root / "04_ADR" / "ADR-003-openrouter-single-key-watchdog.md")
        item3 = next((l for l in (adr3.read_text(encoding="utf-8").split("\n") if adr3.exists() else []) if l.startswith("3. Provider siyosati")), "")
        f129 = doc_row("05_Build_Phases/F1_Platform.md", "F1-AT-29")
        cc = (root / "11_Production_Contracts" / "CONFIG_CONTRACT.md")
        rb = next((l for l in (cc.read_text(encoding="utf-8").split("\n") if cc.exists() else []) if l.startswith("| `budget.request_bounds` |")), "")
        obs12 = root / "03_Architecture" / "OBSERVABILITY.md"
        obs12t = obs12.read_text(encoding="utf-8") if obs12.exists() else ""
        report.check("G12", '`provider.order: ["anthropic"]`, `allow_fallbacks: false`' in item3 and "provider_policy" in item3
                     and "reservation hech qachon cache-read narxida hisoblanmaydi" in item3 and "1 soatlik yoki noma’lum TTL’da 2×" in item3
                     and "reservation hech qachon keshli narxda emas" in f129 and "faqat F4 runtime talab modeli va settlement tahliliga kiradi" in f129
                     and "Upper-bound reservation hech qachon cache-read narxida hisoblanmaydi" in obs12t and "keshli narxni faqat" not in obs12t
                     and "cache_effective" in f129 and "cache_control" in f129 and "allow_fallbacks: false" in f129 and "min_hit_ratio" in rb
                     and "reservation’ga ta’sir qilmaydi" in rb,
                     "ADR-003 item 3 must pin Claude to Anthropic with allow_fallbacks false, name provider_policy and state that a reservation is never priced at the "
                     "cache-read rate (2x for a 1-hour or unknown TTL); F1-AT-29 must measure cache_effective, cache_control pass-through and the pin and keep "
                     "cache_effective out of reservations; OBSERVABILITY §3 must say the same; CONFIG_CONTRACT budget.request_bounds must carry cache.min_hit_ratio "
                     "and say it does not touch reservations")
    # G13 per-role prompt manifest (prompt-manifest.yaml, L4-05, P-83): every business agent has a closed eager set — the common
    # contract block, the kernel (Q13), the invariant index, its role prompt and exactly the skills its charter names — whose
    # estimate (CONTEXT_PACKS estimator) fits max_fixed_tokens; whole contract files are on demand, the runner writes kernel_ref,
    # the release records prompt_digest and budget.request_bounds bounds the whole request with max_input_tokens
    pm = c.get("prompt-manifest.yaml")
    report.check("G13", isinstance(pm, dict), "09_Config_Templates/prompt-manifest.yaml is required (per-role eager prompt and its ceiling, L4-05)")
    if isinstance(pm, dict):
        roles_pm = pm.get("roles") or {}
        report.check("G13", set(roles_pm) == BUSINESS_AGENTS, f"prompt-manifest.yaml roles {sorted(roles_pm)} must be the six business agents")
        report.check("G13", pm.get("kernel_ref_source") == "runner", "prompt-manifest.yaml kernel_ref_source must be runner (the model never computes a digest)")
        est = (c.get("_context_packs") or {}).get("estimator") or {}
        report.check("G13", str(pm.get("estimator_ref", "")).startswith(str(PACKS_FILE)) and bool(est), "prompt-manifest.yaml estimator_ref must name the CONTEXT_PACKS.yaml estimator")

        def part_text(entry):
            f = root / str(entry.get("path", ""))
            if not f.is_file():
                return None
            t = f.read_text(encoding="utf-8")
            if entry.get("section"):
                t = md_section(t, entry["section"])
                if t is not None and entry.get("part") == "text_block":
                    m = re.search(r"```text\n(.*?)```", t, re.S)
                    t = m.group(1) if m else None
            return t
        inv_path = root / "11_Production_Contracts" / "INVARIANTS.md"
        inv_text = inv_path.read_text(encoding="utf-8") if inv_path.exists() else ""
        index = [f"- {m.group(1)}. {m.group(2).split('. ')[0]}" for m in re.finditer(r"^(I\d{2})\. (.+)$", inv_text, re.M)]
        common, common_texts = pm.get("common_eager") or [], []
        common_runtime_tokens = 0   # runtime eager content (released lessons, P-91) counts at its declared max_tokens
        for e in common:
            if not isinstance(e, dict):
                report.check("G13", False, f"prompt-manifest.yaml common_eager entry is not a mapping: {e}")
            elif e.get("extract") == "invariant_index":
                common_texts.append("\n".join(index))
            elif e.get("runtime"):
                mt = e.get("max_tokens")
                report.check("G13", type(mt) is int and mt > 0 and bool(e.get("selection")) and bool(e.get("description")),
                             f"prompt-manifest.yaml common_eager runtime entry needs an integer max_tokens, a selection rule and a description: {e}")
                common_runtime_tokens += mt if type(mt) is int and mt > 0 else 0
            else:
                t = part_text(e)
                report.check("G13", t is not None, f"prompt-manifest.yaml common_eager: {e.get('path')} {e.get('section') or ''} not found")
                common_texts.append(t or "")
        def ident(e):
            if not isinstance(e, dict):
                return ("?", str(e))
            if e.get("extract"):
                return ("extract", e["extract"])
            if e.get("runtime"):
                return ("runtime", e["runtime"])
            return ("path", e.get("path"), e.get("section"), e.get("part"))
        common_canon = [("path", "02_Team_Charter/TEAM.md", "2.5 Umumiy agent execution contract", "text_block"), ("path", "08_Skills/thinking-kernel/SKILL.md", None, None),
                        ("extract", "invariant_index"), ("runtime", "knowledge/lessons/")]   # closed eager common set (REVIEW_B34 #9 probe G13-2)
        report.check("G13", [ident(e) for e in common] == common_canon,
                     f"prompt-manifest.yaml common_eager must be exactly the TEAM §2.5 block, the kernel, the invariant index and the released lessons (got {[ident(e) for e in common]})")
        cpaths = {e.get("path") for e in common if isinstance(e, dict)}
        report.check("G13", {"02_Team_Charter/TEAM.md", "08_Skills/thinking-kernel/SKILL.md"} <= cpaths and any(isinstance(e, dict) and e.get("extract") == "invariant_index" for e in common)
                     and bool(index) and (pm.get("invariant_index") or {}).get("scope") == "all_invariants",
                     "prompt-manifest.yaml common_eager must hold the TEAM §2.5 contract, the always-on kernel (Q13) and the index of all invariants")
        skill_dirs = {f.parent.name for f in (root / "08_Skills").glob("*/SKILL.md")}
        for e in (pm.get("common_on_demand") or []):
            report.check("G13", isinstance(e, dict) and (root / str(e.get("path", ""))).is_file() and bool(e.get("description")), f"prompt-manifest.yaml common_on_demand entry is not an existing file with a description: {e}")
        for role, spec in sorted(roles_pm.items()):
            spec = spec if isinstance(spec, dict) else {}
            rp = spec.get("role_prompt") or {}
            rpt = part_text(rp) if isinstance(rp, dict) else None
            report.check("G13", rpt is not None, f"prompt-manifest.yaml {role}: role prompt {rp} not found")
            cf = root / str(rp.get("path", "")) if isinstance(rp, dict) else None
            ctext = cf.read_text(encoding="utf-8") if cf is not None and cf.is_file() else ""
            m = re.search(r"^Skill’lar:\s*(.+)$", ctext, re.M)
            named = (set(re.findall(r"\b([a-z]+(?:-[a-z]+)+)\b", m.group(1))) & skill_dirs) - {"thinking-kernel"} if m else set()
            eager = [str(x) for x in spec.get("eager_skills") or []]
            report.check("G13", set(eager) == named and len(eager) == len(set(eager)),
                         f"prompt-manifest.yaml {role}: eager_skills {sorted(eager)} must equal the charter Skill’lar line without thinking-kernel {sorted(named)}")
            secs = spec.get("eager_sections") or []
            want_secs = [{"path": "02_Team_Charter/agents/REVIEWER.md", "section": "Verdict sxemasi"}] if role == "reviewer" else []   # REVIEW_B34 #12, P-103
            report.check("G13", secs == want_secs, f"prompt-manifest.yaml {role}: eager_sections must be {want_secs} (got {secs})")
            sec_texts = [part_text(e) or "" for e in secs if isinstance(e, dict)]
            report.check("G13", all(sec_texts) or not secs, f"prompt-manifest.yaml {role}: an eager section is not found")
            texts = common_texts + [rpt or ""] + sec_texts + [(root / "08_Skills" / sk / "SKILL.md").read_text(encoding="utf-8") for sk in eager if sk in skill_dirs]
            tokens = (estimate_tokens("\n\n".join(texts), est) if est else 0) + common_runtime_tokens
            mx = spec.get("max_fixed_tokens")
            ceil13 = -(-int(tokens * 1.15) // 1000) * 1000   # ceiling_rule: estimate + at most 15 %, rounded up to 1 000 (REVIEW_B34 #9 probes G13-1, G13-2)
            report.check("G13", type(mx) is int and 0 < mx <= 60000 and tokens <= mx <= ceil13,
                         f"prompt-manifest.yaml {role}: eager prompt ~{tokens} estimated tokens must fit max_fixed_tokens {mx}, and the ceiling may be at most "
                         f"{ceil13} (estimate + 15 %, rounded up to 1 000; growth is a reviewed manifest change)")
            sk_mp = root / "08_Skills" / "meta-ads-policy-review" / "SKILL.md"
            mcap = re.search(r"at most ([0-9][0-9 ]*) estimated tokens", sk_mp.read_text(encoding="utf-8")) if sk_mp.exists() else None
            mcap_v = int(mcap.group(1).replace(" ", "")) if mcap else None
            for e in spec.get("on_demand") or []:
                if isinstance(e, dict) and e.get("runtime") == "knowledge/meta-policy/":
                    report.check("G13", e.get("max_tokens") == mcap_v and e.get("overflow") == "the release refuses a knowledge/meta-policy/ set over max_tokens; the role opens it by section index",
                                 f"prompt-manifest.yaml {role}: the meta-policy cap must equal the meta-ads-policy-review skill cap ({mcap_v}) and carry the release overflow rule (REVIEW_B34 #11, probe G13-4)")
            for e in spec.get("on_demand") or []:
                ok_e = isinstance(e, dict) and bool(e.get("description")) and (
                    (root / str(e.get("path", ""))).is_file() if e.get("path") else (bool(e.get("runtime")) and type(e.get("max_tokens")) is int and e.get("max_tokens") > 0))
                report.check("G13", ok_e, f"prompt-manifest.yaml {role}: on_demand entry needs an existing bundle path or a runtime path with an integer max_tokens, and a description: {e}")
    hi13 = (pm.get("hermes_injection") or {}) if isinstance(pm, dict) else {}
    report.check("G13", hi13 == {"file": "SOUL.md", "cap_key": "context_file_max_chars", "check": "F4-AT-28",
                                 "cap_rule": "the release sets context_file_max_chars in the pinned Hermes config to ceil(1.1 x the SOUL.md characters), at most 500000; "
                                             "a SOUL.md that would need more refuses the release"},
                 "prompt-manifest.yaml hermes_injection must pin the SOUL.md cap rule (context_file_max_chars, release-computed, checked by F4-AT-28; REVIEW_B34 #5)")
    if docs:
        team = (root / "02_Team_Charter" / "TEAM.md")
        tsec = md_section(team.read_text(encoding="utf-8"), "2.5 Umumiy agent execution contract") if team.exists() else None
        ker = (root / "08_Skills" / "thinking-kernel" / "SKILL.md")
        ktxt = ker.read_text(encoding="utf-8") if ker.exists() else ""
        cc = (root / "11_Production_Contracts" / "CONFIG_CONTRACT.md")
        rb = next((l for l in (cc.read_text(encoding="utf-8").split("\n") if cc.exists() else []) if l.startswith("| `budget.request_bounds` |")), "")
        vfields = set(c.get("release-policy.yaml", {}).get("version_fields") or [])
        f428 = doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-28")
        rv13 = root / "02_Team_Charter" / "agents" / "REVIEWER.md"
        report.check("G13", bool(tsec) and "do not load whole contract files by default." in tsec and "the released lessons that match your role" in tsec
                     and "taxminning kamida 90% i" in f428 and "context_file_max_chars" in f428
                     and rv13.exists() and 'the JSON verdict schema in your prompt (charter section "Verdict sxemasi")' in rv13.read_text(encoding="utf-8"),
                     "TEAM §2.5 must keep 'do not load whole contract files by default.' and name the released lessons; prompt-manifest hermes_injection must pin the SOUL.md cap "
                     "rule; F4-AT-28 must be two-sided (at least 90 % of the estimate or the prompt_digest hash) and check context_file_max_chars; the Reviewer role prompt "
                     "must point to the verdict schema in its prompt (REVIEW_B34 #5, #9, #12)")
        report.check("G13", bool(tsec) and "prompt-manifest.yaml" in tsec and "Read the linked production invariants and the task-relevant business contract" not in tsec
                     and "kernel_ref_source" in ktxt and "prompt_digest" in vfields and "max_input_tokens" in rb and bool(doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-28")),
                     "TEAM §2.5 must load by prompt-manifest.yaml (no whole-contract reads every run), the kernel skill must take kernel_ref from the runner, release-policy "
                     "version_fields need prompt_digest, budget.request_bounds needs max_input_tokens and F4-AT-28 must measure the prompt budget")
    # G14 scope of the 90 % key stop (budgets.yaml#openrouter.admission_classes, L4-08, P-84): "non-critical" is a defined class —
    # every admission by default (critical empty, noncritical '*'); a critical entry names an existing workflow step of that agent and
    # an unknown entry rejects the config; the protective-control effect, the cost-watchdog table and F1-AT-22 use the class
    ac = (((c.get("budgets.yaml") or {}).get("openrouter") or {}).get("admission_classes")) or {}
    crit = ac.get("critical")
    res14 = ("the proxy resolves the class from the run token (workflow_id, step_id) or, for HERMES_LLM_PROXY_WORKFLOW_TOKEN, from the CMO run registered by "
             "amt-workflow; a request without either (CMO chat, media job, gateway Jev call) is noncritical")   # closed value (REVIEW_B34 #2, #9, P-101)
    report.check("G14", isinstance(crit, list) and ac.get("noncritical") == ["*"] and ac.get("unknown_entry") == "reject_config_at_load" and ac.get("resolution") == res14,
                 "budgets.yaml#openrouter.admission_classes needs critical (a list), noncritical ['*'], unknown_entry reject_config_at_load and the closed resolution rule "
                 "(token-less requests are noncritical; the CMO workflow token resolves through the registered run)")
    agent_names = set(((c.get("budgets.yaml") or {}).get("openrouter") or {}).get("shares_minor") or {}) - {"reserve"}
    for entry in crit if isinstance(crit, list) else []:
        m = re.fullmatch(r"([a-z_-]+):(WF-[BEO]\d{2}):(S\d{2}|\*)", str(entry))
        wf = (c.get("_workflows") or {}).get(f"{m.group(2)}.yaml") if m else None

        def runs(st, agent):
            ex = st.get("executor") or {}
            return ex.get("type") == "agent" and (ex.get("ref") == agent or agent in (ex.get("any_of") or []))
        steps = [st for st in (wf or {}).get("steps", []) if m and runs(st, m.group(1)) and (m.group(3) == "*" or st.get("id") == m.group(3))]
        report.check("G14", bool(m) and m.group(1) in agent_names and bool(steps),
                     f"budgets.yaml#openrouter.admission_classes.critical entry {entry} must be agent:WF-xx:Sxx (or :*) naming an existing step that agent runs")
    cref14 = ac.get("critical_decision_ref")
    dl14 = root / "00_Decisions" / "DECISION_LOG.md"
    owner14 = bool(re.fullmatch(r"Q\d+(?:\.\d+)?", str(cref14))) and any(
        l.startswith(f"| {cref14} |") and "✅" in l for l in (dl14.read_text(encoding="utf-8").split("\n") if dl14.exists() else []))
    report.check("G14", "critical_decision_ref" in ac and (not crit or owner14),
                 f"budgets.yaml#openrouter.admission_classes: critical entries {crit} narrow the 90 % key stop, so critical_decision_ref must name an owner ✅ Q-ID "
                 f"of DECISION_LOG (got {cref14!r}; a ◇ proposal is not enough; rule strength, P-98)")
    eff = next((str(pc.get("effect", "")) for pc in (ops.get("protective_controls") or []) if isinstance(pc, dict) and pc.get("id") == "proxy_admission_pause"), "")
    report.check("G14", "admission_classes" in eff, "operations.yaml protective_controls proxy_admission_pause effect must name the admission class (budgets.yaml#openrouter.admission_classes)")
    if docs:
        obs = (root / "03_Architecture" / "OBSERVABILITY.md")
        orow = next((l for l in (obs.read_text(encoding="utf-8").split("\n") if obs.exists() else []) if l.startswith("| Kalit ≥ `key_noncritical_stop_pct` |")), "")
        report.check("G14", "admission_classes" in orow and "admission_classes" in doc_row("05_Build_Phases/F1_Platform.md", "F1-AT-22"),
                     "OBSERVABILITY §3 key-stop row and F1-AT-22 must use budgets.yaml#openrouter.admission_classes")
    # G15 command lifecycle when an agent stops mid-run (execution-policy.yaml#review_ttl, #orphan_cancel, L4-07, P-85): an unreviewed
    # item expires at the Q32 TTL from creation and releases its hold (never auto-approved); commands of a step that ended without an
    # accepted submit_output are cancelled (step_incomplete) so a half-built change set is never presented; DATA_MODEL §6.2 copies the
    # extra transitions exactly ("aynan") and lists both reason codes
    ep = c.get("execution-policy.yaml") or {}
    extra = [str(x) for x in ep.get("extra_transitions") or []]
    rt, oc = ep.get("review_ttl") or {}, ep.get("orphan_cancel") or {}
    cs_pol = (c.get("approval-policy.yaml") or {}).get("change_set") or {}
    href = str(rt.get("hours_ref", ""))
    report.check("G15", any(x.startswith("pending_review -> expired (review_ttl") for x in extra) and any("-> cancelled (step_incomplete" in x for x in extra)
                 and rt.get("basis") == "created_at" and href == "approval-policy.yaml#change_set.approval_ttl_hours" and type(cs_pol.get("approval_ttl_hours")) is int
                 and rt.get("auto_approve") is False and rt.get("reservation") == "release" and rt.get("reason_code") == "review_ttl"
                 and oc.get("writer") == "amt_gateway" and oc.get("reason_code") == "step_incomplete" and oc.get("reservation") == "release",
                 "execution-policy.yaml: pending_review -> expired (review_ttl, created_at + change_set.approval_ttl_hours, never auto-approved, hold released) and "
                 "pending_review|pending_approval -> cancelled (step_incomplete, amt_gateway, hold released) are required in extra_transitions, review_ttl and orphan_cancel")
    if docs:
        dmf = root / "03_Architecture" / "DATA_MODEL.md"
        dmt = dmf.read_text(encoding="utf-8") if dmf.exists() else ""
        mblock = re.search(r"`extra_transitions` bilan aynan:\s*```text\n(.*?)```", dmt, re.S)
        doc_extra = [l.strip() for l in mblock.group(1).splitlines() if l.strip()] if mblock else []
        rc_line = next((l for l in dmt.split("\n") if l.startswith("`reason_code` qiymatlari:")), "")
        report.check("G15", doc_extra == extra and "`review_ttl`" in rc_line and "`step_incomplete`" in rc_line and bool(doc_row("05_Build_Phases/F3_Integrations.md", "F3-AT-33")),
                     "DATA_MODEL §6.2 must copy execution-policy.yaml extra_transitions exactly and list the review_ttl and step_incomplete reason codes; F3-AT-33 must test them")
    # G16 reservation sizing (budgets.yaml#openrouter.reservation_sizing, L4-10, P-86): one request's upper bound fits max_cost_minor and
    # all open holds of a role (max_concurrency x upper bound) fit the share_warn_pct..share_stop_pct band of its share, so holds alone
    # cannot exhaust a share; every LLM share role is covered; an over-limit request queues and ends with a non-SDK-retried code; an
    # uncertain request keeps its slot and is settled by the OpenRouter generation record, never released as free credit; F1-AT-30
    # computes the rules and llm-proxy refuses to ACK a revision that breaks one
    orr = (c.get("budgets.yaml") or {}).get("openrouter") or {}
    rs = orr.get("reservation_sizing") or {}
    us = rs.get("uncertain_settlement") or {}
    llm_roles = set((orr.get("shares_minor") or {})) - {"media_generation", "reserve"}
    band_ok = isinstance(orr.get("share_warn_pct"), int) and isinstance(orr.get("share_stop_pct"), int) and 0 < orr["share_warn_pct"] < orr["share_stop_pct"] <= 100
    conc = str(rs.get("concurrent_rule", ""))
    hold_end = str(us.get("hold_end", ""))
    alert_codes = set(re.findall(r"\b(ALERT_[A-Z0-9_]+)\b", hold_end + " " + str(rs.get("revision_rule", ""))))
    canon16 = {  # REVIEW_B34 #1/#9, P-99: the worst-case pricing text is a closed value; any change is a reviewed validator change
        "upper_bound": "max_input_tokens x the highest input rate the request can incur + max_output_tokens x the output rate of the priced model",
        "input_rate_rule": "no cache_control in the request: the base input rate; cache_control with the default 5-minute TTL: 1.25 x the base input rate; "
                           "a 1-hour or unknown TTL: 2 x the base input rate (VR-43); the cache-read rate is never used for a hold",
        "priced_model": "the models.assignments slot of the role; a build-eval call on a candidate model uses that candidate pricing revision, "
                        "and a call with no pricing revision is refused with price_unknown",
        "settlement_rule": "settle at ceil(total_cost x 100) minor per request (the actual price, cache reads and writes included); never rounded down",
        "single_rule": "upper_bound_minor <= max_cost_minor of the role (budget.request_bounds)",
    }
    canon16.update({  # REVIEW_B34 #6, #8, #14, P-101: the band is per allowance and in money; an uncertain request frees its slot after one tick
        "concurrent_rule": "for every allowance a hold is checked against (an agent share, a CMO part, the media share): the open holds of that allowance "
                           "(in-flight and unsettled, LLM and media) plus the new upper bound <= the allowance x (share_stop_pct - share_warn_pct) / 100",
        "in_flight_rule": "at most max_concurrency requests of a role (per model slot for the reviewer) are in flight at once",
        "uncertain_hold": "an uncertain request frees its concurrency slot after one cost-watchdog tick; its money hold stays in the band until it is settled",
    })
    hold_end16 = ("the hold stays at the upper bound (never free credit) and keeps counting in the band until the daily provider-usage reconciliation settles it; "
                  "ALERT_AGENT_ERROR with reason uncertain_hold_expired")
    bad16 = sorted(k for k, v in canon16.items() if rs.get(k) != v)
    bad16 += [] if (rs.get("uncertain_settlement") or {}).get("hold_end") == hold_end16 else ["uncertain_settlement.hold_end"]
    bad16 += [] if rs.get("band_allowances") == ["agent_share", "cmo_part", "media_share"] else ["band_allowances"]
    bad16 += [] if set(rs.get("applies_to") or []) == set((orr.get("shares_minor") or {})) - {"reserve"} else ["applies_to"]
    bad16 += [] if "uncertain_keeps_slot" not in rs else ["uncertain_keeps_slot (replaced by uncertain_hold)"]
    report.check("G16", not bad16 and orr.get("share_warn_pct") == 80 and orr.get("share_stop_pct") == 100,
                 f"budgets.yaml#openrouter.reservation_sizing must keep the worst-case pricing values exactly (changed or missing: {bad16}) and the ★ band "
                 f"share_warn_pct 80 / share_stop_pct 100 (now {orr.get('share_warn_pct')} / {orr.get('share_stop_pct')})")
    report.check("G16", bool(rs) and {"max_input_tokens", "max_output_tokens"} <= set(re.findall(r"max_[a-z_]+", str(rs.get("upper_bound", ""))))
                 and "max_cost_minor" in str(rs.get("single_rule", "")) and band_ok
                 and rs.get("over_limit_request") == "queue_in_proxy"
                 and us.get("method") == "openrouter_generation_lookup" and str(us.get("endpoint", "")).startswith("GET /api/v1/generation?id=") and "uncertain_settlement_hold_hours" in str(us.get("when", ""))
                 and "ALERT_AGENT_ERROR" in alert_codes and "ALERT_CONFIG_ACK" in alert_codes and alert_codes <= codes
                 and rs.get("check") == "F1-AT-30" and "does not ACK" in str(rs.get("revision_rule", "")),
                 "budgets.yaml#openrouter.reservation_sizing: upper bound from max_input_tokens and max_output_tokens, <= max_cost_minor, all open holds "
                 "max_concurrency x upper_bound_minor <= shares_minor[role] x (share_stop_pct - share_warn_pct) / 100 for every LLM share role, "
                 "queue_in_proxy, uncertain_keeps_slot, settlement by openrouter_generation_lookup (/api/v1/generation) inside uncertain_settlement_hold_hours, "
                 "hold_end never free credit with catalogued alerts, check F1-AT-30 and no ACK for a breaking revision are required")
    if docs:
        gw = root / "03_Architecture" / "GUARDRAIL_GATEWAY.md"
        gtxt = gw.read_text(encoding="utf-8") if gw.exists() else ""
        sec101 = gtxt.split("### 10.1", 1)[-1].split("\n## ", 1)[0]
        slot_row = re.search(r"^\|\s*`slot_wait_exceeded`\s*\|\s*(\d{3})\s*\|", sec101, re.M)
        sec75 = gtxt.split("### 7.5", 1)[-1].split("\n## ", 1)[0]
        f130 = doc_row("05_Build_Phases/F1_Platform.md", "F1-AT-30")
        cc = root / "11_Production_Contracts" / "CONFIG_CONTRACT.md"
        rb = next((l for l in (cc.read_text(encoding="utf-8").split("\n") if cc.exists() else []) if l.startswith("| `budget.request_bounds` |")), "")
        adr3_16 = root / "04_ADR" / "ADR-003-openrouter-single-key-watchdog.md"
        item6 = next((l for l in (adr3_16.read_text(encoding="utf-8").split("\n") if adr3_16.exists() else []) if l.startswith("6. Nazorat qoidalari")), "")
        report.check("G16", "cache-read narxi hold’da hech qachon ishlatilmaydi" in sec75 and "`ceil(total_cost × 100)` minor" in sec75
                     and all(t in f130 for t in ("sovuq kesh", "actual ≤ reserved", "`ceil(total_cost × 100)` minor", "80% idan oshmaguncha", "`price_unknown`"))
                     and "ulush 80% — alert; ulush 100%" in item6,
                     "GUARDRAIL §7.5 must state that the cache-read rate never prices a hold and the ceil settlement; F1-AT-30 must test the cold-cache burst "
                     "(actual ≤ reserved), the ceil settlement, the 80 % band and price_unknown for an unpriced candidate; ADR-003 item 6 must keep the ★ 80 %/100 % values")
        report.check("G16", bool(slot_row) and slot_row.group(1) == "423" and "reservation_sizing" in sec75 and "/api/v1/generation" in sec75
                     and all(t in f130 for t in ("slot_wait_exceeded", "/api/v1/generation", "uncertain_hold_expired", "ALERT_CONFIG_ACK"))
                     and "reservation_sizing" in rb,
                     "GUARDRAIL §10.1 needs the slot_wait_exceeded row (HTTP 423), §7.5 the reservation_sizing rule with the generation lookup, "
                     "F1-AT-30 must test the queue code, the generation settlement, the hold-end alert and the refused ACK, and the CONFIG_CONTRACT "
                     "budget.request_bounds row must bind its values to reservation_sizing")
    # G17 Hermes memory and conversation store (runtime-isolation.yaml#hermes_memory, L4-12, P-87): the memory keys are pinned with the
    # version (write approval on, background review off, character limits recorded), session_search is hidden, staged writes are
    # approved only from the owner DM one id at a time and a write staged in a non-owner session is rejected by the deterministic adapter
    # (fail-closed fallback: memory hidden, release-only); the conversation store and the memory files are privacy datasets with
    # retention; ADR-004 item 3 copies every pin; every privacy dataset is in the SECURITY.md custody table
    hm = (c.get("runtime-isolation.yaml") or {}).get("hermes_memory") or {}
    pins, sw = hm.get("pins") or {}, hm.get("staged_writes") or {}
    pv_ds = {d.get("dataset"): d for d in ((c.get("privacy-policy.yaml") or {}).get("datasets") or []) if isinstance(d, dict)}
    store_ok = all(isinstance(hm.get(k), dict) and (pv_ds.get(hm[k].get("dataset")) or {}).get("custodian") == "hermes"
                   and (pv_ds.get(hm[k].get("dataset")) or {}).get("host") == "AMT PC" and hm[k].get("retention_ref") == "privacy.retention"
                   and (pv_ds.get(hm[k].get("dataset")) or {}).get("retention_ref") == "privacy.retention" for k in ("conversation_store", "memory_files"))
    pins17 = {"memory.memory_enabled": True, "memory.memory_char_limit": 2200, "memory.user_char_limit": 1375, "memory.write_approval": True,
              "skills.write_approval": True, "auxiliary.background_review.enabled": False, "memory.user_profile_enabled": False, "memory.provider": "builtin"}   # VR-39, VR-44
    sw17 = {"approver": "owner", "in_chat_commands": "dropped_for_every_sender", "approval_channel": "ops_bot_typed_callback", "bulk_approve": "refused",
            "non_owner_origin": "rejected", "enforcement": "fail_closed",
            "typed_callback": "the ops-bot owner typed callback (P-14) carries exactly one staged id and passes the same origin rule",
            "fallback": "when the pinned version cannot enforce any staged_writes rule fail-closed (command drop, origin attribution, one id per callback), "
                        "agent.disabled_toolsets also hides memory and MEMORY.md/USER.md change only by release (WF-E04)"}
    bad17 = sorted([k for k, v in pins17.items() if pins.get(k) != v or type(pins.get(k)) is not type(v)] + [f"staged_writes.{k}" for k, v in sw17.items() if sw.get(k) != v])
    report.check("G17", not bad17 and hm.get("config_file") == "read_only"
                 and "session_search" in (hm.get("hidden_tools") or []) and store_ok
                 and {"F4-AT-24", "F4-AT-29"} <= set(hm.get("tests") or []),
                 f"hermes_memory values that differ from the closed set (REVIEW_B34 #3, #9, #17; VR-39, VR-44): {bad17}; config_file must be read_only; "
                 "runtime-isolation.yaml#hermes_memory: pins (memory_enabled and both write approvals on, background_review off, integer character limits), "
                 "session_search hidden, staged writes owner-only from the owner DM, no bulk approve, non-owner origin rejected, a release-only fail-closed "
                 "fallback, conversation store and memory files as hermes/AMT PC privacy datasets with privacy.retention, tests F4-AT-24 and F4-AT-29")
    # inbound lead-PII filter (REVIEW_B34 #4, P-100): staff DM text and voice-note transcripts are redacted before Hermes stores or sends
    # them, fail-closed; the conversation store and the OpenRouter flow say so; the conflict with Q28/Q62 is recorded (C-43)
    inf = (c.get("runtime-isolation.yaml") or {}).get("cmo_telegram_inbound_filter") or {}
    pv17 = c.get("privacy-policy.yaml") or {}
    llm_flow = next((f for f in (pv17.get("off_host_flows") or []) if isinstance(f, dict) and f.get("flow") == "LLM and media requests"), {})
    report.check("G17", inf.get("blocks") == ["lead_pii_patterns"] and inf.get("on_hit") == "redact_and_alert" and inf.get("enforcement") == "fail_closed"
                 and inf.get("alert") == "ALERT_SECURITY_PII" and inf.get("alert") in codes and inf.get("test") == "F4-AT-29" and "transcript passes the same filter" in str(inf.get("voice_notes", ""))
                 and "no lead PII - the inbound filter redacts it before storage" in str((pv_ds.get("hermes_sessions") or {}).get("fields", ""))
                 and "CMO chat text after the inbound lead-PII filter" in str(llm_flow.get("data", "")),
                 "runtime-isolation.yaml#cmo_telegram_inbound_filter must block lead_pii_patterns with redact_and_alert, fail_closed, ALERT_SECURITY_PII, F4-AT-29 and the voice-note "
                 "transcript; privacy-policy hermes_sessions must say no lead PII and the OpenRouter flow must name CMO chat text after the filter (Q28, Q62)")
    if docs:
        adr4 = root / "04_ADR" / "ADR-004-hermes-cmo-no-openclaw.md"
        atxt = adr4.read_text(encoding="utf-8") if adr4.exists() else ""
        bad_pin = []
        for k, v in pins.items():
            want = ("on" if v else "off") if isinstance(v, bool) else str(v)
            row = next((l for l in atxt.split("\n") if l.strip().startswith(f"| `{k}` |")), "")
            if not row or not row.split("|")[2].strip().startswith(want):
                bad_pin.append(k)
        f424, f429 = doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-24"), doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-29")
        sec = root / "03_Architecture" / "SECURITY.md"
        stxt = sec.read_text(encoding="utf-8") if sec.exists() else ""
        custody = stxt.split("**PII custody inventari.**", 1)[-1].split("\n\n", 2)[1] if "**PII custody inventari.**" in stxt else ""
        missing_ds = sorted(n for n in pv_ds if f"| `{n}` |" not in custody)
        ss_row = next((l for l in atxt.split("\n") if l.strip().startswith("| `session_search` tool’i |")), "")
        report.check("G17", not bad_pin and ss_row.split("|")[2].strip().startswith("yashirin") if ss_row.count("|") >= 3 else False,
                     "ADR-004 item 3 must show session_search as yashirin (hidden), like runtime-isolation.yaml#hermes_memory.hidden_tools")
        oi17 = root / "00_Decisions" / "OPEN_ITEMS.md"
        c43 = next((l for l in (oi17.read_text(encoding="utf-8").split("\n") if oi17.exists() else []) if l.startswith("| C-43 |")), "")
        report.check("G17", "cmo_telegram_inbound_filter" in c43 and "Q28" in c43 and "Q62" in c43 and "G17" in c43
                     and "`state.db`ga ham, llm-proxy so‘roviga ham yetmaydi" in f429 and "filtr xatosida xabar tashlanadi" in f429,
                     "OPEN_ITEMS §4 C-43 must record the Q28/Q62 conflict and the inbound filter; F4-AT-29 must prove a lead phone reaches neither state.db nor llm-proxy and that a filter error drops the message")
        report.check("G17", "/memory approval off" in f424 and "fail-closed" in f424 and "faqat ops-bot typed callback yo‘li ishlaydi" in f424,
                     "F4-AT-24 must test /memory approval off from the owner DM, the fail-closed enforcement and the ops-bot typed callback as the only approval path")
        report.check("G17", not bad_pin and "| `session_search` tool’i |" in atxt and "/memory approve all" in f424 and "hermes_memory.pins" in f424
                     and "session_search" in f429 and "retention" in f429 and not missing_ds,
                     f"ADR-004 item 3 must copy every hermes_memory pin with its value (wrong or missing: {bad_pin}) and the hidden session_search; F4-AT-24 must "
                     f"test the bulk approve and the pin read-back, F4-AT-29 the hidden session_search and retention; privacy datasets missing from the SECURITY.md custody table: {missing_ds}")
    # G18 runner sessions are not memory (runtime-isolation.yaml#runner_contract, L4-13, P-88; input bound of L4-10): a fresh session
    # per step (resume only inside the step), an ephemeral workspace, a read-only home with Claude Code memory disabled, a transcript
    # bounded by max_input_tokens with a pre-dispatch refusal (input_over_bound, never sent), durable guidance only from released lessons
    rc = (c.get("runtime-isolation.yaml") or {}).get("runner_contract") or {}
    rs18 = (((c.get("budgets.yaml") or {}).get("openrouter") or {}).get("reservation_sizing")) or {}
    report.check("G18", rc.get("session_policy") == "fresh_per_step" and rc.get("workspace") == "ephemeral_per_step" and rc.get("home_readonly") is True
                 and rc.get("claude_code_memory") == "disabled" and rc.get("transcript_bound") == "budget.request_bounds.max_input_tokens"
                 and rc.get("long_term_memory") == "released_lessons_only" and rc.get("session_test") == "F4-AT-30"
                 and "input_over_bound" in str(rs18.get("input_rule", "")) and "max_input_tokens" in str(rs18.get("input_rule", ""))
                 and "never dispatched" in str(rs18.get("input_rule", "")) and "provider-reported input_tokens" in str(rs18.get("input_count", "")),
                 "runner_contract needs session_policy fresh_per_step, workspace ephemeral_per_step, home_readonly true, claude_code_memory disabled, "
                 "transcript_bound budget.request_bounds.max_input_tokens, long_term_memory released_lessons_only and session_test F4-AT-30; "
                 "reservation_sizing needs the input_rule (input_over_bound, never dispatched) and an input_count never below the provider-reported input_tokens")
    env18 = {"CLAUDE_CONFIG_DIR": "per_step_tmpfs", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "budget.request_bounds.max_output_tokens",
             "ANTHROPIC_DEFAULT_HAIKU_MODEL": "role_slot_model", "API_TIMEOUT_MS": "600000",
             "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "max(100000, max_input_tokens)",
             "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "floor(100 x (max_input_tokens - max_output_tokens) / CLAUDE_CODE_AUTO_COMPACT_WINDOW)"}   # VR-45, REVIEW_B34 #7, #19, P-102
    cc18 = rc.get("claude_code_env") or {}
    bad18 = sorted(k for k, v in env18.items() if str(cc18.get(k)) != v) + sorted(set(cc18) - set(env18))
    comp18 = ("inside a step Claude Code compacts before a request reaches max_input_tokens (claude_code_env); a compaction call is an ordinary llm-proxy request "
              "with request_kind compaction, counted in the role share; nothing is carried across steps (session_policy)")
    ws18 = ("every API-server run that amt-workflow starts uses a new Hermes session id, so a run never loads an earlier transcript (VR-44); "
            "Hermes compression calls go through llm-proxy on the run token and count in the workflow part")
    report.check("G18", not bad18 and rc.get("compaction_policy") == comp18
                 and ((c.get("runtime-isolation.yaml") or {}).get("hermes_memory") or {}).get("workflow_sessions") == ws18,
                 f"runner_contract.claude_code_env must hold exactly the pinned client settings (wrong, missing or extra: {bad18}); compaction_policy and "
                 "hermes_memory.workflow_sessions must keep their closed values (REVIEW_B34 #7, #19, P-102)")
    if docs:
        gw18 = root / "03_Architecture" / "GUARDRAIL_GATEWAY.md"
        sec101_18 = gw18.read_text(encoding="utf-8").split("### 10.1", 1)[-1].split("\n## ", 1)[0] if gw18.exists() else ""
        ib = re.search(r"^\|\s*`input_over_bound`\s*\|\s*(\d{3})\s*\|", sec101_18, re.M)
        arch = root / "03_Architecture" / "ARCHITECTURE.md"
        sec4 = md_section(arch.read_text(encoding="utf-8"), "4. Agent runner integration gate") if arch.exists() else None
        f4 = root / "05_Build_Phases" / "F4_Agents.md"
        risk = next((l for l in (f4.read_text(encoding="utf-8").split("\n") if f4.exists() else []) if l.startswith("| Paperclip session reset")), "")
        a28 = root / "04_ADR" / "ADR-028-improvement-memory-provenance.md"
        f430 = doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-30")
        report.check("G18", bool(sec4) and "step’lar yoki Paperclip heartbeat’lari orasida hech qachon" in sec4 and "`runner_contract.claude_code_env`" in sec4
                     and "`request_kind: compaction`" in sec4 and "step’lararo resume rad, faqat step ichidagi retry" in f430
                     and "`input_over_bound` yo‘q" in f430 and "yangi sessiya ID’si oladi" in f430,
                     "ARCHITECTURE §4 must keep 'never across steps or Paperclip heartbeats' and name the pinned client env and compaction requests; F4-AT-30 must refuse a "
                     "cross-step resume and test the long step (compaction, no input_over_bound) and a fresh Hermes session per CMO run")
        report.check("G18", bool(ib) and ib.group(1) == "413" and bool(sec4) and "session_policy" in sec4 and "claude_code_memory" in sec4
                     and "session_policy" in risk and a28.exists() and "runner_contract" in a28.read_text(encoding="utf-8")
                     and "~/.claude/**" in f430 and "resume" in f430,
                     "GUARDRAIL §10.1 needs input_over_bound (HTTP 413); ARCHITECTURE §4, the F4 session-reset risk row and ADR-028 must name the runner "
                     "session policy; F4-AT-30 must test writes to ~/.claude/** and a cross-step resume")
    # G19 share parts (budgets.yaml#openrouter.sub_shares, L4-16, P-89; REVIEW_B34 #2, P-101): the CMO share is split into exactly chat
    # and workflow, summing to the parent share; a request is assigned by its proxy token (Hermes forwards no run token), workflow runs
    # are registered with llm-proxy for attribution, a part stop refuses only that part and is not a proxy_admission_causes member while
    # the parent-share stop keeps its global effect, an exhausted chat answers without an LLM call; every value is a closed string
    orr19 = (c.get("budgets.yaml") or {}).get("openrouter") or {}
    subs = orr19.get("sub_shares") or {}
    cmo19 = subs.get("cmo") or {}
    canon19 = {
        "parts": ["chat", "workflow"], "sum_rule": "chat + workflow = shares_minor.cmo", "values_ref": "budget.request_bounds", "chat_limits_ref": "budget.request_bounds",
        "resolution": "by proxy token: HERMES_LLM_PROXY_TOKEN (the Telegram chat path and voice-note STT) draws on chat; HERMES_LLM_PROXY_WORKFLOW_TOKEN "
                      "(Hermes API-server runs that amt-workflow starts with provider cmo-workflow) draws on workflow",
        "provider_selection": "the Hermes config holds two providers on the llm-proxy /openai path, cmo-chat and cmo-workflow; the Telegram gateway uses cmo-chat "
                              "and every API-server run names provider cmo-workflow per request (VR-44; F4-AT-31 [T])",
        "run_attribution": "amt-workflow registers the CMO workflow run with llm-proxy before it starts it; cmo-workflow requests are attributed to that run "
                           "(ai_requests run_id, step_id); one CMO workflow run at a time",
        "thresholds": "share_warn_pct and share_stop_pct apply to each part",
        "part_stop": "a stopped part is recorded in agent_runtime_state as cmo.chat or cmo.workflow; only that part is refused (agent_paused, reason part_stop) "
                     "and it is not a proxy_admission_causes member; the parent share stop (both parts used up) keeps its global share_stop effect",
        "part_alert": "ALERT_BUDGET_80 names the part; a part stop raises ALERT_BUDGET_100 with reason part_stop, which is not a proxy_admission_pause",
        "resume": "owner /agent resume cmo.chat or /agent resume cmo.workflow (agent_resume, typed code)",
        "chat_exhausted": "the Hermes Telegram adapter answers with a fixed notice without an LLM call; the workflow part continues",
        "fallback": "if F4-AT-31 cannot prove that the two Hermes paths keep their own tokens, the split stays inactive and only the per-person chat limits bound chat",
        "test": "F4-AT-31",
    }
    bad19 = sorted(k for k, v in canon19.items() if cmo19.get(k) != v)
    env19 = root / "09_Config_Templates" / "env.example"
    env19t = env19.read_text(encoding="utf-8") if env19.exists() else ""
    report.check("G19", set(subs) == {"cmo"} and not bad19 and "part_stop" in (orr19.get("pause_reason_codes") or [])
                 and all(re.search(rf"^{t}=", env19t, re.M) for t in ("HERMES_LLM_PROXY_TOKEN", "HERMES_LLM_PROXY_WORKFLOW_TOKEN")),
                 f"budgets.yaml#openrouter.sub_shares.cmo values that differ from the closed set (REVIEW_B34 #2, #9, P-101): {bad19}; sub_shares holds only cmo, "
                 "pause_reason_codes needs part_stop and env.example both Hermes proxy tokens")
    if docs:
        cc19 = root / "11_Production_Contracts" / "CONFIG_CONTRACT.md"
        rb19 = next((l for l in (cc19.read_text(encoding="utf-8").split("\n") if cc19.exists() else []) if l.startswith("| `budget.request_bounds` |")), "")
        cmo_md = root / "02_Team_Charter" / "agents" / "CMO.md"
        ulush = next((l for l in (cmo_md.read_text(encoding="utf-8").split("\n") if cmo_md.exists() else []) if l.startswith("| Ulush |")), "")
        dm19 = root / "03_Architecture" / "DATA_MODEL.md"
        ars = next((l for l in (dm19.read_text(encoding="utf-8").split("\n") if dm19.exists() else []) if l.startswith("`agent_runtime_state`:")), "")
        f431 = doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-31")
        tg19 = root / "03_Architecture" / "TELEGRAM.md"
        b100 = next((l for l in (tg19.read_text(encoding="utf-8").split("\n") if tg19.exists() else []) if l.startswith("| `ALERT_BUDGET_100` |")), "")
        report.check("G19", "HERMES_LLM_PROXY_WORKFLOW_TOKEN" in ulush and "faqat o‘sha qism rad (`part_stop`)" in ulush and "`part_stop`" in ars
                     and "qolgan besh agent admission’da qoladi" in f431 and "HERMES_LLM_PROXY_WORKFLOW_TOKEN" in f431 and "`part_stop` sababi" in b100,
                     "the CMO Ulush row, DATA_MODEL agent_runtime_state, the ALERT_BUDGET_100 row and F4-AT-31 must state the token split, the local part stop "
                     "(part_stop, not proxy_admission_pause) and that the other five agents stay admitted")
        report.check("G19", all(t in rb19 for t in ("chat_sub_share_minor", "chat_daily_messages_per_person", "chat_max_session_turns")) and "sub_shares.cmo" in ulush
                     and "cmo.chat" in ars and "WF-B06" in f431 and "LLM chaqirmasdan" in f431 and "`chat + workflow = shares_minor.cmo`" in f431,
                     "the CONFIG_CONTRACT budget.request_bounds row must list chat_sub_share_minor, chat_daily_messages_per_person and chat_max_session_turns; "
                     "the CMO Ulush row must name sub_shares.cmo; DATA_MODEL agent_runtime_state must hold cmo.chat; F4-AT-31 must test WF-B06 during a "
                     "stopped chat part, the LLM-free notice and the sum rule")
    # G20 media attribution and bounds (budgets.yaml#media_generation, L4-17, P-90): one reservation owned by media_generation, checked in
    # one transaction against exactly the key cap, the media share and the requesting agent's share (the stricter reading, C-40); the
    # requesting agents are exactly the agents whose allowlist holds a media.* tool; per-job, per-month and concurrency bounds are owner
    # values (null in the template or integers); every job needs a pricing revision; the skill, the contract and F4-AT-32 agree
    mg = (c.get("budgets.yaml") or {}).get("media_generation") or {}
    at20 = mg.get("attribution") or {}
    media_agents = sorted(a for a, spec in ((c.get("approval-policy.yaml") or {}).get("agents") or {}).items()
                          if any(str(t).startswith("media.") for t in ((spec or {}).get("tools") or [])))
    bounds20 = ("max_cost_minor", "max_video_seconds", "max_video_seconds_per_month", "max_concurrent_jobs")
    report.check("G20", at20.get("reservation_owner") == "media_generation" and at20.get("allowance_checks") == ["key_cap", "media_generation", "requesting_agent_share"]
                 and sorted(at20.get("requesting_agents") or []) == media_agents and bool(media_agents)
                 and all(k in mg and (mg[k] is None or (type(mg[k]) is int and mg[k] > 0)) for k in bounds20) and mg.get("price_revision_required") is True,
                 f"budgets.yaml#media_generation: reservation_owner media_generation, allowance_checks exactly [key_cap, media_generation, requesting_agent_share], "
                 f"requesting_agents = the agents with a media.* tool {media_agents}, owner bounds {list(bounds20)} (null or positive integers) and price_revision_required")
    if docs:
        sk20 = root / "08_Skills" / "ad-creative-production" / "SKILL.md"
        sk20t = sk20.read_text(encoding="utf-8") if sk20.exists() else ""
        cc20 = root / "11_Production_Contracts" / "CONFIG_CONTRACT.md"
        bm = next((l for l in (cc20.read_text(encoding="utf-8").split("\n") if cc20.exists() else []) if l.startswith("| `budget.media` |")), "")
        oi20 = root / "00_Decisions" / "OPEN_ITEMS.md"
        c40 = next((l for l in (oi20.read_text(encoding="utf-8").split("\n") if oi20.exists() else []) if l.startswith("| C-40 |")), "")
        f432 = doc_row("05_Build_Phases/F4_Agents.md", "F4-AT-32")
        shape20 = re.search(r"`\{([^}]*)\}`", bm)
        report.check("G20", "media_generation.attribution" in sk20t and "(global, agent and media shares)" not in sk20t
                     and bool(shape20) and {x.strip() for x in shape20.group(1).split(",")} == set(bounds20)
                     and "media_generation.attribution" in c40 and "G20" in c40 and "allowance_exhausted" in f432 and "bir marta" in f432,
                     "ad-creative-production §7 must point to media_generation.attribution (one reservation, three allowances), the CONFIG_CONTRACT budget.media "
                     "row must list the four bounds, OPEN_ITEMS §4 C-40 must record the applied rule and G20, and F4-AT-32 must test the agent-share refusal and single counting")
    # G21 lessons and golden copy inside a prompt budget (improvement-memory-record.schema.json, prompt-manifest.yaml, L4-18, P-91): the
    # schema refuses a guidance-eligible record that is not accepted or lacks a lesson (<= 600 characters), a scope or a review_by date
    # (checked by validating synthetic records, not by reading the schema text); every call takes at most 15 scoped lessons newest first
    # inside a declared token bound counted in max_fixed_tokens, and the golden-copy few-shot is bounded per pipeline x format for exactly
    # the roles that use it
    ims = (c.get("_schemas") or {}).get("improvement-memory-record.schema.json")
    try:
        import jsonschema
        imv = jsonschema.Draft202012Validator(ims) if isinstance(ims, dict) else None
    except (ImportError, AttributeError):
        imv = None   # W00 already reports a missing or old jsonschema
    if imv is not None:
        base21 = {"record_id": "00000000-0000-4000-8000-000000000001", "proposal_id": "UP-1", "source_refs": ["r"], "release_ids": [], "recorded_at": "2026-10-24T00:00:00Z",
                  "problem": "p", "prior_state": "s", "hypothesis": "h", "diff_ref": "d", "cost": {"actual_minor": 0, "currency": "USD"}, "test_evidence": [], "rollout": "r",
                  "observed_result": "o", "verdict": "accepted", "decision_owner": "person:owner", "guidance_eligible": True, "lesson": "a verified rule", "scope": "media-buyer:rent",
                  "status": "active", "review_by": "2027-01-01", "pii_secret_checked": True}
        def ok21(drop=(), **chg):
            rec = {k: v for k, v in base21.items() if k not in drop}
            rec.update(chg)
            return not list(imv.iter_errors(rec))
        bad21 = [name for name, chg in (("lesson null", {"lesson": None}), ("scope null", {"scope": None}), ("review_by null", {"review_by": None}),
                                        ("lesson over 600 characters", {"lesson": "x" * 601}), ("verdict inconclusive", {"verdict": "inconclusive"}),
                                        ("lesson empty", {"lesson": ""})) if ok21(**chg)]
        bad21 += [f"{k} missing" for k in ("lesson", "scope", "review_by") if ok21(drop=(k,))]
        bad21 += [name for name, chg in (("free-text scope", {"scope": "all pipelines, mostly rent"}), ("unknown role scope", {"scope": "owner:rent"}),
                                        ("free-text review_by", {"review_by": "next week"})) if ok21(**chg)]   # REVIEW_B34 #16 grammar
        bad21 += [] if ok21(scope="reviewer") and ok21(scope="cro:sale") else ["valid role or role:pipeline scope refused"]
        report.check("G21", ok21() and ok21(guidance_eligible=False, lesson=None, scope=None, review_by=None, verdict="rejected") and not bad21,
                     f"improvement-memory-record.schema.json must accept a full guidance record and a non-eligible one, and refuse an eligible record with: {bad21}")
    pm21 = c.get("prompt-manifest.yaml") or {}
    les = [e for e in (pm21.get("common_eager") or []) if isinstance(e, dict) and e.get("runtime") == "knowledge/lessons/"]
    gc_roles = sorted(r for r, spec in (pm21.get("roles") or {}).items()
                      if any(isinstance(e, dict) and e.get("runtime") == "knowledge/golden-copy/" for e in ((spec or {}).get("on_demand") or [])))
    gc_ok = all(type(e.get("max_tokens")) is int and 0 < e["max_tokens"] <= 1500 and "at most 6 examples per pipeline x format" in str(e.get("selection", ""))
                for spec in (pm21.get("roles") or {}).values() for e in ((spec or {}).get("on_demand") or []) if isinstance(e, dict) and e.get("runtime") == "knowledge/golden-copy/")
    sel = str((les[0] if les else {}).get("selection", ""))
    sel21 = ("active guidance_eligible lessons whose scope is the role or role:pipeline of the call (schema scope grammar), newest first, at most 15; "
             "one line gives the count of the other matching lessons, all inside max_tokens; the agent opens knowledge/lessons/ on demand")   # closed (REVIEW_B34 #9, #16)
    report.check("G21", len(les) == 1 and type(les[0].get("max_tokens")) is int and 0 < les[0]["max_tokens"] <= 2000 and sel == sel21
                 and gc_roles == ["creative-studio", "reviewer"] and gc_ok,
                 f"prompt-manifest.yaml: exactly one eager knowledge/lessons/ entry (max_tokens <= 2000; guidance_eligible, scope-matched, newest first, at most 15) "
                 f"and golden copy on demand for exactly creative-studio and reviewer (max_tokens <= 1500, at most 6 per pipeline x format); golden copy roles now {gc_roles}")
    if docs:
        a2821 = root / "04_ADR" / "ADR-028-improvement-memory-provenance.md"
        ev21 = root / "07_Evals" / "EVALS.md"
        fe16 = doc_row("05_Build_Phases/FE_Evolution.md", "FE-AT-16")
        report.check("G21", a2821.exists() and "prompt-manifest.yaml" in a2821.read_text(encoding="utf-8") and ev21.exists()
                     and "ko‘pi bilan 6 ta namuna" in ev21.read_text(encoding="utf-8") and "15 ta" in fe16 and "600 belgidan" in fe16,
                     "ADR-028 must name the prompt-manifest lesson bound, EVALS §3 step 8 the golden-copy bound, and FE-AT-16 must test the 15-lesson bound and the 600-character schema limit")
    # G22 the DECISION_LOG ◇ table stays a table (REVIEW_B12 #11): every P-NN row has exactly 7 cells - a pipe inside a code span must be
    # escaped (\\|), otherwise the row shifts its route and critical-path cells
    if docs:
        dlog = (root / "00_Decisions" / "DECISION_LOG.md").read_text(encoding="utf-8")
        bad_p = [l.split("|")[1].strip() for l in dlog.split("\n") if l.startswith("| P-") and len(re.split(r"(?<!\\)\|", l.strip().strip("|"))) != 7]
        report.check("G22", not bad_p, f"DECISION_LOG ◇ rows must have 7 cells (escape a pipe inside a code span as \\|): {bad_p}")


# ---------------------------------------------------------------- VALIDATION_REPORT.md generation (--write-report)

REPORT_FAMILIES = [
    ("H", "Claude handoff: mavjud server admission/init, immutable review va approval binding, entity selector sxemalari, mustaqil PR review, attempt retry/fence/expiry, qabul qilingan custody transfer, provider snapshot yozuvchisi va usable-point RPO; sintetik fixture runtime PASS emas"),
    ("S", "Tuzilma: YAML yuklanishi, takroriy kalit yo‘qligi, sarlavha, `schema_version`, `bundle_state`, qo‘shtirnoqsiz `: ` satrni mapping’ga aylantirmagan, `, ` matnni bo‘lmagan va ` #` uni izoh bilan kesmagan (S09)"),
    ("M", "Pul: USD 150/oy = 15 000 USD minor va USD 1 500/oy = 150 000 USD minor, ulushlar, provider spending limit, rolling24h ≤ 20%, HG-F4-04 variantlari, agent’li har workflow’da run cap’i va to‘g‘ri xarajat hisobi (M09)"),
    ("A", "Tasdiq siyosati: TTL, never_auto, owner-only action’lar, Reviewer mustaqilligi, Q25 ceiling, Q42 til tekshiruvi, protective pause, Trust Ramp mexanikasi va daraja o‘tishlari (A14), o‘zgarishlar oralig‘i va eksperiment lock’i (A15), protective pauzadan keyingi qayta yoqish faqat owner va never_auto (A16)"),
    ("W", "Workflow ta’riflari: JSON sxema, approval action’lari, testlar va talab havolalari, concurrency va run umri (W09), run umri step timeout yo‘lini va jadval slotlarini qamrashi (W14), bajaruvchi, principal va trigger manbasi reyestrlari (W08), shartli step’lar (W15), tasdiq va dispatch egaligi (W11), boshi berk tarmoq yo‘qligi (W16), handoff rad etilganda chegaralangan yo‘l (W17), ko‘p command’li step holati (W18), parent/child start shartnomasi (W13), handoff konvertining deterministik tekshiruvi (W19), inson step timeout’i eskalatsiya bilan mos (W20), inson vazifasi yakunlanish signali va deadlock yo‘qligi (W21)"),
    ("X", "Ijro siyosati: restore boshlanish rejimi, resume, maintenance hold, capability → profil bog‘lanishi, muhitlar kesishmasligi"),
    ("K", "Kill criteria: Q31 chegaralari, resume, `data_status` lug‘ati, KC seriyasi holat mashinasi (K05); umumiy statistik qaror spec’i va uning iste’molchilari (K04), oldindan ro‘yxatga olingan Step 2 qoidasi (K06), shadow mezonining minimal soni va uzaytirish chegarasi (K07)"),
    ("R", "Readiness: profil DAG’i, bitta kalit — bitta gate, inson javobgarligi, `max_evidence_age`, agent tayyorlovchilar F4_AGENTS’dan, CONFIG_CONTRACT va EVOLUTION_CONTRACT jadvallari bilan moslik, profil sharti bilan rad etiladigan va raqamli chegarali qiymatlar, ma’lumot sifatidagi ruxsat etilgan qiymatlar (R20, C-28, C-29)"),
    ("B", "RBAC: rollar, flag’lar, seed qoidalari"),
    ("V", "Release: build_once_promote, owner-only imzolangan tag, F1 dan `release_approvals` yozuvi, ACK ro‘yxatlari servis reyestriga mos"),
    ("T", "Ritm: `operations.yaml#schedule` yagona manba; workflow timer’lari, jadval slotini nomlagan eskalatsiyalar (T08), sale readiness cutoff va hujjat jadvallari unga mos; har schedule yozuvini o‘sha slotga bog‘langan workflow step’i yoki timer’i, yoki missed-run alert’li job bajaradi, alert kodi TELEGRAM §6.2 katalogida (T11)"),
    ("E", "Self-evolution: auto-release o‘chiq, himoyalangan sirtlar va config qamrovi, engineering byudjeti alohida, resurs slice’lari"),
    ("O", "Owner qarorlari qulfi: Q37 tracking `read_only` trigger’i, Q29.1 hajm chegarasi va uning o‘lchov qoidasi (O08), Q55 lokal snapshot (offsite yo‘q, 7 kun), Q54/Q62 shifrlanmagan disk va diskka yozilmaydigan webhook PII, Q57/Q58 kiruvchi port yo‘q, Q61 Jev pre-screen qoidalari"),
    ("D", "Hujjatlar: havolalar va ID’lar; tool, action, servis reyestri, control op matritsasi, himoya nazoratlari, `/role` buyruqlari, slice va dalil yoshi jadvallari config’ga mos; owner qarorlari matni qulfi; audit topilmalari havolalari; ziddiyatlar reyestri ID’lari (D34), protective pauzadan keyingi qayta yoqish gateway/GT/callback’da (D35)"),
    ("Z", "Versiya va tarix qoldig‘i, 100 baravar noto‘g‘ri pul yozuvi"),
    ("G", "Platforma va integratsiyalar: alert katalogi yopiq, o‘chgan monitorni host aniqlaydi (`monitor_unreachable_alert`), tashqi bog‘liqliklar shartnomasi (`external_dependencies`: mas’ul, env’dagi credential, monitorning ACK’dan oldin saqlashi va mustaqil hostingi, hostlararo PII’siz pull o‘qish va reader egress’i), integratsiya kuzatuvi (`integration_watch`) va amoCRM webhook javob byudjeti, CAPI xato taksonomiyasi (`capi_delivery`: batch va auth xatosi eventni yo‘qotmaydi, yuborilmagan so‘rov qayta yuboriladi, noaniq attempt hold’dan keyin sanaladigan yo‘qotish), off-host oqim inventari (`off_host_flows`: yopiq yozuv, `by` va `direction`, egress’i bor har servis qamrab olingan), config’da vergul tufayli kalitga aylangan matn yo‘q (G07), foydalanuvchi huquqini oladigan amoCRM tokenlari `[user-rights]` va `issuing_user_role` bilan, tor scope da’vosisiz (G08), llm-proxy xato kontraktida SDK o‘zi retry qiladigan HTTP kodi yo‘q va upstream xatosi alohida kod (G09), har allowlist tool’ining yopiq argument sxemasi `schemas/tools/` va Hermes Telegram chiqish filtri (G10), runtime talab va unit-cost modeli (`cost-model.schema.json`: agentlar = ulushlar, kirishlar [D]/[T]/[X] tegi bilan, p90 ulush va kalit cap’i bilan solishtiriladi; F1-AT-13 chaqiruv narxi, `ai_requests` token bo‘linishi; G11), provider pin va prompt cache (`provider_policy`: Claude faqat Anthropic, fallback yo‘q, `data_collection: deny`, `cache_control` o‘zgarmaydi, keshli narx faqat F1-AT-29 isbotlagan yo‘lda; G12), rol bo‘yicha prompt manifesti (`prompt-manifest.yaml`: eager to‘plam = kontrakt, kernel, invariant indeksi, rol prompti va aynan charter skill’lari; taxminiy hajm ≤ `max_fixed_tokens`; butun kontrakt fayllari faqat on demand; `kernel_ref`ni runner yozadi, `prompt_digest`, `max_input_tokens`; G13), kalit 90% to‘xtashining doirasi (`admission_classes`: boshlang‘ich holatda har admission non-critical, `critical` yozuvi mavjud step’ni nomlaydi, noma’lum yozuv config’ni rad etadi; G14), agent run o‘rtasida to‘xtaganda command hayoti (`review_ttl`: tekshirilmagan band ✅ Q32 TTL’ida `expired`, hold bo‘shaydi, avtomatik tasdiq yo‘q; `orphan_cancel`: yarim step bandlari `step_incomplete`; DATA_MODEL §6.2 `extra_transitions` nusxasi aynan; G15), reservation o‘lchami (`reservation_sizing`: bitta upper bound ≤ `max_cost_minor`, rolning barcha ochiq hold’lari ulushning 80–100% oralig‘ida, har LLM ulushi rolida; ortiqcha so‘rov navbatda va `slot_wait_exceeded` (423); `uncertain` slot’ini ushlaydi va OpenRouter generation yozuvi bilan settle bo‘ladi, bepul kredit emas; F1-AT-30; G16), Hermes xotirasi (`hermes_memory`: pin’lar — ikkala yozish tasdig‘i on, fon review off, belgi chegaralari; `session_search` yashirin; tasdiq buyruqlari faqat owner DM’idan, bittadan, owner bo‘lmagan sessiyadagi yozuv rad, fail-closed fallback; suhbat ombori va memory fayllari privacy dataset’i; ADR-004 pin nusxasi va SECURITY custody jadvali har dataset bilan; G17), runner sessiyasi xotira emas (`runner_contract`: har step yangi sessiya, tmpfs workspace, read-only home, Claude Code memory o‘chiq, transcript `max_input_tokens` bilan va oshsa `input_over_bound` (413) — yuborilmaydi; F4-AT-30; G18), ulush qismlari (`sub_shares.cmo`: aynan `chat` va `workflow`, yig‘indisi CMO ulushiga teng, run token’siz so‘rov — chat, har qismda warn/stop va pauza qatori, chat tugasa LLM’siz xabar va workflow davom etadi; qiymatlar `budget.request_bounds`da; F4-AT-31; G19), media attributsiyasi (`media_generation.attribution`: bitta reservation egasi `media_generation`, aynan kalit + media ulushi + so‘ragan agent ulushi bitta tranzaksiyada, so‘ragan agentlar = media tool’i bor allowlist’lar; bitta job, oylik soniya va parallellik chegaralari owner qiymati; narx revision’i majburiy; C-40; F4-AT-32; G20), saboq va golden copy byudjeti (sxema `guidance_eligible` yozuvni faqat `accepted`, `lesson` ≤ 600 belgi, `scope` va `review_by` bilan qabul qiladi — sintetik yozuvlar bilan tekshiriladi; har chaqiruvga ko‘pi bilan 15 ta mos saboq, eng yangisi birinchi, ≤ 2 000 token `max_fixed_tokens` ichida; golden copy aynan creative-studio va reviewer uchun, pipeline × format bo‘yicha ≤ 6; FE-AT-16; G21)"),
    ("C", "Builder context pack’lari (CLAUDE.md §0): har faza uchun pack bor, taxminiy hajmi ≤ 60 000 token, ko‘rsatilgan bo‘limlar mavjud"),
    ("Q", "Kuzatuvchanlik: har talab va invariant testga bog‘langan, har test talab/invariant/workflow’ga bog‘langan, PRD va INVARIANTS test ustunlari mos; bu hisobot joriy validator natijasiga mos (Q09)"),
]
REPORT_FIXTURES = [
    ("HC", "haqiqiy tool JSON sxemalariga ijobiy/salbiy payload va sintetik aggregation/RPO hisoblari; runtime dalili emas"),
    ("FX", "config’ni xotirada buzadi (pul, tasdiq, kill, readiness va uning tayyorlovchilari, RBAC, release, muhitlar, workflow, concurrency, ritm)"),
    ("PS", "readiness profilini sintetik tasdiqlar bilan baholaydi (shaxs havolasi, tayyorlovchi ≠ tasdiqlovchi, qiymat, vaqt, co-signer, N/A)"),
    ("DM", "bitta hujjatni vaqtinchalik nusxada buzadi (skill Tool scope, tool/action/control op/himoya nazorati jadvallari, ritm, CONFIG_CONTRACT, dalil yoshi, kuzatuvchanlik, ID, havola, qoldiq, owner matni)"),
]
REPORT_FACTS = [("handoff_schema_cases", "Handoff schema fixture’lari"), ("handoff_semantic_cases", "Handoff aggregation/RPO fixture’lari"), ("readiness_keys", "Readiness kalitlari"), ("profiles", "Readiness profillari"), ("workflows", "Workflow ta’riflari"),
                ("hg", "HUMAN_GATE’lar"), ("phase_at", "Faza AT’lari"), ("uat_evo", "UAT va EVO-AT"), ("wf_tests", "WF-TEST’lar"),
                ("q_ids", "Owner Q-ID’lari"), ("invariants", "Invariantlar"), ("adrs", "ADR’lar"), ("incidents", "Incident turlari (INC)"),
                ("owner_decision_rows", "owner_decision_rows"), ("markdown_files", "Markdown hujjatlar"), ("requirements", "Talablar (FR/NFR/EVO-R)"),
                ("context_pack_max_tokens", "Eng katta context pack (taxminiy token)")]


def write_report(root: Path) -> int:
    """Regenerate 12_Acceptance/VALIDATION_REPORT.md from a real run (full check + self-test); never hand-edited."""
    now = lambda: dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.environ["AMT_REPORT_GENERATION"] = "1"
    try:
        t_full = now()
        rep = validate(root)
        t_self = now()
        st_ok, st_lines = self_test(root)
    finally:
        os.environ.pop("AMT_REPORT_GENERATION", None)
    rules = sorted(rep.checked | {"Q09"})
    fx = yaml.safe_load((root / "12_Acceptance" / "fixtures" / "mutations.yaml").read_text(encoding="utf-8"))
    counts = {"FX": len(fx.get("mutations", [])), "PS": len(fx.get("profile_scenarios", [])), "DM": len(fx.get("doc_mutations", [])), "HC": len(probe_results(root, load_configs(root, Report())))}
    st_pass = sum(1 for l in st_lines if l.startswith("ok "))
    files = [f for f in root.rglob("*") if f.is_file() and "__pycache__" not in f.parts]
    by_ext = {}
    for f in files:
        by_ext[f.suffix or f.name] = by_ext.get(f.suffix or f.name, 0) + 1
    full_ok = not rep.errors
    audits = sorted(f.name for f in (root / "00_Decisions").glob("AUDIT_20*.md"))
    latest_audit = audits[-1] if audits else "DECISION_LOG.md"
    out = ["# Paket tekshiruvi — validator natijasi", "",
           f"Holat: avtomatik yozilgan hisobot · Runtime: NOT_RUN · Sana: {t_full[:10]}.", "",
           "Bu fayl qo‘lda yozilmaydi: u [validate_bundle.py](validate_bundle.py) `--write-report` rejimining haqiqiy natijasidan yaratiladi. Validator faqat fayllarni o‘qiydi; server, API yoki biznes natijasi haqida hech narsa isbotlamaydi. Natija o‘zgarsa hisobot qayta yaratiladi; qo‘lda tahrirlangan PASS dalil hisoblanmaydi.", "",
           "## 1. Natija", "", "| Buyruq | Boshlangan (UTC) | Exit code | Natija |", "|---|---|---|---|",
           f"| `python3 12_Acceptance/validate_bundle.py --json` | {t_full} | {0 if full_ok else 1} | **{'PASS' if full_ok else 'FAIL'}** — {len(rules)} qoida, {len(rep.errors)} xato, {len(rep.warnings)} ogohlantirish |",
           f"| `python3 12_Acceptance/validate_bundle.py --self-test` | {t_self} | {0 if st_ok else 1} | **{'PASS' if st_ok else 'FAIL'}** — {st_pass}/{len(st_lines)} holat kutilgandek |", "",
           "## 2. Self-test tarkibi", "",
           "Har negativ holat bitta qoidani buzadi va validator aynan o‘sha qoidani FAIL qilishi kerak; ijobiy profil ssenariylari PASS bo‘lishi kerak. Manba — [fixtures/mutations.yaml](fixtures/mutations.yaml).", "",
           "| Turi | Nima qiladi | Holatlar | Kutilgandek |", "|---|---|---|---|"]
    ok_by = {k: sum(1 for l in st_lines if l.startswith("ok ") and l[4:].startswith(k + "-")) for k in counts}
    for kind, text in REPORT_FIXTURES:
        out.append(f"| {kind} | {text} | {counts[kind]} | {ok_by[kind]} |")
    out += ["", "## 3. Tekshirilgan qoidalar", "", "| Oila | Mazmuni | Qoidalar |", "|---|---|---|"]
    known = {f for f, _ in REPORT_FAMILIES}
    for fam, text in REPORT_FAMILIES + [(f, "Yangi oila") for f in sorted({r[0] for r in rules} - known)]:
        ids = [r for r in rules if r[0] == fam]
        if ids:
            out.append(f"| {fam} | {text} | {', '.join(ids)} |")
    out += ["", "## 4. To‘plam faktlari", "", "| Fakt | Qiymat |", "|---|---|", f"| Fayllar (jami) | {len(files)} |"]
    for ext in (".md", ".yaml", ".json", ".example", ".hujson", ".py"):
        out.append(f"| `{ext}` fayllar | {by_ext.get(ext, 0)} |")
    for key, label in REPORT_FACTS:
        if key in rep.facts:
            out.append(f"| {label} | {rep.facts[key]} |")
    out += ["", "## 5. Validator nimani isbotlamaydi", "",
            "- Runtime holatini: barcha testlar `not_run`; servislar qurilmagan.",
            "- Vendor faktlarini: ular [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) da build kuni qayta tekshiriladi.",
            "- Readiness qiymatlarini: shablondagi kalitlar `pending`; profil PASS faqat inson tasdig‘i va dalil bilan (`--profile` rejimi).",
            f"- Matn sifatini va biznes to‘g‘riligini: buni mustaqil inson va agent review’lari tekshiradi ([{'AUDIT' if audits else 'DECISION_LOG'}](../00_Decisions/{latest_audit})).", "",
            "## 6. Qayta ishga tushirish", "", "```bash",
            "pip install pyyaml 'jsonschema>=4.18'",
            "python3 12_Acceptance/validate_bundle.py            # to‘liq tekshiruv; xato bo‘lsa exit 1",
            "python3 12_Acceptance/validate_bundle.py --self-test # negativ va ijobiy holatlar",
            "python3 12_Acceptance/validate_bundle.py --write-report # shu hisobotni haqiqiy natijadan qayta yozadi",
            "python3 12_Acceptance/validate_bundle.py --profile F6_STEP1 --readiness <to‘ldirilgan readiness.yaml>",
            "```", ""]
    (root / "12_Acceptance" / "VALIDATION_REPORT.md").write_text("\n".join(out), encoding="utf-8")
    if rep.errors:
        print("\n".join(f"ERROR {r}: {m}" for r, m in rep.errors))
    if not st_ok:
        print("\n".join(l for l in st_lines if not l.startswith("ok ")))
    print(f"VALIDATION_REPORT.md written: full {'PASS' if full_ok else 'FAIL'} ({len(rules)} rules), self-test {'PASS' if st_ok else 'FAIL'} ({st_pass}/{len(st_lines)})")
    return 0 if full_ok and st_ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--write-state-machines", action="store_true", help="regenerate 03_Architecture/STATE_MACHINES.md from the configs (W12)")
    ap.add_argument("--write-report", action="store_true", help="regenerate 12_Acceptance/VALIDATION_REPORT.md from a real run")
    ap.add_argument("--context-pack", metavar="PHASE", help="print the builder reading pack of a phase (F0-F7, FE); --out writes it to a file")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--profile")
    ap.add_argument("--readiness", type=Path)
    ap.add_argument("--now")
    args = ap.parse_args(argv)
    if args.write_state_machines:
        cfg0 = load_configs(args.root, Report())
        (args.root / SM_DOC).write_text(render_state_machines(cfg0), encoding="utf-8")
        print(f"{SM_DOC} written")
        return 0
    if args.write_report:
        return write_report(args.root)
    if args.context_pack:
        packs = load_packs(args.root)
        if not packs or args.context_pack not in packs.get("packs", {}):
            print(f"unknown context pack {args.context_pack}")
            return 1
        text, tokens, problems = render_pack(args.root, packs, args.context_pack)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        else:
            print(text)
        print(f"context pack {args.context_pack}: ~{tokens} estimated tokens (budget {packs['budget_tokens']}); problems: {problems or 'none'}", file=sys.stderr)
        return 0 if tokens <= packs["budget_tokens"] and not problems else 1
    if args.self_test:
        ok, lines = self_test(args.root)
        print("\n".join(lines))
        print("SELF-TEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    if args.profile:
        path = args.readiness or args.root / "09_Config_Templates" / "readiness.yaml"
        r = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
        now = parse_ts(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
        passed, problems = evaluate_profile(r, args.profile, now)
        result = {"profile": args.profile, "result": "pass" if passed else "fail", "problems": problems}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"{args.profile}: {result['result'].upper()} ({len(problems)} open)\n" + "\n".join(problems))
        return 0 if passed else 1
    report = validate(args.root)
    result = {"result": "pass" if not report.errors else "fail", "rules_checked": sorted(report.checked),
              "errors": [f"{r}: {m}" for r, m in report.errors], "warnings": [f"{r}: {m}" for r, m in report.warnings], "facts": report.facts}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for line in result["errors"]:
            print("ERROR", line)
        for line in result["warnings"]:
            print("WARN ", line)
        print(f"{result['result'].upper()}: {len(report.errors)} errors, {len(report.warnings)} warnings, {len(report.checked)} rules; facts {report.facts}")
    return 0 if not report.errors else 1


if __name__ == "__main__":
    sys.exit(main())
