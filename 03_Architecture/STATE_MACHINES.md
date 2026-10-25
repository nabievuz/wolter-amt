# Holat mashinalari

Bu fayl qo‘lda yozilmaydi: [validate_bundle.py](../12_Acceptance/validate_bundle.py) `--write-state-machines` uni config’lardan yaratadi, validator W12 esa jadval config’ga aynan mosligini va mashinalar yopiq hamda to‘liq ekanini tekshiradi (L1-07, ◇ P-166). Har holatning yozuvchisi `amt-workflow` ([WORKFLOW_CONTRACT §3](../11_Production_Contracts/WORKFLOW_CONTRACT.md)); «Kim» ustuni o‘tishni kim keltirib chiqarishini ko‘rsatadi. Manbalar: [workflow-policy.yaml](../09_Config_Templates/workflow-policy.yaml) `state_machines`, `command_aggregation`; [execution-policy.yaml](../09_Config_Templates/execution-policy.yaml) `command_states`, `extra_transitions`, kill va resume; [approval-policy.yaml](../09_Config_Templates/approval-policy.yaml) `trust_ramp`; [kill-criteria.yaml](../09_Config_Templates/kill-criteria.yaml) `streak`; command o‘tishlarining to‘liq jadvali — [DATA_MODEL §6.2](DATA_MODEL.md).

## 1. Run

Holatlar: `created`, `running`, `waiting`, `blocked`, `reconciling`, `completed`, `failed`, `cancelled`, `manual_resolution`. Boshlang‘ich: `created`. Yakuniy: `completed`, `failed`, `cancelled`.

| # | Oldingi | Keyingi | Kim | Guard |
|---|---|---|---|---|
| 1 | `created` | `running` | amt-workflow | trigger dedup passed, concurrency admitted (concurrency_semantics), authorization.preconditions and input freshness hold |
| 2 | `created` | `blocked` | amt-workflow | a required input is missing or stale, or a precondition fails (failure_paths.missing_input) |
| 3 | `created` | `cancelled` | may_cancel_principal | cancel before any step is claimed |
| 4 | `running` | `waiting` | amt-workflow | every ready step waits on a human decision, a timer or a signal |
| 5 | `waiting` | `running` | amt-workflow | the awaited decision, signal or timer arrived (completes_on, continuation.signals, continuation.timers) |
| 6 | `running` | `blocked` | amt-workflow | a blocker is reported: missing input, handoff on_reject escalate, run cost cap, dependency down, kill |
| 7 | `waiting` | `blocked` | amt-workflow | on_timeout wait_and_escalate reached its bound, or a blocker is reported |
| 8 | `blocked` | `running` | amt-workflow | the blocker's owner resolved it (input refreshed, owner decision recorded, resume after kill) |
| 9 | `blocked` | `failed` | amt-workflow | limits.max_duration reached while blocked |
| 10 | `running` | `reconciling` | amt-workflow | a linked command is uncertain |
| 11 | `waiting` | `reconciling` | amt-workflow | a linked command is uncertain |
| 12 | `reconciling` | `running` | amt-workflow | no command still in run custody is uncertain, reconciling or unresolved manual_resolution: each is terminal with required evidence (remote evidence for succeeded/done_manual), or manual_resolution with a durable accepted owner custody handoff under command_aggregation.manual_resolution_handoff; write a running checkpoint before ordinary completion checks |
| 13 | `reconciling` | `manual_resolution` | amt-workflow | the reconciliation deadline passed without remote evidence |
| 14 | `manual_resolution` | `running` | technical_operator | the operator or owner recorded done_manual, succeeded or failed_confirmed with remote evidence (execution-policy extra_transitions), or every remaining manual_resolution item has a verified accepted owner custody handoff under command_aggregation.manual_resolution_handoff; write a running checkpoint before ordinary completion checks |
| 15 | `running` | `completed` | amt-workflow | completion.technical_done holds and every completion.required_evidence item is bound to the run; no uncertain or reconciling command and no manual_resolution item still in run custody remains; handed-off items satisfy command_aggregation.manual_resolution_handoff and are reported separately from success |
| 16 | `running` | `failed` | amt-workflow | a step failed with no attempt left and its failure path ends the run (end_run; compensate_then_end only after its compensation is terminal) |
| 17 | `running` | `cancelled` | may_cancel_principal | owner or a may_cancel principal cancels, or amt-control kills: pending commands become cancelled or expired, a dispatched effect is undone only by a new authorized compensating command |
| 18 | `waiting` | `cancelled` | may_cancel_principal | as running -> cancelled |
| 19 | `blocked` | `cancelled` | may_cancel_principal | as running -> cancelled |

