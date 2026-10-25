# TRACKING & CAPI — durable intake’dan biznes signaligacha

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Maqsad — real qabul qilingan murojaat, CRM holati va qualified biznes hodisasini yo‘qotmasdan o‘lchash va qualified signalni Meta’ga deterministik `capi-bridge` orqali qaytarish (✅ Q17, ✅ Q26). Forma yuborilishi qualified emas. Landing, CAPI va sync yo‘li LLM ishlamasa ham ishlaydi (ADR-007). Kanonik manbalar: [INVARIANTS](../11_Production_Contracts/INVARIANTS.md), [BUSINESS_CONTRACT](../11_Production_Contracts/BUSINESS_CONTRACT.md), [DATA_MODEL](DATA_MODEL.md), [pipelines.yaml](../09_Config_Templates/pipelines.yaml), [tracking-health.yaml](../09_Config_Templates/tracking-health.yaml), [privacy-policy.yaml](../09_Config_Templates/privacy-policy.yaml). Vendor imkoniyatlari F2 integratsiya dalili bilan `vendor.meta_capi`da qotiriladi. Qaror belgilari: ✅ owner, ★ builder standarti, ◇ P-NN taklif, ⧗ OD-NN ochiq qaror.

## 1. Landing va durable receipt

`go.wolter.uz` — Next.js landing, alohida production Dokploy hostida, repo `wolter-landing` (✅ Q46.4). Hozirgi Tilda landing HG-F2-09 dan keyin Meta trafigini olmaydi va F6 tugaguncha zaxira sifatida o‘chirilmaydi ★. Google Sheet transport sifatida ishlatilmaydi. AMT hostining yo‘qligi landingning durable qabulini buzmaydi.

1. Server strict schema, pipeline, telefon formati (`998XXXXXXXXX`), service purpose va so‘rov chegaralarini tekshiradi. Client `submission_id`/idempotency kalitini qayta yuborishda saqlaydi; server uni canonical UUID va receipt bilan bog‘laydi.
2. Shifrlangan payload custody’si (`landing_submission_store`), consent receipt reference, original event vaqti, payload hash va `submission_receipts` bitta durable commit bilan yoziladi. Storage fsync/durability va restart/deploy kafolati F2’da isbotlanadi.
3. Commit’dan keyin `accepted` va receipt ID qaytadi; UI "Murojaat qabul qilindi"ni ko‘rsatadi. Bu CRM’ga yetdi degani emas. Storage to‘la yoki commit yo‘q bo‘lsa success qaytmaydi; client o‘sha idempotency kaliti bilan qayta urinadi.
4. Delivery worker kvota oladi (§4) va CRM contact/lead yaratadi, `amt_submission_id` correlation’ini uzatadi. Provider qo‘llaydigan idempotency yoki lookup imkoniyati test qilinadi; server tomondagi uniqueness taxmin qilinmaydi.
5. Tasdiqlangan CRM ID bilan `crm_confirmed`; javob yo‘qolsa `uncertain`, qayta create’dan oldin correlation/event-history reconciliation. Ikki worker lease/fence bilan bitta submission’ni parallel yarata olmaydi.

Receipt holati `accepted → crm_pending → crm_confirmed`; hal qilinmagan tashqi natija `uncertain`, operatsion eskalatsiya `needs_review`. Har qabul qilingan receipt CRM binding’iga yoki mas’ul ko‘radigan failure/pending holatiga ega bo‘ladi (`ALERT_INTAKE_PENDING`). ≤24 soatlik retry navbati boshlang‘ich delivery oynasi; bu muddat tugashi murojaatni indamay o‘chirish ruxsati emas. Retention, dead-letter recovery va host-loss RPO/RTO real trafikdan oldin tasdiqlanadi (`recovery.intake_datasets`, `recovery.intake_drill`).

**Pixel va server `Lead`.** Browser Pixel `Lead` faqat consent-valid durable acceptance’dan keyin, receipt bilan bog‘langan o‘sha `event_id` bilan yuboriladi. Server `Lead` (CAPI) uchun yagona trigger — submission `crm_confirmed` holatiga yetgani (◇ P-19; `pipelines.yaml` `capi_event_map`). amoCRM `add_lead` webhook’i faqat reconciliation: har landing lead’ida receipt bormi tekshiriladi, landing’dan tashqari kelgan lead `Lead` event yaratmaydi. Browser bo‘lmasa server dalili saqlanadi; Pixel ishlagani intake yoki CRM receipt o‘rniga o‘tmaydi. Accepted→CRM reconciliation Pixel–CRM nisbatidan mustaqil.

Landing kodi va Pixel o‘zgarishi faqat PR orqali (`landing.open_pr`: CRO → `content/**`, Analyst → `tracking/**`), merge — owner (✅ Q19, ✅ Q30). `content/offers.snapshot.json`ni CI `config/offers.yaml`dan generatsiya qiladi; CRO uni tahrirlamaydi.

## 2. Tracking qiymatlari va atributsiya

| Signal | Yig‘ish va custody | Agentga chiqishi |
|---|---|---|
| `fbclid`, `fbc`, `fbp` | consent va amaldagi provider format/cookie qoidasi bilan landing → CRM/custody; F2 test | faqat `has_fbc`/`has_fbp` va agregat coverage |
| `event_id` | server qabul qilgan durable submission bilan barqaror; Pixel va server’da bir xil | opaque sanitized ID |
| First/last UTM | alohida timestamp, lookback va attribution revision; kanonik ad ID’lar | allowlisted source/medium va raqamli/scoped ID; xom erkin matn yo‘q |
| `variant_id` | landing variant-config revision’i bilan | sanitized enum/ID |
| IP/UA | server trusted proxy zanjiridan, marketing purpose bo‘lsa; custody’da | hech qachon xom ko‘rinishda emas |
| Consent | purpose/version/source/granted/withdrawn receipt | joriy sanitized purpose holati; xom dalil yo‘q |

Yig‘ish retseptlari (nomzod; `vendor.meta_capi`da tasdiqlanadi):

| Element | Qoida |
|---|---|
| `fbc` | URL’da `fbclid` bo‘lsa `fb.1.<birinchi ko‘rilgan vaqt, ms>.<fbclid>`; first-party `_fbc` cookie mavjud bo‘lsa o‘sha qiymat [D: Meta CAPI parametrlari hujjati]; F2-AT-03 |
| `_fbc` cookie muddati | 90 kun ★; faqat marketing consent bilan |
| `fbp` | Pixel o‘rnatgan `_fbp` cookie; consent bilan |
| `event_id` | har submission uchun bitta; client UUIDv4 yaratadi, server receipt bilan bog‘laydi |
| IP | faqat server tomonda; Cloudflare ortida `CF-Connecting-IP` [D: Cloudflare hujjati] |
| User-Agent | faqat server tomonda; website event’lari uchun `client_user_agent` talab qilinadi [D: Meta CAPI hujjati] |
| Telefon | CAPI worker xotirasida faqat raqamlarga normalizatsiya (`998XXXXXXXXX`) → SHA-256 → bufer tozalanadi |

