# ADR-018 — Rollar reestri (RBAC): ops-bot, tg-auth va Paperclip uchun yagona manba

Holat: Accepted · Qaror egasi: owner (Q31, Q32, Q47, Q49 ✅) + builder ★ (Q47★ rollar, kvorum) + builder ◇ P-10, P-17 + ⧗ OD-04, OD-10, OD-12 · Sana: 2026-10-22

## Kontekst

- Owner talablari: rollar aniq nomlanadi, bitta rolda bir necha odam bo‘lishi mumkin, rol boshqaruviga alohida e’tibor (Q47); yangi kampaniya, offer va landing deploy faqat owner (Q32); targetolog birinchi 4 hafta ikkinchi approver (Q31); UI 2FA Telegram orqali (Q49) [D: DECISION_LOG].
- Rolni uch komponent tekshiradi: ops-bot (tasdiq, buyruq, kontent qabul), tg-auth (UI kirishi), Paperclip (UI foydalanuvchilari).
- Bot repo checkout’ga yozsa, config’ni o‘zgartira oladigan servislar soni oshadi ([ADR-020](ADR-020-config-deploy-path.md)) [X].
- Shaxsni to‘xtatish (suspension) va bitta rol a’zoligining muddati tugashi — turli hodisalar; flag rolsiz qolsa huquq "osilib" qoladi [X].
- Owner yo‘qligida o‘rinbosarga yashirin vakolat berilsa, owner nazoratidan tashqari pul va vakolat paydo bo‘ladi [X].

## Qaror

1. **Rollar** (Q47★): `owner`, `ads_approver`, `sales_lead`, `fleet_operator`, `content_contributor`, `viewer`. Mas’uliyat tayinlovlari (Telegram ruxsati emas; owner o‘zi ham bajarishi mumkin): `technical_operator`, `finance_owner`, `privacy_owner`, `independent_reviewer` (⧗ OD-12).
2. **Runtime manbai** — DB: `amt.people` + `amt.roles`. `roles.yaml` — bir martalik seed va tungi eksport PR; eksport runtime DB’ni qayta seed qilmaydi.
3. Shaxs suspension’i barcha rollarni yopadi; rol muddati faqat o‘sha a’zolikka tegishli. Kamida bitta faol owner bo‘lishi shart — oxirgi faol owner’ni yo‘qotadigan o‘zgarish bloklanadi.
4. **Flag’lar rolga bog‘langan:** effektiv flag’lar = valid a’zoliklarning default flag’lari ∪ muddati o‘tmagan `person_flags`, faqat kamida bitta valid a’zolik bo‘lsa. Flag’lar: `paperclip_ui`, `langfuse_ui`, `dm_alerts`, `hermes_chat`, `golden_copy_rater`, `shadow_rater`, `language_checker`, `ops_responder`, `rights_clearer`.
5. **O‘zgartirish faqat owner:** `/role add|remove|suspend|resume`, `/role flag add|remove <tg_id> <flag> [expires]` va `/role assign|unassign <tg_id> <assignment> [expires]` — typed-code ikki bosqich (`role_change`, NEVER_AUTO; subcommand → op xaritasi `role_change.command_ops`). Har o‘zgarish `roles_audit` va `audit_log` ga yoziladi va mustaqil monitor kanaliga ko‘zgulanadi. `owner` yoki `ads_approver` berishda ikkinchi kanal tasdig‘i — ⧗ OD-10.
6. **Owner vakolati** faqat odamga `owner` RBAC roli berilganda o‘tadi; yashirin delegatsiya yo‘q. O‘rinbosar yoki technical_operator `ops_responder` flag’i bilan ACK, read-only diagnostika va eskalatsiya qiladi; o‘rinbosarning favqulodda kill vakolati ⧗ OD-04 hal bo‘lguncha yo‘q ([ADR-030](ADR-030-kill-modes-and-protective-controls.md)).
7. **Siyosat:** qaysi action’ni qaysi rol tasdiqlashi [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) da; kvorum ★ — rol ichida bitta odamning tasdig‘i yetarli (`change_set.quorum: 1`).
8. Har approval va dispatch’da rol va policy revision qayta tekshiriladi; YAML reload eski rolni qaytarmaydi.
9. **Telegram ko‘rinishi** (◇ P-10): asosiy guruh — owner, ads_approver, viewer; fleet_operator, content_contributor va sales_lead — DM yoki alohida kichik guruh; CMO bilan muloqot faqat DM. Olib tashlash, suspension yoki expiry’da ops-bot shaxsni guruhdan chiqaradi yoki `ALERT_ACCESS_DRIFT` yuboradi.
10. **Seed bosqichlari:** F1 — owner va break-glass (`ops.roles_owner`); F2 — intake roster owner `/role add` bilan (HG-F2-16, `ops.roles_roster`); F3 — qolgan shaxslar (HG-F3-05).
11. **Targetolog:** F5 da `viewer` + `golden_copy_rater`, `shadow_rater`, `language_checker`; F6 Step 1 da `ads_approver` (expiry Step1 + 28 kun); Step1 + 21 kunda HG-F6-05 — uzaytirish, almashtirish yoki tugatish (◇ P-17).
12. `owner` va `ads_approver` uchun Telegram cloud password attestatsiyasi majburiy; usiz onboarding yakunlanmaydi ([ADR-009](ADR-009-telegram-approvals-and-2fa.md)).
13. Paperclip UI foydalanuvchilari effektiv `paperclip_ui` bilan sinxron yuritiladi ([ROLES_ONBOARDING](../06_Runbooks/ROLES_ONBOARDING.md)).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Har komponentda alohida ruxsat ro‘yxati | komponentlar orasida drift xavfi |
| `roles.yaml` ni runtime manba qilish va bot commit qilishi | bot repo yozish huquqini oladi; ruleset bilan ziddiyat (ADR-020) |
| Rollarni faqat Paperclip’da saqlash | Telegram tomoni qamralmaydi |
| Flag’larni shaxsga rolsiz berish | rol tugagach huquq saqlanib qoladi |
| O‘rinbosarga yashirin owner vakolati | owner nazoratisiz pul va vakolat |

