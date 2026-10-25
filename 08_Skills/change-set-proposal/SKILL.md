---
name: change-set-proposal
description: How Wolter AMT agents propose external changes — every Meta write or manual proposal becomes a revision-bound command that humans approve per policy and the gateway executes after re-validation; required fields, expected-effect and rollback rules, hard limits, approval routing, the outcome loop and Trust Ramp counting.
---

# Change-set proposal

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Principle: **agents propose, humans approve, code executes** (ADR-006). A Meta write tool call does not change Meta; it creates a revision-bound command in the change set. Users of this skill: media-buyer (Meta write proposals), cmo and funnel-analyst (`change_set.propose_manual` items the owner performs by hand), funnel-analyst (outcomes with `change_set.record_outcome`), reviewer (completeness check). Canonical state and dispatch contract: [INVARIANTS I03–I07](../../11_Production_Contracts/INVARIANTS.md), [GUARDRAIL_GATEWAY](../../03_Architecture/GUARDRAIL_GATEWAY.md), [DATA_MODEL §6](../../03_Architecture/DATA_MODEL.md). Tool, action, approver and path authority: [approval-policy](../../09_Config_Templates/approval-policy.yaml) — this skill does not duplicate the allowlists.

## 1. Required fields (the gateway rejects incomplete items)

| Field | Content |
|---|---|
| `action_type` | Set by the gateway from the tool and the entity state (you do not choose it): `creative_activate`, `ad_create`, `asset_upload`, `budget_change`, `entity_pause`, `entity_activate`, `campaign_create`, `campaign_activate`, `adset_duplicate`, `experiment_exposure`, `events_manager_change`, `amo_pipeline_change_proposal` |
| `pipeline` | `sale` · `rent` · `shared` |
| `target` | Schema-valid `{account_id, campaign_id, adset_id, ad_id}` as applicable; managed scope only |
| `params` | Tool parameters; money as **integer minor units** with explicit currency, never floats or strings |
| `current_state` | What it is now, from `meta_read.*` or the warehouse, with source timestamp and entity state version |
| `proposed_state` | What it will be |
| `expected_effect` | `{metric, direction, range_low, range_high, horizon_days, basis_tag, scope}` — a range with basis (`basis_tag` = `D`, `T`, `X` or `?`), never invented precision; may be wide. `scope` is `pipeline` or `entity` (entity only with an entity-level `wh.metrics` endpoint); any other command in that scope whose execution or open effect window intersects the item's window — protective pauses, kills and earlier commands included — makes the outcome `inconclusive` (◇ P-43, P-58). `horizon_days` is not shorter than the approved maturity horizon of that metric (`business.acceptance`) |
| `rollback_spec` | Exact reverse as a new controlled action (for example restore budget to the previous minor amount; pause ad X); never a replay of an old payload |
| `risk` | `low` · `medium` · `high` + one-line reason (learning reset, spend pace, policy, capacity) |
| `evidence` | References: `wh.metrics`/`wh.query`, `meta_read`, Langfuse trace, offer revision, creative revision and `asset_manifest_sha`, Reviewer verdict revision |
| Revisions | Payload, asset, offer and review revisions plus source time and baseline references |

The gateway answers with `{status: queued | shadow | needs_owner, command_id, revision}`. `queued` is a durable command, not an approval; `shadow` means recorded as SHADOW (pipeline `L0_shadow` or global `shadow`) and never executed; `needs_owner` means an owner-only decision is required — it is not success. Rejections use the canonical error codes ([GUARDRAIL §10](../../03_Architecture/GUARDRAIL_GATEWAY.md)), for example `budget_change_exceeds_limit`, `monthly_cap_exceeded`, `foreign_entity`, `tracking_gate`, `offer_mismatch`, `revision_stale`, `readiness_blocked`.

The human-facing summary shown in Telegram is Uzbek, at most three lines: **what · why · expected effect · rollback**.

## 2. Hard limits (enforced in gateway code — do not try to work around them)

