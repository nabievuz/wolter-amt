# RBAC — odamlar, agentlar va tasdiq vakolati

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Runtime manba — DB `amt.people`, `amt.roles` va `amt.person_flags`. [roles.yaml](../09_Config_Templates/roles.yaml) faqat bir martalik seed va keyingi eksport (`mode: seed_once_then_export`, `export_must_not_reseed: true`); `people: []` placeholder hech kimni aktiv qilmaydi. Action approverlari va kvorum — [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) (kvorumning yagona manbai `change_set.quorum`); buyruq, default flag va ko‘rish matritsasi — `roles.yaml` `role_permissions`. Bu ikki manba turli vazifani bajaradi. Owner qarorlari: ✅ Q47 (rollar aniq nomlanadi, bir rolda bir necha odam, ops bot deterministik), ✅ Q49 (Telegram orqali 2FA); rol slug’lari ★. Buyruq sintaksisi va UX — [TELEGRAM](TELEGRAM.md); action ijrosi — [GUARDRAIL_GATEWAY](GUARDRAIL_GATEWAY.md).

## 1. Rollar, mas’uliyat va flaglar

| Rol | Vakolat | Muhim chegara |
|---|---|---|
| `owner` | barcha owner-only/NEVER_AUTO action (§2.1); rol va flag; kill, resume, mode, takeover, graduation; budget override; offer va landing merge; release va upgrade proposal tasdig‘i; asset rights | yagona faol owner o‘chirilmaydi (§4.6) |
| `ads_approver` | `creative_activate`, `budget_change`, `entity_pause`, `entity_activate`, `ad_create`, `experiment_exposure` | birinchi activation (`campaign_activate`), yangi campaign, `adset_duplicate` va boshqa owner-only action yo‘q |
| `sales_lead` | qualified ta’rifi, SOP va QA egasi (`business.qualification`, `sales.sop`, `sales.qa`); kunlik `/sale_ready`; 18:00 digest va feedback | mijozga xabar yoki sotuvchiga task yo‘q (✅ Q18/Q42) |
| `fleet_operator` | kunlik fizik fleet snapshot va tuzatish; `fleet.freshness`, `fleet.waitlist` | budget yoki action tasdig‘i yo‘q |
| `content_contributor` | foto/video’ni quarantine’ga yuklash, manba va rozilik ma’lumoti | o‘z yuklaganini clear qila olmaydi |
| `viewer` | hisobot va ruxsatlangan spend; flag bo‘lsa baholash, til tekshiruvi yoki ACK | approval vakolati yo‘q |

Bir odam bir necha rolga, bitta rol bir necha odamga ega bo‘lishi mumkin. Tasdiq uchun rolning bitta faol a’zosi yetarli (kvorum 1). `owner` rolida bir necha kishi texnik jihatdan mumkin, lekin tavsiya etilmaydi ★; yangi owner faqat mavjud owner ikki bosqichli tasdig‘i bilan qo‘shiladi. `people.status != active` barcha membership va flagni rad qiladi; har membership `active` va `expires_at > now` bo‘lishi kerak; bir rol expiry’si boshqa amaldagi rolni yo‘qotmaydi. Effective permission — yaroqli rollar union’i va §1.3 dagi effective flaglar; deny, `killed` holati va policy freshness har qanday union’dan ustun, flag owner-only cheklovni ochmaydi.

`person_revision`, tegishli membership’ning `role_revision`i va statik role-policy revision effective role binding’ga kiradi. Qaror vaqtida va har dispatch, retry, rollback oldidan joriy rol qayta tekshiriladi. Cache ishlatilsa revocation epoch va qat’iy invalidation bo‘ladi; chegarasiz stale role cache bilan ijro yo‘q. Person suspend tg-auth sessiyalari, ops callback, gateway approval va Hermes allowlist’ni darhol bekor qiladi; navbatdagi approval tirilmaydi.

### 1.1 Mas’uliyat tayinlovlari

`roles.yaml` `responsibility_assignments` — Telegram huquqi emas, roster tayinlovi; owner ularni o‘zi ham ushlashi mumkin.

