---
name: funnel-metrics
description: Canonical analysis procedure for Wolter AMT metrics — funnel stages and sources, attribution keys, KPI and data_status definitions, rent capacity logic, lag and cohorts, baselines and seasonality, kill criteria, tracking health, the weekly report dataset, and how to run C07 and C05 on Wolter data.
---

# Funnel metrics

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

All agents use these definitions; metric semantics, event grains and formulas are owned by [BUSINESS_CONTRACT](../../11_Production_Contracts/BUSINESS_CONTRACT.md) §§2–8 and this skill is the analysis procedure. Never compute a KPI differently in a report; a definition changes only through the contract, a versioned skill change (WF-E04) and a new measurement revision whose date is logged (DAT-05 trap “measurement change”). Thresholds and sources: [business-policy](../../09_Config_Templates/business-policy.yaml), [readiness](../../09_Config_Templates/readiness.yaml), [kill-criteria](../../09_Config_Templates/kill-criteria.yaml), [tracking-health](../../09_Config_Templates/tracking-health.yaml), [capacity-policy](../../09_Config_Templates/capacity-policy.yaml).

## 1. Funnel and facts (per pipeline: `sale`, `rent`)

`impression → click → landing session → submission → lead → qualified → contract`, plus independent business facts. Events are not one linear status chain (`pipelines.yaml#lifecycle_is_linear: false`): payment, delivery, rental start, renewal, cancellation and refund are separate facts that may arrive in any order; a missing fact is `unknown/pending`, never zero or paid.

| Stage / fact | Source | Grain and rule |
|---|---|---|
| impression, click, spend | Meta insights via `meta_read.*` → warehouse | per campaign/ad set/ad and day, provider currency in minor units |
| landing session | Umami (`analytics.umami_query` → warehouse) | sessions by UTM source/campaign/content |
| submission | landing durable intake | `accepted → crm_pending → crm_confirmed`; resend is not a new acquisition |
| lead | amoCRM lead bound to the submission | `lead_id`, pipeline, UTM, `has_fbc` flag; no personal data |
| qualified | first valid qualified fact per `lead_id × pipeline` (Q16 ✅; fact rule in `pipelines.yaml` `qualified_fact_rule`, ◇ P-19) | re-entry is not a new North Star |
| contract, payment, fulfilment, renewal, cancel, refund | source systems via ingest | independent facts with source IDs, correction references |

**Attribution** (canonical: [TRACKING_CAPI §2](../../03_Architecture/TRACKING_CAPI.md)): lead → ad via `utm_content = {{ad.id}}`, `utm_term = {{adset.id}}`, `utm_campaign = {{campaign.id}}`; ad → exact creative revision via the stored ad binding (ad name = `creative_id` is not the join); pipeline via the managed-entity register. First-touch, last-touch, unknown/consent-limited and Meta-reported results are shown side by side and never summed. Warehouse joins never use personal data.

## 2. KPI definitions

| Metric ID | Definition | Notes |
|---|---|---|
| `qualified_leads` | leads whose first qualified fact falls in the period, per pipeline | **North Star** (Q04 ✅) |
| `qualified_cpl` | pipeline spend in the period ÷ `qualified_leads` | event-week (fast signal) and lead-cohort (truth) shown separately; KC-01 uses `qualified_cpl_event_week` |
| `lead_to_qualified` | qualified ÷ leads, by lead-creation cohort | mark immature cohorts |
| `lead_to_contract` | contracts ÷ leads, by cohort | guardrail; KC-02 |
| `cpl` | spend ÷ leads | diagnostic only (Goodhart) |
| `cash_contribution` | finance-approved contribution from source totals | only with `business.contribution_policy`; otherwise `[?]` |
| `utilization` | `rented_bikes / serviceable_bikes` from today’s valid snapshot | zero denominator → `unknown` |
| `waitlist_eligible_ready` | deduplicated current demand ready to rent | snapshot count drives bands; CRM status is a cross-check (⧗ OD-07) |
| `rent_transactions_month` | all rent transactions incl. renewals per month | context only: Jun–Sep 2026 570, 557, 540, 512 [D: owner, Q43 ✅], capacity ≈ 600/month [D: owner]; never the physical denominator |

