"""Text normalisation, redaction and near-duplicate helpers.

All functions are pure and deterministic. They are used at three points:
1. feature building (tokenisation for TF-IDF),
2. leakage guards (exact / near-duplicate message exclusion on retrieval),
3. evidence/person data redaction before any draft reply is emitted.
"""

import re
import unicodedata

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_MENTION_RE = re.compile(r"@[\w_]{1,40}")
_PNR_RE = re.compile(r"\b(?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]{6}\b")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{6,}\d)")
_MONEY_RE = re.compile(r"[£€$]\s?\d+(?:[.,]\d{1,2})?")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_WS_RE = re.compile(r"\s+")
_PUNCT_KEEP = re.compile(r"[^a-z0-9+&£€$\-]+")


def normalize_text(text: str) -> str:
    """Lowercase, normalise unicode, collapse whitespace, strip URLs/mentions."""
    if text is None:
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = _URL_RE.sub(" URL ", t)
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    t = _MENTION_RE.sub(" USER ", t)
    t = t.lower()
    return _WS_RE.sub(" ", t).strip()


def tokenize(text: str) -> list[str]:
    """Deterministic bag-of-words tokeniser (keeps money/phone as no tokens)."""
    t = normalize_text(text)
    t = _EMAIL_RE.sub(" EMAIL ", t)
    t = _MONEY_RE.sub(" MONEY ", t)
    t = _PHONE_RE.sub(" PHONE ", t)
    t = _PNR_RE.sub(" PNR ", t)
    tokens = _PUNCT_KEEP.split(t)
    return [tok for tok in tokens if tok]


def token_set(text: str) -> frozenset:
    return frozenset(tokenize(text))


def is_near_duplicate(a: str, b: str, threshold: float = 0.85) -> bool:
    """Jaccard overlap of the token sets above `threshold` counts as near-dup."""
    sa, sb = token_set(a), token_set(b)
    if not sa or not sb:
        return a.strip() == b.strip()
    inter = len(sa & sb)
    union = len(sa | sb)
    return union > 0 and inter / union >= threshold


def is_near_duplicate_tokens(query_set: frozenset, other_set: frozenset,
                             threshold: float = 0.85) -> bool:
    """Same measure, but with the query token set precomputed (retrieval hot path)."""
    if not query_set or not other_set:
        return False
    inter = len(query_set & other_set)
    union = len(query_set | other_set)
    return union > 0 and inter / union >= threshold


def redact(text: str) -> str:
    """Remove personal/transactable data so a draft replies never exposes them."""
    t = _URL_RE.sub("[link]", text)
    t = _MENTION_RE.sub("@British_Airways", t)
    t = _EMAIL_RE.sub("[email]", t)
    t = _MONEY_RE.sub("[amount]", t)
    t = _PNR_RE.sub("[reference]", t)
    t = _PHONE_RE.sub("[phone]", t)
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return _WS_RE.sub(" ", t).strip()


PII_PATTERNS = {
    "url": _URL_RE,
    "mention": _MENTION_RE,
    "email": _EMAIL_RE,
    "money": _MONEY_RE,
    "pnr/reference": _PNR_RE,
    "phone": _PHONE_RE,
}

# High-precision markers of fabricated / unsupported claims in a draft reply.
# NOTE: 'your booking reference is' (assertion) is a marker, but 'your booking
# reference' as a *request* ("please DM us your booking reference") is safe and
# is deliberately NOT a marker.
HALLUCINATION_MARKERS = {
    "processed your refund": "processed your refund",
    "has been refunded": "has been refunded",
    "payment has been": "payment has been",
    "you will receive": "you will receive",
    "your booking reference is": "your booking reference is",
    "i have checked": "i have checked",
    "i've checked": "i've checked",
    "i have upgraded": "i have upgraded",
    "confirmed your": "confirmed your",
    "your account has been": "your account has been",
    "we have issued": "we have issued",
    "refund of": "refund of",
    "compensation of": "compensation of",
}