| Tayinlov | Vazifa | Telegram’dagi ko‘rinishi |
|---|---|---|
| `technical_operator` | AMT host, restore, credential rotation va drill’lar | `viewer` roli + `ops_responder` flag |
| `finance_owner` | moliyaga oid readiness qiymatlarini tasdiqlaydi (masalan `business.contribution_policy`) | o‘z roli bo‘yicha |
| `privacy_owner` | privacy readiness (`privacy.purposes`, `privacy.retention`, `privacy.breach_response`) va breach jarayoni | o‘z roli bo‘yicha |
| `independent_reviewer` | himoyalangan sirt (E sinfi) o‘zgarishlarining muallif bo‘lmagan inson reviewer’i (⧗ OD-12; `engineering.independent_reviewer`) | o‘z roli bo‘yicha |

Shaxs identifikatorlari faqat `amt.people`/`amt.roles`da. Readiness roster kalitlari (`ops.roles_owner`, `ops.roles_roster`, `ops.intake_responders`, `ops.ads_handback_roster`, `ops.sale_handback_roster`, `engineering.independent_reviewer`) faqat opaque `person_ref` saqlaydi (`operations.yaml` `roster_source`). Agent o‘qiydigan config yoki view’da xodim ID’si yoki ismi yo‘q.

### 1.2 Readiness tasdiq vakolati

`readiness.yaml`da `accountable_role` faqat `owner`, `sales_lead`, `fleet_operator`, `technical_operator`, `finance_owner`, `privacy_owner` yoki `independent_reviewer` bo‘ladi. `approved_by` — `approved_at` paytida shu rol yoki tayinlovni ushlab turgan shaxs va dalilni tayyorlagan shaxsdan farqli; `co_signers` ham tasdiqlaydi. Agentlar va builder faqat `prepared_by` bo‘ladi, hech qachon tasdiqlamaydi. Agent task, Hermes chat, Paperclip izohi, emoji yoki LLM matni inson tasdig‘i emas.

### 1.3 Flaglar

Flaglar rolga bog‘langan (`flag_rules`): effective flaglar = yaroqli membership’larning default flaglari ∪ `person_flags`dagi `expires_at` kelajakda bo‘lgan flaglar; kamida bitta yaroqli membership bo‘lmasa hech qanday flag ishlamaydi (`requires_valid_membership: true`). Saqlash: `person_flags(tg_id, flag, granted_by, granted_at, expires_at, flag_revision)`. O‘zgartirish: `/role flag add|remove <tg_id> <flag> [expires YYYY-MM-DD]` — faqat owner, typed code bilan (`role_change` ichidagi `person_flag_add`/`person_flag_remove`).

| Flag | Ma’no | Default (rol) | Odatiy beriladi |
|---|---|---|---|
| `paperclip_ui` | Paperclip UI, tg-auth orqali | owner | owner tanlagan shaxs |
| `langfuse_ui` | Langfuse UI, tg-auth orqali | owner | owner tanlagan shaxs |
| `dm_alerts` | alertlar DM’da | owner | ads_approver (ixtiyoriy) |
| `hermes_chat` | Hermes CMO bilan suhbat | owner, ads_approver, sales_lead | — |
| `golden_copy_rater` | golden copy blind test baholovchisi | owner | targetolog (F5), HG-F5-03 baholovchisi |
| `shadow_rater` | F5 SHADOW itemlarini baholash | owner | targetolog (F5) |
| `language_checker` | birinchi jonli copy’ning ona tili o‘zbek tekshiruvi (✅ Q42) | — (owner zaxirasi faqat ◇ P-29 qabul qilingach) | targetolog F5’dan; shart `native_language_attested = uz` |
| `ops_responder` | alertni ACK qilish va read-only diagnostika | owner | technical_operator, intake primary/deputy, handback roster |
| `rights_clearer` | asset huquqi dalilini biriktirish (`/asset evidence`); clear/revoke faqat owner | owner | ixtiyoriy; yuklovchi o‘z yuklamasi uchun dalil tayyorlamaydi |

Rater, checker yoki responder flagi action approver rolini bermaydi va mustaqil Reviewer pass o‘rnini bosmaydi.

### 1.4 Owner vakolatini o‘tkazish va o‘rinbosar

