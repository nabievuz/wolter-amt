# ADR-003 — OpenRouter: bitta kalit, qattiq oylik limit, llm-proxy va cost-watchdog

Holat: Accepted · Qaror egasi: owner (Q10/Q33/Q44.1 ✅) + builder ★ (Q44★, watchdog standartlari, build eval ≤ 40%) · Sana: 2026-10-22

## Kontekst

- Owner runtime’ni to‘liq OpenRouter orqali tanlagan: bitta kalit, LLM va rasm/video uchun birga USD 150/oy (15 000 USD minor) qattiq limit; Claude Max 20x faqat tizimni qurish uchun (Q10/Q33/Q44.1, Q23) [D: DECISION_LOG].
- 2026-10-22 holatidagi vendor faktlari ([RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) da claim; build kuni qayta tekshiriladi):
  - kalitga `limit` qo‘yiladi; limit tugasa so‘rov provayderga yetmasdan 403 qaytadi (`limit_source: openrouter_key_limit`); 402 — akkauntda kredit yetarli emas [D: OpenRouter docs · qayta tekshiriladi];
  - `limit_reset` uchun kunlik qiymat hujjatlashtirilgan, oylik faqat eslatilgan [?] — haqiqiy reset va hisob oynasi `vendor.openrouter_period` da o‘lchanadi;
  - kredit sotib olishda platform fee (Standard 5.5%), kreditlar taxminan 1 yildan keyin yo‘qolishi mumkin [D: openrouter.ai/pricing · qayta tekshiriladi] — `budget.tco` ga kiradi;
  - Paperclip `claude_local` OpenRouter-billed run’larni `ANTHROPIC_API_KEY=""` sababli "subscription" deb $0 yozadi, ya’ni Paperclip budget’lari bu sarfni cheklamaydi [D: `resolveClaudeBillingType()`];
  - Claude Code + OpenRouter faqat Anthropic first-party provayder bilan kafolatlanadi [D: OpenRouter Claude Code guide]; akkaunt darajasidagi ZDR Anthropic 1P endpoint’larini olib tashlaydi va videoni bloklaydi [D];
  - Claude Code va Hermes har so‘rovga `provider` siyosati va attributsiya maydonlarini o‘zi qo‘shmaydi [X: RESEARCH_FACTS] — oraliq proxy kerak.
- Kalit agent yoki Hermes muhitida bo‘lsa, agent media endpoint’lariga to‘g‘ridan-to‘g‘ri chiqib budget va kill’ni chetlab o‘tadi va o‘z atributsiyasini soxtalashtiradi [X].
- Agent SDK’lari rad javobini qayta urinib loop yaratishi mumkin [X] — proxy xatolari retry qilinmaydigan bo‘lishi kerak.

## Qaror

