# DATA MODEL — durable ledger va warehouse

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

PostgreSQL `amt` deterministik command, ledger, sanitizatsiyalangan biznes hodisalari, workflow holati va operatsion holatni saqlaydi. Paperclip o‘z `paperclip` bazasida qoladi. PII custody alohida credential va storage bilan ajratiladi; warehouse’ning PII-free talabi real shaxs bilan bog‘lanadigan ID’ni avtomatik anonim deb e’lon qilmaydi. [INVARIANTS](../11_Production_Contracts/INVARIANTS.md), [BUSINESS_CONTRACT](../11_Production_Contracts/BUSINESS_CONTRACT.md) va config shablonlari bu hujjatdan ustun ([DECISION_LOG §0](../00_Decisions/DECISION_LOG.md)). Servis va DB rol nomlari [ARCHITECTURE §3](ARCHITECTURE.md) reyestridan. Quyidagi jadval, ustun va funksiya nomlari mantiqiy kontrakt; konkret migration F1–F3 va FE’da yoziladi, bu hujjat bajarilgan migration emas.

## 1. Global ma’lumot shartlari

| Qatlam | Majburiy qoida |
|---|---|
| Vaqt | event/source/received/processed vaqtlari alohida `timestamptz`; DB UTC, biznes hisobot Asia/Tashkent; Meta account timezone alohida |
| Pul | `bigint *_minor`, explicit ISO currency; manfiy refund/adjustment alohida event turi va original reference bilan; float pul yo‘q. Cap’lar: AI runtime USD 150/oy (15 000 USD minor), paid Meta USD 1 500/oy (150 000 USD minor) |
| Noma’lum | null qiymat va quality/status sababi; unknown nol, false, lost yoki PASS bo‘lmaydi |
| Revision | tasdiqqa ta’sir qiluvchi nusxalar immutable; supersede/revoke yangi yozuv yoki event bilan |
| Majburiy ustun | barcha PK, FK identity, pipeline, state, timestamp, currency va hisob qiymatlari `NOT NULL`, agar quyida explicit NULL yozilmagan bo‘lsa |
| Enum | CHECK yoki type bilan; qiymatlar faqat config’dagi to‘plamdan; erkin matn holatga aylantirilmaydi |
| Enum manbai | command state va qo‘shimcha o‘tishlar, global/pipeline rejim — `execution-policy.yaml`; approval qarori, action, trust o‘qi — `approval-policy.yaml`; `data_status` — `business-policy.yaml`; tracking check holati — `tracking-health.yaml`; workflow run/step/handoff/natija — `workflow-policy.yaml` |
| Tashqi ID | scope: provider+account+ID; multi-account collision oldi olinadi |
| JSON | server schema bilan tekshirilgan, hajmi cheklangan, sir/PII’siz; obyekt maydoni allowlist’i qiymat sanitizatsiyasini bekor qilmaydi |
| PII custody | custody dataset’lari `privacy-policy.yaml` `datasets`da; warehouse faqat opaque reference saqlaydi |
| Audit | transition+outbox+audit bitta transaction; tashqi effekt DB transaction ichida “exactly once” deb olinmaydi |

`NULL` ruxsat etilgan har bir maydon missing ma’nosiga ega: masalan `crm_lead_id=NULL` tasdiqlanmagan delivery, `actual_minor=NULL` noma’lum billing. `reserved_minor` esa NULL emas va uncertain settle bo‘lmaguncha ushlab turiladi.

## 2. Schema, DB rollari va yozish vakolati

### 2.1 Sxema va rollar

`amt` — base jadvallar; barcha obyektlar egasi NOLOGIN `amt_migrator`. `amt_ro` — sanitizatsiyalangan view’lar; agentlar faqat gateway’ning `amt_reader` ulanishi (`wh.query`, `wh.metrics`) orqali o‘qiydi va base schema’ni ko‘rmaydi. Umumiy `amt_writer` yo‘q.

Q65 trust-root istisnosi faqat ilk F1 initialization’da: owner SSH’dan ishga tushirgan pinned fixed bootstrap importer bitta one-shot function orqali `typed_confirmations`, `release_approvals`, `audit_log` va `release_initializations`ni atomik yozadi ([FIRST_RELEASE](../05_Build_Phases/FIRST_RELEASE.md), `release-policy.yaml#initial_release`). Bu yangi doimiy LOGIN yoki runtime writer grant’i emas; builder/agentga credential berilmaydi. Oldingi state’ni almashtirish, role export’ni reseed qilish yoki keyingi release approval’ini shu yo‘l bilan yozish rad. Oddiy DB writer matritsasi quyida saqlanadi.

| DB rol | Servis (UID) | Asosiy vakolat |
|---|---|---|
| `amt_migrator` | — (NOLOGIN) | barcha obyektlar egasi; DDL faqat release `prepared` bosqichida |
| `amt_migrate` | `amt-release` fixed entrypoint’ining faqat migration qadami | LOGIN, NOINHERIT, faqat `SET ROLE amt_migrator`; runtime servislar ishlatmaydi |
| `amt_reader` | `gateway` (`GATEWAY_READER_DATABASE_URL`) | faqat `amt_ro` SELECT |
| `amt_auth` | `tg-auth` (`amt-auth`) | sessiya, login, break-glass; people/roles/flags SELECT |
| `amt_ops` | `ops-bot` (`amt-ops`) | approval, typed confirmation, people/role/flag funksiyalari, fleet/sale/kontent metadata, ACK, `telegram` outbox kanali |
| `amt_gateway` | `gateway` (`amt-gateway`) | command yaratish, review subject va verdict, creative registri, outcome, experiment |
| `amt_executor` | `executor` (`amt-executor`) | claim, attempt, Meta natijasi, pause-only natijalar |
| `amt_control` | `amt-control` | `gateway_state`, `control_events`, kill va protective yozuvlari, `readiness_records`/`readiness_signatures` |
| `amt_amo` | `amocrm-mcp` (`amt-amo`) | amo write command’larining attempt’lari |
| `amt_quota` | `quota-coordinator` (`amt-quota`) | quota allocation va lease |
| `amt_proxy` | `llm-proxy` (`amt-proxy`) | AI request, reservation, settlement (`ai_runtime`) |
| `amt_capi` | `capi-bridge` (`amt-capi`) | inbox, CAPI ledger, source event ingest |
| `amt_sync` | `sync-worker` (`amt-sync`) | sync, cursor, snapshot, tracking, kill-criteria va pacer kirishlari |
| `amt_watchdog` | `cost-watchdog` (`amt-watchdog`) | provider usage snapshot va cost reconciliation |
| `amt_workflow` | `amt-workflow` | workflow jadvallari ([WORKFLOW_RUNTIME §3](WORKFLOW_RUNTIME.md)), evolution signal/proposal/manifest/memory |
| `amt_release` | `amt-release` | release manifest, activation, harness handover, offer import |
| `amt_verify` | `amt-verify` | verification result |
| `amt_eng_proxy` | `amt-eng-proxy` | `engineering` hisobi reservation va settlement |
| `amt_backup` | `amt-backup` | faqat o‘qish (`pg_read_all_data`); yozish yo‘q |

DB roli yo‘q: `caddy`, `telegram-bot-api`, `hermes`, `managed-runner`, `meta-ads-mcp`, `stt-local`, `render-worker`, `amt-sandbox`, barcha agent va engineering UID’lari. `paperclip` va `langfuse` o‘z bazalarida; landing o‘z hostidagi storage’da.

### 2.2 Grant va funksiya qoidalari

- Hech bir runtime rolda DDL, TRUNCATE yoki boshqa servis jadvaliga keng UPDATE/DELETE yo‘q; yozish faqat §2.3 dagi rol va usul bilan.
- `SECURITY DEFINER` funksiyalari: egasi `amt_migrator`, fixed `search_path`, PUBLIC’dan EXECUTE olingan, faqat ro‘yxatdagi rolga EXECUTE; parametr schema va caller scope (`session_user` → servis) tekshiriladi; mutable SQL yoki ixtiyoriy target qabul qilmaydi.
- Audit faqat `append_audit()`; `UPDATE/DELETE audit_log` barcha rollarga rad.
- Append-only jadvallarda (`approvals`, `command_outcomes`, `lead_stage_events`, `business_events`, `roles_audit`, `workflow_events` va boshqalar) correction yangi qator bilan.
- Retention o‘chirishi faqat dataset egasi rolidagi `apply_retention(dataset)` bilan, tombstone va audit bilan.
- Grantlar ijobiy va salbiy test bilan F1/F3’da isbotlanadi (F1-AT-15, F3-AT-22).

### 2.3 Jadval × rol matritsasi

Belgilar: `I` — INSERT; `U(…)` — faqat ko‘rsatilgan ustun yoki holat; `fn()` — faqat shu funksiya orqali; `R` — SELECT. `amt_backup` barcha jadvalda faqat R va jadvalda takrorlanmaydi.

| Jadval / view | Yozish (rol → usul) | O‘qish | Izoh |
|---|---|---|---|
| `submission_receipts`, `submission_attempts`, `submission_resolution` | landing intake/delivery (landing hosti, `amt` roli emas) | landing | PII custody `landing_submission_store` |
| `submission_delivery` | `amt_sync` → `upsert_submission_delivery()` | `amt_capi`, `amt_ops`; `amt_reader` → `v_intake_delivery` | PII’siz |
| `webhook_inbox` | `amt_capi` → I, U(state, lease) | `amt_capi`, `amt_sync` | faqat allowlist maydonlar; raw body diskka yozilmaydi (Q62) |
| `schedule_runs` | jadval job’ini bajaruvchi servis rolining o‘zi (`amt_sync`, `amt_ops`; `amt-backup` ledger’i) → I | `amt_workflow` (yo‘q yozuvni aniqlaydi va `missed_run_alert` ni chiqaradi), `amt_ops` | har `operations.yaml#schedule` job tick’i uchun bitta yakun yozuvi; yo‘qligi `ALERT_SCHEDULE_MISSED` (backup — `ALERT_BACKUP_STALE`) |
| `delivery_outbox` | yaratish: `enqueue_outbox()` — `amt_gateway`, `amt_executor`, `amt_ops`, `amt_control`, `amt_capi`, `amt_sync`, `amt_watchdog`, `amt_workflow`, `amt_release`; holat: kanal iste’molchisi `claim_outbox()`, `finish_outbox()` | kanal iste’molchisi; `amt_ops` | §3.3 |
| `capi_events`, `capi_attempts` | `amt_capi` → I, U(state) | `amt_sync`, `amt_ops`; `amt_reader` faqat agregat | raw user_data yo‘q |
| `monitor_acks` | `amt_control` → I (monitor heartbeat’ni ACK qilganda: heartbeat ID, `observed_at` — yuborilgan vaqt — va ACK vaqti) | `amt_capi` (ACK olgan oxirgi heartbeat’ning `observed_at` i — `capi_dispatch_lease`), `amt_ops` | PII yo‘q; heartbeat’ning DB’dan olinadigan maydonlarini (`capi_terminal_before`, audit zanjiri boshi — seq va hash, backlog soni va eng eski yoshi, oxirgi durable acceptance/delivery/checkpoint vaqtlari) `amt_control` faqat `heartbeat_snapshot()` orqali oladi (`SECURITY DEFINER`, EXECUTE faqat `amt_control`; `capi_events`, `sync_cursors`, `audit_log`, `delivery_outbox` va `submission_delivery` ga grant yo‘q) |
| `consent_references` | `amt_sync`, `amt_capi` → `ingest_consent()` (append) | `amt_capi`, `amt_gateway`, `amt_sync` | withdrawal yangi event |
| `leads_snapshot` | `amt_capi`, `amt_sync` → `upsert_lead_snapshot()` | `amt_gateway`, `amt_sync`; `amt_reader` → `v_leads` | |
| `lead_stage_events`, `business_events`, `cash_events` | `amt_capi`, `amt_sync` → `ingest_source_event()` | `amt_sync`, `amt_gateway` | append-only, idempotent unique key |
| `cohort_metrics`, `baselines` | `amt_sync` → I (yangi revision); `baselines.frozen_at` — `amt_ops` → `freeze_baseline()` | `amt_gateway`, `amt_sync` | freeze `business.baseline` owner tasdig‘idan keyin |
| `ad_insights_daily`, `ads_spend_snapshots`, `account_snapshots` | `amt_sync` → I | `amt_gateway`, `amt_executor`, `amt_ops`, `amt_control` | |
| `offer_revisions` | `amt_release` → `import_offer_revision()` (release activation) | `amt_gateway`, `amt_executor`, `amt_ops` | owner merge’dan keyin |
| `asset_versions`, `drive_assets` | `amt_ops` → I (upload, quarantine); `amt_gateway` → I (generated/rendered); rights — `amt_ops` → `set_asset_rights()` | `amt_gateway`, `amt_executor` | uploader ≠ clearer |
| `creatives`, `creative_revisions`, `copy_artifacts` | `amt_gateway` → `register_creative()` | `amt_ops`, `amt_executor` | |
| `review_subjects` | `amt_gateway` → `issue_review_subject()` | `amt_gateway` | immutable |
| `review_verdicts` | `amt_gateway` → `submit_verdict()` | `amt_ops`, `amt_executor` | faqat berilgan `subject_hash` |
| `command_review_bindings` | `amt_gateway` → `bind_command_review()` (`submit_verdict()` bilan bitta transaction) | `amt_gateway`, `amt_ops`, `amt_executor`, `amt_amo` | append-only; UNIQUE `(command_id, command_revision)`; §6.1 |
| `command_approval_bindings` | `amt_ops` → `freeze_approval_binding()` (`mark_presented()`dan oldin); policy/auto yo‘lda `amt_gateway` → ayni funksiya | `amt_gateway`, `amt_ops`, `amt_executor`, `amt_amo` | append-only, bitta command revision uchun bitta muzlatilgan dependency snapshot; §6.1 |
| `human_checks` | `amt_ops` → `record_human_check()` | `amt_gateway`, `amt_executor` | |
| `creative_ad_bindings` | `amt_executor` → I | `amt_gateway`, `amt_sync` | |
| `dependency_invalidations` | `amt_gateway`, `amt_release`, `amt_ops` → `invalidate_dependents()`; disposition — `amt_ops` | `amt_gateway`, `amt_executor` | |
| `change_set_items` | yaratish: `amt_gateway`, `amt_control` → `create_command()`; holat: `transition_command()` (rol bo‘yicha §6.2); `presented_at` — `amt_ops` → `mark_presented()` | `amt_gateway`, `amt_executor`, `amt_amo`, `amt_ops`, `amt_control`, `amt_workflow` | |
| `approvals` | `amt_ops` (inson), `amt_gateway` (policy) → `record_approval()` | `amt_executor`, `amt_amo`, `amt_gateway` | append-only |
| `execution_attempts` | `amt_executor` (Meta), `amt_amo` (amo write) → I, U(o‘z attempt’i, fence bilan) | `amt_gateway`, `amt_ops`, `amt_control` | |
| `command_outcomes` | `amt_sync` → `classify_outcome()` (natija qatori, WF-B07 S02); `amt_gateway` → `record_outcome()` (faqat annotation qatori, funnel-analyst) | `amt_ops`, `amt_sync`, `amt_control` | append-only |
| `step_command_links` | `create_command()` ichida | `amt_workflow`, `amt_ops` | |
| `shadow_ratings` | `amt_ops` → I | `amt_gateway` | |
| `budget_accounts`, `reservations`, `budget_entries` | davr qatori: scope yozuvchisi → `open_budget_period()`; `ai_runtime`: `amt_proxy`; `engineering`: `amt_eng_proxy`; `ads`: `amt_gateway` (admission), `amt_executor` (settle, uncertain), `amt_ops` va `amt_control` (release) — faqat `reserve_*()`, `settle_*()`, `release_*()` | `amt_watchdog`, `amt_ops` | cap faqat signed config’dan |
| `ai_requests` | `amt_proxy` → I, U(state, usage, actual) | `amt_watchdog`, `amt_ops` | |
| `provider_usage_snapshots` | `amt_watchdog` → I | `amt_proxy`, `amt_ops` | usage-read credential watchdog’da |
| `agent_runtime_state` | `amt_control` → `set_agent_runtime_state()` | `amt_gateway`, `amt_proxy`, `amt_ops` | watchdog so‘rovi RPC orqali |
| `budget_overrides` | `amt_ops` → owner `budget_override` | `amt_proxy`, `amt_watchdog` | |
| `budget_change_ledger` | `amt_executor` (succeeded change), `amt_sync` (kuzatilgan inson drift) | `amt_gateway`, `amt_executor` | |
| `protective_actions` | `amt_control` → I, U; per-entity natija — `amt_executor` → `record_protective_result()` | `amt_ops`, `amt_sync` | |
| `people`, `roles`, `person_flags`, `responsibility_assignments`, `roles_audit` | `amt_ops` → `role_change()` (owner typed confirmation); seed — `import_role_seed()` | `amt_auth`, `amt_gateway`, `amt_executor`, `amt_control`, `amt_ops` | last-owner guard |
| `readiness_records`, `readiness_signatures` | `amt_control` → `record_readiness_evidence()` (control op `readiness_evidence`: `amt-workflow`, `amt-release`), `sign_readiness()` (control op `readiness_sign`: `amt-ops`, typed confirmation `readiness_signoff`) | `amt_release`, `amt_gateway`, `amt_ops`, `amt_workflow` | |
| `typed_confirmations` | normal `amt_ops` → I; Q65 first-only fixed importer §9.1; iste’mol — `amt_control`, `amt_ops` → `consume_confirmation()` | `amt_control` | |
| `sessions`, `login_requests`, `breakglass_codes` | `amt_auth` → I, U; login qarori — `amt_ops` → `decide_login_request()` | `amt_auth` | xodim ma’lumoti |
| `gateway_state`, `control_events`, `kill_switch_events` | faqat `amt_control` funksiyalari | barcha servis rollari R (`gateway_state`); `amt_ops`; `amt_sync` R (`control_events` — upgrade va incident kuzatuv step’lari) | §2.4 |
| `managed_entities` | `amt_ops` → `takeover_scope_change`; `amt_executor` → created/duplicated, `ever_active`; `amt_control` → `release_managed_entities()` | `amt_gateway`, `amt_executor`, `amt_sync`, `amt_control` | |
| `tracking_health`, `tracking_streaks` | `amt_sync` | `amt_gateway`, `amt_control`, `amt_ops` | |
| `fleet_snapshots`, `waitlist_aggregates` | `amt_ops` (wizard); `waitlist_aggregates` CRM cross-check — `amt_sync` | `amt_gateway`, `amt_sync` | |
| `sale_readiness` | `amt_ops` (`/sale_ready`) | `amt_gateway` | |
| `trust_ramp_ledger` | `item` qatorlari — `amt_gateway`; daraja o‘zgarishi — `amt_control` | `amt_ops`, `amt_gateway` | |
| `kill_criteria_evaluations` | `amt_sync` | `amt_control`, `amt_ops` | |
| `incident_acks`, `handback_acks` | `amt_ops` | `amt_control`, `amt_ops` | |
| `release_manifests`, `release_activations`, `harness_handovers`, `migration_drills`, `independent_reviews` | `amt_release` | ACK servislari, `amt_ops`, `amt_workflow`; `amt_sync` R (`release_activations` — WF-E01…E04 va WF-O02 kuzatuv step’lari) | |
| `release_approvals` | normal `amt_ops` → `/release approve` typed confirmation; Q65 first-only fixed importer §9.1 | `amt_release` | |
| `release_initializations` | Q65 fixed importer → unique first INSERT; `amt_release` → faqat shu identity ACK/progress/seal function’i | `amt_release`, `amt_ops` | canonical binding tuple o‘zgarmaydi; ikkinchi bootstrap/nonce/candidate rad |
| `service_revision_acks` | ACK servislari → `ack_revision()` (faqat o‘z `service_id`) | `amt_release`, `amt_ops`, `amt_control` | |
| `role_seed_imports` | `amt_ops` (bir martalik bootstrap) | `amt_ops` | |
| `audit_log` | barcha runtime rollar → `append_audit()` | `amt_ops` | |
| `sync_cursors` | `amt_sync` | `amt_sync` | |
| `quota_allocations` | `amt_quota` | `amt_quota` | |
| `experiments` | `amt_gateway` (`experiment.*`) | `amt_reader` → `v_experiments` | |
| workflow jadvallari | `amt_workflow`; signal — `SECURITY DEFINER` signal funksiyalari (gateway, ops, executor, sync, capi, watchdog, release) | [WORKFLOW_RUNTIME §3](WORKFLOW_RUNTIME.md) | §12.1 |
| `evolution_signals`, `upgrade_proposals`, `candidate_manifests`, `improvement_memory` | `amt_workflow` | `amt_verify`, `amt_release`, `amt_ops` | §12.2 |
| `verification_results` | `amt_verify` | `amt_release`, `amt_ops` | |
| `amt_ro.*` view’lar | — | `amt_reader`; kerakli servis rollari | sanitizatsiyalangan |