- **Rolling 24h movement:** the sum of absolute ordinary budget changes per entity over rolling 24 hours ≤ 20% of the trusted window-start budget (◇ P-01; Q08/Q32 ✅). Human edits do not silently reset the base; zero or unknown baseline → owner review, no automatic increase; CBO/ABO counts once.
- **Monthly ads cap:** USD 1 500/oy (150 000 USD minor), admission = verified MTD + Σ(active daily × remaining days) + held commitments + requested ≤ cap − safety margin ([budgets.yaml](../../09_Config_Templates/budgets.yaml) `ads.admission_rule`), in the provider counter currency. The Ads Manager account spending limit is a mandatory, independent backstop (Q37 ✅); `protective_pause` is an additional deterministic layer (◇ P-21), not your tool.
- **Creation and activation:** `campaign_create`, `ad_create` and `adset_duplicate` create PAUSED entities. The first activation of a campaign or ad set created via `campaign_create` or `adset_duplicate` (`ever_active = false`) is `campaign_activate` — owner-only, NEVER_AUTO; an ads_approver approval returns `needs_owner`. Activating an ad (new from `ad_create`, or a creative swap) inside an active ad set is `creative_activate` (owner or ads_approver, independent Reviewer pass).
- **Review requirement:** an action with `review_required: true` goes `new → pending_review` and needs an independent Reviewer pass on the exact revision before approval and claim; `asset_upload`, `ad_create` and `creative_activate` also need the human language check for the first 20 live-eligible copy artifacts and, for `asset_upload`, cleared asset rights. A Reviewer `fail` never enters the change set; a human check never replaces the Reviewer.
- **Tracking gate:** one real fail day → alert; two consecutive fail days → global `read_only` (`tracking_gate`); missing or stale required signals block risk-increasing dispatch immediately.
- **Modes:** pipeline `L0_shadow` (F5, kill criteria) or global `shadow` → recorded as SHADOW (`pipeline_shadow`), never executed; `killed` → `write_mode_killed`.
- **Business readiness:** ordinary rent budget changes need today’s accepted fleet snapshot revision (capacity hold otherwise); a sale increase or rent→sale shift needs valid sale readiness; a triggered KC-02 or non-`valid` lead→contract data blocks budget increases.
- **No-tool list:** spend cap, billing, automated rules, audiences, lead forms, dataset/Pixel settings, deletions and comments are never changed through AMT tools. Events Manager changes are manual proposals the owner performs.

## 3. Approval routing ([approval-policy](../../09_Config_Templates/approval-policy.yaml) `actions`)

| Action | Approvers | Max level | `review_required` |
|---|---|---|---|
| `asset_upload` | — (auto, audited) | auto | true |
| `budget_change`, `entity_activate`, `creative_activate`, `ad_create` | owner or ads_approver | L2 after graduation | true |
| `entity_pause` | owner or ads_approver | L2 after graduation | false |
| `experiment_exposure` | owner or ads_approver | L1 | true |
| `campaign_create`, `campaign_activate`, `adset_duplicate` | owner | NEVER_AUTO | true |
| `events_manager_change` (owner performs it manually after approval) | owner | NEVER_AUTO | true |
| `amo_pipeline_change_proposal` (owner performs it manually) | owner | NEVER_AUTO | false |

Effective level = `min(global mode, pipeline mode, trust level)`. Daily batch at 10:00 with a 12-hour TTL from `presented_at`; urgent items carry their own `presented_at`. L1 has no approval by silence; expiry means not executed (Q32 ✅). Editing an approved item is numeric decrease-only and creates a new revision that needs a new review and approval.

## 4. Good vs bad proposal

✅ Good (synthetic format example, not a real recommendation): “Ijara · `budget_change` · ad set kunlik budgeti `<old_minor>` → `<new_minor>` (+`<pct>`%; rolling24h yig‘indisi undan keyin `<used_pct>`%) · Sabab: bugungi `accepted` snapshot’da bo‘sh velosiped band chegarasidan yuqori [D: fleet.read_utilization, snapshot revision], qualified CPL baseline oralig‘ida [D: wh.metrics, measurement revision] · Kutilgan: `<horizon_days>` kunda qualified lead `<range_low>`…`<range_high>` [T: asos, masalan o‘xshash o‘zgarish tarixi yo‘qligi] · Rollback: `<old_minor>` ga qaytarish.”

❌ Bad: “Byudjetni oshiramiz, natija 23.7% yaxshilanadi.” — no source, invented precision, no rollback, no revision.

## 5. Batching and noise

