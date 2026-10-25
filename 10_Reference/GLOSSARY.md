# Atamalar lug‘ati — Wolter AMT

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Bu lug‘at atamalar indeksi; u biznes semantikasini o‘zgartirmaydi. Biznes ta’riflari [BUSINESS_CONTRACT](../11_Production_Contracts/BUSINESS_CONTRACT.md)da, qisqa domen tili [CONTEXT](../CONTEXT.md)da, state va vakolat [INVARIANTS](../11_Production_Contracts/INVARIANTS.md)da, texnik tafsilot [DATA_MODEL](../03_Architecture/DATA_MODEL.md) va config shablonlarida kanonik. Ziddiyat bo‘lsa kanonik manba ustun; lug‘at tuzatiladi.

## 1. Holat belgilari va ustuvorlik

| Belgi | Ma’nosi |
|---|---|
| ✅ Q-ID | owner tasdiqlagan qaror; faqat yangi owner Q bilan o‘zgaradi (eskisi ⟲) |
| ★ | owner xulosada qabul qilgan builder standarti |
| ◇ P-NN | builder taklifi, owner ko‘rib chiqishini kutmoqda; nazoratni kuchaytiradigan yoki neytral ◇ darhol amal qiladi, yumshatadigani faqat owner qabul qilgach |
| ⧗ OD-NN | ochiq owner qarori; faqat o‘z qatoridagi gate’ni bloklaydi ([OPEN_ITEMS](../00_Decisions/OPEN_ITEMS.md)) |
| ⟲ | keyingi qaror bilan almashtirilgan |

Ustuvorlik ([DECISION_LOG §0](../00_Decisions/DECISION_LOG.md)): 1) owner ✅ qarorlari; 2) INVARIANTS (owner qaroridan qattiqroq bo‘lishi mumkin, yumshoqroq emas); 3) production kontraktlar, config shablonlari, `Holat: Accepted` ADR’lar; 4) arxitektura, fazalar, runbook’lar, nizomlar, skill va eval’lar; 5) `readiness.yaml` qiymatlari (faqat 1–3 chegarasida); 6) ma’lumotnoma (`10_Reference/`, shu lug‘at ham). Hal bo‘lguncha qattiqroq qoida amal qiladi; ziddiyat OPEN_ITEMS “Ziddiyatlar reyestri”ga (C-NN), pul/PII/vakolat ziddiyati — HUMAN_GATE.

## 2. Yagona holat lug‘atlari

Har lug‘at alohida; biri boshqasining o‘rniga ishlatilmaydi.

