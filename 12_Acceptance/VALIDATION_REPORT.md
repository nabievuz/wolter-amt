# Paket tekshiruvi — validator natijasi

Holat: avtomatik yozilgan hisobot · Runtime: NOT_RUN · Sana: 2026-10-25.

Bu fayl qo‘lda yozilmaydi: u [validate_bundle.py](validate_bundle.py) `--write-report` rejimining haqiqiy natijasidan yaratiladi. Validator faqat fayllarni o‘qiydi; server, API yoki biznes natijasi haqida hech narsa isbotlamaydi. Natija o‘zgarsa hisobot qayta yaratiladi; qo‘lda tahrirlangan PASS dalil hisoblanmaydi.

## 1. Natija

| Buyruq | Boshlangan (UTC) | Exit code | Natija |
|---|---|---|---|
| `python3 12_Acceptance/validate_bundle.py --json` | 2026-10-25T09:01:47Z | 0 | **PASS** — 210 qoida, 0 xato, 0 ogohlantirish |
| `python3 12_Acceptance/validate_bundle.py --self-test` | 2026-10-25T09:01:51Z | 0 | **PASS** — 786/786 holat kutilgandek |

## 2. Self-test tarkibi

Har negativ holat bitta qoidani buzadi va validator aynan o‘sha qoidani FAIL qilishi kerak; ijobiy profil ssenariylari PASS bo‘lishi kerak. Manba — [fixtures/mutations.yaml](fixtures/mutations.yaml).

| Turi | Nima qiladi | Holatlar | Kutilgandek |
|---|---|---|---|
| HC | haqiqiy tool JSON sxemalariga ijobiy/salbiy payload va sintetik aggregation/RPO hisoblari; runtime dalili emas | 98 | 98 |
| FX | config’ni xotirada buzadi (pul, tasdiq, kill, readiness va uning tayyorlovchilari, RBAC, release, muhitlar, workflow, concurrency, ritm) | 543 | 543 |
| PS | readiness profilini sintetik tasdiqlar bilan baholaydi (shaxs havolasi, tayyorlovchi ≠ tasdiqlovchi, qiymat, vaqt, co-signer, N/A) | 17 | 17 |
| DM | bitta hujjatni vaqtinchalik nusxada buzadi (skill Tool scope, tool/action/control op/himoya nazorati jadvallari, ritm, CONFIG_CONTRACT, dalil yoshi, kuzatuvchanlik, ID, havola, qoldiq, owner matni) | 128 | 128 |

## 3. Tekshirilgan qoidalar

