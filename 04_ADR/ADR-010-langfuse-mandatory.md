# ADR-010 — Langfuse: self-hosted, majburiy kuzatuv

Holat: Accepted · Qaror egasi: owner (Q48 ✅) + builder ★ (Q48★, Q44★, Langfuse standartlari) · Sana: 2026-10-22

## Kontekst

- Owner Langfuse’ni qat’iy talab qilgan va MVP’ni rad etgan (Q48); ★ Langfuse self-hosted, OpenRouter Broadcast → Langfuse, Claude Code OTel → Langfuse (Q48★) [D: DECISION_LOG].
- Paperclip OpenRouter sarfini $0 yozadi ([ADR-003](ADR-003-openrouter-single-key-watchdog.md)) — har agent sarfining tashqi tekshiruvi kerak.
- OpenRouter’da Broadcast funksiyasi trace’larni Langfuse’ga yuboradi [D: openrouter.ai/docs/guides/features/broadcast/langfuse · qayta tekshiriladi]. Claude Code OTel eksportining Langfuse OTLP endpoint’iga mosligi tekshirilmagan [?].
- Trace ingest kechikishi mumkin; pul limiti telemetriyaga bog‘lansa kech ushlanadi [X].
- Langfuse steki (ClickHouse, MinIO, Redis, PostgreSQL) RAM va disk talab qiladi; AMT PC’da (64 GB RAM) yetishi taxmin [T].

## Qaror

1. **Langfuse 3.x** self-hosted, AMT PC’da compose stack: web, worker, ClickHouse, Redis, MinIO va ★ o‘z PostgreSQL’i (host `postgres` bilan bog‘lanmaydi); UID `langfuse`, faqat `127.0.0.1:3000`.
2. UI — ★ `mar3.wolter.uz`, tg-auth ortida. Istisno faqat `/api/public/*` (ingest), Langfuse API kaliti bilan himoyalangan.
3. Ma’lumot manbalari: (a) `llm-proxy` — barcha agent va Hermes LLM/media chaqiruvlari, token egasidan attributsiya va metadata bilan; (b) OpenRouter Broadcast — proxy orqali o‘tgan chaqiruvlar; (c) Claude Code OTel → proxy relay → Langfuse — tool span’lari uchun, moslik tasdiqlansa (ixtiyoriy); (d) gateway har tool chaqiruvini `trace_id` bilan Langfuse’ga va `audit_log` ga yozadi. Agentlarda Langfuse kaliti yo‘q.
4. Trace, billing va audit — alohida dalil turlari: pul limiti proxy ledger’ida ushlanadi (ADR-003, [ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)); Langfuse — mustaqil solishtiruv va tahlil manbai.
5. Trace va loglarda PII yoki sir yo‘q ([ADR-008](ADR-008-pii-minimization.md)); bu PII probe testi bilan tekshiriladi.
6. Trace yo‘qligi alert: agent ishlayapti, lekin ★ 30 daqiqa ichida unga oid trace kelmasa ops-bot alert yuboradi. Langfuse yoki usage reconciliation mavjud bo‘lmasa ★ 6 soat chegarasi qo‘llanadi (`budgets.yaml#openrouter.billing_unreliable_noncritical_pause_after_hours: 6`): undan keyin billing ishonchsiz hisoblanadi va muhim bo‘lmagan agentlar `proxy_admission_pause` bilan to‘xtaydi; reconciliation isbotlangach avtomatik qayta ochiladi, oy chegarasidagi pauzalar esa owner `agent_resume` ni talab qiladi (`billing_unreliable_resume`). Tafsilot — [OBSERVABILITY](../03_Architecture/OBSERVABILITY.md).
7. ★ Trace’lar 180 kun saqlanadi; backup qamrovi butun stack (ClickHouse, MinIO, PostgreSQL) va artefaktlar; tanlangan exporter yo‘li test bilan tasdiqlanadi.
8. Foydalanuvchilar: `cost-watchdog` (sarf), Funnel Analyst (agentlar samaradorligi), eval runner va C12 retro.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Langfuse’siz, faqat Paperclip log’lari | owner rad etgan (Q48) |
| Opik | owner Langfuse’ni tanlagan |
| Langfuse Cloud | self-hosted tamoyiliga zid; PII xavfi |
| Pul limitini Langfuse ma’lumotiga bog‘lash | ingest kechiksa limit kech ushlanadi |

## Oqibatlar

- **+** Har agentning sarfi, sifati, latency’si va xatolari ko‘rinadi; eval va retro uchun yagona manba.
- **−** Og‘ir stek: ClickHouse va MinIO RAM va disk talab qiladi ([ADR-032](ADR-032-owner-pc-office-host.md) resurs konverti); shu RAID1’dagi lokal snapshot hajmi oshadi.
- **−** Qo‘shimcha UI ochiq turadi (tg-auth ortida).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Resurs iste’moli | Langfuse’ning resurs iste’moli serverning ★ 30% idan oshsa | OBSERVABILITY resurs konverti (`ops.resource_envelope`) | ADR qayta ko‘riladi: retention yoki sampling, stack sozlamasi yoki Langfuse joylashuvi (owner qarori) |
| Integratsiya buzilishi | Broadcast yoki OTel trace’lari kelmasligi takrorlansa | `regression` (WF-E03) | adapter yoki versiya tuzatish |
| Uzoq uzilish | ★ 6 soat chegarasi oshgan insident | INCIDENTS (`incident_aar`) | RCA; kuzatuv arxitekturasi qayta ko‘riladi |

## Kanonik implementatsiya

- [OBSERVABILITY §1–§3, §6](../03_Architecture/OBSERVABILITY.md) — dalil ierarxiyasi, Langfuse, LLM/media nazorati, dependency matritsasi.
- [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) — `langfuse`, `llm-proxy`; [budgets.yaml](../09_Config_Templates/budgets.yaml) — `openrouter.billing_unreliable_noncritical_pause_after_hours`, `billing_unreliable_resume`; [operations.yaml](../09_Config_Templates/operations.yaml) — `protective_controls.proxy_admission_pause`.
- [BACKUP_RESTORE](../06_Runbooks/BACKUP_RESTORE.md), [INCIDENTS](../06_Runbooks/INCIDENTS.md).
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-20.
