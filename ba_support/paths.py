"""Repository anchors, dataset locations and seed policy (single source of truth).

Everything the pipeline reads/writes derives from these constants so that no
script hard-codes absolute paths and all runs work from a clean checkout.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---- dataset / caches -----------------------------------------------------
RAW_TWCS_CSV = ROOT / "data_extracted" / "twcs" / "twcs.csv"
CACHE_DIR = ROOT / "analysis" / "cache"
CONVERSATIONS_PARQUET = CACHE_DIR / "conversations.parquet"
CONVERSATION_SUMMARY_PARQUET = CACHE_DIR / "conversation_summary.parquet"
CORPUS_PARQUET = CACHE_DIR / "retrieval_corpus.parquet"
TRAINABLE_CORPUS_PARQUET = CACHE_DIR / "trainable_corpus.parquet"
GOLDEN_CUSTOMER_IDS_JSON = CACHE_DIR / "golden_customer_ids.json"

# ---- golden set / annotation artifacts ------------------------------------
EVAL_DIR = ROOT / "evaluation"
GOLDEN_CSV = EVAL_DIR / "golden_set.csv"
GOLDEN_JSONL = EVAL_DIR / "golden_set.jsonl"
SPLIT_IDS_CSV = EVAL_DIR / "golden_split_ids.csv"
REVIEW_QUEUE_CSV = EVAL_DIR / "golden_set_review_queue.csv"
RECOMMENDATIONS_CSV = EVAL_DIR / "golden_set_recommendations.csv"

# ---- Phase-1 audit manifest -----------------------------------------------
AUDIT_POOL_MD = ROOT / "analysis" / "candidate_conversations" / "British_Airways.md"

# ---- outputs ---------------------------------------------------------------
RESULTS_JSON = EVAL_DIR / "results.json"
RESULTS_MD = EVAL_DIR / "EVALUATION_REPORT.md"
PREDICTIONS_CSV = EVAL_DIR / "predictions.csv"
FAILURES_MD = ROOT / "analysis" / "TOP_5_FAILURES.md"
REVIEW_SUMMARY_MD = EVAL_DIR / "review_summary.md"

BRAND = "British_Airways"

# ---- seeds (determinism) ---------------------------------------------------
# Phase-2 golden sampling used seed 2026 (unchanged). Evaluation/model runs
# use a separate explicit seed so that adding evaluation tooling can never
# perturb the shipped golden sample.
SAMPLING_SEED = 2026
EVAL_SEED = 42

# ---- knobs -----------------------------------------------------------------
DEFAULT_TOP_K = 3
MIN_EVIDENCE_SIMILARITY = 0.10


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path