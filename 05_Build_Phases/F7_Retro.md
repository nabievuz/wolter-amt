# F7 — To‘liq takeover’dan 30 kun keyingi biznes qabul va retro

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

## Maqsad
To‘liq takeover’dan **30 kun** keyin AMT natijasini dalil bilan baholash (C12, Q13 ✅), premortem va Trust Ramp holatini qayta ko‘rish, saboqlarni boshqariladigan yaxshilash sikli orqali SOP/ADR/skill’larga kiritish, birinchi to‘liq evolution siklini qabul qilish va keyingi chorak rejasini (C11) tuzish.

## Prerequisites
F6 accepted ([PHASES §2.2](PHASES.md)). F7 soati — HG-F6-02 dan keyingi birinchi sale live dispatch vaqti; 30 kun shundan hisoblanadi ([PHASES §3](PHASES.md)). Oldingi 14 + 7 tracking, 7 shadow va 14 rent oynalari bilan ketma-ket minimal kuzatuv 72 kun; build, kutish va takroriy oyna qo‘shimcha. 30 kun yetilmagan kogortani sun’iy ravishda yetilgan qilmaydi. Kirish ma’lumotlari: haftalik C07 hisobotlari, change set tarixi, `command_outcomes` va Trust Ramp ledger’i, Langfuse va proxy xarajat datasi.

## Tasks
1. **C12 retro** (`cmo` + `funnel-analyst`, L3): IMP-03 AAR (nima rejalangan / nima bo‘ldi / nega / nima o‘zgaradi) → DGN-02 → SYS-02 → MTA-02 (mustaqil kontekstda stress-test) → PRI-01.
   - Qamrov: North Star (qualified lead sale/rent), qualified CPL vs baseline, yetilgan lead→shartnoma, paid/realized cash/contribution, fulfilment, cancel/refund, rent yangi/renewal va bandlik/waitlist, sale readiness, xarajat (USD 150/oy — 15 000 USD minor — ichidami, agent ulushlari), approval statistikasi (latency, ❌ ulushi, rubber-stamp signali), insidentlar, kreativ samaradorligi, eksperiment natijalari (jumladan `inconclusive`).
2. **Premortem review** — C1–C10 sabablari: qaysi biri ro‘y berdi, kuchaydi yoki yo‘qoldi; erta signallar holati; yangi risklar ([PREMORTEM](../00_Decisions/PREMORTEM.md)).
3. **Trust Ramp graduation review** — har `action_type × pipeline` uchun `command_outcomes` asosidagi ledger: 10 ketma-ket `met` natijali toza live item va oxirgi sanalgan itemdan keyin shu juftlikda 14 kun incidentsiz (★; `inconclusive`, `not_met` va shadow sanalmaydi — ◇ P-04; seriya `trust_ramp.graduation.streak_effects` bo‘yicha: sanaladigan `met`dan boshqa har natija 0 ga qaytaradi, `met` deterministik — ◇ P-42; ledger yonida `TRUST_RAMP_FEASIBILITY.md` jadvali yangilanadi) shartiga yetgan juftliklar ro‘yxati. Har juftlik L2 ga faqat alohida HG-L2-01 (`/graduate`, `trust_graduation`, identity isolation dalili bilan; L2_ENABLE) orqali o‘tadi; NEVER_AUTO ro‘yxati o‘zgarmaydi.
4. **Targetolog roli** — `ads_approver` muddati HG-F6-01 dan 28 kun va u F7 dan oldin tugaydi; rotatsiya qarori Step1 + 21 kunda HG-F6-05 da qabul qilingan (◇ P-17). F7 shu qaror va uning natijasini ko‘rib chiqadi, `amt.people`/`amt.roles` bilan mosligini va eslatma tugashdan 7 kun oldin yuborilganini tekshiradi.
4a. **Operatsion intizom** — HG-OPS-01 (`cap_update_formula` va read-back), kill criteria job natijalari, tracking health tarixi, choraklik kill mashqi (◇ P-12), oylik restore drill va credential rotation retroga kiritiladi.
5. **Saboq → o‘zgarish** — har saboq `evo.signal.submit` bilan signal sifatida (`problem_fingerprint` bo‘yicha dedup; ochiq proposal takroriy signalni o‘ziga oladi) WF-E04 (saboq/skill/bilim) yoki WF-E01 (upgrade proposal) ga beriladi: sandbox, mustaqil verification, owner merge va release (HG-GIT-01, HG-REL-01), kuzatuv va `accepted | rejected | inconclusive` verdikti bilan ([EVOLUTION_CONTRACT](../11_Production_Contracts/EVOLUTION_CONTRACT.md)). Faqat `accepted` va `guidance_eligible` saboq `knowledge/lessons/` ga va agent ko‘rsatmasiga kiradi; rejected yoki inconclusive natija yutuq deb yozilmaydi; xom log yoki tashqi hujjat avtomatik ko‘rsatma bo‘lmaydi. ADR’lar `04_ADR/` da (yangi yoki `Superseded`), runbook’lar `06_Runbooks/` da shu yo‘l bilan yangilanadi.
6. **Keyingi chorak rejasi** (C11): STR-01 → STR-02/03 → reja va KPI daraxti (DAT-01); landing avto-deploy uchun trafik hajmi tekshiruvi (Q41 ✅).
7. Keyingi retro va premortem sanalarini routine qilish (oylik C12; premortem — 2027-01-15 va keyin har 3–4 oyda).
8. **FE biznes qabuli** — birinchi to‘liq haqiqiy evolution sikli: signal → proposal → sandbox → mustaqil verification → owner release → kuzatuv → verdikt → xotira (EVO-AT14). Pullik engineering o‘chiq bo‘lsa (⧗ OD-02) sikl owner/builder qo‘lda bajargan, lekin xuddi shu sandbox → verification → release yo‘lidan o‘tgan ish bilan. EVO-AT14 `pass` FE ni `business_accepted` qiladi ([FE_Evolution](FE_Evolution.md)).