Owner vakolati faqat odamga `owner` RBAC roli berilganda o‘tadi (`operations.yaml` `owner_authority_transfer`); yashirin delegatsiya yo‘q. "Operator", "deputy" yoki "texnik mas’ul" nomi owner-only huquq bermaydi. O‘rinbosar va technical_operator ACK, read-only diagnostika va eskalatsiya qiladi; owner yo‘qligida faqat oldindan ruxsatlangan protective control’lar (`operations.yaml` `protective_controls`) va human handback ishlaydi. Deputy uchun emergency kill ⧗ OD-04 (variant: `emergency_kill_ai_only` flag, faqat A rejim, typed code, avtomatik expiry, owner va off-host alert); qaror bo‘lguncha deputy kill qila olmaydi.

## 2. Action approval matritsasi

✔ — change set tugmasi bilan tasdiq; ✔² — typed code bilan ikki bosqich ([TELEGRAM §3](TELEGRAM.md)). Manba — `approval-policy.yaml` `actions`; farq bo‘lsa config ustun.

| Action | `owner` | `ads_approver` | Boshqa rol yoki flag | Avtonomiya | `review_required` |
|---|---|---|---|---|---|
| `creative_activate` — mavjud faol ad set ichidagi AD; Reviewer pass + kerakli inson til tekshiruvi | ✔ | ✔ | — | L1; L2 faqat graduation’dan keyin | true |
| `budget_change` — rolling24h ≤20%, admission va biznes natija guard’i ichida | ✔ | ✔ | — | L1; L2 faqat graduation’dan keyin | true |
| `entity_pause` | ✔ | ✔ | — | L1; L2 faqat graduation’dan keyin | false |
| `entity_activate` — oldin faol bo‘lgan campaign/ad set | ✔ | ✔ | — | L1; L2 faqat graduation’dan keyin | true |
| `ad_create` — PAUSED, exact creative, Reviewer pass + kerakli inson til tekshiruvi | ✔ | ✔ | — | L1; L2 faqat graduation’dan keyin | true |
| `experiment_exposure` | ✔ | ✔ | — | ko‘pi bilan L1 | true |
| `campaign_activate` — campaign/ad set’ning birinchi yoqilishi | ✔ | — | — | NEVER_AUTO | true |
| `campaign_create`, `adset_duplicate` | ✔ | — | — | NEVER_AUTO, PAUSED | true |
| `offer_change`, `landing_pr_merge` | ✔ | — | — | NEVER_AUTO, GitHub owner merge | true |
| `events_manager_change` | ✔ | — | — | NEVER_AUTO, `awaiting_manual → done_manual` | true |
| `amo_pipeline_change_proposal` | ✔ | — | sales_lead maslahat beradi | NEVER_AUTO, `awaiting_manual → done_manual` | false |
| `plan_authority_items` | ✔ | — | — | NEVER_AUTO | false |
| `asset_upload` | — | — | — | auto: guard + attempt + audit; Reviewer pass, inson tekshiruvi, rights | true |
| `amo_tag_write`, `amo_field_write` | — | — | — | auto: guard + attempt + audit | false |
| `protective_pause` | owner tasdiqlagan policy revision | — | — | pre-authorized, faqat pause | false |
| `asset_rights_clear`, `asset_rights_revoke` | ✔² | — | — (`rights_clearer` faqat dalil tayyorlaydi) | NEVER_AUTO | false |
| `role_change`, `kill_switch`, `global_mode_change`, `control_resume`, `pipeline_mode_change`, `takeover_scope_change`, `trust_graduation`, `budget_override`, `agent_resume` | ✔² | — | — | NEVER_AUTO | false |
| `upgrade_proposal_approval`, `upgrade_release`, `harness_handover`, `migration_drill`, `protected_surface_change`, `engineering_budget_change` | ✔² | — | `protected_surface_change` uchun qo‘shimcha mustaqil inson review’i (⧗ OD-12) | NEVER_AUTO | false |
| `readiness_signoff` | ✔² (owner accountable yoki co-signer bo‘lgan kalit; `na` — faqat `optional`; `withdraw` — istalgan kalit) | — | kalitning accountable/co-signer roli egasi ✔² (RBAC roli yoki `responsibility_assignments`); dalil tayyorlovchisi, agent va builder emas | NEVER_AUTO | false |
| Ichki tool’lar (registry, review, outcome, experiment, evo signal, workflow) | — | — | faqat agent allowlist | audit va exact revision; inson huquqi emas | — |

