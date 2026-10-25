# FE — Evolution qatlami: sandbox, mustaqil verification va himoyalangan release

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

## Maqsad va boshlash sharti

FE F1 accepted bo‘lgach boshlanadi: FE_SANDBOX profili F1_ISOLATION va F1_WORKFLOW ni talab qiladi (managed runner, workflow runtime va root publisher F1’da tayyor). FE F2–F4 bilan parallel quriladi; Q67 bo‘yicha sandbox, mustaqil verification va himoyalangan release qatlami F5 formal eval hamda real shadow’dan **oldin** deployed va dalilli tayyor bo‘lishi shart. Natija: tizim o‘z upgrade’ini dalil bilan taklif qiladi, alohida sandbox’da tayyorlaydi, candidate’dan mustaqil verification bilan tekshiradi va faqat owner release’i bilan chiqaradi (Q11 ✅, Q50 ✅ qamrov; [EVOLUTION_CONTRACT](../11_Production_Contracts/EVOLUTION_CONTRACT.md), [SELF_EVOLUTION](../03_Architecture/SELF_EVOLUTION.md)).

Ichki tartib: workflow kontraktlari va durable runtime (F1) → engineering sandbox va mustaqil verification → himoyalangan release va harness handover → biznes workflow’lari bilan integratsiya va haqiqiy kuzatuv (F5–F7). Bu bitta to‘liq qabulning ichki ketma-ketligi; bosqichlash qamrovni qisqartirmaydi.

## Lifecycle va gate’lar

FE [PHASES §2.1](PHASES.md) dagi yagona lifecycle lug‘atini yuritadi (`build/FE/STATUS.md`):

| Milestone | Shart |
|---|---|
| `verified_in_staging` | FE-AT-01…15 isolated/staging’da `pass`; HG-FE-04 drill guvohligi. **birinchi F5 formal eval va real shadow’dan oldin** (Q67), FE_SANDBOX/FE_RELEASE PASS, deployed qatlam va HG-FE-01…05 bilan; Q66 exact baseline mustaqil texnik inson signoff’i FE_RELEASE’dan oldin |
| `merged`, `released`, `deployed` | owner merge (HG-GIT-01); release controller kengaytmasi F1 root publisher orqali owner imzolagan tag bilan chiqadi (HG-REL-01) va servis ACK’lari bilan faollashadi. Shundan boshlab har AMT host release `release_approvals` va manifest bog‘lanishi bilan |
| `observed` | haqiqiy release’lar manifest yo‘lidan o‘tgani dalillangan |
| `technically_accepted` | **F6 Step 1 dan keyingi production kuzatuv qabuli** (FE qatlamining deployment/readiness/drill yoki Q66 human signoff’ini bu vaqtgacha surishga ruxsat bermaydi): builder sudo’siz (HG-F6-06) va kamida bitta haqiqiy AMT host release sandbox → verification → `release_approvals` + imzolangan tag yo‘lidan o‘tgan; HG-FE-01…05 yopiq |
| `business_accepted` | **F7 da** EVO-AT14 `pass` ([F7_Retro](F7_Retro.md)) |

F4da offline synthetic fixture va harness kodi tayyorlanishi mumkin; F4 acceptance smoke o‘z gate/cap’larida qoladi. Ular FE kirish sharti yopilmaguncha F5 formal model/adapter eval dalili yoki shadow kuni hisoblanmaydi. Q66 dastlabki AI + owner review davri `evolution-policy.yaml#initial_build_review` bo‘yicha exact baseline human signoff’i bilan tugaydi; Q67 FE_RELEASE’ni F5dan oldinga qo‘ygani sabab bu signoff ham F5 formal evaldan oldin. Keyingi engineering E o‘zgarishlari har doim mustaqil inson review’idan o‘tadi.

FE_RELEASE dan oldin AMT host code release’lari F1 publisher, `release_approvals` yozuvi (verification maydonlari hali bo‘sh) va owner imzolagan `release-*` tag (HG-REL-01) bilan chiqadi; FE yozuvni verification natijasiga bog‘laydi va `build_once_promote` ni majburiy qiladi.

## Qurish tartibi

