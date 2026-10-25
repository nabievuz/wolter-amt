# ADR-002 — Hetzner EX44 (dedicated), Ubuntu 24.04, production’dan ajratilgan

Holat: Superseded → [ADR-032](ADR-032-owner-pc-office-host.md)

- 2026-10-22 da AMT host sifatida ijaraga olinadigan Hetzner EX44 dedicated serveri (DE yoki FI) tanlangan edi: dasturiy RAID1, Hetzner Storage Box’ga har kecha restic bilan shifrlangan offsite backup va mashqlar uchun alohida DR host.
- O‘shanda Toshkentdagi PC qishki elektr uzilishlari, zaxira qism yo‘qligi va 64 GB RAM narxi sabab rad etilgan edi.
- 2026-10-23 da owner bir xil CPU va RAM’li (i5-13500, 64 GB) o‘z PC’sini sotib oldi va AMT hostini Toshkentdagi ofisga ko‘chirdi (Q52); server ijarasi kerak bo‘lmay qoldi.
- Avvalgi e’tirozlarga javob hamda hali amal qiladigan qismlar (Ubuntu 24.04, faqat AMT, builder huquqlari, resurs slice’lari) — [ADR-032](ADR-032-owner-pc-office-host.md).
