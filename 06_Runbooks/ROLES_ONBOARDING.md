# RUNBOOK — Rollar, operator va deputy vakolatlari

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

> Spetsifikatsiya: [RBAC](../03_Architecture/RBAC.md), [ADR-018](../04_ADR/ADR-018-rbac-registry.md), [roles.yaml](../09_Config_Templates/roles.yaml). **Runtime reestr — `amt.people` + `amt.roles` (DB)**; `roles.yaml` — boshlang‘ich seed va tungi eksport PR (Q47★); eksport DB’ni hech qachon qayta seed qilmaydi (`export_must_not_reseed: true`). Bir rolda bir necha odam, bir odamda bir necha rol bo‘lishi mumkin. **Rolni faqat `owner` o‘zgartiradi** (`role_change`): tugma → bot 4 xonali kod → owner 2 daqiqa ichida `TASDIQ <kod>` ★. Kod — ongli harakat tasdig‘i, ikkinchi autentifikatsiya omili emas; identity Telegram akkaunti, cloud-password attestatsiyasi va tg-auth’ga tayanadi. Har `role_change` off-host monitor kanaliga ham ko‘zgulanadi. owner/ads_approver berishda ikkinchi kanal — ⧗ OD-10. Approval quorum faqat [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) `change_set.quorum`da.

## 1. Rollar qisqacha

| Rol | Kim (misol) | Nima qiladi |
|---|---|---|
| `owner` — Egasi | Akmal | hamma narsa: rol tayinlash, kill/resume, NEVER_AUTO tasdiqlar (yangi kampaniya, uning birinchi aktivlashtirilishi, `adset_duplicate`, offer, landing merge, release va boshqalar) |
| `ads_approver` — Reklama tasdiqlovchisi | targetolog (**F6 Step 1 dan** 4 hafta ★) | kreativ yoqish (exact asset/review/offer revision), rolling24h ≤20% byudjet o‘zgarishi (◇ P-01), pause, avval faol bo‘lgan obyektni qayta yoqish, ad yaratish, eksperiment exposure’ini tasdiqlash (`experiment_exposure`) |
| `sales_lead` — Sotuv rahbari | call-center rahbari | 18:00 lead sifati digest’i ★, feedback, qualified ta’rifi egasi, kunlik `/sale_ready` (◇ P-22) |
| `fleet_operator` — Park operatori | park/ijara mas’uli | har kuni to‘liq fizik park snapshot’i va amaldagi waitlist (`operations.yaml` `schedule.fleet_ask`); append-only tuzatish |
| `content_contributor` — Kontent yetkazuvchi | foto/video oluvchi | ops-bot’ga material yuklash; haftalik eslatma (Q20/Q29.3 ✅) |
| `viewer` — Kuzatuvchi | investor/hamkor; F5’da targetolog | hisobotlarni ko‘rish |

**Flag’lar** (faqat owner beradi; `roles.yaml` `flags`): `paperclip_ui`, `langfuse_ui`, `dm_alerts`, `hermes_chat`, `golden_copy_rater`, `shadow_rater`, `language_checker`, `ops_responder`, `rights_clearer`. Effective flag’lar = yaroqli membership’larning default flag’lari ∪ `person_flags` (`expires_at` kelmagan), faqat kamida bitta yaroqli membership bo‘lsa. Buyruq: `/role flag add|remove <tg_id> <flag> [expires]` (owner, ikki bosqich).

**Ko‘rish doirasi (◇ P-10):** asosiy “Wolter AMT” guruhi — owner, ads_approver, viewer. fleet_operator, content_contributor va sales_lead — DM yoki alohida kichik guruh. `💬 CMO` — faqat DM. Har rolning `sees` ro‘yxati `roles.yaml`da.

## Operator roster, responsibility assignment va qamrov

Responsibility assignment’lar — roster yozuvi, Telegram ruxsati emas; owner ularni o‘zi ushlashi mumkin (`roles.yaml` `responsibility_assignments`). Owner `/role assign <tg_id> <assignment> [expires]` (typed code) bilan beradi va `/role unassign` bilan oladi; yozuv `amt.responsibility_assignments`da. Egasi Telegram’dan foydalanishi (masalan `/readiness approve`) uchun kamida `viewer` a’zoligi kerak:

