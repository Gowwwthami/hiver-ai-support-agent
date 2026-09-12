# PHASE 2.1 — LABEL & TAXONOMY AUDIT (British_Airways golden set)

**Scope:** investigation-only pass to prepare the 200 examples for genuine
human verification. **No gold label was overwritten.** The shipped labels
remain the assistant-drafted, human-unverified proposals. Every change below is
a *proposal for the human reviewer*, recorded in
`evaluation/golden_set_review_queue.csv` (`proposed_*` columns; `human_final_*`
are blank — nothing here is a fabricated human label).

Working definitions used throughout this audit (they must stay separate):

- **Intent** = "what is the customer trying to accomplish?"
- **Escalation** = "can a safe autonomous agent handle this without human
  investigation/judgment or account-specific data?"

---

## 0. What was reviewed

- All 29 `contact_or_human_escalation_request` examples (full class).
- All 3 `account_or_security` and all 7 `seat_or_upgrade` examples.
- The named deep-dives (BA_349968, BA_567068, BA_152445, BA_351856, BA_167696,
  BA_32854, BA_334633, BA_33704, BA_410381, BA_358073, BA_132217, BA_479193,
  BA_261585, BA_150929, BA_147482, BA_255518, BA_26002, BA_472183).
- Escalation labels across all 200 rows against a single operational rule (§6).
- Corpus scans for additional account/security and seat/upgrade candidates
  (`analysis/candidate_examples/*.csv`).

Net result as produced by `build_review_queue.py`: **34 intent proposals** and
**16 escalation proposals** differ from the draft; **134 rows flagged HIGH**,
6 MEDIUM, 60 LOW priority for human review.

---

## 1. Finding 1 — the contact/human-escalation class conflates four things

The draft class `contact_or_human_escalation_request` mixes at least four
different customer objectives:

| sub-objective | draft examples | problem with current label |
|---|---|---|
| (a) contact-**information** question | BA_349968, BA_567068, BA_579921, BA_163041 | Factual lookup of a channel, answerable publicly → better `information_or_policy` |
| (b) *serious* complaint needing investigation | BA_627007, BA_331684, BA_542898, BA_787976 | Genuinely needs human handling — inherently different from (a) |
| (c) complaint-**venting** (no request) | BA_152445, BA_278441, BA_32854, BA_334633, BA_749232 | Not a "request" at all; borderline with `noise` |
| (d) sarcasm / commentary (no support intent) | BA_167696, BA_337964, BA_71213, BA_755802, BA_358073* | Closer to `noise` than to human escalation |

(*) BA_358073 is a vague connection-complaint; flagged `unclear_intent` — see §8.

### Named deep-dives

| example | draft (intent / esc) | audit proposal | why |
|---|---|---|---|
| BA_349968 | contact / AUTO_HANDLE | **information_or_policy** / AUTO_HANDLE | "best number to call in an emergency" = public contact facts; AUTO_HANDLE already correct |
| BA_567068 | contact / AUTO_HANDLE | **information_or_policy** / AUTO_HANDLE | contact method abroad = public info or an automatic "this is the channel" answer |
| BA_152445 | contact / ESCALATE(complaint) | **complaint_or_human_assistance** / AUTO_HANDLE | complaint-venting, no concrete ask; safe public empathy + open prompt — historical "DM details" is not proof of need |
| BA_351856 | contact / ESCALATE(legal) | **complaint_or_human_assistance** / ESCALATE(legal) | lawsuit service query: legal exposure; routing stays human, intent is complaint-class |
| BA_167696 | contact / ESCALATE(complaint) | **non_support_or_acknowledgement** / AUTO_HANDLE | "#downgrade" sarcasm with zero request |
| BA_32854 | contact / ESCALATE(complaint) | **complaint_or_human_assistance** / AUTO_HANDLE | lounge-food complaint + photo; public apology + feedback capture; no account data |
| BA_334633 | contact / ESCALATE(complaint) | **complaint_or_human_assistance** / AUTO_HANDLE | 777 experience complaint; public empathy + feedback |
| BA_33704 | contact / ESCALATE(complaint) | **complaint_or_human_assistance** / ESCALATE(**account_specific**) | urgent but actionable: sorting *today's flight* needs the booking → reason should be account_specific, not generic complaint |
| BA_410381 | contact / ESCALATE(complaint) | **complaint_or_human_assistance** / AUTO_HANDLE | in-flight product complaint; public apology + feedback |
| BA_358073 | contact / UNCERTAIN(complaint) | **complaint_or_human_assistance** / AUTO_HANDLE | "shockingly bleak connection" — public probe; alt labels non_support / UNCERTAIN acceptable; flagged for reviewer |

