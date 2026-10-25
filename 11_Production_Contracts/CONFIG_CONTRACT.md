# Konfiguratsiya va readiness shartnomasi

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

`09_Config_Templates` qurilish uchun machine sxema va xavfsiz boshlang‘ich shablonlarni beradi; shablonlar machine truth hisoblanadi, prose ular bilan aynan mos bo‘ladi. Template’ning sintaktik to‘g‘riligi production ruxsati emas. Builder typed loader, migration va semantic validation’ni runtime kodda amalga oshiradi; paketdagi [validator](../12_Acceptance/validate_bundle.py) hujjat va shablon yaxlitligini tekshiradi (§6). Ustuvorlik [INVARIANTS](INVARIANTS.md) sarlavhasida: config shablonlari 3-darajada; `readiness.yaml` qiymatlari 5-darajada — ular faqat owner qarorlari, invariantlar va kontraktlar ichida ishlaydi va owner o‘rnatgan nazoratga muqobil yarata olmaydi. Readiness va approval vakolati bo‘yicha qaror yozuvi — ADR-031.

## 1. Kanonik konfiguratsiyalar

O‘zgartirish yo‘llari: **PR** — owner merge (HG-GIT-01), keyin `amt-release` validate → prepare (candidate) → owner `/release approve <candidate_id>` (HG-REL-01, `release_approvals`) va owner imzolagan tag → activate → ACK; **PR + E** — himoyalangan sirt (`evolution-policy.yaml#protected_surfaces`): E sinfi, typed code, mustaqil inson review va owner; **DB** — runtime holat, faqat ops-bot owner buyruqlari bilan. Q65 faqat birinchi F1da [FIRST_RELEASE](../05_Build_Phases/FIRST_RELEASE.md) fixed owner SSH importer’iga shu canonical yozuvni atomik yaratishga ruxsat beradi; keyin oddiy typed Telegram yo‘li. Q66 dastlabki build review’i — `evolution-policy.yaml#initial_build_review`, engineering E esa mustaqil inson review’ini saqlaydi. ACK sinfi `runtime-isolation.yaml#services.ack_class` va `release-policy.yaml` dan: `write_gate` servis yangi revision’ni ACK qilmaguncha yozmaydi; `function_gate` servis o‘z funksiyasini ACK’gacha ushlab turadi (sync job ishlamaydi, CAPI outbox hold, watchdog eski chegarada, tg-auth yangi sessiya bermaydi).

| Fayl | Mas’uliyat | O‘zgartirish yo‘li | Consumers (ACK sinfi) |
|---|---|---|---|
| [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) | Action → approver, `review_required`, NEVER_AUTO (owner control amallari, jumladan `agent_resume`), Trust Ramp, agent tool allowlist, landing PR yo‘llari, Reviewer va inson til tekshiruvi, amoCRM ceiling | PR + E | gateway, ops-bot, amt-control, amocrm-mcp, quota-coordinator (write_gate) |
| [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) | Command va rejim enum’lari, `approval_binding` (yagona joy), kill/resume/restore/maintenance, `capability_requires_profile` | PR + E | gateway, executor, amt-control, llm-proxy, ops-bot, amt-workflow (write_gate); amt-release |
| [budgets.yaml](../09_Config_Templates/budgets.yaml) | Minor-unit cap’lar, ulush va reserve, reservation, billing ishonchsizligida pauza, non-critical admission sinflari (`admission_classes`), provider siyosati, ads admission/commitment, provider spending limit, rolling24h | PR + E | llm-proxy, gateway, amt-control, ops-bot (write_gate); cost-watchdog, sync-worker (function_gate) |
| [prompt-manifest.yaml](../09_Config_Templates/prompt-manifest.yaml) | Rol bo‘yicha har LLM chaqiruviga kiradigan matn (eager) va kerak bo‘lganda ochiladigan matn (on demand), qat’iy prompt chegarasi `max_fixed_tokens`, invariant indeksi, `kernel_ref` manbai (◇ P-83) | PR + E | managed-runner, Hermes adapter (prompt yig‘ish); amt-release (`prompt_digest`); validator |
| [engineering-budget.yaml](../09_Config_Templates/engineering-budget.yaml) | Runtime va ads cap’laridan alohida engineering hisobi; pullik engineering o‘chiq | PR + E | amt-eng-proxy, amt-sandbox; amt-workflow (write_gate) |
| [resource-policy.yaml](../09_Config_Templates/resource-policy.yaml) | cgroup slice’lar (control > production > sandbox), production zaxirasi, sandbox limitlari | PR + E | amt-release (systemd slice), amt-sandbox, amt-verify |
| [capacity-policy.yaml](../09_Config_Templates/capacity-policy.yaml) | Fizik park balansi, wizard maydonlari, waitlist, freshness/hold, rent bandlari | PR + E | ops-bot, gateway (write_gate); sync-worker (function_gate); amt-workflow WF-O01 |
| [sale-readiness.yaml](../09_Config_Templates/sale-readiness.yaml) | Sale readiness snapshot sxemasi, manba, cadence, gate | PR + E | ops-bot, gateway (write_gate); amt-workflow WF-O01 |
| [business-policy.yaml](../09_Config_Templates/business-policy.yaml) | Qualified ta’rifi, `data_status`, haftalik hisobot metrikalari, Q29.1 qoidasi, iqtisodiy gate | PR + E | sync-worker (function_gate); gateway (`wh.metrics`, `report.submit`) |
| [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml) | KC-01/KC-02, `data_status` harakatlari, low-data exposure, kill-criteria’dan keyingi resume | PR + E | sync-worker (function_gate); amt-control (write_gate) |
| [decision-statistics.yaml](../09_Config_Templates/decision-statistics.yaml) | Umumiy statistik qaror qoidalari: har qoida uchun usul, MDE, alpha, power, minimal exposure, maksimal uzaytirish, non-inferiority margin va iste’molchi config’lar (KC-01/KC-02 seriya holati, Step 2, Trust Ramp, shadow, eksperiment, Q29.1); owner qiymatlari readiness’da | PR + E | sync-worker (function_gate); amt-control (write_gate); amt-verify (shadow suite) |
| [agent-hiring.yaml](../09_Config_Templates/agent-hiring.yaml) | Avtonom agent yollash chegarasi (✅ Q68): so‘rovchi, ruxsat etilgan va taqiqlangan tool’lar, taqiqlangan imkoniyatlar, PII yo‘q, Trust Ramp maksimumi L1, ulush faqat `reserve` dan, WF-E05 tekshiruvlari | PR + E |
| [pipelines.yaml](../09_Config_Templates/pipelines.yaml) | amoCRM pipeline/status ID, `qualified_fact_rule`, lifecycle hodisalari, CAPI event map | PR + E | sync-worker, capi-bridge (function_gate); amocrm-mcp (write_gate) |
| [offers.yaml](../09_Config_Templates/offers.yaml) | Owner tasdiqlagan offer revision’lari, faktlar, huquq va propagation ref’lari | PR (faqat owner, Q35) | gateway (`offers.read`, Reviewer subject); landing repo CI snapshot generatori |
| [tracking-health.yaml](../09_Config_Templates/tracking-health.yaml) | Tracking gate holat mashinasi, check sxemasi, streak va `read_only`dan chiqish | PR + E | sync-worker (function_gate); amt-control (write_gate) |
| [privacy-policy.yaml](../09_Config_Templates/privacy-policy.yaml) | Consent maqsadlari, PII dataset inventari, breach ref | PR + E | capi-bridge, sync-worker, tg-auth (function_gate); gateway, ops-bot (write_gate); landing ilovasi |
| [roles.yaml](../09_Config_Templates/roles.yaml) | Statik rol/flag ruxsatlari, ko‘rinish, bir martalik seed sxemasi | fayl: PR + E; a’zolik va flag: DB (`/role`, owner typed code) | ops-bot (write_gate), tg-auth (function_gate) — runtime’da DB’dan o‘qiydi |
| [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) | Servis reyestri (UID, unit, socket, DB rol, credential, egress, ACK sinfi), agent va engineering rollari, Paperclip bridge | PR + E | amt-release (unit/UID/egress), managed-runner, gateway, llm-proxy |
| [release-policy.yaml](../09_Config_Templates/release-policy.yaml) | Publish yo‘li, release sinflari (`normal`, `recovery`), ACK ro‘yxatlari, `release_approvals`, tag ruleset, AMT-host scope | PR + E | amt-release; ACK beradigan barcha servislar |
| [evolution-policy.yaml](../09_Config_Templates/evolution-policy.yaml) | Evolution sikli, o‘zgarish sinflari, himoyalangan sirtlar, gate’lar, auto-release (o‘chiq) | PR + E | amt-workflow (write_gate); amt-release, amt-verify, amt-sandbox; ops-bot (owner gate’lari) |
| [workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml) | Workflow katalogi, holat enum’lari, owner ko‘rinishi | PR + E | amt-workflow (write_gate) |
| `workflows/WF-*.yaml` | Workflow definition’lari | PR (C sinfi, WF-E02) | amt-workflow (write_gate) |
| [operations.yaml](../09_Config_Templates/operations.yaml) | Yagona jadval, protective controls katalogi, severity/ACK ref, RPO ta’rifi, upgrade oynasi | PR + E | ops-bot, amt-control, amt-workflow (write_gate); sync-worker, cost-watchdog (function_gate); amt-backup; off-host monitor |
| [environments.yaml](../09_Config_Templates/environments.yaml) | Muhit bo‘yicha resurs reyestri; prod bilan kesishmaslik | PR + E | amt-release, amt-sandbox; validator |
| [readiness.yaml](../09_Config_Templates/readiness.yaml) | Readiness qoidalari, profil DAG’i va qiymatlari (§2–§4) | qoida va profil: PR + E; qiymat: readiness jarayoni (§2) | amt-release, amt-control (`capability_enforced_by`); validator |
| `schemas/*.json` | Workflow definition, handoff, candidate manifest, verification result, upgrade proposal, improvement memory, runtime talab va unit-cost modeli (`cost-model.schema.json`, F4-AT-19) | PR | amt-workflow, amt-verify, amt-release |
| [env.example](../09_Config_Templates/env.example) | Servis bo‘limlari bo‘yicha env nomlari (qiymatsiz) | PR | `runtime-isolation.yaml#services` dagi har servis o‘z bo‘limini oladi |
| [bundle-index.json](../09_Config_Templates/bundle-index.json) | Config, workflow va schema indeksi | PR | validator |

