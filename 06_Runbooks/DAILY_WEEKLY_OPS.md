# RUNBOOK — Kundalik, haftalik va oylik production ish ritmi

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Barcha vaqtlar **Asia/Tashkent**, host UTC. **Jadvalning yagona manbai — [operations.yaml](../09_Config_Templates/operations.yaml) `schedule`**; bu runbook va TEAM, F4, agent nizomlari, TELEGRAM, WF-* undan boshqa vaqt yozmaydi. Bu hujjat real timer yoki xabar yubormaydi; odamlar nima qilishini tushuntiradi. Ritm qatorlarini o‘zgartirish config PR orqali.

Roster: `amt.people` + `amt.roles` (identity faqat shu yerda); readiness’da faqat opaque `person_ref`: `ops.intake_responders`, `ops.ads_handback_roster`, `ops.sale_handback_roster`, ACK muddatlari `ops.ack_minutes.<severity>`, eskalatsiya `ops.escalation`. Owner kuniga bir marta kirishi favqulodda qamrov o‘rnini bosmaydi.

## Kun davomida

| Vaqt (`schedule.id`) | Kim | Ish va xavfsiz qaror |
|---|---|---|
| uzluksiz | mustaqil monitor + primary/deputy (`ops_responder`) | landing/intake backlog yoshi, last-success/freshness, host, elektr (`ALERT_HOST_POWER`) va lokal snapshot, spend himoyasi; ACK `[Qabul qildim]`; ACK bo‘lmasa eskalatsiya |
| har sync sikli (`exposure_guard`) | sync-worker | sarf bor, qualified nol yoki past N → scale blok + `ALERT_ZERO_QUALIFIED_EXPOSURE`; haftalik job kutilmaydi |
| 02:00 (`backup`) | `amt-backup.timer` (systemd) | lokal snapshot (shu RAID1’da, 7 kun, Q55); keyin snapshot yoshi, hajmi va `MANIFEST` sha256 tekshiriladi; deadline o‘tsa yoki joy yetmasa `ALERT_BACKUP_STALE` + catch-up ([BACKUP_RESTORE §3](BACKUP_RESTORE.md)) |
| 08:00 (`fleet_ask`) | ops-bot → fleet_operator | to‘liq fizik snapshot so‘rovi (◇ P-06; owner ★ vaqtlari 09:00/12:00/14:00; ⧗ OD-14) |
| 08:30 (`media_buyer_daily`) | media-buyer | sotuv va capacity’ga bog‘liq bo‘lmagan takliflar: spend/cap/MTD + pending, status, tracking/freshness, drift; sale readiness’siz increase yo‘q |
| 09:00 (`fleet_remind`) | ops-bot | yaroqli snapshot hali yo‘q bo‘lsa eslatma; hold ertalabdan amal qiladi |
| `fleet_snapshot_accepted` hodisasi (`rent_capacity_review`) | media-buyer | rent takliflari faqat bugungi snapshot revision’i bilan |
| 09:00 (`sale_ready`) | sales_lead | `/sale_ready` snapshot (◇ P-22); F6_STEP2 dan sale byudjetini oshirish uchun majburiy; eskirsa `ALERT_SALE_READINESS_STALE` |
| 09:30 (`sale_ready_cutoff`) | ops-bot → sales_lead, owner | yaroqli sale readiness snapshot yo‘q → sale byudjetini oshirish va rent→sale ko‘chirish blok; `ALERT_SALE_READINESS_STALE` sales_lead va owner’ga ([sale-readiness.yaml](../09_Config_Templates/sale-readiness.yaml) `cadence`) |
| 09:30 (`tracking_health`) | sync-worker | tracking gate va accepted→CRM reconciliation; 1 kun fail → alert, 2 ketma-ket kun → `read_only`; stale/missing → risk oshiruvchi dispatch darhol rad |
| 09:45 (`batch_cutoff`) | gateway | 10:00 batch uchun ko‘rib chiqilgan itemlar shu paytgacha; keyingilari alohida item, o‘z `presented_at` va TTL bilan |
| 10:00 (`change_set`) | owner / ads_approver | kunlik change set (Q38 ✅): har bandni ✅/❌/✏️; dispatch paytida joriy guard’lar qayta tekshiriladi |
| 14:00 (`fleet_escalate`) | ops-bot → owner | yaroqli snapshot yo‘q → bugun barcha odatiy rent budget o‘zgarishlari hold; protective controls ta’sirlanmaydi |
| 18:00 (`sales_digest`) | ops-bot → sales_lead | PII’siz digest ★: qualification kechikishi/QA, contract/paid/fulfilment/cancel-refund; feedback tugmalari |
| `presented_at` + 12 soat | gateway | tasdiqlanmagan item `expired` (`approval_ttl_hours: 12`); avtomatik tasdiq yo‘q; timeout remote `uncertain` bo‘lib qoladi |