**Do NOT assume these are wrong** — the above are *proposals*, each keyed to the
customer objective visible in the message. The class clearly needs a boundary
re-cut (a) vs (b) vs (c) vs (d).

---

## 2. Finding 2 — rename proposal: `contact_or_human_escalation_request` → `complaint_or_human_assistance`

**Evidence FOR:**
- §1 shows the current name invites *contact-channel queries* (fact-answerable,
  info-level) into a label that implies service requests. The customer's actual
  need in most of the 29 rows is *investigation or human judgment*, not "a
  channel".
- A name centered on "complaint / human assistance" matches the boundary that
  matters operationally: "must a human own this?" It makes (a) fall naturally
  to `information_or_policy` and (d) to `non_support_or_acknowledgement`,
  leaving a coherent residual class.

**Evidence AGAINST:**
- Renaming alone changes nothing; without re-cutting (a)/(d) out, the class
  stays a grab-bag under a new name.
- Some rows are genuinely "I want a person to contact me" (BA_131149,
  BA_33704) where "complaint" under-reads the ask; and some complaints arrive
  with a money/seat secondary where the *complaint* is secondary.
- Documentation/enum churn (200-row set, validator, taxonomy files) and risk of
  confusing the separate `escalation_label=ESCALATE` concept with an intent
  named like the escalation reason.

**Recommendation (proposal, not decision):** adopt
`complaint_or_human_assistance` **with** the re-cut in §1 — pure contact-info →
`information_or_policy`; sarcasm/no-request → `non_support_or_acknowledgement`;
actionable complaint / human-assistance / legal-pressure remains the renamed
class. High-value complaints that arrive with a money secondary should keep
the money intent primary or a `secondary_intent`. Human reviewer confirms.

---

## 3. Finding 3 — noise rename: `noise_or_off_topic_or_ack` → `non_support_or_acknowledgement`

**The semantic point is real.** In this corpus "noise" is mostly *legitimate*
messages with no support request (praise, thanks, banter, acknowledgement),
which a support agent must still answer (or decline) — and the eval must score
as its own class, not discard as bad data. "Noise = bad data" biases both
annotation and evaluation.

- **FOR the rename:** matches corpus reality (43 rows; `noise_flag=TRUE` only
  on 41 — the 2 remaining are praise-with-embedded-soft-complaint hybrids kept
  deliberately); keeps junk (spam/truncated/marketing) distinguishable via the
  orthogonal `noise_flag`.
- **AGAINST:** churn; Phase-1 audit text calls this residue "noise"; some rows
  really are junk where "non-support" reads too neutral.

**Recommendation (proposal):** rename to `non_support_or_acknowledgement` and
retain `noise_flag` as the junk-vs-legit filter. Await human confirmation.

---

## 4. Finding 4 — `account_or_security` is too narrow

Draft class (3 examples): BA_132217 (hacked EC), BA_479193 (household-name
removal error), BA_729813 (password-reset emails not arriving). Only BA_132217
is a *security incident*; the other two are **account access / account
management**. The current definition ("hacked account, suspect activity, or
identity checks") therefore does not cover 2/3 of its own members.

- **Proposal:** rename to **`account_access_or_security`**, defined as:
  "Executive Club / BA account access, management, or security problem: log-in
  failures, password reset, household/member management, hacked or suspect
  activity, identity-verification gates." The treatment (escalate to the EC
  team with identity/account data) is identical; only the label's denotation
  widens.
