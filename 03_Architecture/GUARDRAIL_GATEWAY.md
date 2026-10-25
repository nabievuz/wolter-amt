# GUARDRAIL GATEWAY — agent tool’lari ijro shartnomasi

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

`gateway` — agentlar tashqi dunyoga chiqadigan yagona eshik: `services/gateway`, UID `amt-gateway`, `127.0.0.1:3300` ([runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) `services`). Gateway’da Meta write kaliti yo‘q: Meta write faqat `amt-executor` chegarasida, amoCRM credential faqat `amt-amo` connector’ida, OpenRouter kaliti faqat `amt-proxy`da. Kanonik manbalar: tool allowlist va action’lar — [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml); command holati, kill/resume va capability profillari — [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml); pul — [budgets.yaml](../09_Config_Templates/budgets.yaml); state va birliklar — [INVARIANTS](../11_Production_Contracts/INVARIANTS.md); schema — [DATA_MODEL](DATA_MODEL.md); kill tartibi — [SECURITY §6](SECURITY.md). Qaror belgilari: ✅ owner qarori (Q-ID), ★ owner qabul qilgan builder standarti, ◇ P-NN owner ko‘rib chiqishini kutayotgan taklif, ⧗ OD-NN ochiq owner qarori. Bu hujjat runtime tayyorligi da’vosi emas.

## 1. Kirish, identity va tool ko‘rinishi

Har agent alohida UID, workspace va credential bilan ishlaydi: CMO `hermes`, qolgan beshta rol `agent-*` UID’larida (`runtime-isolation.yaml` `agents`). Root egaligidagi managed runner har run uchun 256-bit tasodifiy gateway tokenini (`GW_TOKEN`) beradi ★. Gateway tokenning o‘zini emas, faqat hash’ini saqlaydi (`GATEWAY_AGENT_TOKEN_HASHES_FILE`) va uni server tanlagan `agent_id`, peer UID, run audience (`AMT_RUN_AUDIENCE`) va ruxsatlangan purpose bilan bog‘laydi. Agent so‘rovidagi `agent_id`, `requested_by`, run ID yoki cost attributsiyasi ishonch manbai emas: bu maydonlarni server token egasidan qo‘yadi. Kill’da va credential rotatsiyasida (`ops.credential_inventory`) agent tokenlari bekor qilinadi; eski token darhol `unauthorized` oladi. `paperclip` orkestratorida vendor, agent yoki Reviewer tokeni yo‘q.

Har agent sessiyasining MCP konfiguratsiyasida faqat `amt-gateway` serveri bor; `claude_local` adapterida `--strict-mcp-config` bilan [D: Claude Code CLI hujjati; F4-AT-03 tekshiradi]. Hermes o‘z MCP client’i bilan ayni endpoint’ga o‘z tokeni orqali ulanadi. Transport — Streamable HTTP yoki pinned adapter’ning autentifikatsiyalangan lokal transporti; endpoint faqat `127.0.0.1`da, Caddy orqali tashqariga chiqarilmaydi.

`tools/list` faqat shu principal allowlist’ini (§2) qaytaradi. Ro‘yxatda yo‘q tool’ni nom bilan to‘g‘ridan-to‘g‘ri chaqirish ham `tool_not_allowed` va audit. `meta_read.*` vendorning barcha tool’i degani emas: u `approval-policy.yaml` `meta_read_allowlist`dagi concrete read tool’larga kengayadi (readiness `vendor.meta_read_tools`); `meta_read.creative_previews_only` — `meta_read_groups.creative_previews_only` guruhi. Allowlist to‘ldirilganda har concrete read tool o‘z argument sxemasini oladi (`schemas/tools/<tool>.schema.json`, G10). Nom va annotation ikkalasi tekshiriladi; write annotatsiyali tool yoki Lead Ads lead/PII tool read kanalga kirmaydi; javobdan token, billing va Lead Ads ma’lumoti filtrlanadi. Agentga tashqi kalit qaytmaydi.

Run konteksti (Paperclip run/issue ID, workflow `run_id/step_id`) server tomonda solishtiriladigan qo‘shimcha dalil; UID chegarasining o‘rnini bosmaydi; mos kelmasa `unauthorized` va anomaly audit. Ichki servislar (ops-bot, tg-auth, capi-bridge, llm-proxy, amt-control, amt-workflow) gateway bilan per-caller Unix socket peer UID yoki per-caller HMAC kaliti (`INTERNAL_HMAC_KEYS_FILE`) orqali gaplashadi; hammaga umumiy service credential yo‘q (F3-AT-22). Runner mexanizmi F1’da `vendor.runner_isolation`, F4’da `vendor.runner_isolation_final` bilan [SECURITY §2](SECURITY.md) bo‘yicha isbotlanadi; writer/Reviewer process izolyatsiyasi F4_AGENTS uchun talab (◇ P-07), imkonsiz bo‘lsa ⧗ OD-05.

## 2. Agent × tool vakolati

| Agent | UID | Ruxsatlangan tool’lar (`approval-policy.yaml` `agents.<slug>.tools`, config tartibida) |
|---|---|---|
| `cmo` | `hermes` | `meta_read.*`, `wh.metrics`, `wh.query`, `fleet.read_utilization`, `offers.read`, `offers.propose_pr`, `analytics.umami_query`, `report.submit`, `change_set.propose_manual`, `evo.signal.submit`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker`, `workflow.start` |
| `media-buyer` | `agent-media-buyer` | `meta_read.*`, `meta_write.pause_entity`, `meta_write.activate_entity`, `meta_write.update_budget`, `meta_write.create_campaign_paused`, `meta_write.create_ad_from_creative`, `meta_write.duplicate_adset`, `meta_write.upload_creative_asset`, `wh.metrics`, `wh.query`, `fleet.read_utilization`, `offers.read`, `drive.get_asset`, `evo.signal.submit`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker` |
| `creative-studio` | `agent-creative-studio` | `drive.list_raw`, `drive.get_asset`, `media.generate_image`, `media.generate_video`, `render.html_to_png`, `render.video_template`, `offers.read`, `wh.metrics`, `creative.register`, `meta_read.creative_previews_only`, `evo.signal.submit`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker` |
| `cro` | `agent-cro` | `offers.read`, `offers.propose_pr`, `landing.open_pr`, `wh.metrics`, `wh.query`, `analytics.umami_query`, `analytics.clarity_export`, `media.generate_image`, `evo.signal.submit`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker`, `workflow.start` |
| `funnel-analyst` | `agent-funnel-analyst` | `meta_read.*`, `amo.read_leads`, `amo.read_pipelines`, `amo.read_events`, `amo.write_tags`, `amo.write_fields`, `wh.query`, `wh.metrics`, `analytics.umami_query`, `analytics.clarity_export`, `fleet.read_utilization`, `offers.read`, `landing.open_pr`, `change_set.record_outcome`, `change_set.propose_manual`, `experiment.create`, `experiment.update`, `experiment.close`, `report.submit`, `evo.signal.submit`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker`, `workflow.start` |
| `reviewer` | `agent-reviewer` | `offers.read`, `drive.get_asset`, `meta_read.creative_previews_only`, `review.get_subject`, `review.submit_verdict`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker` |

Bu jadval `approval-policy.yaml` `agents.<slug>.tools`ning aynan nusxasi. Validator (D14) GUARDRAIL §2 va config’ni har agent bo‘yicha to‘plam sifatida solishtiradi; farq bo‘lsa bundle rad etiladi. F4-AT-17 qo‘shimcha lint’lari: D13 (charter tool jadvali = config), D16 (charter/prompt matni faqat o‘z tool’larini nomlaydi), D15 (skill’ning `Tool scope` jadvali — rol faqat o‘zi ushlaydigan va skill’ni yuklaydigan tool’ga yo‘naltiriladi). Engineering rollari (`eng-planner`, `eng-architect`, `eng-implementer`, `eng-verifier`) biznes tool’larini olmaydi (I20).

Tor cheklovlar: `cro` uchun `media.generate_image` faqat landing vizual eskizlari; jonli landing’da ishlatishdan oldin rights va Reviewer pass (`tool_constraints`). `landing.open_pr`: CRO faqat `content/**` (generated `content/offers.snapshot.json` deny), Funnel Analyst faqat `tracking/**` (`landing_pr_paths`); boshqa yo‘l `policy_violation`.

