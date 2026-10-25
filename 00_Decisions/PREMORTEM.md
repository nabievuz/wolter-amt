# PREMORTEM — Wolter AMT

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23 · Usul: RSK-02 (mustaqil kontekst), C01 audit bilan to‘ldirilgan.

Ssenariy: **"Bugun 2027-04-22. Wolter AMT butunlay barbod bo‘ldi — owner uni o‘chirib qo‘ydi."** Bu bashorat yoki sodir bo‘lgan incident emas. Ehtimollik va ta’sir sifat darajasida beriladi; foiz yoki ROI uydirilmaydi. Har risk himoyasi qoldiq riskni kamaytiradi, uni nolga tushirmaydi.

**Qayta ko‘rish sanalari:** tracking gate’dan oldin (F2 oxiri, HG-F2-08) · F5 go/no-go (HG-F5-02) · to‘liq takeover’dan 4 hafta keyin · 2027-01-15 (qish ma’lumoti bilan) · har katta release, vakolat, offer yoki custody o‘zgarishida. F5 va F7 shu hujjatga qaytadi.

## Xulosa (BLUF)

Eng ehtimolli muvaffaqiyatsizlik xavfsizlik emas, **o‘lchov va operatsiya** bilan bog‘liq [X]: AI kampaniyalarni baseline’siz, tracking tuzatilmasdan va ehtimol qishki past mavsumda oladi; natija pasaysa sabab AI’dami, mavsumdami yoki trackingdami — ajratib bo‘lmaydi. Bunga yolg‘iz founder’ning approval charchog‘i va murakkab stack’ni ushlab turish yuki qo‘shiladi. Self-evolution qatlami bu yukni kamaytirishi yoki — nazoratsiz bo‘lsa — testlarni yumshatib, xavfni yashirishi mumkin.

## Sabablar va himoyalar

