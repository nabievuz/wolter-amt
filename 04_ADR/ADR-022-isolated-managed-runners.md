# ADR-022 — Rol bo‘yicha managed runner chegarasi

Holat: Proposed · Qaror egasi: builder ◇ P-07 + ⧗ OD-05 · Sana: 2026-10-23

## Kontekst

- Q25 ✅: agentlar va tool’lar orasida guardrail-gateway va per-agent allowlist. ★ H-bo‘lim aniqlashtirishi agentlar bitta UID’da ishlashini qoldiq risk sifatida qabul qilgan va izolyatsiyani faqat L2 uchun shart qilgan ([ADR-019](ADR-019-llm-proxy-agent-isolation.md)).
- Paperclip agentlarni skip-permissions bilan ishga tushiradi [D]; bitta UID’dagi processlar bir-birining `/proc`, environment, FD va socket’lariga yetadi — prompt, per-agent token yoki o‘sha UID o‘qiy oladigan run JWT fayllarni himoya qilmaydi [X].
- Writer va Reviewer bitta UID’da bo‘lsa, writer Reviewer verdict’ini soxtalashtirishi mumkin — Q03/Q42 dagi mustaqil Reviewer kafolati buziladi [X].
- ◇ P-07 izolyatsiyani F4_AGENTS gate’iga ko‘taradi. Bu ★ qoidadan qattiqroq, shuning uchun owner ko‘rib chiqquncha ham amal qiladi.
- Paperclip/Hermes adapterlari per-role UID’ni native qo‘llashi taxmin qilinmaydi [?]; "qo‘llamaydi" degan taxmin bilan yangi texnologiya ham majburlanmaydi — avval capability prototipi.

## Qaror

1. **UID’lar ajratiladi:** orkestrator `paperclip`; CMO `hermes`; Media Buyer, Creative Studio, CRO, Funnel Analyst va Reviewer — `agent-<slug>`; engineering rollari `agent-eng-*` (faqat sandbox vakolati); har trusted servis o‘z UID’ida ([runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) `agents`, `engineering_roles`, `services`).
2. **Managed runner:** root egaligidagi fixed entrypoint faqat oldindan belgilangan rol → unit/entrypoint mapping’ini ishga tushiradi; caller UID, executable, buyruq, environment, path, working directory yoki credential faylni tanlay olmaydi (`runner_contract`). Paperclip’ga root yoki sudo berilmaydi.
3. Qisqa muddatli run credential’lari aniq audience va immutable rol mapping’iga bog‘lanadi; bir UID’dagi token yoki JWT izolyatsiya hisoblanmaydi (`same_uid_tokens_count_as_isolation: false`).
4. **Egress:** agent UID’lari faqat autentifikatsiyalangan gateway va llm-proxy’ga chiqadi; CMO uchun faqat bot transporti (`cmo_telegram_transport`); WebFetch va WebSearch o‘chiq; IPv4/IPv6, loopback, Unix socket, proxy va DNS bypass salbiy testlari ([SECURITY §3](../03_Architecture/SECURITY.md)). Engineering egress — default-deny namespace, faqat package proxy.
5. Servislararo chaqiruvlar Unix socket peer-UID allowlist yoki per-caller autentifikatsiya bilan; agent UID’lari trusted guruhlarda emas; renderer va uchinchi tomon MCP child jarayonlari gateway UID’ini meros qilib olmaydi.
6. **Gate (◇ P-07):** F1 da prototip — `vendor.runner_isolation` (F1_ISOLATION, F1-AT-21); F4 da olti rolning barchasi alohida UID/token bilan ishlaydi va cross-role salbiy testlari PASS — `vendor.runner_isolation_final` (F4_AGENTS). L2 graduation har holatda izolyatsiya dalilini talab qiladi (`requires_identity_isolation_evidence: true`).
7. **Integratsiya o‘tmasa** huquqlar birlashtirilmaydi va yangi erkin root launcher qo‘shilmaydi; owner qarori ⧗ OD-05 ([OPEN_ITEMS](../00_Decisions/OPEN_ITEMS.md) bilan bir xil harflar): (a) custom runner qurish (vaqt/pul) → `vendor.runner_isolation_final = all_roles_isolated`; (b) L1’da bir UID qoldiq riskini qabul qilish, L2 har doim bloklangan → `vendor.runner_isolation_final = residual_risk_l1_l2_blocked` (owner imzosi bilan; risk qaysi yo‘llarga taalluqli ekani owner reyestrida). Qaror va qiymat bo‘lguncha F4_AGENTS yopiq.
8. Paperclip gateway bridge per-agent `allowed_ops`/`denied_ops` bilan; F4 da har rol uchun salbiy test.

## Ko‘rib chiqilgan variantlar

| Variant | Nega tanlanmadi |
|---|---|
| Bitta UID + per-agent token (★ qoldiq risk qoidasi) | Reviewer mustaqilligi va credential custody isbotlanmaydi; faqat ⧗ OD-05 dagi owner qarori bilan qaytishi mumkin |
| Paperclip’ga root yoki sudo berish | orkestrator buzilsa butun host buziladi |
| Har agent uchun erkin container/VM launcher yozish | yangi root hujum yuzasi; capability testsiz yangi texnologiya |
| Docker socket orqali izolyatsiya | socket amalda root vakolati |
| Run JWT’ni yagona chegara qilish | o‘sha UID JWT’ni ham o‘qiy oladi |

## Oqibatlar

- **+** Rol vakolati process va credential darajasida ajraladi; Reviewer verdict’ini soxtalashtirib bo‘lmaydi.
- **−** Qo‘shimcha UID, unit, runner va deploy ishi; adapter integratsiyasi F1/F4 da riskli [?].
- **−** Izolyatsiya imkonsiz chiqsa F4 gate’i owner qarorini kutadi (⧗ OD-05).

## Qayta ko‘rish triggeri

| Trigger | Metrika va chegara | Manba | Harakat |
|---|---|---|---|
| Prototip natijasi | `vendor.runner_isolation` evidence fail | F1 capability testi | ⧗ OD-05 owner’ga |
| Native sandbox | Paperclip per-agent OS user yoki sandbox’ni rasman qo‘llasa | `vendor_advisory` (WF-E03) | managed runner soddalashtiriladi |
| Cross-role kirish | ≥ 1 urinish (audit yoki salbiy test) | `incident_aar` | INCIDENTS; release bloklanadi |
| Owner qarori | P-07 qabul yoki rad, OD-05 qarori | `owner_request` | Holat yangilanadi |

## Kanonik implementatsiya

- [runtime-isolation.yaml](../09_Config_Templates/runtime-isolation.yaml) — `runner_contract`, `paperclip_bridge`, `agent_egress`, `engineering_egress`.
- [SECURITY §1–§3](../03_Architecture/SECURITY.md), [ARCHITECTURE §4](../03_Architecture/ARCHITECTURE.md).
- [readiness.yaml](../09_Config_Templates/readiness.yaml) — `vendor.runner_isolation`, `vendor.runner_isolation_final`; [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) — `trust_ramp.graduation.requires_identity_isolation_evidence`.
- [F1_Platform](../05_Build_Phases/F1_Platform.md) F1-AT-21; [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md) UAT-27; [INVARIANTS](../11_Production_Contracts/INVARIANTS.md) I02.
