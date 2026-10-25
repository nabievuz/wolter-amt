# ADR-004 — Hermes faqat CMO uchun; OpenClaw o‘rnatilmaydi

Holat: Accepted · Qaror egasi: owner (Q07, Q15/Q39, Q47 ✅) + builder ★ (Hermes toolset cheklovi) + builder ◇ P-14 (memory/skill qoidasi) · Sana: 2026-10-22

## Kontekst

- Owner agentlarning "insondek" ishlashini xohlaydi: Telegram’da mavjudlik, xotira, proaktivlik; brauzer avtomatlashtirish yo‘q (Q07). Hermes — faqat CMO uchun, birinchi kundan; **OpenClaw ishlatilmaydi** (Q15/Q39). Ops bot deterministik; Hermes — suhbat, read-only savol-javob, ovozli xabar → vazifa, offer g‘oyasi → PR drafti; Hermes’da Meta/amoCRM yozish yo‘q, tasdiq hech qachon Hermes orqali o‘tmaydi (Q47) [D: DECISION_LOG].
- Hermes faktlari (2026-10-22, pinned versiyada qayta tekshiriladi, [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md)):
  - MIT, Python; xotira `MEMORY.md`, `USER.md` va FTS5 qidiruv; skill’larni o‘zi yaratadi va yamaydi — yozish `memory.write_approval` va `skills.write_approval` bilan nazorat qilinadi [D: Hermes docs];
  - Telegram gateway, cron, MCP client, browser va computer-use tool’lari bor [D];
  - Paperclip’da `hermes_gateway` adapteri (HTTP runs API + SSE, `API_SERVER_KEY`) [D]; Paperclip boshqaradigan OpenRouter routing’i gateway’larni qamramaydi — provayder Hermes’ning o‘zida sozlanadi [D];
  - `execute_code` buyruq naqshlarini chetlab o‘tishi mumkin [D: Hermes security docs]; CVE-2026-10221 holati aniq emas ("no fix yet", advisory ichki ziddiyatli) [?].
- OpenClaw: funksiyasi Hermes bilan deyarli bir xil; ClawHub’da yuzlab zararli skill va internetga ochiq o‘n minglab gateway qayd etilgan [D2: conscia.com, adversa.ai].
- Chat orqali har qanday ruxsatli foydalanuvchi Hermes’ning in-chat `write_approval` so‘roviga rozilik bera olsa, prompt injection doimiy xotiraga yozilishi mumkin [X].

## Qaror

1. **Hermes — faqat CMO runtime’i**, birinchi kundan; Paperclip’ga `hermes_gateway` orqali ulanadi. **OpenClaw o‘rnatilmaydi (Q15/Q39 ✅).** Uni yoki boshqa Claw-runtime’ni qayta taklif qilish yangi owner Q talab qiladi.
2. Ishga tushirish: UID `hermes`; API server faqat localhost’da. LLM provayderi — `llm-proxy` `/openai`, ikki CMO proxy tokeni bilan: `cmo-chat` (Telegram suhbati, ovozli xabar STT) va `cmo-workflow` (amt-workflow ishga tushiradigan API-server run’lari, har so‘rovda `provider: cmo-workflow`), ular CMO ulushining `chat` va `workflow` qismlariga yoziladi (◇ P-101); OpenRouter kaliti Hermes’da yo‘q ([ADR-003](ADR-003-openrouter-single-key-watchdog.md)). Egress: gateway, llm-proxy va faqat CMO boti uchun `api.telegram.org` (`runtime-isolation.yaml#cmo_telegram_transport`); bu kanal hech qachon approval kanali emas.
3. Pinned Hermes konfiguratsiyasi — F4 da pinned versiya bilan qotiriladi; o‘zgarishi faqat repo PR → mustaqil verification → owner release (A sinf, WF-E04). Kalitlarning aniq nomlari pinned versiyada tekshiriladi [?]:

   | Sozlama | Qiymat |
   |---|---|
   | `memory.write_approval` | on |
   | `skills.write_approval` | on |
   | `memory.memory_enabled` | on (Q07 xotirasi qoladi) |
   | `memory.memory_char_limit` | 2200 (pinned versiyaning default’i yozib qo‘yiladi; upgrade uni jim oshirmaydi) |
   | `memory.user_char_limit` | 1375 |
   | `memory.user_profile_enabled` | off (bitta USER.md har `hermes_chat` sessiyasiga kiradi — owner profili sales_lead’ga ko‘rinishi mumkin [?]; F4-AT-24 shaxs bo‘yicha profilni isbotlaguncha o‘chiq; ◇ P-99) |
   | `memory.provider` | builtin (tashqi memory provider xotirani hostdan olib chiqadi; aniq kalit va qiymat pinned versiyada [?], VR-44) |
   | `auxiliary.background_review.enabled` | off (Hermes default’i on: memory yozuvlarini stage qiladigan fon LLM o‘tishi, input’i kontekst oynasining 75% igacha — ko‘pi bilan 600 000 token; yashirin memory yozuvchisi va xarajat ko‘paytiruvchisi) |
   | `session_search` tool’i | yashirin (`agent.disabled_toolsets`; barcha sessiyalardan saqlangan xabarlarni rol doirasisiz qaytaradi; aniq toolset nomi pinned versiyada F4-AT-29 da tekshiriladi [T]) |
   | runtime’da skill yaratish va yamash (`skill_manage`) | o‘chiq |
   | tashqi skill hub’dan o‘rnatish | o‘chiq |
   | terminal, `execute_code`, browser, web qidiruv, computer-use toolset’lari | o‘chiq |
   | MCP serverlar | faqat AMT gateway |
   | Hermes cron | nazorat manbai sifatida ishlatilmaydi; CMO ritmi `operations.yaml#schedule` va `amt-workflow` orqali |

