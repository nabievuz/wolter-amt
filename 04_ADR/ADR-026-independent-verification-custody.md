# ADR-026 — Mustaqil verification va evaluator custody

Holat: Proposed · Qaror egasi: owner instruction 2026-10-23 (Q50 ✅ scope) + builder ◇ details · Sana: 2026-10-23

- Asos: EVO-R07, EVO-R08, EVO-R11; invariantlar I19, I20
- Bog‘liq: [ADR-016](ADR-016-model-selection-by-eval.md), [ADR-025](ADR-025-engineering-roles-and-sandbox.md), [ADR-027](ADR-027-release-controller-and-harness-handover.md)

## Kontekst

Agent yozgan candidate o‘z testini yozishi yoki o‘zgartirishi mumkin. Agar authoritative mezon candidate bilan birga o‘zgarsa, PASS hech narsani isbotlamaydi. Model/prompt/skill o‘zgarishida yashirin regression faqat muallif ko‘rmagan holdout bilan topiladi.

## Qaror

1. Authoritative suite — **joriy release’dagi** `evals/protected/**`; candidate branch’idagi testlar faqat qo‘shimcha, authoritative emas.
2. Holdout `/var/lib/amt-verify/holdout` da shifrlangan; kalit faqat `amt-verify` UID’da; muallif rollari va builder o‘qiy olmaydi. Custody `verification.custody` readiness’da owner va mustaqil tekshiruvchi bilan tasdiqlanadi.
3. Natija exact manifest digest, suite digest, holdout digest va evaluator revision’iga bog‘lanadi ([verification-result](../09_Config_Templates/schemas/verification-result.schema.json)). Himoyalangan yo‘l diff’i, test sonining kamayishi yoki chegara pasayishi `criteria_changes_detected` → verdict `fail`.
4. Mezonni o‘zgartirish faqat E sinfi proposal: amaldagi (eski) suite bilan tekshiruv, mustaqil inson review va owner typed tasdig‘i.
5. `eng-verifier` hisobot yozadi, verdict’ni o‘zgartirmaydi; owner release qarori verification’ning o‘rnini bosmaydi.

## Ko‘rib chiqilgan variantlar

| Variant | Holat va sabab |
|---|---|
| Candidate testlari authoritative | Tanlanmadi: muallif mezonni yumshatadi |
| Faqat inson review | Tanlanmadi: takrorlanmaydi, regressionni ishonchli tutmaydi; inson review E sinfida qo‘shimcha gate sifatida qoladi |
| Holdout’ni repo’da saqlash | Tanlanmadi: muallif o‘qiy oladi |

## Oqibatlar

- Ijobiy: PASS exact artifact’ga tegishli va qayta tekshiriladi.
- Salbiy: holdout’ni yangilab turish va custody ishi; himoyalangan suite o‘zgarishi sekinroq.
- Risk: holdout eskirishi — `review_by` va WF-E04 orqali boshqariladi; holdout sizishi — kalit rotatsiyasi va yangi holdout.

## Tekshiruv

EVO-AT03, EVO-AT08, EVO-AT11; FE salbiy testlari (holdout o‘qish urinishi rad).
