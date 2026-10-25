# ADR-019 — `llm-proxy` va agentlarni izolyatsiya qilish

Holat: Accepted — 1–5-bandlar o‘z kuchida (llm-proxy kanonik joyi ADR-003); 6-band ◇ P-07 / ADR-022 (Proposed) dagi qattiqroq qoida bilan almashtirilgan, owner ko‘rib chiqishi kutilmoqda · Qaror egasi: builder ★ (owner qabul qilgan H-bo‘lim aniqlashtirishlari: Q10/Q44 kaliti faqat llm-proxy’da, Q25 qoldiq riski) · Sana: 2026-10-22

## Kontekst

- Paperclip `claude_local` agentlarni `--dangerously-skip-permissions` bilan va bitta Unix user (`paperclip`) ostida ishga tushiradi [D]; agentlarda shell bor.
- Agent OpenRouter va Langfuse kalitlarini o‘zida ushlasa [X: mustaqil review]: media endpoint’lariga to‘g‘ridan-to‘g‘ri chiqib gateway media budget’i va kill’ni chetlab o‘tadi; o‘z xarajat atributsiyasini soxtalashtiradi; Claude Code va Hermes per-request `provider` siyosatini (Anthropic 1P tartibi, `data_collection: deny`) qo‘ya olmaydi.
- Bitta UID ostidagi agentlar bir-birining tokenini `/proc/<pid>/environ` dan o‘qib, boshqa rol nomidan chaqiruv qilishi mumkin (masalan, `review.submit_verdict` yoki `amo_*_write`) [D]; per-agent token yoki o‘sha UID o‘qiy oladigan run JWT bu holatda izolyatsiya emas.
- **Joriy holat:** bu yozuvning izolyatsiya qarori o‘rniga [ADR-022](ADR-022-isolated-managed-runners.md) amal qiladi — writer/Reviewer process va credential izolyatsiyasi F4_AGENTS profilida majburiy (◇ P-07; bu ★ qoldiq risk qoidasidan qattiqroq, shuning uchun darhol amal qiladi; imkonsiz chiqsa ⧗ OD-05). llm-proxy qarori o‘z kuchida va [ADR-003](ADR-003-openrouter-single-key-watchdog.md) da kanonik.

## Qaror

Yozuvdagi qaror bandlari va ularning joriy holati:

| # | Qaror bandi | Joriy holat |
|---|---|---|
| 1 | `llm-proxy` — deterministik lokal servis (`127.0.0.1:3500`); per-agent proxy token talab qilinadi; proxy bitta OpenRouter kalitini o‘zi qo‘yadi; har so‘rovga provider siyosati (Anthropic 1P ustuvor, `data_collection: deny`) va attributsiya (`user` = agent slug, run va issue ID) majburlanadi; per-agent ulush; kill faol bo‘lsa agent tokenlari rad etiladi; `/images` va `/videos` faqat gateway servis tokeni bilan | o‘z kuchida — ADR-003 |
| 2 | Provider, Langfuse, Meta, amoCRM va Telegram-ops kalitlari faqat trusted servislarda; agent va Hermes muhitida faqat gateway va proxy tokeni | o‘z kuchida; har servis o‘z UID’i va credential fayli bilan ([runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml)) |
| 3 | Majburiy egress filtri (nftables owner-match); agentlarda WebFetch va WebSearch o‘chiq | o‘z kuchida — ADR-022, [SECURITY §3](../03_Architecture/SECURITY.md) |
| 4 | Servislararo chaqiruvlar Unix socket yoki per-caller autentifikatsiya orqali; agent UID’lari trusted guruhlarda emas | o‘z kuchida — ADR-022 |
| 5 | Hermes ovozli xabar uchun faqat proxy STT yo‘lini chaqiradi; yangi API kalit yo‘q | o‘z kuchida — [ADR-004](ADR-004-hermes-cmo-no-openclaw.md) (bitta engine, Q44.3) |
| 6 | Agentlar bitta UID’da ishlaydi; token o‘g‘irlash qoldiq riski qabul qilinadi; kompensatsiya — run konteksti tekshiruvi, anomaliya alertlari va L1 da har oqibatli harakatning inson tasdig‘i | **amal qilmaydi** — ADR-022 (◇ P-07); imkonsizlik holati ⧗ OD-05 |

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Agentlarga to‘g‘ridan-to‘g‘ri OpenRouter kaliti | budget, media va kill chetlab o‘tiladi; atributsiya soxtalashadi |
| Har agentga alohida OpenRouter kaliti | owner bitta kalitni tanlagan (Q44.1) |
| Har agentga alohida Unix user | yozuv Paperclip `claude_local` buni qo‘llamaydi degan taxminga tayangan [T]; bu taxmin managed runner bilan tekshiriladi — ADR-022 |

## Oqibatlar

- **+** OpenRouter kaliti va media endpoint’lari agentlardan yashiringan; atributsiya ishonchli, provider siyosati majburiy, kill LLM qatlamida ham ishlaydi — bular ADR-003 orqali saqlanadi.
- **−** Bitta UID’dagi token o‘g‘irlash riski Reviewer mustaqilligi va izolyatsiyaga tayanuvchi auto yo‘llar bilan mos kelmaydi — shu sabab izolyatsiya bo‘yicha amaldagi qaror ADR-022 da.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Izolyatsiya bo‘yicha owner qarori | owner ◇ P-07 ni rad etsa yoki ⧗ OD-05 da L1 qoldiq riskini qabul qilsa | `owner_request` | izolyatsiya qarori yangi ADR bilan yoziladi; bu yozuv qayta faollashmaydi |

## Kanonik implementatsiya

- llm-proxy: [ADR-003](ADR-003-openrouter-single-key-watchdog.md), [OBSERVABILITY §3](../03_Architecture/OBSERVABILITY.md).
- Izolyatsiya: [ADR-022](ADR-022-isolated-managed-runners.md), [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml), [SECURITY §1–§3](../03_Architecture/SECURITY.md), [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I02.
