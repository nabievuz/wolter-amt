# F5 — Model, biznes va production readiness qabul darvozasi

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

## Boshlash sharti

- **F4 offline tayyorgarligi:** synthetic fixture va harness kodi F4da tayyorlanishi mumkin; F4ning o‘z acceptance smoke sinovlari o‘z gate/cap’larida qoladi. Bu F5 formal eval natijasi yoki shadow kuni emas. **F5 formal eval** (model/adapter tanlash, hard safety, blind golden va F5-AT dalili) F4 `verified_in_staging` bilan birga quyidagi Q67 FE kirish shartini ham kutadi.
- **Real shadow** ham Q67 FE kirish sharti bajarilgach va faqat **F3 va F4 accepted** (barcha AT `pass`, mustaqil red team critical 0, HG-GIT-01 merged; F4_AGENTS va F4_CONTENT PASS) va **HG-F2-08 Tracking gate PASS** (F2_TRACKING_PASS) bo‘lgach boshlanadi. 14 kun report_only va 7 kun enforce kuzatuvi tugamaguncha real shadow oynasi ochilmaydi.
- **Q67 FE kirish sharti** (`readiness.yaml#rules.phase_entry_profiles.F5`): sandbox, mustaqil verification va himoyalangan release qatlami **deployed**, FE_SANDBOX/FE_RELEASE **PASS**, FE `verified_in_staging` va HG-FE-01…05 yopiq bo‘lishi **birinchi F5 formal evaldan ham, real shadow’dan ham oldin** majburiy ([FE_Evolution](FE_Evolution.md)). Faqat F5_GO oldida yopish yetarli emas. Q66 bo‘yicha exact baseline mustaqil texnik inson signoff’i FE_RELEASE’dan oldin yoziladi; shuning uchun u formal evaldan oldin ham tayyor. Engineering E human review’i saqlanadi; F1dan oldin bunday inson tayinlash talabi yo‘q.
- Targetolog F5’da `viewer` + `golden_copy_rater` + `shadow_rater` + `language_checker` (`roles.yaml` `targetologist_timeline`, HG-F5-03); reklama tasdiqlash vakolati yo‘q. HG-F5-03 ona tili o‘zbek bo‘lgan uchinchi baholovchini tayinlaydi. [EVALS](../07_Evals/EVALS.md) va [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) mezonlari qo‘llanadi.

## 1. Har rol model va adapter tanlovi

Har rol uchun 2–3 joriy nomzod rasmiy model/provider hujjatlari va OpenRouter mavjudligi/narxi orqali build kuni tekshiriladi (Q44.2 ✅: asosiy mezon tool-use ishonchliligi). Research aniq ID/provider/routing/context/tool schema/cache/privacy/narx/sana bilan; leaderboard o‘zi yetarli dalil emas. Pinned Paperclip/Hermes/native adapter manbasi, source commit/hash/litsenziya va real runner → proxy → gateway zanjiri isbotlanadi. Claude Code faqat Claude modellari bilan; boshqa oila `opencode_local` yoki Hermes adapterida (★ Q44.2). AdClaw faqat reference_only; foydali kod/pattern olinsa provenance va regression eval zarur.

Kirish shartlari yopilgani `build/F5/PLAN.md`da FE release/manifest, readiness revision, drill va baseline human signoff reference’lari bilan yozilmaguncha quyidagi formal eval boshlanmaydi. Har agent E/M/tool-use, mustaqil Reviewer, til sifati va production failure scenario evalini o‘z haqiqiy identity’sida bajaradi. Hard safety 100%, stochastic hard har safar 3/3. Blind golden: bir xil offer/brief, kamida 3 baholovchi, anonim tartib; registry/claim xatosi diskvalifikatsiya. Sifat va hujjatlangan haqiqiy narx/kechikish bo‘yicha qaror; model/adapter fallback yo‘q (Q44.3 ✅).

