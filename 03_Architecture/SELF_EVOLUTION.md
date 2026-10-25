# SELF-EVOLUTION — sandbox, mustaqil verification va release controller dizayni

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Kontrakt: [EVOLUTION_CONTRACT](../11_Production_Contracts/EVOLUTION_CONTRACT.md). Ish oqimlari: WF-E01…E04 ([WORKFLOW_CONTRACT §8](../11_Production_Contracts/WORKFLOW_CONTRACT.md)). Qarorlar: [ADR-025](../04_ADR/ADR-025-engineering-roles-and-sandbox.md), [ADR-026](../04_ADR/ADR-026-independent-verification-custody.md), [ADR-027](../04_ADR/ADR-027-release-controller-and-harness-handover.md). Yangi vendor tanlanmaydi; mavjud stack (systemd, cgroup2, PostgreSQL, git worktree, root publisher) ishlatiladi va har imkoniyat F1/FE capability testi bilan isbotlanadi.

## 1. Komponentlar

| Komponent | Unix user / joy | Vazifa |
|---|---|---|
| `amt-sandbox` | `amt-sandbox` servis; build’lar `eng-build` UID’da systemd transient unit sifatida | proposal bo‘yicha worktree ochish, cheklangan build/test, candidate artifact va manifest |
| `amt-verify` | `amt-verify` servis; holdout kaliti faqat shu UID’da | himoyalangan suite va holdout’ni exact manifest ustida yurgizish, verification result yozish |
| `amt-release` (release controller) | `amt-release.service` — root egaligidagi tor fixed publisher entrypoint (alohida servis UID’i yo‘q) | manifest/verification/approval tekshiruvi, immutable publish, ACK, rollback, handover |
| `amt-eng-proxy` | `amt-eng-proxy` | engineering LLM identity va accounting (faqat `engineering.llm_access` tasdiqlangandan keyin); runtime `llm-proxy` va OpenRouter kalitidan alohida |
| Engineering agentlari | `agent-eng-planner`, `agent-eng-architect`, `agent-eng-implementer`, `agent-eng-verifier` | managed runner orqali, faqat o‘z workspace’i va tool’lari bilan |

Builder (qurilish bosqichidagi Claude Code) ham F6 Step 1 dan keyin shu yo‘ldan foydalanadi: sudo’siz, sandbox → verification → owner release.

## 2. Repo va yo‘llar

| Yo‘l | Egasi va ruxsat |
|---|---|
| `/srv/sandbox/<proposal_id>/<attempt>` | `eng-build` yozadi; har attempt alohida git worktree; boshqa proposal’ni ko‘rmaydi |
| `/opt/wolter-amt/releases/<release_id>` | root, immutable; runtime faqat o‘qiydi |
| `evals/protected/**` (repo ichida, himoyalangan yo‘l) | o‘zgarishi faqat E sinfi; verification har doim **joriy release’dagi** himoyalangan suite’ni ishlatadi, candidate branch’idagisini emas |
| `/var/lib/amt-verify/holdout` | shifrlangan; kalit faqat `amt-verify`; muallif rollari o‘qiy olmaydi |
| `knowledge/lessons/**` | faqat WF-E04 release’i orqali yangilanadi |

## 3. Identity, workspace va tool matritsasi

| Imkoniyat | eng-planner | eng-architect | eng-implementer | eng-verifier | amt-release | biznes agentlari |
|---|---|---|---|---|---|---|
| Repo snapshot o‘qish | ✔ (sanitized) | ✔ | ✔ (o‘z worktree’si) | ✔ (read-only) | ✔ | ✖ |
| Branch’ga yozish | ✖ | ✖ | ✔ faqat `allowed_paths` | ✖ | ✖ | ✖ |
| Himoyalangan yo‘lga yozish | ✖ | ✖ | faqat E sinfi proposal | ✖ | ✖ | ✖ |
| Holdout o‘qish | ✖ | ✖ | ✖ | faqat `amt-verify` orqali | ✖ | ✖ |
| Engineering LLM (`amt-eng-proxy`) | ✔ | ✔ | ✔ | ✔ | ✖ | ✖ |
| Runtime LLM (`llm-proxy`) | ✖ | ✖ | ✖ | ✖ | ✖ | ✔ |
| Biznes gateway tool’lari (Meta/CRM/offers) | ✖ | ✖ | ✖ | ✖ | ✖ | o‘z allowlist’i |
| Production DB | sanitized view | sanitized view | ✖ | ✖ | release jadvallari | sanitized view |
| Production secret, Meta/CRM write | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ (executor’da) |
| Root, sudo, Docker socket | ✖ | ✖ | ✖ | ✖ | faqat fixed publish entrypoint | ✖ |
| Tashqi egress | ✖ | ✖ | package proxy allowlist (`cand/*` push’ni `amt-sandbox` bajaradi) | ✖ | faqat GitHub read-only (tag va imzo tekshiruvi; [ARCHITECTURE §3.1](ARCHITECTURE.md)) | gateway/proxy |
| Merge yoki release tag | ✖ | ✖ | ✖ | ✖ | ✖ (owner beradi) | ✖ |

