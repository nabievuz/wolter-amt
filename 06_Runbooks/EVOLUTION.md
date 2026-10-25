# RUNBOOK — Evolution siklini yuritish

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Kontrakt: [EVOLUTION_CONTRACT](../11_Production_Contracts/EVOLUTION_CONTRACT.md), [evolution-policy.yaml](../09_Config_Templates/evolution-policy.yaml). Workflow’lar: WF-E01 (umumiy upgrade), WF-E02 (harness/workflow), WF-E03 (dependency/model/adapter), WF-E04 (prompt/skill/bilim). Release tartibi: [UPGRADE](UPGRADE.md). Qamrov Q50 ✅; Q11 ✅ saqlanadi — production o‘zgarishi faqat owner tasdig‘i bilan. Qaror egasi — owner.

## Haftalik ritm

Vaqtlar [operations.yaml](../09_Config_Templates/operations.yaml) `schedule`dan; bu yerda faqat evolution’ga tegishli qatorlar.

| Vaqt (`schedule.id`) | Kim | Nima |
|---|---|---|
| Doimiy | `amt-workflow` | signal intake va dedup (`problem_fingerprint`); ochiq proposal takroriy signalni o‘ziga oladi; qayta ochish faqat yangi dalil bilan; agent signallari `evo.signal.submit` orqali (ichki, audit, PII’siz) |
| Chorshanba 15:00 (`dependency_check`) | WF-E03 | `VERSIONS.lock.md` va rasmiy advisory tekshiruvi |
| Juma 16:00 (`cmo_status`) | cmo → ops-bot | ochiq proposal’lar, kutilayotgan qarorlar, engineering sarfi (alohida hisob) |
| Oyning 1-kuni (`retro`, C12) | cmo + funnel-analyst, eng-planner | retro saboqlari → signal; qabul qilingan saboqlar → WF-E04 |

Release oynasi: 14:00–18:00 Asia/Tashkent, dushanba emas ★ (`upgrade_window`), operator qamrovi va owner mavjudligi bilan; oyna davomida `maintenance_hold` ([UPGRADE §2](UPGRADE.md)). Favqulodda security holatida ham qamrov va dalil saqlanadi.

## Owner qarorlari

1. **Proposal** (WF-E01 S03; `upgrade_proposal_approval`, `/proposal approve <proposal_id>`): scope, `allowed_paths`, o‘zgarish sinfi (A–E), pul/vaqt limiti, acceptance plan va kuzatuv rejasi o‘qiladi. Pullik engineering ⧗ OD-02 hal bo‘lguncha o‘chiq (`engineering-budget.yaml` `paid_engineering_enabled: false`): owner yoki builder ishni qo‘lda, xuddi shu sandbox, verification va release yo‘lida bajaradi. Engineering xarajati runtime USD 150/oy (15 000 USD minor) va reklama cap’laridan alohida (I25).
2. **Release** (WF-E01 S07; `upgrade_release`, HG-REL-01): verification ID, verdict, eng-verifier hisoboti va manifest digest. Owner `/release approve <candidate_id>` (typed code) `release_approvals` yozuvini yaratadi va aynan shu manifest commit’iga owner imzolagan `release-*` tag qo‘yadi; merge (HG-GIT-01) fast-forward yoki tree-hash tengligi bilan. Global rejim `killed` bo‘lsa faqat `release_class: recovery`.
3. **Himoyalangan sirt** (E sinfi; `protected_surface_change`): typed code + mustaqil inson review (⧗ OD-12) + owner. Release controller, kill/control, policy’lar, budget/cap, RBAC, verification suite/holdout, INVARIANTS va DECISION_LOG shu sinfga kiradi.
4. **Handover** (WF-E02 S03; `harness_handover`): inventar va har run disposition’i; owner mavjud bo‘lmagan vaqtda handover boshlanmaydi.
5. **Verdict** (WF-E01 S10): `accepted | rejected | inconclusive`; inconclusive avtonomiya yoki rollout’ni kengaytirmaydi; xotira yozuvi qaror egasi bilan.

Auto-release o‘chiq; uni yoqish Q11 ni o‘zgartiruvchi yangi owner Q (⧗ OD-03) va AUTO_RELEASE_ENABLE profilini talab qiladi.

## To‘xtatish

- Engineering byudjeti yoki resurs limiti: yangi engineering ishi to‘xtaydi yoki navbatga; production ta’sirlanmaydi ([INCIDENTS](INCIDENTS.md) INC-22).
- Verification `fail` yoki `criteria_changes_detected`: candidate rad; mezonni o‘zgartirish faqat alohida E sinfi proposal (INC-23).
- Kuzatuvda guardrail buzildi: hold, oldingi release yoki sinalgan repair/restore; remote effektlar compensation command bilan; incident (WF-O02).
- Kill: global rejim `killed` bo‘lsa faqat `release_class: recovery` release (containment, reconciliation yoki oldin tekshirilgan release’ni tiklash) o‘tadi, `normal` release rad etiladi; release tasdig‘i `control_epoch`ga bog‘langan, epoch o‘zgarsa qayta tasdiq kerak.
- Shubhali holdout sizishi: kalit rotatsiyasi, yangi holdout, E sinfi incident.

## Dalil

Lifecycle milestone’lari alohida dalil bilan: `specified → implemented → verified_in_staging → merged → released → deployed → observed → technically_accepted → business_accepted`; terminal `rejected | inconclusive | rolled_back | cancelled | not_applicable`. Kuzatuv oynasi va stop qoidalari `release.scope_observation` va `evolution.outcome_policy`da; `observed` biznes qabul emas.

Har yopilgan proposal uchun improvement memory yozuvi: source, revision, diff, test, haqiqiy xarajat, rollout, kuzatilgan natija, verdict, qaror egasi. Faqat `accepted` + `guidance_eligible` saboq WF-E04 bilan agentlarga yetadi.
