# ADR-030 — Kill rejimlari, yozuvchi klasslari va himoya nazoratlari

Holat: Accepted · Qaror egasi: owner (Q37 ✅ — kill switch) + builder ★ (kill A/B, tasdiq va resume qoidasi) + builder ◇ P-03, P-12, P-16, P-21 + ⧗ OD-04, OD-11 · Sana: 2026-10-23

## Kontekst

- Q37 ✅ kill switch’ni talab qiladi. ★ standart (H-bo‘lim): kill’ning yagona spetsifikatsiyasi; standart rejim A (faqat AI to‘xtaydi), B (AI + AMT boshqaradigan entity’lar pauza); tasdiq — tugma + `TASDIQ <kod>`; `/resume` har pipeline’ni `min(kill’dan oldingi rejim, L1)` ga qaytaradi, oldingi global `shadow` saqlanadi — avtonomiya hech qachon oshmaydi [D: DECISION_LOG].
- Kill paytida Telegram, DB, Paperclip yoki Meta API ishlamasligi mumkin. Birinchi amal ularga bog‘liq bo‘lsa, aynan insident paytida AI to‘xtamaydi [X] (◇ P-03).
- Executor va proxy’dan tashqari yozuvchilar bor: amoCRM teg/maydon yozuvi, GitHub PR, Telegram outbox, CAPI, landing → CRM yetkazish va release. Ularning kill’dagi xulqi yozilmasa ikki xil implementatsiya "spec bo‘yicha" bo‘lib qoladi: yo kill amoCRM va GitHub yozuvini ochiq qoldiradi, yo CAPI va intake to‘xtab qualified signal hamda murojaatlar yo‘qoladi [X].
- Kill B uchun alohida favqulodda Meta write credential’i yangi hujum yuzasi va Q40 tor operatsiyalaridan tashqaridagi write yo‘li bo‘lardi; Q40 to‘plamida `pause_entity` allaqachon bor [D: [ADR-005](ADR-005-meta-read-mcp-write-sdk.md)].
- Owner javob bermagan paytda ham ayrim himoyalar ishlashi kerak (sarf headroom, tracking, KC-01); lekin owner vakolatini yashirin delegatsiya qilish mumkin emas [X].
- Eskirgan snapshot’dan restore qilish avtonomiyani yoki eski approval’larni tiklab yuborishi mumkin [X] (◇ P-16).

## Qaror

### Kill rejimlari va birinchi amal

1. Owner `/pause_all` da A yoki B ni tanlaydi — tugma + 2 daqiqalik bir martalik typed code (`kill_switch`, NEVER_AUTO, standart rejim A). Telegram kill ops DB va ops inbox’ni talab qiladi; ular yo‘q bo‘lsa yoki Telegram ishlamasa — darhol SSH: `/opt/wolter-amt/current/bin/amt-kill` (`root:root`; owner’ning `amt-kill` uchun alohida sudoers yozuvi (`70-owner-kill`) bor — umumiy sudo olib tashlansa ham ishlaydi).
2. **Birinchi amal (◇ P-03):** `amt-control` durable lokal latch va monoton `control_epoch` ni yozadi; dispatch barrier shu paytdan yangi normal write va LLM/media dispatch’ni rad etadi. Snapshot, Paperclip, Meta, Telegram yoki markaziy DB javobi bundan oldin kutilmaydi. Latch o‘qilmasa — default deny.
3. **Rejim A (standart):** AI dispatch, LLM/media va normal tashqi write’lar to‘xtaydi; reklama provider spending limit ostida davom etishi mumkin ([ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)). **Rejim B:** A + har managed entity’ning to‘liq boshqariladigan eng yuqori darajasi pauza qilinadi (kampaniya to‘liq managed bo‘lsa — kampaniya, aks holda ad set yoki ad); begona parent’larga tegilmaydi; qisman xato `partial_failure` va qolgan entity ro‘yxati bilan ko‘rsatiladi.
4. **Pause yo‘li:** B va `protective_pause` pauzalari `amt-executor` ning pause-only emergency yo‘li orqali bajariladi (chaqiruvchi — `amt-control`): re-read → pause → verify → `protective_actions` yozuvi → urgent alert. Faqat `pause_entity`; activate, budget oshirish va create yo‘q. Yangi credential yoki UID qo‘shilmaydi.
5. **Keyingi amallar** — mustaqil, timeout va partial natija bilan: DB mirror va audit; dispatch qilinmagan command’lar `cancelled` (`reason_code: kill`); in-flight attempt’lar `uncertain`/`reconciling`; Paperclip va worker pauzasi; best-effort snapshot; token rotatsiyasi yoki xotiradan tushirish; natija outbox va off-host monitor’ga (contained_at, epoch, in-flight, B dagi paused/failed/unverified ro‘yxati).

