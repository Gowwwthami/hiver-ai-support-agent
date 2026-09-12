"""Verify: (1) comma-list response_tweet_id semantics, (2) edge consistency for reconstruction."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import duckdb
import pandas as pd

BASE = r"C:\Users\M.Gowthami\OneDrive\文档\Default Project"
DATA_PATH = BASE + r"\data_extracted\twcs\twcs.csv"

con = duckdb.connect()
con.execute(f"CREATE TABLE twcs AS SELECT * FROM read_csv_auto('{DATA_PATH}', HEADER=true, SAMPLE_SIZE=1000000)")
con.execute("CREATE TABLE inbound_ids AS SELECT tweet_id, author_id FROM twcs WHERE inbound = TRUE")

# --- 1. comma-list: are the ids real tweets that chain to each other? ---
print("=== comma-list example: does each listed id exist as a tweet? ===")
print(con.execute("""
    SELECT t.response_tweet_id, t.tweet_id,
           (SELECT count(*) OVER () ) AS dummy
    FROM twcs t
    WHERE regexp_matches(t.response_tweet_id, '^[0-9]+(,[0-9]+)+$')
    LIMIT 1
""").df().to_string(index=False))

# Take chain '155,157' and '5,7'. Resolve each.
print(con.execute("""
    SELECT tweet_id, author_id, inbound, text
    FROM twcs
    WHERE tweet_id IN (5, 7, 155, 157)
    ORDER BY tweet_id
""").df().to_string(index=False))

print("\n=== for comma-list rows, is LAST id the direct parent? (check last==in_response_to when present) ===")
print(con.execute("""
    SELECT
        count(*) AS n_comma_rows,
        count(*) FILTER (WHERE in_response_to_tweet_id = CAST(regexp_extract(response_tweet_id, '.*,([0-9]+)$', 1) AS BIGINT)) AS last_matches_irt,
        count(*) FILTER (WHERE in_response_to_tweet_id IS NOT NULL) AS with_irt
    FROM twcs
    WHERE regexp_matches(response_tweet_id, '^[0-9]+(,[0-9]+)+$')
""").df().to_string(index=False))

print("\n=== do the OTHER ids in the comma chain also exist as tweets? (sample '5,7') ===")
print(con.execute("""
    SELECT response_tweet_id, tweet_id, author_id, inbound, text
    FROM twcs
    WHERE regexp_matches(response_tweet_id, '^[0-9]+(,[0-9]+)+$')
    ORDER BY length(response_tweet_id) LIMIT 8
""").df().to_string(index=False))

# --- 2. edge consistency: for outbound tweet O with in_response_to_tweet_id = X (inbound),
#        does X's own parent field point back to O (or to an earlier customer tweet, or forward)?
print("\n=== consistency: outbound->inbound(X) edges: what does X point back to? ===")
print(con.execute("""
    WITH oe AS (
        SELECT o.tweet_id AS out_tweet, o.author_id AS brand, o.in_response_to_tweet_id AS cust_tweet
        FROM twcs o WHERE o.inbound = FALSE AND o.in_response_to_tweet_id IS NOT NULL
    )
    SELECT
        count(*) AS edges,
        count(*) FILTER (WHERE i.in_response_to_tweet_id = oe.out_tweet) AS back_to_out,
        count(*) FILTER (WHERE i.response_tweet_id = CAST(oe.out_tweet AS VARCHAR)) AS rt_back_to_out,
        count(*) FILTER (WHERE i.in_response_to_tweet_id IS NOT NULL AND i.in_response_to_tweet_id <> oe.out_tweet) AS irt_other,
        count(*) FILTER (WHERE i.in_response_to_tweet_id IS NULL AND NOT regexp_matches(i.response_tweet_id, '^[0-9]+$')) AS no_backlink
    FROM oe JOIN twcs i ON oe.cust_tweet = i.tweet_id
""").df().to_string(index=False))

# --- 3. inbound rows with both fields non-null pointing to DIFFERENT tweets ---
print("\n=== inbound rows: both fields non-null and disagreeing? ===")
print(con.execute("""
    SELECT count(*) AS n_both,
           count(*) FILTER (WHERE CAST(response_tweet_id AS BIGINT) <> in_response_to_tweet_id
                             AND regexp_matches(response_tweet_id, '^[0-9]+$')) AS disagree
    FROM twcs WHERE inbound = TRUE
      AND response_tweet_id IS NOT NULL AND in_response_to_tweet_id IS NOT NULL
""").df().to_string(index=False))

# --- 4. For customers, do their inbound->inbound edges form chains? (customer replies to own tweets) ---
print("\n=== inbound->inbound edges: are parents earlier customer tweets in same thread? ===")
print(con.execute("""
    SELECT
        count(*) AS n,
        count(*) FILTER (WHERE i.created_at < p.created_at) AS parent_earlier,
        count(*) FILTER (WHERE i.created_at >= p.created_at) AS parent_not_earlier
    FROM twcs i JOIN twcs p ON i.in_response_to_tweet_id = p.tweet_id
    WHERE i.inbound = TRUE AND p.inbound = TRUE
""").df().to_string(index=False))