# WORKFLOW RUNTIME — durable ish birligining texnik dizayni

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Kontrakt (nima kafolatlanadi): [WORKFLOW_CONTRACT](../11_Production_Contracts/WORKFLOW_CONTRACT.md). Bu hujjat qanday quriladi va qanday sinaladi. Mexanizm tanlovi [ADR-024](../04_ADR/ADR-024-workflow-runtime-capability-first.md) bo‘yicha capability test natijasiga bog‘liq; quyidagi dizayn — standart gipoteza: AMT’ning mavjud PostgreSQL ledger’i ustidagi durable workflow jadvallari, Paperclip esa projection va vazifa yuzasi. Yangi vendor yoki workflow engine tanlanmaydi.

## 1. Komponent va chegaralar

| Element | Qiymat |
|---|---|
| Servis | `amt-workflow`, Unix user `amt-workflow`, private Unix socket; Internetga ochilmaydi |
| DB roli | `amt_workflow` — faqat workflow jadvallariga yozadi; command ledger’ga faqat `run_id/step_id` bog‘lovchi function orqali |
| Chaqiruvchilar | gateway (agent output/handoff), ops-bot (inson signali), executor (command natijasi), sync/capi/watchdog (hodisa signali), release controller (epoch/handover) — har biri o‘z service audience token’i bilan |
| Agentlar | runtime’ni to‘g‘ridan-to‘g‘ri chaqirmaydi; gateway’dagi tor tool’lar: `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker` |
| Paperclip | agent step’i uchun issue yaratadi/yangilaydi (projection); issue holati truth emas |
| Release va kill | `amt-control` latch/epoch’i yopiq bo‘lsa runtime yangi tashqi effektli step’ni dispatch qilmaydi; ichki tahlil step’lari ham killed’da LLM proxy tomonidan rad etiladi |

`amt-workflow` resurs jihatdan `production` slice’ida, scheduler esa yagona faol controller epoch’i bilan ishlaydi ([resource-policy.yaml](../09_Config_Templates/resource-policy.yaml)).

## 2. Interface

| Operatsiya | Kirish | Natija va guard |
|---|---|---|
| `start` | `workflow_id`, input, dedup kaliti, chaqiruvchi | definition’ning amaldagi `definition_version`/digest’iga pin; `authorization.may_start` tekshiruvi; ochiq run bo‘lsa dedup bo‘yicha o‘sha `run_id` |
| `signal` | `run_id` yoki `correlation_key`, signal turi va ID | signal ID dedup; yopiq run uchun faqat audit (`late_audit_only`) |
| `status` | `run_id` yoki filtr | owner ko‘rinishining besh savoli + blocker/deadline/oxirgi ishonchli natija |
| `cancel` | `run_id`, sabab, aktor | `authorization.may_cancel`; pending command’lar `cancelled/expired`; compensation alohida command |
| `submit_output` (gateway orqali) | step, artifact reference’lari | step egasi va lease fence mosligi; konvert yozilishidan oldin deterministik tekshiriladi (`workflow-policy.yaml#handoff_validation`: sxema, `analysis`, pin, freshness, `round`, payload; o‘tmasa `invalid_args`); artifact digest yoziladi |
| `handoff_decide` (gateway orqali) | handoff ID, `accepted/rejected`, sabab | qabul qiluvchi identity va [WORKFLOW_CONTRACT §6](../11_Production_Contracts/WORKFLOW_CONTRACT.md) tekshiruvlari |

## 3. Logical yozuvlar

Ustunlar kontrakt darajasida; konkret migration F1’da yoziladi. Barcha vaqt `timestamptz` UTC, pul `bigint *_minor` + currency, JSON sxema bilan tekshiriladi va PII’siz.

