# RUNBOOK — Owner kill, epoch va human handback

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Kanonik tartib: [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I06–I07, [SECURITY §6–§7](../03_Architecture/SECURITY.md) va [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) (`kill_*`, `resume`, `restore`, `maintenance_hold`). Bu runbook ularni inson qadamlariga aylantiradi. Ziddiyat bo‘lsa config va SECURITY §6 ustun; ziddiyat [OPEN_ITEMS §4](../00_Decisions/OPEN_ITEMS.md) ga yoziladi.

**Kim:** kill va resume faqat `owner` (`kill_switch`, `control_resume` — typed code, `never_auto`). **Qachon:** AI noto‘g‘ri harakat qilayotganiga shubha, nazoratsiz xarajat, xavfsizlik yoki PII hodisasi, Meta akkaunt muammosi. Ikkilansangiz — bosing: A rejim qaytariladigan (Type-2) harakat va reklamani o‘zi to‘xtatmaydi. Primary/deputy (`ops_responder` flag) ACK qiladi, read-only diagnostika va eskalatsiya qiladi. Oldindan ruxsat etilgan protective controls (§7) inson buyrug‘isiz ishlaydi; bu owner-only vakolat emas.

## 1. Birinchi amal va ikki rejim

Kill qabul qilinganda **birinchi amal** — `amt-control` lokal himoyalangan control journal’ida kill latch va monoton `control_epoch`ni fsync bilan yozish (`kill_first: durable_local_latch_and_epoch`; ◇ P-03, qattiqroq — darhol amal qiladi). Shu paytdan dispatcher barrier yangi normal tashqi write’ni, proxy esa yangi LLM/media dispatch’ni rad etadi. DB transaction, snapshot, Paperclip javobi yoki remote API bundan oldin kutilmaydi; latch DB mavjudligiga bog‘lanmaydi. Vendor bizning epoch’ni biladi deb olinmaydi.

Standart rejim — **A** ★ (`kill_default_mode: A`, [DECISION_LOG §H](../00_Decisions/DECISION_LOG.md)). Bot birinchi bo‘lib A ni taklif qiladi; B faqat ongli tanlov bilan.

| Rejim | Nima to‘xtaydi | Reklama |
|---|---|---|
| **A `ai_only`** (standart ★) | latch→epoch; normal tashqi write, LLM/media, amoCRM yozish, GitHub PR yozish va `normal` release rad (faqat `release_class: recovery` o‘tadi); jo‘natilmagan `approved`/`claimed` itemlar `cancelled` (`reason_code=kill`, rezerv bo‘shatiladi); agent va routine pauza; agent tokenlari rotatsiya; durable audit + outbox | Meta’dagi reklama oxirgi holatda davom etadi; uni provider account spending limit (Q37 ✅) va `protective_pause` (◇ P-21) cheklaydi; inson Ads Manager custody’si saqlanadi |
| **B `ai_and_ads`** | A’dagi hammasi, latch birinchi; keyin har managed entity uchun **eng yuqori to‘liq managed daraja** PAUSED: butun kampaniya managed bo‘lsa — kampaniya, aks holda ad set yoki ad; har entity natijasi va reconcile | AMT boshqaradigan entity’lar to‘xtaydi; foreign (inson boshqaradigan) parent va entity’ga tegilmaydi; `partial_failure` va tasdiqlanmagan entity yashirilmaydi |

B pauzasi yangi credential yoki UID talab qilmaydi: `amt-control` pause-only buyruq beradi, `amt-executor`ning pause-only emergency yo‘li har entity’ni qayta o‘qiydi → pause → verify qiladi va natijani kill log hamda `protective_actions`ga yozadi. Bu yo‘l hech qachon activate, budget increase yoki create qilmaydi va agentga berilmaydi.

### 1.1 Kill paytida yozuvchi klasslari

Kanonik jadval — [SECURITY §6](../03_Architecture/SECURITY.md) (`writer_classes_ref`). Qisqacha (`kill_rejects` / `kill_allows`):

| Yozuvchi | `killed` holatida |
|---|---|
| executor — Meta normal write | rad (epoch tekshiruvi) |
| executor — `protective_pause` va B pauzasi | ruxsat, faqat pause (`protective_pause` `shadow`, `enabled`, `read_only` va `killed` rejimlarida ishlaydi) |
| amocrm-mcp — teg/maydon yozish | rad |
| gateway — GitHub PR (landing, offer) | rad |
| llm-proxy — LLM/media | yangi admission rad; ishlab turgan rezervlar settle bo‘ladi |
| amt-release — release | faqat `release_class: recovery` (containment, reconciliation yoki oldin tekshirilgan release’ni tiklash; owner ikki bosqich bilan); `normal` release rad |
| capi-bridge — CAPI yetkazish | davom etadi (deterministik hot path, ADR-007) |
| landing → CRM yetkazish | davom etadi |
| ops-bot — xabar va ACK outbox | davom etadi |

**In-flight:** latchdan oldin jo‘natilgan remote so‘rov keyin bajarilishi mumkin. U bekor bo‘ldi deb hisoblanmaydi: attempt `uncertain → reconciling` va haqiqiy remote holat bilan `succeeded | failed_confirmed | manual_resolution` ga yakunlanadi. B’da pauza muvaffaqiyatsiz bo‘lsa: signal va responder, provider spending limit, owner yoki targetolog qo‘lda Ads Manager orqali; “hammasi to‘xtadi” deyilmaydi.

## 2. Telegram va SSH yo‘li

**Telegram (asosiy yo‘l):**

1. Ops bot guruhida yoki DM’da `/pause_all`.
2. Bot rejimni so‘raydi: **A** (standart, birinchi tugma) yoki **B**.
3. Bot xulosani ko‘rsatadi (rejim, ta’sir qiladigan pipeline va entity soni, in-flight soni) → “Ha, to‘xtat” tugmasi.
4. Bot 4 xonali bir martalik kod chiqaradi → **2 daqiqa ichida** `TASDIQ <kod>` ★. Kod — ongli harakat tasdig‘i, ikkinchi autentifikatsiya omili emas; identity Telegram akkaunti, cloud-password attestatsiyasi va tg-auth’ga tayanadi.
5. Callback identity, sessiya va joriy rol serverda qayta tekshiriladi. Buning uchun ops DB va ops inbox ishlashi kerak (`telegram_kill_requires: [ops_db_available, ops_inbox_available]`).
6. Bot natijani beradi: latch vaqti va epoch, in-flight soni, B’da paused/failed/unverified entity ro‘yxati, snapshot ID (olinmagan bo‘lsa `NULL` + sabab), incident ID (`ALERT_KILLED`). Remote bosqich kechiksa lokal natija darhol, qolgani durable outbox orqali keyin keladi. Hammasi `kill_switch_events`, `control_events` va `audit_log`ga yoziladi; kill hodisasi off-host monitor journal’iga ham ko‘zgulanadi.

**Telegram yoki ops DB ishlamasa — darhol SSH (Tailscale orqali, Q58).** Telegram kill bu holatda qabul qilinmaydi; uni kutish yo‘q.

```bash
ssh owner@<AMT tailnet IP>     # faqat Tailscale orqali, owner qurilmasidan
sudo /opt/wolter-amt/current/bin/amt-kill --mode ai_only     # yoki --mode ai_and_ads
sudo /opt/wolter-amt/current/bin/amt-kill --status
```

`amt-kill` — root:root fixed entrypoint (`ssh_kill_path`); owner’ning `amt-kill` uchun alohida sudoers yozuvi (`/etc/sudoers.d/70-owner-kill`: aniq yo‘l va faqat `execution-policy.yaml#kill_cli` argumentlari, F1-AT-27) bor — umumiy sudo (`80-owner`) olib tashlansa ham ishlaydi. Agent yoki builder unga yo‘l ololmaydi; umumiy service user yo‘q. CLI ham xuddi shu `amt-control` latch’iga boradi. Tailscale ishlamasa, lekin owner ofisda bo‘lsa, xuddi shu buyruq lokal konsoldan ishga tushiriladi.

**Server ham javob bermasa** (jumladan ofis interneti uzilganda, Q60): owner yoki vakolatli handback custodian Ads Manager’da AMT managed entity’larni qo‘lda pauza qiladi. Kerak bo‘lsa account spending limit’ni joriy sarfga yaqin qiymatga tushiradi (limit kumulyativ — [budgets.yaml](../09_Config_Templates/budgets.yaml) `cap_update_formula`). Owner OpenRouter dashboard’da runtime kalitni disable qiladi. Bu yo‘l mustaqil monitor/responder checklist’ida va choraklik mashqda (§6) sinaladi.

## 3. Token sizishi

1. Avval kill (A): lokal barrier rotatsiyadan oldin turadi.
2. Owner tegishli kalitlarni revoke/rotate qiladi: Business Manager → System users (`amt-read`, `amt-write`, CAPI), amoCRM integratsiya tokeni, OpenRouter runtime kaliti, BotFather `/revoke` (ops-bot, Hermes CMO bot), GitHub token va deploy key, Langfuse kalitlari, Cloudflare Tunnel tokeni (aylantirish va API orqali barcha mavjud ulanishlarni uzish — aylantirishning o‘zi ishlab turgan connector’ni uzmaydi; [BACKUP_RESTORE §7](BACKUP_RESTORE.md)), Tailscale tugun kaliti, tg-auth sessiyalari. PC yoki disk o‘g‘irlansa — hammasi ([INCIDENTS](INCIDENTS.md) INC-26).
3. Yangi sirlar `secrets/*.sops.yaml` → root renderer → har servis uchun alohida 0600 credential fayl → servis ACK. Inventar va qadamlar: [BACKUP_RESTORE §7](BACKUP_RESTORE.md).
4. B emergency pauzasi executor’ning pause-only yo‘lida qoladi; credential agentga berilmaydi.
5. Trace/log’da sir qolmagani tekshiriladi; compromise qamrovi, PII va rol/sessiya revoke AAR’da. PII tegsa — [INCIDENTS](INCIDENTS.md) INC-18 (`privacy.breach_response`).

## 4. Owner resume

Shartlar: sabab RCA/AAR bilan yopilgan; `uncertain` attempt’lar reconcile qilingan yoki `manual_resolution`da; tracking/freshness; tegishli capability’lar avval o‘z gate’idan o‘tgan (release snapshot’i yoki `control_events`) va amaldagi tasdiqlar kuchda (`operational_validity`; resume gate emas, `max_evidence_age` qayta qo‘llanmaydi); zarur ACK’lar (`incident_acks`, `handback_acks`) bor.

`/resume` — `control_resume` (owner, typed code; binding: pipeline to‘plami, from/to mode, sabab ref, `control_epoch`). Natija `execution-policy.yaml#resume` bo‘yicha:

- har pipeline `min(pre_kill_pipeline_mode, L1_approve_each)`: L0 L0 bo‘lib qoladi, L2 ko‘pi bilan L1. Resume avtonomiyani hech qachon oshirmaydi; L1 dan yuqoriga faqat alohida owner qarori (L2_ENABLE profili, HG-L2-01);
- global `shadow` saqlanadi; `read_only` sababi hal bo‘lmaguncha saqlanadi;
- yangi epoch va tokenlar, joriy policy revision; eski approval yoki item tirilmaydi;
- release qilingan entity avtomatik qaytarilmaydi (`released_entities_require_owner_retakeover: true`, `auto_retakeover_on_resume: false`) — owner `takeover_scope_change` (HG-F6-04) bilan qayta takeover qiladi;
- B’da pauza qilingan reklama o‘zi yoqilmaydi: exact joriy payload/review/offer bilan yangi change set. Hech qachon faol bo‘lmagan entity — `campaign_activate` (faqat owner), oldin faol bo‘lgan campaign yoki ad set — `entity_activate`, faol ad set ichidagi ad — `creative_activate`.

Resume bosqichli monitoring va haqiqiy responder ACK bilan tugaydi; resume hodisasi off-host journal’ga ko‘zgulanadi.

### 4.1 Restore’dan keyin

Restore har doim `killed` bilan boshlanadi (◇ P-16, qattiqroq — amal qiladi). `shadow`+L0 ga o‘tish faqat reconcile tugagach owner qadami bilan. Keyingi resume darajasi: `min(snapshot_mode, off-host control journal’idagi oxirgi mode, L1_approve_each)`. Journal o‘qilmasa barcha pipeline `L0_shadow` qoladi va owner har pipeline’ni alohida ochadi (`/resume <pipeline>`, `control_resume`, sabab `restore`, ko‘pi bilan L1). Restore’dan keyingi qaytish gate emas: `max_evidence_age` qayta qo‘llanmaydi, buning o‘rniga aniq shartlar tekshiriladi — reconcile tugagan, provider spending limit read-back mos, handback custodian va operator ACK (`execution-policy.yaml#restore.preconditions`). To‘liq tartib: [BACKUP_RESTORE §5](BACKUP_RESTORE.md).

### 4.2 Maintenance hold kill emas

Rejali release oynasida `amt-release` `maintenance_hold` qo‘yadi: `global_mode: read_only`, `proxy_admission: paused`, `restore_previous_modes_on_release: true` (`is_kill: false`). Release tugagach `amt-release` `maintenance_release` bilan faqat hold o‘zgartirgan o‘lchovlarni tiklaydi; L2 pasaytirilmaydi; hold paytida yoqilgan kill yoki protective control o‘z chiqish qoidasigacha qoladi (`controls_raised_during_hold_persist`). Owner mavjud bo‘lishi shart (`owner_unavailable_allowed: false`). Oyna ichida incident yoki rollback bo‘lsa yuqoridagi kill/resume qoidalari amal qiladi. Tafsilot: [UPGRADE §2](UPGRADE.md).

## 5. Deterministic kill-criteria va handback

**Q31 ✅:** qualified CPL comparable baseline’dan >25% yomonlashsa va bu ikki hafta ketma-ket kuzatilsa, o‘sha pipeline avtomatik `L0_shadow` ga o‘tadi, boshqaruv odamga qaytadi va C05 RCA ochiladi. Owner F5’da baseline, qualification revision, cohort yetilishi, minimum sample va hisob dalilini tasdiqlaydi (`business.baseline`, `business.acceptance`; accountable owner, dalilni funnel-analyst tayyorlaydi). Bu tasdiq qoidani ixtiyoriy qilmaydi; dalil yetishmasa F5/F6 readiness bloklanadi.

Mexanizm — [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml):

- **KC-01:** metrika `qualified_cpl_event_week` (`amt_ro.v_pipeline_cohorts`), solishtirish `worse_pct_greater_than: 25`, `consecutive_weeks: 2`, min sample `business.acceptance`dan; cohort tasdig‘i ⧗ OD-13. Job Du 07:30 (`operations.yaml` `schedule.kill_criteria`).
- **KC-02:** `lead_to_contract` yomonlashsa `block_auto_increase` + urgent alert (`ALERT_KILL_CRITERIA_GUARDRAIL`); chegara `business.acceptance`da.
- **data_status harakati:** `valid` → baholanadi; `spend_zero_qualified` → exposure va yomon hafta sanaladi; `insufficient_sample`, `not_mature`, `incomparable_baseline` → inconclusive, streak saqlanadi, exposure soati davom etadi; `missing_data`, `stale_data` → blocked + alert; `no_activity`, `no_spend` → baholanmaydi. Denominator nol jim PASS emas.
- **Exposure guard** har sync siklida ishlaydi (`low_data.check_schedule: every_sync_cycle`): sarf bor, qualified nol → scale blok + `ALERT_ZERO_QUALIFIED_EXPOSURE`; maksimal sarf/vaqt `business.exposure`da. Ikki haftani jim kutmaydi.
- **Step vaqti (◇ P-13):** F6 Step 1 dushanba boshlanadi; Step 2 uchun KC-01 ning ikkinchi baholashi bajarilgan bo‘lishi shart; inconclusive → uzaytirish yoki hold, avtomatik o‘tish yo‘q.

| Qadam | Kim/nima | Harakat |
|---|---|---|
| 1 | `sync-worker --job kill-criteria` | qoidalarni pipeline bo‘yicha hisoblaydi → `kill_criteria_evaluations` |
| 2 | kod (LLM emas) → `amt-control` | KC-01 trigger: shu pipeline `L0_shadow` + yangi epoch; boshqa pipeline ta’sirlanmaydi |
| 3 | ops-bot | `ALERT_KILL_CRITERIA` urgent alert va durable outbox: metrika, baseline revision, ketma-ket haftalar |
| 4 | handback custodian (`ops.ads_handback_roster`) | `[Qabul qildim]` → `handback_acks`; Ads Manager’da qo‘lda boshqaruv; `managed_entities.released_at` belgilanadi. ACK kechiksa `ALERT_HANDBACK_ACK_OVERDUE` → deputy → owner |
| 5 | funnel-analyst | C05 RCA (faqat tahlil, qaror emas) |
| 6 | owner | qayta urinish: C05 RCA → `takeover_scope_change` (HG-F6-04, `/takeover <pipeline> <manifest_id>`) → `pipeline_mode_change` ikki bosqich bilan L1 ga (`/mode <pipeline> L1`). Oddiy `/resume` kill-criteria L0 ni ochmaydi (`resume.after_kill_criteria`) |

Alert yetkazilishi human handback emas. LLM faqat RCA yozadi; protective trigger LLM qaroriga bog‘liq emas. Owner yo‘qligida oldindan tasdiqlangan safe state va eskalatsiya bajariladi; owner-only resume, rol va yangi activation delegatsiya qilinmaydi.

## 6. Dalil va drill

| Qachon | Mashq | Dalil |
|---|---|---|
| F3 | F3-AT-15 (A va B, test obyektlarda), F3-AT-25 (kill race, partial remote) — izolyatsiyalangan | `kill_switch_events`, `control_events` |
| F6 Step 1 oldidan (HG-F6-03) | F6-AT-08: `restore_drill` konteynerida fixture’larda, simulyatsiya qilingan Meta endpoint’iga qarshi A/B kill; owner tasdiqlagan PAUSED test entity bilan haqiqiy integratsiya production’da global `shadow` rejimida, F3-AT-05 dagi `origin=test` PAUSED-fixture istisnosi bo‘yicha (production credential’lari, faqat PAUSED test entity), activation simulyatsiya; faqat B kill ishlatadigan pauza chaqiruvi `origin=test` item orqali sinaladi, production kill bajarilmaydi — production `control_epoch` va kill latch o‘zgarmaydi; hech qachon `staging` yoki `restore_drill` da emas; SSH yo‘li — production `amt-kill --self-test`; resume | `build/ops/kill-drills.md`, F6-AT-13 tartib tekshiruvi |
| Choraklik (★; ◇ P-12) | (a) AMT PC’dagi izolyatsiyalangan `restore_drill` konteynerida (alohida host yo‘q, Q55; tarmoq yo‘q) fixture’larda, konteyner ichidagi simulyatsiya qilingan Meta endpoint’iga qarshi to‘liq A/B mashq: race, partial failure, in-flight, DB/Telegram yo‘qligi; production control socket va kill latch konteynerga ulanmaydi, mashqdan oldin va keyin production `control_epoch` va kill latch o‘qiladi va o‘zgarmagan bo‘lishi shart; (b) SSH yo‘li faqat production’da Tailscale orqali SSH bilan rejimni o‘zgartirmaydigan `sudo /opt/wolter-amt/current/bin/amt-kill --self-test` barrier probe bilan isbotlanadi (mashq ichidagi kill bilan emas): entrypoint, sudoers (`70-owner-kill`), latch yo‘li va bot yo‘li ishlayotganini o‘lchaydi | `build/ops/kill-drills.md`; `operations.yaml` `schedule.kill_drill`: har kuni 10:00 muddat tekshiruvi — `recovery.full_drill` dalili P75D bo‘lganda va P83D dan har kuni ops-bot owner’ga eslatadi, owner mashqni P92D ichida belgilaydi va unda ishtirok etadi (technical_operator + owner) |

O‘lchov chegaralari — `ops.kill_targets` (F3_CONTROLLED_TEST): `local_containment_max_ms`, `remote_pause_report_max_s`, `in_flight_report_max_s`. Lokal containment uchun ≤5 s — taklif (⧗ OD-11); qiymat tasdiqlanmaguncha UAT-21 va F6-AT-08 `blocked`, PASS emas. Barcha fault injection izolyatsiyalangan.

Kill log saqlaydi: latch commit vaqti, oldingi global va pipeline holati, eski/yangi epoch, in-flight dispatch, har entity natijasi, outbox yetkazilishi va ACK, resume avtorizatsiyasi. Snapshot vaqti latchdan oldingi bloklashni almashtirmaydi.

## 7. Owner yo‘qligi, deputy va protective controls

Owner vakolati faqat odamga `owner` RBAC roli berilganda o‘tadi (to‘liq owner); yashirin delegatsiya yo‘q. Deputy favqulodda kill — ⧗ OD-04 (variant: `emergency_kill_ai_only` flag, faqat A, ikki bosqich, avtomatik muddat, owner va off-host’ga alert). Qaror bo‘lmaguncha deputy kill qila olmaydi; u ACK, diagnostika va eskalatsiya qiladi. Ads Manager’da oldindan vakolati bor handback custodian AMT’dan tashqarida, inson sifatida, reklamani qo‘lda boshqarishi mumkin.

Inson buyrug‘isiz ishlaydigan himoya nazoratlari ([operations.yaml](../09_Config_Templates/operations.yaml) `protective_controls`):

| ID | Trigger | Effekt |
|---|---|---|
| `protective_pause` (◇ P-21) | managed headroom ≤ safety margin yoki sarf ma’lumoti `budget.ads_pacing` chegarasidan eski | faqat managed entity pause; provider spending limit mustaqil cap bo‘lib qoladi; `ALERT_PROTECTIVE_PAUSE` |
| `proxy_admission_pause` | kalit ≥ `key_noncritical_stop_pct`, agent ulushi ≥ `share_stop_pct` yoki billing reconciliation (Langfuse/usage) `billing_unreliable_noncritical_pause_after_hours` (6 soat ★) dan uzoq yo‘q | yangi non-critical LLM/media admission to‘xtaydi (sinf — `budgets.yaml#openrouter.admission_classes`; boshlang‘ich holatda har LLM/media admission), ishlab turgan rezervlar settle; qaytish `billing_unreliable_resume` bo‘yicha yoki owner `agent_resume`; `ALERT_BUDGET_100` |
| `tracking_read_only` | tracking gate 2 kun ketma-ket fail | global `read_only`, sabab hal bo‘lguncha va owner `/resume`; `ALERT_READ_ONLY` |
| `provider_limit_read_only` | provider spending limit yo‘q yoki API read-back kutilgan qiymatga teng emas | global `read_only`, read-back mos kelguncha va owner `/resume`; `ALERT_SPEND_CAP_HEADROOM` |
| `account_restricted_read_only` | ad account cheklovi, disable yoki abuse signali | global `read_only`, cheklov hal bo‘lguncha va owner `/resume`; avtomatik qayta ochilmaydi; `ALERT_ACCOUNT_RESTRICTED` |
| `kill_criteria_l0` | KC-01 | pipeline `L0_shadow` + handback + C05; `ALERT_KILL_CRITERIA` |
| `maintenance_hold` | rejali release oynasi | §4.2; owner mavjud bo‘lishi shart |

Owner-only (typed code, NEVER_AUTO): `kill_switch`, `control_resume`, `agent_resume`, `global_mode_change`, `pipeline_mode_change`, `takeover_scope_change`, `role_change`, `trust_graduation`, `budget_override`, `protected_surface_change`, `engineering_budget_change` (to‘liq ro‘yxat — `approval-policy.yaml#trust_ramp.never_auto`). `budget_change` owner-only emas: owner yoki ads_approver, L2 gacha.