Taqiqlangan o‘tishlar:

| Oldingi | Keyingi | Kim | Sabab |
|---|---|---|---|
| `completed` | `*` | har kim | terminal; a correction is a new run |
| `failed` | `*` | har kim | terminal; a correction is a new run |
| `cancelled` | `*` | har kim | terminal; a correction is a new run |
| `reconciling` | `completed` | har kim | an uncertain command is never treated as done (state_separation) |
| `reconciling` | `cancelled` | har kim | a cancel request during reconciliation is recorded and applied after the uncertain commands are resolved; reconciliation never stops |
| `manual_resolution` | `completed` | har kim | only through a running checkpoint after remote resolution evidence or an accepted manual_resolution custody handoff is recorded |
| `blocked` | `completed` | har kim | a blocked run completes only after it runs again |

## 2. Step

Holatlar: `pending`, `ready`, `claimed`, `running`, `waiting`, `handoff_pending`, `completed`, `rejected`, `failed`, `skipped`, `cancelled`, `compensated`. Boshlang‘ich: `pending`. Yakuniy: `completed`, `rejected`, `failed`, `skipped`, `cancelled`, `compensated`.

| # | Oldingi | Keyingi | Kim | Guard |
|---|---|---|---|---|
| 1 | `pending` | `ready` | amt-workflow | every depends_on step is terminal with a success disposition and the step's `when` condition holds |
| 2 | `pending` | `skipped` | amt-workflow | the `when` condition is false, or on_timeout auto_not_applicable |
| 3 | `pending` | `cancelled` | amt-workflow | the run is cancelled, killed or ended by a failure path |
| 4 | `ready` | `claimed` | executor | the executor named by the definition acquires the lease (lease.required, fence_on_takeover) |
| 5 | `ready` | `cancelled` | amt-workflow | the run is cancelled, killed or ended by a failure path |
| 6 | `claimed` | `running` | amt-workflow | the lease holder started; checkpoint written |
| 7 | `claimed` | `ready` | amt-workflow | the lease expired before start (lease_ttl); the old holder is fenced |
| 8 | `claimed` | `cancelled` | amt-workflow | the run is cancelled or killed before dispatch |
| 9 | `running` | `waiting` | amt-workflow | the step awaits a timer, a signal, a human decision or an uncertain command |
| 10 | `waiting` | `running` | amt-workflow | the awaited event arrived (completes_on, signal, timer, resolved command) |
| 11 | `waiting` | `failed` | amt-workflow | on_timeout fail_step_safe |
| 12 | `waiting` | `completed` | amt-workflow | on_timeout expire_item_and_close with every item terminal (an expired item is never approved) |
| 13 | `waiting` | `cancelled` | amt-workflow | the run is cancelled or killed; uncertain commands keep reconciling |
| 14 | `running` | `handoff_pending` | amt-workflow | the output was submitted as a handoff (workflow.submit_output passed handoff_validation) |
| 15 | `handoff_pending` | `completed` | receiver | the receiver accepted the handoff revision |
| 16 | `handoff_pending` | `rejected` | receiver | the receiver rejected with reject_codes; on_reject applies (producer_retry creates attempt + 1 of the producer step, escalate blocks the run, end_run ends it) |
| 17 | `handoff_pending` | `failed` | amt-workflow | the handoff expired and on_reject.after_max ends the step |
| 18 | `running` | `completed` | amt-workflow | outputs recorded; a command-linked step satisfies its command_aggregation role complete_when and the first matching ordered rule returns completed (approval, dispatch or reconciliation). Per-item dispositions preserve remote evidence and accepted manual_resolution custody handoffs; uncertain or handed-off items are never reported as succeeded. Run-owned unresolved commands still prevent run completion (state_separation). A step without linked commands uses its declared outputs, approvals or completes_on evidence |
| 19 | `running` | `failed` | amt-workflow | an error with no attempt left (max_attempts_per_step), or a linked primary command failed_confirmed per command_aggregation |
| 20 | `running` | `cancelled` | amt-workflow | the run is cancelled or killed before this step dispatched an effect |
| 21 | `completed` | `compensated` | amt-workflow | a compensating command for this step's effect reached succeeded with remote evidence |

