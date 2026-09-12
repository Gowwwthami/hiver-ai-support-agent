# HUMAN REVIEW GUIDE — British_Airways Golden Set (Phase 2.1)

You are reviewing the **proposed** labels in
`evaluation/golden_set_review_queue.csv` (200 rows). These labels were drafted
by an assistant (LLM) and have **not** been human-verified. Your review turns
them into genuinely human-verified gold. Nothing here is a black-box answer;
every omission or suggestion in the queue is a proposal, and your decision is
the final one.

**Never use `reference_brand_reply` (the historical BA tweet) as proof that a
label is correct.** The historical response is evidence for later system design
— a record of what BA did — not ground truth for the customer's intent. Decide
from the customer message + `prior_context` only.

For each row, work in this order:

---

## Step 1 — Intent (first)

Ask: **"What is the customer's primary actionable objective?"**

Choose the best single label from `analysis/intent_taxonomy.csv`, with a
`secondary_intent` only if a second objective is genuinely present. See
`analysis/PHASE2_1_LABEL_AUDIT.md` §1–§5 for the boundary questions the
draft-author flagged, in particular:

- contact channel *queries* (e.g. "what number do I call?") → these are the
  proposed **`information_or_policy`**, not a complaint.
- complaint-venting vs. actionable complaint vs. sarcasm/noise → apply the
  working rule: an **actionable ask** or **investigation-worthy grievance**
  = complaint/human-assistance; **pure venting/sarcasm with no request**
  = `non_support_or_acknowledgement`; **praise/thanks/banter** =
  `non_support_or_acknowledgement`.
- account cases: access, management, security all belong to the proposed
  **`account_access_or_security`** (§4).

## Step 2 — Escalation (second; independent of intent)

Ask: **"Could a safe autonomous agent answer this from general policy/historical
evidence WITHOUT accessing customer-specific information or exercising human
judgment?"**

- **AUTO_HANDLE** — yes, a complete and safe public answer exists
  (policy/factual, contact channels, generic troubleshooting, or empathy +
  feedback-capture).
- **ESCALATE** — no: it needs account/booking/household data
  (`account_specific`), money/compensation adjudication
  (`payment_or_refund`/`compensation`), identity/security verification
  (`security_or_identity`), legal/regulatory exposure
  (`legal_or_regulatory_risk`) or a real investigation/complaint routing
  (`complaint_or_human_judgment`).
- **UNCERTAIN** — undecidable from the customer side; the next turn (e.g. DM
  details) would resolve it. Use sparingly.

The historical BA agent's choices are **not** the test. There are rows where BA
asked for a DM but a complete public answer exists (→ AUTO_HANDLE), and rows
where BA answered publicly but the ask genuinely needs a human (→ ESCALATE).
Follow the safety rule above, not the archive.

Set `escalation_reason` accordingly (empty iff AUTO_HANDLE).

## Step 3 — Ambiguity

Mark `ambiguity_flag` (e.g. `multi_intent`, `unclear_intent`, `multilingual`,
`truncated_captured`, `other`) when **reasonable annotators could select
different intents**. Do not "write off" difficult rows to make the set look
cleaner — flag them; the evaluator must report them separately.

## Filling the queue

- Scan by `review_priority` (HIGH → MEDIUM → LOW). HIGH = boundary/conflict/
  account/seat/contact/ambiguous/UNCERTAIN/multi-intent/later-position rows;
  MEDIUM = medium-confident or noisy/sarcastic; LOW = clear cases (verify but
  quickly).
- Fill **only** `human_final_intent`, `human_final_escalation`,
  `human_final_reason`, `human_notes`. Leave `current_*`/`proposed_*` untouched
  (they document the draft vs. the audit).
- Propose rename decisions (labels `complaint_or_human_assistance`,
  `non_support_or_acknowledgement`, `account_access_or_security`) explicitly in
  your final decision: a rename without re-cutting the boundary changes nothing.

### Decision codes per row (use `human_decision_accept`)

For every row record one of:

| code                 | meaning                                                            | fill                                                                   |
|----------------------|--------------------------------------------------------------------|-----------------------------------------------------------------------|
| `KEEP`               | the recommended label and escalation are correct                   | leave the other `human_final_*` columns blank                          |
| `CHANGE INTENT`      | recommended intent is wrong                                        | `human_final_intent` = your label (+ `human_final_reason`)            |
| `CHANGE ESCALATION`  | routing is wrong                                                   | `human_final_escalation` + `human_final_reason`                       |
| `MARK UNCERTAIN`     | you cannot decide intent and/or routing from the customer side     | `human_final_escalation` = `UNCERTAIN` + `human_final_reason`         |
| `REJECT`             | the example itself is unusable (off-topic/duplicated/truncated...) | `human_notes` explaining why; exclude it from downstream metrics       |

## After review

1. Decide the canonical taxonomy verdict (see §2.1 of the audit): applying the
   renames `contact_or_human_escalation_request → complaint_or_human_assistance`,
   `noise_or_off_topic_or_ack → non_support_or_acknowledgement`,
   `account_or_security → account_access_or_security` — with the new boundary
   rules — is the final system's label space.
2. Compute the draft-vs-human statistics and (if a second annotator exists)
   inter-annotator agreement:

   ```bash
   python -X utf8 analysis/scripts/apply_human_review.py                              # stats only
   python -X utf8 analysis/scripts/apply_human_review.py --annotator2 <second_file.csv>  # + IAA
   ```

   The script writes `evaluation/golden_set_reviewed.csv` and reports the draft
   intent/escalation error rate, the most common draft→human errors, and
   Cohen's kappa between annotators. It never fabricates a number: with no
   human rows filled it prints `HUMAN REVIEW PENDING`.
3. Only then may the set (or the reviewed subset) be called
   **human-verified**; until every row has a `human_final_*` value, the set
   remains **assistant-drafted / human-unverified proposed gold set**.
4. Feed the human-approved labels back through `evaluation/run_eval.py` (by
   pointing the harness at the reviewed CSV) so the reported metrics reflect
   the truly verified gold.