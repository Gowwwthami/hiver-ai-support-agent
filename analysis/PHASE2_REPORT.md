# Phase 2 Report — Golden Evaluation Set for British_Airways

**Hiver SDE Intern assignment · British_Airways**
**Status: PHASE 2 COMPLETE — AWAITING HUMAN REVIEW**

This report answers the Phase-2 requirements in order. Every number is
computed from the generated artifacts (`evaluation/golden_set.csv`,
`analysis/scripts/validate_golden_set.py` output, `analysis/golden_sampling_summary.json`,
Phase-1 `analysis/brand_analysis.md` / `analysis/british_airways_qualitative_audit.md`).
Nothing is invented; where something is **not** established, the report says so
explicitly (`Not established in Phase 2.` / `Not available from the dataset.`).

---

## 1. Final intent taxonomy

Ten mutually-exclusive (with tracked `secondary_intent`) intents, defined in
`analysis/intent_taxonomy.csv` (machine) and `analysis/intent_taxonomy.md`
(human), enums in `analysis/scripts/_taxonomy.py`:

`noise_or_off_topic_or_ack`, `contact_or_human_escalation_request`,
`flight_disruption`, `refund_or_compensation`, `website_or_app_issue`,
`information_or_policy`, `baggage`, `booking_change_or_cancellation`,
`seat_or_upgrade`, `account_or_security`.

### Intent table (n = 200)

| intent | definition | count | % | closest confusion(s) | typical handling in golden set |
|---|---:|---:|---:|---|---|
| noise_or_off_topic_or_ack | Praise, thanks, banter, sarcastic venting with no actionable request | 43 | 21.5% | contact_or_human_escalation_request (venting with a real complaint ≠ noise) | AUTO_HANDLE 43/43; empathy_only 41/43 |
| contact_or_human_escalation_request | Wants human contact/numbers, complaint handling, threats, legal/regulatory pressure | 29 | 14.5% | refund (complaint + money ask), flight_disruption, information | ESCALATE 22/29 (complaint_or_human_judgment 21); action_offered 13, empathy_only 7 |
| flight_disruption | Concrete disruption: delay, cancellation, diversion, misconnect, stranded | 27 | 13.5% | refund_or_compensation (disruption + claim), contact (venting after disruption) | AUTO 16 / ESCALATE 10 / UNCERTAIN 1; action_offered 8, empathy_only 8 |
| refund_or_compensation | Money/points claim: refund, EU261 compensation, Avios credit, expense reimbursement | 22 | 11.0% | flight_disruption (claim-after-disruption), website (Avios collection), information (eligibility ask) | ESCALATE 21/22 (payment_or_refund 11, compensation 10); action_offered 18/22 |
| website_or_app_issue | Technical failure of a BA digital channel (check-in, MMB, site, app, payment) | 21 | 10.5% | account_or_security (login vs. hacked), booking_change (site booking flow vs data amendment) | AUTO 16/21; action_offered 10, direct_answer 8 |
| information_or_policy | Standalone factual/policy question needing no booking change | 20 | 10.0% | baggage (cabin-baggage policy), booking_change (policy touching their booking) | AUTO 17/20; direct_answer 15/20 |
| baggage | Bag delayed/damaged/lost/misrouted or carry-on item issue with a real trip | 16 | 8.0% | information (carry-on policy vs. item), contact (baggage complaint) | AUTO 8 / ESCALATE 8; direct_answer 6, action_offered 5 |
| booking_change_or_cancellation | Modify/add-to/cancel own booking incl. PNR data amendments | 12 | 6.0% | website (site booking flow), information (policy) | ESCALATE 6/12 (account_specific 6) + AUTO 6; direct_answer 5, action_offered 5 |
| seat_or_upgrade | Seat selection/fees/upgrades/cabin for a specific booking | 7 | 3.5% | information (generic seat policy), refund (seat-fee dispute) | ESCALATE 5/7; status_update 2, action_offered 2, direct_answer 2 |
| account_or_security | Executive Club account hacked/suspect activity/identity-gate | 3 | 1.5% | website_or_app_issue (login-like symptom), contact (frustration) | ESCALATE 3/3 (security_or_identity 2, account_specific 1); action_offered 3/3 |
| **Total** | | **200** | **100%** | | |