Runtime holat — approval, a’zolik va flag, rejim o‘zgarishi, fleet va sale snapshot’lari, readiness dalil yozuvlari — config PR’i emas. Ular DB’da, vakolatli buyruq va audit bilan yuritiladi; tungi eksport ularni config’ga qaytarib yozmaydi.

### Command binding va retry lifecycle

`execution-policy.yaml#approval_binding_lifecycle` intent yaratilishi, append-only exact command review va approval dependency snapshot’ini ajratadi. `command_review_bindings` verdict’ni, `command_approval_bindings` approval oldidan muzlatilgan dependency’larni saqlaydi; barcha inson, policy va auto approval’lar bitta freeze funksiyasidan foydalanadi. Birinchi taqdimot yoki tugma oldidan zarur verdict/til tekshiruvi mavjud; keyingi dependency almashtirish eski binding’ni tahrirlamaydi, yangi command revision talab qiladi. Hash qilinadigan intent keyin olinadigan verdict/approval’ni o‘z ichiga olmaydi.

`execution-policy.yaml#retry` command holatini qaytarmaydi: faqat dalilli no-effect attempt yakunlangach, original muddat ichida yangi monotonic fence bilan o‘sha command/reservation davom etadi. Unknown natija `uncertain` → reconcile; terminal natija qayta ochilmaydi. Gateway, executor va typed loader bir xil lifecycle’ni ishlatadi. Qabul: F3-AT-24, F3-AT-32 va F3-AT-34; biznes va real vendor sinovi bajarilmaguncha bular spetsifikatsiya.

## 2. Readiness modeli

Holatlar: `pending` (qiymat noma’lum) → `evidenced` (dalil tayyorlangan) → `approved` (vakolatli inson tasdiqlagan); `not_applicable` — faqat `criticality: optional` yozuvda, `value: {disabled: true, rationale}` va owner imzosi bilan. Critical capability hech qachon N/A bo‘lmaydi.

Yozuv maydonlari (`readiness.yaml#record_fields`): `key`, `gate`, `criticality`, `accountable_role`, `co_signers`, `prepared_by`, `description`, `status`, `value`, `evidence_ref`, `evidence_at`, `evidence_prepared_by`, `max_evidence_age`, `approved_by`, `approved_at`, `co_signatures`, `valid_until`.

Qoidalar (`readiness.yaml#rules`):

1. **Bitta gate.** Har talab aynan bitta — eng erta — gate profilini nomlaydi. Keyingi profillar uni `profiles.requires` orqali tranzitiv meros oladi.
2. **Yangiroq dalil — alohida kalit.** Keyingi gate to‘liqroq yoki yangiroq dalil talab qilsa, alohida kalit `max_evidence_age` bilan ochiladi (masalan `vendor.meta_cap` F3_CONTROLLED_TEST, `budget.ads_fresh_check` F6_STEP1, `P1D`).
3. **Profil PASS va gate.** Gate — capability’ni oshirish (`execution-policy.yaml#capability_enablement`): config’dagi capability manifest’ning `capabilities_enabled` ro‘yxatiga birinchi marta kiradigan release (`amt-release` prepare’da va activate’da baholaydi) hamda owner’ning oshiruvchi o‘tishlari — `global_mode_change` `shadow → enabled`, `pipeline_mode_change` `L0 → L1` yoki `L1 → L2`, `trust_graduation` `L1 → L2` (`amt-control` typed code’ni iste’mol qilganda baholaydi va `profile_evaluation_digest`ni bog‘laydi). L2 gate’i L2_ENABLE bilan birga o‘sha pipeline’ning L1 profilini ham baholaydi (rent — F6_STEP1, sale — F6_STEP2). Gate’da profilning va u meros olgan barcha profillarning har talabi `approved` va dalili `max_evidence_age`dan eski emas, yoki yaroqli `not_applicable`. Gate’dan o‘tgan profil o‘zi ochgan capability uchun PASS bo‘lib qoladi (`gate_result` release snapshot’ida yoki `control_events`da); gate’lar orasida ishlatish faqat `operational_validity` bilan to‘xtaydi. Pasaytirish, odatiy release, `maintenance_release`, `control_resume` (restore’dan keyingi qaytish ham) va avtomatik himoya o‘tishlari gate emas (`readiness.yaml#rules`: `gate_time`, `pass_persistence`).
4. **Tasdiqlovchi.** `approved_by` — `approved_at` paytida `accountable_role`ni egallagan shaxs; u dalilni tayyorlagan shaxs bo‘la olmaydi. `co_signers` ham imzolaydi; hammasining imzosisiz `approved` yo‘q.
5. **Agentlar va builder** faqat `prepared_by` bo‘ladi; hech qachon tasdiqlamaydi.
6. **Runtime binding** — §3: release manifest `readiness_snapshot`ni olib yuradi; `amt-control` har capability, rejim va trust tekshiruvida amaldagi tasdiqlarni qayta baholaydi. Config shabloni `*readiness_ref` orqali havola qilgan kalit bundle’ga bog‘langan: uning amaldagi tasdig‘i — faol snapshot qadagan revision, yangi tasdiqlangan qiymat release uni qadaganda kuchga kiradi (kerak bo‘lsa faol commit’dan faqat readiness snapshot’i o‘zgargan candidate — `release-policy.yaml#release_approval.readiness_only_candidate`). `max_evidence_age`li kalit — yangilik kaliti, har doim jonli: bundle’ga bog‘lanmaydi va yangilangan tasdiq release’siz kuchga kiradi (`freshness_keys`). Agent faqat gate profili F4_AGENTS’ni meros oladigan kalitning `prepared_by`si bo‘la oladi (`agent_preparers`).
7. **Saqlash va imzo.** Yozuvlar `amt.readiness_records` va `amt.readiness_signatures`da ([DATA_MODEL §8](../03_Architecture/DATA_MODEL.md)); yagona yozuvchi `amt-control`. Dalilni builder yoki agent workflow output’i yoki merge bo‘lgan PR’dagi evidence manifest’i orqali beradi (`evidenced` revision; control op `readiness_evidence` — `amt-workflow`, `amt-release`); tasdiq va co-sign faqat `/readiness approve <key>` va `/readiness cosign <key>` (typed code, `readiness_signoff`; control op `readiness_sign`, dalil imzo paytida `max_evidence_age` ichida). Noto‘g‘ri tasdiqni owner (istalgan kalit) yoki kalitning javobgar rol egasi `/readiness withdraw <key> <sabab>` bilan qaytarib oladi: sabab bilan qiymatsiz `pending` revision amaldagi tasdiqni to‘xtatadi; qaytarib olish tayyorlovchi va dalil yoshi tekshiruvidan mustasno (`withdraw`). RBAC bo‘lmagan javobgar rollar (`technical_operator`, `finance_owner`, `privacy_owner`, `independent_reviewer`) `amt.responsibility_assignments`da, owner `/role assign` bilan beradi.
8. **Chegaralangan qiymat.** Readiness qiymati owner o‘rnatgan nazoratni almashtira olmaydi: Ads Manager spending limit (✅ Q37), amoCRM ceiling 7 req/s (✅ Q25), AI va paid Meta cap’lari (✅ Q10/Q33/Q44.1, Q08) faqat yangi owner Q bilan o‘zgaradi.

Rollar. `accountable_role` ∈ `owner`, `sales_lead`, `fleet_operator`, `technical_operator`, `finance_owner`, `privacy_owner`, `independent_reviewer` (`readiness.yaml#accountable_roles`). Birinchi uchtasi Telegram RBAC rollari; qolganlari roster mas’uliyatlari (`roles.yaml#responsibility_assignments`), Telegram ruxsati emas, owner ularni o‘zi egallashi mumkin. `prepared_by` ∈ `readiness.yaml#preparers` (builder, `amt-workflow` — HG-F6-06 dan keyingi gate dalili WF-O01 orqali, olti agent, sales_lead, fleet_operator, technical_operator). Readiness qiymati va dalili PII’siz: odam opaque `person_ref` bilan yoziladi, identifikatsiya faqat `amt.people`/`amt.roles`da.