`internal_auto_tools` — `creative.register`, `change_set.propose_manual`, `review.get_subject`, `review.submit_verdict`, `change_set.record_outcome`, `experiment.create`, `experiment.update`, `experiment.close`, `evo.signal.submit`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker`, `workflow.start` — gateway orqali, tashqi effektsiz va audit bilan ishlaydi; ular inson approval’i emas (§9)

Creative oqimi: Creative Studio kreativni yaratadi → `creative.register` immutable revision → Reviewer exact subject’ni `review.get_subject` bilan oladi (`models.pre_screen` approved bo‘lsa Jev pre-screen natijasi bilan, §9.2) va `review.submit_verdict` beradi → policy talab qilsa inson til tekshiruvi ([TELEGRAM §2.3](TELEGRAM.md)) → Media Buyer tasdiqlangan nusxa bo‘yicha `meta_write.upload_creative_asset` va `meta_write.create_ad_from_creative` taklif qiladi. Creative Studio’da Meta write yo‘q; Reviewer muallif nomidan yozolmaydi va subject’ni o‘zgartira olmaydi.

### 2.1 Paperclip bridge

Agentlarning Paperclip control-plane vakolati gateway’dagi bridge orqali, `runtime-isolation.yaml` `paperclip_bridge` bo‘yicha. Ruxsat: `issue.create`, `issue.assign`, `issue.comment`, `issue.status`, `document.attach`, `issue.read_assigned_or_linked`. Rad: `agent.hire`, `agent.create`, `agent.update`, `instructions.update`, `adapter.update`, `model.update`, `budget.update`, `routine.create`, `routine.update`, `approval.request`. F4’da har rol uchun rad etilgan amallar salbiy test bilan sinaladi. Paperclip issue matni yoki izohi approval, Reviewer verdict yoki workflow holati emas (I16); step natijasi faqat `workflow.submit_output` orqali qaytadi ([WORKFLOW_RUNTIME §4](WORKFLOW_RUNTIME.md)).

## 3. Guard tartibi va xato kodlari

Bitta shared policy implementation ikki entrypoint’da ishlaydi: ingress (agent tool chaqiruvi yoki proposal) va dispatch (executor claim’dan oldin, har retry va rollback’da). Guard’lar quyidagi tartibda tekshiriladi; birinchi rad qiluvchi guard’ning kodi qaytadi va audit yoziladi. `shadow` belgisi rad emas: qolgan guard’lar baribir ishlaydi, shadow taklif jonli taklif bilan bir xil tekshiriladi va javob `status: shadow` bo‘ladi. Proposal’dagi tekshiruv dispatch’dagi tekshiruvni almashtirmaydi.

| # | Guard | Tekshiriladigan holat va manba | `error_code` | Bosqich |
|---|---|---|---|---|
| 1 | Identity | token hash, peer UID, audience, purpose; agent pauzada emas (`agent_runtime_state`, watchdog/control) | `unauthorized`, `agent_paused` | ingress; dispatch’da servis identity va command muallifi |
| 2 | Allowlist | tool `agents.<slug>.tools`da; `tool_constraints`, `landing_pr_paths` | `tool_not_allowed`, `policy_violation` | ingress |
| 3 | Kvota | agent ≤60 chaqiruv/daqiqa ★ (`rate_limits.per_agent_calls_per_minute`); amoCRM — barcha caller uchun ✅ Q25 ceiling 7 req/s ichidagi tasdiqlangan ajratma (`vendor.amocrm_quota`); Meta throttle holati (§6.3) | `rate_limited` | ingress, dispatch |
| 4 | Argument va qiymat | strict schema — har allowlist tool’ining nomlangan argument sxemasi `09_Config_Templates/schemas/tools/<tool>.schema.json` (Draft 2020-12, `additionalProperties: false`, umumiy turlar `_common.schema.json`; release manifest’ida `tool_schema_digest`; validator G10; `format` faqat annotation — har satr `maxLength` va kerak bo‘lsa `pattern` bilan chegaralangan, har massiv `items` va `maxItems` bilan, `wh.query` qiymatlari va `limit` (≤ 5000) chegaralangan, `workflow.start` har workflow uchun aniq input maydonlari bilan yopiq, render parametrlari ruxsat etilgan belgilar to‘plamidan, currency F3 da ad account valyutasidan const qilinadi); pul faqat integer `*_minor` + currency; scoped ID; erkin matn ≤2000 belgi (◇ P-30), boshqaruv belgilarisiz; UTM/tag/URL/metadata qiymat sanitizatsiyasi; erkin matn hech qachon buyruq emas; qiymat darajasidagi PII yoki sir | `invalid_args`, `pii_blocked` | ingress, dispatch |
| 5 | Revision readiness | faol code/config/schema bundle va kerakli servis ACK’lari bir xil; capability o‘z gate’idan o‘tgan (release manifest’i yoki `control_events`) va profil kalitlarining amaldagi tasdig‘i kuchda (`execution-policy.yaml` `capability_requires_profile`; `readiness.yaml#rules`: `pass_persistence`, `operational_validity`); majburiy readiness yopiq | `readiness_blocked` | ingress, dispatch |
| 6 | Global `write_mode` | `killed` → normal write, LLM va media rad; `read_only` → mutatsion tool rad, sabab bilan; `shadow` → `shadow` belgisi. F3 nazoratli testi: owner tasdiqlagan PAUSED `origin=test` fixture (HG-F3-03) uchun oldindan belgilangan non-activation amal faqat F2 tracking gate o‘tgandan keyin (F2_TRACKING_PASS → F3_CONTROLLED_TEST, ✅ Q37) va `shadow`da bajarilishi mumkin; `killed`/`read_only`da istisno yo‘q; test obyektda har qanday activation `policy_violation`. `protective_pause` bu guard’dan mustasno (§6.4) | `write_mode_killed`; `tracking_gate` (`reason=read_only:<sabab>`); shadow → `pipeline_shadow` | ingress, dispatch |
| 7 | Pipeline va trust | effective daraja = `min(global_mode, pipeline_mode, trust_level)` (§4); L0 → `shadow` belgisi; `shared` = `min(sale, rent)` | `pipeline_shadow` | ingress, dispatch |
| 8 | Ownership va activation turi | `(account, entity_type, id)` `managed_entities`da, pipeline mos, `released_at` yo‘q; activation turini agent emas, gateway `entity_type + ever_active + origin`dan aniqlaydi (§8) | `foreign_entity` | ingress, dispatch |
| 9 | Remote state va revision | joriy remote version kutilgan state bilan mos; payload, offer, creative, review, asset, human check, role, policy revision va `control_epoch` amalda | `state_drift`, `revision_stale` | ingress, dispatch |
| 10 | Offer, rights va review | narx/da’vo faol offer revision’ida; asset rights `cleared`; `review_required: true` action uchun mustaqil Reviewer `pass` aynan shu `subject_hash`ga; birinchi 20 copy doirasida inson til tekshiruvi (§9.7). Ingress’da review hali yo‘qligi rad emas — item `pending_review`ga boradi; dispatch’da hammasi majburiy | `offer_mismatch`; `policy_violation` (`reason=review_fail` / `rights_not_cleared` / `human_check_missing`); `needs_owner` | ingress (offer/rights), dispatch (hammasi) |
| 11 | Tracking va freshness | F2 tracking gate o‘tgan (HG-F2-08, F2_TRACKING_PASS) — har Meta write uchun, F3 `origin=test` fixture ham shu jumladan (✅ Q37); kerakli check va source’lar `tracking.freshness` ichida; missing/stale manba risk oshiruvchi dispatch’ni darhol bloklaydi | `tracking_gate` (`reason=gate_not_passed` / `stale_source`) | ingress, dispatch |
| 12 | Capacity, sale va biznes natija | rent: bugungi valid fleet snapshot (capacity hold); sale increase va rent→sale ko‘chishi (F6_STEP2 dan): `valid_until`i o‘tmagan sale readiness snapshot’i (`sale-readiness.yaml`, qoidasi `sale.readiness`); har budget increase: biznes natija guard’i — KC-02 trigger faol bo‘lsa yoki `v_lead_to_contract` `data_status` `valid` bo‘lmasa increase rad (`actions.budget_change.business_outcome_guard`); eksperiment lock’i — pipeline’da eksperiment ishlayotganda uning arm’laridan tashqari increase, kreativ almashuvi va struktura o‘zgarishi rad, kamaytirish va pauza ochiq (`change_set.experiment_lock`, ◇ P-43) | `readiness_blocked` (`reason=capacity_hold` / `sale_readiness` / `business_outcome_guard` / `experiment_lock`) | ingress, dispatch |
| 13 | Pul | rolling24h harakat; bitta entity yoki uning parent’ida ketma-ket budget increase’lar orasida `budget.ads_limits.min_interval_hours` (`change_set.change_spacing`, ◇ P-43; `reason=min_interval`); oylik commitment admission; provider spending limit tasdiqlanmagan (`vendor.meta_cap` amaldagi tasdig‘i yo‘q) yoki read-back mos emas (`provider_limit_read_only` faol, §7) | `budget_change_exceeds_limit`, `monthly_cap_exceeded`, `readiness_blocked` (`reason=vendor.meta_cap`), `tracking_gate` (`reason=read_only:provider_limit`) | ingress, dispatch |
| 14 | Vakolat va marshrut | `review_required: true` → `pending_review`; L1 → `pending_approval`; L2 → policy approval faqat graduation’dan keyin; approver rol/flag/expiry/attestation joriy holatda; owner-only action yoki yetarsiz rol → owner navbati; action `cases` generik case’dan oldin aniqlanadi — oxirgi pauzasi `protective_actions` yozuvi bo‘lgan entity’ni qayta yoqish (`entity_activate`/`creative_activate`, case `re_activation_after_protective_pause`) faqat owner navbatiga boradi, ads_approver ham, L2 policy approval ham uni tasdiqlay olmaydi (never_auto) | marshrut `needs_owner` (202) | ingress; dispatch’da approval hozir ham yaroqli |
| 15 | Audit durability | intent, attempt, outbox va audit yozilishi mumkin; yozilmasa tashqi write yo‘q (fail-closed) | `readiness_blocked` (`reason=audit_unavailable`) | ingress, dispatch |

Dispatch’da bulardan keyin executor’ning lokal epoch barrier’i ishlaydi (§6.1): latch yopiq yoki epoch eskirgan bo‘lsa `write_mode_killed`.

`killed` normal write, LLM va media dispatchni yopadi. Davom etadigan yo‘llar faqat `execution-policy.yaml` `kill_allows`dagilar: `protective_pause` (pause-only), CAPI delivery, landing CRM delivery, notification va ACK. `amo.write_*` va GitHub PR tool’lari (`landing.open_pr`, `offers.propose_pr`) epoch tekshiruvi bilan rad (`kill_rejects`: `amo_write`, `github_write`); writer klasslari jadvali [SECURITY §6](SECURITY.md)da. `read_only` mutatsion tool’larni yopadi; faol Meta reklamasi o‘zi pauza bo‘lmaydi. Global `shadow` yoki L0’dagi taklif faqat shadow intent: mode keyin ochilsa ham eski shadow item ijro qilinmaydi va TTL’da `expired` bo‘ladi.

## 4. Mode, pipeline va Trust Ramp

### 4.1 Global `write_mode`

| Mode | Kim yoki nima yoqadi | Natija |
|---|---|---|
| `shadow` | F5 real shadow; restore’dan keyin reconcile tugagach owner qadami (◇ P-16) | proposal va hisobot bor; normal tashqi dispatch yo‘q |
| `enabled` | owner; capability `write_mode.enabled` uchun `F6_STEP1` profili PASS; rejali release oynasidan keyin `amt-release` `maintenance_release` bilan hold o‘zgartirgan o‘lchovlarni tiklaydi (oynada yoqilgan himoya nazoratlari qoladi) | barcha guard ichida ijro mumkin |
| `read_only` | tracking’da ikki ketma-ket fail kun (`tracking_read_only`); `maintenance_hold`; provider spending limit yo‘q yoki read-back mos emas (`provider_limit_read_only`, §7.2); account cheklovi (`account_restricted_read_only`, §6.3). Owner `read_only`ni bevosita yoqmaydi: u `shadow`ga qaytaradi yoki kill qiladi (`global_mode_change.scope`) | o‘qish ishlaydi; normal write yo‘q; `protective_pause` ruxsat |
| `killed` | owner kill (`/pause_all` yoki SSH `amt-kill`); restore har doim shu holatdan boshlanadi (◇ P-16) | lokal containment; normal write/LLM/media deny; recovery owner-only; release faqat `release_class: recovery` (`release-policy.yaml#release_classes`) |

"Locked" — operatsion atama: `killed` yoki `shadow`+L0; alohida enum emas.

### 4.2 Pipeline rejimi va trust o‘qi

`pipeline_modes`: `sale` va `rent` alohida `L0_shadow`, `L1_approve_each` yoki `L2_auto_within_guardrails`; boshlang‘ich holat `L0_shadow`. L0↔L1 va L1↔L2 faqat owner `pipeline_mode_change` bilan (`/mode`, typed code; binding: pipeline, from/to, evidence_ref, policy_revision). L1 ochilishi capability profiliga bog‘liq: `pipeline.rent.L1` → `F6_STEP1`, `pipeline.sale.L1` → `F6_STEP2`. L2 rejimi faqat L1 dan va `pipeline.any.L2` → `L2_ENABLE` PASS bilan ochiladi; pipeline L2 bo‘lishining o‘zi hech bir action’ni avtomatlashtirmaydi — action_type × pipeline darajasini alohida `trust_graduation` (trust o‘qi) belgilaydi. Avtomatik o‘zgarish faqat xavfsiz tomonga: KC-01 → shu pipeline L0 (`kill_criteria_l0`), journal’siz restore → barcha pipeline L0.

Trust o‘qi (`trust_ramp.axis`): `trust_levels` trust kaliti bo‘yicha (action_type × pipeline; `budget_change` uchun × direction, ◇ P-55) faqat L1↔L2 orasida o‘zgaradi; L0 faqat pipeline rejimi yoki global `shadow`dan keladi. Effective daraja `min(global_mode, pipeline_mode, trust_level)`: global `shadow` L0 ga teng, `enabled` cheklov qo‘shmaydi, `read_only`/`killed`da normal write yo‘q. Shu sababli F6 Step 1’da `write_mode=enabled`, rent L1 va trust L1 bo‘lsa rent effective L1; sale L0 bo‘lsa sale taklifi shadow. ✅ Q08 dagi avtomatik daraja (L2) uchun ikkalasi kerak: pipeline rejimi L2 (`/mode <pipeline> L2`) va shu action_type’ning trust darajasi L2 (`/graduate`). `shared` pipeline’dagi command `min(sale, rent)` bilan baholanadi (`execution-policy.yaml` `shared_pipeline_mode`).

L2 graduation — owner `trust_graduation` (`/graduate`, HG-L2-01, `L2_ENABLE` profili). Boshlang‘ich mezon ★ (✅ Q08’dagi "toza tasdiqlardan keyin guardrail ichida avtomatik daraja"ning implementatsiyasi): shu action_type × pipeline’da 10 ketma-ket `met` natijali jonli item (`command_outcomes`), oxirgi sanalgan itemdan keyin 14 kun shu action_type × pipeline’da incident yo‘q va identity isolation dalili bor. `inconclusive` clean emas (◇ P-04), shadow item sanalmaydi. `met`ni agent emas, WF-B07 S02 dagi deterministik `outcome_classify` hisoblaydi (band ichida va aytilgan yo‘nalishda, `data_status = valid`); item faqat `basis_tag` D/T/X, taklif paytidagi qiymat ma’lum va nisbiy band kengligi `business.acceptance.outcome_band_max_relative_width`dan oshmasa sanaladi; `budget_change` increase va decrease alohida juftlik; sanaladigan `met`dan boshqa har natija (jumladan `inconclusive`, rad, ✏️, expired, cancelled) seriyani 0 ga qaytaradi — vaqtinchalik qattiqroq o‘qish, HG-F5-04 da ko‘riladi (◇ P-42; `decision-statistics.yaml` TRUST_RAMP_GRADUATION). `trust_ramp.never_auto` ro‘yxatidagi action L2’ga o‘tmaydi. Pasayish: incident → trust L1; kill criteria → pipeline L0 (`kill_criteria_l0`) va shu pipeline’dagi trust L1 (`trust_ramp.demotion`).

