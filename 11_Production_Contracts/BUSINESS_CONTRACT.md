# Biznes natijasi va xizmatga tayyorlik shartnomasi

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23 · Hisobot va operatsion vaqt: Asia/Tashkent.

Bu hujjat Wolter AMT uchun biznes atamalari, hisob birligi, manba va qarorga kirish shartlarining kanonik manbai; [CONTEXT](../CONTEXT.md) va [GLOSSARY](../10_Reference/GLOSSARY.md) shu ta’riflarga havola qiladi. Owner qarorlari (✅) va [INVARIANTS](INVARIANTS.md) bu hujjatdan ustun; ziddiyatda qattiqroq qoida amal qiladi. Machine qiymatlar [business-policy.yaml](../09_Config_Templates/business-policy.yaml), [capacity-policy.yaml](../09_Config_Templates/capacity-policy.yaml), [sale-readiness.yaml](../09_Config_Templates/sale-readiness.yaml), [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml) va [pipelines.yaml](../09_Config_Templates/pipelines.yaml) da. Raqamli threshold, odam, manba adapteri va noma’lum qiymatlar [readiness reyestri](../09_Config_Templates/readiness.yaml) orqali tasdiqlanadi. Hujjatning mavjudligi runtime PASS yoki biznes natijasi dalili emas.

## 1. Qamrov va biznes natijasi

Wolter B2C kuryerlarga elektr velosiped sotadi va ijaraga beradi. AMT pullik Meta reklamasining strategiya, kampaniya, kreativ, landing va funnel tahlili konturini boshqaradi. Olti agent, Hermes CMO va Paperclip orkestratsiyasi saqlanadi. Organik SMM, DM, mijozga xabar, sotuvchiga vazifa berish, to‘lov undirish, shartnoma tuzish yoki ERP qurish bu qamrovga kirmaydi (✅ Q01, Q02, Q05, Q06→Q14, Q18/Q42).

North Star — `sale` va `rent` bo‘yicha qualified lead; guardrail — lead→shartnoma konversiyasi (✅ Q04). U qo‘shimcha iqtisodiy guardrail’lar bilan birga baholanadi: yetilgan shartnoma konversiyasi, haqiqiy cash/refund, contribution, xizmatga tayyorlik va ijara sig‘imi (◇ P-08, §4.1). Ijara va sotuv maqsadlari ajratiladi (★ Q43★). Rent maqsadi — ishga yaroqli park bandligini va amaldagi kutayotgan talabni kerakli diapazonda eng kam acquisition sarfi bilan ushlash. Sale maqsadi — haqiqiy xizmat sig‘imi va iqtisodiy chegaralar ichida sifatli yangi talabni oshirish. Byudjet limiti sarflanishi shart bo‘lgan reja emas.

## 2. Hisob birligi va hodisalar

| Birlik | Majburiy ajratish va kalit |
|---|---|
| Murojaat | Durable `submission_id`, sanitizatsiyalangan `lead_id`, manba va qabul vaqti; qayta yuborish yangi acquisition emas |
| Qualified | Bitta `lead_id × pipeline` uchun birinchi valid qualified fact (§3.1); qayta statusga kirish yangi North Star emas |
| Acquisition episode | Tasdiqlangan dedup qoidasiga ko‘ra bir yangi mijoz ehtiyoji; bir nechta lead va `sale↔rent` ko‘chishi bog‘lanadi |
| Shartnoma | Manbadagi `contract_id`, pipeline, acquisition episode va offer revision; bir lead’dan bir nechta shartnoma chiqishi mumkin |
| Pul hodisasi | Manbadagi payment/refund ID, `contract_id`, integer minor unit, currency, effective/received time, correction reference |
| Fulfilment | Sale topshirilishi yoki rent boshlanishi/qaytarilishi uchun alohida source event; shartnomadan avtomatik chiqarilmaydi |
| Ijara davomiyligi | Yangi ijara, renewal va yakun alohida; renewal yangi acquisition sifatida sanalmaydi |
| Fizik velosiped | Muayyan snapshot’dagi yagona velosiped; oylik tranzaksiya soni bu birlik emas |

Biznes hodisalari ketma-ket bitta status zanjiri emas (`pipelines.yaml#lifecycle_is_linear: false`). `lead_created`, `contacted`, `qualified`, `contract_signed`, `payment_received`, `delivered`, `rental_started`, `renewal`, `cancelled`, `refunded` mustaqil fact’lardir. Pul shartnomadan oldin kelishi, bo‘lib to‘lash topshirishdan keyin davom etishi, refund qisman va cancellation’dan boshqa vaqtda bo‘lishi mumkin. Kelmagan hodisa `unknown/pending`; u nol, to‘langan yoki bajarilgan deb talqin qilinmaydi.

Har bir fact manba event ID yoki tasdiqlangan composite key bilan idempotent ingest qilinadi; `occurred_at`, `received_at`, source revision va correction/reversal bog‘lanishi saqlanadi. Status orqaga qaytishi tarixiy fact’ni o‘chirmaydi. Dublikat merge va correction keyingi hisobotga measurement revision bilan kiradi. Qualification bekor topilsa uning invalidation sababi va qayta hisoblangan period ko‘rsatiladi; oldingi hisobot jimgina almashtirilmaydi.

Agent ombori PII saqlamaydi (✅ Q28). Mijoz bilan bog‘lovchi asl hujjat va kontaktlar biznesning vakolatli manbasida qoladi; AMT’da custody reference, psevdonim kalit va kerakli agregatlar bo‘ladi. PII saqlanadigan har joy `privacy-policy.yaml#datasets` inventarida maqsad, kalit, retention va withdrawal bilan yozilgan. CAPI uchun telefon manbada SHA-256 bilan hash qilinadi; hash ham anonimlik kafolati emas. Consent maqsad, versiya va withdrawal bilan yuritiladi; xizmat so‘rovi roziligi marketing/CAPI ruxsati o‘rniga o‘tmaydi.

## 3. Qualified ta’rifi va sales sifati

Qualified lead uchun uchala shart vakolatli call-center xodimi tomonidan tasdiqlanadi (✅ Q16):

1. Murojaatchi bilan haqiqiy aloqa bo‘lgan.
2. Uning kuryer ekani tasdiqlangan.
3. Sotib olish yoki ijaraga olish niyati 30 kun ichida.

Kontaktga chiqilmagan, kuryer bo‘lmagan yoki faqat uzoq muddatga qiziqqan murojaat qualified emas. Status mapping [pipelines.yaml](../09_Config_Templates/pipelines.yaml) orqali shu ta’rifga bog‘lanadi; status nomining o‘zi semantik dalil emas. Ta’rif call-center bilan yozma kelishiladi (✅ Q42; HG-F2-06, `business.qualification`).

`sales_lead` quyidagilarni yozma tasdiqlaydi (`sales.sop`, `sales.qa`): ish vaqti, birinchi aloqa va qayta urinish qoidasi, yakuniy reason code’lar, qualification evidence maydonlari, backlog va response lag chegarasi, QA tanlanmasi, aniqlik chegarasi va o‘rinbosar. AMT suhbat yoki kontaktlarni agentga uzatmaydi; QA natijasi agregat va audit reference ko‘rinishida keladi. Inson SOP’ni sotuv jamoasi bajaradi; AMT sotuvchilarga avtomatik task yaratmaydi.

