# ADR-008 — PII minimallashtirish: agentlar shaxsiy ma’lumot ko‘rmaydi

Holat: Accepted · Qaror egasi: owner (Q28, Q18, Q62 ✅) + ⧗ OD-16 (breach xabari oluvchilari va muddatlari) · Sana: 2026-10-22

## Kontekst

Owner qarorlari: agentlar lid ismi va telefonini ko‘rmaydi — faqat lead ID, stage, UTM va vaqt; PII faqat amoCRM va capi-bridge’da (manbada hash); landing’da rozilik matni (Q28). amoCRM’da AMT o‘qiydi va faqat teg/maydon yozadi; lidlarga to‘g‘ridan-to‘g‘ri xabar yo‘q (Q18) [D: DECISION_LOG].

Huquqiy faktlar — 2026-10-22 holati. Har biri amaldagi qonun matnidan qayta tekshiriladi va `privacy.*` readiness yozuvida manba va sana bilan tasdiqlanadi; bu ro‘yxat huquqiy xulosa emas:

- **ZRU-1125** (kuchga kirgan 2026-03-27): O‘zbekistonda saqlash shart bo‘lgan ma’lumotlar faqat biometrik, genetik va telekom foydalanuvchilari ma’lumotlari; boshqalari adekvat davlatda, tasdiqlangan shartnoma bandlari bilan yoki xalqaro standart bo‘yicha xorijda saqlanishi mumkin [D: lex.uz/docs/8104580 · qayta tekshiriladi].
- **415-qaror** (2026-08-03): adekvatlik ro‘yxatida 49 yurisdiksiya, jumladan EU (Germaniya, Finlyandiya), UK va Rossiya; AQSh faqat DPF sertifikatiga ega kompaniyalar uchun [D: lex.uz/en/docs/8371383 · qayta tekshiriladi].
- Anthropic DPF reyestrida yo‘q [?: 2026-sentabr ikkilamchi manba]; runtime OpenRouter (AQSh) va undan keyingi provayderlar orqali o‘tadi — agentlarga PII bermaslik shuning uchun ham muhim.
- Buzilish yuz bersa 24 soat ichida xabar, 72 soat ichida tafsilot — ikkilamchi manba da’vosi [?: pactum.uz; qonun matnidan tasdiqlanmagan]. Standart shartnoma bandlari 2026-10-12 holatida e’lon qilinmagan [?].
- AI yordamida shaxsiy ma’lumotni noqonuniy qayta ishlash uchun javobgarlik 50–100 BRV [D: norma.uz · qayta tekshiriladi].
- amoCRM serverlari Rossiyada; Rossiya adekvatlik ro‘yxatida [D: amocrm.ru/support/security/server · qayta tekshiriladi].

Texnik kontekst: telefon/ism regexi yolg‘iz himoya emas; hash anonimlik kafolati emas [X]. CAPI so‘rovidagi hash’langan telefon, `fbc`/`fbp`, IP va UA "dalil" sifatida diskka yozilsa, withdrawal va retention kafolati buziladi [X].

## Qaror

1. Agentlar faqat sanitizatsiyalangan ID va agregatlarni oladi: lead ID, pipeline/status, vaqtlar, UTM va tracking flag’lari (`has_fbc` va shu kabi), allowlist’dagi custom field’lar. Ism, telefon, email, kontakt havolalari, izoh va erkin matnli maydonlar olib tashlanadi. Agent warehouse’da, Langfuse trace’larida, loglarda va Telegram hisobotlarida PII yo‘q; bu PII probe testlari bilan tekshiriladi (I09).
2. PII custody `privacy-policy.yaml#datasets` inventari bilan yuritiladi; har dataset uchun host, custodian, maqsad, maydonlar, kalit, retention ref va withdrawal yo‘li yozilgan:

   | Dataset | Custodian | Asosiy qoida |
   |---|---|---|
   | `amocrm_contacts` | amoCRM, `amt-amo` API | xizmat maqsadi; withdrawal — CRM jarayoni (sales_lead) |
   | `landing_submission_store` | landing app (production Dokploy) | shifrlangan payload; purge job + audit |
   | `webhook_inbox` | `capi-bridge` (AMT host) | lead PII diskka yozilmaydi: faqat allowlist maydonlari (ID’lar, status, vaqtlar, akkaunt, body sha256, imzo natijasi); xom body faqat xotirada (Q62); DB grant; ishlov oynasidan keyin purge |
   | `capi_in_memory` | `capi-bridge` | hash faqat xotirada; yuborishdan oldin consent tekshiruvi |
   | `capi_attempt_evidence` | `capi-bridge` | `request_hash`, field presence bitmap, provider javob kodi va trace ID; xom `user_data` hech qachon saqlanmaydi |
   | `staff_identity` | `amt.people`/`amt.roles` | kirish nazorati; offboarding runbook |
   | `tg_auth_sessions` | `tg-auth` | sessiya va login so‘rovi metadata’si; muddat bilan o‘chadi |
   | `drive_raw_and_quarantine_media` | ops-bot, render-worker | rights va review’gacha quarantine; `asset_rights_revoke` |
   | `backups` | `amt-backup` | AMT PC’dagi lokal snapshot (shu RAID1), shifrlanmagan (Q54); 7 kun saqlanadi va shu muddat bilan o‘chadi (Q55) |
   | `forensic_copy` | owner | faqat stsenariy (e) da (◇ P-32): ishonchsiz disklardan PC ichida olingan nusxa, faqat AAR uchun matn sifatida o‘qiladi (`pg_restore --list`, `pg_restore -f -`), hech qaysi PostgreSQL serveriga tiklanmaydi; AAR yopilganda o‘chadi |

