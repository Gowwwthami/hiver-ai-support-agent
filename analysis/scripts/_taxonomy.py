"""Single source of truth for the intent/escalation/resolution label taxonomies.

These constants are imported by the golden-set assembly and validation scripts
so that label enums are checked against exactly one definition.
"""

INTENT_LABELS = [
    "refund_or_compensation",
    "booking_change_or_cancellation",
    "flight_disruption",
    "baggage",
    "seat_or_upgrade",
    "website_or_app_issue",
    "account_or_security",
    "contact_or_human_escalation_request",
    "information_or_policy",
    "noise_or_off_topic_or_ack",
]

CONFIDENCE_LEVELS = ["high", "medium", "low"]

ESCALATION_LABELS = ["AUTO_HANDLE", "ESCALATE", "UNCERTAIN"]

ESCALATION_REASONS = [
    "account_specific",
    "payment_or_refund",
    "compensation",
    "security_or_identity",
    "complaint_or_human_judgment",
    "legal_or_regulatory_risk",
    "unresolved_or_insufficient_information",
    "other",
    "",  # no reason when AUTO_HANDLE
]

RESOLUTION_OBSERVABLE = [
    "RESOLVED_IN_THREAD",
    "HANDOFF_OUTCOME_OFF_THREAD",
    "INFORMATION_PROVIDED",
    "APOLOGY_ONLY",
    "UNRESOLVED",
    "UNCLEAR",
]

RESOLUTION_TYPES = [
    "direct_answer",
    "action_offered",
    "link_or_reference",
    "empathy_only",
    "status_update",
    "none",
]

NOISE_FLAGS = ["TRUE", "FALSE"]

AMBIGUITY_FLAGS = [
    "none",
    "multi_intent",
    "unclear_intent",
    "truncated_captured",
    "template_or_bot",
    "multilingual",
    "other",
]

LABEL_COLUMNS = [
    "intent",
    "intent_confidence",
    "secondary_intent",
    "resolution_observable",
    "resolution_type",
    "escalation_label",
    "escalation_reason",
    "noise_flag",
    "ambiguity_flag",
]

# Enums that allow the empty string ("" means "not applicable" / "none").
OPTIONAL_ALLOW_EMPTY = ["secondary_intent", "escalation_reason"]

ENUM_MAP = {
    "intent": INTENT_LABELS,
    "intent_confidence": CONFIDENCE_LEVELS,
    "secondary_intent": INTENT_LABELS + [""],
    "resolution_observable": RESOLUTION_OBSERVABLE,
    "resolution_type": RESOLUTION_TYPES,
    "escalation_label": ESCALATION_LABELS,
    "escalation_reason": ESCALATION_REASONS,
    "noise_flag": NOISE_FLAGS,
    "ambiguity_flag": AMBIGUITY_FLAGS,
}

# Cross-field consistency rules checked by the validator.
# escalation_label == AUTO_HANDLE  -> escalation_reason must be ""
# escalation_label in {ESCALATE, UNCERTAIN} -> escalation_reason must be set
# noise_flag == TRUE -> intent should be noise_or_off_topic_or_ack
# secondary_intent != "" -> ambiguity_flag should note multi_intent