| Oila | Mazmuni | Qoidalar |
|---|---|---|
| H | Claude handoff: mavjud server admission/init, immutable review va approval binding, entity selector sxemalari, mustaqil PR review, attempt retry/fence/expiry, qabul qilingan custody transfer, provider snapshot yozuvchisi va usable-point RPO; sintetik fixture runtime PASS emas | H01, H02, H03, H04, H05, H06, H07, H08, H09, H10, H11, H12, H13 |
| S | Tuzilma: YAML yuklanishi, takroriy kalit yo‘qligi, sarlavha, `schema_version`, `bundle_state`, qo‘shtirnoqsiz `: ` satrni mapping’ga aylantirmagan, `, ` matnni bo‘lmagan va ` #` uni izoh bilan kesmagan (S09) | S01, S02, S03, S05, S07, S08, S09 |
| M | Pul: USD 150/oy = 15 000 USD minor va USD 1 500/oy = 150 000 USD minor, ulushlar, provider spending limit, rolling24h ≤ 20%, HG-F4-04 variantlari, agent’li har workflow’da run cap’i va to‘g‘ri xarajat hisobi (M09) | M01, M02, M03, M04, M05, M06, M07, M08, M09 |
| A | Tasdiq siyosati: TTL, never_auto, owner-only action’lar, Reviewer mustaqilligi, Q25 ceiling, Q42 til tekshiruvi, protective pause, Trust Ramp mexanikasi va daraja o‘tishlari (A14), o‘zgarishlar oralig‘i va eksperiment lock’i (A15), protective pauzadan keyingi qayta yoqish faqat owner va never_auto (A16) | A01, A02, A03, A04, A05, A06, A07, A08, A09, A10, A11, A12, A13, A14, A15, A16 |
| W | Workflow ta’riflari: JSON sxema, approval action’lari, testlar va talab havolalari, concurrency va run umri (W09), run umri step timeout yo‘lini va jadval slotlarini qamrashi (W14), bajaruvchi, principal va trigger manbasi reyestrlari (W08), shartli step’lar (W15), tasdiq va dispatch egaligi (W11), boshi berk tarmoq yo‘qligi (W16), handoff rad etilganda chegaralangan yo‘l (W17), ko‘p command’li step holati (W18), parent/child start shartnomasi (W13), handoff konvertining deterministik tekshiruvi (W19), inson step timeout’i eskalatsiya bilan mos (W20), inson vazifasi yakunlanish signali va deadlock yo‘qligi (W21) | W01, W02, W03, W04, W05, W06, W07, W08, W09, W10, W11, W12, W13, W14, W15, W16, W17, W18, W19, W20, W21 |
| X | Ijro siyosati: restore boshlanish rejimi, resume, maintenance hold, capability → profil bog‘lanishi, muhitlar kesishmasligi | X01, X02, X03, X04, X05, X06, X07, X08, X09 |
| K | Kill criteria: Q31 chegaralari, resume, `data_status` lug‘ati, KC seriyasi holat mashinasi (K05); umumiy statistik qaror spec’i va uning iste’molchilari (K04), oldindan ro‘yxatga olingan Step 2 qoidasi (K06), shadow mezonining minimal soni va uzaytirish chegarasi (K07) | K01, K02, K03, K04, K05, K06, K07 |
| R | Readiness: profil DAG’i, bitta kalit — bitta gate, inson javobgarligi, `max_evidence_age`, agent tayyorlovchilar F4_AGENTS’dan, CONFIG_CONTRACT va EVOLUTION_CONTRACT jadvallari bilan moslik, profil sharti bilan rad etiladigan va raqamli chegarali qiymatlar, ma’lumot sifatidagi ruxsat etilgan qiymatlar (R20, C-28, C-29) | R01, R02, R03, R04, R05, R06, R07, R08, R10, R12, R13, R14, R15, R16, R17, R18, R19, R20 |
| B | RBAC: rollar, flag’lar, seed qoidalari | B01, B02, B03 |
| V | Release: build_once_promote, owner-only imzolangan tag, F1 dan `release_approvals` yozuvi, ACK ro‘yxatlari servis reyestriga mos | V01, V02, V03, V04, V05, V06, V07, V08, V09, V10, V11 |
| T | Ritm: `operations.yaml#schedule` yagona manba; workflow timer’lari, jadval slotini nomlagan eskalatsiyalar (T08), sale readiness cutoff va hujjat jadvallari unga mos; har schedule yozuvini o‘sha slotga bog‘langan workflow step’i yoki timer’i, yoki missed-run alert’li job bajaradi, alert kodi TELEGRAM §6.2 katalogida (T11) | T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11 |
| E | Self-evolution: auto-release o‘chiq, himoyalangan sirtlar va config qamrovi, engineering byudjeti alohida, resurs slice’lari | E01, E02, E03, E04, E05, E06, E07, E08, E09 |
| O | Owner qarorlari qulfi: Q37 tracking `read_only` trigger’i, Q29.1 hajm chegarasi va uning o‘lchov qoidasi (O08), Q55 lokal snapshot (offsite yo‘q, 7 kun), Q54/Q62 shifrlanmagan disk va diskka yozilmaydigan webhook PII, Q57/Q58 kiruvchi port yo‘q, Q61 Jev pre-screen qoidalari | O01, O02, O03, O04, O05, O06, O07, O08 |
| D | Hujjatlar: havolalar va ID’lar; tool, action, servis reyestri, control op matritsasi, himoya nazoratlari, `/role` buyruqlari, slice va dalil yoshi jadvallari config’ga mos; owner qarorlari matni qulfi; audit topilmalari havolalari; ziddiyatlar reyestri ID’lari (D34), protective pauzadan keyingi qayta yoqish gateway/GT/callback’da (D35) | D01, D03, D04, D05, D06, D07, D08, D09, D10, D11, D12, D13, D14, D15, D16, D17, D18, D19, D20, D21, D22, D23, D24, D25, D26, D28, D29, D30, D31, D32, D33, D34, D35, D37 |
| Z | Versiya va tarix qoldig‘i, 100 baravar noto‘g‘ri pul yozuvi | Z01 |
| G | Platforma va integratsiyalar: alert katalogi yopiq, o‘chgan monitorni host aniqlaydi (`monitor_unreachable_alert`), tashqi bog‘liqliklar shartnomasi (`external_dependencies`: mas’ul, env’dagi credential, monitorning ACK’dan oldin saqlashi va mustaqil hostingi, hostlararo PII’siz pull o‘qish va reader egress’i), integratsiya kuzatuvi (`integration_watch`) va amoCRM webhook javob byudjeti, CAPI xato taksonomiyasi (`capi_delivery`: batch va auth xatosi eventni yo‘qotmaydi, yuborilmagan so‘rov qayta yuboriladi, noaniq attempt hold’dan keyin sanaladigan yo‘qotish), off-host oqim inventari (`off_host_flows`: yopiq yozuv, `by` va `direction`, egress’i bor har servis qamrab olingan), config’da vergul tufayli kalitga aylangan matn yo‘q (G07), foydalanuvchi huquqini oladigan amoCRM tokenlari `[user-rights]` va `issuing_user_role` bilan, tor scope da’vosisiz (G08), llm-proxy xato kontraktida SDK o‘zi retry qiladigan HTTP kodi yo‘q va upstream xatosi alohida kod (G09), har allowlist tool’ining yopiq argument sxemasi `schemas/tools/` va Hermes Telegram chiqish filtri (G10), runtime talab va unit-cost modeli (`cost-model.schema.json`: agentlar = ulushlar, kirishlar [D]/[T]/[X] tegi bilan, p90 ulush va kalit cap’i bilan solishtiriladi; F1-AT-13 chaqiruv narxi, `ai_requests` token bo‘linishi; G11), provider pin va prompt cache (`provider_policy`: Claude faqat Anthropic, fallback yo‘q, `data_collection: deny`, `cache_control` o‘zgarmaydi, keshli narx faqat F1-AT-29 isbotlagan yo‘lda; G12), rol bo‘yicha prompt manifesti (`prompt-manifest.yaml`: eager to‘plam = kontrakt, kernel, invariant indeksi, rol prompti va aynan charter skill’lari; taxminiy hajm ≤ `max_fixed_tokens`; butun kontrakt fayllari faqat on demand; `kernel_ref`ni runner yozadi, `prompt_digest`, `max_input_tokens`; G13), kalit 90% to‘xtashining doirasi (`admission_classes`: boshlang‘ich holatda har admission non-critical, `critical` yozuvi mavjud step’ni nomlaydi, noma’lum yozuv config’ni rad etadi; G14), agent run o‘rtasida to‘xtaganda command hayoti (`review_ttl`: tekshirilmagan band ✅ Q32 TTL’ida `expired`, hold bo‘shaydi, avtomatik tasdiq yo‘q; `orphan_cancel`: yarim step bandlari `step_incomplete`; DATA_MODEL §6.2 `extra_transitions` nusxasi aynan; G15), reservation o‘lchami (`reservation_sizing`: bitta upper bound ≤ `max_cost_minor`, rolning barcha ochiq hold’lari ulushning 80–100% oralig‘ida, har LLM ulushi rolida; ortiqcha so‘rov navbatda va `slot_wait_exceeded` (423); `uncertain` slot’ini ushlaydi va OpenRouter generation yozuvi bilan settle bo‘ladi, bepul kredit emas; F1-AT-30; G16), Hermes xotirasi (`hermes_memory`: pin’lar — ikkala yozish tasdig‘i on, fon review off, belgi chegaralari; `session_search` yashirin; tasdiq buyruqlari faqat owner DM’idan, bittadan, owner bo‘lmagan sessiyadagi yozuv rad, fail-closed fallback; suhbat ombori va memory fayllari privacy dataset’i; ADR-004 pin nusxasi va SECURITY custody jadvali har dataset bilan; G17), runner sessiyasi xotira emas (`runner_contract`: har step yangi sessiya, tmpfs workspace, read-only home, Claude Code memory o‘chiq, transcript `max_input_tokens` bilan va oshsa `input_over_bound` (413) — yuborilmaydi; F4-AT-30; G18), ulush qismlari (`sub_shares.cmo`: aynan `chat` va `workflow`, yig‘indisi CMO ulushiga teng, run token’siz so‘rov — chat, har qismda warn/stop va pauza qatori, chat tugasa LLM’siz xabar va workflow davom etadi; qiymatlar `budget.request_bounds`da; F4-AT-31; G19), media attributsiyasi (`media_generation.attribution`: bitta reservation egasi `media_generation`, aynan kalit + media ulushi + so‘ragan agent ulushi bitta tranzaksiyada, so‘ragan agentlar = media tool’i bor allowlist’lar; bitta job, oylik soniya va parallellik chegaralari owner qiymati; narx revision’i majburiy; C-40; F4-AT-32; G20), saboq va golden copy byudjeti (sxema `guidance_eligible` yozuvni faqat `accepted`, `lesson` ≤ 600 belgi, `scope` va `review_by` bilan qabul qiladi — sintetik yozuvlar bilan tekshiriladi; har chaqiruvga ko‘pi bilan 15 ta mos saboq, eng yangisi birinchi, ≤ 2 000 token `max_fixed_tokens` ichida; golden copy aynan creative-studio va reviewer uchun, pipeline × format bo‘yicha ≤ 6; FE-AT-16; G21) | G01, G02, G03, G04, G05, G06, G07, G08, G09, G10, G11, G12, G13, G14, G15, G16, G17, G18, G19, G20, G21, G22 |
| C | Builder context pack’lari (CLAUDE.md §0): har faza uchun pack bor, taxminiy hajmi ≤ 60 000 token, ko‘rsatilgan bo‘limlar mavjud | C01, C02, C03 |
| Q | Kuzatuvchanlik: har talab va invariant testga bog‘langan, har test talab/invariant/workflow’ga bog‘langan, PRD va INVARIANTS test ustunlari mos; bu hisobot joriy validator natijasiga mos (Q09) | Q02, Q03, Q04, Q05, Q06, Q07, Q08, Q09 |