1. Bitta OpenRouter runtime kaliti; qattiq limit `budgets.yaml#openrouter.key_hard_cap_minor: 15000` (USD 150/oy = 15 000 USD minor). Limitni faqat Q10 ni o‘zgartiruvchi yangi owner Q o‘zgartiradi.
2. Kalit faqat `llm-proxy` (`amt-proxy` UID) credential faylida. Agentlar, Hermes va boshqa servislarda provider kaliti yo‘q (`provider_keys_on_agents: false`); har agent faqat o‘z proxy tokeniga ega ([ADR-022](ADR-022-isolated-managed-runners.md)).
3. Provider siyosati proxy’da majburlanadi (Q44★, `budgets.yaml#openrouter.provider_policy`): Claude so‘rovlari faqat Anthropic 1P provayderiga (`provider.order: ["anthropic"]`, `allow_fallbacks: false` — ✅ Q44.3: zaxira yo‘l yo‘q; bitta provayder bo‘lgani uchun prompt cache prefiksi ham doim o‘sha provayderda); boshqa model oilasi `models.assignments`da pin qilingan provayderga, xuddi shunday fallback’siz; `cache_control` o‘zgarmasdan uzatiladi; reservation hech qachon cache-read narxida hisoblanmaydi — upper bound so‘rov to‘lashi mumkin bo‘lgan eng yuqori input narxi bilan: `cache_control` bo‘lmasa asosiy narx, 5 daqiqalik TTL’da 1,25×, 1 soatlik yoki noma’lum TTL’da 2× (VR-43); settlement haqiqiy narx bilan, yuqoriga yaxlitlanadi; F1-AT-29 `cache_effective` faqat xarajat modeliga kiradi (◇ P-82, P-86, P-99); har so‘rovda `provider.data_collection: "deny"`; akkaunt darajasidagi ZDR yoqilmaydi; zaxira qatlam — owner akkauntda data collection’ni o‘chiradi (HG-F1-03). Attributsiya token egasidan (`user` = agent slug, run va issue ID) — agent uni soxtalashtira olmaydi.
4. Pul hisobi proxy’da: har so‘rov uchun atomik actual+reserved hisob (`reservation_required: true`); narxi noma’lum yoki noaniq so‘rov rezervni reconcile’gacha ushlaydi (`unknown_cost_behavior: retain_reservation_until_reconciled`). Upper bound ulushga moslab o‘lchanadi (`openrouter.reservation_sizing`, ◇ P-86): bitta so‘rov ≤ rolning `max_cost_minor`, rolning barcha ochiq hold’lari (`max_concurrency × upper_bound_minor`) ulushning 80–100% oralig‘iga sig‘adi; `uncertain` so‘rov slot’ini ushlaydi va OpenRouter generation yozuvi bilan settle bo‘ladi. Limit nazorati Langfuse telemetriyasini kutmaydi ([ADR-010](ADR-010-langfuse-mandatory.md), [ADR-029](ADR-029-money-model-minor-units-and-independent-cap.md)).
5. Ulushlar `openrouter.shares_minor` (yig‘indisi 15 000): creative-studio 3500, cmo 2000, funnel-analyst 1500, media-buyer 1500, cro 1000, reviewer 500, media_generation 4000, reserve 1000. CMO ulushi `sub_shares.cmo` bilan `chat` va `workflow` qismlariga bo‘linadi (ulush yig‘indisi o‘zgarmaydi, bo‘linish qiymati owner’niki, ◇ P-89). `reserve` oldindan tayinlanmaydi; uni faqat owner `budget_override` (`/budget raise <agent_slug|media_generation> <whole_usd>`, `extra_minor = whole_usd * 100`, typed-code ikki bosqich) kalit limiti ichida qayta taqsimlaydi; reklama cap’iga tegmaydi.
6. Nazorat qoidalari ★: ulush 80% — alert; ulush 100%, kalit 90% yoki billing reconciliation (Langfuse/usage) ★ 6 soatdan uzoq mavjud bo‘lmasa (`billing_unreliable_noncritical_pause_after_hours: 6`) — `proxy_admission_pause` (muhim bo‘lmagan yangi LLM/media admission to‘xtaydi, ishlayotgan rezervlar settle bo‘ladi; «muhim bo‘lmagan» sinfi `budgets.yaml#openrouter.admission_classes`, boshlang‘ich holatda har admission, ◇ P-84). `cost-watchdog` (`amt-watchdog`, ★ har 10 daqiqa) proxy ledger’i, `provider_usage_snapshots` (yozuvchi `amt-proxy`) va Langfuse’ni solishtiradi; agent pauzasini `amt-control` orqali `agent_runtime_state` ga yozadi (o‘quvchilar — gateway va proxy); Paperclip pause faqat qo‘shimcha signal. Billing ishonchsizligi pauzasi reconciliation isbotlangach avtomatik ochiladi (`billing_unreliable_resume`); ulush, kalit yoki oy chegarasi pauzasidagi agent faqat owner `agent_resume` (typed code, NEVER_AUTO) bilan qayta yoqiladi (`resume_after_reset_requires_owner: true`).
7. Proxy xato kontrakti — agent uchun retry qilinmaydi: `agent_paused` (HTTP 423), `allowance_exhausted` (OpenRouter 402 va `limit_source`li 403 ham), `price_unknown`, `write_mode_killed` (HTTP 423, lokal kill latch); upstream 408/429/5xx/timeout, ulanish xatosi va qabul qilingandan keyingi xato (HTTP 200 + `error`, SSE `error`) — `upstream_unavailable` (HTTP 424, proxy qayta urinmaydi, zaxira yo‘l yo‘q — ✅ Q44.3; qayta urinish faqat step chegarasi ichida); guardrail yoki moderation 403 va boshqa upstream 4xx — `upstream_refused` (HTTP 422, qayta urinilmaydi); rol slot’lari band bo‘lsa — `slot_wait_exceeded` (HTTP 423, navbat adapter timeout’idan oldin tugaydi; ◇ P-86); input `max_input_tokens`dan oshsa — `input_over_bound` (HTTP 413, yuborilmaydi; ◇ P-88). Pinned adapterlar o‘z retry’isiz (`max_retries: 0`) ishlaydi va proxy upstream muddati ularning eng kichik timeout’idan qisqa (◇ P-97, VR-41, VR-42). Kanonik jadval — [GUARDRAIL_GATEWAY §10](../03_Architecture/GUARDRAIL_GATEWAY.md).
8. Media (`/images`, `/videos`) faqat gateway `media.*` tool’lari orqali, gateway servis tokeni bilan; agent tokenlari bu endpoint’larga kira olmaydi. `media_generation.enabled: false` — `budget.media` yopilguncha.
9. Claude Code muhiti: `ANTHROPIC_BASE_URL` — lokal proxy `/anthropic`; `ANTHROPIC_AUTH_TOKEN` — per-agent proxy tokeni; `ANTHROPIC_API_KEY=""`; model alias’lari aniq OpenRouter ID’lariga bog‘lanadi. Hermes proxy’ning `/openai` yo‘lidan foydalanadi ([ADR-004](ADR-004-hermes-cmo-no-openclaw.md)).
10. ★ Build davridagi AT/eval/shadow sarfi oylik kalit limitining 40% idan oshmaydi (`build_eval_max_pct: 40`); oshsa HG-F4-04 variantlari faqat uchta: eval/shadow’ni ikki oyga bo‘lish, eval qamrovini kamaytirish yoki Q10 ni o‘zgartiruvchi yangi owner Q.
11. Engineering LLM sarfi bu kalitdan va bu limitdan foydalanmaydi (I25, [ADR-025](ADR-025-engineering-roles-and-sandbox.md), ⧗ OD-02).
12. Biznes hisob oyi `Asia/Tashkent`. Provider reset bazasi `vendor.openrouter_period` (F1_COST_RUNTIME) da o‘lchanadi va ikki oy chegarasi fixture bilan sinaladi; har so‘rov chegaralari `budget.request_bounds` da.
13. Jev pre-screen (Q61, [ADR-034](ADR-034-jev-review-pre-screen.md)) ham shu kalit va limit ichida, faqat llm-proxy orqali: chaqiruvchi — gateway (Decisions API yo‘li), narx `ai_runtime` da `reviewer` ulushidan rezerv qilinadi, so‘rovda `data_collection: "deny"` va `allow_fallbacks: false` (Q44★); ZDR akkaunt darajasida ham, so‘rov darajasida ham yoqilmaydi (Jev uchun owner rad etgan, G14).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Har agentga alohida OpenRouter kaliti | owner bitta kalitni tanlagan (Q44.1) |
| To‘g‘ridan-to‘g‘ri Anthropic API kaliti | owner OpenRouter’ni tanlagan — u media modellarini ham beradi |
| Paperclip budget’lariga tayanish | OpenRouter-billed run’lar $0 yoziladi |
| Kalitni agent yoki Hermes muhitida saqlash | budget, media va kill chetlab o‘tiladi; atributsiya soxtalashadi |
| Akkaunt darajasidagi ZDR | Anthropic 1P endpoint’lari va video o‘chadi |
| Limit tugaganda boshqa kalit yoki provayderga o‘tish | fallback yo‘q (Q44.3) |
| Limit nazoratini Langfuse ma’lumotiga bog‘lash | ingest kechiksa limit kech ushlanadi |
| Engineering uchun runtime kalitini ishlatish | runtime custody va 15 000 USD minor cap buziladi (I25) |

