"""Stratified sampling of COMPLETE reconstructed conversations for candidate
brands.

Stratification axes per brand:
  - conversation length bucket (short 2, medium 3-4, long >=5)
  - product/problem area proxy: TF-IDF KMeans cluster of the first customer msg
  - response behavior: whether the brand responded >=2 times
Deterministic (seed 137). ~N_PER_BRAND complete threads saved as markdown.

Outputs analysis/candidate_conversations/BRAND.md
"""
import os
import re
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "analysis", "cache")
OUT = os.path.join(BASE, "analysis")
CONV_DIR = os.path.join(OUT, "candidate_conversations")
os.makedirs(CONV_DIR, exist_ok=True)

CONV = pd.read_parquet(os.path.join(CACHE, "conversations.parquet"))

SHORTLIST = ["AmazonHelp", "British_Airways", "AmericanAir", "Delta",
             "VirginTrains", "SpotifyCares", "Tesco", "XboxSupport"]
N_PER_BRAND = 50
SEED = 137
KM_CLUSTERS = 6

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@[a-zA-Z0-9_]+")


def norm(t):
    t = URL_RE.sub("", str(t))
    t = MENTION_RE.sub("", t)
    t = re.sub(r"[^a-zA-Z ']+", " ", t).lower()
    return re.sub(r"\s+", " ", t).strip()


def main():
    bot = CONV.loc[CONV["inbound"] == False]
    conv2brand = {b: set(g["conv_id"].unique()) for b, g in bot.groupby("author_id")}

    for brand in SHORTLIST:
        conv_ids = conv2brand.get(brand)
        sub = CONV[CONV["conv_id"].isin(conv_ids)].sort_values(["conv_id", "created_ts"])
        summ = sub.groupby("conv_id").agg(n=("tweet_id", "count"),
                                          n_brand=("inbound", lambda s: (~s).sum()),
                                          start=("created_ts", "min"))
        # first customer message per conv for clustering
        firsts = sub[sub["inbound"] == True].sort_values("created_ts") \
            .groupby("conv_id").first().reset_index()
        firsts = firsts[["conv_id", "text"]].dropna()

        # length bucket
        def bucket(n):
            if n == 2:
                return "short"
            if n <= 4:
                return "medium"
            return "long"

        summ["bucket"] = summ["n"].apply(bucket)

        # problem clusters (only convs with a first customer message)
        texts = firsts["text"].astype(str)
        vec_texts = texts.apply(norm)
        vec_texts = vec_texts[vec_texts.str.len() >= 3]
        vec = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), min_df=3, sublinear_tf=True)
        X = vec.fit_transform(vec_texts)
        km = KMeans(n_clusters=KM_CLUSTERS, random_state=SEED, n_init=10)
        labs = km.fit_predict(X)
        lab_of = dict(zip(vec_texts.index, labs))
        summ["pcluster"] = summ.index.map(lambda c: lab_of.get(c, -1))

        # strata weights and sample
        rng = np.random.RandomState(SEED)
        candidates = summ[(summ["pcluster"] >= 0)]
        if len(candidates) == 0:
            continue
        # sample per bucket+cluster cell proportionally, min 1, capped
        cells = candidates.groupby(["bucket", "pcluster"]).size()
        sampled = []
        need = N_PER_BRAND
        for (bk, pc), cnt in cells.items():
            cell = candidates[(candidates["bucket"] == bk) & (candidates["pcluster"] == pc)]
            take = max(1, int(round(need * cnt / len(candidates))))
            take = min(take, len(cell))
            sampled.append(cell.sample(n=take, random_state=SEED))
        sel = pd.concat(sampled)
        if len(sel) > need:
            sel = sel.sample(n=need, random_state=SEED)

        # write markdown
        lines = [f"# {brand} - sampled conversations (n={len(sel)})\n",
                 "\nDeterministic stratified sample (seed=137): buckets short/medium/long x problem clusters.\n"]
        for cid, row in sel.iterrows():
            g = sub[sub["conv_id"] == cid].sort_values("created_ts")
            lines.append(f"\n## Conversation {cid}  | tweets={row['n']}  brand_msgs={row['n_brand']}  bucket={row['bucket']}")
            for i, t in g.iterrows():
                who = "CUSTOMER" if t["inbound"] else "BRAND(" + t["author_id"] + ")"
                lines.append(f"* [{t['created_at']}] {who}: {t['text']}")
        fname = os.path.join(CONV_DIR, brand + ".md")
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"{brand}: sampled {len(sel)} convs (capsules {dict(sel['bucket'].value_counts())}) -> {fname}")


if __name__ == "__main__":
    main()