### 2.1 Owner-only action’lar

`approvers: [owner]` bo‘lgan barcha action’lar: `campaign_activate`, `campaign_create`, `adset_duplicate`, `offer_change`, `landing_pr_merge`, `events_manager_change`, `amo_pipeline_change_proposal`, `plan_authority_items`, `role_change`, `kill_switch`, `global_mode_change`, `control_resume`, `pipeline_mode_change`, `takeover_scope_change`, `trust_graduation`, `budget_override`, `asset_rights_clear`, `asset_rights_revoke` (`rights_clearer` faqat dalil tayyorlaydi), `upgrade_proposal_approval`, `upgrade_release`, `harness_handover`, `migration_drill`, `protected_surface_change`, `engineering_budget_change`, `agent_resume`. To‘liq NEVER_AUTO ro‘yxatining yagona manbai — `approval-policy.yaml` `trust_ramp.never_auto`; TEAM, INVARIANTS va runbook’lar undan ko‘chiradi.

Bir actor bir command revision’ga bir ovoz beradi; callback replay yoki parallel approver atomik unique transition bilan bitta qarorga keladi. Boshqa revision’dagi approval joriy revision kvorumiga kirmaydi. Telegram tasdig‘i faqat jo‘natuvchining numeric ID’si, joriy roli, cloud-password attestatsiyasi (§4.2), action, item hash, joriy nonce va expiry tekshirilgan callback bilan. Birinchi campaign/ad set activation turini agent emas, gateway `entity_type + ever_active`dan chiqaradi; `ads_approver`ning "tasdiqlayman" matni owner-only action’ni ijro qilmaydi. CMO, Analyst va CRO offer, landing yoki manual taklif berishi approval huquqi emas.

## 3. Buyruq, ko‘rish va UI ruxsatlari

### 3.1 Buyruqlar

`roles.yaml` `role_permissions.<rol>.commands` bo‘yicha. Sintaksis va natija [TELEGRAM §3](TELEGRAM.md)da.

| Buyruq | `owner` | `ads_approver` | `sales_lead` | `fleet_operator` | `content_contributor` | `viewer` |
|---|---|---|---|---|---|---|
| `/status`, `/help`, `/whoami` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| `/report` | ✔ | ✔ | ✔ (faqat o‘z `sees` qismi) | — | — | ✔ |
| `/spend` | ✔ | ✔ | — | — | — | ✔ |
| `/fleet` | ✔ | — | — | ✔ | — | — |
| `/upload` (yoki media yuborish) | —⁵ | — | — | — | ✔ | — |
| `/sales_feedback` | ✔ | — | ✔ | — | — | — |
| `/sale_ready` | — | — | ✔ | — | — | — |
| `/pause_all`, `/resume` | ✔² | — | — | — | — | — |
| `/agent resume` | ✔² | — | — | — | — | — |
| `/role add\|remove\|suspend\|resume`, `/role flag add\|remove`, `/role assign\|unassign` | ✔² | — | — | — | — | — |
| `/role list` | ✔ | — | — | — | — | — |
| `/budget raise`, `/budget engineering` | ✔² | — | — | — | — | — |
| `/mode`, `/takeover`, `/graduate` | ✔² | — | — | — | — | — |
| `/asset clear\|revoke` | ✔² | — | — | — | — | — |
| `/asset evidence` | ✔³ | ✔³ | ✔³ | ✔³ | ✔³ | ✔³ |
| `/release approve`, `/proposal approve`, `/handover approve`, `/drill accept`, `/protected approve` | ✔² | — | — | — | — | — |
| `/readiness show` | ✔ (istalgan kalit) | — | ✔⁴ | ✔⁴ | — | ✔⁴ |
| `/readiness approve\|cosign` | ✔⁴ | — | ✔⁴ | ✔⁴ | — | ✔⁴ |
| `/readiness na` | ✔² (faqat `optional` kalit) | — | — | — | — | — |
| `/readiness withdraw` | ✔² (istalgan kalit) | — | ✔⁴ | ✔⁴ | — | ✔⁴ |
| `/work`, `/decisions` | ✔ | — | — | — | — | — |

