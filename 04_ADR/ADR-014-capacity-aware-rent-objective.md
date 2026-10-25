# ADR-014 — Ijara pipeline’i uchun park sig‘imini hisobga oluvchi maqsad

Holat: Accepted · Qaror egasi: owner (Q43 ✅) + builder ★ (Q43★, fleet hold) + builder ◇ P-06, P-09, P-22 + ⧗ OD-07, OD-14 · Sana: 2026-10-22

## Kontekst

- Faktlar [D: owner, Q43]: ijara tranzaksiyalari (uzaytirishlar bilan birga) — iyun 570, iyul 557, avgust 540, sentabr 512; o‘sha kontekstdagi taxminiy sig‘im ≈ 600 tranzaksiya/oy; park to‘lganda waitlist ochiladi; kunlik bandlikni AI Telegram bot orqali so‘raydi.
- Bu raqamlar oylik tranzaksiya (renewal bilan) — fizik velosiped soni yoki bandlik chegarasi emas (`capacity-policy.yaml#historical_owner_context.use_as_physical_denominator: false`).
- Xulosalar: bandlik yuqori [X]; iyundan sentabrgacha pasayish bor, sababi noma’lum [?] — F2 da C05 retsepti bilan tahlil qilinadi (mavsum, churn, raqobat yoki tracking).
- Theory of Constraints: cheklov parkda bo‘lsa, qo‘shimcha ijara lead’i daromad bermaydi, reklama pulini yeydi [X].
- Rent tekshiruvi fleet so‘rovidan oldin ishlasa, rent qarori har kuni kechagi ma’lumotga tayanadi va 10:00 batch’dagi rent band eskirgan bo‘ladi [X] — ritm hodisaga bog‘lanishi kerak.
- Waitlist’ning yagona manbai (fleet snapshot yoki CRM statuslari) hali tanlanmagan (⧗ OD-07).

## Qaror

1. **Ijara maqsadi:** bandlikni va sog‘lom waitlist’ni eng arzon narxda ushlab turish, chiqib ketganlarni to‘ldirish. **Sotuv maqsadi:** qualified lead’ni maksimallashtirish (Q43★).
2. **Bandlik** = `rented_bikes / serviceable_bikes` (denominator nol bo‘lsa — unknown). Balans: `serviceable_bikes = rented_bikes + reserved_bikes + available_bikes`; `total_fleet = serviceable_bikes + maintenance_bikes` (I10).
3. **Kunlik fleet snapshot:** ops-bot `fleet_operator` dan wizard orqali so‘raydi — `rented_bikes`, `reserved_bikes`, `available_bikes`, `maintenance_bikes`, `waitlist_active`, `waitlist_eligible_ready`, `waitlist_oldest_at`, `expected_returns_next_24h`; `serviceable_bikes` va `total_fleet` hisoblanadi va oldingi valid snapshot bilan solishtiriladi (farq operator tasdig‘ini talab qiladi). Javoblar append-only; oxirgi valid javob amal qiladi.
4. **Ritm** (◇ P-06 — ★ standartdagi 09:00/12:00/14:00 vaqtlari o‘rniga; owner tasdig‘i ⧗ OD-14): so‘rov 08:00, eslatma 09:00, eskalatsiya 14:00. Media Buyer rent takliflari `fleet_snapshot_accepted` hodisasida bugungi snapshot revision’i bilan tuziladi; 10:00 batch uchun cutoff 09:45; kech kelgan rent band alohida, o‘z `presented_at` va TTL bilan.
5. **Hold:** bugungi valid snapshot bo‘lmasa oddiy rent byudjet o‘zgarishi taklif ham, dispatch ham qilinmaydi — freshness taklif va dispatch paytida tekshiriladi, eskirgan snapshot hech qachon valid emas. ★ 14:00 gacha valid snapshot bo‘lmasa o‘sha kun barcha oddiy rent byudjet o‘zgarishlari hold (oshirilmaydi ham, pasaytirilmaydi ham). Protective controls bunga bog‘liq emas.
6. **Band qoidalari** (`capacity-policy.yaml#bands`): `waitlist_eligible_ready ≥ waitlist_high` → ijara byudjeti owner tasdiqlagan floor tomon kamayadi; `available_bikes ≥ available_high` va `waitlist_eligible_ready = 0` → byudjet va approval doirasida oshiriladi; boshqa holatda o‘zgarish yo‘q; histerezis kunlari bilan. Barcha o‘zgarishlar rolling 24 soat ≤ 20% chegarasida ([ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)) va change set orqali. `waitlist_high`, `available_high`, `rent_floor_daily_minor`, `hysteresis_days` — null; ular F5 da owner va Funnel Analyst tomonidan bandlik va waitlist tarixidan kalibrlanadi (`fleet.thresholds`).
7. **Sotuvga o‘tkazish** `sale.readiness` talab qiladi: gate F6_STEP2 (◇ P-09); manba — sales_lead kunlik `/sale_ready` wizard’i yoki tasdiqlangan eksport (◇ P-22). Butun byudjetni sarflash majburiyati yo‘q.
8. **Waitlist manbai** (⧗ OD-07 hal bo‘lguncha): snapshot sonlari bandlarni boshqaradi; CRM waitlist statuslari solishtirish uchun; biznes metrikalari PII’siz `waitlist_aggregates` dan.
9. Capacity hold — favqulodda pauza vakolati emas; `protective_pause` alohida ([ADR-030](ADR-030-kill-modes-and-protective-controls.md)).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Ikkala pipeline uchun bitta qualified-lead maksimizatsiyasi | park cheklovini e’tiborsiz qoldiradi |
| Bandlikni u-code.io API’sidan avtomatik olish | owner Telegram so‘rovini tanlagan (Q43); API integratsiyasi keyinroq ko‘rib chiqilishi mumkin |
| Q43 tranzaksiya raqamlarini fizik denominator qilish | tranzaksiya ≠ velosiped; bandlik noto‘g‘ri chiqadi |
| Valid snapshot bo‘lmagan kunda kechagi qiymat bilan rent byudjetini o‘zgartirish | eskirgan ma’lumot bilan pul harakati |
| Rent tekshiruvini qat’iy 08:30 vaqtda qoldirish | bugungi snapshot hali kelmagan bo‘ladi; rent bandlari har kuni hold’ga tushadi |

