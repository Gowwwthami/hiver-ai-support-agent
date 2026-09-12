"""Historical-response retrieval over the leakage-controlled BA corpus.

Retriever indexes corpus customer messages with TF-IDF cosine similarity
(the deterministic, dependency-free default) and, when the optional
`sentence-transformers` package is installed, can be switched to a semantic
embedding encoder (`Retriever(semantic=True)`) — both are exposed through the
same interface so ablations compare them honestly.

Filters applied per query:
  - conversation-level: golden/audit conversations never appear in the corpus;
  - customer-level: the query customer's other conversations are excluded;
  - near-duplicate: corpus messages near-duplicate to the query are excluded;
  - optional intent filter: restrict candidates to rows whose weak intent
    equals the predicted intent (falls back to unfiltered when too few).
"""

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import paths, taxonomy
from .corpus import normalize_msg
from .normalize import (is_near_duplicate, is_near_duplicate_tokens,
                        normalize_text, token_set)

try:  # optional semantic encoder (ablation); not required for default runs
    from sentence_transformers import SentenceTransformer  # type: ignore

    _ST_AVAILABLE = True
except Exception:  # pragma: no cover - depends on optional package
    _ST_AVAILABLE = False


class TfidfEncoder:
    """TF-IDF cosine encoder over corpus customer messages."""

    name = "tfidf"

    def __init__(self, corpus: pd.DataFrame):
        self.vectorizer = TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), min_df=2, max_df=0.95,
            sublinear_tf=True, stop_words="english",
        )
        self._fit(corpus)

    def _fit(self, corpus: pd.DataFrame):
        docs = [normalize_text(t) for t in corpus["customer_msg"]]
        self.vectors = self.vectorizer.fit_transform(docs)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.vectorizer.transform([normalize_text(t) for t in texts])


class SemanticEncoder:  # pragma: no cover - optional dependency path
    name = "sbert"

    def __init__(self, corpus: pd.DataFrame, model_name: str = "all-MiniLM-L6-v2"):
        if not _ST_AVAILABLE:
            raise ImportError("sentence-transformers not installed")
        self.model = SentenceTransformer(model_name)
        self._fit(corpus)

    def _fit(self, corpus: pd.DataFrame):
        from sentence_transformers import util

        self.util = util
        embs = self.model.encode(corpus["customer_msg"].tolist(),
                                 convert_to_tensor=False, show_progress_bar=False)
        self.vectors = embs
        self.norm = np.linalg.norm(embs, axis=1, keepdims=True)

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(list(texts), show_progress_bar=False)


class Retriever:
    def __init__(self, corpus: pd.DataFrame, semantic: bool = False):
        self.corpus = corpus.reset_index(drop=True)
        self.semantic = semantic
        if semantic:
            self.encoder = SemanticEncoder(self.corpus)
        else:
            self.encoder = TfidfEncoder(self.corpus)
        self._doc_vectors = self.encoder.vectors
        # Precompute candidate token sets once so per-query near-duplicate
        # exclusion is cheap (navy-ish O(corpus) per query instead of O(tokens)).
        self._token_sets = [token_set(m) for m in self.corpus["customer_msg"]]

    def search(self, query_msg: str, top_k: int = paths.DEFAULT_TOP_K,
               query_conv_id: int | None = None, query_customer: str | None = None,
               intent_filter: str | None = None,
               exclude_near_duplicates: bool = True,
               min_similarity: float = 0.0) -> list[dict]:
        q = np.asarray(self.encoder.encode([query_msg]).todense())
        corpus = self.corpus

        mask = pd.Series(True, index=corpus.index)
        if query_conv_id is not None:
            mask &= corpus["conv_id"] != query_conv_id
        if query_customer is not None and str(query_customer):
            mask &= corpus["customer_author_id"].astype(str) != str(query_customer)

        cand = corpus.loc[mask.values]
        if cand.empty:
            return []

        if intent_filter is not None and intent_filter in taxonomy.INTENT_LABELS:
            sub = cand[cand["weak_intent"] == intent_filter]
            if len(sub) >= top_k * 3:
                cand = sub

        if exclude_near_duplicates:
            qset = token_set(query_msg)
            keep_idx = [i for i in cand.index
                        if not is_near_duplicate_tokens(qset, self._token_sets[i])]
            cand = cand.loc[keep_idx]

        idx = cand.index.tolist()
        sims = cosine_similarity(q, self._doc_vectors[idx]).ravel()

        if min_similarity > 0:
            keep = sims >= min_similarity
            sims = sims[keep]
            idx = [i for i, k in zip(idx, keep) if k]

        order = np.argsort(sims)[::-1][:top_k]
        out = []
        for pos in order:
            i = idx[pos]
            row = cand.loc[i]
            out.append({
                "rank": len(out) + 1,
                "similarity": float(sims[pos]),
                "corpus_id": row["corpus_id"],
                "conv_id": int(row["conv_id"]),
                "customer_msg": row["customer_msg"],
                "prior_context": row["prior_context"],
                "brand_reply": row["brand_reply"],
                "weak_intent": row["weak_intent"],
            })
        return out