## 4. To‘plam faktlari

| Fakt | Qiymat |
|---|---|
| Fayllar (jami) | 2622 |
| `.md` fayllar | 108 |
| `.yaml` fayllar | 43 |
| `.json` fayllar | 53 |
| `.example` fayllar | 1 |
| `.hujson` fayllar | 1 |
| `.py` fayllar | 3 |
| Handoff schema fixture’lari | 55 |
| Handoff aggregation/RPO fixture’lari | 43 |
| Readiness kalitlari | 72 |
| Readiness profillari | 17 |
| Workflow ta’riflari | 17 |
| HUMAN_GATE’lar | 63 |
| Faza AT’lari | 199 |
| UAT va EVO-AT | 48 |
| WF-TEST’lar | 98 |
| Owner Q-ID’lari | 77 |
| Invariantlar | 25 |
| ADR’lar | 34 |
| Incident turlari (INC) | 29 |
| owner_decision_rows | 76 |
| Markdown hujjatlar | 108 |
| Talablar (FR/NFR/EVO-R) | 68 |
| Eng katta context pack (taxminiy token) | 55617 |

## 5. Validator nimani isbotlamaydi

- Runtime holatini: barcha testlar `not_run`; servislar qurilmagan.
- Vendor faktlarini: ular [RESEARCH_FACTS](../10_Reference/RESEARCH_FACTS.md) da build kuni qayta tekshiriladi.
- Readiness qiymatlarini: shablondagi kalitlar `pending`; profil PASS faqat inson tasdig‘i va dalil bilan (`--profile` rejimi).
- Matn sifatini va biznes to‘g‘riligini: buni mustaqil inson va agent review’lari tekshiradi ([DECISION_LOG](../00_Decisions/DECISION_LOG.md)).

## 6. Qayta ishga tushirish

```bash
pip install pyyaml 'jsonschema>=4.18'
python3 12_Acceptance/validate_bundle.py            # to‘liq tekshiruv; xato bo‘lsa exit 1
python3 12_Acceptance/validate_bundle.py --self-test # negativ va ijobiy holatlar
python3 12_Acceptance/validate_bundle.py --write-report # shu hisobotni haqiqiy natijadan qayta yozadi
python3 12_Acceptance/validate_bundle.py --profile F6_STEP1 --readiness <to‘ldirilgan readiness.yaml>
```