1. **Identity va UID’lar.** `amt-sandbox`, `eng-build` (sandbox transient build UID’i — builder’ning F0 dagi `amt-build` foydalanuvchisidan alohida), `amt-verify`, `amt-release` (root egaligidagi publish entrypoint va `amt_release` DB roli), `amt-eng-proxy`, `agent-eng-planner`, `agent-eng-architect`, `agent-eng-implementer`, `agent-eng-verifier`. Engineering rollari biznes agentlari emas: alohida `runtime-isolation.yaml` `engineering_roles` reyestri, faqat sandbox vakolati (I01, I20). Managed runner mapping’iga ular qo‘shiladi; caller UID yoki entrypoint tanlay olmaydi. Biznes agentlarining allowlist’i va terminal/egress cheklovlari o‘zgarmaydi. Engineering egress’i default-deny network namespace’da, faqat package proxy; engineering credentiali faqat `cand/*` branch’larga push qiladi.
2. **Resurs slice’lari.** `control > production > sandbox` systemd slice’lari ([resource-policy.yaml](../09_Config_Templates/resource-policy.yaml)); `capacity.sandbox_host` o‘lchovi uchun yuklama testi (build + verification + odatiy runtime + DB). Production zaxirasi tasdiqlanmaguncha sandbox build’lari faqat isolated test hostida; alohida build host — owner pul qarori (HG-FE-03).
3. **Sandbox.** Worktree boshqaruvi, transient unit, nftables UID egress qoidasi (faqat package proxy), lockfile majburiyati, artifact va candidate manifest yaratish.
4. **Verification.** Har doim **joriy release’dagi** `evals/protected/**` suite’lari, shifrlangan holdout va `amt-verify` kaliti (`verification.custody`); verification result yozuvi exact manifest va evaluator revision’iga bog‘langan; himoyalangan yo‘l diff detektori; mavjud regression, invariant, security va eval suite’lari (UAT, EVO-AT, EVALS) shu harness’ga ulanadi. Muallif rollari holdout’ni o‘qiy olmaydi; class E o‘zgarishi mustaqil inson review’ini talab qiladi (`engineering.independent_reviewer`, ⧗ OD-12).
5. **Release controller.** F1 root publisher ustida `requested → validated → prepared → activated → acked → observing → closed` (xato yo‘llari `refused`, `rolled_back`). Bog‘lanish: owner `release_approvals` yozuvi (`/release approve <candidate_id>`, typed code, `upgrade_release`; manifest digest, verification ID, verdict, evaluator/policy/role revision, control epoch, approver, nonce hash, `approved_at`, `expires_at`) **va** owner imzolagan annotated `release-*` tag (HG-REL-01). **`build_once_promote`:** artefaktlar sandbox’da bir marta quriladi, digest’lari candidate manifest’da, verification shu digest’larda, publisher aynan shularni chiqaradi; merge fast-forward yoki rebase va tree-hash tengligi bilan, aks holda yangi manifest va qayta verification. Release sinflari: global `killed` da `normal` rad, faqat `recovery` (`release-policy.yaml` `release_classes`). Doira faqat AMT host: landing/Umami — WF-B04 PR, owner merge va Dokploy deploy (Q46.4 ✅); `amt-release`da Dokploy yoki landing credentiali yo‘q.
6. **Harness handover.** WF-E02: inventar, disposition, drain, epoch, state migration, handover, reconciliation; release controller’ning o‘z yangilanishini amaldagi controller chiqaradi va qo‘lda root tiklash yo‘li bor. Eski workflow definition’lari ularning run’lari tugaguncha bundle’da yuklanadigan qoladi; yangi definition bilan mos kelmaydigan run WF-E02 disposition qarorigacha `frozen` holatida turadi va yangi qadam boshlamaydi.
7. **Engineering byudjeti.** `budget_accounts(scope=engineering)` va `amt-eng-proxy` reservation/settlement. Engineering hisobi runtime AI cap’idan (USD 150/oy, 15 000 USD minor) va reklama cap’idan (USD 1 500/oy, 150 000 USD minor) alohida; runtime OpenRouter kaliti ishlatilmaydi. `engineering.budget` va `engineering.llm_access` tasdiqlanmaguncha pullik engineering o‘chiq (`paid_engineering_enabled: false`, ⧗ OD-02) va ish qo‘lda, lekin xuddi shu sandbox → verification → release yo‘li bilan.
8. **Yaxshilanish xotirasi va owner ko‘rinishi.** `improvement_memory` jadvali (faqat `accepted` + `guidance_eligible` yozuv ko‘rsatmaga, WF-E04 orqali), sanitizatsiyalangan view, `v_owner_queue` da evolution navbati; ops-bot `/work` (besh savol) va `/decisions`.
9. **Workflow’lar.** WF-E01…E04 definition’lari publish qilinadi; har biri uchun WF-TEST-E0x-* testlari ([WORKFLOW_TESTS](../12_Acceptance/WORKFLOW_TESTS.md)).

