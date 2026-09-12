"""Step 1b: Investigate response_tweet_id format and identify brand accounts.

The Kaggle TWCS dataset stores response_tweet_id as either:
  - "<tweet_id>"            (tweet the current row responds to)
  - "<author_id>@<tweet_id>" (same but tagged with original author)

This script:
  - characterizes both possible formats for response_tweet_id
  - characterizes in_response_to_tweet_id
  - identifies candidate brand/support accounts as authors who post many
    outbound tweets that directly reply to inbound customer tweets
  - writes analysis/brand_statistics.csv / .json

Brand identification logic (documented, not assumed):
  A "support account" is an author_id that:
    (a) has > 100 outbound tweets that are recognized as direct replies to
        an inbound customer tweet, AND
    (b) mostly appears in outbound (inbound=False) positions.

Customers are inferred from the accounts on the *other* side of those reply links.
We deliberately do dozens of small DuckDB queries (each fast) rather than one
giant join so it stays memory-light.
"""
import json
import os
import re
import time

import duckdb
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(BASE, "data_extracted", "twcs", "twcs.csv")
OUT_DIR = os.path.join(BASE, "analysis")
os.makedirs(OUT_DIR, exist_ok=True)

MIN_BRAND_TWEETS = 100
MAX_ACCOUNTS_TO_RANK = 125


