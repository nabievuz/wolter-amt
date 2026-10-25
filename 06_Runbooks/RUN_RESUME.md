# RUNBOOK — Workflow run’larini tiklash va davom ettirish

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Qachon: `amt-workflow` yoki host qayta ishga tushdi, controller handover bo‘ldi, restore qilindi yoki run’lar `blocked`/`reconciling`/`manual_resolution` da to‘planib qoldi (`ALERT_WORKFLOW_BLOCKED`, [INCIDENTS](INCIDENTS.md) INC-21/INC-24). Kontrakt: [WORKFLOW_CONTRACT](../11_Production_Contracts/WORKFLOW_CONTRACT.md); dizayn: [WORKFLOW_RUNTIME](../03_Architecture/WORKFLOW_RUNTIME.md). Mas’ul: `technical_operator` (primary/deputy, `ops_responder` flag); kill va resume qarori faqat owner.

## 1. Process restart (host saqlangan)

1. Ops-bot `/status` va `v_owner_queue`: ochiq run soni, `reconciling`, `blocked`, eng eski `waiting_until`.
2. Controller epoch’ini tekshiring: bitta faol controller, eski yozuvlarda `controller_epochs.revoked_at` to‘ldirilgan. Eski epoch’dagi har dispatch rad va auditda (`stale_epoch_dispatch: reject_and_audit`). Ikki faol controller ko‘rinsa — operator darhol owner’ga eskalatsiya qiladi, owner kill A ([KILL_SWITCH](KILL_SWITCH.md)) va incident (WF-O02, INC-24).
3. Muddati o‘tgan lease’lar avtomatik qayta claim qilinadi (fence++); qo‘lda “retry” bosilmaydi.
4. `uncertain` command’lar reconciliation navbatida; step holati `workflow-policy.yaml#command_aggregation` dagi o‘z rolidan olinadi. Dispatch `complete_when` va tartibli qoida bilan tugab, noaniq bandni reconciliation step’iga o‘tkazishi mumkin — bu muvaffaqiyat emas. Run custody’sidagi noaniq band `reconciling`/`manual_resolution`ni saqlaydi. `manual_resolution` faqat durable owner task **va** I18 accepted handoff bilan run’dan tashqariga topshiriladi (`command_aggregation.manual_resolution_handoff`): exact command revision, attempt/evidence, receiver/time, reservation va conflict-lock reference’lari saqlanadi, lock va reservation bo‘shamaydi. Assignment yoki alert qabul emas. Har band remote terminal yoki qabul qilingan custody’da bo‘lgach avval `running` checkpoint’i, keyin odatiy completion tekshiruvi; to‘g‘ridan-to‘g‘ri `completed` va ko‘r-ko‘rona retry yo‘q.
5. O‘tkazib yuborilgan timer’lar bir marta otiladi; natijasi eskirgan bo‘lsa (masalan, approval TTL o‘tgan) command `expired`, step esa `cancelled` bo‘ladi — eski approval tirilmaydi.

## 2. Host yo‘qolishi yoki restore

1. [BACKUP_RESTORE](BACKUP_RESTORE.md) bo‘yicha locked restore: start har doim `killed` (◇ P-16); timer va routine’lar avtomatik ishga tushmaydi. `shadow`+L0 ga faqat reconcile’dan keyin owner qadami bilan.
2. Workflow jadvallari va command ledger bir xil restore nuqtasidan ekanini tekshiring (manifest hash).
3. Remote reconciliation: Meta/CRM/CAPI holatini read-only o‘qing; restore’dan keyin vendor’da bo‘lgan effektlar `uncertain` attempt’larga bog‘lanadi.
4. Landing’dan `submission_delivery` ingest’i: AMT yo‘q paytda qabul qilingan murojaatlar uchun WF-B01 run’lari yaratiladi yoki to‘ldiriladi (dedup `submission_id`).
5. Tracking/freshness gate’lari qayta tekshiriladi; owner resume darajasi `min(snapshot_mode, off-host control journal’idagi oxirgi mode, L1_approve_each)`; journal o‘qilmasa barcha pipeline `L0_shadow` va owner har birini alohida ochadi ([KILL_SWITCH §4.1](KILL_SWITCH.md)).

Global rejim `killed` bo‘lgan paytda `amt-release` faqat `release_class: recovery` release’ni qabul qiladi; harness handover (WF-E02) owner mavjud bo‘lmagan vaqtda boshlanmaydi.

## 3. Bloklangan run’lar

| Belgisi | Harakat |
|---|---|
| Handoff `rejected` sabab kodi bilan | sabab egasiga vazifa; yangi input bilan yangi handoff; eski artifact publish qilinmaydi |
| `waiting_for: approval` va TTL yaqin | ops-bot eslatma; TTL o‘tsa command `expired` — avtomatik tasdiq yo‘q |
| `manual_resolution` | technical_operator vendor dalilini yozadi; yoki owner exact command revision va unresolved dalillarni durable handoff’da qabul qilib, o‘z task’i bilan custody’ni oladi. Runtime accepted receiver/time va reservation/conflict-lock reference’larini tekshiradi; ular saqlanadi, command success bo‘lmaydi. Qabul yo‘q bo‘lsa run ochiq; qabul yoki remote resolution bo‘lsa `running` checkpoint’idan keyin completion yoki vakolatli alohida compensation command |
| Agent pauzada (`share_stop`, `key_noncritical_stop`, `billing_unreliable`, `anomaly`) | agent LLM chaqira olmaydi, `workflow.report_blocker` ham yo‘q; yarim qolgan step’ning command’lari `cancelled` (`step_incomplete`) va taqdim etilmaydi; `review_required` bandlar review TTL’da `expired` (`review_ttl`), avtomatik tasdiq yo‘q; Reviewer pauzada faqat `entity_pause` va `protective_pause` o‘tadi; owner — kerak bo‘lsa `/budget raise <agent> <usd>` (faqat zaxira), keyin `/agent resume <agent>` (typed code); qaytgandan keyin bandlar qayta taklif qilinadi (◇ P-85) |
| Paperclip drift | issue qo‘lda yopilgan yoki o‘zgargan — runtime truth bo‘yicha issue tiklanadi; step tugamaydi |
| Definition pin nomosligi | run eski definition’da qoladi; ko‘chirish faqat WF-E02 orqali; mos bo‘lmagan run WF-E02 disposition’igacha to‘xtatib turiladi |

## 4. Dalil

Har tiklash: vaqt, epoch, ochiq run’lar soni (oldin/keyin), reconciliation natijalari, owner resume ID. Workflow ledger RPO/RTO `workflow.recovery` (FE_RELEASE) bo‘yicha o‘lchanadi; host yo‘qolishi — `recovery.full_datasets` dagi qabul qilingan doira (Q55: ikkala disk yo‘qolsa ledger ham yo‘qoladi; faqat intake (WF-B01) run’lari landing va amoCRM’dan qayta quriladi; boshqa run’lar yo‘qoladi va kerak bo‘lsa yangidan boshlanadi). Natijalar [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) EVO-AT01, EVO-AT07, EVO-AT12 dalili sifatida saqlanadi.