| # | Muvaffaqiyatsizlik yo‘li | Tur | Ehtimol / Ta’sir | Himoya (kanonik joy) | Qabul |
|---|---|---|---|---|---|
| C1 | Counterfactual yo‘q: yangi tracking/landing ta’siri AI foydasi deb olinadi; targetolog tajribasi yo‘qoladi | Jamoa | yuqori / yuqori | Bosqichli takeover (Q36 ✅), 8 haftalik baseline + definition/tracking revision, deterministik kill criteria (Q31 ✅, [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml)), targetolog 4 hafta approver | UAT-05/06/07 |
| C2 | Murojaat yo‘qoladi yoki o‘lchov zanjiri buzuq (fbclid, CAPI, qo‘lda "qualified") | Texnik | yuqori / yuqori | Tracking hard gate (Q37 ✅), durable accepted receipt → CRM reconciliation, qualified fakt qoidasi (◇ P-19), off-host monitor | UAT-08…12 |
| C3 | Past hajm: nol qualified yoki past N "inconclusive" nomi bilan sarf davom etadi | Bozor/Moliya | yuqori / o‘rta–yuqori | Konsolidatsiya va bitta eksperiment (Q41 ✅), `data_status` harakat jadvali, exposure guard har sync siklida, scale blok, inson handback | UAT-07/17/29 |
| C4 | Approval charchog‘i: rubber-stamp yoki eski tasdiq yangi asset/rol/policy bilan bajariladi | Jamoa | yuqori / yuqori | Bitta 10:00 change set (Q38 ✅), revision binding va har dispatch revalidation, reject-rate monitoringi, TTL 12 soat | UAT-13/14/26 |
| C5 | Stack/host xatosi: ofis PC’sida disk, elektr yoki internet uzilishi (zaxira liniya hozircha yo‘q, Q60), jismoniy ishni faqat owner qila oladi (Q52); monitor host bilan birga o‘chadi; eski DB bilan write replay; founder SRE’ga aylanadi | Texnik | o‘rta–yuqori / yuqori | RAID1 (har disk yolg‘iz yuklaydi, degraded alert), UPS va toza o‘chish (Q53, `ALERT_HOST_POWER`), lokal snapshot (Q55), pinned versiyalar, off-host signal, locked restore (`killed` bilan boshlanadi), tashqi reconciliation, schema-aware rollback, resurs konverti | UAT-21…25/29/33/34, F0-AT-12, F0-AT-19 |
| C6 | Meta policy/huquq: noto‘g‘ri offer, special category yoki asset huquqi bilan reklama | Tashqi | o‘rta / yuqori | Owner offer registry (Q35 ✅), special category tekshiruvi (Q42 ✅), mustaqil Reviewer `review.get_subject` bilan (◇ P-20), asset huquqi `asset_rights_clear` | UAT-26/31 |
| C7 | Pul: unit xatosi, parallel so‘rovlar bir limitni ikki marta sarflaydi, oy reset ortiqcha headroom beradi | Texnik/Moliya | past–o‘rta / yuqori | Minor units, reservation, MTD headroom, commitment formulasi, **Ads Manager spending limit majburiy** (Q37 ✅) + protective pause qo‘shimcha (◇ P-21) | UAT-16…20 |
| C8 | Sales sifati: status bor, lekin bog‘lanish yoki shartnoma yo‘q; agent vazifalari sotuvchilarni bezovta qiladi | Jamoa | o‘rta / yuqori | Yozma qualified ta’rifi (Q16 ✅), sotuvchilarga vazifa yo‘q (Q18 ✅), SOP + sample QA, mustaqil contract/payment manbasi | UAT-03/04 |
| C9 | Sig‘im/mavsum: renewal tranzaksiyasi fizik park deb olinadi; go-live qishga to‘g‘ri keladi | Bozor | o‘rta / o‘rta–yuqori | Fizik park balansi, bugungi snapshot (◇ P-06), 12+ oylik mavsumiy baseline (Q37 ✅), sale readiness (◇ P-09) | UAT-01/02/06 |
| C10 | Kreativ/model: eval yuqori, lekin real tool/task yoki o‘zbekcha copy sifati yomon; foto kutubxonasi charchaydi | Jamoa | o‘rta / o‘rta | Golden copy, birinchi 20 live copy — inson (Q42 ✅, ◇ P-15), Reviewer til slot’i, haftalik real kontent (Q20 ✅) | UAT-27/30/31/32 |
| C11 | Self-evolution testlarni, evaluator’ni yoki holdout’ni yumshatib, yomon o‘zgarishni "o‘tdi" deb chiqaradi | Texnik | o‘rta / yuqori | Himoyalangan sirtlar (E sinfi), mustaqil verifier va holdout custody, manifest digest’iga bog‘langan owner release, auto-release o‘chiq (Q50 ✅, ⧗ OD-03) | EVO-AT03…08 |
| C12 | Workflow runtime qayta ishga tushganda qadam ikki marta bajariladi yoki run’lar jim qotadi | Texnik | o‘rta / yuqori | Durable checkpoint, lease/fence/epoch, command ledger orqali reconciliation, owner ko‘rinishi `/work` | EVO-AT01/02/07/12, WF-TEST-RT-* |
| C13 | Engineering ishi production resursini yoki pulini yeydi | Texnik/Moliya | o‘rta / o‘rta | Alohida engineering hisobi (⧗ OD-02), cgroup slice’lar control > production > sandbox, bosimda sandbox pauza | EVO-AT05, FE-AT-* |
| C14 | AMT PC yoki disk o‘g‘irlanadi, unga ruxsatsiz jismoniy kirish bo‘ladi yoki ikkala disk yo‘qoladi; AMT PC’dan tashqarida nusxa yo‘q, disk shifrlanmagan | Texnik | past / yuqori | Qabul qilingan xavf (Q54, Q55): AMT tarixi (approval, audit, readiness imzolari, ledger’lar) yo‘qoladi; lead’lar landing store va amoCRM’da qoladi, CAPI ulardan faqat yo‘qolgan host yubora olmagan eventlar uchun qayta yuboriladi (takroriy server eventi dedup’iga tayanilmaydi; qolganlari `skipped_unknown_prior_send`); o‘g‘irlikda va ruxsatsiz kirish belgisida (◇ P-32) INC-26 — breach javobi (⧗ OD-16), eski Tailscale tuguni o‘chiriladi, tunnel tokeni aylantiriladi va barcha mavjud tunnel ulanishlari uziladi (aylantirishning o‘zi ishlab turgan connector’ni uzmaydi), barcha credential rotatsiya qilinadi va `sops rotate` bilan data key yangilanadi; xotiradagi PII diskka tushmaydi (swap va core dump yo‘q, F0-AT-20); PC qulflangan, plombalangan server qutisida (Q52); yangi PC `--rebuild` va age kalitining qog‘oz/QR nusxasi bilan (Q56); belgi PC joyida topilsa ham ikkala disk tozalanadi va holat manbalardan quriladi — disklardagi ma’lumot production’ga tiklanmaydi (BACKUP_RESTORE §5.4) | UAT-23, F6-AT-09, F0-AT-17, F0-AT-20, F0-AT-22 |
| C15 | Cloudflare yoki Tailscale akkaunti buziladi: begona hostname tunnel orqali lokal servisga yo‘naltiriladi, begona qurilma tailnet’ga qo‘shiladi yoki siyosat ochiladi | Tashqi | past / yuqori | 2FA va faqat owner a’zoligi (HG-F0-02, HG-F0-04); `cloudflared` UID loopback’da faqat Caddy’ga yetadi (nftables), Caddy faqat `mar*` ni tg-auth bilan xizmat qiladi; Tailscale siyosati shabloni `tests` bloki bilan, device approval, Tailscale SSH o‘chiq, sshd faqat kalit bilan; har o‘zgarishda va choraklik mashqda F0-AT-04 va F0-AT-08 qayta | F0-AT-04, F0-AT-08, F0-AT-21 |

