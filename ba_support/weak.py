"""Rule-based weak (distant) supervision over the BA corpus.

The golden set (200 examples) is strictly held out. To give the TF-IDF
baseline and the hybrid main classifier *any* supervised signal without using
golden labels, we distil coarse deterministic rules (one pass over the corpus)
into weak labels. These rules follow the keyword priors and taxonomy deciding
rules from Phase 2 (`analysis/scripts/build_golden_worksheet.py` and
`analysis/intent_taxonomy.csv`) — they are knowledge priors, NOT truth, and
only messages with a single unambiguous bucket match are kept for training.

Weak labels are emitted in the CANONICAL (finalized) label names
(`ba_support/taxonomy.py`); the raw golden-set file is mapped into the same
space via `taxonomy.to_canonical` at evaluation time.
"""

import re

# Ordered strongest-to-weakest so single-bucket matches are exact.
_RULES: list[tuple[str, list[re.Pattern[str]]]] = [
    (
        "account_access_or_security",
        [r"\baccount\b", r"\bhack(ed|ing)?\b", r"password", r"\blog ?in\b",
         r"\bsign ?in\b", r"identity", r"fraud", r"unauthor[isz]", r"suspicious",
         r"\bsecurity\b", r"\btheft\b", r"\bscam\b", r"someone else",
         r"executive club (account|number)", r"ec (account|number)"]
    ),
    (
        "refund_or_compensation",
        [r"refund", r"compen[sz]", r"reimburs", r"money back", r"\bowe(s)?\b",
         r"\bexpenses\b", r"\bvoucher\b", r"\bcredit\b", r"\bavios\b",
         r"european regulation 261", r"ec ?261", r"eu ?261", r"claim", r"chargeback"]
    ),
    (
        "baggage",
        [r"\bbags?\b", r"\bbaggage\b", r"\bluggage\b", r"\bsuitcase\b",
         r"\bcabin bag\b", r"\bhold bag\b", r"\bchecked bag\b", r"\bstroller\b",
         r"\bpram\b", r"lost baggage", r"\blost bag\b", r"\bbag\b"]
    ),
    (
        "seat_or_upgrade",
        [r"\bseat(s|ing)?\b", r"leg ?room", r"exit row", r"\bupgrade\b",
         r"pre-?book", r"\bbassinet\b", r"\baisle\b", r"window seat",
         r"\bsit together\b", r"seat reservation", r"business class chair",
         r"\bcabin\b"]
    ),
    (
        "website_or_app_issue",
        [r"\bwebsite\b", r"\bweb ?site\b", r"\bsite\b", r"\bapp\b",
         r"\bonline check-?in\b", r"manage my booking", r"\berror\b",
         r"\bfailed\b", r"unable to book", r"can't (book|check in|log)",
         r"cannot (book|check in|log)", r"\bpage\b", r"\bpayment step\b",
         r"check in online", r"\bcode\b (not|doesn't) work", r"\botter\b",
         r"\bscreen\b", r"\bloads?\s+(slow|not)", r"\bglitch\b", r"money taken"]
    ),
    (
        "flight_disruption",
        [r"cancelled?", r"cancellation", r"delayed?", r"\bdelay\b", r"diversion",
         r"diverted", r"stranded", r"\bstuck\b", r"overbooked", r"stand-?by",
         r"\brebook(ing|ed)?\b", r"re-?route", r"alternative flight",
         r"\bnext flight\b", r"missed (my )?flight", r"missed connection",
         r"waiting (since|for)", r"hours (at|in)", r"\btarmac\b", r"\bdelay at\b",
         r"got stuck", r"\bno flight\b", r"left without"]
    ),
    (
        "booking_change_or_cancellation",
        [r"change my (booking|flight|date|seat)", r"change the (date|flight|name)",
         r"\bamend", r"date change", r"\bswap\b", r"\bswitch (my |the )?",
         r"\bmove my\b", r"change (my )?flight", r"\bdifferent flight\b",
         r"\bflexible\b", r"name change", r"change of name", r"\bcancel(ling)? my\b",
         r"\btransfer my\b", r"\bpostpone\b", r"add (a )?(passenger|person|child)",
         r"remove (a )?(passenger|person)", r"add (my )?avios", r"book a different",
         r"re-?schedule"]
    ),
    (
        "complaint_or_human_assistance",
        [r"\bcomplaint\b", r"\bcomplain\b", r"\bcontact\b", r"\bemail\b",
         r"\bphone\b", r"\bcall\b", r"\bspeak to\b", r"\btalk to\b", r"\bhuman\b",
         r"no (one|body) (is )?responding", r"\bignore(d|s)?\b",
         r"customer relations", r"\bdm\b", r"case (number|id)", r"\bworst\b",
         r"\bawful\b", r"\bappalling\b", r"\bdisgusting\b", r"\brefuse\b",
         r"\bno one\b", r"no response", r"still waiting", r"\bhelp\b",
         r"disgraceful", r"\bterrible\b", r"\bshambles\b", r"\bfiasco\b"]
    ),
    (
        "information_or_policy",
        [r"how (do |can |to |much )", r"\bis\b (it |there )?(allowed|permitted)",
         r"what( is|'s| are| time| the|s)", r"when (is|do|will|can)",
         r"\bpolicy\b", r"\ballow(ed)?\b", r"requirements?", r"is it possible",
         r"do you (offer|provide|allow|have)", r"\binformation\b",
         r"please advise", r"tell me", r"know if", r"how many",
         r"is there", r"\bcost\b", r"\bprice\b", r"rules?", r"\bfee(s)?\b",
         r"can i (carry|take|bring)", r"what\u2019s the"]
    ),
    (
        "non_support_or_acknowledgement",
        [r"thank", r"thanks", r"\blove (it|you)\b", r"\bgreat\b", r"\bamazing\b",
         r"\bawesome\b", r"\bfantastic\b", r"\bwonderful\b", r"\bbrilliant\b",
         r"\bhaha\b", r"\blol\b", r"congrats", r"fan of", r"favourite airline",
         r"favorite airline", r"\bglad\b", r"\bdelighted\b", r"enjoy your",
         r"\bfabulous\b", r"safe flight", r"best flight", r"good luck",
         r"happy .{0,15}flight", r"\u270f", r"\ud83d\ude0a", r"\ud83d\udc4d",
         r"\ud83d\ude81", r"\ud83d\udc51", r"\ud83c\udf89"]
    ),
]