Taqiqlangan o‘tishlar:

| Oldingi | Keyingi | Kim | Sabab |
|---|---|---|---|
| `running` | `ready` | har kim | no new attempt while an effect may be in flight (retry.irreversible_effect reconcile_before_new_attempt) |
| `waiting` | `ready` | har kim | no new attempt while a linked command is uncertain |
| `rejected` | `*` | har kim | terminal for that attempt; producer_retry creates a new attempt |
| `failed` | `*` | har kim | terminal; recovery is a new attempt or a new run |
| `skipped` | `*` | har kim | terminal |
| `cancelled` | `*` | har kim | terminal |
| `compensated` | `*` | har kim | terminal |

## 3. Handoff

Holatlar: `offered`, `accepted`, `rejected`, `expired`. Boshlang‘ich: `offered`. Yakuniy: `accepted`, `rejected`, `expired`.

| # | Oldingi | Keyingi | Kim | Guard |
|---|---|---|---|---|
| 1 | `offered` | `accepted` | receiver | receiver_validates: the envelope schema and accept_when pass for this exact revision (handoff_validation) |
| 2 | `offered` | `rejected` | receiver | a reason code from the handoff reject_codes is recorded with the round (handoff_rejection) |
| 3 | `offered` | `expired` | amt-workflow | the handoff deadline passed (step timeout or on_timeout) |

Taqiqlangan o‘tishlar:

| Oldingi | Keyingi | Kim | Sabab |
|---|---|---|---|
| `offered` | `accepted` | executor | the producer never accepts its own handoff |
| `rejected` | `accepted` | har kim | a corrected revision is a new handoff_id with round + 1 |
| `expired` | `accepted` | har kim | a late answer is a new revision |
| `accepted` | `*` | har kim | terminal |

## 4. Command

Holatlar: `pending_review`, `pending_approval`, `approved`, `claimed`, `executing`, `succeeded`, `rejected`, `expired`, `cancelled`, `failed_confirmed`, `uncertain`, `reconciling`, `manual_resolution`, `awaiting_manual`, `done_manual`. Asosiy o‘tishlar, yozuvchi funksiyalar va guard’lar — [DATA_MODEL §6.2](DATA_MODEL.md); qo‘shimcha o‘tishlar `execution-policy.yaml#extra_transitions`:

- `claimed -> cancelled (kill or revoke before dispatch intent; reservation released)`
- `approved\|claimed -> cancelled (guard failure with reason_code)`
- `awaiting_manual -> expired`
- `manual_resolution -> succeeded\|failed_confirmed (operator evidence)`
- `shadow item -> expired at TTL`
- `pending_review -> expired (review_ttl - no Reviewer pass within the review TTL; reservation released)`
- `pending_review\|pending_approval -> cancelled (step_incomplete - the producing workflow step ended without workflow.submit_output; reservation released)`

## 5. Change-set item va step natijasi

Change-set item — bitta command revision’i; item holati uning command holati. Bir nechta command’li step natijasi `workflow-policy.yaml#command_aggregation` qoidalari bo‘yicha (yuqoridan pastga, birinchi mos qoida):

Ochiq command holatlari: `pending_review`, `pending_approval`, `approved`, `claimed`, `executing`, `awaiting_manual`, `uncertain`, `reconciling`, `manual_resolution`; yakuniy: `succeeded`, `done_manual`, `failed_confirmed`, `rejected`, `expired`, `cancelled`; muvaffaqiyat: `succeeded`, `done_manual`.