Davomiylik. `max_evidence_age` — ISO 8601 davomiylik (`P1D`, `P7D`, `P30D`, `P92D`); `approve`/`cosign` imzosida va gate’da `evidence_at + max_evidence_age` hali o‘tmagan bo‘lishi kerak. Gate’lar orasida u qayta qo‘llanmaydi. Jonli kalitda dalilning o‘zi muddatli bo‘lsa (masalan vendor ruxsatining tugash sanasi) `valid_until` dalil bilan birga yoziladi va revision bilan imzolanadi; u o‘tgach capability to‘xtaydi. Bundle’ga bog‘langan kalitda `valid_until` bo‘lmaydi: qiymat ichidagi element muddati (masalan credential yoki asset `expires_at`) iste’mol qiluvchi servis tomonidan majburlanadi.

Kalit bo‘linishlari (bir kalit bir nechta profilga yoki bir nechta dalil bosqichiga bitta status bilan xizmat qilmaydi):

| Birinchi dalil kaliti | Alohida keyingi yoki to‘liqroq dalil kaliti |
|---|---|
| `ops.roles_owner` — F1_AUTH | `ops.roles_roster` — F2_LIVE_INTAKE |
| `ops.intake_responders` — F2_LIVE_INTAKE | `ops.ads_handback_roster` — F6_STEP1 (`P7D`); `ops.sale_handback_roster` — F6_STEP2 (`P7D`) |
| `recovery.intake_datasets`, `recovery.intake_drill` — F2_LIVE_INTAKE | `recovery.full_datasets`, `recovery.restore_check` (`P30D`), `recovery.full_drill` (`P92D`) — F6_STEP1 |
| `ops.independent_monitor` — F2_LIVE_INTAKE | `ops.independent_monitor_full` — F6_STEP1 |
| `vendor.meta_cap` — F3_CONTROLLED_TEST | `budget.ads_fresh_check` — F6_STEP1 (`P1D`) |
| `vendor.runner_isolation` — F1_ISOLATION (prototip) | `vendor.runner_isolation_final` — F4_AGENTS |
| `tracking.thresholds` — F2_TRACKING_PASS | `tracking.pass_7d` — F2_TRACKING_PASS |

Joylashuvlar: `offers.initial` va `offers.asset_rights` — F2_LIVE_INTAKE (landing offer va asset’larni ko‘rsatadi; HG-F2-15); `sale.readiness` — F6_STEP2 (◇ P-09); `workflow.recovery` va `release.scope_observation` — FE_RELEASE.

## 3. Gate profillari va runtime binding

`readiness.yaml#profiles` — DAG; `requires` tranzitiv. Profil statusi HUMAN_GATE qarorini almashtirmaydi; profil ↔ HG mosligi [PHASES](../05_Build_Phases/PHASES.md) dagi readiness bo‘limida.

| Profil | requires | Tavsif | Ochadigan capability (`execution-policy.yaml#capability_requires_profile`) |
|---|---|---|---|
| F1_AUTH | — | Owner identity, tg-auth, break-glass, ops-bot transport | — |
| F1_COST_RUNTIME | — | llm-proxy orqali pullik LLM, real reset/accounting oynasi bilan | `llm.billable` |
| F1_ISOLATION | — | Pinned komponentlar va izolyatsiyalangan rol runner prototipi | — |
| F1_WORKFLOW | — | Durable workflow runtime prototipi (restart, timer, handoff, replay) | `workflow.runtime` |
| F2_LIVE_INTAKE | F1_AUTH, F1_COST_RUNTIME, F1_ISOLATION, F1_WORKFLOW | Durable intake, consent, recovery va monitoring bilan real landing trafigi | `intake.live_traffic` |
| F2_TRACKING_PASS | F2_LIVE_INTAKE | 14 kun report-only, tasdiqlangan threshold, 7 ketma-ket PASS (HG-F2-08) | `shadow.real_data` |
| F3_CONTROLLED_TEST | F2_TRACKING_PASS | Owner tasdiqlagan PAUSED entity’larda nazoratli Meta testlari, faqat tracking gate’dan keyin (✅ Q37); production write yo‘q | `meta.remote_test` |
| F4_AGENTS | F3_CONTROLLED_TEST | Olti agent gateway/proxy orqali, real rol izolyatsiyasi bilan; barcha pipeline L0 | `agents.run` |
| F4_CONTENT | F4_AGENTS | Kreativ publish uchun offer, asset huquqi va media chegaralari | `creative.publish` |
| FE_SANDBOX | F1_ISOLATION, F1_WORKFLOW | Production credential’siz engineering sandbox candidate’lari | `sandbox.candidate` |
| FE_RELEASE | FE_SANDBOX | Manifest’ga bog‘langan verification va owner tasdiqlagan `amt-release` | `release.manifest` |
| F5_GO | F2_TRACKING_PASS, F4_CONTENT, FE_RELEASE | Global readiness yopilishi, eval va 7 kunlik real shadow; HG-F5-02 go/no-go | — |
| F6_STEP1 | F5_GO | Rent pipeline 14 kun L1; sale targetologda | `write_mode.enabled`, `pipeline.rent.L1` |
| F6_STEP2 | F6_STEP1 | Step 1 dalilidan keyin sale L1 / full takeover | `pipeline.sale.L1` |
| L2_ENABLE | F6_STEP1 | Muayyan action_type×pipeline uchun graduation’dan keyin L2 (HG-L2-01) | `pipeline.any.L2` |
| PRE_SCREEN | F5_GO | F5 eval’dan keyin Reviewer’dan oldingi Jev pre-screen (Q61); boshqa profil uni meros olmaydi, shuning uchun `models.pre_screen` withdraw qilinsa faqat pre-screen o‘chadi | `review.pre_screen` |
| AUTO_RELEASE_ENABLE | F6_STEP2, FE_RELEASE | Tor auto-release; Q11 ni o‘zgartiruvchi yangi owner Q talab qiladi (⧗ OD-03) | `release.auto` |

Q67 bo‘yicha FE_RELEASE F5 formal eval va shadow boshlanishidan oldin PASS bo‘ladi; F5_GO merosi ham saqlanadi (OD-01 yopildi). F1’dan keyin parallel qurilish mumkin; Q66 exact baseline mustaqil texnik inson signoff’i FE_RELEASE’dan oldin majburiy. `technically_accepted` F6 Step 1 dan keyingi real kuzatuvni, `business_accepted` F7 da EVO-AT14 ni bildiradi; bu keyingi holatlar qatlam tayyorligini yoki inson tekshiruvini F5’dan keyinga surmaydi.

Manifest [candidate-manifest.schema.json](../09_Config_Templates/schemas/candidate-manifest.schema.json) `deployment: {kind, phase, services, required_acks}`ni majburiy saqlaydi: registry ID’lari bounded/unique; `services` disabled/none-ACK servislarni ham o‘z ichiga olgan to‘liq installed inventar. `required_acks` aynan shu inventarning ACK-class servislari, full kataloglarni o‘zgartirmaydi. `release-policy.yaml#deployment` cumulative phase floor, prior installed inventar va barcha active/enabled capability dependency’larini prepare/activate’da qayta tekshiradi; unknown capability yoki omitted protective/dependency rad. Phase pastga tushmaydi; target_profile informational. Initial faqat F1/null base/bo‘sh enabled va snapshot capability’lar; update base active current’ga teng. Q65 importer existing state’ni qayta yozmaydi va oddiy signed tag, owner approval yoki readiness tekshiruvini chetlab o‘tmaydi. Failed first ACK current yaratmaydi; update ACK failure eski current’ni saqlaydi.

Majburlash ikki qatlamli (`capability_enforced_by: [amt-release, amt-control]`):

1. **Release vaqti.** `amt-release prepare` `readiness_snapshot` yasaydi (har kalit: qadalgan amaldagi tasdiq `record_revision`i, `value_hash`, status, `evidence_at`; har capability: `gate_result` — `pass`, `carried` yoki `fail`) va uni `capabilities_enabled` bilan birga manifestga yozadi ([candidate-manifest.schema.json](../09_Config_Templates/schemas/candidate-manifest.schema.json)); manifest digest’i `release_approvals` va imzolangan tag bilan bog‘lanadi. `capabilities_enabled`ga birinchi marta kiradigan capability uchun bu gate (§2 band 3): profil prepare’da va activate’da `max_evidence_age` bilan baholanadi, PASS bo‘lmasa `amt-release` uni yoqmaydi. Allaqachon yoqilgan capability `operational_validity` bilan o‘tadi (`carried`); u bajarilmasa release baribir faollashishi mumkin, lekin capability amaldagi tasdiqlar tiklanguncha to‘xtab turadi. Config shablonidagi `*readiness_ref` havolasi orqali qiymati ishlatiladigan kalitlar bundle’ga bog‘langan: snapshot ularning so‘nggi tasdiqlangan revision’ini qadaydi va config o‘sha qiymat bilan quriladi; `max_evidence_age`li yangilik kalitlari bundan mustasno. Manifest `target_profile` maydonini ham olib yuradi (`release-policy.yaml#version_fields`).
2. **Har ishlatishda.** `amt-control` har capability, rejim va trust tekshiruvida (`readiness.yaml#rules.operational_validity`) capability’ning gate’dan o‘tganini va profil kalitlarining amaldagi tasdig‘i kuchda ekanini tekshiradi: jonli kalitda — eng so‘nggi `approved`/`not_applicable` revision (`valid_until` o‘tmagan), bundle’ga bog‘langan kalitda — faol snapshot qadagan revision; ikkalasida ham `/readiness withdraw` bilan to‘xtatilmagan. Bundle’ga bog‘langan kalitning yangi tasdiqlangan revision’i ishlab turgan capability’ni to‘xtatmaydi, release uni qadaganda kuchga kiradi. `max_evidence_age` faqat imzoda va gate’da tekshiriladi, shuning uchun qisqa muddatli dalil kalitlari (masalan `budget.ads_fresh_check` P1D, `ops.ads_handback_roster` P7D, `recovery.restore_check` P30D) keyingi gate (F6_STEP2 uchun `/mode sale L1`, L2 uchun `/mode <pipeline> L2` va `/graduate` — L2_ENABLE va o‘sha pipeline’ning L1 profili, AUTO_RELEASE_ENABLE uchun `release.auto`ni yoqadigan release) oldidan release’siz yangilanadi (dalilni WF-O01 tayyorlaydi); yangilanmasa o‘sha gate rad etiladi, ishlab turgan capability va odatiy release’lar esa to‘xtamaydi.

