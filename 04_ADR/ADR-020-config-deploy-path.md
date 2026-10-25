# ADR-020 — Runtime config va deploy yo‘li: immutable bundle, owner release va servis ACK

Holat: Accepted · Qaror egasi: owner (Q11, Q12, Q35, Q47 ✅) + builder ★ (H-bo‘lim: Q12 repo va release yo‘li) + builder ◇ P-05 (builder huquqlari) · Sana: 2026-10-22

## Kontekst

- Q11: build fazali va avtonom; ishga tushgandan keyin tizim o‘zini faqat PR + owner tasdig‘i bilan o‘zgartiradi. Q12: spetsifikatsiya markdown’da, keyin kod bilan birga private GitHub repo’da. Q35: `offers.yaml` ni faqat owner o‘zgartiradi. Q47: rollar aniq boshqariladi [D: DECISION_LOG]. ★ H-bo‘lim: `main` ga faqat PR va owner tasdig‘i bilan (ruleset); runtime config `/opt/wolter-amt` ga keladi; kod deploy faqat owner release’i orqali.
- Agentlar `approval-policy.yaml` ni yoza olsa, o‘z limitlarini o‘zlari oshiradi [X].
- Builder sudo’si F6 Step 1 dan oldin olinadi (◇ P-05, [ADR-032](ADR-032-owner-pc-office-host.md)) — deploy yo‘li builder’siz ishlashi kerak.
- Symlink almashishining atomikligi barcha servis yangi policy’ni olganini bildirmaydi; forward-only DB migratsiyasidan keyin eski binary’ni qaytarishning o‘zi yetarli emas [X].
- Workflow va self-evolution (Q50 ✅ qamrov) candidate’larni tizimning o‘zi tayyorlaydi — publisher candidate’dan mustaqil bo‘lishi va tasdiq aniq manifest’ga bog‘lanishi kerak ([ADR-027](ADR-027-release-controller-and-harness-handover.md)).
- Git tag nomining o‘zi qaysi artefakt tekshirilgani va kim tasdiqlaganini isbotlamaydi [X].

## Qaror

