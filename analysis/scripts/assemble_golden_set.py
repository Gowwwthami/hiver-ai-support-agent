"""Assemble the golden evaluation set.

Merges the sampled candidates worksheet (evaluation/_candidates_worksheet.csv)
with the hand labels (evaluation/_labels.tsv) into
evaluation/golden_set.csv, evaluation/golden_set.jsonl and
evaluation/golden_split_ids.csv.

Integrity checks run before anything is written: exact example_id match,
no duplicates, and enum validation against _taxonomy. On any failure the
script exits non-zero without producing outputs.
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation"
WORKSHEET = EVAL / "_candidates_worksheet.csv"
LABELS = EVAL / "_labels.tsv"
OUT_CSV = EVAL / "golden_set.csv"
OUT_JSONL = EVAL / "golden_set.jsonl"
OUT_SPLIT_IDS = EVAL / "golden_split_ids.csv"

sys.path.insert(0, str(ROOT / "analysis" / "scripts"))
from _taxonomy import ENUM_MAP, LABEL_COLUMNS  # noqa: E402

SAMPLE_SOURCE = "conversations_parquet_2017_twcs_british_airways"
DATA_SPLIT = "golden_eval"
LEAKAGE_OK = True
INCLUDES_FUTURE = False

OUTPUT_COLUMNS = [
    "example_id",
    "conv_id",
    "target_tweet_id",
    "target_author_id",
    "target_created_ts",
    "customer_message",
    "prior_context",
    "intent",
    "intent_confidence",
    "secondary_intent",
    "resolution_observable",
    "resolution_type",
    "escalation_label",
    "escalation_reason",
    "noise_flag",
    "ambiguity_flag",
    "annotator_notes",
    "sampling_bucket_primary",
    "is_conflict",
    "sample_slice",
    "is_first_inbound",
    "target_position",
    "n_inbound_total",
    "conv_tweets_total",
    "n_brand_tweets_total",
    "message_chars",
    "message_words",
    "has_brand_reply_after",
    "reference_brand_reply",
    "data_split",
    "sample_source",
    "includes_future_context",
    "leakage_safe",
]


def validate_enums(df: pd.DataFrame):
    errors = []
    for col in LABEL_COLUMNS:
        allowed = ENUM_MAP[col]
        bad = set(df[col].dropna().unique()) - set(allowed)
        for v in sorted(bad, key=str):
            errors.append(f"{col}: invalid value {v!r}")
    # cross-field rules
    for _, r in df.iterrows():
        if r["escalation_label"] == "AUTO_HANDLE" and r["escalation_reason"] != "":
            errors.append(
                f"{r['example_id']}: AUTO_HANDLE but escalation_reason='{r['escalation_reason']}'"
            )
        if r["escalation_label"] in ("ESCALATE", "UNCERTAIN") and r["escalation_reason"] == "":
            errors.append(
                f"{r['example_id']}: {r['escalation_label']} but escalation_reason is empty"
            )
        if r["escalation_label"] == "":
            errors.append(f"{r['example_id']}: escalation_label empty")
        if r["noise_flag"] == "TRUE" and r["intent"] != "noise_or_off_topic_or_ack":
            errors.append(
                f"{r['example_id']}: noise_flag TRUE but intent='{r['intent']}'"
            )
    return errors


def main():
    ws = pd.read_csv(WORKSHEET, dtype=str, keep_default_na=False)
    lb = pd.read_csv(LABELS, sep="\t", dtype=str, keep_default_na=False)

    ws_ids = set(ws["example_id"])
    lb_ids = set(lb["example_id"])
    problems = []
    if ws_ids != lb_ids:
        problems.append(
            f"id mismatch: in worksheet not labels={sorted(ws_ids - lb_ids)}, "
            f"in labels not worksheet={sorted(lb_ids - ws_ids)}"
        )
    if ws["example_id"].duplicated().any():
        problems.append("duplicate example_id in worksheet")
    if lb["example_id"].duplicated().any():
        problems.append("duplicate example_id in labels")
    if ws.shape[0] != 200:
        problems.append(f"worksheet rows={ws.shape[0]} (expected 200)")
    if lb.shape[0] != 200:
        problems.append(f"labels rows={lb.shape[0]} (expected 200)")

    enums = validate_enums(lb)
    if enums:
        problems.extend(enums)

    if problems:
        print("ASSEMBLY FAILED:")
        for p in problems:
            print(" -", p)
        sys.exit(1)

    merged = ws.merge(lb, on="example_id", how="inner", suffixes=("_ws", ""))
    if merged.shape[0] != 200:
        print(f"ASSEMBLY FAILED: merge produced {merged.shape[0]} rows")
        sys.exit(1)

    merged = merged.rename(columns={"bucket_primary": "sampling_bucket_primary"})
    merged["data_split"] = DATA_SPLIT
    merged["sample_source"] = SAMPLE_SOURCE
    merged["includes_future_context"] = INCLUDES_FUTURE
    merged["leakage_safe"] = LEAKAGE_OK

    merged = merged[OUTPUT_COLUMNS].sort_values("example_id").reset_index(drop=True)

    merged.to_csv(OUT_CSV, index=False, encoding="utf-8")
    OUT_JSONL.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in merged.to_dict("records")),
        encoding="utf-8",
    )
    split_ids = merged[["example_id", "conv_id", "target_tweet_id", "data_split"]]
    split_ids.to_csv(OUT_SPLIT_IDS, index=False, encoding="utf-8")

    # summary
    print(f"Wrote {OUT_CSV.name} ({merged.shape[0]} rows)")
    print(f"Wrote {OUT_JSONL.name} ({OUT_JSONL.read_text(encoding='utf-8').count(chr(10)) + 1} lines)")
    print(f"Wrote {OUT_SPLIT_IDS.name}")
    print()
    print("=== intent balance ===")
    print(merged["intent"].value_counts().sort_index().to_string())
    print()
    print("=== escalation ===")
    print(merged["escalation_label"].value_counts().sort_index().to_string())
    print()
    print("=== confidence ===")
    print(merged["intent_confidence"].value_counts().sort_index().to_string())
    print()
    print("=== resolution_observable ===")
    print(merged["resolution_observable"].value_counts().sort_index().to_string())
    print()
    print("=== ambiguity ===")
    print(merged["ambiguity_flag"].value_counts().sort_index().to_string())
    print()
    print("=== noise_flag ===")
    print(merged["noise_flag"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()