## 3. Data status (canonical)

Every number carries one `data_status` ([business-policy.yaml](../../09_Config_Templates/business-policy.yaml) `data_status_definitions`):

| `data_status` | Meaning | Decision effect |
|---|---|---|
| `valid` | spend > 0, sample and maturity rules met, baseline comparable | may support a decision |
| `no_activity` | spend = 0 and qualified = 0 | not evaluated |
| `no_spend` | spend = 0 and qualified > 0 | not evaluated |
| `spend_zero_qualified` | spend > 0 and qualified = 0 | CPL undefined; counts toward exposure and the bad-week streak; scale blocked |
| `insufficient_sample` | below the approved minimum sample | inconclusive |
| `not_mature` | outcome window not closed | inconclusive |
| `incomparable_baseline` | qualification or tracking revision differs from the baseline | inconclusive |
| `missing_data` | required source rows absent | blocked + alert |
| `stale_data` | source older than the approved freshness cutoff | blocked + alert |

## 4. Capacity logic (rent)

- More rent leads are valuable only when there are available bikes or the eligible waitlist needs refilling (ADR-014).
- Bands come from [capacity-policy.yaml](../../09_Config_Templates/capacity-policy.yaml) (`waitlist_high`, `fleet_slack`, otherwise no change, hysteresis); thresholds are calibrated from data (`fleet.thresholds`), never invented.
- Today’s snapshot missing or invalid → all ordinary rent budget movement is held immediately; the 09:00 reminder and 14:00 escalation do not extend data validity. A rent→sale shift needs valid sale readiness; unused rent budget may stay unspent.

## 5. Lag and cohorts

- Qualification and contracts happen days after the lead. Report cohorts by lead-creation week and mark the latest cohorts `not_mature` until the measured lag (F2, from history) has passed.
- State which view a number uses: event-period or cohort.

## 6. Baselines and seasonality

| Baseline | Built in | Used for |
|---|---|---|
| Takeover baseline | F2 — last 8 weeks before shadow, per pipeline | kill criteria, F6 comparison |
| Seasonal profile | F2 — 12+ months of amoCRM history (or all available), monthly per pipeline | interpreting winter and holiday changes |
| Rent transactions | owner monthly data + warehouse | capacity context |

Comparability is checked, not assumed: qualified definition and effective date, source coverage, measurement revision, offer/landing/stock changes, lag and exclusions. Unauditable old data is labelled `legacy_proxy` and a new comparable baseline is collected. The F6 comparison (rent AI vs its baseline, sale targetologist vs its baseline) uses difference-in-differences only as a diagnostic unless parallel trends are supported (`kill-criteria.yaml` `baseline.diff_in_diff`); state that it is quasi-experimental.

## 7. Kill criteria

KC-01: `qualified_cpl_event_week` of a pipeline worse than its comparable baseline by more than 25% for 2 consecutive weeks, with the minimum sample from `business.acceptance` (Q31 ✅) → evaluated by the **deterministic** job on Monday 07:30, not by an agent; the pipeline goes `L0_shadow` with human handback and an urgent alert. KC-02: lead→contract worse beyond its approved threshold → automatic increases blocked and an alert. Your job: the C05 RCA and correct outcome/experiment records; you never reopen a gate.

## 8. Tracking health (daily 09:30, deterministic; the analyst owns the diagnosis)

Check IDs and gate relevance: [TRACKING_CAPI §6](../../03_Architecture/TRACKING_CAPI.md) and tracking-health.yaml — gate checks `fbc_share`, `fbp_share`, `untagged_leads`, `capi_error_rate`, `pixel_capi_dedup`, `pixel_vs_crm_leads`, `accepted_vs_crm_receipts`, `queue_oldest_age`, `sync_freshness`; informational `capi_lag_p95`, `emq`. One real fail day → alert; two consecutive fail days → global `read_only`; missing or stale signals block risk-increasing dispatch at once. Thresholds come from 14 days of report-only measurement and owner approval (`tracking.thresholds`). The analyst finds the root cause and proposes fixes and threshold changes with data; it never toggles the gate.