`auto` action’lar (`asset_upload`, `amo_tag_write`, `amo_field_write`) L1/L2’da faqat global `enabled` bo‘lganda inson tasdig‘isiz o‘tadi, lekin barcha guard, durable attempt va audit bilan; L0 yoki `shadow`da SHADOW sifatida yoziladi; `killed`da amo yozuvi rad. `asset_upload` qo‘shimcha ravishda Reviewer pass, kerakli inson til tekshiruvi va `asset_rights_cleared`ni talab qiladi. `protective_pause` oldindan ruxsatlangan himoya (§6.4).

### 4.3 Resume, restore va maintenance

- Global kill’dan keyin `/resume` (`control_resume`): har pipeline `min(pre_kill_pipeline_mode, L1_approve_each)`; oldingi global `shadow` saqlanadi; `read_only` sababi hal bo‘lmaguncha saqlanadi. Oldingi approval tirilmaydi; yangi epoch, token, review va approval kerak.
- KC-01’dan keyin pipeline C05 RCA, owner `takeover_scope_change` (HG-F6-04 qayta) va owner `pipeline_mode_change` → L1 bo‘lmaguncha `L0_shadow`da qoladi; `/resume` uni ochmaydi.
- Release qilingan entity owner qayta takeover’isiz yozishga ochilmaydi (`released_entities_require_owner_retakeover: true`, `auto_retakeover_on_resume: false`).
- Restore `killed` bilan boshlanadi; `shadow`+L0 faqat reconcile’dan keyin owner qadami bilan. Keyingi daraja `min(snapshot_mode, off-host control journal’dagi oxirgi mode, L1_approve_each)`; journal yo‘q bo‘lsa barcha pipeline L0 va owner har pipeline’ni alohida ochadi. Kill, mode o‘zgarishi, rol revoke va resume off-host journal’ga ko‘chiriladi.
- Tracking `read_only`dan chiqish: `tracking.thresholds`dagi N ketma-ket PASS kun va owner `/resume` (◇ P-18; [TRACKING_CAPI §6.5](TRACKING_CAPI.md)).
- Maintenance hold kill emas: `write_mode=read_only`, proxy admission pauza, release tugagach `maintenance_release` bilan faqat hold o‘zgartirgan o‘lchovlar (global rejim, proxy admission) tiklanadi, hold paytida yoqilgan kill va himoya nazoratlari o‘z chiqish qoidasigacha qoladi (`controls_raised_during_hold_persist`); L2 pasaytirilmaydi (`execution-policy.yaml` `maintenance_hold`).

## 5. Revision-bound command va tasdiq

### 5.1 Action jadvali

`approval-policy.yaml` `actions`ning inson o‘qiydigan ko‘rinishi; config bilan farq qilsa config ustun va validator rad etadi.

| Action | Approver | Maks. daraja | `review_required` | Ikki bosqich | Qo‘shimcha shart |
|---|---|---|---|---|---|
| `creative_activate` | owner, ads_approver | L2_auto_within_guardrails | true | — | mavjud faol ad set ichida AD’ni yoqish (yangi ad, creative almashtirish yoki oldin faol bo‘lgan ad’ni qayta yoqish); Reviewer pass + kerakli inson til tekshiruvi |
| `budget_change` | owner, ads_approver | L2_auto_within_guardrails | true | — | rolling24h ≤20%; biznes natija guard’i |
| `entity_pause` | owner, ads_approver | L2_auto_within_guardrails | false | — | — |
| `entity_activate` | owner, ads_approver | L2_auto_within_guardrails | true | — | oldin faol bo‘lgan campaign/ad set (`ever_active = true`) |
| `campaign_activate` | owner | never_auto | true | — | `campaign_create`/`adset_duplicate` orqali yaratilgan obyektning birinchi yoqilishi |
| `ad_create` | owner, ads_approver | L2_auto_within_guardrails | true | — | doim PAUSED; Reviewer pass + kerakli inson til tekshiruvi |
| `campaign_create` | owner | never_auto | true | — | doim PAUSED |
| `adset_duplicate` | owner | never_auto | true | — | doim PAUSED |
| `asset_upload` | — (auto) | auto | true | — | Reviewer pass, kerakli inson til tekshiruvi, `asset_rights_cleared` |
| `experiment_exposure` | owner, ads_approver | L1_approve_each | true | — | eksperiment arm’ining jonli exposure’i; pipeline’da bitta eksperiment (✅ Q41) |
| `protective_pause` | — (pre-authorized) | pre-authorized | false | — | §6.4 |
| `offer_change` | owner | never_auto | true | — | `github_pr` |
| `landing_pr_merge` | owner | never_auto | true | — | `github_pr` |
| `events_manager_change` | owner | never_auto | true | — | `change_set_manual_execution` |
| `amo_tag_write` | — (auto) | auto | false | — | faqat `AMT:` prefiksi |
| `amo_field_write` | — (auto) | auto | false | — | faqat `amt_creative_id`, `amt_quality_flag`, `amt_lead_score` |
| `amo_pipeline_change_proposal` | owner | never_auto | false | — | `change_set_manual_execution` |
| `plan_authority_items` | owner | never_auto | false | — | haftalik rejadagi owner vakolatidagi bandlar |
| `role_change` | owner | never_auto | false | typed_code | membership va flag o‘zgarishlari; off-host monitor’ga mirror; ⧗ OD-10 |
| `kill_switch` | owner | never_auto | false | typed_code | default rejim A; deputy kill ⧗ OD-04 |
| `global_mode_change` | owner | never_auto | false | typed_code | `/mode global shadow\|enabled`; `enabled` faqat F6_STEP1 gate’idan o‘tganda (`max_evidence_age` bilan, iste’mol paytida); binding: from/to, `profile_evaluation_digest`, control_epoch |
| `control_resume` | owner | never_auto | false | typed_code | binding: pipeline_set, from/to mode, cause_ref, control_epoch |
| `pipeline_mode_change` | owner | never_auto | false | typed_code | `/mode`; oshirish — gate (`profile_evaluation_digest`), pasaytirish gate emas |
| `takeover_scope_change` | owner | never_auto | false | typed_code | HG-F6-04; binding: pipeline, managed_entity_manifest_hash, policy_revision |
| `trust_graduation` | owner | never_auto | false | typed_code | HG-L2-01; binding: action_type, pipeline, from/to level, outcome va isolation dalili, `profile_evaluation_digest` (L1→L2 gate) |
| `budget_override` | owner | never_auto | false | typed_code | `/budget raise`; key cap ichida; ads cap’ga ta’sirsiz |
| `asset_rights_clear` | owner | never_auto | false | typed_code | `rights_clearer` flag egasi faqat dalil tayyorlaydi (`/asset evidence`); yuklovchi o‘z yuklamasi uchun dalil tayyorlamaydi va clear qilolmaydi |
| `asset_rights_revoke` | owner | never_auto | false | typed_code | `rights_clearer` faqat dalil tayyorlaydi; offer/asset revocation tarqalishi |
| `upgrade_proposal_approval` | owner | never_auto | false | typed_code | `evolution-policy.yaml` gate |
| `upgrade_release` | owner | never_auto | false | typed_code | HG-REL-01; `release_approvals` yozuvi |
| `harness_handover` | owner | never_auto | false | typed_code | `evolution-policy.yaml` gate |
| `migration_drill` | owner | never_auto | false | typed_code | D sinfi: `restore_drill` muhitida forward migration va rollback drill’i hamda data check (`migration_drills` yozuvi) |
| `protected_surface_change` | owner | never_auto | false | typed_code | mustaqil inson review’i majburiy (⧗ OD-12) |
| `engineering_budget_change` | owner | never_auto | false | typed_code | `evolution-policy.yaml` gate |
| `readiness_signoff` | readiness_accountable_or_co_signer | never_auto | false | typed_code | kalit bo‘yicha `accountable_role`/`co_signers` egasi; dalil tayyorlovchisi, agent va builder imzolay olmaydi; binding: kind, key, record_revision, value_hash, evidence_ref, evidence_at, role, control_epoch; `withdraw` — owner (istalgan kalit) yoki accountable rol egasi, sabab bilan, tayyorlovchi va yangilik tekshiruvidan mustasno |
| `agent_resume` | owner | never_auto | false | typed_code | cost-watchdog ulush tugashi, `billing_unreliable` dan boshqa proxy admission pause yoki oy chegarasi (`month_boundary`) pauza qilgan agentni qaytarish; `billing_unreliable` pauzasi reconciliation isbotlangach avtomatik ochiladi (`budgets.yaml#openrouter.billing_unreliable_resume`); binding: agent_slug, pause_reason_code, cause_ref |
| `agent_retire` | owner | never_auto | false | typed_code | WF-E05 yaratgan agentni to‘xtatish: ochiq item’lar bekor, ulush `reserve` ga qaytadi, Paperclip agenti pauza (✅ Q68); oltita asosiy rolga qo‘llanmaydi; binding: agent_slug, hire_run_id |

Case bo‘yicha toraytirish (`approval-policy.yaml#actions.<action>.cases`): `entity_activate` va `creative_activate` da `re_activation_after_protective_pause` — approvers faqat owner, `never_auto`, `trust_ramp.never_auto_cases`; gateway case’ni generik action’dan oldin belgilaydi (guard 14), ops-bot callback’i case’ni ham tekshiradi (GT-51).

Owner-only action’lar (`approvers: [owner]`, hammasi NEVER_AUTO): `campaign_activate`, `campaign_create`, `adset_duplicate`, `offer_change`, `landing_pr_merge`, `events_manager_change`, `amo_pipeline_change_proposal`, `plan_authority_items`, `role_change`, `kill_switch`, `global_mode_change`, `control_resume`, `pipeline_mode_change`, `takeover_scope_change`, `trust_graduation`, `budget_override`, `asset_rights_clear`, `asset_rights_revoke`, `upgrade_proposal_approval`, `upgrade_release`, `harness_handover`, `migration_drill`, `protected_surface_change`, `engineering_budget_change`, `agent_resume`, `agent_retire`. `asset_rights_clear/revoke`ni faqat owner bajaradi; `rights_clearer` flag egasi faqat dalil biriktiradi (`/asset evidence`); yuklovchi o‘z yuklaganini clear qilolmaydi (`uploader_may_not_clear`). Typed code bilan ikki bosqichli action’lar sintaksisi [TELEGRAM §3](TELEGRAM.md)da. To‘liq NEVER_AUTO ro‘yxatining yagona manbai — `approval-policy.yaml` `trust_ramp.never_auto`; boshqa hujjatlar undan ko‘chiradi.

`new → pending_review` faqat `review_required: true` bo‘lsa; aks holda `new → pending_approval` yoki auto/pre-authorized yo‘l. `review_required: false` bo‘lgan pauza va control action’lari Reviewer’ni kutmaydi.

### 5.2 Binding va javob kontrakti

Gateway proposal yaratilganda normalized params/target va `payload_hash` bilan immutable intent’ni saqlaydi; keyingi command review va inson tekshiruvi alohida append-only binding’dan olinadi ([DATA_MODEL §6.1](DATA_MODEL.md)). `review_required: true` item `review_revision` hali yo‘q paytda `pending_review`da yaratilishi mumkin. Mustaqil Reviewer exact `(command_id, command_revision, payload_hash)` subject’iga `pass` bergach `command_review_bindings` bir marta yoziladi; creative revision’ning avvalgi `creative_review_revision` verdict’i command review o‘rnini bosmaydi. Inson approval tugmasidan/`mark_presented()`dan, policy yoki auto approval’dan oldin `freeze_approval_binding()` barcha zarur review/human check dalillarini tekshirib bitta immutable `command_approval_bindings` snapshot yaratadi. Approval shu snapshot’ning `approval_binding_id/binding_hash`iga bog‘lanadi. Effective approval binding (`execution-policy.yaml#approval_binding`) frozen dependency snapshot’i va `record_approval()`da atomik tekshirilgan actor membership’idan iborat: `payload_hash`, `command_revision`, `creative_revision`, `asset_manifest_sha`, `creative_review_revision`, `review_revision`, `human_check_id`, `offer_revision`, `policy_revision`, `role_revision`, `entity_state_version`, `control_epoch`, `expires_at`. Talab qilinmagan dependency NULL + explicit not_applicable reason’i bilan; command muallifining role revision’i approver membership revision’idan alohida. Presentation’dan keyin dependency qo‘shish/almashtirish yo‘q: edit yoki invalidation yangi command revision’ini talab qiladi. Approval aynan shu immutable revision va frozen binding’ga tegishli; dispatch, retry va rollback oldidan hammasi qayta tekshiriladi (`revalidate_before`). Fayl nomi yoki path o‘zgarmagani bytes bir xilligiga dalil emas.