QA failed, backlog me’yordan yuqori, status mapping o‘zgargan yoki lag ma’lumoti eskirgan bo‘lsa bu o‘lchov va sales readiness’ga ta’sir qiladi. Analyst C05 sabab tahlili qiladi; qualified event asosidagi yangi scale yoki optimization qarori tegishli gate tiklanmaguncha o‘tmaydi. Muammo marketing sifati deb avtomatik yozilmaydi.

### 3.1 Qualified fact qoidasi (◇ P-19)

Qualified fact — `lead_id × pipeline` ning `pipelines.<pipeline>.qualified_status_ids` dagi statusga birinchi o‘tishi, agar o‘tishni `qualified_fact_rule.allowed_actor_user_ids` dagi call-center foydalanuvchisi qilgan bo‘lsa va sales_lead tasdiqlagan `required_evidence_field_ids` (bo‘lsa) to‘ldirilgan bo‘lsa. Event vaqti — o‘tishning `occurred_at` vaqti. Keyingi QA natijasi yangi measurement revision yoki invalidation yaratadi; owner boshqacha qaror qilmasa real-time CAPI’ni bloklamaydi. CAPI trigger’lari (`pipelines.yaml#capi_event_map`): server `Lead` — landing submission `crm_confirmed` bo‘lganda; amoCRM `add_lead` webhook faqat reconciliation uchun; `QualifiedLead` — qualified fact qoidasi bajarilganda.

### 3.2 Optimizatsiya event’i (✅ Q29.1)

Meta `QualifiedLead` bo‘yicha faqat ikki shart birga bajarilsa optimallashtiriladi: (a) akkauntda eligibility dalili bor; (b) Analyst F2’da amoCRM’dan o‘lchagan oylik hajm owner mo‘ljali (~200 lead/oy, `owner_volume_floor_per_month`) va Meta’ning joriy rasmiy talabidan (manba sana bilan [D]) kattasiga yetadi. Aks holda optimizatsiya `Lead` bo‘yicha, qualified esa guardrail bo‘ladi. Qaror `vendor.qualified_optimization` da, har pipeline uchun alohida (`supported`, `counted_event`, `measured_monthly_volume`, `vendor_conditions`, `selected_goal`; [CONFIG_CONTRACT](CONFIG_CONTRACT.md) §4.1). Sanaladigan hodisa — Meta’ga atributsiya qilingan `crm_confirmed` landing murojaati (server `Lead` trigger’i, ◇ P-19), oyna — oldingi kalendar oyi (owner birligi "lead/oy" aynan; oxirgi 28 kunlik hisob samarali chegarani ≈ 217/oy ga ko‘tarardi, ◇ P-56), qayta o‘lchash — har oyning birinchi dushanbasi (`qualified_volume_check`); `QualifiedLead` ga o‘tish — ketma-ket 2 oylik o‘lchovda shart bajarilsa, `Lead` ga qaytish — birinchi past o‘lchovda (Q29.1 matnicha, yumshoqroq band yo‘q); almashtirishni faqat owner qiladi (`events_manager_change`; `decision-statistics.yaml` Q29_1_VOLUME, ◇ P-45). Qaysi goal tanlanmasin, `QualifiedLead` CAPI orqali yuborilishda davom etadi. Faqat eligibility’ga tayangan qoida kerak bo‘lsa — yangi owner Q (⟲ Q29.1).

### 3.3 amoCRM yuklama chegarasi (✅ Q25)

amoCRM — call-center’ning ishlab turgan tizimi. AMT’ning barcha chaqiruvchilari (landing, capi-bridge, sync-worker, gateway MCP, tarix importi) birgalikda `approval-policy.yaml#rate_limits.amocrm_global_rps_ceiling: 7` so‘rov/s ichida ishlaydi. `vendor.amocrm_quota` bu ceiling’ni faqat taqsimlaydi yoki pasaytiradi; undan yuqori qiymat faqat yangi owner Q bilan. Limit tugasa intake yo‘qolmaydi: murojaat durable navbatda `crm_pending` bo‘lib kutadi.

## 4. Shartnoma, pul va contribution manbalari

Owner tayinlagan moliya mas’uli (`finance_owner`) va uning o‘rinbosari mavjud biznes manbasidan ma’lumot beradi: masalan, vakolatli hisob tizimi eksporti, to‘lov reyestri yoki kelishilgan boshqariladigan jadval. Qaysi manba haqiqiy hisob manbai ekani `business.outcome_sources` da yoziladi; AMT yangi ERP yoki bank tizimi sifatida ishlamaydi.

Manba kontrakti kamida quyidagilarni yopadi: export/API egasi, dataset va source IDs, cadence va freshness, correction/refund tartibi, currency va timezone, `contract_id` mapping, yangi/renewal belgisi, offer revision, haqiqiy payment, depozit, refund, fulfilment va tegishli o‘zgaruvchan xarajatlar. Har ingest’da source count/total va AMT total reconcile qilinadi; unmatched yoki kechikkan yozuvlar alohida ko‘rsatiladi. Agentlar uchun kerakli agregatlar `wh.metrics`/`wh.query` orqali beriladi; bu hujjat yangi moliyaviy write tool vakolati bermaydi.

| Metrika | Hisob va cheklov |
|---|---|
| Shartnoma qiymati | Tasdiqlangan kelishuv summasi; cash yoki tan olingan daromad bilan tenglashtirilmaydi |
| Tushgan pul | Real payment event’lar jami; refundable deposit va boshqa turlar alohida |
| Refund | Haqiqiy chiqim hodisasi, original payment/contract’ga bog‘langan; cancellation’dan taxmin qilinmaydi |
| Net cash collection | Moliya siyosatida belgilangan tegishli cash receipts minus haqiqiy refunds; deposit va qarz harakati alohida ko‘rsatiladi |
| Contribution | Bir xil kogorta/horizon/currency bo‘yicha moliya tasdiqlagan revenue basis minus tegishli o‘zgaruvchan xarajatlar; reklama kiritilgan/kiritilmagan basis explicit |
| Paid new customer CAC | Tegishli acquisition spend ÷ birinchi malakali real payment’i bor yangi mijozlar; renewals denominator’ga kirmaydi |
| Contract CPA | Tegishli spend ÷ yetilgan, distinct yangi shartnomalar; lead-to-contract bilan bir xil grain emas |

Contribution siyosati (`business.contribution_policy`; accountable `finance_owner`, co-signer owner) rent uchun xizmat/texnik xizmat xarajatlari va aktiv qiymatini qaysi horizon’da hisoblashni, sale uchun mahsulot/fulfilment/financing xarajatlarini, refund/cancel va bo‘lib to‘lashni qanday ko‘rsatishni belgilaydi. Cash collection va accounting contribution alohida report qilinadi. Turli currency summalar qo‘shilmaydi; konversiya bo‘lsa rate source/date/basis ko‘rsatiladi.

### 4.1 Iqtisodiy readiness gate’i (◇ P-08 · ⧗ OD-06)

`business-policy.yaml#economic_readiness_gate: F5_GO`. `business.outcome_sources` va `business.contribution_policy` — `F5_GO` gate’ining critical kalitlari. Bu ✅ Q04 guardrail’idan (lead→shartnoma) qattiqroq: cash, contribution, refund va fulfilment guardrail’lari qo‘shiladi, shuning uchun darhol amal qiladi. ⧗ OD-06 da owner gate’ni `F6_STEP2` ga yoki F7 monitoringiga ko‘chirishi mumkin; qaror bo‘lguncha `F5_GO` amal qiladi. `economic_scaling_requires_mature_outcomes: true`: pulga tayangan scale faqat yetilgan natija bilan ochiladi.

