# ADR-025 — Engineering rollari va izolyatsiyalangan sandbox

Holat: Proposed · Qaror egasi: owner instruction 2026-10-23 (Q50 ✅ scope) + builder ◇ details · Sana: 2026-10-23

- Asos: EVO-R05, EVO-R06, EVO-R14; owner qarorlari Q52, Q10/Q33/Q44.1, Q11; invariantlar I20, I25
- Bog‘liq: [ADR-019](ADR-019-llm-proxy-agent-isolation.md), [ADR-022](ADR-022-isolated-managed-runners.md), [ADR-026](ADR-026-independent-verification-custody.md)

## Kontekst

Tizim o‘z yaxshilanishini tayyorlay olishi kerak, lekin muallif o‘zini tekshirmasligi va production’ga bevosita tegmasligi shart. Biznes agentlarining terminal/egress cheklovlari (ADR-019/022) saqlanadi. Runtime AI cap’i (USD 150/oy (15 000 USD minor)) faqat biznes runtime uchun; engineering uchun qo‘shimcha pul borligi taxmin qilinmaydi. Qurilish davridagi builder (Claude Code, Max 20x — Q33 bo‘yicha faqat tizimni qurish uchun) F6 Step 1 dan oldin (HG-F6-06, ◇ P-05) sudo’dan to‘liq chiqariladi [D: F0/F6].

## Qaror

1. To‘rt engineering roli — `eng-planner`, `eng-architect`, `eng-implementer`, `eng-verifier` — alohida UID va credential bilan managed runner orqali; deterministik `amt-release`. Matritsa: [SELF_EVOLUTION §3](../03_Architecture/SELF_EVOLUTION.md).
2. Har proposal attempt’i `amt-sandbox` worktree’sida, `eng-build` UID’da, cgroup `sandbox.slice` limitlari bilan; production secret/DB/Meta/CRM write, root, sudo va Docker socket yo‘q; egress faqat package proxy allowlist.
3. Engineering LLM kirishi `amt-eng-proxy` orqali, runtime `llm-proxy` kalitidan alohida identity va accounting bilan. Variantni owner `engineering.llm_access` va `engineering.budget` da tanlaydi; tanlanmaguncha pullik engineering o‘chiq va sikl qo‘lda (owner/builder) xuddi shu yo‘ldan yuradi.
4. Sandbox standart bo‘yicha AMT hostida, production zaxirasini cgroup bilan saqlagan holda; `capacity.sandbox_host` o‘lchovi yetishmasligini ko‘rsatsa alohida build host — owner pul gate’i.

## Ko‘rib chiqilgan variantlar

| Variant | Holat va sabab |
|---|---|
| Bitta “builder” agent barcha vakolat bilan | Tanlanmadi: muallif o‘zini tasdiqlaydi (EVO-R05 buziladi) |
| Engineering ishini biznes agentlariga berish | Tanlanmadi: vakolat kengayadi, terminal/egress cheklovlari buziladi |
| Docker socket bilan konteyner build | Tanlanmadi: socket amalda root vakolati |
| Hosted CI runner’ida build/verification | Hozir tanlanmadi: holdout custody va egress nazorati boshqacha, qo‘shimcha xarajat; capability test va owner qarori bilan keyin ko‘rilishi mumkin |
| Runtime OpenRouter kalitini engineering uchun ishlatish | Tanlanmadi: runtime secret custody va 15 000 USD minor cap buziladi |

## Oqibatlar

- Ijobiy: vazifalar ajratilishi tekshiriladigan; production resurs va pul hisobi himoyalangan.
- Salbiy: qo‘shimcha UID, slice va proxy; ekspluatatsiya ishi ko‘payadi.
- Risk: bitta hostda build yuklamasi — cgroup va pauza/navbat bilan; obuna limitlari yoki shartlari engineering’ni to‘xtatishi mumkin [?] — owner qarori va manual yo‘l bilan qoplanadi.

## Tekshiruv

FE-AT salbiy ruxsat testlari, EVO-AT04, EVO-AT05; `capacity.sandbox_host` o‘lchov dalili.