## Deliverables
`build/F7/{RETRO,PREMORTEM_REVIEW,TRUST_RAMP_REVIEW,NEXT_QUARTER_PLAN,EVOLUTION_CYCLE,REPORT,STATUS}.md`, verdikti bilan yopilgan WF-E01/WF-E04 run’lari, yangilangan ADR/runbook/skill PR’lari.

## Acceptance tests

| ID | Nima | Usul | Kutilgan |
|---|---|---|---|
| F7-AT-01 | Retro | `RETRO.md` | L3 shablon, har da’vo teglangan, manbasiz raqam yo‘q |
| F7-AT-02 | Premortem | `PREMORTEM_REVIEW.md` | C1–C10 har biri holati bilan |
| F7-AT-03 | Graduation | `TRUST_RAMP_REVIEW.md` + `approval-policy.yaml` + HG-L2-01 yozuvlari | har L2 o‘tishi owner tasdig‘i va `trust_graduation` binding’i bilan; shart bajarilmagan juftlik L1 da |
| F7-AT-04 | Saboqlar → artefakt | WF-E04/WF-E01 run’lari va PR’lar ro‘yxati | har asosiy saboq verdikti bilan yopilgan run’ga va ADR/SOP/skill o‘zgarishiga bog‘langan; rejected/inconclusive yutuq deb yozilmagan |
| F7-AT-05 | Keyingi chorak | `NEXT_QUARTER_PLAN.md` + HG-F7-01 | owner tasdiqlagan |
| F7-AT-06 | Biznes qabul | yetilgan kogorta, min sample, zero-qualified exposure, cash/contribution va fulfilment/refund hisoboti | biznes chegarasi dalili; past N inconclusive va scale blok; uydirma uplift yo‘q |
| F7-AT-07 | Davomiy ops | primary/deputy ACK, recovery class RPO/RTO, cap reconciliation, choraklik kill mashqi, credential rotation va rol muddati (HG-F6-05) dalili | har ochiq risk egasi, muddati va xavfsiz holati bilan; monitoring uzluksiz |

## HUMAN_GATEs
HG-F7-01. Har L2 o‘tishi — HG-L2-01; saboq release’lari — HG-GIT-01 va HG-REL-01.

## Rollback
Retro qarorlari PR va release orqali kiritiladi — har biri alohida qaytarilishi mumkin; L2 juftligi incident yoki kill criteria bilan pasaytiriladi (`trust_ramp.demotion`).

## Riskler (RSK-03)

| Nosozlik | Oqibat | Chora |
|---|---|---|
| Retro "framework teatri"ga aylanadi | o‘zgarish yo‘q | har blokda "Qarorga ta’siri"; saboq → verdiktli run majburiy (F7-AT-04) |
| 30 kun mavsumiy shovqinga to‘g‘ri keladi | noto‘g‘ri xulosa | 12 oylik profil va diff-in-diff diagnostika sifatida davom ettiriladi |
| Tekshirilmagan saboq ko‘rsatmaga aylanadi | xotira ifloslanadi | faqat `accepted` va `guidance_eligible`; WF-E04; EVO-AT14 |
| `inconclusive` natija yutuq deb yoziladi | noto‘g‘ri strategiya | `evolution.outcome_policy`; inconclusive kengayish yoki avtonomiyani oqlamaydi |