### 2.4 Mode va control yozuvlari

`gateway_state`, `control_events`, `kill_switch_events`, `agent_runtime_state` va `protective_actions` boshlanishi faqat `amt_control` funksiyalari bilan yoziladi. Chaqiruvchi servislar (`amt-sync` — avtomatik himoyalar, `ops-bot` — owner va readiness imzolari, `cost-watchdog` — admission va agent pauzasi, `amt-workflow` va `amt-release` — readiness dalili, `amt-release` — maintenance hold va uning tugashi) holatni o‘zi yozmaydi — [ARCHITECTURE §10.1](ARCHITECTURE.md) matritsasidagi op’ni RPC orqali so‘raydi (to‘liq ro‘yxat — `runtime-isolation.yaml#control_socket_peers`). Dispatch qarori uchun lokal latch kanonik; DB undan mirror, zid bo‘lsa yangi send rad.

## 3. Intake, webhook va CAPI ledger

### 3.1 Encrypted submission custody

Bu jadval landing storage’da, warehouse’dan alohida PII zonasida:

| Jadval / grain | Majburiy maydonlar va cheklovlar |
|---|---|
| `submission_receipts`: bitta biznes submit | `submission_id uuid PK`, `accepted_at`, `payload_hash`, `payload_ciphertext_ref`, `consent_receipt_ref`, `pipeline`, `state`, `expires_at`, `retention_policy_revision`; `client_idempotency_key` scoped unique |
| `submission_attempts`: bitta CRM yuborish urinishi | `attempt_id uuid PK`, `submission_id FK`, `attempt_no`, `lease_owner`, `lease_until`, `fence`, `started_at`, `state`, nullable `provider_request_id`, `crm_lead_id`, `finished_at`; UNIQUE `(submission_id,attempt_no)` |
| `submission_resolution`: yakun dalili | `submission_id FK`, nullable `crm_lead_id`, `resolution_kind`, `evidence_ref`, `resolved_at`, `resolved_by`; tasdiqlangan bir submit uchun bitta canonical CRM binding |

Receipt state: `accepted → crm_pending → crm_confirmed`; tashqi natija noma’lum `uncertain`, hal qilinmagan operatsion xato `needs_review`. Writer — landing intake/delivery; state o‘zgarishi compare-and-swap oldingi state/fence bilan. Qabul transaction commit+durability kafolati bo‘lmaguncha HTTP success yo‘q. Disk to‘la — visible failure; qabul qilingan yozuv retention deadline’da indamay o‘chmaydi. CRM unique submission reference’ni qo‘llashi F2’da tekshiriladi; imkoniyat yo‘q bo‘lsa reconciliation dalilisiz qayta create qilinmaydi.

Analytics `amt.submission_delivery` faqat `submission_id`, pipeline, accepted/delivered time, state, queue age, custody reference va CRM opaque ID’ni oladi; payload/ciphertext/telefon/IP/UA yo‘q. Ingest qayta replay’da `submission_id` unique. `crm_confirmed` holati server `Lead` CAPI event’ining yagona trigger’i (§3.4).

### 3.2 `webhook_inbox`

Grain — bitta manba hodisasining durable qabul qilinishi. Faqat allowlist maydonlar saqlanadi (Q62; `privacy-policy.yaml` `datasets` → `webhook_inbox`): `inbox_id uuid PK`, `source`, `source_account_id`, `source_event_key`, nullable scoped entity ID’lari (`amo_lead_id`, `amo_pipeline_id`) va `status_id`, `original_event_at`, `received_at`, `body_sha256`, `signature_result` (vendor imzosi tekshiruvi natijasi; imzo bo‘lmasa shu ham yoziladi), `mapping_revision`, `is_test`, `state`, `attempts`, nullable `lease_until`, `claimed_by`, `disposition_reason`. Raw body faqat capi-bridge xotirasida tekshiriladi va qayta ishlanadi; disk, log yoki trace’ga yozilmaydi. UNIQUE `(source,source_account_id,source_event_key)`. Event ID bo‘lmasa canonical fingerprint algoritmi va uning revision’i hamda event-history reconciliation qo‘llanadi; bir xil statusli ikki haqiqiy hodisa tasodifan yo‘qolmasligi sinov qilinadi.

Inbox ACK faqat commit’dan keyin. `received → claimed → processed`; muammo `retry_wait`, `poison`, `needs_review`. Duplicate yangi business event qilmaydi, receipt count/audit yangilanadi. Raw body hech qayerda saqlanmaydi (Q62): worker lead ID bo‘yicha ma’lumotni CRM’dan qayta o‘qiydi ([TRACKING_CAPI §4](TRACKING_CAPI.md)); `poison` va `needs_review` disposition’i ham faqat allowlist maydonlar va `body_sha256` bilan. Inbox qatori qayta ishlash oynasidan keyin purge (`privacy.retention`); warehouse’da allowlisted metadata. Quarantine va redacted URL log secret’ni saqlamaydi.

### 3.3 `delivery_outbox`

Grain — bitta logical tashqi yetkazish: `outbox_id uuid PK`, `channel`, `logical_key UNIQUE`, `subject_type`, `subject_id`, `payload_hash`, `payload_ref`, `created_at`, `available_at`, `expires_at`, `state`, `attempts`, nullable `lease_until`, `provider_ref`, `last_error_code`. Holat: `pending → leased → delivered`; `retry_wait`, `dead_letter`, `expired`. Barcha business final/approval/kill update’lari notification bilan atomik yoziladi. Yetkazish retry’si alohida attempt; callback yoki notification takrori command’ni qayta bajarmaydi.

| `channel` | Iste’molchi | Mazmun |
|---|---|---|
| `telegram` | `amt_ops` | change set, alert (kod va severity — [TELEGRAM §6](TELEGRAM.md)), digest, natija xabari |
| `capi` | `amt_capi` | `capi_events` yetkazilishi |
| `workflow` | `amt_workflow` | command holat o‘tishi va servis signallari (§6.5) |
| `paperclip` | `amt_workflow` | issue projection va natija izohi |
| `monitor` | `amt_control` | off-host jurnal: kill, mode_change, role_revoke, resume |

Alert ACK `incident_acks` yozuvida alert’ning `logical_key`iga bog‘lanadi; Telegram “yuborildi/o‘qildi” ACK emas.

### 3.4 CAPI ledger: `capi_events` va `capi_attempts`

Semantika [TRACKING_CAPI §5](TRACKING_CAPI.md)da; bu yerda schema.

| Jadval / grain | Maydonlar va cheklovlar |
|---|---|
| `capi_events`: bitta logical biznes event | `capi_event_id` PK (source account + logical subject + event kind’dan deterministik; Pixel bilan bir xil event_id), `event_name` (`Lead`, `QualifiedLead`, `Contract` — `pipelines.yaml` `capi_event_map`), `trigger_kind` (`submission_crm_confirmed`, `qualified_fact_rule`, `contract_fact`), nullable `submission_id`, `business_event_id`, scoped `amo_lead_id`, `pipeline_at_event`, original `event_time`, `mapping_revision`, `definition_revision`, `consent_ref`, `consent_state_at_decision`, `is_test`, `state`, `attempts`, `outbox_id FK`, `created_at`, nullable `sent_at`, `disposition_reason` |
| `capi_attempts`: bitta tashqi so‘rov | `attempt_id` PK, `capi_event_id FK`, `attempt_no` (har so‘rov qatorining tartib raqami — hold’lar ham; maksimal urinish faqat `counted_results` bo‘yicha `capi_events.attempts` da sanaladi), `started_at`, nullable `finished_at`, `request_hash`, `field_presence` (qaysi user_data maydoni bor edi — faqat bitmap, qiymat emas), nullable `provider_http_status`, `provider_response_code`, `fbtrace_id`, `result` (`accepted`, `retryable_error`, `connect_error`, `no_response`, `unclassified_error`, `batch_rejected`, `permanent_error`, `config_error`, `auth_error` — `pipelines.yaml#capi_delivery`), `error_class`; UNIQUE `(capi_event_id, attempt_no)` |

Holat: `queued → sending → sent` (har so‘rovda bitta event, `batch_policy: realtime_single`); saqlangan bo‘lishi mumkin bo‘lgan javob (`no_response`, `unclassified_error`, `batch_rejected`) — `uncertain`, qayta yuborilmaydi; `uncertain` hard deadline ichida o‘z javobi bilan yopilmasa `dropped_uncertain` (terminal, yo‘qotilgan deb sanaladi); `retry_wait` (sanaladigan vaqtinchalik xato yoki `auth_error`/`config_error` hold’i); bitta event rad etilsa `needs_review`, technical_operator tasdig‘i bilan `rejected` yoki qayta `queued`; marketing consent yo‘q `skipped_no_consent`; vendor vaqt oynasidan tashqari `skipped_too_old`; muhitda tasdiqlangan test kodi bo‘lmagan test eventi `skipped_test`; host-loss qayta qurishida yo‘qolgan host yubora olmagani isbotlanmagan event `skipped_unknown_prior_send`, `disposition_reason` = `terminal_before_loss` (yo‘qolishdan oldin avtomatik yuborish yo‘lidan chiqqan) yoki `unknown_state` (audit bilan; [TRACKING_CAPI §5.3](TRACKING_CAPI.md), §8). `sent` provider requestni qabul qilganini bildiradi, attribution yoki optimization muvaffaqiyati emas. Server `Lead` faqat submission `crm_confirmed` bo‘lganda; amoCRM `add_lead` webhook faqat reconciliation; `QualifiedLead` faqat `qualified_fact_rule` bajarilganda (◇ P-19). `Contract` config’da o‘chiq. Test event faqat staging’da `capi_test_code_ref` bilan (`environments.yaml`). Consent har yuborishdan oldin tekshiriladi; withdrawal pending yuborishni to‘xtatadi. Raw yoki hash telefon, `fbc/fbp`, IP/UA disk, warehouse, log yoki trace’da saqlanmaydi (`capi_in_memory`, `capi_attempt_evidence` dataset’lari). `capi_error_rate` denominator’i (attempt yoki event) check revision’ida explicit. Restore va backfill’da faqat consent-valid va time-valid event yuboriladi; eski hodisa “hozir” qilib yuborilmaydi.

## 4. Biznes eventlari va snapshot

### 4.1 `leads_snapshot`

Grain — `(source_account_id,amo_lead_id)` current snapshot. `pipeline`, `amo_pipeline_id`, `status_id`, `source_created_at`, `source_updated_at`, `synced_at`, `mapping_revision`, `current_is_qualified`, `ever_qualified`, nullable `first_qualified_at`, `first_contract_at`, `campaign_id`, `adset_id`, `ad_id`, `creative_id`, `variant_id`, `lost_reason_code`; `has_fbc`, `has_fbp`, `marketing_consent_state` explicit. Sanitized first/last touch ID’lar va attribution quality saqlanadi; erkin UTM, tag, CRM name/notes saqlanmaydi. `ever_qualified` tarixiy ledger’dan, `current_is_qualified` joriy mapping’dan hisoblanadi; ikkalasi teng bo‘lishi shart emas.

### 4.2 `lead_stage_events`

Grain — manba tizimidagi bitta status transition. PK `(source_account_id,amo_event_id)`; `amo_lead_id`, `pipeline_at_event`, `from_status_id`, `to_status_id`, `occurred_at`, `received_at`, `mapping_revision`, `qualified_definition_revision`, `is_test`, nullable `created_by_source_user_id`, `corrects_event_id`, `tombstone_reason`. Append-only correction/tombstone original hodisani o‘chirmaydi. API joriy statusni tasdiqlaydi; tarixiy qualification vaqtini joriy snapshot bilan almashtirmaydi.

### 4.3 `business_events`

Grain — bitta haqiqiy biznes hodisasi. `business_event_id uuid PK`, `source`, `source_account_id`, `source_event_key`, `entity_ref`, `acquisition_episode_id`, `pipeline_at_event`, `event_type`, `event_at`, `received_at`, `definition_revision`, `is_test`, nullable `corrects_event_id`, `contract_ref`, `payment_ref`, `fulfilment_ref`. UNIQUE `(source,source_account_id,source_event_key,event_type)`.