Pul yoki contribution manbasi bo‘sh yoki eski bo‘lsa profitability, ROI yoki pulga tayangan scale PASS yozilmaydi. F5 go/no-go ikki savolga javob beradi: (A) tizim xavfsiz boshqaradimi — dalil bilan GO/NO-GO; (B) biznes natijasi uchun asos — `sufficient | inconclusive | insufficient` va ruxsat etilgan exposure. B `sufficient` bo‘lmasa F6 faqat tasdiqlangan exposure ichida rent L1 bilan boshlanadi; Step 2 hech qachon avtomatik ochilmaydi.

## 5. Fizik park va amaldagi waitlist

Har snapshot bitta `as_of` vaqt va tasdiqlangan egaga tegishli:

```text
serviceable_bikes = rented_bikes + reserved_bikes + available_bikes
total_fleet = serviceable_bikes + maintenance_bikes
utilization = rented_bikes / serviceable_bikes
```

Holatlar mutually exclusive. Qo‘shimcha fizik holat zarur bo‘lsa schema va formulaga explicit kiritiladi. `available_bikes` — rezerv qilinmagan, topshirishga tayyor birlik. `reserved_bikes` available sifatida qayta sanalmaydi. Denominator nol bo‘lsa utilization `unknown`; nol foiz emas. Ijaradagi, rezervdagi va texnik xizmatdagi bir velosiped bir snapshot’da ikki marta sanalmaydi.

`rent_transactions_month`, renewals, new starts, returns, bike-days va fizik utilization alohida metrikalar. 2026 iyun–sentyabr tarixiy 570/557/540/512 tranzaksiya (✅ Q43) kontekst ma’lumoti; fizik park soni yoki threshold emas (`capacity-policy.yaml#historical_owner_context.use_as_physical_denominator: false`).

### 5.1 Snapshot va kunlik ritm (◇ P-06 · ⧗ OD-14)

Fleet ma’lumotini AI Telegram bot orqali so‘raydi (✅ Q43). Wizard to‘g‘ridan-to‘g‘ri so‘raydigan maydonlar: `rented_bikes`, `reserved_bikes`, `available_bikes`, `maintenance_bikes`, `waitlist_active`, `waitlist_eligible_ready`, `waitlist_oldest_at`, `expected_returns_next_24h`. `serviceable_bikes` va `total_fleet` hisoblanadi; `total_fleet` oldingi valid snapshot bilan solishtiriladi va farqni operator tasdiqlaydi. Bir kunda bir nechta report append-only; oxirgi valid report amal qiladi.

Vaqtlar yagona manbadan — `operations.yaml#schedule`:

| Vaqt | Qadam |
|---|---|
| 08:00 | ops-bot fleet_operator’dan bugungi snapshot’ni so‘raydi (`fleet_ask`) |
| 08:30 | Media Buyer kundalik tekshiruvi: sale va capacity’ga bog‘liq bo‘lmagan takliflar (`media_buyer_daily`) |
| 09:00 | Valid snapshot yo‘q bo‘lsa eslatma (`fleet_remind`) |
| `fleet_snapshot_accepted` hodisasida | Media Buyer rent takliflarini bugungi snapshot revision’idan hisoblaydi (`rent_capacity_review`) |
| 09:45 | 10:00 batch’ga kiradigan band’lar review’dan o‘tgan bo‘lishi kerak (`batch_cutoff`) |
| 10:00 | Kundalik change set (✅ Q38) |
| 14:00 | Valid snapshot hali yo‘q — o‘sha kun barcha odatiy rent budget o‘zgarishi hold (`fleet_escalate`) |

Bugungi valid snapshot bo‘lmaganda **darhol capacity hold**: odatiy rent budget harakati — oshirish ham, kamaytirish ham — muzlaydi. Eskirgan snapshot hech qachon valid emas (`stale_snapshot_never_valid: true`); freshness taklif paytida ham, dispatch paytida ham tekshiriladi. 09:45 dan keyin kelgan snapshot bo‘yicha rent bandi o‘z `presented_at` va TTL’i bilan alohida change-set item bo‘ladi. Protective controls (`protective_pause` va boshqalar) hold’dan ta’sirlanmaydi. Oxirgi yaroqsiz snapshot o‘rniga jim fallback yo‘q. Snapshot TTL’i, egasi va o‘rinbosari — `fleet.freshness`.

### 5.2 Waitlist (⧗ OD-07)

Waitlist — dedup qilingan hozirgi talab: aloqa qilingan, kuryer ekani va ijara niyati mos, muddati o‘tmagan. Faqat mos va hozir tayyor talab capacity qaroriga kiradi; butun tarixiy ro‘yxat denominator emas. Manba qarori ochiq (⧗ OD-07); u qabul qilinguncha vaqtinchalik qoida: fleet snapshot’dagi sonlar band’larni boshqaradi, CRM `waitlist_status_ids` faqat cross-check. Metrikalar PII’siz `waitlist_aggregates` jadvalidan olinadi: `eligible_ready`, `eligible_not_ready`, `expired_in_period`, `age_bucket_counts`, `exits_by_reason`, `fills_in_period`, `definition_revision` ([DATA_MODEL](../03_Architecture/DATA_MODEL.md)). Eligibility, ready/expired, TTL, renewal va fill qoidalarini owner va fleet_operator `fleet.waitlist` da yopadi.

### 5.3 Rent band qoidalari

`capacity-policy.yaml#bands`: `waitlist_eligible_ready ≥ waitlist_high` bo‘lsa rent owner tasdiqlagan floor’ga qarab kamaytiriladi; `available_bikes ≥ available_high` va `waitlist_eligible_ready = 0` bo‘lsa rent budget va approval doirasida oshiriladi; boshqa holatda o‘zgarish yo‘q; `hysteresis_days` tebranishni cheklaydi. Parametrlar (`waitlist_high`, `available_high`, `rent_floor_daily_minor`, `hysteresis_days`) — `fleet.thresholds`, haqiqiy ma’lumot bilan kalibrlanadi. Rent bo‘shatgan budget sale’ga faqat §6 shartlari bilan o‘tadi (`shift_to_sale_requires: sale.readiness`).

## 6. Sale readiness va budget ko‘chishi

`sale` uchun `capacity_bound: false` park qoidasini qo‘llamaslikni bildiradi; sotuv cheksiz degani emas. Sale readiness bitta yaroqli snapshot bilan tasdiqlanadi; sxema yagona — `sale-readiness.yaml#required_fields`: `report_id`, `observed_at`, `reported_by_person_ref`, `offer_revision`, `stock_unpromised_by_model`, `delivery_lead_time_days`, `financing_available`, `call_center_backlog`, `response_lag_hours`, `capacity_per_day`, `valid_until`.

Manba — sales_lead’ning kundalik `/sale_ready` wizard’i yoki tasdiqlangan eksport (◇ P-22); cadence — har kuni 09:30 gacha. Accountable — `sales_lead`: u kundalik snapshot’ni to‘ldiradi va `sale.readiness` kalitini (manba, TTL, egasi; builder tayyorlaydi, `max_evidence_age: P1D` gate paytida) tasdiqlaydi; kundalik yaroqlilik snapshot’ning `valid_until`i bilan o‘lchanadi. Stock, financing va yetkazish ma’lumotini tegishli biznes mas’ullari sales_lead’ga beradi. Gate — `F6_STEP2` (◇ P-09): F6 Step 1 da sale insonda qoladi, shuning uchun sale readiness Step 2 oldidan yopiladi.