## 2. Why this granularity is right

- **Grounded in Phase-1 evidence**, not invented: the taxonomy extends the
  categories hand-identified in the n=50 audit
  (`analysis/british_airways_qualitative_audit.md`, §"What the customer asks"):
  refund/compensation, disruption, seat dispute, account security, IT/website,
  booking change, baggage, noise, contact-routing.
- **One label is assigned per customer *turn*** (the target inbound message),
  with `secondary_intent` for genuinely two-intent turns — this matches the
  Phase-2 agent decision point (route this message public vs. escalate) and
  matches how the audit found intents to be "crisp, separable" while some
  threads "span two intents."
- **Granularity is actionable**: the intents map 1:1 onto the two-part BA
  playbook observed in the audit ("public answer where factual, structured
  DM/CR hand-off where account-gated") — no intent requires the agent to
  *execute* a booking/refund inside Twitter, only to answer or route.
- The two genuinely fuzzy boundaries (disruption↔compensation,
  login↔account-security) were resolved by pre-committed conventions
  (`taxonomy_analysis.md` §1), and drift from the sampling auto-bucket to the
  final label is documented (§3 below), not hidden.

## 3. How the golden examples were sampled

Deterministic pipeline, all reproducible (`analysis/golden_sampling_summary.json`):

1. **Pool** = Phase-1 reconstructed BA conversations (16,452);
   the 50 conversations already used for the Phase-1 audit are excluded →
   **eligible pool 16,402**.
2. **Auto-bucketing** of eligible conversations by keyword rules plus the
   Phase-1 oracle cluster (for ambiguous matches a conflict flag is recorded —
   `is_conflict`, `bucket_hits`).
3. **Stratified random sample** (`seed=2026`, `TARGET_N=200`) with quotas per
   bucket proportional to population, capped; plus a `main`/`borderline`
   slice split. Result: **171 main / 29 borderline; 188 of 200 (94.0%) targets
   are the conversation's first inbound message**; conversational covariates
   (`target_position`, turn counts) are carried in the worksheet.
4. **Deduplication at build**: exact + normalized customer-message
   deduplication prevents the same utterance being sampled twice
   (`build_golden_worksheet.py`).
5. One row per conversation → no conversation is split.

## 4. How the labels were assigned (honest account)

- **Process.** Every target message was read together with its `prior_context`
  (earlier turns only; `includes_future_context = False`). The historical
  brand reply (`reference_brand_reply`) was **not** read to decide customer
  intent — it is stored separately as the resolution reference. Labels,
  escalation routing and resolution observability were then recorded in
  `evaluation/_labels.tsv` following the taxonomy + conventions documented in
  `analysis/taxonomy_analysis.md` §1/§4.
- **Who assigned them.** The labels were **drafted by the assistant (a large
  language model)** during this phase, under the documented taxonomy, and then
  run through deterministic consistency/enum validation
  (`analysis/scripts/validate_golden_set.py`). This is **not equivalent to
  human hand-labelling**: no independent human annotator has reviewed the
  labels. Automated/LLM assistance was used to draft them; automated
  suggestions were **not** treated as gold. **The set is an assistant-drafted
  golden set awaiting independent human review** — see §10 (IAA) and the
  Limitations section (§16).

## 5. How many golden examples were created

**200** (`evaluation/golden_set.csv`, 200 rows, 200 unique `conv_id`s; same in
`.jsonl`). Verified by the validator at run time — see §§15.2.

## 6. Class distribution

See the table in §1. Repeats from the validator's report summary:

- noise 43 · contact 29 · disruption 27 · refund 22 · web 21 · info 20 ·
  baggage 16 · booking_change 12 · seat 7 · security 3.
- `intent_confidence`: high 168 / medium 30 / low 2.
- `secondary_intent` set on 55 examples (27.5%); `ambiguity_flag=multi_intent`
  on 44 of the 58 flagged examples.

## 7. Escalation-label distributions

`escalation_label`: **AUTO_HANDLE 112 (56.0%) · ESCALATE 83 (41.5%) ·
UNCERTAIN 5 (2.5%)**.

### Escalation table

| escalation label / reason | count | % (of 200) | interpretation |
|---|---:|---:|---|
| AUTO_HANDLE | 112 | 56.0% | Historical brand reply fully answered in public (policy/factual, or plain empathy); no account-gated data and no human judgement needed. `escalation_reason` empty by rule. |
| ESCALATE — account_specific | 21 | 10.5% | Brand routed to DM for booking/account data (booking changes, MMB access, Avios adds). |
| ESCALATE — payment_or_refund | 12 | 6.0% | Refund/payment disputes routed to the payments/CR team. |
| ESCALATE — compensation | 11 | 5.5% | EU261/compensation claims routed to Customer Relations. |
| ESCALATE — complaint_or_human_judgment | 23 | 11.5% | Heated/repeated complaints, unfair-treatment claims, threats — need a human. |
| ESCALATE — security_or_identity | 2 | 1.0% | Account hacking / identity checks routed to Executive Club security. |
| ESCALATE — legal_or_regulatory_risk | 2 | 1.0% | Legal/regulatory pressure (small-claims threat, statutory taint) needing human handling. |
| ESCALATE — other | 12 | 6.0% | Structural escalation not fitting the named buckets (partner operator, airport staff, baggage-claim routes, call-backs). |
| UNCERTAIN (any reason) | 5 | 2.5% | Routing genuinely undecidable from the customer side (vague complaints, stranded passenger whose rebooking status is unknown, racing thread). |

Reason totals among the 88 routed labels: complaint_or_human_judgment 27
(23 ESCALATE + 4 UNCERTAIN), account_specific 21, other 13,
payment_or_refund 12, compensation 11, legal_or_regulatory_risk 2,
security_or_identity 2.

**Observable vs. policy vs. model-validated.** `HANDOFF_OUTCOME_OFF_THREAD`
(47/200) and `INFORMATION_PROVIDED` (71/200) are directly observable in the
threads. The `ESCALATE` labels are **our labeling policy** applied on top of
observable brand routing (DM/CR/security hand-offs) — i.e., "the historical
thread routed this in a way our future agent should reproduce." Nothing in this
phase validates that our agent *executes* that policy correctly; **escalation
precision/automation-rate are not measured here** (§9).

## 8. How ambiguity and noise were handled

- **Controlled fields**: `ambiguity_flag` (none/multi_intent/unclear_intent/
  truncated_captured/template_or_bot/multilingual/other), `noise_flag`
  (TRUE/FALSE), `intent_confidence`, and `escalation_label=UNCERTAIN`.
- **Ambiguity distribution (58/200, 29.0%)**: multi_intent 44, unclear_intent
  11, other 2, truncated_captured 1; 142 (71.0%) none.
  Ambiguity is not uniform: refund_or_compensation 11 multi_intent,
  flight_disruption 9, booking_change 6 multi + 2 unclear,
  contact 7 multi + 7 unclear, baggage 5 multi.
- **Hardest boundaries (data-grounded)**: refund↔flight_disruption
  (disruption + claim), baggage↔information (carry-on item vs. policy),
  contact↔flight_disruption / contact↔refund (complaint attached to a service
  ask), refund↔website (Avios/duty-free collection vs. site failure).
- **Treatment during evaluation**: ambiguous and low-confidence examples are
  kept (never silently dropped to flatter accuracy), and must be reported as a
  separate slice (44/58 carry a `secondary_intent`; low/medium-confidence rows
  are flagged). Downstream consumers may weight or exclude but must disclose it.
- **Noise**: 43 `noise_or_off_topic_or_ack` (21.5%); `noise_flag=TRUE` on 41.
  The 2 remaining noise rows have `noise_flag=FALSE, medium confidence` —
  praise messages that embed a soft complaint ("decline in standards",
  "too many people in the lounge") — deliberately kept as noise-with-a-signal
  so evaluation can decide whether the assistant should pick up the embedded
  hint. Noise anchors the "decline / acknowledge" decision and is not
  discarded.

## 9. What this phase does and does not measure

**Phase 2 establishes a (draft) human-reviewed evaluation foundation. It does
NOT establish model performance.** Any accuracy/F1/retrieval-recall/response
quality/escalation precision/automation-rate would be **Not established in
Phase 2.** No classifier, index, RAG, judge, or evaluation harness was built
(per scope). Those numbers belong to Phase 3 evaluation and must not be
reported from this phase.

## 10. Inter-annotator agreement

**Not performed.** Exactly one draft-author exists for the labels (the
assistant), and no independent human or second annotator produced a second
annotation pass. Therefore **no inter-annotator agreement statistic exists;
none is reported; none may be fabricated.** A defensible IAA can only come from
a real, independent second human annotation pass on these 200 examples
(agreement on `intent`, `escalation_label`, `noise_flag`), which is a pending
requirement for treating this set as gold.

## 11. Major taxonomy decisions

1. **Ten labels, one per turn, + secondary.** Chosen over more fine-grained or
   hierarchical taxonomies because BA threads resist span-level tagging and
   the agent decision is turn-level.
2. **`contact_or_human_escalation_request` absorbs complaint routing** (contact
   numbers + complaints + threats), matching the audit's contact-routing
   category, while pure money claims stay in `refund_or_compensation`.
3. **Noise gets an explicit acknowledgement arm** (`noise_or_off_topic_or_ack`),
   because praise/banter/marketing is ~20% of BA traffic (§6, and the audit's
   recommended "filter ~20% praise/humor/marketing residue"), and the agent
   must learn to decline politely rather than misroute.
4. **Carry-on items are `baggage`, carry-on *policy* is `information`** — a
   boundary that surfaced in the worksheet reading and is documented as a
   convention, not left to intuition.
5. **`resolution_observable` admits "off-thread" and "unclear"**: because BA
   resolves most account-gated cases off-Twitter, `RESOLVED_IN_THREAD` is
   **intentionally unused** (consistent with the audit's ~8/50 in-thread
   closures); forcing it would over-claim closure.
6. **Escalation is labelled as routing policy** (`AUTO_HANDLE`/`ESCALATE`/
   `UNCERTAIN` + reason), not as a verdict on brand quality.
7. **`escalation_label=UNCERTAIN` exists** (5 uses) so annotators may admit
   undecidability instead of guessing — the same ethos as `ambiguity_flag`.

## 12. Hardest boundaries (ranked by evidence in the set)

1. **refund_or_compensation ↔ flight_disruption** — 11 multi_intent on refund,
   3 explicit primary/secondary pairs; convention applied.
2. **contact_or_human_escalation_request ↔ nearly everything** — complaints
   attach to disruptions/money/seat/baggage; 22% of ambiguous rows are contact;
   21 of 27 complaint-reason escalations come from this label.
3. **baggage ↔ information_or_policy** — 6 pairs; item-vs-policy convention.
4. **refund_or_compensation ↔ website_or_app_issue** — Avios/duty-free
   collection is a money claim triggered by a web/App failure; 2 pairs.
5. **booking_change_or_cancellation ↔ website_or_app_issue** — a site booking
   failure vs. asking for a data amendment to an existing PNR; 2 pairs.
6. **login ↔ account hack** — `website_or_app_issue` vs `account_or_security`
   (only 3 security examples in the set): a known coverage thin spot (§14).

## 13. Evidence the taxonomy will support RAG

- **Information-dense, answerable intents are plentiful**: `information` 20 +
  pure-public portions of `website`, `baggage`, `noise` — the audit's
  "strong factual/policy QA + troubleshooting" finding is reproduced:
  71/200 threads show `INFORMATION_PROVIDED` and `direct_answer` is the
  dominant `resolution_type` for `information` (15/20), `baggage` (6/16),
  `website` (8/21).
- **Controlled context discipline** (`prior_context` only, `reference_brand_reply`
  separated) matches the Phase-3 retrieval→chat shape and prevents answer
  leakage into inputs.
- **Grounding material exists per intent**: `reference_brand_reply` on rows
  with `has_brand_reply_after=True` gives paired customer-prompt → historical
  answer examples, which is exactly the shape needed to ground/draft responses
  for `information`, `website`, `baggage`, `booking_change` (AUTO_HANDLE 112).
- **Honest caveat**: only ~16% in-thread closure in the Phase-1 audit; RAG
  grounding is *drafted* from reference replies, not shown to *resolve*
  cases — retrieval quality itself is **Not established in Phase 2** (§9).

## 14. Evidence the taxonomy will support escalation

- **A real escalation corpus exists in the threads**: 88/200 labels route
  (ESCALATE 83 + UNCERTAIN 5); 47/200 show `HANDOFF_OUTCOME_OFF_THREAD`;
  structured reasons are populated for all 88 (account_specific 21,
  complaint_or_human_judgment 27, payment_or_refund 12, compensation 11,
  security_or_identity 2, legal_or_regulatory_risk 2, other 13).
- **Notable**: 21/22 `refund`, 3/3 `security`, 26/29 `contact`
  (22 ESCALATE + 4 UNCERTAIN), 5/7 `seat` route — the exact intents the audit
  identified as DM/CR/security hand-offs.
- **Rare-but-operation-critical intents were intentionally retained** despite
  small population: `account_or_security` (3) and `seat_or_upgrade` (7) were
  quota-protected so security and seat disputes exist as evaluation anchors;
  coverage is therefore **deliberately partial, not "complete coverage"** —
  a full-coverage claim would be false (§6, §12.6).
- **Honest caveat distinguishing policy from proof**: the ESCALATE labels are
  our routing policy inferred from historical brand behavior; they do not
  prove our agent's future escalation is *optimal*, nor that any escalation
  *reached a good outcome* (most outcomes are off-thread and unconfirmable).

## 15. Leakage controls — verification

### 15.1 Design (documented in `analysis/data_split_plan.md`)
- One conversation = one example (validator enforces conv_id uniqueness).
- **Golden examples are reserved for eval only**: `evaluation/golden_split_ids.csv`
  lists the 200 conv_ids, `data_split=golden_eval`. Rule: these conversations
  must never enter retrieval index / training in Phase 3. No retrieval index or
  model exists yet, so **"golden not used as retrieval/training" is currently
  satisfied trivially and is enforced going forward by the manifest + a
  dedicated `data_split` column**; it is a policy + manifest now, not a
  runtime-computable guarantee against a corpus we do not have yet.
- Inputs exclude future: `includes_future_context=False` everywhere;
  `prior_context` is strictly pre-target; `reference_brand_reply` is stored in
  a separate column, not in `prior_context`.
- The 50 Phase-1 audit conversations are excluded from the pool (eligible
  pool 16,402).

### 15.2 Verification actually run (`analysis/scripts/validate_golden_set.py`)
- 200 rows; example_id ↔ conv_id consistent; no duplicate `conv_id`
  (conversation-level separation).
- **Duplicate customer-message check**: 0 exact duplicates via the worksheet
  dedup; validator's normalized-message check finds **0 near-duplicate target
  messages** among the 200.
- Audit-overlap check: 0 of the 50 audit conversations present.
- Cache checks: all conv_ids and target_tweet_ids exist in the source parquet;
  stored `target_created_ts` matches cached timestamps.
- Enum + cross-field validation incl. `escalation_reason` emptiness rules.
- **Validator PASSED, exit code 0.**

### 15.3 Limits of the guarantee (honest)
Near-duplicate detection is string-normalization only; **semantic
near-duplicates (paraphrases) are not measured**. Whether future Phase-3
retrieval/training accidentally reuses golden ids is **not yet verifiable**
here — nothing indexes or trains anything yet, so exclusion is enforced by the
manifest and `data_split` convention, and Phase 3 must re-run the same
validator (re-runnable) once a corpus exists. No stronger claim is made than
what the validator implements.

## 16. What critical reviewers will challenge

1. **Labels are assistant-drafted, not human-verified** — the strongest
   challenge. No IAA, one draft-author, no second human pass. Answer: this is
   disclosed as the set's central limitation (§4, §10); the set is titled
   "AWAITING HUMAN REVIEW"; confidence/ambiguity/UNCERTAIN machinery exists so
   the eventual human pass can focus on 58 flagged rows + low-confidence rows.
2. **Small/uneven classes**: `account_or_security` 3, `seat_or_upgrade` 7 —
   too few to evaluate those routes reliably. Answer: intentional retention
   (quota-protected); evaluation must report per-class with confidence or
   aggregate rare intents; do not claim per-class conclusions.
3. **Inference vs. measurement**: the `resolution_observable` categories
   (e.g., `HANDOFF_OUTCOME_OFF_THREAD`) are annotator judgement applied on top
   of observable routing, not measured outcomes — documented, not disguised.
4. **Sampling prior ≠ label distribution**: quota buckets are sampling strata;
   the final labels drift (e.g., security bucket → noise/website). Reported as
   a crosstab (`taxonomy_analysis.md` §3), not hidden.
5. **Historic-reply grounding**: the set evidences *what* BA said/handled, not
   *whether it worked*; only ~16% in-thread closure is observable (audit).
   Evaluation must not claim a "resolution rate".
6. **2017 data**: policies, contact channels and the EC program differ today;
   the set is a historical evaluation slab, not current best-practice.
7. **`noise` is 21.5%**: a classifier could trivially "score well" by routing
   everything to noise; the evaluator must treat noise as a real class with
   precision requirements, and reviewers should weight it by pool prevalence.

---

## Appendix A — Reproducibility & provenance
- Sampling: `analysis/scripts/build_golden_worksheet.py` (`seed=2026`,
  `TARGET_N=200`); pool evidence in `analysis/golden_sampling_summary.json`;
  audit seed (Phase-1) `137`.
- Labels: `evaluation/_labels.tsv` (TSV, 11 columns, 200 rows).
- Assembly: `analysis/scripts/assemble_golden_set.py` → `golden_set.csv` /
  `golden_set.jsonl` / `golden_split_ids.csv`.
- Validation: `analysis/scripts/validate_golden_set.py`
  (`python -X utf8 analysis\scripts\validate_golden_set.py` → **PASSED**).

## Appendix B — Artifact consistency
The following were cross-checked for agreement (counts, labels, enums:
`noise_or_off_topic_or_ack`, `INTENT_LABELS`, `ESCALATE/UNCERTAIN/AUTO_HANDLE`,
reasons, percentages):
`analysis/intent_taxonomy.md` ✓ · `analysis/intent_taxonomy.csv` ✓ ·
`analysis/escalation_taxonomy.csv` ✓ · `analysis/taxonomy_analysis.md` ✓ ·
`analysis/data_split_plan.md` ✓ · `evaluation/golden_set.csv` ✓ ·
`evaluation/golden_set_README.md` ✓ · this report ✓.
Any discrepancy found during the pass was fixed in the artifacts, not papered
over.

## Appendix C — Phase-1 integrity
British_Airways selection, the Phase-1 scorecard, the qualitative-audit
conclusion and Phase-1 metrics were **not modified** in Phase 2. They are
referenced as evidence only. No factual inconsistency requiring a correction
was discovered.

## Appendix D — Phase 2.1 follow-up (label audit & review queue)

After this report, a **Phase 2.1 human-review preparation pass** was performed
(no gold label overwritten). It produced:
`evaluation/golden_set_review_queue.csv` (200 rows × 17 cols, `human_final_*`
blank), `evaluation/HUMAN_REVIEW_GUIDE.md`,
`analysis/PHASE2_1_LABEL_AUDIT.md`, and corpus candidate files
(`analysis/candidate_examples/*.csv`). Headline proposals (reviewer to decide):
rename `contact_or_human_escalation_request` → `complaint_or_human_assistance`
with a boundary re-cut (pure contact-info → `information_or_policy`; sarcasm →
noise), `noise_or_off_topic_or_ack` → `non_support_or_acknowledgement`,
`account_or_security` → `account_access_or_security` (wider), keep
`seat_or_upgrade`; apply a single operational escalation rule (AUTO_HANDLE iff
a safe autonomous answer exists from public evidence — not mirroring BA's
"DM us" habit). The dataset remains **assistant-drafted / human-unverified
proposed gold set** until that human review completes.