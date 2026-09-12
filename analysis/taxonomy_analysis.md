# British Airways — Intent Taxonomy, Label Conventions & Distribution

**Phase 2 · British_Airways · 200-example golden label set**

This document records *how* the taxonomy and the 200 labels were produced,
how fuzzy cases were resolved, and what the label distribution shows. It is the
annotator-facing and reviewer-facing companion to `golden_set.csv`.
The machine-readable enums live in `analysis/scripts/_taxonomy.py`.

---

## 1. Where the taxonomy came from

1. **Phase 1 audit (ground source).** The 9 recurring categories identified in
   `analysis/british_airways_qualitative_audit.md` (n=50 hand-categorised
   threads) were the starting point: refund/compensation, disruption,
   seat dispute, account security, IT/website, booking change, baggage,
   noise, contact/routing.
2. **Phase 2 confirmation pass.** All 200 worksheet rows were read end-to-end
   before labelling. Categories that were thin or that blended were re-cut
   into the final **10-label** set (`evaluation/intent_taxonomy.csv`),
   including splitting *contact numbers* from *human-escalation requests*
   into one combined intent, and adding an explicit *acknowledgement* arm to
   the noise label.
3. **Conventions on the two genuinely fuzzy boundaries** (agreed before and
   applied consistently; violations were caught in the validator):

   | Boundary | Rule applied |
   |---|---|
   | disruption ↔ compensation | Leading disruption → `flight_disruption` (+ secondary `refund_or_compensation`). Claim-with-no-disruption-narrative or a pure policy/eligibility ask → `refund_or_compensation` / `information_or_policy`. |
   | site login ↔ account security | One-time code / login / page errors → `website_or_app_issue`. Hacked account, suspect activity, identity check-gate → `account_or_security`. |

   Additional conventions that came out of the reading pass:

   - Money/points claims → `refund_or_compensation` (including Avios collection
     and duty-free over-charges).
   - Carry-on *items* on board (drone, skateboard, laptop) → `baggage`
     (fruits/dried foods flagged `multilingual`/`unclear_intent`).
   - Booking *data* changes (name, passport, date, Avios-add) → `booking_change_or_cancellation`.
   - Contact numbers, heated complaints, threats, legal/regulatory pressure,
     feedback-to-partner → `contact_or_human_escalation_request`.
   - Purely public-information answers (check-in times, policy facts) → `AUTO_HANDLE`
     with `resolution_observable = INFORMATION_PROVIDED`.
   - Praise, thanks, banter, and sarcastic venting *without an actionable
     request* → `noise_or_off_topic_or_ack` (`noise_flag = TRUE`).
   - The dominant BA pattern `"send us your booking reference via DM"` →
     `escalation_label = ESCALATE`, reason depending on the account-gated data
     (`account_specific`, `payment_or_refund`, `compensation`,
     `security_or_identity`).

---

## 2. Label distribution (golden set, n=200)

| intent | n | share |
|---|---:|---:|
| noise_or_off_topic_or_ack | 43 | 21.5% |
| contact_or_human_escalation_request | 29 | 14.5% |
| flight_disruption | 27 | 13.5% |
| refund_or_compensation | 22 | 11.0% |
| website_or_app_issue | 21 | 10.5% |
| information_or_policy | 20 | 10.0% |
| baggage | 16 | 8.0% |
| booking_change_or_cancellation | 12 | 6.0% |
| seat_or_upgrade | 7 | 3.5% |
| account_or_security | 3 | 1.5% |

**Escalation routing:** AUTO_HANDLE 112 (56.0%), ESCALATE 83 (41.5%),
UNCERTAIN 5 (2.5%). Escalation reasons among the 88 routed labels:
account_specific dominates.

**Confidence:** high 168 / medium 30 / low 2.

**Ambiguity:** none 142 (71.0%), multi_intent 44 (22.0%), unclear_intent 11,
other 2, truncated_captured 1. `secondary_intent` was set on 55 examples
(27.5%); 44 carry the `multi_intent` flag, and the remaining 11 secondary
intents appear alongside `unclear_intent`/`other`/`none` flags (a soft
secondary without a loud ambiguity signal).