3. `capi-bridge` telefonni yuborish paytida amoCRM’dan (faqat alohida `capi_lookup` socket orqali) o‘qiydi, `998…` formatiga normallashtiradi, xotirada SHA-256 bilan hash’laydi va ochiq matnni hech qachon saqlamaydi.
4. Consent: `service_fulfilment` va `marketing_measurement` maqsadlari alohida. Receipt maydonlari — `subject_ref`, `purpose`, `text_version`, `granted_at`, `source`, `withdrawn_at`; noma’lum marketing ruxsati — deny; withdrawal keyingi yuborish va backfill’da tekshiriladi. Landing rozilik matnini owner tasdiqlaydi (HG-F2-07).
5. Huquqiy asos, transchegaraviy uzatish, saqlash va o‘chirish qoidalari `privacy.purposes` va `privacy.retention` da privacy_owner (owner co-signer) tasdig‘i bilan yopiladi (F2_LIVE_INTAKE). `data_collection: deny` yoki ism yo‘qligi muvofiqlikni avtomatik tasdiqlamaydi.
6. Buzilishga javob: kimga xabar beriladi, muddatlar, mas’ul shaxs va shablon `privacy.breach_response` (privacy_owner + owner, F2_LIVE_INTAKE) da amaldagi qonun matni va sanasi bilan yoziladi; muddat qiymatlari spetsifikatsiyada uydirilmaydi (⧗ OD-16). Ijro tartibi [INCIDENTS](../06_Runbooks/INCIDENTS.md) da.
7. Identifikatsiyalanadigan media avval quarantine’da; rights va consent dalilisiz agentga xom bayt yoki generatsiya kirishi berilmaydi.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| PII’ni agentlarga redaksiyasiz berish | qonuniy xavf; prompt injection orqali sizish |
| Hamma ma’lumotni O‘zbekistonda saqlash | ZRU-1125 dan keyin talab qilinmaydi [qayta tekshiriladi]; AMT PC Toshkentdagi ofisda (Q52, [ADR-032](ADR-032-owner-pc-office-host.md)), amoCRM va runtime provayderlar esa xorijda |
| CAPI attempt dalili sifatida xom identifikatorlarni saqlash | hash telefon, `fbc`/`fbp`, IP va UA diskka tushadi; withdrawal kafolati buziladi |
| Hash’ni anonimlashtirish deb hisoblash | hash qayta identifikatsiyani to‘smaydi |
| Breach muddatlarini ikkilamchi manbadan spetsifikatsiyaga yozish | tasdiqlanmagan huquqiy fakt kafolat sifatida tarqaladi (⧗ OD-16) |

## Oqibatlar

- **+** Qonuniy xavf kamayadi; agentlarda injection orqali sizadigan PII qolmaydi.
- **−** Agentlar bitta lead darajasida suhbat sifatini tahlil qila olmaydi, faqat agregatlar bilan ishlaydi — bu qasddan.
- **−** Dataset inventari, purge job’lari va breach jarayoni qo‘shimcha ekspluatatsiya ishini talab qiladi.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Qonunchilik o‘zgarishi | yangi qonun yoki qaror; standart shartnoma bandlari e’lon qilinsa | `owner_request` (privacy_owner) | `privacy.*` qayta tasdiqlanadi; ADR yangilanadi |
| PII sizishi | ≥ 1 insident (`ALERT_SECURITY_PII`) | `incident_aar` | INCIDENTS breach tartibi; `privacy.breach_response` |
| Yangi ma’lumot manbai | yangi dataset yoki integratsiya | `owner_request` | inventarga qo‘shish; privacy_owner tasdig‘i |
| Provider transfer asosi | provayderning DPF yoki joylashuv holati o‘zgarishi | `vendor_advisory` | transfer asosi qayta tekshiriladi |

## Kanonik implementatsiya

- [privacy-policy.yaml](../09_Config_Templates/privacy-policy.yaml) — `datasets`, `consent_receipt_fields`, `breach_response_ref`.
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `privacy.purposes`, `privacy.retention`, `privacy.breach_response`, `offers.asset_rights`.
- [TRACKING_CAPI §5, §8](../03_Architecture/TRACKING_CAPI.md), [DATA_MODEL §3, §5](../03_Architecture/DATA_MODEL.md), [SECURITY §4](../03_Architecture/SECURITY.md).
- [INCIDENTS](../06_Runbooks/INCIDENTS.md), [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) — huquqiy claim’lar; [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) UAT-11; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I09.