Rent’da mablag‘ bo‘shashi sale budget increase uchun yetarli dalil emas. Sale readiness, financial/measurement guardrail, oylik cap va rolling24h chegarasi hammasi o‘tishi kerak. Sale readiness yo‘q yoki eskirgan bo‘lsa sale budget oshirish va rent→sale ko‘chirish o‘tmaydi (`missing_or_stale: block_sale_budget_increase`, ALERT_SALE_READINESS_STALE). Ishlatilmagan budget sarflanmay qolishi maqbul (`unused_budget_may_remain_unspent: true`). Hold yoki spend kamaytirish vakolati gateway policy va incident runbook bilan belgilanadi; agent o‘zicha biznes limitini o‘zgartirmaydi.

## 7. Atributsiya va counting

First-touch va last-touch alohida saqlanadi. First-touch — tasdiqlangan lookback ichidagi birinchi eligible marketing touch; last-touch — conversion oldidagi oxirgi eligible touch. Lookback, eligible kanal, direct visit va cross-device qoidasi measurement revision bilan tasdiqlanadi (`business.attribution`). Birinchi ad click bilan oxirgi landing qaytishi almashtirilmaydi. Meta ad join’i `ad.id`/`adset.id`/`campaign.id` va managed entity mapping orqali; PII join yo‘q.

UTM’siz, consent cheklangan, unmatched va noma’lum source alohida guruh. Unknown CRM holati “organic” yoki “Meta”ga avtomatik o‘tmaydi va eng yaxshi kreativga taqsimlanmaydi. Report’da `matched + unmatched/unknown` jami source jami bilan teng bo‘ladi. Meta-reported natija, CRM first-touch natija va CRM last-touch natija yonma-yon va aniq label bilan chiqadi; ular bir-biriga qo‘shilmaydi va incremental lift isboti emas.

`lead_id × pipeline` qualified count, acquisition episode, shartnoma va mijoz count’lari alohida qoladi. `sale↔rent` transfer, merge, duplicate, requalification va multiple contract qoidalari source facts’ni saqlagan holda measurement contract’da yuradi. Account total qualified lead distinct canonical lead/acquisition qoidasiga ko‘ra chiqariladi; ikki pipeline jami account distinct count deb ko‘rsatilmaydi. Attribution revision o‘zgarsa oldingi baseline solishtiriluvchanligi qayta tekshiriladi.

Kreativ reytingi denominator, coverage, cohort maturity va uncertainty’siz budget qaroriga aylanmaydi. Past N’da “g‘olib” e’lon qilinmaydi; yangi tajriba exposure limiti bilan boshqariladi.

## 8. Metrikalar va baseline

### 8.1 Metrika grain’i

Har metrika `wh.metrics` katalogidagi bitta nomlangan endpoint orqali beriladi ([DATA_MODEL](../03_Architecture/DATA_MODEL.md)); agent yoki dashboard `wh.query` bilan muqobil formula yozmaydi, hamma bir xil qiymatni oladi. `event_week` — Asia/Tashkent bo‘yicha dushanba 00:00 dan yakshanba oxirigacha biznes haftasi.

| Metrika | Aniq grain va foydalanish |
|---|---|
| `qualified_leads` | Davrda birinchi valid qualified fact’i (§3.1) bo‘lgan distinct `lead_id × pipeline`; event davri North Star |
| `qualified_cpl` | Shu pipeline’dagi davr spend ÷ event davridagi qualified; lag-sensitive operatsion signal |
| `qualified_cpl_event_week` | `qualified_cpl` ning `event_week` grain’i; KC-01 metrikasi (§8.3) |
| Cohort qualified CPL | Tanlangan lead-acquisition kogortasiga tegishli spend ÷ shu kogortaning valid qualified natijasi; attribution/cost allocation basis explicit |
| `lead_to_qualified` | Bir xil lead yaratilish kogortasidagi qualified ÷ distinct leads; maturity ko‘rsatiladi |
| `lead_to_contract` | Bir xil yetilgan lead kogortasida kamida bir valid shartnomali distinct lead ÷ leads; ko‘p contract’lar numerator’ni ko‘paytirmaydi; KC-02 metrikasi |
| `contract_cpa`/cash/contribution | §4 dagi ta’rif va moliya tasdiqlagan horizon bilan; event-week CPL bilan aralashtirilmaydi |
| Tracking coverage | Consent-eligible/matched denominator explicit; `fbc` ulushi barcha murojaatga majburan tenglashtirilmaydi |
| Sales readiness/fleet freshness | Har qaror vaqtida valid snapshot, source age va status; faqat kunlik report emas |

### 8.2 `data_status`

Har metrika qiymati bitta `data_status` bilan chiqadi; bu ta’rif kanonik — DATA_MODEL, kill-criteria, UAT-07 va OBSERVABILITY shu lug‘atni ishlatadi (`business-policy.yaml#data_status_values`):

| `data_status` | Ta’rif |
|---|---|
| `valid` | spend > 0; sample va maturity qoidalari bajarilgan; baseline taqqoslanadi |
| `no_activity` | spend = 0 va qualified = 0 |
| `no_spend` | spend = 0 va qualified > 0 |
| `spend_zero_qualified` | spend > 0 va qualified = 0 — CPL aniqlanmagan (nol yoki “yaxshi” emas), loss exposure |
| `insufficient_sample` | tasdiqlangan minimal sample’dan past |
| `not_mature` | natija oynasi hali yopilmagan |
| `incomparable_baseline` | qualification yoki tracking ta’rifi revision’i baseline’nikidan farq qiladi |
| `missing_data` | kerakli source qatorlari yo‘q |
| `stale_data` | source tasdiqlangan freshness cutoff’dan eski |

Har holatdagi harakat `kill-criteria.yaml#data_status_actions` da: `valid` — baholanadi; `spend_zero_qualified` — exposure va yomon hafta sanaladi; `insufficient_sample`, `not_mature`, `incomparable_baseline` — `inconclusive`, yomon hafta seriyasi tozalanmaydi, exposure soati davom etadi; `missing_data`, `stale_data` — blok va alert (48 soatgacha qayta baholash, §8.7); `no_activity`, `no_spend` — baholanmaydi, yomon hafta seriyasi o‘zgarmaydi. Spend>0 va qualified=0 har sync siklida tekshiriladi (`operations.yaml#schedule` dagi `exposure_guard`): scale blok va ALERT_ZERO_QUALIFIED_EXPOSURE; maksimal exposure, vaqt va handback — `business.exposure`. Uzoq `inconclusive`da owner belgilagan maksimal exposure yoki vaqt va handback ishlaydi; jim PASS yo‘q.

### 8.3 Kill criteria (✅ Q31, ✅ Q04)

| Qoida | Metrika va shart | Harakat |
|---|---|---|
| KC-01 | Pipeline bo‘yicha `qualified_cpl_event_week` taqqoslanadigan baseline’dan 25%dan ko‘proq yomon (`worse_pct_greater_than: 25`), ketma-ket 2 hafta; minimal sample `business.acceptance` dan | Pipeline `L0_shadow`, urgent alert (ALERT_KILL_CRITERIA), inson handback, funnel-analyst C05 RCA |
| KC-02 | Har yangi yetilgan haftalik lead kogortasining `lead_to_contract`i baseline’ning yetilgan kogortalaridagidan `worse_pct`dan ko‘proq yomon (`worse_pct`, `min_sample`, `maturity_days` — `business.acceptance` da), ketma-ket 2 yetilgan kogorta | Avtomatik budget oshirish blok (`block_auto_increase`) va urgent alert (ALERT_KILL_CRITERIA_GUARDRAIL) |