URL params shabloni — yagona kanonik ta’rif (HG-F2-09 jonli ad’larni shunga ko‘chiradi): `utm_source=meta&utm_medium=paid_social&utm_campaign={{campaign.id}}&utm_term={{adset.id}}&utm_content={{ad.id}}` ★. Dynamic parametr kengayishi F3’da Ads Manager preview va real test klik bilan tekshiriladi. `utm_campaign` — campaign ID, `utm_term` — ad set ID, `utm_content` — ad ID. Agent erkin matnli UTM yasamaydi. First-touch cookie oldingi first touch’ni oxirgi tashrif bilan almashtirmaydi; TTL va lookback `business.attribution`da.

`creative_id`: `wlt_{pipeline}_{yyyymmdd}_{concept}_{lang}_{format}_v{n}`; pipeline `sale`/`rent`, lang `uz`/`ru`, format `1x1`/`4x5`/`9x16`. Canonical creative ID va immutable creative revision alohida. Meta ad nomi = `creative_id` (bir kreativ bir necha ad’da bo‘lsa ad set suffiksi bilan); campaign `wlt_{pipeline}_{objective}_{yyyymm}_{slug}`, ad set `wlt_{pipeline}_{audience}_{yyyymmdd}_{slug}`. Ad → creative exact revision binding `creative_ad_bindings`da; ad nomini parse qilish asosiy join emas. `pipeline` manbai — `managed_entities.pipeline`.

Takeover qilingan kampaniyalar majburan qayta nomlanmaydi; owner scoped managed entity → pipeline mapping’ini tasdiqlaydi (HG-F6-04). Noma’lum attribution alohida guruh; first/last/Meta-reported natijalar qo‘shilib ikki marta sanalmaydi. Xom UTM ichidagi telefon/email yoki CRM tag’idagi PII qiymati sanitizer’da rad yoki redact qilinadi; field nomi ruxsatli bo‘lishi yetarli emas.

## 3. CRM custom field shartnomasi

HG-F2-04’da amoCRM admin quyidagi field’larni yaratadi va webhook’ni ulaydi; field ID’lari F2’da API’dan olinadi. `env.example`da faqat `AMO_FIELD_*` nomlari, qiymatlar shifrlangan custody’da. Jadval `env.example` ro‘yxati bilan bir xil.

| CRM kod nomi | Tur | Guruh | Vazifa | Kim yozadi | Agentga ko‘rinishi |
|---|---|---|---|---|---|
| `utm_source` … `utm_term` | amoCRM standart `tracking_data` [D: amoCRM API hujjati] | Статистика | standartlashgan last-touch | landing | sanitized qiymat |
| `amt_ft_utm` (`AMO_FIELD_AMT_FT_UTM`) | text | Статистика | versiyalangan first-touch (`source\|medium\|campaign\|term\|content`) ★ | landing | sanitized struktura |
| `amt_fbc` (`AMO_FIELD_AMT_FBC`) | text | Статистика | CAPI identifikatori | landing | yo‘q, faqat `has_fbc` |
| `amt_fbp` (`AMO_FIELD_AMT_FBP`) | text | Статистика | CAPI identifikatori | landing | yo‘q, faqat `has_fbp` |
| `amt_event_id` (`AMO_FIELD_AMT_EVENT_ID`) | text | Статистика | Pixel/server dedup ID | landing | opaque ID |
| `amt_submission_id` (`AMO_FIELD_AMT_SUBMISSION_ID`) | text | Статистика | receipt → CRM correlation | landing | opaque UUID |
| `amt_consent_receipt_ref` (`AMO_FIELD_AMT_CONSENT_RECEIPT_REF`) | text | Статистика | purpose/version dalilining custody ref’i | landing | opaque ref |
| `amt_client_ip` (`AMO_FIELD_AMT_CLIENT_IP`) | text | Статистика | consent-valid website CAPI matching | landing (server) | yo‘q |
| `amt_client_ua` (`AMO_FIELD_AMT_CLIENT_UA`) | text | Статистика | consent-valid website CAPI matching | landing (server) | yo‘q |
| `amt_variant_id` (`AMO_FIELD_AMT_VARIANT_ID`) | text | Статистика | landing variant | landing | sanitized ID |
| `amt_consent` (`AMO_FIELD_AMT_CONSENT`) | checkbox | Статистика | call-center ko‘radigan `marketing_measurement` holati; authoritative emas | landing | holat |
| `amt_consent_version` (`AMO_FIELD_AMT_CONSENT_VERSION`) | text | Статистика | rozilik matni versiyasi (ko‘rsatish uchun); authoritative emas | landing | versiya ID |
| `amt_creative_id` (`AMO_FIELD_AMT_CREATIVE_ID`) | text | AMT | exact binding’dan creative ID | sync-worker; funnel-analyst (`amo.write_fields`) | ID |
| `amt_quality_flag` (`AMO_FIELD_AMT_QUALITY_FLAG`) | select: `ok` / `suspect` / `spam` / `duplicate` ★ | AMT | sifat belgisi | funnel-analyst | enum |
| `amt_lead_score` (`AMO_FIELD_AMT_LEAD_SCORE`) | numeric | AMT | tasdiqlangan range/ta’rif | funnel-analyst | bounded son |

Authoritative consent manbai — consent receipt (`subject_ref`, `purpose`, `text_version`, `granted_at`, `source`, `withdrawn_at`; `privacy-policy.yaml` `consent_receipt_fields`); `amt_consent` va `amt_consent_version` faqat CRM’dagi ko‘rinish. `ad_id`/`adset_id`/`campaign_id` alohida field emas — kanonik UTM’larda keladi (§2). Analyst faqat oxirgi uch AMT field’ni o‘zgartiradi; contact, status, pipeline, consent va tracking metadata’ga write yo‘q; `AMT:` tag prefiksi va qiymat allowlist’i ★. Test classification original source metadata’da immutable `is_test=true` (`AMT:TEST` tegi, HG-F2-12); keyinchalik teg olib tashlansa ham eski test hodisasi production’ga aylanmaydi. Builder production CRM’da lead statusini hech qachon o‘zgartirmaydi — test lead statusini owner yoki call-center o‘zgartiradi.

### 3.1 Qualified fakt qoidasi (◇ P-19)

Status nomining o‘zi yetarli emas (✅ Q16: haqiqiy aloqa, kuryerlik va 30 kun ichidagi sotib olish yoki ijara niyati). `pipelines.yaml` `qualified_fact_rule` bo‘yicha qualified fakt — `lead_id × pipeline` uchun birinchi transition, bunda:

- `to_status_id` `pipelines.<pipeline>.qualified_status_ids` ichida;
- transition aktori sales_lead tasdiqlagan call-center foydalanuvchilaridan (`allowed_actor_user_ids`);
- sales_lead talab qilgan evidence field’lari to‘ldirilgan (`required_evidence_field_ids`, ixtiyoriy);
- `event_time` = transition `occurred_at`.

