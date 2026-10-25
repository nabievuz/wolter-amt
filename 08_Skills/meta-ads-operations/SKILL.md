---
name: meta-ads-operations
description: Operating rules for Wolter's Meta Ads account — consolidated structure per pipeline, naming, one experiment per pipeline, learning-phase discipline, capacity-aware rent budgeting from today's accepted fleet snapshot, optimisation-event choice (Lead vs QualifiedLead), the 08:30 daily check, the read/write tool boundary and incident handling.
---

# Meta ads operations

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Applies to media-buyer (operator) and, read-only, to cmo and funnel-analyst. Read [INVARIANTS](../../11_Production_Contracts/INVARIANTS.md) I03–I07 and I10–I12 and [BUSINESS_CONTRACT](../../11_Production_Contracts/BUSINESS_CONTRACT.md) before budget, activation or performance decisions. Tools and action mapping live in [approval-policy](../../09_Config_Templates/approval-policy.yaml); the concrete pinned Meta read-tool list is configured (`vendor.meta_read_tools`), never inferred from a wildcard. Exact Meta product behaviour (objectives, Advantage+ options, learning thresholds, category rules) changes often: verify it against current official documentation and account diagnostics before relying on any specific number [?].

## 1. Account structure (consolidation — Q41 ✅)

- Per pipeline (`sale`, `rent`): few campaigns and few ad sets; prefer broad or Advantage+ audiences and let creatives do the targeting; do not slice audiences finely.
- Naming and URL parameters are defined once in [TRACKING_CAPI §2](../../03_Architecture/TRACKING_CAPI.md) — follow it exactly. Summary: campaign `wlt_{pipeline}_{objective}_{yyyymm}_{slug}`; ad set `wlt_{pipeline}_{audience}_{yyyymmdd}_{slug}`; ad name = `creative_id`; URL parameters `utm_source=meta&utm_medium=paid_social&utm_campaign={{campaign.id}}&utm_term={{adset.id}}&utm_content={{ad.id}}`. Ad → exact creative revision binding is stored separately; never parse ad names as the join.
- The pipeline of an entity comes from the managed-entity register; taken-over campaigns keep their names (owner-approved mapping, HG-F6-04). Released or foreign entities are never written.
- New campaigns, ads and ad sets are created **PAUSED**. The first activation of a campaign or ad set created via `campaign_create` or `adset_duplicate` is `campaign_activate` — owner-only, NEVER_AUTO. `entity_activate` re-activates a campaign or ad set that was active before; activating an ad inside an active ad set is `creative_activate`. `adset_duplicate` is owner-only.
- Media-buyer uploads only registered creative revisions that passed independent review (and the human language check where required).

## 2. Optimisation event (Q29.1 ✅)

- Optimise toward **QualifiedLead** (CAPI CRM signal) only when BOTH hold: (a) account eligibility evidence and (b) the monthly volume measured in F2 from amoCRM (before `agents.run` the builder runs the funnel-analyst procedure, ◇ P-31; then re-measured per pipeline on the first Monday of every month over the previous calendar month by `qualified_volume_check` (P-56), counting crm_confirmed Meta-attributed submissions; the switch up needs 2 consecutive passing months, the switch back happens at the first miss, and only the owner switches — P-45) reaches the larger of the owner floor (~200 leads per month, Q29.1) and Meta’s current official requirement, cited with a dated source ([business-policy.yaml](../../09_Config_Templates/business-policy.yaml) `qualified_optimization_rule`, readiness `vendor.qualified_optimization`; OI-01, OI-02).
- Otherwise optimise for `Lead`; qualified stays the guardrail. General benchmark volumes do not establish eligibility.
- Changing the optimisation event resets learning — a major change that needs a plan and owner-visible rationale; never flip-flop.

## 3. Learning-phase discipline

- Avoid edits to ad sets in learning: no repeated budget changes, no frequent creative swaps; batch changes. The gateway enforces a minimum interval between budget increases on the same entity or its parent (`budget.ads_limits.min_interval_hours`, `change_set.change_spacing`, ◇ P-43); decreases, pauses, protective pauses and Q38 urgent items are exempt.
- Report “learning limited” ad sets in the daily check; consolidate rather than multiply.
- Larger budget moves happen over several days inside the rolling-24h absolute bound (◇ P-01); never split a move to stay under it.

## 4. One experiment per pipeline (Q41 ✅)

- At most one live experiment per pipeline (creative concept, audience, optimisation event or offer — coordinated with CRO landing changes by the CMO plan).
- Each has a DAT-04 card registered **before** launch (funnel-analyst `experiment.create`): hypothesis, primary metric (qualified leads / qualified CPL), guardrail (lead→contract), cell split, baseline revision, minimum sample and maturity, minimum duration of at least one full week, maximum exposure, stop rule (DEC-05). Live exposure needs the `experiment_exposure` approval. The card pre-registers the design of `decision-statistics.yaml` EXPERIMENT (decision, MDE, alpha, power, minimum exposure, maximum duration, margin); an underpowered design is labelled exploratory before launch. While it runs, the gateway `experiment_lock` refuses other increases, creative swaps and structure changes in that pipeline; decreases and pauses stay allowed (◇ P-43). `inconclusive` is a valid outcome and never a winner.

## 5. Capacity-aware rent budgeting (ADR-014, Q43 ✅ / Q43★)

Rent budget proposals are made only by the `rent_capacity_review` trigger on `fleet_snapshot_accepted`, from that snapshot revision ([capacity-policy.yaml](../../09_Config_Templates/capacity-policy.yaml)):