## Deliverables

`services/{sandbox,verify,release-controller,eng-proxy}`, slice va nftables konfiguratsiyasi, managed runner mapping kengaytmasi, `evals/protected/` va holdout custody hujjati, release controller va handover runbook bo‘limlari ([UPGRADE](../06_Runbooks/UPGRADE.md), [EVOLUTION](../06_Runbooks/EVOLUTION.md), [RUN_RESUME](../06_Runbooks/RUN_RESUME.md)), `build/FE/{PLAN,EVIDENCE,REPORT,STATUS}.md`.

## Acceptance tests

| ID | Nima | Usul | Kutilgan |
|---|---|---|---|
| FE-AT-01 | Sandbox UID izolyatsiyasi | har engineering UID boshqa workspace, production secret, `/opt/wolter-amt`, Docker socket va himoyalangan yo‘lga yozishga; biznes gateway tool’ini chaqirishga urinadi | hammasi rad va auditda |
| FE-AT-02 | Build egress | zararli install/build hook Meta, amoCRM, OpenRouter va ixtiyoriy hostga chiqishga urinadi | faqat package proxy ishlaydi; urinish auditda (EVO-AT04) |
| FE-AT-03 | Resurs bosimi | parallel build va verification limitdan oshadi | sandbox pauza/navbat; intake, kill, accounting va ops-bot javobi konvert ichida (EVO-AT05) |
| FE-AT-04 | Mezonni yumshatish | candidate himoyalangan testni o‘chiradi yoki chegarani pasaytiradi | verdict `fail`, `criteria_changes_detected` to‘ldirilgan (EVO-AT03) |
| FE-AT-05 | Holdout custody | planner/implementer/builder holdout’ni o‘qishga urinadi | rad; verification result suite/holdout digest’iga bog‘langan |
| FE-AT-06 | Manifest drift | verification’dan keyin artifact yoki config almashtiriladi; squash merge tree-hash’ni o‘zgartiradi | release `refused`; yangi manifest va qayta verification talab qilinadi (EVO-AT08) |
| FE-AT-07 | Approval binding | approval’dan keyin rol revoke, policy o‘zgarishi, approval muddati o‘tishi yoki boshqa manifest digest | release rad (`release_approvals` binding); yangi approval |
| FE-AT-08 | Publisher mustaqilligi va doirasi | candidate release-policy yoki release controller’ni E sinfisiz o‘zgartiradi; `release-*` tag yaratishga yoki imzosiz tag bilan release qilishga urinadi; `amt-release` credential’larida Dokploy/landing kaliti qidiriladi | o‘zgarish va release rad (EVO-AT03); Dokploy/landing credentiali yo‘q |
| FE-AT-09 | Handover drill | WF-E02 to‘liq; eski controller qaytadi | yagona dispatch; eski epoch rad; inventar to‘liq hisobga olingan (EVO-AT06) |
| FE-AT-10 | Migratsiya paytida trafik | migration/rollback paytida submit, consent withdrawal va webhook keladi | custody, outbox, billing va audit saqlanadi; remote reconciliation (EVO-AT07); workflow ledger RPO/RTO o‘lchangan (`workflow.recovery`) |
| FE-AT-11 | Yashirin regression | model/prompt o‘zgarishi holdout’da yomonlashadi | promotion blok (EVO-AT11) |
| FE-AT-12 | Engineering byudjeti | byudjet yo‘q; keyin limit tugaydi | LLM engineering rollari o‘chiq; tugaganda stop/navbat; runtime ta’sirlanmaydi, runtime kaliti ishlatilmaydi (EVO-AT05) |
| FE-AT-13 | Vazifalar ajratilishi | muallif verification result yozishga yoki release so‘rashga urinadi | rad va auditda |
| FE-AT-14 | Xotira | rejected/inconclusive yozuvdan guidance yaratish; accepted saboqni revoke qilish | birinchisi rad; revoke saboqni keyingi bundle’dan olib tashlaydi |
| FE-AT-15 | Owner ko‘rinishi | ochiq proposal, kutilayotgan qaror va xarajat | `/work` besh savoli, blocker va deadline ko‘rinadi; `/decisions` faqat owner qarorlari |
| FE-AT-16 | Saboq va golden copy hajmi | isolated: `guidance_eligible: true` va `lesson: null` (yoki `verdict: inconclusive`, 600 belgidan uzun `lesson`, `scope`/`review_by` yo‘q) bilan improvement_memory yozuvi; 20 ta aktiv saboqli rol; 10 ta golden copy namunali pipeline × format | sxema hamma noto‘g‘ri yozuvni rad etadi; prompt’ga eng yangisi birinchi, ko‘pi bilan 15 ta va ≤ 2 000 token saboq kiradi, qolganlari faqat ID bilan; golden copy ≤ 6 ta; birinchi turn `input_tokens` `max_fixed_tokens`dan oshmaydi (◇ P-91) |