`event_type`: `lead_created`, `contacted`, `qualified`, `contract_signed`, `payment_received`, `delivered`, `rental_started`, `renewal`, `cancelled`, `refunded` (`pipelines.yaml` `lifecycle_events`, `lifecycle_is_linear: false`). Bekor qilish contract’dan oldin, qisman to‘lov esa fulfilment’dan keyin ham kelishi mumkin. Renewal eski episode’ga bog‘lanadi va yangi acquisition numerator/denominator’ini ko‘paytirmaydi. Merge canonical lead relation orqali alias’ni bog‘laydi; reopen yangi episode qoidasi owner tasdiqlagan definition bilan, avtomatik yangi lead emas.

`qualified` hodisasi faqat `pipelines.yaml` `qualified_fact_rule` bajarilganda yoziladi (◇ P-19): o‘tish `qualified_status_ids`dan biriga, ruxsatli aktyor (`allowed_actor_user_ids`) va talab qilingan dalil maydonlari (`required_evidence_field_ids`) bilan; `event_at` = o‘tishning `occurred_at`i. Keyingi QA yangi measurement revision yoki invalidation yaratadi va owner boshqacha qaror qilmasa real-time CAPI’ni to‘xtatmaydi.

### 4.4 `cash_events` va kogorta

`cash_event_id`, source unique ref, `business_event_id FK`, `amount_minor bigint`, `currency`, `event_at`, `kind`, nullable `adjustment_ref`, `refund_of`, `fx_rate_ref`. Deposit, actual receipt, instalment, refund va earned revenue bir turga yig‘ilmaydi. Contribution owner va moliya tasdiqlagan `economic_definition_revision` bilan hisoblanadi; manba yo‘q bo‘lsa ROI unknown.

`cohort_metrics` grain `(cohort_start,pipeline,attribution_revision,qualified_definition_revision,maturity_revision,metric)`. `value` NULL bo‘lishi mumkin, lekin `data_status` majburiy va faqat [business-policy.yaml](../09_Config_Templates/business-policy.yaml) `data_status_values`dan:

| `data_status` | Ta’rif (`data_status_definitions`) |
|---|---|
| `valid` | spend > 0, sample va maturity qoidalari bajarilgan, baseline taqqoslanadigan |
| `no_activity` | spend = 0 va qualified = 0 |
| `no_spend` | spend = 0 va qualified > 0 |
| `spend_zero_qualified` | spend > 0 va qualified = 0 |
| `insufficient_sample` | tasdiqlangan minimal sample’dan past |
| `not_mature` | natija oynasi yopilmagan |
| `incomparable_baseline` | qualification yoki tracking definition revision’i baseline’dan farq qiladi |
| `missing_data` | kerakli manba qatorlari yo‘q |
| `stale_data` | manba tasdiqlangan freshness cutoff’idan eski |

Har holat uchun kill-criteria harakati `kill-criteria.yaml` `data_status_actions`da. Lead→contract va qualified→contract denominatorlari alohida, bir xil cohort/maturity bilan. Unknown manba eng yaxshi kreativga taqsimlanmaydi; matched+unmatched jami tekshiriladi.

### 4.5 Ads va baseline

`ad_insights_daily` grain `(account_id,account_date,ad_id,insight_revision)`; `account_timezone`, pipeline (`sale/rent/unknown`), campaign/adset ID, `spend_minor`, `currency`, impressions/reach/clicks/link_clicks, leads_meta, nullable qualified_meta/frequency/learning_status, `reported_at`, `source_window`. Oxirgi 7 kun qayta olinadi (★, §9.4); attribution kechikishi integratsiyada tekshiriladi, correction yangi revision’da. Ierarxiya aggregate CBO/ABO sarfni ikki marta hisoblamaydi.

`baselines` PK `(metric,pipeline,period_start,method,definition_revision)`; period end, value nullable, status/source/window/maturity/attribution revision va `frozen_at` majburiy. Frozen baseline correction tarixisiz almashtirilmaydi. Baseline’ni agent tayyorlaydi (`prepared_by`), lekin `frozen_at` faqat owner `business.baseline` readiness’ni tasdiqlagandan keyin qo‘yiladi. Oxirgi 8 hafta va mavjud 12+ oylik mavsumiy tarix alohida dalil (Q31 ✅, Q37 ✅).

## 5. Creative, offer, consent va assetlar

| Jadval / grain | Shartnoma |
|---|---|
| `offer_revisions` / bitta immutable offer revision | `offer_id`, `offer_revision` composite PK; validity, price terms, claim set hash, owner approval, `config_sha`, `status`; expiry/revoke append event bilan. Revision’da narx o‘zgartirilmaydi (Q35 ✅) |
| `asset_versions` / bitta bytes nusxa | `asset_id`, `asset_revision`, `sha256`, `mime`, `size_bytes`, custody ref, `origin` (`upload`, `generated`, `rendered`), `uploader_person_id`, `rights_state` (`quarantined`, `cleared`, `revoked`, `expired`), `consent_ref`, nullable `cleared_by_person_id`, `cleared_at`, `rights_confirmation_ref`, `rights_expires_at`; bir xil path boshqa bytes bo‘lsa yangi revision |
| `drive_assets` / Drive immutable version binding | `drive_file_id`, version/hash, quarantine/cleared/revoked holat, uploader reference, `cleared_by`, `cleared_at`, nullable `revoked_by`, `revoked_at` va sanitized tags; `consent_people` boolean dalil o‘rnini bosmaydi |
| `consent_references` / purpose bo‘yicha receipt | warehouse’da opaque subject/receipt ref, purpose (`service_fulfilment`, `marketing_measurement`), text version, event time, source, current state, nullable withdrawal time; raw evidence custody’da |
| `creatives` / canonical creative ID | ID, pipeline, format/lang/media_type, sanitized hypothesis/headline/text/CTA, current revision pointer va derived review_status (`pending/passed/failed/needs_owner/retired`); mutable file pointer tasdiq emas |
| `creative_revisions` / bitta content manifest | `(creative_id,creative_revision)` PK, `asset_manifest_sha`, exact asset versions, offer revisions, copy hash, `copy_artifact_id`, generation request ref, created_at, author ID, state |
| `copy_artifacts` / bitta unique copy lineage | `copy_artifact_id` PK, birinchi revision ref, `language`, `origin` (`live`, `shadow`, `eval`, `test`), nullable `first_live_proposal_at`, `counts_toward_first20` boolean, `count_reason`, nullable `first20_ordinal`; lineage immutable |
| `review_subjects` / Reviewer’ga berilgan exact subject | `subject_id` PK, `subject_type` (`creative_revision`, `change_set_item`, `offer_pr`, `landing_pr`, `weekly_report`), `subject_ref`, `subject_hash`, `content_ref` (creative copy, manifest, preview, `asset_manifest_sha`; normalized payload, observed remote state, `rollback_spec`; aniq commit SHA bo‘yicha PR diff; hisobotning aniq matni), `issued_to_run_id`, `issued_at`; immutable |
| `review_verdicts` / bitta authoritative verdict | `review_revision` PK, `subject_id FK`, `subject_hash`, `policy_revision`, `offer_revisions[]`, Reviewer principal va run, model slot’lari (`reviewer.language`, `reviewer.policy_checklist`), `checks[]`, `required_fixes[]`, `confidence`, verdict `pass/fail/needs_owner`, created/expires/revoked time |
| `human_checks` / immutable inson til tekshiruvi | `human_check_id` PK, `copy_artifact_id`, `creative_revision`, `asset_manifest_sha`, `offer_revision`, `policy_revision`, `subject_hash`, `person_id`, `membership_revision`, `checker_flag_revision`, `checked_at`, `verdict` (`pass`, `reject`), `reason_uz`, `expires_at`, nullable `revoked_at`, callback nonce hash |
| `creative_ad_bindings` / creative revision→Meta ad | account/ad ID, creative revision, uploaded hash/video ID, bound_at, validity; scoped unique relation |
| `dependency_invalidations` / revoke yoki expiry ta’siri | source revision, dependent creative/ad/landing/command ref, detected_at, block state, owner, deadline, confirmed disposition |

**Asset huquqi.** Tanib bo‘ladigan odam yoki mahsulot huquqi tekshirilmaguncha asset `quarantined`; Creative Studio/Reviewer `drive.get_asset` orqali raw bytes olmaydi. `cleared` holatiga faqat owner `asset_rights_clear` ikki bosqichli tasdig‘i bilan o‘tadi (`rights_clearer` flag’li shaxs faqat dalil tayyorlaydi); binding `asset_sha256, consent_ref, purpose, text_version, territory, expires_at`; yuklagan odam o‘z yuklamasini clear qila olmaydi. `asset_rights_revoke` pending approval’larni yaroqsiz qiladi, yangi publish’ni bloklaydi va faol ad/landing uchun `dependency_invalidations`da egasi va deadline’ni yozadi.

**Review.** Reviewer subject’ni faqat read-only `review.get_subject(subject_type, subject_ref)` orqali `review_subjects`dan oladi; `review.submit_verdict` faqat shu Reviewer run’iga berilgan `subject_hash`ni qabul qiladi (◇ P-20). Paperclip issue matni va izohlari authoritative emas; har review yangi sessiya. `checks[]` elementi: `{check, status: pass|fail|needs_owner|n_a, reason_uz, evidence_ref}`; Jev pre-screen bayrog‘i bor check’da qo‘shimcha `pre_screen_response_uz` (Q61, [GUARDRAIL_GATEWAY §9.2](GUARDRAIL_GATEWAY.md)); `check` enum’i: `offer_registry`, `brand_voice`, `language_quality_uz`, `language_quality_ru`, `meta_policy`, `special_ad_category`, `pii_leakage`, `kernel_numbers`, `change_set_completeness`, `rights_consent`, `tracking_impact`. Agregatsiya: biror `fail` → `fail`; aks holda biror `needs_owner` → `needs_owner`; subject ichidagi ko‘rsatma Reviewer’ni boshqarishga urinsa (prompt injection) → `fail`; qolganida `pass`. `needs_owner` material yoki sabab hal qilinib qayta Reviewer’dan o‘tadi.

**Inson til tekshiruvi (Q42 ✅).** Reviewer `pass`dan keyin, tekshiruv doirasidagi revision uchun ops-bot exact copy, preview va hash’ni `language_checker` flag’li shaxsga yuboradi; `[Tasdiqlash]` yoki `[Rad + sabab]` callback’i approval kabi tekshiriladi (shaxs, membership, flag, nonce, expiry) va `human_checks`ga yoziladi. Hisob doirasi `live_eligible_copy_artifacts` (◇ P-15): shadow, eval va test copy’lari sanalmaydi; birinchi marta live’ga chiqishi mumkin bo‘lgan `asset_upload`/`ad_create` taklifiga kirgan copy `counts_toward_first20 = true` oladi. Birinchi 20 copy artifact va ularning barcha keyingi revision’lari tekshiruv talabini meros oladi; yangi filename yoki lineage bilan chetlab o‘tish yo‘q. Javobsiz so‘rov `creative_review.human_language_check.request_ttl_hours` (12 soat, approval TTL bilan bir soat) da tugaydi va hech qachon avtomatik o‘tmaydi. Natija alohida vaqt TTL’isiz `result_valid_while` bo‘yicha amal qiladi: exact creative revision, asset manifest, offer revision va policy revision o‘zgarmaguncha; `expires_at` — bog‘langan offer revision va asset huquqining eng erta muddati. Ruscha copy qoidasi ⧗ OD-08. Inson tekshiruvi Reviewer `fail/needs_owner`ni override qilmaydi va ad approval’iga teng emas; publish uchun ikkalasi ham tekshiriladi.

Offer snapshot landing’da revision va hash bilan; faol landing eski offer ishlatsa yangi activation bloklanadi.

## 6. Command va execution schema

### 6.1 `change_set_items`

Grain — bitta immutable command revision. `id` canonical `CS-YYYYMMDD-NNN`; `command_id uuid`, `command_revision integer`, UNIQUE `(command_id,command_revision)`. Har bir yangi edit revision oldingi approval’ni bekor qiladi. `entity_state_version` vendor-native version bo‘lishi shart emas: version yo‘q bo‘lsa tasdiqlangan authoritative remote field snapshot’i, read time va canonical hash’dan olinadigan internal observed version; stale snapshot yangi state deb yashirin almashtirilmaydi.

**Immutable maydonlar:** `created_at`, `agent_id` (yoki `system:amt-control`), `action_type` (`approval-policy.yaml` `actions` kaliti), `pipeline` (`sale/rent/shared`), schema-valid `target`, `params`, `payload_hash`, `expected_effect`, `rollback_spec`, `risk`, `evidence`, `manual`, `shadow`, `review_required` (yaratilgan paytdagi `actions.<action>.review_required`), `policy_revision`, `role_revision` (yaratilgan paytdagi `role_registry_revision`), `control_epoch`, `entity_state_version`, `expires_at`, `trust_level_at_creation`, `run_id`, `step_id`. Creative/offer/asset talab qiladigan action’da `offer_revision`, `creative_revision`, `asset_manifest_sha` va oldindan mavjud kreativ verdict’i kerak bo‘lsa `creative_review_revision` immutable intent’da `NOT NULL`; boshqa dependency’da NULL va explicit `not_applicable` reason’i bo‘ladi. `creative_review_revision` faqat exact `creative_revision` subject’ining oldingi `pass` verdict’i; u command payload review’ining o‘rnini bosmaydi. Command’ning `review_revision`i yaratishda hali mavjud bo‘lmasligi mumkin va immutable intent ustuni emas: u quyidagi append-only binding’dan olinadi. `human_check_id` ham keyin keladigan dalil bo‘lishi mumkin; birinchi 20 live-eligible copy artifact va ularning revision’lari uchun approval binding muzlatilishidan oldin `NOT NULL` bo‘ladi, claim va har retry’da exact evidence, amaldagi person/membership/`language_checker` flag revision, verdict va `expires_at` yana tekshiriladi. `reservation_id` pullik/ads commitment action uchun claim’dan oldin majburiy; `entity_pause` va `protective_pause` kabi xarajatsiz action’da explicit `reservation_not_required`.

**Review va approval dependency lifecycle.** Immutable intent `payload_hash`i normalized target/params, expected effect, rollback, evidence, yaratilishdagi policy/role/epoch va mavjud creative/offer/asset reference’larini qamraydi; keyin yaratiladigan command verdict’i, human check, approval yoki lifecycle holati hash’ga kirmaydi. Shuning uchun review `subject_hash`i o‘z verdict’iga rekursiv bog‘lanmaydi. `change_set_item` review subject’i exact `(command_id, command_revision, payload_hash)` va shu intent’dan olingan materialga bog‘lanadi.

- `command_review_bindings`: `binding_id`, `command_id`, `command_revision`, `payload_hash`, `subject_id`, `subject_hash`, `review_revision`, `bound_at`. UNIQUE `(command_id, command_revision)`, FK’lar exact issued `change_set_item` subject’i va mustaqil Reviewer `pass` verdict’iga; `bind_command_review()` caller, hash, muallifdan mustaqillik, policy/offer dependency, expiry/revoke va joriy command `pending_review` ekanini tekshiradi. Verdict, binding, `pending_review → pending_approval`, audit va outbox bitta transaction’da. `fail` → `rejected`; `needs_owner` → `pending_review`da qoladi, owner material/sababni hal qiladi va yangi mustaqil Reviewer `pass` kerak; inson Reviewer verdict’ini override qilmaydi. Bir revision’ga boshqa pass’ni keyin almashtirib bog‘lash taqiqlanadi; supersede/revoke yangi invalidation event va yangi command revision’ini talab qiladi. `review_required: false`da binding yo‘q va `review_not_required` reason’i bor.
- `command_approval_bindings`: `approval_binding_id`, `command_id`, `command_revision`, `payload_hash`, `binding_hash`, `frozen_at`, dependency snapshot. `freeze_approval_binding()` barcha amaldagi dependency’larni qayta tekshirib `execution-policy.yaml#approval_binding_lifecycle` bo‘yicha bitta append-only snapshot yaratadi. Snapshot’da command `review_revision`, mavjud bo‘lsa `creative_review_revision` va `human_check_id` ham bor; talab qilinmagan dependency NULL + `not_applicable` reason’i bilan yoziladi. Bu dependency snapshot’i; keyingi inson actor’ining membership’i uni mutatsiya qilmaydi: tanlangan approver’ning `membership_revision`i (effective approval binding’dagi `role_revision`) `record_approval()`da atomik tekshirilib approval qatoriga yoziladi. Muallifning immutable `role_revision`i esa yaratilishdagi role registry revision’i bo‘lib, alohida saqlanadi. Freeze idempotent: parallel chaqiruv bitta `(command_id, command_revision)` snapshot’ini qaytaradi; bytes/dependency farqi bo‘lsa yozuvni update qilmaydi va `revision_stale` bilan rad etadi. Snapshot commit’idan keyin presentation uzilsa, recovery aynan shu valid binding’ni qayta ishlatadi yoki command’ni bekor qiladi.
- Inson yo‘lida snapshot muzlatilishi `mark_presented()` va birinchi approval tugmasidan oldin; policy/auto yo‘lida `record_approval()`dan oldin majburiy. Human check kutilayotgan item `pending_approval`da ko‘rsatilmasdan turishi mumkin, lekin immutable `expires_at`dan oshmaydi. `presented_at` faqat shu snapshot bilan bir marta yoziladi. Approval `approval_binding_id/binding_hash`ga bog‘lanadi; keyin review yoki human check’ni shu revision’da qo‘shib/almashtirib bo‘lmaydi. Dependency yangilansa eski item `cancelled` (`revision_stale`), yangi command revision’i review va approval’dan yana o‘tadi; expiry/revoke faqat rad etadi, freeze muddatni uzaytirmaydi.

