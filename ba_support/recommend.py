"""Golden-set review recommendation artifact builder (Phase 2.1 completion).

Reads `evaluation/golden_set_review_queue.csv` and writes
`evaluation/golden_set_recommendations.csv` (the assistant's recommended
decision per row, explicitly labelled ASSISTANT-RECOMMENDED / AWAITING
HUMAN CONFIRMATION) plus `evaluation/review_summary.md`.

Hard rules:
  - `human_final_*` fields are NEVER populated here;
  - the golden set itself is NEVER modified;
  - no claim of human review is made anywhere.
"""

import pandas as pd

from . import paths
from .taxonomy import RENAME_PROPOSALS

STATUS = "ASSISTANT-RECOMMENDED / AWAITING HUMAN CONFIRMATION"

REVIEW_COLUMNS = [
    "example_id", "review_priority", "customer_message",
    "current_intent", "recommended_intent",
    "current_escalation", "recommended_escalation",
    "recommended_escalation_reason",
    "ambiguity_flag", "intent_review_status", "escalation_review_status",
    "status",
    "human_decision_accept", "human_final_intent", "human_final_escalation",
    "human_notes",
]


def load_queue() -> pd.DataFrame:
    return pd.read_csv(paths.REVIEW_QUEUE_CSV, dtype=str, keep_default_na=False)


HUMAN_COLUMNS = ["human_decision_accept", "human_final_intent",
                 "human_final_escalation", "human_notes"]


def build_recommendations() -> pd.DataFrame:
    q = load_queue()
    rows = []
    for _, r in q.iterrows():
        rows.append({
            "example_id": r["example_id"],
            "review_priority": r["review_priority"],
            "customer_message": r["customer_message"],
            "current_intent": r["current_intent"],
            "recommended_intent": r["proposed_intent"],
            "current_escalation": r["current_escalation"],
            "recommended_escalation": r["proposed_escalation"],
            "recommended_escalation_reason": r["proposed_escalation_reason"],
            "ambiguity_flag": r["ambiguity_flag"],
            "intent_review_status": r["intent_review_status"],
            "escalation_review_status": r["escalation_review_status"],
            "status": STATUS,
            "human_decision_accept": "",
            "human_final_intent": "",
            "human_final_escalation": "",
            "human_notes": "",
        })
    out = pd.DataFrame(rows).sort_values(
        ["review_priority", "example_id"],
        key=lambda s: s.map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}) if s.name == "review_priority" else s,
    ).reset_index(drop=True)
    # Never blank a human review that is already on disk: carry forward any
    # recorded `human_final_*` / acceptance decision by example_id so that
    # run_eval's regeneration of the machine-drafted artifact cannot destroy it.
    if paths.RECOMMENDATIONS_CSV.exists():
        prev = pd.read_csv(paths.RECOMMENDATIONS_CSV, dtype=str,
                           keep_default_na=False).set_index("example_id")
        for col in HUMAN_COLUMNS:
            vals = prev[col].astype(str).to_dict()
            out[col] = out["example_id"].map(
                lambda e: vals.get(str(e), ""))
    out.to_csv(paths.RECOMMENDATIONS_CSV, index=False, encoding="utf-8")
    return out


