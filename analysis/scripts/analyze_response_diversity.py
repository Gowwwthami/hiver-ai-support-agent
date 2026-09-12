"""Per-brand brand-response diversity analysis.

Normalization (analysis-only; originals preserved):
  - URLs -> {URL}
  - @mentions -> @USER   (including numeric-id mentions)
  - numbers -> {NUM}
  - collapse whitespace
  - lowercase

Metrics per brand over its outbound tweets:
  - unique normalized responses, unique-response ratio
  - top-10 / top-20 template share (share of ALL brand outbound tweets)
  - most common raw canned messages (top 20 raw exact texts)
Outputs analysis/response_diversity.csv/.json and analysis/cache/templates/…
"""
import json
import os
import re
from collections import Counter

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "analysis", "cache")
OUT = os.path.join(BASE, "analysis")
CONV = pd.read_parquet(os.path.join(CACHE, "conversations.parquet"))
BRANDS = pd.read_csv(os.path.join(OUT, "brand_statistics.csv"))

CANDidate_BRANDS = [
    "AmazonHelp", "AppleSupport", "Uber_Support", "SpotifyCares", "AmericanAir",
    "Delta", "Tesco", "British_Airways", "VirginTrains", "XboxSupport",
    "VerizonSupport", "TMobileHelp", "sprintcare", "Ask_Spectrum", "comcastcares",
]

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@[a-zA-Z0-9_]+")
NUM_RE = re.compile(r"\d+")


def normalize(t):
    t = URL_RE.sub("{URL}", str(t))
    t = MENTION_RE.sub("@USER", t)
    t = NUM_RE.sub("{NUM}", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def main():
    brand_rows = CONV.loc[CONV["inbound"] == False]
    rows = []
    for brand in CANDidate_BRANDS:
        sub = brand_rows[brand_rows["author_id"] == brand]["text"].dropna()
        n = len(sub)
        if n == 0:
            continue
        n_uniq_raw = sub.nunique()
        norm = sub.apply(normalize)
        vc = norm.value_counts()
        n_uniq_norm = len(vc)
        top10_share = float(vc.head(10).sum()) / n
        top20_share = float(vc.head(20).sum()) / n
        top50_share = float(vc.head(50).sum()) / n
        # raw exact duplicates (canned)
        raw_vc = sub.value_counts()
        top20_raw = raw_vc.head(20)
        rows.append({
            "brand": brand,
            "n_brand_outbound_tweets": n,
            "unique_raw_texts": n_uniq_raw,
            "unique_normalized_templates": n_uniq_norm,
            "unique_ratio_normalized": round(n_uniq_norm / n, 4),
            "top10_template_share": round(top10_share, 4),
            "top20_template_share": round(top20_share, 4),
            "top50_template_share": round(top50_share, 4),
            "most_frequent_raw_msg_share": round(float(raw_vc.iloc[0]) / n, 4),
        })
        # save per-brand template tables for deeper inspection
        os.makedirs(os.path.join(CACHE, "templates"), exist_ok=True)
        vc.rename("count").to_frame().assign(share=round(vc / n, 5)).head(20).to_csv(
            os.path.join(CACHE, "templates", f"{brand}_top20.csv"))

    result = pd.DataFrame(rows).sort_values("n_brand_outbound_tweets", ascending=False)
    result.to_csv(os.path.join(OUT, "response_diversity.csv"), index=False)
    with open(os.path.join(OUT, "response_diversity.json"), "w", encoding="utf-8") as f:
        json.dump({"method": ("templates normalized: URLs->{{URL}}, mentions->@USER, numbers->{{NUM}}, "
                              "lowercased, whitespace collapsed; metrics over brand outbound tweets"),
                   "results": result.to_dict("records")}, f, indent=2, default=str)
    print(result.to_string(index=False))
    print("Wrote analysis/response_diversity.csv/.json ; per-brand top-20 templates in analysis/cache/templates/")


if __name__ == "__main__":
    main()