Real foto/video istalgan vaqtda yuklanishi mumkin (rights/source va hash bilan; mijozga chiqadigan xabar yo‘q); haftalik majburiy eslatma pastda.

**Fleet hisobot:** append-only — `report_id`, `observed_at`, `submitted_at`, reporter, fizik invariantlar. Wizard `rented/reserved/available/maintenance` va waitlist maydonlarini so‘raydi; `serviceable_bikes` va `total_fleet` hisoblanadi va oldingi yaroqli snapshot bilan solishtiriladi ([capacity-policy.yaml](../09_Config_Templates/capacity-policy.yaml)). Tuzatish `supersedes_report_id` bilan; kech kelgan eski `observed_at` “yangi” bo‘lmaydi; eskirgan snapshot hech qachon yaroqli emas. Capacity band’larini snapshot’dagi `waitlist_eligible_ready` boshqaradi; CRM waitlist statuslari faqat cross-check (⧗ OD-07 vaqtinchalik qoidasi). Capacity hold barcha odatiy rent budget harakatini ushlaydi; protective pause alohida yo‘l. Rent byudjetini sale’ga ko‘chirish `sale.readiness` va rolling24h ≤20% (◇ P-01) shartiga bo‘ysunadi.

**Change set’ni ko‘rishda (30 soniyalik checklist):**
1. Kutilgan effekt aniq va o‘lchanadimi (`expected_effect`)?
2. Rollback bormi?
3. Kreativ/ad uchun exact immutable asset/payload + offer revision’iga mustaqil Reviewer `pass` bormi? Inson til tekshiruvi kerak bo‘lsa — alohida shart, Reviewer o‘rnini bosmaydi.
4. Narx/aksiya offer registry’dagi faol revision’ga mosmi?
5. Ijara: waitlist uzun paytda byudjet oshirilmayaptimi; bugungi snapshot bormi?
6. Pul/cap va action vakolati to‘g‘rimi?

Shubha → ✏️ izoh yoki ❌. **❌ bosish — normal holat**; deyarli hech qachon ❌ bo‘lmasa, bu rubber-stamp signali (Q38 ✅). Owner-only harakatlar to‘liq ro‘yxati — [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) `trust_ramp.never_auto` (jumladan `campaign_create`, `campaign_activate`, `adset_duplicate`, `offer_change`, `landing_pr_merge`, `events_manager_change`, `amo_pipeline_change_proposal`, `role_change`, `kill_switch`, `control_resume`). Approver favqulodda navbatchiligi owner-only vakolatni almashtirmaydi.

## Haftalik