³ istalgan rolda, faqat effektiv `rights_clearer` flag’i bor shaxs (yuklovchi emas; `roles.yaml#flag_rules.flag_commands`); asset holatini o‘zgartirmaydi.
⁴ faqat kalitning `accountable_role` yoki `co_signers` rolini egallagan shaxs (RBAC roli yoki `responsibility_assignments`); `approve`/`cosign` typed code bilan; dalil tayyorlovchisi, agent va builder imzolay olmaydi.
⁵ owner yuklamaydi: `asset_rights_clear.uploader_may_not_clear` va clear faqat owner’da bo‘lgani uchun owner yuklagan media karantinda qolib ketardi; owner materialini content_contributor yuklaydi.

Flag bilan ochiladigan amallar: `rights_clearer` — `/asset evidence <asset_id>` (huquq dalilini biriktiradi, holatni o‘zgartirmaydi; yuklovchining o‘zi emas); `/asset clear` va `/asset revoke` faqat owner; `ops_responder` — alert `[Qabul qildim]` va read-only diagnostika; `shadow_rater` — SHADOW baholash tugmalari; `language_checker` — til tekshiruvi tugmalari; `golden_copy_rater` — blind test baholari; `paperclip_ui`/`langfuse_ui` — tg-auth orqali UI; `hermes_chat` — Hermes suhbati. Change set tugmalari §2 matritsasi bo‘yicha; `viewer` tugmani bossa holat o‘zgarmaydi.

### 3.2 Ko‘rish (`sees`)

Rol qaysi ma’lumotni ko‘rishi `roles.yaml` `role_permissions.<rol>.sees` bilan belgilanadi; ops-bot xabar, buyruq javobi va Hermes javobini shu ro‘yxat bilan filtrlaydi.

| Ma’lumot | `owner` | `ads_approver` | `sales_lead` | `fleet_operator` | `content_contributor` | `viewer` |
|---|---|---|---|---|---|---|
| `change_set` | ✔ | ✔ | — | — | — | — |
| `alerts` (barcha alertlar) | ✔ | — | — | — | — | — |
| `ads_alerts` | (alerts ichida) | ✔ | — | — | — | — |
| `intake_alerts` | (alerts ichida) | — | ✔ | — | — | — |
| `fleet_alerts` | (alerts ichida) | — | — | ✔ | — | — |
| `reports` | ✔ | ✔ | — | — | — | ✔ |
| `digests` / `sales_digest` | ✔ (`digests`) | — | ✔ (`sales_digest`) | — | — | — |
| `spend` | ✔ | ✔ | — | — | — | ✔ |
| `sale_readiness` | — | — | ✔ | — | — | — |
| `fleet_requests` | — | — | — | ✔ | — | — |
| `content_requests`, `upload_receipts` | — | — | — | — | ✔ | — |
| `workflow_queue`, `decisions` | ✔ | — | — | — | — | — |

Owner fleet, kontent va sale readiness holatini o‘z buyruqlari (`/status`, `/fleet`, `/decisions`) orqali ko‘radi. Flaglar qo‘shimcha yetkazish beradi: `ops_responder` egasi o‘zi javobgar bo‘lgan alertlarni DM’da oladi; `shadow_rater`, `language_checker` va `golden_copy_rater` egalari faqat baholash yoki tekshirish uchun yuborilgan itemni ko‘radi.

Telegram kanal qoidasi (◇ P-10; `roles.yaml` `telegram_main_group`): asosiy "Wolter AMT" guruhi a’zolari — `owner`, `ads_approver`, `viewer`. Telegram topic’ni a’zo bo‘yicha yashira olmaydi, shuning uchun asosiy guruhga faqat uchala rol ham ko‘ra oladigan ma’lumot (`reports`, `spend`) chiqadi; change set va alertlar DM orqali boradi. `fleet_operator`, `content_contributor` va `sales_lead` DM yoki faqat ruxsatli rollar a’zo bo‘lgan alohida kichik guruhdan foydalanadi; `💬 CMO` faqat DM. Removal, suspension yoki expiry’da ops-bot odamni guruhdan chiqaradi yoki `ALERT_ACCESS_DRIFT` beradi.