def write_review_summary(recommendations: pd.DataFrame) -> str:
    n = len(recommendations)
    n_int_chg = int((recommendations["recommended_intent"]
                     != recommendations["current_intent"]).sum())
    n_esc_chg = int((recommendations["recommended_escalation"]
                     != recommendations["current_escalation"]).sum())
    prio = recommendations["review_priority"].value_counts().to_dict()
    esc = recommendations["recommended_escalation"].value_counts().to_dict()
    renamed = recommendations["recommended_intent"].map(
        lambda x: RENAME_PROPOSALS.get(x, x)).value_counts()

    n_human = int((recommendations["human_final_intent"] != "").sum())
    n_rejected = int((recommendations["human_decision_accept"] == "FALSE").sum())

    state = ("Every recommendation is labelled "
             "`ASSISTANT-RECOMMENDED / AWAITING HUMAN CONFIRMATION`. No `human_final_*` "
             "field is populated. The golden set and its draft labels are unchanged.**"
             if n_human == 0 else
             f"**Human review is recorded: `human_final_intent` populated for "
             f"{n_human}/{n} rows and `human_decision_accept`=FALSE on "
             f"{n_rejected} of them (see `evaluation/golden_set_reviewed.csv`, "
             f"produced by `apply_human_review.py`). The canonical golden set "
             f"(`evaluation/golden_set.csv`) now carries those final decisions — "
             f"applied by `analysis/scripts/finalize_golden_set.py` — while the "
             f"pre-review assistant draft stays archived in `evaluation/_labels.tsv`, "
             f"`evaluation/golden_set_review_queue.csv` and "
             f"`evaluation/golden_set_recommendations.pre_human_review_backup.csv`.**")

    review_or_pending = ("" if n_human else " (awaiting human decision)")
    lines = [
        "# Golden-Set Review Summary (Phase 2.1)",
        "",
        f"- Examples reviewed: **{n}** (all of the 200-example golden set).",
        f"- Review priority: HIGH {prio.get('HIGH', 0)} / MEDIUM {prio.get('MEDIUM', 0)} / "
        f"LOW {prio.get('LOW', 0)}.",
        f"- Intent changes proposed vs shipped draft: **{n_int_chg}**.",
        f"- Escalation changes proposed vs shipped draft: **{n_esc_chg}**.",
        f"- Recommended escalation mix: AUTO_HANDLE {esc.get('AUTO_HANDLE', 0)} / "
        f"ESCALATE {esc.get('ESCALATE', 0)} / UNCERTAIN {esc.get('UNCERTAIN', 0)}.",
        "",
        state,
        "",
        "## Taxonomy renames" + review_or_pending,
        "",
        "| current label | canonical label | examples touched |",
        "|---|---|---|",
    ]
    for cur, new in RENAME_PROPOSALS.items():
        count = int((recommendations["recommended_intent"].map(
            lambda x: x == new)).sum())
        lines.append(f"| `{cur}` | `{new}` | {count} recommended rows |")
    if n_human:
        lines += [
            "",
            "## Final state",
            "",
            "The recorded human-final decisions are now the canonical gold: `intent` "
            "and `escalation_label` in `evaluation/golden_set.csv` equal the human "
            "finals (the three renamed classes stored in their legacy spelling and "
            "mapped at eval time by `ba_support/taxonomy.to_canonical`). Final "
            "escalation mix: AUTO_HANDLE / ESCALATE / UNCERTAIN match "
            "`golden_set_reviewed.csv`. No independent (second) annotator ran, so no "
            "inter-annotator agreement is claimed.",
        ]
    else:
        lines += [
            "",
            "## How to act",
            "",
            "1. Open `evaluation/golden_set_recommendations.csv` and scan by "
            "`review_priority`. For each row set `human_decision_accept` = "
            "ACCEPT/REJECT and, when rejecting, fill `human_final_intent` / "
            "`human_final_escalation` + `human_notes`.",
            "2. Apply the taxonomy renames ONLY after you confirm them, and re-cut "
            "boundaries (`contact → information/noise`, etc.) as the "
            "`review_reason` column notes.",
            "3. Once `human_final_*` is populated for every row, finalize the golden "
            "set with `analysis/scripts/finalize_golden_set.py`, then re-run the "
            "validator and the evaluation.",
            "",
            "Until a human fills `human_final_*` for every row, the set remains "
            "**assistant-drafted / human-unverified proposed gold set**.",
        ]
    text = "\n".join(lines)
    paths.REVIEW_SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    paths.REVIEW_SUMMARY_MD.write_text(text, encoding="utf-8")
    return text


def main():
    recs = build_recommendations()
    write_review_summary(recs)
    print(f"Wrote {paths.RECOMMENDATIONS_CSV}: {len(recs)} rows "
          f"({STATUS}).")
    n_int = int((recs["recommended_intent"] != recs["current_intent"]).sum())
    n_esc = int((recs["recommended_escalation"] != recs["current_escalation"]).sum())
    print(f"intent changes: {n_int}; escalation changes: {n_esc}")
    print(f"human_final fields all blank: "
          f"{bool(((recs['human_final_intent']=='') & (recs['human_final_escalation']=='')).all())}")


if __name__ == "__main__":
    main()