Salbiy ruxsat testlari (FE-AT va EVO-AT03/04/05): har engineering UID boshqa UID workspace’i, holdout, production secret, Meta/CRM token, Docker socket, `/opt/wolter-amt` va himoyalangan yo‘lga yozishga urinadi — hammasi rad va auditda. Engineering identity biznes agentining tool’ini chaqira olmaydi.

## 4. Sandbox

1. `amt-sandbox` approved proposal revision’ini oladi, `base_release_id` commit’idan worktree ochadi.
2. Build `eng-build` UID’da `systemd-run --slice=sandbox.slice` bilan: `NoNewPrivileges`, `PrivateTmp`, read-only system, faqat worktree `ReadWritePaths`, bo‘sh capability set, `MemoryMax/CPUQuota/IOWeight/TasksMax` [resource-policy](../09_Config_Templates/resource-policy.yaml) dan.
3. Tarmoq: nftables UID qoidasi faqat package proxy’ga; lockfile majburiy, `latest` yo‘q; install script’lar root’da hech qachon ishlamaydi.
4. Natija: candidate artifact + [candidate manifest](../09_Config_Templates/schemas/candidate-manifest.schema.json); `allowed_paths` dan tashqari diff yoki himoyalangan yo‘l o‘zgarishi (E sinfisiz) avtomatik rad.
5. Resurs bosimi yoki engineering byudjeti tugasa sandbox pauza/navbat; production va control slice’lari ta’sirlanmaydi.

## 5. Mustaqil verification

`amt-verify` exact manifest’ni toza isolated muhitga (credential/jobs/egress’siz) joylaydi va quyidagilarni yurgizadi: joriy release’dagi himoyalangan regression, kontrakt, security va invariant testlari; migration testi (D sinfi); nazoratli real integratsiya (PAUSED test entity, activation simulyatsiyasi) faqat proposal talab qilsa; holdout; rol bo‘yicha eval va golden copy (model/prompt o‘zgarsa). Natija verification result sifatida manifest va evaluator revision’iga bog‘lanadi. Himoyalangan yo‘llar diff’i yoki test sonining kamayishi `criteria_changes_detected` ga tushadi va verdict’ni `fail` qiladi. `eng-verifier` natijani o‘qib mustaqil review hisobotini yozadi, lekin verdict’ni o‘zgartira olmaydi.

## 6. Release controller va harness handover

Release holati: `requested → validated → prepared → activated → acked → observing → closed`; xato yo‘llari `refused` (manifest/approval nomosligi) va `rolled_back`.

- **validated:** owner’ning `release_approvals` yozuvi (`/release approve`, typed code) aynan shu `manifest_digest`, verification ID va verdict, evaluator/policy/role revision’i va control epoch’iga bog‘langan, muddati o‘tmagan; `release-*` tag owner kaliti bilan imzolangan annotated tag, imzo `/etc/amt/release-signers` bo‘yicha tekshiriladi, commit `main` dan yetib boriladi va manifest’dagi commit bilan bir xil; himoyalangan sirt o‘zgargan bo‘lsa E sinfi gate’lari yopiq; global rejim `killed` bo‘lsa faqat recovery release qabul qilinadi ([release-policy.yaml](../09_Config_Templates/release-policy.yaml)).
- **prepared:** sandbox’da bir marta qurilgan artefaktlar (`build_once_promote`) manifest’dagi digest’lar bilan solishtiriladi va root egaligidagi release katalogiga ko‘chiriladi; qayta build qilinmaydi; root repo’dagi ixtiyoriy script’ni bajarmaydi. Merge fast-forward yoki tree-hash tengligi bilan; teng bo‘lmasa yangi manifest va qayta verification.
- **activated/acked:** symlink atomik almashadi; `write_gate_acks` (gateway, executor, llm-proxy, ops-bot, amt-control, amocrm-mcp, quota-coordinator, amt-workflow) ACK bermaguncha normal write yopiq; `function_gate_acks` (sync-worker, capi-bridge, cost-watchdog, tg-auth) yangi revision’ni qabul qilmaguncha o‘z vazifasini eski qiymat bilan to‘xtatib turadi; ACK yetishmasa oldingi release saqlanadi.
- **observing:** proposal’dagi scope (avval isolated yoki read-only) va guardrail; stop rule buzilsa avtomatik hold va rollback taklifi, remote effektlar compensation command bilan. Kuzatuvni `sync-worker` dagi kuzatuv step’i bajaradi (WF-E01 S09, WF-E02 S08, WF-E03 S06, WF-E04 S06) va `regression_detected`, `stop_rule_triggered`, `rollback_trigger` signallarini o‘zi chiqaradi (`workflow-policy.yaml#signal_producer_constraints`); `cost-watchdog` release va guardrail ma’lumotini ko‘rmaydi, u faqat xarajat drift’ini beradi.

