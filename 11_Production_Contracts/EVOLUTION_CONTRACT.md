# Evolution kontrakti — inson boshqaradigan o‘zini yaxshilash

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23 · Vaqt: Asia/Tashkent.

AMT butun loyihani kuzatadi, yaxshilash zaruratini dalil bilan aniqlaydi, alohida nusxada yangi variant tayyorlaydi, uni mustaqil tekshirtiradi va **berilgan vakolat doirasida** ishga chiqaradi. Standart vakolat: merge va release — owner. Bu hujjat [INVARIANTS](INVARIANTS.md) I19–I25 ning batafsil shakli; ish birligi [WORKFLOW_CONTRACT](WORKFLOW_CONTRACT.md) dagi WF-E01…E04. Texnik dizayn: [SELF_EVOLUTION](../03_Architecture/SELF_EVOLUTION.md). Policy: [evolution-policy.yaml](../09_Config_Templates/evolution-policy.yaml), [engineering-budget.yaml](../09_Config_Templates/engineering-budget.yaml), [resource-policy.yaml](../09_Config_Templates/resource-policy.yaml), [release-policy.yaml](../09_Config_Templates/release-policy.yaml).

Bu kontrakt yangi release, auto-release, server, xarajat yoki production amaliga avtomatik ruxsat bermaydi. Owner qarori ✅ Q11 (“ishga tushgandan keyin tizim o‘zini faqat PR + owner tasdig‘i bilan o‘zgartiradi”) to‘liq amal qiladi. Evolution qatlami owner ko‘rsatmasi bilan kanonik qamrovda (✅ Q50); FE_RELEASE joylashuvi Q67 bilan yopilgan: qatlam F5 formal eval va shadow boshlanishidan oldin tayyor, exact baseline Q66 bo‘yicha mustaqil texnik inson tekshiruvidan o‘tadi. Engineering byudjeti va LLM kirishi ⧗ OD-02, auto-release ⧗ OD-03, mustaqil insonni tayinlash ⧗ OD-12 da ochiq.

## 1. Sikl

**Signal → triage → upgrade proposal → qabul mezoni va dizayn → alohida nusxada implementatsiya → mustaqil verification → release qarori → chiqarish → kuzatuv → accepted/rejected/inconclusive → saboq va backlog.**

Signal manbalari (`evolution-policy.yaml#signal_sources`): incident AAR (WF-O02), owner talabi, regression, xarajat yoki tezlik og‘ishi, vendor/dependency o‘zgarishi yoki advisory, oylik C12 retro va F7, eval drift, biznes agentlarining `evo.signal.submit` signali (ichki, audit qilinadi, PII’siz; CMO kod yoki skill PR ochmaydi). Takroriy signal `problem_fingerprint` bo‘yicha ochiq proposal’ga biriktiriladi; yangi dalilsiz qayta ochish yo‘q — bitta muammo cheksiz development loop yaratmaydi. Parallel candidate va step urinishlari `engineering-budget.yaml` (`max_parallel_candidates`, `max_attempts_per_step`) bilan cheklanadi. Sikl natijani o‘lchashgacha davom etadi; WF-E01 faqat verdict (`accepted`, `rejected`, `inconclusive`) va yaxshilanish xotirasi yozuvi bilan yopiladi; kod yozilgani yoki merge bo‘lgani yakun emas.

## 2. Modul va interface mas’uliyati

| Modul | Interface vazifasi | Ichida hal qilinadigan ish |
|---|---|---|
| Workflow Runtime (`amt-workflow`) | Definition revision’iga pin qilingan ishni boshlash, signal berish, holatini olish va bekor qilish | Durable run/step, timer, handoff, retry, correlation, epoch va recovery |
| Engineering Sandbox (`amt-sandbox`) | Tasdiqlangan proposal bo‘yicha candidate tayyorlash | Branch/worktree, cheklangan build/test, resurs va egress chegarasi |
| Independent Verification (`amt-verify`) | Exact manifest uchun evidence va verdict | Himoyalangan regression/holdout, security, invariant va runtime sinovlari |
| Release Controller (`amt-release`) | Vakolatli exact candidate’ni chiqarish yoki tiklash — faqat AMT host’da | Approval tekshiruvi, immutable publish, schema compatibility, ACK, handover va kuzatuv |