## Erta signallar va trigger’lar

| Risk | Erta signal | Trigger → harakat | Egasi |
|---|---|---|---|
| C1 | learning reset’lar ko‘payadi, qualified lead pasayadi | KC-01: 2 hafta ketma-ket >25% yomon → pipeline L0 + handback + C05 | sync-worker → owner |
| C2 | UTM/fbclid’siz lidlar, EMQ pasayishi, accepted↔CRM farqi | 2 kun health fail → read_only; 1 kun fail → alert | sync-worker → owner |
| C3 | "learning limited", qarama-qarshi xulosalar | 3 ta ketma-ket inconclusive → eksperimentlar qisqartiriladi; spend>0 va qualified=0 → `ALERT_ZERO_QUALIFIED_EXPOSURE` | funnel-analyst → owner |
| C4 | approval kechikadi, reject ≈ 0 | 1 hafta approval qarzi → batch rejimni qayta ko‘rish yoki approver qo‘shish (owner qarori) | owner |
| C5 | majburiy upgrade, sessiya xatolari, disk/inode o‘sishi, RAID degraded, UPS batareyada ishlashi, internet uzilishlari, founder ops vaqti oshishi | `ops.founder_time_budget` 2 hafta oshsa → stack’ni soddalashtirish ADR’i; bir oylik uzilish statistikasi → zaxira internet liniyasi qarori (Q60) | owner |
| C14 | buzilgan plomba, noma’lum chassis-intrusion yozuvi, kutilmagan reboot, tunnel connector ro‘yxatida ikkinchi connector | INC-26 (◇ P-32): breach javobi, tugun va tunnel ulanishlarini uzish, to‘liq rotatsiya | owner |
| C15 | Cloudflare yoki Tailscale’dan yangi a’zo, API token, public hostname yoki qurilma haqida xabar | F0-AT-04 va F0-AT-08 qayta; begona bo‘lsa INC-26 dagi kabi token aylantirish va ulanishlarni uzish | owner |
| C7 | headroom tez kamayadi, provider read-back farqi | headroom ≤ zaxira → protective pause; read-back farqi → `budget_change` blok + owner | amt-control → owner |
| C11 | `criteria_changes_detected` bo‘sh emas, holdout natijasi public suite’dan keskin farq qiladi | verification `fail` → candidate rad; holdout sizishi gumoni → kalit rotatsiyasi va yangi holdout | eng-verifier → owner |
| C12 | `reconciling`/`blocked` run’lar to‘planadi, eng eski `waiting_until` oshadi | `ALERT_WORKFLOW_BLOCKED` → [RUN_RESUME](../06_Runbooks/RUN_RESUME.md) | technical_operator |

## Owner qayta ko‘rib chiqqan qarorlar

| Premortem tavsiyasi | Owner qarori |
|---|---|
| Darhol takeover o‘rniga bosqichli | ✅ qabul (Q36) |
| Tracking tuzatilmasdan go-live qilmaslik | ✅ qabul (Q37) |
| 6 agent + Hermes + Paperclip o‘rniga soddaroq stack | ❌ rad: Hermes birinchi kundan, MVP yo‘q (Q39, Q48) — xavf choralar bilan boshqariladi |
| byadsco orqali yozish o‘rniga tor SDK operatsiyalari | ✅ qabul (Q40) |
| Landing A/B o‘rniga katta pre/post o‘zgarishlar | ✅ qabul (Q41) |
| Tizim o‘zini yaxshilashi faqat inson nazoratida | ✅ qabul (Q11, Q50); auto-release ⧗ OD-03 |

## Favqulodda vaziyat

Control latch yangi dispatch/LLM/media ishini birinchi bo‘lib yopadi. Tashqariga jo‘natilgan so‘rovni ortga qaytarish kafolatlanmaydi: natija va xarajat reconcile qilinadi. B rejim pauza natijasi qisman bo‘lsa aynan qaysi entity qolgani ko‘rsatiladi. Human handback — alert emas, inson qabul qilganining dalili (`handback_acks`). Kanonik qabul: [PRODUCTION_ACCEPTANCE](../12_Acceptance/PRODUCTION_ACCEPTANCE.md).
