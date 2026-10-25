# ADR-029 — Pul modeli: integer minor birlik, mustaqil provider cap va admission

Holat: Accepted · Qaror egasi: owner (Q08, Q10/Q33/Q44.1, Q37 ✅) + builder ★ (integer birlik, oylik cap yangilash, `/budget raise`) + builder ◇ P-01, P-02, P-21 · Sana: 2026-10-23

## Kontekst

- Owner chegaralari [D: DECISION_LOG]:
  - AI/media runtime — bitta OpenRouter kaliti, USD 150/oy (15 000 USD minor) qattiq limit (Q10/Q33/Q44.1);
  - paid Meta — oylik reklama ≤ USD 1 500/oy (150 000 USD minor), kunlik byudjet o‘zgarishi ≤ ±20%, narx/aksiya faqat offer registry’dan (Q08);
  - Ads Manager **account spending limit** — AI’dan mustaqil cap; kill switch; tracking hard gate (Q37).
- ★ H-bo‘lim: Meta `spend_cap` kumulyativ (lifetime), oylik emas; owner har oy 1-kuni cap’ni yangilaydi (HG-OPS-01); gateway headroom’ni va oy boshidan sarfni alohida nazorat qiladi. Tarixi bor akkauntga to‘g‘ridan-to‘g‘ri 1 500 qo‘yilsa barcha reklama darhol to‘xtaydi [D2: kb.orbee.com, jonloomer.com · qayta tekshiriladi].
- Akkaunt valyutasi, timezone’i va provider counter bazasi akkauntga bog‘liq va hali o‘lchanmagan [?] — `vendor.meta_cap`.
- byadsco’da budget va spend cap’ning sent/dollar aralashish xatosi bo‘lgan (#171) [D] — float yoki aralash birlik to‘g‘ridan-to‘g‘ri pul xatosiga olib keladi.
- Faol kampaniyalar yangi write bo‘lmasa ham sarflashda davom etadi; AMT hosti yoki AI ishlamay qolsa ham cap ishlashi kerak [X] — demak asosiy himoya host’dan mustaqil bo‘lishi shart.
- Ketma-ket kichik byudjet o‘zgarishlari "kunlik ±20%" ni aylanib o‘tishi mumkin [X]. Oy o‘rtasida `amount_spent + oylik cap` bilan yangilangan cap oylik limitdan oshirib yuborishi mumkin [X].
- Inson boshqaradigan (begona) kampaniyalar ham oy boshidan sarfga (MTD) kiradi; AMT’da ularni pauza qilish vakolati yo‘q.

## Qaror

### Birlik va hisob davri

1. Barcha pul integer minor birlikda va aniq valyuta bilan (`budgets.yaml#amount_unit: minor`; 1 USD = 100 minor); float ishlatilmaydi; har birlik konvertatsiyasi unit-test bilan qoplanadi. Biznes oyi — `Asia/Tashkent`.
2. Hujjat yozuvi: "USD 150/oy (15 000 USD minor)", "USD 1 500/oy (150 000 USD minor)"; config kalitlari `_minor` bilan tugaydi.

### AI/media runtime

3. Kalit limiti `openrouter.key_hard_cap_minor: 15000`; ulushlar, rezerv, 80/100/90% qoidalari va proxy admission — [ADR-003](ADR-003-openrouter-single-key-watchdog.md). AI hisobi atomik actual+reserved; noaniq billing nolga aylanmaydi (I11).
4. `/budget raise <agent_slug|media_generation> <whole_usd>` → `extra_minor = whole_usd * 100`; owner typed-code ikki bosqich (`budget_override`); faqat 15 000 USD minor kalit limiti ichida qayta taqsimlaydi va reklama cap’iga tegmaydi (`affects_ads_cap: false`); bot major va minor qiymatni birga ko‘rsatadi.
5. Engineering xarajati alohida hisob (`engineering-budget.yaml#shares_runtime_ai_cap: false`, `shares_ads_cap: false`); pullik engineering ⧗ OD-02 hal bo‘lguncha o‘chiq (I25).

### Paid Meta — ikki mustaqil himoya qatlami

6. **Provider spending limit majburiy va AI’dan mustaqil (Q37 ✅):** `ads.provider_spend_limit_required: true`. Limitni HG-F3-02 da owner o‘rnatadi; `vendor.meta_cap` (F3_CONTROLLED_TEST) faqat API read-back kutilgan qiymatga teng bo‘lsa PASS (`provider_spend_limit_readback_required: true`). Limitni olib tashlash yoki boshqa mexanizm bilan almashtirish faqat Q37 ni o‘zgartiruvchi yangi owner Q bilan (⟲ Q37) — readiness qiymati bilan hech qachon.
7. **Oylik yangilash** — har oy 1-kuni HG-OPS-01 (★; ops-bot qiymatni hisoblab eslatadi), formula (◇ P-02, qattiqroq):
   `spend_cap_native = provider_counter_now_native + to_native(max(0, monthly_cap_minor - verified_mtd_minor - safety_margin_minor))`
   — provider minor birligiga pastga yaxlitlanadi (`cap_update_rounding: round_down_to_provider_minor_unit`). AI so‘rovining settlement’i esa yuqoriga yaxlitlanadi: `ceil(total_cost × 100)` minor (`budgets.yaml#openrouter.reservation_sizing.settlement_rule`, ◇ P-99) — sentdan arzon ko‘p chaqiruv ulushni kam hisoblamaydi. `safety_margin_minor`, valyuta, timezone, counter bazasi va `fx_policy` hozir null — `budget.ads_limits` va `vendor.meta_cap` da dalil bilan yopiladi.
8. **Gateway admission** (Q08 ning oylik cap’ini kodda ushlash): risk oshiruvchi har ads command commitment hisoblaydi va faqat quyidagi shart bajarilsa qabul qilinadi:
   `verified_mtd_minor + sum(active_daily_minor * remaining_days) + sum(held_commitments_minor) + requested_minor <= monthly_cap_minor - safety_margin_minor` (`ads.admission_rule`)
   Barcha qiymatlar `ads.fx_policy` bo‘yicha provider counter valyutasiga keltiriladi.

   | Action (`ads.commitment_basis`) | `commitment_minor` |
   |---|---|
   | `budget_change` | `max(0, new_daily_minor - old_daily_minor) * remaining_days_in_business_month` |
   | `entity_activate` | `daily_budget_minor * remaining_days_in_business_month` |
   | `campaign_activate` | `daily_budget_minor * remaining_days_in_business_month` |
   | `creative_activate_new_adset` | `daily_budget_minor * remaining_days_in_business_month` |
   | `entity_pause`, `protective_pause` | 0 |

   Rezerv `rejected`, `expired` va `cancelled` da bo‘shatiladi, `succeeded` da settle qilinadi.
9. **Rolling 24 soat chegarasi** (◇ P-01 — Q08/Q32 dagi "kunlik ±20%" ning qattiqroq aniqlashtirilishi): entity bo‘yicha oyna ichidagi barcha oddiy budget o‘zgarishlari mutlaq qiymatlarining yig‘indisi oyna boshidagi tasdiqlangan budget’ning 20% idan oshmaydi (`rolling24h_sum_abs_delta / verified_budget_at_window_start <= 0.20`). Inson qo‘lda o‘zgartirgan budget (drift) bloklanadi va reconcile qilinadi, yangi bazani yashirin o‘rnatmaydi (`manual_drift_behavior: block_and_reconcile`); nol yoki noma’lum baza oshirishni bloklaydi va owner review talab qiladi.
10. **Biznes natija guard’i:** KC-02 ishga tushgan yoki lead → shartnoma `data_status` `valid` bo‘lmagan paytda budget oshirish bloklanadi (`actions.budget_change.business_outcome_guard`).
11. **`protective_pause` — qo‘shimcha deterministik qatlam, provider limit’ning muqobili emas** (◇ P-21; `ads.protective_pause_is_additional: true`): spend pacer tekshiruvi har sync siklida `amt-sync` da ishlaydi; managed headroom ≤ safety margin bo‘lsa yoki managed entity faol paytda spend ma’lumoti `budget.ads_pacing` cutoff’idan eski bo‘lsa, `amt-control` pause-only command chiqaradi ([ADR-030](ADR-030-kill-modes-and-protective-controls.md)).
12. **Begona kampaniyalar:** AMT inson boshqaradigan kampaniyalarni hech qachon pauza qilmaydi; ular cap’ni yesa — urgent alert va owner handback (`foreign_spend_behavior: alert_and_owner_handback_only`). Alertning o‘zi himoya emas.
13. **Hard-cap qabul dalili** uch qismdan iborat (`ads.hard_cap_pass_requires`): provider limit read-back, gateway headroom testi va AMT host o‘chiq paytda provider limit ushlab turishi. F6 Step 1 dan oldin shu kungi read-back va headroom tekshiruvi — `budget.ads_fresh_check` (`max_evidence_age: P1D`).
14. **Hisob yozuvlari:** AI — `ai_requests` (actual+reserved), `provider_usage_snapshots` (yozuvchi `amt-proxy`), `agent_runtime_state` (yozuvchi `amt-watchdog` → `amt-control`); ads — spend va budget harakati ledger’i, commitment rezervlari, `protective_actions`.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Provider limit o‘rniga faqat AMT ichidagi safe-pause | AMT host ishlamasa himoya yo‘qoladi; Q37 ni o‘zgartiradi |
| Ads Manager’da cap’ni to‘g‘ridan-to‘g‘ri 150 000 USD minor qilish | cap kumulyativ — tarixi bor akkauntda reklama darhol to‘xtaydi |
| Cap = `amount_spent + oylik cap` | oy o‘rtasida yangilansa oylik limitdan oshiradi (◇ P-02 qattiqroq) |
| Float yoki aralash birlik | yaxlitlash va sent/dollar xatolari |
| "±20%" ni har bitta o‘zgarishga alohida qo‘llash | ketma-ket kichik o‘zgarishlar chegarani aylanib o‘tadi |
| Faqat alertga tayanish | alert inson javobiga bog‘liq; kafolat emas |
| Begona kampaniyalarni ham avtomatik pauza qilish | AMT vakolatidan tashqari; inson boshqaruvini buzadi |

## Oqibatlar

- **+** Ikki mustaqil himoya: host’dan mustaqil provider limit va host ichidagi admission hamda protective pause.
- **+** Pul birligi xatolari strukturaviy jihatdan yopiladi.
- **−** Oylik qo‘lda yangilash owner vaqtini oladi (HG-OPS-01).
- **−** Commitment rezervlari oy oxirida yangi faollashtirishni cheklaydi — bu qasddan.
- **−** Valyuta, FX va timezone dalili bo‘lmaguncha F3_CONTROLLED_TEST yopilmaydi.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Read-back nomuvofiqligi | provider cap kutilgan qiymatga teng emas | `vendor.meta_cap`, HG-OPS-01 tekshiruvi | risk oshiruvchi write bloklanadi; owner tuzatadi |
| Oy yakuni sarfi | verified MTD `monthly_cap_minor − safety_margin_minor` dan oshsa | spend ledger | RCA; `safety_margin_minor` qayta ko‘riladi |
| Protective pause tez-tez ishlashi | bir biznes oyida takroriy `protective_pause` | `protective_actions` | pacing va commitment parametrlari qayta ko‘riladi |
| Meta cap semantikasi | vendor hujjatida spend cap xulqi o‘zgarsa | `vendor_advisory` | formula va ADR yangilanadi |
| Begona sarf | `foreign_spend_behavior` alerti | TELEGRAM alerti | owner bilan cap va handback kelishuvi |
| Owner qarori | P-01, P-02 yoki P-21 qabul yoki rad | `owner_request` | holat yangilanadi |

## Kanonik implementatsiya

- [budgets.yaml](../09_Config_Templates/budgets.yaml) — `openrouter.*`, `ads.*` (jumladan `cap_update_formula`, `commitment_basis`, `admission_rule`, `hard_cap_pass_requires`).
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `budget_change.limits`, `budget_change.business_outcome_guard`, `protective_pause`, `budget_override`.
- [engineering-budget.yaml](../09_Config_Templates/engineering-budget.yaml); [operations.yaml](../09_Config_Templates/operations.yaml) — `protective_controls`, `schedule.spend_cap_update`.
- [GUARDRAIL_GATEWAY §7](../03_Architecture/GUARDRAIL_GATEWAY.md), [DATA_MODEL §7](../03_Architecture/DATA_MODEL.md), [OPERATING_ENVELOPE §1](../11_Production_Contracts/OPERATING_ENVELOPE.md).
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `vendor.meta_cap`, `budget.ads_limits`, `budget.ads_pacing`, `budget.ads_fresh_check`, `vendor.openrouter_period`.
- [PHASES §4](../05_Build_Phases/PHASES.md) — HG-F3-02, HG-OPS-01; [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-16, UAT-17, UAT-18, UAT-20; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I11, I12.