**Reviewer (Q42 ✅):** ikki slot — `reviewer.language` (Sonnet darajasidagi model yoki UZ/RU til holdout’ida teng natija isbotlangan model) va `reviewer.policy_checklist` (arzonroq ruxsat). EVALS’dagi ataylab xato qo‘yilgan o‘zbekcha til holdout’i `reviewer.language` uchun majburiy. STT engine bitta, owner tanlaydi (OI-40).

**Jev pre-screen (Q61)** Reviewer slot’laridan alohida baholanadi ([EVALS §4.2](../07_Evals/EVALS.md)): UZ va RU golden copy hamda belgilangan qoidabuzarlik to‘plamida har check (`meta_policy`, `special_ad_category`, `pii_leakage`) va til bo‘yicha recall va yolg‘on bayroq ulushi owner tasdiqlagan chegarada bo‘lsa production’ga kiradi (F5-AT-14); aks holda faqat RU yoki umuman yo‘q. Chegara, scope (`uz_ru` yoki `ru_only`) va xizmat ko‘rsatgan snapshot `models.pre_screen` da; F5-AT-14 ikkala scope uchun ham o‘tmasa kalit tasdiqlanmaydi va pre-screen o‘chiq qoladi. Pre-screen faqat `models.pre_screen` approved va PRE_SCREEN profili (F5_GO ni talab qiladi, boshqa profil uni meros olmaydi; capability `review.pre_screen`) PASS bo‘lganda ishlaydi; aks holda Reviewer avvalgidek ishlaydi, kalit qaytarib olinsa faqat pre-screen o‘chadi va F6 gate’lariga tegmaydi. Har Jev chaqiruvidan oldin gateway’dagi lokal PII guard ishlaydi (telefon, email, karta yoki ID raqami yoki UZ/RU ism va manzil evristikasi ishlasa Jev chaqirilmaydi, `pii_leakage` lokal bayroqlanadi; asosiy himoya — Q28; guard’ning yolg‘on bayroq ulushi ham F5-AT-14 da o‘lchanadi va `models.pre_screen` chegarasida bo‘ladi); so‘rovlar `data_collection: deny` bilan (Q44★).

Tayinlov rol UID’i, adapter/versiya, model/provider, prompt/skill/tool/schema/config revision va eval natija hash’i bilan **`models.assignments`** readiness yozuviga yoziladi (Reviewer’ning ikki slot’i va Jev pre-screen pin’i bilan). ADR-016 faqat qaror mezoni; kanonik tayinlov — `models.assignments`.

## 2. Global konfiguratsiya yopilishi — HG-F5-04

[readiness.yaml](../09_Config_Templates/readiness.yaml) va [CONFIG_CONTRACT](../11_Production_Contracts/CONFIG_CONTRACT.md) bo‘yicha F5_GO PASS = F5_GO kalitlari + meros profillarning (F2_TRACKING_PASS, F4_CONTENT, FE_RELEASE va ularning ajdodlari) har kaliti `approved` (gate paytida `max_evidence_age` ichida) yoki valid `not_applicable`. Config template’da `null` ochiq blocker sifatida to‘g‘ri; **active live bundle**da critical null/TBD/example yo‘q. O‘chirilgan ixtiyoriy feature owner sababi bilan valid `not_applicable`; critical kalit N/A bo‘lmaydi. Approver — dalilni tayyorlagan shaxs emas, `accountable_role` ga ega inson; builder va agentlar faqat `prepared_by` ([PHASES §4.3](PHASES.md)).

