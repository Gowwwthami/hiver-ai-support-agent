"""Metric aggregation and result serialisation for the evaluation harness.

Honesty rules:
  - every number is computed here from actually-run predictions;
  - class imbalance is surfaced (macro F1 + per-class table + support counts);
  - escalation safety (false AUTO_HANDLE on gold-ESCALATE/UNCERTAIN) is
    reported explicitly and prioritised over raw routing accuracy;
  - judge outputs are returned verbatim and attributed to their backend.
"""

import json

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report,
                             confusion_matrix, f1_score, precision_score,
                             recall_score)

from . import taxonomy


def classification_metrics(y_true: list[str], y_pred: list[str],
                           labels: list[str] | None = None) -> dict:
    labels = labels or taxonomy.INTENT_ORDER
    # only classes present in y_true keep their macro vote (mirrors sklearn macro)
    present = sorted(set(y_true))
    macro = f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)
    weighted = f1_score(y_true, y_pred, average="weighted", labels=labels,
                        zero_division=0)
    micro = f1_score(y_true, y_pred, average="micro", labels=labels, zero_division=0)
    acc = accuracy_score(y_true, y_pred)

    report_rows = []
    for lab in present:
        p = precision_score(y_true, y_pred, labels=[lab], average="micro",
                            zero_division=0)
        r = recall_score(y_true, y_pred, labels=[lab], average="micro",
                         zero_division=0)
        f = f1_score(y_true, y_pred, labels=[lab], average="micro",
                     zero_division=0)
        report_rows.append({
            "intent": lab,
            "support": int(y_true.count(lab)),
            "precision": round(float(p), 4),
            "recall": round(float(r), 4),
            "f1": round(float(f), 4),
        })
    report_rows.sort(key=lambda x: -x["support"])

    conf = confusion_matrix(y_true, y_pred, labels=labels)
    return {
        "accuracy": round(float(acc), 4),
        "macro_f1": round(float(macro), 4),
        "weighted_f1": round(float(weighted), 4),
        "micro_f1": round(float(micro), 4),
        "n": len(y_true),
        "per_class": report_rows,
        "confusion_matrix": {
            "labels": labels,
            "matrix": conf.astype(int).tolist(),
        },
        "missing_classes_in_prediction": sorted(set(labels) - set(y_pred))
        if len(set(labels) - set(y_pred)) else [],
    }


def escalation_metrics(gold: list[str], pred: list[str],
                       gold_reasons: list[str] | None = None,
                       pred_reasons: list[str] | None = None) -> dict:
    """Routing metrics. Gold UNCERTAIN counts as 'not auto' for safety; a
    prediction of AUTO_HANDLE on a gold-{ESCALATE, UNCERTAIN} row UNSAFE."""
    unsafe = [(g, p) for g, p in zip(gold, pred)
              if g in {"ESCALATE", "UNCERTAIN"} and p == "AUTO_HANDLE"]
    false_esc = [(g, p) for g, p in zip(gold, pred)
                 if g == "AUTO_HANDLE" and p in {"ESCALATE", "UNCERTAIN"}]
    auto_prec = precision_score(
        [1 if g == "AUTO_HANDLE" else 0 for g in gold],
        [1 if p == "AUTO_HANDLE" else 0 for p in pred],
        zero_division=0)
    auto_rec = recall_score(
        [1 if g == "AUTO_HANDLE" else 0 for g in gold],
        [1 if p == "AUTO_HANDLE" else 0 for p in pred],
        zero_division=0)
    auto_f1 = f1_score(
        [1 if g == "AUTO_HANDLE" else 0 for g in gold],
        [1 if p == "AUTO_HANDLE" else 0 for p in pred],
        zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(gold, pred)), 4),
        "false_auto_handle_rate": round(len(unsafe) / max(1, len(gold)), 4),
        "n_false_auto_handle": int(len(unsafe)),
        "false_escalation_rate": round(len(false_esc) / max(1, len(gold)), 4),
        "n_false_escalation": int(len(false_esc)),
        "auto_handle_precision": round(float(auto_prec), 4),
        "auto_handle_recall": round(float(auto_rec), 4),
        "auto_handle_f1": round(float(auto_f1), 4),
        "confusion": {"AUTO_HANDLE": int(gold.count("AUTO_HANDLE")),
                      "ESCALATE": int(gold.count("ESCALATE")),
                      "UNCERTAIN": int(gold.count("UNCERTAIN"))},
    }


def aggregate_judge(judgements: list[dict]) -> dict:
    if not judgements:
        return {}
    means = {}
    for k in ("correctness", "groundedness", "completeness", "overall"):
        means[k] = round(float(np.mean([j.get(k, 0) for j in judgements])), 4)
        means[f"{k}_n"] = int(len(judgements))
    means["hallucination_rate"] = round(
        float(np.mean([bool(j.get("hallucination", False)) for j in judgements])), 4)
    esc_ok = [bool(j.get("escalation_appropriate", False)) for j in judgements]
    means["escalation_appropriate_rate"] = round(float(np.mean(esc_ok)), 4)
    backends = {}
    for j in judgements:
        b = j.get("judge_backend", "offline")
        backends[b] = backends.get(b, 0) + 1
    means["judge_backends_used"] = backends
    return means


def imbalance_summary(y_true: list[str]) -> dict:
    counts = {lab: int(y_true.count(lab)) for lab in set(y_true)}
    total = max(1, len(y_true))
    return {
        "counts": counts,
        "share_max_over_min": round(max(counts.values()) / max(1, min(counts.values())), 2)
        if len(counts) > 1 else 1.0,
        "zero_support_classes": sorted(set(taxonomy.INTENT_ORDER) - set(counts)),
    }


def dump_results(results: dict, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    cols = df.columns.tolist()
    hdr = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "|" + "---|" * len(cols)
    body = []
    for _, r in df.iterrows():
        body.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join([hdr, sep] + body)