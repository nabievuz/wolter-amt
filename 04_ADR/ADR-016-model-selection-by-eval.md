# ADR-016 — Model tanlash research va eval asosida; adapter model oilasiga qarab

Holat: Accepted · Qaror egasi: owner (Q42, Q44.2, Q44.3 ✅) + builder ★ (Q44.2★, boshlang‘ich modellar) · Sana: 2026-10-22

## Kontekst

- Owner har agent modelini deep research va agent vazifasi asosida tanlashni so‘ragan; asosiy mezon — tool-use ishonchliligi; arzonroq yoki boshqa model faqat eval’da teng natija bersa olinadi; o‘zbekcha copy uchun F5 da golden copy to‘plamida 2–3 model ko‘r-ko‘rona solishtiriladi (Q44.2). Zaxira (fallback) yo‘l ishlab chiqilmaydi (Q44.3) [D: DECISION_LOG].
- **Q42:** Reviewer’da til tekshiruvi — Sonnet darajasidagi model, policy checklist — arzon model; birinchi 20 kreativni ona tili o‘zbek bo‘lgan odam tekshiradi [D]. Arzon model nozik o‘zbekcha til xatolarini o‘tkazib yuborishi mumkin [X].
- Faktlar (build kuni qayta tekshiriladi, [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md)):
  - Claude Code faqat Claude modellari bilan ishlaydi; gateway model discovery faqat "claude" yoki "anthropic" so‘zli ID’larni qoldiradi; noma’lum ID 400 xatosiga olib kelishi mumkin [D: code.claude.com/docs/en/llm-gateway];
  - `opencode_local` OpenRouter’ni native qo‘llaydi va sarfni metered deb yozadi; u `claude_local` dan yoshroq [D: Paperclip repo];
  - Hermes OpenRouter’ni native qo‘llaydi [D];
  - Claude Code va Hermes har so‘rovga provider siyosati va attributsiyani o‘zi qo‘sha olmaydi [X] — barcha agent trafigi llm-proxy orqali ([ADR-003](ADR-003-openrouter-single-key-watchdog.md));
  - narx (USD / MTok, input/output) [D: platform.claude.com pricing, 2026-10-22 · qayta tekshiriladi]: Opus 5.5 — 4/20; Sonnet 5.5 — 2/10; Haiku 5.5 — 0.10/0.50 (prompt ≤ 100K). OpenRouter inference narxiga ustama qo‘ymaydi [D].
- Model tanlash eval’lari faqat muallif ko‘rmaydigan holdout bilan ishonchli bo‘ladi ([ADR-026](ADR-026-independent-verification-custody.md)) [X].

## Qaror

1. **Model tanlash protokoli** ([EVALS §4](../07_Evals/EVALS.md)): deep research → shortlist (≤ 3) → haqiqiy gateway bilan L0 da tool-use ishonchlilik testi → tegishli K va M eval’lar → har run narxi → og‘irlikli qaror. Model ID’lari build/eval kuni OpenRouter `/models` dan olinadi, kodga yozib qo‘yilmaydi.
2. **Adapter model oilasiga qarab** (hammasi llm-proxy orqali, agentda kalit yo‘q): Claude → `claude_local` (proxy `/anthropic`); Claude bo‘lmagan model → `opencode_local` (proxy `/openai`; custom base URL qo‘llovi F5 da tekshiriladi [?]) yoki Hermes; CMO har doim Hermes ichida ([ADR-004](ADR-004-hermes-cmo-no-openclaw.md)).
3. **Reviewer ikki model slotida (Q42):**
   - `reviewer.language` — Sonnet-sinfi model yoki UZ/RU til holdout’ida teng natija isbotlangan model (Q44.2);
   - `reviewer.policy_checklist` — arzonroq model ruxsat etiladi.
   `models.assignments` ikkala slotni alohida yozadi; [EVALS](../07_Evals/EVALS.md) da seeded xatolar bilan UZ til holdout’i bor; inson til tekshiruvi Reviewer o‘rnini bosmaydi (`approval-policy.yaml#creative_review`).