| Assignment | Vazifa |
|---|---|
| `technical_operator` | AMT host, restore, rotatsiya va drill’lar; Telegram’da `viewer` roli + `ops_responder` flag |
| `finance_owner` | moliyaviy readiness qiymatlarini tasdiqlaydi |
| `privacy_owner` | privacy readiness va breach yo‘lini tasdiqlaydi |
| `independent_reviewer` | himoyalangan sirt o‘zgarishlarining muallif bo‘lmagan inson reviewer’i (⧗ OD-12); candidate PR’ni `people.github_login` dagi GitHub akkaunti bilan review qiladi (`independent_reviews`) |

Readiness kalitlari (qiymatda faqat opaque `person_ref`; identity faqat `amt.people/roles`da):

| Kalit | Gate | Nima |
|---|---|---|
| `ops.roles_owner` | F1_AUTH | owner Telegram ID, person seed, 2FA va oflayn break-glass kodlari |
| `ops.roles_roster` | F2_LIVE_INTAKE | intake roster’i: sales_lead, intake primary/deputy, fleet_operator (HG-F2-16) |
| `ops.intake_responders` | F2_LIVE_INTAKE | nomlangan intake primary/deputy, qamrov soatlari, `ops_responder` |
| `ops.ads_handback_roster` | F6_STEP1 (`max_evidence_age: P7D`) | har pipeline uchun reklama handback custodian’i va ACK yo‘li |
| `ops.sale_handback_roster` | F6_STEP2 (`max_evidence_age: P7D`) | sale pipeline handback custodian’i |
| `ops.ack_minutes`, `ops.escalation` | F2_LIVE_INTAKE | severity bo‘yicha ACK muddati, primary → deputy → owner yo‘li va owner yo‘qligidagi safe operation |

Operator ACK qiladi (`[Qabul qildim]` → `incident_acks`), read-only diagnostika va oldindan ruxsat etilgan protective ish bajaradi; bu avtomatik owner yoki ads_approver vakolatini bermaydi. **Owner vakolati faqat odamga `owner` roli berilganda o‘tadi**; boshqa delegatsiya yo‘q. **Deputy kill — ⧗ OD-04**; qaror bo‘lmaguncha deputy kill/resume, rol tayinlash, offer/landing merge yoki birinchi activation’ni owner o‘rnida qila olmaydi. Owner yo‘q bo‘lsa safe hold/handback va mavjud protective controls saqlanadi. Human ad handback faqat oldindan Ads Manager vakolati bor custodian tomonidan ACK qilinadi (`handback_acks`). Mustaqil monitor va alternate channel mashqi `ops.independent_monitor` (F2) va `ops.independent_monitor_full` (F6 Step 1) dalilida.

## 2. Yangi odam qo‘shish

1. Odam ops-bot’ga `/start` yozadi → `/whoami` unga Telegram user ID’sini ko‘rsatadi.
2. **Owner:** `/role add <user_id> <rol> [expires YYYY-MM-DD]` → bot xulosa + “Tasdiqlash” tugmasi → bot kod chiqaradi → owner `TASDIQ <kod>`.
3. Bot `amt.people`/`amt.roles`ni yangilaydi, `roles_audit` va `audit_log`ga yozadi, o‘zgarishni off-host monitor kanaliga ko‘zgulaydi, yangi odamga xush kelibsiz xabarini (roli va nima qilishi) yuboradi; asosiy guruhga faqat ruxsat etilgan rollar taklif qilinadi (§1).
4. `owner` yoki `ads_approver` berilsa bot **Telegram cloud password** (two-step verification) yoqishni talab qiladi. Odam tasdiqlamaguncha (`people.cloud_password_attested_at` bo‘sh) approval tugmalari va tg-auth rad etiladi ★ (texnik tekshirib bo‘lmaydi — o‘z-o‘zini tasdiqlash + owner javobgarligi). `language_checker` uchun owner `people.native_language_attested` ni qayd etadi.
5. UI kerak bo‘lsa owner flag beradi (`/role flag add <tg_id> paperclip_ui|langfuse_ui [expires]`) va Paperclip/Langfuse’da akkaunt yaratadi; kunlik sync-checker farqni topsa `ALERT_ACCESS_DRIFT`.

Seed qamrovi (`roles.yaml` `seed_scope`): F1 — faqat owner va break-glass (`ops.roles_owner`); F2 — intake roster’i owner `/role add` bilan (HG-F2-16); F3 — qolgan odamlar har biri uchun owner `/role add` (HG-F3-05), seed bilan emas.

## 3. Rolni o‘zgartirish / to‘xtatish / olib tashlash

