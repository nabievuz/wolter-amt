# ADR-024 — Workflow runtime: avval capability isboti, keyin mexanizm

Holat: Proposed · Qaror egasi: owner instruction 2026-10-23 (Q50 ✅ scope) + builder ◇ details · Sana: 2026-10-23

- Asos: EVO-R01–R03, EVO-R10, EVO-R15; owner qarorlari Q01, Q11, Q26; invariantlar I16–I18, I22
- Bog‘liq: [ADR-001](ADR-001-paperclip-orchestrator.md), [ADR-007](ADR-007-deterministic-hot-paths.md), [ADR-021](ADR-021-durable-execution-custody.md), [ADR-027](ADR-027-release-controller-and-harness-handover.md)

## Kontekst

Ish birligi — trigger’dan natijagacha kuzatiladigan workflow. U ko‘p kunlik kutish, inson qarori, timer, handoff va tashqi effektli command’larni o‘z ichiga oladi. Paperclip issue/routine’lari agent ishini tashkil qiladi, lekin ularning restart, timer, dedup, lease va epoch semantikasi bizning kontraktimizni kafolatlashi isbotlanmagan [?]. Command ledger (ADR-021) tashqi ijroni durable qiladi, ammo run/step darajasidagi davom ettirish va handoff qabulini qamramaydi. Bitta AMT hostida (owner PC, [ADR-032](ADR-032-owner-pc-office-host.md)) qo‘shimcha murakkab platforma ekspluatatsiya yukini oshiradi [T].

## Qaror

1. Kontrakt mexanizmdan oldin: [WORKFLOW_CONTRACT](../11_Production_Contracts/WORKFLOW_CONTRACT.md) va definition sxemasi majburiy; har workflow schema-valid definition va test bilan.
2. Standart gipoteza: AMT’ning mavjud PostgreSQL `amt` bazasidagi durable workflow jadvallari (`amt-workflow` servisi) — truth; Paperclip — projection va agent vazifa yuzasi ([WORKFLOW_RUNTIME](../03_Architecture/WORKFLOW_RUNTIME.md)).
3. Mexanizm F1’da `workflow.mechanism` readiness’dagi haqiqiy prototip bilan tanlanadi: WF-TEST-RT-CRASH/TIMER/DUPSIG/LATE/HANDOFF/DRIFT/LEASE/EPOCH/LONGWAIT. Paperclip o‘zi shu testlardan o‘tsa, unga ko‘proq tayaniladi; lekin truth baribir tekshiriladigan, command ledger bilan bog‘langan va owner ko‘rinishiga chiqadigan bo‘ladi.
4. Hozir yangi vendor yoki workflow engine tanlanmaydi. Testlar o‘tmasa gate `blocked` qoladi va muqobil C02 retsepti hamda yangi ADR bilan baholanadi.

## Ko‘rib chiqilgan variantlar

| Variant | Holat va sabab |
|---|---|
| Paperclip issue/routine’ni yagona truth qilish | Tanlanmadi: restart/timer/epoch semantikasi isbotlanmagan; issue yopilishi tashqi effekt dalili emas |
| Tashqi durable workflow engine | Hozir tanlanmadi: yangi vendor va ekspluatatsiya yuki; talab capability testsiz yangi engine tanlashni taqiqlaydi. Prototip muvaffaqiyatsiz bo‘lsa C02 bilan qayta ko‘riladi |
| Hermes cron/routine | Tanlanmadi: CMO runtime’i deterministik nazorat manbai bo‘lmaydi (Q26) |
| Har servis o‘z holatini o‘zi yuritishi | Tanlanmadi: end-to-end zanjir, handoff qabuli va owner ko‘rinishi yo‘qoladi |

## Oqibatlar

- Ijobiy: bitta baza va audit zanjiri; command ledger bilan to‘g‘ridan-to‘g‘ri bog‘lanish; owner ko‘rinishi bitta view’dan.
- Salbiy: scheduler, lease va epoch kodi o‘zimizda — xato ehtimoli; capability va fault testlari majburiy.
- Risk: scheduler bitta nuqta; yechim — controller epoch, durable timer va restart testlari; host yo‘qolishi `workflow.recovery` bilan o‘lchanadi.

## Tekshiruv

WF-TEST-RT-CRASH, WF-TEST-RT-TIMER, WF-TEST-RT-DUPSIG, WF-TEST-RT-LATE, WF-TEST-RT-HANDOFF, WF-TEST-RT-DRIFT, WF-TEST-RT-LEASE, WF-TEST-RT-EPOCH, WF-TEST-RT-LONGWAIT (F1), EVO-AT01, EVO-AT02, EVO-AT06, EVO-AT13; har workflow uchun [WORKFLOW_TESTS](../12_Acceptance/WORKFLOW_TESTS.md).
