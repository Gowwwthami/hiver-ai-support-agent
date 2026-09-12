"""Step 1: Inspect the Customer Support on Twitter dataset schema.

Reads twcs/twcs.csv via DuckDB and reports schema-level facts.
All results are cached to analysis/cache/*.parquet for downstream steps.
"""
import json
import os
import sys
import time

import duckdb
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(BASE, "data_extracted", "twcs", "twcs.csv")
CACHE_DIR = os.path.join(BASE, "analysis", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def main():
    t0 = time.time()
    con = duckdb.connect()

    # --- schema / column metadata (cheap, no full scan needed for dtypes) ---
    schema_sql = f"""
        SELECT column_name, column_type
        FROM (DESCRIBE SELECT * FROM read_csv_auto('{DATA_PATH}', HEADER=true, SAMPLE_SIZE=1000000))
    """
    schema = con.execute(schema_sql).df()
    print("=== COLUMN TYPES (inferred on 1M-row sample) ===")
    print(schema.to_string(index=False))

    # --- row count ---
    n = con.execute(
        f"SELECT count(*) FROM read_csv_auto('{DATA_PATH}', HEADER=true, SAMPLE_SIZE=1000000)"
    ).fetchone()[0]
    print("\n=== TOTAL ROWS:", n)

    # --- full read into DuckDB table once (parquet mid-fly? no -- keep CSV) ---
    # Load once into a DuckDB view we reuse per query via in-memory connection.
    con.execute(f"CREATE TABLE twcs AS SELECT * FROM read_csv_auto('{DATA_PATH}', HEADER=true, SAMPLE_SIZE=1000000)")

    # --- per-column null counts & dup counts ---
    cols = ["tweet_id", "author_id", "inbound", "created_at", "text", "response_tweet_id", "in_response_to_tweet_id"]
    null_sql = " UNION ALL ".join(
        f"SELECT '{c}' AS col, count(*) AS n_null, count(DISTINCT {c}) AS n_unique FROM twcs WHERE {c} IS NULL"
        for c in cols
    )
    nulls = con.execute(null_sql).df().fillna(0)
    print("\n=== NULL COUNTS (for key columns) ===")
    print(nulls.to_string(index=False))

    uniq_sql = " UNION ALL ".join(
        f"SELECT '{c}' AS col, count(DISTINCT {c}) AS n_unique FROM twcs WHERE {c} IS NOT NULL"
        for c in cols
    )
    uniq = con.execute(uniq_sql).df()
    print("\n=== UNIQUE COUNTS (non-null) ===")
    print(uniq.to_string(index=False))

    # --- exact duplicate rows ---
    dup = con.execute(
        "SELECT count(*) AS n_dup_rows FROM (SELECT * FROM twcs GROUP BY ALL HAVING count(*) > 1) t"
    ).fetchone()[0]
    dup_tweet = con.execute(
        "SELECT count(*) AS n_dup_tweet_ids FROM (SELECT tweet_id FROM twcs GROUP BY tweet_id HAVING count(*) > 1) t"
    ).fetchone()[0]
    print("\n=== EXACT DUP ROWS:", dup)
    print("=== ROWS WITH DUP tweet_id:", dup_tweet)

    # --- date range ---
    dr = con.execute("SELECT min(created_at), max(created_at) FROM twcs").fetchone()
    print("\n=== CREATED_AT RANGE:", dr)

    # --- inbound distribution ---
    print("\n=== INBOUND DISTRIBUTION ===")
    print(con.execute("SELECT inbound, count(*) FROM twcs GROUP BY inbound ORDER BY 2 DESC").df().to_string(index=False))

    report = {
        "data_path": DATA_PATH,
        "file_size_bytes": os.path.getsize(DATA_PATH),
        "total_rows": int(n),
        "columns": schema.to_dict("records"),
        "null_counts": nulls.to_dict("records"),
        "unique_counts": uniq.to_dict("records"),
        "exact_dup_rows": int(dup),
        "dup_tweet_id_rows": int(dup_tweet),
        "created_at_min": dr[0],
        "created_at_max": dr[1],
        "runtime_seconds": round(time.time() - t0, 1),
    }
    with open(os.path.join(BASE, "analysis", "schema_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print("\nSaved analysis/schema_report.json")


if __name__ == "__main__":
    main()