- **Boundary care:** login-*page* failures traceable to the web/App stay
  `website_or_app_issue`; the draft already splits one of these into
  `secondary_intent=website_or_app_issue` (BA_479193). Reviewer decides each.

**Additional corpus candidates (strengthen this class; NOT added to golden
set):** `analysis/candidate_examples/account_access_or_security_candidates.csv`
(12 rows) — e.g. ACCT_0000 (login via Amex, cannot reset), ACCT_0005 (EC login
after password change), ACCT_0008 (Avios-combine error), ACCT_0009 (web login
works, app rejects). These would raise the class from 3 to ~10+ examples.

---

## 5. Finding 5 — `seat_or_upgrade` class audit

All 7 draft examples read: BA_288483 (reassignment vs "first come served"),
BA_423824 (medical seat need), BA_568345 (seat-pricing complaint), BA_577348
("leg room" complaint), BA_578442 (upgrade payment failed), BA_705984
(birthday-upgrade banter), BA_707914 (seat switched at check-in).

- **Coherent?** Mostly. 6/7 are genuine seat/upgrade asks spanning:
  availability/allocation (288483), policy/seating-need (423824),
  pricing-value complaint (568345, 577348), purchase/upgrade mechanic (578442),
  operational re-seat (707914).
- **One outlier:** BA_705984 is banter (a birthday prank question) — proposed
  `non_support_or_acknowledgement`, flagged for review. This shows the class
  boundary with `non_support` (joke "right?" questions).
- **Keep separate?** Yes — knotting seats into `flight_disruption` or `refund`
  would blur two distinct agent actions (policy/seat answer vs. routing).
  It stays; optionally distinguish "seat availability/selection" from
  "seat/upgrade money complaint" in later annotation guidelines.
- **More examples from the corpus:** `analysis/candidate_examples/
  seat_or_upgrade_candidates.csv` (15 curated from a 24-row keyword scan pool,
  `seat_or_upgrade_scan_pool.csv`). The 15 (conv ids) cover: window-seat loss
  on plane change (315011), failed terminal upgrade (730427), Club World seats
  apart (547094), cabin-full upgrade block (528438), post-purchase upgrade
  policy (465381, 178169, 755296-Avios), legroom/exit-row questions (727454,
  533810), seat-site discrepancies (446495, 567075), first-class availability
  (273417), downgrade/paid-seat complaints (412855, 290736, 584832). All are
  **candidates for a second annotation wave, not gold-set additions.**

---

## 6. Finding 6 — escalation policy: a single operational rule, applied to all 200

The draft's `escalation_label` mixed two things: *"what BA actually did"* and
*"what our policy would route"*. The audit re-checks every row against one
rule that is **not** a mirror of the archive:

> **AUTO_HANDLE** iff a safe autonomous agent can produce a complete, accurate,
> safe public answer from general policy/historical evidence *without*
> account-specific data or human judgment. Otherwise **ESCALATE** with the
> reason from `escalation_taxonomy.csv`; use **UNCERTAIN** only when the
> customer-side evidence cannot decide.

Consequences (all proposals):

- **Contact-information queries** (BA_349968, BA_567068, BA_579921, BA_163041)
  → AUTO_HANDLE (they already are 3/4).
- **Complaint-venting / feedback** (BA_152445, BA_167696, BA_278441, BA_32854,
  BA_334633, BA_337964, BA_358073, BA_410381, BA_466171, BA_749232, BA_755802,
  BA_71213) → **AUTO_HANDLE** (public empathy + feedback-capture; no account
  data; no investigation asked). This is the biggest single change proposed —
  the draft defaulted ~23 complaint rows to `ESCALATE(complaint)` largely by
  mirroring BA's "DM us" habit, which §0/Guide §2 says is not the test.
- **Investigation-worthy / partner-routed** (BA_627007, BA_331684, BA_542898,
  BA_787976, BA_737110) → keep ESCALATE(complaint).