**Lifecycle maydonlari (nazoratli transition bilan):** `state`, `reason_code`, `presented_at` (Telegram’da birinchi ko‘rsatilgan vaqt, `mark_presented()`), `approval_expires_at` (= `presented_at` + `change_set.approval_ttl_hours`, `expiry_basis: presented_at`), `succeeded_at` yoki `done_manual_at`, `outcome_check_at`. 09:45 dan keyin kelgan band 10:00 batch’ga kirmaydi va alohida band sifatida o‘z `presented_at` va TTL’i bilan ko‘rsatiladi (`batch_cutoff`).

**`expected_effect`** — har agent taklifida majburiy:

```text
{ metric:       wh.metrics katalogidagi nom (§10.3)
  direction:    increase | decrease | hold
  range_low:    son (metrika birligida; pul minor’da)
  range_high:   son, range_low’dan kichik emas
  horizon_days: butun son ≥ 1
  basis_tag:    D | T | X | ?
  scope:        pipeline | entity }   # entity — faqat entity darajasidagi wh.metrics endpoint bilan (◇ P-43)
```

`scope` required enum; entity metric’lari faqat `entity_spend` yoki `entity_qualified` va faqat `scope: entity`, qolgan katalog metrikalari `scope: pipeline` bilan. `entity_spend` bandi manfiy bo‘lmagan integer minor’da, account currency bilan; boshqa `*_minor` metrikalar ham integer. JSON schema’da scope/metric mosligi tekshiriladi; gateway guard 4 qo‘shimcha katalog a’zoligi, finite sonlar, `range_low <= range_high`, maturity va exact target/account/pipeline mosligini tekshiradi. Entity selector’ini agent alohida ko‘rsatib ta’sir doirasini boshqa obyektga ko‘chira olmaydi: mavjud managed campaign/adset command’ida server normalized target’dan oladi; `campaign_create` yoki `adset_duplicate`da faqat shu command’ning muvaffaqiyatli remote natijasi bilan bir marta aniqlanadi (source adset emas). `ad_create`, ad-level activation va manual control’da entity endpoint yo‘q — `scope: pipeline` talab qilinadi. Kerakli selector aniqlanmasa natija `missing_data/inconclusive`; boshqa entity yoki pipeline’ga fallback yo‘q.

`protective_pause` va kill bilan yaratilgan tizim command’larida `expected_effect = {kind: not_applicable, reason}`. `outcome_check_at` = `succeeded_at` yoki `done_manual_at` + `horizon_days`; agar metrikaning maturity horizon’i (`business.baseline`, `business.acceptance`) uzunroq bo‘lsa, kechroq sana olinadi.

`idempotency_key` normalized immutable command intent’dan olinadi; kun+params hash’ining o‘zi biznes uniqueness dalili emas. Provider aynan bir marta bajarishini taxmin qilmaydi. `current_state` faqat muayyan `observed_at/version/hash` bilan; approval paytidagi remote state keyin almashtirilmaydi.

```sql
CREATE TYPE amt.command_state AS ENUM (
 'pending_review','pending_approval','approved','claimed','executing',
 'succeeded','rejected','expired','cancelled','failed_confirmed','uncertain',
 'reconciling','manual_resolution','awaiting_manual','done_manual'
);
-- Schema kontrakti: production migration shu majburiyatlarni konkret ustunlarga bog‘laydi.
ALTER TABLE amt.change_set_items
  ADD CONSTRAINT command_expiry_after_creation CHECK (expires_at > created_at),
  ADD CONSTRAINT command_revision_positive CHECK (command_revision > 0),
  ADD CONSTRAINT manual_dispatch_boundary CHECK (
    NOT manual OR state NOT IN ('claimed','executing','succeeded')),
  ADD CONSTRAINT shadow_never_dispatched CHECK (
    NOT shadow OR state IN ('pending_review','pending_approval','rejected','expired','cancelled')),
  ADD CONSTRAINT presented_pair CHECK (
    (presented_at IS NULL) = (approval_expires_at IS NULL)),
  ADD CONSTRAINT terminal_reason CHECK (
    state NOT IN ('rejected','expired','cancelled') OR reason_code IS NOT NULL);
CREATE UNIQUE INDEX one_live_command_revision
 ON amt.change_set_items(command_id)
 WHERE state IN ('pending_review','pending_approval','approved','claimed','executing',
                 'uncertain','reconciling','manual_resolution','awaiting_manual');
```

`reason_code` qiymatlari: `kill`, `revoked`, `guard_failed` (va [GUARDRAIL_GATEWAY](GUARDRAIL_GATEWAY.md) xato kodi), `superseded_by_edit`, `superseded`, `approval_ttl`, `manual_ttl`, `shadow_ttl`, `review_ttl`, `step_incomplete`, `approver_reject`, `reviewer_fail`, `owner_cancel`, `revision_stale`, `retry_ineligible`, `retry_limit`, `permanent_no_effect`.

### 6.2 State o‘tishlari

| Oldingi → yangi | Writer (rol → funksiya) | Guard va natija |
|---|---|---|
| new → `pending_review` | `amt_gateway`, `amt_control` → `create_command()` | `review_required: true`; immutable intent, reservation hold, step link, audit, outbox |
| new → `pending_approval` | shu | `review_required: false` |
| `pending_review` → `pending_approval` | `amt_gateway` → `submit_verdict()` / `bind_command_review()` | mustaqil Reviewer exact command revision `pass` va append-only binding bitta transaction’da; `fail` → `rejected` (`reviewer_fail`); `needs_owner` pending holatda, owner sababni hal qilgach yangi Reviewer verdict’i kerak |
| `pending_approval` → `approved` | `amt_ops` (inson), `amt_gateway` (L2 policy yoki `auto` action) → `record_approval()` | muzlatilgan approval binding va exact revision, amaldagi approver membership va expiry, `approval_expires_at` hamda immutable `expires_at` o‘tmagan, quorum; audit + outbox |
| `pending_approval` → `rejected` | `amt_ops` | approver rad; reservation release |
| `pending_approval` → `expired` | `amt_ops` expiry job | `approval_expires_at` yoki immutable `expires_at` o‘tdi; avtomatik tasdiq yo‘q (Q32 ✅); reservation release |
| `pending_approval` → yangi revision | `amt_ops` → `amt_gateway` | `edit_decrease`: faqat raqamli kamaytirish; eski revision `cancelled` (`superseded_by_edit`), yangi revision review va approval’dan qayta o‘tadi |
| `approved` → `claimed` | `amt_executor` (amo command’da `amt_amo`) | row lock/CAS, lease+fence va kerakli reservation bitta transaction’da |
| `claimed` → `executing` | shu | qayta guard, durable dispatch intent, latch/epoch critical section ([ARCHITECTURE §10.4](ARCHITECTURE.md)); remote call shundan keyin |
| `executing` → `succeeded` | shu | provider effect dalili va remote version; reservation settle; outbox (`telegram`, `workflow`) |
| `claimed`/`executing` → `failed_confirmed` | shu | tashqi ta’sir bo‘lmagani dalilli va permanent xato, retry limiti yoki eligibility tugagan; no-effect transient attempt esa §6.3 bo‘yicha shu ochiq command ichida qayta urinadi; timeout bu holat emas |
| `executing` → `uncertain` | shu | response yo‘q, process crash, provider success→DB commit uzilishi; reservation `uncertain`da saqlanadi |
| `uncertain` → `reconciling` → `succeeded`/`failed_confirmed`/`manual_resolution` | shu | read-only provider lookup/event history; noaniqlikda yangi write yo‘q |
| `approved` → `awaiting_manual` → `done_manual` | `amt_ops` | faqat owner qo‘lda action (`events_manager_change`, `amo_pipeline_change_proposal`); evidence va actor; executor ishlamaydi |
| `pending_review`/`pending_approval`/`approved` → `cancelled` | `amt_control` → `cancel_for_kill()`; `amt_gateway`/`amt_ops` (revoke, supersede, owner cancel) | `reason_code` majburiy; kill’da `kill`; reservation release |

Qo‘shimcha o‘tishlar — [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) `extra_transitions` bilan aynan:

```text
claimed -> cancelled (kill or revoke before dispatch intent; reservation released)
approved|claimed -> cancelled (guard failure with reason_code)
awaiting_manual -> expired
manual_resolution -> succeeded|failed_confirmed (operator evidence)
shadow item -> expired at TTL
pending_review -> expired (review_ttl - no Reviewer pass within the review TTL; reservation released)
pending_review|pending_approval -> cancelled (step_incomplete - the producing workflow step ended without workflow.submit_output; reservation released)
```

| O‘tish | Writer | Izoh |
|---|---|---|
| `claimed` → `cancelled` | `amt_control` (kill), `amt_ops` yoki `amt_gateway` (revoke) | dispatch intent’gacha; `reason_code` = `kill` (`kill_cancel_reason_code`) yoki `revoked`; reservation release |
| `approved` yoki `claimed` → `cancelled` | `amt_executor` (dispatch guard), `amt_gateway` | `reason_code=guard_failed` va xato kodi; masalan `state_drift` — owner yangi revision bilan qayta taklif oladi |
| `awaiting_manual` → `expired` | `amt_ops` | manual muddat o‘tdi; expired yoki revoked approval bilan manual completion qabul qilinmaydi |
| `manual_resolution` → `succeeded` yoki `failed_confirmed` | `amt_ops` (owner yoki operator dalili) | reservation settle yoki release; entity conflict lock’i ochiladi |
| shadow item → `expired` | `amt_ops` | TTL’da; shadow item hech qachon claim qilinmaydi |
| `pending_review` → `expired` | `amt_ops` expiry job | `created_at` + `change_set.approval_ttl_hours` (✅ Q32 qiymati, `execution-policy.yaml#review_ttl`) ichida mustaqil Reviewer `pass` bo‘lmadi — masalan Reviewer ulushi tugagan yoki pauzada; `reason_code=review_ttl`; avtomatik tasdiq yo‘q, reservation release; owner `/decisions`da ko‘radi (◇ P-85) |
| `pending_review` yoki `pending_approval` → `cancelled` | `amt_gateway` → `cancel_step_orphans(run_id, step_id)`, uni `amt-workflow` chaqiradi | command’ni yaratgan step qabul qilingan `workflow.submit_output`siz `failed`, timeout yoki `cancelled` bo‘ldi (masalan agent ulushi tugab step yarim qoldi); `reason_code=step_incomplete`; reservation release; yarim change set hech qachon taqdim etilmaydi (`execution-policy.yaml#orphan_cancel`, ◇ P-85) |

`auto: true` action’lar (`asset_upload`, `amo_tag_write`, `amo_field_write`) L1/L2’da faqat global `enabled`da policy approval (`approvals.actor_type = policy`) bilan o‘tadi; L0 yoki global `shadow`da SHADOW item sifatida yoziladi. Amo write command’larini `amocrm-mcp` xuddi shu attempt ledger semantikasi bilan bajaradi. Retry ayni command uchun yangi `execution_attempts` qatori, guardlar yana ishlaydi; retry paytida command `claimed` yoki `executing`da qoladi (§6.3), `approved`ga qaytmaydi. `failed_confirmed` terminal va qayta ochilmaydi; reconcile no-effect bilan yopgan command ham yangi revision talab qiladi. Rejected/expired payload “qayta approve” qilinmaydi; yangi revision kerak. Rollback ham yangi command, original command bilan `compensates_command_id` bog‘lanadi; `rolled_back` ikkinchi state manbai emas.

### 6.3 `execution_attempts` va `approvals`

`execution_attempts`: `attempt_id uuid PK`, `command_id`, `command_revision`, `attempt_no`, `run_id`, `step_id`, `executor_service` (`executor` yoki `amocrm-mcp`), `path` (`normal` yoki `pause_only`), `worker_id`, `lease_until`, `fence bigint`, `control_epoch`, `state`, `started_at`, `dispatch_recorded_at` NULL, `provider_dispatched_at` NULL, `provider_request_id` NULL, `response_hash` NULL, `remote_entity_ref` NULL, `error_code` NULL, `finished_at` NULL, `reconciliation_ref` NULL. UNIQUE `(command_id,command_revision,attempt_no)` va bitta unresolved attempt partial unique index. Lease takeover fence’ni atomik oshiradi; stale worker DB state yoki dispatcher orqali write qilolmaydi. Dispatch intent durable bo‘lib, response commit yo‘q bo‘lsa recovery `uncertain` deb oladi. Qo‘shimcha attempt ustunlari: `no_effect_evidence_ref` NULL, `retryable` boolean, `next_attempt_at` NULL, `retry_of_attempt_id` NULL. Attempt holatlari `claimed`, `dispatch_intent`, `succeeded`, `no_effect`, `uncertain`, `reconciling`, `manual_resolution`; yakunlangan no-effect attempt’da `finished_at` va evidence majburiy, unresolved index uni hisoblamaydi. Command holati attempt holati emas: backoff command’ni terminal yoki yana `approved` qilmaydi.

| Holat / hodisa | Command va attempt natijasi | Keyingi urinish sharti |
|---|---|---|
| Birinchi claim | command `claimed`; attempt N `claimed` | barcha guard; epoch barrier’da intent yozilgach command `executing`, attempt `dispatch_intent` |
| Jo‘natilmagani isbotlangan quota/connection hold (intent yozilgan yoki yozilmagan); yoki provider pinned no-effect transient javobi | attempt N `no_effect`, `retryable=true`; command oldingi `claimed`/`executing` holatida; durable `next_attempt_at` | N < 5, `next_attempt_at` original command/approval/dependency expiry’laridan oldin; bitta reservation va entity conflict lock saqlanadi |
| Backoff vaqti keldi | shu ochiq command CAS bilan; yangi attempt N+1 va monoton yangi fence, eski lease/permit bekor | oldingi attempt terminal `no_effect`, dalil bor, unresolved attempt yo‘q; approval snapshot, rol/policy/epoch, target drift, readiness va pul guard’lari to‘liq qayta tekshiriladi; reservation’ni qayta olish yoki ikki marta band qilish yo‘q |
| Muddat, revoke, kill yoki guard backoff ichida o‘zgardi | command `claimed` bo‘lsa `cancelled` (`guard_failed` va aniq sabab); oldin `executing` bo‘lsa isbotlangan no-effect sababli `failed_confirmed` (`retry_ineligible` va aniq sabab) | remote call yo‘q; barcha attempt no-effect ekani tasdiqlangach reservation bir marta release; yangi revision kerak |
| Permanent no-effect yoki N = 5 | command `failed_confirmed`; attempt `no_effect` | terminal; shu revision uchun retry yo‘q, reservation bir marta release |
| Javob/commit noma’lum yoki worker intent’dan keyin yo‘qoldi | command va attempt `uncertain`; keyin `reconciling` | reservation/conflict lock saqlanadi; yangi attempt yoki write yo‘q. Reconcile `succeeded`, `failed_confirmed` yoki `manual_resolution` bilan yopadi; `failed_confirmed`dan qayta urinish faqat yangi command revision’i |

`next_attempt_at` faqat scheduler readiness; approval emas va TTL’ni yangilamaydi. Guard failure `rate_limited` bo‘lsa faqat pinned retryable no-effect klassifikatsiyasi bilan yuqoridagi backoff yo‘li; noma’lum 429/5xx/timeout avtomatik retry dalili emas. `execution-policy.yaml#retry` limit/klassifikatsiya/expiry/fence/reservation shartlarining yagona config manbai. Command state transition’lari uchun mavjud `cmd:<id>:<revision>:<state>` dedup kaliti o‘zgarmaydi; urinish signalining kaliti `attempt:<attempt_id>:<state>` — har yangi attempt alohida, qayta delivery esa dedup qilinadi. Backoff/retry uchun soxta command transition outbox’i yozilmaydi.

