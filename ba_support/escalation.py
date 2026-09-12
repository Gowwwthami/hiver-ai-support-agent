"""Deterministic operational escalation policy.

Single rule (adopted from analysis/PHASE2_1_LABEL_AUDIT.md §6; independent of
intent):

    AUTO_HANDLE  iff a safe autonomous agent can produce a complete, accurate,
                  safe public answer from general policy / historical evidence
                  WITHOUT account-specific data or human judgment.
    ESCALATE     otherwise, with a structured reason (escalation_taxonomy.csv).
    UNCERTAIN    only when the customer-side evidence genuinely cannot decide.

The policy is NOT a mirror of BA's historical "DM us" habit.
"""

import re

from . import taxonomy

_AUTO_INTENTS = {"information_or_policy", "non_support_or_acknowledgement"}

# Factual intents whose AUTO_HANDLE branch needs usable public evidence; without
# it the system escalates instead of hallucinating a policy answer.
_EVIDENCE_GATED_AUTO_INTENTS = {
    "information_or_policy", "website_or_app_issue", "baggage", "seat_or_upgrade",
}

_MONEY_RX = re.compile(r"refund|compen[sz]|reimburs|money back|\bcost\b|\bfee\b|"
                       r"\bcharge[d]?\b|voucher|\bcredit\b|avios|\bclaim\b",
                       re.IGNORECASE)
_ACCOUNT_RX = re.compile(r"my booking|\bpnr\b|booking reference|executive club|"
                         r"\bec number\b|\blog ?in\b|password|account|household",
                         re.IGNORECASE)
_SECURITY_RX = re.compile(r"hack|\bsecurity\b|identity|fraud|unauthor[isz]|"
                          r"suspicious|theft|scam|someone else|password",
                          re.IGNORECASE)
_LEGAL_RX = re.compile(r"\blawyer\b|\battorney\b|\bsue\b|\bsuing\b|\bsues\b|"
                       r"\blaw\b|\bsolicitor\b|\blawsuit\b|\blegal\b|\bregulatory\b|"
                       r"\bstatutory\b|\bsmall claims\b|\bcourt\b|\bofficer\b",
                       re.IGNORECASE)
_COMPLAINT_RX = re.compile(r"complaint|worst|awful|appalling|disgusting|"
                           r"disgraceful|terrible|shambles|fiasco|no response|"
                           r"still waiting|ignore", re.IGNORECASE)
_MONEY_ADJUDICATION_RX = re.compile(r"eu261|ec ?261|regulation 261|compensation",
                                    re.IGNORECASE)
_HUMAN_CALLBACK_RX = re.compile(r"call me|phone me|speak to|talk to|human agent|"
                                r"customer service|contact me", re.IGNORECASE)
_BOOKING_ACTION_RX = re.compile(r"change my|amend|date change|transfer|"
                                r"cancel(ling)? my|swap|move my|add (a )?(passenger|"
                                r"avios|child)|remove (passenger|person)|"
                                r"name change|rebook", re.IGNORECASE)
_SEAT_OP_RX = re.compile(r"switched|changed|reassign|at check-?in|moved (me |us |my )",
                         re.IGNORECASE)
_SEAT_MONEY_RX = re.compile(r"cost|price|paid|fee|charge|refund", re.IGNORECASE)
_DISRUPT_ACTION_RX = re.compile(r"stranded|next flight|rebook|alternative flight|"
                                r"reroute|re-?route|help me get|sort (out )?(my )?|"
                                r"stand-?by", re.IGNORECASE)
_CONCRETE_PROBLEM_RX = re.compile(r"error|fail|broken|wrong|bidirectional|doesn.t work|"
                                  r"not working|blocked|cannot|can't|\b404\b",
                                  re.IGNORECASE)