Har yozish/proposal tool’ining javobi HTTP 202 va quyidagi obyekt yoki §10’dagi xato kodi:

```json
{"status": "queued | shadow | needs_owner", "command_id": "uuid", "revision": 1}
```

`queued` — item `pending_review` yoki `pending_approval`da (L2 policy ichida bo‘lsa policy approval bilan); `shadow` — `shadow=true`, hech qachon dispatch qilinmaydi va TTL’da `expired`; `needs_owner` — owner qarori navbatida (`/decisions`). Agent Meta javobini sinxron olmaydi: natija command ledger’dan workflow step’iga va notification outbox orqali keladi.

### 5.3 State, TTL va qarorlar

State: `pending_review → pending_approval → approved → claimed → executing → succeeded`; rad, muddat yoki revoke `rejected/expired/cancelled`; ta’sir yo‘qligi isbotlansa `failed_confirmed`; noma’lum tashqi natija `uncertain → reconciling → succeeded | failed_confirmed | manual_resolution`. Qo‘shimcha o‘tishlar (`execution-policy.yaml` `extra_transitions`): `claimed → cancelled` (dispatch intent yozilishidan oldin kill yoki revoke; reservation bo‘shatiladi); `approved|claimed → cancelled` (guard fail, `reason_code` bilan); `awaiting_manual → expired`; `manual_resolution → succeeded|failed_confirmed` (operator dalili bilan); shadow item TTL’da `expired`. Kill sababi — `cancelled` + `reason_code=kill`. Barcha o‘tish writer/guard/atomic audit bilan [DATA_MODEL §6](DATA_MODEL.md)da; command holatining boshqa manbai yo‘q va workflow run/step holati uni almashtirmaydi (I16).

Approval TTL `change_set_items.presented_at`dan 12 soat (`approval_ttl_hours: 12`, `expiry_basis: presented_at`; ✅ Q32/Q38). Odatiy 10:00 batch 22:00’da tugaydi; 09:45 dan keyin review’dan o‘tgan item alohida, o‘z `presented_at` va TTL’i bilan keladi (`batch_cutoff`). Timeout hech qachon avtomatik approve qilmaydi (`auto_approve_on_timeout: false`). `approvals.decision ∈ {approve, reject, edit_decrease, expire}`; kvorum 1 (`change_set.quorum`, yagona manba). Approver edit faqat raqamli va faqat kamaytirish yo‘nalishida ★: bu yangi payload/revision, oldingi review/approval bekor, yangi revision tegishli review va approval’dan qayta o‘tadi, eski tugma/nonce ishlamaydi. Rol revoke yoki policy o‘zgarsa navbatdagi item dispatch oldidan rad etiladi.

Manual action (`events_manager_change`, `amo_pipeline_change_proposal`): owner approval → `awaiting_manual` → ownerning dalilli `[Bajarildi]` callback’i → `done_manual`; executor vendor call qilmaydi. `awaiting_manual` item `expires_at`da `expired` bo‘ladi; expired yoki revoked approval bilan manual completion qabul qilinmaydi — real tashqi o‘zgarish bo‘lgan bo‘lsa u yangi command yoki incident orqali dalillanadi.

## 6. Claim, lease, fence, provider noaniqligi va himoya pauzasi

### 6.1 Ijro ketma-ketligi

1. Executor bitta approved revision’ni `FOR UPDATE SKIP LOCKED`/CAS bilan oladi. Entity serialization lock, bounded lease, monoton fence va kerakli monetary reservation bir transaction’da yoziladi.
2. Remote state o‘qiladi; drift, freshness, role, policy, offer, review, asset va epoch qayta tekshiriladi. Drift bandni yangi state ustida yashirin qayta hisoblamaydi: eski item `cancelled` (`reason_code=state_drift`), ownerga re-proposal kerak.
3. Dispatcher local barrier ichida amaldagi epoch/latch’ni tekshiradi va durable `execution_attempts` dispatch-intent yozuvini oladi. Provider call huquqi bitta attempt’ga bog‘lanadi. Epoch tekshiruvi va upstream send boshlanishi bitta bounded local critical section’da; keshlangan permit yo‘q, remote response lock ichida kutilmaydi. Kill shu barrier bilan tartiblanadi (◇ P-03).
4. Provider javobidan keyin exact request/response hash, remote ref, cost va final state audit va notification outbox bilan atomik commit qilinadi. Telegram/Paperclip’ga natija outbox worker orqali boradi.
5. Dispatch intent bor, lekin tasdiqlangan final commit yo‘q bo‘lsa recovery `uncertain` deb oladi. Lease tugashi stale worker’ga davom huquqi bermaydi; eski fence DB update va yangi dispatch’da rad.

Fence faqat lokal stale worker’ni to‘sadi; Meta bizning fence’ni biladi deb olinmaydi. Kill’dan oldin yuborilgan so‘rov keyin bajarilishi mumkin. Network timeout, 5xx yoki broker uzilishi no-side-effect dalili emas. Ko‘r-ko‘rona retry yo‘q: provider read, event history yoki request ID orqali reconcile. Create operatsiyasida nomning bir xilligi uniqueness kafolati emas; vendor correlation/lookup F3’da tekshiriladi. Yechilmasa `manual_resolution`, reservation saqlanadi va entity uchun yangi conflict write yopiq.

### 6.2 Retry va compensation

Retry’ning to‘liq transition jadvali — [DATA_MODEL §6.3](DATA_MODEL.md); kanonik config — `execution-policy.yaml#retry`. Faqat transport jo‘natilmaganini yoki pinned F3 dalili provider hech qanday effekt qilmaganini isbotlagan transient xato qayta uriniladi: attempt N terminal `no_effect`, command `claimed`/`executing`da o‘zgarmay qoladi, original bilan jami ko‘pi bilan 5 urinish ★. `next_attempt_at` exponential backoff va uzunroq `retry_after`ni hurmat qiladi; command `approved`ga qaytmaydi. N+1 attempt CAS, yangi monoton fence va barcha guard/frozen binding qayta tekshiruvi bilan olinadi; eski worker permit’i bekor. Original command/approval/dependency expiry’lari uzaymaydi; shu reservation va conflict lock saqlanadi, ikki marta reserve/settle/release yo‘q.

Kill/revoke/drift/expiry yoki retry limiti dispatchni to‘xtatadi; hali `claimed` command `cancelled`, oldin `executing` bo‘lgan va barcha attempt’i no-effect command `failed_confirmed` bilan yopiladi (aniq sabab/evidence bilan). `failed_confirmed` terminal. Noma’lum 429/5xx/timeout yoki intent’dan keyingi crash — `uncertain → reconciling`, retry yo‘q, reservation/lock qoladi; reconcile no-effect bilan yopsa ham keyingi write yangi revision/review/approval talab qiladi. SDK retry o‘chiq. Attempt signali `attempt:<attempt_id>:<state>`, command outbox’i faqat haqiqiy command transition’da (`cmd:<id>:<revision>:<state>`).

Rollback — yangi compensating command (§8 `Compensation` ustuni), `compensates_command_id` bilan; amaldagi vakolat, drift, pul va epoch guard’laridan o‘tadi. `rolled_back` alohida state emas. Pause-only yo‘l (§6.4) activation, increase yoki create qilmaydi.

### 6.3 Meta throttling, rad etish va account cheklovi

- **Meta API rad etishi yoki throttling** (`ALERT_META_REJECTED`). Executor va read connector vendor’ning usage/throttle signallarini (`x-business-use-case-usage` va pinned SDK’dagi throttle kodlari [D: Meta Marketing API hujjati; pinned versiyada F3’da tekshiriladi]) kuzatadi. Throttle qilingan write faqat yuborilmagani yoki provider hech qanday ta’sir qilmagani F3’da tasdiqlangan klassifikatsiyada `retry_after`/backoff bilan shu ochiq command’ning attempt scheduler’iga qaytadi (§6.2); bu command’ni `approved`ga qaytarish emas. Bunday dalilsiz throttle `uncertain` va reconcile bo‘ladi; vendor permanent rad (validation, permission) tashqi ta’sir yo‘qligi dalili bilan `failed_confirmed` bo‘ladi, qayta urinish yo‘q, yangi revision kerak. Har ikki holatda `ALERT_META_REJECTED`.
- **Account cheklovi** (`ALERT_ACCOUNT_RESTRICTED`). Abuse signali [D: byadsco README; pinned versiyada qayta tekshiriladi], account restriction yoki disable bo‘lsa yangi risk write to‘xtaydi: `sync-worker` `amt-control`dan `account_restricted_read_only` so‘raydi (global `read_only`) va owner issue ochiladi. Avtomatik qayta ochilmaydi; sabab hal bo‘lgach owner `/resume` beradi.
- **Meta ad review rad etishi** (`ALERT_POLICY_REJECTION`): executor javobi yoki sync’dagi ad holati/review feedback bo‘yicha darhol urgent alert (✅ Q38) va Reviewer’ga exact creative revision bilan Paperclip issue (anti-case; WF-B02 `meta_rejection` signali). Shu creative revision’ga bog‘langan pending command’lar `cancelled` (`reason_code=policy_rejected`). Apellyatsiyani faqat owner beradi; AI faqat qoralama tayyorlaydi.

### 6.4 Himoya pauzasi (`protective_pause`)

✅ Q37 provider spending limit’iga qo‘shimcha deterministik qatlam; uning o‘rnini bosmaydi (`additional_to: provider_spending_limit`; ◇ P-21).

| Element | Qiymat |
|---|---|
| Trigger | managed spend headroom ≤ safety margin, yoki managed entity faol paytda spend ma’lumoti `budget.ads_pacing` cutoff’idan eski (`operations.yaml` `protective_controls`) |
| Ishga tushiruvchi | `amt-sync`dagi spend pacer check har sync siklida `amt-control`dan so‘raydi; `amt-control` `protective_pause` command chiqaradi |
| Ijro | `amt-executor` pause-only emergency path: re-read → pause → verify → `protective_actions` qatori → `ALERT_PROTECTIVE_PAUSE` |
| Vakolat | owner tasdiqlagan policy revision oldindan ruxsat bergan (`pre_authorized_by`); runtime approver yo‘q; `review_required: false`; yangi credential yoki UID yo‘q |
| Qamrov | faqat `managed_entities`; operatsiya faqat `pause`; hech qachon activate, budget increase yoki create |
| Rejimlar | `shadow`, `enabled`, `read_only` va `killed`da ishlaydi (`allowed_global_modes`) |
| Foreign spend | inson boshqaradigan kampaniya cap’ni yesa AMT uni pauza qilmaydi: faqat urgent alert va owner handback (`foreign_spend_behavior`) |
| Qaytarish | faqat action qoidalari bo‘yicha yangi vakolatli activation command; avtomatik qayta yoqish yo‘q |

Kill B ham shu pause-only yo‘ldan foydalanadi: eng yuqori to‘liq managed daraja pauza qilinadi (butun campaign managed bo‘lsa campaign, aks holda ad set yoki ad), foreign parent’ga tegilmaydi ([SECURITY §6](SECURITY.md)).

## 7. Pul shartnomasi

### 7.1 Birlik va cap’lar

AI/media runtime cap — USD 150/oy (15 000 USD minor), `openrouter.key_hard_cap_minor` (✅ Q10/Q33/Q44.1). Paid Meta biznes cap — USD 1 500/oy (150 000 USD minor), `ads.monthly_cap_minor` (✅ Q08/Q37). Pul integer minor va explicit currency bilan (1 USD = 100 minor). Meta account valyutasi, timezone, counter bazasi va FX siyosati (`ads.account_currency`, `ads.account_timezone`, `ads.counter_basis`, `ads.fx_policy`) F3’da `vendor.meta_cap` va `budget.ads_limits` readiness’da isbotlanadi; noma’lum valyuta yoki konversiya bilan write bloklanadi.

### 7.2 Mustaqil provider limit (✅ Q37) va qo‘shimcha himoya