## Oqibatlar

- **+** Bitta reestr, hamma joyda bir xil qoida va to‘liq audit; rolni bir joyda olib tashlash hamma joyda kuchga kiradi.
- **−** Paperclip foydalanuvchilarini sinxronlash qo‘lda; Paperclip API imkoniyatiga qarab avtomatlashtiriladi.
- **−** Reestr DB’da — uning kunlik backup’i majburiy; git’dagi `roles.yaml` faqat kechki nusxa.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Jamoa kattalashishi | ★ 10 kishidan oshsa | `amt.people` | rol modeli qayta ko‘riladi |
| Rol bilan bog‘liq insident | ≥ 1 insident | `incident_aar` | ⧗ OD-10 ustuvor; audit va rotatsiya |
| Yangi rol ehtiyoji | owner so‘rovi | `owner_request` | rol va ruxsat matritsasi yangilanadi |
| Access drift | `ALERT_ACCESS_DRIFT` takrorlansa | TELEGRAM alertlari | guruh boshqaruvi tuzatiladi |

## Kanonik implementatsiya

- [RBAC](../03_Architecture/RBAC.md); [roles.yaml](../09_Config_Templates/roles.yaml) — `roles`, `responsibility_assignments`, `flags`, `flag_rules`, `telegram_main_group`, `targetologist_timeline`.
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `role_change`, `change_set.quorum`.
- [ROLES_ONBOARDING](../06_Runbooks/ROLES_ONBOARDING.md), [TELEGRAM §1, §3](../03_Architecture/TELEGRAM.md).
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `ops.roles_owner`, `ops.roles_roster`; [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) UAT-13, UAT-28.