### Yozuvchi klasslari

Kill ostida har yozuvchi klassining xulqi (`execution-policy.yaml#kill_rejects`, `kill_allows`); `shadow`, `read_only` va pipeline `L0` ustunlari bilan to‘liq kanonik jadval — [SECURITY §6](../03_Architecture/SECURITY.md) (`writer_classes_ref`).

| Yozuvchi klassi | `killed` da | Izoh |
|---|---|---|
| `amt-executor` — Meta normal write | rad | `shadow`, `read_only` va L0 da ham rad; `shadow` va L0 SHADOW item yozadi |
| `amt-executor` — `protective_pause` (pause-only yo‘l) | ruxsat | `allowed_global_modes: [shadow, enabled, read_only, killed]`; faqat `managed_entities` doirasida |
| `amt-amo` — teg va maydon yozuvi | rad (epoch tekshiruvi) | |
| gateway — GitHub PR | rad (epoch tekshiruvi) | |
| `llm-proxy` — LLM va media | rad (epoch tekshiruvi) | `write_mode_killed`, retry yo‘q |
| `amt-eng-proxy` — engineering LLM | rad (epoch tekshiruvi) | engineering hisobi ⧗ OD-02 |
| `amt-workflow` — tashqi effektli step | dispatch yo‘q | run’lar durable holatda kutadi ([WORKFLOW_RUNTIME](../03_Architecture/WORKFLOW_RUNTIME.md)) |
| `ops-bot` — Telegram outbox, bildirishnoma, ACK | ruxsat | deterministik issiq yo‘l ([ADR-007](ADR-007-deterministic-hot-paths.md)) |
| `capi-bridge` — CAPI yetkazish | ruxsat | |
| landing → CRM yetkazish | ruxsat | |
| `amt-release` | faqat `recovery` sinfidagi release | `release-policy.yaml#release_classes`: `normal` — `killed` da rad; `recovery` — faqat containment, reconciliation yoki oldin tekshirilgan release’ni tiklaydi |

### Himoya nazoratlari katalogi

`operations.yaml#protective_controls` — owner javob bermaganda ham ishlaydigan deterministik nazoratlar (◇ P-21 `protective_pause` uchun):

| ID | Trigger | Chaqiruvchi | Owner yo‘qligida | Ta’sir |
|---|---|---|---|---|
| `protective_pause` | managed headroom ≤ safety margin yoki managed entity faol paytda spend ma’lumoti `budget.ads_pacing` cutoff’idan eski | `amt-control` (spend pacer `amt-sync` da so‘raydi) | ha | faqat managed entity, faqat pause; provider limit mustaqil cap bo‘lib qoladi |
| `proxy_admission_pause` | kalit sarfi ≥ `key_noncritical_stop_pct`, agent ulushi ≥ `share_stop_pct` yoki billing reconciliation `billing_unreliable_noncritical_pause_after_hours` (★ 6 soat) dan uzoq mavjud emas | `cost-watchdog` → `amt-control` | ha | yangi muhim bo‘lmagan LLM/media admission to‘xtaydi; ishlayotgan rezervlar settle bo‘ladi; qayta ochish — `billing_unreliable_resume` yoki owner `agent_resume` |
| `tracking_read_only` | tracking gate 2 ketma-ket kun fail | `sync-worker` → `amt-control` | ha | global `read_only` — sabab hal bo‘lguncha va owner `/resume` gacha |
| `provider_limit_read_only` | provider spending limit yo‘q yoki API read-back kutilgan qiymatga teng emas (`vendor.meta_cap`) | `sync-worker` → `amt-control` | ha | global `read_only` — read-back mos kelguncha va owner `/resume` gacha |
| `account_restricted_read_only` | ad account cheklovi, disable yoki abuse signali | `sync-worker` → `amt-control` | ha | global `read_only` — cheklov hal bo‘lguncha va owner `/resume` gacha; avtomatik qayta ochilmaydi |
| `kill_criteria_l0` | KC-01 | `sync-worker` → `amt-control` | ha | pipeline `L0_shadow` + human handback + C05 |
| `maintenance_hold` | rejalangan release oynasi | `amt-release` | yo‘q | `execution-policy.yaml#maintenance_hold` |