## Oqibatlar

- **+** Bitta qattiq chegara: pul limitdan oshmaydi; rasm va video ham shu hisobda.
- **+** Atributsiya ishonchli, provider siyosati majburiy, kill LLM qatlamida ham ishlaydi.
- **−** Nazoratdan chiqqan bitta agent boshqalarning ulushini yeb qo‘yishi mumkin — ulush qoidalari va anomaly detektor (`budget.anomaly`) bilan yumshatiladi.
- **−** llm-proxy kritik komponent: ishlamasa agentlar to‘xtaydi (fail-closed); deterministik servislar va reklama davom etadi.
- **−** Langfuse yoki Broadcast ishlamasa watchdog’ning tashqi solishtiruvi ko‘r qoladi; proxy ledger’i limitni baribir ushlaydi, trace kelmasligi alert.
- **−** Kredit fee va muddati umumiy xarajatga qo‘shiladi (`budget.tco`).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Paperclip billing tuzatilishi | stable versiyada OpenRouter-billed run’lar to‘g‘ri hisoblansa | `vendor_advisory` (WF-E03) | watchdog manbalari qayta ko‘riladi |
| Oylik sarf limitga yaqin | 2 oy ketma-ket kalit limitining ≥ 90% i | `provider_usage_snapshots`, Langfuse (`cost_drift`) | ulushlarni qayta taqsimlash yoki Q10 bo‘yicha owner qarori |
| Bitta agent limitni tugatishi | ulushi tufayli boshqa agentlar to‘xtagan insident | `incident_aar` | ulush va anomaly chegaralari tuzatiladi |
| Provider limit semantikasi | 403/402 yoki reset xulqi `vendor.openrouter_period` dalilidan farq qilsa | `vendor_advisory` | dalil yangilanadi, proxy kodi tuzatiladi |
| Agent sarfi ulushidan oshishi | 2 oy ketma-ket | Langfuse (`cost_drift`) | [ADR-016](ADR-016-model-selection-by-eval.md) bo‘yicha model qayta tanlovi |

## Kanonik implementatsiya

- [budgets.yaml](../09_Config_Templates/budgets.yaml) — `openrouter.*`, `media_generation.*`.
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `budget_override`, `agent_resume`; [operations.yaml](../09_Config_Templates/operations.yaml) — `protective_controls.proxy_admission_pause`.
- [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) — `llm-proxy`, `cost-watchdog`, `provider_keys_on_agents`.
- [OBSERVABILITY §3](../03_Architecture/OBSERVABILITY.md), [GUARDRAIL_GATEWAY §10](../03_Architecture/GUARDRAIL_GATEWAY.md), [DATA_MODEL §7](../03_Architecture/DATA_MODEL.md) — `ai_requests`, `provider_usage_snapshots`, `agent_runtime_state`.
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `vendor.openrouter_period`, `budget.request_bounds`, `budget.anomaly`, `budget.media`, `budget.tco`.
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-19, UAT-20; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I02, I11, I25; [ADR-019](ADR-019-llm-proxy-agent-isolation.md) (proxy va izolyatsiya yozuvi; 6-band ADR-022 bilan almashtirilgan).