| Yopiladigan shart | F5_GO kalitlari | Dalil |
|---|---|---|
| Resurs va operator yuki | `ops.resource_envelope` (technical_operator + owner), `ops.founder_time_budget` (ixtiyoriy, ⧗ OD-15) | real shadow davridagi yuklama o‘lchovi; slice zaxiralari, navbat chegaralari, disk/inode harakatlari (UAT-33/34) |
| Qualification sifati | `sales.qa` | report-only va shadow davridagi sampled status QA |
| Pul va biznes natijasi (◇ P-08, ⧗ OD-06) | `business.outcome_sources`, `business.contribution_policy` (finance_owner + owner), `business.attribution`, `business.baseline`, `business.acceptance`, `business.exposure` | contract/paid/fulfilment/refund manbalari, yetilgan kogorta oynasi, min sample, pipeline target’lari, KC-02 chegarasi, zero-qualified exposure va handback |
| Haqiqiy sig‘im | `fleet.freshness`, `fleet.waitlist` (⧗ OD-07 vaqtinchalik qoida), `fleet.thresholds` | bugungi snapshot TTL va egasi; waitlist qoidalari; data bilan kalibrlangan bandlar |
| Optimizatsiya maqsadi | `vendor.qualified_optimization` | Q29.1 ✅: akkaunt eligibility va o‘lchangan oylik hajm, aks holda `Lead` + qualified guardrail |
| Xarajat | `budget.anomaly`, `budget.tco` | real shadow’dan anomaliya va loop chegaralari; host (owner PC, ikkinchi disk, UPS, Omada controller), elektr va ofis interneti, off-host monitor (HG-F2-17), litsenziya, inson ops, kredit fee/soliq/FX va paid Meta alohida |
| Reklama pul nazorati | `budget.ads_pacing`, `budget.ads_limits` | spend freshness cutoff va `protective_pause` trigger’i (provider limitga qo‘shimcha); safety margin, valyuta/FX, floor, split va headroom alertlari |
| Model | `models.assignments` | §1 (Reviewer’ning ikki slot’i va Jev pin’i bilan) |
| Global yopilish | `config.closure` | schema-valid cross-reference, critical null 0, egasi/dalili/revision’i bilan, active servis ACK |

- **`models.pre_screen` F5_GO kaliti emas:** u alohida PRE_SCREEN profilining kaliti (F5_GO ni talab qiladi, boshqa profil meros olmaydi; capability `review.pre_screen`). Dalili F5-AT-14 da tayyorlanadi; tasdiqlanmasa yoki qaytarib olinsa faqat pre-screen o‘chadi, F5_GO va F6 gate’lariga ta’siri yo‘q.
- **Meros profillar** gate paytida qayta tekshiriladi: F1_* (owner identity, OpenRouter davri, request bounds, runner prototipi, component lock’lar, workflow mexanizmi), F2_LIVE_INTAKE (roster, responder’lar, monitor, ACK, eskalatsiya, credential inventari, intake recovery, qualification, sales SOP, offer va asset huquqlari, privacy, tracking freshness, CAPI, amoCRM quota), F2_TRACKING_PASS, F3_CONTROLLED_TEST (kill target’lari, provider spending limit read-back, Meta access tier, read tool’lar), F4_AGENTS/F4_CONTENT va FE_SANDBOX/FE_RELEASE.
- **F5’da gate’lanmaydi:** `sale.readiness`, `business.step1_comparison`, `ops.sale_handback_roster` — F6_STEP2 (◇ P-09); `recovery.full_datasets`, `recovery.full_drill`, `ops.independent_monitor_full`, `ops.ads_handback_roster`, `budget.ads_fresh_check` — F6_STEP1. F5 ularning dalilini tayyorlaydi; to‘liq mashq AMT PC’dagi izolyatsiyalangan `restore_drill` muhitida (HG-F6-03).
- **Trust Ramp parametrlari (★ 10/14, `requires_identity_isolation_evidence`)** HG-F5-04 da owner tomonidan ko‘rib chiqiladi, majburiy dalil `build/F5/TRUST_RAMP_FEASIBILITY.md` bilan: har trust kaliti uchun kunlik jonli item soni r, hal qiluvchi natija ulushi d, hal qiluvchilar ichida `met` ulushi p (shadow va tarixdan); ikkala model chiqariladi (◇ P-55): reset (amaldagi) — q = d · p, E[item] = (1 − q¹⁰) / ((1 − q) · q¹⁰), E[kun] = E[item] / r + horizon + 14; hold (muqobil) — E[item] = (1 − p¹⁰) / ((1 − p) · p¹⁰), E[kun] = E[item] / (r · d) + horizon + 14; 180 kundan ortig‘i "joriy hajmda yetib bo‘lmaydi" deb belgilanadi (r = 0,5, d = 0,3 da reset bilan L2 hech qachon). Shu yerda `inconclusive` seriyani 0 ga qaytaradigan vaqtinchalik qattiqroq o‘qish (◇ P-42) va `outcome_band_max_relative_width` (`business.acceptance`) ham ko‘riladi; o‘zgarish faqat config PR va owner merge orqali (`approval-policy.yaml` himoyalangan sirt).