- Ads Manager **account spending limit** majburiy va AI’dan mustaqil cap (`ads.provider_spend_limit_required: true`). HG-F3-02 uni birinchi marta qo‘yadi; HG-OPS-01 har oy 1-kuni (`operations.yaml` `spend_cap_update`) yangilaydi: `spend_cap_native = provider_counter_now_native + to_native(max(0, monthly_cap_minor − verified_mtd_minor − safety_margin_minor))`, provider minor birligiga pastga yaxlitlanadi (`cap_update_formula`, ◇ P-02). Oy o‘rtasida to‘liq 150 000 USD minor allaqachon sarflangan MTD ustiga qayta qo‘shilmaydi.
- `vendor.meta_cap` PASS sharti — API read-back kutilgan qiymatga teng (`ads.provider_spend_limit_readback_required: true`); F6 Step 1 oldidan bir kunlik yangi dalil `budget.ads_fresh_check` (`max_evidence_age: P1D`). Limit yo‘q yoki read-back mos emas → yangi risk write rad, `sync-worker` `amt-control`dan `provider_limit_read_only` so‘raydi (global `read_only`), `ALERT_SPEND_CAP_HEADROOM` (critical).
- `protective_pause` (§6.4) qo‘shimcha qatlam (`ads.protective_pause_is_additional: true`). Provider limitni olib tashlash yoki almashtirish faqat yangi owner Q bilan (⟲ Q37), hech qachon readiness qiymati bilan emas.
- Hard-cap qabul (`ads.hard_cap_pass_requires`): `provider_spend_limit_readback`, `gateway_headroom_test`, `host_down_test_provider_limit_holds`. Alert yoki operator javobi yolg‘iz kafolat emas: faol reklamalar yangi write bo‘lmasa ham sarflaydi.
- MTD butun account sarfini, jumladan inson boshqarayotgan kampaniyalarni qamraydi; `reported_at`, account timezone, counter basis, pending commitments, provider limit, safety margin va freshness saqlanadi.

### 7.3 Commitment va admission

Commitment (reservation miqdori) `budgets.yaml` `ads.commitment_basis` bo‘yicha:

| Action | `commitment_minor` |
|---|---|
| `budget_change` | `max(0, new_daily_minor − old_daily_minor) × remaining_days_in_business_month` |
| `entity_activate` | `daily_budget_minor × remaining_days_in_business_month` |
| `campaign_activate` | `daily_budget_minor × remaining_days_in_business_month` |
| `creative_activate` (yangi ad set’da) | `daily_budget_minor × remaining_days_in_business_month` |
| `entity_pause`, `protective_pause` | `0` |

Admission (`ads.admission_rule`): `verified_mtd_minor + Σ(active_daily_minor × remaining_days) + Σ(held_commitments_minor) + requested_minor ≤ monthly_cap_minor − safety_margin_minor`. Barcha had’lar `ads.fx_policy` bo‘yicha provider counter valyutasiga keltiriladi. `remaining_days_in_business_month`ning aniq ta’rifi (joriy kun kiradimi, account timezone farqi) `vendor.meta_cap` dalilida qotiriladi; qotirilguncha konservativ hisob — joriy kun ham kiradi. Shart buzilsa `monthly_cap_exceeded`. Reservation claim’dan oldin olinadi; `rejected`, `expired`, `cancelled`da bo‘shatiladi, `succeeded`da settle qilinadi; `uncertain` reconcile bo‘lguncha ushlab turiladi. Commitment bitta headroom’ni ikki parallel proposal’ga va’da qilishni to‘sadi, lekin real sarf uchun pacing, freshness va provider limit qatlamlarini almashtirmaydi.

### 7.4 Rolling 24 soat budget harakati

`rolling24h_sum_abs_delta / verified_budget_at_window_start ≤ 0.20` (`actions.budget_change.limits`; ◇ P-01 ✅ Q08/Q32’dagi "±20%"ni aniqlashtiradi; `ads.max_rolling24h_change_pct: 20`, `ads.movement_basis: sum_absolute_ordinary_budget_changes`). Takroriy +15%, +10% yoki kamaytirib yana oshirish chetlab o‘tolmaydi. Nol yoki noma’lum baseline → owner review, avtomatik increase yo‘q (`zero_or_unknown_baseline`); inson drift’i → block va reconcile (`manual_drift_behavior`), yangi baseline yashirin o‘rnatilmaydi. CBO/ABO budget egasi bir marta hisoblanadi. Lifetime budget o‘zgartirish rad (`policy_violation`) ★. Fleet hold paytida rent’ning odatiy kamaytirishi ham hold; himoya pauzasi alohida yo‘l.

### 7.5 LLM/media proxy

`llm-proxy` bitta shared account va agent/media ulushini atomik actual+reserved bilan tekshiradi: `request_id`, versioned pricing/model, upper-bound reserve, upstream generation ID va settlement. Ulushlar (`openrouter.shares_minor`, USD minor): creative-studio 3 500, cmo 2 000, funnel-analyst 1 500, media-buyer 1 500, cro 1 000, reviewer 500, media_generation 4 000, reserve 1 000; jami 15 000. `reserve` oldindan hech kimga berilmaydi; uni faqat owner `budget_override` agentga yoki `media_generation`ga, key cap ichida, ko‘chiradi (`reserve_rule`). Ogohlantirish `share_warn_pct: 80` (`ALERT_BUDGET_80`); ulush to‘xtashi `share_stop_pct: 100`, key bo‘yicha noncritical ish to‘xtashi `key_noncritical_stop_pct: 90` (sinf — `admission_classes`: boshlang‘ich holatda har LLM/media admission non-critical, ◇ P-84) va billing reconciliation 6 soatdan ortiq ishlamasa noncritical agentlar pauzasi (`billing_unreliable_noncritical_pause_after_hours: 6` ★) — hammasi `proxy_admission_pause` va `ALERT_BUDGET_100`. Faqat billing reconciliation sababli pauza reconciliation tiklangani isbotlangach avtomatik ochiladi (`billing_unreliable_resume`); ulush yoki key chegarasi, cost-watchdog yoki oy chegarasi sababli pauzalangan agentni faqat owner `agent_resume` (`/agent resume <agent_slug>`) qaytaradi (`resume_after_reset_requires_owner: true`). Build davridagi AT/eval/shadow sarfi oylik key cap’ning ko‘pi bilan 40% ★ (`build_eval_max_pct`); oshsa faqat: ikki oyga bo‘lish, eval qamrovini kamaytirish yoki Q10’ni o‘zgartiruvchi yangi owner Q (HG-F4-04). Noma’lum stream/async narx nol bo‘lmaydi, reservation reconcile bo‘lguncha qoladi; narx upper bound’i yo‘q bo‘lsa billable dispatch rad. Upper bound hech qachon eng yomon holatdan past emas (◇ P-99): input so‘rov to‘lashi mumkin bo‘lgan eng yuqori narxda — `cache_control` bo‘lmasa asosiy narx, 5 daqiqalik TTL’da 1,25×, 1 soatlik yoki noma’lum TTL’da 2× (cache write, VR-43), cache-read narxi hold’da hech qachon ishlatilmaydi; settlement haqiqiy narx bo‘yicha `ceil(total_cost × 100)` minor. Upper bound ulushga moslab o‘lchanadi (`budgets.yaml#openrouter.reservation_sizing`, ◇ P-86): bitta so‘rovning upper bound’i rolning `max_cost_minor`idan oshmaydi va har allowance’ning (agent ulushi, CMO ulushi qismi, media ulushi) ochiq hold’lari — ishlayotgan va settle bo‘lmagan, LLM va media — yangi upper bound bilan birga o‘sha allowance’ning `share_warn_pct`–`share_stop_pct` oralig‘iga (80–100%) sig‘adi (◇ P-101), shuning uchun hold’lar haqiqiy sarf 80% ga yetmaguncha allowance’ni o‘zi tugata olmaydi; bir vaqtda ko‘pi bilan `max_concurrency` so‘rov (reviewer uchun model slot’i bo‘yicha); oshgan so‘rov rol navbatida kutadi va adapter timeout’idan oldin `slot_wait_exceeded` oladi; `uncertain` so‘rov slot’ini bitta cost-watchdog tick’idan keyin bo‘shatadi, pul hold’i esa settle bo‘lguncha oraliqda qoladi, proxy uni har cost-watchdog tick’ida OpenRouter `GET /api/v1/generation?id=` yozuvi bilan settle qiladi (VR-38); `uncertain_settlement_hold_hours` tugasa hold upper bound’da qoladi (bepul kredit emas) va kunlik provider usage reconciliation settle qilguncha oraliqda hisoblanadi, `ALERT_AGENT_ERROR` (`uncertain_hold_expired`). Qoida F1-AT-30 da har rol uchun hisoblanadi; buzadigan config yoki pricing revision’ini proxy ACK qilmaydi (`ALERT_CONFIG_ACK`). Media generation config’da o‘chiq (`media_generation.enabled: false`); `budget.media` yopilib owner yoqmaguncha tool mavjudligi pullik ishga ruxsat emas.

`/budget raise <agent_slug|media_generation> <whole_usd>` (`budget_override`, owner, typed code): `extra_minor = whole_usd × 100`; faqat key cap (15 000 USD minor) ichida qayta taqsimlaydi — oylik `reserve` qoldig‘idan oshsa rad; ads cap’ga hech qachon ta’sir qilmaydi (`affects_ads_cap: false`); override joriy biznes oyi oxirida tugaydi; bot summani major va minor ko‘rinishida qaytaradi ([TELEGRAM §3](TELEGRAM.md)).

## 8. Tashqi Meta tool kontraktlari

| Tool | Muhim parametr va guard | Action / yakun | Compensation |
|---|---|---|---|
| `meta_write.pause_entity` | scoped `entity_type` (campaign/adset/ad), id, pipeline, reason; managed ownership; allaqachon PAUSED → no-op dalili | `entity_pause` | yangi activation command: ad → `creative_activate`, oldin faol campaign/ad set → `entity_activate`; joriy vakolat va guard’lar bilan |
| `meta_write.activate_entity` | exact remote state; ad uchun creative/review/offer/rights; commitment admission; action turini server aniqlaydi | ad → `creative_activate`; oldin faol campaign/ad set → `entity_activate`; `ever_active=false` campaign/ad set → owner-only `campaign_activate` | `pause_entity` |
| `meta_write.update_budget` | campaign CBO yoki ad set ABO, integer `daily_budget_minor`, currency, `expected_effect`; rolling24h, drift, admission, fleet/sale va biznes natija guard’i | `budget_change`; lifetime budget o‘zgartirish rad | eski `daily_budget_minor`ga qaytaruvchi yangi `update_budget` (rolling24h’ga kiradi) |
| `meta_write.create_campaign_paused` | kanonik nom ([TRACKING_CAPI §2](TRACKING_CAPI.md)), objective, explicit `special_ad_categories` (bo‘sh ro‘yxat ham aniq yoziladi), currency/budget/pipeline, owner approval | `campaign_create`; doim PAUSED, `origin=amt_created`, `ever_active=false` | PAUSED qoladi; o‘chirish tool’i yo‘q — arxivlash faqat owner’ning qo‘lda amali |
| `meta_write.create_ad_from_creative` | mavjud managed ad set, exact immutable creative revision/hash, Reviewer pass va kerakli inson tekshiruvi; ad nomi = `creative_id`; URL params’ni server qo‘yadi | `ad_create`; doim PAUSED; `creative_ad_bindings` | PAUSED qoladi; binding bekor qilinadi |
| `meta_write.duplicate_adset` | managed manba, nom/budget/currency, targeting/placement field allowlist, owner approval | `adset_duplicate`; PAUSED, `origin=amt_duplicated`, `ever_active=false` | PAUSED qoladi |
| `meta_write.upload_creative_asset` | faqat media-buyer; cleared asset manifest bytes/hash/type/size, Reviewer pass, kerakli inson tekshiruvi, `asset_rights_cleared` | `asset_upload` (auto, lekin durable attempt + guard + audit) | remote o‘chirish yo‘q; lokal binding invalidatsiyasi va bog‘liq ad’lar uchun `pause_entity` |

**Tool’i yo‘q amallar (No-tool list):** campaign, ad set, ad yoki asset’ni o‘chirish; auditoriya yaratish yoki ulashish; lead form; account spending limit (spend cap) o‘zgartirish; billing va to‘lov; Pixel/dataset va Events Manager sozlamalari (faqat owner qo‘lda, `events_manager_change` orqali); automated rules; komment moderatsiyasi; WhatsApp yoki mijozga xabar; business va system user ruxsatlari; lifetime budget. Bunday amal kerak bo‘lsa — PR + ADR orqali yangi tor operatsiya va `approval-policy.yaml`da yangi action (himoyalangan sirt, `protected_surface_change`).

