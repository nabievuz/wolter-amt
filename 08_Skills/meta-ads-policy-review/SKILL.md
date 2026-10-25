---
name: meta-ads-policy-review
description: Checklist framework for reviewing Wolter ads, landing pages and targeting against verified official Meta policy sources, active offer terms and asset permissions; maps each row to the Reviewer verdict checks, holds unresolved special-category or source questions for the owner, and learns from a reviewed enforcement log.
---

# Meta ads policy review

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

**Status of this checklist:** framework. It does not replace current Meta policy facts. In **F4** every row gets its verified official source (Advertising Standards, special ad categories and targeting rules, Business Tools terms), the check date, applicability to Wolter and the policy revision; rows that do not match are adjusted. Until verified, a row is guidance only and an uncertain case returns `needs_owner`, never a confident pass or fail from memory. Later reviews check the effect of policy changes.

Verification record (filled in F4 and on every policy revision): `verified_by · date · sources[] · policy_revision`.

Users: reviewer (verdicts), creative-studio and cro (self-check before review). Offer and rights semantics: [BUSINESS_CONTRACT §9](../../11_Production_Contracts/BUSINESS_CONTRACT.md). Verdict schema and aggregation: [REVIEWER](../../02_Team_Charter/agents/REVIEWER.md). The Reviewer works only with its allowlisted tools; official policy material reaches it only as the release file set `knowledge/meta-policy/` (verified sources with their verification records, added by a reviewed PR of the technical operator or owner) and is opened on demand within the prompt-manifest cap (`prompt-manifest.yaml`, at most 8 000 estimated tokens).

## 1. How to use

1. Identify the exact subject — ad copy and media hash, landing/offer revision, pipeline, destination and targeting summary (the Reviewer reads it with `review.get_subject`). Complete when the reviewed artifact is immutable and its intended use is clear.
2. Decide the **S rows first** (special categories): financing/installment or job-like wording can change category and targeting obligations in this jurisdiction. Use the verified source and date. Complete when applicability is resolved or held for the owner; the owner’s decision must still comply with the rules.
3. Evaluate every applicable row with `pass | fail | needs_owner | n_a`, a one-line Uzbek reason and the policy link. Any `fail` → the subject fails. Any `needs_owner` on S rows → the item is held for the owner. If `review.get_subject` returns a pre-screen flag for `meta_policy`, `special_ad_category` or `pii_leakage`, that check can be `pass` only with `pre_screen_response_uz` ([REVIEWER](../../02_Team_Charter/agents/REVIEWER.md)); a flag never relaxes a row.
4. Record the verdict with `review.submit_verdict`, tied to the subject hash and the offer, policy and verdict revisions. Complete when the writer has actionable repairs, not a vague rejection.
5. Re-review on changed content, policy, offer or rights revision; a stale pass never authorises changed bytes or terms.
6. Never “fix” a policy doubt by weakening the offer text arbitrarily — propose a compliant alternative that cites the registry.

## 2. Checklist

Each row maps to a Reviewer `check`.

### S — Special ad categories (decide before anything else) → `special_ad_category`

| # | Check | Why it matters for Wolter | Verified rule / link |
|---|---|---|---|
| S1 | Does the ad promote credit, installment or financing terms (bo‘lib to‘lash, deferred payment, deposit financing)? If yes, is a special ad category declaration required in this market? | `sale` offers may include installments (Q42 ✅; OI-04) [?] | [? verify in F4] |
| S2 | Could the ad read as an employment opportunity (“kuryer bo‘lib ishlang”, income promises)? | Wolter sells and rents bikes, not jobs; wording must not look like a job ad [?] | [? verify in F4] |
| S3 | If a category applies: are targeting restrictions respected (age, gender, location granularity) and is the category declared at campaign level? | category ads have restricted targeting [?] | [? verify in F4] |

### C — Content → `meta_policy`, `offer_registry`, `rights_consent`, `language_quality_uz/ru`

| # | Check | Verified rule / link |
|---|---|---|
| C1 | Personal attributes: copy does not assert or imply the viewer’s personal situation (debt, hardship, health, religion, ethnicity); “Qarzingiz bormi?” style hooks are not allowed [?] | [? verify] |
| C2 | Misleading or unrealistic claims: no income guarantees, no unrealistic earnings, no fake urgency or scarcity | [? verify] |
| C3 | Prices and terms match the active offer revision and the landing page exactly; no `forbidden_claims` wording | active offer revision |
| C4 | No before/after, shocking or sensational imagery | [? verify] |
| C5 | Third-party IP: no other brands’ logos, characters or unlicensed music; no misuse of Meta brand assets | rights reference |
| C6 | Testimonials and endorsements: only real, consented ones; no fabricated reviews or invented people | rights/consent reference |
| C7 | Language quality: natural Uzbek/Russian, no excessive caps or profanity | brand voice + exact artifact |
| C8 | Safety depiction: no dangerous riding or phone use while riding ★ | [? verify] |

### D — Destination and tracking → `meta_policy`, `tracking_impact`

| # | Check | Verified rule / link |
|---|---|---|
| D1 | Landing works on mobile, matches the ad’s promise; no bait-and-switch | release/offer revision |
| D2 | Consent text present for data collection and a privacy link available | `privacy.purposes` |
| D3 | Pixel/CAPI use follows Business Tools terms; no sensitive custom data; hashed identifiers are not anonymity or consent | [? verify] |

### T — Targeting (media-buyer proposals) → `meta_policy`, `special_ad_category`

| # | Check | Verified rule / link |
|---|---|---|
| T1 | If S1–S3 apply, targeting follows category restrictions | [? verify] |
| T2 | No exclusion or targeting that could be discriminatory | [? verify] |
| T3 | Custom audiences only from lawfully collected, consented data | privacy source review |

Hash presence is not anonymity or tracking permission. A policy verdict does not replace human approval, cap/readiness guards or a legal determination. The Reviewer never publishes; a repair returns to the writer as a new revision.

## 3. Known operational signals

- Ad rejections and account-quality notices are detected by the deterministic sync job; each one raises an urgent alert (ALERT_META_REJECTED / ALERT_ACCOUNT_RESTRICTED) and a Reviewer issue, and new `ad_create` proposals pause until the Reviewer re-checks.
- The verbatim rejection reason is stored durably. After owner review it enters the enforcement log below only through WF-E04 (a versioned skill change with independent verification and an owner release); agents never edit this file at runtime.

## Appendix — enforcement log (filled during operation through WF-E04)

| Date | creative_id / revision | Meta reason (verbatim) | Rule row | Change made |
|---|---|---|---|---|
| | | | | |

## Tool scope

Machine-checked by the bundle validator (rule D15, F4-AT-17). A role is instructed to call a tool here only where it is listed; every listed role holds the tool in `approval-policy.yaml#agents.<slug>.tools` and loads this skill in its charter. `citation` = the tool appears only as an evidence-source format; `—` = any role may cite a source it received, calling it still needs the tool. The gateway refuses every tool outside the caller's allowlist regardless of this table.

| Tool | Instructed roles | Mention |
|---|---|---|
| `review.get_subject` | reviewer | call |
| `review.submit_verdict` | reviewer | call |
