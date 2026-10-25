# ADR-009 — Telegram: tasdiqlash kanali va 2FA (tg-auth)

Holat: Accepted · Qaror egasi: owner (Q08, Q32, Q38, Q47, Q49 ✅) + builder ★ (Q49★ sessiya va break-glass standartlari) + ⧗ OD-10 · Sana: 2026-10-22

## Kontekst

- Owner tasdiqlarni Telegram orqali berishni (Q47) va 2FA’ni ham Telegram orqali qilishni (Q49) tanlagan; avtomatik tasdiq hech qachon yo‘q, 12 soatda javob bo‘lmasa harakat bekor (Q32); kunlik change set 10:00 (Q38) [D: DECISION_LOG].
- Paperclip’da o‘z 2FA’si yo‘q [D: commit `043f2514` (2026-10-21) manbasida TOTP yoki 2FA kodi topilmadi].
- Telegram Bot API faktlari [D: core.telegram.org · qayta tekshiriladi]: inline keyboard’dan `callback_query` keladi; `callback_data` ≤ 64 bayt [?]; guruhga daqiqasiga ~20 xabar; hosted API orqali yuklab olish ≤ 20 MB, lokal `telegram-bot-api --local` serverida limit yo‘q.
- Telegram akkaunti egallab olinsa hujumchi ikkinchi faktorni ham oladi — bu WebAuthn yoki TOTP’dan zaifroq [X]. Shu sessiyada keladigan tasdiq kodi alohida faktor emas [X].

## Qaror

1. **Ops bot** (`ops-bot`, `amt-ops` UID, deterministik; buyruq va UX bo‘yicha yagona spec — [TELEGRAM](../03_Architecture/TELEGRAM.md)): lokal Bot API server orqali (HG-F1-05), webhook localhost’ga; kunlik change set `operations.yaml#schedule` dagi 10:00 da, har band uchun inline ✅/❌/✏️; urgent bandlar darhol; TTL 12 soat `presented_at` dan; avtomatik tasdiq hech qachon yo‘q.
2. Har callback’da nonce, item revision, actor, joriy rol/a’zolik va expiry deterministik tekshiriladi; takroriy callback rad etiladi.
3. Owner-critical buyruqlar (`/pause_all`, `/resume`, `/role`, `/budget raise`, `/mode`, `/takeover`, `/graduate`, `/agent resume`, `/asset clear|revoke`, `/release approve`, `/proposal approve`) — ikki bosqich: tugma + 2 daqiqa ichida `TASDIQ <4 xonali kod>`. Typed code — qasddan bajarilgan amal tasdig‘i, ikkinchi autentifikatsiya faktori emas; identity Telegram akkaunti, cloud password attestatsiyasi va tg-auth’ga tayanadi.
4. **tg-auth** (Caddy `forward_auth`) `mar.wolter.uz` va `mar3.wolter.uz` uchun: Paperclip yoki Langfuse paroli + Telegram’da ✅ (xabarda IP, qurilma va vaqt). Kirish faqat effektiv `paperclip_ui` yoki `langfuse_ui` flag’iga ega faol shaxslarga ([ADR-018](ADR-018-rbac-registry.md)).
5. ★ Standartlar: tasdiq kutish 2 daqiqa; sessiya 12 soat (`SameSite=Lax`); yangi qurilma yoki IP → qayta tasdiq; 10 daqiqada ≤ 3 so‘rov; `owner` va `ads_approver` Telegram cloud password’ni yoqishi shart — `cloud_password_attested_at` bo‘lmasa approval tugmalari va tg-auth rad etiladi; owner uchun 10 ta oflayn, bir martalik break-glass kod (doirasi `paperclip_ui`).
6. Har bosish va har kirish `audit_log` ga yoziladi; har `role_change` mustaqil monitor kanaliga ko‘zgulanadi. `owner` yoki `ads_approver` roli berilganda ikkinchi kanal tasdig‘i — ⧗ OD-10.
7. Tasdiq **hech qachon** Hermes yoki boshqa LLM orqali o‘tmaydi ([ADR-004](ADR-004-hermes-cmo-no-openclaw.md)).
8. Telegram ishlamasa: owner Tailscale orqali SSH bilan `amt-kill` ([ADR-030](ADR-030-kill-modes-and-protective-controls.md), [ADR-033](ADR-033-tunnel-tailscale-omada-access.md)); host’dan mustaqil signal; break-glass sessiyasi eski approval’ni qayta kuchga kiritmaydi.
9. Callback ma’lumoti qisqa ID ko‘rinishida (64 bayt cheklovi pinned API’da tekshiriladi).

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Authelia (TOTP/WebAuthn) | owner Telegram’ni tanlagan (Q49) |
| Cloudflare Access | ishlatilmaydi: Cloudflare faqat Tunnel va HTTPS proxy (Q57), 2FA — Telegram (Q49); SSH Tailscale orqali (Q58) |
| Typed code’ni ikkinchi faktor deb hisoblash | kod o‘sha Telegram sessiyasiga keladi; u faqat qasddan amal tasdig‘i |
| Hosted Bot API webhook (`mar2/tg`) | lokal Bot API bilan bir vaqtda ishlamaydi; `mar2` faqat amoCRM va Meta webhook’lari uchun |
| Hermes orqali tasdiq | injection xavfi (Q47) |

## Oqibatlar

- **+** Tasdiq va 2FA owner allaqachon ishlatadigan kanalda; qo‘shimcha ilova kerak emas; ikkalasi uchun bitta rol reestri.
- **−** Telegram akkaunti egallanishi asosiy xavf. Kompensatsiya: cloud password, kiruvchi port yo‘q va kirish faqat Cloudflare Tunnel orqali ([ADR-033](ADR-033-tunnel-tailscale-omada-access.md)), sessiya TTL, audit va `role_change` ning off-host ko‘zgusi.
- **−** Telegram ishlamasa kirish to‘xtaydi — break-glass kodlar va SSH kill yo‘li bilan qoplanadi.

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Paperclip native 2FA | stable versiyada 2FA paydo bo‘lsa | `vendor_advisory` | native 2FA yoqiladi; tg-auth qo‘shimcha qatlam sifatida qoladi |
| Telegram akkaunti insidenti | ≥ 1 insident | `incident_aar` | ⧗ OD-10 owner’ga ustuvor; sessiya va token rotatsiyasi |
| Telegram kanali ishlamay qolishi | 1 kundan ortiq yoki takroriy uzilish | off-host monitor | muqobil kanal ADR’i — owner qarori |

## Kanonik implementatsiya

- [TELEGRAM](../03_Architecture/TELEGRAM.md) — change set, buyruqlar, alert katalogi (§6), tg-auth (§7).
- [RBAC §3–§4](../03_Architecture/RBAC.md); [roles.yaml](../09_Config_Templates/roles.yaml) — `people_seed_schema.cloud_password_attested_at`, `flags`.
- [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `change_set`, `two_step.typed_code`, `role_change`.
- [PHASES §4](../05_Build_Phases/PHASES.md) — HG-F1-02, HG-F1-04, HG-F1-05, HG-F1-06; [SECURITY §6](../03_Architecture/SECURITY.md).
- [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) — UAT-13, UAT-29.