Kirish view’i — `amt_ro.v_pipeline_cohorts` (pipeline × event_week: `qualified_cpl`, `baseline_revision`, `data_status`, exposure). Baholash deterministik `sync-worker` job’ida, dushanba 07:30 (`operations.yaml#schedule` dagi `kill_criteria`); LLM qatnashmaydi. Seriya semantikasi, baseline CPL formulasi va qoidalarning operatsion xarakteristikasi — §8.7. Kogorta bo‘yicha qo‘shimcha tasdiq va aniqlash kechikishi ⧗ OD-13. F6 Step 1 dushanba boshlanadi, shuning uchun 14 kun — ikkita to‘liq event-week; Step 2 faqat KC-01 ning ikkinchi baholashi bajarilgandan keyin; natija `inconclusive` bo‘lsa Step 1 uzaytiriladi yoki hold, avtomatik o‘tish yo‘q (◇ P-13); qaror qoidasi, uzaytirish birligi va maksimumi oldindan ro‘yxatga olinadi (§8.7, ◇ P-41). KC-01’dan keyingi resume — [INVARIANTS](INVARIANTS.md) I07.

### 8.4 Baseline va maturity

Baseline har pipeline uchun metric formula, numerator/denominator, measurement revision, qualified definition effective date, source coverage, cohort maturity horizon, currency/timezone, spend allocation, offer/landing/stock va tracking o‘zgarishlari, exclusions va source query reference’ni saqlaydi (`business.baseline`). Oxirgi 8 hafta operational baseline va 12+ oy seasonal profile maqsadli kirishlar (✅ Q31, Q37); tarixning o‘zi solishtiriluvchanlik isboti emas. Eski qualified status Q16 bilan sample audit’dan o‘tsa comparable bo‘lishi mumkin; o‘tmasa `legacy_proxy` sifatida ajratiladi va yangi comparable baseline yig‘iladi.

Maturity qualification/contract/payment/refund lag’lari bilan aniqlanadi; kerakli horizon readiness’da tasdiqlanadi. Kalendar 14 kun o‘tgani barcha kogorta yetildi degani emas. Diff-in-diff faqat pretrend, taqqoslanadigan guruh va o‘zgarmagan measurement asoslari bo‘lsa yordamchi dalil; `rent`/`sale` farqi sababiy AI lift’i deb berilmaydi.

### 8.5 Haftalik hisobot (✅ Q24)

Dushanba 09:00: Telegram’da BLUF (≤250 so‘z) va Paperclip’da to‘liq C07 hisobot. Funnel-analyst 08:00 da `report.submit` qiladi; Reviewer 08:00–09:00 orasida aynan shu matnni Kernel, PII va da’volar bo‘yicha tekshiradi; ops-bot 09:00 da e’lon qiladi (`operations.yaml#schedule`). Metrikalar (`business-policy.yaml#weekly_report_metrics`):

- qualified lead (sale/rent) va qualified CPL (pipeline bo‘yicha);
- lead→shartnoma;
- sarf va limit;
- eng yaxshi va eng yomon kreativ — minimal N va coverage bilan;
- keyingi hafta eksperimentlari;
- ijarada bandlik va waitlist;
- ma’lumot bo‘shliqlari va freshness, Trust Ramp holati, mavjud bo‘lsa cash/contribution.

Event va cohort ko‘rinishi, Meta va CRM atributsiyasi, source freshness va uncertainty ajratib ko‘rsatiladi; har raqam manba va vaqt bilan.

### 8.6 Metrika daraxti va Goodhart nazorati

```text
Qualified leads (pipeline p, hafta w)
= Impressions × CTR × Landing CVR (forma yuborish) × Lead→Qualified rate
   │              │            │                         └─ call-center sifati, offer mosligi, segment (sales_lead, CRO)
   │              │            └─ offer, landing tezligi, forma, ishonch belgilari (CRO)
   │              └─ kreativ, xabar, auditoriya (Creative Studio, Media Buyer)
   └─ byudjet, auksion, learning holati (Media Buyer)

Ijara cheklovi: qo‘shimcha qiymat ≈ min(qualified leads, bo‘sh sig‘im + waitlist chiqishi)
```

CTR, barcha lead CPL’i va platforma ROAS’i oraliq diagnostika. Ular yaxshilanib, qualified lead yoki lead→shartnoma yomonlashsa — bu muvaffaqiyat emas; Analyst har hafta ikkalasini yonma-yon ko‘rsatadi.

### 8.7 Statistik qaror qatlami (◇ P-40)

Shovqinli biznes raqamini boshqaruv qaroriga aylantiradigan har qoida bitta umumiy spec’dan oladi: [decision-statistics.yaml](../09_Config_Templates/decision-statistics.yaml). Har qoidada usul, MDE, alpha, power, minimal exposure, maksimal uzaytirish va non-inferiority margin yozilgan. Qiymat yo manbasi ko‘rsatilgan literal (✅ Q-ID, ★ yoki ◇), yo `readiness:<kalit>.<maydon>` (owner qiymati, kalitning mavjud gate’ida tasdiqlanadi), yo `not_applicable: <sabab>`. Iste’molchi config qoidani `decision_rule: <id>` bilan nomlaydi, qoida esa iste’molchini sanaydi; validator K04 ikki tomonni tekshiradi. Spec yangi gate, HUMAN_GATE yoki pul qo‘shmaydi.

| Qoida | Owner qarori | Usul | Iste’molchi |
|---|---|---|---|
| KC-01 | ✅ Q31 | `threshold_streak`: haftalik qualified CPL baseline’dan 25%dan ko‘proq yomon, 2 yomon hafta; statistik test emas, Q31 qanday yozilgan bo‘lsa shunday | `kill-criteria.yaml` KC-01 |
| KC-02 | ✅ Q04 | `threshold_streak`: har yangi yetilgan haftalik lead kogortasi baseline’ning yetilgan kogortalariga nisbatan, 2 ketma-ket kogorta | `kill-criteria.yaml` KC-02 |
| STEP1_TO_STEP2 | ✅ Q36, ✅ Q31 | `business.acceptance.verdict_rule`: non-inferiority yoki superiority, margin, alpha, power, `min_qualified`, `max_weeks` — owner qiymatlari, HG-F6-01 dan oldin oldindan ro‘yxatga olinadi (◇ P-41) | `kill-criteria.yaml` `step1_timing` |
| TRUST_RAMP_GRADUATION | ✅ Q08, ✅ Q38 | `consecutive_success_run`: 10 ketma-ket sanaladigan deterministik `met` (★) + 14 kun incidentsiz (★); boshqa har natija seriyani 0 ga qaytaradi (◇ P-42) | `approval-policy.yaml` `trust_ramp.graduation` |
| EXPERIMENT | ✅ Q41 | `pre_registered_design`: har eksperiment kartasida qaror turi, MDE, alpha, power, minimal exposure, maksimal davomiylik (`business.exposure` ichida), margin — WF-B05 S03 da exposure bilan tasdiqlanadi; yetarli quvvatsiz dizayn launch’dan oldin `exploratory` deb belgilanadi; ishlayotganda `experiment_lock` (◇ P-43) | WF-B05 S02, S06 |
| SHADOW_WEEK | ✅ Q36, ★ EVALS §6 | `proportion_with_minimum_n`: ≥ 60% foydali, `min_rated_items: 30`, `min_material_items: 10`, 2 × 7 kun uzaytirish (◇ P-44) | [EVALS](../07_Evals/EVALS.md) §6 |
| Q29_1_VOLUME | ✅ Q29.1 | `threshold_with_hysteresis`: pipeline bo‘yicha oldingi kalendar oyidagi hisob ≥ max(200, vendor talabi); o‘tish 2 ketma-ket oyda, qaytish birinchi past oyda (◇ P-45) | `business-policy.yaml` `qualified_optimization_rule` |