Faqat owner (typed code, NEVER_AUTO): `kill_switch`, `control_resume`, `agent_resume` va barcha owner `*_change` action’lari (`pipeline_mode_change`, `takeover_scope_change`, `role_change` va boshqalar).

### Owner vakolati va o‘rinbosar

6. Owner vakolati faqat odamga `owner` RBAC roli berilganda o‘tadi; yashirin delegatsiya yo‘q ([ADR-018](ADR-018-rbac-registry.md)). O‘rinbosar yoki technical_operator `ops_responder` flag’i bilan ACK, read-only diagnostika va eskalatsiya qiladi.
7. O‘rinbosarning favqulodda kill vakolati — ⧗ OD-04 (ko‘rib chiqiladigan variant: `emergency_kill_ai_only` flag’i, faqat A rejim, ikki bosqich, avtomatik muddat, owner va off-host alert). OD-04 hal bo‘lguncha o‘rinbosar kill qila olmaydi.

### Resume

8. Global kill’dan keyin `/resume` — owner `control_resume` (typed code, yangi epoch): har pipeline `min(pre_kill_pipeline_mode, L1_approve_each)`; global `shadow` saqlanadi; `read_only` sababi hal bo‘lguncha saqlanadi; eski approval’lar tirilmaydi; inson qaytarib olgan entity faqat owner qayta takeover qilganda ochiladi (`released_entities_require_owner_retakeover: true`, `auto_retakeover_on_resume: false`).
9. KC-01 dan keyin pipeline C05 RCA, owner `takeover_scope_change` (HG-F6-04) va owner `pipeline_mode_change` (L1 ga) bo‘lmaguncha `L0_shadow` da qoladi.

### Restore

10. Restore har doim `killed` bilan boshlanadi (◇ P-16); `shadow` + L0 faqat reconcile tugagach owner qadami bilan. Resume darajasi — `min(snapshot_mode, off-host control journal’dagi oxirgi rejim, L1_approve_each)`; journal mavjud bo‘lmasa barcha pipeline `L0_shadow` va owner har birini alohida ochadi. Kill, rejim o‘zgarishi, rol bekor qilinishi va resume hodisalari off-host monitor journal’iga ko‘zgulanadi.

### Maintenance hold

11. Maintenance hold kill emas: `{global_mode: read_only, proxy_admission: paused, restore_previous_modes_on_release: true}`; `maintenance_release` faqat hold o‘zgartirgan o‘lchovlarni tiklaydi, hold paytida yoqilgan kill va himoya nazoratlari o‘z chiqish qoidasigacha qoladi (`execution-policy.yaml#maintenance_hold`, `mode_causes`); L2 pasaytirilmaydi. Insident yoki rollback esa kill va resume qoidalari bilan boshqariladi.

### Maqsadlar va mashq