| Lug‘at | Qiymatlar | Kanonik manba |
|---|---|---|
| Delivery lifecycle (faza, release, upgrade candidate) | `specified → implemented → verified_in_staging → merged → released → deployed → observed → technically_accepted → business_accepted`; terminal: `rejected`, `inconclusive`, `rolled_back`, `cancelled`, `not_applicable` | [evolution-policy.yaml](../09_Config_Templates/evolution-policy.yaml) `outcome.lifecycle`, I23 |
| Faza ledger mosligi | boshlanmagan = `specified`; build tugadi = `implemented`; izolyatsiyalangan/staging testlar o‘tdi = `verified_in_staging`; owner merge = `merged`; owner release = `released`; hostda = `deployed`; oyna dalil bilan yopildi = `observed`; barcha AT+HG yopildi = `technically_accepted`; biznes dalili = `business_accepted` yoki sabab bilan `not_applicable` | [PHASES](../05_Build_Phases/PHASES.md) |
| Faza qabul qilingan | `technically_accepted` ∧ (`business_accepted` ∨ uning N/A) va HG/AT/kuzatuv oynalari yopilgan | [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) |
| Test/dalil natijasi | `not_run`, `pass`, `fail`, `blocked`, `inconclusive` (oxirgisi faqat biznes/statistik testlarda); data’da kichik harf, ko‘rinishda katta harf | PRODUCTION_ACCEPTANCE |
| Readiness yozuvi | `pending → evidenced → approved`; `not_applicable` (faqat `criticality: optional`, sabab + owner) | [readiness.yaml](../09_Config_Templates/readiness.yaml) |
| Gate va blok so‘zlari | gate yoki profil **o‘tdi (PASS)** — talablari bajarilgan; yozish yoki capability **yopiq (bloklaydi)** — bajarilmaydi; readiness kalitini yoki ochiq bandni **yopish** — dalil va inson imzosi bilan `approved` qilish. "Gate yopildi" iborasi ishlatilmaydi | shu lug‘at |
| Upgrade verdict | `accepted`, `rejected`, `inconclusive` | evolution-policy.yaml `outcome.verdicts` |
| Release sinfi | `normal`, `recovery` (`killed` paytida faqat `recovery`) | [release-policy.yaml](../09_Config_Templates/release-policy.yaml) `release_classes` |
| Gateway global rejimi | `shadow`, `enabled`, `read_only`, `killed` | [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) `global_modes` |
| Pipeline rejimi | `L0_shadow`, `L1_approve_each`, `L2_auto_within_guardrails`; `shared` = `min(sale, rent)` | execution-policy.yaml |
| Trust darajasi | action_type × pipeline bo‘yicha faqat `L1_approve_each` ↔ `L2_auto_within_guardrails`; L0 faqat pipeline rejimi yoki global `shadow`dan; samarali daraja = `min(global, pipeline, trust)` | [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) `trust_ramp` |
| Command state | `pending_review`, `pending_approval`, `approved`, `claimed`, `executing`, `succeeded`, `rejected`, `expired`, `cancelled`, `failed_confirmed`, `uncertain`, `reconciling`, `manual_resolution`, `awaiting_manual`, `done_manual` | execution-policy.yaml `command_states`, I05 |
| Approval qarori | `approve`, `reject`, `edit_decrease`, `expire` | approval-policy.yaml `change_set.decisions` |
| Intake receipt | `accepted → crm_pending → crm_confirmed`; `uncertain`; `needs_review` | I08 |
| Workflow run | `created`, `running`, `waiting`, `blocked`, `reconciling`, `completed`, `failed`, `cancelled`, `manual_resolution` | [workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml) |
| Workflow step | `pending`, `ready`, `claimed`, `running`, `waiting`, `handoff_pending`, `completed`, `rejected`, `failed`, `skipped`, `cancelled`, `compensated` | workflow-policy.yaml |
| Handoff | `offered`, `accepted`, `rejected`, `expired` | workflow-policy.yaml |
| Run biznes natijasi | `pending`, `met`, `not_met`, `inconclusive`, `not_applicable` | workflow-policy.yaml |
| Command outcome (Trust Ramp) | `met`, `not_met`, `inconclusive` (`command_outcomes`; faqat `met` toza) | approval-policy.yaml `graduation` |
| `data_status` | `valid`, `no_activity`, `no_spend`, `spend_zero_qualified`, `insufficient_sample`, `not_mature`, `incomparable_baseline`, `missing_data`, `stale_data` | [business-policy.yaml](../09_Config_Templates/business-policy.yaml); harakatlar — [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml) |
| Tracking check | `pass`, `warn`, `fail`, `unknown`, `stale`, `low_n`, `not_applicable` | [tracking-health.yaml](../09_Config_Templates/tracking-health.yaml) |
| Reviewer check | `pass`, `fail`, `needs_owner`, `n_a` (yig‘indi: biror `fail` → fail; biror `needs_owner` → needs_owner) | [REVIEWER](../02_Team_Charter/agents/REVIEWER.md) |
| Insident severity | `critical`, `degraded` | [operations.yaml](../09_Config_Templates/operations.yaml) `severities` |
| Kill rejimi | A `ai_only` (standart ★), B `ai_and_ads` | execution-policy.yaml |
| AdClaw adoption holati | `reference_only` (joriy), `restricted_runtime_candidate`, `replacement_proposal` | [ADR-023](../04_ADR/ADR-023-adclaw-reference-only.md), [ADCLAW_ASSESSMENT](ADCLAW_ASSESSMENT.md) |

## 3. Atamalar