Birinchi qualification CRM event history’dan sanaladi, joriy snapshot’dan emas (`history_counting: first_qualified_event_not_current_stage`); renewal yangi acquisition emas. Keyingi QA yangi measurement revision yoki invalidation yaratadi; owner boshqacha qaror qilmasa real-time CAPI’ni bloklamaydi (`qa_effect`). Remap, transfer, merge, reopen va correction measurement revision bilan; yangi acquisition jimgina ko‘paytirilmaydi. SOP, QA va disposition egasi — sales_lead (`business.qualification`, `sales.sop`, `sales.qa`; HG-F2-06).

## 4. Webhook inbox va global CRM kvotasi

`capi-bridge` — `127.0.0.1:3400`, UID `amt-capi`; `mar2.wolter.uz/amo/<secret>` Cloudflare Tunnel orqali keladi va Caddy uni marshrutlaydi (✅ Q46.2, Q57). Secret ≥32 random bayt, account/subdomain tekshiruvi, body/type/size/rate chegarasi, redacted route log va rotation grace. amoCRM webhook’ni imzolashi taxmin qilinmaydi [T: F2’da tekshiriladi]; vendor imzo bersa raw-body bo‘yicha tekshiriladi. Webhook tanasiga ishonilmaydi: lead ID olinadi va ma’lumot CRM’dan qayta o‘qiladi. Raw body faqat xotirada tekshiriladi va qayta ishlanadi, diskka yozilmaydi (Q62): durable inbox (`webhook_inbox`) faqat allowlist maydonlarni saqlaydi — entity ID’lari, status, vaqtlar, account, body sha256 va imzo natijasi ([DATA_MODEL §3.2](DATA_MODEL.md)); qayta ishlash oynasidan keyin purge; queue va warehouse metadata’sida PII yo‘q.

capi-bridge’da amoCRM tokeni yo‘q: CRM’ni faqat `amocrm-mcp` (`amt-amo`)ning alohida `capi_lookup` socket’i orqali o‘qiydi (peer UID faqat `amt-capi`). Diagnostika va job’lar faqat o‘z UID’ida ishlaydi: webhook va CAPI — `amt-capi`; tracking-health va sync — `amt-sync`; umumiy `amt` UID yo‘q.

ACK faqat durable inbox commit’idan keyin. Dedupe manbasi account + event ID yoki versiyalangan canonical fingerprint. Worker CRM’ni qayta o‘qib identity va account’ni tekshiradi, tarixiy transition’ni event history’dan oladi; qualified → lost qisqa o‘tishi joriy snapshot reread’ida yo‘qolmaydi. Out-of-order va replay source vaqti bilan append qilinadi; poison event disposition, egasi va alert oladi. Cursor sahifa hodisalari commit’dan keyin siljiydi.

**amoCRM yetkazish shartnomasi** ([RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) VR-36; `operations.yaml#amo_webhook_contract`). amoCRM hook javobini ko‘pi bilan 2 soniya kutadi; capi-bridge javobni durable commit bilan birga `reply_budget_ms` (builder nomzodi 1 500 ms, p99) ichida beradi — vendorning 2 soniyasi amoCRM → Cloudflare edge → tunnel → ofis PC yo‘li bo‘yicha o‘lchanadi, shuning uchun byudjet F2-AT-24 da tashqi nuqtadan tunnel orqali end-to-end o‘lchanadi. Commit bajarilmasa yoki byudjetga sig‘masa darhol `503` qaytariladi — 5xx barcha 5 vendor urinishini oladi (5, 15, 15 daqiqa va 1 soat), timeout esa yaroqsiz javob sifatida hisoblanadi; commit’dan oldin 2xx hech qachon berilmaydi. So‘nggi 2 soatda 100 dan ortiq yaroqsiz javob bo‘lsa amoCRM hook’ni o‘chiradi va uni faqat amoCRM admini qo‘lda qayta yoqadi; har ≥ 2 soatlik uzilish (ish vaqtida ~21 hodisa × 5 urinish [inference]), sekin javob yoki disk bosimidagi fail-closed shunga olib kelishi mumkin. Murosa: `503` 4- va 5-urinishni oladi, shuning uchun har muvaffaqiyatsiz hodisa 3 emas 5 ta yaroqsiz javob beradi va o‘chirish chegarasiga ~34 emas ~21 hodisada yetiladi [inference]; tanlov — qo‘shimcha urinishlar qisqa commit xatolarini 15 daqiqalik sync’dan oldin yetkazadi, tunnel yoki PC uzilganda esa javobni AMT emas, Cloudflare edge’ning o‘zi (530) beradi [inference] (`amo_webhook_contract.retry_tradeoff`). O‘chgan hook jim qolmaydi: sync-worker `amo_webhook_liveness` tekshiruvi sync topgan status hodisalari `webhook_inbox` da yo‘qligini ko‘rsa `ALERT_WEBHOOK_SILENT` beradi va hook obunasi holatini kuniga bir marta o‘qiydi (INC-28). Hook faqat `add_lead` va `status_lead` hodisalariga obuna (HG-F2-04). Cloudflare challenge (WAF yoki Bot Fight) amoCRM uchun 5xx bo‘lmagan javob — faqat 3 urinish; `mar2/amo/*` challenge olmasligi F2-AT-24 da tekshiriladi.

**Kvota (✅ Q25).** amoCRM ceiling — 7 req/s (`approval-policy.yaml` `rate_limits.amocrm_global_rps_ceiling: 7`), barcha caller uchun umumiy: landing delivery (boshqa host, `LANDING_QUOTA_ALLOCATION_ID`), CAPI lookup, sync baseline va incremental, gateway MCP va operator integratsiya ishlari. `vendor.amocrm_quota` faqat 7 ichida taqsimlaydi yoki pasaytiradi (haqiqiy vendor limiti pastroq bo‘lsa o‘sha qo‘llanadi); yuqoriroq qiymat faqat yangi owner Q bilan; validator null yoki 7 dan katta qiymatni rad etadi. Variantlar: `quota-coordinator` (`amt-quota`) + bounded safe lease yoki konservativ cross-host ajratmalar; ajratmalar va burst yig‘indisi ceiling’dan oshmaydi. Tarix importi ≤2 req/s ★ va batch ≤50 ★ — ceiling ichidagi ajratma.

AMT yoki coordinator ishlamasa landing qabul ishlaydi; delivery faqat oldindan tasdiqlangan lokal bounded ajratma ichida davom etadi yoki `crm_pending`da turadi; kvota tugashi qabul ledger’ini yo‘qotmaydi. Alohida lokal to‘liq limitlar account limitini ko‘paytirmaydi. 429 → vendor `retry_after`/backoff; takroriy 429 yoki 403 → breaker va `ALERT_AMO_BREAKER` (403 da sotuv jamoasi akkauntini himoya qilish uchun to‘xtash); ko‘r-ko‘rona butun tarixni rescan qilish yo‘q.

## 5. Logical CAPI event va delivery ledger

### 5.1 Event xaritasi