def main():
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"CREATE TABLE twcs AS SELECT * FROM read_csv_auto('{DATA_PATH}', HEADER=true, SAMPLE_SIZE=1000000)")

    # ---------- response_tweet_id format characterization ----------
    print("=== response_tweet_id formats (top patterns) ===")
    fmt = con.execute("""
        SELECT
            CASE
                WHEN regexp_matches(response_tweet_id, '^[0-9]+$') THEN 'plain_tweet_id'
                WHEN regexp_matches(response_tweet_id, '^[a-zA-Z0-9_]+@[0-9]+$') THEN 'author@tweet_id'
                WHEN response_tweet_id IS NULL THEN 'NULL'
                ELSE 'other'
            END AS fmt,
            count(*) AS n
        FROM twcs
        GROUP BY 1 ORDER BY 2 DESC
    """).df()
    print(fmt.to_string(index=False))

    print("\n=== sample author@tweet_id values ===")
    print(con.execute("""
        SELECT text, response_tweet_id
        FROM twcs WHERE regexp_matches(response_tweet_id, '^[a-zA-Z0-9_]+@[0-9]+$')
        LIMIT 5
    """).df().to_string(index=False))

    # ---------- inbound vs outbound mention stats ----------
    print("\n=== inbound/outbound per-column nulls ===")
    print(con.execute("""
        SELECT inbound,
               count(*) AS n,
               count(response_tweet_id) AS with_response_id,
               count(in_response_to_tweet_id) AS with_in_response_to
        FROM twcs GROUP BY inbound
    """).df().to_string(index=False))

    # ---------- Parse response_tweet_id into (other_author, parent_tweet) ----------
    # resolution: if pattern author@tweet_id, author id is the original parent's author.
    con.execute("""
        CREATE TABLE r AS
        SELECT tweet_id, author_id, inbound, created_at, text,
               in_response_to_tweet_id,
               response_tweet_id,
               CASE
                    WHEN regexp_matches(response_tweet_id, '^[a-zA-Z0-9_]+@[0-9]+$')
                         THEN regexp_extract(response_tweet_id, '^(.*)@([0-9]+)$', 1)
                    ELSE NULL END AS rt_author,
               CASE
                    WHEN regexp_matches(response_tweet_id, '^[a-zA-Z0-9_]+@[0-9]+$')
                         THEN CAST(regexp_extract(response_tweet_id, '^(.*)@([0-9]+)$', 2) AS BIGINT)
                    WHEN regexp_matches(response_tweet_id, '^[0-9]+$')
                         THEN CAST(response_tweet_id AS BIGINT)
                    ELSE NULL END AS rt_tweet
        FROM twcs
    """)

    # ---------- Who are the big outbound authors? ----------
    print("\n=== TOP AUTHORS BY RAW VOLUME ===")
    top = con.execute("""
        SELECT author_id, inbound, count(*) AS n
        FROM twcs GROUP BY author_id, inbound
        ORDER BY n DESC LIMIT 20
    """).df()
    print(top.to_string(index=False))

    # ---------- Brand identification via reply structure ----------
    # A brand tweet is an OUTBOUND tweet whose parent (rt_tweet) is an INBOUND tweet by someone else.
    # Steps:
    #  1. index inbound tweets: tweet_id -> author_id (as customer)
    #  2. join outbound tweets to that index via rt_tweet
    #  3. count such "responses-to-customer" per outbound author
    con.execute("CREATE TABLE inbound_ids AS SELECT tweet_id, author_id FROM twcs WHERE inbound = TRUE")
    con.execute("""
        CREATE TABLE brand_responses AS
        SELECT o.author_id AS brand,
               count(*) AS n_responded_to_customer
        FROM r o
        LEFT JOIN inbound_ids c ON o.rt_tweet = c.tweet_id
        WHERE o.inbound = FALSE AND c.tweet_id IS NOT NULL
        GROUP BY o.author_id
    """)
    print("\n=== AUTHORS RANKED BY RESPONSES-TO-INBOUND-CUSTOMERS (>=100) ===")
    br = con.execute(f"""
        SELECT brand, n_responded_to_customer
        FROM brand_responses WHERE n_responded_to_customer >= {MIN_BRAND_TWEETS}
        ORDER BY n_responded_to_customer DESC
    """).df()
    print(br.to_string(index=False))
    print(f"\nTotal qualifying support-account candidates: {len(br)}")

    br.to_csv(os.path.join(OUT_DIR, "brand_candidates_raw.csv"), index=False)

    # ---------- For top candidates, full per-brand stats ----------
    brands = br["brand"].head(MAX_ACCOUNTS_TO_RANK).tolist()
    rows = []
    for b in brands:
        stats = con.execute("""
            SELECT
                count(*) AS total_tweets,
                count(*) FILTER (WHERE inbound)  AS inbound_tweets,
                count(*) FILTER (WHERE NOT inbound) AS outbound_tweets
            FROM twcs WHERE author_id = ?
        """, [b]).fetchone()
        n_respond_to_customer = int(br[br.brand == b]["n_responded_to_customer"].iloc[0])
        n_unique_customers = con.execute("""
            SELECT count(DISTINCT c.author_id)
            FROM r o JOIN inbound_ids c ON o.rt_tweet = c.tweet_id
            WHERE o.author_id = ? AND o.inbound = FALSE
        """, [b]).fetchone()[0]
        rows.append({
            "brand": b,
            "total_tweets": int(stats[0]),
            "inbound_tweets": int(stats[1]),
            "outbound_tweets": int(stats[2]),
            "tweets_responding_to_customer_tweets": int(n_respond_to_customer),
            "unique_customers_interacted_with": int(n_unique_customers),
            "share_of_tweet_volume": round(float(stats[0]) / 2811774, 4),
        })

    df = pd.DataFrame(rows).sort_values("tweets_responding_to_customer_tweets", ascending=False)
    df.to_csv(os.path.join(OUT_DIR, "brand_statistics.csv"), index=False)
    with open(os.path.join(OUT_DIR, "brand_statistics.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "method": ("brand = author_id with >= %d outbound tweets whose rt_tweet matches an "
                              "inbound tweet; customers = authors on other side of reply links" % MIN_BRAND_TWEETS),
                   "brands": df.to_dict("records")}, f, indent=2, default=str)

    print("\n=== BRAND STATISTICS (ranked) ===")
    print(df.to_string(index=False))
    print(f"\nWrote analysis/brand_statistics.csv and .json  [{round(time.time()-t0,1)}s]")


if __name__ == "__main__":
    main()