Biznes chegaralari uydirma raqam bilan to‘ldirilmaydi; owner, sales/fleet/finance/privacy mas’ullari original manba bilan tasdiqlaydi. Umumiy RPO ≤24 soat (mantiqiy xato uchun; host yo‘qolishi — Q55) minimum; RTO va data-class qiymati dalilsiz "erishilgan" deyilmaydi. To‘liq drill (`restore_drill` muhitida lokal snapshot’dan restore va manbalardan qayta qurish) dalili Step 1 dan oldin HG-F6-03 da yopiladi. F5 go o‘zi live ruxsat bermaydi.

## 3. Haqiqiy 7 kun shadow

Oyna langari: HG-F2-08 va F3+F4 accepted bo‘lgandan keyingi birinchi to‘liq kun ([PHASES §3](PHASES.md)). Barcha agentlar to‘liq ritmda (`operations.yaml#schedule`); gateway shadow va barcha pipeline L0. Targetolog real reklamani boshqaradi; AMT normal remote write 0 — Meta activity log va dispatcher attempt’lari buni tasdiqlaydi.

- Har kuni 10:00 SHADOW change set aniq revision’lar bilan. Owner va targetolog har bandni `cs:rate:<id>:<useful|neutral|harmful>` callback bilan baholaydi (`shadow_rater` flag’i). Agregatsiya ⧗ OD-09 (taklif: biror baholovchi `harmful` desa — harmful; `useful` = ikkalasi useful yoki useful + neutral; qamrov 100%).
- Shadow metrikalari: "10:00 SHADOW change set yetkazildi — 7/7"; "Du 09:00 haftalik hisobot — oynadagi rejalangan run’lar 100%"; ixtiyoriy "08:00 fleet so‘rovi yuborildi — 7/7". EVALS shadow chegaralari (★, ◇ P-44/P-54): ≥60% `useful`, 5–7-kunlarda va yakuniy (uzaytirilgan bo‘lsa ham) oynaning oxirgi 3 kunida 0 `harmful`; moddiy bandlarda Wilson 80% quyi chegarasi ≥ 50%.
- Shadow yozuvi Trust Ramp’da clean item emas. Shadow, eval va test copy’lari "birinchi 20 copy" til tekshiruvi hisobiga kirmaydi (◇ P-15); ular ixtiyoriy tekshirilishi mumkin.
- CMO → Creative → Reviewer → Media Buyer zanjirida handoff qabul/rad dalili (EVO-AT13); WF-B05 eksperiment oqimi shadow’da.
- `ops.resource_envelope` shu oynada o‘lchanadi (peak/soak; UAT-33/34).
- 7 kun tracking/freshness yashil; false-positive, harmful taklif, offer/sig‘im/sale/consent/retry tavsiyalari tahlil qilinadi. Inson bahosi va haqiqiy manba model evali bilan solishtiriladi; zararli fikr o‘rtacha ball ostida yashirilmaydi. Budget actual + reserved/proyeksiya rol, media va provider billing bilan reconcile. Shadow haftasi atipik bo‘lsa hisobotda va qabulda cheklov; `min_rated_items` (30) yoki `min_material_items` (10) yig‘ilmasa oyna 7 kunga uzaytiriladi, ko‘pi bilan ikki marta, keyin HG-F5-02 qaror qiladi ([EVALS §6](../07_Evals/EVALS.md), `decision-statistics.yaml` SHADOW_WEEK, ◇ P-44).

## 4. Go/no-go