### 3.3 UI va boshqa ruxsatlar

| Amal | Ruxsat |
|---|---|
| Paperclip UI (`mar.wolter.uz`) | effective `paperclip_ui` + tg-auth + cloud-password attestatsiyasi + Paperclip login |
| Langfuse UI (`mar3.wolter.uz`) | effective `langfuse_ui` + tg-auth + attestatsiya + Langfuse login |
| Umami UI (`stats.wolter.uz`) | owner; ads_approver ★ — Umami’ning o‘z login’i, akkauntni owner yaratadi, read-only |
| Hermes suhbat | effective `hermes_chat`; approval, rol yoki kill imkoniyati yo‘q; javob so‘rovchining `sees` doirasida |
| Golden/shadow baholash | `golden_copy_rater`/`shadow_rater`; bu ad approval emas |
| Urgent DM | `dm_alerts`; owner default |

Paperclip UI foydalanuvchisi bo‘lish ops approval rolini avtomatik bermaydi. Paperclip va Langfuse akkauntlarini owner yaratadi; kunlik sync checker flag va akkaunt farqini topsa `ALERT_ACCESS_DRIFT` beradi; Paperclip profili rol DB’sini yozmaydi.

## 4. Membership hayot sikli

### 4.1 `/role` buyruqlari

Barcha mutatsiya — owner, typed code bilan ikki bosqich ([TELEGRAM §3](TELEGRAM.md)): bot exact shaxs (numeric ID va ko‘rinadigan ism), rol yoki flag, expiry va timezone hamda effective permission xulosasini ko‘rsatadi → tugma → bir martalik 4 xonali kod → owner ikki daqiqa ichida `TASDIQ <kod>` yozadi. Tasdiqdan keyin DB transaction membership/flag, revision, `roles_audit`, `audit_log` va outbox’ni birga yozadi. Username faqat numeric ID’ga ishonchli resolve qilinib qayta ko‘rsatilsa ishlatiladi; noma’lum ID taxmin qilinmaydi.

| Buyruq | Ta’siri |
|---|---|
| `/role add <tg_id> <role> [expires YYYY-MM-DD]` | yangi membership; rolning default flaglari shu membership amal qilganda ishlaydi |
| `/role remove <tg_id> <role>` | faqat shu membership tugaydi; boshqa yaroqli rollar qoladi |
| `/role suspend <tg_id>` | person darajasida barcha rol, flag, sessiya va callback yopiladi |
| `/role resume <tg_id>` | personni qaytaradi; expired yoki removed membership, eski sessiya va approval qaytmaydi |
| `/role assign\|unassign <tg_id> <assignment> [expires YYYY-MM-DD]` | `responsibility_assignments` yozuvi (`technical_operator`, `finance_owner`, `privacy_owner`, `independent_reviewer`); faol shaxs kerak; off-host jurnalga ko‘chiriladi |
| `/role flag add\|remove <tg_id> <flag> [expires YYYY-MM-DD]` | `person_flags` yozuvi; faqat kamida bitta yaroqli membership bo‘lsa ishlaydi |
| `/role list` | rollar, flaglar, a’zolar va muddatlar (faqat owner ko‘radi) |

Typed code — ataylab qilinayotgan amalni tasdiqlash, ikkinchi autentifikatsiya faktori emas (`two_step.typed_code.meaning`): kod o‘sha chatda ko‘rinadi. Identity Telegram akkaunti, cloud-password attestatsiyasi va tg-auth’ga tayanadi. Har `role_change` (flag ham) off-host monitor kanaliga ko‘chiriladi (`role_change.mirror_to: independent_monitor_channel`). `owner` yoki `ads_approver` berish uchun ikkinchi kanal tasdig‘i ⧗ OD-10. Rol o‘zgarishi hech qachon LLM (Hermes) orqali bajarilmaydi.

### 4.2 Attestatsiyalar

