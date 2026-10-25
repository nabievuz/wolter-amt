# ADR-001 — Paperclip orkestratsiya qatlami sifatida

Holat: Accepted · Qaror egasi: owner (Q01, Q11, Q15, Q48 ✅) · Sana: 2026-10-22

## Kontekst

- Owner butun tizimni Paperclip ustida qurishni tanlagan; tizim faqat Wolter uchun, Paperclip’da bitta company — "Wolter AMT" (Q01). Paperclip org-as-code beradi: company, goal, agent, issue, routine, approval va audit log [D: DECISION_LOG Q01].
- Build kuni qayta tekshiriladigan vendor faktlari (2026-10-22 holati, [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) da claim sifatida):
  - stable kanal sana bo‘yicha versiyalanadi; Node ≥ 24.11 talab qilinadi [D: npm `paperclipai`];
  - `DATABASE_URL` berilmasa embedded PostgreSQL ishga tushadi va ma’lumot uy katalogida, backup qamrovidan tashqarida qoladi [D: `docs/deploy/database.md`];
  - 2026.1001.0 dan standart rejim to‘liq avtomat: approve-all va `--dangerously-skip-permissions` [D: release notes];
  - @-mention agentni uyg‘otmaydi; uyg‘otish assignment, routine yoki review orqali [D];
  - native runner eksperimental va self-hosted o‘rnatishda standart holatda yoqiq [D: `packages/paperclip-runner/README.md`] — pinned versiyadagi holati F1 da tekshiriladi [?];
  - OpenRouter orqali hisoblangan `claude_local` run’lari Paperclip budget’ida $0 yoziladi [D: `resolveClaudeBillingType()`] — xarajat nazorati Paperclip’dan tashqarida quriladi (ADR-003);
  - o‘z 2FA’si yo‘q [D: commit `043f2514` manbasi] — ADR-009;
  - kritik CVE’lar (CVE-2026-41679, GHSA-x8hx-rhr2-9rf7, CVE-2026-41208) 2026.416.0 da tuzatilgan; loyiha tez o‘zgaradi, hujjatlar koddan orqada qoladi [D: GitHub, advisory’lar].
- Paperclip issue va routine’lari restart, durable timer, lease va epoch bo‘yicha bizning kontraktimizni kafolatlashi isbotlanmagan [?]; issue yopilishi tashqi effekt dalili emas [X].

## Qaror

1. Paperclip — orkestratsiya va agent vazifa yuzasi: company, agentlar, issue, routine va hujjatlar. Approval, pul, kill va tashqi write vakolati AMT deterministik servislarida qoladi; Paperclip UI, approval board yoki agent xulosasi tashqi write’ga ruxsat bermaydi (I02, I03).
2. Faqat stable kanal. Pinned versiya build kuni qayta tekshiriladi va `VERSIONS.lock.md` ga yoziladi; 2026.416.0 dan eski versiya hech qachon ishlatilmaydi. Yangilash WF-E03 orqali.
3. Tashqi PostgreSQL, alohida `paperclip` bazasi. `DATABASE_URL` majburiy; production’da embedded PostgreSQL yo‘q (F1 da tekshiriladi).
4. `authenticated` rejim, faqat `127.0.0.1:3100` da, `TRUST_PROXY` bilan Caddy va tg-auth ortida (ADR-009, ADR-033); telemetry o‘chiq (`PAPERCLIP_TELEMETRY_DISABLED=1`).
5. O‘z UID’i `paperclip`; root yoki sudo yo‘q; sirlar va agent tokenlari unga berilmaydi. Agentlar faqat managed runner orqali alohida rol UID’larida ishga tushadi (ADR-022).
6. Agentlar faqat assignment, routine yoki approval hodisasi bilan uyg‘otiladi; interval taymer ishlatilmaydi.
7. Workflow truth — `amt-workflow` ledger’i; Paperclip issue — uning projection’i. Issue yopilishi, agent matni yoki suhbatdagi rozilik step’ni tugatmaydi (I16, [ADR-024](ADR-024-workflow-runtime-capability-first.md)).
8. Agent Paperclip control-plane’ga faqat gateway bridge orqali va faqat `runtime-isolation.yaml#paperclip_bridge.allowed_ops` bilan chiqadi: issue yaratish, biriktirish, izoh, holat, hujjat biriktirish, o‘ziga biriktirilgan yoki bog‘langan issue’ni o‘qish. Agent yollash/yaratish/o‘zgartirish, instructions, adapter, model, budget, routine yaratish/tahrirlash va approval so‘rovi rad etiladi; F4 da har rol uchun salbiy test.
9. Company tuzilmasi repo’da kod sifatida yuritiladi va pinned formatda preview → apply orqali import qilinadi.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| O‘zimiz yozgan orkestrator (cron + skriptlar) | Owner Paperclip va Agentic OS’ni aniq tanlagan (Q01); approval va org UI’ni qayta yozish qimmat; premortem’dagi "soddaroq stack" taklifini owner rad etgan |
| Production’da embedded PostgreSQL | backup, upgrade va restore boshqaruvi qiyin; ma’lumot backup qamrovidan chiqib qoladi |
| Paperclip issue/routine’ni workflow truth qilish | restart, timer va epoch kafolati isbotlanmagan; issue holati tashqi effekt dalili emas (ADR-024) |
| Xarajat nazoratini Paperclip budget’lariga topshirish | OpenRouter-billed run’lar $0 yoziladi (ADR-003) |
| Paperclip va Hermes’ni AdClaw bilan almashtirish | dalil yetarli emas; holat `reference_only` ([ADR-023](ADR-023-adclaw-reference-only.md)) |