Artefaktlar exact revision’lar bilan: `MODEL_RESEARCH`, `EVAL_RESULTS`, `GOLDEN_COPY_RESULT`, `SHADOW_DAILY`, `SHADOW_REPORT`, `COST_PROJECTION`, `READINESS_CLOSURE`, `GO_NO_GO`. Premortem C1–C10 yangilanadi. Avval HG-F5-04 global signoff, keyin HG-F5-02.

`GO_NO_GO.md` ikki alohida savolga javob beradi:

- **A) Operatsion xavfsizlik:** `GO` yoki `NO-GO`, dalil bilan — F5 AT, red team, F5_GO readiness, shadow xavfsizligi, xarajat proyeksiyasi.
- **B) Biznes asosi:** `sufficient | inconclusive | insufficient` va exposure qarori (`business.exposure` doirasida maksimal sarf/vaqt). B `sufficient` bo‘lmasa F6 faqat rent L1 bilan va tasdiqlangan exposure ichida boradi; Step 2 hech qachon avtomatik emas — har doim HG-F6-02 va F6_STEP2 dalili bilan.

**GO** (A = GO) F6 Step 0 ni (drill’lar, privilege revocation, joriy health tekshiruvlari) boshlashga ruxsat; to‘g‘ridan-to‘g‘ri reklama vakolati emas. **NO-GO** da L0/shadow saqlanadi va tegishli build/eval bandi qayta ishlanadi.

## Acceptance tests

| ID | Nima | Usul | Kutilgan |
|---|---|---|---|
| F5-AT-01 | Model research | `MODEL_RESEARCH.md` | har rol 2–3 nomzod; rasmiy manba + sana + aniq ID/narx/provider; pinned adapter source va haqiqiy tool chain |
| F5-AT-02 | Eval to‘liqligi | `EVAL_RESULTS.md` | har agent × nomzod × to‘plam natijasi; EVALS’dagi o‘tish chegaralari `pass`; Reviewer til holdout’i bilan |
| F5-AT-03 | Golden copy | `GOLDEN_COPY_RESULT.md` | ≥3 baholovchi natijasi (owner, targetolog, HG-F5-03); g‘olib model sababi bilan |
| F5-AT-04 | Model tayinlash | active rol identity/adapter/model/prompt/tool/config bundle vs `models.assignments` readiness yozuvi (ADR-016 faqat mezon) | mos, Reviewer’ning ikki slot’i bilan; smoke testlar qayta `pass` |
| F5-AT-05 | Mustaqil red team | muallif kontekstisiz yangi subagent: gateway, ops-bot, tg-auth, Hermes va Reviewer’ni chetlab o‘tish; landing matni, Drive fayl nomi, Telegram xabari va amoCRM tegi orqali injection | critical topilma yo‘q yoki tuzatilgan |
| F5-AT-06 | Shadow davomiyligi | `SHADOW_DAILY.md` + ops-bot log | langardan keyingi 7 ketma-ket to‘liq kun; 10:00 SHADOW change set 7/7; Du 09:00 hisobot — oynadagi rejalangan run’lar 100%; reyting qamrovi 100%, agregatsiya ⧗ OD-09 bo‘yicha; tracking/freshness dalili |
| F5-AT-07 | Shadow xavfsizligi | Meta activity log | AMT tomonidan bajarilgan o‘zgarish **yo‘q** |
| F5-AT-08 | Xarajat | `COST_PROJECTION.md` | oylik runtime proyeksiya ≤ USD 150/oy (15 000 USD minor), actual + reserved va rol/ulush/media chegaralari ichida; `budget.tco` approved; proyeksiya shadow o‘lchovidan va F4 runtime talab modeli (`cost-model.json`, ◇ P-81) bilan solishtirilgan: o‘lchangan agent sarfi model p50–p90 oralig‘idan tashqarida bo‘lsa sababi (qaysi kirish farq qildi) va qayta kalibrlangan model HG-F5-02 dan oldin |
| F5-AT-09 | Kalibrlash | barcha majburiy config schema’lari + readiness cross-check + active revision ACK | critical null/TBD/placeholder yo‘q; barcha tegishli readiness approved, dalil va egasi bilan; ixtiyoriy o‘chirilgan N/A asoslangan |
| F5-AT-10 | Go/no-go | `GO_NO_GO.md` + HG-F5-02 | owner qarori ikki qism bilan: A) GO/NO-GO dalil bilan; B) `sufficient`/`inconclusive`/`insufficient` va exposure; B `sufficient` bo‘lmasa F6 faqat rent L1, Step 2 avtomatik emas |
| F5-AT-11 | Global readiness | F5_GO profili va meros profillar reyestri | HG-F5-04; har qiymat typed/evidenced/approved, `max_evidence_age` ichida; critical placeholder 0 |
| F5-AT-12 | Biznes: nol yoki past N | qualified = 0 + sarf, yetilmagan kogorta va siyrak sample fixture’i | jim PASS yoki g‘olib yo‘q; scale blok va kelishilgan exposure/handback ishlaydi |
| F5-AT-13 | Haqiqiy identity model | barcha 6 rol haqiqiy adapter/UID/model/tool/trace va fallback fault’i | to‘g‘ri rol atributsiyasi, isolated tool chain; qo‘llab-quvvatlanmagan yoki fallback model yo‘q |
| F5-AT-14 | Jev pre-screen eval (Q61) | UZ va RU golden copy + belgilangan qoidabuzarlik to‘plami (policy checklist bo‘yicha sintetik buzilishlar, bo‘lib to‘lash/special ad category va PII sizish holatlari) + lokal PII guard holatlari (UZ/RU ism, familiya + bosh harf, manzil, biznes manzili, kichik harfli `-ов` so‘zlari va qoldiq holatlar — yolg‘iz ism, yolg‘iz familiya); savollar inglizcha. Birinchi 20 jonli copy’ning inson tekshiruvi F6 Step 1 dan keyin bo‘ladi (◇ P-15), uning natijalari keyingi qayta baholashga qo‘shiladi | har check va til bo‘yicha recall va yolg‘on bayroq ulushi hamda lokal PII guard’ning yolg‘on bayroq ulushi owner tasdiqlagan chegarada; owner guard’ning qoldiq ism/manzil xavfini qabul qilgani yoki rad etgani yozilgan (OI-54); chegara, scope (`uz_ru` yoki `ru_only`) va xizmat ko‘rsatgan snapshot `models.pre_screen` da; ikkala scope uchun ham o‘tmasa `models.pre_screen` tasdiqlanmaydi va pre-screen o‘chiq qoladi (PRE_SCREEN profili PASS emas) |

