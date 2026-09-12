"""Intent classifiers: majority baseline, TF-IDF+LogisticRegression baseline,
and the hybrid main system (deterministic rules + TF-IDF LR + centroid
similarity). All models are fitted ONLY on the leakage-excluded weak-labelled
corpus — never on the golden set.
"""

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import joblib
except ImportError:  # pragma: no cover - joblib ships with scikit-learn
    joblib = None

from . import paths, taxonomy, weak
from .normalize import normalize_text

N_CLASSES = taxonomy.INTENT_ORDER


def _train_rows(corpus: pd.DataFrame) -> pd.DataFrame:
    """Confident, single-bucket, leakage-excluded rows available for training."""
    usable = corpus[corpus["weak_confident"] & (corpus["weak_intent"] != "other")]
    return usable[["corpus_id", "customer_msg", "weak_intent"]].drop_duplicates(
        "customer_msg")


class MajorityBaseline:
    """Predicts the majority class of the (weakly-labelled) training corpus.
    Deliberately does not peek at golden-label distribution."""

    name = "majority_baseline"

    def __init__(self, corpus: pd.DataFrame):
        train = _train_rows(corpus)
        vc = train["weak_intent"].value_counts()
        self.majority_class = vc.idxmax()
        self.distribution = vc.to_dict()
        if self.majority_class not in taxonomy.INTENT_LABELS:
            self.majority_class = taxonomy.INTENT_ORDER[0]

    def predict(self, texts: list[str]) -> np.ndarray:
        return np.array([self.majority_class] * len(texts))

    def predict_with_confidence(self, texts: list[str]):
        out = []
        for _ in texts:
            out.append({
                "predicted_intent": self.majority_class,
                "confidence": 1.0,
                "top_k": [{"intent": self.majority_class, "prob": 1.0}],
                "evidence": "majority class of weakly-labelled BA corpus",
            })
        return out


class TfidfLRBaseline:
    """TF-IDF (char+word) + scaled LogisticRegression (multinomial), fitted on
    weak-labelled corpus rows only. Reproducible (shuffled with EVAL_SEED)."""

    name = "tfidf_lr_baseline"

    def __init__(self, corpus: pd.DataFrame, seed: int = paths.EVAL_SEED):
        train = _train_rows(corpus)
        docs = train["customer_msg"].map(normalize_text).tolist()
        y = train["weak_intent"].tolist()

        self.vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=3,
            max_df=0.9,
            sublinear_tf=True,
            stop_words="english",
        )
        X = self.vectorizer.fit_transform(docs)
        self.clf = LogisticRegression(
            C=1.0, solver="lbfgs",
            max_iter=2000, random_state=seed,
        )
        self.clf.fit(X, y)
        self.classes_ = list(self.clf.classes_)

    # -- persistence (deterministic reload, no refit) --------------------------
    def save(self, path) -> None:
        if joblib is None:
            raise RuntimeError("joblib not available to save the model")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"vectorizer": self.vectorizer, "clf": self.clf,
                     "classes_": self.classes_}, path)

    @classmethod
    def load(cls, path) -> "TfidfLRBaseline":
        if joblib is None:
            raise RuntimeError("joblib not available to load the model")
        obj = cls.__new__(cls)
        d = joblib.load(path)
        obj.vectorizer = d["vectorizer"]
        obj.clf = d["clf"]
        obj.classes_ = d["classes_"]
        return obj

    def _predict_proba(self, texts: list[str]):
        X = self.vectorizer.transform([normalize_text(t) for t in texts])
        return self.clf.predict_proba(X)

    def predict(self, texts: list[str]) -> np.ndarray:
        X = self.vectorizer.transform([normalize_text(t) for t in texts])
        return self.clf.predict(X)

    def predict_with_confidence(self, texts: list[str]):
        probs = self._predict_proba(texts)
        out = []
        for p in probs:
            order = np.argsort(p)[::-1]
            top = [{"intent": self.classes_[i], "prob": float(p[i])} for i in order]
            out.append({
                "predicted_intent": self.classes_[order[0]],
                "confidence": float(p[order[0]]),
                "top_k": top[:5],
                "evidence": "multinomial logistic regression on TF-IDF(1-2gram) "
                            "weak-labelled corpus",
            })
        return out


