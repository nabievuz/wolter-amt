# ADR-027 — Release controller, promotion vakolati va harness handover

Holat: Proposed · Qaror egasi: owner instruction 2026-10-23 (Q50 ✅ scope) + builder ◇ details · Sana: 2026-10-23

- Asos: EVO-R09, EVO-R10, EVO-R11, EVO-R15; owner qarorlari Q11, Q12; invariantlar I13, I19, I21, I22
- Bog‘liq: [ADR-020](ADR-020-config-deploy-path.md), [ADR-024](ADR-024-workflow-runtime-capability-first.md), [ADR-026](ADR-026-independent-verification-custody.md)

## Kontekst

Immutable release va service ACK (ADR-020) allaqachon bor. Endi candidate’lar tizimning o‘zi tomonidan tayyorlanadi, shuning uchun publisher candidate’dan mustaqil bo‘lishi, approval exact manifest’ga bog‘lanishi va orkestratsiya kodining o‘zi yangilanganda faol ishlar yo‘qolmasligi kerak. Q11: ishga tushgandan keyin tizim o‘zini faqat PR + owner tasdig‘i bilan o‘zgartiradi.

## Qaror

1. `amt-release` — deterministik release controller; mavjud root publisher’ning tor kengaytmasi. U faqat owner release tag’i bergan, verification `pass` bo‘lgan va approval’i amaldagi rol/policy revision’ida bo‘lgan exact manifest’ni publish qiladi ([SELF_EVOLUTION §6](../03_Architecture/SELF_EVOLUTION.md)).
2. Promotion standart bo‘yicha owner’da. Auto-release `enabled: false`; uni yoqish Q11 ni o‘zgartiruvchi alohida owner qarori, `release.scope_observation` readiness, FE `technically_accepted` va EVO-AT14 PASS’ni talab qiladi. Pul, sir/permission, himoyalangan sirtlar, destructive migration va auto-release siyosati har doim inson gate’ida.
3. Harness/workflow o‘zgarishi WF-E02 bilan: inventar → disposition → owner tasdig‘i → drain → epoch++ → migration → handover → reconciliation → bosqichli kuzatuv. Bir vaqtda bitta faol controller; eski epoch dispatch’i rad.
4. Release controller’ning o‘z yangilanishini amaldagi controller publish qiladi; muvaffaqiyatsizlikda owner uchun hujjatlangan qo‘lda root tiklash yo‘li bor.
5. Rollback schema va workflow-state mosligini tekshiradi; remote effekt DB restore bilan bekor bo‘lmaydi — compensation alohida command.

## Ko‘rib chiqilgan variantlar

| Variant | Holat va sabab |
|---|---|
| PR auto-merge bot | Tanlanmadi: Q11 ga zid |
| Ikki controller parallel ishlashi (blue/green writer) | Tanlanmadi: takroriy dispatch xavfi; faqat drain + epoch handover |
| Har release’da butun tizimni to‘xtatish | Faqat C sinfi uchun drain; boshqa sinflarda ACK bilan atomik activation yetarli |
| Candidate o‘z deploy script’ini olib kelishi | Tanlanmadi: root ixtiyoriy script bajarmaydi |

## Oqibatlar

- Ijobiy: release vakolati candidate’dan mustaqil; handover dalilli.
- Salbiy: C sinfi o‘zgarishi sekinroq (drain oynasi); release controller’ni yangilash maxsus tartib talab qiladi.
- Risk: drain paytida owner yo‘q — tizim drained holatda kutadi (xavfsiz, lekin ish to‘xtaydi); boshlashdan oldin owner mavjudligi tekshiriladi.

## Tekshiruv

EVO-AT03, EVO-AT06, EVO-AT07, EVO-AT08, EVO-AT12; FE-AT handover drill.


## Q65 — first F1 trust initialization (2026-10-25)

The owner authorizes one initial release approval through signed owner SSH before ops-bot is active. `FIRST_RELEASE.md` discloses the sequence; `release-policy.yaml#initial_release` owns its closed guards. A fixed owner-installed importer records the exact signed envelope as durable typed confirmation, release approval and audit in one transaction. The ordinary publisher still requires both this DB approval and the owner-signed release tag; builder, agent and candidate gain no approval or root execution authority.

The initial manifest has `deployment.kind: initial`, F1, null base and no enabled capabilities. Existing current/history/killed state or a consumed bootstrap cannot become another initial install. Failed initial ACK retains no current and reuses only the same pending identities; later updates require active base and normal Telegram approval. `release-policy.yaml#deployment` derives cumulative phase floors, complete deployed service inventory, capability dependencies and exact effective ACKs from the unchanged service/ACK registries. Missing future services do not deadlock F1; installed protective services cannot be omitted. F1-AT-24/H03 verify this protocol before use. Runtime remains NOT_RUN.