## HUMAN_GATE

Avval Q67: FE qatlami deployed, FE `verified_in_staging`, FE_RELEASE PASS, HG-FE-01…05 va Q66 exact baseline human signoff → HG-F5-03 → formal eval/HG-F5-01; F3/F4 accepted va HG-F2-08 bilan real shadow 7 kun → HG-F5-04 → HG-F5-02. HG-F4-04 kerak bo‘lsa oldin yopilgan; HG-GIT-01. FE gate’larini faqat F5_GO oldigacha qoldirish mumkin emas.

## Riskler (RSK-03)

| Nosozlik | Oqibat | Chora |
|---|---|---|
| Eval to‘plami haqiqiy ishni aks ettirmaydi | yaxshi ball, yomon natija | shadow taqqoslash evaldan ustun; golden copy’ni inson baholaydi |
| Shadow haftasi mavsumiy atipik | noto‘g‘ri xulosa | 12 oylik profil bilan solishtirish; oyna uzaytiriladi; B qismi `inconclusive` |
| Baholovchilar ko‘r-ko‘rona baholaydi (rubber-stamp) | Trust Ramp signali buziladi | `harmful`/`neutral` ulushi va izohlar kuzatiladi; agregatsiya ⧗ OD-09 |
| Xarajat proyeksiyasi USD 150/oy (15 000 USD minor) dan oshadi | F6’da agentlar to‘xtab qoladi | routine chastotasi, model va caching F5’da sozlanadi; HG-F4-04 variantlari |
| Shadow sifati biznes asosi bilan aralashadi | asossiz go | `GO_NO_GO.md` A va B qismlari alohida |