Release Controller doirasi — faqat AMT host release’lari (`release-policy.yaml#scope`). Landing va Umami o‘zgarishlari WF-B04 bo‘yicha: AMT PR ochadi, owner production Dokploy’da merge va deploy qiladi (✅ Q46.4), AMT chop etilgan snapshot’ni read-only tekshiradi; `amt-release` da Dokploy yoki landing credential’i yo‘q (`release_controller_holds_dokploy_or_landing_credentials: false`). Agent root terminal yoki ixtiyoriy publisher buyrug‘ini olmaydi. Engineering agentiga faqat sandbox ichidagi aniq vakolat beriladi; biznes agentlari uchun amaldagi terminal/egress cheklovlari o‘zgarmaydi.

## 3. Upgrade proposal

Har proposal [upgrade-proposal.schema.json](../09_Config_Templates/schemas/upgrade-proposal.schema.json) bo‘yicha: boshlang‘ich `release_id`, muammo dalili va signal reference’lari, ta’sir doirasi, ruxsatli fayl/modullar, kutilgan natija, qabul asosi (`business`, `technical_no_harm`, `both`), risk, pul/vaqt/urinish chegarasi, testlar, migration turi, kuzatuv (scope, oyna, guardrail, stop rule) va recovery rejasi. Proposal revision’i immutable; tahrir yangi revision va oldingi approval’ni bekor qiladi.

## 4. O‘zgarish sinflari va gate’lar

| Sinf | Qamrov | Majburiy gate |
|---|---|---|
| A — kontent | hujjat, prompt, skill, bilim, golden copy kutubxonasi | mustaqil verification + owner release |
| B — kod | himoyalanmagan servis kodi | mustaqil verification + owner merge/release |
| C — workflow/harness | workflow definition, `amt-workflow`, orkestratsiya adapteri, managed runner mapping | B + WF-E02 handover rejasi va owner tasdig‘i |
| D — schema/migration | DB va workflow state migration | B + migration drill (restore/forward repair) dalili |
| E — himoyalangan sirt | `evolution-policy.yaml#protected_surfaces`: release controller, verifier suite/holdout/evaluator, approval/evolution/execution/release/workflow policy, kill/control, runtime-isolation, budgets va engineering-budget, resource-policy, RBAC (roles), kill-criteria, operations (protective controls va jadval), readiness qoidalari va profillari, owner qarorini olib yuruvchi config’lar (tracking-health, pipelines, business-policy, capacity-policy, privacy-policy, sale-readiness, environments), sirlar va permission, INVARIANTS, WORKFLOW_CONTRACT, EVOLUTION_CONTRACT, DECISION_LOG, validator va himoyalangan fixture’lar | B + mustaqil inson review (`engineering.independent_reviewer`, ⧗ OD-12) + owner typed tasdig‘i (`protected_surface_change`) |

Kod, agent, prompt/skill, workflow, adapter, schema, test va infratuzilma konfiguratsiyasi proposal doirasiga kira oladi. Har config shabloni yo himoyalangan sirt (E sinfi), yo `engineering_may_not_change` ro‘yxatida (`offers.yaml` — faqat WF-B04 orqali); config o‘zgarishi hech qachon A yoki B sinfi emas (`config_coverage_rule`). Owner qarorini (Q-ID) o‘zgartiradigan qiymat avval yangi owner Q talab qiladi. Bu ularni tizim o‘zi tasdiqlab chiqaradi degani emas. Himoya kodini yangilash mumkin, lekin candidate amaldagi himoyani o‘zi chetlab o‘tmaydi: E sinfi o‘zgarishi eski (amaldagi) himoyalangan suite va publisher bilan tekshiriladi.

## 5. Engineering rollari va vazifalar ajratilishi