## 9. Weekly report dataset (Q24 ✅)

Submitted by funnel-analyst on Monday 08:00 with `report.submit` (BLUF ≤ 250 words + full report), pre-checked by the Reviewer before 09:00, published by the ops-bot at 09:00 ([business-policy.yaml](../../09_Config_Templates/business-policy.yaml) `weekly_report_metrics`):

- qualified leads per pipeline; qualified CPL per pipeline; lead→contract;
- spend vs limit; best and worst creative with a minimum N and attribution coverage;
- next week’s experiments; rent utilization and eligible waitlist;
- data gaps and freshness; Trust Ramp state (including the rubber-stamp signal when rejects/edits stay near zero, Q38 ✅); cash/contribution when available;
- kill-criteria and exposure status per pipeline.

Every number has a source, `as_of` and `data_status`; synthetic or test data never appears as business reporting.

## 10. How to run C07 on Wolter data (weekly, L3)

| Phase | Model | Wolter-specific question |
|---|---|---|
| P1 | DAT-01 driver tree + Goodhart | qualified_leads = sessions × lead rate × qualification rate; which leaf moved? guardrails lead→contract, CPL vs qualified CPL |
| P2 | DAT-02 funnel and cohort | largest absolute loss per pipeline; immature cohorts flagged |
| P3 | DAT-03 unit economics | cost per qualified and per contract vs contribution (only with the approved policy; else `[?]`) |
| P4 | DAT-05 + PPL-02 | statistical traps (Simpson across pipelines, small N, seasonality, tracking changes); incentives (sales tagging behaviour, rubber-stamp approvals) |
| P5 | PRI-03 RICE + DEC-05 | next week’s ≤ 1 experiment per pipeline with stop rule |
| P6 | — | optimisation plan + DAT-04 designs → CMO handoff; weekly report data |

## 11. How to run C05 (RCA)

DGN-01 IS/IS NOT (which pipeline, weeks, creatives, placements; new vs renewal for rent) → DAT-01 + DAT-05 (did measurement change?) → DGN-03 fishbone → DGN-02 why-chain → DGN-05 + EST-03 (competing hypotheses, update with evidence) → PRI-01 + IMP-01 (fix + monitoring).

First assignment: the **rent decline 570 → 512 transactions/month (June → September 2026)** — hypotheses to test, not conclusions: seasonality, churn/renewals, fleet availability (bikes out of service), competition, pricing [T].

## 12. Data access rules

- Heavy analysis only through `wh.query` / `wh.metrics`; amoCRM reads stay incremental under the global ceiling of 7 requests per second (Q25 ✅); bulk scraping can block the account.
- No personal data in queries, outputs or handoffs; the warehouse has none by design. Customer conversations never reach agent output.
- Inconclusive is a real result with exposure and a deadline; it never counts as a clean Trust Ramp item.

## Tool scope

Machine-checked by the bundle validator (rule D15, F4-AT-17). A role is instructed to call a tool here only where it is listed; every listed role holds the tool in `approval-policy.yaml#agents.<slug>.tools` and loads this skill in its charter. `citation` = the tool appears only as an evidence-source format; `—` = any role may cite a source it received, calling it still needs the tool. The gateway refuses every tool outside the caller's allowlist regardless of this table.

| Tool | Instructed roles | Mention |
|---|---|---|
| `analytics.umami_query` | cmo, cro, funnel-analyst | call |
| `report.submit` | funnel-analyst | call |
| `wh.query` | media-buyer, cmo, cro, funnel-analyst | call |
| `wh.metrics` | media-buyer, cmo, cro, funnel-analyst | call |