| Band | Condition | Proposal |
|---|---|---|
| `waitlist_high` | `waitlist_eligible_ready ≥ waitlist_high` | Reduce rent budget toward the owner-approved floor (`rent_floor_daily_minor`), within the rolling-24h bound; freed budget moves to sale only with valid sale readiness, otherwise it may stay unspent |
| `fleet_slack` | `available_bikes ≥ available_high` and `waitlist_eligible_ready = 0` | Increase rent budget within budget, approval and the rolling-24h bound, if qualified CPL is within the baseline band |
| otherwise | — | No change (`hysteresis_days` applies) |

- Thresholds are calibrated from real data (`fleet.thresholds`, F5_GO; OI-14); until approved the policy runs `report_only` and proposals stay advisory. Never invent a threshold.
- No accepted snapshot today → ordinary rent budget changes are held from the start of the day; the 08:30 daily check makes no rent budget proposal. Reminder 09:00 and escalation 14:00 only notify; without a valid snapshot by 14:00 the whole day stays held. A stale snapshot is never valid; freshness is checked again at proposal and dispatch.
- A snapshot accepted before 09:45 can put reviewed rent items into the 10:00 batch; later ones go separately with their own TTL. Protective controls are unaffected by the hold.
- Physical utilization (`rented_bikes / serviceable_bikes`), monthly transactions, renewals and bike-days stay separate; transactions per month are never the physical denominator.

## 6. Daily check (08:30, L1)

1. Spend pace vs the monthly cap: verified MTD, held commitments, safety margin; provider spending-limit headroom (`spend_cap − amount_spent`, a cumulative counter updated monthly by the owner — HG-OPS-01).
2. Delivery: rejected ads, account-quality notices, learning-limited ad sets, drift from human edits.
3. Anomalies vs the recent pattern (CPM, CTR, CPL, landing-view rate) — run DAT-05 before calling anything a trend.
4. Qualified signal from the warehouse — lag-aware, with `data_status`; rolling-24h movement already used.
5. Sale readiness state for any sale increase; KC-02 and lead→contract guard.
6. Output: an L1 note via `workflow.submit_output` and 0–N proposals for sale and non-capacity items — often zero is right.

## 7. Tool boundary

| Read (allowed) | Write (only as a command proposal, media-buyer) |
|---|---|
| `meta_read.*` — the pinned read allowlist (insights, structure, diagnostics, Pixel/dataset quality, spend-limit read-back) | `meta_write.pause_entity`, `meta_write.activate_entity`, `meta_write.update_budget`, `meta_write.create_campaign_paused`, `meta_write.create_ad_from_creative`, `meta_write.duplicate_adset`, `meta_write.upload_creative_asset` |

byadsco write tools are never exposed; Meta writes go through the gateway’s narrow SDK operations (Q40 ✅, ADR-005). Spend cap, billing, automated rules, audiences, lead forms, dataset/Pixel settings, deletions and comments are outside AMT tools. Events Manager changes are manual proposals (funnel-analyst `change_set.propose_manual`) the owner performs by hand after approval.

## 8. Incidents

- **Overspend risk:** urgent `entity_pause` proposal if a human decision helps; the deterministic `protective_pause` (◇ P-21) pauses managed entities when headroom reaches the safety margin or spend data goes stale; the provider spending limit stays the independent cap (Q37 ✅). Human-managed (foreign) campaigns are never paused by AMT — alert and owner handback only.
- **Ad rejected or account restricted:** ALERT_META_REJECTED / ALERT_ACCOUNT_RESTRICTED and a Reviewer issue; new `ad_create` proposals stop until the Reviewer re-checks; the verbatim rejection reason feeds the policy-review enforcement log through WF-E04.
- **Tracking gate failing** (two consecutive days → `read_only`, `tracking_gate`): no optimisation proposals; wait for the funnel-analyst diagnosis and the owner `/resume`.
- **Kill criteria triggered** (deterministic weekly job, KC-01): that pipeline is `L0_shadow` with human handback; proposals for it are recorded as SHADOW only; support the C05 RCA. Resume and re-takeover are owner actions.
- **Account spending limit reached:** ads stop by themselves; only the owner raises the cap (HG-OPS-01, [INCIDENTS](../../06_Runbooks/INCIDENTS.md)).

Read-only, shadow, killed and freshness guards remain binding at every dispatch even if an action has approval. Done means a source-backed proposal or a remotely confirmed canonical command result — never an LLM intention to change advertising. Human output Uzbek Latin, PII-free; keys and IDs English.

## Tool scope

Machine-checked by the bundle validator (rule D15, F4-AT-17). A role is instructed to call a tool here only where it is listed; every listed role holds the tool in `approval-policy.yaml#agents.<slug>.tools` and loads this skill in its charter. `citation` = the tool appears only as an evidence-source format; `—` = any role may cite a source it received, calling it still needs the tool. The gateway refuses every tool outside the caller's allowlist regardless of this table.

| Tool | Instructed roles | Mention |
|---|---|---|
| `meta_read.*` | media-buyer, cmo, funnel-analyst | call |
| `meta_write.pause_entity` | media-buyer | call |
| `meta_write.activate_entity` | media-buyer | call |
| `meta_write.update_budget` | media-buyer | call |
| `meta_write.create_campaign_paused` | media-buyer | call |
| `meta_write.create_ad_from_creative` | media-buyer | call |
| `meta_write.duplicate_adset` | media-buyer | call |
| `meta_write.upload_creative_asset` | media-buyer | call |
| `workflow.submit_output` | media-buyer | call |
| `experiment.create` | funnel-analyst | call |
| `change_set.propose_manual` | funnel-analyst | call |