| Rol | Bajaradi | Bajarmaydi |
|---|---|---|
| `eng-planner` (triage/planner) | signal triage, proposal qoralamasi, backlog | kod yozish, verification, merge, release, holdout o‘qish |
| `eng-architect` | dizayn, qabul mezoni, test rejasi, WF-E02 disposition rejasi | o‘z dizayniga PASS, merge, release |
| `eng-implementer` | faqat biriktirilgan sandbox branch’ida o‘zgarish va ochiq testlar | holdout o‘qish, himoyalangan suite’ni E sinfisiz o‘zgartirish, merge, release, production kirish |
| `eng-verifier` | `amt-verify` orqali himoyalangan suite/holdout, review hisoboti | candidate’ni o‘zgartirish, merge, release, production write |
| `amt-release` (deterministik) | owner tasdiqlagan exact manifest’ni publish/rollback, handover | qaror qabul qilish, manifest’ni o‘zgartirish |
| `owner` | proposal, merge, release, handover va E sinfi qarorlari | — |

Muallif o‘ziga mustaqil PASS yoki release vakolati bermaydi. Rollar uchun credential, workspace va tool matritsasi hamda salbiy ruxsat testlari [SELF_EVOLUTION §3](../03_Architecture/SELF_EVOLUTION.md) da. Engineering identity biznes agentlarining Meta/CRM/approval vakolatini kengaytirmaydi.

## 6. Izolyatsiyalangan sandbox

Har upgrade alohida branch/worktree’da va cheklangan build muhitida: alohida unprivileged UID, production secret/DB/Meta/CRM write yo‘q, root va Docker socket yo‘q, package registry’ga faqat pinned lockfile va proxy allowlist orqali chiqish, yagona credential — `ENG_GITHUB_TOKEN` (`sandbox.env`, faqat `cand/*` branch’lariga push; `environments.yaml#environments.sandbox`), CPU/RAM/disk/IO/vaqt limiti ([resource-policy.yaml](../09_Config_Templates/resource-policy.yaml)). Zararli build hook, secret o‘qish yoki live egress urinishi bloklanadi va auditga yoziladi (EVO-AT04).

## 7. Manifest va revision xaritasi

Code commit, workflow definition digest’lari, prompt, skill, model/provider, adapter, config, schema, dependency lock va evaluator suite/holdout digest’i bitta immutable manifestga bog‘lanadi ([candidate-manifest.schema.json](../09_Config_Templates/schemas/candidate-manifest.schema.json)). Manifest ta’sirlangan test, invariant va run’larni sanaydi. Verification, approval va release faqat manifest digest’iga tegishli: sinov yoki tasdiqdan keyin artifact almashtirilsa dalil va approval yaroqsiz (EVO-AT08). Eski run yangi definition’ni jim yuklamaydi.

## 8. Mustaqil verification

Suite: regression, kontrakt, security, invariant, migration, tegishli nazoratli real integratsiya (PAUSED test entity, activation simulyatsiyasi) va yashirin holdout. Natija [verification-result.schema.json](../09_Config_Templates/schemas/verification-result.schema.json) bo‘yicha exact manifest va evaluator revision’iga bog‘lanadi. Holdout va evaluator konfiguratsiyasi muallif rollari o‘qiy olmaydigan custody’da (`verification.custody`). Candidate authoritative mezonni o‘zi yumshata olmaydi: test o‘chirilishi, chegara pasaytirilishi yoki evaluator o‘zgarishi aniqlansa verdict `fail`; bunday o‘zgarish faqat alohida E sinfi proposal, mustaqil review va owner gate’i bilan (EVO-AT03).

## 9. Promotion vakolati