`pipelines.yaml` `capi_event_map` bo‘yicha:

| `on` | Trigger | `event_name` | `action_source` | Holat |
|---|---|---|---|---|
| `lead_created` | landing submission `crm_confirmed`ga yetdi (server Lead); `add_lead` webhook faqat reconciliation | `Lead` | `website` | yoqilgan |
| `qualified` | `qualified_fact_rule` bajarildi (§3.1) | `QualifiedLead` | `system_generated` | yoqilgan |
| `contract_signed` | birinchi valid shartnoma fakti | `Contract` | `system_generated` | o‘chiq; `vendor.meta_capi` dalili va owner qarorisiz yoqilmaydi |

`event_name` bir marta ishlatilgach o‘zgarmaydi [D: ikkilamchi manba — Meta funnel bosqichlarini nom bo‘yicha bog‘laydi; `vendor.meta_capi`da tekshiriladi]. Event nomi, `action_source`, dataset va majburiy field’lar haqiqiy account bilan `vendor.meta_capi`da tasdiqlanadi; bu jadval vendor support kafolati emas. CRM hodisalari uchun CRM turidagi dataset yoki sales funnel sozlamasi kerak bo‘lishi mumkin [D: ikkilamchi manba]; Events Manager sozlamasini owner qo‘lda bajaradi (`events_manager_change`, NEVER_AUTO; HG-F2-05).

### 5.2 Payload (nomzod mapping)

| Event | Asosiy maydonlar |
|---|---|
| `Lead` | `event_id` = receipt’dagi (Pixel bilan dedup); `event_time` = original submission vaqti; `event_source_url`; `user_data`: `ph` (hash), `fbc`, `fbp`, `client_ip_address`, `client_user_agent`, `external_id` = sha256(amo_lead_id) ★ |
| `QualifiedLead`, `Contract` | `custom_data`: `event_source: crm`, `lead_event_source: amoCRM`, `pipeline` [D: ikkilamchi manba]; `user_data`: `ph`, `fbc`, `fbp`, `external_id` |

`user_data` faqat marketing consent valid bo‘lsa va vendor talab qilganidan ortiq bo‘lmagan holda yuboriladi; hash anonimlik kafolati emas (`hash_means_anonymous: false`). CAPI worker CRM kontaktini minimal vaqt xotirada oladi (`capi_in_memory` dataset); raw yoki hash telefon disk, warehouse, log yoki trace’da saqlanmaydi. `fbc`, `fbp`, IP va UA faqat purpose-valid custody’dan olinadi, agentga berilmaydi.

### 5.3 Ledger va holatlar

Bu bo‘limdagi enum’lar kanonik; [DATA_MODEL](DATA_MODEL.md), [OBSERVABILITY](OBSERVABILITY.md) va testlar shularni ishlatadi.

`capi_events` — bitta logical biznes event: `capi_event_id`, deterministik `event_id`, `event_name`, `source_event_key`, `pipeline_at_event`, original `event_time`, mapping/definition revision, `consent_ref`, `is_test`, `state`, `attempt_count`, `next_attempt_at`, nullable `provider_trace_id`. Canonical ID manba account + logical subject + event turidan deterministik olinadi; qualification’ga qayta kirish yoki mapping revision o‘zi yangi event yaratmaydi; cross-pipeline/account collision sinovi majburiy. Yetkazish navbati `delivery_outbox` qatori (`channel = capi`, `logical_key = event_id`), biznes holati esa faqat `capi_events.state`da.

| `capi_events.state` | Ma’no |
|---|---|
| `queued` | navbatda; consent, yosh va test tekshiruvi kutilmoqda |
| `sending` | attempt lease ostida yuborilmoqda |
| `sent` | provider so‘rovni qabul qildi (attribution yoki optimization muvaffaqiyati emas) |
| `retry_wait` | vaqtinchalik xato, backoff kutilmoqda |
| `uncertain` | javob noaniq (timeout, crash); reconcile bo‘lmaguncha qayta yuborilmaydi |
| `needs_review` | maksimal sanaladigan urinish tugadi yoki bitta eventning maydoni rad etildi (`permanent_error`); technical_operator `rejected` qiladi yoki `queued` ga qaytaradi (`needs_review_exits`) |
| `rejected` | vendor bitta eventni doimiy rad etdi va technical_operator buni `needs_review` da tasdiqladi |
| `dropped_uncertain` | `uncertain` attempt hard deadline (`vendor.meta_capi.uncertain_hold`) ichida ochiq ulanishda o‘z provider javobi bilan yopilmadi; yo‘qotilgan deb sanaladi (`capi_error_rate`, reconciliation hisoboti), qayta yuborilmaydi |
| `skipped_no_consent` | marketing consent yo‘q yoki qaytarib olingan |
| `skipped_too_old` | `event_time` vendor oynasidan tashqarida (`vendor.meta_capi.max_event_age`) |
| `skipped_test` | `is_test=true` va muhitda tasdiqlangan test kodi yo‘q |
| `skipped_unknown_prior_send` | faqat host-loss qayta qurishida: kafolatli cutoff’dan (oxirgi yaxshi off-host heartbeat’ning `observed_at` vaqti + lease, ya’ni ikki heartbeat oralig‘i, + soat zaxirasi) oldingi event; sabab `terminal_before_loss` (manba o‘zgarishi oxirgi yaxshi heartbeat’dagi `capi_terminal_before` dan oldin — event yo‘qolishdan oldin avtomatik yuborish yo‘lidan chiqqan: yuborilgan, rad etilgan, skip qilingan yoki `uncertain`/`needs_review`) yoki `unknown_state` (qolgani — yuborilgan-yuborilmagani noma’lum); qayta yuborilmaydi (bir manbali server eventi dedup’iga F2 dalilisiz tayanilmaydi, VR-33), audit bilan sanaladi (§8, `operations.yaml#host_loss.rebuild_from_sources`) |