## Oqibatlar

- **+** Reklama puli cheklovi yo‘q yo‘nalishga (sotuvga) yo‘naltiriladi; ijara KPI’si biznes reallikka mos.
- **−** Kundalik inson kiritishiga bog‘liqlik bor (fleet_operator yuki) — premortem’dagi operator yuki xavfi.
- **−** Ijara qualified CPL’ini tushunish uchun uni bandlik bilan birga o‘qish kerak ([ADR-013](ADR-013-staged-golive-kill-criteria.md)).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Park kengayishi | `total_fleet` o‘zgarishi | fleet snapshot | bandlar qayta kalibrlanadi |
| Waitlist bo‘sh qolishi | 2 hafta ketma-ket `waitlist_eligible_ready = 0` | fleet snapshot | ijara maqsadi va bandlari qayta ko‘riladi |
| Bandlik ma’lumoti kelmasligi | 3 kundan ortiq valid snapshot yo‘q | `fleet_escalate` alertlari | u-code.io API integratsiyasi ADR’i |
| Waitlist manbai qarori | ⧗ OD-07 hal bo‘lsa | `owner_request` | band manbai yangilanadi |
| Ritm qarori | ⧗ OD-14 da owner P-06 ni rad etsa | `owner_request` | jadval qayta ko‘riladi |

## Kanonik implementatsiya

- [capacity-policy.yaml](../09_Config_Templates/capacity-policy.yaml), [sale-readiness.yaml](../09_Config_Templates/sale-readiness.yaml), [operations.yaml](../09_Config_Templates/operations.yaml) — `schedule`.
- [BUSINESS_CONTRACT §5–§6](../11_Production_Contracts/BUSINESS_CONTRACT.md), [MEDIA_BUYER](../02_Team_Charter/agents/MEDIA_BUYER.md), [TELEGRAM §4](../03_Architecture/TELEGRAM.md).
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `fleet.freshness`, `fleet.waitlist`, `fleet.thresholds`, `sale.readiness`.
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-01, UAT-02; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I10.