`approvals` append-only: `approval_id`, `command_id`, `command_revision`, `payload_hash`, `approval_binding_id`, `binding_hash`, `decision` (`approve`, `reject`, `edit_decrease`, `expire` — `change_set.decisions`), `actor_type` (`person`, `policy`, `system`), nullable `person_id`, `membership_revision`, `role_registry_revision`, effective roles snapshot, `policy_revision`, `control_epoch`, `presented_at`, `decided_at`, `expires_at`, callback nonce hash, nullable `edited_params` (`edit_decrease`). `execution-policy.yaml` `approval_binding`dagi `role_revision` = shu approval’dagi `membership_revision`: dispatch, retry va rollback’dan oldin approver membership hali yaroqli va revision o‘zgarmagan bo‘lishi shart. Har approval frozen dependency snapshot’ini o‘zgartirmasdan aynan `binding_hash` bilan bog‘laydi va o‘z actor authority snapshot’ini qo‘shadi; callback eski yoki boshqa binding’ni tasdiqlay olmaydi. Quorum `change_set.quorum`dan; ikki callback bitta approved state’ga faqat bitta transition qiladi.

### 6.4 `command_outcomes`

Append-only, Trust Ramp’ning yagona manbai (`trust_ramp.graduation.outcome_source: command_outcomes`): `outcome_id` PK, `command_id`, `command_revision`, `horizon_days`, `due_at` (= `outcome_check_at`), `outcome` (`met`, `not_met`, `inconclusive`), `harmful` boolean, `data_status`, `measurement_revision`, `evidence_refs`, `overlapping_command_ids` (`trust_ramp.graduation.overlap_rule`: scope ichidagi boshqa har command — himoyaviy pauza va kill ham, oldingilari ham — bajarilish vaqti yoki ochiq ta’sir oynasi bilan oynaga tushsa natija `inconclusive`, sabab `attribution_confounded`, ◇ P-43, P-58), `countable` (boolean, `trust_ramp.graduation.countable_item`), `kind` (`outcome`, `annotation` yoki `harm_flag`), `recorded_by` (`system:outcome_classify` yoki agent run), `recorded_at`, nullable `supersedes_id`. Natija qatorini faqat `amt_sync` `classify_outcome()` yozadi — WF-B07 S02 dagi deterministik `outcome_classify` (`approval-policy.yaml` `trust_ramp.graduation.met_rule`, ◇ P-42); funnel-analyst `change_set.record_outcome` bilan faqat `not_met`/`inconclusive` natijaga `annotation` qatorini qo‘shadi va `outcome`ni o‘zgartira olmaydi. Faqat `succeeded`/`done_manual` command uchun va `due_at`dan keyin. `due_at` kelganda `amt-workflow` timer’i WF-B07 run’ini davom ettiradi (har command uchun alohida run; WF-B03 reconciliation bilan tugaydi). `inconclusive` clean hisoblanmaydi va shadow item sanalmaydi (◇ P-04); juftlik seriyasiga ta’sir `trust_ramp.graduation.streak_effects` da — faqat sanaladigan `met` +1, qolgan har natija 0 ga qaytaradi (◇ P-42). `harmful`ni `outcome_classify` `trust_ramp.graduation.harm_rule` bo‘yicha hisoblaydi (yo‘nalishga teskari, band’dan `business.acceptance.harm_margin_pct`dan ko‘proq; scope ichida guardrail buzilishi; command’ni nomlagan WF-O02 incident run’i) yoki funnel-analyst `harm_flag` qatori bilan bir tomonlama belgilaydi (istalgan natijaga, `met` ham; `harmful`ni hech kim tozalamaydi va natijani ko‘tarmaydi, ◇ P-54). `harmful = true` incident sifatida qayd etiladi va o‘sha trust kalitini `L1_approve_each`ga tushiradi (`trust_ramp.demotion.on_incident`); gateway yozuv paytida WF-O02 run’ini ochadi.

### 6.5 Workflow bog‘lanishi

- `change_set_items` va `execution_attempts` `run_id` va `step_id` ustunlarini oladi; workflow step’idan yaratilgan har command uchun `NOT NULL` ([WORKFLOW_RUNTIME §3](WORKFLOW_RUNTIME.md)). Protective va kill pause command’lari WF-O02 incident run’iga, F3 `origin=test` fixture command’lari test run’iga bog‘lanadi.
- `step_command_links`: `(run_id, step_id, step_attempt_no, command_id, command_revision, link_role)`; `link_role` ∈ `primary` (yaratgan step), `approval` (item’ni tasdiqlagan inson step’i), `dispatch` (urinish qilgan step), `reconciliation`, `compensation`, `protective`; PK `(command_id, command_revision, step_id)` — bitta command revision’i yaratgan, tasdiqlagan, dispatch qilgan va reconcile qilgan step’larga alohida bog‘lanadi. Bitta step bir nechta command yaratishi mumkin; yozuv `create_command()` ichida, server tomonidagi run descriptor’dan — agent run/step’ni o‘zi ko‘rsata olmaydi.
- Har command o‘tishi `transition_command()` ichida `delivery_outbox` qatorini yozadi: `channel = workflow`, `logical_key = cmd:<command_id>:<command_revision>:<state>`. `amt-workflow` uni `workflow_signals`ga oladi (dedup `logical_key` bo‘yicha) va step/run holatini quyidagicha o‘zgartiradi. Runtime command holatini yozmaydi; Paperclip issue yopilishi faqat drift hodisasi.

| Command holati | Step holati | Run holati |
|---|---|---|
| `pending_review`, `pending_approval`, `approved`, `claimed`, `executing`, `awaiting_manual` | `waiting` | `waiting` |
| `uncertain`, `reconciling` | `waiting` | `reconciling` |
| `manual_resolution` | `waiting` | `manual_resolution` |
| `succeeded`, `done_manual` (remote evidence bilan) | `completed` | definition bo‘yicha keyingi step |
| `failed_confirmed` | `failed` | compensation yoki eskalatsiya (definition) |
| `rejected` | `rejected` | `failure_paths` bo‘yicha |
| `expired` | `failed` | `failure_paths.cancel_or_escalate` |
| `cancelled` | `cancelled` | run cancel yoki `failure_paths` |

Jadval bitta command’li step uchun. Bir nechta command’ga bog‘langan step holatini birinchi yoki oxirgi command’dan emas, butun to‘plamdan, step roli bo‘yicha oladi — [workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml) `command_aggregation` (rollar: WF-B02 S09/S07 va WF-B03 S04 — `approval`, WF-B02 S10/S11 va WF-B03 S05 — `dispatch`, WF-B03 S06 — `reconciliation`). **Tasdiq step’i** har item qaror olganda tugaydi: biror item tasdiqlansa `completed`; hech biri tasdiqlanmagan va biror item muddati o‘tgan bo‘lsa `failed` → `failure_paths.cancel_or_escalate` (yuqoridagi jadvaldagi `expired` qatori bilan bir xil — owner sukuti hech qachon «bajarildi» emas); hammasi rad (yoki rad va bekor) → `rejected`; hammasi bekor → `cancelled`. **Dispatch step’i** hech bir item `approved`/`claimed`/`executing` holatida qolmaganda tugaydi: compensation `failed_confirmed` → `failed`; biror item `succeeded`, `done_manual`, `uncertain`, `reconciling` yoki `manual_resolution` bo‘lsa `completed` (`all_succeeded` yoki `partial`; `uncertain` item’lar reconciliation step’iga o‘tadi); hammasi `failed_confirmed`/`expired` → `failed`; hammasi bekor → `cancelled`. **Reconciliation step’i** faqat `every_item_terminal_or_handed_off` bo‘lganda tugaydi (`workflow-policy.yaml#command_aggregation.manual_resolution_handoff`): har item remote terminal dalilga ega yoki faqat `manual_resolution` holatida I18 bo‘yicha durable owner task va autentifikatsiyasi tekshirilgan qabul qiluvchining `accepted_by/accepted_at` handoff’i bilan run’dan tashqari custody’ga o‘tgan. Handoff exact command ID/revision, unresolved attempt/evidence ref’lari, reservation va conflict-lock ref’larini (yoki explicit not_required) qamraydi; reservation/lock saqlanadi. Vazifa yaratish, offered/rejected/expired/missing handoff yoki P2D timeout’ning o‘zi yetarli emas. Run egaligidagi `uncertain`/`reconciling` yoki topshirilmagan `manual_resolution` run’ni reconciliation’da ushlab turadi. Hammasi terminal yoki qabul qilingan custody transfer bilan yopilgach checkpoint avval `running`ga qaytadi, keyin odatiy completion guard’lari ishlaydi; `reconciling/manual_resolution → completed` to‘g‘ridan-to‘g‘ri o‘tishi yo‘q. Handoff remote success, retry ruxsati yoki WF-B07 measurement start’i emas. Muvaffaqiyatsiz pauza yoki budget kamaytirish darhol urgent item bo‘ladi (`dispatch_ownership.urgent_entry`), keyingi round kutilmaydi. Step har item uchun disposition yozadi (`command_id`, `command_revision`, terminal holat yoki `handed_off`, `reason_code`); `failure_paths` muvaffaqiyatsiz item’ga qo‘llanadi, muvaffaqiyatli item’larga emas, bir xil revision avtomatik qayta yuborilmaydi. WF-B07 ta’sir o‘lchovi har command uchun uning o‘z `succeeded`/`done_manual` o‘tishida boshlanadi ([workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml) `outcome_start`), parent run step’idan emas — shuning uchun boshqa item tiqilib qolsa ham muvaffaqiyatli item’lar o‘lchanadi.

### 6.6 Dinamik agentlar (✅ Q68)

| Jadval | Maydonlar | Yozuvchi |
|---|---|---|
| `dynamic_agents` | `slug`, `role`, `parent_role`, `tools[]`, `model`, `share_minor`, `currency`, `status` (`active`/`retired`), `hire_run_id`, `paperclip_agent_id`, `created_at`, `retired_at`, `retired_by` | gateway (WF-E05 S03, `agent_retire`) |
| `agent_hire_checks` | `hire_run_id`, `proposal_revision`, `check_id`, `passed`, `detail` | amt-workflow (WF-E05 S02, S04) |

Dinamik ulushlar yig‘indisi `budgets.yaml#openrouter.shares_minor.reserve` dan oshmaydi; retire qilinganda ulush `reserve` ga qaytadi ([agent-hiring.yaml](../09_Config_Templates/agent-hiring.yaml)).

## 7. Pul ledger va request reservation

### 7.1 Atomik hisob

`budget_accounts` PK `(scope,account_id,period_start,currency)`; `scope` ∈ `ai_runtime`, `ads`, `engineering` (workflow definition `limits.cost.budget_account` bilan bir xil); period timezone/end, `cap_minor`, `actual_minor >= 0`, `reserved_minor >= 0`, `revision`, freshness va reconciliation status. `cap_minor` faqat signed config’dan, runtime kirishidan emas:

| scope | Cap manbai | Qiymat |
|---|---|---|
| `ai_runtime` | `budgets.yaml` `openrouter.key_hard_cap_minor` | USD 150/oy (15 000 USD minor), Q10/Q33/Q44.1 ✅ |
| `ads` | `budgets.yaml` `ads.monthly_cap_minor` | USD 1 500/oy (150 000 USD minor), Q08/Q37 ✅ |
| `engineering` | `engineering-budget.yaml` `cap_minor` | tasdiqlanmagan (null); `paid_engineering_enabled: false`, ⧗ OD-02 |

Hisoblar bir-biridan qarz olmaydi (I25). Agent va media ulushlari `openrouter.shares_minor`da; `reserve` hech kimga oldindan berilmaydi (`reserve_rule`). Ulush va kalit chegaralari `share_warn_pct`, `share_stop_pct`, `key_noncritical_stop_pct`. Build davridagi AT/eval/shadow sarfi `build_eval_max_pct` (★) ichida; oshsa faqat `build_eval_over_limit_options` (HG-F4-04).

`budget_overrides`: `override_id`, `target` (`agent_slug` yoki `media_generation`), `whole_usd`, `extra_minor` (= `whole_usd × 100`), `reason`, `expires_at` (joriy oy oxiri, Asia/Tashkent), `approved_by_person_id`, `typed_confirmation_ref`, `created_at`. Buyruq `/budget raise <agent_slug|media_generation> <whole_usd>` (owner, `budget_override`, ikki bosqich); bot summani major va minor’da qaytaradi. Override faqat 15 000 USD minor kalit cap’i ichida qayta taqsimlaydi va ads cap’iga tegmaydi.

`reservations`: `reservation_id uuid PK`, account/period/currency, command, AI request yoki engineering request ref (aynan bitta logical owner CHECK), `reserved_minor`, `state` (`held`, `settled`, `released`, `uncertain`), created/expires, nullable actual cost/provider ref. Reserve olinganda `actual + reserved + requested <= allowance` tekshiriladi. `budget_entries` append-only actual, hold, release, adjustment va source ref’ni saqlaydi; settlement idempotent, unique provider ref bilan. Timeout reserve’ni avtomatik release qilmaydi. Narx upper bound’i topilmasa billable dispatch bloklanadi. AI reservation’ining upper bound’i hech qachon cache-read narxida emas (cache write narxi bilan, ◇ P-99); settlement haqiqiy narx bo‘yicha `ceil(total_cost × 100)` minor (pastga yaxlitlanmaydi). `uncertain` AI reservation’i OpenRouter generation yozuvi bilan settle bo‘ladi (`settled`, provider ref = generation ID) va settle bo‘lguncha rolning `max_concurrency` slot’ini band qiladi; `uncertain_settlement_hold_hours` tugasa `uncertain` qoladi, slot bo‘shaydi va kunlik provider usage reconciliation hal qiladi (`budgets.yaml#openrouter.reservation_sizing`, ◇ P-86).

### 7.2 AI so‘rovlar, provider usage va agent holati

`ai_requests` — bitta LLM/STT/media billable request: `request_id uuid PK`, `budget_account` (`ai_runtime` yoki `engineering`), `principal` (agent, gateway media yoki engineering roli), `requested_by`, `request_kind` (shu jumladan `compaction` — step ichidagi compaction chaqiruvi rol ulushida, ◇ P-102), `provider`, `model_version`, `pricing_revision`, `billing_period`, `reservation_id FK`, `estimated_upper_minor`, `currency`, `state`, `max_output_tokens`/duration/quality schema-bound limitlari, nullable `workflow_id`, `run_id`, `step_id` (agent run token’idan; chat va media job’da null), started time, nullable upstream generation ID, usage (`input_tokens`, `cached_input_tokens`, `cache_write_tokens`, `output_tokens` — provider javobidagi qiymat; javob yo‘q bo‘lsa null, nol emas), actual minor, finished time va reconciliation reference. Shu maydonlar F1-AT-13 unit cost o‘lchovi va F4 runtime talab modelining (`schemas/cost-model.schema.json`, ◇ P-81) yagona manbai. Stream uzilishi yoki async video timeout `uncertain`; unknown usage nol emas. Eski oyda ochilgan ish original period rezervini saqlaydi va provider’ning haqiqiy billing davri bilan explicit adjustment qilinadi (`vendor.openrouter_period`).

`provider_usage_snapshots`: `snapshot_id` PK, `provider`, `key_label` (kalitning o‘zi emas), `period_start`, `period_end`, `usage_minor`, nullable `provider_limit_minor`, `currency`, `observed_at`, `source`, `reconciliation_status`. Yozuvchi `amt_watchdog` — provider usage API’ni faqat uning read credential’i o‘qiydi (registr); `llm-proxy` per-request usage’ni `ai_requests`ga yozadi. Kunlik reconciliation `attributed_actual + unattributed`ni provider usage bilan solishtiradi; Langfuse uchinchi tekshiruv, uch manba qo‘shilib ikki marta sarf bo‘lmaydi.

