# ADR-012 — Landing alohida repo’da, production Dokploy’da; AMT faqat PR ochadi

Holat: Accepted · Qaror egasi: owner (Q11, Q19, Q41, Q46.4 ✅) · Sana: 2026-10-22

## Kontekst

- Owner qarorlari: AMT avval PR ochadi (variantlar JSON config’da), owner merge qiladi; avto-deploy (feature flag + rollback) — keyinroq, Trust Ramp va trafik hajmiga bog‘liq (Q19); landing avto-deploy trafik yetarliligi isbotlanguncha yo‘q (Q41); landing `go.wolter.uz` production Dokploy’da, alohida GitHub repo, deploy merge’dan keyin Dokploy orqali, AMT serverida production deploy huquqi yo‘q (Q46.4); ishga tushgandan keyin o‘zgarish faqat PR + owner tasdig‘i (Q11) [D: DECISION_LOG].
- Hozirgi oqim Tilda → Google Sheet → amoCRM; bu oqim `fbclid` ni yo‘qotishi mumkin [T].
- AMT hostida agentlar ishonchsiz kod ijrochisi sifatida ishlaydi; landing esa production’ga tegishli.
- Release controller ([ADR-027](ADR-027-release-controller-and-harness-handover.md)) "candidate’ni chiqaradi" degan qoida so‘zma-so‘z o‘qilsa, AMT hostiga Dokploy yoki landing deploy credential’i berilishi mumkin [X] — release doirasi aniq chegaralanishi kerak.

## Qaror

1. Repo `wolter-landing` (private), Next.js; production Dokploy’da `go.wolter.uz`; `main` ga merge bo‘lganda Dokploy deploy qiladi.
2. Landing F2 da quriladi: variant config (JSON/YAML, sxema bilan); tracking yig‘ish (`fbclid → fbc`, `fbp`, `event_id`, UTM, IP, UA); rozilik matni; lead’ni amoCRM’ga Google Sheet’siz, durable submission custody orqali yetkazish ([ADR-021](ADR-021-durable-execution-custody.md)); Pixel (`event_id` bilan), Umami, Clarity.
3. AMT huquqi — faqat `landing.open_pr`: CRO → `content/**` (`content/offers.snapshot.json` dan tashqari), funnel-analyst → `tracking/**`. GitHub fine-grained tokeni faqat shu repo uchun, contents + pull request; admin yoki Dokploy huquqi yo‘q.
4. Branch himoyasi (HG-F0-05): `main` ruleset — PR va owner review majburiy, bypass yo‘q, force-push va o‘chirish taqiqlangan; `contents:write` token bilan ham `main` ga to‘g‘ridan-to‘g‘ri push rad etiladi (acceptance test).
5. `content/offers.snapshot.json` ni CI `offers.yaml` dan generatsiya qiladi; agentlar uni tahrirlamaydi (Q35).
6. Merge va deploy faqat owner (`landing_pr_merge`, NEVER_AUTO); oqim — WF-B04.
7. **`amt-release` doirasi faqat AMT host.** Landing va Umami o‘zgarishida AMT PR ochadi, owner Dokploy’da merge va deploy qiladi, AMT e’lon qilingan snapshot’ni read-only tekshiradi. `amt-release` va boshqa AMT servislarida Dokploy yoki landing deploy credential’i yo‘q (salbiy test) — `release-policy.yaml#out_of_scope`.
8. Landing real trafik olishidan oldin intake durability, recovery, consent va monitoring dalili kerak (F2_LIVE_INTAKE, HG-F2-14); production Dokploy’dagi landing/Umami backup va owner bajargan restore dalili (HG-F2-18); boshlang‘ich offer va asset rights (HG-F2-15). AMT host ishlamasa ham qabul qilingan murojaat jim yo‘qolmaydi (I08).
9. Jonli Meta trafigi HG-F2-09 da yangi landingga o‘tkaziladi; Tilda ★ F6 tugaguncha zaxira.
10. Q19 dagi kelajakdagi avto-deploy yo‘li shartli ravishda ochiq: trafik yetarliligi isbotlansa (Q41), CRO uchun Trust Ramp bajarilsa va Q46.4/Q11 bilan munosabatni hal qiluvchi yangi owner qarori hamda alohida ADR bo‘lsa (auto-release ⧗ OD-03 bilan birga ko‘riladi). Unga qadar `landing_pr_merge` owner-only.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Landing’ni AMT hostida joylashtirish | izolyatsiya buziladi (Q46.4) |
| Tilda’da qolish | tracking va variant boshqaruvi cheklangan; `fbclid` yo‘qoladi |
| Darhol avtomatik deploy | Q41 |
| `amt-release` ga landing/Umami deploy vakolatini berish | AMT hostiga production deploy credential’i tushadi (Q46.4) |

## Oqibatlar

- **+** Agent xatosi production’ni buza olmaydi; har o‘zgarish ko‘rib chiqilgan PR; `fbclid` saqlanadi va CAPI ishlaydi.
- **−** CRO sikli sekinroq: owner merge’ini kutish kerak.
- **−** Landing kodini AMT build qiladi, lekin deploy’ni owner qiladi (HUMAN_GATE).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Avto-deploy shartlari | Q41 trafik yetarliligi dalili va CRO Trust Ramp bajarilishi | `owner_request` | avto-deploy ADR’i va yangi owner Q |
| Landing’da tracking yo‘qolishi | `accepted_vs_crm_receipts` yoki `pixel_vs_crm_leads` tekshiruvi fail | tracking-health | INCIDENTS; tuzatish PR’i |
| AMT hostida Dokploy/landing credential’i | ≥ 1 topilma (salbiy test yoki audit) | `incident_aar` | release bloklanadi; credential rotatsiyasi |

## Kanonik implementatsiya

- [F2_Landing_Tracking](../05_Build_Phases/F2_Landing_Tracking.md), [TRACKING_CAPI §1](../03_Architecture/TRACKING_CAPI.md).
- [release-policy.yaml](../09_Config_Templates/release-policy.yaml) — `scope`, `out_of_scope`.
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `landing_pr_merge`, `landing_pr_paths`, `offer_change`.
- [WF-B04](../09_Config_Templates/workflows/WF-B04.yaml); [PHASES §4](../05_Build_Phases/PHASES.md) — HG-F0-05, HG-F2-01, HG-F2-09, HG-F2-14, HG-F2-15, HG-F2-18.
- [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I08, I21; [ADR-020](ADR-020-config-deploy-path.md).