`capi_attempts` — har tashqi so‘rov: `attempt_id`, `capi_event_id`, `attempt_no` (har so‘rov qatorining tartib raqami, hold’lar ham), `started_at`, `finished_at`, `result`, `request_hash`, `field_presence` bitmap, provider response code va trace ID; maksimal urinish faqat `counted_results` (`retryable_error`, `connect_error`) bo‘yicha `capi_events.attempts` da sanaladi — `auth_error` va `config_error` hold, urinish sarflanmaydi. Xom `user_data` hech qachon saqlanmaydi (`capi_attempt_evidence` dataset). `capi_attempts.result`: `accepted | retryable_error | connect_error | no_response | unclassified_error | batch_rejected | permanent_error | config_error | auth_error` (kanonik o‘tish xaritasi — [pipelines.yaml](../09_Config_Templates/pipelines.yaml) `capi_delivery.result_transitions`; Graph javobi → natija — `capi_delivery.vendor_error_map`). Meta xatoni so‘rov bo‘yicha qaytaradi, lekin xato qaytargan ko‘p eventli so‘rovning yaroqli eventlari baribir saqlangan bo‘lishi mumkin — yangi hujjat: «If any event in a batch is invalid, the request returns an error — but valid events with an `event_id` are still accepted» ([RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) VR-37); bir manbali `event_id` dedup’iga AMT F2 dalilisiz tayanmaydi (VR-33). Shuning uchun **saqlangan bo‘lishi mumkin bo‘lgan hech narsa qayta yuborilmaydi**: `batch_policy: realtime_single` — har so‘rovda bitta event (hajm kuniga 10–30 event, bir haftalik backlog ham bir necha yuz bitta eventli so‘rov), ko‘p eventli siyosat faqat F2 dedup dalili (`dedup_evidence_ref`) va owner qarori (◇) bilan; xato qaytargan ko‘p eventli so‘rov (`batch_rejected`), 5xx yoki tanilmagan javob (`unclassified_error`) va javobsiz so‘rov (`no_response`) — `uncertain`, avtomatik qayta yuborilmaydi. So‘rov darajasidagi xato (`config_error`: dataset yoki pixel ID, API versiyasi, yuqori darajadagi parametr) va token xatosi (`auth_error`) event xatosi deb o‘qilmaydi: hech narsa qayta ishlanmagan, event `retry_wait` da ushlanadi, urinish sanalmaydi, `ALERT_CAPI_FAILED` sabab `config` yoki `auth` ([SECURITY](SECURITY.md) §10: muddati o‘tgan credential capability’ni fail-closed qiladi, event’ni yo‘qotmaydi); sabab tuzatilgach yuborish davom etadi. Bitta eventning o‘z maydoni rad etilsa (`permanent_error`) event saqlanmagan — u `needs_review` ga o‘tadi, avtomatik terminal emas; technical_operator uni `rejected` qiladi yoki sabab tuzatilgach `queued` ga qaytaradi (`needs_review_exits`: biror attempt’i `no_response`, `unclassified_error` yoki `batch_rejected` bo‘lgan event qayta navbatga qo‘yilmaydi). Bir xil kodli ketma-ket 3 ta `permanent_error` (builder nomzodi) tizimli xato hisoblanadi: breaker navbatni ushlaydi (`ALERT_CAPI_FAILED` sabab `config`), cooldown’dan keyin bitta event half-open probe sifatida yuboriladi (`permanent_error_breaker`). `vendor_error_map` dagi qayta yuboradigan har qator (`auth_error`, `config_error`, `retryable_error`, `connect_error`) faqat o‘zining F2-AT-25 holati o‘tgandan keyin qo‘llanadi; ungacha bunday javob `unclassified_error`.

O‘tishlar: `queued → sending → sent`; `sending → retry_wait → sending` (`retryable_error`, `connect_error` — sanaladi; `auth_error`, `config_error` — hold, sanalmaydi); `sending → needs_review` (`permanent_error`, faqat bitta eventli so‘rov); `needs_review → rejected | queued` (technical_operator, audit bilan; `queued` faqat `needs_review_exits` sharti bilan); `sending → uncertain` (`no_response`: so‘rov yozildi, javob kelmadi; `unclassified_error`; `batch_rejected`); `connect_error` — ulanish rad etildi, DNS yoki TLS handshake so‘rov yozilishidan oldin uzildi, yuborilmagani isbotlangan (TLS 1.3 early data va client tomonidagi avtomatik retry o‘chiq — `capi_delivery.transport`); `uncertain → sent` faqat o‘sha attempt’ning o‘z provider javobi (`request_hash` va trace ID bilan) ochiq ulanishda soft deadline (`vendor.meta_capi.request_timeout`) dan keyin, hard deadline (`vendor.meta_capi.uncertain_hold`, daqiqalar) ichida kelsa; hard deadline’da ulanish yopiladi va javob endi kela olmaydi — `uncertain → dropped_uncertain` darhol (terminal: event yo‘qotilgan deb sanaladi va `capi_error_rate` hamda reconciliation hisobotida ko‘rinadi; Meta production eventi uchun event bo‘yicha read-back bermaydi, `pipelines.yaml#capi_delivery.uncertain_resolution`); `uncertain` hech qachon avtomatik qayta yuborilmaydi — bir manbali `event_id` dedup’i F2 dalilisiz kafolat emas (VR-33); `retry_wait → needs_review` (maksimal sanaladigan urinish); `queued → skipped_no_consent | skipped_too_old | skipped_test | skipped_unknown_prior_send` (oxirgisi faqat host-loss qayta qurishida, §8). Host-loss qayta qurishida qayta yaratilgan event (§8): manba o‘zgarishi kafolatli cutoff’dan kechroq bo‘lsa — `queued` (odatdagi yuborish yo‘li); qolgani — `skipped_unknown_prior_send`, sababi bilan (`terminal_before_loss` yoki `unknown_state`); yangi attempt yozilmaydi.

### 5.4 Yetkazish qoidalari