**KC seriyasi holat mashinasi** (`kill-criteria.yaml#streak`, yozuvchi faqat `sync-worker` kill-criteria job’i, LLM qatnashmaydi):

| Haftaning `data_status`i | Seriyaga ta’siri |
|---|---|
| `valid` va chegaradan yomon; `spend_zero_qualified` | +1 |
| `valid` va yomon emas | 0 ga qaytadi |
| `insufficient_sample`, `not_mature`, `incomparable_baseline`, `no_activity`, `no_spend` | o‘zgarmaydi (hold); KC-01 da istisno — 0 < qualified < `min_sample` haftada spend ÷ max(qualified, `min_sample`) > 1,25 × baseline CPL bo‘lsa +1 (`streak.low_sample_bound`, ◇ P-56; `min_sample` birligi — pipeline × event_week dagi qualified fact) |
| `missing_data`, `stale_data` | blok: ma’lumot kelishi bilan baholanadi (har sync siklida, muddatsiz; kech kelgan ma’lumot measurement revision qoidasi bilan); 48 soatdan keyin owner va technical_operator’ga ALERT_KILL_CRITERIA (`evaluation_blocked`, degraded); blok paytida shu pipeline’da budget increase rad (◇ P-58) |

Hold haftalar bilan ajralgan ikki yomon hafta trigger beradi — Q31’dagi "ketma-ket"ning qattiqroq o‘qilishi. `triggered` holatidan faqat owner chiqaradi: KC-01 — resume (C05 RCA, HG-F6-04, owner rejim o‘zgarishi), seriya keyingi to‘liq `event_week`dan qaytadan sanaladi; KC-02 — C05 RCA va trigger’dan keyin kamida bitta yetilgan kogorta valid va yomon emas bo‘lgach owner `control_resume` (sabab `kc02_guardrail`), seriya keyingi yetilgan kogortadan sanaladi va Trust Ramp incident oynasi shu paytdan qayta boshlanadi (◇ P-55). Yangi measurement revision (owner `business.attribution` orqali tasdiqlaydi) seriyani muzlatilgan xom ma’lumotdan yangi revision bo‘yicha qayta hisoblaydi; bajarilgan L0 hech qachon bekor qilinmaydi, `counting` seriyani tozalagan qayta hisob owner tasdig‘i yonida jurnalga yoziladi — ya’ni revision seriyani ikki tomonga ham o‘zgartira oladi (◇ P-58). `business.exposure.bad_week_streak` shu seriyani sanaydi va KC-01’ning 2 haftasidan oshmaydi.

**Baseline CPL formulasi:** muzlatilgan oynadagi valid haftalar bo‘yicha Σspend ÷ Σqualified (`kill-criteria.yaml#baseline.cpl_formula: pooled_ratio`). Haftalik CPL’lar o‘rtachasi ishlatilmaydi: kam hajmda u baseline’ni yuqoriga suradi va KC-01’ni kechiktiradi. `business.baseline.metric_formula_ref` shu formulani nomlaydi; boshqa formula — himoyalangan config o‘zgarishi.

**KC-01 operatsion xarakteristikasi (Fermi, simulyatsiya).** Kirishlar: λ — baseline CPL’da pipeline’ning haftalik kutilgan qualified soni (bundle’da real qiymat yo‘q, shuning uchun 5–80 oralig‘i); spend har hafta bir xil; baseline 8 hafta; haftalik son Poisson yoki negative binomial (k = 25 yoki 8, haftalik CV ≈ √(1/λ + 1/k)); har katakda 200 000 simulyatsiya; seriya qat’iy qo‘shni haftalar bilan. Hold qoidasi ikkala ko‘rsatkichni biroz oshiradi [inference].

| λ/hafta | Taqsimot | Yolg‘on signal (o‘zgarish yo‘q): 8 haftada ≥1 trigger | 2 haftada | CPL +25%: 4 haftada aniqlash | 8 haftada | CPL +50%: 4 haftada | 8 haftada |
|---|---|---|---|---|---|---|---|
| 5 | Poisson | 50% | 13% | 53% | 77% | 71% | 90% |
| 5 | k=25 | 54% | 15% | 54% | 78% | 70% | 90% |
| 5 | k=8 | 60% | 17% | 55% | 80% | 70% | 90% |
| 10 | Poisson | 37% | 9% | 52% | 77% | 76% | 94% |
| 10 | k=25 | 45% | 11% | 53% | 78% | 75% | 93% |
| 10 | k=8 | 55% | 15% | 55% | 80% | 73% | 92% |
| 20 | Poisson | 22% | 5% | 51% | 76% | 84% | 97% |
| 20 | k=25 | 36% | 8% | 53% | 78% | 79% | 95% |
| 20 | k=8 | 51% | 13% | 55% | 79% | 75% | 93% |
| 40 | Poisson | 9% | 2% | 51% | 76% | 91% | 99% |
| 40 | k=25 | 29% | 6% | 53% | 78% | 84% | 97% |
| 40 | k=8 | 48% | 13% | 55% | 80% | 77% | 94% |
| 80 | Poisson | 1% | 0% | 51% | 76% | 97% | 100% |
| 80 | k=25 | 24% | 5% | 53% | 77% | 87% | 98% |
| 80 | k=8 | 47% | 12% | 55% | 79% | 78% | 94% |

**`min_sample` ning ta’siri (Fermi, simulyatsiya, Poisson, 200 000 run).** Yuqoridagi jadval `min_sample` hold’larini modellashtirmagan, shuning uchun optimistik. `min_sample` bilan (8 hafta kuzatuv; aniqlash — 4 haftada):

| λ/hafta | `min_sample` | Qoida | Yolg‘on signal 8 haftada | +25%: 4 haftada | +50%: 4 haftada |
|---|---|---|---|---|---|
| 5 | 5 | faqat hold | 2% | 1% | 1% |
| 5 | 5 | hold + `low_sample_bound` | 5% | 5% | 6% |
| 10 | 5 | faqat hold | 33% | 40% | 55% |
| 10 | 5 | hold + `low_sample_bound` | 37% | 52% | 76% |
| 10 | 10 | hold + `low_sample_bound` | 1% | 1% | 1% |
| 20 | 10 | faqat hold | 21% | 46% | 71% |
| 20 | 10 | hold + `low_sample_bound` | 22% | 51% | 84% |

`min_sample` haftalik qualified hajmiga teng yoki undan katta bo‘lsa KC-01 deyarli hech qachon ishlamaydi — u holda yagona himoya `business.exposure`ning yig‘ma chegarasi. `min_sample` qiymatini haftalik hajmga qarab tanlash — owner qarori (`business.acceptance`).

