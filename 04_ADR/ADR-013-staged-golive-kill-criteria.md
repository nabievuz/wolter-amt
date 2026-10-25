# ADR-013 — Bosqichli go-live va kill criteria

Holat: Accepted · Qaror egasi: owner (Q22→Q36, Q31, Q37 ✅) + builder ◇ P-04, P-08, P-13 + ⧗ OD-06, OD-13 · Sana: 2026-10-22

## Kontekst

- Owner qarorlari: takeover bosqichma-bosqich — 1 hafta shadow → ijara pipeline’i AI’ga, sotuv 2 hafta targetologda → qualified CPL bo‘yicha taqqoslash → to‘liq takeover (Q22→Q36); baseline oxirgi 8 hafta, kill criteria — qualified CPL 2 hafta ketma-ket baseline’dan 25% yomon bo‘lsa boshqaruv odamga qaytadi + C05 RCA, targetolog birinchi 4 hafta ikkinchi approver (Q31); F2 da 12+ oylik tarixdan mavsumiy baseline (Q37) [D: DECISION_LOG].
- Mustaqil premortem eng katta xavf sifatida darhol to‘liq takeover’ni ko‘rsatgan: counterfactual bo‘lmaydi va AI qiymatini isbotlab bo‘lmaydi (C1); qishki mavsum oldin/keyin taqqoslashni shovqinli qiladi (C9) [D: [PREMORTEM](../00_Decisions/PREMORTEM.md)].
- Reklama byudjeti ≤ USD 1 500/oy (150 000 USD minor); bu hajmda parallel A/B sinovning statistik kuchi past [X].
- Kill criteria xavfsizlik nazorati — LLM yo‘lida bo‘lmasligi kerak (Q26).
- Haftalik metrika 14 kunlik bosqichda ikki to‘liq hafta bermasa KC-01 Step 2 dan oldin ishga tushmaydi [X].

## Qaror

1. **Baseline** (F2): oxirgi 8 hafta qualified lead, qualified CPL va lead → shartnoma pipeline bo‘yicha; 12+ oylik amoCRM tarixidan mavsumiy profil; taqqoslanishi va definition revision `business.baseline` da.
2. **Shadow (L0) — 7 kun** (F5): agentlar to‘liq ishlaydi, write SHADOW item sifatida yoziladi; targetolog odatdagidek ishlaydi.
3. **F6 Step 1 — rent L1, 14 kun**; sale targetologda qoladi. Step 1 dushanba boshlanadi; Step 2 uchun KC-01 ning ikkinchi baholashi bajarilgan bo‘lishi shart; `inconclusive` → uzaytirish yoki hold, avtomatik o‘tish yo‘q (◇ P-13).
4. **Taqqoslash:** har pipeline o‘z baseline’iga nisbatan baholanadi; diff-in-diff faqat diagnostika — parallel trend dalilisiz causal lift deb talqin qilinmaydi.
5. **To‘liq takeover** (Step 2) faqat owner ✅ bilan (HG-F6-02); keyin F7 +30 kun kuzatuv. Minimal kuzatuv zanjiri 14 + 7 + 7 + 14 + 30 = 72 kun; build va kutish vaqti qo‘shimcha.
6. **F5 go/no-go** ikki savoldan iborat: A) operatsion xavfsizlik — GO yoki NO-GO, dalil bilan; B) biznes asosi — `sufficient | inconclusive | insufficient` va exposure qarori. B `sufficient` bo‘lmasa F6 faqat rent L1, exposure doirasida; Step 2 hech qachon avtomatik emas.
7. **Kill criteria** (`kill-criteria.yaml`):
   - KC-01: `qualified_cpl_event_week` comparable baseline’dan 25% dan ko‘proq yomon, 2 ketma-ket hafta; minimal sample `business.acceptance` dan; kohorta tasdig‘i ⧗ OD-13. Baholovchi LLM emas: `sync-worker --job kill-criteria` (Du 07:30, `operations.yaml#schedule`). Oqibat avtomatik: shu pipeline `L0_shadow`, urgent alert, human handback; Funnel Analyst faqat C05 RCA yozadi.
   - KC-02: lead → shartnoma guardrail’i — `block_auto_increase` + alert; chegara `business.acceptance` da.
   - `data_status` (`valid`, `spend_zero_qualified`, `insufficient_sample`, `not_mature`, `incomparable_baseline`, `missing_data`, `stale_data`, …) bo‘yicha harakatlar `kill-criteria.yaml#data_status_actions` da. Past N yoki spend > 0 / qualified = 0 jim PASS emas: exposure soati to‘xtamaydi, scale bloklanadi, `business.exposure` chegarasida handback.