| Step roli | Qoida | Shart | Step | Run |
|---|---|---|---|---|
| approval | `any_approved` | {'any_in': ['approved']} | `completed` | — |
| approval | `none_approved_expired` | {'none_in': ['approved'], 'any_in': ['expired']} | `failed` | failure_paths.cancel_or_escalate |
| approval | `all_rejected` | {'all_in': ['rejected', 'cancelled'], 'any_in': ['rejected']} | `rejected` | failure_paths |
| approval | `all_cancelled` | {'all_in': ['cancelled']} | `cancelled` | failure_paths |
| dispatch | `compensation_failed` | {'compensation_in': ['failed_confirmed']} | `failed` | failure_paths |
| dispatch | `any_progress` | {'any_in': ['succeeded', 'done_manual', 'uncertain', 'reconciling', 'manual_resolution']} | `completed` | — |
| dispatch | `all_failed` | {'all_in': ['failed_confirmed', 'expired']} | `failed` | failure_paths |
| dispatch | `all_cancelled` | {'all_in': ['cancelled']} | `cancelled` | failure_paths |
| reconciliation | `compensation_failed` | {'compensation_in': ['failed_confirmed']} | `failed` | failure_paths |
| reconciliation | `reconciled` | {'all_in': ['succeeded', 'done_manual', 'failed_confirmed', 'rejected', 'expired', 'cancelled', 'manual_resolution']} | `completed` | — |

## 6. Trust Ramp (L0 / L1 / L2)

Darajalar: `L0_shadow`, `L1_approve_each`, `L2_auto_within_guardrails`; boshlang‘ich: `L1_approve_each`.

| # | O‘q | Sabab | Oldingi | Keyingi | Kim | Guard |
|---|---|---|---|---|---|---|
| 1 | pipeline_mode | `go_live` | `L0_shadow` | `L1_approve_each` | owner | capability profile passes at the transition (pipeline.rent.L1 F6_STEP1, pipeline.sale.L1 F6_STEP2) and owner pipeline_mode_change typed code (HG-F6-01 rent, HG-F6-02 sale) |
| 2 | pipeline_mode | `post_kill_criteria_resume` | `L0_shadow` | `L1_approve_each` | owner | execution-policy resume.after_kill_criteria - C05 RCA, owner takeover_scope_change (HG-F6-04) and owner pipeline_mode_change |
| 3 | pipeline_mode | `restore` | `L0_shadow` | `L1_approve_each` | owner | execution-policy restore - reconcile complete and owner control_resume (cause restore) per pipeline, at most L1; not a gate |
| 4 | pipeline_mode | `owner_mode` | `L1_approve_each` | `L2_auto_within_guardrails` | owner | L2_ENABLE passes and owner pipeline_mode_change typed code |
| 5 | pipeline_mode | `owner_mode` | `L2_auto_within_guardrails` | `L1_approve_each` | owner | owner pipeline_mode_change typed code |
| 6 | pipeline_mode | `global_kill_resume` | `L2_auto_within_guardrails` | `L1_approve_each` | amt-control | execution-policy resume.after_global_kill - min(pre_kill_pipeline_mode, L1_approve_each) |
| 7 | pipeline_mode | `owner_mode` | `L1_approve_each` | `L0_shadow` | owner | owner pipeline_mode_change typed code |
| 8 | pipeline_mode | `owner_mode` | `L2_auto_within_guardrails` | `L0_shadow` | owner | owner pipeline_mode_change typed code |
| 9 | pipeline_mode | `kill_criteria_l0` | `L1_approve_each` | `L0_shadow` | amt-control | KC-01 triggered (protective control kill_criteria_l0) |
| 10 | pipeline_mode | `kill_criteria_l0` | `L2_auto_within_guardrails` | `L0_shadow` | amt-control | KC-01 triggered (protective control kill_criteria_l0) |
| 11 | pipeline_mode | `restore_without_journal` | `L1_approve_each` | `L0_shadow` | amt-control | restore without the control journal (execution-policy restore.journal_unavailable) |
| 12 | pipeline_mode | `restore_without_journal` | `L2_auto_within_guardrails` | `L0_shadow` | amt-control | restore without the control journal (execution-policy restore.journal_unavailable) |
| 13 | trust_level | `graduation` | `L1_approve_each` | `L2_auto_within_guardrails` | owner | graduation met for the trust key (decision rule TRUST_RAMP_GRADUATION), identity isolation evidence, action not in never_auto, owner trust_graduation typed code (HG-L2-01) |
| 14 | trust_level | `demotion` | `L2_auto_within_guardrails` | `L1_approve_each` | amt-control | incident on the trust key (graduation.incident_definition) or KC-01 on the pipeline (demotion) |
| 15 | trust_level | `owner_lowering` | `L2_auto_within_guardrails` | `L1_approve_each` | owner | owner /graduate <trust key> L1 (lowering, not a gate) |

Taqiqlangan:

- pipeline_mode L0_shadow -> L2_auto_within_guardrails in one step
- trust_level into or out of L0_shadow (the trust axis is L1 <-> L2 only)
- any raise (L0 -> L1, L1 -> L2) by an agent, a workflow, amt-control or a timer
- trust_level L2 for an action in never_auto

## 7. Kill criteria seriyasi (KC-01 / KC-02)

Holatlar: `clear`, `counting`, `triggered`; yakuniy: yo‘q (seriya qayta tiklanadi).

| # | Oldingi | Keyingi | Hafta ta’siri | Kim | Guard |
|---|---|---|---|---|---|
| 1 | `clear` | `counting` | `increment` | sync-worker | bad_count + 1 < consecutive_weeks |
| 2 | `clear` | `triggered` | `increment` | sync-worker | consecutive_weeks = 1 |
| 3 | `counting` | `triggered` | `increment` | sync-worker | bad_count + 1 >= consecutive_weeks |
| 4 | `counting` | `clear` | `reset` | sync-worker | a valid week not worse than the reference |
| 5 | `clear` | `clear` | `reset` | sync-worker | a valid week not worse than the reference |
| 6 | `clear` | `clear` | `hold` | sync-worker | a held week |
| 7 | `clear` | `clear` | `blocked` | sync-worker | a blocked week (blocked_rule) |
| 8 | `counting` | `counting` | `hold` | sync-worker | a held week |
| 9 | `counting` | `counting` | `blocked` | sync-worker | a blocked week (blocked_rule) |
| 10 | `triggered` | `clear` | `owner_clear` | owner | resume completed (resume.policy_ref - C05 RCA, HG-F6-04 takeover_scope_change, owner pipeline_mode_change); counting restarts at the next full event_week |
| 11 | `triggered` | `clear` | `owner_clear` | owner | C05 RCA recorded and at least one matured cohort since the trigger is valid and not worse, then owner control_resume (cause kc02_guardrail); counting restarts at the next matured cohort; the Trust Ramp incident window restarts at the clear |

Taqiqlangan:

- triggered -> counting or clear by an evaluation (only the owner resume clears a trigger)
- any transition written by an agent, the LLM or a human edit of the evaluation record
- a measurement-revision recomputation that moves triggered back while the pipeline is in L0

## 8. Kill rejimlari va resume

Global rejimlar: `shadow`, `enabled`, `read_only`, `killed`; pipeline rejimlari: `L0_shadow`, `L1_approve_each`, `L2_auto_within_guardrails`; standart kill rejimi: `A`.

| Kill rejimi | Nima to‘xtaydi |
|---|---|
| `A` | stop AI dispatch, LLM/media and normal external writes |
| `B` | A + pause the highest fully managed level of every managed entity; foreign parents untouched |

Kill paytida ruxsat etiladi: `protective_pause`, `capi_delivery`, `landing_crm_delivery`, `notifications_and_acks`; rad etiladi: `normal_external_write`, `llm_dispatch`, `media_dispatch`, `amo_write`, `github_write`, `non_recovery_release`.

| Resume qoidasi | Qiymat |
|---|---|
| `after_global_kill` | min(pre_kill_pipeline_mode, L1_approve_each) |
| `preserve_global_shadow` | True |
| `preserve_read_only_until_cause_resolved` | True |
| `after_kill_criteria` | L0_shadow until C05 RCA + owner takeover_scope_change (HG-F6-04) + owner pipeline_mode_change to L1_approve_each |
| `released_entities_require_owner_retakeover` | True |
| `auto_retakeover_on_resume` | False |

| Rejim sabablari | Qoida |
|---|---|
| `read_only_causes` | set of {cause, control_event_id, raised_at}; causes - maintenance_hold, tracking_read_only, provider_limit_read_only, account_restricted_read_only |
| `proxy_admission_causes` | set of {cause, control_event_id, raised_at}; causes - maintenance_hold, proxy_admission_pause (reason_code) |
| `exit` | each exit removes only its own cause - maintenance_release (maintenance_hold), control_resume (the read_only cause it names; or cause kc02_guardrail for a triggered KC-02 streak after C05 RCA and one matured cohort that is not worse, kill-criteria.yaml#streak), agent_resume (proxy_admission_pause with reason key_noncritical_stop, share_stop or month_boundary, refused while the cause is still active), billing_unreliable_resume (billing_unreliable); write_mode leaves read_only and admission reopens only when the set is empty |
