"""Customer-message (problem) diversity for candidate brands.

Deterministic sampling (seed 42), TF-IDF + KMeans per brand over a sample of
customer tweets, then top discriminating terms + representative examples for
each cluster. PURPOSE: evidence about support-problem diversity, NOT the final
intent taxonomy.

Outputs analysis/customer_diversity.json (per-brand cluster summaries) and
saves per-brand representative examples.
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "analysis", "cache")
OUT = os.path.join(BASE, "analysis")

CONV = pd.read_parquet(os.path.join(CACHE, "conversations.parquet"))
BRANDS = pd.read_csv(os.path.join(OUT, "brand_statistics.csv"))

CANDIDATE_BRANDS = ["AmazonHelp", "AppleSupport", "Uber_Support", "SpotifyCares",
                    "AmericanAir", "Delta", "Tesco", "British_Airways",
                    "VirginTrains", "XboxSupport", "VerizonSupport", "TMobileHelp"]

RNG = np.random.RandomState(42)
SAMPLE_PER_BRAND = 20000
N_CLUSTERS = 6

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@[a-zA-Z0-9_]+")


def norm(t):
    t = URL_RE.sub("", str(t))
    t = MENTION_RE.sub("", t)
    t = re.sub(r"[^a-zA-Z0-9' ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def main():
    out = {}
    # customer tweets live in conversations belonging to the brand
    conv2brand = {}
    bot = CONV.loc[CONV["inbound"] == False]
    for b, g in bot.groupby("author_id"):
        conv2brand[b] = set(g["conv_id"].unique())

    for brand in CANDIDATE_BRANDS:
        conv_ids = conv2brand.get(brand, set())
        cust = CONV.loc[(CONV["inbound"] == True) & (CONV["conv_id"].isin(conv_ids))]
        # first customer message of each conversation = problem statement
        first_cust = cust.sort_values("created_ts").groupby("conv_id").first().reset_index()
        texts = first_cust["text"].dropna().astype(str)
        n_all = len(texts)
        sample = texts.sample(n=min(SAMPLE_PER_BRAND, n_all), random_state=42)
        normed = sample.apply(norm)
        normed = normed[normed.str.len() >= 3]

        vec = TfidfVectorizer(max_features=5000, ngram_range=(1, 2),
                              min_df=3, sublinear_tf=True)
        X = vec.fit_transform(normed)
        km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
        labs = km.fit_predict(X)
        terms = np.array(vec.get_feature_names_out())

        clusters = []
        for c in range(N_CLUSTERS):
            idx = np.where(labs == c)[0]
            center = X[idx].mean(axis=0).A1
            top = terms[np.argsort(-center)[:10]].tolist()
            reps = normed.iloc[idx][:4].tolist()
            clusters.append({"cluster": int(c),
                             "size": int(len(idx)),
                             "share_of_first_customer_msgs_sampled": round(len(idx) / len(normed), 4),
                             "top_terms": top,
                             "representative_examples_original": reps})
        clusters.sort(key=lambda d: -d["size"])

        # interpretability: count how many first-msgs are actually support-like later
        out[brand] = {"n_first_customer_messages": int(n_all),
                      "sampled": int(len(normed)),
                      "clusters": clusters}

        with open(os.path.join(OUT, "customer_diversity.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

        print(f"\n### {brand}  (first-msgs: {n_all})")
        for cl in clusters:
            print(f"  c{cl['cluster']}: n={cl['size']} ({cl['share_of_first_customer_msgs_sampled']}) "
                  f"{cl['top_terms']}")
            for ex in cl["representative_examples_original"]:
                print(f"      - {ex[:110]}")
    print("\nWrote analysis/customer_diversity.json")


if __name__ == "__main__":
    main()