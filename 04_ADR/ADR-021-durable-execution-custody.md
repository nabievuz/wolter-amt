# ADR-021 — Durable custody va tashqi ijro protokoli

Holat: Proposed · Qaror egasi: builder ◇ P-24 (kill latch qismi — P-03) · Sana: 2026-10-23

## Kontekst

- Owner qarorlari: har yozish → approval → bajarish (Q25); 12 soatda javob yo‘q → harakat bekor, avto-tasdiq yo‘q (Q32); kill switch (Q37); doimiy oqimlar deterministik servis (Q26) [D: DECISION_LOG]. Bu ADR ularning ijro mexanizmini taklif qiladi; mexanizm qattiqroq bo‘lgani uchun owner ko‘rib chiqquncha ham amal qiladi.
- Tashqi API timeout’i natijani noma’lum qiladi; vendor bizning fence’ni tanimaydi; allaqachon jo‘natilgan so‘rov keyinroq bajarilishi mumkin [X].
- Landing murojaati CRM’ga yetguncha AMT hosti yoki CRM ishlamasligi mumkin; at-least-once transport bir xabarni takror yetkazadi; ikki worker bir ishni olishi mumkin [X].
- Uch yo‘l ko‘rib chiqilgan: (1) mavjud dizaynni durable holatlar, fault testlari va reconciliation bilan to‘ldirish; (2) butun platformani boshqa orkestrator bilan qayta loyihalash; (3) mavjud targetolog va tashqi servislar bilan doimiy qo‘l boshqaruvi.

## Qaror

1. **Lokal durable custody:** landing shifrlangan submission store (`accepted → crm_pending → crm_confirmed`, noaniq natija `uncertain`, operatsion xato `needs_review`); webhook inbox (commit’dan keyin ACK, original event vaqti va ID saqlanadi); delivery outbox; notification outbox command va audit bilan bitta tranzaksiyada.
2. **Command, attempt va reservation ledger:** revision-bound command; har urinish alohida attempt yozuvi; claim, lease va fence; timeout → `uncertain → reconciling`; `failed_confirmed` faqat tashqi effekt yo‘qligi dalillanganda; zarur qayta urinish yangi attempt orqali (I05, I06).
3. **Qo‘shimcha holat o‘tishlari** (`execution-policy.yaml#extra_transitions`): `claimed → cancelled` (dispatch niyatidan oldin kill yoki revoke; rezerv bo‘shatiladi); `approved|claimed → cancelled` (guard fail, `reason_code` bilan); `awaiting_manual → expired`; `manual_resolution → succeeded|failed_confirmed` (operator dalili bilan); SHADOW item TTL’da `expired`. Kill sababi — `cancelled` + `reason_code: kill`.
4. At-least-once transport biznes idempotency va reconciliation bilan boshqariladi; vendor va DB orasida exactly-once da’vo qilinmaydi (`provider_fencing_assumed: false`).
5. **Kill** lokal durable latch va `control_epoch` dan boshlanadi; snapshot, Paperclip yoki Meta javobi kutilmaydi (◇ P-03, [ADR-030](ADR-030-kill-modes-and-protective-controls.md)).
6. **Platforma:** PostgreSQL va tor servis modullari mavjud qamrov uchun yetarli; Kafka, Kubernetes, ko‘p region yoki tashqi workflow engine majburiy emas. Run va step darajasidagi davom ettirish shu bazadagi `amt-workflow` da ([ADR-024](ADR-024-workflow-runtime-capability-first.md)); command holati workflow holati bilan almashtirilmaydi (I16).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Butun platformani boshqa orkestrator bilan qayta loyihalash | biznes semantikasi, pul va crash muammolari baribir qoladi; yangi migratsiya va xizmat yuki |
| Doimiy qo‘l boshqaruvi (targetolog + tashqi servislar) | avtonom AMT maqsadi bajarilmaydi; faqat tiklanish yoki no-go davri uchun operatsion yo‘l sifatida qoladi |
| Kafka yoki boshqa katta platforma | bitta host va mavjud qamrov uchun ortiqcha ekspluatatsiya yuki |
| Timeout’ni xato deb qayta yuborish | takroriy pul harakati xavfi |
| Paperclip issue holatini ijro truth’i qilish | issue holati tashqi effekt dalili emas (I16) |

## Oqibatlar

- **+** Noaniq natijalar va recovery kuzatiladi; qabul qilingan murojaat jim yo‘qolmaydi; kill tashqi API’ga bog‘liq emas.
- **−** Holat mashinasi va fault testlari puxta implementatsiyani talab qiladi.
- **−** Reconciliation va `manual_resolution` operator vaqtini oladi.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Hal qilinmagan noaniq attempt’lar | `uncertain`/`reconciling` attempt `ops.ack_minutes` muddatidan uzoq ochiq qolsa | `amt-control` metrikalari | INCIDENTS; reconciler tuzatish |
| Accepted ↔ CRM farqi | `accepted_vs_crm_receipts` tekshiruvi fail | tracking-health | INCIDENTS; intake recovery |
| Ledger yuklamasi | queue chuqurligi yoki eng eski yozuv yoshi `ops.resource_envelope` chegarasidan oshsa | OBSERVABILITY (`latency_drift`) | sxema/indeks tuzatish yoki arxitektura ADR’i (WF-E01) |
| Owner qarori | owner bu mexanizmni rad etsa yoki o‘zgartirsa | `owner_request` | yangi ADR |

## Kanonik implementatsiya

- [DATA_MODEL §3, §6, §7](../03_Architecture/DATA_MODEL.md); [GUARDRAIL_GATEWAY §5–§6](../03_Architecture/GUARDRAIL_GATEWAY.md); [TRACKING_CAPI §1, §4–§5](../03_Architecture/TRACKING_CAPI.md).
- [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) — `command_states`, `extra_transitions`, `approval_binding`, `kill_first`.
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-08, UAT-09, UAT-10, UAT-12, UAT-14, UAT-15; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I05–I08.
