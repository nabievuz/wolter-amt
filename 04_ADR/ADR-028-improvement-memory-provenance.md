# ADR-028 — Yaxshilanish xotirasi va provenance

Holat: Proposed · Qaror egasi: owner instruction 2026-10-23 (Q50 ✅ scope) + builder ◇ details · Sana: 2026-10-23

- Asos: EVO-R13, EVO-R04; owner qarorlari Q13, Q28; invariantlar I09, I24
- Bog‘liq: [ADR-015](ADR-015-thinking-library-kernel.md), [ADR-026](ADR-026-independent-verification-custody.md)

## Kontekst

Har upgrade’dan saboq olinishi kerak, lekin agent xotirasi tekshirilmagan gap, xom log yoki muvaffaqiyatsiz taklifni “qoida”ga aylantirib yuborsa xato o‘zini o‘zi kuchaytiradi. Hermes memory va skill yozish allaqachon owner review talab qiladi [D: CMO charter].

## Qaror

1. `improvement_memory` jadvali: har yopilgan upgrade uchun source, revision, sana, muammo, oldingi holat, gipoteza, diff, test dalili, haqiqiy xarajat, rollout, kuzatilgan natija, verdict va qaror egasi ([sxema](../09_Config_Templates/schemas/improvement-memory-record.schema.json)).
2. Agent ko‘rsatmasiga faqat `accepted` va `guidance_eligible: true` yozuv, faqat WF-E04 (mustaqil holdout + owner release) orqali `knowledge/lessons/` ga chiqadi.
3. Rejected va inconclusive yozuvlar saqlanadi, lekin guidance emas. Supersede/revoke/expire va `review_by` eskirish qoidasi bor.
4. PII va secret saqlanmaydi; yozishdan oldin sanitizer va `pii_secret_checked`.
5. Agent runner’ining sessiyasi, workspace’i va Claude Code memory fayllari xotira emas (◇ P-88): har step yangi sessiya, workspace step bilan o‘chiriladi, home read-only, `claude_code_memory: disabled` (`runtime-isolation.yaml#runner_contract`, F4-AT-30). Doimiy ko‘rsatmaning yagona yo‘li — shu qarordagi release qilingan saboq.
6. Saboq va golden copy prompt byudjeti ichida (◇ P-91): `guidance_eligible: true` yozuv `accepted`, `lesson` (≤ 600 belgi), `scope` va `review_by` bilan (sxema); har chaqiruvga rol yoki uning pipeline’iga mos aktiv saboqlardan eng yangisi birinchi, ko‘pi bilan 15 ta va ≤ 2 000 token kiradi (`prompt-manifest.yaml` `common_eager`, `max_fixed_tokens` ichida hisoblanadi), qolganlari ID bilan on demand; golden copy few-shot pipeline × format bo‘yicha ko‘pi bilan 6 ta (≤ 1 500 token, creative-studio va reviewer); FE-AT-16.

## Ko‘rib chiqilgan variantlar

| Variant | Holat va sabab |
|---|---|
| Agentning erkin long-term memory’si | Tanlanmadi: provenance va revoke yo‘q |
| Faqat inson retro hujjatlari | Yetarli emas: mashina o‘qiy oladigan bog‘lanish va dedup yo‘q; retro manba sifatida qoladi |

## Oqibatlar

- Ijobiy: saboq manbali, qaytarib olinadigan va tekshirilgan.
- Salbiy: saboqni ko‘rsatmaga aylantirish sekinroq.
- Risk: eskirgan saboq — `review_by` va revoke.

## Tekshiruv

EVO-AT14 (memory yozuvi), WF-TEST-E04-E2E, WF-TEST-E04-MISSING, WF-TEST-E04-UNCERTAIN, WF-TEST-E04-CANCEL.