- Prefer **one well-reasoned item** over many small edits (learning phase, approver fatigue).
- Group related items under a shared evidence link; the ops-bot shows them together.
- Never resubmit a rejected item unchanged; address the rejection reason or drop it.
- Never split one change into several items to stay under a limit.
- Items reviewed by the 09:45 cutoff join the 10:00 batch; later items go separately with their own TTL.

## 6. After dispatch: states and the outcome loop

The canonical lifecycle is `pending_review → pending_approval → approved → claimed → executing → succeeded`, with alternatives `rejected`, `expired`, `cancelled`, `failed_confirmed` and `uncertain → reconciling → succeeded | failed_confirmed | manual_resolution`. Manual items use `approved → awaiting_manual → done_manual`. `expired`, `rejected`, `cancelled` and `uncertain` never mean executed; a provider timeout may still have produced an external effect. Every dispatch, retry and rollback rechecks revisions, role, policy, control epoch, freshness and capacity/spend guards; an old approval does not revive after kill/resume, offer change or re-takeover; vendor idempotency is not assumed.

Outcome loop:

1. `outcome_check_at = succeeded_at` (or `done_manual_at`) `+ horizon_days`; a deterministic workflow timer (WF-B07, one run per command) runs the outcome step at that time — no agent memory or routine is relied on.
2. The deterministic `outcome_classify` (WF-B07 S02, `sync-worker`) computes `met | not_met | inconclusive` from `expected_effect` and `wh.metrics` (`approval-policy.yaml` `trust_ramp.graduation.met_rule`: inside the band and in the stated direction, `data_status` valid) and writes it with `data_status`, `countable` and evidence into the append-only `command_outcomes` ledger. The funnel-analyst only annotates a `not_met` or `inconclusive` outcome via `change_set.record_outcome` and never changes it (◇ P-42); a correction is a new record with `supersedes_id`.
3. Data that is not `valid` (immature, insufficient sample, incomparable baseline, missing or stale) gives `inconclusive`, never `met`. Harm is computed by `outcome_classify` (`trust_ramp.graduation.harm_rule`: a move against the stated direction beyond the band by more than `business.acceptance.harm_margin_pct`, a guardrail breach in scope, or a WF-O02 incident naming the command); the funnel-analyst may add a one-way `harm_flag` to any outcome, `met` included, and nobody can clear it (◇ P-54). Harm is recorded as an incident and demotes the pair.
4. Trust Ramp counts only a countable `met` (`basis_tag` D, T or X; relative band width within `business.acceptance.outcome_band_max_relative_width`): 10 consecutive such live items plus 14 incident-free days after the last counted item, per action_type × pipeline, with `budget_change` increases and decreases as separate pairs (★, ◇ P-42); any other result — `not_met`, `inconclusive`, harmful, rejected, ✏️ edited, expired or cancelled — resets the pair's streak (interim stricter reading, reviewed at HG-F5-04); SHADOW items do not count. A wide band is honest, but it does not count toward autonomy. CMO proposes graduation at C12; the owner decides with `/graduate` (HG-L2-01). NEVER_AUTO actions never graduate.

## 7. Never

- Never describe an item as done before its command is `succeeded` or `done_manual` with remote evidence.
- Never turn a timeout into `failed_confirmed` or resubmit blindly.
- Never split one change to stay under limits or bypass the review requirement.
- Never include personal data in params, evidence or summaries.
- Never promise fabricated lift; numbers without basis stay unknown.

## Tool scope

Machine-checked by the bundle validator (rule D15, F4-AT-17). A role is instructed to call a tool here only where it is listed; every listed role holds the tool in `approval-policy.yaml#agents.<slug>.tools` and loads this skill in its charter. `citation` = the tool appears only as an evidence-source format; `—` = any role may cite a source it received, calling it still needs the tool. The gateway refuses every tool outside the caller's allowlist regardless of this table.

| Tool | Instructed roles | Mention |
|---|---|---|
| `change_set.propose_manual` | cmo, funnel-analyst | call |
| `change_set.record_outcome` | funnel-analyst | call |
| `wh.metrics` | media-buyer, cmo, funnel-analyst | citation |
| `wh.query` | media-buyer, cmo, funnel-analyst | citation |
| `fleet.read_utilization` | media-buyer, cmo, funnel-analyst | citation |