Harness/workflow o‘zgarishi (C sinfi) uchun WF-E02: inventar (run, checkpoint, lease/epoch, in-flight command va attempt, reservation, timer, webhook, audit head) → har run uchun disposition (eski definition’da tugatish / sinalgan migration / sababli bekor qilish) → owner tasdig‘i → drain (eski controller yangi dispatch’ni yopadi) → epoch++ → state migration → yangi controller qabul qiladi → reconciliation → bosqichli kuzatuv. Eski controller qaytsa eski epoch’i bilan barcha dispatch rad.

Release controller faqat AMT host release’larini bajaradi; landing va Umami o‘zgarishlari WF-B04 bo‘yicha PR → owner merge → owner Dokploy deploy yo‘lida qoladi (Q46.4 ✅) va `amt-release` da Dokploy/landing credential’i yo‘q. Release controller’ning o‘zi himoyalangan sirt: uning yangilanishini amaldagi (eski) controller publish qiladi; muvaffaqiyatsiz bo‘lsa owner uchun hujjatlangan qo‘lda root tiklash yo‘li [UPGRADE](../06_Runbooks/UPGRADE.md) da.

## 7. Yaxshilanish xotirasi

`improvement_memory` jadvali (`amt` DB, `amt_workflow` yozadi) [improvement-memory-record](../09_Config_Templates/schemas/improvement-memory-record.schema.json) sxemasida. `eng-planner` faqat sanitizatsiyalangan view’ni o‘qiydi. Agentlarga ko‘rsatma sifatida faqat `accepted` va `guidance_eligible` yozuvlar WF-E04 release’i orqali `knowledge/lessons/` ga chiqadi; `superseded/revoked/expired` yozuvlar avtomatik olib tashlanadi.

## 8. Byudjet va resurs

`budget_accounts` ichida `scope=engineering` hisobi `engineering-budget.yaml` dan; runtime `ai_runtime` (15000 USD minor/oy) va `ads` (150000 USD minor/oy) hisoblari bilan umumiy emas. Engineering LLM chaqiruvlari `amt-eng-proxy` orqali actual+reserved bilan; noma’lum narx nolga tushmaydi. Hisob yoki readiness yo‘q bo‘lsa engineering LLM yopiq va sikl qo‘lda (owner/builder) davom etadi. CPU/RAM/disk/IO limitlari cgroup slice’larida; `control > production > sandbox` ustuvorligi.

## 9. Qurilish joyi

Workflow runtime va capability prototipi — F1. Command bog‘lanishi — F3. Biznes agentlarining handoff qabuli — F4. Sandbox, verification, release controller kengaytmasi, engineering rollari va salbiy testlar — [FE fazasi](../05_Build_Phases/FE_Evolution.md); Q67 bo‘yicha FE `verified_in_staging`, deployed qatlam va FE_RELEASE PASS F5 formal eval hamda shadow boshlanishidan oldin shart; Q66 exact baseline mustaqil texnik inson signoff’i ham oldin olinadi. F4 offline harness/fixture va o‘z smoke tekshiruvlari tegishli gate’lar ichida oldin tayyorlanishi mumkin, F5 formal dalili deb hisoblanmaydi. Haqiqiy kuzatuvli to‘liq sikl (EVO-AT14) F6/F7 da yopiladi.