Vendor endpoint, Marketing API/SDK versiyasi, ad category va xato tasnifi `VERSIONS.lock.md` va integration dalilida pin qilinadi; tasdiqlanmagan vendor nomi yoki xato kodi fakt sifatida qo‘llanmaydi. Read MCP’ning write tool’i hech qachon ijro kanali emas (GT-21).

## 9. Ichki va tor yozish tool’lari

### 9.1 Tool jadvali

| Tool | Egasi | State va cheklov |
|---|---|---|
| `creative.register` | creative-studio | immutable revision + manifest (`asset_manifest_sha`), faol offer ref’lari, rights-cleared asset’lar, `copy_artifact_id` lineage; current pointer, creative review `pending` |
| `review.get_subject` | reviewer | §9.2; read-only; `models.pre_screen` approved bo‘lsa Jev pre-screen natijasi bilan |
| `review.submit_verdict` | reviewer | §9.3; faqat shu Reviewer run’iga berilgan `subject_hash` |
| `change_set.record_outcome` | funnel-analyst | §9.4 |
| `experiment.create`, `experiment.update`, `experiment.close` | funnel-analyst | pipeline’da bir vaqtda bitta `running` eksperiment (✅ Q41); sample, maturity, guardrail va stop qoidasi; natija `experiments` enum’i bo‘yicha ([DATA_MODEL](DATA_MODEL.md)); jonli exposure alohida `experiment_exposure` action |
| `change_set.propose_manual` | cmo, funnel-analyst | faqat `events_manager_change` va `amo_pipeline_change_proposal`; aniq qo‘lda qadamlar, `expected_effect`, rollback; approval tashqi manual bajarishni anglatmaydi |
| `evo.signal.submit` | barcha biznes agentlari | yaxshilanish signali (ichki, audit, PII’siz) → WF-E04/WF-E01; agent kod yoki skill PR’ini o‘zi ochmaydi; signal ko‘rsatma emas |
| `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker` | barcha biznes agentlari | faqat o‘z step’i va lease fence’i; artifact digest; handoff `accepted/rejected` sabab bilan; blocker owner ko‘rinishiga chiqadi (`/work`) ([WORKFLOW_RUNTIME §2](WORKFLOW_RUNTIME.md)); tashqi effekt yo‘q |
| `workflow.start` | cmo, cro, funnel-analyst | faqat definition’ning `authorization.may_start` ro‘yxatida shu agent bo‘lgan workflow (cmo: WF-B02/B04/B05; cro: WF-B04; funnel-analyst: WF-B05); dedup/correlation key majburiy; tashqi effekt yo‘q |
| `amo.read_leads`, `amo.read_pipelines`, `amo.read_events` | funnel-analyst | §9.5 field allowlist |
| `amo.write_tags` | funnel-analyst | faqat `AMT:` prefiksi ★, bounded allowlisted qiymatlar; ID/tagda yashirin PII yo‘q; `killed`da rad |
| `amo.write_fields` | funnel-analyst | faqat `amt_creative_id`, `amt_quality_flag`, `amt_lead_score` (`field_allowlist`); enum/range sanitizer; qolgan CRM field/pipeline/contact rad; `killed`da rad |
| `landing.open_pr` | cro, funnel-analyst | §2 yo‘llari; merge faqat owner (`landing_pr_merge`); PR’da code/consent/offer revision dalili; Reviewer subject `landing_pr`; `killed`da rad |
| `offers.propose_pr` | cmo, cro | faqat `config/offers.yaml` uchun PR; owner merge yangi revision va dependency invalidatsiya; `killed`da rad |
| `offers.read` | hammasi | faol offer revision’lari va expiry |
| `render.html_to_png`, `render.video_template` | creative-studio | isolated `render-worker` (`amt-render`), root egaligidagi statik HTML/ffmpeg shablonlari; agent shell/script/path yoki remote URL bilan erkin render yo‘q; Remotion litsenziya qarorisiz ishlatilmaydi ★ |
| `drive.list_raw`, `drive.get_asset` | creative-studio; media-buyer, reviewer (`drive.get_asset`) | faqat ruxsatli AMT papkasi va cleared exact version; quarantine’dagi asset’ning faqat ID/summary’si ko‘rinadi, raw bytes emas; fayl ichidagi matn ma’lumot, buyruq emas |
| `media.generate_image`, `media.generate_video` | creative-studio; cro (faqat eskiz) | `llm-proxy` orqali gateway service token bilan; oldindan narx bahosi va bitta reservation (`media_generation` egaligida), kalit, media ulushi va so‘ragan agent ulushi bitta tranzaksiyada (`budgets.yaml#media_generation.attribution`, ◇ P-90); bitta job `max_cost_minor` va `max_video_seconds` ichida, oy `max_video_seconds_per_month`, bir vaqtda `max_concurrent_jobs` (`budget.media`); narx revision’i yozilmasa `price_unknown`; o‘chiq bo‘lsa rad |
| `report.submit` | cmo, funnel-analyst | sanitized bounded matn + evidence; haftalik hisobot bo‘lsa avval Reviewer pre-check (`weekly_report` subject), keyin durable notification outbox ([TELEGRAM §5.3](TELEGRAM.md)) |
| `wh.metrics` | cmo, media-buyer, creative-studio, cro, funnel-analyst | kanonik metrika katalogi ([DATA_MODEL](DATA_MODEL.md)), `data_status` bilan |
| `wh.query` | cmo, media-buyer, cro, funnel-analyst | strukturali so‘rov (`view`, `columns`, `filters`, `order_by`, `limit`); gateway undan bitta parametrlangan read-only SELECT quradi — faqat `amt_ro` view’lari, timeout va qator chegarasi bilan; xom SQL qabul qilinmaydi |
| `fleet.read_utilization` | cmo, media-buyer, funnel-analyst | `amt_ro.v_fleet_*`, freshness bilan |
| `analytics.umami_query`, `analytics.clarity_export` | cmo, cro, funnel-analyst (Clarity: cro, funnel-analyst) | read-only token; Clarity Data Export imkoniyati va limitlari F3’da tekshiriladi [?] |

### 9.2 Reviewer subject kanali (`review.get_subject`)

Reviewer tekshiradigan material va verdict bog‘lanadigan revision bir xil bo‘lishi uchun Reviewer subject’ni faqat `review.get_subject(subject_type, subject_ref)` orqali gateway egaligidagi immutable subject store’dan o‘qiydi (◇ P-20; `creative_review.reviewer_subject_source`).

| `subject_type` | Qaytariladigan exact subject |
|---|---|
| `creative_revision` | creative revision: copy, manifest, rendered preview va `asset_manifest_sha` |
| `change_set_item` | normalized payload, target, kuzatilgan remote state, `rollback_spec`, evidence ref’lari |
| `offer_pr` | gateway GitHub’dan exact commit SHA bo‘yicha olgan `offers.yaml` PR diff va ta’sir qiladigan offer revision’lari |
| `landing_pr` | gateway GitHub’dan exact commit SHA bo‘yicha olgan PR diff |
| `weekly_report` | `report.submit` qilingan aniq matn (BLUF va to‘liq hisobot) |

Javobda `subject_hash` bor. `review.submit_verdict` faqat shu Reviewer principal’iga shu run’da berilgan hash’ni qabul qiladi (`verdict_accepts_only_issued_subject_hash: true`); boshqa yoki eski hash → `revision_stale`, boshqa principal → `unauthorized`. Paperclip issue matni va izohlari authoritative emas; har review yangi sessiya, muallif fikrlash izi va writer izohlari kontekstga berilmaydi. Reviewer ikki model slotida ishlaydi (✅ Q42): `reviewer.language` — Sonnet-class yoki UZ/RU holdout’da teng ekani isbotlangan model (✅ Q44.2), `reviewer.policy_checklist` — arzonroq model mumkin; ikkalasi `models.assignments` readiness’da qayd etiladi.

**Jev pre-screen** (✅ Q61; [ADR-034](../04_ADR/ADR-034-jev-review-pre-screen.md); [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) `creative_review.pre_screen`). Jev — TypeSafe decision model (LLM emas), Reviewer’dan oldingi deterministik tekshiruv. `review.pre_screen` capability yoqilgan bo‘lsa (o‘z `PRE_SCREEN` profili, `models.pre_screen` tasdiqlangan), `review.get_subject` subject’ni berishdan oldin gateway Jev’ni chaqiradi va javobga har check bo‘yicha pre-screen natijasini qo‘shadi; yoqilmagan bo‘lsa yoki `models.pre_screen` withdraw qilingan bo‘lsa pre-screen o‘chiq va `review.get_subject` avvalgidek ishlaydi. `PRE_SCREEN` profilini boshqa profil meros olmaydi, shuning uchun bu kalit F6/L2 gate’lariga ta’sir qilmaydi.

| Element | Qoida |
|---|---|
| Chaqiruv | faqat gateway, `review.get_subject` ichida, Reviewer run’idan oldin (`called_by: gateway`); faqat llm-proxy orqali (`via: llm-proxy`, `endpoint: openrouter_decisions`) — OpenRouter kaliti faqat proxy’da (I02); agent Jev’ni chaqira olmaydi |
| Model | pinned `typesafe/jev-1.14`; `~typesafe/jev-latest` alias va `typesafe/jev-router` hech qachon (`model_alias_allowed: false`, `router_allowed: false`) |
| Check’lar | `meta_policy`, `special_ad_category`, `pii_leakage`; savollar inglizcha (`question_language: en`), holat matni o‘zbek/rus |
| Kirish | subject’ning kreativ copy, offer va landing matni; rasm preview faqat `models.pre_screen` rasm tekshiruvini tasdiqlagan bo‘lsa; lead PII hech qachon (`sees_lead_pii: false`, Q28) |
| Lokal PII himoyasi | ikkinchi qatlam (asosiy himoya — Q28: agentlarda lead PII yo‘q): har Jev chaqiruvidan oldin gateway matnni lokal deterministik detektor bilan tekshiradi — `998…` telefon, email, karta va pasport/ID raqami hamda UZ/RU ism va manzil evristikasi — ro‘yxatdagi ism yonida yoki bosh harf (masalan `Karimov A.`) yonida bosh harfli familiya yoki otasining ismi shakli (lotincha `-ov`, `-ova`, `-ev`, `-eva`, `-yev`, `-yeva`, `-ovich`, `-ovna`, `-evich`, `-evna`, `o‘g‘li`, `ogli`, `qizi`; kirillcha `-ов`, `-ова`, `-ев`, `-ева`, `-вич`, `-вна`, `ўғли`, `угли`, `қизи`, `кизи`; kichik harfli so‘z, masalan `курьеров`, hech qachon mos kelmaydi) va manzil naqshi (`ko‘cha`, `mahalla`, `tuman`, `uy`/`kv` + raqam, `ул.`, `д.`, `кв.`; `offers.yaml` dagi biznes manzillari istisno); topilsa Jev chaqirilmaydi va `pii_leakage` lokal bayroqlanadi (faqat qattiqroq), Reviewer va inson approver lokal bayroqni ko‘radi. Guard’ning yolg‘on bayroq ulushi F5-AT-14 da o‘lchanadi va `models.pre_screen` dagi owner tasdiqlagan chegaradan oshmaydi (aks holda guard ko‘p subject uchun Jev’ni o‘chirib qo‘yardi). Qoldiq xavf: bu shakllardan tashqaridagi har ism o‘tadi: yolg‘iz ism, ro‘yxatdagi ism yoki bosh harfsiz yolg‘iz familiya, ro‘yxatda yo‘q ism va boshqa oxirli familiyalar — ular uchun Reviewer’ning `pii_leakage` check’i va inson approver qoladi; owner bu xavfni `models.pre_screen` ni tasdiqlashda qabul qiladi yoki rad etadi (OI-54) |
| Provider | har so‘rovda `data_collection: deny` (Q44★); boshqa provider’ga o‘tish yo‘q |
| Qamrov | `models.pre_screen` (F5-AT-14 eval natijasi): chegaralar, scope (`uz_ru` yoki `ru_only`) va tasdiqlangan snapshot; eval o‘tmasa kalit tasdiqlanmaydi va pre-screen o‘chiq qoladi |
| Ta’sir | faqat qattiqroq (`effect: stricter_only`): bayroq hech qachon `fail`ni `pass`ga aylantirmaydi va Reviewer check’ini olib tashlamaydi; bayroqsiz subject’da verdikt o‘zgarmaydi; Reviewer model slotlari (Q42) o‘zgarmaydi |
| Bayroq qoidasi | bayroqli check Reviewer o‘sha check uchun `pre_screen_response_uz` yozmaguncha `pass` bilan yakunlanmaydi — bunday `review.submit_verdict` rad etiladi; inson approver bayroqni ham, Reviewer javobini ham ko‘radi |
| Ishlamasa | Jev 5xx/timeout yoki xizmat ko‘rsatgan snapshot tasdiqlanganiga teng emas → subject berilmaydi, review kutadi (`unavailable: wait`, `snapshot_mismatch: wait`; zaxira model yo‘q, Q44.3) va `ALERT_WORKFLOW_BLOCKED`; owner `/readiness withdraw models.pre_screen <sabab>` bilan pre-screen’ni o‘chiradi (faqat `review.pre_screen` unga bog‘liq), shundan keyin Reviewer avvalgidek ishlaydi |
| Xarajat va log | input token × tasdiqlangan narx (output bepul) `ai_runtime` hisobida, `reviewer` ulushidan llm-proxy orqali rezerv qilinadi; log — xizmat ko‘rsatgan snapshot, har check ehtimoli, chegara, bayroq, `subject_hash` va narx |