1. **Runtime bundle** `/opt/wolter-amt`: egasi `root:root`, hamma o‘qiydi; agent, Paperclip, Hermes va servis UID’lari yoza olmaydi. Manba — `wolter-amt` `main` (read-only deploy key); `main` ruleset bilan himoyalangan: PR va owner review majburiy, bypass yo‘q (HG-F0-05, merge — HG-GIT-01).
2. **Yagona fixed publisher** `amt-release` (root egaligidagi entrypoint, F1 da quriladi): `validate → prepare → activate → ACK`. Config JSON schema va cross-field invariantlar bilan tekshiriladi; noto‘g‘ri bo‘lsa oldingi revision qoladi va alert. Repo ichidagi ixtiyoriy script root sifatida bajarilmaydi.
3. **Kod release:** owner release tasdig‘i — `release_approvals` yozuvi (`/release approve <candidate_id>`, typed code, HG-REL-01; manifest digest, verification ID, verdict, evaluator/policy/role revision va control epoch’ga bog‘langan) **va** owner imzolagan annotated `release-*` tag. Publisher imzoni `/etc/amt/release-signers` bo‘yicha, commit `main` dan reachable ekanini va tag commit manifest commit’iga tengligini tekshiradi. `release-*` va `F*-done` tag’larini faqat owner yaratadi, yangilaydi yoki o‘chiradi; bypass yo‘q. F1 dan boshlab har release `release_approvals` yozuvi va owner imzolagan tag bilan (tag’ning o‘zi yetarli emas); FE_RELEASE gacha yozuvdagi verification maydonlari bo‘sh bo‘lishi mumkin, FE ularni majburiy qiladi.
4. **`build_once_promote`:** artefaktlar sandbox’da bir marta quriladi, digest’lari candidate manifest’da; verification aynan shu digest’larda; publisher aynan ularni chiqaradi. Merge fast-forward yoki rebase bilan, tree-hash tengligi bilan; aks holda yangi manifest va qayta verification.
5. Build, dependency install va test unprivileged `amt-build` da. Engineering credential’lari faqat `cand/*` ga push qiladi; builder tokeni `release-*` tag yarata olmaydi.
6. **Servis ACK:** `write_gate` servislar (gateway, executor, llm-proxy, ops-bot, amt-control, amocrm-mcp, quota-coordinator, amt-workflow) yangi revision’ni ACK qilmaguncha normal write yopiq; `function_gate` servislar (sync-worker, capi-bridge, cost-watchdog, tg-auth) o‘z funksiyasini ushlab turadi (`release-policy.yaml#function_gate_behavior`).
7. **Revision maydonlari:** `code_sha`, `config_sha`, `manifest_digest`, `schema_version`, `min_compatible_code`, `max_compatible_code`, `target_profile`, `capabilities_enabled`, `readiness_snapshot`, `active_ack_at`, `tool_schema_digest` (gateway guard 4 argument sxemalari). `amt-release` va `amt-control` capability o‘z gate’idan o‘tmagan (release’da yoqiladigan capability — release snapshot’i, owner o‘tishi bilan ochiladigan — `control_events`) yoki `operational_validity` bajarilmagan bo‘lsa unga tegishli capability yoki rejimni rad etadi ([ADR-031](ADR-031-readiness-and-decision-authority.md), `readiness.yaml#rules`).
8. **DB rollback:** aniq moslik, forward repair yoki restore; eski va yangi worker parallel yozmaydi.
9. **Rollar** runtime manbai — DB ([ADR-018](ADR-018-rbac-registry.md)); reload runtime DB’ni hech qachon qayta seed qilmaydi. Shoshilinch nazorat bot buyruqlari orqali DB holatini o‘zgartiradi (`/budget raise` → `budget_overrides`, `/role` → `amt.roles`), repo’ga yozmaydi.
10. Agentlar `knowledge/` va `config/` ni faqat o‘qiydi; sirlar u yerda yo‘q; render shablonlari uchun kanonik yo‘l — `knowledge/templates/`.
11. Release sinflari `release-policy.yaml#release_classes`: `normal` — global rejim `killed` bo‘lganda rad etiladi; `recovery` — manifest’da `release_class: recovery` deb e’lon qilingan va faqat containment, reconciliation yoki oldin tekshirilgan release’ni tiklaydigan owner tasdiqlagan release, `killed` da ham ruxsat. Rejalangan release oynasi — `maintenance_hold` ([ADR-030](ADR-030-kill-modes-and-protective-controls.md)).
12. Doira faqat AMT host; landing va Umami — [ADR-012](ADR-012-landing-separate-repo-pr-only.md).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Builder repo working tree’sidan to‘g‘ridan-to‘g‘ri o‘qish | builder yoza oladi; F6 Step 1 dan keyin builder huquqi yo‘q |
| ops-bot `roles.yaml` ga commit qilishi | bot repo yozish huquqini oladi; ruleset bilan ziddiyat |
| Push-based deploy (CI → SSH) | serverga tashqaridan yozish kanali ochiladi |
| Tag nomini yagona release tasdig‘i deb olish | tag manifest va verification’ga bog‘lanmaydi; yozuv va imzo kerak |
| Root publisher repo’dagi deploy script’ini bajarishi | candidate root huquqida ixtiyoriy kod ishga tushiradi |

## Oqibatlar

- **+** Agentlar runtime config yoki policy’ni o‘zgartira olmaydi; o‘zgarish faqat PR → owner merge → owner release yo‘lida.
- **+** Builder huquqisiz ham tizimni yangilash mumkin.
- **−** Config o‘zgarishi release oqimi bilan kechikadi; shoshilinch nazorat bot buyruqlari orqali DB’da bajariladi.
- **−** Rollar ikki joyda turadi (DB va YAML eksport); haqiqat manbai — DB.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Release kechikishi | release kechikishi ish jarayoniga xalaqit bergani haqida owner signali | `owner_request` | tartib himoyalarni kamaytirmasdan soddalashtiriladi |
| Rollback ishlamasligi | deploy xatosidan keyin rollback muvaffaqiyatsiz (≥ 1) | `incident_aar` | UPGRADE runbook va drill yangilanadi |
| ACK’siz faollashish | ≥ 1 audit topilmasi | `regression` | release bloklanadi |
| Auto-release qarori | ⧗ OD-03 hal bo‘lsa (Q11 ni o‘zgartiruvchi owner Q) | `owner_request` | bu ADR va ADR-027 yangilanadi |

## Kanonik implementatsiya

- [release-policy.yaml](../09_Config_Templates/release-policy.yaml); [evolution-policy.yaml](../09_Config_Templates/evolution-policy.yaml) — `promotion`.
- [ARCHITECTURE §7](../03_Architecture/ARCHITECTURE.md), [UPGRADE](../06_Runbooks/UPGRADE.md), [SELF_EVOLUTION §6](../03_Architecture/SELF_EVOLUTION.md).
- [PHASES §4](../05_Build_Phases/PHASES.md) — HG-F0-05, HG-GIT-01, HG-REL-01, HG-F6-06, HG-OPS-02.
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-25, UAT-28; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I13, I19, I21.