- `people.cloud_password_attested_at` — shaxs Telegram cloud password (two-step verification) yoqilganini tasdiqlaydi; platforma buni texnik tekshira olmaydi, bu o‘z-o‘zini tasdiqlash va owner javobgarligi (✅ Q49, ★). Attestatsiya yo‘q bo‘lsa: owner va ads_approver approval tugmalari va typed-code buyruqlari ishlamaydi, til tekshiruvi va rights clear callback’lari ham approval kabi rad etiladi, tg-auth har qanday shaxsga UI sessiya bermaydi. ACK, fleet snapshot, kontent yuklash va baholash attestatsiyaga bog‘lanmaydi.
- `people.native_language_attested` (`uz | ru | null`) — owner `language_checker` flagini berishda shaxsning ona tilini attestatsiya qiladi; `language_checker` faqat `uz` bilan ishlaydi.

### 4.3 Seed qamrovi

| Bosqich | Kim qo‘shiladi | Qanday | Readiness / HG |
|---|---|---|---|
| F1 | faqat owner va break-glass | bir martalik seed | `ops.roles_owner` (`F1_AUTH`) |
| F2 | intake roster: sales_lead, intake primary/deputy, fleet_operator | owner `/role add` (HG-F2-14 dan oldin) | `ops.roles_roster`, HG-F2-16 |
| F3 | qolgan odamlar (targetolog, kontent yetkazuvchilar va boshqalar) | owner `/role add` har odam uchun | HG-F3-05 |

Seed qayta ishlatilmaydi; keyingi barcha o‘zgarish `/role` orqali.

### 4.4 Muddat va eslatma

Membership yoki flag muddati tugashidan 7 kun oldin ownerga `REMINDER_ROLE_EXPIRY` `[Uzaytirish] [Tugatish]` bilan keladi (`expiry_reminder_days_before: 7`); javob bo‘lmasa muddat tugaydi. Expiry worker shu transaction funksiyalaridan foydalanadi; dispatch paytidagi expiry tekshiruvi worker ishlamay qolishidan mustaqil. Membership tugasa uning default flaglari ham, boshqa yaroqli membership bo‘lmasa `person_flags` ham ishlamaydi.

### 4.5 Targetolog vaqt chizig‘i

| Bosqich | Rol va flag | Langar va gate |
|---|---|---|
| F5 | `viewer` + `golden_copy_rater` + `shadow_rater` + `language_checker`; reklama tasdig‘i yo‘q | HG-F5-03 |
| F6 Step 1 | `ads_approver`, `expires_at` = Step 1 + 28 kun | soat HG-F6-01 vaqt belgisidan boshlanadi (✅ Q31: targetolog birinchi 4 hafta ikkinchi approver) |
| Step 1 + 21 kun | rotatsiya: uzaytirish, almashtirish yoki tugatish; `ops.ads_handback_roster` qayta tasdiqlanadi | HG-F6-05 (◇ P-17), approver muddati tugashidan oldin |
| Keyin | `language_checker` faqat yaroqli membership bo‘lsa (masalan `viewer`); owner zaxira checker — ◇ P-29 (qabul qilinmaguncha yo‘q) | ✅ Q42; ◇ P-29 |

Approver muddati tugashi avtomatik scale, owner-only huquq yoki handback vakolatini bermaydi; keyingi approver va handback egasi HG-F6-05’da nomlanadi.

### 4.6 Oxirgi owner, suspend va guruh

Kamida bitta faol owner normal write uchun majburiy (`at_least_one_active_owner_required: true`). Oxirgi ownerni o‘chirish, suspend qilish yoki oldindan ma’lum expiry bilan nol owner qoldirish oddiy boshqaruv transaction’ida rad. Security compromise yoki guruhdan chiqish tufayli oxirgi ownerga deny kerak bo‘lsa huquq saqlab qolinmaydi: tizim contained holatga o‘tadi va offline owner recovery yo‘li ishlaydi; bootstrap/recovery root operator protsedurasi auditli, oddiy seed reload emas.

Telegram `chat_member` hodisasi (guruhdan chiqish) rollarni `suspended` qiladi va ownerga alert beradi. Suspend, removal yoki expiry’da ops-bot odamni tegishli guruhlardan chiqaradi; chiqara olmasa `ALERT_ACCESS_DRIFT`. Offboarding’da Paperclip, Langfuse va Umami akkauntlari ham yopiladi; odam ko‘rgan sir bo‘lsa u rotatsiya qilinadi.