| Vaqt (`schedule.id`) | Kim | Natija |
|---|---|---|
| Oyning birinchi dushanbasi 07:30 (`qualified_volume_check`) | sync-worker → owner | Q29.1: pipeline bo‘yicha crm_confirmed Meta-atributsiyali landing murojaatlari oldingi kalendar oyida (◇ P-56); `QualifiedLead` ga o‘tish — ketma-ket 2 o‘lchovda ≥ max(200, vendor talabi), `Lead` ga qaytish — birinchi past o‘lchovda; almashtirishni faqat owner qiladi (`events_manager_change`, ◇ P-45) |
| Du 07:30 (`kill_criteria`) | sync-worker | KC-01/KC-02: `qualified_cpl_event_week` (`amt_ro.v_pipeline_cohorts`), min N va `data_status` qoidalari; trigger → pipeline L0 + epoch/outbox + handback ACK ([KILL_SWITCH §5](KILL_SWITCH.md)) |
| Du 11:00 (`weekly_plan`) | cmo | haftalik reja hisobotdan keyin (WF-B06 S05); owner vakolati kerak bo‘lgan bandlar `plan_authority_items` orqali; yangi vakolat o‘zi ochilmaydi |
| Du 08:00 (`weekly_report_submit`) | funnel-analyst | `report.submit`: BLUF ≤250 so‘z + to‘liq hisobot |
| Du 08:00–09:00 (`weekly_report_review`) | reviewer | aynan shu matn bo‘yicha Kernel/PII/da’vo tekshiruvi |
| Du 09:00 (`weekly_report`) | ops-bot | Telegram’da BLUF, Paperclip’da to‘liq hisobot (Q24 ✅) |
| Du 09:30 (`content_reminder`) | ops-bot → content_contributor | haftalik real foto/video (Q20/Q29.3 ✅, Drive `AMT/raw`); material kelmasa owner yoki kontent egasiga ko‘rinadigan vazifa (UAT-31) |
| Chorshanba 15:00 (`dependency_check`) | amt-workflow | WF-E03: `VERSIONS.lock.md` va rasmiy advisory tekshiruvi |
| har hafta | technical_operator; jismoniy ish faqat owner (Q52) | RAID holati (`cat /proc/mdstat` → `[UU]`), UPS holati va batareya (`upsc`, USB port bo‘lsa), disk bo‘sh joyi va lokal snapshot hajmi (`df -h`, `/var/backups/amt`); og‘ish → [INCIDENTS](INCIDENTS.md) INC-25 yoki INC-11 |
| Ju 16:00 (`cmo_status`) | cmo | qisqa status ★: ochiq proposal’lar va kutilayotgan qarorlar |
| hafta davomida | sales_lead, fleet_operator | qualification QA, kechikish/backlog, data provenance; tasdiqlangan exposure va insident harakatlari |
| hafta yakuni | owner | spend/budget/rezerv reconcile, offer muddati va revocation, operator qamrovini ko‘rish |

**Haftalik hisobot tarkibi (Q24 ✅; [business-policy.yaml](../09_Config_Templates/business-policy.yaml) `weekly_report_metrics`):** qualified lead (sale/rent), qualified CPL, lead→shartnoma, sarf/limit, eng yaxshi va eng yomon kreativ (min N bilan), keyingi hafta eksperimentlari, ijarada bandlik/waitlist; qo‘shimcha — data bo‘shliqlari va freshness, Trust Ramp holati, mavjud bo‘lsa cash/contribution. Har raqam manbali; unknown/inconclusive ochiq qoladi, dalilsiz yutuq yozilmaydi. Diff-in-diff sabab isboti deb berilmaydi.

**Kill criteria (Q31 ✅):** qualified CPL >25% yomonlashishi ikki hafta ketma-ket — majburiy trigger. Owner F5’da comparable baseline/oyna/sample va hisob dalilini tasdiqlaydi; undan voz kechish yo‘q. Kerakli dalil bo‘lmasa live readiness blok.

**F5 shadow haftasida o‘lchanadi:** “10:00 SHADOW change set 7/7 kun yetkazildi”; “Du 09:00 haftalik hisobot: oynadagi rejalangan run’lar 100%”; ixtiyoriy “08:00 fleet so‘rovi 7/7 yuborildi”. Shadow baholash agregatsiyasi — ⧗ OD-09.

## Oylik va choraklik