Xulosa: haqiqiy +25% yomonlashuv 4 haftada taxminan yarim holatda ushlanadi, haftalik son kam yoki tarqoq bo‘lsa esa o‘zgarish bo‘lmaganda ham 8 haftada yarim holatgacha yolg‘on trigger bor. KC-01 xavfsiz tomonga (L0 va inson) ishlagani uchun yolg‘on signal pulni emas, AI ish vaqtini yo‘qotadi. Statistik usulga o‘tish (spend offset’li gamma-Poisson posterior yoki CUSUM) ✅ Q31’ni o‘zgartiradi va owner qaroriga chiqarilgan; qaror bo‘lguncha qoida Q31 matni bo‘yicha ishlaydi.

**Step 1 → Step 2 taqqoslashi (Fermi).** 2 AI haftasi 8 baseline haftasiga qarshi (α = 0.05 ikki tomonlama, power 0.8, log-CPL nisbati bo‘yicha Wald yaqinlashuvi) aniqlanadigan eng kichik CPL farqi:

| λ/hafta | MDE (Poisson) | MDE (k=25) | MDE (k=8) |
|---|---|---|---|
| 10 | +101% / −50% | +129% / −56% | +186% / −65% |
| 20 | +64% / −39% | +94% / −49% | +153% / −60% |
| 40 | +42% / −30% | +76% / −43% | +136% / −58% |
| 80 | +28% / −22% | +66% / −40% | +127% / −56% |

(Nisbat shkalasida: CPL o‘sishi +x% yoki pasayishi −y%, (1 + x)(1 − y) = 1. Bu jadval ikki tomonlama α bilan; Step 2 verdikti `verdict_rule` dagi bir tomonlama α bilan, ◇ P-56.)

Non-inferiority uchun kerakli AI haftalari (bir tomonlama α = 0.05, power 0.8, haqiqiy farq 0, 8 baseline haftasi):

| λ/hafta | margin 15%: Poisson | k=25 | k=8 | margin 25%: Poisson | k=25 | k=8 |
|---|---|---|---|---|---|---|
| 10 | hech qachon | hech qachon | hech qachon | hech qachon | hech qachon | hech qachon |
| 20 | hech qachon | hech qachon | hech qachon | 28 | hech qachon | hech qachon |
| 40 | >156 | hech qachon | hech qachon | 6 | hech qachon | hech qachon |
| 80 | 8 | hech qachon | hech qachon | 2 | 36 | hech qachon |

"Hech qachon" — 8 haftalik baseline’ning o‘z dispersiyasi (z₀.₉₅ + z₀.₈) · SE ning o‘zi ln(1 + margin) dan katta: AI haftalari qancha uzaytirilsa ham non-inferiority isbotlanmaydi; yagona richag — uzunroq yoki birlashtirilgan baseline (owner qarori). k 8 haftalik sondan beqaror baholanadi, shuning uchun rejalashtirishda Poisson’dan past olinmaydi va oralig‘i ko‘rsatiladi.

Ya’ni 14 kunlik Step 1 o‘zi statistik qabul emas (F6 matnida ham shunday): realistik hajmda u faqat katta yomonlashuvni ko‘rsatadi. Shuning uchun Step 2 qarori natijani ko‘rishdan oldin yozilgan qoida bo‘yicha olinadi: test statistikasi (log CPL nisbati), dispersiya modeli (Poisson yoki baseline k’li negative binomial), baseline noaniqligi, verdikt xaritasi (sufficient / insufficient / inconclusive) va ko‘rishlar soni (`max_weeks`da bitta tahlil yoki oldindan yozilgan alpha-spending; tuzatilmagan takroriy ko‘rish taqiqlangan) — maydonlar majburiy, qiymatlari owner’niki (◇ P-56); uzaytirishning birligi va maksimumi bor, maksimumda hold va owner qarori; qaror turi va margin — owner tanlovi (✅ Q36 talqini, owner qaroriga chiqarilgan).

**Trust Ramp (Fermi).** Itemlar mustaqil, sanaladigan `met` ulushi q bo‘lganda:

| q | 30 itemda kamida bir marta 10 ketma-ket | 60 itemda | Birinchi 10 ketma-ketgacha kutilgan item soni |
|---|---|---|---|
| 0,5 | 1% | 3% | ≈ 2 000 |
| 0,6 | 5% | 12% | ≈ 410 |
| 0,7 | 19% | 39% | ≈ 115 |
| 0,8 | 49% | 79% | ≈ 42 |
| 0,9 | 87% | 99% | ≈ 19 |

Kuniga r ≈ 0,5 jonli item (rent × `budget_change`), hal qiluvchi (valid ma’lumotli) natija ulushi d va hal qiluvchi itemlar ichida `met` ulushi p bo‘lsa [inference]:

| d | p | reset qoidasi (amaldagi vaqtinchalik o‘qish): q = d · p, E[kun] = E[item]/r | hold qoidasi (muqobil): E[kun] = E[item]/(r · d) |
|---|---|---|---|
| 0,3 | 0,8 | ≈ 4,2 mln kun — **hech qachon** | ≈ 277 |
| 0,3 | 0,9 | ≈ 1,3 mln kun — **hech qachon** | ≈ 125 |
| 0,7 | 0,8 | ≈ 1 500 | ≈ 119 |
| 0,7 | 0,9 | ≈ 540 | ≈ 53 |

(+ horizon + 14 kun.) Amaldagi reset qoidasida d = 0,3 da L2 ga umuman yetib bo‘lmaydi, d = 0,7 da ham 1,5–4 yil; hold qoidasida 2–9 oy. HG-F5-04 dagi `TRUST_RAMP_FEASIBILITY.md` ikkala modelni har trust kaliti uchun real shadow va tarix bilan ko‘rsatadi (◇ P-55); reset/hold tanlovi, parametrlarni yumshatish yoki portfel darajasidagi graduation — owner qarori.

**Q29.1 hajm qoidasi (Fermi).** Oylik hisob Poisson, haqiqiy o‘rtacha μ bo‘lganda bitta o‘lchov chegaradan (200) o‘tish ehtimoli: μ = 170 — 1%, 185 — 14%, 200 — 51%, 215 — 86%, 230 — 98%. Gisterezissiz chegara atrofida goal deyarli har ikkinchi oyda almashardi (μ = 200 da 50%); 2-yuqoriga / 1-pastga qoidasi bilan μ = 200 da goal baribir oyiga ≈ 0,26 marta (taxminan 4 oyda bir) almashadi. Oxirgi 28 kunlik hisob oylik chegara bilan taqqoslanganda samarali chegara ≈ 217/oy bo‘lardi (μ = 200 da o‘tish 13%, ketma-ket ikki marta 1,6%) — shuning uchun oyna kalendar oy (◇ P-56).

## 9. Offer revision va aktiv materiallar

Narx, aksiya, kafolat va ijara shartlari faqat owner tasdiqlagan offer registry’dan (✅ Q08, Q35). Har tijorat artefakti immutable `offer_id + revision`, effective/expiry vaqt, owner approval source, asset content hash va Reviewer verdict revision’iga bog‘lanadi. Revision maydonlari — `offers.yaml#example_schema`: narx (`amount_minor`, currency, period), shartlar, ruxsat etilgan da’volar, `forbidden_claims`, `restrictions`, `capacity_bound`, huquq ref’i va `special_ad_category`. Bo‘lib to‘lash offer’lari uchun Meta special ad category tekshiriladi; noma’lum qiymat activation’ni bloklaydi (✅ Q42). Brend faktlari (masalan, stansiya soni) `fact_schema` bo‘yicha manba va muddat bilan; Reviewer registry’da yo‘q da’voni bloklaydi. Owner-only PR/merge yangi offer’ni tasdiqlaydi; config bundle deployment va servis ACK’lari faol revision’ni isbotlaydi. Landing snapshot generated; qo‘lda chetlab o‘tilmaydi. Boshlang‘ich offer va landing asset huquqlari F2 live trafikdan oldin yopiladi (HG-F2-15; `offers.initial`, `offers.asset_rights`).

