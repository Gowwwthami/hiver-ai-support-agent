"""Leakage isolation: golden-set manifests and customer-level exclusion rules.

The central rule of this project (see README / docs/DATA_CONTRACT.md):

    No golden-set conversation, and no conversation whose *customer* appears
    inside a golden conversation, may enter the retrieval corpus, the
    classifier's training set, few-shot demonstrations, or any artifact that a
    tested example is learned from. Semantic leakage is mitigated by the same
    conversation/customer-level exclusion plus near-duplicate filtering at
    retrieval time.
"""

import hashlib
import json
import re

import pandas as pd

from . import paths


def audit_conv_ids() -> set[int]:
    if not paths.AUDIT_POOL_MD.exists():
        return set()
    body = paths.AUDIT_POOL_MD.read_text(encoding="utf-8", errors="ignore")
    return {int(m) for m in re.findall(r"## Conversation (\d+)", body)}


def golden_panel() -> pd.DataFrame:
    """The shipped golden set (dtype-stable)."""
    return pd.read_csv(paths.GOLDEN_CSV, dtype=str, keep_default_na=False)


def golden_conv_ids() -> set[int]:
    return {int(x) for x in golden_panel()["conv_id"]}


def golden_customer_ids() -> set[str]:
    """Customers appearing in any golden conversation (conv-level, from cache)."""
    cache_file = paths.GOLDEN_CUSTOMER_IDS_JSON
    if cache_file.exists():
        return set(json.loads(cache_file.read_text(encoding="utf-8")))
    from .corpus import _load_conversations  # avoid import cycle

    convs = _load_conversations()
    golden = set(golden_conv_ids())
    custs = set(convs.loc[(convs["conv_id"].isin(golden)) & (convs["inbound"]), "author_id"])
    paths.ensure_dir(paths.CACHE_DIR)
    cache_file.write_text(
        json.dumps(sorted(custs)), encoding="utf-8")
    return custs


def conv_customer_ids(conv_id: int) -> set[str]:
    """Author ids of customer (inbound) turns of one conversation."""
    from .corpus import _load_conversations

    convs = _load_conversations()
    sub = convs[(convs["conv_id"] == conv_id) & (convs["inbound"])]
    return set(sub["author_id"])


def hash_message(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()


def is_golden_isolated(corpus: pd.DataFrame) -> bool:
    """True iff `corpus` contains no golden conversation id."""
    if corpus is None or corpus.empty:
        return False
    return not bool(set(corpus["conv_id"].astype(int)) & golden_conv_ids())


def customer_isolation_stats(corpus: pd.DataFrame) -> dict:
    """Number of corpus rows/conversations sharing a customer with the golden set."""
    golds = golden_customer_ids()
    mask = corpus["customer_author_id"].astype(str).isin(golds)
    return {
        "golden_customer_share_rows": int(mask.sum()),
        "golden_customer_share_convs": int(corpus.loc[mask, "conv_id"].nunique()),
    }