| Buyruq | Ta’siri |
|---|---|
| `/role suspend <user_id>` | barcha rollari nofaol (`status=suspended`); rol revision’i o‘zgaradi, tg-auth sessiyalari bekor; Hermes allowlist’dan chiqariladi; eski approval’lari dispatch/retry’da yaroqsiz; guruhlardan chiqariladi yoki `ALERT_ACCESS_DRIFT` |
| `/role resume <user_id>` | oldingi rol grantlari muddati va owner tasdig‘i bo‘yicha qayta faol; eski sessiya va approval avtomatik tirilmaydi |
| `/role remove <user_id> <rol>` | faqat shu rol o‘chadi; boshqa rollar qoladi; shu rolga bog‘liq flag’lar effektini yo‘qotadi |
| `/role flag add\|remove <tg_id> <flag> [expires]` | person flag beriladi yoki olinadi (`person_flags`, `flag_revision`) |
| `/role list` | rollar, a’zolar, flag’lar va muddatlar (owner) |

- **Targetolog vaqt chizig‘i** (`roles.yaml` `targetologist_timeline`): **F5** — `viewer` + `golden_copy_rater` + `shadow_rater` + `language_checker` (reklama tasdig‘i yo‘q); **F6 Step 1** — owner `/role add <id> ads_approver expires <Step 1 + 28 kun>`; **Step 1 + 21 kun** — HG-F6-05 (◇ P-17): uzaytirish, almashtirish yoki tugatish, `ops.ads_handback_roster` qayta tasdiqlanadi. Muddat tugashidan 7 kun oldin `REMINDER_ROLE_EXPIRY`; javob bo‘lmasa membership tugaydi. F7 kutilmaydi.
- Owner yagona faol owner’ni o‘chira olmaydi (`at_least_one_active_owner_required`).

## 4. Odam ketganda (offboarding) — checklist

1. Agar odam handback custodian, intake responder yoki technical_operator bo‘lsa — avval o‘rinbosarni roster’ga kiriting va tegishli readiness kalitini (`ops.intake_responders`, `ops.ads_handback_roster`, `ops.sale_handback_roster`) qayta tasdiqlating.
2. `/role suspend <user_id>` (keyin kerak bo‘lsa `/role remove`); person flag’lari olinadi.
3. Telegram guruhlaridan chiqarish (ops-bot `chat_member` hodisasini ko‘rsa rollarni avtomatik `suspended` qiladi va owner’ga alert beradi).
4. Tashqi tizimlar (owner yoki tegishli egasi bajaradi): Meta Business Manager / Ads Manager foydalanuvchisi; amoCRM foydalanuvchisi (sales_lead bilan); Google Drive `AMT/raw` ulashilishi; GitHub collaborator va token’lari; Paperclip va Langfuse akkauntlari; Umami/Clarity kirishi.
5. Odam break-glass yoki boshqa sirni ko‘rgan bo‘lsa — tegishli sir rotatsiya qilinadi ([BACKUP_RESTORE §7](BACKUP_RESTORE.md)); owner darajasida bo‘lsa break-glass kodlari qayta yaratiladi.
6. Natija `roles_audit`da; tashqi tizimlar ro‘yxati bo‘yicha dalil offboarding yozuviga.

## 5. Nazorat

- Har oy (C12 retro; mas’ul owner): reestr ro‘yxati, faol bo‘lmaganlar, muddati yaqinlashganlar, kim nechta tasdiq bergan, rad etish ulushi (rubber-stamp signali, Q38 ✅), handback custodian’lar dolzarbligi.
- Reestr o‘zgarishlari `amt.roles_audit` va `audit_log`da; git tarixi — tungi eksport PR’lari orqali (Q47★).

## 6. Evidence va regression

Onboarding/offboarding izolyatsiyalangan fixture’da tekshiriladi: callback replay, approvaldan keyin rol revoke, muddati o‘tgan approver, last-owner himoyasi, YAML eksportni DB ustiga reload qilish urinishi, membership tugagach flag effekti yo‘qligi, cloud-password attestatsiyasisiz approval rad. Barcha tashqi akkaunt va sessiya kirishi ham olinadi; faqat bot roli bilan cheklanmaydi. Rol/policy revision har dispatch/retry/rollback oldidan qayta tekshiriladi; eski approval bilvosita resume qilinmaydi. Seed bir martalik; eksport PR audit va DR uchun, runtime manbai DB bo‘lib qoladi. Gate’lar: HG-F2-16, HG-F3-05, HG-F6-05.