Test — F4-AT-26 (izolyatsiyalangan) va F5-AT-14 (eval).

### 9.3 Verdict sxemasi va agregatsiya

`review.submit_verdict` input sxemasi:

```json
{
  "subject_type": "creative_revision | change_set_item | offer_pr | landing_pr | weekly_report",
  "subject_ref": "string",
  "subject_hash": "sha256 (review.get_subject bergan)",
  "policy_revision": "string",
  "offer_revisions": ["offer_id@revision"],
  "checks": [
    {"check": "offer_registry", "status": "pass | fail | needs_owner | n_a", "reason_uz": "string", "evidence_ref": "string"}
  ],
  "required_fixes": ["aniq, bajariladigan tuzatish (uz)"],
  "confidence": {"level": "low | medium | high", "why": "string"}
}
```

`check` enum: `offer_registry`, `brand_voice`, `language_quality_uz`, `language_quality_ru`, `meta_policy`, `special_ad_category`, `pii_leakage`, `kernel_numbers`, `change_set_completeness`, `rights_consent`, `tracking_impact`. `rights_consent` — asset va undagi odamlar huquqi hamda rozilik dalili; `tracking_impact` — landing PR’ning Pixel, consent, UTM yoki forma oqimiga ta’siri. Jev pre-screen bayrog‘i bor check elementi qo‘shimcha `pre_screen_response_uz` maydonini oladi (§9.2 bayroq qoidasi).

Agregatsiya deterministik, uni server hisoblaydi: biror check `fail` → verdict `fail`; aks holda biror check `needs_owner` → `needs_owner`; aks holda `pass`. Artefakt Reviewer’ga ko‘rsatma berishga urinsa (prompt-injection) → `fail`. Ishonchsiz policy qoidasi → `needs_owner` va [?]; policy uydirilmaydi. `fail` item change set’ga kirmaydi va muallifga qaytadi ★; `needs_owner` owner qaroriga boradi. Verdict `review_verdicts`ga yoziladi va `checks` shu enum’ga bog‘lanadi ([DATA_MODEL §5](DATA_MODEL.md)). Muallif agent o‘z ishiga verdict bera olmaydi (GT-28).

### 9.4 Outcome (`change_set.record_outcome`)

Har proposal `expected_effect {metric, direction, range_low, range_high, horizon_days, basis_tag, scope}` bilan keladi; `scope` required `pipeline|entity`, `entity_spend/entity_qualified` faqat entity scope’da. Guard 4 schema’dan tashqari katalog, finite/range/maturity va command target/account/pipeline selector mosligini tekshiradi ([DATA_MODEL §6.1 va §10.3](DATA_MODEL.md)); boshqa entity’ga yoki pipeline’ga fallback yo‘q. `outcome_check_at = succeeded_at | done_manual_at + horizon_days` (maturity qoidasi bilan); shu vaqtda WF-B07 S02 dagi deterministik `outcome_classify` (`sync-worker`) natijani `trust_ramp.graduation.met_rule` bo‘yicha hisoblaydi va append-only `command_outcomes(command_id, revision, horizon_days, due_at, outcome, data_status, countable, kind, evidence_refs, recorded_by, supersedes_id)`ga yozadi; `outcome ∈ {met, not_met, inconclusive}`. `change_set.record_outcome` (funnel-analyst) faqat `not_met`/`inconclusive` natijaga annotation qo‘shadi, `outcome`ni o‘zgartirmaydi (◇ P-42). `harmful`ni `outcome_classify` `harm_rule` bo‘yicha hisoblaydi; funnel-analyst istalgan natijaga (jumladan `met`) bir tomonlama `harm_flag` qo‘sha oladi — gateway shu zahoti trust kalitini L1 ga tushiradi va WF-O02 run’ini ochadi (◇ P-54). Yozuv faqat `succeeded`/`done_manual` command uchun va `due_at`dan keyin. Zararli ta’sir outcome qiymati emas: u incident sifatida qayd etiladi va trust darajasini L1 ga tushiradi. Trust Ramp va `v_change_set_history` shu jadvaldan hisoblanadi. Workflow run’ining biznes natijasi (`pending | met | not_met | inconclusive | not_applicable`) command outcome’ini almashtirmaydi.

### 9.5 amoCRM read field allowlist

`amocrm-mcp` (`amt-amo`) lead obyektidan faqat quyidagilarni qaytaradi: `id`, `pipeline_id`, `status_id`, `created_at`, `updated_at`, `closed_at`, `loss_reason_id`, `AMT:` va allowlist’dagi teglar, hamda [TRACKING_CAPI §3](TRACKING_CAPI.md)da agentga ko‘rinadi deb belgilangan custom field’lar sanitized qiymat bilan (`amt_fbc`, `amt_fbp`, `amt_client_ip`, `amt_client_ua` o‘rniga faqat `has_fbc`/`has_fbp`). `_embedded.contacts`, ism, telefon, email va notes matni hech qachon qaytarilmaydi. So‘rovlar ✅ Q25 ceiling ichidagi ajratma bilan, batch ≤50 ★ [D: amoCRM API hujjati; F2’da tekshiriladi]. Sync-worker uchun bitta qo‘shimcha o‘qish: webhook obunalari ro‘yxati — faqat `mar2/amo/<secret>` manzilli obunaning holati (`disabled` bayrog‘i va hodisalar ro‘yxati) kuniga bir marta (`operations.yaml#integration_watch[amo_webhook_liveness].subscription_read`); boshqa obunalar qaytarilmaydi, obuna yaratish yoki o‘zgartirish yo‘q; endpoint va admin huquqi kerakligi F2’da tekshiriladi [T, VR-16].

### 9.6 Backend va credential custody

| Tool guruhi | Backend | Credential (env) va egasi |
|---|---|---|
| `meta_read.*` | `meta-ads-mcp` (byadsco, pinned ≥ v4.0.0), UID `amt-meta-read` | `META_READ_TOKEN` (system user `amt-read`, `ads_read`) faqat shu child’da |
| `meta_write.*` ijrosi | `amt-executor`, rasmiy Business SDK | `META_WRITE_TOKEN` (system user `amt-write`) faqat executor’da; gateway’da yo‘q |
| `amo.*` | `amocrm-mcp`, UID `amt-amo` | `AMO_TOKEN` faqat shu connector’da; kvota `AMO_QUOTA_ALLOCATION_ID` |
| `drive.*` | Google Drive API, faqat AMT papkasi | `GDRIVE_SERVICE_ACCOUNT_JSON_PATH` (read) gateway’da; upload credential faqat ops-bot’da |
| `landing.open_pr` | GitHub `wolter-landing` | `GITHUB_TOKEN_LANDING` — faqat PR scope; admin va merge yo‘q |
| `offers.propose_pr` | GitHub `wolter-amt` | `GITHUB_TOKEN_AMT_OFFERS` — faqat offers PR scope |
| `media.generate_*` | `llm-proxy` → OpenRouter | `LLMPROXY_GATEWAY_TOKEN` (faqat media va Jev pre-screen’ning Decisions endpoint’i, Q61); OpenRouter kaliti faqat proxy’da; agent tokenlari media va Decisions endpoint’lariga chiqa olmaydi |
| `analytics.*` | Umami API, Clarity Data Export API | `UMAMI_API_TOKEN`, `CLARITY_API_TOKEN` (read) |
| `wh.*`, `fleet.read_utilization` | PostgreSQL `amt_ro` view’lari | `GATEWAY_READER_DATABASE_URL` (read-only role) |
| `render.*` | `render-worker`, UID `amt-render` | credential yo‘q |

### 9.7 Inson til tekshiruvi (gateway tomoni)

`creative_review`: `independent_reviewer_required: true`, `human_check_substitutes_reviewer: false`. `asset_upload`, `ad_create` va `creative_activate` mustaqil Reviewer pass va talab qilingan inson til tekshiruvini ikkalasini tekshiradi; biri ikkinchisining o‘rnini bosmaydi.

Qamrov (✅ Q42; sanash qoidasi ◇ P-15): loyiha bo‘yicha birinchi 20 ta jonli publish’ga yaroqli copy artifact (`count_scope: live_eligible_copy_artifacts`; shadow, eval va test sanalmaydi) va ularning barcha keyingi revision’lari (`revisions_inherit_check_requirement: true`). Yangi fayl nomi yoki 21-artifact qilib birinchi 20 talikni chetlab o‘tish yo‘q. Tekshiruvchi — effective `language_checker` flag’i, `native_language_attested = uz`, active person va active membership egasi; callback approval kabi tekshiriladi ([TELEGRAM §2.3](TELEGRAM.md)). RU copy qoidasi ⧗ OD-08: qaror bo‘lguncha qamrovdagi RU copy inson tekshiruvisiz publish qilinmaydi.

`human_checks` evidence binding: `creative_revision`, `asset_manifest_sha`, `offer_revision`, `policy_revision`, `subject_hash`, `person_id`, `membership_revision`, `checker_flag_revision`, `verdict`, `checked_at`, `expires_at`. So‘rov muddati `request_ttl_hours: 12` (javobsiz so‘rov tugaydi, avtomatik o‘tmaydi); natija `result_valid_while` bo‘yicha faqat o‘sha exact creative/asset/offer/policy revision uchun amal qiladi, `expires_at` — bog‘langan offer revision va asset huquqining eng erta muddati; revocation va checker’ning joriy person/membership/flag holati har dispatch, retry va rollback’da qayta tekshiriladi. Inson tekshiruvi Reviewer `fail`/`needs_owner`ni override qilmaydi; material tuzatilgach yangi revision qayta Reviewer’dan o‘tadi.

## 10. Kanonik xato kodlari

Boshqa hujjatlar, testlar va skill’lar faqat shu kodlarni ishlatadi; aniq sabab `reason` maydonida.

| Kod | HTTP | Ma’no |
|---|---|---|
| `unauthorized` | 401 | token/principal/run/service binding noto‘g‘ri yoki subject hash boshqa principal’niki |
| `agent_paused` | 423 | agent yoki uning spending allowance’i pauzada |
| `tool_not_allowed` | 403 | principal tool’iga ruxsat yo‘q (yoki read MCP’ning write tool’i) |
| `invalid_args` | 422 | schema, birlik, uzunlik yoki qiymat validatsiyasi |
| `policy_violation` | 403 | action/path/runtime policy zid (`reason`: masalan `review_fail`, `rights_not_cleared`, `human_check_missing`, `lifetime_budget`) |
| `budget_change_exceeds_limit` | 409 | rolling24h harakat limiti |
| `monthly_cap_exceeded` | 409 | admission sharti bajarilmaydi (§7.3) |
| `foreign_entity` | 403 | ownership/account/pipeline mos emas yoki entity release qilingan |
| `tracking_gate` | 423 | tracking gate hali o‘tmagan (F2_TRACKING_PASS yo‘q), global `read_only` yoki stale source (`reason` bilan) |
| `offer_mismatch` | 409 | offer/revision/expiry yoki da’vo mos emas |
| `write_mode_killed` | 423 | lokal durable kill latch faol yoki epoch eskirgan |
| `pipeline_shadow` | 202 | global `shadow` yoki effective L0: shadow sifatida saqlandi, ijro yo‘q (`status: shadow`) |
| `rate_limited` | 429 | caller yoki umumiy kvota |
| `pii_blocked` | 422 | qiymat darajasida PII yoki sir aniqlandi |
| `needs_owner` | 202 | owner qarori kerak (`status: needs_owner`); muvaffaqiyat emas |
| `state_drift` | 409 | kutilgan remote revision/state o‘zgardi |
| `revision_stale` | 409 | payload/asset/review/human check/role/policy/config revision yaroqsiz yoki subject hash eskirgan |
| `execution_uncertain` | 202 | tashqi natija hal qilinmagan, retry yopiq |
| `readiness_blocked` | 423 | readiness, ACK, capability profili, capacity/sale/biznes natija guard’i yoki audit yozuvi yetishmaydi (`reason` bilan) |