# If none of the above fire, the message is "other" (kept out of training).
OTHER_KEYWORDS = [r"weather", r"strike", r"football", r"airspace", r"privacy"]


def _compile() -> list[tuple[str, list[re.Pattern[str]]]]:
    return [(name, [re.compile(p, re.IGNORECASE) for p in pats])
            for name, pats in _RULES]


_COMPILED = _compile()


def weak_label(text: str, use_noise_fallback: bool = False) -> tuple[str, list, bool]:
    """Return (label, hits, confident).

    `confident` is True iff exactly one *content* bucket matched and (for a
    noise label) no content bucket simultaneously fired. Messages that match
    multiple content buckets are considered ambiguous and are NOT used for
    training (they stay in the corpus for retrieval only).
    """
    low = text.lower()
    hits = []
    for name, pats in _COMPILED:
        if any(p.search(low) for p in pats):
            hits.append(name)
    if not hits:
        if use_noise_fallback and not any(re.search(p, low, re.IGNORECASE) for p in OTHER_KEYWORDS):
            return "non_support_or_acknowledgement", ["non_support_or_acknowledgement"], True
        return "other", [], False
    content = [h for h in hits if h != "non_support_or_acknowledgement"]
    # noise bucket only wins if it is the ONLY bucket
    if "non_support_or_acknowledgement" in hits and not content:
        return "non_support_or_acknowledgement", hits, True
    if len(content) == 1:
        return content[0], hits, True
    return "other", hits, False  # ambiguous -> confident=False


def weak_bucket(text: str) -> str:
    return weak_label(text)[0]