- **Booking/account-dependent** (BA_131149, BA_33704, BA_150929, BA_472183,
  BA_423824, BA_707914) → ESCALATE(account_specific) — several already.
- **Money / upgrade-payment** (BA_135900 refund-thread, BA_578442,
  BA_568345) → ESCALATE(payment_or_refund / complaint).
- **Identity/legal** (BA_132217, BA_729813, BA_147482 alt, BA_351856) →
  ESCALATE(security_or_identity / legal_or_regulatory_risk).

Deep-dives the user named:

| example | draft | reassess (operational rule) | outcome |
|---|---|---|---|
| BA_261585 | AUTO_HANDLE | delay-care claim "where" is public info; agent can also note EC261 threshold | keep AUTO_HANDLE ✓ |
| BA_150929 | ESCALATE(account_specific) | intent is really a same-day flight *change*; routing still needs PNR | keep ESCALATE; **intent → booking_change_or_cancellation** |
| BA_147482 | ESCALATE(legal) | boarding-document ID crisis at airport; autonomously unsolvable | keep ESCALATE; **reason → security_or_identity** (alt legal) |
| BA_349968 | AUTO_HANDLE | public contact channels | keep AUTO_HANDLE ✓ |
| BA_567068 | AUTO_HANDLE | public contact channels | keep AUTO_HANDLE ✓ |
| BA_255518 | AUTO_HANDLE | MMB self-service change = complete public answer | keep AUTO_HANDLE ✓ |
| BA_26002 | ESCALATE(account_specific) | booking class IS shown on e-ticket / MMB ⇒ public answer exists | **propose AUTO_HANDLE** (ESCALATE defensible; reviewer decides) |
| BA_472183 | ESCALATE(account_specific) | confirm-booking-exists needs PNR lookup; spam/MMB guidance public first | keep ESCALATE(account_specific) ✓ |

---

## 7. Intent and escalation are independent (enforced)

A single intent legitimately holds both AUTO_HANDLE and ESCALATE rows — e.g.
`seat_or_upgrade` already contains BA_288483 (AUTO_HANDLE) and BA_423824
(ESCALATE). The audit therefore made escalation adjustments **without** inventing
new intents for handling differences (e.g. complaint-venting rows stay
complaint-class while their escalation flips to AUTO_HANDLE). No new intent
labels were proposed for routing reasons.

---

## 8. Ambiguity / noise census (numbers, not opinions)

- 58/200 rows carry a non-none `ambiguity_flag` (multi_intent 44, unclear_intent
  11, other 2, truncated_captured 1); `secondary_intent` on 55. These are HIGH
  priority (§ queue).
- Hardest boundaries evidenced by the flagged rows:
  `refund ↔ disruption` (11 multi-intent on refund), `contact ↔ everywhere`
  (14 ambiguous), `baggage ↔ information` (6 pairs), `booking_change ↔ web`,
  `seat ↔ noise` (BA_705984).
- The 2 noise rows with `noise_flag=FALSE` (BA_725131, BA_76703 — praise with
  embedded soft-complaint) are flagged MEDIUM so the reviewer decides whether
  non-support still applies.
- **No difficult example was silently discarded.** Low-confidence (2), UNCERTAIN
  (5) and ambiguous (58) rows are all in the HIGH queue for explicit decisions.

## 9. Status & reproducibility

- `evaluation/golden_set_review_queue.csv` = 200 rows × 17 columns, `human_final_*`
  empty; produced by `analysis/scripts/build_review_queue.py` (deterministic).
- Candidates: `analysis/candidate_examples/seat_or_upgrade_candidates.csv`,
  `account_access_or_security_candidates.csv` (scanner:
  `analysis/scripts/find_candidate_examples.py`; golden + 50 audit convs excluded).
- Golden set and validator unchanged (`validate_golden_set.py` still PASSES on
  `golden_set.csv`).
- The dataset remains **assistant-drafted / human-unverified proposed gold set**
  until the human review completes. No claim of human labelling is made.
- Phase 3 (classifier, RAG, embeddings, judge, harness, UI/API) is **not**
  started; this pass stops at queue + audit + guide.