| Jadval | Grain va majburiy maydonlar |
|---|---|
| `workflow_definitions` | bitta immutable definition: `workflow_id`, `definition_version`, `definition_digest`, `release_id`, `published_at`, `status (active/retired)`; UNIQUE `(workflow_id, definition_version)` |
| `workflow_runs` | bitta run: `run_id PK`, `workflow_id`, `definition_version`, `definition_digest`, `release_id`, `parent_run_id`, `root_run_id`, `correlation_key`, `dedup_key`, `entity_refs`, `revisions`, `status`, `business_outcome`, `current_step_id`, `waiting_for`, `waiting_until`, `decision_deadline`, `controller_epoch`, `cost_account`, `cost_reserved_minor`, `cost_actual_minor`, `currency`, `last_trusted_result_ref`, `created_at`, `updated_at`, `completed_at`; ochiq run uchun partial UNIQUE `(workflow_id, dedup_key)` |
| `step_runs` | bitta step urinishi: `(run_id, step_id, attempt_no)` UNIQUE, `status`, `executor_type`, `executor_ref`, `lease_owner`, `lease_until`, `fence`, `input_refs`, `output_refs`, nullable `command_id/command_revision`, nullable `handoff_id`, `started_at`, `finished_at`, `error_code`; bitta step uchun bitta hal qilinmagan urinish |
| `workflow_events` | append-only: `seq`, `run_id`, nullable `step_id`, `event_type`, `payload_hash`, `actor`, `controller_epoch`, `at`, `audit_ref` |
| `handoffs` | `handoff_id PK`, `run_id`, `step_id`, `from`, `to`, `payload_ref`, `payload_hash`, `status`, `decided_by`, `decided_at`, `reason_code`, `expires_at` |
| `artifact_refs` | `run_id`, `step_id`, `kind`, `ref`, `digest`, `created_at`; creative/review/offer/report/proposal/manifest bog‘lanishi |
| `workflow_timers` | `timer_id`, `run_id`, nullable `step_id`, `kind`, `fire_at`, `state (pending/fired/cancelled)`, `fired_at` |
| `workflow_signals` | `signal_id`, nullable `run_id`, `correlation_key`, `kind`, `source`, `received_at`, `payload_hash`, `disposition (attached/duplicate/late_audit_only)` |
| `controller_epochs` | `epoch`, `controller_id`, `release_id`, `acquired_at`, `handover_evidence_ref`, `revoked_at` |

`change_set_items` va `execution_attempts` ([DATA_MODEL §6](DATA_MODEL.md)) `run_id` va `step_id` ustunlarini oladi: workflow step’idan yaratilgan har command uchun `NOT NULL`. Command state enum va o‘tishlari o‘zgarmaydi. B rejimidagi emergency pause command’lari WF-O02 incident run’iga bog‘lanadi.

**Grant:** yozish — faqat `amt_workflow`; gateway/ops/executor/sync faqat `SECURITY DEFINER` signal function’lari orqali; agentlar `amt_ro.v_workflow_runs`, `amt_ro.v_owner_queue` va o‘z step’lari uchun sanitizatsiyalangan view’ni o‘qiydi. `UPDATE/DELETE workflow_events` barcha runtime rollari uchun rad. Grantlar F1’da ijobiy va salbiy test bilan isbotlanadi.

**Retention:** run/step/event metadata `privacy.retention` va `recovery.full_datasets` da tasdiqlanadi; boshlang‘ich taklif CAPI/tracking agregatlari bilan bir xil 24 oy. Payload’lar faqat reference/digest; custody’dagi asl material o‘z retention qoidasida.

## 4. Paperclip projection

Agent step’i `ready` bo‘lganda runtime Paperclip’da issue yaratadi: assignee — rol, maqsad, `done_when`, deadline, `run_id`/`step_id`/`handoff_id`. Agent assignment yoki routine orqali managed runner bilan uyg‘otiladi; matndagi mention’ga uyg‘onish kafolati taxmin qilinmaydi. Natija issue izohi orqali emas, gateway `workflow.submit_output` orqali qaytadi. Runtime issue holatini sinxronlaydi. Kimdir issue’ni qo‘lda yopsa drift hodisasi yoziladi, step tugamaydi va issue qayta ochiladi yoki egaga xabar beriladi. Paperclip yo‘q paytda run’lar `waiting` holatida durable qoladi; Paperclip qaytgach projection qayta quriladi.