| Daraja | Siyosat |
|---|---|
| Standart | Tizim upgrade’ni aniqlaydi, rejalaydi, yozadi va tekshirtiradi; merge — owner (HG-GIT-01); release — owner `release_approvals` yozuvi (ops-bot `/release approve <candidate_id>`, typed code, `upgrade_release`, HG-REL-01) va owner imzolagan annotated `release-*` tag (`release-policy.yaml#tag_ruleset`) |
| Kelajakdagi tor auto-release | `evolution-policy.yaml#promotion.auto_release.enabled: false`, `decision_ref: OD-03` (⧗). Yoqish uchun: Q11 ni o‘zgartiruvchi yangi owner qarori (readiness `auto_release.decision_ref`), `release.scope_observation`, `AUTO_RELEASE_ENABLE` profili, FE fazasi `technically_accepted` va EVO-AT14 PASS. Siyosat aniq toifa, fayl/ta’sir doirasi, risk, xarajat, TTL, recovery va mustaqil dalil shartlarini belgilaydi |
| Har doim alohida inson gate’i | pul limitlari, sirlar va permission, himoyalangan verifier/publisher/kill, destructive migration va auto-release siyosatining o‘zi |

Approval exact manifest digest, verification ID va verdict, proposal revision, evaluator, amaldagi rol va policy revision’lari hamda control epoch’ga bog‘lanadi (`release-policy.yaml#release_approval.bound_to`; `evolution-policy.yaml#gates.upgrade_release.binds_ref` shu ro‘yxatga havola qiladi). Artefakt bir marta quriladi va aynan tekshirilgan digest’lar chiqariladi (`build_once_promote`); publisher tag imzosini, commit `main`dan yetib borishini va tag commit = manifest commit ekanini tekshiradi. Engineering credential faqat `cand/*` ga push qiladi. Test yoki tasdiqdan keyin boshqa artifact chiqarilmaydi. Kutish paytida approval revoke/expiry bo‘lsa yoki source, dependency, offer, rol, policy yoki evaluator o‘zgarsa tegishli qayta tekshiruv talab qilinadi (EVO-AT08). Dalilsiz, TTL o‘tgan yoki ruxsatli toifadan tashqari promotion rad etiladi.

## 10. Harness o‘zini yangilashi

Orkestratsiya va workflow kodi ham nomzod bo‘la oladi (C sinfi, WF-E02). Yangi versiyaga o‘tishda run, checkpoint, lease/fence, in-flight command, reservation, timer, webhook va audit inventari olinadi. Har faol run uchun yo‘l oldindan tanlanadi: eski definition’da tugatish, sinalgan state migration yoki sababli bekor qilish. Amaldagi controller yangi dispatch’ni yopadi; handover dalili va yangi epoch bilan yangi controller qabul qiladi. Eski process qaytib kelishi uni qayta vakolatli qilmaydi — eski epoch bilan har dispatch rad etiladi (EVO-AT06). Bir ish uchun ikki faol controller yoki parallel eski-yangi tashqi writer bo‘lmaydi.

## 11. Himoyalangan release va tiklash

Publisher, verification va kill nazorati candidate’dan mustaqil; candidate o‘z release vakolatini o‘zgartirib production’ga o‘tolmaydi (EVO-AT03). Global rejim `killed` bo‘lsa faqat `recovery` sinfidagi release chiqariladi — manifest’da `release_class: recovery` deb e’lon qilingan va faqat containment, reconciliation yoki oldin tekshirilgan release’ni tiklaydigan owner tasdiqlagan release (`release-policy.yaml#release_classes`, `kill_interaction`); rejali release oynasida maintenance hold ishlaydi (`execution-policy.yaml#maintenance_hold`). Release exact artifact, schema-aware migration, service ACK, kuzatuv va tiklash rejasi bilan. Kuzatuv avval isolated/read-only yoki tashqi effektni takrorlamaydigan scope’da boshlanadi. Rollback oldingi kodni qo‘yish bilangina yopilmaydi: schema mosligi, oldingi versiya tushunmaydigan workflow state va upgrade paytida qabul qilingan biznes yozuvlari (submission, consent withdrawal, webhook, billing) tekshiriladi (EVO-AT07). Remote effekt DB restore bilan bekor bo‘lmaydi; zarur compensation alohida vakolatli command.

## 12. Texnik va biznes qabul