4. Gateway tool’lari faqat `approval-policy.yaml#agents.cmo.tools`: `meta_read.*`, `wh.metrics`, `wh.query`, `fleet.read_utilization`, `offers.read`, `offers.propose_pr` (Q47 — offer PR drafti, owner merge, NEVER_AUTO), `analytics.umami_query`, `report.submit`, `change_set.propose_manual`, `evo.signal.submit`, `workflow.submit_output`, `workflow.handoff_decide`, `workflow.report_blocker`, `workflow.start` (ro‘yxat config’dan nusxa; farq bo‘lsa config ustun). Paperclip issue amallari gateway bridge orqali (`paperclip_bridge.allowed_ops`). Meta/amoCRM write yo‘q; CMO kod yoki skill PR ochmaydi — yaxshilash g‘oyasi faqat `evo.signal.submit` orqali WF-E04/WF-E01 ga.
5. Memory va skill yagona qoidasi (◇ P-14 — ★ "memory va skill yozish tasdiq bilan" standartining qattiqroq aniqlashtirilishi, darhol amal qiladi):
   - runtime’da skill yaratish va yamash o‘chiq; skill o‘zgarishi faqat repo PR → release;
   - memory yozish faqat owner sessiyasida yoki ops-bot orqali owner typed callback tasdig‘i bilan; boshqa foydalanuvchi sessiyasida memory write rad etiladi — owner bo‘lmagan shaxs in-chat `write_approval` so‘rovini tasdiqlay olmaydi;
   - mexanizm (◇ P-87, P-99, `runtime-isolation.yaml#hermes_memory.staged_writes`) LLM emas, deterministik Hermes Telegram adapterida va fail-closed: har `/memory …` va `/skills …` buyrug‘i (`pending`, `approve`, `reject`, `approval on|off`) har yuboruvchidan — owner’dan ham — tashlanadi va auditga yoziladi, chunki Hermes orqali hech qanday tasdiq o‘tmaydi (✅ Q47) va runtime toggle pin qilingan write approval’ni o‘chirib saqlab qo‘yardi (VR-39, VR-44); stage qilingan yozuv faqat ops-bot’dagi owner typed callback bilan, bitta ID bilan tasdiqlanadi; owner bo‘lmagan `person_ref` sessiyasida stage qilingan yozuvni adapter rad etadi va tasdiqqa ko‘rsatmaydi; Hermes config fayli `hermes` UID uchun read-only, effektiv config hash ACK qilinadi (drift — `ALERT_CONFIG_ACK`); Hermes `pre_command` faqat kuzatadi, `post_gateway_admission` va `pre_gateway_dispatch` xato yoki timeout’da ochiq qoladi (VR-44), shuning uchun yolg‘iz hook yetmaydi; pinned versiyada biror qoida fail-closed bajarilmasa memory toolset ham yashiriladi va `MEMORY.md`/`USER.md` faqat release (WF-E04) bilan o‘zgaradi (F4-AT-24); chatda owner tasdig‘i kerak bo‘lsa — Q47 bo‘yicha yangi owner qarori;
   - suhbat ombori (`state.db`) xotira hisoblanadi: `privacy-policy.yaml#datasets` `hermes_sessions` va `hermes_memory`, retention `privacy.retention`;
   - har oy C12 retro’da memory diff audit qilinadi va owner ko‘radi.
