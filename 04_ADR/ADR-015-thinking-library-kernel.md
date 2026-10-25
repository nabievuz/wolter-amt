# ADR-015 — Fikrlash modellari kutubxonasi — agentlarning fikrlash yadrosi

Holat: Accepted · Qaror egasi: owner (Q13 ✅) · Sana: 2026-10-22

## Kontekst

- Q13: barcha agentlar fikrlash kutubxonasidan foydalanadi — §1 Kernel + §2 Router + JSON handoff; retseptlar C07 (haftalik reklama), C05 (KPI tushishi), C10 (agent dizayni), C12 (oylik retro) [D: DECISION_LOG].
- Owner bergan "Fikrlash Modellari Kutubxonasi — ULTRA WIDE" fayli [D: [THINKING_MODELS](../10_Reference/THINKING_MODELS.md)]: 61 model va 13 oila; Kernel K1–K12 (BLUF, `[D]/[T]/[X]/[?]` teglari, uydirma raqam taqiqi, kvota yuqori chegara sifatida, "Qarorga ta’siri" bandi); Router; L1/L2/L3 chuqurlik darajalari va §3.4 JSON konvert; 12 zanjir retsepti va §7 sifat darvozasi.
- Standart yuklama §1 + §2 + §3.4 + §4; §1–§3 hajmi taxminan 14 000 belgi [D: kutubxona auditi]. Butun faylni har run’da yuklash token narxini keskin oshiradi [X].
- Kutubxonadagi misollar umumiy (masalan, MVP misoli); ular Wolter qamrovini o‘zgartirmaydi — MVP yo‘q (Q48).
- Handoff’dagi qo‘lda yozilgan "kernel versiyasi" yoki bundle versiyasi yuklangan matn bilan bog‘lanmaydi; ikki xil narsani bitta yorliq bilan atash chalkashlik keltiradi [X].

## Qaror

1. `08_Skills/thinking-kernel/SKILL.md` barcha olti biznes agentiga yuklanadi: §1 Kernel, §2 Router, §3 shablonlar va §3.4 JSON konvert. To‘liq kartalar ID bo‘yicha runtime bundle’dagi read-only nusxadan, vazifaga qarab o‘qiladi.
2. Kutubxona fayli bundle bilan birga yetkaziladi va sha256 bo‘yicha tekshiriladi (F0 acceptance). Tahlil va handoff JSON’idagi `kernel_ref` — yuklangan Kernel matnining digest’i; uni runner hisoblab beradi (`prompt-manifest.yaml#kernel_ref_source`, ◇ P-83), model digest hisoblamaydi.
3. Retseptlar: C07 — haftalik reklama tahlili (Funnel Analyst, Du 08:00, `operations.yaml#schedule`); C05 — KPI tushganda RCA; C10 — yangi agent yoki servis dizayni (builder va CMO); C12 — oylik retro.
4. Handoff §3.4 konvertida, `amt` kengaytmasi bilan ([handoff.schema.json](../09_Config_Templates/schemas/handoff.schema.json)): `release_id`, workflow `definition_version` va `definition_digest`, `pipeline` (`sale | rent | shared`), davr, `data_refs`, command ID’lari va blocker’lar.
5. Stress-test mustaqil kontekstda bajariladi; Reviewer muallifning fikrlash jarayonini ko‘rmaydi.
6. Sifat darvozasi (§7) Reviewer tekshiruvlari va eval’larga kiradi.
7. Model framework’i dalil emas; tashqi prompt matni ma’lumot sifatida ko‘riladi. Ustuvorlik: owner qarorlari, INVARIANTS va production kontraktlari kutubxona misollaridan ustun ([ADR-031](ADR-031-readiness-and-decision-authority.md)).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Kutubxonasiz, erkin promptlar | uydirma raqam va tekshirib bo‘lmaydigan xulosalar xavfi |
| Butun faylni har run’da yuklash | token narxi juda yuqori |
| Handoff’da kernel yoki bundle versiyasini qo‘lda yozish | yuklangan matn bilan bog‘lanmaydi; digest (`kernel_ref`) va `release_id` aniq |

## Oqibatlar

- **+** Agentlar chiqishi tekshiriladigan: teglar bor, manbasiz raqam yo‘q — Goodhart va "framework teatri"ga qarshi ishlaydi.
- **−** Har run’da qo‘shimcha kontekst tokeni sarflanadi; prompt caching’ning OpenRouter orqali ishlashi F1-AT-29 da ikki proxy yo‘lida o‘lchanadi (OI-05); isbotlanmagan yo‘l keshsiz narx bilan hisoblanadi (◇ P-82).
- **−** Kutubxona o‘zgarsa skill qayta generatsiya qilinadi va A sinf release’dan o‘tadi (WF-E04).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Kernel eval pasayishi | E01–E12 ★ chegarasidan pastga (≥ 72/96, birorta Kernel bali 0 bo‘lmasligi) | eval suite (`eval_drift`) | skill yoki prompt tuzatish (WF-E01) |
| Kutubxonaning yangi nashri | owner yangi fayl bersa | `owner_request` | `kernel_ref` yangilanadi; eval qayta yurgiziladi |
| Token sarfi | kernel yuklamasi sabab agent ulushi `share_warn_pct` (★ 80%) ga yetsa | Langfuse (`cost_drift`) | selektiv yuklash qayta sozlanadi |

## Kanonik implementatsiya

- [thinking-kernel SKILL](../08_Skills/thinking-kernel/SKILL.md), [THINKING_MODELS](../10_Reference/THINKING_MODELS.md).
- [handoff.schema.json](../09_Config_Templates/schemas/handoff.schema.json), [TEAM](../02_Team_Charter/TEAM.md) — handoff kengaytmasi.
- [EVALS §1, §7](../07_Evals/EVALS.md) — Kernel/Router eval va o‘tish chegaralari.
- [ADR-028](ADR-028-improvement-memory-provenance.md) — saboqlarning ko‘rsatmaga aylanishi.