| Qachon (`schedule.id`) | Mas’ul | Ish | Dalil |
|---|---|---|---|
| Oy 1-kuni (`spend_cap_update`) | owner (HG-OPS-01) | Meta spending limit’ni yangilash — quyidagi qadamlar | API read-back = kutilgan qiymat |
| Oy 1-kuni (`retro`) | cmo + funnel-analyst → owner | C12 retro ([WF-O05](../09_Config_Templates/workflows/WF-O05.yaml)): natija; AI sarfi USD 150/oy (15 000 USD minor) kalit cap’iga nisbatan — har agent/media actual + reserved va provider billed; paid Meta USD 1 500/oy (150 000 USD minor) alohida; TCO (`budget.tco`: host — owner PC, ikkinchi disk, UPS, Omada controller; elektr va ofis interneti; monitor, litsenziya, inson ops, kredit fee/soliq/FX); approval statistikasi; insidentlar; qabul qilingan saboqlar → WF-E04 | retro hujjati |
| Oy 1-kuni (`credential_expiry_check`) | technical_operator | credential inventari; T-30/T-7/T-1 alertlari ([BACKUP_RESTORE §7](BACKUP_RESTORE.md)) | `ops.credential_inventory` |
| OpenRouter reset’idan / oy chegarasidan keyin | owner | budget sabab pauzadagi agentlarni ko‘rib, har biri uchun `agent_resume` (`/agent resume <agent_slug\|cmo.chat\|cmo.workflow>`, typed code); owner’siz avtomatik qayta yoqilish yo‘q (`resume_after_reset_requires_owner: true`; ★ watchdog standarti). Langfuse/usage uzilishi sabab pauza esa reconciliation tiklangani isbotlangach avtomatik qaytadi (`billing_unreliable_resume`) | `agent_resume` audit |
| har kuni 04:30 muddat tekshiruvi (`restore_check`, WF-O03) | technical_operator; owner natijani ko‘radi | `recovery.restore_check` dalili P25D yoki undan eski bo‘lsa (taxminan oyiga bir marta; har doim P30D ichida): oxirgi lokal snapshot’ning `MANIFEST` sha256 tekshiruvi va AMT PC’dagi `restore_test` ga izolyatsiyalangan DB restore (`recovery.restore_check` ni yangilaydi); target vs o‘lchangan RPO/RTO; 7 kunlik retention | `build/ops/restore-checks.md` |
| oylik | owner | rol reestri: odamlar, rollar, flag’lar, muddatlar, faol bo‘lmaganlar, kim nechta tasdiq bergan, rad ulushi (Q38), handback custodian’lar ([ROLES_ONBOARDING §5](ROLES_ONBOARDING.md)) | `roles_audit` |
| oylik | owner | founder vaqti `ops.founder_time_budget` bilan solishtiriladi (ixtiyoriy; ⧗ OD-15); 2 hafta oshsa soddalashtirish ADR triggeri ([PREMORTEM](../00_Decisions/PREMORTEM.md)) | retro |
| har kuni 10:00 muddat tekshiruvi; mashq choraklik (`kill_drill`, WF-O03) | technical_operator + owner | `recovery.full_drill` dalili P75D bo‘lganda ops-bot owner’ga eslatadi, P83D dan har kuni; owner to‘liq mashqni P92D ichida belgilaydi va unda ishtirok etadi: AMT PC’dagi izolyatsiyalangan `restore_drill` konteynerida (alohida host yo‘q, Q55; tarmoq yo‘q) lokal snapshot’dan restore, PII’siz manba eksportidan qayta qurish (CAPI qayta yuborish konteyner ichidagi sintetik endpoint’ga), fixture’larda simulyatsiya qilingan Meta endpoint’iga qarshi kill A/B, schema-aware rollback (`recovery.full_drill` ni yangilaydi) + production’da Tailscale orqali SSH bilan `amt-kill --self-test` (★ choraklik; ◇ P-12) | `build/ops/kill-drills.md` |
| choraklik | owner + cmo | model/prompt/adapter regressiyasi (WF-E03/WF-E04), premortem qayta ko‘rish (birinchisi 2027-01-15, keyin 3–4 oyda; sana kelishi avtomatik dalil emas), keyingi chorak rejasi | PREMORTEM |
| Step 1 + 21 kun | owner (HG-F6-05, ◇ P-17) | targetolog `ads_approver`: uzaytirish, almashtirish yoki tugatish; handback roster qayta tasdiqlanadi. Rol Step 1 + 28 kunda tugaydi; 7 kun oldin `REMINDER_ROLE_EXPIRY`; F7 kutilmaydi | `ops.ads_handback_roster` |

