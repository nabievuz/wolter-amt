# ADR-007 — Issiq yo‘llarda faqat deterministik kod, LLM yo‘q

Holat: Accepted · Qaror egasi: owner (Q26, Q37, Q38, Q39, Q47, Q49 ✅; workflow va release yo‘llarida Q50 ✅ qamrovi) · Sana: 2026-10-22

## Kontekst

- Q26: doimiy oqimlar (CAPI, webhook, UTM yozish) — deterministik servis, agent emas [D: DECISION_LOG].
- Ba’zi oqimlar har hodisada ishlaydi va xato narxi yuqori: CAPI event’i `event_time` dan 7 kun ichida yuborilmasa butun batch rad etiladi [D: Meta CAPI docs · qayta tekshiriladi]; tasdiq tugmalari, 2FA, alertlar va kill ham shunday.
- LLM bu yerda uchta muammo keltiradi: noaniqlik, token narxi va prompt injection. Tasdiq LLM orqali o‘tsa, uni matn bilan manipulyatsiya qilish mumkin [X].
- Workflow reyestri va self-evolution (Q50 ✅ qamrov) bosqich o‘tishi, durable timer, handoff qabuli, verification verdict’i va release’ni qo‘shadi. Ularni CMO yoki engineering agenti boshqarsa, holat agent xotirasiga bog‘lanadi va Q26 buziladi [X].

## Qaror

Quyidagilar **faqat deterministik kod**:

| Oqim | Komponent |
|---|---|
| Landing submission custody, accepted → CRM yetkazish va reconciliation | landing server kodi, `sync-worker` |
| UTM, `fbc`, `fbp`, `event_id` yig‘ish va CRM maydonlariga yozish | landing server kodi |
| amoCRM webhook inbox → Meta CAPI (`Lead`, `QualifiedLead`) | `capi-bridge` |
| Change set, ✅/❌/✏️ callback, TTL/expiry, typed-code ikki bosqich | `ops-bot` |
| Rol va approval tekshiruvi, revision binding, dispatch barrier | `gateway`, `amt-executor`, `amt-control` |
| Pul rezervi, admission, headroom, spend pacer, protective controls | `llm-proxy`, `gateway`, `sync-worker`, `amt-control` |
| Tracking health, freshness, sync, kill criteria (KC-01/KC-02), exposure guard | `sync-worker` |
| Alert, ACK, eskalatsiya, mustaqil signal | `ops-bot`, `amt-control`, off-host monitor |
| 2FA va sessiyalar | `tg-auth` |
| Per-agent sarf nazorati va agent pauzasi | `cost-watchdog` → `amt-control` |
| Kill, resume, restore boshlanishi, maintenance hold | `amt-control`, `amt-kill`, `amt-release` |
| Workflow step o‘tishi, durable timer, signal dedup, handoff sxema/freshness/vakolat tekshiruvi, lease va controller epoch fence | `amt-workflow` |
| Candidate manifest tasnifi, verification verdict’i, release approval bog‘lanishi, promotion va publish | `amt-verify`, `amt-release` |

- Agentlar bu oqimlarni kuzatadi va tahlil qiladi (masalan, Analyst health check va EMQ trendlarini o‘qiydi). Workflow’da agent faqat o‘ziga berilgan step’ni bajaradi va artefakt beradi; o‘tishni, handoff qabulini, verdict’ni yoki promotion’ni o‘zi belgilamaydi (I16–I22).
- LLM fallback qo‘shilmaydi. Model yoki provider outage’ida mavjud reklama provider spending limit ostida ([ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)), intake esa durable yo‘lda ([ADR-021](ADR-021-durable-execution-custody.md)) davom etadi.
- Bu kodni o‘zgartirish faqat PR orqali va kamida B sinfi gate’lari bilan (mustaqil verification + owner release); kill/control, release controller, verify, budget va policy sirtlari E sinfi (`evolution-policy.yaml#protected_surfaces`, typed code + mustaqil inson review + owner).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| CAPI’ni agent yuboradi | ishonchsiz va qimmat; 7 kunlik oyna buzilishi mumkin |
| Tayyor amoCRM→CAPI widget’i (SENZIB va boshqalar) | uchinchi tomon, nazorati kamroq; owner tez boshlash variantini tanlamagan (Q26) |
| Hermes yoki boshqa LLM orqali tasdiq | injection xavfi (Q47) |
| Workflow bosqichlarini CMO yoki `eng-planner` boshqaradi | holat agent xotirasiga bog‘lanadi; Q26 ga zid |
| Hermes cron yoki Paperclip routine’ni timer truth qilish | restart va catch-up kafolati isbotlanmagan ([ADR-024](ADR-024-workflow-runtime-capability-first.md)) |

## Oqibatlar

- **+** Ishonchli, arzon va sinaladi; injection bilan tasdiq, bosqich o‘tishi yoki release’ni o‘zgartirib bo‘lmaydi.
- **−** Ko‘proq kod yozish kerak; testlari F1–F3 va FE acceptance’ga kiradi.
- **−** Deterministik servisdagi xato yashirilmaydi: RCA va kod tuzatish talab qiladi.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Deterministik servisda takroriy xato | bir xil sabab bilan ikkinchi insident | `incident_aar` | C05 RCA → WF-E01 tuzatish; LLM’ga o‘tkazilmaydi |
| Yangi doimiy oqim | hodisaga bog‘langan yangi integratsiya yoki workflow | `owner_request` | jadvalga qo‘shiladi; ADR yangilanadi |
| Agent bosqich, qabul yoki release’ga ta’sir qilgani | ≥ 1 audit topilmasi | `incident_aar` | I16–I22 buzilishi sifatida release bloklanadi |

## Kanonik implementatsiya

- [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I07, I08, I16–I22.
- [ARCHITECTURE §2](../03_Architecture/ARCHITECTURE.md), [TRACKING_CAPI](../03_Architecture/TRACKING_CAPI.md), [WORKFLOW_RUNTIME](../03_Architecture/WORKFLOW_RUNTIME.md), [SELF_EVOLUTION](../03_Architecture/SELF_EVOLUTION.md).
- [workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml), [evolution-policy.yaml](../09_Config_Templates/evolution-policy.yaml) — `change_classes`, `protected_surfaces`, `separation_of_duties`.
- [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml), [operations.yaml](../09_Config_Templates/operations.yaml) — `protective_controls`.
- [ADR-024](ADR-024-workflow-runtime-capability-first.md), [ADR-026](ADR-026-independent-verification-custody.md), [ADR-027](ADR-027-release-controller-and-harness-handover.md), [ADR-030](ADR-030-kill-modes-and-protective-controls.md).