def retrieval_quality(retriever: Retriever, golden: pd.DataFrame,
                      intent_source="golden", top_k: int = paths.DEFAULT_TOP_K) -> dict:
    """Reference-quality metrics over the golden set (isolation respected).

    - R@k intent-consistency: share of queries with >=1 retrieved record whose
      weak intent matches the query intent (a coarse coverage proxy).
    - mean top-1 / top-k similarity.
    - evidence relevance proxy: cosine between the top evidence's brand reply
      and the golden reference reply (rows with a historical reply only).
    """
    from .leakage import golden_panel as _gp

    gold = golden.copy()
    rows = []
    for _, r in gold.iterrows():
        intent = r["intent"] if intent_source == "golden" else None
        hits = retriever.search(
            r["customer_message"], top_k=top_k,
            query_conv_id=int(r["conv_id"]),
            query_customer=r["target_author_id"],
            intent_filter=intent,
        )
        rows.append({
            "example_id": r["example_id"],
            "n_hits": len(hits),
            "top1_sim": hits[0]["similarity"] if hits else 0.0,
            "topk_mean_sim": float(np.mean([h["similarity"] for h in hits])) if hits else 0.0,
            "intent_match_topk": any(h["weak_intent"] == intent for h in hits) if intent else None,
            "evidence_brand_reply": hits[0]["brand_reply"] if hits else "",
            "top_conv": hits[0]["conv_id"] if hits else None,
        })
    df = pd.DataFrame(rows)
    result = {
        "records": int(len(df)),
        "hit_rate_at_k": round(float((df["n_hits"] > 0).mean()), 4),
        "mean_top1_similarity": round(float(df["top1_sim"].mean()), 4),
        "mean_topk_similarity": round(float(df["topk_mean_sim"].mean()), 4),
        "mean_topk_similarity_median": round(float(df["topk_mean_sim"].median()), 4),
    }
    if intent_source == "golden":
        sub = df[~df["intent_match_topk"].isna()]
        result["recall_at_k_intent_consistency"] = round(
            float(sub["intent_match_topk"].mean()), 4)
    ref = df[df["evidence_brand_reply"].astype(str).str.len() > 0]
    if len(ref) and golden is not None:
        gmap = dict(zip(gold["example_id"], gold["reference_brand_reply"]))
        covs = []
        for _, rr in ref.iterrows():
            ref_text = gmap.get(rr["example_id"], "")
            if not ref_text:
                continue
            import math

            a = normalize_msg(rr["evidence_brand_reply"])
            b = normalize_msg(str(ref_text))
            if not a or not b:
                continue
            sa, sb = set(a.split()), set(b.split())
            covs.append(len(sa & sb) / max(1.0, math.sqrt(len(sa) * len(sb))))
        if covs:
            result["evidence_word_overlap_with_reference"] = round(
                float(np.mean(covs)), 4)
    return result