8. KC-01 dan keyin qayta ochish: pipeline C05 RCA, owner `takeover_scope_change` (HG-F6-04) va owner `pipeline_mode_change` (typed code) bo‘lmaguncha `L0_shadow` da; release qilingan entity avtomatik qayta takeover qilinmaydi ([ADR-030](ADR-030-kill-modes-and-protective-controls.md)).
9. **Targetolog:** F5 da `viewer` + baholovchi; F6 Step 1 dan 4 hafta `ads_approver` (expiry Step1 + 28 kun), Step1 + 21 kunda rotatsiya qarori HG-F6-05 (◇ P-17), keyin owner qarori.
10. **Takeover obyektlari** har bosqichdan oldin owner tasdiqlaydi va `managed_entities` ga `origin=takeover` bilan yoziladi (HG-F6-04).
11. `inconclusive` natija "toza" ham, muvaffaqiyat ham emas — Trust Ramp va takeover uchun sanalmaydi (◇ P-04). Iqtisodiy readiness (`business.*`) F5_GO da talab qilinadi (◇ P-08); ⧗ OD-06 uni F6_STEP2 yoki F7 monitoringiga ko‘chirishi mumkin.
12. Qo‘shimcha himoyalar: provider spending limit ([ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)); tracking 2 ketma-ket fail kuni → `read_only`; kill switch (ADR-030).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Darhol to‘liq takeover (Q22 dastlabki varianti) | counterfactual yo‘q (premortem C1); owner Q36 bilan bosqichli yo‘lni tanlagan |
| Parallel 30% byudjet bilan sinov | 150 000 USD minor/oyda statistik kuch past (premortem C3) |
| Kill criteria’ni Analyst agenti baholaydi | xavfsizlik nazorati LLM yo‘lida bo‘ladi (Q26) |
| `inconclusive` ni toza natija deb sanash | Trust Ramp va takeover isbotsiz kengayadi |
| Step 2 ga 14 kun o‘tishi bilan avtomatik o‘tish | ikkinchi KC-01 baholashisiz xavf ko‘rinmaydi (◇ P-13) |

## Oqibatlar

- **+** AI qiymati dalil bilan baholanadi; xavf bitta pipeline bilan cheklanadi; orqaga qaytish rejasi oldindan yozilgan.
- **−** To‘liq takeover kamida 3 hafta kechikadi; kuzatuv zanjiri 72 kun.
- **−** Ijarada park sig‘imi cheklovi bor: CPL taqqoslashi bandlik bilan birga o‘qiladi ([ADR-014](ADR-014-capacity-aware-rent-objective.md)).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Kill criteria ishga tushishi | KC-01 trigger | `kill_criteria` job | C05 RCA → WF-E01; strategiya qayta ko‘riladi |
| Owner takeover’ni to‘xtatishi | owner qarori | `owner_request` | bosqichlar qayta rejalanadi |
| Mavsumiy baseline yetarli emas | 12 oylik tarix yo‘q yoki `incomparable_baseline` | `business.baseline` | baseline usuli yangilanadi (owner) |
| Eksperimentlar natija bermasligi | 3 ta ketma-ket eksperiment `inconclusive` | experiment ledger, `command_outcomes` | eksperimentlar soni va qamrovi qisqartiriladi |

## Kanonik implementatsiya

- [F5_Eval_Shadow](../05_Build_Phases/F5_Eval_Shadow.md), [F6_GoLive](../05_Build_Phases/F6_GoLive.md), [F7_Retro](../05_Build_Phases/F7_Retro.md), [PHASES](../05_Build_Phases/PHASES.md).
- [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml), [business-policy.yaml](../09_Config_Templates/business-policy.yaml), [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) — `resume.after_kill_criteria`.
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `business.baseline`, `business.acceptance`, `business.exposure`, `business.step1_comparison`.
- [BUSINESS_CONTRACT §8, §11](../11_Production_Contracts/BUSINESS_CONTRACT.md); [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I15, I23; [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) UAT-06, UAT-07.
