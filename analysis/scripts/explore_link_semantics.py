"""Inspect the 'other' response_tweet_id format and validate reply-link semantics."""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import duckdb
import pandas as pd

BASE = r"C:\Users\M.Gowthami\OneDrive\文档\Default Project"
DATA_PATH = BASE + r"\data_extracted\twcs\twcs.csv"

con = duckdb.connect()
con.execute(f"CREATE TABLE twcs AS SELECT * FROM read_csv_auto('{DATA_PATH}', HEADER=true, SAMPLE_SIZE=1000000)")

print("=== sample 'other' response_tweet_id values ===")
print(con.execute("""
    SELECT response_tweet_id, text
    FROM twcs
    WHERE NOT regexp_matches(response_tweet_id, '^[0-9]+$')
      AND response_tweet_id IS NOT NULL
    LIMIT 15
""").df().to_string(index=False))

print("\n=== is 'other' consistent with author@tweet_id but with case/underscores? ===")
print(con.execute("""
    SELECT
        CASE
            WHEN regexp_matches(response_tweet_id, '^(.+)@(.+)$') THEN 'contains_at'
            WHEN regexp_matches(response_tweet_id, '[^.0-9]') THEN 'has_nondigit_nonat'
            ELSE 'other_digitlike'
        END AS cat, count(*)
    FROM twcs
    WHERE NOT regexp_matches(response_tweet_id, '^[0-9]+$') AND response_tweet_id IS NOT NULL
    GROUP BY 1
""").df().to_string(index=False))

print("\n=== 'other' containing '@' breakdown ===")
print(con.execute("""
    SELECT
        CASE
            WHEN regexp_matches(response_tweet_id, '^[a-zA-Z_][a-zA-Z0-9_]*@[0-9]+$') THEN 'user@id'
            WHEN regexp_matches(response_tweet_id, '^@?[a-zA-Z0-9_ .]+@[0-9]+$') THEN 'userlike@id'
            ELSE 'other@'
        END AS cat, count(*)
    FROM twcs
    WHERE regexp_matches(response_tweet_id, '@') AND response_tweet_id IS NOT NULL
    GROUP BY 1
""").df().to_string(index=False))

# Validate reply-link semantics:
print("\n=== For OUTBOUND rows: does in_response_to_tweet_id match an inbound tweet? (sample check) ===")
print(con.execute("""
    SELECT b.in_response_to_tweet_id, i.tweet_id, i.author_id AS inbound_author,
           b.text AS brand_text, i.text AS customer_text
    FROM twcs b JOIN twcs i ON b.in_response_to_tweet_id = i.tweet_id
    WHERE b.inbound = FALSE
    LIMIT 5
""").df().to_string(index=False))

print("\n=== For OUTBOUND rows: count matching inbound parents via in_response_to_tweet_id ===")
print(con.execute("""
    SELECT count(*) AS outbound_total,
           count(i.tweet_id) AS outbound_with_inbound_parent
    FROM twcs b LEFT JOIN twcs i ON b.in_response_to_tweet_id = i.tweet_id
    WHERE b.inbound = FALSE
""").df().to_string(index=False))

print("\n=== For INBOUND rows: what does in_response_to_tweet_id point to? (sample) ===")
print(con.execute("""
    SELECT i.in_response_to_tweet_id, p.tweet_id, p.author_id AS parent_author,
           p.inbound AS parent_inbound,
           i.text AS customer_text, p.text AS parent_text
    FROM twcs i JOIN twcs p ON i.in_response_to_tweet_id = p.tweet_id
    WHERE i.inbound = TRUE AND i.in_response_to_tweet_id IS NOT NULL
    LIMIT 6
""").df().to_string(index=False))

print("\n=== For OUTBOUND rows: what does response_tweet_id point to? (sample) ===")
print(con.execute("""
    SELECT o.response_tweet_id, p.tweet_id, p.author_id AS parent_author, p.inbound AS parent_inbound
    FROM twcs o JOIN twcs p ON CAST(o.response_tweet_id AS BIGINT) = p.tweet_id
    WHERE o.inbound = FALSE AND regexp_matches(o.response_tweet_id, '^[0-9]+$')
    LIMIT 6
""").df().to_string(index=False))

print("\n=== outbound response_tweet_id parents: inbound vs outbound ===")
print(con.execute("""
    SELECT p.inbound AS parent_inbound, count(*)
    FROM twcs o JOIN twcs p ON CAST(o.response_tweet_id AS BIGINT) = p.tweet_id
    WHERE o.inbound = FALSE AND regexp_matches(o.response_tweet_id, '^[0-9]+$')
    GROUP BY 1
""").df().to_string(index=False))

print("\n=== inbound in_response_to parents: inbound vs outbound ===")
print(con.execute("""
    SELECT p.inbound AS parent_inbound, count(*)
    FROM twcs i JOIN twcs p ON i.in_response_to_tweet_id = p.tweet_id
    WHERE i.inbound = TRUE AND i.in_response_to_tweet_id IS NOT NULL
    GROUP BY 1
""").df().to_string(index=False))

print("\n=== inbound response_tweet_id parents: inbound vs outbound ===")
print(con.execute("""
    SELECT p.inbound AS parent_inbound, count(*)
    FROM twcs i JOIN twcs p ON CAST(i.response_tweet_id AS BIGINT) = p.tweet_id
    WHERE i.inbound = TRUE AND regexp_matches(i.response_tweet_id, '^[0-9]+$')
    GROUP BY 1
""").df().to_string(index=False))

print("\n=== nulls for inbound vs outbound response_tweet_id ===")
print(con.execute("""
    SELECT inbound,
           count(*) AS n,
           count(*) FILTER (WHERE response_tweet_id IS NULL) AS rt_null,
           count(*) FILTER (WHERE in_response_to_tweet_id IS NULL) AS irt_null
    FROM twcs GROUP BY 1
""").df().to_string(index=False))