**Resolution observability:** INFORMATION_PROVIDED 71, UNCLEAR 40,
HANDOFF_OUTCOME_OFF_THREAD 47, UNRESOLVED 27, APOLOGY_ONLY 15.
`RESOLVED_IN_THREAD` is intentionally **not used**: consistent with the
Phase-1 audit (~8/50 in-thread closures), 2017 BA threads rarely show an
explicit in-thread confirmation of a completed action. Claiming it would be
over-reading the data; its absence is a deliberate, documented decision
enforced by nothing but this note.

---

## 3. Sampling prior vs. final label (documented drift)

Quotas in `build_golden_worksheet.py` were set on the *sampling bucket*
(auto-rule or oracle category), not on labels. Both should be reported;
the table shows where the label assignment parted from the auto bucket.

| sampling bucket → | → final intent having the most overlap | note |
|---|---|---|
| account_or_security (10 sampled) | only 3 kept; 4 became noise, 3 website | many "security" tweets are ART-style spam or login noise |
| seat_or_upgrade (12 sampled) | 5 kept; rest re-judged | generic seat *policy* questions re-labelled information |
| contact_or_complaint (12) | 8 kept; 2 noise, 2 moved to refund/booking | complaints with a money ask moved to refund |
| refund_or_compensation (26) | 15 kept; drift to info/noise/contact | policy asks and vents separated out |

Full 11×10 crosstab is printed by `assemble_golden_set.py` output; the point of
recording it is transparency: quotas are *stratified sampling*, not label
promises.

---

## 4. How the labels were produced (honest account)

- **Who assigned labels.** The labels in `evaluation/_labels.tsv` were drafted
  during this phase by the assistant (a large language model) following the
  taxonomy and conventions documented here and in `intent_taxonomy.csv` /
  `escalation_taxonomy.csv`. Each worksheet row's target customer message was
  read **together with its** `prior_context` (earlier customer/brand turns in
  the thread). The historical `reference_brand_reply` was **not** read to
  decide the customer intent of the target turn — it is stored only as the
  resolution reference. Labels, escalation routing and resolution observability
  were decided on the **customer-side evidence** plus what the *thread* shows
  (e.g., whether DM details were later supplied).
- **Why this is not "hand-labelled".** No independent human annotator reviewed
  these labels. The set is **assistant-drafted (LLM-drafted), machine-checked
  for enum/consistency — not human-verified gold**. It is explicitly
  **awaiting independent human review** before being treated as authoritative.
  Automated suggestions were *not* treated as ground truth; the drafting pass,
  the documented conventions, and the deterministic validator are what the
  labels rest on. Reviewer instruction #3 of the phase requires this
  distinction, and it is made here deliberately.
- `resolution_observable` describes the thread outcome as visible in the
  cached thread; `HANDOFF_OUTCOME_OFF_THREAD` means the brand routed the case
  (DM / Customer Relations) and the outcome is off-Twitter and unconfirmable
  from the cache.
- A post-hoc validator (`analysis/scripts/validate_golden_set.py`) enforces
  enums and cross-field rules; the 5 `UNCERTAIN` routing labels were a final
  consistency pass over genuinely ambiguous routing, not a relabeling of
  content intents.

---

## 5. Honest limitations

- **Labels are assistant-drafted, not human-verified.** No human annotator and
  no second reviewer have touched these labels; no inter-annotator agreement
  was (or could be) measured in this phase. This is the single most important
  caveat. It is mitigated by (a) the audit-derived taxonomy, (b) documented
  pre-committed conventions, (c) a validator that mechanically enforces enums
  and consistency rules, (d) a `confidence` field so consumers can weight or
  drop low-confidence examples, and (e) `ambiguity_flag` /
  `escalation_label=UNCERTAIN` captures instead of forced guesses. **Any IAA
  number reported in future work must come from a real human second-annotation
  pass; none is reported here, and none may be fabricated.**
- **Intents are not evenly balanced** (see §2) because the pool itself is
  uneven; quotas were honoured on the sampling side and final counts follow
  the label assignment, so they should be re-weighted rather than over-sampled.
- **Labels describe the customer turn, not the outcome.** The set is a
  classifier/evaluation resource for *what the customer is asking*, not a
  promise about whether BA fixed it.