Lifecycle milestone’lari alohida yoziladi: `specified`, `implemented`, `verified_in_staging`, `merged`, `released`, `deployed`, `observed`, `technically_accepted`, `business_accepted`; muqobil yakunlar `rejected`, `inconclusive`, `rolled_back`, `cancelled`, `not_applicable`. Compile/test PASS, tezroq javob yoki kamroq token biznes foydasini avtomatik isbotlamaydi. Sifat, xavfsizlik, xarajat, operator yuki va tegishli biznes natijasi oldindan belgilangan guardrail bilan baholanadi. Infratuzilma/security upgrade’ida maqsadga mos texnik acceptance va biznesga zarar yetmaganlik dalili tanlanadi (`business_accepted: not_applicable`); har upgrade’dan sun’iy savdo uplift’i talab qilinmaydi.

Tracking, qualified yoki attribution ta’rifi, kogorta yetilishi yoki source completeness o‘zgarsa baseline taqqoslanuvchanligi qayta tekshiriladi (EVO-AT10). Yetarli dalil yo‘q holat `inconclusive`; kuzatuvning maksimal muddati, exposure va hold/reject qarori oldindan `evolution.outcome_policy` da belgilanadi. Inconclusive natija kengroq rollout, keyingi avtomatlashtirish yoki avtonomiya oshirishni oqlamaydi (EVO-AT09).

## 13. Yaxshilanish xotirasi

Har yopilgan upgrade uchun [improvement-memory-record.schema.json](../09_Config_Templates/schemas/improvement-memory-record.schema.json) yozuvi: manba, revision, sana, muammo, oldingi holat, gipoteza, diff, test dalili, haqiqiy xarajat, rollout, kuzatilgan natija va qaror egasi. Faqat `accepted` va `guidance_eligible: true` yozuv keyingi rejalash yoki WF-E04 ga kiradi; rejected/inconclusive upgrade yutuq sifatida yozilmaydi. Xom log, tashqi hujjat yoki muvaffaqiyatsiz taklif avtomatik agent ko‘rsatmasiga aylanmaydi. PII/secret ajratiladi; retention, supersede/revoke va `review_by` eskirish qoidasi bor.

## 14. Engineering byudjeti va resurs himoyasi

Engineering AI/test/compute xarajati runtime AI cap’idan (USD 150/oy, 15 000 USD minor) va reklama cap’idan (USD 1 500/oy, 150 000 USD minor) **alohida** hisob; ulardan olinmaydi (`engineering-budget.yaml`: `shares_runtime_ai_cap: false`, `shares_ads_cap: false`). Engineering uchun qo‘shimcha mablag‘ bor deb olinmaydi: `engineering.budget` va `engineering.llm_access` owner tomonidan yopilmaguncha pullik engineering o‘chiq (`paid_engineering_enabled: false`, ⧗ OD-02) — bu davrda sikl deterministik intake/backlog va owner/builder qo‘lda bajaradigan, lekin xuddi shu sandbox → verification → release yo‘lidan o‘tadigan ish bilan ishlaydi. Owner tanlovi variantlari `engineering-budget.yaml#options_for_owner_decision` da. Engineering identity, kalit va accounting runtime secret custody’sidan alohida; runtime OpenRouter kaliti engineering’da ishlatilmaydi.

Parallel candidate, retry, token/vaqt, CPU/RAM/disk/IO va kill chegaralari belgilanadi; production uchun resurs zaxirasi cgroup slice’lari bilan majburlanadi. Engineering limiti tugashi yoki build yuklamasi intake, kill, pul hisobi va operator boshqaruvini ishdan chiqarmaydi (EVO-AT05). AMT PC yetadi deb taxmin qilinmaydi: `capacity.sandbox_host` AMT PC’dagi haqiqiy build/test yuklamasi o‘lchovi bilan yopiladi; alohida build host kerak bo‘lsa — bu pul qarori va owner gate’i.

## 15. Owner ko‘rinishi

Evolution ishlari uchun ham besh savol: nima bajarilmoqda; qanday natija kutilmoqda; kimdan nima kerak; qancha sarflandi (engineering hisobi alohida); keyingi qadam nima. Ochiq proposal’lar, kutilayotgan qarorlar, deadline’lar va oxirgi ishonchli natija ko‘rinadi ([WORKFLOW_CONTRACT §9](WORKFLOW_CONTRACT.md)).

