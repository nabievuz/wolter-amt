"""Offline handoff regression checks (H family).

Only reads the specification and evaluates synthetic schema/reference fixtures.
No server, provider, database or runtime behavior is exercised or asserted.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path


def _text(root: Path, path: str) -> str:
    p = root / path
    return p.read_text(encoding='utf-8') if p.exists() else ''


def _terms(value, *terms: str) -> bool:
    text = str(value).lower()
    return all(term.lower() in text for term in terms)


def _wf(c: dict, wid: str) -> dict:
    return next((w for w in c.get('_workflows', {}).values() if w.get('workflow_id') == wid), {})


def _steps(c: dict, wid: str) -> dict:
    return {s.get('id'): s for s in _wf(c, wid).get('steps', [])}


def _edge(c: dict, machine: str, source: str, target: str) -> dict:
    return next((e for e in (c.get('workflow-policy.yaml', {}).get('state_machines', {}).get(machine, {}).get('transitions') or [])
                 if e.get('from') == source and e.get('to') == target), {})


def usable_point_age(snapshots: list[dict], at_seconds: int) -> int | None:
    """Reference RPO calculation: a started/incomplete/unverified run is unusable."""
    usable = [s['point_seconds'] for s in snapshots
              if s.get('manifest_verified') is True and s.get('complete_seconds') is not None
              and 0 <= s['point_seconds'] <= s['complete_seconds'] <= at_seconds]
    return at_seconds - max(usable) if usable else None


def accepted_custody(c: dict, item: dict) -> bool:
    """Reference predicate for the documented accepted manual-resolution handoff."""
    h = item.get('handoff') or {}
    refs = (c.get('workflow-policy.yaml', {}).get('command_aggregation', {}).get('manual_resolution_handoff') or {}).get('required_refs') or []
    return (item.get('state') == 'manual_resolution' and h.get('status') == 'accepted'
            and h.get('authorized_receiver') is True and h.get('owner_task_durable') is True
            and bool(h.get('accepted_by')) and bool(h.get('accepted_at'))
            and bool(refs) and all(h.get('refs', {}).get(k) for k in refs))


def aggregate_commands(c: dict, role: str, items: list[dict]) -> str:
    """Small executable reference for complete_when + ordered aggregation rules."""
    ca = c.get('workflow-policy.yaml', {}).get('command_aggregation') or {}
    block = ca.get(role) or {}
    states = [i.get('state') for i in items]
    if not states:
        return 'waiting'
    cw = block.get('complete_when')
    if cw == 'every_item_decided':
        ready = all(s in {'approved', 'rejected', 'expired', 'cancelled'} for s in states)
    elif cw == 'no_item_before_attempt':
        ready = not any(s in {'pending_review', 'pending_approval', 'approved', 'claimed', 'executing', 'awaiting_manual'} for s in states)
    elif cw == 'every_item_terminal_or_handed_off':
        ready = all(i.get('state') in ca.get('terminal_command_states', []) or accepted_custody(c, i) for i in items)
    else:
        return 'invalid_contract'
    if not ready:
        return 'waiting'
    for rule in block.get('rules') or []:
        w = rule.get('when') or {}
        tests = []
        if 'any_in' in w:
            tests.append(any(s in w['any_in'] for s in states))
        if 'none_in' in w:
            tests.append(not any(s in w['none_in'] for s in states))
        if 'all_in' in w:
            tests.append(all(s in w['all_in'] for s in states))
        if 'compensation_in' in w:
            tests.append(any(i.get('compensation') and i.get('state') in w['compensation_in'] for i in items))
        if tests and all(tests):
            return rule.get('step')
    return 'waiting'





def historical_clear_closes_incident(c: dict, record: dict, raised_id: str, current: dict) -> bool:
    """Reference historical clearance proof plus a separate verified live-cause check."""
    fields = c.get('workflow-policy.yaml', {}).get('incident_cause_resolution', {}).get('exact_match') or []
    if 'clearance_control_epoch' not in fields:
        return False
    auth = record.get('authenticated_at_clearance') or {}
    epoch = record.get('clearance_control_epoch')
    now_epoch = current.get('control_epoch')
    return (record.get('raised_control_event_id') == raised_id and bool(record.get('cleared_control_event_id'))
            and auth.get('authorized') is True and isinstance(epoch, int) and auth.get('control_epoch') == epoch
            and all(record.get(k) and record.get(k) == auth.get(k) for k in [
                'key_and_period', 'approved_policy_revision', 'fresh_reconciliation_evidence', 'actual_plus_reserved_allowance_evidence'])
            and current.get('snapshot_verified') is True and isinstance(now_epoch, int) and now_epoch >= epoch
            and (now_epoch == epoch or current.get('later_epoch_changes_authorized') is True)
            and current.get('active_causes') == [])


def phase_entry_profiles_met(c: dict, phase: str, results: dict) -> bool:
    """Reference check of the declared entry profiles, not all phase/runtime gates."""
    entry = c.get('readiness.yaml', {}).get('rules', {}).get('phase_entry_profiles', {}).get(phase) or {}
    required = entry.get('requires_profiles') or []
    return bool(required) and all(results.get(p) == 'pass' for p in required)


def deployment_errors(c: dict, candidate: dict, observed_services: list[str], *, prior_services: list[str] | None = None,
                      active_phase: str | None = None, active_release_id: str | None = None,
                      transition_capabilities: list[str] | None = None, bootstrap_used: bool = False) -> list[str]:
    """Reference phase/capability/installed-inventory ACK admission, with no runtime effects."""
    dp = candidate.get('deployment') or {}
    rule = c.get('release-policy.yaml', {}).get('deployment') or {}
    registry = {s['service_id']: s for s in c.get('runtime-isolation.yaml', {}).get('services', [])}
    phases = rule.get('phases') or []
    phase = dp.get('phase')
    if phase not in phases:
        return ['unknown phase']
    services = set(dp.get('services') or [])
    problems = []
    if services != set(observed_services):
        problems.append('inventory mismatch')
    if not services <= set(registry):
        problems.append('unknown service')
    floor = {name for p in phases[:phases.index(phase) + 1] for name in rule.get('phase_service_additions', {}).get(p, [])}
    if not floor <= services:
        problems.append('missing phase floor')
    if not set(prior_services or []) <= services:
        problems.append('prior installed service disappeared')
    if active_phase is not None and (active_phase not in phases or phases.index(phase) < phases.index(active_phase)):
        problems.append('phase regressed')
    capabilities = set(candidate.get('capabilities_enabled') or []) | set(transition_capabilities or [])
    for cap in capabilities:
        deps = rule.get('capability_services', {}).get(cap)
        if not deps or not set(deps) <= services:
            problems.append('missing or unknown capability service closure')
    expected_acks = {name for name in services if name in registry and registry[name].get('ack_class') in {'write_gate', 'function_gate'}}
    acks = dp.get('required_acks') or []
    if set(acks) != expected_acks or len(acks) != len(set(acks)):
        problems.append('ACK set mismatch')
    if len(dp.get('services') or []) != len(services):
        problems.append('duplicate service')
    if dp.get('kind') == 'initial':
        if bootstrap_used or active_release_id is not None or phase != 'F1' or candidate.get('base_release_id') is not None:
            problems.append('initial seed not eligible')
        if candidate.get('capabilities_enabled') or candidate.get('readiness_snapshot', {}).get('capabilities') or candidate.get('release_class') != 'normal':
            problems.append('initial capability/class forbidden')
    elif dp.get('kind') == 'update':
        if not candidate.get('base_release_id') or (active_release_id is not None and candidate.get('base_release_id') != active_release_id):
            problems.append('invalid update base')
    else:
        problems.append('unknown deployment kind')
    return problems


def probe_results(root: Path, c: dict) -> list[dict]:
    """Validate real schema instances and explicit synthetic aggregation/RPO cases."""
    fixture_path = root / '12_Acceptance/fixtures/handoff_cases.json'
    if not fixture_path.exists():
        return [{'id': 'HC-MISSING', 'rule': 'H05', 'pass': False, 'message': 'handoff_cases.json missing'}]
    try:
        fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
        docs = [json.loads(p.read_text(encoding='utf-8')) for p in (root / '09_Config_Templates/schemas/tools').glob('*.schema.json')]
        docs += [d for d in c.get('_schemas', {}).values() if isinstance(d, dict) and '$id' in d]
        by_name = {d['$id'].rsplit('/', 1)[-1]: d for d in docs}
        registry = Registry().with_resources((d['$id'], Resource.from_contents(d)) for d in docs)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        return [{'id': 'HC-LOAD', 'rule': 'H05', 'pass': False, 'message': str(exc)}]
    out = []
    for case in fixture.get('schema_cases', []):
        try:
            errors = list(Draft202012Validator(by_name[case['schema']], registry=registry).iter_errors(case['instance']))
            actual = not errors
            good = actual == case['valid']
            message = case['name'] + ('' if good else f': expected valid={case["valid"]}, got {actual}')
        except Exception as exc:  # an invalid/unresolvable mutated schema is a failed probe, never a validator crash
            good, message = False, f'{case.get("name")}: {exc}'
        out.append({'id': case['id'], 'rule': case.get('rule', 'H05'), 'kind': 'schema', 'pass': good, 'message': message})
    for case in fixture.get('aggregation_cases', []):
        actual = aggregate_commands(c, case['role'], case['items'])
        out.append({'id': case['id'], 'rule': 'H10', 'kind': 'semantic', 'pass': actual == case['step'],
                    'message': f'{case["name"]}: expected {case["step"]}, got {actual}'})
    for case in fixture.get('rpo_cases', []):
        actual = usable_point_age(case['snapshots'], case['at_seconds'])
        met = actual is not None and actual <= case['target_seconds']
        out.append({'id': case['id'], 'rule': 'H12', 'kind': 'semantic', 'pass': actual == case['age_seconds'] and met == case['met'],
                    'message': f'{case["name"]}: usable-point age {actual}; target met={met}'})
    for case in fixture.get('deployment_cases', []):
        problems = deployment_errors(c, case['candidate'], case['observed_services'], **case.get('context', {}))
        actual = not problems
        out.append({'id': case['id'], 'rule': 'H03', 'kind': 'semantic', 'pass': actual == case['valid'],
                    'message': f'{case["name"]}: expected valid={case["valid"]}, got {actual}; {problems}'})
    for case in fixture.get('phase_entry_cases', []):
        actual = phase_entry_profiles_met(c, case['phase'], case['profile_results'])
        out.append({'id': case['id'], 'rule': 'H03', 'kind': 'semantic', 'pass': actual == case['met'],
                    'message': f'{case["name"]}: entry profile prerequisites met={actual}'})
    for case in fixture.get('historical_clear_cases', []):
        actual = historical_clear_closes_incident(c, case['record'], case['raised_id'], case['current'])
        out.append({'id': case['id'], 'rule': 'H13', 'kind': 'semantic', 'pass': actual == case['closes'],
                    'message': f'{case["name"]}: historical proof and current closure valid={actual}'})
    return out


def handoff_rules(root: Path, c: dict, report, docs: bool = True):
    ep = c.get('execution-policy.yaml', {}) or {}
    ap = c.get('approval-policy.yaml', {}) or {}
    wp = c.get('workflow-policy.yaml', {}) or {}
    op = c.get('operations.yaml', {}) or {}
    # H01/H02: adoption is separate from the owner-only fresh initializer.
    if docs:
        adoption = _text(root, '05_Build_Phases/SERVER_ADOPTION.md')
        claude = _text(root, 'CLAUDE.md')
        readme = _text(root, 'README.md')
        preflight = _text(root, '12_Acceptance/preflight_server.py')
        try:
            ast.parse(preflight)
            valid_preflight = bool(preflight)
        except SyntaxError:
            valid_preflight = False
        report.check('H01', valid_preflight and _terms(adoption, 'read-only admission', 'match | mismatch | unknown',
                     'one decision at a time', 'Existing installation is the default route', 'existing SSH session use `sudo -iu builder`',
                     'repo_root=/srv/builder/wolter-amt', 'project_os_root="$repo_root/project-os"',
                     'cd "$project_os_root"', 'HG-F0-00') and 'SERVER_ADOPTION' in claude and 'SERVER_ADOPTION' in readme,
                     'existing-server admission must preserve unknowns, owner gates, builder login and explicit repo/project-os directories')
        blocks = re.findall(r'```bash\n(.*?)\n```', adoption, re.S)
        boot = next((b for b in blocks if b.startswith('#!/usr/bin/env bash')), '')
        guards = ['[[ ! -e "$STATE" ]]', '! id builder', '! id amt-build', '! command -v claude',
                  '! command -v tailscale', '! dpkg -s openssh-server', '[[ ! -e /opt/wolter-amt/current ]]']
        first_mutation = boot.find('  install -d -m 700 -o root -g root "$STATE"')
        guarded_first = first_mutation >= 0 and all(0 <= boot.find(g) < first_mutation for g in guards)
        report.check('H02', guarded_first and _terms(boot, '$STATE/complete', '$STATE/script.sha256', '$STATE/inputs.sha256',
                     '$STATE/*.inflight', '$STATE/$step.done', 'set -o noclobber', 'cmp -s "$tmp" "$file"',
                     'test -f ~/.ssh/id_ed25519_$r || ssh-keygen', 'grep -qxF -- "$OWNER_PUBKEY"',
                     'existing builder policy is preserved', 'if [[ "$MODE" == "build" ]]',
                     '[[ -e "$STATE/03-privileges.done" ]]', '[[ "$REQUEST" != --resume ]]')
                     and '[[ "$(cat "$STATE/script.sha256")" == "$SCRIPT_SHA" ]]' in boot
                     and '[[ "$(cat "$STATE/inputs.sha256")" == "$INPUT_SHA" ]]' in boot
                     and 'if [[ -e "$STATE/$step.done" ]]; then return 0; fi' in boot
                     and 'git pull' not in boot and 'git reset' not in boot and 'git clean' not in boot,
                     'initializer must reject existing/complete state before mutation, pin resumed script+inputs, stop inflight steps and preserve keys/authority/checkout')
    # H03: Q65 one-time owner seed; effective ACKs follow the installed inventory and safety floors.
    rp = c.get('release-policy.yaml', {}) or {}
    init, dep = rp.get('initial_release') or {}, rp.get('deployment') or {}
    fixture = json.loads(_text(root, '12_Acceptance/fixtures/handoff_cases.json') or '{}')
    pin = fixture.get('release_contract') or {}
    registry = {v['service_id']: v for v in c.get('runtime-isolation.yaml', {}).get('services', [])}
    ack_registry = {k for k, v in registry.items() if v.get('ack_class') in {'write_gate', 'function_gate'}}
    manifest = c.get('_schemas', {}).get('candidate-manifest.schema.json') or {}
    dp_schema = manifest.get('properties', {}).get('deployment') or {}
    sp = dp_schema.get('properties') or {}
    def enum_items(key):
        items = sp.get(key, {}).get('items', {})
        if items.get('$ref', '').startswith('#/$defs/'):
            items = manifest.get('$defs', {}).get(items['$ref'].rsplit('/', 1)[-1], {})
        return set(items.get('enum') or [])
    report.check('H03', init.get('decision_ref') == 'Q65' and init.get('approval_source') == 'owner_ssh_signed_initial'
                 and set(init.get('required_absent') or []) == {'current_symlink', 'active_release', 'prior_release_ledger', 'killed_latch', 'used_bootstrap'}
                 and init.get('initial_manifest') == {'deployment_kind': 'initial', 'phase': 'F1', 'base_release_id': None,
                        'capabilities_enabled': [], 'readiness_snapshot_capabilities': {}, 'release_class': 'normal'}
                 and init.get('startup') == {'global_mode': 'shadow', 'pipeline_modes': {'rent': 'L0_shadow', 'sale': 'L0_shadow'},
                                            'admission': 'denied', 'capabilities_enabled': []}
                 and _terms(init.get('trust_root'), '/etc/amt/release-signers', 'owner-signed annotated', 'amt-build', 'same digests')
                 and _terms(init.get('entrypoint'), 'root-owned fixed installer', 'no arbitrary repo script')
                 and _terms(init.get('seed_transaction'), 'atomically', 'typed_confirmations', 'release_approvals', 'append-only audit', 'singleton bootstrap marker', 'no persistent new runtime DB writer grant')
                 and _terms(init.get('replay_rule'), 'exact replay', 'different nonce', 'permanently sealed')
                 and _terms(init.get('publisher_rule'), 'release_approvals', 'no tag-only release', 'no initial killed-latch exception')
                 and _terms(init.get('retry_rule'), 'same pending candidate', 'original validity checks', 'no implicit expiry extension')
                 and _terms(init.get('later_updates'), 'nonnull base_release_id equal to current active release', 'ordinary Telegram'),
                 'Q65 initial install must use a signed exact one-time seed with durable ordinary approval, denied admissions, no replay or killed-state bypass')
    envelope = init.get('approval_envelope') or {}
    bound = {'bootstrap_id', 'host_identity', 'installer_digest', 'candidate_id', 'manifest_digest', 'main_commit', 'artifact_digests',
             'owner_person_id', 'policy_revision', 'role_revision', 'control_epoch', 'nonce_hash', 'approved_at', 'expires_at',
             'verification_id', 'verdict', 'evaluator_revision', 'proposal_revision'}
    report.check('H03', set(envelope.get('required_fields') or []) == bound
                 and _terms(envelope.get('signature'), 'owner detached signature', '/etc/amt/release-signers', 'seeded active owner')
                 and dep.get('phases') == ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7']
                 and dep.get('phase_service_additions') == pin.get('phase_service_additions')
                 and dep.get('capability_services') == pin.get('capability_services')
                 and set(dep.get('capability_services') or {}) == set(ep.get('capability_requires_profile') or {})
                 and all(set(x) <= set(registry) for x in dep.get('capability_services', {}).values())
                 and _terms(dep.get('services_rule'), 'including disabled', 'prior active inventory', 'never a caller-selected enabled subset')
                 and _terms(dep.get('ack_rule'), 'must equal exactly', 'ack_class', 'no missing, extra, duplicate, unknown')
                 and _terms(dep.get('gate_rule'), 'prepare and activate recompute', 'target_profile is informational')
                 and _terms(dep.get('absence_rule'), 'phase floor', 'prior installed inventory', 'every enabled capability dependency'),
                 'release manifest selection must retain phase floors and capability closures, verify full staged inventory and require every installed ACK-class service')
    report.check('H03', 'deployment' in (manifest.get('required') or []) and dp_schema.get('additionalProperties') is False
                 and set(dp_schema.get('required') or []) == {'kind', 'phase', 'services', 'required_acks'}
                 and sp.get('kind', {}).get('enum') == ['initial', 'update']
                 and all(sp.get(k, {}).get('uniqueItems') is True and isinstance(sp.get(k, {}).get('maxItems'), int)
                         for k in ['services', 'required_acks'])
                 and enum_items('services') == set(registry)
                 and enum_items('required_acks') == ack_registry,
                 'candidate manifest must carry a closed bounded unique deployment inventory and ACK list from the canonical service registry')
    if docs:
        first = _text(root, '05_Build_Phases/FIRST_RELEASE.md')
        report.check('H03', _terms(first, 'Q65', 'release_approvals', 'SSH signature', 'approval source', 'nonce', 'shadow', 'L0', 'ACK'),
                     'FIRST_RELEASE must explain the approved initial seed, audit and denied-capability staged ACK protocol')
    f5_entry = c.get('readiness.yaml', {}).get('rules', {}).get('phase_entry_profiles', {}).get('F5') or {}
    initial_review = c.get('evolution-policy.yaml', {}).get('initial_build_review') or {}
    reviewer = next((r for r in c.get('readiness.yaml', {}).get('requirements', []) if r.get('key') == 'engineering.independent_reviewer'), {})
    report.check('H03', f5_entry == {'decision_ref': 'Q67', 'requires_profiles': ['FE_RELEASE'],
                                   'before': ['formal_eval', 'real_shadow'], 'missing_or_failed': 'blocked'}
                 and initial_review.get('decision_ref') == 'Q66' and initial_review.get('sequencing_decision_ref') == 'Q67'
                 and _terms(initial_review.get('ends'), 'exact baseline manifest', 'before any formal F5 eval or real shadow')
                 and reviewer.get('gate') == 'FE_RELEASE'
                 and _terms(reviewer.get('description'), 'Q67', 'before formal F5 eval and real shadow', 'class_e_frozen is refused'),
                 'Q67 requires complete FE_RELEASE and its independent human baseline signoff before formal F5 eval and real shadow, not only before F5_GO')
    # H04: a command may precede its verdict; exact review and approval snapshots are append-only.
    lifecycle = ep.get('approval_binding_lifecycle') or {}
    review = lifecycle.get('command_review') or {}
    frozen = lifecycle.get('approval_snapshot') or {}
    report.check('H04', _terms(lifecycle.get('immutable_intent'), 'excludes later command verdict', 'human check', 'lifecycle fields')
                 and review.get('created_without_verdict') == 'pending_review'
                 and review.get('binding_table') == 'command_review_bindings'
                 and review.get('write_rule') == 'append_only_unique_command_revision'
                 and _terms(review.get('subject'), 'command_id', 'command_revision', 'payload_hash')
                 and _terms(review.get('accepts'), 'independent', 'issued', 'pass', 'expiry', 'revocation')
                 and _terms(review.get('creative_review_is_separate'), 'creative_review_revision', 'never substitutes')
                 and _terms(review.get('needs_owner'), 'pending_review', 'independent Reviewer', 'no human verdict override')
                 and frozen.get('table') == 'command_approval_bindings'
                 and frozen.get('write_rule') == 'append_only_unique_command_revision'
                 and set(frozen.get('freeze_before') or []) == {'mark_presented', 'approval_callback_issued', 'record_approval'}
                 and _terms(frozen.get('approval_reference'), 'approval_binding_id', 'binding_hash')
                 and _terms(frozen.get('human_check_when_required'), 'pass before freeze')
                 and _terms(frozen.get('approver_role_revision'), 'membership_revision', 'atomically', 'never mutates')
                 and _terms(frozen.get('repeat_freeze'), 'same', 'never update')
                 and _terms(frozen.get('after_freeze'), 'no dependency replacement', 'new command revision')
                 and 'creative_review_revision' in (ep.get('approval_binding') or []),
                 'exact command review must bind after intent creation and frozen dependency snapshot must precede every approval path')
    if docs:
        dm = _text(root, '03_Architecture/DATA_MODEL.md')
        report.check('H04', _terms(dm, 'command_review_bindings', 'command_approval_bindings', 'creative_review_revision',
                     'binding_hash', 'rekursiv', 'membership_revision')
                     and 'offer_revision`, `creative_revision`, `review_revision`, `asset_manifest_sha` `NOT NULL`' not in dm,
                     'DATA_MODEL must separate prior creative review, later exact-command review and frozen dependency binding without recursive payload hash')
    # H05 probes use the real closed JSON schemas; unknown/forged selectors cannot pass by prose alone.
    probes = probe_results(root, c)
    for probe in probes:
        report.check(probe['rule'], probe['pass'], f'{probe["id"]}: {probe["message"]}')
    report.facts['handoff_schema_cases'] = sum(p.get('kind') == 'schema' for p in probes)
    report.facts['handoff_semantic_cases'] = sum(p.get('kind') != 'schema' for p in probes)
    try:
        common = json.loads(_text(root, '09_Config_Templates/schemas/tools/_common.schema.json') or '{}')
    except ValueError:
        common = {}
    ee = common.get('$defs', {}).get('expected_effect') or {}
    report.check('H05', 'scope' in (ee.get('required') or [])
                 and set(ee.get('properties', {}).get('scope', {}).get('enum') or []) == {'pipeline', 'entity'},
                 'expected_effect.scope must be a required pipeline/entity enum')
    protected = str(c.get('evolution-policy.yaml', {}).get('protected_surfaces') or [])
    report.check('H05', '12_Acceptance/handoff_checks.py' in protected and '12_Acceptance/fixtures/**' in protected,
                 'the handoff validator helper and fixtures must remain protected surfaces')
    # H06: author routing is distinct from CI and independent exact-revision review.
    b04 = _steps(c, 'WF-B04')
    expected = {'S01': ('deterministic', 'amt-workflow'), 'S02': ('agent', 'cro'), 'S10': ('agent', 'funnel-analyst'),
                'S03': ('deterministic', 'github-ci'), 'S11': ('agent', 'funnel-analyst'), 'S12': ('agent', 'reviewer'),
                'S04': ('human', 'owner')}
    actors = all((b04.get(s, {}).get('executor') or {}) == {'type': t, 'ref': r} for s, (t, r) in expected.items())
    route = all(b04.get(s, {}).get('when') == {'step': 'S01', 'output': 'kind', 'in': kinds}
                for s, kinds in [('S02', ['offer', 'landing_content']), ('S10', ['tracking']), ('S11', ['landing_content'])])
    edges = all(set(b04.get(s, {}).get('depends_on') or []) == set(deps)
                for s, deps in [('S03', ['S02', 'S10']), ('S11', ['S03']), ('S12', ['S03', 'S11']), ('S04', ['S12'])])
    paths = ap.get('landing_pr_paths') or {}
    report.check('H06', actors and route and edges and b04.get('S01', {}).get('output_fields') == ['kind']
                 and paths.get('cro') == {'allow': ['content/**'], 'deny': ['content/offers.snapshot.json']}
                 and paths.get('funnel-analyst') == {'allow': ['tracking/**']}
                 and _terms(b04.get('S12'), 'review.get_subject', 'review.submit_verdict', 'subject_hash', 'commit SHA', 'separate from the author')
                 and _terms(b04.get('S04', {}).get('inputs'), 'current PR head commit SHA', 'S12', 'immediately before'),
                 'WF-B04 must route tracking to Analyst, keep CRO content-only, separate CI/independent reviews and bind owner merge to the current exact head')
    b02, b03 = _steps(c, 'WF-B02'), _steps(c, 'WF-B03')
    command_reviews = all((b02.get(s, {}).get('executor') or {}) == {'type': 'agent', 'ref': 'reviewer'}
                          and _terms(b02.get(s), 'change_set_item', 'command_review_bindings', 'payload_hash', 'independent')
                          for s in ['S12', 'S14'])
    review_edges = all(b02.get(s, {}).get('depends_on') == deps
                       for s, deps in [('S12', ['S06']), ('S09', ['S12']), ('S13', ['S10']), ('S14', ['S13']), ('S07', ['S14'])])
    activation_gate = all(b02.get(s, {}).get('when') == {'step': 'S10', 'output': 'created_entity_ids', 'non_empty': True}
                          for s in ['S13', 'S14', 'S07', 'S11'])
    report.check('H06', command_reviews and review_edges and activation_gate
                 and (b02.get('S13', {}).get('executor') or {}) == {'type': 'agent', 'ref': 'media-buyer'}
                 and (b03.get('S03', {}).get('executor') or {}) == {'type': 'agent', 'ref': 'reviewer'}
                 and b03.get('S04', {}).get('depends_on') == ['S03']
                 and _terms(b03.get('S03'), 'every', 'review_required', 'no creative dependency', 'change_set_item', 'payload_hash', 'command_review_bindings')
                 and _terms(wp.get('cost_caps', {}).get('demand_model'), 'S12', 'S13', 'S14', 'every review_required item', 'caps stay unchanged'),
                 'WF-B02/B03 approval must follow fresh exact-command review; creation, activation and creative verdicts are separate, bounded calls under existing caps')
    tuple_fields = ['landing_merge_commit', 'build_digest', 'content_artifact_hashes', 'tracking_artifact_hashes', 'offer_snapshot_hash']
    metadata = str(b04.get('S09', {}))
    signal = wp.get('signals', {}).get('catalog', {}).get('landing_snapshot_matched') or {}
    report.check('H06', all(k in metadata for k in tuple_fields)
                 and _terms(metadata, '/.well-known/amt-deployment.json', 'trusted', 'observed_at', 'response digest')
                 and all(k in str(signal.get('payload')) for k in tuple_fields)
                 and _terms(signal.get('dedup'), 'run_id', 'merge commit', 'build digest')
                 and (b04.get('S08', {}).get('executor') or {}) == {'type': 'human', 'ref': 'owner'},
                 'landing deployment ACK must match trusted CI merge/build/content/tracking/offer tuple; unchanged offer hash alone or self-authorizing metadata cannot ACK')
    # H07/H08 are pinned only now that explicit owner Q63/Q64 decisions exist.
    billing = (c.get('budgets.yaml', {}).get('openrouter') or {}).get('billing_resume_policy') or {}
    callers = c.get('runtime-isolation.yaml', {}).get('control_socket_peers') or {}
    report.check('H07', billing.get('decision_ref') == 'Q63'
                 and billing.get('mode') == 'automatic_for_matching_billing_cause_only'
                 and billing.get('invoker') == 'amt-watchdog' and billing.get('control_op') == 'billing_unreliable_resume'
                 and _terms(billing.get('requires'), 'fresh reconciled', 'current key and period', 'actual plus reserved',
                            'every active allowance', 'control_event_id', 'current control_epoch', 'unchanged approved policy revision')
                 and _terms(billing.get('clears'), 'only the matching billing_unreliable', 'compare-and-set', 'all remaining causes')
                 and set(billing.get('never_clears') or []) == {'share_stop', 'part_stop', 'key_noncritical_stop', 'month_boundary', 'anomaly', 'owner', 'kill', 'maintenance'}
                 and billing.get('missing_or_stale_evidence') == 'remain_paused'
                 and _terms(billing.get('audit'), 'control_events', 'reconciliation evidence', 'concurrent new causes remain active')
                 and {caller for caller, ops in callers.items() if 'billing_unreliable_resume' in ops} == {'amt-watchdog'},
                 'Q63 billing recovery may clear only its exact event/epoch/policy-matched reconciled cause; every other active pause remains')
    exposure = (ap.get('actions') or {}).get('experiment_exposure') or {}
    e_step = _steps(c, 'WF-B05').get('S03', {})
    report.check('H08', exposure.get('decision_ref') == 'Q64' and exposure.get('approvers') == ['owner', 'ads_approver']
                 and exposure.get('max_level') == 'L1_approve_each' and exposure.get('review_required') is True
                 and e_step.get('executor') == {'type': 'human', 'ref': 'approver_per_policy'}
                 and e_step.get('approval') == {'policy_action': 'experiment_exposure'},
                 'Q64 experiment exposure requires a current owner or ads_approver human approval, independent review and no automatic L2 exposure')
    if docs:
        report.check('H07', _terms(_text(root, '11_Production_Contracts/INVARIANTS.md'), 'Q63', 'billing_resume_policy', 'boshqa faol pauza ochilmaydi'),
                     'billing exception must be explicit in the higher-precedence invariant')
        rbac = _text(root, '03_Architecture/RBAC.md')
        report.check('H08', '| `experiment_exposure` | ✔ | ✔ | — | ko‘pi bilan L1 | true |' in rbac
                     and 'Q64' in _text(root, '00_Decisions/OPEN_ITEMS.md'),
                     'RBAC and OD-32 must reflect the accepted Q64 human delegation without closing unrelated experiment questions')
    # H09: safe no-effect retries concern attempts, never a resurrected terminal command.
    retry = ep.get('retry') or {}
    report.check('H09', retry.get('command_states') == ['claimed', 'executing']
                 and retry.get('command_state_during_backoff') == 'unchanged'
                 and retry.get('attempt_terminal_no_effect') == 'no_effect'
                 and retry.get('max_attempts') == 5 and retry.get('automatic_sdk_retry') is False
                 and retry.get('expiry_extension') == 'forbidden' and retry.get('unknown_classification') == 'uncertain'
                 and retry.get('attempt_states') == ['claimed', 'dispatch_intent', 'succeeded', 'no_effect', 'uncertain', 'reconciling', 'manual_resolution']
                 and retry.get('unresolved_attempt_states') == ['claimed', 'dispatch_intent', 'uncertain', 'reconciling', 'manual_resolution']
                 and _terms(retry.get('retry_only_when'), 'no_effect_evidence_ref', 'F3-verified', 'no unresolved attempt', 'frozen approval binding')
                 and _terms(retry.get('deadline'), 'original command.expires_at', 'approval.expires_at', 'dependency expiry')
                 and _terms(retry.get('retry_claim'), 'CAS', 'strictly higher fence', 'old worker', 'invalidated')
                 and _terms(retry.get('reservation'), 'same reservation', 'conflict lock', 'no second reserve', 'release once', 'settle once')
                 and _terms(retry.get('permanent_or_limit'), 'failed_confirmed terminal', 'never reopens')
                 and _terms(retry.get('uncertain_or_reconciling'), 'no retry', 'retain reservation')
                 and _terms(retry.get('reconciled_no_effect'), 'failed_confirmed terminal', 'new command revision')
                 and _terms(retry.get('eligibility_lost', {}).get('claimed'), 'cancelled', 'guard_failed', 'no dispatch')
                 and _terms(retry.get('eligibility_lost', {}).get('executing'), 'failed_confirmed', 'retry_ineligible', 'all attempts proven no_effect', 'no dispatch')
                 and retry.get('attempt_signal_key') == 'attempt:<attempt_id>:<state>'
                 and _terms(retry.get('command_signal_key'), 'only for real command transitions'),
                 'retry requires durable no-effect, bounded attempts, original validity, fresh fence and the same reservation; uncertain/terminal commands never reopen')
    # H10: role completion is separate from remote success and accepted out-of-run custody.
    ca = wp.get('command_aggregation') or {}
    handoff = ca.get('manual_resolution_handoff') or {}
    refs = ['command_id_and_revision', 'unresolved_attempt_and_evidence', 'owner_task', 'accepted_handoff_with_receiver_and_time',
            'reservation_or_explicit_not_required', 'conflict_lock_or_explicit_not_required']
    report.check('H10', _terms(_edge(c, 'step', 'running', 'completed').get('guard'), 'command_aggregation role', 'first matching',
                     'approval, dispatch or reconciliation', 'accepted', 'never reported as succeeded', 'Run-owned unresolved')
                 and handoff.get('applies_to') == 'manual_resolution_only' and handoff.get('required_refs') == refs
                 and _terms(handoff.get('rule'), 'durable owner task', 'I18 accepted handoff', 'task creation', 'never counts as accepted')
                 and _terms(handoff.get('acceptance'), 'authorized owner receiver', 'accepted_by', 'accepted_at', 'verifies')
                 and _terms(handoff.get('preserved'), 'reservation and conflict locks', 'never sets succeeded', 'never retries', 'never starts WF-B07')
                 and _terms(handoff.get('run_continuation'), 'still in run custody', 'checkpoint back to running', 'never reconciling or manual_resolution directly to completed')
                 and _terms(_edge(c, 'run', 'running', 'completed').get('guard'), 'no uncertain or reconciling', 'still in run custody', 'handed-off'),
                 'step completion must use its aggregation role; unresolved custody leaves a run only through accepted I18 transfer, never task creation or invented success')
    report.check('H10', _terms(_wf(c, 'WF-B03').get('completion', {}).get('technical_done'),
                     'accepted custody handoff', 'command_aggregation.manual_resolution_handoff', 'separately from success', 'running'),
                 'WF-B03 completion must retain verified accepted custody and the running checkpoint; task-only manual resolution never suffices')
    # H11: proxy per-request accounting and watchdog provider snapshots are distinct grants.
    if docs:
        envelope = _text(root, '11_Production_Contracts/OPERATING_ENVELOPE.md')
        dm = _text(root, '03_Architecture/DATA_MODEL.md')
        matrix = next((l for l in dm.splitlines() if l.startswith('| `provider_usage_snapshots` |')), '')
        report.check('H11', _terms(envelope, 'provider_usage_snapshots', 'yagona yozuvchi `cost-watchdog`', 'amt_watchdog', '`amt_proxy` faqat o‘qiydi', 'ai_requests')
                     and '| `amt_watchdog` → I | `amt_proxy`, `amt_ops` |' in matrix
                     and _terms(dm, 'usage-read credential watchdog', '`ai_requests` | `amt_proxy` → I'),
                     'provider_usage_snapshots writer must be cost-watchdog/amt_watchdog; proxy writes ai_requests and only reads provider snapshots')
    # H12: daily scheduling is not evidence that a usable recovery point meets the target.
    report.check('H12', _terms(op.get('rpo_definition'), 'usable only after', 'MANIFEST verifies', 'consistency point', 'I + D', 'daily 02:00 baseline alone does not prove')
                 and _terms(op.get('rpo_readiness_rule'), 'interval', 'completion', 'scheduling bounds', 'failed/missed', 'worst', 'pending', '<=24 h', 'No offsite copy')
                 and _terms(op.get('backup_stale_alert_rule'), 'consistency point', 'RPO breach', 'not proof')
                 and (op.get('local_snapshot') or {}).get('offsite_copy') is False,
                 'RPO must use completed verified consistency points and bounded delay/failure evidence; a daily cron or stale alert is not proof')
    if docs:
        br = _text(root, '06_Runbooks/BACKUP_RESTORE.md')
        report.check('H12', _terms(br, '24 soat 5 daqiqa', 'usable_completion_delay', 'scheduling_delay', 'readiness', 'pending'),
                     'backup runbook must retain the daily-run counterexample and block acceptance until per-dataset RPO evidence passes')
    if docs:
        f6 = _text(root, '05_Build_Phases/F6_GoLive.md')
        report.check('H12', 'har kechagi run tugasa 24 soatdan kam' not in f6
                     and _terms(f6, 'operations.yaml#rpo_readiness_rule', 'completion/scheduling delay', 'failed/missed', 'readiness pending'),
                     'F6 restore acceptance must use measured verified usable-point RPO evidence; daily snapshot completion alone proves no 24-hour guarantee')
    # H13: resume and handback are independent branches, including a handback-only incident.
    o02 = _steps(c, 'WF-O02')
    report.check('H13', o02.get('S06', {}).get('when') == {'step': 'S10', 'output': 'remaining_owner_causes', 'non_empty': True}
                 and o02.get('S09', {}).get('when') == {'step': 'S03', 'output': 'handback_triggers', 'non_empty': True}
                 and o02.get('S09', {}).get('depends_on') == ['S03']
                 and set(o02.get('S07', {}).get('depends_on') or []) == {'S05', 'S06', 'S09', 'S11'}
                 and _terms(_wf(c, 'WF-O02').get('completion', {}).get('technical_done'), 'S06 owner resume', 'S09 handback', 'handback_acks', 'not_applicable')
                 and _terms(_wf(c, 'WF-O02').get('failure_paths', {}).get('other'), 'Handback-only', 'S06 resume is skipped', 'S09 opens immediately after S03', 'accepted handback_acks'),
                 'WF-O02 handback-only incident must skip S06 resume but collect S09 accepted ACKs independently and wait for recovery before observation')

    live_causes = wp.get('incident_cause_resolution') or {}
    cause_signal = wp.get('signals', {}).get('catalog', {}).get('containment_cause_changed') or {}
    proxy_case = next((x for x in o02.get('S06', {}).get('approval', {}).get('by_cause', []) if x.get('cause') == 'proxy_admission_pause'), {})
    report.check('H13', o02.get('S10', {}).get('executor') == {'type': 'deterministic', 'ref': 'amt-control'}
                 and o02.get('S10', {}).get('depends_on') == ['S05']
                 and o02.get('S10', {}).get('output_fields') == ['remaining_owner_causes', 'automatic_cause_evidence']
                 and o02.get('S06', {}).get('depends_on') == ['S10']
                 and o02.get('S06', {}).get('executor') == {'type': 'human', 'ref': 'owner'}
                 and o02.get('S06', {}).get('approval', {}).get('never_auto') is True
                 and _terms(proxy_case.get('requires'), 'non-billing', 'billing_unreliable is excluded', 'Q63')
                 and o02.get('S11', {}).get('executor') == {'type': 'deterministic', 'ref': 'amt-control'}
                 and set(o02.get('S11', {}).get('depends_on') or []) == {'S05', 'S06'}
                 and live_causes.get('workflow') == 'WF-O02'
                 and _terms(live_causes.get('initial_snapshot'), 'audit only', 'never the post-recovery resume truth')
                 and live_causes.get('exact_match') == ['raised_control_event_id', 'clearance_control_epoch', 'key_and_period',
                    'approved_policy_revision', 'fresh_reconciliation_evidence', 'actual_plus_reserved_allowance_evidence']
                 and _terms(live_causes.get('historical_clear'), 'authenticated against live state at the successful clear transaction',
                            'remains valid across later authorized epoch changes', 'separately re-reads fresh current causes',
                            'never resolves a new raised_control_event_id')
                 and _terms(live_causes.get('owner_routing'), 'excludes billing_unreliable', 're-reads', 'owner never_auto')
                 and _terms(live_causes.get('closure'), 'zero unresolved required', 'newly raised owner causes', 'never auto-approved')
                 and _terms(live_causes.get('signal_rule'), 'wake-up reference only', 'missing/stale/mismatched/replayed')
                 and _terms(live_causes.get('observation'), 'recheck at admission', 'during observation', 'block/reset the full window')
                 and _terms(o02.get('S07', {}).get('inputs'), 'every containment_cause_changed', 'restarts the full window after verified closure')
                 and cause_signal.get('producers') == [{'service': 'amt-control'}]
                 and cause_signal.get('transport') == 'control_event' and cause_signal.get('dedup') == 'control_event_id'
                 and 'containment_cause_changed' in _wf(c, 'WF-O02').get('continuation', {}).get('signals', []),
                 'Q63 incident recovery must use fresh remaining owner causes plus exact billing-clear evidence; S11 live closure, not the S03 snapshot or admission reopening, gates observation')
