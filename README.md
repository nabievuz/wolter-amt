# Wolter AMT — Project OS

**Real ishlab turgan Wolter biznesi uchun to‘liq AI Marketing Team qurilish spetsifikatsiyasi.** Biznes natijasi, ma’lumotni ishonchli yetkazish, xavfsiz tashqi ijro, kundalik xizmat va inson boshqaradigan self-evolution yagona kontraktga birlashtirilgan. Bu paket server, kod yoki go-live bajarilganini anglatmaydi.

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-25 · Vaqt zonasi: Asia/Tashkent · Egasi: owner.

## Asosiy qarorlar

| Soha | Tanlov | Manba |
|---|---|---|
| Biznes | Wolter, B2C kuryerlar; sotuv va ijara alohida | Q01, Q05 ✅ |
| Kanal | Faqat pullik Meta Ads; organik SMM, DM va sotuvchilarga vazifa yo‘q | Q06→Q14, Q18 ✅ |
| Agentlar | CMO (Hermes), Media Buyer, Creative Studio, CRO, Funnel Analyst, mustaqil Reviewer | Q03, Q15 ✅ |
| Natija | North Star — amoCRM’dagi qualified lead; lead→shartnoma guardrail | Q04, Q16 ✅ |
| Ijara | Fizik park va amaldagi waitlist; tranzaksiya/oy boshqa birlik | Q43 ✅ |
| AI/media cap | USD 150/oy (15 000 USD minor); bitta OpenRouter kaliti faqat llm-proxy’da | Q10 ✅ |
| Reklama cap | USD 1 500/oy (150 000 USD minor); Ads Manager spending limit majburiy, AI’dan mustaqil | Q08, Q37 ✅ |
| Tasdiq | Kunlik 10:00 change set, TTL 12 soat, avto-tasdiq yo‘q; Trust Ramp L0/L1/L2 | Q32, Q38 ✅ |
| Go-live | 7 kun shadow → ijara L1 14 kun → dalil bilan to‘liq takeover; kill criteria | Q31, Q36 ✅ |
| Landing | Alohida repo va production Dokploy; AMT PR ochadi, owner merge va deploy qiladi | Q19, Q46.4 ✅ |
| Workflow | Durable workflow runtime: checkpoint, handoff qabul/rad, uchdan-uchgacha dalil zanjiri | Q50 ✅ |
| Self-evolution | Sandbox → mustaqil verification → owner release (exact manifest) → kuzatuv → verdict; auto-release o‘chiq | Q11, Q50 ✅, ⧗ OD-03 |
| Server va backup | Owner’ning ofis PC’si: RAID1, disk shifrlanmaydi, UPS; backup — faqat shu PC’dagi lokal snapshot, ikkala disk yo‘qolishi qabul qilingan xavf ([ADR-032](04_ADR/ADR-032-owner-pc-office-host.md)) | Q52–Q56 ✅ |
| Kirish | Tashqi kirish faqat Cloudflare Tunnel orqali, kiruvchi port yo‘q; SSH faqat Tailscale; PC ofis tarmog‘idan Omada VLAN/ACL bilan ajratilgan ([ADR-033](04_ADR/ADR-033-tunnel-tailscale-omada-access.md)) | Q57–Q60 ✅ |
| Reviewer oldi tekshiruvi | Jev — verdiktni faqat qattiqlashtiradigan deterministik pre-screen; F5 eval’dan o‘tsagina yoqiladi ([ADR-034](04_ADR/ADR-034-jev-review-pre-screen.md)) | Q61 ✅ |
| Favqulodda holat | Lokal kill birinchi; protective controls; resume ko‘pi bilan L1; restore `killed` bilan | ✅ Q37; ◇ P-03, P-21, P-16 |

MVP qurilmaydi (Q48 ✅). Bosqichli rollout — to‘liq tizimni ishlayotgan biznesga nazorat bilan kiritish usuli. Haqiqiy qiymati noma’lum parametrlar `readiness.yaml` da mas’ul inson, dalil va gate bilan ochiq turadi; soxta offer, ID yoki biznes ko‘rsatkichi kiritilmagan.

## Egasi uchun o‘qish tartibi

1. [Qarorlar](00_Decisions/DECISION_LOG.md) — owner qarorlari, ustuvorlik va kutilayotgan takliflar (◇).
2. [Ochiq savollar](00_Decisions/OPEN_ITEMS.md) — owner qarori kerak bo‘lgan ⧗ bandlar, readiness va ziddiyatlar.
3. [PRD](01_PRD/PRD.md) — biznes qamrovi va muvaffaqiyat mezoni.
4. [Biznes kontrakti](11_Production_Contracts/BUSINESS_CONTRACT.md) — qualified, pul, park, attribution va inson javobgarligi.
5. [Qurilish fazalari](05_Build_Phases/PHASES.md) — engineering, real trafik va takeover gate’lari.
6. [Qabul mezonlari](12_Acceptance/PRODUCTION_ACCEPTANCE.md) — production kafolatlari qanday isbotlanadi.