def decide(customer_message: str, intent: str, confidence: float,
           ambiguity_flag: str = "none", can_handle_public: bool = True):
    """Return dict(label, reason, confidence, policy_debug).

    `can_handle_public` is a pipeline-level guard for intents whose answer would
    need account data (set False by the generation layer when no public evidence
    exists for a factual answer).
    """
    low = customer_message.lower()
    debug = []

    def _esc(reason, note):
        return {"label": "ESCALATE", "reason": reason,
                "confidence": round(float(confidence), 3),
                "policy_debug": note}

    def _auto(reason_="", note=""):
        return {"label": "AUTO_HANDLE", "reason": "",
                "confidence": round(float(confidence), 3),
                "policy_debug": reason_ or note}

    def _unc(note):
        return {"label": "UNCERTAIN", "reason": "unresolved_or_insufficient_information",
                "confidence": round(float(confidence), 3), "policy_debug": note}

    # 1) safety/legal/security markers are evaluated BEFORE any intent branch so
    #    routing stays independent of the predicted intent. A legal or security
    #    signal must never become AUTO_HANDLE merely because the classifier
    #    predicted a safe-by-default intent such as information_or_policy.
    if _SECURITY_RX.search(low):
        return _esc("security_or_identity", "identity/security marker detected")
    if _LEGAL_RX.search(low):
        return _esc("legal_or_regulatory_risk", "legal/regulatory exposure detected")

    # 1b) evidence-sufficiency gate: a factual AUTO_HANDLE requires usable
    # public evidence; without it we escalate rather than hallucinate policy.
    if not can_handle_public and intent in _EVIDENCE_GATED_AUTO_INTENTS:
        return _esc("unresolved_or_insufficient_information",
                    "no usable public evidence for a factual auto answer")

    # 2) intents that are safe-by-definition when a public answer exists
    if intent == "information_or_policy":
        if _HUMAN_CALLBACK_RX.search(low) and _ACCOUNT_RX.search(low):
            return _esc("account_specific",
                        "info request tied to the caller's own booking")
        return _auto(reason_="public factual/policy answer")

    if intent == "non_support_or_acknowledgement":
        return _auto(reason_="public acknowledgement/decline; no account data")

    if intent == "account_access_or_security":
        return _esc("security_or_identity" if _SECURITY_RX.search(low)
                    else "account_specific",
                    "account/security routing is always human")

    if intent == "refund_or_compensation":
        if _MONEY_ADJUDICATION_RX.search(low) or "compensation" in low:
            return _esc("compensation", "EU261/compensation claim needs adjudication")
        return _esc("payment_or_refund", "refund/payment dispute needs the payments team")

    if intent == "flight_disruption":
        if _DISRUPT_ACTION_RX.search(low) and _ACCOUNT_RX.search(low):
            return _esc("account_specific", "reroute/rebooking of *my* flight")
        if _DISRUPT_ACTION_RX.search(low):
            return _esc("account_specific", "needs booking/PNR to rebook")
        if _MONEY_RX.search(low):
            return _esc("compensation", "disruption + money/compensation wording")
        return _auto(reason_="public disruption status/info/empathy")

    if intent == "booking_change_or_cancellation":
        if _BOOKING_ACTION_RX.search(low) and _ACCOUNT_RX.search(low):
            return _esc("account_specific", "amends/cancels the customer's own booking")
        if _BOOKING_ACTION_RX.search(low):
            return _esc("account_specific", "booking data-change requires PNR lookup")
        return _auto(reason_="public self-service/policy guidance")

    if intent == "seat_or_upgrade":
        if _SEAT_OP_RX.search(low):
            return _esc("account_specific", "operational re-seat requires PNR lookup")
        if _SEAT_MONEY_RX.search(low):
            return _esc("complaint_or_human_judgment",
                        "seat/upgrade cost complaint needs judgment")
        if _ACCOUNT_RX.search(low):
            return _esc("account_specific", "seat/upgrade action on *my* booking")
        return _auto(reason_="public seat policy/availability answer")

    if intent == "baggage":
        if _MONEY_RX.search(low) or "compensation" in low or "claim" in low:
            return _esc("compensation", "baggage loss/damage claim needs adjudication")
        if _ACCOUNT_RX.search(low):
            return _esc("account_specific", "baggage status lookup on *my* trip")
        return _auto(reason_="public baggage policy / item answer")

    if intent == "website_or_app_issue":
        if _ACCOUNT_RX.search(low) and _CONCRETE_PROBLEM_RX.search(low):
            return _esc("account_specific",
                        "technical fault on the customer's own account/booking")
        if _ACCOUNT_RX.search(low):
            return _esc("account_specific", "site fault tied to an account/booking")
        return _auto(reason_="public generic troubleshooting")

    if intent == "complaint_or_human_assistance":
        # legal/regulatory exposure is handled globally above the intent
        # branches, so every non-legal path that lands here is routed normally.
        if _MONEY_RX.search(low):
            return _esc("complaint_or_human_judgment", "high-value complaint with money claim")
        if _COMPLAINT_RX.search(low) and _ACCOUNT_RX.search(low):
            return _esc("account_specific", "complaint tied to the customer's booking")
        if _HUMAN_CALLBACK_RX.search(low):
            return _esc("complaint_or_human_judgment", "explicit human-callback request")
        if _COMPLAINT_RX.search(low):
            return _esc("complaint_or_human_judgment",
                        "investigation-worthy complaint requires a human")
        return _auto(reason_="contact/channel question or plain venting; public")

    # fallback
    if not can_handle_public:
        return _esc("unresolved_or_insufficient_information",
                    "no safe public answer available")
    if ambiguity_flag == "unclear_intent" and confidence < 0.5:
        return _unc("customer-side evidence cannot decide routing")
    return _auto(reason_="fallback AUTO_HANDLE for unruled intent")


def policy_documentation() -> str:
    return (
        "AUTO_HANDLE iff a safe autonomous agent can produce a complete, "
        "accurate, safe public answer from general policy/historical evidence "
        "without account-specific data or human judgment; otherwise ESCALATE "
        "with a structured reason; UNCERTAIN only when the customer side cannot "
        "decide. Historical BA behavior is evidence, never autonomous-truth."
    )