- Maksimal event yoshi — `vendor.meta_capi.max_event_age` (nomzod 7 kun [D: ikkilamchi manba]); eskisi `skipped_too_old`. Yosh faqat `queued` da emas, **batch qurilayotganda** ham tekshiriladi: `event_time < now − (max_event_age − send_age_margin)` bo‘lgan event so‘rovga kirmaydi va `skipped_too_old` bo‘ladi (`vendor.meta_capi.send_age_margin`: `clock_margin` + so‘rov vaqti, ya’ni bir necha daqiqa, soatlar emas — har so‘rovda bitta event, eskirgan event faqat o‘zini rad ettiradi) — event so‘rov yo‘lida 7 kunlik chegaradan o‘tib ketmaydi (`pipelines.yaml#capi_delivery.age_check`). Original `event_time` saqlanadi, eski hodisa "hozir" qilib yuborilmaydi.
- Dispatch lease: capi-bridge eventni faqat `amt.monitor_acks` dagi ACK olgan oxirgi heartbeat’ning `observed_at` (yuborilgan) vaqtidan beri lease (ikki heartbeat oralig‘i) o‘tmagan bo‘lsa yuboradi (`operations.yaml#host_loss.capi_dispatch_lease`); lease ACK kelgan paytdan emas, shu vaqtdan o‘lchanadi, heartbeat so‘rovi `heartbeat_timeout` (30 s) dan keyin tashlanadi; qatorni monitor heartbeat’ni ACK qilganda `amt-control` yozadi, `amt_capi` faqat o‘qiydi; monitor yetmasa eventlar `queued` da kutadi; o‘chgan monitor o‘zi alert bera olmagani uchun host tomonidagi `ALERT_MONITOR_UNREACHABLE` ishlaydi (`operations.yaml#host_loss.monitor_unreachable_alert`, INC-27), yo‘l to‘silgan bo‘lsa monitorning dead-man alerti ham (F2-AT-23). Heartbeat `capi_terminal_before` ni olib boradi: avtomatik yuborilishi mumkin bo‘lgan (`queued`, `sending`, `retry_wait`) eventlarning eng erta manba o‘zgarishi va manba sinxron watermark’ining kichigi — `uncertain` va `needs_review` avtomatik qayta yuborilmaydi, shuning uchun uni ushlab turmaydi; `amt-control` uni va heartbeat’ning boshqa maydonlarini faqat `amt.heartbeat_snapshot()` (`SECURITY DEFINER`) orqali oladi, `now − capi_terminal_before` 1 soatdan oshsa `ALERT_CAPI_FAILED` (manba o‘zgarishi — eventning trigger vaqti: CRM tasdig‘i, qualified yoki shartnoma fakti; host yo‘qolgandan keyin u amoCRM tarixidan qayta olinadi, Meta’ga yuboriladigan original `event_time` emas) — undan oldingi hech bir manba o‘zgarishi endi avtomatik yuborilmaydi (`heartbeat_capi_field`). Host yo‘qolsa 1- va 2-qoida shularga tayanadi (§8).
- Batch hajmi (`batch_policy: realtime_single`, bitta event), dedup oynasi (Pixel va server eventi orasidagi `event_id` dedup’i — 48 soat; «single source is not deduplicated» gapi Meta hujjatida fbp/external_id usuliga tegishli, `event_id` usuli esa bir manbali takror haqida jim, yangi Batch Requests matni bir xil `event_id` + `event_name` uchun birinchi nusxa qoladi deydi — VR-33, VR-37; shuning uchun server eventi F2 dalilisiz hech qachon dedup’ga tayanib qayta yuborilmaydi, §8), maksimal retry va rate limit `vendor.meta_capi`dagi pinned kontraktda; tekshirilmagan raqamlar production faktiga aylanmaydi. Timeout tashqi idempotency bor degani emas.
- Test: `is_test=true` hodisa production optimizatsiyaga hech qachon kirmaydi; faqat shu muhitda tasdiqlangan test kodi bo‘lsa (`environments.yaml` `capi_test_code_ref`) Events Manager Test Events’ga yuboriladi, aks holda `skipped_test`.
- Kill: CAPI delivery `killed`da ham davom etadi (`execution-policy.yaml` `kill_allows: capi_delivery`). DB yoki custody ishlamasa yangi accept yoki ACK berilmaydi.
- Backfill durable cursor va event ledger’dan, joriy consent/withdrawal, event-time asosi va test classification bilan. Restore’da avval read/ingest va remote reconciliation, keyin consent-valid va time-valid CAPI; qayta yuborish dedup’ga tayanmaydi — host-loss qayta qurishida faqat yo‘qolgan host yubora olmagan event qayta yuboriladi; `capi_terminal_before` dan oldingisi va holati noma’lum qolgani `skipped_unknown_prior_send` (§8). Yo‘q event history joriy statusdan uydirilmaydi; noma’lum qamrov hisobotda ko‘rsatiladi. Ops bot yoki LLM ishlamasa hot path davom etadi.

## 6. Tracking health va gate holat mashinasi

### 6.1 Grain va holatlar

`tracking_health` grain: pipeline × check × business_date × measurement_revision; `measured_at`, `source_fresh_until`, `sample_size`, `data_status`. Job har kuni 09:30, `sync-worker --job tracking-health`, UID `amt-sync` (`operations.yaml` `tracking_health`). Check holatlari (`check_states`): `pass`, `warn`, `fail`, `unknown`, `stale`, `low_n`, `not_applicable`. Har check sxemasi (`check_schema`): `unit`, `direction`, `denominator`, `window`, `min_sample`, `warn`, `fail`; qiymatlar `tracking.thresholds`da tasdiqlanadi, uydirma default yo‘q. Missing job eski `pass`ni saqlamaydi.

### 6.2 Check’lar

| Check | Ma’no | Gate |
|---|---|---|
| `fbc_share`, `fbp_share` | consent-eligible va manbaga mos denominator bilan coverage | gate |
| `untagged_leads` | kelishilgan javob lag’idan keyin klassifikatsiyasiz qolgan lead’lar (lag — `sales.sop`) | gate |
| `capi_error_rate` | yakuniy xato (`rejected`, `dropped_uncertain`) + unresolved (`uncertain`, `needs_review`) ulushi (`tracking-health.yaml#checks.capi_error_rate.counts`); attempt/event denominatori explicit | gate |
| `pixel_capi_dedup` | accountda o‘lchanadigan Pixel/server juftligi; mavjudligi dalil bilan | gate |
| `pixel_vs_crm_leads` | original event kuni va delivery lag moslashtirilgan nisbat | gate |
| `accepted_vs_crm_receipts` | accepted receipt → tasdiqlangan CRM farqi, pending/needs_review | gate |
| `queue_oldest_age` | hali yetkazilmagan eng eski receipt/outbox, retry va dead-letter soni | gate |
| `sync_freshness` | CRM va Meta kerakli manbalarining oxirgi durable sync’i | gate |
| `capi_lag_p95` | source event → provider qabul; maqsad `tracking-health.capi_lag_p95.target_minutes` (15 daqiqa; NFR-08), normal yuk konverti ichida (`ops.resource_envelope`) | informational |
| `emq` | vendor accountda mavjud va ishonchli o‘lchov bo‘lsa (`vendor.meta_capi`) | informational |

CAPI lag va intake delivery yoshi alohida. Accepted = CRM faqat kunlik jami emas: har submission matching, duplicate va pending yoshi tekshiriladi; bitta submission yo‘qolib, boshqa duplicate bilan jami teng bo‘lib qolishi PASS bermaydi. `pixel_capi_dedup` va `sync_freshness`ning Meta qismi `amt-read` tokeniga tayanadi, shuning uchun HG-F2-19 (`amt-read`) F2 davomida kerak.

### 6.3 Jonli ketma-ketlik va soat (✅ Q37)

`live_sequence`: `F2_LIVE_INTAKE_ready` → HG-F2-09 → `real_lead_e2e_evidence` → `14_days_report_only` → `owner_threshold_approval` → `7_consecutive_all_gate_checks_pass` → HG-F2-08.

- `F2_LIVE_INTAKE_ready`: UAT-08–12, intake recovery va mustaqil monitoring (HG-F2-14), privacy va operator readiness yopilgan.
- HG-F2-09: owner yoki targetolog jonli Meta ad’larining manzilini `go.wolter.uz` va §2 shabloniga ko‘chiradi.
- Report-only soati HG-F2-09 ro‘yxatidagi barcha jonli ad `go.wolter.uz`ga yo‘nalgan paytdan boshlanadi (`report_only_clock_starts`); qisman ko‘chirish soatni boshlamaydi.
- `real_lead_e2e_evidence`: kamida bitta haqiqiy (test emas) lead uchun klik → durable accepted → `crm_confirmed` → Pixel/server `Lead` dedup → call-center qualification → consent-valid `QualifiedLead` Events Manager’da qabul qilingani PII’siz ID’lar bilan dalillangan; test event uning o‘rnini bosmaydi. 14 kunlik oyna shu dalilsiz yopilmaydi.
- 14 kun `mode: report_only`: chegara qo‘llanmaydi; qiymat, haqiqiy N, consent va missingness yoziladi.
- Owner threshold tasdig‘i: builder funnel-analyst’ning `funnel-metrics` protsedurasi bilan 14 kunlik data asosida chegaralarni taklif qiladi (agentlar F4_AGENTS dan oldin ishlamaydi, ◇ P-31), owner PR orqali `tracking.thresholds`ni tasdiqlaydi; `warn` qoidasi va read_only’dan chiqish N’i shu yerda. Threshold F5’da qayta uydirilmaydi.
- 7 ketma-ket barcha gate check PASS kun (`tracking.pass_7d`) → HG-F2-08 (`F2_TRACKING_PASS`).