Rad etish auditga yoziladi va `ALERT_RELEASE_REFUSED` yoki `readiness_blocked` qaytaradi.

## 4. Typed qiymatlar

`value` kalitga mos type va sxema bilan tekshiriladi. Pul — integer `_minor` va ISO 4217 currency; vaqt — UTC timestamp, biznes vaqt zonasi Asia/Tashkent; davomiylik — ISO 8601 yoki birligi nomida yozilgan integer (`_ms`, `_s`, `_minutes`, `_hours`, `_days`, `_seconds`); odam — `person_ref`. Bo‘sh, null, TBD yoki placeholder qiymat `approved` bo‘lmaydi; “approved” status bo‘sh qiymatni qonuniy qilmaydi; cheksiz qiymat yo‘q. Reference va concrete parametr zid bo‘lsa bundle rad etiladi. Har o‘zgarish yangi config revision va dalil talab qiladi. Template’da null va bo‘sh reyestr kutilgan holat; live profilda ular yopilmagan gate.

### 4.1 Majburiy qiymat sxemalari

`budget.ads_pacing` — `protective_pause` trigger’i; provider spending limitga qo‘shimcha (◇ P-21):

```yaml
budget.ads_pacing:                     # gate F5_GO
  currency: ISO4217                    # provider counter currency (ads.account_currency)
  spend_freshness_cutoff_minutes: integer > 0   # managed entity active and spend data older -> protective_pause
  trigger_headroom_minor: integer >= ads.safety_margin_minor   # managed headroom <= value -> protective_pause
  check_cadence: every_sync_cycle      # spend pacer check in amt-sync
  pause_deadline_minutes: integer > 0  # trigger -> every managed entity re-read, paused and verified
  scope: managed_entities_only
  never: [activate, budget_increase, create]
  evidence: [gateway_headroom_test, host_down_test_provider_limit_holds]
```

`vendor.qualified_optimization` — ✅ Q29.1 qoidasi (`business-policy.yaml#qualified_optimization_rule`):

```yaml
vendor.qualified_optimization:         # gate F5_GO; one entry per pipeline (sale, rent), ◇ P-45
  - pipeline: sale | rent
    supported: boolean                 # account eligibility for a QualifiedLead optimization goal
    account_eligibility_evidence_ref: string
    counted_event: crm_confirmed_meta_attributed_submission   # business-policy.yaml#qualified_optimization_rule.counted_event
    measured_monthly_volume: integer >= 0      # count over the previous calendar month (window, P-56), first measured in F2 (builder with the funnel-analyst procedure before agents.run, ◇ P-31); afterwards sync-worker qualified_volume_check
    measured_window: {from: date, to: date}    # the previous calendar month before measured_at
    measured_at: date
    previous_measurement: {measured_at: date, measured_monthly_volume: integer} | null   # for the 2-month up-switch
    vendor_requirement_ref: {url: string, retrieved_at: date, quoted_requirement: string}   # current official Meta requirement [D]
    vendor_conditions: [{name: string, value: string, window: string, source: url, retrieved_at: date}]   # every structured condition, in its own window; all must hold
    owner_volume_floor_per_month: integer   # business-policy.yaml#qualified_optimization_rule (Q29.1: ~200 lead/oy)
    selected_goal: Lead | QualifiedLead
# QualifiedLead only if supported, every vendor condition holds and measured_monthly_volume >= max(owner_volume_floor_per_month, vendor volume)
# in 2 consecutive monthly measurements; back to Lead at the first measurement below (Q29.1); qualified stays a guardrail; CAPI QualifiedLead is still sent
```

`business.acceptance.verdict_rule` — Step 1 → Step 2 qarori oldindan ro‘yxatga olinadi (`decision-statistics.yaml` STEP1_TO_STEP2, ◇ P-41); qarorning turi, margin, alpha, power va `max_weeks` — owner qiymatlari (✅ Q36 talqini):

```yaml
business.acceptance.verdict_rule:      # gate F5_GO (HG-F5-04), per pipeline; approved before HG-F6-01
  primary: qualified_cpl_vs_baseline   # each pipeline against its own frozen baseline (ADR-013); DiD diagnostic only
  decision: non_inferiority | superiority   # owner choice
  margin_pct: number > 0               # non-inferiority margin only (owner choice)
  target_effect_pct: number > 0 | null # superiority only: the CPL improvement to show (owner choice)
  alpha: number                        # 0 < alpha < 0.5
  alpha_sided: one_sided               # the verdict uses one-sided alpha; the BUSINESS_CONTRACT 8.7 MDE table is two-sided
  power: number                        # 0.5 < power < 1
  test:                                # owner approves the test before HG-F6-01 (P-56)
    statistic: log_cpl_ratio           # log(CPL of the AI weeks / baseline CPL)
    variance_model: poisson | negative_binomial_baseline_k   # owner choice; negative binomial is never below Poisson
    baseline_uncertainty: included | excluded   # owner choice
  verdict_map:                         # owner approves; canonical non-inferiority form in the comments
    sufficient: string                 # e.g. one-sided upper confidence bound of the CPL ratio < 1 + margin_pct
    insufficient: string               # e.g. lower bound > 1 + margin_pct (superiority: lower bound > 1 - target_effect_pct)
    inconclusive: otherwise
  looks: single_at_max_weeks | alpha_spending   # every extension week is a look; unadjusted repeated looks are not allowed
  alpha_spending: {method: string, schedule: [number]} | null   # required when looks = alpha_spending
  min_qualified: integer > 0           # qualified facts in the AI window before any verdict other than inconclusive
  guardrails: [metric_ref]             # lead_to_contract, cash/contribution, fulfilment/refund
  rent_constraints: {occupancy_in_range_days_pct: number}   # rent only; needs an occupancy target range in fleet.thresholds before it can be computed
  extension_unit_weeks: 1              # one more full event_week and KC-01 evaluation
  max_weeks: integer >= 2              # Step 1 length incl. extensions; at the maximum: hold, sale stays with the targetologist
# A revision approved after the Step 1 anchor is not used for that Step 1; COMPARISON.md shows the implied MDE
```

`ops.kill_targets` — UAT-21 va F6-AT-08 shu qiymatlarga bog‘lanadi:

```yaml
ops.kill_targets:                      # gate F3_CONTROLLED_TEST
  local_containment_max_ms: integer > 0      # kill -> no new normal write, LLM or media dispatch (proposed default <= 5000 ms, OD-11)
  remote_pause_report_max_s: integer > 0     # mode B: per-entity paused or partial_failure report
  in_flight_report_max_s: integer > 0        # in-flight attempts listed with reconcile state
```

`ops.credential_inventory` — har credential bitta qator; muddat alertlari ALERT_CREDENTIAL_EXPIRY:

```yaml
ops.credential_inventory:              # gate F2_LIVE_INTAKE; list
  - name: string                       # amoCRM token, Meta system users and CAPI token, OpenRouter key, BotFather tokens, Langfuse keys,
                                       # GitHub tokens and deploy keys, Cloudflare Tunnel token, Tailscale node key, age key, tg-auth break-glass
    service_id: string                 # runtime-isolation.yaml#services service_id that holds it
    holder_role: string                # accountable role (technical_operator or owner)
    issuing_user_role: string | null   # tokens that inherit the issuing user's rights (env.example [user-rights]; amoCRM, VR-16): that user and role; null for tokens with their own scope
    expires_at: UTC timestamp | null   # null only when the vendor states no expiry (evidence_ref)
    rotation_steps_ref: string         # sops -> render -> service ACK steps
    last_rotated_at: UTC timestamp
    alerts: [T-30, T-7, T-1]
```

`recovery.*` — RPO = ma’lumot yo‘qotish oynasi: eng yangi yaroqli lokal snapshot consistency point’idan mantiqiy xatogacha (`operations.yaml#rpo_definition`; mantiqiy xato uchun — AMT host yo‘qolishi qabul qilingan doira, Q55); qiymatlar faqat shu kalitlarda, sekundda:

