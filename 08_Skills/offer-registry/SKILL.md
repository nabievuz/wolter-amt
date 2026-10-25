---
name: offer-registry
description: How Wolter AMT agents read and propose commercial offers — the owner-approved registry (config/offers.yaml) is the only source for prices, terms, claims, forbidden claims, restrictions, capacity conditions and brand facts; agents cite offer_id + revision everywhere and handle revocation and expiry of live artifacts.
---

# Offer registry

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

The registry is the **single source of truth** for every commercial statement in ads and on the landing page: prices, discounts, promotions, warranty, installment conditions, rental periods, deposits, bundles — and for brand facts that copy may state. Semantics: [BUSINESS_CONTRACT §9](../../11_Production_Contracts/BUSINESS_CONTRACT.md). Template and schema: [offers.yaml](../../09_Config_Templates/offers.yaml); deployed as the immutable owner-approved `config/offers.yaml` of the active release, never an agent-editable working file. Unknown fields close through `offers.initial` (HG-F2-15), `offers.asset_rights` and `offers.propagation` in [readiness](../../09_Config_Templates/readiness.yaml).

## 1. Rules

1. **Read with `offers.read`.** Bind `offer_id + revision`, validity window and approval source. Every price or term in any artifact carries that reference (creative manifest, landing variant config, change-set evidence).
2. **Only active offers:** `status: active` and the publication time within `valid_from`–`valid_to`. `draft`, `paused`, `expired` and `revoked` offers never appear in ads or on the landing page.
3. **Exact wording:** approved `claims` (Uzbek, optional Russian) are used as written. A hook may be adapted; numbers, conditions and guarantees never are.
4. **Forbidden claims:** `forbidden_claims` of the offer are never used, even paraphrased; the Reviewer fails them.
5. **Restrictions:** eligibility, territory and channel `restrictions` are honoured in copy, targeting and landing.
6. **Capacity-bound offers:** a rent offer with `capacity_bound` runs only under its stated capacity band or stock condition; urgency is never proposed while the eligible waitlist is long. Registry activity is not physical availability.
7. **Brand facts:** a factual statement that is not an offer term (for example the number of stations) is allowed only from the registry `facts` list (`fact_id`, `text_uz`, optional `text_ru`, `source_ref`, `valid_to`), cited by `fact_id`.
8. **Special ad category:** `special_ad_category: unknown` blocks activation; installment/credit offers need a verified category decision first (Q42 ✅).
9. **Only the owner changes the registry** (Q35 ✅). Only `cro` and `cmo` (owner ideas via Telegram, Q47 ✅) may open `offers.propose_pr`; other roles report the need through a handoff or blocker for them. `offer_change` is NEVER_AUTO and merges only by the owner. The landing offer snapshot is generated from the approved registry by CI and is never edited by hand.
10. **No invented offers** in chat, plans or drafts. A new idea becomes a PR proposal with rationale.

## 2. Offer schema (summary — full template in offers.yaml `example_schema`)

```yaml
- offer_id: rent-weekly-std          # stable, kebab-case
  revision: 1                        # positive integer; a same-named file is not the same revision
  pipeline: rent                     # sale | rent
  status: active                     # draft | active | paused | expired | revoked
  valid_from: 2026-11-01T00:00:00Z
  valid_to: null                     # explicit open_ended decision, never silent
  price:
    amount_minor: null               # integer minor units, set by the owner
    currency: UZS                    # ISO 4217
    period: week                     # one_time | day | week | month
  terms: {}                          # typed owner-approved business terms (deposit, minimum period, installment, warranty, inclusions)
  claims:                            # exact approved sentences, numbers verbatim
    uz: ["string"]
    ru: ["string"]
  forbidden_claims:                  # the Reviewer rejects these for this offer
    uz: ["string"]
    ru: ["string"]
  restrictions: ["string"]           # eligibility, territory, channel
  capacity_bound: "string | null"    # rent only: band or stock condition under which it may run
  source_approval_ref: "string"      # owner approval evidence
  asset_rights_ref: "string"         # rights evidence for assets shown with the offer
  special_ad_category: unknown       # verified policy choice; unknown blocks activation
facts:
- fact_id: string
  text_uz: "string"
  text_ru: "string | null"
  source_ref: "string"
  valid_to: "UTC timestamp | open_ended"
```

Schema example, not real offer data.

## 3. Proposing a change (`offers.propose_pr`)

The PR body (Uzbek) contains:

- **What changes** — the YAML diff, pipeline and the new revision.
- **Why** — tagged evidence: funnel data (`wh.metrics`), JTBD insight, competitor observation [T], capacity status for rent, sale readiness for sale.
- **Expected effect** — `{metric, direction, range_low, range_high, horizon_days, basis_tag}`; no invented precision.
- **Risks** — margin impact (DAT-03 unit economics), policy (special category), operational capacity.
- **Measurement plan** — equal pre/post windows of at least one full weekly cycle, success criterion and stop rule (DAT-04/DEC-05).
- **Affected artifacts** — live ads, landing variants and pending approvals that reference the old revision, the propagation SLA (`offers.propagation`) and the owner of each.
- **Rollback** — the previous revision stays `paused` for revert; rollback is a new controlled action against the current approved offer and epoch, an old expired offer is never resurrected automatically.

PR creation is not approval or activation.

## 4. Revocation, expiry and propagation

On an approved revision, expiry or revocation: inventory affected artifacts, invalidate stale approval and review bindings, and reconcile the deployed bundle, the landing snapshot and live ads. Live ads are replaced or paused only through owner-approved commands or the owner-approved propagation plan in `offers.propagation`; hiding the offer from future drafts is not enough. The work closes only when propagation evidence covers every affected live artifact or an explicit incident with an owner and deadline remains.

## 5. Reviewer checks against the registry

- Every number and condition maps to an active offer revision (`offer_id@revision`); wording of guarantees and conditions is exact.
- No `forbidden_claims` wording; restrictions honoured; brand facts only from `facts`.
- `special_ad_category` is not `unknown` for installment/credit offers before launch — otherwise `needs_owner`.
- Capacity-bound rent claims match the current band.

Before any handoff, confirm the exact terms, pipeline, publication time, source rights, human owner and unresolved blockers. Output in Uzbek Latin with source refs; English IDs and keys. No invented offer, profitability or live-state claim.

## Tool scope

Machine-checked by the bundle validator (rule D15, F4-AT-17). A role is instructed to call a tool here only where it is listed; every listed role holds the tool in `approval-policy.yaml#agents.<slug>.tools` and loads this skill in its charter. `citation` = the tool appears only as an evidence-source format; `—` = any role may cite a source it received, calling it still needs the tool. The gateway refuses every tool outside the caller's allowlist regardless of this table.

| Tool | Instructed roles | Mention |
|---|---|---|
| `offers.read` | cmo, media-buyer, creative-studio, cro, funnel-analyst, reviewer | call |
| `offers.propose_pr` | cro, cmo | call |
| `wh.metrics` | cro, cmo | citation |
