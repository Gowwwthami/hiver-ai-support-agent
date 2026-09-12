"""Per-brand conversation quality statistics from reconstructed conversations.

For every brand (support account) we compute, over conversations that contain
at least one tweet by that account:
  - number of conversations
  - median / mean / max conversation length (tweets)
  - # and % of conversations with >= 2 brand responses; >= 3 brand responses
  - unique customers
  - avg customer messages / conversation
  - avg brand messages / conversation
  - % of conversations containing both customer AND brand messages

Outputs analysis/conversation_quality.csv (+ .json)
"""
import json
import os

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "analysis", "cache")
OUT = os.path.join(BASE, "analysis")
CONV = pd.read_parquet(os.path.join(CACHE, "conversations.parquet"),
                       columns=["conv_id", "author_id", "inbound", "tweet_id"])
SUM = pd.read_parquet(os.path.join(CACHE, "conversation_summary.parquet"))
BRANDS = pd.read_csv(os.path.join(OUT, "brand_statistics.csv"))


def main():
    # Brand conversation membership: conv has >=1 tweet authored by brand.
    brand_tweets = CONV.loc[CONV["inbound"] == False].copy()
    conv_brands = brand_tweets.groupby("conv_id")["author_id"].apply(lambda s: list(dict.fromkeys(s)))

    rows = []
    for brand in BRANDS["brand"]:
        convs = conv_brands[conv_brands.apply(lambda a: brand in a)]
        # per conversation: brand tweet count, customer msg/brand msg counts within that conv
        if convs.empty:
            continue
        conv_ids = set(convs.index)
        sub = CONV[CONV["conv_id"].isin(conv_ids)]
        g = sub.groupby("conv_id")
        n_tweets = g["tweet_id"].count()
        n_cust = sub.loc[sub["inbound"] == True].groupby("conv_id")["tweet_id"].count()
        n_brand_all = (sub.loc[sub["inbound"] == False].groupby("conv_id")["author_id"].count())
        # brand responses = tweets by THIS brand (a conv may contain another brand)
        bmask = (sub["inbound"] == False) & (sub["author_id"] == brand)
        n_brand_resp = sub.loc[bmask].groupby("conv_id")["tweet_id"].count()
        n_cust_resp = sub.loc[sub["inbound"] == True].groupby("conv_id")["author_id"].nunique()

        dfc = pd.DataFrame({"n_tweets": n_tweets,
                            "n_brand": n_brand_resp.reindex(n_tweets.index).fillna(0),
                            "n_cust": n_cust.reindex(n_tweets.index).fillna(0),
                            "n_cust_authors": n_cust_resp.reindex(n_tweets.index).fillna(0)})
        have_both = ((dfc["n_brand"] > 0) & (dfc["n_cust"] > 0)).mean()
        rows.append({
            "brand": brand,
            "n_conversations": int(len(dfc)),
            "median_conversation_length": float(dfc["n_tweets"].median()),
            "mean_conversation_length": round(float(dfc["n_tweets"].mean()), 2),
            "max_conversation_length": int(dfc["n_tweets"].max()),
            "n_ge2_brand_responses": int((dfc["n_brand"] >= 2).sum()),
            "pct_ge2_brand_responses": round(float((dfc["n_brand"] >= 2).mean()), 4),
            "n_ge3_brand_responses": int((dfc["n_brand"] >= 3).sum()),
            "pct_ge3_brand_responses": round(float((dfc["n_brand"] >= 3).mean()), 4),
            "unique_customers": int(dfc["n_cust_authors"].sum()),
            "avg_customer_messages_per_conv": round(float(dfc["n_cust"].mean()), 2),
            "avg_brand_messages_per_conv": round(float(dfc["n_brand"].mean()), 2),
            "pct_both_customer_and_brand": round(float(have_both), 4),
        })

    result = pd.DataFrame(rows)
    result = result.sort_values("n_conversations", ascending=False)
    result.to_csv(os.path.join(OUT, "conversation_quality.csv"), index=False)
    with open(os.path.join(OUT, "conversation_quality.json"), "w", encoding="utf-8") as f:
        json.dump({"method": "conversations from union-find reconstruction; per-brand convs = convs containing ≥1 tweet by that author",
                   "results": result.to_dict("records")}, f, indent=2, default=str)

    print(result.to_string(index=False))
    print("Wrote analysis/conversation_quality.csv/.json")


if __name__ == "__main__":
    main()