```yaml
recovery.intake_datasets | recovery.full_datasets:     # list
  - dataset: string                    # privacy-policy.yaml#datasets / DATA_MODEL name
    host: string
    custodian_uid: string              # runtime-isolation.yaml#services uid
    source_of_truth: string
    backup_method: string              # AMT local snapshot (pg_dump -Fc, ClickHouse BACKUP, file copy), production Dokploy backup (HG-F2-18), vendor export
    consistency_point: string
    encryption: string                 # AMT local snapshot: none (Q54)
    key_custodian: person_ref
    key_custody_ref: string            # key needed for the restore, e.g. the sops age key paper/QR copy in the owner's safe (Q56)
    retention_ref: privacy.retention
    rpo_seconds: integer > 0
    rto_seconds: integer > 0
    loss_class: process | host         # separate rows when both apply
    restore_precedence: integer
    host_loss_scope: string            # full_datasets only; accepted AMT history loss and the rebuild-from-sources path (Q55)
recovery.intake_drill | recovery.full_drill:
  drill_id: string
  environment: isolated                # AMT side: restore_test / restore_drill on the AMT PC (no live credentials, jobs or egress; starts killed); landing side: an isolated restore target on the production Dokploy host, never over the live DB (owner, HG-F2-18)
  manifest_digest: string
  dataset_hashes: {dataset: sha256}
  incident_at: UTC timestamp
  last_restored_event_at: UTC timestamp
  recovery_start_at: UTC timestamp
  business_resume_at: UTC timestamp
  measured_rpo_seconds: integer        # incident_at - last_restored_event_at
  measured_rto_seconds: integer        # business_resume_at - incident_at (recovery_start -> resume shown separately)
  live_egress_count: 0
  result: pass | fail | blocked | inconclusive
  evidence_ref: string
  # restore_check: local snapshot MANIFEST sha256 check + restore_test result, max_evidence_age P30D
  # full_drill only (restore_drill environment, max_evidence_age P92D) - the key cannot be approved without these fields:
  source_export_ref: string            # owner-exported PII-free landing receipt metadata + amoCRM events (environments.yaml#restore_drill.source_export)
  rebuild_from_sources_result: pass | fail
  capi_resend_counts: {resent: integer, terminal_before_loss: integer, unknown_state: integer}   # synthetic endpoint; the last two are skipped_unknown_prior_send reasons (operations.yaml#host_loss.rebuild_from_sources)
  kill_a_b_result: {result: pass | fail, timings_ref: string}   # fixtures + simulated Meta endpoint; ops.kill_targets
  schema_rollback_result: pass | fail
  production_self_test_ref: string     # sudo /opt/wolter-amt/current/bin/amt-kill --self-test over SSH via Tailscale; mode unchanged
  production_control_check: {control_epoch_before: integer, control_epoch_after: integer, kill_latch_unchanged: true}
  host_loss_time_seconds: {f0_install_bootstrap: {seconds: integer, method: measured}, rebuild_delta: {seconds: integer, method: measured | estimated}, keys_tunnel: {seconds: integer, method: measured | estimated}, rebuild_from_sources: {seconds: integer, method: measured}, source_fetch: {seconds: integer, method: estimated}, validation: {seconds: integer, method: measured}, sum_seconds: integer}   # rebuild_delta is measured only in the optional owner rehearsal before F2; keys_tunnel is estimated when done as a tabletop; rebuild_from_sources is measured on the staged export, source_fetch (amoCRM history over the rate-limited API) is computed from the rate limit; not an end-to-end rehearsal (no spare PC, Q55)
```

Backup stale alert — jadvaldan olingan run deadline’i (02:00 + kutilgan run davomiyligi + margin) o‘tsa darhol alert va bitta catch-up run; shu payt ma’lumot yo‘qotish oynasi 24 soatdan oshishi mumkin va hisobotda ko‘rsatiladi (`operations.yaml#backup_stale_alert_rule`, `rpo_definition`).

`budget.tco` — runtime cap’dan alohida umumiy xizmat narxi; o‘lchov bo‘lmasa tejam yoki ROI yozilmaydi:

```yaml
budget.tco:                            # gate F5_GO
  currency: ISO4217
  period: month
  one_time_build_minor: integer        # build cost, separate from recurring run
  one_time_host_minor: integer         # owner PC (Q52), second disk, UPS (Q53), Omada controller (Q59)
  recurring:
    ai_runtime_minor: integer          # <= openrouter.key_hard_cap_minor
    electricity_and_office_internet_minor: integer
    independent_monitor_minor: integer # HG-F2-17
    licenses_minor: integer
    credit_fees_tax_fx_minor: integer
    engineering_minor: integer         # engineering-budget.yaml, separate account
  human_ops_hours_per_week: number     # links ops.founder_time_budget
  paid_meta_minor: integer             # shown separately, <= ads.monthly_cap_minor
  source_refs: [string]                # dated quotes; unknown stays unknown
```

### 4.2 Barcha readiness kalitlari

Gate, kritiklik va accountable `readiness.yaml` dan aynan olingan; qiymat shakli shu shartnomada.