`agent_runtime_state`: `agent_id` PK (biznes agentlari, `media_generation` va ulush qismlari `cmo.chat`, `cmo.workflow` — `budgets.yaml#openrouter.sub_shares`, ◇ P-89), `state` (`active`, `paused`), `reason_code` (`share_stop`, `part_stop` (faqat ulush qismi, ◇ P-101), `key_noncritical_stop`, `billing_unreliable`, `month_boundary`, `anomaly`, `owner`, `kill`, `maintenance`; `billing_unreliable` reconciliation tiklangani isbotlangach avtomatik ochiladi, qolganlari owner `agent_resume` bilan), allowance snapshot (actual+reserved vs ulush), `paused_at`, `paused_by_service`, `resume_requires_owner` (`resume_after_reset_requires_owner: true`), nullable `resumed_at`, `resumed_by_person_id`, `typed_confirmation_ref`, `revision`. Yozuvchi `amt_control` (watchdog so‘rovi bo‘yicha); o‘quvchilar gateway va proxy — Paperclip ishlamasa ham lokal rad etadi. Proxy javoblari: `agent_paused` → HTTP 423; `allowance_exhausted`, `price_unknown`, `write_mode_killed` — qayta urinilmaydigan xato. Oy boshida pauzadagi agent owner’siz qayta yoqilmaydi.

`agent_costs` — request/entry ledger’dan kunlik view yoki materialized aggregate: date×agent×source×currency. `llm_proxy`, `langfuse`, `provider_key_usage`, `unattributed` alohida; ikki manba qo‘shilib ikki marta sarf bo‘lmaydi. Telemetry kechikishi accounting’ni to‘xtatmaydi; accounting DB yo‘q bo‘lsa yangi pullik request yopiladi.

### 7.3 Ads spend, commitment va budget harakatlari

`ads_spend_snapshots`: `snapshot_id`, `account_id`, `reported_at`, `account_timezone`, `currency`, `month_start`, `month_to_date_spend_minor`, `provider_counter_minor`, `spend_counter_basis`, nullable `provider_cap_minor`, `pending_commitment_minor`, `safety_margin_minor`, nullable `fx_rate_ref`, `fresh_until`, `reconciliation_status`. Account valyutasi USD bo‘lmasa USD biznes cap’i uchun verified FX va minor offset kontrakti F3 gate’da yopiladi (`ads.fx_policy`, `budget.ads_limits`); noma’lum konversiya bilan sonlar solishtirilmaydi va write bloklanadi. MTD inson boshqarayotgan kampaniyalarni ham qamraydi.

**Mustaqil cap (Q37 ✅).** Ads Manager account spending limit majburiy va AI’dan mustaqil (`ads.provider_spend_limit_required: true`, `provider_spend_limit_readback_required: true`): HG-F3-02 da qo‘yiladi, HG-OPS-01 da har oy 1-kuni yangilanadi; `vendor.meta_cap` va Step 1 oldidan `budget.ads_fresh_check` faqat API read-back kutilgan qiymatga teng bo‘lsa PASS. Yangilash formulasi (`cap_update_formula`, ◇ P-02):

```text
spend_cap_native = provider_counter_now_native + to_native(max(0, monthly_cap_minor - verified_mtd_minor - safety_margin_minor))
cap_update_rounding: round_down_to_provider_minor_unit
```

Oy o‘rtasida to‘liq 150 000 USD minor qayta qo‘shilmaydi. `protective_pause` qo‘shimcha qatlam, limit o‘rnini bosmaydi (`protective_pause_is_additional: true`).

**Commitment va admission** (`budgets.yaml` `ads.commitment_basis`, `ads.admission_rule`):

```text
budget_change:               max(0, new_daily_minor - old_daily_minor) * remaining_days_in_business_month
entity_activate:             daily_budget_minor * remaining_days_in_business_month
campaign_activate:           daily_budget_minor * remaining_days_in_business_month
creative_activate_new_adset: daily_budget_minor * remaining_days_in_business_month
entity_pause:                0
protective_pause:            0

admission: verified_mtd_minor + sum(active_daily_minor * remaining_days) + sum(held_commitments_minor) + requested_minor <= monthly_cap_minor - safety_margin_minor
```

`remaining_days_in_business_month` Asia/Tashkent bo‘yicha joriy kunni ham sanaydi. Barcha qiymatlar `ads.fx_policy` bo‘yicha provider counter valyutasiga keltiriladi. Commitment gateway admission’ida `held` reservation sifatida olinadi (ikki parallel taklifga bir headroom va’da qilinmaydi); `rejected`, `expired`, `cancelled`da release (`reservation_release_on`), `succeeded`da settle (`reservation_settle_on`); `uncertain`, `reconciling` va `manual_resolution`da ushlanadi; `failed_confirmed`da tashqi ta’sir yo‘qligi dalili bilan release. Inson boshqaradigan (foreign) sarf cap’ni yesa — faqat alert va owner handback (`foreign_spend_behavior: alert_and_owner_handback_only`). Hard-cap PASS uchun `ads.hard_cap_pass_requires` dalillari kerak.

`budget_change_ledger`: account/entity/hierarchy budget egasi, observed baseline/version, from/to integer minor, absolute delta, event time, command/human source, emergency flag. Rolling 24h normal write’lar uchun `rolling24h_sum_abs_delta / verified_budget_at_window_start <= 0.20` (◇ P-01; `budget_change.limits`). Oyna boshidagi ishonchli baseline nol yoki noma’lum bo‘lsa avtomatik increase yo‘q, owner review (`zero_or_unknown_baseline: owner_review_no_auto_increase`); human drift yangi baseline’ni yashirin o‘rnatmaydi (`manual_drift_behavior: block_and_reconcile`). CBO campaign budget va ABO adset budget bir ierarxiyada ikki marta olinmaydi. Budget increase KC-02 trigger bo‘lgan yoki `lead_to_contract` `data_status` `valid` bo‘lmagan paytda bloklanadi (`business_outcome_guard`). Emergency pause alohida yo‘l va audit.

**`protective_actions`** — har protective control faollashuvi: `action_id` PK, `control_id` (`operations.yaml` `protective_controls` id’si), `trigger_kind`, trigger kirishlari (`ads_spend_snapshot_id`, freshness, headroom), `policy_revision`, `control_epoch`, `control_event_id`, nullable `command_id`, `run_id` (WF-O02), `entity_set_hash`, per-entity natija (`paused`, `already_paused`, `failed`, `unverified`), `partial_failure`, alert `logical_key`, nullable `handback_id`, started/finished. Ijro yo‘li [ARCHITECTURE §11](ARCHITECTURE.md).

## 8. Odamlar, boshqaruv va freshness

| Jadval | Grain va muhim invariant |
|---|---|
| `people` | `person_id uuid PK` (readiness va audit’dagi opaque `person_ref`), `tg_id` UNIQUE, display_name, status (`active`, `suspended`, `removed`), `person_revision`, `cloud_password_attested_at` (owner va ads_approver approval tugmalari hamda tg-auth uchun majburiy), `native_language_attested` (`uz`, `ru`, null; owner attest qiladi), nullable `github_login` (`independent_reviewer` uchun majburiy; GitHub review shu login bilan bog‘lanadi), created/updated time; person suspend barcha rol va flag’ni rad qiladi |
| `roles` | membership: PK `(person_id, role)`, status (`active`, `suspended`, `removed`), nullable `expires_at`, added_by/at, `membership_revision` (har o‘zgarishda oshadi); expiry faqat shu membership’ga tegishli. RBAC’dagi membership `role_revision` = `membership_revision`; butun reyestr bo‘yicha monoton `role_registry_revision` alohida |
| `person_flags` | `(person_id, flag)` + `granted_by`, `granted_at`, nullable `expires_at`, nullable `revoked_at`, `flag_revision`. Effective flag = yaroqli membership’larning default flag’lari ∪ muddati o‘tmagan `person_flags`, faqat kamida bitta yaroqli membership bo‘lsa (`roles.yaml` `flag_rules`). `checker_flag_revision` = flag shaxsga berilgan bo‘lsa `flag_revision`, membership default’idan bo‘lsa o‘sha `membership_revision` |
| `responsibility_assignments` | PK `(person_id, assignment)`; `assignment` ∈ `roles.yaml#responsibility_assignments` (`technical_operator`, `finance_owner`, `privacy_owner`, `independent_reviewer`); status (`active`, `suspended`, `removed`), nullable `expires_at`, assigned_by/at, `assignment_revision`. Faol shaxs talab qilinadi; Telegram RBAC roli shart emas. Faqat owner `/role assign\|unassign` (typed code, `role_change`) bilan o‘zgaradi va off-host jurnalga ko‘chiriladi. Readiness’dagi `accountable_role`/`co_signers` qiymatlaridan RBAC rollari (`owner`, `sales_lead`, `fleet_operator`) `roles`dan, qolganlari shu jadvaldan tekshiriladi |
| `readiness_records` | PK `(key, record_revision)`; `key` ∈ `readiness.yaml#requirements`; status (`readiness.yaml#record_states`: `pending`, `evidenced`, `approved`, `not_applicable`), `value_json`, `value_hash`, `evidence_ref`, `evidence_at`, `evidence_prepared_by` (`person:<id>`, `agent:<slug>`, `system:amt-workflow` yoki `builder`), `max_evidence_age`, nullable `approved_by` (person_id), `approved_at`, `valid_until`, `created_at`. Append-only; har revision o‘z imzolarini oladi. Dalil `amt-control`ning `readiness_evidence` op’i bilan `evidenced` revision sifatida yoziladi: workflow output’i (`amt-workflow`) yoki merge bo‘lgan main commit’dagi evidence manifest’i (`amt-release`, candidate yasashda). Amaldagi tasdiq: jonli kalitda — eng so‘nggi `approved` yoki `not_applicable` revision; bundle’ga bog‘langan kalitda — faol release snapshot’i qadagan revision (yangi tasdiq release uni qadaganda kuchga kiradi). Keyingi `evidenced` revision (yangilash) hech qachon tasdiqni to‘xtatmaydi. `/readiness withdraw` (owner yoki javobgar rol egasi, `withdraw` imzosi bilan) bitta revision’ni nishonga oladi: amaldagi tasdiqni qaytarsa uni to‘xtatadi, hali qadalmagan yangi revision’ni qaytarsa faqat o‘shani bekor qiladi. Muddat `max_evidence_age` (imzoda va gate’da) va faqat jonli kalitda ixtiyoriy `valid_until` (gate’lar orasida) bilan hisoblanadi; alohida `expired`/`revoked` holati yo‘q (`readiness.yaml#rules`) |
| `readiness_signatures` | `signature_id` PK, `(key, record_revision)`, `role` (accountable yoki co-signer roli; `withdraw`da `owner` ham), nullable `reason` (`withdraw` uchun majburiy), `person_id`, `kind` (`approve`, `cosign`, `not_applicable`, `withdraw`), `typed_confirmation_ref`, `signed_at`; append-only. `amt-control` imzo paytida shaxs shu rolni egallaganini (`roles` yoki `responsibility_assignments`; `withdraw`da owner ham), `approve`/`cosign`da esa qo‘shimcha `evidence_prepared_by` emasligini va dalil yangiligini tekshiradi (`withdraw` bu ikkisidan mustasno); barcha imzolar bo‘lgach yozuv `approved` |
| `roles_audit` | op (`add`, `remove`, `suspend`, `resume`, `expire`, `flag_add`, `flag_remove`, `assign`, `unassign`), actor/subject `person_id`, role yoki flag, before/after revision, `typed_confirmation_ref`, off-host jurnalga yozilgan vaqt; append-only |
| `typed_confirmations` | `confirmation_id` PK, `action` (`approval-policy.yaml` action kaliti), action binding maydonlari va `binding_hash`, `person_id`, `membership_revision`, nullable `assignment_revision` (responsibility rol bilan imzolanganda), `nonce_hash`, `source` (`telegram_typed` yoki Q65 first-only `owner_ssh_signed_initial`), `code_hash` (normal typed yo‘lda NOT NULL; faqat signed initial source’da NULL), nullable `signed_envelope_ref`, `issued_at`, nullable `confirmed_at`, `expires_at` (normal typed yo‘lda `two_step.typed_code.timeout_minutes`; initial’da imzolangan envelope muddati, ordinary release expiry guard’i ham saqlanadi), nullable `consumed_at`, `consumed_by_service`, `result`. Initial NULL code faqat tekshirilgan owner signature va unique initialization FK bilan, u Telegram session/callback deb yozilmaydi. Typed code — ataylab qilingan harakat tasdig‘i, ikkinchi faktor emas |
| `gateway_state` | singleton typed record: `write_mode` (`shadow`, `enabled`, `read_only`, `killed`), `pipeline_modes` (sale, rent: `L0_shadow`, `L1_approve_each`, `L2_auto_within_guardrails`), `control_epoch`, `trust_levels` (trust kaliti — action_type × pipeline, `budget_change` uchun × direction `increase`/`decrease`, ◇ P-55: faqat `L1_approve_each` yoki `L2_auto_within_guardrails`), `read_only_causes` (to‘plam: `{cause, control_event_id, raised_at}`; `write_mode` faqat to‘plam bo‘sh bo‘lganda `read_only`dan chiqadi), `proxy_admission` (`open`, `paused`) va `proxy_admission_causes` (xuddi shunday to‘plam; admission faqat u bo‘sh bo‘lganda ochiladi), `maintenance_hold` (faol bo‘lsa oldingi rejimlar), `pre_kill_state`, `policy_revision`, `config_sha`, `last_control_event_id`, updated_at, `updated_by_service`, nullable `updated_by_person_id`. Yozuvchi faqat `amt_control` |
| `control_events` | `event_id`, `op` ([ARCHITECTURE §10.1](ARCHITECTURE.md)), `requested_by_service` (peer UID’dan), nullable `person_id`, `typed_confirmation_ref`, `cause_ref`, `epoch_before`, `epoch_after`, `pre_state`, `post_state`, `latch_written_at`, per-service containment ACK, `partial_steps` (har qadam natijasi), unresolved in-flight ref’lari, owner oshiruvchi o‘tishlarida `gate_result` (`profile`, `profile_evaluation_digest`, `pass`/`fail`), off-host jurnalga yozilgan vaqt |
| `kill_switch_events` | `kill_id`, `mode` (`A` `ai_only` yoki `B` `ai_and_ads`), owner `person_id`, `requested_via` (`telegram`, `ssh`), `typed_confirmation_ref` (Telegram), `control_event_id`, nullable `snapshot_id`, B uchun per-entity natija (eng yuqori to‘liq managed daraja; `paused`, `already_paused`, `failed`, `unverified`), `complete` yoki `partial_failure`, `contained_at`, nullable `remote_completed_at`, resume `control_event_id`, resolved_at/by |
| `account_snapshots` | `snapshot_id uuid PK`, taken_at/by, reason, source account, remote-state version/freshness va immutable entity status/budget/currency/objective/bid manifest; kill uchun best-effort, birinchi containment sharti emas |
| `managed_entities` | scoped `(account_id, entity_type, entity_id)` PK, parent ref’lar, pipeline, origin (`amt_created`, `amt_duplicated`, `takeover`, `test`), `ever_active`, nullable `first_activated_at`, `managed_since`, takeover `typed_confirmation_ref` va manifest hash (`takeover_scope_change`, HG-F6-04), nullable `released_at`, `released_reason`, `entity_state_version`. Faqat `released_at IS NULL` obyektga yoziladi; released entity faqat owner qayta takeover’i bilan qaytadi (`released_entities_require_owner_retakeover: true`, `auto_retakeover_on_resume: false`) |
| `tracking_health` | PK `(business_date, pipeline, check_id, measurement_revision)`, value nullable, status (`pass`, `warn`, `fail`, `unknown`, `stale`, `low_n`, `not_applicable` — `tracking-health.yaml` `check_states`), `measured_at`, `source_fresh_until`, sample size, `thresholds_revision`, policy revision |
| `tracking_streaks` | key `(pipeline, scope)`; `scope` = `check_id`, `all_gate` yoki global `fail_day` (pipeline = `all`; `tracking-health.yaml#fail_streak`: istalgan gate check `fail` bo‘lgan kun +1, barcha gate `pass` kuni 0, boshqa holatlar o‘zgartirmaydi; 2 → `tracking_read_only`); `consecutive_fail_days`, `consecutive_pass_days`, `last_business_date`, `last_status`. Faqat `pass` PASS streak’ini oshiradi; `fail`, `unknown`, `stale`, `low_n` uni uzadi; `warn` ⧗ OD-17; `not_applicable` faqat owner tasdiqlagan check uchun. Fail streak ketma-ket valid business-date fail’larni sanaydi; missing kun PASS deb sanalmaydi, freshness alohida fail-closed |
| `fleet_snapshots` | `report_id uuid PK`, business_date, `observed_at`, `submitted_at`, `reported_by_person_ref`, `valid_until`, snapshot_version, `total_fleet`, `serviceable_bikes`, `rented_bikes`, `reserved_bikes`, `available_bikes`, `maintenance_bikes`, `waitlist_active`, `waitlist_eligible_ready`, nullable `waitlist_oldest_at`, `expected_returns_next_24h`, nullable `supersedes_report_id` (`capacity-policy.yaml` `required_fields`) |
| `waitlist_aggregates` | PII’siz: `report_id FK` yoki CRM cross-check ref, `source` (`fleet_wizard`, `crm_crosscheck`), `waitlist_active`, `waitlist_eligible_ready`, `eligible_not_ready`, `expired_in_period`, `age_bucket_counts` (sxemali JSON), `exits_by_reason` (sxemali JSON), `fills_in_period`, `definition_revision`, `observed_at` |
| `sale_readiness` | `report_id`, `observed_at`, `reported_by_person_ref`, `offer_revision`, `stock_unpromised_by_model`, `delivery_lead_time_days`, `financing_available`, `call_center_backlog`, `response_lag_hours`, `capacity_per_day`, `valid_until` (`sale-readiness.yaml` `required_fields`); approval’dagi revision ijroda qayta tekshiriladi |
| `trust_ramp_ledger` | `entry_id`, action_type, pipeline, `direction` (`increase`, `decrease` yoki `none`), `kind` (`item`, `graduation`, `demotion`); `item`: command revision, `outcome_id`, `clean`, nullable incident ref; daraja o‘zgarishi: `level_before`/`level_after`, `typed_confirmation_ref` (`trust_graduation`, HG-L2-01), `isolation_evidence_ref` |
| `kill_criteria_evaluations` | `evaluation_id`, pipeline, `event_week`, `metric` (`qualified_cpl_event_week`), value minor va currency, `baseline_revision`, baseline value, `worse_pct_observed`, `min_sample_ref`, `data_status`, bajarilgan `data_status_actions` harakati, seriya ta’siri (`increment`, `reset`, `hold`, `blocked`), `streak_state` (`clear`, `counting`, `triggered`; `kill-criteria.yaml#streak`), `consecutive_bad_weeks`, `catch_up_until` (blok bo‘lsa), `measurement_revision`, exposure (spend, soat), `triggered`, KC-02 holati (baholangan yetilgan kogorta), nullable `control_event_id`, `handback_id`, owner resume ref; kogorta tasdig‘i ⧗ OD-13 |
| `incident_acks` | `ack_id`, alert `logical_key`, `alert_code`, `severity` (`critical`, `degraded`), `responder_person_id` (effective `ops_responder` flag), `channel` (`telegram`, `alternate`), `acked_at`, `ack_deadline_at` (`ops.ack_minutes`), `custody_scope`, `escalation_step` (`ops.escalation`), nullable `signed_ack_ref` |
| `handback_acks` | `handback_id`, `trigger` (`kill_criteria` — KC-01 `human_handback`; `zero_qualified_exposure` — `kill-criteria.yaml` `low_data.handback_ack_required`; `kill_b` — [SECURITY §6](SECURITY.md) hisobot qadami; `protective_pause` va foreign spend — `budgets.yaml` `ads.foreign_spend_behavior`; `incident`), pipeline, `entity_set_hash`, `offered_at`, `deadline_at`, nullable `accepted_by_person_id`, `accepted_at`, `channel`, `evidence_ref` (mustaqil account kirishi tasdig‘i), `escalation_step` |
| `shadow_ratings` | `(command_id, command_revision, rater_person_id)` PK, `rating` (`useful`, `neutral`, `harmful`), `rated_at`, callback nonce hash; rater effective `shadow_rater` flag’li; agregatsiya ⧗ OD-09 |