## HUMAN_GATE

| HG | Owner nima qiladi | Qaytariladigan narsa | Bloklaydi |
|---|---|---|---|
| HG-FE-01 | Engineering LLM kirishi va byudjetini tanlash (`engineering.llm_access`, `engineering.budget`) yoki manual rejimni sabab bilan `not_applicable` deb tasdiqlash (⧗ OD-02) | imzolangan readiness revision | FE_SANDBOX (pullik engineering) |
| HG-FE-02 | Holdout va kalit custody’si (`verification.custody`), Q66 exact baseline mustaqil texnik inson signoff’i; engineering E uchun faol independent reviewer person_ref (`engineering.independent_reviewer`, ⧗ OD-12 shaxs) | custody attestatsiyasi, baseline manifest signoff’i, reviewer person_ref | FE_RELEASE; F5 formal eval/shadow boshlanishi (Q67) |
| HG-FE-03 | Sig‘im o‘lchovi va production zaxirasini tasdiqlash yoki alohida build host buyurtmasi (pul) (`capacity.sandbox_host`) | o‘lchov hisoboti, qaror | FE_SANDBOX, sandbox build’lari |
| HG-FE-04 | FE-AT-04/06/08/09/10 drill’lariga guvoh bo‘lish (workflow.recovery), deployed sandbox/verification/release zanjiri dalili | ✅ | FE `verified_in_staging` + FE_RELEASE → birinchi F5 formal eval hamda real shadow (Q67) |
| HG-FE-05 | `evolution.outcome_policy` va `release.scope_observation` (standart — owner release) ni tasdiqlash | imzolangan readiness revision | FE_RELEASE |

## Rollback

Sandbox, verification va release controller o‘zgarishlari E sinfi; muvaffaqiyatsizlikda oldingi immutable release va qo‘lda root tiklash yo‘li ([UPGRADE](../06_Runbooks/UPGRADE.md)). FE ishlamay qolsa production runtime ta’sirlanmaydi; yangi release faqat `release_approvals` yozuvi va owner imzolagan tag bilan, `recovery` sinfida (`release-policy.yaml#release_classes`) chiqariladi; tag’ning o‘zi bilan release yo‘q. Global `killed` da faqat `recovery` sinfidagi release.

## Riskler (RSK-03)

| Risk | Erta signal | Chora |
|---|---|---|
| Bitta hostda build yuklamasi production’ni sekinlashtiradi | ops-bot/intake latency, slice bosimi | cgroup ustuvorligi, pauza/navbat, alohida host qarori (HG-FE-03) |
| Holdout sizishi | holdout kalitiga g‘ayrioddiy kirish, natijalar keskin yaxshilanishi | kalit rotatsiyasi, yangi holdout, E sinfi insidenti |
| Engineering obunasi yoki limiti to‘xtaydi | eng-proxy xatolari | manual rejim; runtime ta’sirlanmaydi |
| Handover paytida owner yo‘q | drain uzoq davom etadi | handover faqat owner mavjudligida boshlanadi; drained holat xavfsiz |
| Sinalgan va chiqarilgan artefakt farq qiladi | tree-hash yoki digest nomosligi | `build_once_promote`; nomoslikda `refused` (FE-AT-06) |