Huquq reyestri source asset egasi/litsenziya, kanal/territory/usage permission, zarur release reference, expiry/revocation va derived asset bog‘lanishini saqlaydi. Huquqni owner beradi va bekor qiladi (`asset_rights_clear`, `asset_rights_revoke`; ixtiyoriy `rights_clearer` flag’i; yuklagan odam o‘z yuklamasini tasdiqlay olmaydi). Agentga shaxsiy consent hujjati berilmaydi; custody reference va ruxsat holati yetarli. Noma’lum huquqli asset publish’dan o‘tmaydi.

Offer expiry/narx o‘zgarishi, claim correction yoki rights revocation’da: ta’sirlangan live ad, landing va approval aniqlanadi; yangi dispatch bloklanadi; pending approval’lar invalidation qilinadi; owner va mas’ulga ALERT_OFFER_REVOKED; `offers.propagation` SLA ichida owner yoki ads_approver `entity_pause` yoki owner tasdiqlagan almashtirishni bajaradi; live reconciliation bilan yopiladi. `protective_pause` faqat `operations.yaml#protective_controls` dagi trigger’lar uchun; offer revocation uning trigger’i emas. Faqat yangi write’ni bloklash eski live reklamadagi da’voni tuzatmaydi. Revision o‘zgarsa eski approval yoki Reviewer pass qayta ishlatilmaydi.

## 10. Javobgar odamlar va uzluksizlik

| Majburiyat | Accountable rol | Primary/o‘rinbosar va dalil |
|---|---|---|
| Strategiya, pul chegarasi, offer, go-live/kill/resume | `owner` | `ops.roles_owner`; owner-only vakolat hech kimga avtomatik o‘tmaydi |
| Kundalik ruxsatli ads approval va human handback | `ads_approver` | Amaldagi primary+deputy, ish vaqti, vakolat expiry va qabul ACK; `ops.ads_handback_roster`, `ops.sale_handback_roster` |
| Qualified SOP, status mapping, QA, backlog va sale readiness | `sales_lead` | Primary+deputy, QA dalili, `/sale_ready` |
| Fizik park, waitlist va topshirish sig‘imi | `fleet_operator` | Primary+deputy, snapshot attestatsiyasi |
| Payment/refund/contribution manbasi | `finance_owner` | Source signoff; RBAC’da yangi tool vakolati avtomatik yaratilmaydi |
| Consent, retention va breach javobi | `privacy_owner` | `privacy.*` readiness, owner co-sign |
| Infra, incident, restore va credential rotatsiyasi | `technical_operator` | Primary+deputy, restore drill va xizmat vaqti; Telegram’da `viewer` + `ops_responder` flag |
| Himoyalangan sirt o‘zgarishining mustaqil review’i | `independent_reviewer` | `engineering.independent_reviewer` (⧗ OD-12) |
| Haqiqiy foto/video va undan foydalanish huquqi | `content_contributor` (yuklaydi), owner (huquqni beradi) | Haftalik yuklash eslatmasi (✅ Q20/Q29.3) |

Roster urgent ACK va harakat deadline’i (`ops.ack_minutes`), coverage, eskalatsiya (`ops.escalation`) va yo‘qlikdagi xavfsiz holatni belgilaydi; identifikatsiya faqat `amt.people/roles` da, readiness’da opaque `person_ref`. Deputy faqat o‘zida mavjud vakolatni ishlatadi: owner vakolati faqat odamga RBAC’da `owner` roli berilganda o‘tadi, yashirin delegatsiya yo‘q. Deputat favqulodda kill vakolati ⧗ OD-04; u hal bo‘lguncha deputat kill qila olmaydi, faqat ACK, diagnostika va eskalatsiya qiladi. Owner yo‘q paytdagi owner-only taklif kutadi yoki oldindan tasdiqlangan xavfsiz holatda qoladi ([OPERATING_ENVELOPE](OPERATING_ENVELOPE.md) §5).

Targetolog F6 Step 1 dan 4 hafta `ads_approver` (✅ Q31; `expires_at` = HG-F6-01 vaqti + 28 kun). Step1+21 kunda HG-F6-05: rolni uzaytirish, almashtirish yoki tugatish, yangi primary/deputy va handback egasi tayinlanadi va roster qayta tasdiqlanadi (◇ P-17). Alert yuborilishi handback emas: tegishli inson boshqaruvni qabul qilgani ACK (`handback_acks`) va managed entity holati bilan qayd etiladi.

## 11. Biznes qabul mezonlari

F5 GO oldidan reyestr har pipeline uchun formula, source, baseline revision, sample/maturity, target/guardrail, observation window, exposure/inconclusive deadline, primary/deputy, tasdiq va evidence ref’ni yopadi (`business.*`, `sales.*`, `fleet.*`; iqtisodiy manbalar §4.1 bo‘yicha). Bo‘sh majburiy maydon yoki yaroqsiz source gate’ni yopiq qoldiradi. Shadow’da foydali taklif real iqtisodiy natija PASS’i emas; F6/F7 alohida tekshiriladi. F6 Step 2 oldidan `business.step1_comparison` (KC-01 ning ikkinchi baholashi bilan), `sale.readiness` va `ops.sale_handback_roster` yopiladi; HG-F6-04 (sale) va HG-F6-02 owner qarori.

Majburiy fixture va real-source sample reconciliation:

- Qualification uch shartning har biri yetishmagan holat, qayta qualification, merge va cross-pipeline ko‘chish to‘g‘ri sanaladi.
- Qisman to‘lov, topshirishdan keyingi installment, refundable deposit, qisman refund va cancellation cash/shartnomani aralashtirmaydi; source jami mos.
- Bir xil oylik tranzaksiya bilan turli maintenance fizik utilization’ni turlicha beradi; nol denominator, zid snapshot, stale snapshot va expired waitlist hold beradi; `waitlist_aggregates` snapshot bilan mos.
- Sale stock yo‘q, financing blok, backlog yuqori yoki stale bo‘lsa sale increase va rent→sale o‘tmaydi.
- First/last/unknown source, consent-off, multiple contract va lagged correction’da source reconciliation va counting mos.
- Noma’lum yoki eskirgan offer yoki asset huquqi pending approval va live artifact rejasida yo‘qolmaydi.
- Har `data_status` qiymati §8.2 dagi harakatni beradi; spend>0/qualified=0, past N, null baseline va uzoq inconclusive scale PASS bermaydi.
- Owner, fleet operator yoki approver vaqtincha yo‘qligi hamda approver expiry dry run’ida vakolatsiz yozish va egasiz incident bo‘lmaydi.

Tekshiruv: UAT-01–UAT-07, UAT-26, UAT-29, F5-AT-12, F6-AT-04, F6-AT-05, F6-AT-15, F7-AT-06. Dalil formati va yakuniy gate: [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md). Operatsion chegaralar: [OPERATING_ENVELOPE](OPERATING_ENVELOPE.md). Texnik data mapping: [DATA_MODEL](../03_Architecture/DATA_MODEL.md). Talablar bajarilmaguncha natija `not_run`, `blocked`, `fail` yoki `inconclusive`; dalilsiz `pass` emas.