## Oqibatlar

- **+** Org-as-code, issue va approval UI, adapterlar (`claude_local`, `hermes_gateway`, `opencode_local`) va REST API tayyor holda keladi.
- **+** Paperclip vakolatsiz qatlam bo‘lgani uchun uning xatosi pul yoki tashqi write’ga to‘g‘ridan-to‘g‘ri olib kelmaydi.
- **−** Skip-permissions standarti rol izolyatsiyasini majburiy qiladi (ADR-022).
- **−** Tez o‘zgarishi sabab upgrade intizomi kerak ([UPGRADE](../06_Runbooks/UPGRADE.md), WF-E03).
- **−** Ikki holat yuzasi bor (Paperclip issue va `amt-workflow` run): projection va divergence alerti uchun qo‘shimcha kod.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Upgrade to‘xtatishi | Paperclip upgrade’i sabab tizim 1 kundan ortiq ishlamasa | `incident_aar` (WF-E01) | pin/rollback; zarur bo‘lsa muqobil orkestrator ADR’i |
| Kritik advisory | pinned stable versiyaga ta’sir qiladigan yangi kritik CVE | `vendor_advisory` (WF-E03) | patch release yoki UI’ni vaqtincha yopish |
| Founder ops vaqti | 2 hafta ketma-ket `ops.founder_time_budget` limitidan oshsa (⧗ OD-15) | haftalik ops vaqti o‘lchovi | stack’ni soddalashtirish ADR’i — owner qarori |
| Projection drift | issue ↔ run divergence alerti takrorlansa | `amt-workflow` divergence alerti (`regression`) | adapter yoki projection tuzatish (WF-E01) |
| Billing tuzatilishi | stable versiyada OpenRouter-billed run’lar to‘g‘ri hisoblansa | `vendor_advisory` | ADR-003 dagi watchdog manbalari qayta ko‘riladi |

## Kanonik implementatsiya

- [TEAM](../02_Team_Charter/TEAM.md) — rollar va Paperclip company tuzilmasi.
- [ARCHITECTURE §2–§3](../03_Architecture/ARCHITECTURE.md) — komponent va chegaralar; [WORKFLOW_RUNTIME §4](../03_Architecture/WORKFLOW_RUNTIME.md) — Paperclip projection.
- [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) — `orchestrator_uid`, `services`, `paperclip_bridge`.
- [workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml) — `paperclip.issue_close_completes_step: false`.
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `vendor.component_locks`, `workflow.mechanism`, `ops.founder_time_budget`.
- [F1_Platform](../05_Build_Phases/F1_Platform.md), [F4_Agents](../05_Build_Phases/F4_Agents.md), [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I01, I02, I16.
