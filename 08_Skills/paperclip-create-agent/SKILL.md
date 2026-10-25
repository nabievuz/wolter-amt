---
name: paperclip-create-agent
description: How the Wolter AMT CMO drafts a new agent that the platform then creates by itself (owner decision Q68) — an envelope-checked hire proposal submitted to WF-E05, never a direct Paperclip API call.
---

# Paperclip create agent (AMT)

Holat: spetsifikatsiya · Runtime: NOT_RUN · Sana: 2026-10-25.

Adapted from the MIT-licensed `paperclipai/paperclip` skill `skills/paperclip-create-agent` (commit `8415f4a679689eab68af5d41331639cacf7fd6cd`, Copyright (c) 2025 Paperclip AI). Upstream an agent with `can_create_agents` calls `POST /api/companies/:id/agent-hires`. In AMT no agent holds that permission and the Paperclip bridge refuses `agent.hire` and `agent.create`: the CMO drafts the hire, and the platform (WF-E05) checks it against [agent-hiring.yaml](../../09_Config_Templates/agent-hiring.yaml), creates the agent, verifies it and tells the owner. There is no owner approval step (✅ Q68); the envelope applies the owner decisions Q68 did not change.

## 1. When to draft a hire

- A recurring piece of paid Meta Ads work (Q14) that none of the six base roles owns, or that keeps one role over its share, with evidence from `wh.metrics` and the weekly plan (C07) or the monthly retro (C12).
- Design it with the C10 recipe (agent design: CRT-01, DGN-04, DAT-04, RSK-03 + RSK-04, PRI-03): what the agent owns, what it must never do, how its output is evaluated.
- Never draft an agent for browser automation, DM or comment replies, organic social, a new integration or credential, lead PII, hiring, approvals or review verdicts — WF-E05 refuses it (`envelope.forbidden_capabilities`).

## 2. Hire proposal (WF-E05 S01 output)

Fields mirror the upstream hire payload; WF-E05 fills the Paperclip-specific ones.

| Field | Content |
|---|---|
| `slug` | new lowercase id, not one of the six base roles |
| `role`, `title` | short role name and title |
| `owned_responsibility` | one paragraph: identity and the responsibility it owns (upstream baseline role guide; ≤ 1 200 characters); no operating manual, heartbeat rules or review routes |
| `parent_role` | the base role whose kernel and prompt template it uses (`media-buyer`, `funnel-analyst`, `cro` or `creative-studio`) |
| `tools` | subset of `envelope.allowed_tools`, each justified in one line; a tool the platform lacks is a code release (Q11), not a hire |
| `model` | one of the models already allowed for the six roles (Q44.2) |
| `share_minor` | integer USD minor taken from `reserve`; must fit the remaining reserve |
| `reports_to` | `cmo` |
| `heartbeat` | off (upstream default); the agent wakes only through WF assignments |
| `evaluation` | how its outputs are judged in the first 30 days (C10 eval plan) |
| `evidence` | `wh.metrics` / `wh.query` references and the C07 or C12 item it comes from |

## 3. After you submit

1. WF-E05 S02 runs the envelope checks (`agent-hiring.yaml#checks`); a failure ends the run with the failing check named — revise or drop the idea.
2. S03 creates the agent (AMT dynamic agent record, share from reserve, Paperclip agent through the platform-only board create call; Paperclip's approval requirement for agent hire requests stays on).
3. S04 verifies it with its own token (bridge denials, tool limit, L1 approval for every command, no PII).
4. S05 sends the owner `ALERT_AGENT_HIRED`; the owner can stop it at any time with `/agent retire <slug>`.

Never say an agent exists before WF-E05 reports S04 passed. Every external action of a created agent goes through the daily change set at `L1_approve_each`; created agents never hire.

## Tool scope

Machine-checked by the bundle validator (rule D15). This skill is loaded on demand by WF-E05 S01 (not an eager skill of any role); it cites the CMO tools the step uses, which the CMO already holds in `approval-policy.yaml#agents.cmo.tools`.

| Tool | Instructed roles | Mention |
|---|---|---|
| `workflow.submit_output` | — | citation |
| `wh.metrics` | — | citation |
| `wh.query` | — | citation |