## 5. Scheduler, timer va signal

Scheduler yagona faol controller epoch’i ostida ishlaydi va `workflow_timers` dagi `fire_at <= now()` yozuvlarini `FOR UPDATE SKIP LOCKED` bilan oladi. Cron jadvallari Asia/Tashkent bo‘yicha talqin qilinadi, DB’da UTC. Timer otilishi `workflow_events` va step o‘tishi bilan bitta tranzaksiyada. Signal avval `workflow_signals` ga durable yoziladi, keyin run’ga biriktiriladi; takroriy signal `duplicate`. Kechikkan callback yopilgan run’da tashqi harakat chiqarmaydi. Yangi trigger avval `dedup_key` bo‘yicha ochiq run’ga biriktiriladi; keyin `workflow-policy.yaml#concurrency_semantics` limitlari ochiq run’lar soni bo‘yicha tekshiriladi va limit to‘lsa definition’dagi `on_limit` qo‘llanadi (navbat, audit bilan o‘tkazib yuborish yoki ALERT_WORKFLOW_BLOCKED bilan rad).

`operations.yaml#schedule` dagi har yozuvni nima bajarishi `workflow-policy.yaml#schedule_execution` da yoziladi (validator T11): workflow (trigger, step yoki o‘sha yozuvga havola qiluvchi schedule timer’i — kechikkan timer yoki boshlanmagan run `ALERT_WORKFLOW_BLOCKED`) yoki ro‘yxatdagi servisning deterministik job’i. Job har tick uchun `schedule_runs` ga bitta yakun yozuvini qoldiradi; o‘sha id’ning keyingi tick’i yoki biznes kuni oxiri (qaysi biri oldin bo‘lsa) gacha yozuv bo‘lmasa job’ning `missed_run_alert` i (`ALERT_SCHEDULE_MISSED`, backup uchun `ALERT_BACKUP_STALE`) technical_operator’ga ketadi — jim o‘tkazib yuborilgan jadval qolmaydi. Workflow yozuvida ham `missed_run_alert` bo‘lishi mumkin: rejalashtirilgan run yoki unga bog‘langan step vaqtida boshlanmasa (concurrency limiti, precondition) scheduler shu alert’ni chiqaradi; himoya yozuvlari (`schedule_protective`: tracking_health, exposure_guard, kill_criteria, backup) uchun u majburiy va ularning workflow’ida start freshness yo‘q — eskirgan ma’lumot step ichida `blocked` deb yoziladi, run boshlanmay qolmaydi (KC uchun `ALERT_KILL_CRITERIA` `evaluation_not_started`). Oylik yozuvlar ham workflow: `spend_cap_update` — WF-O04, `retro` — WF-O05. Workflow yozuvi step yoki timer’ni nomlaydi; timer’siz yozuvda jadval id’si workflow `trigger.source_refs` ida (jadval run’ni boshlaydi) yoki step’ning `schedule_refs` ida bo‘ladi (step run ichida o‘sha slotga tayanadi: WF-B03 S04 — `batch_cutoff`, WF-B06 S03 — `weekly_report_review`), `missed_run_alert` esa [TELEGRAM §6.2](TELEGRAM.md) katalogidagi kod (T11). Step va schedule timer bilan berilgan yozuv step’ning eng erta boshlanishini belgilaydi: run umri (`max_duration`) shu slotgacha bo‘lgan vaqtni ham qamraydi (W14; WF-B06 S09 — juma 16:00). Eskalatsiya kanali jadval slotini `(<jadval id> HH:MM)` deb nomlasa, run boshlanishi + `after` aynan shu vaqtga va jadvaldagi vaqtga tushadi (T08; WF-O04 — `change_set 10:00`).

### Command aggregation va run yakuni

