# ADR-023 — AdClaw hozir reference only

Holat: Proposed · Qaror egasi: builder ◇ P-25 (manba baholash; Q01 va Q15/Q39 ✅ o‘zgarishsiz qoladi) · Sana: 2026-10-23

## Kontekst

- AdClaw manbasi baholangan [D: github.com/Citedy/adclaw, `main` snapshot `25bf9601f30f069dc5c24f4845abc9ce120d809b`, paket 1.0.33; 2026-10-23 dagi targeted statik audit — o‘rnatish, dependency testi, jonli reklama yoki Citedy xizmatlarini chaqirish bajarilmagan]. U agent profillari, suhbat va jadval boshqaruvi, MCP ulanishi, xotira va marketing ko‘rsatmalarini bitta dasturda jamlaydi.
- Kuzatilgan cheklovlar [D: manba kodi]:
  - Meta skill eksport/screenshot va checklist asosida audit qiladi — bu Marketing API executor, CAPI bridge yoki amoCRM integratsiyasi tayyorligini isbotlamaydi;
  - `execute_delegation` persona promptini tuzib, bitta model chaqiruvi natijasini qaytaradi — tool’lar bilan to‘liq agent run’i emas;
  - rasmiy security modeli bir ishonch chegarasidagi operatorni nazarda tutadi — Wolter’dagi owner/approver/fleet/sales vakolatlari, mustaqil Reviewer va secret custody alohida enforcement talab qiladi;
  - OpenRouter yo‘lida shell va umumiy tool’lar bor; persona MCP tanlovi barcha yo‘llarni avtomatik cheklamaydi;
  - `META_ADS_ACCESS_TOKEN` bo‘lsa tashqi `npx -y meta-ads-mcp` versiyaga qotirilmasdan yoqiladi;
  - tashqi skill hub, avtomatik tuzatish va Citedy xizmatlari yo‘llari bor; ayrim bundled materiallar root Apache belgisidan boshqa litsenziya shartlariga ega.
- Owner Paperclip (Q01) va Hermes CMO (Q15/Q39) ni tanlagan; AdClaw bilan almashtirish shu ✅ qarorlarni o‘zgartiradi va yangi owner Q talab qiladi.
- Tejaladigan vaqt yoki token o‘lchanmagan [?]; foiz yoki pul va’dasi berilmaydi.

## Qaror

1. **Joriy holat — `reference_only`.** Tanlangan dizayn va checklist materiallari (persona UX, MCP lifecycle, sessiya saqlash, audit tuzilmasi, Meta audit rubrikasi) mahalliylashtirish, fakt va litsenziya tekshiruvi bilan manba sifatida ishlatiladi. Paperclip, Hermes, gateway yoki llm-proxy almashtirilmaydi; hostga uchinchi runtime qo‘shilmaydi.
2. **Kanonik adoption holati enum’i:** `reference_only | restricted_runtime_candidate | replacement_proposal`.

   | Holat | Ma’nosi | O‘tish sharti |
   |---|---|---|
   | `reference_only` | faqat manba va material; runtime yo‘q | — |
   | `restricted_runtime_candidate` | gateway va llm-proxy ortida, kalitsiz va PII’siz, egress cheklangan, immutable skill’li cheklangan worker yoki CMO runtime muqobili | izolyatsiyalangan muhitda quyidagi beshta mezon dalili + owner qarori |
   | `replacement_proposal` | Paperclip va/yoki Hermes’ni almashtirish taklifi | beshta mezon + barcha UAT qayta dalillanishi + Q01/Q15/Q39 ni o‘zgartiruvchi yangi owner Q |

3. **Moslik mezonlari:**
   1. *Vazifa bajarish* — olti rolning har biri to‘g‘ri model, tasdiqlangan skill va kerakli tool bilan ishlaydi; direct chat, delegation, cron, restart va yakuniy natija alohida tekshiriladi; oddiy matn qaytishi "vazifa bajarildi" deb belgilanmaydi.
   2. *Vakolat* — barcha tashqi marketing harakati gateway orqali, barcha LLM/media sarfi proxy orqali; agent secret va control faylini o‘qiy yoki yoza olmaydi; mustaqil Reviewer testdan o‘tadi; fallback o‘chiq.
   3. *Production nazorati* — durable lead, approval revision, uncertain outcome, sarf, kill, restore va baseline mezonlari saqlanadi.
   4. *Sifat va tannarx* — bir xil Wolter fixture, golden copy, tool-use va nosozlik ssenariylarida amaldagi yechim bilan solishtiriladi; Langfuse va xarajat hisobi mos; to‘g‘ridan-to‘g‘ri pullik xizmat umumiy nazoratdan tashqarida qolmaydi.
   5. *Yetkazish* — pin va image digest, auth va tarmoq chegarasi, migration/rollback, servis egasi va per-component litsenziya reyestri tayyor.
4. Provenance tekshiruvisiz butun skill bundle ko‘chirilmaydi; AdClaw’ning umumiy byudjet qoidalari (masalan, "20% at a time" yoki 70/20/10) AMT limitlari o‘rniga ishlatilmaydi.
5. Holat o‘zgarishi WF-E01 orqali, dalil paketi bilan; ishlayotgan biznes qamrovi shu tekshiruv uchun qisqartirilmaydi.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Paperclip va Hermes’ni birga almashtirish | approval/RBAC, audit, task recovery, pul va kill, migratsiya va barcha UAT’larni qayta dalillash kerak; dalil yetarli emas |
| Hostga cheklangan qo‘shimcha worker sifatida darhol qo‘shish | tool, secret va egress izolyatsiyasi, haqiqiy delegation, trace va xarajat isbotlanmagan; ikki orkestratorni saqlash xarajati |
| AdClaw’ni butunlay e’tiborsiz qoldirish | foydali persona, xotira va rubrika materiallari yo‘qotiladi |

## Oqibatlar

- **+** Tayyor g‘oya va materiallardan foyda olinadi; production nazoratlari tayyor deb taxmin qilinmaydi.
- **−** Materiallarni mahalliylashtirish va litsenziya tekshiruvi ishi.
- **−** Kelajakdagi runtime nomzodi uchun alohida dalil paketi va owner qarori kerak.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Upstream o‘zgarishi | yangi release delegation, izolyatsiya yoki pinning cheklovlarini hal qilsa | `vendor_advisory` | beshta mezon bo‘yicha qayta baholash |
| Owner so‘rovi | owner almashtirishni ko‘rib chiqmoqchi | `owner_request` | `restricted_runtime_candidate` dalil paketi (WF-E01) |
| Amaldagi stack muammosi | ADR-001 yoki ADR-004 triggerlari ishga tushsa | `incident_aar` | AdClaw muqobil sifatida baholanadi |

## Kanonik implementatsiya

- [ADCLAW_ASSESSMENT](../10_Reference/ADCLAW_ASSESSMENT.md) — manba tahlili va dalillar.
- [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I01; [ADR-001](ADR-001-paperclip-orchestrator.md), [ADR-004](ADR-004-hermes-cmo-no-openclaw.md); [WF-E01](../09_Config_Templates/workflows/WF-E01.yaml).