12. Kill vaqt maqsadlari `ops.kill_targets` (F3_CONTROLLED_TEST, owner): `local_containment_max_ms`, `remote_pause_report_max_s`, `in_flight_report_max_s`. Lokal containment ≤ 5 s — ◇ taklif qilingan standart; qiymat ⧗ OD-11 da owner tomonidan tasdiqlanadi. UAT-21 va F6-AT-08 shu kalitga bog‘lanadi.
13. Choraklik mashq: izolyatsiyalangan to‘liq A/B mashqi + production’da rejim o‘zgartirmaydigan `amt-kill --self-test` barrier probe (◇ P-12; ★ "kill switch testi choragiga"). Natija F6 Step 1 dan oldin HG-F6-03 da ham talab qilinadi.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Kill avval snapshot, Paperclip yoki Meta javobini kutadi | tashqi API ishlamasa AI to‘xtamaydi |
| B uchun alohida favqulodda executor va credential | yangi Meta write yo‘li va credential custody; Q40 tor operatsiyalaridan tashqari |
| Kill barcha yozuvchini to‘xtatadi (CAPI, intake, ACK ham) | qualified signal va murojaatlar yo‘qoladi; owner xabar ololmaydi |
| Kill faqat executor va proxy’ni to‘xtatadi | amoCRM va GitHub yozuvi kill’dan keyin ham davom etadi |
| Begona kampaniyalarni ham pauza qilish | AMT vakolatidan tashqari |
| O‘rinbosarga yashirin owner vakolati | owner nazoratisiz pul va vakolat |
| Restore snapshot’dagi rejimni tiklaydi | eskirgan avtonomiya va approval’lar qaytadi |
| Maintenance hold’ni kill sifatida bajarish | pipeline va L2 holatlari keraksiz pasayadi; owner har birini qayta ochishi kerak bo‘ladi |

## Oqibatlar

- **+** Kill tashqi tizimlarga bog‘liq emas; har yozuvchi klassining xulqi aniq va testlanadi.
- **+** Intake, CAPI va ogohlantirishlar kill paytida ham ishlaydi; owner javob bermasa ham avtomatik himoyalar ishlaydi.
- **−** `amt-executor` kill paytida Meta credential’ini pause-only yo‘l uchun ushlab turadi; token sizsa rotatsiya ([KILL_SWITCH](../06_Runbooks/KILL_SWITCH.md) §3).
- **−** OD-04 hal bo‘lguncha owner yo‘q paytda faqat avtomatik himoyalar ishlaydi; o‘rinbosar kill qila olmaydi.
- **−** Choraklik mashq va self-test operator vaqtini oladi.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Kill maqsadi buzilishi | mashqda `local_containment_max_ms` yoki `remote_pause_report_max_s` oshsa | kill mashqi dalili | RCA; WF-E01 |
| B dagi qisman xato | ≥ 1 entity pauza qilinmasa yoki tasdiqlanmasa | kill natijasi, `protective_actions` | INCIDENTS; human handback |
| Owner yo‘qligidagi insident | owner javob bermagan paytda zarar ko‘rilgan insident | `incident_aar` | ⧗ OD-04 owner’ga ustuvor |
| Telegram kill yo‘li | mashqda SSH yo‘liga o‘tish kerak bo‘lsa | kill mashqi | runbook yangilanadi |
| Owner qarorlari | P-03, P-12, P-16, P-21, OD-04 yoki OD-11 bo‘yicha qaror | `owner_request` | holat yangilanadi |

## Kanonik implementatsiya

- [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) — `kill_first`, `kill_modes`, `kill_rejects`, `kill_allows`, `ssh_kill_path`, `resume`, `restore`, `maintenance_hold`; [release-policy.yaml](../09_Config_Templates/release-policy.yaml) — `release_classes`, `kill_interaction`.
- [operations.yaml](../09_Config_Templates/operations.yaml) — `protective_controls`, `owner_authority_transfer`, `deputy_emergency_kill`, `schedule.kill_drill`.
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `kill_switch`, `control_resume`, `pipeline_mode_change`, `takeover_scope_change`, `protective_pause`.
- [SECURITY §6–§8](../03_Architecture/SECURITY.md), [KILL_SWITCH](../06_Runbooks/KILL_SWITCH.md), [BACKUP_RESTORE](../06_Runbooks/BACKUP_RESTORE.md).
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `ops.kill_targets`, `ops.escalation`, `ops.independent_monitor`; [PHASES §4](../05_Build_Phases/PHASES.md) — HG-F6-03, HG-F6-04.
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-14, UAT-21, UAT-22, UAT-24; [F6_GoLive](../05_Build_Phases/F6_GoLive.md) — F6-AT-08; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I07.