Command-linked step `workflow-policy.yaml#command_aggregation` dagi rol, `complete_when` va tartibli qoidalarga amal qiladi; dispatch’dagi `uncertain` band reconciliation’ga o‘tadi, success hisoblanmaydi. Custody transfer faqat `manual_resolution_handoff`ning durable owner task + I18 accepted handoff shartlari bilan; exact command/attempt/evidence, receiver/time va reservation/conflict-lock reference’lari saqlanadi, lock/reservation bo‘shamaydi. Taskning o‘zi yetmaydi. Run-owned unresolved band run’ni ochiq saqlaydi; terminal dalil yoki accepted transfer’dan keyin `running` checkpoint’i, keyin normal completion ([WORKFLOW_CONTRACT §3](../11_Production_Contracts/WORKFLOW_CONTRACT.md)).

WF-O02 S03 containment cause snapshot’i audit, `handback_triggers` esa mustaqil S09 ACK’ni ochadi. Recovery’dan keyin S10 current amt-control ledger’dan `remaining_owner_causes`ni qayta oladi: Q63 billing_unreliable owner vazifasiga kirmaydi, S06 faqat boshqa sabablar uchun owner/never_auto. S11 exact raised-event va `clearance_control_epoch`, policy/key/period/reconciliation dalillarining clear tranzaksiyasi paytidagi live holatga mosligini tekshiradi; o‘sha paytda yaroqli qabul qilingan tarixiy clear keyingi vakolatli epoch almashishidan yaroqsiz bo‘lib qolmaydi. Hozirgi cause snapshot’i alohida qayta o‘qiladi; eski clear boshqa yangi raised-control-event’ni hech qachon yechmaydi. Shunday qilib avtomatik billing clear’i hamda boshqa sabablarning vakolatli resolution event’lari tekshiriladi (`workflow-policy.yaml#incident_cause_resolution`); yo‘qolgan flag, ochilgan AI yoki task status’i dalil emas. S07 S05/S06/S09/S11ni kutadi, start va har cause event’da zero-unresolvedni qayta tekshiradi; yangi sabab observation’ni bloklaydi va verified closure’dan keyin oynani boshidan boshlaydi. Handback-only holatda S09 S02/S05ni kutmaydi; billing-only holatda S06 skip bo‘lsa ham S11 haqiqiy matching automatic clear’ni kutadi.

## 6. Lease, fence va epoch

Step claim `lease_owner`, `lease_until` va monoton `fence` bilan. Lease muddati o‘tsa yangi urinish fence’ni oshiradi; eski worker natijasi va eski fence bilan har yozish rad. Controller epoch handover’da oshadi ([SELF_EVOLUTION §6](SELF_EVOLUTION.md)); har dispatch, timer otilishi va command yaratish joriy epoch’ni tekshiradi. Eski epoch’dagi process qaytsa uning yozuvlari rad etiladi va auditga tushadi.

## 7. Tiklash

Process restart: ochiq run’lar yuklanadi, muddati o‘tgan lease’lar qayta claim qilinadi, `uncertain` command’lar reconciliation’ga yuboriladi; tugagan step qayta bajarilmaydi. Mantiqiy xato (noto‘g‘ri migration, o‘chirish, noto‘g‘ri ommaviy yozuv): workflow jadvallari `amt` bazasi bilan birga lokal snapshot’da (`pg_dump -Fc`, o‘sha RAID1, 7 kun; Q55); restore har doim `killed` bilan boshlanadi (◇ P-16; `shadow`+L0 faqat reconcile va owner qadamidan keyin), timer’lar avtomatik otilmaydi, read/ingest → remote reconciliation → gate → owner resume tartibi ([BACKUP_RESTORE](../06_Runbooks/BACKUP_RESTORE.md), [RUN_RESUME](../06_Runbooks/RUN_RESUME.md)). RPO/RTO `workflow.recovery` da o‘lchanadi va faqat shu holatni qamraydi. Host yo‘qolishi (Q55): PC buzilsa disklar boshqa PC’ga ko‘chiriladi va ledger saqlanadi; ikkala disk yo‘qolsa workflow ledger’i (run, step, handoff, timer va event tarixi) ham yo‘qoladi — snapshot o‘sha disklarda — va tiklanmaydi. Yangi PC’da (`00-owner-bootstrap.sh --rebuild`) runtime bo‘sh ledger bilan `killed`dan boshlanadi; tashqi holat (Meta, amoCRM, landing) remote reconciliation bilan o‘qiladi, intake va CAPI manbalardan qayta quriladi ([TRACKING_CAPI §8](TRACKING_CAPI.md)), eski approval va handoff tirilmaydi (I14).