**HG-OPS-01 qadamlari (◇ P-02):**
1. Ops-bot `REMINDER_SPEND_CAP_RESET` yuboradi: `spend_cap_native = provider_counter_now_native + to_native(max(0, monthly_cap_minor - verified_mtd_minor - safety_margin_minor))`, provider minor birligiga pastga yaxlitlangan (`cap_update_formula`, `cap_update_rounding`). Qiymat akkaunt valyutasida va USD’da ko‘rsatiladi; valyuta, timezone va counter bazasi `budget.ads_limits`dan.
2. Owner Ads Manager’dagi account spending limit sozlamasida (Billing bo‘limi [?] — joriy UI’da tekshiriladi) shu qiymatni qo‘yadi va `[Qo‘ydim]` bosadi.
3. `sync-worker` (WF-O04 S03) API orqali har sync siklida qayta o‘qiydi; qiymat kutilganiga teng bo‘lishi shart (`provider_spend_limit_readback_required`). Limit “Change/Reset” qilingan bo‘lsa counter qayta o‘qiladi — reset `amount_spent` ni nolga tushirishi mumkin [?].
4. Oy boshida sarflangan pul ustiga yana to‘liq USD 1 500 (150 000 USD minor) qo‘shilmaydi. Cap oshirish faqat yangi owner Q bilan.
5. Qadamlar [WF-O04](../09_Config_Templates/workflows/WF-O04.yaml) run’i sifatida kuzatiladi (◇ P-52): hisob 1-kuni 00:00 da; eslatma 10:00 dagi change set bilan takrorlanadi; 1-kun oxirigacha mos read-back bo‘lmasa `ALERT_SPEND_CAP_HEADROOM` critical alternate channel’da. Kutilgan cap (`vendor.meta_cap`) oldingi qiymatda qoladi va faqat yangi formula qiymatiga teng read-back bilan almashadi (`budgets.yaml#ads.expected_cap_switch`) — `[Qo‘ydim]` dan oldin to‘g‘ri qo‘yilgan qiymat ham qabul qilinadi; oy almashishining o‘zi `read_only` bermaydi; ikkalasiga ham teng bo‘lmagan qiymat `provider_limit_read_only` (INC-12).

## Hodisa va owner unavailable

Insident severity’si bo‘yicha (`critical | degraded`) primary ACK qiladi; muddatda ACK bo‘lmasa deputy → owner. Owner javob bermasa: oldindan tasdiqlangan protective controls va safe state ishlaydi, yangi approval/scale/model fallback ochilmaydi, inson ad custody’si faqat oldindan Ads Manager vakolati bor odamda. Deputy kill — ⧗ OD-04; qaror bo‘lmaguncha deputy kill qilmaydi. Missed alert “yuborildi” deb yopilmaydi. Telegram yoki asosiy host yo‘q bo‘lsa mustaqil alternate channel. Accepted lead backlog, spend cap yoki remote `uncertain` attempt — [INCIDENTS](INCIDENTS.md); owner kill/resume — [KILL_SWITCH](KILL_SWITCH.md).

## Owner uchun “agar …”

- **Ko‘p ❌ bosyapman** → sababini CMO’ga yozing (Hermes, DM); CMO `evo.signal.submit` bilan signal beradi, skill/brief o‘zgarishi WF-E04 orqali.
- **Hisobot raqami shubhali** → Hermes’dan manbasini so‘rang; har raqam manbali bo‘lishi shart.
- **Hammasini to‘xtatish kerak** → `/pause_all` (standart A — faqat AI; B — AI + AMT managed reklama); Telegram ishlamasa SSH (Tailscale) `amt-kill`.
- **Kill criteria ishga tushdi** → pipeline avtomatik `L0_shadow`; handback custodian qo‘lda boshqaradi; C05 RCA’dan keyin `/takeover` va `/mode <pipeline> L1`.
- **Narx o‘zgardi** → `offers.yaml` PR (owner merge); eski narxli ad/landing/approval topiladi (`ALERT_OFFER_REVOKED`), yangi activation bloklanadi, Reviewer qayta tekshiradi (UAT-26).
- **Bugun fleet snapshot yo‘q** → rent hold o‘z-o‘zidan; fleet_operator’ga murojaat; eski raqamni “bugungi” deb kiritmang.
