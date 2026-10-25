# ADR-031 — Readiness modeli va qaror vakolati

Holat: Proposed · Qaror egasi: builder ◇ P-26 (gate joylashuvi — P-08, P-09) + ⧗ OD-06; FE joylashuvi owner Q67 bilan tasdiqlangan · Sana: 2026-10-25

## Kontekst

- Owner qarorlarining asl matni [DECISION_LOG](../00_Decisions/DECISION_LOG.md) da; boshqa hujjatlar ularni amalga oshiradi. Q11: build to‘xtashi faqat credential/OAuth, pul sarfi va go-live’da; ishga tushgandan keyin o‘zgarish faqat PR + owner tasdig‘i bilan [D: DECISION_LOG].
- Owner tasdiqlagan qaror (✅), owner xulosada qabul qilgan builder standarti (★), builder taklifi (◇) va ochiq qaror (⧗) bir-biridan farqlanmasa, builder qaysi qoidani faqat owner o‘zgartira olishini bilmaydi va taklif jim "qaror"ga aylanadi [X].
- Haqiqiy qiymatlar — narx, RPO/RTO, sample, operator, vendor imkoniyati — spetsifikatsiya yozilgan paytda noma’lum; ularni uydirish Kernel qoidasiga zid [D: THINKING_MODELS §1]. Ular readiness kalitlari sifatida egasi, gate’i va dalili bilan yopilishi kerak.
- Bitta kalit bir nechta profilda turli dalil bilan takrorlansa, gate soxta yopilishi yoki hech qachon yopilmasligi mumkin; dalilni tayyorlagan va tasdiqlagan shaxs bir xil bo‘lsa, nazorat yo‘qoladi [X].
- Readiness faqat hujjatda PASS bo‘lib, runtime capability’ni cheklamasa, gate faqat qog‘ozda qoladi [X].

## Qaror

### Qaror holatlari

| Belgi | Ma’nosi | Kim o‘zgartiradi |
|---|---|---|
| ✅ | owner tasdiqlagan qaror (Q-ID) | faqat owner, yangi Q orqali; eskisi ⟲ |
| ★ | owner xulosada qabul qilgan builder standarti | owner, yoki owner qabul qilgan ◇ |
| ◇ | builder taklifi `P-NN`, owner ko‘rib chiqishini kutmoqda | qattiqroq bo‘lsa darhol amal qiladi; biror narsani yumshatsa — faqat owner qabul qilgach |
| ⧗ | ochiq owner qarori `OD-NN` | owner; faqat o‘z qatoridagi gate’ni bloklaydi |
| ⟲ | keyingi qaror bilan almashtirilgan | — |

### Ustuvorlik (ziddiyatda yuqoridagisi ustun)

1. DECISION_LOG’dagi owner ✅ qarorlari (asl matn, Q-ID).
2. [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) — har invariant amalga oshirgan Q-ID’ni ko‘rsatadi; ✅ dan qattiqroq bo‘lishi mumkin, yumshoqroq emas.
3. Production kontraktlar (BUSINESS_CONTRACT, CONFIG_CONTRACT, OPERATING_ENVELOPE, WORKFLOW_CONTRACT, EVOLUTION_CONTRACT), config shablonlari va `Holat: Accepted` ADR’lar.
4. Arxitektura, build fazalari, runbook’lar, jamoa nizomlari, skill’lar va eval’lar.
5. `readiness.yaml` qiymatlari — faqat 1–3 chegarasida; readiness qiymati owner belgilagan nazoratga muqobil yaratolmaydi (masalan, provider spending limit o‘rnini bosolmaydi — [ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)).
6. Ma’lumotnoma (`10_Reference/`).

Ziddiyat qoidasi: hal bo‘lguncha qattiqroq qoida amal qiladi; ziddiyat [OPEN_ITEMS](../00_Decisions/OPEN_ITEMS.md) ziddiyatlar reyestriga (C-NN) yoziladi; pul, PII yoki vakolatga tegsa — HUMAN_GATE.

### Readiness yozuvi