## 5. DB va YAML manbalari

```text
roles.yaml seed (F1, bir marta) --explicit bootstrap--> amt.people + amt.roles + amt.person_flags
                                                     <-- /role (owner, typed code)
                       export PR <------------------- DB tungi eksport
```

`role_seed_imports` seed SHA va bootstrap ID’ni qayd etadi. Eksportdan live DB’ni avtomatik tiklash yoki import qilish yo‘q (`release-policy.yaml` `roles_reload: never_reseed_runtime_DB`). Seed sxemasi (`people_seed_schema`): `tg_id`, `display_name`, `memberships[{role, expires_at}]`, `flags[{flag, expires_at}]`, `cloud_password_attested_at`, `native_language_attested`. `role_permissions` statik code/config bundle orqali validate → prepare → activate → ACK bilan keladi; odamlar va membership esa runtime DB truth. Ikkalasini bitta fayl reload deb talqin qilish privilege regressiyasi bo‘ladi.

Ops bot, tg-auth, gateway, amt-control va Hermes allowlist bitta shared RBAC kutubxonasidan yoki bitta authoritative servisdan foydalanadi. Hermes allowlist’ining dinamik reload’i F4’da tekshiriladi; reload muvaffaqiyatsiz bo‘lsa eski allowlist bilan kirish ochiq qolmaydi. Staff ma’lumoti (`staff_identity`) va tg-auth sessiyalari privacy dataset inventarizatsiyasida retention bilan ([privacy-policy.yaml](../09_Config_Templates/privacy-policy.yaml)).

DB grantlari: agent UID’lari DB’ga to‘g‘ridan-to‘g‘ri ulanmaydi; `amt_ops` owner tekshiruvi parametrlarisiz universal rol UPDATE huquqiga ega emas. People, membership va flag o‘zgarishi serialized last-owner guard, expected revision va append-only audit bilan. Broad shared secret yoki bir UID’dagi HMAC privilege boundary emas.

## 6. Qabul

F1: real owner seed, noto‘g‘ri seed, eksport reimport rad va last-owner himoyasi. F2: intake roster `/role add` (HG-F2-16). F3: barcha rol × buyruq/action uchun deny-by-default; person suspend, membership va flag expiry, multi-role union, parallel approval, revoked queued approval, owner-only birinchi activation, attestatsiyasiz approval, stale cache va soxta callback. F4: Reviewer/process credential izolyatsiyasi va Hermes revoke. F6: operator/targetolog expiry, HG-F6-05 rotatsiya va handback drill. UAT-13 va UAT-27–30 hamda tegishli faza dalillari [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md)ga yoziladi. Ruxsati bekor bo‘lgan eski itemni mode resume qayta tiriltirmaydi.

### F3 regression case identifikatorlari

| Case | Talab qilingan natija |
|---|---|
| RB-01 | ads_approver `campaign_create` bandini tasdiqlay olmaydi |
| RB-02 | viewer action tugmasini bossa holat o‘zgarmaydi |
| RB-03 | typed code yo‘q, noto‘g‘ri yoki 2 daqiqadan keyin → rol yoki flag o‘zgarmaydi |
| RB-04 | person suspend → barcha sessiya, callback va Hermes kirishi deny |
| RB-05 | membership expiry → ayni rol bilan approval yo‘q va shu membership’dan kelgan flaglar ishlamaydi; boshqa yaroqli rol alohida ishlaydi |
| RB-06 | bir roldagi ikki approver parallel → bitta qaror, ikkinchisiga idempotent toast |
| RB-07 | oxirgi faol owner oddiy remove/suspend/expiry bilan yo‘qolmaydi; compromise recovery fail-closed |
| RB-08 | noto‘g‘ri, replay yoki eksport qilingan seed → runtime DB o‘zgarmaydi |
| RB-09 | ads_approver birinchi campaign/ad set activation’i → `needs_owner` |
| RB-10 | paperclip, hermes va agent UID’lari roles/control DB’ga yozolmaydi |