| O‘zbekcha / ID | English | Ma’nosi |
|---|---|---|
| Project OS | Project Operating System | PRD, jamoa, arxitektura, config, build, runbook va acceptance’dan iborat to‘liq yetkazish shartnomasi; runtime mavjudligi isboti emas |
| AMT | AI Marketing Team | Paid Meta uchun olti biznes agenti: cmo, media-buyer, creative-studio, cro, funnel-analyst, reviewer |
| Engineering rollari | engineering roles | eng-planner, eng-architect, eng-implementer, eng-verifier — alohida reyestr, faqat sandbox vakolati; biznes agenti emas |
| Quruvchi | builder | spetsifikatsiya bo‘yicha implementatsiya qiluvchi; readiness’da faqat `prepared_by`; real credential/approval vakolati alohida |
| Sifatli murojaat | qualified lead | bog‘langan, kuryerligi va 30 kun ichidagi sale/rent niyati tasdiqlangan; uchala shart zarur (Q16 ✅) |
| Asosiy metrika | North Star | pipeline bo‘yicha birinchi valid qualified (Q04 ✅); cash/contribution, contract va readiness guardrail bilan |
| Himoya metrikasi | guardrail metric | optimizatsiya buzmasligi kerak bo‘lgan metrika: lead→shartnoma, bandlik |
| Goodhart tuzog‘i | Goodhart’s law | metrika maqsadga aylansa yaxshi o‘lchov bo‘lmay qoladi; CPL faqat diagnostika |
| Qualified narxi | qualified CPL | mos pipeline spend ÷ qualified; event-week (`qualified_cpl_event_week`) va cohort variantlari alohida |
| Diagnostik CPL / CTR | cost per lead / click-through rate | oraliq ko‘rsatkich; mustaqil biznes muvaffaqiyati emas |
| Acquisition episode | acquisition episode | dedup qilingan bitta yangi mijoz ehtiyoji; bir nechta lead/transfer bilan bog‘lanishi mumkin |
| Shartnoma | contract | tasdiqlangan sotuv/ijara kelishuvi; payment yoki fulfilment degani emas |
| Topshirish / ijara boshlanishi | fulfilment / rental start | alohida manba hodisasi; shartnoma statusidan taxmin qilinmaydi |
| Tushgan pul | received cash | haqiqiy payment hodisasi; shartnoma summasi, deposit va revenue’dan farqlanadi |
| Qaytarish / bekor qilish | refund / cancellation | refund — alohida real pul chiqimi; cancellation majburiyatni bekor qiladi, payment/refund faktlarini o‘chirmaydi |
| Contribution | contribution margin | moliya tasdiqlagan bir xil kogorta/horizon/valyuta bazasida revenue minus o‘zgaruvchan xarajat |
| Yangi to‘lagan mijoz narxi | paid new customer CAC | tegishli spend ÷ birinchi haqiqiy payment’i bor yangi mijoz; renewal yangi acquisition emas |
| Yangi ijara / uzaytirish | new rental / renewal | yangi munosabat boshlanishi va mavjud davr davomi; hisobotda ajratiladi |
| Fizik park | physical fleet | bir snapshot’dagi velosipedlar; tranzaksiya/oy soni emas |
| Ishga yaroqli park | serviceable_bikes | rented + reserved + available; maintenance alohida |
| Topshirishga tayyor | available_bikes | rezerv qilinmagan, ishga yaroqli bo‘sh velosipedlar |
| Park bandligi | fleet utilization | rented ÷ serviceable; denominator 0 → unknown |
| Tranzaksiya / bike-days | throughput / bike-days | oylik operatsiyalar yoki foydalanish kunlari; fizik bandlikka teng emas |
| Amaldagi waitlist | current eligible waitlist | dedup, mos, hozir tayyor va muddati o‘tmagan talab; band’larni `waitlist_eligible_ready` boshqaradi (⧗ OD-07) |
| Sig‘imni hisobga oluvchi maqsad | capacity-aware objective | ijara byudjeti park bandligi va waitlist’ga bog‘lanadi (ADR-014, Q43★) |
| Capacity hold | capacity hold | bugungi yaroqli fleet snapshot yo‘q bo‘lganda barcha odatiy rent budget harakatini muzlatish; protective pause alohida |
| Sotuvga tayyorlik | sale readiness | amaldagi offer, stock, financing, fulfilment va call-center quvvati bo‘yicha yaroqli snapshot (`/sale_ready`, F6_STEP2) |
| QA / response lag | qualification quality / response lag | sales_lead egasi bo‘lgan semantik tanlanma va aloqa kechikishi |
| Kogorta / yetilgan | cohort / mature | bir xil acquisition davri va kelishilgan natija oynasi yetarlicha kuzatilgan guruh |
| Baseline | comparable baseline | formula, source, measurement revision, coverage va maturity mos tasdiqlangan solishtirish (8 hafta + 12 oylik mavsumiy profil) |
| Eski proxy baseline | historical proxy baseline | yangi qualified/o‘lchov ta’rifi bilan solishtiriluvchanligi isbotlanmagan tarix |
| O‘lchov revision’i | measurement revision | ta’rif, sanash, attribution yoki formula o‘zgarishini belgilovchi revision |
| First-touch / last-touch | first / last eligible marketing touch | tasdiqlangan lookback’da birinchi va conversion oldidagi oxirgi eligible touch; alohida saqlanadi |
| Unknown source | unknown/unmatched attribution | manbasi yetishmagan yoki consent cheklagan guruh; organic yoki Meta deb taxmin qilinmaydi |
| Meta-reported | platform-attributed result | Meta o‘z modeli bilan ko‘rsatgan natija; CRM touch bilan qo‘shilmaydi |
| Farqlar ayirmasi | difference-in-differences | faqat diagnostika; pretrend isbotlanmasa sababiy lift emas |
| Natija noaniq | inconclusive | sample/maturity/dalil yetarli emas; exposure/deadline bor; toza natija yoki PASS emas (◇ P-04) |
| Nol qualified | `spend_zero_qualified` | sarf > 0, qualified = 0; CPL aniqlanmagan, zarar exposure’i; jim PASS emas |
| Exposure guard | exposure guard | har sync siklida zero-qualified va past-data holatini tekshiruvchi deterministik job; scale blok + alert |
| Intake qabul | accepted submission | shifrlangan durable commit bor; CRM tasdiqlanganini bildirmaydi |
| Reconciliation | source/remote reconciliation | manba yoki tashqi holatni lokal holat bilan dalilli moslashtirish; alertning o‘zi emas |
| CAPI / Pixel | Conversions API / Meta Pixel | server/browser event yetkazish; dedup, consent va event vaqti qoidalari bilan |
| Event ID / dedup | event identifier / deduplication | bir hodisaning qayta hisoblanishini ajratish; har vendor write uchun exactly-once kafolati emas |
| EMQ / fbc / fbp | Event Match Quality / click va browser ID | Meta matching signallari; consent va coverage denominator’i bilan |
| O‘rganish bosqichi | learning phase | Meta ad set’i optimizatsiyani o‘rganayotgan davr; tez-tez o‘zgartirish uni qayta boshlaydi |
| Akkaunt konsolidatsiyasi | account consolidation | kam ad set, broad yoki Advantage+ — signalni to‘plash uchun (Q41 ✅) |
| Maxsus reklama toifasi | special ad category | Meta’ning moliya va shu kabi cheklangan toifalari; bo‘lib to‘lash offerlari tekshiriladi (Q42 ✅) |
| Tizim foydalanuvchisi | system user | Business Manager’dagi server avtomatlashtirish foydalanuvchisi (`amt-read`, `amt-write`); soni access tier’ga bog‘liq (`vendor.meta_access_tier`) |
| Boshqariladigan entity | managed entity | owner aniq AMT’ga topshirgan campaign/ad set/ad scope’i (`managed_entities`) |
| Takeover | takeover | insondan AMT’ga tasdiqlangan scope boshqaruvini o‘tkazish (`takeover_scope_change`, HG-F6-04) |
| Human handback | human handback | AMT yozishi yopilib, mas’ul inson boshqaruvni qabul qilgani ACK bilan (`handback_acks`); alert yuborilishi handback emas |
| Handback custodian | handback custodian | Ads Manager vakolati bor, roster’da nomlangan inson (`ops.ads_handback_roster`, `ops.sale_handback_roster`) |
| O‘zgarish taklifi | change-set item / command | aniq target/payload/revision/evidence’li durable harakat yozuvi; approval va execution alohida |
| Kunlik change set | daily change set | 10:00 dagi tasdiqlash ro‘yxati (Q38 ✅); cutoff 09:45; TTL `presented_at`dan 12 soat |
| Approval | scoped human approval | tegishli rolning exact action/revision’ga qarori; chat xabari emas; avtomatik tasdiq yo‘q |
| Ikki bosqichli tasdiq | two-step (`TASDIQ <kod>`) | tugma → bot 4 xonali kod → `TASDIQ <kod>` 2 daqiqa ichida ★; ongli harakat tasdig‘i, ikkinchi autentifikatsiya omili emas |
| Reviewer verdict | independent review result | `review.get_subject` bergan exact subject hash + offer/policy revision bo‘yicha tekshiruv; human approval emas |
| Inson til tekshiruvi | human language check | birinchi 20 live copy uchun `language_checker` flag’li ona tili o‘zbek odam (Q42 ✅); Reviewer o‘rnini bosmaydi |
| Jev pre-screen | Jev pre-screen (TypeSafe decision model) | Reviewer’dan oldingi deterministik tekshiruv (`meta_policy`, `special_ad_category`, `pii_leakage`): verdiktni faqat qattiqlashtiradi, Reviewer o‘rnini bosmaydi; lead PII’sini ko‘rmaydi — asosiy himoya Q28 (agentlarda lead PII yo‘q), ikkinchi qatlam — har Jev chaqiruvidan oldin gateway’dagi lokal PII guard: telefon, email, karta yoki ID raqami yoki UZ/RU ism va manzil evristikasi ishlasa Jev chaqirilmaydi va `pii_leakage` lokal bayroqlanadi (guard ushlamaydigan shakldagi ism — yolg‘iz ism, bosh harfsiz yolg‘iz familiya, ro‘yxatda yo‘q ism yoki boshqa oxirli familiya evristikadan o‘tadi — qoldiq xavf, OI-54); har so‘rov `data_collection: deny` (Q44★), ZDR talab qilinmaydi; scope `uz_ru` yoki `ru_only`; faqat `models.pre_screen` approved va PRE_SCREEN profili PASS bo‘lganda ishlaydi (capability `review.pre_screen`), aks holda o‘chiq (Q61, ADR-034) |
| Succeeded | confirmed execution success | tashqi harakatning tasdiqlangan yakuni |
| Uncertain | ambiguous external outcome | timeout/uzilishdan keyin ta’sir bo‘lgan-bo‘lmagani noma’lum; ko‘r retry emas, reconcile |
| Failed confirmed | confirmed no-effect failure | tashqi ta’sir bo‘lmaganini dalil tasdiqlagan yakun; har timeout bu holat emas |
| Done manual | evidenced manual completion | owner tasdiqlagan qo‘lda ish dalil bilan tugagan |
| Idempotency key / attempt | duplicate-control key / execution attempt | lokal qayta ishlashni tartiblaydi; vendor idempotency’si alohida tekshiriladi |
| Revision / hash | immutable version / content hash | aniq payload, asset, offer, review yoki policy nusxasi; fayl nomi revision emas |
| Birinchi aktivlashtirish | `campaign_activate` | `campaign_create` yoki `adset_duplicate` bilan yaratilgan, hech qachon faol bo‘lmagan entity’ni birinchi yoqish — faqat owner, never_auto |
| Qayta yoqish | `entity_activate` | avval faol bo‘lgan kampaniya yoki ad set’ni qayta yoqish (owner yoki ads_approver) |
| Kreativ yoqish | `creative_activate` | mavjud faol ad set ichida ad’ni yoqish yoki kreativni almashtirish; Reviewer `pass` majburiy |
| Ad set nusxasi | `adset_duplicate` | owner-only, never_auto; nusxa PAUSED yaratiladi |
| Control epoch / fence | control generation / dispatch barrier | kill va yangi dispatch’ni lokal tartiblaydi; vendor oldingi so‘rovni to‘xtata oladi deb olinmaydi |
| Gateway | guardrail gateway | agent tool’lari va deterministik executor orasidagi yagona vakolat yo‘li |
| LLM proxy | llm-proxy | model/media routing, pin, trace va atomik spend rezervi yo‘li; fallback o‘chiq; runtime kaliti faqat shu yerda |
| Xarajat qo‘riqchisi | cost-watchdog | per-agent sarfni kuzatadi; ulush/kalit chegarasida `proxy_admission_pause` |
| Trust Ramp | scoped autonomy | action × pipeline bo‘yicha L0/L1/L2; L2 ga 10 ketma-ket `met` + 14 kun insidentsiz ★, owner `/graduate` (HG-L2-01); NEVER_AUTO alohida |
| Locked | locked operating condition | operatsion atama: `killed` yoki `shadow`+L0; yangi enum emas |
| Kill A / B | `ai_only` / `ai_and_ads` | avval lokal durable latch; B’da har managed entity’ning eng yuqori to‘liq managed darajasi pauza, foreign parent’ga tegilmaydi; partial reconcile |
| Resume | controlled resume | global kill’dan keyin har pipeline `min(pre_kill, L1)`; global `shadow` va sababi hal bo‘lmagan `read_only` saqlanadi; eski approval tirilmaydi |
| Protective pause | `protective_pause` | oldindan ruxsatli deterministik pauza: faqat managed entity, faqat pause; `shadow`, `enabled`, `read_only` va `killed` rejimlarida ishlaydi; provider spending limit’ning o‘rnini bosmaydi (◇ P-21) |
| Agent qaytarish | `agent_resume` | cost-watchdog, proxy admission pauzasi yoki oy chegarasi pauza qilgan agentni owner qaytaradi (`/agent resume <agent_slug\|cmo.chat\|cmo.workflow>`, typed code, never_auto); Langfuse/usage uzilishi pauzasi reconciliation isbotlangach avtomatik qaytadi |
| Protective controls | protective controls | inson buyrug‘isiz ishlaydigan himoyalar: `protective_pause`, `proxy_admission_pause`, `tracking_read_only`, `provider_limit_read_only`, `account_restricted_read_only`, `kill_criteria_l0`, `maintenance_hold` (`operations.yaml#protective_controls`) |
| Maintenance hold | maintenance hold | release oynasida `read_only` + proxy admission pauza; tugagach `maintenance_release` faqat hold o‘zgartirgan o‘lchovlarni qaytaradi, oynada yoqilgan himoya nazoratlari qoladi; kill emas, L2 pasaymaydi |
| Kill criteria | deterministic handback rule | KC-01: qualified CPL comparable baseline’dan >25% yomon 2 ketma-ket hafta → pipeline L0 + handback + C05 (Q31 ✅); KC-02: lead→shartnoma guardrail’i → avtomatik oshirish blok |
| Rolling24h budget chegarasi | absolute cumulative movement bound | 24 soat ichidagi barcha oddiy increase/decrease mutlaq yig‘indisi oyna boshidagi ishonchli bazaning ≤20% i (◇ P-01, Q08/Q32 ✅ aniqlashtirishi) |
| Oylik cap / headroom | monthly cap / remaining allowed exposure | verified MTD, commitment’lar va safety margin bilan; limitni sarflash majburiy emas |
| Provider spending limit | account spending limit | Ads Manager’dagi akkaunt cap’i, AI’dan mustaqil va majburiy (Q37 ✅); kumulyativ, har oy HG-OPS-01 bilan yangilanadi |
| Spending limit zaxirasi | spend_cap headroom | `spend_cap − amount_spent`; owner har oy formula (◇ P-02) bilan qayta qo‘yadi |
| Actual + reserved | atomic spend accounting | to‘langan va hali yakunlanmagan rezerv sarf birga; uncertain billing nol emas |
| Pul birligi | minor unit | integer USD minor: USD 150/oy = 15 000 USD minor; USD 1 500/oy = 150 000 USD minor |
| Offer registry | commercial registry | owner tasdiqlagan immutable narx/da’vo/shart revision’lari (`offers.yaml`, Q35 ✅) |
| Asset huquqi | usage rights | manba/litsenziya, kanal/hudud/release, muddat/revoke va hosila lineage; tozalovchi yuklovchi bilan bir odam emas |
| Propagation | live revision propagation | eski offer yoki huquq ta’siridagi ad/landing/approval’ni topish, invalidation va boshqariladigan update/pause |
| Oltin matnlar | golden copy | owner tasdiqlagan til/brend namunalari; yangi offer yoki policy dalili emas |
| Ko‘r-ko‘rona test | blind test | baholovchilar qaysi model yozganini bilmaydi |
| Roster / deputy | coverage register / backup person | primary, o‘rinbosar, qamrov va muddatlar; owner-only vakolat avtomatik o‘tmaydi |
| Responsibility assignment | responsibility assignment | `technical_operator`, `finance_owner`, `privacy_owner`, `independent_reviewer` — roster yozuvi, Telegram ruxsati emas |
| ACK | acknowledgement | `[Qabul qildim]` yoki imzolangan alternate ACK: signalni ko‘rdim va custody’ni qabul qildim (`incident_acks`); yuborish/o‘qish ACK emas |
| `ops_responder` | ops responder flag | ACK va read-only diagnostika huquqi; owner vakolatini bermaydi |
| Severity | severity | `critical` yoki `degraded`; ACK muddati `ops.ack_minutes.<severity>` |
| Mustaqil monitor | independent off-host monitor | AMT host va Telegram’dan tashqaridagi dead-man signal va alternate channel (HG-F2-17) |
| Favqulodda kirish | break-glass | Telegram ishlamasa owner uchun 10 ta bir martalik oflayn kod ★; faqat `paperclip_ui` scope; approval/kill/vendor huquqi bermaydi |
| tg-auth / forward_auth | Telegram-based 2FA / forward auth | Caddy UI so‘rovini avval tg-auth’ga tekshirtiradi; Paperclip paroli + Telegram ✅ (Q49 ✅) |
| Cloudflare Tunnel | Cloudflare Tunnel (`cloudflared`) | `mar`, `mar2`, `mar3` uchun yagona tashqi kirish: `cloudflared` Cloudflare’ga faqat chiquvchi ulanish ochadi va so‘rovni `127.0.0.1:8080` dagi Caddy’ga uzatadi; AMT PC’da kiruvchi port ochilmaydi (Q57, ADR-033) |
| Tailscale | Tailscale (tailnet, `tag:amt`) | AMT PC’ga yagona SSH yo‘li: Tailscale siyosati (`tailscale-policy.hujson`) faqat owner qurilmalariga `tag:amt:22` ni ochadi, AMT tuguni tailnet’dagi boshqa tugunlarga ulana olmaydi; sshd faqat `tailscale0` interfeysida — `ssh.socket` drop-in’i `BindToDevice=tailscale0` (`0.0.0.0%tailscale0:22` va `[::]%tailscale0:22`, `ListenAddress` yo‘q); socket’ni `sockets.target` emas, `tailscale0` paydo bo‘lganda udev qoidasi ishga tushiradi, LAN NIC’da ufw ikkinchi qatlam — SSH faqat Tailscale orqali, faqat kalit, root login yo‘q; Tailscale SSH funksiyasi o‘chiq (`--ssh=false`) (Q58, ADR-033) |
| Omada VLAN/ACL | Omada VLAN and gateway ACL | ER605 v2.0 + SG2428P v5.30 va apparat controller (OC200/OC300): AMT PC alohida VLAN’da, ofis LAN’i bilan ikki tomonlama yopiq, controller va boshqaruv IP’lari yopiq, faqat internet ochiq; AMT uchun port forward/DMZ/UPnP yo‘q, IPv6 o‘chiq; controller AMT PC’da emas (Q59, ADR-033) |
| Cloud password attestatsiyasi | cloud-password attestation | owner/ads_approver Telegram two-step verification yoqqanini tasdiqlashi (`people.cloud_password_attested_at`); yo‘q bo‘lsa approval tugmalari va tg-auth rad |
| Flag | person flag | rol ichidagi qo‘shimcha huquq; faqat yaroqli membership bo‘lsa ishlaydi (`person_flags`) |
| Yurak urishi / routine / adapter | heartbeat / routine / adapter | Paperclip agentining uyg‘onishi; jadval bo‘yicha vazifa; agent qaysi runtime’da yurishi (`claude_local`, `hermes_gateway` va boshqalar) |
| Managed runner | managed runner | root fixed entrypoint; har rolni o‘z UID’ida yurgizadi; ixtiyoriy buyruq yo‘q |
| Ichki tool’lar | internal tools | `creative.register`, `review.*`, `change_set.record_outcome`, `experiment.*`, `evo.signal.submit` — tashqi ta’sirsiz, audit bilan |
| ZDR | Zero Data Retention | OpenRouter rejimi; akkaunt darajasida yoqilmaydi, so‘rov darajasida ham talab qilinmaydi (Jev uchun owner rad etgan, G14); har so‘rovda `data_collection: deny` (Q44★) |
| C05 / C07 / C12 | chain recipes | fikrlash kutubxonasi retseptlari: KPI tushishi RCA, haftalik reklama tahlili, oylik retro (Q13 ✅) |
| `wh.metrics` | canonical metric endpoints | agentlar va dashboard bir xil qiymatni oladigan nomlangan metrika katalogi; formula BUSINESS_CONTRACT’dan |
| `v_pipeline_cohorts` | kill-criteria input view | pipeline × event-week: qualified CPL, baseline revision, `data_status`, exposure |
| Workflow / run / step | workflow / run / step | versiyalangan ish ta’rifi; uning bitta durable bajarilishi; run ichidagi qadam (`amt-workflow` ledger’i haqiqat manbai, I16) |
| Handoff | handoff | agentlar orasidagi natija; qabul qiluvchi tekshiradi va `accepted`/`rejected` qayd etadi (I18) |
| Candidate / manifest | candidate / manifest | izolyatsiyada tayyorlangan o‘zgarish va uning barcha artefakt/config/evaluator digest’larini bog‘lovchi immutable ro‘yxati |
| Release sinfi | release class | `normal` — `killed` paytida rad; `recovery` — manifest’da e’lon qilingan, faqat containment, reconciliation yoki oldin tekshirilgan release’ni tiklaydi, `killed` paytida ham ruxsat |
| Release controller | `amt-release` | deterministik root publisher: faqat `release_approvals` yozuvi va owner imzolagan `release-*` tag bog‘langan manifest digest’larini chiqaradi |
| Release tasdig‘i | release approval | `/release approve <candidate_id>` (typed code) bilan yaratilgan `release_approvals` yozuvi (HG-REL-01); tag nomi vakolat emas |
| Bir marta build | build_once_promote | sinalgan artefakt aynan chiqariladigan artefakt; qayta build yo‘q |
| Himoyalangan sirt / o‘zgarish sinfi | protected surface / change class A–E | release controller, kill/control, policy, budget, RBAC, verification va boshqalar — faqat E sinfi (typed code + mustaqil inson review + owner) |
| Harness handover | harness handover | controller almashinuvi: inventar, disposition, drain, epoch++, migration, reconcile (WF-E02) |
| Sandbox / mustaqil verification | sandbox / independent verification | production credential’siz build muhiti (`amt-sandbox`); muallifdan mustaqil suite va holdout (`amt-verify`) |
| Evolution signali | evolution signal | yaxshilash zarurati dalili; `problem_fingerprint` bo‘yicha dedup; WF-E01 kirishi |
| Yaxshilanish xotirasi | improvement memory | dalilli yozuvlar; faqat `accepted` va guidance’ga yaroqli saboq agent ko‘rsatmasiga aylanadi (I24) |
| Readiness | configuration/business closure | owner/source/evidence bilan noma’lumlarni yopuvchi reyestr; uydirma default emas |
| Readiness profili | readiness profile | gate DAG’i (F1_AUTH … AUTO_RELEASE_ENABLE); har kalitda bitta gate, meros tranzitiv |
| Immutable bundle / ACK | approved release / service acknowledgement | runtime read-only code/config revision va uni olgan servis dalili |
| RBAC | role-based access control | runtime manbai `amt.people` + `amt.roles`; YAML bir martalik seed/eksport, qayta yuklanmaydi |
| HUMAN_GATE / AT | human gate / acceptance test | owner qadamining vakolati va kuzatiladigan dalil bilan test; yozilgan test PASS degani emas |
| RPO / RTO | recovery point / recovery time objective | RPO — ma’lumot yo‘qotish oynasi: eng yangi yaroqli lokal snapshot’ning (`amt` dump’i tugagan va `MANIFEST` tekshiruvidan o‘tgan) consistency point’idan mantiqiy xatogacha bo‘lgan vaqt; host yo‘qolishi — Q55 doirasi; qiymatlar `recovery.*` readiness’da sekundlarda |
| Lokal snapshot | local snapshot | `amt-backup` har kecha 02:00 va har upgrade oldidan shu RAID1’dagi har run uchun alohida `/var/backups/amt/<YYYY-MM-DDTHHMMZ>-<nightly\|pre-upgrade\|catchup>` katalogiga yozadigan shifrlanmagan nusxa; `MANIFEST` sha256 bilan, 7 kun saqlanadi; faqat mantiqiy xatodan himoya; AMT PC’dan tashqarida nusxa yo‘q (Q55) |
| `restore_drill` | restore drill environment | muhit nomi ([environments.yaml](../09_Config_Templates/environments.yaml)), jadval id’si emas: AMT PC’dagi izolyatsiyalangan systemd-nspawn konteyneri (root; lokal snapshot `--bind-ro` bilan; `--private-network` — tarmoq yo‘q; o‘z `/run`, `/var/lib` va PostgreSQL cluster; ichida Docker yo‘q — Langfuse omborlari bir xil pinned versiyadagi oddiy jarayonlar; production control socket va kill latch ulanmaydi) — choraklik to‘liq mashq: lokal snapshot’dan to‘liq restore, owner eksport qilgan PII’siz manba eksportidan qayta qurish (CAPI qayta yuborish konteyner ichidagi sintetik endpoint’ga), fixture’larda kill A/B, schema-aware rollback (`recovery.full_drill`, HG-F6-03); PAUSED Meta test integratsiyasi bu yerda ham, `staging` da ham emas — production’da global `shadow` rejimida, F3-AT-05 dagi `origin=test` istisnosi bo‘yicha; live credential, job va egress yo‘q, `killed` bilan boshlanadi |
| `restore_check` / `kill_drill` | schedule ids | [operations.yaml](../09_Config_Templates/operations.yaml) `schedule` id’lari, muhit emas: `restore_check` — har kuni 04:30 muddat tekshiruvi (03:30 dagi avtomatik xavfsizlik yangilanishlaridan keyin); `recovery.restore_check` dalili P25D yoki undan eski bo‘lsa lokal snapshot’dan `restore_test` muhitiga (alohida `amt_restore_test` bazasi; servis, credential, job va egress yo‘q) izolyatsiyalangan DB restore — taxminan oyiga bir marta, har doim P30D ichida. `kill_drill` — har kuni 10:00 muddat tekshiruvi; `recovery.full_drill` dalili P75D bo‘lganda va P83D dan har kuni ops-bot owner’ga eslatadi, owner choraklik to‘liq mashqni `restore_drill` konteynerida P92D ichida belgilaydi va unda ishtirok etadi |
| `off_host_flows` | off-host flows (◇ P-33) | `privacy-policy.yaml#off_host_flows`: AMT PC’dan chiqadigan ish oqimlari — off-host monitor’ga heartbeat (holat, backlog soni, `capi_terminal_before`, audit zanjiri boshi — seq va hash) va control journal (hodisa ID, rejim va vaqt) va rol o‘zgarishi ko‘zgusi (hodisa ID, rol, amal, vaqt va opaque `person_ref`; tg_id va ism yo‘q), GitHub’ga `roles.yaml` eksport PR’i, git’dagi build dalili, Telegram xabarlari, OpenRouter’ga sanitizatsiyalangan so‘rovlar, Meta’ga CAPI eventlari va executor’ning Meta Marketing API yozuvlari (budget/status o‘zgarishlari, huquqi tasdiqlangan asset’larning kreativ yuklanishi), ops-bot qabul qilgan foto/videolarning Google Drive’ga yuklanishi, amoCRM yozuvlari va PR qoralamalari. Ular backup nusxasi emas: Q55 backup nusxasining AMT PC’dan chiqishini taqiqlaydi; ro‘yxatda yo‘q oqim qo‘shilmaydi. ◇ P-76 ro‘yxatni servis reyestri egress’i bilan to‘ldiradi: Cloudflare edge’da TLS tugashi (`mar*` va webhook tanalari edge’da ochiq), Tailscale transporti, read so‘rovlari (Meta, amoCRM, Umami, Clarity, Google Drive, landing delivery holati, OpenRouter usage, GitHub release), FE’dagi `cand/*` push, package proxy va engineering LLM (OD-02); har qatorda `by` (servis yoki builder/owner) va `direction` (`send`/`read`/`transport`), egress’i bor har servis kamida bitta qatorda (G06) |
| `capi_terminal_before` / `capi_dispatch_lease` | CAPI host-loss fields | [operations.yaml](../09_Config_Templates/operations.yaml) `host_loss`: `capi_terminal_before` — heartbeat’dagi vaqt, undan oldingi hech bir manba o‘zgarishi endi avtomatik yuborilmaydi (avtomatik yuborilishi mumkin bo‘lgan eventlarning eng erta manba o‘zgarishi va manba sinxron watermark’ining kichigi); `capi_dispatch_lease` — capi-bridge faqat ACK olgan oxirgi heartbeat’ning `observed_at` vaqtidan beri lease (ikki heartbeat oralig‘i) o‘tmagan bo‘lsa yuboradi (`amt.monitor_acks`). Host yo‘qolsa qayta yuborish shu ikkisiga tayanadi, Meta dedup’iga emas ([TRACKING_CAPI](../03_Architecture/TRACKING_CAPI.md) §8) |
| Credential inventari | credential inventory | har sirning egasi, muddati va rotatsiya qadamlari; T-30/T-7/T-1 alertlari (`ops.credential_inventory`) |
| PII / consent custody | personal data / purpose-based permission custody | kontakt va hujjatlar manba custody’sida; agent faqat sanitizatsiyalangan ref va agregat bilan |
| Premortem / red team | premortem / red team | “loyiha barbod bo‘ldi” deb sabablarni oldindan topish; mustaqil kontekstda buzishga urinish |
| Runbook / ADR | runbook / Architecture Decision Record | qadam-baqadam operatsion ko‘rsatma; arxitektura qarori yozuvi |
| AdClaw `reference_only` | external design reference | tanlangan g‘oya/material manbai; production runtime yoki Paperclip/Hermes almashtirish qarori emas |