6. Telegram chat allowlist — effektiv `hermes_chat` flag’iga ega faol shaxslar (`roles.yaml#flag_rules`: valid a’zoliklarning default flag’lari ∪ muddati o‘tmagan `person_flags`, faqat kamida bitta valid a’zolik bo‘lsa). DM pairing default-deny; runtime manbai `amt.people` + `amt.roles`. CMO bilan muloqot faqat DM’da (◇ P-10).
7. Hermes orqali hech qanday tasdiq o‘tmaydi ([ADR-009](ADR-009-telegram-approvals-and-2fa.md)); suhbatdagi "ha" approval, step tugashi yoki owner vakolati emas (I16).
8. Ovozli xabar: owner tanlagan bitta STT engine (proxy orqali audio model yoki lokal `stt-local`), avtomatik fallback yo‘q (Q44.3); yangi API kalit qo‘shilmaydi; Hermes o‘zi hech narsa ishga tushirmaydi.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| OpenClaw | Hermes bilan funksional ustma-ust; xavfsizlik tarixi og‘ir (zararli skill’lar, ochiq gateway’lar); owner rad etgan (Q15/Q39) |
| Hermes’siz, Paperclip’ning eksperimental Telegram connector’i | owner Hermes’ni tanlagan (Q39) |
| Hermes’ni keyingi bosqichga qoldirish | MVP yo‘q (Q39, Q48) |
| Hermes memory’ni butunlay o‘chirish | Q07 dagi "xotira" talabi bajarilmaydi |
| Har qanday `hermes_chat` foydalanuvchisiga memory write tasdig‘ini berish | owner bo‘lmagan sessiya orqali injection doimiy xotiraga yoziladi |
| AdClaw’ni CMO runtime’i qilish | dalil yetarli emas ([ADR-023](ADR-023-adclaw-reference-only.md)) |

## Oqibatlar

- **+** Owner bilan tabiiy suhbat: ovozli xabar vazifaga aylanadi, read-only savol-javob ishlaydi, proaktiv insight va xotira bor.
- **−** Ikkinchi runtime (Python) qo‘shiladi; uning yangilanishi va advisory’lari kuzatiladi (WF-E03).
- **−** Hermes sarfi Paperclip’ga yetib bormasligi mumkin [?]; xarajat proxy attributsiyasi (`user=cmo`) → Broadcast → Langfuse orqali kuzatiladi, proxy CMO ulushini ushlaydi.
- **−** Memory qoidasi qo‘shimcha ops-bot callback’i va oylik audit ishini talab qiladi.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Patch qilinmagan kritik CVE | pinned Hermes versiyasiga ta’sir qiladigan advisory | `vendor_advisory` (WF-E03) | patch release yoki CMO runtime’ni vaqtincha to‘xtatish |
| Ruxsat etilmagan tool chaqiruvi | ≥ 1 urinish (gateway yoki proxy audit) | `incident_aar` | INCIDENTS; toolset qayta tekshiruvi |
| Owner bo‘lmagan sessiyadan memory write urinishi | ≥ 1 urinish | ops-bot audit, C12 memory diff (`retro_c12`) | INCIDENTS; P-14 qoidasi qayta ko‘riladi |
| Hermes adapteri buzilishi | Paperclip yoki Hermes upgrade’dan keyin F4 Hermes testlari fail | `regression` | pin/rollback (WF-E03) |

## Kanonik implementatsiya

- [CMO](../02_Team_Charter/agents/CMO.md) — runtime, Hermes sozlamalari, allowlist.
- [TELEGRAM §5](../03_Architecture/TELEGRAM.md), [RBAC §3](../03_Architecture/RBAC.md).
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `agents.cmo`; [roles.yaml](../09_Config_Templates/roles.yaml) — `flags.hermes_chat`, `flag_rules`, `telegram_main_group`.
- [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) — `agents.cmo`, `cmo_telegram_transport`, `paperclip_bridge`.
- [F4_Agents](../05_Build_Phases/F4_Agents.md) — F4-AT-10, F4-AT-11, F4-AT-16; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I01, I02, I16.