### 6.4 Streak va read_only

- PASS streak faqat `pass`ni sanaydi; `fail`, `unknown`, `stale` va `low_n` uni uzadi (`streak_rules`). `not_applicable` faqat owner tasdiqlagan alohida check uchun. `warn` ⧗ OD-17: qaror bo‘lguncha `warn` PASS sanalmaydi.
- Kun "barcha gate PASS" bo‘lishi uchun har pipeline’dagi har gate check `pass` yoki owner tasdiqlagan `not_applicable` bo‘lishi kerak.
- Jonli rejimda biror gate check bir kun `fail` → `ALERT_TRACKING_FAIL`. Kamida bitta gate check (istalgan check, istalgan pipeline) `fail` bo‘lgan kun — fail kuni (`fail_day_scope: any_gate_check`, ✅ Q37). Fail-kun streak 2 ga yetsa → global `read_only` (`tracking_read_only`) va `ALERT_READ_ONLY` (`reason=tracking`; `fail_days_to_read_only: 2`). Streak barcha gate check `pass` bo‘lgan kun bilan nolga tushadi; `unknown`, `stale`, `low_n` (va OD-17 hal bo‘lguncha `warn`) kunlari uni oshirmaydi ham, nolga ham tushirmaydi (`fail_streak`).
- Missing yoki stale kerakli signal risk oshiruvchi dispatch’ni ikki kunni kutmasdan darhol bloklaydi (`unknown_or_stale: block_risk_increase_by_freshness_policy`, `tracking.freshness`).
- Joriy `read_only` yoki `killed` har doim ustun. Fleet freshness va sale readiness tracking check’larining o‘rnini bosmaydi — ular parallel guard.

### 6.5 read_only’dan chiqish (◇ P-18)

`exit_read_only`: `tracking.thresholds`da tasdiqlangan N ketma-ket barcha gate PASS kun (`consecutive_pass_days`) va owner `/resume` (`requires_owner_resume: true`). N tasdiqlanmaguncha avtomatik chiqish yo‘q (⧗ OD-17). Bitta PASS kun yoki threshold’ni yumshatish read_only’ni ochmaydi.

## 7. Umami, Clarity va optimization capability

| | Umami | Microsoft Clarity |
|---|---|---|
| Joy | production Dokploy, `stats.wolter.uz` (HG-F2-02, HG-F2-11) | SaaS (HG-F2-03) |
| Maqsad | trafik, manba, sahifa va variant bo‘yicha konversiya; `lead_submit` event faqat durable acceptance’dan keyin, `variant_id` bilan | heatmap va sessiya yozuvlari — CRO uchun |
| Cookie | cookiesiz, tasdiqlangan policy bilan | cookie; faqat marketing consent’dan keyin yuklanadi ★ |
| Maskalash | — | strict masking: barcha input maydonlari ★; forma qiymati va PII yozilmasligi real test bilan (F2-AT-11) |
| Agent kirishi | `analytics.umami_query` (read-only) | `analytics.clarity_export` (Data Export API; imkoniyat va limitlar F3’da tekshiriladi [?]; bo‘lmasa owner asoslagan disabled optional feature, taxminiy data yo‘q) |

GA4 ishlatilmaydi (✅ Q45); Clarity–GA4 integratsiyasi yoqilmaydi.

**Optimization maqsadi (✅ Q29.1).** `business-policy.yaml` `qualified_optimization_rule` (pipeline bo‘yicha, oldingi kalendar oyi, oylik qayta o‘lchash, `QualifiedLead` ga o‘tish ketma-ket 2 oyda, qaytish birinchi past oyda — ◇ P-45): `QualifiedLead` bo‘yicha optimizatsiya faqat (a) account eligibility dalili VA (b) Funnel Analyst F2’da amoCRM’dan o‘lchagan oylik hajm owner mo‘ljali va Meta’ning joriy rasmiy talabidan (sanasi bilan [D] manba) kattasiga yetsa tanlanadi; aks holda Meta `Lead` bo‘yicha optimallashadi, qualified esa guardrail bo‘lib qoladi. Owner qarori matnidagi mo‘ljal ~200 lead/oy (`owner_volume_floor_per_month: 200`) pastki chegara; Meta talabi yuqoriroq bo‘lsa o‘sha qo‘llanadi, manbasi `vendor_requirement_ref`da. `vendor.qualified_optimization` qiymat sxemasi — har pipeline uchun bitta yozuv: `{pipeline, supported, counted_event, measured_monthly_volume, measured_window, measured_at, previous_measurement, vendor_requirement_ref, vendor_conditions, selected_goal}` (gate `F5_GO`; [CONFIG_CONTRACT](../11_Production_Contracts/CONFIG_CONTRACT.md) §4.1, ◇ P-45/P-56). Ikkilamchi manbalardagi eligibility belgilari [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md)da qayta tekshiriladigan da’vo, threshold emas. Signal sifatining o‘zi vendor eligibility kafolati emas. Event/dataset sozlamasini owner Events Manager’da qo‘lda, NEVER_AUTO jarayon bilan qiladi; optimization event almashuvi katta o‘zgarish sifatida owner qaroriga chiqadi.

## 8. Consent, recovery va qabul

Xizmat so‘rovi uchun `service_fulfilment`, reklama va tracking uchun `marketing_measurement` alohida purpose (`privacy-policy.yaml` `purposes`). Formadagi xizmat roziligi Pixel, Clarity yoki CAPI roziligini majburan bermaydi; noma’lum marketing ruxsati deny. Withdrawal keyingi send va backfill’dan oldin tekshiriladi.

Rozilik matni: builder qoralaydi, owner (kerak bo‘lsa yurist bilan) va `privacy_owner` tasdiqlaydi (`privacy.purposes`, HG-F2-07); builder yuridik xulosa bermaydi. Matnda: kim yig‘adi — controller (GETNOW MChJ / Wolter; privacy_owner tasdiqlaydi); qaysi ma’lumot (ism, telefon, texnik identifikatorlar, cookie); maqsadlar (murojaatga javob; reklama samaradorligini o‘lchash); qabul qiluvchilar (amoCRM, Meta va TLS’ni edge’da tugatadigan Cloudflare — `privacy-policy.yaml#off_host_flows`, ◇ P-76) va ularning ma’lumot joylashuvi [?]; xorijga uzatish asosi; saqlash muddati (`privacy.retention`); rozilikni qaytarib olish yo‘li. Matn o‘zbek lotin va rus tilida. Xizmat roziligi forma ostida majburiy; marketing roziligi alohida va ixtiyoriy; Pixel va Clarity cookie’lari banner roziligiga bog‘langan ★. Amaldagi qonun matni va tahrirlari privacy mas’uli tomonidan sana bilan tekshiriladi [?]; breach javobi `privacy.breach_response` (⧗ OD-16).