## 8. Capability test (`workflow.mechanism`)

F1’da haqiqiy prototip quyidagilarni isbotlaydi; har biri `WF-TEST-RT-*` sifatida yoziladi va natija ADR-024 ga ilova qilinadi:

| Test | Kutilgan |
|---|---|
| WF-TEST-RT-CRASH | step o‘rtasida process o‘ldiriladi → oxirgi checkpoint’dan davom, tugagan step qayta bajarilmaydi |
| WF-TEST-RT-TIMER | restart orqali o‘tadigan timer o‘z vaqtida bir marta otiladi |
| WF-TEST-RT-DUPSIG | bir signal ikki marta keladi → bitta ta’sir |
| WF-TEST-RT-LATE | run yopilgandan keyin callback → faqat audit |
| WF-TEST-RT-HANDOFF | handoff reject va expiry → blocker va eskalatsiya; WF-B04 review handoff’lari exact current revision va muallifdan boshqa reviewer’ni talab qiladi |
| WF-TEST-RT-DRIFT | Paperclip issue qo‘lda yopiladi → step tugamaydi, drift hodisasi |
| WF-TEST-RT-LEASE | lease takeover, eski worker qaytadi → eski fence rad |
| WF-TEST-RT-EPOCH | controller handover, eski controller qaytadi → dispatch rad |
| WF-TEST-RT-LONGWAIT | ko‘p kunlik kutish process yoki LLM sessiyasini ushlamaydi |
| WF-TEST-RT-CONCURRENCY | limit to‘lganda trigger `concurrency_semantics` bo‘yicha `queue`, `skip_with_audit` yoki `reject_with_alert`; ochiq `waiting`/`reconciling` run’lar sanaladi; WF-B03 oldingi kun reconcile qilinayotganda ham yangi kun run’i boshlanadi |
| WF-TEST-RT-CHILD-START | child faqat parent step `starts` ida e’lon qilingan bo‘lsa `parent_run_id` bilan boshlanadi; `await` (`none`, `started`, `child_completed`) aynan bajariladi; e’lon qilinmagan `parent_run` start rad etiladi |
| WF-TEST-RT-COSTCAP | run’ning `cost_actual_minor + cost_reserved_minor` cap’ga yetganda keyingi LLM so‘rov `run_cost_cap` bilan rad etiladi, step `blocked`, `ALERT_WORKFLOW_BLOCKED`; himoya pauzasi va reconciliation to‘xtamaydi |

Testlar o‘tmasa F1 workflow gate’i `blocked`; muammo capability test va yangi ADR bilan hal qilinadi, kontrakt zaiflashtirilmaydi.

## 9. Owner ko‘rinishi

`amt_ro.v_owner_queue` view’i har ochiq run uchun: nima bajarilmoqda (workflow, step, entity), kutilgan natija (`purpose` + expected effect), kimdan nima kerak (`waiting_for`, rol, deadline), qancha sarflandi (`cost_actual_minor` + reserved, hisob turi bo‘yicha), keyingi qadam, blocker va oxirgi ishonchli natija. Ops-bot `/status` qisqa BLUF, Paperclip dashboard to‘liq jadval beradi. Ma’lumot PII’siz va manba reference’lari bilan.
