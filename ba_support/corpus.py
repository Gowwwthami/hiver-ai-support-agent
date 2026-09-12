"""Retrieval / training corpus construction for British_Airways.

A corpus record is a historical *resolution example*: a customer inbound
message, a little preceding context, and the brand's next reply (if any),
plus the conversation/customer ids needed for leakage filters and a weak
intent label for retrieval filtering / weak supervision.

Exclusions applied at build time:
  - the 200 golden conversations (evaluation hold-out),
  - the 50 Phase-1 audit conversations,
  - conversations whose *customer* also appears inside a golden conversation
    (customer-level separation; strictly stronger than conversation-level).
Per-query near-duplicate exclusion is applied at retrieval time.

The build is deterministic and cached to `analysis/cache/retrieval_corpus.parquet`.
"""

import re

import duckdb
import pandas as pd

from . import paths
from . import weak


def _load_conversations() -> pd.DataFrame:
    if not paths.CONVERSATIONS_PARQUET.exists():
        raise FileNotFoundError(
            f"Missing reconstructed conversations at {paths.CONVERSATIONS_PARQUET}. "
            f"Run analysis/scripts/reconstruct_conversations.py first.")
    return pd.read_parquet(paths.CONVERSATIONS_PARQUET)


def _load_summary() -> pd.DataFrame:
    return pd.read_parquet(paths.CONVERSATION_SUMMARY_PARQUET)


def ba_conversation_tweets() -> pd.DataFrame:
    """All tweets of conversations that contain a British_Airways brand author."""
    con = duckdb.connect()
    return con.execute(
        "SELECT c.conv_id, c.tweet_id, c.author_id, c.inbound, c.created_ts, c.text "
        "FROM read_parquet(?) c "
        "WHERE EXISTS (SELECT 1 FROM read_parquet(?) s "
        "  WHERE s.conv_id = c.conv_id "
        "    AND EXISTS (SELECT 1 FROM unnest(s.brand_authors) AS t(a) "
        "               WHERE t.a = ?)) "
        "ORDER BY c.conv_id, c.created_ts, c.tweet_id",
        [str(paths.CONVERSATIONS_PARQUET), str(paths.CONVERSATION_SUMMARY_PARQUET),
         paths.BRAND],
    ).df()


def _extract_pairs(conv: pd.DataFrame):
    """Yield (conv_id, customer message, prior context, brand reply) records."""
    out = []
    rows = conv.reset_index(drop=True)
    cust_author = rows.loc[rows["inbound"], "author_id"].unique().tolist()
    for i, r in rows.iterrows():
        if not r["inbound"]:
            continue
        brand_after = rows.loc[(rows.index > i) & (~rows["inbound"]) & (
            rows["author_id"] == paths.BRAND), "text"]
        if brand_after.empty:
            continue
        reply = brand_after.iloc[0]
        ctx = []
        for j in range(i - 1, -1, -1):
            if j < 0:
                break
            pre = rows.loc[j]
            ctx.append(f"[{'BRAND' if not pre['inbound'] else 'CUSTOMER'}] {pre['text']}")
            if len(ctx) >= 2:
                break
        ctx.reverse()
        out.append({
            "conv_id": int(r["conv_id"]),
            "tweet_id": int(r["tweet_id"]),
            "customer_author_id": str(r["author_id"]),
            "customer_msg": r["text"],
            "prior_context": "\n".join(ctx),
            "brand_reply": reply,
            "created_ts": str(r["created_ts"]),
        })
    return out


def build_corpus(*, force: bool = False) -> pd.DataFrame:
    """Deterministic leakage-controlled corpus; cached to parquet.

    Pass `force=True` to rebuild (required after taxonomy-name changes, since
    the weak labels are materialised into the cached column).
    """
    if paths.CORPUS_PARQUET.exists() and not force:
        return pd.read_parquet(paths.CORPUS_PARQUET)

    tweets = ba_conversation_tweets()
    from . import leakage

    golden = leakage.golden_conv_ids()
    audit = leakage.audit_conv_ids()
    excluded = golden | audit
    keep_ids = [c for c in tweets["conv_id"].unique() if c not in excluded]
    tweets = tweets[tweets["conv_id"].isin(keep_ids)].reset_index(drop=True)

    rows = []
    for cid, grp in tweets.groupby("conv_id", sort=True):
        rows.extend(_extract_pairs(grp))

    df = pd.DataFrame(rows)
    # customer-level separation: drop records whose customer appears in golden
    gold = leakage.golden_customer_ids()
    df["customer_overlaps_golden"] = df["customer_author_id"].astype(str).isin(gold)
    df = df[~df["customer_overlaps_golden"]].reset_index(drop=True)

    weak_out = [weak.weak_label(t) for t in df["customer_msg"]]
    df["weak_intent"] = [lbl for lbl, _, _ in weak_out]
    df["weak_confident"] = [conf for _, _, conf in weak_out]
    df["corpus_id"] = [f"CR_{i:05d}" for i in range(len(df))]
    df["normalized_msg"] = df["customer_msg"].map(normalize_msg)

    paths.ensure_dir(paths.CACHE_DIR)
    df.to_parquet(paths.CORPUS_PARQUET, index=False)
    return df


def corpus_summary(df: pd.DataFrame) -> dict:
    return {
        "records": int(len(df)),
        "conversations": int(df["conv_id"].nunique()),
        "with_brand_reply": int((df["brand_reply"].astype(str).str.len() > 0).sum()),
        "weak_label_counts": df["weak_intent"].value_counts().to_dict(),
        "weak_confident_share": round(float(df["weak_confident"].mean()), 4),
    }


def load_corpus() -> pd.DataFrame:
    return build_corpus()


def normalize_msg(text: str) -> str:
    """Normalised message (lowercased, whitespace-collapsed, stripped links)."""
    return " ".join(re.sub(r"https?://\S+", " URL ", text or "").lower().split())