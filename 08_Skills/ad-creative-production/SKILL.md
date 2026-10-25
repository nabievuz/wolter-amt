---
name: ad-creative-production
description: Production rules for Wolter paid Meta ad creatives — real-footage-first workflow, formats and safe zones, naming, immutable manifest, static (HTML→PNG) and video (ffmpeg) templates, Uzbek subtitles, audio and voice-over rules, AI-generation limits, media-cost discipline, footage hygiene and the first-20 human language check.
---

# Ad creative production

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-23.

Scope: **paid Meta ads only** (Facebook + Instagram placements; Q14 ✅). No organic posts, channel stories or Telegram content. User: creative-studio. Required semantics: [BUSINESS_CONTRACT §9](../../11_Production_Contracts/BUSINESS_CONTRACT.md), [CREATIVE_STUDIO](../../02_Team_Charter/agents/CREATIVE_STUDIO.md), [offer-registry](../offer-registry/SKILL.md), [wolter-brand-voice](../wolter-brand-voice/SKILL.md). Tools and media limits: [approval-policy](../../09_Config_Templates/approval-policy.yaml), [budgets](../../09_Config_Templates/budgets.yaml) (`media_generation.enabled: false` until `budget.media` is approved).

## 1. Workflow

1. **Brief** (handoff from cmo or a WF-B05 arm): pipeline, hypothesis, audience insight, offer revision(s), formats, languages, deadline, experiment cell. Accept or reject it first (`workflow.handoff_decide`); an inactive offer revision or unknown rights is a rejection, not a guess.
2. **Source selection:** `drive.list_raw` shows only rights-cleared material (quarantined or unknown-rights uploads stay invisible). Pick real footage and photos — bikes, couriers at work, stations, swaps, Tashkent streets — and record the source hashes and rights references.
3. **Concept:** up to 1–3 concepts (K4: “up to”, not “at least”). Each is one idea: pain or desire → proof → offer → CTA.
4. **Copy:** per wolter-brand-voice; Uzbek Latin first; an adapted Russian variant only if the brief asks (Q21 ✅).
5. **Render:** statics with `render.html_to_png` from brand HTML templates; video with `render.video_template` (ffmpeg templates).
6. **Self-check:** brand-voice checklist, meta-ads-policy-review matrix, every term mapped to an offer revision or registry fact, rights for every source.
7. **Register:** `creative.register` with the manifest — one durable revision per variant. Changed bytes or copy = a new revision.
8. **Review and hand-off:** return the exact revision with `workflow.submit_output` for independent review; after a Reviewer pass (and the human language check where required) the media-buyer handoff carries the creative revisions and a suggested ad set. Meta upload and ad creation belong to media-buyer, not to this skill. At most two repair attempts after a fail, then escalate to CMO.

## 2. Formats ★

| Format | Use | Notes |
|---|---|---|
| 9:16 vertical | Reels/Stories placements | key text and CTA inside the central safe zone; burned-in subtitles mandatory |
| 4:5 portrait | Feed | primary static format |
| 1:1 square | Feed fallback, carousel cards | |
| Video length | short; hook in the first seconds | exact lengths come from experiments, not from this skill |

Exact pixel specs, safe zones and file limits are verified against Meta’s current placement guidance through the review process [?]; generic dimensions are not an evergreen platform contract.

## 3. Naming

Canonical definition: [TRACKING_CAPI §2](../../03_Architecture/TRACKING_CAPI.md). `creative_id = wlt_{pipeline}_{yyyymmdd}_{concept}_{lang}_{format}_v{n}` — for example `wlt_rent_20261115_noqueue_uz_9x16_v<n>` (`<n>` — the creative’s revision sequence number); pipeline `sale|rent`, lang `uz|ru`, format `1x1|4x5|9x16`. The Meta ad name is the `creative_id`; `utm_content` carries `{{ad.id}}` (not the creative ID), and the ad → exact creative revision binding is stored separately so qualified leads attribute to the right revision.

## 4. Manifest

Stored with the assets and registered with `creative.register`. Schema example, not real data:

```json
{
  "creative_id": "wlt_rent_20261115_noqueue_uz_9x16_v<n>",
  "revision": 1,
  "pipeline": "rent",
  "hypothesis": "string (uz)",
  "offer_refs": [{"offer_id": "rent-weekly-std", "revision": 3}],
  "fact_refs": ["fact_id"],
  "language": "uz | ru",
  "format": "9x16 | 4x5 | 1x1",
  "media_type": "image | video",
  "copy": {"primary_text": "…", "headline": "…", "description": "…", "cta": "…"},
  "sources": [{"asset_sha256": "…", "rights_ref": "…", "type": "video | photo", "usage_count_after": 0}],
  "derived": [{"file_sha256": "…", "kind": "render | subtitle | audio"}],
  "ai_generation": [{"used_for": "background", "model": "provider/model-id", "cost_minor": 0, "currency": "USD", "trace_ref": "…"}],
  "subtitles": "uz",
  "render": {"template": "static_offer | video_hook_proof_cta", "tool": "render.html_to_png | render.video_template"},
  "experiment_id": "string | null",
  "asset_manifest_sha": "sha256:…"
}
```

The manifest does not grant publish permission. Reviewer pass, the human language check, the action approval, offer/rights freshness and dispatch controls remain separate.

## 5. Static templates (HTML → PNG)

- Templates live in `knowledge/templates/` of the active release (read-only; video templates in `knowledge/templates/video/`), built in F4 from the brand kit: logo, colours, fonts, approved photo crops. Render tools read only from there.
- Parameters: photo, headline, sub-line, offer badge (exact registry claim), CTA label, slogan toggle (“Olib ket. Almashtir. Davom et.”).
- Text budget: headline up to 4–5 words, sub-line one line; avoid text-heavy layouts.

## 6. Video templates

- **ffmpeg templates only.** Remotion may require a paid company licence (OI-30); it is enabled only after the owner’s recorded licence decision (money — HUMAN_GATE).
- Structure: **hook → proof → offer → CTA** with real clips; burned-in Uzbek subtitles; brand end card.
- Audio: owned or licensed music only, or none. Voice-over only if recorded by Wolter or generated with explicit owner approval ★.
- Output: H.264 MP4 within Meta upload limits [?].

## 7. AI generation (`media.generate_image`, `media.generate_video`)

| Allowed | Not allowed |
|---|---|
| backgrounds, textures, scene fills, concept sketches, extending a real photo’s canvas | fabricating the product (bike, battery, station), fake people or testimonials, fake results or crowds, other brands, an implied facility or service that does not exist |

Cost discipline: the gateway reserves the estimated cost once before generating — one reservation owned by the media_generation share, checked in one transaction against the key cap, the media share and your own share (your LLM spend plus your media spend stay within your share; `budgets.yaml#media_generation.attribution`); one job stays within `max_cost_minor` and `max_video_seconds`, and the month within `max_video_seconds_per_month`; prefer the cheapest model that meets quality; video generation only when the brief explicitly justifies it; record the actual cost in minor units in the manifest. Failed or uncertain billing is not free credit.

## 8. Footage hygiene

- Track `usage_count` per source; when a source already runs in several live ads, prefer fresh material and ask for new shots through the weekly content routine (`content_reminder`, Monday 09:30 — Q20/Q29.3 ✅).
- Identifiable customers or people only with a recorded consent reference ★; blur faces and plates when in doubt. Revoked or expired rights trigger the live-asset remediation process; hiding the asset from future drafts alone is insufficient.

## 9. First 20 live-eligible copies

The first 20 live-eligible copy artifacts (shadow, eval and test copies excluded — ◇ P-15) and all their later revisions need, in addition to the Reviewer pass, a native-Uzbek human language check by a person with the `language_checker` flag: the targetologist from F5 (Q42 ✅). The owner becomes a backup checker only if the owner accepts ◇ P-29; until then a missing checker means the item waits. The rule for Russian copy is ⧗ OD-08. A copy approved by the checker may enter the golden-copy library only through WF-E04 and an owner release; it calibrates tone and is never offer evidence.

Creative performance is reported with attribution coverage and cohort maturity; a higher CTR or a low-N ranking is not a profit claim. Notes and handoffs are Uzbek Latin, machine IDs English, no customer PII.

## Tool scope

Machine-checked by the bundle validator (rule D15, F4-AT-17). A role is instructed to call a tool here only where it is listed; every listed role holds the tool in `approval-policy.yaml#agents.<slug>.tools` and loads this skill in its charter. `citation` = the tool appears only as an evidence-source format; `—` = any role may cite a source it received, calling it still needs the tool. The gateway refuses every tool outside the caller's allowlist regardless of this table.

| Tool | Instructed roles | Mention |
|---|---|---|
| `workflow.handoff_decide` | creative-studio | call |
| `drive.list_raw` | creative-studio | call |
| `render.html_to_png` | creative-studio | call |
| `render.video_template` | creative-studio | call |
| `creative.register` | creative-studio | call |
| `workflow.submit_output` | creative-studio | call |
| `media.generate_image` | creative-studio | call |
| `media.generate_video` | creative-studio | call |
