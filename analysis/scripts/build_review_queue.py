"""Build the human-review queue for the Phase-2 golden set (PHASE 2.1).

Reads evaluation/golden_set.csv and produces evaluation/golden_set_review_queue.csv
with, per example:
  - current_*  : the assistant-drafted (proposed) label as shipped;
  - proposed_* : the audit's proposition for the human reviewer (XML-free,
                 current-namespace names OR proposed rename targets);
  - review_priority / review_reason : deterministic priority + audit rationale;
  - human_final_* : ALWAYS EMPTY - filled only by the human reviewer.

This script NEVER writes to golden_set.csv/_labels.tsv. Human labels are not
fabricated anywhere. Audit rationale is documented in analysis/PHASE2_1_LABEL_AUDIT.md.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "evaluation" / "golden_set.csv"
OUT = ROOT / "evaluation" / "golden_set_review_queue.csv"

OLD_CONTACT = "contact_or_human_escalation_request"
NEW_CONTACT = "complaint_or_human_assistance"
OLD_NOISE = "noise_or_off_topic_or_ack"
NEW_NOISE = "non_support_or_acknowledgement"
OLD_ACCT = "account_or_security"
NEW_ACCT = "account_access_or_security"

# ---- Audit propositions: only intent/escalation changes we actually propose.
# (intent, escalation_label, escalation_reason, note)
A = {
    # contact class (29)
    "BA_105364": (NEW_CONTACT, "AUTO_HANDLE", "", "vague airline-performance complaint; public empathy+probe suffices, no account data"),
    "BA_131149": (NEW_CONTACT, "ESCALATE", "account_specific", "explicit human-callback request re flight-time change; needs booking lookup"),
    "BA_135900": (NEW_CONTACT, "ESCALATE", "payment_or_refund", "channel-blocked follow-up inside a refund thread (later turn); refund routing retained"),
    "BA_147482": (NEW_CONTACT, "ESCALATE", "security_or_identity", "boarding-document identity crisis; autonomously unsolvable (alt reason legal_or_regulatory_risk)"),
    "BA_152445": (NEW_CONTACT, "AUTO_HANDLE", "", "complaint-venting, no concrete ask; public empathy + open prompt"),
    "BA_163041": ("information_or_policy", "AUTO_HANDLE", "", "asks for online-chat channel; public contact info (secondary booking_change kept)"),
    "BA_167696": (NEW_NOISE, "AUTO_HANDLE", "", "sarcastic venting, no actionable request"),
    "BA_278441": (NEW_CONTACT, "AUTO_HANDLE", "", "route-frequency complaint; public empathy + feedback capture"),
    "BA_32854": (NEW_CONTACT, "AUTO_HANDLE", "", "lounge food complaint + photo; public apology + capture feedback; no account data"),
    "BA_331684": (NEW_CONTACT, "ESCALATE", "complaint_or_human_judgment", "6,500 EUR business-class complaint; money + investigation, human needed"),
    "BA_334633": (NEW_CONTACT, "AUTO_HANDLE", "", "777 experience complaint; public apology + feedback"),
    "BA_33704": (NEW_CONTACT, "ESCALATE", "account_specific", "needs today-flight sorting; booking lookup required (reason proposed change)"),
    "BA_337964": (NEW_NOISE, "AUTO_HANDLE", "", "sarcastic cost jibe, no request"),
    "BA_349968": ("information_or_policy", "AUTO_HANDLE", "", "contact-number lookup; pure public info"),
    "BA_351856": (NEW_CONTACT, "ESCALATE", "legal_or_regulatory_risk", "lawsuit service address query; legal exposure, human handling"),
    "BA_358073": (NEW_CONTACT, "AUTO_HANDLE", "", "vague connection-experience complaint; public probe (alt: non_support / UNCERTAIN)"),
    "BA_410381": (NEW_CONTACT, "AUTO_HANDLE", "", "in-flight product complaint; apology + feedback capture"),
    "BA_466171": (NEW_CONTACT, "AUTO_HANDLE", "", "airport-conditions complaint + marketing-email displeasure; public apology + offer to help"),
    "BA_495495": (NEW_CONTACT, "UNCERTAIN", "complaint_or_human_judgment", "later-position no-reply complaint in racing thread; routing undecidable"),
    "BA_542898": (NEW_CONTACT, "ESCALATE", "complaint_or_human_judgment", "on-site lounge incident; staff escalation beyond a public answer"),
    "BA_567068": ("information_or_policy", "AUTO_HANDLE", "", "contact method while abroad; public contact info"),
    "BA_579921": ("information_or_policy", "AUTO_HANDLE", "", "US toll-free number trouble; public contact info"),
    "BA_627007": (NEW_CONTACT, "ESCALATE", "complaint_or_human_judgment", "two-month mishandled complaint + insurance redirect; investigation needed"),
    "BA_689051": (NEW_CONTACT, "UNCERTAIN", "complaint_or_human_judgment", "\"about to cancel BA\" - object unclear; routing undecidable"),
    "BA_71213": (NEW_NOISE, "AUTO_HANDLE", "", "industry comment/venting, not a BA support request"),
    "BA_737110": (NEW_CONTACT, "ESCALATE", "complaint_or_human_judgment", "prize-flights booking hassle; process complaint, human follow-up"),
    "BA_749232": (NEW_CONTACT, "AUTO_HANDLE", "", "service-line improvement ask; public apology + feedback (no account data)"),
    "BA_755802": (NEW_NOISE, "AUTO_HANDLE", "", "pure service venting, no request"),
    "BA_787976": (NEW_CONTACT, "ESCALATE", "complaint_or_human_judgment", "partner-operator (RSA/Comair) feedback; partner routing is material"),
    # account/security class (3)
    "BA_132217": (NEW_ACCT, "ESCALATE", "security_or_identity", "hacked EC account; identity verification required"),
    "BA_479193": (NEW_ACCT, "ESCALATE", "account_specific", "household-account name-removal error = ACCOUNT MANAGEMENT not security; shows class too narrow"),
    "BA_729813": (NEW_ACCT, "ESCALATE", "security_or_identity", "password-reset emails not arriving; account-access + identity path"),
    # seat class (7)
    "BA_288483": ("seat_or_upgrade", "AUTO_HANDLE", "", "seat reassignment policy answer is public: AUTO_HANDLE consistent"),
    "BA_423824": ("seat_or_upgrade", "ESCALATE", "account_specific", "seat selection for medical need; needs PNR"),
    "BA_568345": ("seat_or_upgrade", "ESCALATE", "complaint_or_human_judgment", "seat-pricing complaint; cost/what-it-is judgment needs human"),
    "BA_577348": ("seat_or_upgrade", "AUTO_HANDLE", "", "legroom complaint; public apology + feedback capture"),
    "BA_578442": ("seat_or_upgrade", "ESCALATE", "complaint_or_human_judgment", "upgrade payment failure; needs account/payment check"),
    "BA_705984": (NEW_NOISE, "AUTO_HANDLE", "", "birthday-upgrade banter, no real request (was seat, multi-intent)"),
    "BA_707914": ("seat_or_upgrade", "ESCALATE", "account_specific", "seat switched at check-in; needs PNR/operational lookup"),
    # escalation-policy deep-dive extras (intent kept unless stated)
    "BA_261585": ("flight_disruption", "AUTO_HANDLE", "", "delay-care claim location is public info; AUTO_HANDLE matches operational rule"),
    "BA_150929": ("booking_change_or_cancellation", "ESCALATE", "account_specific", "objective = same-day flight change; needs PNR (intent shifted from info)"),
    "BA_255518": ("booking_change_or_cancellation", "AUTO_HANDLE", "", "MMB self-service change is a complete public answer"),
    "BA_26002": ("information_or_policy", "AUTO_HANDLE", "", "booking class is shown on e-ticket / MMB: complete public answer (ESCALATE alternative noted)"),
    "BA_472183": ("website_or_app_issue", "ESCALATE", "account_specific", "confirming a booking exists needs PNR lookup; escalate (spam/MMB guidance public first)"),
}

# names under review for possible rename (flagged HIGH via class membership)
RENAME_REVIEW = {OLD_CONTACT, OLD_NOISE, OLD_ACCT, "seat_or_upgrade"}


def priority_for(row: pd.Series) -> tuple[str, list[str]]:
    reasons = []
    intent = row["intent"]
    esc = row["escalation_label"]
    amb = row["ambiguity_flag"]
    sec = row["secondary_intent"]
    first = row["is_first_inbound"].strip().lower() == "true"
    conf = row["intent_confidence"]

    high = False
    if intent in RENAME_REVIEW:
        high = True
        reasons.append("taxonomy class under rename/boundary review")
    if esc == "UNCERTAIN":
        high = True
        reasons.append("UNCERTAIN escalation")
    if amb != "none":
        high = True
        reasons.append(f"ambiguous ({amb})")
    if sec != "":
        high = True
        reasons.append("multi-intent / secondary intent set")
    if not first:
        high = True
        reasons.append("later-position conversation example")
    if conf == "low":
        high = True
        reasons.append("low confidence")
    if high:
        return "HIGH", reasons

    medium = False
    if conf == "medium":
        medium = True
        reasons.append("medium confidence")
    if row["noise_flag"] == "TRUE":
        medium = True
        reasons.append("noise-flagged wording")
    if medium:
        return "MEDIUM", reasons
    return "LOW", ["clear high-confidence example"]


def main():
    df = pd.read_csv(GOLDEN, dtype=str, keep_default_na=False)

    rows = []
    for _, r in df.iterrows():
        eid = r["example_id"]
        prop = A.get(eid)
        if prop is not None:
            p_intent, p_esc, p_reason, note = prop
            intent_status = "KEEP_PROPOSED" if p_intent == r["intent"] else "CHANGE_PROPOSED"
            esc_status = "KEEP_PROPOSED" if p_esc == r["escalation_label"] else "CHANGE_PROPOSED"
        else:
            p_intent, p_esc, p_reason = r["intent"], r["escalation_label"], r["escalation_reason"]
            intent_status, esc_status = "KEEP_PROPOSED", "KEEP_PROPOSED"
            note = ""

        prio, reasons = priority_for(r)
        listed = "audit deep-dive (§" + str(
            1 if r["intent"] == OLD_CONTACT else (4 if r["intent"] == OLD_ACCT else 5)
        ) + ")" if eid in A else ""
        review_reason = "; ".join([x for x in [listed, "; ".join(reasons), note] if x])

        rows.append({
            "example_id": eid,
            "customer_message": r["customer_message"],
            "current_intent": r["intent"],
            "proposed_intent": p_intent,
            "intent_review_status": intent_status,
            "current_escalation": r["escalation_label"],
            "proposed_escalation": p_esc,
            "escalation_review_status": esc_status,
            "current_escalation_reason": r["escalation_reason"],
            "proposed_escalation_reason": p_reason,
            "ambiguity_flag": r["ambiguity_flag"],
            "review_priority": prio,
            "review_reason": review_reason,
            "human_final_intent": "",
            "human_final_escalation": "",
            "human_final_reason": "",
            "human_notes": "",
        })

    out = pd.DataFrame(rows).sort_values(
        ["review_priority", "example_id"],
        key=lambda s: s.map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}) if s.name == "review_priority" else s,
    ).reset_index(drop=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print(f"Wrote {OUT} ({len(out)} rows)")
    print(out["review_priority"].value_counts().to_string())
    print()
    n_int_chg = (out["proposed_intent"] != out["current_intent"]).sum()
    n_esc_chg = (out["proposed_escalation"] != out["current_escalation"]).sum()
    print(f"intent changes proposed: {n_int_chg}")
    print(f"escalation changes proposed: {n_esc_chg}")
    blanks = (out["human_final_intent"] == "") & (out["human_final_escalation"] == "") & (out["human_notes"] == "")
    print(f"human_final fields all blank: {bool(blanks.all())}")


if __name__ == "__main__":
    main()