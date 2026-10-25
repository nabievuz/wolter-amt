# ADR-017 — Caddy + Cloudflare proxy (Tunnel’siz), origin faqat Cloudflare’ga ochiq

Holat: Superseded → [ADR-033](ADR-033-tunnel-tailscale-omada-access.md)

- 2026-10-22 da Hetzner hostiga kirish Cloudflare Tunnel’siz tanlangan edi: ochiq 443 va 22 portlar, 443 faqat Cloudflare IP’lariga, Origin CA sertifikati va Authenticated Origin Pulls, Hetzner Robot firewall, kalitli SSH va fail2ban.
- AMT host statik IP’siz ofis PC’siga ko‘chgach kiruvchi port ochish imkoni qolmadi.
- 2026-10-23 da owner tashqi kirishni kiruvchi portsiz Cloudflare Tunnel orqali (Q57) va SSH’ni faqat Tailscale orqali (Q58) qilishni tanladi.
- Saqlanib qolgan qismlar — Caddy, `mar2` yo‘l allowlist’i va imzo tekshiruvi, `mar3`, tg-auth — [ADR-033](ADR-033-tunnel-tailscale-omada-access.md).