| Kalit | Gate | Kritiklik | Accountable (+ co-signer) | Qiymat shakli |
|---|---|---|---|---|
| `ops.roles_owner` | F1_AUTH | critical | owner | `{person_ref, seed_ref, tg_auth_enrolment_ref, cloud_password_attested_at, break_glass_ref}`; identifikatsiya faqat `amt.people` |
| `ops.roles_roster` | F2_LIVE_INTAKE | critical | owner | `[{person_ref, role, expires_at}]` — owner `/role add` (HG-F2-16); sales_lead, intake primary/deputy, fleet_operator |
| `ops.intake_responders` | F2_LIVE_INTAKE | critical | owner | `{primary: person_ref, deputy: person_ref, coverage: {timezone, windows[]}, flag: ops_responder}` |
| `ops.independent_monitor` | F2_LIVE_INTAKE | critical | technical_operator | `{monitor_ref, provider_ref, hosting_ref, checks: [landing_availability, accepted_to_crm_age, queue_last_success, backup_age, critical_heartbeat], alternate_channel_ref, retention_days: int ≥ 8, store_before_ack_evidence_ref, ack_contract_ref, heartbeat_interval_s: int, dead_man_after_s: int, independence_evidence_ref, test_evidence_ref}` (HG-F2-17); qiymat [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) `external_dependencies[independent-monitor]` shartnomasini qanoatlantirishi shart: ACK’dan oldin saqlash, ACK’da `observed_at` va nonce aks-sadosi HMAC bilan, tarix ≥ 8 kun, AMT PC’da ham landing production hostida ham emas |
| `ops.ack_minutes` | F2_LIVE_INTAKE | critical | owner | `{critical: {ack_minutes, escalate_after_minutes}, degraded: {...}}` — musbat integer, haqiqiy coverage bilan; “24/7” faqat coverage isbotlansa |
| `ops.escalation` | F2_LIVE_INTAKE | critical | owner | `{route: [primary, deputy, owner], owner_unavailable: protective_controls_only, alternate_signal_ref}` |
| `ops.credential_inventory` | F2_LIVE_INTAKE | critical | technical_operator | §4.1 sxemasi |
| `ops.kill_targets` | F3_CONTROLLED_TEST | critical | owner | §4.1 sxemasi |
| `ops.resource_envelope` | F5_GO | critical | technical_operator + owner | `{measured_window, peak_and_soak_refs, production_reserve, sandbox_limits, queue_caps, disk_inode_actions_ref, raid_degraded_alert}` — `resource-policy.yaml` qiymatlari |
| `ops.founder_time_budget` | F5_GO | optional | owner | `{weekly_minutes, measurement_method, trigger: {consecutive_weeks_over, action: simplification_adr}}` (⧗ OD-15) |
| `ops.independent_monitor_full` | F6_STEP1 | critical | technical_operator | ops.independent_monitor + host, bot va Telegram yo‘qolishi signali, alternate channel mashqi |
| `ops.ads_handback_roster` | F6_STEP1, `max_evidence_age: P7D` | critical | owner | `{pipeline: rent, custodian: person_ref, deputy: person_ref, ads_manager_access_verified_at, ack_path}` |
| `ops.sale_handback_roster` | F6_STEP2, `max_evidence_age: P7D` | critical | owner | ops.ads_handback_roster shakli, `pipeline: sale` |
| `recovery.intake_datasets` | F2_LIVE_INTAKE | critical | technical_operator | §4.1 sxemasi: intake dataset custody va RPO/RTO (sekund) — landing custody production’da (HG-F2-18 backup), outbox, AMT ingest (host yo‘qolsa landing va amoCRM’dan qayta quriladi, Q55); process va host yo‘qolishi alohida qator |
| `recovery.intake_drill` | F2_LIVE_INTAKE | critical | technical_operator | §4.1 sxemasi: landing custody’ni production Dokploy hostidagi izolyatsiyalangan restore target’ga tiklash (owner, HG-F2-18; jonli DB ustiga emas) + AMT ingest’ni lokal snapshot’dan va manbalardan qayta qurish mashqi |
| `recovery.full_datasets` | F6_STEP1 | critical | technical_operator | §4.1 sxemasi: workflow ledger va Langfuse bilan barcha dataset; lokal snapshot qamrovi; qabul qilingan host-loss doirasi (Q55) |
| `recovery.restore_check` | F6_STEP1, `max_evidence_age: P30D` | critical | technical_operator | oylik izolyatsiyalangan restore tekshiruvi (lokal snapshot sha256 + `restore_test` ga DB restore) |
| `recovery.full_drill` | F6_STEP1, `max_evidence_age: P92D` | critical | technical_operator | §4.1 sxemasi: choraklik to‘liq mashq AMT PC’dagi `restore_drill` konteynerida — lokal snapshot’dan to‘liq restore, PII’siz manba eksportidan qayta qurish (CAPI hisoblari bilan), fixture’larda kill A/B, schema-aware rollback, production `amt-kill --self-test`, production control_epoch/latch tekshiruvi va host yo‘qolishi vaqtining qismlar yig‘indisi (HG-F6-03) |
| `business.qualification` | F2_LIVE_INTAKE | critical | sales_lead | `{definition_revision, effective_from, signed_doc_ref (HG-F2-06), pipelines: {sale/rent: {qualified_status_ids, allowed_actor_user_ids, required_evidence_field_ids}}}` → `pipelines.yaml#qualified_fact_rule` |
| `sales.sop` | F2_LIVE_INTAKE | critical | sales_lead | `{working_hours, first_contact_rule, retry_rule, disposition_codes[], evidence_fields[], measured_qualification_lag: {p50_hours, p90_hours, window}, deputy: person_ref}` |
| `sales.qa` | F5_GO | critical | sales_lead | `{sample_rule, rubric_ref, accuracy_threshold, cadence, evidence_ref}` |
| `business.outcome_sources` | F5_GO | critical | owner | `[{dataset, owner: person_ref, export_or_api_ref, grain, cadence, freshness_cutoff, currency, timezone, correction_rule, contract_id_mapping}]` |
| `business.contribution_policy` | F5_GO | critical | finance_owner + owner | `{revenue_basis, variable_costs[], deposit_rule, refund_cancel_rule, installment_rule, horizon_days, ads_cost_included: bool, currency}` |
| `business.attribution` | F5_GO | critical | owner | `{measurement_revision, lookback_days, eligible_channels[], direct_visit_rule, cross_device_rule, duplicate_transfer_correction_rules}` |
| `business.baseline` | F5_GO | critical | owner | pipeline bo‘yicha `{metric_formula_ref (KC-01 baseline CPL: pooled_ratio, kill-criteria.yaml#baseline), window_weeks, seasonal_months, definition_revision, tracking_revision, coverage, maturity_horizon_days, exclusions[], source_query_ref, comparable: bool}` |
| `business.acceptance` | F5_GO | critical | owner | pipeline bo‘yicha `{targets, guardrails, denominator, min_sample, maturity_days, kc02_worse_pct, detection_latency_days, verdict_rule, outcome_band_max_relative_width, harm_margin_pct}`; `outcome_band_max_relative_width` — Trust Ramp’ga sanaladigan `expected_effect` bandining eng katta nisbiy kengligi (◇ P-42); `harm_margin_pct` — natija aytilgan yo‘nalishga teskari tomonga band’dan shu foizdan ko‘proq chiqsa `harmful` (`trust_ramp.graduation.harm_rule`, ◇ P-54); `verdict_rule` §4.1 sxemasi bo‘yicha, HG-F6-01 dan oldin oldindan ro‘yxatga olinadi (◇ P-41); bo‘sh threshold bilan GO yo‘q |
| `business.exposure` | F5_GO | critical | owner | pipeline bo‘yicha `{max_spend_minor, currency, max_elapsed_hours, bad_week_streak (KC seriyasining o‘zi, ≤ KC-01 consecutive_weeks; readiness.yaml rules.value_constraints, C-29), scale_block: true, handback_path}`; cheksiz qiymat yo‘q |
| `business.step1_comparison` | F6_STEP2 | critical | owner | `{comparison_ref, verdict_rule_revision, weeks_observed, extensions_used, kc01_evaluations: [Step 1 ning har to‘liq event_week’i uchun bittadan], cohort_maturity, verdict: sufficient/inconclusive/insufficient}`; verdict faqat pin qilingan `verdict_rule_revision` bo‘yicha |
| `sale.readiness` | F6_STEP2, `max_evidence_age: P1D` | critical | sales_lead | `{source_ref (/sale_ready yoki export), cadence, ttl, owner: person_ref, deputy: person_ref}`; snapshot maydonlari — `sale-readiness.yaml#required_fields` |
| `fleet.freshness` | F5_GO | critical | fleet_operator | `{snapshot_ttl, reporter: person_ref, deputy: person_ref, unavailable_behaviour: hold_all_ordinary_rent_budget_changes}` |
| `fleet.waitlist` | F5_GO | critical | fleet_operator | `{definition_revision, eligibility_rule, ready_rule, expiry_days, renewal_rule, fill_rule, source_rule (⧗ OD-07)}` |
| `fleet.thresholds` | F5_GO | critical | owner | `capacity-policy.yaml#parameters`: `{waitlist_high, available_high, rent_floor_daily_minor, hysteresis_days}` + kalibrlash dalili |
| `offers.initial` | F2_LIVE_INTAKE | critical | owner | `offers.yaml#example_schema` bo‘yicha revision’lar va `fact_schema` bo‘yicha faktlar (HG-F2-15) |
| `offers.asset_rights` | F2_LIVE_INTAKE | critical | owner | `[{asset_sha256, consent_ref, purpose, text_version, territory, expires_at, cleared_by: person_ref}]` (`asset_rights_clear` binding) |
| `offers.propagation` | F4_CONTENT | critical | owner | `{sla_hours_by_artifact: {ad, landing, pending_approval}, owner: person_ref, replacement_or_pause_rule}` |
| `privacy.purposes` | F2_LIVE_INTAKE | critical | privacy_owner + owner | `{purposes: [service_fulfilment, marketing_measurement], text_versions[], legal_basis_ref, transfer_basis_ref, recipients[]}` — `recipients` — `privacy-policy.yaml#off_host_flows`dagi lead ma’lumotini ochiq yoki xeshlangan holda ko‘radigan har qabul qiluvchi (kamida Cloudflare edge, amoCRM, Meta CAPI); rozilik matni ularni nomlaydi (◇ P-76) — manba sanasi bilan [D] |
| `privacy.retention` | F2_LIVE_INTAKE | critical | privacy_owner + owner | `privacy-policy.yaml#datasets` har biri uchun `{dataset, retention_days, deletion_method, withdrawal_handling, backup_expiry}` |
| `privacy.breach_response` | F2_LIVE_INTAKE | critical | privacy_owner + owner | `{recipients[], deadlines_from_law_text, legal_source_ref, retrieved_at, owner: person_ref, template_ref}` — muddat uydirilmaydi (⧗ OD-16) |
| `tracking.freshness` | F2_LIVE_INTAKE | critical | owner | manba bo‘yicha `{missing_cutoff_minutes, stale_cutoff_minutes, standalone_delivery_monitor}` |
| `tracking.thresholds` | F2_TRACKING_PASS | critical | owner | har check uchun `tracking-health.yaml#check_schema` (`unit, direction, denominator, window, min_sample, warn, fail`) + `exit_read_only.consecutive_pass_days` + `warn` qoidasi (⧗ OD-17) + 14 kunlik kalibrlash oynasi |
| `tracking.pass_7d` | F2_TRACKING_PASS | critical | owner | `{pass_dates[7], thresholds_revision, evidence_refs[]}` |
| `vendor.meta_cap` | F3_CONTROLLED_TEST | critical | owner | `{account_ref, currency, timezone, counter_basis, reset_semantics, spend_cap_set_native, readback_native, readback_at, equals_expected: true, mtd_correction_rule, host_down_evidence_ref}` (HG-F3-02) |
| `vendor.meta_access_tier` | F3_CONTROLLED_TEST | critical | technical_operator | `{app_ref, system_users: [amt-read, amt-write], access_tier, rate_limits_granted, evidence_at}` |
| `vendor.meta_capi` | F2_LIVE_INTAKE | critical | technical_operator | `{api_version_pin, events[], dataset_ref, max_event_age, send_age_margin: ISO duration (≥ clock_margin + request_timeout, daqiqalar), batch_policy: realtime_single (pin; ko‘p eventli siyosat faqat dedup_evidence_ref va owner ◇ bilan), batch_max_events: 1, request_timeout: ISO duration (soft deadline), uncertain_hold: ISO duration (hard deadline, request_timeout dan uzun, daqiqalar [?]; `uncertain` → `dropped_uncertain`), error_taxonomy_ref: pipelines.yaml#capi_delivery, vendor_error_map_evidence_ref (F2-AT-25), dedup_evidence_ref: null \| F2-AT-25 (8) dalili, dedup_rule: event_id, test_event_evidence_ref, rate_scope}` |
| `vendor.qualified_optimization` | F5_GO | critical | owner | §4.1 sxemasi |
| `vendor.meta_read_tools` | F3_CONTROLLED_TEST | critical | technical_operator | `{mcp_pin, read_allowlist[], creative_previews_only[]}` → `approval-policy.yaml#meta_read_allowlist`, `meta_read_groups` |
| `vendor.amocrm_quota` | F2_LIVE_INTAKE | critical | technical_operator | `{ceiling_rps: 7, allocations: {landing, capi-bridge, sync-worker, gateway_mcp, backfill}, cross_host_split, evidence_ref}`; Σ allocations ≤ 7 |
| `vendor.openrouter_period` | F1_COST_RUNTIME | critical | technical_operator | `{key_limit_usd, reset_period, reset_timezone, counter_semantics, boundary_fixture_ref}` |
| `vendor.runner_isolation` | F1_ISOLATION | critical | technical_operator | `{roles: {slug: {uid, unit, entrypoint, token_audience}}, adapter_versions, llm_client: {adapter: {max_retries, retry_watchdog, client_timeouts_ms}}, proxy_upstream_deadline_ms, negative_tests_ref}` — prototip |
| `vendor.runner_isolation_final` | F4_AGENTS | critical | technical_operator | vendor.runner_isolation shakli, olti rol uchun to‘liq; qiymat `all_roles_isolated` yoki (faqat ⧗ OD-05 (b) owner qarori bilan) `residual_risk_l1_l2_blocked` |
| `vendor.component_locks` | F1_ISOLATION | critical | technical_operator | `{versions_lock_ref, source_hashes, licenses, advisory_check_at}` |
| `budget.request_bounds` | F1_COST_RUNTIME | critical | owner | rol bo‘yicha (reviewer uchun model slot’i bo‘yicha: `reviewer.language`, `reviewer.policy_checklist`, ◇ P-101) `{max_cost_minor, max_input_tokens, max_output_tokens, max_concurrency, uncertain_settlement_hold_hours}` (`max_input_tokens` — harness, tool ta’riflari va tarix bilan bitta so‘rovning to‘liq input’i; narx uzun kontekstda o‘zgaradigan model uchun o‘sha chegaradan past, ◇ P-83); umumiy `cache: {min_hit_ratio}` — F1-AT-29 chegarasi, faqat xarajat modeli uchun; reservation’ga ta’sir qilmaydi, hold hech qachon cache-read narxida emas (◇ P-82, P-99); qiymatlar `budgets.yaml#openrouter.reservation_sizing` qoidalariga mos (`upper_bound_minor ≤ max_cost_minor`, `max_concurrency × upper_bound_minor ≤ ulush × (share_stop_pct − share_warn_pct) / 100`; F1-AT-30); `uncertain_settlement_hold_hours` — `uncertain` so‘rov generation yozuvi kutilib slot’ini ushlab turadigan oyna (◇ P-86); `cmo` uchun qo‘shimcha `{chat_sub_share_minor, chat_daily_messages_per_person, chat_max_session_turns}` — CMO ulushining chat qismi (workflow qismi = ulush − chat) va Hermes adapteri sanaydigan shaxs/kun va sessiya turn chegaralari (`budgets.yaml#openrouter.sub_shares.cmo`, ◇ P-89); `run_caps_minor: {<workflow_id>: integer}` — agent step’i bor har runtime workflow uchun bitta run cap’i (F1 unit-cost dalilidan; F4 cost model o‘zgartirsa yangi readiness revision; `workflow-policy.yaml#cost_caps`) |
| `budget.media` | F4_CONTENT | optional | owner | `budgets.yaml#media_generation`: `{max_cost_minor, max_video_seconds, max_video_seconds_per_month, max_concurrent_jobs}` — `max_cost_minor` va `max_video_seconds` bitta job uchun, `max_video_seconds_per_month` biznes oyidagi barcha job’lar, `max_concurrent_jobs` bir vaqtdagi barcha media job’lari; job bitta reservation (`media_generation` egaligida) va kalit, media ulushi hamda so‘ragan agent ulushida bitta tranzaksiyada tekshiriladi (`attribution`, ◇ P-90); N/A = media o‘chiq |
| `budget.anomaly` | F5_GO | critical | owner | `{hourly_spend_anomaly_minor, loop_detector: {max_calls, window_minutes}}` |
| `budget.ads_pacing` | F5_GO | critical | owner | §4.1 sxemasi |
| `budget.ads_limits` | F5_GO | critical | owner | `{safety_margin_minor → ads.safety_margin_minor, account_currency, fx_policy: {source, date_rule, conservative_rounding}, pipeline_split, headroom_alert_levels, min_interval_hours}`; `min_interval_hours` — bitta entity’da ketma-ket budget increase’lar orasidagi eng kichik vaqt (`approval-policy.yaml` `change_set.change_spacing`, ◇ P-43) |
| `budget.ads_fresh_check` | F6_STEP1, `max_evidence_age: P1D` | critical | owner | `{readback_native, readback_at, verified_mtd_minor, headroom_minor, checked_by: person_ref}` |
| `budget.tco` | F5_GO | critical | owner | §4.1 sxemasi: host (owner PC, ikkinchi disk, UPS, Omada controller), elektr va ofis interneti, monitor, litsenziya, inson vaqti, kredit to‘lovlari/soliq/FX; Meta sarfi alohida |
| `models.assignments` | F5_GO | critical | owner | rol bo‘yicha `{adapter, model_id, provider, prompt_sha, tool_schema_sha, skill_shas, eval_ref, measured_cost_minor}` + `reviewer.language`, `reviewer.policy_checklist` + Jev pre-screen pin (Q61); fallback yo‘q |
| `models.pre_screen` | PRE_SCREEN | critical | owner | `{eval_ref (F5-AT-14), per_check_language: {recall, false_flag_rate}, thresholds, scope: uz_ru/ru_only, model: typesafe/jev-1.14, served_snapshot}` — Jev pre-screen F5 eval natijasi, chegara, scope va tasdiqlangan snapshot; approved bo‘lmasa pre-screen o‘chiq, Reviewer avvalgidek ishlaydi (Q61) |
| `config.closure` | F5_GO | critical | owner | `{manifest_digest, validation_ref, active_ack_ref, profiles_pass[]}` |
| `workflow.mechanism` | F1_WORKFLOW | critical | technical_operator | `{mechanism: amt_ledger/paperclip/combined, prototype: {restart, timer, handoff, replay, divergence}, adr_ref}` (WORKFLOW_TESTS runtime capability testlari) |
| `workflow.recovery` | FE_RELEASE | critical | technical_operator | `{process_loss: {rpo_seconds, rto_seconds}, host_loss_scope: accepted_loss_Q55, rebuild_ref, checkpoint_evidence_ref, migration_drill_ref}` — host yo‘qolishida ledger yo‘qoladi, unga RPO/RTO berilmaydi |
| `engineering.budget` | FE_SANDBOX | optional | owner | `engineering-budget.yaml`: `{currency, period, cap_minor, per_proposal_max_minor, max_parallel_candidates, token_or_wall_time_limits}`; N/A = pullik engineering o‘chiq (⧗ OD-02) |
| `engineering.llm_access` | FE_SANDBOX | optional | owner | `{funding_option (engineering-budget.yaml#options_for_owner_decision), identity_ref, key_custody_ref, ledger_scope: engineering}`; N/A = faqat qo‘lda engineering (⧗ OD-02) |
| `capacity.sandbox_host` | FE_SANDBOX | critical | technical_operator + owner | `resource-policy.yaml`: `{production_reserve, sandbox_limits, measurement_ref}` — AMT PC’dagi build/test yuklamasi; alohida host — owner pul gate’i |
| `verification.custody` | FE_RELEASE | critical | owner | `{suite_digest, holdout_digest, storage_ref, verifier_credential_ref, author_read_access: none}` (HG-FE-02) |
| `engineering.independent_reviewer` | FE_RELEASE | critical | owner | `{person_ref, scope: protected_surfaces, response_time}` yoki `class_e_frozen` (owner imzosi; E sinfi release’lar F7 gacha rad) (⧗ OD-12); `class_e_frozen` Q67 bo‘yicha majburiy FE_RELEASE o‘rniga qabul qilinmaydi; F5_GO yopilmasidagi cheklov ham saqlanadi (C-28, `rules.value_constraints`) |
| `release.scope_observation` | FE_RELEASE | critical | owner | `{default: owner_release, classes: {A..E: {observation_scope, window, stop_rules}}}` |
| `evolution.outcome_policy` | FE_RELEASE | critical | owner | `{baseline_rule, measurement_revision_rule, guardrails, min_sample, maturity, max_observation_days, inconclusive_rule}` |
| `auto_release.decision_ref` | AUTO_RELEASE_ENABLE | critical | owner | `{decision_q_id (Q11 ni o‘zgartiradi), allowed_classes, allowed_paths, ttl_days}`; hech qachon N/A emas — qaror bo‘lmaguncha profil o‘tmaydi va auto-release yopiq (⧗ OD-03) |
| `evolution.fe_acceptance` | AUTO_RELEASE_ENABLE | critical | owner | `{fe_technically_accepted_ref, evo_at14_result_ref}` (`evolution-policy.yaml#promotion.auto_release.blocked_until`) |