### 10.1 llm-proxy xato kontrakti

| Kod | HTTP | Ma’no | Retry |
|---|---|---|---|
| `agent_paused` | 423 | agent yoki uning ulushi pauzada (`agent_runtime_state`) | yo‘q |
| `allowance_exhausted` | 402 | agent/media ulushi yoki key cap tugadi; OpenRouter 402 (kredit yetmaydi) yoki `error.metadata.limit_source`li 403 (`openrouter_key_limit`, `openrouter_workspace_budget`, `openrouter_guardrail_budget` — so‘rov provayderga yetmasdan rad etilgan, VR-42) ham shu kod; proxy `limit_source`ni ledger’ga yozadi (INC-06) | yo‘q |
| `price_unknown` | 422 | model yoki media narxining upper bound’i yo‘q | yo‘q |
| `write_mode_killed` | 423 | kill latch faol | yo‘q |
| `input_over_bound` | 413 | so‘rovning dispatch’dan oldingi input hisobi rolning `budget.request_bounds` `max_input_tokens`idan oshdi (harness, tool ta’riflari va transcript bilan; ◇ P-86, P-88) | yo‘q; so‘rov yuborilmaydi, step `workflow.report_blocker` bilan to‘xtaydi — sessiya jim o‘smaydi |
| `slot_wait_exceeded` | 423 | rolning `max_concurrency` slot’lari band (ishlayotgan yoki settle bo‘lmagan `uncertain` so‘rovlar) va navbatdagi so‘rov pinned adapter’ning o‘z timeout’idan oldin slot ololmadi (`budgets.yaml#openrouter.reservation_sizing`, ◇ P-86) | proxy o‘zi qayta urinmaydi; step `max_attempts_per_step` ichida qayta chaqiradi, tugagach `workflow.report_blocker` |
| `upstream_unavailable` | 424 | OpenRouter yoki model provayderi 408, 429 yoki 5xx (`timeout` 504 ham) qaytardi, ulanish xatosi bo‘ldi yoki `upstream_deadline` ichida javob kelmadi; yoki provayder so‘rovni qabul qilgandan keyin xato bo‘ldi — HTTP 200 tanasida `error` maydoni yoki stream’da SSE `error` event’i (`finish_reason: "error"`) (VR-42); zaxira yo‘l yo‘q (✅ Q44.3; `allow_fallbacks: false` OpenRouter’ning avtomatik zaxira provayderini ham o‘chiradi) | proxy o‘zi qayta urinmaydi; javobda maslahat `retry_after_s` (upstream `Retry-After` bo‘lsa shu); agent step’ning `max_attempts_per_step` ichida qayta chaqirishi mumkin, tugagach `workflow.report_blocker` (`llm_upstream_unavailable`) |
| `upstream_refused` | 422 | OpenRouter so‘rovni qayta yuborish bilan o‘zgarmaydigan sabab bilan rad etdi: `limit_source`siz 403 (guardrail bloki yoki moderation flag; sabab `error.metadata`da) yoki boshqa 4xx (400, 401, 404, 413 …; 401 — proxy kaliti nosoz) (VR-42); ro‘yxatda yo‘q har upstream natijasi ham shu kod (`upstream_contract.unmatched_result`) | yo‘q; proxy qayta urinmaydi, step `workflow.report_blocker` (`llm_upstream_refused`) bilan to‘xtaydi; `ALERT_AGENT_ERROR` detektoriga kiradi |

Birinchi to‘rt kod, `input_over_bound` va `upstream_refused` retry qilinmaydi; `slot_wait_exceeded` faqat step chegarasi ichida qayta chaqiriladi. HTTP kodlari agent mijozining (SDK yoki Claude Code) avtomatik retry’i loop yaratmasligi uchun tanlangan — 408, 409, 429 va 5xx ishlatilmaydi (VR-41); bundan tashqari har pinned adapter o‘z retry’isiz ishlaydi (`runtime-isolation.yaml#runner_contract.llm_client`: `max_retries: 0`, Claude Code retry watchdog’i yo‘q). Upstream javobi `budgets.yaml#openrouter.upstream_contract` yopiq ro‘yxati bo‘yicha o‘qiladi (VR-42): HTTP 200 faqat tanasida `error` yo‘q va stream oxirgi event’ining `finish_reason`i `error` bo‘lmasa muvaffaqiyat; agent stream’i boshlangandan keyingi xato shu kodli terminal xato event’i bilan yopiladi, ulanish uzilmaydi (uzilgan ulanishdan keyin adapter so‘rovni o‘zi takrorlaydi). Proxy’ning `upstream_deadline`i har pinned adapterning eng kichik mijoz timeout’idan qisqa (F1-AT-28 o‘lchaydi), shuning uchun adapter o‘z timeout’iga yetmaydi: upstream’ning 408/429/5xx/timeout xatosi ham agentga 424 bo‘lib qaytadi va qayta urinishni SDK emas, step chegarasi boshqaradi. Reservation upstream xatosida ham §7.5 qoidasi bilan qoladi (`pending`/`uncertain` → `provider_usage_snapshots` bilan reconcile; narx nol deb olinmaydi); upstream xatolari ulushi `ALERT_AGENT_ERROR` detektoriga kiradi [T: har pinned adapter’ning retry va timeout xulqi F1’da isbotlanadi, F1-AT-28].

## 11. Qabul dalillari

F3 gateway/RBAC salbiy testlari har agent, tool va rol uchun: integer birlik va scoped foreign entity, replay approval, state drift, fake reviewer va berilmagan `subject_hash`, DB audit failure, quarantine media, path/symlink, L0 va test activation, tracking bir/ikki kun va stale, barcha caller kvotasi, javob kontrakti, protective pause va biznes natija guard’i. UAT-13–20 dispatch, lease/fence, uncertain, rolling24h, MTD/currency va AI parallel reservation’ni; UAT-14/21/22 lokal kill birinchi va B partial’ni; UAT-24/25 restore va schema’ni; UAT-26–28 offer, identity va config’ni; UAT-31 Reviewer va inson tekshiruvini yopadi. Testlar [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md)da; runtime dalilisiz PASS belgilanmaydi.

### F3 regression case identifikatorlari

Quyidagi identifikatorlar faza testlari bilan traceability uchun; UAT guruhlari ularning crash/production chegaralarini kengaytiradi. Hozirgi hujjat ularni bajarilgan deb belgilamaydi.

| Case | Fixture va talab qilingan natija |
|---|---|
| GT-01 | Creative Studio budget write → `tool_not_allowed` + audit |
| GT-02 | +25% budget → `budget_change_exceeds_limit` |
| GT-03 | Ikki +15% yoki kamaytirib qayta oshirish → absolute yig‘indi limiti chetlab o‘tilmaydi |
| GT-04 | Float yoki string pul → `invalid_args` |
| GT-05 | Currency minor offset/FX fixture → exact integer provider qiymati; noma’lum konversiya deny |
| GT-06 | Begona account/entity → `foreign_entity` |
| GT-07 | Parallel yoki replay approval callback → bitta revision transition va bitta dispatch |
| GT-08 | Inson budget drift’i → `state_drift`; eski approval ijro qilinmaydi |
| GT-09 | CRM/UTM/tag qiymatidagi telefon/email/ism → agent, log va trace’da yo‘q |
| GT-10 | Erkin matnli injection → policy yoki approval o‘zgarmaydi |
| GT-11 | `read_only`da normal write → `tracking_gate` + `reason` |
| GT-12 | Global `shadow` yoki pipeline L0 → `{status: shadow}` (`pipeline_shadow`), ijro yo‘q; shadow item TTL’da `expired` |
| GT-13 | Create campaign → PAUSED va explicit tekshirilgan special ad category |
| GT-14 | Reviewer fail/expiry/revoke yoki majburiy inson tekshiruvi yo‘q → publish rad |
| GT-15 | Noto‘g‘ri narx yoki offer revision → `offer_mismatch` |
| GT-16 | A/B kill → avval lokal latch, restart’da deny; B’da remote partial ro‘yxat va reconciliation |
| GT-17 | Paused agent → `agent_paused`, Paperclip ishlamasa ham |
| GT-18 | Landing+CAPI+sync+MCP+operator parallel → amoCRM jami ✅ Q25 ceiling 7 req/s va tasdiqlangan ajratmalar ichida; 429 bo‘roni yo‘q |
| GT-19 | Landing PR’da taqiqlangan yo‘l yoki generated offer snapshot → `policy_violation` |
| GT-20 | Audit/attempt commit failure → normal tashqi write yo‘q (`readiness_blocked`, `audit_unavailable`) |
| GT-21 | Vendor read MCP write tool’ini to‘g‘ridan-to‘g‘ri chaqirish → deny |
| GT-22 | Provider spending limit yo‘q yoki API read-back kutilgan qiymatga teng emas → `sync-worker` `provider_limit_read_only` so‘raydi: yangi risk write deny, global `read_only`, `ALERT_SPEND_CAP_HEADROOM`; read-back mos kelgach owner `/resume`; `protective_pause` uning o‘rnini bosmaydi |
| GT-23 | ads_approver birinchi campaign/ad set activation’ini tasdiqlaydi → `needs_owner` |
| GT-24 | NEVER_AUTO action uchun L2 graduation → deny |
| GT-25 | Admission sharti buziladi (verified MTD + faol kunlik × qolgan kunlar + held + requested > cap − margin) → `monthly_cap_exceeded`; counter nomosligi → reconciliation yoki owner tuzatishi; dalilsiz hard-cap PASS yo‘q |
| GT-26 | Rent kill criteria → faqat rent L0 va handback; sale ownership mustaqil |
| GT-27 | Boshqa agent tokeni/process, soxta Reviewer yoki berilmagan `subject_hash` bilan verdict → UID/credential chegarasida va hash tekshiruvida deny |
| GT-28 | Creative Studio o‘z kreativiga verdict → `tool_not_allowed` |
| GT-29 | Bir kun fail → alert; ikki ketma-ket kun → `read_only`; missing job alohida freshness deny |
| GT-31 | Har allowlist tool’i o‘z `schemas/tools/<tool>.schema.json` sxemasiga qarshi: noma’lum maydon, float yoki string pul, currency’siz `*_minor`, 2000 belgidan uzun yoki boshqaruv belgili erkin matn, `wh.query`ga xom SQL, render parametrida URL yoki yo‘l → `invalid_args`, tashqi chaqiruv yo‘q (F3-AT-32) |
| GT-50 | `workflow.submit_output`: `analysis` konverti sxemadan tashqari (masalan `handoff` 8 band) yoki `analysis_max_chars` dan katta, `definition_digest` pin’ga mos emas, `round` `on_reject.max_rounds` dan oshgan yoki payload sxemaga mos emas → `invalid_args`, handoff qabul qiluvchiga ko‘rsatilmaydi (`workflow-policy.yaml#handoff_validation`) |
| GT-51 | Oxirgi pauzasi `protective_pause` (`protective_actions`) bo‘lgan entity uchun `entity_activate`/`creative_activate`: ads_approver tasdig‘i → `needs_owner`; o‘sha action × pipeline L2’ga graduation qilingandan keyin ham policy approval yo‘q → owner navbati; ops-bot callback’ida ads_approver tugmasi rad; owner tasdig‘i → dispatch (case `re_activation_after_protective_pause`) |
| GT-30 | Owner tasdiqlagan scoped PAUSED `origin=test` fixture: F2_TRACKING_PASS dan oldin → `tracking_gate` rad; keyin faqat ruxsatlangan non-activation; `killed`/`read_only`/live delivery bypass yo‘q |