- Maydonlar: `key`, `gate`, `criticality` (`critical | optional`), `accountable_role`, `co_signers`, `prepared_by`, `description`, `status`, `value`, `evidence_ref`, `evidence_at`, `max_evidence_age`, `approved_by`, `approved_at`, `valid_until`.
- Holat: `pending → evidenced → approved`; `not_applicable` faqat `criticality: optional` uchun, sabab va owner imzosi bilan.
- `accountable_role` ∈ {`owner`, `sales_lead`, `fleet_operator`, `technical_operator`, `finance_owner`, `privacy_owner`, `independent_reviewer`}. Agentlar va builder faqat `prepared_by` sifatida ko‘rinadi va hech qachon approve qilmaydi.
- `approved_by` — `approved_at` paytida `accountable_role` ni egallagan shaxs va dalilni tayyorlagan shaxsdan boshqa; `co_signers` ham tasdiqlaydi. Identitetlar faqat `amt.people`/`amt.roles` da; readiness opaque `person_ref` saqlaydi.

### Profillar DAG’i

- Har talab aniq **bitta** `gate` profiliga ega — eng erta profil; keyingi profillar uni `requires` orqali tranzitiv meros oladi. Keyingi gate to‘liqroq yoki yangiroq dalil talab qilsa — `max_evidence_age` bilan alohida kalit: `vendor.meta_cap` (F3_CONTROLLED_TEST) / `budget.ads_fresh_check` (F6_STEP1, P1D); `recovery.intake_datasets`, `recovery.intake_drill` (F2_LIVE_INTAKE) / `recovery.full_datasets`, `recovery.full_drill` (F6_STEP1); `ops.independent_monitor` (F2_LIVE_INTAKE) / `ops.independent_monitor_full` (F6_STEP1); `vendor.runner_isolation` (F1_ISOLATION) / `vendor.runner_isolation_final` (F4_AGENTS); `ops.roles_owner` (F1_AUTH) / `ops.roles_roster` (F2_LIVE_INTAKE).
- Profil PASS: o‘zining va meros olgan barcha profillarning har talabi `approved` (va `max_evidence_age` dan eskirmagan) yoki asosli `not_applicable`.

| Profil | `requires` |
|---|---|
| F1_AUTH, F1_COST_RUNTIME, F1_ISOLATION, F1_WORKFLOW | — |
| F2_LIVE_INTAKE | F1_AUTH, F1_COST_RUNTIME, F1_ISOLATION, F1_WORKFLOW |
| F2_TRACKING_PASS | F2_LIVE_INTAKE |
| F3_CONTROLLED_TEST | F2_TRACKING_PASS |
| F4_AGENTS | F3_CONTROLLED_TEST |
| F4_CONTENT | F4_AGENTS |
| FE_SANDBOX | F1_ISOLATION, F1_WORKFLOW |
| FE_RELEASE | FE_SANDBOX |
| F5_GO | F2_TRACKING_PASS, F4_CONTENT, FE_RELEASE |
| F6_STEP1 | F5_GO |
| F6_STEP2 | F6_STEP1 |
| L2_ENABLE | F6_STEP1 |
| PRE_SCREEN | F5_GO |
| AUTO_RELEASE_ENABLE | F6_STEP2, FE_RELEASE |

- Gate joylashuvi takliflari: iqtisodiy readiness (`business.*`) F5_GO da (◇ P-08; ⧗ OD-06 uni F6_STEP2 yoki F7 monitoringiga ko‘chirishi mumkin); `sale.readiness` F6_STEP2 da (◇ P-09); FE_RELEASE F5 formal eval va shadow boshlanishidan oldin, Q66 exact baseline mustaqil texnik inson signoff’i bilan (Q67; OD-01 yopildi); F5_GO merosi saqlanadi.

### Runtime bog‘lanishi

- `execution-policy.yaml#capability_requires_profile` capability’ni profilga bog‘laydi; `amt-release` va `amt-control` capability o‘z gate’idan o‘tmagan (release’da yoqiladigan capability — release snapshot’i, owner o‘tishi bilan ochiladigan — `control_events`) yoki `operational_validity` bajarilmagan bo‘lsa capability yoki rejimni rad etadi (`capability_enforced_by`; gate qoidalari — `readiness.yaml#rules`: `gate_time`, `pass_persistence`, `operational_validity`); release manifest `target_profile` ni olib yuradi (`release-policy.yaml#version_fields`).

