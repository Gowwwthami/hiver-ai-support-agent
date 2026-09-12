"""Conversation reconstruction via union-find over reply links.

EDGE MODEL (established empirically from the data):
  - `in_response_to_tweet_id`  = parent tweet of this row (backward link)
  - `response_tweet_id`        = may be a comma-separated LIST of tweet ids
    belonging to the same thread (crawler artifact), or a single id. Every
    listed id is treated as a link to the same conversation component.

Connected components of the tweet-reply graph define "conversations".
Tweets that link to non-existent ids still belong to their component (the
phantom id is simply not a real turn).

Outputs:
  analysis/cache/conversations.parquet           row-level
  analysis/cache/conversation_summary.parquet    conversation-level
"""
import os
import time

import duckdb
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(BASE, "data_extracted", "twcs", "twcs.csv")
CACHE = os.path.join(BASE, "analysis", "cache")
os.makedirs(CACHE, exist_ok=True)


class UnionFind:
    __slots__ = ("parent", "size")

    def __init__(self, n):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x):
        p = self.parent
        while p[x] != x:
            p[x] = p[p[x]]
            x = p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        pa, pb = self.parent, self.size
        if pb[ra] < pb[rb]:
            ra, rb = rb, ra
        pa[rb] = ra
        pb[ra] += pb[rb]


def main():
    t0 = time.time()
    con = duckdb.connect()
    con.execute(f"CREATE TABLE twcs AS SELECT * FROM read_csv_auto('{DATA_PATH}', HEADER=true, SAMPLE_SIZE=1000000)")

    # --- node list ---
    nodes = con.execute("""
        SELECT tweet_id, author_id, inbound, created_at, text
        FROM twcs ORDER BY tweet_id
    """).fetchall()
    n = len(nodes)
    print(f"nodes: {n:,}")

    tid2idx = {r[0]: i for i, r in enumerate(nodes)}
    uf = UnionFind(n)

    # --- edges: both fields; comma lists split ---
    edges = con.execute("""
        WITH pe AS (
            SELECT tweet_id, in_response_to_tweet_id AS other FROM twcs
            WHERE in_response_to_tweet_id IS NOT NULL
        ),
        re AS (
            SELECT t.tweet_id, CAST(elem AS BIGINT) AS other
            FROM (
                SELECT tweet_id, string_split(response_tweet_id, ',') AS parts
                FROM twcs WHERE response_tweet_id IS NOT NULL
            ) t CROSS JOIN UNNEST(t.parts) AS p(elem)
            WHERE regexp_matches(trim(elem), '^[0-9]+$')
        )
        SELECT * FROM pe UNION ALL SELECT * FROM re
    """).fetchall()
    print(f"candidate edges: {len(edges):,}")

    linked = 0
    for src, dst in edges:
        s = tid2idx.get(src)
        d = tid2idx.get(dst)
        if s is None or d is None:
            continue
        uf.union(s, d)
        linked += 1
    print(f"edges to existing tweets: {linked:,}")

    conv = [uf.find(i) for i in range(n)]
    uniq_roots = {r: k for k, r in enumerate(sorted(set(conv)))}
    conv_id = [uniq_roots[r] for r in conv]
    n_conv = len(uniq_roots)

    df = pd.DataFrame(nodes, columns=["tweet_id", "author_id", "inbound", "created_at", "text"])
    df["created_ts"] = pd.to_datetime(df["created_at"], format="%a %b %d %H:%M:%S +0000 %Y", utc=True)
    df["conv_id"] = conv_id
    df = df.sort_values(["conv_id", "created_ts"]).reset_index(drop=True)

    # --- conversation summary ---
    outb_s = (~df["inbound"]).astype(int)
    agg = df.groupby("conv_id").agg(
        n_tweets=("tweet_id", "count"),
        n_customer_tweets=("inbound", "sum"),
        n_authors=("author_id", "nunique"),
        start_ts=("created_ts", "min"),
        end_ts=("created_ts", "max"),
    ).reset_index()

    n_out = df.groupby("conv_id")["inbound"].apply(lambda s: outb_s[s.index].sum()).to_dict()
    agg["n_brand_tweets"] = agg["conv_id"].map(n_out)

    brand_map = df.loc[df["inbound"] == False].groupby("conv_id")["author_id"] \
        .apply(lambda s: list(dict.fromkeys(s))).to_dict()
    agg["brand_authors"] = agg["conv_id"].map(lambda c: brand_map.get(c, []))
    agg["n_brand_authors"] = agg["brand_authors"].apply(len)
    agg["cust_ids"] = df.loc[df["inbound"] == True].groupby("conv_id")["author_id"].nunique().reindex(agg["conv_id"]).fillna(0).astype(int)
    agg["span_seconds"] = (agg["end_ts"] - agg["start_ts"]).dt.total_seconds()
    agg = agg.sort_values("conv_id").reset_index(drop=True)

    agg.to_parquet(os.path.join(CACHE, "conversation_summary.parquet"), index=False)
    df.to_parquet(os.path.join(CACHE, "conversations.parquet"), index=False)

    print(f"conversations: {n_conv:,}  (singletons: {(agg.n_tweets == 1).sum():,})")
    print("\nsize distribution (n_tweets):")
    print(agg["n_tweets"].value_counts().head(12).to_string())
    print(f"\nWrote conversations.parquet + conversation_summary.parquet  [{round(time.time()-t0,1)}s]")


if __name__ == "__main__":
    main()