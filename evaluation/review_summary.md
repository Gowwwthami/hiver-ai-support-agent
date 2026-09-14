# Golden-Set Review Summary (Phase 2.1)

- Examples reviewed: **200** (all of the 200-example golden set).
- Review priority: HIGH 134 / MEDIUM 6 / LOW 60.
- Intent changes proposed vs shipped draft: **34**.
- Escalation changes proposed vs shipped draft: **16**.
- Recommended escalation mix: AUTO_HANDLE 128 / ESCALATE 69 / UNCERTAIN 3.

**Human review is recorded: `human_final_intent` populated for 200/200 rows and `human_decision_accept`=FALSE on 19 of them (see `evaluation/golden_set_reviewed.csv`, produced by `apply_human_review.py`). The canonical golden set (`evaluation/golden_set.csv`) now carries those final decisions — applied by `analysis/scripts/finalize_golden_set.py` — while the pre-review assistant draft stays archived in `evaluation/_labels.tsv`, `evaluation/golden_set_review_queue.csv` and `evaluation/golden_set_recommendations.pre_human_review_backup.csv`.**

## Taxonomy renames

| current label | canonical label | examples touched |
|---|---|---|
| `contact_or_human_escalation_request` | `complaint_or_human_assistance` | 21 recommended rows |
| `noise_or_off_topic_or_ack` | `non_support_or_acknowledgement` | 5 recommended rows |
| `account_or_security` | `account_access_or_security` | 3 recommended rows |

## Final state

The recorded human-final decisions are now the canonical gold: `intent` and `escalation_label` in `evaluation/golden_set.csv` equal the human finals (the three renamed classes stored in their legacy spelling and mapped at eval time by `ba_support/taxonomy.to_canonical`). Final escalation mix: AUTO_HANDLE / ESCALATE / UNCERTAIN match `golden_set_reviewed.csv`. No independent (second) annotator ran, so no inter-annotator agreement is claimed.