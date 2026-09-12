"""Per-brand data-quality / noise analysis.

For every major brand we estimate (on that brand's tweets and its customers'
tweets inside reconstructed conversations):
  - empty text, near-empty, extremely short (<=4 chars)
  - exact-duplicate brand messages
  - URL-only messages
  - reply relationships missing (brand tweet with no parent in conversation)
  - conversations that look structurally unusable for support modeling
    (customer-only, brand-only, or brand has 0 responses inside thread)

Analysis only. No deletion.
Outputs analysis/data_quality.csv (+ .json)
"""
import json
import os
import re

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "analysis", "cache")
OUT = os.path.join(BASE, "analysis")

CONV = pd.read_parquet(os.path.join(CACHE, "conversations.parquet"))
SUM = pd.read_parquet(os.path.join(CACHE, "conversation_summary.parquet"))
BRANDS = pd.read_csv(os.path.join(OUT, "brand_statistics.csv"))

URL_RE = re.compile(r"https?://\S+")
TEXTLESS = re.compile(r"^\s*$")


def clean_text_len(t):
    return len(re.sub(r"\s+", " ", str(t)))


def main():
    conv_ids_by_brand = {}
    brand_rows = CONV.loc[CONV["inbound"] == False]
    brand_tweets_by_brand = brand_rows.groupby("author_id")
    rows = []
    for brand in BRANDS["brand"]:
        sub = brand_rows[brand_rows["author_id"] == brand]
        conv_ids = set(sub["conv_id"].unique())
        csub = CONV[CONV["conv_id"].isin(conv_ids)]
        cust = csub[csub["inbound"] == True]

        n_brand = len(sub)
        n_cust = len(cust)

        # text lengths
        blen = sub["text"].apply(clean_text_len)
        clen = cust["text"].apply(clean_text_len) if n_cust else pd.Series(dtype=float)

        # noise indicators
        b_empty = int((blen == 0).sum())
        c_empty = int((clen == 0).sum())
        b_short4 = int((blen <= 4).sum())
        c_short4 = int((clen <= 4).sum())
        b_url_only = int((sub["text"].str.strip().str.fullmatch(r"(https?://\S+)*", na=False) & (blen > 0)).sum())
        c_url_only = int((cust["text"].str.strip().str.fullmatch(r"(https?://\S+)*", na=False) & (clen > 0)).sum())
        b_dup = int(sub["text"].duplicated().sum())
        # brand tweet with no parent link inside its conversation (its conv is the pair itself + no inbound parent)
        # Simpler proxy: brand tweets whose conversation has 0 customer messages are 'orphaned brand-tweets'
        n_brand_only_convs = int(
            (csub.groupby("conv_id")["inbound"].sum() == 0).sum()
        ) if len(csub) else 0

        # per-conversation summary metrics for this brand
        summ = SUM[SUM["conv_id"].isin(conv_ids)]
        n_conv = len(summ)
        n_customer_only = int((summ["n_brand_tweets"] == 0).sum())
        n_conv_ne_1cust1brand = int(((summ["n_customer_tweets"] >= 1) & (summ["n_brand_tweets"] >= 1)).sum())

        rows.append({
            "brand": brand,
            "n_brand_tweets": n_brand,
            "n_customer_tweets": n_cust,
            "n_conversations": n_conv,
            "brand_empty_text": b_empty,
            "customer_empty_text": c_empty,
            "brand_extremely_short_<=4chars": b_short4,
            "customer_extremely_short_<=4chars": c_short4,
            "brand_url_only": b_url_only,
            "customer_url_only": c_url_only,
            "brand_duplicate_texts": b_dup,
            "n_brand_only_convs": n_brand_only_convs,
            "n_customer_only_convs": n_customer_only,
            "n_convs_with_1plus_cust_and_1plus_brand": n_conv_ne_1cust1brand,
        })

    result = pd.DataFrame(rows)
    result = result.sort_values("n_conversations", ascending=False)
    result.to_csv(os.path.join(OUT, "data_quality.csv"), index=False)
    with open(os.path.join(OUT, "data_quality.json"), "w", encoding="utf-8") as f:
        json.dump({"method": "noise heuristics over reconstructed conversations; analysis only",
                   "results": result.to_dict("records")}, f, indent=2, default=str)
    print(result.to_string(index=False))
    print("Wrote analysis/data_quality.csv/.json")


if __name__ == "__main__":
    main()