4. ★ **Boshlang‘ich modellar** (faqat F4 smoke test uchun, yakuniy tanlov emas): CMO, Media Buyer, Creative Studio, CRO, Funnel Analyst — Sonnet-sinfi; C07 va C12 — Opus-sinfi; Reviewer `reviewer.policy_checklist` — Haiku-sinfi, `reviewer.language` — Sonnet-sinfi.
5. O‘zbekcha copy uchun golden copy blind test: 2–3 model oilasi, ≥ 3 baholovchi (EVALS §3, HG-F5-01, HG-F5-03).
6. Media modellari (`/images`, `/videos`) narx va sifat bo‘yicha F5 da tanlanadi; ularni faqat gateway `media.*` tool’lari proxy orqali chaqiradi.
7. **Tayinlovlar ADR’da emas**, `models.assignments` readiness yozuvida (F5_GO): rol yoki slot × model ID × adapter × prompt/tool/skill revision × eval ballari × haqiqiy narx. Keyingi o‘zgarish WF-E03 orqali: manifest’ga bog‘langan mustaqil verification (holdout) va owner release (I19, [ADR-027](ADR-027-release-controller-and-harness-handover.md)).
8. Fallback o‘chiq; noma’lum yoki yetishmagan konfiguratsiya boshqa provayder yoki modelni jim tanlamaydi — fail-closed.
9. **Jev pre-screen** (Q61, [ADR-034](ADR-034-jev-review-pre-screen.md)) Reviewer model sloti emas: gateway uni Reviewer’dan oldin llm-proxy orqali `typesafe/jev-1.14` bilan chaqiradi; chegara, scope va snapshot `models.pre_screen` da (F5-AT-14), `models.assignments` da emas.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Barcha rollar uchun bitta eng arzon model | tool-use va til sifati tekshirilmaydi (Q44.2) |
| Reviewer uchun bitta umumiy (arzon) model | Q42 ga zid; nozik til xatolari o‘tib ketadi |
| Statik benchmark bo‘yicha tanlash | runtime tool-use muvaffaqiyati alohida o‘lchanishi kerak |
| Zaxira provayder yoki model | Q44.3 |
| Tayinlovlarni ADR jadvalida yuritish | runtime revision, dalil va narx readiness yozuvida va manifest’da; ADR faqat qaror mezoni |

## Oqibatlar

- **+** Model tanlash dalilga asoslanadi; o‘zbekcha copy sifati alohida o‘lchanadi; Reviewer til sifati Q42 bo‘yicha himoyalangan.
- **−** Claude bo‘lmagan model tanlansa ikkinchi adapter yo‘li paydo bo‘ladi (texnik xizmat).
- **−** Fallback yo‘q: provayder ishlamasa agent kutadi.
- **−** Ikki Reviewer slotini baholash qo‘shimcha eval xarajati (build eval ★ ≤ 40% chegarasi ichida, ADR-003).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Muntazam ko‘rib chiqish | har chorakda bir marta | `retro_c12` | WF-E03 bo‘yicha qayta baholash |
| Yangi model oilasi | vendor e’loni | `vendor_advisory` (WF-E03) | shortlist va eval |
| Eval natijasi tushishi | K/M eval yoki UZ holdout ★ chegaradan pastga | `eval_drift` | model yoki prompt qayta tanlovi |
| Agent sarfi ulushidan oshishi | 2 oy ketma-ket | Langfuse (`cost_drift`) | teng natijali arzonroq model eval’i |
| Reviewer til xatosini o‘tkazib yuborishi | inson til tekshiruvi Reviewer `pass` bergan copy’da xato topsa | `human_checks` | `reviewer.language` sloti qayta baholanadi |

## Kanonik implementatsiya

- [EVALS §3–§4](../07_Evals/EVALS.md), [REVIEWER](../02_Team_Charter/agents/REVIEWER.md).
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `creative_review.model_slots`, `human_language_check`.
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `models.assignments`.
- [WF-E03](../09_Config_Templates/workflows/WF-E03.yaml); [F5_Eval_Shadow](../05_Build_Phases/F5_Eval_Shadow.md) — F5-AT-04.
