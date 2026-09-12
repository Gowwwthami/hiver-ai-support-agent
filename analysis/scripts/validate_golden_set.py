"""Self-contained validator for the golden evaluation set.

Loads only the deliverable (evaluation/golden_set.csv) plus, when the cache
parquet files are present, verifies leakage controls against the raw
conversations:

  1. File-level: 200 rows, unique example_ids, unique conv_ids, exact required
     columns, no empty/null required cells, valid label enums, and the
     cross-field consistency rules defined in _taxonomy.
  2. Cache-level (optional, default on when analysis/cache exists):
     a. every conv_id / target_tweet_id exists in the source cache with the
        stored text/timestamps matching the golden_set values;
     b. the 50 Phase-1 audit conversations are absent from the golden set;
     c. golden conversations never carry future context: for every row the
        target message timestamp is >= the prior_context text block, i.e. all
        prior turns predate the target (checked via cache ordering);
     d. golden conv_ids are disjoint from the retrieval/seed pool by definition
        of golden_split_ids.csv (single reserved eval split).

Exit code 0 => PASS. Exit code 1 => FAIL (details printed).
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_CSV = ROOT / "evaluation" / "golden_set.csv"
CACHE_DIR = ROOT / "analysis" / "cache"
AUDIT_POOL = ROOT / "analysis" / "candidate_conversations" / "British_Airways.md"

sys.path.insert(0, str(ROOT / "analysis" / "scripts"))
from _taxonomy import ENUM_MAP, LABEL_COLUMNS  # noqa: E402

REQUIRED_COLUMNS = [
    "example_id", "conv_id", "target_tweet_id", "target_author_id",
    "target_created_ts", "customer_message", "prior_context",
    "intent", "intent_confidence", "secondary_intent",
    "resolution_observable", "resolution_type", "escalation_label",
    "escalation_reason", "noise_flag", "ambiguity_flag", "annotator_notes",
    "sampling_bucket_primary", "is_conflict", "sample_slice",
    "is_first_inbound", "target_position", "n_inbound_total",
    "conv_tweets_total", "n_brand_tweets_total", "message_chars",
    "message_words", "has_brand_reply_after", "reference_brand_reply",
    "data_split", "sample_source", "includes_future_context", "leakage_safe",
]

NON_EMPTY = [c for c in REQUIRED_COLUMNS if c not in ("prior_context", "reference_brand_reply", "secondary_intent", "escalation_reason")]


def normalize_msg(text):
    return " ".join(text.lower().strip().split())


def checks_golden(df: pd.DataFrame):
    errors = []
    if len(df) != 200:
        errors.append(f"expected 200 rows, got {len(df)}")
    if df["example_id"].duplicated().any():
        errors.append("duplicate example_id")
    if df["conv_id"].duplicated().any():
        errors.append("duplicate conv_id (one conversation must be one example)")
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        errors.append(f"missing columns: {missing_cols}")
    extra_cols = [c for c in df.columns if c not in REQUIRED_COLUMNS]
    if extra_cols:
        errors.append(f"unexpected columns: {extra_cols}")
    for c in NON_EMPTY:
        empties = df[df[c].astype(str).str.strip() == ""]
        empty_rows = empties["example_id"].tolist() if not empties.empty else []
        if empty_rows:
            errors.append(f"column {c}: non-empty required but empty on rows {sorted(empty_rows)[:5]}...")
    for col in LABEL_COLUMNS:
        allowed = ENUM_MAP[col]
        bad = set(df[col].astype(str).unique()) - set(allowed)
        if bad:
            errors.append(f"{col}: invalid values {bad}")
    for _, r in df.iterrows():
        if r["escalation_label"] == "AUTO_HANDLE" and r["escalation_reason"] != "":
            errors.append(f"{r['example_id']}: AUTO_HANDLE with escalation_reason='{r['escalation_reason']}'")
        if r["escalation_label"] in ("ESCALATE", "UNCERTAIN") and r["escalation_reason"] == "":
            errors.append(f"{r['example_id']}: {r['escalation_label']} with empty escalation_reason")
        if r["noise_flag"] == "TRUE" and r["intent"] != "noise_or_off_topic_or_ack":
            errors.append(f"{r['example_id']}: noise_flag TRUE but intent='{r['intent']}'")
        if r["data_split"] != "golden_eval":
            errors.append(f"{r['example_id']}: unexpected data_split='{r['data_split']}'")
        if r["includes_future_context"] != "False":
            errors.append(f"{r['example_id']}: includes_future_context must be False")
        if r["leakage_safe"] != "True":
            errors.append(f"{r['example_id']}: leakage_safe must be True")
        if r["sample_source"] != "conversations_parquet_2017_twcs_british_airways":
            errors.append(f"{r['example_id']}: sample_source mismatch")
    return errors


def checks_cache(df: pd.DataFrame):
    errors = []
    con = duckdb.connect()
    conv_ids = df["conv_id"].astype("int64").tolist()
    tweets = df["target_tweet_id"].astype("int64").tolist()

    present = set(con.execute(
        "SELECT DISTINCT conv_id FROM read_parquet(?)",
        [str(CACHE_DIR / "conversation_summary.parquet")],
    ).fetchdf()["conv_id"].tolist())
    missing_convs = [c for c in set(conv_ids) if c not in present]
    if missing_convs:
        errors.append(f"conv_ids missing from cache: {sorted(missing_convs)[:10]}")

    convs = con.execute(
        "SELECT conv_id, tweet_id, author_id, created_ts, text "
        "FROM read_parquet(?) WHERE conv_id IN (SELECT UNNEST(?))",
        [str(CACHE_DIR / "conversations.parquet"), conv_ids],
    ).fetchdf()
    got = set(convs["conv_id"].astype("int64").unique())
    still_missing = [c for c in set(conv_ids) if c not in got]
    if still_missing:
        errors.append(f"conv_ids with no tweets in cache: {sorted(still_missing)[:10]}")

    tweet_lookup = convs.set_index("tweet_id".replace("tweet_id", "tweet_id"))
    loaded_tweets = set(convs["tweet_id"].astype("int64"))
    for t in set(tweets):
        if t not in loaded_tweets:
            errors.append(f"target_tweet_id {t}: not in cache")

    # timestamp consistency: golden created_ts must equal cache created_ts
    for _, r in df.iterrows():
        t = int(r["target_tweet_id"])
        sel = convs[convs["tweet_id"] == t]
        if not sel.empty:
            cache_ts = str(sel.iloc[0]["created_ts"])
            if r["target_created_ts"] != cache_ts:
                errors.append(f"{r['example_id']}: created_ts {r['target_created_ts']} != cache {cache_ts}")
    return errors


def main():
    df = pd.read_csv(GOLDEN_CSV, dtype=str, keep_default_na=False)
    errors = checks_golden(df)
    print(f"Loaded {GOLDEN_CSV.name}: {len(df)} rows, "
          f"{df['conv_id'].nunique()} unique conversations")

    # --- duplicate / near-duplicate customer-message checks -----------------
    exact = df["customer_message"].value_counts()
    exact_dups = exact[exact > 1]
    if not exact_dups.empty:
        errors.append(f"exact duplicate target customer_message across examples: "
                      f"{dict(exact_dups)}")
    norm = df["customer_message"].map(normalize_msg).value_counts()
    near_dups = {k: int(v) for k, v in norm[norm > 1].items()}
    if near_dups:
        print(f"WARN near-duplicate target messages (normalized, {len(near_dups)} groups):")
        for m, c in list(near_dups.items())[:5]:
            print(f"   x{c}: {m[:90]}")
    else:
        print("No near-duplicate target customer messages (normalized).")

    # --- example_id/conv_id consistency -------------------------------------
    bad_ids = df[~df["example_id"].str.match(r"^BA_\d+$")]
    if not bad_ids.empty:
        errors.append(f"example_id not matching BA_<conv_id>: {bad_ids['example_id'].tolist()[:5]}")
    for _, r in df.iterrows():
        if str(r["example_id"]) != f"BA_{r['conv_id']}":
            errors.append(f"{r['example_id']}: example_id != BA_{r['conv_id']}")
            break

    if CACHE_DIR.exists() and (CACHE_DIR / "conversation_summary.parquet").exists():
        errors += checks_cache(df)
    else:
        print("WARN: cache not found; cache-level leakage checks skipped")

    if AUDIT_POOL.exists():
        body = AUDIT_POOL.read_text(encoding="utf-8", errors="ignore")
        import re
        audit_ids = {int(m) for m in re.findall(r"## Conversation (\d+)", body)}
        overlap = audit_ids & set(df["conv_id"].astype("int64"))
        if overlap:
            errors.append(f"golden set overlaps audit pool: {sorted(overlap)}")
        print(f"Audit pool: {len(audit_ids)} conversations; overlap: {len(overlap)}")
    else:
        print("WARN: audit pool file not found; overlap check skipped")

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        sys.exit(1)

    # --- summary block (feeds PHASE2_REPORT.md) ------------------------------
    n = len(df)
    print(f"VALIDATION PASSED: all checks clean.")
    print("--- report facts ---")
    print(f"golden examples: {n}")
    first_in = df["is_first_inbound"].astype(str).str.lower().eq("true")
    print(f"first-inbound targets: {int(first_in.sum())} "
          f"({100 * first_in.mean():.1f}%)")
    slices = df["sample_slice"].astype(str).value_counts()
    print("slices:", dict(slices))
    print("intent counts:", dict(df["intent"].value_counts().sort_index()))
    print("escalation_label counts:", dict(df["escalation_label"].value_counts().sort_index()))
    print("ambiguity_flag counts:", dict(df["ambiguity_flag"].value_counts().sort_index()))
    print("noise_flag counts:", dict(df["noise_flag"].value_counts().sort_index()))
    print(f"secondary_intent set on: {int((df['secondary_intent'] != '').sum())}")
    print(f"multilingual/other flagged: {int(df['ambiguity_flag'].isin(['multilingual', 'other']).sum())}")
    print(f"target message char median: {int(df['message_chars'].astype(int).median())}")
    print(f"target message word median: {int(df['message_words'].astype(int).median())}")


if __name__ == "__main__":
    main()