# ADR-011 — Analitika: Meta Pixel + CAPI + Umami + Microsoft Clarity (GA4 yo‘q)

Holat: Accepted · Qaror egasi: owner (Q14, Q17, Q29.1, Q30/Q45 ✅) + builder ◇ P-19 (qualified fakt qoidasi) · Sana: 2026-10-22

## Kontekst

- Funnel & Tracking Analyst landing Pixel’ini va kiruvchi trafikni tahlil qiladi va boshqaradi (Q14); CAPI qualified signal Meta’ga qaytariladi — P0 (Q17); analitika Pixel + CAPI + Umami + Clarity, GA4 yo‘q (Q30/Q45); Pixel event’lari va landing kodi faqat PR orqali, Events Manager sozlamalari — taklif va owner ✅ (Q30) [D: DECISION_LOG].
- Owner GA4 ni ko‘rib chiqib, Q30 to‘plamida qolishni tanlagan (Q45).
- Pixel’ning o‘zi foydalanuvchi xulqini ko‘rsatmaydi; CRO uchun heatmap kerak [X].
- CAPI faktlari [D: Meta CAPI docs · qayta tekshiriladi]: website lead’larida `lead_id` yo‘q; `fbc`, `fbp`, IP va UA hash’siz, telefon SHA-256 bilan yuboriladi; Pixel va server bir xil `event_id` bilan yuborsa dedup bo‘ladi; CRM stage event’lari `action_source: system_generated`.
- Qualified-lead optimizatsiyasi uchun vendor hajm va eligibility talablari o‘zgarib turadi [D2: 2026 ikkilamchi manbalar · qayta tekshiriladi] — Q29.1 bo‘yicha F2 da o‘lchanadi.
- Faqat Pixel muvaffaqiyatlariga tayangan nisbat yo‘qolgan submission’larni aniqlay olmaydi [X].

## Qaror

| Vosita | Joyi | Vazifasi | AMT kirishi |
|---|---|---|---|
| Meta Pixel | landing (client) | `Lead` va boshqa event’lar, `event_id` bilan dedup | Meta API orqali o‘qish (Events Manager diagnostikasi) |
| Meta CAPI | `capi-bridge` (server) | server `Lead` va CRM stage event’lari (`QualifiedLead`) | audit va EMQ |
| Umami | ★ production Dokploy, `stats.wolter.uz` (HG-F2-11) | trafik manbalari, sahifalar, konversiya yo‘li | `analytics.umami_query` (read-only) |
| Microsoft Clarity | landing (client) | heatmap va sessiya yozuvlari; kiritish maydonlari maskalangan | `analytics.clarity_export` [?: eksport limitlari tekshiriladi] |

- **GA4 ishlatilmaydi.**
- Landing’da rozilik banneri; Pixel va Clarity faqat rozilikdan keyin yuklanadi ★.
- Pixel event’lari va landing kodidagi o‘zgarishlar faqat PR orqali ([ADR-012](ADR-012-landing-separate-repo-pr-only.md)).
- Events Manager sozlamalari (`events_manager_change`, NEVER_AUTO): agent change set orqali tavsif sifatida taklif qiladi, owner ✅ dan keyin o‘zi qo‘lda bajaradi; API orqali bajarish yo‘q.
- Server `Lead` CAPI event’i landing submission `crm_confirmed` bo‘lganda yuboriladi; amoCRM `add_lead` webhook’i faqat reconciliation uchun. Qualified fakt qoidasi — status, ruxsatli aktyor, dalil maydoni va hodisa vaqti — `pipelines.yaml#qualified_fact_rule` da (◇ P-19).
- Optimizatsiya maqsadi (Q29.1): `QualifiedLead` optimizatsiyasi faqat (a) akkaunt eligibility dalili va (b) F2 da Analyst o‘lchagan oylik hajm owner mo‘ljali (~200 lead/oy) va Meta’ning amaldagi rasmiy talabidan (sanasi bilan [D] manba) kattasiga yetsa; aks holda `Lead` bo‘yicha optimizatsiya, qualified — guardrail (`vendor.qualified_optimization`).
- Delivery health accepted submission’lar va CRM ledger’i farqiga tayanadi va Pixel–CRM tekshiruvidan mustaqil (I08); consent qamrovi va noma’lum attributsiya alohida ko‘rsatiladi.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| GA4 | owner Q45 |
| Faqat Pixel | CRO’ga xulq ma’lumoti kerak; yo‘qolgan submission’lar ko‘rinmaydi |
| amoCRM `add_lead` webhook’ini server `Lead` manbai qilish | landing submission bilan bog‘lanish va dedup noaniq; CRM’ga yetkazilganini tasdiqlamaydi |
| Hajmdan qat’i nazar `QualifiedLead` optimizatsiyasi | Q29.1: hajm yetmasa optimizatsiya ishonchli emas |

## Oqibatlar

- **+** Uchta tracker o‘rniga ikkita yengil qo‘shimcha vosita: sahifa tezroq yuklanadi; Umami self-hosted.
- **−** Clarity tashqi servis: maskalash majburiy, PII tushmasligi testlanadi.
- **−** Umami production serverda turadi; deploy owner HUMAN_GATE’i (HG-F2-02).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Clarity eksporti yetarli emas | CRO tahlili uchun kerakli maydonlar eksportda yo‘q | `agent_signal` | muqobil eksport yoki qamrov taklifi |
| Qualified optimizatsiya | `vendor.qualified_optimization` `supported: false` qolsa va qo‘shimcha signal kerak bo‘lsa | Analyst F2/F5 o‘lchovi | owner qarori |
| Vendor talablari | Meta rasmiy hujjatida hajm yoki eligibility talabi o‘zgarsa | `vendor_advisory` | `vendor.qualified_optimization` va `vendor.meta_capi` qayta dalillanadi |

## Kanonik implementatsiya

- [TRACKING_CAPI](../03_Architecture/TRACKING_CAPI.md) — durable receipt, CAPI outbox, tracking health, Umami/Clarity.
- [pipelines.yaml](../09_Config_Templates/pipelines.yaml) — `qualified_fact_rule`, `capi_event_map`; [business-policy.yaml](../09_Config_Templates/business-policy.yaml) — `qualified_optimization_rule`.
- [tracking-health.yaml](../09_Config_Templates/tracking-health.yaml); [readiness.yaml](../09_Config_Templates/readiness.yaml) — `vendor.meta_capi`, `vendor.qualified_optimization`, `tracking.thresholds`.
- [F2_Landing_Tracking](../05_Build_Phases/F2_Landing_Tracking.md); [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I08.
