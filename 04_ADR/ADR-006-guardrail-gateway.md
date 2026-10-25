# ADR-006 — Agentlar va barcha tashqi tool’lar orasida guardrail-gateway

Holat: Accepted · Qaror egasi: owner (Q08, Q25, Q31, Q32, Q37, Q38, Q40 ✅) + builder ◇ P-01 (±20% formulasi) · Sana: 2026-10-22

## Kontekst

- Paperclip Claude Code agentlarini `--dangerously-skip-permissions` bilan ishga tushiradi [D]: MCP server’lardagi "odamdan so‘ra" izohlari agentni to‘xtatmaydi; agent shell buyrug‘ini bajarishi mumkin.
- amoCRM faktlari (2026-10-22, qayta tekshiriladi): tokenni read-only qilib cheklab bo‘lmaydi; integratsiyaga 7 so‘rov/s; oshsa 429, takroriy buzilishda akkaunt 403 bilan bloklanadi; to‘lanmagan akkauntda (402) yozish darhol to‘xtaydi [D: amoCRM API recommendations].
- Owner talablari: per-agent allowlist, byudjet chegaralari kodda, har yozish → approval → bajarish, amoCRM ≤ 7 so‘rov/s, incremental sync (Q25); 12 soatda javob yo‘q → bekor, avto-tasdiq yo‘q (Q32); kunlik change set va urgent bandlar (Q38).
- Request timeout tashqi natija noma’lumligini bildiradi; uni `failed_confirmed` deb belgilab qayta yuborish takroriy pul harakatiga olib keladi [X].
- Intent qabul qiladigan servis Meta write kalitini ham saqlasa, uning buzilishi to‘g‘ridan-to‘g‘ri write vakolatini beradi [X].

## Qaror

1. `gateway` (`amt-gateway` UID, `127.0.0.1:3300`, MCP over HTTP) — agentlarning tashqi dunyoga yagona yo‘li. Har agentning o‘z bearer tokeni; per-agent allowlist kanonik manbai `approval-policy.yaml#agents`, agent charter’lari unga mos.
2. Siyosat dvigateli `approval-policy`, `budgets`, `capacity-policy`, `kill-criteria`, `tracking-health` va `execution-policy` dan o‘qiydi; limitlar kodda ushlanadi: rolling 24 soat Σ|delta| ≤ 20% (◇ P-01), oylik 150 000 USD minor va admission formulasi ([ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)), integer minor birlik.
3. Gateway’da Meta write kaliti yo‘q: u intent va policy’ni tekshiradi, revision-bound command yozadi; tashqi ijro alohida `amt-executor` da ([ADR-005](ADR-005-meta-read-mcp-write-sdk.md), [ADR-021](ADR-021-durable-execution-custody.md)).
4. Yozish oqimi: `review_required: true` bo‘lgan action avval `pending_review` dan o‘tadi, keyin `pending_approval → approved → claimed → executing → succeeded`. Ops-bot tasdiqni aniq revision uchun vakolatli odamdan oladi (TTL 12 soat `presented_at` dan; qarorlar `approve | reject | edit_decrease | expire`; tahrir faqat sonni kamaytiradi va yangi revision yaratadi). Executor har dispatch, retry va rollback oldidan approval bog‘lanishini qayta tekshiradi (`execution-policy.yaml#approval_binding`, I06).
5. Timeout → `uncertain → reconciling`; `failed_confirmed` faqat tashqi effekt yo‘qligi dalillanganda (I05).
6. Tracking gate: F2 o‘tmaguncha risk oshiruvchi write yopiq; ishga tushgandan keyin 1 fail kun — alert, 2 ketma-ket fail kun — avtomatik `read_only` (Q37).
7. Pipeline rejimlari sale va rent uchun alohida (`L0_shadow`, `L1_approve_each`, `L2_auto_within_guardrails`); KC-01 deterministik `sync-worker` job’i bilan pipeline’ni `L0_shadow` ga o‘tkazadi ([ADR-013](ADR-013-staged-golive-kill-criteria.md)).
8. Yagona xato kodlari enum’i va javob kontrakti `{status: queued|shadow|needs_owner, command_id, revision}` — [GUARDRAIL_GATEWAY](../03_Architecture/GUARDRAIL_GATEWAY.md).
9. amoCRM: barcha chaqiruvchilar uchun umumiy shift `amocrm_global_rps_ceiling: 7` (Q25); `vendor.amocrm_quota` faqat shu shift ichida taqsimlaydi yoki kamaytiradi; yuqoriroq qiymat yangi owner Q talab qiladi. Yoziladigan teglar `AMT:` prefiksli, maydonlar faqat allowlist’da ★.
10. Har chaqiruv `audit_log` ga (agent, tool, redacted parametrlar, natija) va `trace_id` bilan yoziladi.
11. Agentlarning hech biri Meta, amoCRM yoki provider tokenini ko‘rmaydi; har servis credential’i o‘z UID’ida 0600 faylda ([runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml)).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Agentlarni to‘g‘ridan-to‘g‘ri MCP’larga ulash | limit va approval kodda bo‘lmaydi |
| Claude Code permission sozlamalariga tayanish | skip-permissions ularni bekor qiladi |
| Meta write kalitini gateway ichida saqlash | intent va ijro bitta chegarada — gateway buzilsa write vakolati ham ketadi |
| Timeout’dan keyin avtomatik qayta yuborish | takroriy budget yoki activate xavfi |
| "Kunlik ±20%" ni har bitta o‘zgarishga alohida qo‘llash | ketma-ket kichik o‘zgarishlar chegarani aylanib o‘tadi (◇ P-01) |

## Oqibatlar

- **+** Xavfsizlik kafolati agentning niyatiga emas, kodga tayanadi; audit va limit yagona nuqtada.
- **−** Gateway kritik nuqta: u ishlamasa agentlar faqat o‘ylay oladi — bu xavfsiz tomonga yiqilish.
- **−** Gateway va executor adversarial test va mustaqil red team talab qiladi (F3).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Gateway’ni chetlab o‘tish | ≥ 1 insident yoki salbiy test fail | `incident_aar` | WF-E01; red team qayta |
| Yangi tashqi integratsiya | yangi vendor yoki tool so‘rovi | `owner_request` | tool kontrakti, allowlist va ADR |
| Adversarial suite | ≥ 1 test fail | `regression` | release bloklanadi |
| amoCRM bloklanish xavfi | har qanday 403 yoki takroriy 429 | quota-coordinator metrikalari | `vendor.amocrm_quota` qayta taqsimot; INCIDENTS |

## Kanonik implementatsiya

- [GUARDRAIL_GATEWAY](../03_Architecture/GUARDRAIL_GATEWAY.md) — guard tartibi, pul shartnomasi, tool kontraktlari, xato kodlari.
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml), [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml), [tracking-health.yaml](../09_Config_Templates/tracking-health.yaml).
- [DATA_MODEL §6](../03_Architecture/DATA_MODEL.md) — command va attempt sxemasi; [RBAC §2](../03_Architecture/RBAC.md).
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-13, UAT-15, UAT-16; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I02–I06.