## Builder uchun kirish

[CLAUDE.md](CLAUDE.md) va birinchi sessiyada [SERVER_ADOPTION](05_Build_Phases/SERVER_ADOPTION.md) ni o‘qing. Mavjud ofis PC’sida avval read-only preflight va `adopt_existing`: o‘rnatilgan Ubuntu/Claude, ma’lumotlar, login va toraytirilgan huquqlar saqlanadi; bajarilmagan gate’lar uydirib yopilmaydi. Qabul qilingan sessiyada `project_os_root=/srv/builder/wolter-amt/project-os` ichidan joriy fazaning context pack’ini yarating va o‘qing (`python3 12_Acceptance/validate_bundle.py --context-pack F<n>`; ta’rifi [CONTEXT_PACKS.yaml](05_Build_Phases/CONTEXT_PACKS.yaml)). [Qarorlar](00_Decisions/DECISION_LOG.md), [atamalar](CONTEXT.md), [invariantlar](11_Production_Contracts/INVARIANTS.md) va boshqa kanonik hujjatlarni faqat pack yoki vazifa ko‘rsatgan bo‘limda oching — ularning hammasi birgalikda kontekst oynasiga sig‘maydi. Qamrovni kamaytirish yoki bajarilmagan gate’ni stub bilan yopish qurilish natijasi hisoblanmaydi.

Serverdagi papka ichida Claude Code’ga beriladigan birinchi vazifa:

> `CLAUDE.md` ni o‘qi. Mavjud ofis PC’sidagi o‘rnatilgan Ubuntu va Claude Code’ni saqlab, `SERVER_ADOPTION.md` bo‘yicha read-only preflight’dan boshla. Haqiqiy holatni hujjat bilan solishtir, keyin F0’dan to‘liq loyihani fazalar bo‘yicha qur. Owner tasdig‘i yoki ma’lumoti kerak bo‘lsa tayyor dalil va aniq amal bilan HUMAN_GATE och, savollarni birma-bir ber; mustaqil bajariladigan ishni davom ettir. Bajarilmagan gate yoki testni PASS deb belgilama.

Bu papka HG-F0-05 bo‘yicha `wolter-amt/project-os/` ichiga joylashtiriladi. `build/` dalillari shu `project_os_root`ga, ilova kodi va `infra/` esa monorepo `repo_root`iga tegishli. Owner SSH sessiyasidan builder’ga `sudo -iu builder` bilan o‘tiladi. Ilk platforma release’i [FIRST_RELEASE](05_Build_Phases/FIRST_RELEASE.md) bo‘yicha Q65 bir martalik SSH tasdig‘idan, keyingilari Telegram tasdig‘idan o‘tadi. `09_Config_Templates` dan runtime `config/` yaratiladi va haqiqiy qiymatlar hamda dalil bilan to‘ldiriladi. Runtime root egaligidagi immutable release’dan o‘qiydi, builder working tree’dan emas. Repo yaratish, pul, secret/OAuth, DNS va go-live ishlari tegishli HUMAN_GATE’da qoladi.

## Paket tuzilishi

- `00_Decisions` — qarorlar, ochiq savollar va premortem.
- `01_PRD`, `02_Team_Charter` — mahsulot, jamoa, olti biznes agenti va alohida engineering rollari.
- `03_Architecture`, `04_ADR` — komponentlar, data, ijro, xavfsizlik, workflow runtime, self-evolution va tanlov sabablari.
- `05_Build_Phases` — F0–F7 va parallel FE (evolution) fazasi; HUMAN_GATE reyestri.
- `06_Runbooks` — incident, kill, restore, release, run’larni tiklash, evolution sikli, kundalik xizmat va odamlar.
- `07_Evals`, `08_Skills` — model/skill/tool sifat va xavfsizlik tekshiruvi.
- `09_Config_Templates` — typed konfiguratsiya shablonlari, readiness reyestri, 17 workflow ta’rifi va JSON sxemalar.
- `10_Reference` — atamalar, tekshiriladigan vendor faktlari, AdClaw bahosi va fikrlash kutubxonasi.
- `11_Production_Contracts` — invariantlar, biznes, konfiguratsiya, operatsion konvert, workflow va evolution kontraktlari.
- `12_Acceptance` — production ssenariylari, workflow testlari, talab→test xaritasi, paket validatori va tekshiruv natijasi.

## Qabul holati

Hujjatlar spetsifikatsiya sifatida yozilgan. Runtime gate’lar, real biznes parametrlarining tasdig‘i va production acceptance tegishli build dalilini talab qiladi. [Paket tekshiruvi](12_Acceptance/VALIDATION_REPORT.md) faqat spetsifikatsiya va shablonlar yaxlitligi haqida; live tizim tayyorligi haqida emas.
