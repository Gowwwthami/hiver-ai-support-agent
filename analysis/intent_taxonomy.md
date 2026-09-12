# British Airways — Intent Taxonomy (Phase 2)

The 10-label intent taxonomy used for the golden set. Machine-readable version:
`analysis/intent_taxonomy.csv`. Enums: `analysis/scripts/_taxonomy.py`.

## The 10 intents

| intent | definition | count | share |
|---|---:|---:|
| noise_or_off_topic_or_ack | Praise, thanks, banter, sarcastic venting with no actionable request, marketing interactions, or plain acknowledgement. | 43 | 21.5% |
| contact_or_human_escalation_request | Customer wants meaningful human contact: real contact numbers, human agents, complaint handling, or signals a need for human judgement (heated complaints, threats, legal/regulatory pressure, venting with emotional load). | 29 | 14.5% |
| flight_disruption | Customer reports a concrete disruption to their travel: delay, cancellation, diversion, long tarmac wait, misconnect, stranded/reroute, crew/aircraft problems. | 27 | 13.5% |
| refund_or_compensation | Customer claims money back: refund of fare/fees/taxes, EU261/EC261 compensation, Avios or points credit, or reimbursement of incurred expenses. | 22 | 11.0% |
| website_or_app_issue | Customer reports a technical failure of a BA digital channel: online check-in, Manage My Booking, website errors, payment step, seat-selection screen. | 21 | 10.5% |
| information_or_policy | Customer asks a factual question about BA policy, quick service facts, eligibility rules, or product facts that need no booking change. | 20 | 10.0% |
| baggage | Customer reports a baggage problem (delayed, damaged, lost, misrouted) or a carry/checked-item issue (drone, skateboard, laptop, instrument) tied to a specific journey. | 16 | 8.0% |
| booking_change_or_cancellation | Customer asks to modify, add-to, or cancel their own booking: rebooking, passenger changes, date/fare changes, Avios number or Executive Club detail adds to a PNR, name/passport amendments. | 12 | 6.0% |
| seat_or_upgrade | Customer asks about or wants seat selection, seat fees, upgrades, or cabin class on a specific booking. | 7 | 3.5% |
| account_or_security | Customer reports an Executive Club account or security problem: hacked account, suspect activity, lockout, or identity checks blocking access. | 3 | 1.5% |
| **Total** | | **200** | **100%** |

## Deciding rules (condensed)

Definitions, primary signals, deciding rules, example conversation IDs and
fuzzy-boundary conventions are in `intent_taxonomy.csv` and
`taxonomy_analysis.md` §1. Key pre-committed conventions:

- Money/points claims → `refund_or_compensation`.
- Leading concrete disruption → `flight_disruption` (+ secondary
  `refund_or_compensation` when a claim follows); pure eligibility/policy
  asks → `information_or_policy` / `refund_or_compensation`.
- Carry-on *items* on board → `baggage`; generic cabin-baggage *policy*
  questions → `information_or_policy`.
- Booking *data* amendments → `booking_change_or_cancellation`.
- Contact numbers / heated complaints / threats / legal-regulatory pressure /
  feedback-to-partner → `contact_or_human_escalation_request`.
- Effort-only praise or venting with no request → `noise_or_off_topic_or_ack`.
- Purely public-information answers → AUTO_HANDLE / INFORMATION_PROVIDED.
- The BA pattern «send us your booking reference via DM» → ESCALATE with the
  reason matching the account-gated data.