**Trust o‘qi** (`approval-policy.yaml` `trust_ramp.axis`). `trust_levels` faqat `L1_approve_each` ↔ `L2_auto_within_guardrails` o‘rtasida, trust kaliti bo‘yicha (action_type × pipeline; `trust_ramp.graduation.direction_split_actions` dagi action uchun × direction — kamaytirishdagi L2 oshirishga hech qachon L2 bermaydi, ◇ P-55) va faqat `trust_graduation` (owner, HG-L2-01) bilan ko‘tariladi; qatorlar `L1_approve_each` bilan yaratiladi. `L0_shadow` faqat pipeline_mode yoki global `shadow`dan keladi; boshlang‘ich samarali daraja `L0_shadow` (`trust_ramp.initial_level`) barcha pipeline’larning `L0_shadow` rejimidan kelib chiqadi. Samarali daraja = `min(global_mode, pipeline_mode, command’ning trust kalitidagi trust_level)`. `shared` pipeline’li command uchun pipeline rejimi `min(sale, rent)` (`shared_pipeline_mode`). Graduation: 10 ketma-ket clean `met` va oxirgi sanalgan item’dan keyin 14 kun incident’siz, owner tasdig‘i bilan; `never_auto` action’lar hech qachon L2 emas.

**Resume va restore** (`execution-policy.yaml` `resume`, `restore`). Global kill’dan keyin har pipeline `min(pre_kill_pipeline_mode, L1_approve_each)`; global `shadow` saqlanadi; `read_only` sababi hal bo‘lguncha `read_only` qoladi. KC-01’dan keyin pipeline C05 RCA, owner `takeover_scope_change` (HG-F6-04) va owner `pipeline_mode_change`gacha `L0_shadow`. Restore `killed`dan boshlanadi; `shadow`+L0 reconcile va owner qadamidan keyin; resume darajasi `min(snapshot_mode, off_host_control_journal_last_mode, L1_approve_each)`, jurnal bo‘lmasa barcha pipeline `L0_shadow`. Maintenance hold kill emas: global `read_only`, proxy admission pauza, release’dan keyin `maintenance_release` bilan faqat hold o‘zgartirgan o‘lchovlar (global rejim, proxy admission) tiklanadi, hold paytida yoqilgan kill va himoya nazoratlari o‘z chiqish qoidasigacha qoladi (`controls_raised_during_hold_persist`).

**Fleet.** Barcha sonlar `>= 0`; `serviceable_bikes = rented_bikes + reserved_bikes + available_bikes`, `total_fleet = serviceable_bikes + maintenance_bikes`; wizard rented/reserved/available/maintenance va waitlist sonlarini so‘raydi, serviceable/total hisoblanadi va oldingi valid snapshot’dagi total bilan farqi operator tasdig‘ini talab qiladi. Birinchi report’da `supersedes_report_id=NULL`; `waitlist_active=0` bo‘lsa `waitlist_oldest_at=NULL`. Qo‘shimcha fizik holat bo‘lsa schema va tenglama yangi revision. Bir kundagi javoblar append-only; valid va supersede chain bo‘yicha oxirgi valid effective; race paytida expected revision talab qilinadi; eskirgan snapshot hech qachon valid emas (`stale_snapshot_never_valid: true`). Bugungi valid snapshot bo‘lmasa barcha odatiy rent budget harakati darhol hold; 08:00 so‘rov, 09:00 eslatma va 14:00 eskalatsiya (◇ P-06, `operations.yaml` `schedule`) faqat aloqa jadvali; protective control’lar ta’sirlanmaydi. Waitlist manbai ⧗ OD-07: hozircha snapshot sonlari band’larni boshqaradi, CRM `waitlist_status_ids` cross-check; band’lar `waitlist_eligible_ready`dan.

**Sale readiness.** Manba — sales_lead’ning kunlik `/sale_ready` wizard’i (09:30 dan oldin) yoki tasdiqlangan eksport (◇ P-22); gate F6_STEP2 (◇ P-09). Yo‘q yoki eskirgan bo‘lsa sale budget increase va rent→sale ko‘chirish bloklanadi (`ALERT_SALE_READINESS_STALE`); ishlatilmagan budget sarflanmay qolishi maqbul.

`sessions` (`session_id` — random 256-bit, cookie’da faqat imzolangan ID; `person_id`, `scope` (`paperclip_ui`, `langfuse_ui`), xodim IP, `ua_hash`, `device_id`, created/expires/revoked), `login_requests` (`request_id`, `person_id`, IP, `ua_hash`, holat `pending/approved/denied/timeout`, created/decided) va `breakglass_codes` (argon2id hash, `used_at`; foydalanish faqat `paperclip_ui` scope’ini beradi) tg-auth’ga tegishli. Sessiya 12 soat, login request 2 daqiqa (Q49★). Xodim IP/UA `tg_auth_sessions` va `staff_identity` dataset’lari sifatida custody va retention bilan; agent view’lariga kirmaydi.

## 9. Konfiguratsiya, release, audit va integratsiya holati

### 9.1 Release yozuvlari

`release_manifests`: `release_id`, `release_class` (`normal`, `recovery`; `release-policy.yaml`), `manifest_digest`, `code_sha`, `config_sha`, `schema_version`, `min_compatible_code`, `max_compatible_code`, `target_profile`, `capabilities_enabled[]` va `readiness_snapshot` (qadalgan kalit revision’lari va har capability `gate_result`; manifest digest’i ichida), `artifact_digests[]` (`build_once_promote`), `workflow_definitions_digest`, `tool_schema_digest` (`schemas/tools/**`), `prompt_skill_digest`, `model_assignment_revision`, `evaluator_revision`, `policy_revision`, dependency lock hash, `tag_name`, `tag_commit`, tag imzolovchi fingerprint, `base_release_id`/`previous_release_id` (faqat initial uchun NULL), `deployment {kind: initial/update, phase: F1…F7, services[], required_acks[]}`, prepared/activated time, `active_ack_at`. Candidate manifest maydonlari [candidate-manifest.schema.json](../09_Config_Templates/schemas/candidate-manifest.schema.json)da (I19).

`release_approvals`: `approval_id` PK, `candidate_id`, `manifest_digest`, `verification_id`, `verdict`, `evaluator_revision`, `proposal_revision`, `policy_revision`, `role_revision`, `control_epoch`, approver `person_id`, `typed_confirmation_ref`, `nonce_hash`, `approved_at`, `expires_at`, nullable `revoked_at`. Normal update’da ops-bot `/release approve <candidate_id>` va typed code bilan yaratiladi (`upgrade_release`, HG-REL-01). Q65 faqat first F1da fixed owner SSH importer shu canonical row’ni signed envelope asosida yaratadi: `source: owner_ssh_signed_initial`, initialization/envelope/signature reference’lari bilan; tagning o‘zi yoki fabricated Telegram callback qabul emas. Manifest, verification, rol, policy, evaluator yoki `control_epoch` o‘zgarsa tasdiq yaroqsiz (`evolution-policy.yaml` `revalidate_on`). FE_RELEASE profilidan oldin release owner imzolagan `release-*` tag va shu yozuv bilan chiqadi; verification maydonlari FE_RELEASE’dan boshlab majburiy.

`service_revision_acks`: `(release_id, service_id)` unique; `service_id` faqat registrdan; `ack_class` (`write_gate`, `function_gate`), desired/prepared/active SHA, validation result va vaqt. To‘liq ACK kataloglari `release-policy.yaml` `write_gate_acks`/`function_gate_acks`; effective to‘plam manifest `deployment.services`dan registry ack_class bilan aynan hisoblanadi va `required_acks`ga teng. Cumulative phase floor, prior installed inventory va active/enabled capability dependency’lari tekshiriladi. Missing/unknown/extra/duplicate yoki omitted protective ACK rad; update’da oldingi current, initial’da current yo‘qligi va admission deny saqlanadi.

`release_initializations`: host uchun singleton PK (`singleton = true`), unique `bootstrap_id`, `host_identity_hash`, `installer_digest`, `approval_envelope_digest`, signer fingerprint, `candidate_id`, `manifest_digest`, `owner_person_id`, unique `nonce_hash`, unique `typed_confirmation_id`, unique `approval_id`, unique `activation_id` (publisher yaratadigan `release_activations.release_id` uchun oldindan band qilingan identity), absence-evidence reference, `state` (`approval_seeded`, `awaiting_acks`, `complete`), `created_at`, nullable `sealed_at`. Initial INSERT oldidan current/active release, prior release ledger, killed latch va boshqa used bootstrap yo‘qligi tekshiriladi. INSERT typed confirmation/release approval/audit bilan bir transaction; exact replay mavjud identity’larni qaytaradi, boshqa nonce/candidate yoki partial seed rad. Binding ustunlari immutable; `amt_release` faqat o‘sha identity progress’i va to‘liq effective ACK’dan keyingi seal’ni yozadi. First failure current yaratmaydi; retry o‘sha candidate/approval/activation va original expiry bilan. Sealed marker keyingi offline approval’ni abadiy rad qiladi; manifest update base’i active current’ga teng. Bu yangi role seed yoki killed-state reset emas.

### 9.2 Rol seed va audit

Runtime rol manbai DB; `role_seed_imports(seed_sha, imported_at, bootstrap_id)` bir martalik importni belgilaydi; eksport qayta import qilinmaydi.

`audit_log`: monoton seq, at, actor_type/id, action, sanitized target/detail, result, nullable trace ID, `prev_hash`, `row_hash`, config/policy/control revision. `append_audit` row/advisory lock ostida hash zanjirini serialize qiladi; `bigserial` raqamining o‘zi commit tartibini kafolatlamaydi. Hash zanjiri root kompromatidan mutlaq himoya emas; imzolangan zanjir digest’i off-host bilan solishtiriladi (faqat hash; AMT ma’lumotining nusxasi PC’dan chiqmaydi, Q55). Audit yozilmasa normal mutatsiya yo‘q; lokal kill latch DB’siz ham saqlanadi va keyin auditga idempotent import qilinadi.

### 9.3 Quota va muhitlar

`quota_allocations` barcha caller va vendor quota scope’ini, reserved rate/burst/lease/revocation’ni saqlaydi. amoCRM uchun owner ceiling ≤ 7 so‘rov/s (Q25 ✅, `approval-policy.yaml` `rate_limits.amocrm_global_rps_ceiling: 7`); `vendor.amocrm_quota` ajratmalari uni faqat bo‘lishi yoki pasaytirishi mumkin, oshirish yangi owner Q talab qiladi. Landing, capi, sync, gateway va operator umumiy limitdan o‘tadi; coordinator ishlamasa faqat oldindan ajratilgan bounded lokal lease ishlaydi.

DB nomlari muhit bo‘yicha [environments.yaml](../09_Config_Templates/environments.yaml)dan (`prod`: `amt`, `staging`: `amt_staging`, `sandbox`: `amt_sandbox_<candidate>`, `restore_test`: `amt_restore_test`, `restore_drill`: `amt_restore_drill`); prod bilan kesishma validator tomonidan rad. Ikkala restore muhiti AMT PC’da izolyatsiyalangan: lokal snapshot’dan tiklanadi, live credential, job va egress’siz, `killed` holatida boshlanadi; alohida tiklash hosti yo‘q (Q55).

### 9.4 Manba bo‘yicha sync va ingest

`sync_cursors` grain source+account+stream; cursor value, committed_at, page/checkpoint hash, mapping revision. Sahifa hodisalari durable commit bo‘lgandan keyin cursor siljiydi. ★ belgili qiymatlar owner qabul qilgan builder standarti ([DECISION_LOG §G](../00_Decisions/DECISION_LOG.md) Sync va Watchdog); belgisizlari boshlang‘ich taklif. Ikkalasi ham `tracking.freshness` readiness’da (gate F2_LIVE_INTAKE) tasdiqlangan qiymat bilan qo‘llanadi. Vendor endpoint nomlari va sahifa hajmlari pinned API hujjatida F2/F3’da tasdiqlanadi [T].

| Manba | O‘qish yo‘li | Cursor / oyna | Chastota | Qoida |
|---|---|---|---|---|
| amoCRM status hodisalari | sync-worker → amocrm-mcp → amoCRM events API | `amo_events`: oxirgi `created_at` − 10 daqiqa overlap | har 15 daqiqa ★ | `webhook_inbox` bilan bir dedup kaliti; kech kelgan hodisa yo‘qolmaydi |
| amoCRM lidlar | sync-worker → amocrm-mcp → leads API, `updated_at` filtri | `amo_leads` | har 15 daqiqa ★ | faqat allowlist maydonlar; contact, ism, telefon, izoh olinmaydi |
| amoCRM webhook | Caddy `mar2` → capi-bridge → `webhook_inbox` | — | real vaqt | asosiy signal; sync — reconciliation; javob durable commit bilan 1,5 s ichida, aks holda 503 (`operations.yaml#amo_webhook_contract`); o‘chgan hook `amo_webhook_liveness` bilan aniqlanadi (INC-28) |
| Meta insights | sync-worker → meta-ads-mcp | `meta_insights`: oxirgi 7 kun qayta ★ | kuniga 2 marta ★ | ad darajasi, kunlik bo‘lak; correction yangi `insight_revision` |
| Meta account spend va counter | sync-worker → meta-ads-mcp | — | har sync sikli; interval `budget.ads_pacing` | `ads_spend_snapshots`; spend pacer va exposure guard kirishi |
| Umami | sync-worker → Umami API (o‘z read token’i) | `umami` | kuniga 1 marta | |
| Landing yetkazish holati | sync-worker → landing `GET /internal/delivery?since=<cursor>` (`go.wolter.uz`, `SYNC_LANDING_DELIVERY_TOKEN`; [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) `external_dependencies[landing-delivery-api]`) | `landing_delivery` | har 1 daqiqa (nomzod; qiymat `tracking.freshness`da) | `submission_delivery`, PII’siz (`submission_id`, pipeline, `accepted_at`, `delivered_at`, holat, `crm_lead_id`, `event_id`, `consent_ref`, `custody_ref`); `crm_confirmed` — server `Lead` trigger’i |
| Contract/to‘lov manbalari | `business.outcome_sources` bo‘yicha | manba bo‘yicha | readiness | `cash_events`, `business_events` |
| OpenRouter usage | cost-watchdog → usage API | — | har 10 daqiqa ★ | `provider_usage_snapshots` |
| Tarix importi (bir martalik) | sync-worker → amocrm-mcp | qayta boshlanadigan cursor | ≤ 2 so‘rov/s ★, tunda | owner tasdiqlagan mapping (§11) |