## 16. Qurishdan oldin yopiladigan qiymatlar

Accountable rol, co-signer va gate [readiness.yaml](../09_Config_Templates/readiness.yaml) dan; tasdiqlash qoidalari [CONFIG_CONTRACT](CONFIG_CONTRACT.md) §2 da.

| Masala | Readiness kaliti | Gate | Accountable (+ co-signer) | Dalil |
|---|---|---|---|---|
| Workflow mexanizmi va Paperclip adapteri | `workflow.mechanism` | F1_WORKFLOW | technical_operator | haqiqiy restart/timer/handoff/replay prototipi; issue statusi workflow truth bilan zid kelmasligi |
| Engineering AI/test/compute byudjeti | `engineering.budget` (optional) | FE_SANDBOX | owner | pul birligi, davr, actual+reserve, loop/retry va stop chegaralari; runtime/ads cap saqlanishi; N/A = pullik engineering o‘chiq (⧗ OD-02) |
| Engineering LLM kirishi | `engineering.llm_access` (optional) | FE_SANDBOX | owner | alohida identity, account/key va accounting; runtime custody o‘zgarmasligi; N/A = faqat qo‘lda engineering (⧗ OD-02) |
| Server va sandbox sig‘imi | `capacity.sandbox_host` | FE_SANDBOX | technical_operator + owner | AMT PC’dagi build/runtime/DB yuklamasi, CPU/RAM/disk/IO limitlari va production zaxirasi (HG-FE-03) |
| Verifier va evaluator custody | `verification.custody` | FE_RELEASE | owner | suite/hash, holdout kirishi, muallifdan ajratilgan credential va PASS vakolati (HG-FE-02) |
| Mustaqil inson reviewer | `engineering.independent_reviewer` | FE_RELEASE | owner | E sinfi o‘zgarishlarini ko‘radigan, muallif bo‘lmagan nomlangan shaxs (`person_ref`) yoki `class_e_frozen` (owner imzosi; E sinfi release’lar F7 gacha rad) (⧗ OD-12); Q67 bo‘yicha majburiy pre-F5 baseline inson review’i o‘rniga `class_e_frozen` rad etiladi (C-28) |
| Release scope va kuzatuv | `release.scope_observation` | FE_RELEASE | owner | standart owner release; o‘zgarish sinfi bo‘yicha kuzatuv doirasi, oyna va stop qoidalari (HG-FE-05) |
| Workflow run/migration recovery | `workflow.recovery` | FE_RELEASE | technical_operator | process/host yo‘qolishi uchun RPO/RTO, checkpoint va schema migration drill |
| Upgrade natijasini baholash | `evolution.outcome_policy` | FE_RELEASE | owner (tayyorlaydi: funnel-analyst) | baseline, measurement revision, guardrail, sample/maturity va inconclusive siyosati (HG-FE-05) |
| Auto-release qarori | `auto_release.decision_ref` (critical) | AUTO_RELEASE_ENABLE | owner | Q11 ni o‘zgartiruvchi owner qarori va ruxsatli scope; hech qachon N/A emas — qaror bo‘lmaguncha profil o‘tmaydi va auto-release yopiq (⧗ OD-03) |
| FE qabul dalili | `evolution.fe_acceptance` (critical) | AUTO_RELEASE_ENABLE | owner | FE fazasi `technically_accepted` va EVO-AT14 `pass` (`evolution-policy.yaml#promotion.auto_release.blocked_until`) |

Pullik engineering va auto-release tegishli bandlar yopilmaguncha ochilmaydi.

## 17. Qabul

Talablar EVO-R04–R14; testlar EVO-AT03–AT12 va EVO-AT14 ([PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md)). Yakuniy isbot: kamida bitta tizim aniqlagan haqiqiy muammo butun sikldan o‘tib, exact change/evidence, kuzatuv va accepted/rejected/inconclusive qarori bilan yopiladi; faqat kod yozilgani self-evolution isboti emas (EVO-AT14).
