---
name: wolter-brand-voice
description: Wolter's "Dadil do‘st" brand voice for paid Meta ad copy for delivery couriers — Uzbek Latin primary, adapted Russian variant; tone rules, banned words, ad structure, calibration examples, pipeline nuances and a self-check, while preserving approved commercial terms and current availability.
---

# Wolter brand voice — “Dadil do‘st”

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

“Dadil do‘st” = **Samimiy** (sincere) + **Dadil** (bold); theme **“Yo‘lda to‘xtamang”** — the courier’s working day should not stop (Q21 ✅). Origin: the Wolter app’s owner-approved voice, adapted here to paid ad copy. The brand kit (logo, colours, fonts, approved photos) and the golden-copy library are read-only knowledge in the active release; templates live in `knowledge/templates/`. This skill never confirms a new commercial fact: prices and terms come only through [offer-registry](../offer-registry/SKILL.md). Users: creative-studio (writing), cro (landing copy), reviewer and cmo (review and tone with the owner).

## 1. Voice in one line

| Use bold (Dadil) for | Use sincere (Samimiy) for |
|---|---|
| hooks, headlines, CTA, momentum (“Davom eting”) | price, installment and rental terms, deposits, documents, guarantees |
| speed of swapping, uninterrupted work | anything that sounds like a risk, an error or an obligation |

Never bold or pushy about money, debt, identity documents or errors.

## 2. Writing workflow

1. Identify the courier benefit, the exact active offer revision, the pipeline and real availability. Complete when the copy has one truthful promise the business can fulfil.
2. Lead with the benefit, then proof, then the user-perspective action. Headline up to 4–5 words, one idea per ad, short sentences. Complete when the reader understands what to do without a company-centred introduction.
3. Use “siz” in all body copy; “sen” appears only in the owner-approved slogan **“Olib ket. Almashtir. Davom et.”** Prefer familiar loanwords couriers use (kuryer, aksiya, zaryad, referal). Complete when the wording sounds natural and uses one Uzbek Latin apostrophe convention from the brand kit (o‘, g‘, sh, ch, ʼ).
4. Keep every price, installment, deposit, warranty and restriction exactly as approved; explain obligations calmly. Complete when hook adaptation has not changed the commercial meaning and no `forbidden_claims` wording appears.
5. Write a Russian variant only when the plan requests it (§5). Complete when both variants carry the same claim and each reads naturally on its own.
6. Read against current capacity/readiness and the Reviewer checklist, then hand over the exact revision for review. Complete when urgency, ownership/financing language and proof are supported.

## 3. Rules and structure

- **Banned words and phrasing:** “iltimos”, “muvaffaqiyatli”; bureaucratic forms such as “amalga oshirish”, “taqdim etiladi”, “biz taqdim etamiz”.
- **Verbs from the user’s perspective:** “Ijaraga olish”, “Batareyani almashtirish”, “Narxni bilish” — not the company’s.
- **Problems always come with a way forward** (low battery → nearest station), never a dead end.
- **No superlatives or scarcity without proof:** “eng arzon”, “eng yaxshi”, “№1”, guaranteed income or fake urgency only if the registry and policy explicitly allow it; never by default.

| Part | Guideline |
|---|---|
| Hook (first line / first 1–2 s of video) | the courier’s concrete pain or desire: waiting for a charge, lost orders, high upfront cost; no unproven income promise |
| Proof | real footage, a concrete registry term, or a registry fact (`fact_id`) such as the station network |
| Offer | exact registry wording + offer revision in the manifest |
| CTA | user-perspective action: “Ijara shartlarini ko‘rish”, “Narxni bilish”, “Ariza qoldirish” |

## 4. Calibration references

Approved tone references from the app — for calibration, not for direct reuse in ads:

- “Zaryad tugadimi? Almashtiring” — a simple question + action, light emotion (the owner liked this pattern).
- “Batareyani stansiyada almashtiring va yo‘lda davom eting!”
- Success: “Davom eting!”; low battery: “To‘xtab qolmang: eng yaqin stansiya — <masofa>” (pattern: problem + way forward).

Native-speaker-checked golden copy (first 20 live-eligible copies, Q42 ✅) becomes a calibration reference only after it is released into the library through WF-E04; it is never evidence for a new offer.

## 5. Russian variant

- **Adapt, don’t translate:** the same benefit and offer in the natural Russian couriers use; no calques from Uzbek.
- Address with “вы” (lowercase) in body copy. The slogan stays in Uzbek unless an owner-approved Russian equivalent exists ★ — never invent one.
- No bureaucratic Russian (“осуществить”, “предоставляется”).
- Russian variants run as a separate A/B cell only when the plan includes it (one experiment per pipeline, Q41 ✅). The human check rule for Russian copy is ⧗ OD-08.

## 6. Pipeline nuances

| Pipeline | Emphasis | Caution |
|---|---|---|
| `sale` | ownership, long-term earnings, exact financing terms | installment/credit wording may trigger a Meta special ad category — the Reviewer and the owner decide |
| `rent` | start working fast, no big upfront cost, swap network | if the eligible waitlist is long or no bike is available, do not push urgency (“hoziroq oling”); use capacity-aware messaging (“navbatga yoziling”) ★ |

## 7. Self-check before review

- [ ] Headline up to 4–5 words; one idea.
- [ ] Benefit before action; CTA from the user’s perspective.
- [ ] “siz” in body copy; “sen” only in the slogan.
- [ ] No “iltimos”, no “muvaffaqiyatli”, no bureaucratic phrasing, no unsupported superlatives or scarcity.
- [ ] Every term or number maps to an offer revision or registry fact; no `forbidden_claims` wording.
- [ ] One orthography convention; Russian adapted, not translated.
- [ ] Availability and urgency match today’s capacity or sale readiness.
- [ ] No personal data, other brands or famous people.

A tone pass is not a Meta policy pass or a business-availability pass; the Reviewer and, for the first 20 live-eligible copies, the human language check stay separate.
