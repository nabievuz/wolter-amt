# Deterministik servis: Release Controller (`amt-release`)

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Release controller agent emas — u qaror qabul qilmaydi va LLM ishlatmaydi. U owner bergan release qarorini exact manifest bo‘yicha bajaradi yoki sababini aytib rad etadi ([ADR-027](../../04_ADR/ADR-027-release-controller-and-harness-handover.md), [SELF_EVOLUTION §6](../../03_Architecture/SELF_EVOLUTION.md)).

## Vazifa

| Kirish | Tekshiruv | Natija |
|---|---|---|
| Owner `release_approvals` yozuvi, proposal ID | yozuv shu `manifest_digest`, verification ID va revision’larga bog‘langan, muddati o‘tmagan | aks holda `refused: approval_invalid` |
| Owner `release-*` tag’i | imzo `/etc/amt/release-signers` bo‘yicha to‘g‘ri, commit `main` dan yetib boriladi va manifest’dagi commit bilan bir xil | aks holda `refused: signature_invalid`, `refused: not_on_main` yoki `refused: tag_mismatch` |
| Artefaktlar | digest’lar manifest’dagi sandbox build bilan bir xil (`build_once_promote`) | aks holda `refused: artifact_digest_mismatch` |
| Global rejim | `killed` paytida faqat recovery release | aks holda `refused: killed_non_recovery` |
| Candidate manifest | digest verification result’dagi bilan bir xil, verdict `pass` | aks holda `refused: manifest_mismatch` yoki `refused: not_verified` |
| Approval tafsiloti | amaldagi rol/policy revision’i, TTL, owner identity, typed tasdiq; E sinfi uchun mustaqil inson review dalili | aks holda `refused: approval_invalid` |
| Himoyalangan sirt diff’i | E sinfi gate’lari va mustaqil inson review dalili | aks holda `refused: protected_without_gates` |
| C sinfi | WF-E02 handover rejasi tasdiqlangan | aks holda `refused: handover_required` |

Holatlar: `requested → validated → prepared → activated → acked → observing → closed`; muqobil `refused`, `rolled_back`.

## Chegara

Doira — faqat AMT host; landing/Umami (production Dokploy) release controller’dan tashqarida va unda Dokploy yoki landing credential’i yo‘q (Q46.4 ✅). Root egaligidagi fixed publish entrypoint’dan boshqa root amali yo‘q; repo’dagi ixtiyoriy script bajarilmaydi. Release controller o‘z konfiguratsiyasi va kodini o‘zgartira olmaydi; uning yangilanishini amaldagi controller E sinfi gate’lari bilan publish qiladi. Muvaffaqiyatsiz holatda owner uchun qo‘lda root tiklash yo‘li [UPGRADE](../../06_Runbooks/UPGRADE.md) da.

## Kuzatuv va rollback

ACK yetishmasa normal write yopiq va oldingi release aktiv. Observation scope proposal’dagi kabi (avval isolated yoki read-only). Stop rule buzilsa hold va rollback taklifi; rollback schema/workflow-state mosligini tekshiradi; remote effektlar compensation command bilan.

## Qabul

FE-AT-06/07/08/09, EVO-AT03, EVO-AT06, EVO-AT08.
