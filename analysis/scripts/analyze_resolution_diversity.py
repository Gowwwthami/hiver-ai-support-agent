"""Problem->resolution diversity: do different problem types get different
resolution behavior?

For each candidate brand:
  - cluster first-customer-messages (TF-IDF + KMeans, deterministic seed 42, K=5)
  - for each problem cluster compute the distribution of heuristic resolution
    types of the LAST brand response, plus top-2 last-response templates
  - report mean pairwise chi^2-like dissimilarity (Bhattacharyya distance) of
    the type-distributions across clusters (diversity metric, labelled approx)

Outputs analysis/resolution_diversity_by_cluster.csv/.json
"""
import json
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
CONV = pd.read_parquet(os.path.join(CACHE, "conversations.parquet"))

CANDIDATE_BRANDS = ["AmazonHelp", "AppleSupport", "Uber_Support", "SpotifyCares",
                    "AmericanAir", "Delta", "Tesco", "British_Airways",
                    "VirginTrains", "XboxSupport", "VerizonSupport", "TMobileHelp"]
K = 5
SAMPLE = 20000

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@[a-zA-Z0-9_]+")
NUM_RE = re.compile(r"\d+")

DM_RE = re.compile(r"\b(dm|direct message|private message|inbox|send us a note|"
                   r"message us|reach out|contact us|pm us)\b", re.I)
SELF_RE = re.compile(r"\b(check|visit|go to|follow|try|see|download|log ?in)\b.{0,40}"
                     r"(https?://|support|help center|\.com)\b", re.I)
COMP_RE = re.compile(r"\b(refund|credit|reimburse|compensation|discount|voucher|money back|goodwill)\b", re.I)
FIXED_RE = re.compile(r"\b(resolved|fixed|sorted|workaround|back up and update|update (has )?(been )?(released|available))\b", re.I)
ESCAL_RE = re.compile(r"\b(pass(ed|ing)? (to|this on)|forward(ed|ing)?|team will be in touch|"
                      r"someone (will|is going to)|we (will|'ll) (look|take)|looking into|investigat|"
                      r"ticket|c[as]se reference)\b", re.I)
STATUS_RE = re.compile(r"\b(status|on its way|arriv|deliver|track(all)?ing|due to arrive|depart|delayed|cancel|"
                       r"gate|schedule|eta|food web|flight)\b", re.I)
APOL_RE = re.compile(r"\b(sorry|apolog|apologies)\b", re.I)
ACK_RE = re.compile(r"\b(thank|thanks|great|appreciate|no problem|happy to help)\b", re.I)

TYPES = [("DM_INFO", DM_RE), ("SELF_SERVICE", SELF_RE), ("COMPENSATION", COMP_RE),
         ("FIXED", FIXED_RE), ("ESCALATION", ESCAL_RE), ("STATUS_UPDATE", STATUS_RE),
         ("APOLOGY_ONLY", APOL_RE), ("ACK", ACK_RE)]


def type_of(t):
    for nm, rx in TYPES:
        if rx.search(t):
            return nm
    return "OTHER"


def norm(t):
    t = URL_RE.sub("", str(t))
    t = MENTION_RE.sub("", t)
    t = NUM_RE.sub("", t)
    t = re.sub(r"[^a-zA-Z ']+", " ", t).lower()
    return re.sub(r"\s+", " ", t).strip()


def bhattacharyya(p, q):
    p = np.asarray(p, float) / max(np.sum(p), 1)
    q = np.asarray(q, float) / max(np.sum(q), 1)
    eps = 1e-9
    return -np.log(np.sum(np.sqrt(p * q)) + eps)


def main():
    bot = CONV.loc[CONV["inbound"] == False]
    cust = CONV.loc[CONV["inbound"] == True]
    conv2brand = {b: set(g["conv_id"].unique()) for b, g in bot.groupby("author_id")}

    rows = []
    for brand in CANDIDATE_BRANDS:
        conv_ids = conv2brand.get(brand, set())
        sub = CONV[CONV["conv_id"].isin(conv_ids)].sort_values(["conv_id", "created_ts"])

        # problem = first customer message; last response per conv by THIS brand
        pairs = []
        for cid, g in sub.groupby("conv_id"):
            cm = g[g["inbound"] == True]
            bm = g[(g["author_id"] == brand) & (~g["inbound"])]
            if cm.empty or bm.empty:
                continue
            pairs.append({"conv_id": cid, "problem": str(cm.iloc[0]["text"]),
                          "last_response": str(bm.iloc[-1]["text"])})
        dfp = pd.DataFrame(pairs)
        if dfp.empty:
            continue
        dfp["resp_type"] = dfp["last_response"].apply(type_of)
        dfp["problem_norm"] = dfp["problem"].apply(norm)
        sample = dfp["problem_norm"].sample(n=min(SAMPLE, len(dfp)), random_state=42)
        vec = TfidfVectorizer(max_features=3000, ngram_range=(1, 2), min_df=3, sublinear_tf=True)
        X = vec.fit_transform(sample)
        km = KMeans(n_clusters=K, random_state=42, n_init=10)
        labs = km.fit_predict(X)
        dfp["pcluster"] = km.predict(vec.transform(dfp["problem_norm"].fillna("")))

        # type distribution per cluster
        type_rows = []
        for c in range(K):
            subc = dfp[dfp["pcluster"] == c]
            dist = subc["resp_type"].value_counts(normalize=True).to_dict()
            top2 = [f"{t} ({n})" for t, n in
                    subc["last_response"].apply(norm).value_counts().head(2).items()]
            type_rows.append({"pcluster": int(c), "n": len(subc), "type_dist": dist,
                              "top2_last_response_templates": top2})
        # pairwise Bhattacharyya distance of type distributions
        nK = len(type_rows)
        mats = np.zeros((nK, 9))
        tnames = ["DM_INFO", "SELF_SERVICE", "COMPENSATION", "FIXED", "ESCALATION",
                  "STATUS_UPDATE", "APOLOGY_ONLY", "ACK", "OTHER"]
        for j, tr in enumerate(type_rows):
            mats[j] = [tr["type_dist"].get(t, 0) for t in tnames]
        d = 0.0
        cnt = 0
        for a in range(nK):
            for bb in range(a + 1, nK):
                d += bhattacharyya(mats[a], mats[bb])
                cnt += 1
        mean_bhat = d / max(cnt, 1)

        rows.append({"brand": brand,
                     "n_problem_response_pairs": len(dfp),
                     "mean_pairwise_bhattacharyya_between_problem_clusters": round(mean_bhat, 4),
                     "clusters": type_rows})

        print(f"\n### {brand}   mean_Bhatt={mean_bhat:.4f}")
        for tr in type_rows:
            top = sorted(tr["type_dist"].items(), key=lambda x: -x[1])[:4]
            print(f"  cluster n={tr['n']:6d}  {top}")
            for t in tr["top2_last_response_templates"]:
                print(f"      -> {t[:130]}")

    with open(os.path.join(OUT, "resolution_diversity_by_cluster.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False, default=str)
    print("\nWrote analysis/resolution_diversity_by_cluster.json")


if __name__ == "__main__":
    main()