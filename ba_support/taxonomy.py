"""Canonical label enums for the final system (single source of truth).

The Phase-2 shipped taxonomy lived in `analysis/scripts/_taxonomy.py`. After the
Phase-2.1 label audit and the decision to freeze names for the final build, the
following THREE names are adopted as the **canonical** label space (meanings and
boundary rules are unchanged):

    contact_or_human_escalation_request -> complaint_or_human_assistance
    noise_or_off_topic_or_ack           -> non_support_or_acknowledgement
    account_or_security                 -> account_access_or_security

The shipped golden-set file (`evaluation/golden_set.csv`) stores the final,
human-reviewed label decisions while keeping the repository-wide legacy
spellings for these three names; evaluation maps them via
`taxonomy.to_canonical` so the metrics are computed in the canonical space.
`analysis/scripts/finalize_golden_set.py` is what promoted the recorded human
finals into the golden file; the pre-review assistant draft remains archived in
`evaluation/_labels.tsv`. Everything the final system builds (weak labels, model
predictions, confusion matrices, reports) uses the canonical names.
"""

import sys
from pathlib import Path

from . import paths

_TAXONOMY_DIR = paths.ROOT / "analysis" / "scripts"
if str(_TAXONOMY_DIR) not in sys.path:
    sys.path.insert(0, str(_TAXONOMY_DIR))

import _taxonomy as _t  # noqa: E402

LEGACY_INTENT_LABELS = list(_t.INTENT_LABELS)
CONFIDENCE_LEVELS = list(_t.CONFIDENCE_LEVELS)
ESCALATION_LABELS = list(_t.ESCALATION_LABELS)
ESCALATION_REASONS = [r for r in _t.ESCALATION_REASONS if r]
RESOLUTION_OBSERVABLE = list(_t.RESOLUTION_OBSERVABLE)
RESOLUTION_TYPES = list(_t.RESOLUTION_TYPES)
NOISE_FLAGS = list(_t.NOISE_FLAGS)
AMBIGUITY_FLAGS = list(_t.AMBIGUITY_FLAGS)

# ---- canonical (finalized) label space -------------------------------------
LEGACY_TO_CANONICAL = {
    "contact_or_human_escalation_request": "complaint_or_human_assistance",
    "noise_or_off_topic_or_ack": "non_support_or_acknowledgement",
    "account_or_security": "account_access_or_security",
}

INTENT_LABELS = [
    "non_support_or_acknowledgement",
    "complaint_or_human_assistance",
    "flight_disruption",
    "refund_or_compensation",
    "website_or_app_issue",
    "information_or_policy",
    "baggage",
    "booking_change_or_cancellation",
    "seat_or_upgrade",
    "account_access_or_security",
]
INTENT_ORDER = sorted(INTENT_LABELS)  # stable ordering for tables/matrices

# Back-compat alias used by the review-recommendation artifact builder.
RENAME_PROPOSALS = dict(LEGACY_TO_CANONICAL)

ESCALATION_REASON_FOR_AUTO = ""

# Gold routed away from AUTO_HANDLE while the system predict AUTO_HANDLE = unsafe.
UNSAFE_AUTO_IF_GOLD = {"ESCALATE", "UNCERTAIN"}

SHORT_NAMES = {
    "non_support_or_acknowledgement": "non-support/ack",
    "complaint_or_human_assistance": "complaint/human",
    "flight_disruption": "disruption",
    "refund_or_compensation": "refund",
    "website_or_app_issue": "website/app",
    "information_or_policy": "info/policy",
    "baggage": "baggage",
    "booking_change_or_cancellation": "booking_change",
    "seat_or_upgrade": "seat",
    "account_access_or_security": "account/security",
}


def to_canonical(label: str) -> str:
    """Map a legacy (shipped golden-set) label to its canonical name."""
    return LEGACY_TO_CANONICAL.get(label, label)


def display_label(label: str) -> str:
    """Render a label in the canonical namespace."""
    return to_canonical(label)