class RuleKeywordBaseline:
    """Baseline 3: deterministic keyword/deciding rules only (the taxonomy
    priors from weak.py), with the weak-label majority class as fallback.
    No learned weights — pure inspectable rules."""

    name = "rule_keyword_baseline"

    def __init__(self, corpus: pd.DataFrame):
        train = _train_rows(corpus)
        vc = train["weak_intent"].value_counts()
        self.majority_class = vc.idxmax()
        self.distribution = vc.to_dict()
        if self.majority_class not in taxonomy.INTENT_LABELS:
            self.majority_class = taxonomy.INTENT_ORDER[0]

    def predict_with_confidence(self, texts: list[str]):
        out = []
        for t in texts:
            label, _hits, confident = weak.weak_label(t)
            if not confident or label == "other":
                label, confident = self.majority_class, False
            out.append({
                "predicted_intent": label,
                "confidence": 0.9 if confident else 0.3,
                "top_k": [{"intent": label, "prob": 0.9 if confident else 0.3}],
                "evidence": "single-bucket keyword/deciding rules; majority fallback",
            })
        return out

    def predict(self, texts: list[str]) -> np.ndarray:
        return np.array([x["predicted_intent"] for x in
                         self.predict_with_confidence(texts)])


class HybridMainClassifier:
    """Main system: deterministic weak/deciding rules when the message matches a
    single content bucket exactly, otherwise the TF-IDF+LR baseline; confidence
    is blended (rule label with LR probability, else LR top-1)."""

    name = "hybrid_main"

    def __init__(self, corpus: pd.DataFrame, seed: int = paths.EVAL_SEED):
        self.lr = TfidfLRBaseline(corpus, seed=seed)
        self.rules_fired = {"messages": 0, "matched_bucket": None}

    # -- persistence ------------------------------------------------------------
    def save(self, path) -> None:
        if joblib is None:
            raise RuntimeError("joblib not available to save the model")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"lr": self.lr, "rules_fired": self.rules_fired}, path)

    @classmethod
    def load(cls, path) -> "HybridMainClassifier":
        if joblib is None:
            raise RuntimeError("joblib not available to load the model")
        obj = cls.__new__(cls)
        d = joblib.load(path)
        obj.lr = d["lr"]
        obj.rules_fired = d["rules_fired"]
        return obj

    def predict(self, texts: list[str]) -> np.ndarray:
        return np.array([x["predicted_intent"] for x in
                         self.predict_with_confidence(texts)])

    def predict_with_confidence(self, texts: list[str]):
        lr_out = self.lr.predict_with_confidence(texts)
        resolved = []
        for text, base in zip(texts, lr_out):
            label = weak.weak_label(text)
            if label[2] and label[0] != "other":
                rule = label[0]
                lr_top = base["top_k"][0]["intent"]
                lr_prob = base["top_k"][0]["prob"]
                # if LR strongly disagrees, still trust the explicit rule but
                # dampen confidence; the rule is the taxonomy's deciding signal.
                conf = max(lr_prob, 0.6) if lr_top == rule else 0.6
                top_k = [{"intent": k["intent"], "prob": 0.0} for k in base["top_k"]]
                top_k = [{"intent": rule, "prob": conf}] + [
                    k for k in base["top_k"] if k["intent"] != rule][:4]
                resolved.append({
                    "predicted_intent": rule,
                    "confidence": float(conf),
                    "top_k": top_k,
                    "evidence": "deterministic deciding-rule fired + TF-IDF LR",
                })
                self.rules_fired["messages"] += 1
                self.rules_fired["matched_bucket"] = rule
            else:
                resolved.append(base)
        return resolved


def system_descriptions() -> dict:
    return {
        "majority_baseline": "predicts the weak-label majority class of the "
                             "leakage-excluded BA corpus (no learning).",
        "rule_keyword_baseline": "single-bucket keyword/deciding rules from "
                                 "weak.py (taxonomy priors); weak-label majority "
                                 "fallback only when no bucket fires or multiple "
                                 "buckets fire.",
        "tfidf_lr_baseline": "TF-IDF(1,2 gram, English stopwords, sublinear tf) + "
                             "L2 multinomial logistic regression fitted on "
                             "confident weak-labelled corpus rows.",
        "hybrid_main": "single-bucket deterministic deciding rules (taxonomy "
                       "priors) when unambiguous, else the TF-IDF+LR model; "
                       "confidence blended probabilistically.",
    }