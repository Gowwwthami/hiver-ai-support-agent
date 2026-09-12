"""Apply human-reviewed final labels and report draft-vs-human agreement.

Usage:
    python -X utf8 analysis/scripts/apply_human_review.py [--annotator2 PATH]

Reads `evaluation/golden_set_recommendations.csv` after a human has filled the
`human_decision_accept` / `human_final_intent` / `human_final_escalation` /
`human_notes` columns, and:

  1. writes `evaluation/golden_set_reviewed.csv` (recommendations + the recorded
     human finals; the golden set itself is NEVER modified);
  2. computes the assistant-draft error rate vs the human finals (intent and
     escalation), and the most-confused intent pairs;
  3. with `--annotator2 PATH`, computes inter-annotator agreement between two
     independent human reviewers (exact agreement + Cohen's kappa for intent).

Honesty rules: this script can ONLY report what was actually filled in. If no
human rows exist it reports "HUMAN REVIEW PENDING" and does not invent metrics.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ba_support import paths  # noqa: E402
from ba_support.taxonomy import to_canonical  # noqa: E402

REVIEWED_CSV = paths.EVAL_DIR / "golden_set_reviewed.csv"


def load_recommendations() -> pd.DataFrame:
    rec = pd.read_csv(paths.RECOMMENDATIONS_CSV, dtype=str, keep_default_na=False)
    if "human_decision_accept" not in rec.columns or \
            "human_final_intent" not in rec.columns or \
            "human_final_escalation" not in rec.columns:
        raise SystemExit("recommendations CSV lacks human_final_* columns; "
                         "re-run ba_support/recommend.py first")
    return rec


def reviewed_mask(rec: pd.DataFrame) -> pd.Series:
    return (
        (rec["human_final_intent"] != "") | (rec["human_final_escalation"] != "")
        | (rec["human_decision_accept"].str.strip() != "")
    )


def intent_error_rate(draft, final) -> dict:
    n = len(draft)
    acc = float((np.array(draft) == np.array(final)).mean()) if n else 0.0
    errs = pd.DataFrame({"draft": draft, "final": final})
    pairs = (errs[errs["draft"] != errs["final"]]
             .value_counts().head(8).to_dict())
    pairs = {f"{k[0]} -> {k[1]}": int(v) for k, v in pairs.items()}
    return {
        "n_endpoints": int(n),
        "agreement": round(1.0 - acc, 4) if n else None,
        "draft_error_rate": round(1.0 - acc, 4) if n else None,
        "most_common_draft_errors": pairs,
    }


def escalation_metrics(draft, final) -> dict:
    n = len(final)
    unsafe = sum(1 for d, f in zip(draft, final)
                 if f in {"ESCALATE", "UNCERTAIN"} and d == "AUTO_HANDLE")
    return {
        "n_endpoints": int(n),
        "draft_error_rate": round(
            1.0 - float(np.mean([d == f for d, f in zip(draft, final)])), 4) if n else None,
        "n_draft_auto_on_human_escalate": int(unsafe),
        "n_human_escalate": int(sum(1 for f in final if f in {"ESCALATE", "UNCERTAIN"})),
    }


def iaa(rec: pd.DataFrame, ann2: pd.DataFrame) -> dict:
    m = rec.merge(ann2[["example_id", "human_final_intent", "human_final_escalation"]],
                  on="example_id", suffixes=("_a", "_b"))
    m = m[(m["human_final_intent_a"] != "") & (m["human_final_intent_b"] != "")]
    if len(m) == 0:
        return {"agreement_computable": False, "n_shared": 0,
                "reason": "no shared human finals between the two annotator files"}
    intent_exact = float((m["human_final_intent_a"] == m["human_final_intent_b"]).mean())
    esc_exact = float((m["human_final_escalation_a"] == m["human_final_escalation_b"]).mean())
    union_labs = sorted(set(m["human_final_intent_a"]) | set(m["human_final_intent_b"]))
    # sparse kappa over the intent classes actually used (sklearn requires >=2)
    kappa = float(cohen_kappa_score(
        m["human_final_intent_a"], m["human_final_intent_b"], labels=union_labs)) \
        if len(union_labs) >= 2 else None
    return {
        "agreement_computable": True,
        "n_shared": int(len(m)),
        "intent_exact_agreement": round(intent_exact, 4),
        "escalation_exact_agreement": round(esc_exact, 4),
        "intent_cohen_kappa": round(kappa, 4) if kappa is not None else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotator2", default=None,
                    help="second completed recommendations CSV (same schema) for IAA")
    args = ap.parse_args()

    rec = load_recommendations()
    reviewed = reviewed_mask(rec)
    n_reviewed = int(reviewed.sum())

    if n_reviewed == 0 or not args.annotator2:
        pass  # decide reporting below

    if n_reviewed == 0:
        print(f"{n_reviewed}/{len(rec)} rows reviewed.")
        print("STATUS: HUMAN REVIEW PENDING — no human_final_* values exist.")
        print(f"Open {paths.RECOMMENDATIONS_CSV} and fill human_decision_accept / "
              f"human_final_intent / human_final_escalation / human_notes.")
        return

    rev = rec[reviewed].copy()
    rev[["human_final_intent", "human_final_escalation"]] = rev[
        ["human_final_intent", "human_final_escalation"]].astype(str)
    rev["human_final_reason"] = rev["human_notes"].astype(str)

    intent_metrics = intent_error_rate(
        rev["recommended_intent"].map(to_canonical).tolist(),
        rev["human_final_intent"].map(to_canonical).tolist())
    esc_metrics = escalation_metrics(
        rev["recommended_escalation"].tolist(),
        rev["human_final_escalation"].tolist())

    print(f"Reviewed: {n_reviewed}/{len(rec)} rows ({100 * n_reviewed / len(rec):.1f}%).")
    print(f"[intent] draft error rate vs human finals: "
          f"{intent_metrics['draft_error_rate']}")
    print("  most common draft->human errors:", intent_metrics["most_common_draft_errors"])
    print(f"[escalation] draft error rate vs human finals: "
          f"{esc_metrics['draft_error_rate']}; draft-AUTO on human-ESCALATE: "
          f"{esc_metrics['n_draft_auto_on_human_escalate']}")

    if args.annotator2:
        ann2 = pd.read_csv(args.annotator2, dtype=str, keep_default_na=False)
        agreement = iaa(rev, ann2)
        print(f"[IAA] shared={agreement.get('n_shared')} "
              f"intent_exact={agreement.get('intent_exact_agreement')} "
              f"escalation_exact={agreement.get('escalation_exact_agreement')} "
              f"kappa={agreement.get('intent_cohen_kappa')}")
    else:
        print("[IAA] not computed (no --annotator2 file provided)")

    rev.to_csv(REVIEWED_CSV, index=False, encoding="utf-8")
    print(f"Wrote {REVIEWED_CSV} with the {n_reviewed} human-reviewed rows. "
          f"The golden set and the recommendations file are unchanged.")


if __name__ == "__main__":
    main()