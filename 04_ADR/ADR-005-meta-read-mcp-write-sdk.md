# ADR-005 — Meta: o‘qish byadsco MCP orqali, yozish tor SDK operatsiyalari orqali

Holat: Accepted · Qaror egasi: owner (Q07, Q25, Q30, Q32, Q40 ✅) · Sana: 2026-10-22

## Kontekst

- Owner Ads Manager uchun `byadsco/meta-ads-mcp` ni tanlagan (Q07). Q40: o‘qish — byadsco MCP (≥ v4.0.0, pinned); yozish — gateway ichida rasmiy Business SDK ustidagi ~6 tor operatsiya; Analyst va Reviewer — `ads_read` system user [D: DECISION_LOG].
- byadsco faktlari (2026-10-22, [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) da claim; build kuni qayta tekshiriladi):
  - MIT, TypeScript, Marketing API v26.0; 142 tool — 79 o‘qish, 63 o‘zgartirish [D: manba kodi];
  - global read-only rejim, write allowlist va byudjet chegarasi yo‘q [D];
  - budget va spend cap’dagi sent/dollar aralashish xatosi faqat 2026-10-11 da tuzatilgan (#171), v4.0.0 esa 2026-09-18 da chiqqan — demak "≥ v4.0.0" shartining o‘zi tuzatishni kafolatlamaydi [D: repo · qayta tekshiriladi];
  - paket faqat GitHub Packages yoki GHCR’da [D]; bitta asosiy maintainer [D];
  - yangi kampaniya va ad set standart holatda PAUSED yaratiladi; CAPI tool’i yo‘q [D].
- Marketing API: soatlik limit 300 + 40 × faol ad (Standard); server avtomatlashtirish uchun system user soni Limited tier’da 1, Full tier’da 10 [D: developers.facebook.com · qayta tekshiriladi]. AMT kamida ikki system user (`amt-read`, `amt-write`) talab qiladi — haqiqiy tier `vendor.meta_access_tier` da dalillanadi [?].
- Muqobillar: pipeboard (BUSL-1.1, lokal rejimda standart holatda o‘zining Meta app ID’si) [D]; Meta’ning rasmiy hosted Ads MCP’si (open beta, akkaunt bo‘yicha yoqiladi, draft’lar Ads Manager’da tasdiqlanadi) [D2].

## Qaror

**O‘qish**

1. `meta-ads-mcp` alohida `amt-meta-read` UID’da, faqat `ads_read` huquqli system user tokeni bilan ishlaydi. **Pin floor — byadsco #171 unit tuzatishini o‘z ichiga olgan commit** [?: aniq commit SHA build kuni repo tarixidan aniqlanadi va `VERSIONS.lock.md` ga manba URL bilan yoziladi]; Q40 dagi "≥ v4.0.0" sharti shu floor bilan birga qo‘llanadi.
2. Gateway agentlarga faqat dalillangan read allowlist’ni `meta_read.<tool>` nomi bilan ko‘rsatadi (`vendor.meta_read_tools`, F3_CONTROLLED_TEST). MCP tool soni yoki write flag’i ruxsat dalili emas. MCP orqali o‘qilgan budget/spend qiymatlari birlik testidan (sent va dollar fixture’lari) o‘tmaguncha guard’da ishlatilmaydi.

**Yozish**

3. `amt-executor` (alohida UID; `ads_management` system user tokeni faqat shu yerda) rasmiy SDK ustida tor operatsiyalarni bajaradi: `pause_entity`, `activate_entity`, `update_budget`, `create_campaign_paused`, `create_ad_from_creative`, `duplicate_adset`, `upload_creative_asset`. Gateway’da Meta write kaliti yo‘q ([ADR-006](ADR-006-guardrail-gateway.md)).
4. Har operatsiya change set → approval → executor orqali o‘tadi ([ADR-021](ADR-021-durable-execution-custody.md)); barcha yangi obyektlar PAUSED yaratiladi.
5. Action turini gateway aniqlaydi: `campaign_create`/`adset_duplicate` orqali yaratilgan, hech qachon faol bo‘lmagan obyektning birinchi faollashtirilishi — `campaign_activate` (faqat owner, NEVER_AUTO, Q32); avval faol bo‘lgan kampaniya yoki ad set’ni qayta yoqish — `entity_activate`; mavjud faol ad set ichida ad’ni yoqish (yangi ad, kreativ almashtirish yoki oldin faol bo‘lgan ad’ni qayta yoqish) — `creative_activate`.
6. `upload_creative_asset` — media-buyer’da; Creative Studio’da hech qanday `meta_write` yo‘q.
7. Events Manager (`events_manager_change`, Q30) API orqali bajarilmaydi: o‘zgarish change set’da tavsif sifatida taklif qilinadi, owner ✅ dan keyin owner o‘zi qo‘lda bajaradi.
8. Account spending limit’ni o‘zgartiruvchi tool yo‘q; limitni owner qo‘yadi va har oy yangilaydi (HG-F3-02, HG-OPS-01, [ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)).
9. `protective_pause` va kill B pauzalari ham faqat `pause_entity` dan foydalanadi — yangi Meta write turi qo‘shilmaydi ([ADR-030](ADR-030-kill-modes-and-protective-controls.md)).
10. Pul faqat integer minor birlikda; har konvertatsiya unit-test bilan qoplanadi (ADR-029).
11. Yangi write operatsiyasi faqat PR, adversarial test, mustaqil verification va owner release bilan qo‘shiladi.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| byadsco orqali to‘g‘ridan-to‘g‘ri yozish | 63 ta write tool, read-only rejim va byudjet chegarasi yo‘q, bitta maintainer |
| pipeboard | BUSL-1.1 litsenziyasi; standart holatda begona Meta app ID |
| Meta’ning rasmiy hosted Ads MCP’si | open beta va hosted; zaxira reference sifatida kuzatiladi |
| Brauzer orqali Ads Manager | Meta ToU avtomatlashtirilgan kirishni taqiqlaydi; akkaunt bloklanish xavfi (Q07) |
| byadsco’ni faqat "≥ v4.0.0" bilan pin qilish | v4.0.0 #171 unit tuzatishidan oldin chiqqan |

## Oqibatlar

- **+** Tahlil uchun boy o‘qish imkoniyati; yozish yuzasi tor, sinalgan va yagona kontraktda (pul, approval, attempt auditi, yaratilgan obyekt egaligi).
- **−** Ikkita Meta klienti yuritiladi; SDK write yo‘li qo‘shimcha kod talab qiladi.
- **−** byadsco yangilanishlari va unit xulqi har upgrade’da qayta tekshiriladi (WF-E03).
- **−** Access tier cheklovlari (system user soni, rate limit) F3 da dalillanmaguncha gate o‘tmaydi (PASS bo‘lmaydi).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| byadsco yangilanmasligi yoki xavfsizlik muammosi | 3 oy commit yo‘q yoki advisory | `vendor_advisory` (WF-E03) | fork/pin yoki muqobil read yo‘li ADR’i |
| Meta rasmiy MCP GA bo‘lishi | GA va Wolter akkauntida yoqilishi | `vendor_advisory` | read yo‘li qayta baholanadi |
| Marketing API breaking change | yangi API versiyasining deprecation sanasi e’lon qilinsa | `vendor_advisory` (WF-E03) | SDK va MCP upgrade |
| Birlik xatosi | budget/spend birlik testi fail yoki provider read-back nomuvofiq | `regression` | risk oshiruvchi write bloklanadi; reconcile; INCIDENTS |
| Access tier yetmasligi | `vendor.meta_access_tier` limiti rate limit xatolariga olib kelsa | `incident_aar` | tier oshirish (owner) yoki sync kadensini qayta sozlash |

## Kanonik implementatsiya

- [GUARDRAIL_GATEWAY §8–§9](../03_Architecture/GUARDRAIL_GATEWAY.md) — tashqi Meta tool kontraktlari.
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `agents.media-buyer`, `campaign_activate`, `entity_activate`, `creative_activate`, `events_manager_change`, `meta_read_allowlist`.
- [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) — `executor`, `meta-ads-mcp`.
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `vendor.meta_read_tools`, `vendor.meta_access_tier`, `vendor.component_locks`, `vendor.meta_cap`.
- [F3_Integrations](../05_Build_Phases/F3_Integrations.md); [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) — vendor risk claim’lari.
