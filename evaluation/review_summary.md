# Golden-Set Review Summary (Phase 2.1)

- Examples reviewed: **200** (all of the 200-example golden set).
- Review priority: HIGH 134 / MEDIUM 6 / LOW 60.
- Intent changes proposed vs shipped draft: **34**.
- Escalation changes proposed vs shipped draft: **16**.
- Recommended escalation mix: AUTO_HANDLE 128 / ESCALATE 69 / UNCERTAIN 3.

**Human review is recorded: `human_final_intent` populated for 200/200 rows and `human_decision_accept`=FALSE on 19 of them (see `evaluation/golden_set_reviewed.csv`, produced by `apply_human_review.py`). This artifact preserves each recorded human decision; the golden set and its draft labels are unchanged.**

## Proposed taxonomy renames (awaiting human decision)

| current label | proposed label | examples touched |
|---|---|---|
| `contact_or_human_escalation_request` | `complaint_or_human_assistance` | 21 recommended rows |
| `noise_or_off_topic_or_ack` | `non_support_or_acknowledgement` | 5 recommended rows |
| `account_or_security` | `account_access_or_security` | 3 recommended rows |

## How to act

1. Open `evaluation/golden_set_recommendations.csv` and scan by `review_priority`. For each row set `human_decision_accept` = ACCEPT/REJECT and, when rejecting, fill `human_final_intent` / `human_final_escalation` + `human_notes`.
2. Apply the taxonomy renames ONLY after you confirm them, and re-cut boundaries (`contact → information/noise`, etc.) as the `review_reason` column notes.
3. The draft error rate vs human finals is computable once `human_final_*` is populated (see `evaluation/HUMAN_REVIEW_GUIDE.md` §After review).

Until a human fills `human_final_*` for every row, the set remains **assistant-drafted / human-unverified proposed gold set**.