## 5. Holat lug‘ati (STATE_VOCABULARY)

Bitta tushuncha uchun bitta lug‘at. Data va config’da enum qiymati aynan config’dagidek yoziladi (test va readiness natijalari kichik harf bilan); `PASS`, `NOT_RUN` kabi KATTA harf faqat ko‘rinishda (hisobot, Telegram, hujjat holat qatori).

| Lug‘at | Qiymatlar | Machine manba | Qoida |
|---|---|---|---|
| Delivery lifecycle (faza, release, upgrade candidate) | `specified → implemented → verified_in_staging → merged → released → deployed → observed → technically_accepted → business_accepted`; yakun: `rejected`, `inconclusive`, `rolled_back`, `cancelled`, `not_applicable` | `evolution-policy.yaml#outcome.lifecycle`, `terminal` | Sof infra/security o‘zgarishida `business_accepted` texnik va zarar yo‘qligi dalili bilan `not_applicable` bo‘lishi mumkin |
| Test va dalil natijasi | `not_run`, `pass`, `fail`, `blocked`, `inconclusive` | [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) dalil yozuvi | `inconclusive` faqat biznes yoki statistik test uchun |
| Readiness | `pending`, `evidenced`, `approved`, `not_applicable` | `readiness.yaml#record_states` | §2 |
| Global write_mode | `shadow`, `enabled`, `read_only`, `killed` | `execution-policy.yaml#global_modes` | “Locked” = `killed` yoki `shadow`+L0; enum emas |
| Pipeline rejimi va trust darajasi | `L0_shadow`, `L1_approve_each`, `L2_auto_within_guardrails` | `execution-policy.yaml#pipeline_modes`, `approval-policy.yaml#trust_ramp` | Effektiv = `min(global_mode, pipeline_mode, trust_level)`; trust faqat L1↔L2 |
| Kill rejimi | `A`, `B` | `execution-policy.yaml#kill_modes` | Default `A` |
| Command state | `pending_review`, `pending_approval`, `approved`, `claimed`, `executing`, `succeeded`, `rejected`, `expired`, `cancelled`, `failed_confirmed`, `uncertain`, `reconciling`, `manual_resolution`, `awaiting_manual`, `done_manual` | `execution-policy.yaml#command_states`, `extra_transitions` | INVARIANTS I05 |
| Approval qarori | `approve`, `reject`, `edit_decrease`, `expire` | `approval-policy.yaml#change_set.decisions` | TTL `presented_at`dan 12 soat |
| Intake receipt | `accepted → crm_pending → crm_confirmed`; `uncertain`; `needs_review` | DATA_MODEL intake | Intake `accepted` faza yoki upgrade qabuli bilan aralashtirilmaydi |
| Workflow run | `created`, `running`, `waiting`, `blocked`, `reconciling`, `completed`, `failed`, `cancelled`, `manual_resolution` | `workflow-policy.yaml#run_states` | Run, step, command va vendor holati bir-birini almashtirmaydi |
| Workflow step | `pending`, `ready`, `claimed`, `running`, `waiting`, `handoff_pending`, `completed`, `rejected`, `failed`, `skipped`, `cancelled`, `compensated` | `workflow-policy.yaml#step_states` | — |
| Handoff | `offered`, `accepted`, `rejected`, `expired` | `workflow-policy.yaml#handoff_states` | Assignment yoki mention qabul emas |
| Run biznes natijasi | `pending`, `met`, `not_met`, `inconclusive`, `not_applicable` | `workflow-policy.yaml#business_outcomes` | — |
| Command outcome (`command_outcomes`) | `met`, `not_met`, `inconclusive` (+ `data_status`) | `approval-policy.yaml#trust_ramp.graduation` | Trust Ramp faqat `met`ni sanaydi; `inconclusive` toza emas (◇ P-04) |
| Upgrade verdict | `accepted`, `rejected`, `inconclusive` | `evolution-policy.yaml#outcome.verdicts` | `inconclusive` scale yoki avtonomiyaga ruxsat bermaydi |
| Tracking check | `pass`, `warn`, `fail`, `unknown`, `stale`, `low_n`, `not_applicable` | `tracking-health.yaml#check_states`, `streak_rules` | Streak faqat `pass`ni sanaydi; `fail`, `unknown`, `stale`, `low_n` uni uzadi; `warn` ⧗ OD-17; `not_applicable` faqat owner tasdiqlagan check uchun |
| `data_status` | `valid`, `no_activity`, `no_spend`, `spend_zero_qualified`, `insufficient_sample`, `not_mature`, `incomparable_baseline`, `missing_data`, `stale_data` | `business-policy.yaml#data_status_values` | Ta’rif — [BUSINESS_CONTRACT](BUSINESS_CONTRACT.md) §8.2; harakat — `kill-criteria.yaml#data_status_actions` |
| Reviewer check | `pass`, `fail`, `needs_owner`, `n_a` | Reviewer verdict sxemasi | Birorta `fail` → `fail`; birorta `needs_owner` → `needs_owner`; injection urinishi → `fail` |
| O‘zgarish sinfi | `A_content`, `B_code`, `C_workflow_harness`, `D_schema_migration`, `E_protected_surface` | `evolution-policy.yaml#change_classes` | [EVOLUTION_CONTRACT](EVOLUTION_CONTRACT.md) §4 |
| Release sinfi | `normal`, `recovery` | `release-policy.yaml#release_classes` | `killed` paytida faqat `recovery`: manifest’da e’lon qilingan, faqat containment, reconciliation yoki oldin tekshirilgan release’ni tiklaydi |
| Alert severity | `critical`, `degraded` | `operations.yaml#severities` | ACK muddati `ops.ack_minutes` |
| Offer status | `draft`, `active`, `paused`, `expired`, `revoked` | `offers.yaml#example_schema` | — |
| F5 biznes asosi | `sufficient`, `inconclusive`, `insufficient` | F5 go/no-go | `sufficient` bo‘lmasa F6 faqat exposure ichida rent L1; Step 2 avtomatik emas |