| Capability | Profil |
|---|---|
| `llm.billable` | F1_COST_RUNTIME |
| `workflow.runtime` | F1_WORKFLOW |
| `intake.live_traffic` | F2_LIVE_INTAKE |
| `shadow.real_data` | F2_TRACKING_PASS |
| `meta.remote_test` | F3_CONTROLLED_TEST |
| `agents.run` | F4_AGENTS |
| `creative.publish` | F4_CONTENT |
| `sandbox.candidate` | FE_SANDBOX |
| `release.manifest` | FE_RELEASE |
| `write_mode.enabled`, `pipeline.rent.L1` | F6_STEP1 |
| `pipeline.sale.L1` | F6_STEP2 |
| `pipeline.any.L2` | L2_ENABLE |
| `review.pre_screen` | PRE_SCREEN |
| `release.auto` | AUTO_RELEASE_ENABLE |

- Profil statusi HUMAN_GATE o‘rnini bosmaydi: inson gate’lari alohida, revision va dalil bilan yopiladi ([PHASES §4](../05_Build_Phases/PHASES.md)).

### Faza qabuli

- Delivery lifecycle: `specified → implemented → verified_in_staging → merged → released → deployed → observed → technically_accepted → business_accepted`; terminal holatlar `rejected | inconclusive | rolled_back | cancelled | not_applicable`. Faza "accepted" = `technically_accepted` ∧ (`business_accepted` ∨ uning asosli `not_applicable`) va HG/AT/kuzatuv oynalari yopiq.
- Qabul tranzitiv: F6 kirishi = F0–F5 accepted; F5 real shadow boshlanishi = F3 va F4 accepted + HG-F2-08.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Barcha qiymatlarni spetsifikatsiyaning o‘zida yozish | uydirma raqamlar; owner dalilsiz qiymatlarga bog‘lanadi |
| Bitta kalitni bir nechta profilda takrorlash | qaysi dalil qaysi gate uchun ekani noaniq; meros buziladi |
| Builder yoki agent readiness’ni approve qiladi | muallif o‘zini tekshiradi |
| Readiness’ni faqat hujjat sifatida yuritish | runtime capability cheklanmaydi; gate qog‘ozda qoladi |
| Readiness qiymati bilan owner nazoratini almashtirish | ✅ qaror chetlab o‘tiladi |
| Statussiz qarorlar ro‘yxati | ✅ va ★/◇ farqlanmaydi; taklif jim qarorga aylanadi |

## Oqibatlar

- **+** Har noma’lum qiymatning egasi, gate’i va dalili bor; validator DAG merosi, yagona gate, rol va `not_applicable` qoidalarini tekshiradi.
- **+** Gate runtime’da majburlanadi, faqat hujjatda emas.
- **−** Inson yuki ortadi: ko‘p readiness kalitlari va imzolar (founder vaqti — `ops.founder_time_budget`, [ADR-001](ADR-001-paperclip-orchestrator.md) triggeri).
- **−** Dalil eskirsa (`max_evidence_age`) qayta tasdiq kerak.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Gate tiqilishi | critical kalit tegishli faza rejasidan keyin ham `pending` va boshqa ishni to‘xtatsa | OPEN_ITEMS readiness indeksi | owner bilan gate joylashuvi yoki dalil yo‘li ko‘riladi |
| Owner qarorlari | OD-01, OD-06 yoki P-08, P-09, P-11 bo‘yicha qaror | `owner_request` | profil DAG’i va kalitlar yangilanadi |
| Soxta PASS | validator negativ fixture’ni o‘tkazib yuborsa | `regression` | validator tuzatiladi; release bloklanadi |
| Founder yuki | `ops.founder_time_budget` 2 hafta ketma-ket oshsa | haftalik ops vaqti o‘lchovi | readiness va jarayonni soddalashtirish (owner) |

## Kanonik implementatsiya

- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `record_fields`, `rules`, `accountable_roles`, `preparers`, `profiles`, `requirements`.
- [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) — `capability_requires_profile`, `capability_enforced_by`; [release-policy.yaml](../09_Config_Templates/release-policy.yaml) — `version_fields`.
- [CONFIG_CONTRACT](../11_Production_Contracts/CONFIG_CONTRACT.md), [DECISION_LOG](../00_Decisions/DECISION_LOG.md), [OPEN_ITEMS](../00_Decisions/OPEN_ITEMS.md).
- [PHASES §2, §4](../05_Build_Phases/PHASES.md); [validate_bundle.py](../12_Acceptance/validate_bundle.py); [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-30, UAT-32.