PII custody `privacy-policy.yaml` `datasets` inventarizatsiyasi bo‘yicha: `landing_submission_store`, `webhook_inbox` (lead PII’siz, Q62), `capi_in_memory`, `capi_attempt_evidence`, `amocrm_contacts` va `backups`; har birida host, custodian, purpose, field’lar, kalit, retention va withdrawal yo‘li bor. Restore tartibi: read/ingest → remote reconciliation → consent-valid CAPI backfill → tracking/freshness gate → owner resume.

**AMT host yo‘qolsa — manbalardan qayta qurish (Q55).** Lokal snapshot faqat mantiqiy xatodan himoya qiladi. PC buzilsa disklar boshqa PC’ga ko‘chiriladi va ledger’lar saqlanadi. Ikkala disk yo‘qolsa yoki o‘g‘irlansa AMT tomondagi intake va CAPI holati (`submission_delivery`, `webhook_inbox`, `capi_events`/`capi_attempts`, sync cursor’lari) yangi PC’da (`00-owner-bootstrap.sh --rebuild`) manbalardan qayta quriladi: landing receipt’lari (production Dokploy, `landing_submission_store`) va amoCRM lead va event tarixi o‘qiladi, `submission_delivery` va qualified faktlar (§3.1) qayta hosil qilinadi, CAPI event’lari o‘sha deterministik `event_id` bilan qayta yaratiladi. `capi_attempts` disklar bilan yo‘qolgani uchun qaysi event Meta’ga yetgani noma’lum, qayta yuborish esa dedup’ga tayanmaydi: bir manbali `event_id` dedup’i F2 dalilisiz kafolat emas (VR-33 — «single source is not deduplicated» va «two consecutive server events … we do not discard either» gaplari Meta hujjatida fbp/external_id usuliga tegishli, `event_id` usuli bu haqda jim; VR-37 — yangi Batch Requests matni bir xil `event_id` + `event_name` uchun birinchi nusxa qoladi deydi), `QualifiedLead` va `Contract` esa faqat server eventlari (§5.1). Shuning uchun consent-valid va Meta’ning 7 kunlik oynasidagi (`vendor.meta_capi.max_event_age`) event uch qoida bilan ajratiladi (`operations.yaml#host_loss.rebuild_from_sources`): (1) manba o‘zgarishi oxirgi yaxshi off-host heartbeat’ning `observed_at` vaqti, lease (ikki heartbeat oralig‘i) va soat zaxirasidan **kechroq** bo‘lsa — qayta yuboriladi: capi-bridge faqat ACK olgan oxirgi heartbeat’ning `observed_at` (yuborilgan) vaqtidan beri lease o‘tmagan bo‘lsa yuboradi (`capi_dispatch_lease`; lease ACK kelgan paytdan emas, shu vaqtdan o‘lchanadi — kechikkan ACK uni uzaytirmaydi), shuning uchun yo‘qolgan host bu eventni yubora olmagan; qoida faqat monitor yozuvi o‘sha davr uchun butun bo‘lsa ishlatiladi (monitor har heartbeat’ni ACK qilishdan oldin saqlaydi), aks holda hammasiga 3-qoida; (2) manba o‘zgarishi oxirgi yaxshi heartbeat xabar bergan `capi_terminal_before` vaqtidan oldin bo‘lsa — event yo‘qolishdan oldin avtomatik yuborish yo‘lidan chiqqan (yuborilgan, rad etilgan, skip qilingan yoki `uncertain`/`needs_review`) — qayta yuborilmaydi; (3) qolgan har event qayta yuborilmaydi. 2- va 3-qoidadagilar `skipped_unknown_prior_send` (sabab `terminal_before_loss` yoki `unknown_state`), audit bilan sanaladi. Oynadan eskisi `skipped_too_old`. Yangi host ishga tushishidan oldin writer fence: eski Tailscale tuguni olib tashlanadi, Cloudflare Tunnel tokeni aylantiriladi va barcha mavjud tunnel ulanishlari API bilan majburan uziladi (aylantirishning o‘zi ishlab turgan connector’ni uzmaydi), connector ro‘yxatida faqat yangi host qolgani tekshiriladi ([BACKUP_RESTORE §5](../06_Runbooks/BACKUP_RESTORE.md)) — eski host yozuvchi bo‘lib qaytmasligi uchun. Lead’lar yo‘qolmaydi; AMT tarixi (approval, audit, readiness imzolari, ledger’lar) qayta tiklanmaydi — qabul qilingan risk. Mashq — `restore_drill` konteynerida, tashqi egress’siz: owner chiqargan PII’siz manba eksporti (landing receipt metadata’si — receipt ID, vaqtlar, consent bayroqlari, event ID, ism va telefon yo‘q; amoCRM events eksporti — lead ID, pipeline, status, vaqtlar) read-only fayl sifatida beriladi va CAPI qayta yuborish konteyner ichidagi sintetik endpoint’ga boradi; uch son — qayta yuborilgan, `terminal_before_loss` va `unknown_state` — sanaladi (F6-AT-09, UAT-23); sintetik endpoint Meta dedup’ini isbotlamaydi va bunday da’vo qilinmaydi.

Testlar: UAT-08 (crash/restart/deploy), UAT-09 (CRM success+timeout, client resend, ikki worker), UAT-10 (disk to‘la, deadline), UAT-11 (purpose, withdrawal, retention), UAT-12 (ACK chegarasi, out-of-order, poison, barcha caller kvotasi); UAT-03–07 biznes event, kohorta va zero-qualified; UAT-23/24 isolated restore; UAT-26 asset va offer; UAT-29 off-host signal. Faza testlari: F2-AT-03 (`fbc`), F2-AT-04 (§3 field’lari), F2-AT-06 (dedup), F2-AT-07 (`QualifiedLead`; lag `tracking-health.capi_lag_p95.target_minutes` bilan solishtiriladi), F2-AT-10 (eski event → `skipped_too_old`, `vendor.meta_capi.max_event_age`), F2-AT-12 va F2-AT-20 (consent), F2-AT-14 (§6 check’lari, `amt-sync` UID’da), F2-AT-15 (§2 UTM shabloni), F2-AT-17–19 (durable intake, CRM noaniqligi, webhook ACK), F3-AT-11 (amoCRM ✅ Q25 ceiling ichida). Test lead klassifikatsiyasi immutable; production CRM statusini test uchun agent o‘zgartirmaydi, owner yoki call-center belgilangan test resursida bajaradi. Dalillar [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) bo‘yicha; hozirgi matn `not_run` talab.