Faza ledger’i lifecycle’ga quyidagicha bog‘lanadi:

| Faza holati | Lifecycle qiymati |
|---|---|
| Boshlanmagan, reja va AT yozilgan | `specified` |
| Build tugagan | `implemented` |
| Isolated/staging testlari PASS | `verified_in_staging` |
| Owner merge qilgan (HG-GIT-01) | `merged` |
| Owner release qilgan (HG-REL-01) | `released` |
| Host’da faol | `deployed` |
| Kuzatuv oynasi dalil bilan yopilgan | `observed` |
| Barcha AT va HG yopilgan | `technically_accepted` |
| Biznes dalili bor (yoki asosli `not_applicable`) | `business_accepted` |

“Faza accepted” = `technically_accepted` ∧ (`business_accepted` ∨ uning asosli N/A’si) ∧ faza HG/AT va kuzatuv oynalari yopilgan.

## 6. Semantic rad etish va validator

### 6.1 Runtime loader

Builder yozadigan typed loader quyidagilarni rad etadi: noma’lum enum, rol, action, tool yoki profil; duplicate key; bo‘sh required reyestr; float yoki manfiy pul; currency chalkashligi; `openrouter.shares_minor` yig‘indisi `key_hard_cap_minor`ga teng emas; AI kalit cap’i 15 000 minor’dan yoki paid Meta cap’i 150 000 minor’dan farq qiladi; `ads.provider_spend_limit_required` `true` emas; `amocrm_global_rps_ceiling` null yoki 7 dan katta; NEVER_AUTO zaiflashishi; timeout’da avto-tasdiq; noto‘g‘ri hold/resume (restore `killed`dan boshqa rejimda boshlanadi, released entity owner takeover’siz qaytadi, global `shadow` yoki `read_only` sababsiz ochiladi); eskirgan approval; pipeline’lar streak’ini aralashtirish; `auto_release.enabled: true` owner qarori ref’isiz. Code/config/schema mosligi va faol servis ACK’i tekshiriladi; yarim yangi policy bilan write bajarilmaydi. Xatoda oldingi mos revision yoki safe mode saqlanadi.

### 6.2 Bundle validator

[validate_bundle.py](../12_Acceptance/validate_bundle.py) quyidagilarni tekshiradi:

- profil DAG merosi va noma’lum profil nomlari;
- har kalitda bitta gate;
- `criticality` va `not_applicable` qoidalari;
- `accountable_role`, `prepared_by` va `approved_by` qoidalari (§2);
- config’lar orasidagi exact-value invariant assert’lari;
- Q25 ceiling (7; null yoki undan katta qiymat — fail);
- pul cap’lari (15 000 va 150 000 minor, ulushlar yig‘indisi);
- enum lug‘atlari (§5);
- har FR, NFR va invariant uchun keltirilgan test ID’larining mavjudligi;
- HG ID’larining mavjudligi;
- lokal havolalar va heading anchor’lari;
- versiya qoldig‘i grep’i;
- `12_Acceptance/fixtures/` dagi negativ fixture’lar (har biri fail berishi shart).

Validator PASS — hujjat va shablon yaxlitligi; u runtime yoki gate PASS emas. Runtime testlari dalil bilan yopilguncha `not_run` bo‘lib qoladi.

## 7. Sirlar, runtime rollar va muhitlar

Secret qiymatlar sops+age’da; har servis faqat o‘z credential faylini oladi (`runtime-isolation.yaml#services.credential_file`), umumiy `.env` barcha servisga berilmaydi; `env.example` faqat nomlarni servis bo‘limlari bo‘yicha beradi. Credential inventari, muddati, egasi va rotatsiya qadamlari (sops → render → ACK, T-30/T-7/T-1 alertlar) — `ops.credential_inventory`. Readiness dalillari PII’siz reference. Runtime rollar manbai — DB (`amt.people`, `amt.roles`); `roles.yaml` faqat bir martalik seed (`export_must_not_reseed: true`, `release-policy.yaml#roles_reload: never_reseed_runtime_DB`). Test, staging va sandbox resurslari `environments.yaml` da; `must_not_intersect_with_prod` ro‘yxatidagi har resurs prod bilan kesishsa bundle rad etiladi.