Job’lar (`operations.yaml` `schedule`): `tracking_health` har kuni 09:30, `kill_criteria` Du 07:30, `exposure_guard` va spend pacer har sync siklida. 429 → vendor `retry_after`/backoff; takroriy quota xatosi alert; butun tarixni qayta skanerlash taqiqlangan. Har sync natijasi `tracking_health.sync_freshness`ga yoziladi.

## 10. Agent query, view’lar va `wh.metrics`

### 10.1 `wh.query`

`wh.query` bitta SELECT statement, read-only transaction, fixed `search_path=amt_ro,pg_catalog`, temp/create yo‘q, ruxsatli funksiyalar, `statement_timeout=15s`, bounded concurrency/connection va LIMIT ≤ 5000 bilan. Writable CTE, side-effect funksiya, `pg_sleep`, file/network funksiya, catalog credential, katta recursive query va cross-schema read rad. Parser yagona himoya emas; DB roli (`amt_reader`) va transaction ham cheklaydi.

### 10.2 View’lar

| View | Semantika |
|---|---|
| `v_leads` | sanitized snapshot; raw tag/UTM/name/IP yo‘q |
| `v_qualified_daily`, `v_qualified_weekly` | event-time tarixiy birinchi qualification; joriy statusdan sanamaydi |
| `v_lead_to_contract`, `v_qualified_to_contract` | alohida denominator, maturity/definition/`data_status` |
| `v_cohort_metrics` | `cohort_metrics` revision’lari va `data_status` |
| `v_pipeline_cohorts` | KC-01 kirishi: pipeline × `event_week` (Asia/Tashkent ISO hafta); `spend_minor`, `currency`, qualified soni, `qualified_cpl_event_week`, `min_sample_ref`, `baseline_revision`, baseline qiymati, `worse_pct`, `data_status`, exposure (spend va soat), measurement/attribution revision; kogorta tasdig‘i ustunlari ⧗ OD-13 |
| `v_cash_contribution` | cash/refund/contribution revision+currency, unknown explicit |
| `v_creative_performance`, `v_adset_learning` | exact creative revision, attribution va sample sifati |
| `v_fleet_today`, `v_fleet_daily` | serviceable denominator, available, waitlist, freshness; tranzaksiya/oy alohida |
| `v_waitlist` | `waitlist_aggregates`, eligible_ready va yosh bo‘laklari |
| `v_tracking_health` | kutilgan, lekin yo‘q check ham `stale`/`unknown` bo‘lib ko‘rinadi |
| `v_change_set_history` | kanonik command holatlari va `command_outcomes`; approver PII/token yo‘q |
| `v_experiments`, `v_baselines`, `v_creatives`, `v_kill_criteria` | revision va evidence ref’lari |
| `v_agent_costs_month` | actual+reserved+unattributed, `ai_runtime` cap va ulush |
| `v_ads_spend_month` | verified MTD, counter bazasi, valyuta, headroom, provider limit holati |
| `v_intake_delivery` | accepted→CRM farqi va queue yoshi, custody bytes yo‘q |
| `v_workflow_runs`, `v_owner_queue` | [WORKFLOW_RUNTIME §9](WORKFLOW_RUNTIME.md); besh savol, blocker, deadline |

### 10.3 `wh.metrics` katalogi

Agentlar biznes metrikasini faqat shu nomli endpoint’lar orqali oladi; formula agent tomonidan yozilmaydi va har endpoint bir xil qiymatni barcha dashboard va agentga beradi (UAT-01). Har javob `value` (yoki null), birlik/valyuta, `data_status`, definition/attribution/measurement revision, freshness va coverage’ni qaytaradi. Yangi endpoint yoki formula o‘zgarishi faqat release orqali.

| Endpoint | Parametrlar | View | Ta’rif |
|---|---|---|---|
| `qualified_leads` | pipeline, from, to, grain | `v_qualified_daily`/`weekly` | BUSINESS_CONTRACT §8 `qualified_leads` |
| `qualified_cpl` | pipeline, from, to, grain | `v_qualified_weekly` | §8 `qualified_cpl` (event davri) |
| `cohort_qualified_cpl` | pipeline, cohort_from, cohort_to | `v_cohort_metrics` | §8 Cohort qualified CPL |
| `lead_to_qualified` | pipeline, cohort_from, cohort_to | `v_cohort_metrics` | §8 `lead_to_qualified` |
| `lead_to_contract` | pipeline, cohort_from, cohort_to | `v_lead_to_contract` | §8 `lead_to_contract` (guardrail, Q04 ✅) |
| `qualified_to_contract` | pipeline, cohort_from, cohort_to | `v_qualified_to_contract` | §8 |
| `cash_contribution` | pipeline, period, basis | `v_cash_contribution` | §4 va §8 `contract_cpa`/cash/contribution |
| `utilization` | from, to | `v_fleet_daily` | §5 `utilization`; denominator nol → unknown |
| `waitlist` | from, to | `v_waitlist` | §5 waitlist |
| `creative_ranking` | pipeline, week, min_n | `v_creative_performance` | §7: denominator, coverage, min N |
| `spend_vs_limit` | month | `v_ads_spend_month`, `v_agent_costs_month` | ads MTD/headroom va AI actual+reserved |
| `pipeline_cohorts` | pipeline, weeks | `v_pipeline_cohorts` | KC-01 kirishi |
| `tracking_health` | days | `v_tracking_health` | [TRACKING_CAPI §6](TRACKING_CAPI.md) |
| `experiments` | pipeline, state | `v_experiments` | Q41 ✅ bitta pipeline’da bitta eksperiment |
| `entity_spend` | entity_type, entity_id, from, to, grain | `v_entity_daily` | managed ad set yoki campaign spend’i; `expected_effect.scope: entity` uchun (◇ P-43) |
| `entity_qualified` | entity_type, entity_id, from, to, grain | `v_entity_daily` | shu entity’ga atributsiya qilingan qualified (attribution basis explicit, §7); `scope: entity` uchun |

**Entity read selector.** `wh.metrics` tool’ining wire maydonlari `metrics[]`, `date_from`, `date_to`, `grain` va optional `pipeline`; jadvaldagi `from/to` shu sanalarning qisqa nomi. `entity_spend/entity_qualified` so‘ralsa qo‘shimcha `entity_type` (`campaign|adset`) va `entity_id` (1–24 raqamli bounded string) ikkalasi majburiy. Bitta so‘rov faqat shu ikki entity metric’dan iborat bo‘lishi mumkin; entity va pipeline metric’lari aralashmaydi, non-entity so‘rovda entity selector man etiladi. Account caller argumenti emas, serverning tasdiqlangan account scope’i; managed entity mavjudligi, `released_at` yo‘qligi va optional pipeline bilan mosligi tekshiriladi. Calendar sanalar haqiqiy, `date_from <= date_to`; server configured row/timeout limiti va parametrli view’dan tashqari query yo‘q. `scope: entity` outcome aynan shu selector’ni command target’dan oladi (§6.1); selector uchun chiqarilgan natija/birlik/currency va attribution revision’i evidence’da yoziladi.

`experiments` bir pipeline’da bitta running partial unique index bilan; holatlar planned/running/stopped/concluded, natija `met`/`not_met`/`inconclusive`, min sample, primary/guardrail metrikalar, owner tasdiqlagan maturity va `data_status` qoidalari. Eksperiment arm’ining live exposure’i `experiment_exposure` approval’ini talab qiladi.

## 11. Migration, import va retention

| Bosqich | Quriladigan yozuvlar |
|---|---|
| F1 | people/roles/person_flags/`responsibility_assignments`/roles_audit/typed_confirmations, `readiness_records`/`readiness_signatures` (F1 profillari shu yozuvlar bilan yopiladi), sessions/login/breakglass, audit, `gateway_state`/`control_events`/`agent_runtime_state`, release manifest/approval/`release_initializations` va ACK, AI request/budget ledger (`ai_runtime`), `provider_usage_snapshots`, `delivery_outbox`, workflow jadvallari ([WORKFLOW_RUNTIME §3](WORKFLOW_RUNTIME.md)); pullik runtime ularsiz boshlanmaydi |
| F2 | `submission_delivery`, `webhook_inbox`, `capi_events`/`capi_attempts`, `monitor_acks` va `heartbeat_snapshot()`, consent, event/snapshot, `tracking_health`/`tracking_streaks`, `sync_cursors`, `quota_allocations`, `incident_acks`; live trafikdan oldin |
| F3 | command/attempt/approval, `command_review_bindings`/`command_approval_bindings`, `command_outcomes`, `step_command_links`, ads spend/reservation/commitment, `budget_change_ledger`, `protective_actions`, creative/review/human check/copy artifact, dependency, managed entities, trust, fleet/waitlist/sale readiness, kill va kill-criteria yozuvlari, `handback_acks`, `shadow_ratings` |
| FE | `evolution_signals`, `upgrade_proposals`, `candidate_manifests`, `verification_results`, `release_activations`, `harness_handovers`, `migration_drills`, `independent_reviews`, `improvement_memory`, `engineering` budget hisobi; F1’dan keyin parallel |

Keyingi bosqich migration’i oldingi servislar bilan mosligini isbotlaydi. Migration faqat release `prepared` bosqichida `amt_migrate` → `amt_migrator` orqali bajariladi.

**Import.** Tizim noldan quriladi. Mavjud ma’lumot (amoCRM tarixi, baseline manbalari, takeover qilinadigan kampaniyalar) faqat owner tasdiqlagan mapping bilan import qilinadi: mapping revision, manba, qamrov, natija hisobi va audit bilan. Tasdiqlanmagan mapping bilan import yo‘q; mos kelmagan qiymat `unknown` yoki `missing_data` bo‘ladi, uydirma qiymat kiritilmaydi. Rol seed’i — `role_seed_imports`; tarix importi ≤ 2 so‘rov/s ★, qayta boshlanadigan cursor bilan.

**Retention.** Har dataset, backup va raw asset uchun muddat owner va custody mas’uli tasdiqlagan `privacy.retention` reyestrida. Boshlang‘ich taklif (tasdiqlanguncha qiymat emas): CAPI/tracking/cost agregat 24 oy; trace va render 180 kun; auth 90 kun; operational JSON log 30 kun; workflow run metadata 24 oy. Audit, lead ID va business event uchun “PII yo‘q” deb abadiy saqlash avtomatik ruxsat emas. Deletion/withdrawal tombstone keyingi restore/backfill’da ham qayta qo‘llanadi. Backup — AMT PC’dagi lokal snapshot, 7 kun (Q55). Backup va dataset RPO/RTO `recovery.*` readiness’da, [BACKUP_RESTORE](../06_Runbooks/BACKUP_RESTORE.md) bo‘yicha. UAT-01–20, UAT-23–28, UAT-30–32 va EVO-AT01/02/06/07 schema, replay, salbiy grant va migration dalillariga bog‘lanadi.

## 12. Workflow va evolution yozuvlari

### 12.1 Workflow jadvallari

`workflow_definitions`, `workflow_runs`, `step_runs`, `workflow_events`, `handoffs`, `artifact_refs`, `workflow_timers`, `workflow_signals` va `controller_epochs` maydonlari, grant va retention’i [WORKFLOW_RUNTIME §3](WORKFLOW_RUNTIME.md)da; bu yerda takrorlanmaydi. Yozuvchi faqat `amt_workflow`; boshqa servislar faqat signal funksiyalari orqali. `controller_epochs` — harness epoch yozuvi; uni ham `amt_workflow` yozadi, `amt-release` faqat WF-E02 handover’ida `advance_controller_epoch()` funksiyasini chaqiradi. Command ledger bilan bog‘lanish §6.5 da; run/step/command/vendor holatlari bir-birini almashtirmaydi (I16).

### 12.2 Evolution yozuvlari

Sikl va vakolat [EVOLUTION_CONTRACT](../11_Production_Contracts/EVOLUTION_CONTRACT.md), texnik dizayn [SELF_EVOLUTION](SELF_EVOLUTION.md)da.

| Yozuv | Maydonlar manbai | Yozuvchi | Izoh |
|---|---|---|---|
| `evolution_signals` | `signal_id`, manba (`evolution-policy.yaml` `signal_sources`), `problem_fingerprint`, evidence ref’lari, disposition, nullable `proposal_id` | `amt_workflow` → `submit_signal()`; agentning `evo.signal.submit` tool’i gateway orqali shu funksiyani chaqiradi | dedup `problem_fingerprint` bo‘yicha; PII’siz |
| `upgrade_proposals` | [upgrade-proposal.schema.json](../09_Config_Templates/schemas/upgrade-proposal.schema.json); `(proposal_id, proposal_revision)` immutable | `amt_workflow` | tasdiq `upgrade_proposal_approval` (owner) |
| `candidate_manifests` | [candidate-manifest.schema.json](../09_Config_Templates/schemas/candidate-manifest.schema.json); `manifest_digest` PK | `amt_workflow` (amt-sandbox natijasi socket orqali) | har maydon o‘zgarsa yangi digest |
| `verification_results` | [verification-result.schema.json](../09_Config_Templates/schemas/verification-result.schema.json); `verification_id` PK | faqat `amt_verify` | `criteria_changes_detected` → `fail` |
| `release_approvals` | §9.1 | normal `amt_ops`; Q65 first-only fixed owner importer | HG-REL-01; oddiy publisher DB approval va signed tag talabini saqlaydi |
| `release_activations` | `release_id`, `manifest_digest`, `approval_id`, holat (`requested`, `validated`, `prepared`, `activated`, `acked`, `observing`, `closed`, `refused`, `rolled_back`), `refusal_code`, `maintenance_hold_ref`, vaqtlar | `amt_release` | [SELF_EVOLUTION §6](SELF_EVOLUTION.md) |
| `harness_handovers` | `handover_id`, from/to release, `inventory_digest`, run disposition rejasi ref’i, holat, epoch before/after, `typed_confirmation_ref` (`harness_handover`), evidence ref | `amt_release` | `controller_epochs.handover_evidence_ref` shu yozuvga ko‘rsatadi |
| `migration_drills` | `drill_id` PK, `candidate_id`, `manifest_digest`, `environment` (`restore_drill`), forward migration natijasi, rollback natijasi, `data_check_ref`, operator `person_id`, `run_at`, evidence ref, nullable `typed_confirmation_ref` (`migration_drill`, owner `/drill accept`) | `amt_release` (drill harness); qabul — `amt_ops` | D sinfi release sharti |
| `independent_reviews` | `review_id` PK, `candidate_id`, `manifest_digest`, reviewer `person_id` (faol `independent_reviewer` assignment, muallif emas), `github_review_ref` (candidate PR’dagi review, `people.github_login` bilan), `verdict` (`pass`, `fail`), `reviewed_at`; owner `/protected approve` uni `typed_confirmation_ref` bilan bog‘laydi | `amt_release` (read-only GitHub import) | E sinfi release sharti; `class_e_frozen` bo‘lsa yozuv qabul qilinmaydi |
| `improvement_memory` | [improvement-memory-record.schema.json](../09_Config_Templates/schemas/improvement-memory-record.schema.json) | `amt_workflow` | guidance’ga faqat `accepted` va `guidance_eligible` |
| `engineering` budget hisobi | §7.1 `budget_accounts(scope = engineering)` va `reservations` | `amt_eng_proxy` | runtime va ads hisoblaridan alohida |

Evolution yozuvlarida PII va secret yo‘q; retention `privacy.retention` va `recovery.full_datasets`da tasdiqlanadi.
