# British Airways Qualitative Audit

Sample-under-review: `analysis/candidate_conversations/British_Airways.md` (n=50, stratified: short/medium/long × problem clusters, seed=137). Companion samples: `Tesco.md` (n=50), `AmazonHelp.md` (n=50). No Phase-1 metric or scorecard was recomputed; the scorecard is unchanged. The 50 BA threads were hand-categorized thread-by-thread below. All proportions quoted in this document are sample-derived estimates (n=50) and are explicitly labelled; nothing here estimates population-wide rates.

## Executive conclusion

**Recommend British_Airways with reservations.**

The audit supports the recommendation: the BA customer-intent space is genuinely separable into crisp, distinct categories; there is abundant, real escalation evidence (Customer Relations case refs, security checks, compensation claims, small-claims threats); and historical threads provide solid grounding for policy/factual Q&A, standard troubleshooting, and correct hand-off drafting.

The reservations are real and honest, however:

1. **In-thread resolution is modest** — from this sample, only ~8/50 conversations show an observable outcome that supports "resolved" (129, 6036, 1895, 9185, 9750 as benign-close, 15055 mostly, 1748, 961 via phone). A substantial share (13/50 clean DM / Customer-Relations hand-offs, plus several pending-third-party escalations) ends with the outcome happening off-Twitter and unconfirmable from the sample. So "high response diversity" does not mean "high in-thread closure".
2. **The "98.9% unique responses" claim is inflated by surface variation** — see the dedicated challenge section. It is largely a template-with-slots + sign-off artifact.
3. **~20% of the sample (10/50) is praise/humor/marketing noise**, plus a few borderline/misparse threads.
4. Conversations occasionally interleave multiple customers (1389, 542, 13559), which complicates conversation-level splits.

None of these invalidate BA as the best tested choice versus Tesco and AmazonHelp (see comparison), but they should temper how the Phase-1 diversity numbers are quoted internally.

## Intent landscape

The customer intent space is cleanly separable. From the n=50 sample I identify ~9 recurring categories; 2–3 representative conversation IDs each. Category boundaries are distinct — a "refund/compensation claim" thread does not look like a "website/IT" thread or a "seat policy" thread — although individual threads can span two intents (e.g., disruption + compensation, seat dispute + refund), in which case a primary-intent label is still unambiguous.

1. **Refund / compensation / cancellation claims** — 15801, 15055, 1748, 12371, 15799.
2. **Seat policy & seating disputes** (fees, legroom, exit-row moves, seat selection) — 13199, 14530, 4197, 9750, 4722.
3. **Website / online-booking / account-access issues** (bugs, search, currency, login) — 14810, 966, 1895, 6100, 4722, 2388.
4. **Flight disruption & airport experience** (diversions, delays, queues, boarding) — 15799, 13558, 15263, 14806.
5. **Baggage & onboard issues** (cabin baggage, damage, lost property, catering, cabin comfort) — 3735, 6102, 13553, 9754, 15259, 4726.
6. **Account security & loyalty** — 961 (Executive Club hacked), 5842 (unable to email support).
7. **Rebooking / booking modifications** (code-share swaps, partial cancellation) — 15804, 5646.
8. **Contact-routing & general-service complaints** (can't reach a human, "worst CS") — 5844, 8975, 6100.
9. **Product/technical curiosity** — 6036 (787 air quality).
10. **Non-issue: praise / humor / marketing / contests** — 9184, 1620, 7481, 11024, 1388, 14809, 9396, 15806, 14812, 13559 (10/50 = ~20%).

Verdict on separability: **strong**. The 4–9 substantive categories above are easy to distinguish on a single customer utterance, and the two "fuzzy" boundaries (refund↔disruption, seat-dispute↔refund) are resolvable with a primary-label rule. This is the single strongest qualitative argument for BA.

## Historical resolution patterns

**Problem → brand action → follow-up → outcome**, per major intent, with status labels. `Status` uses the conservative definitions from the task (no "resolved" claim unless the thread supports it).

| Intent | Typical problem in sample | Typical BA action | Typical follow-up | Observed outcome | Status |
|---|---|---|---|---|---|
| Refund/compensation | Flight cancelled; refund promised but not paid (15801, 15055); comp MasterCard broken (1748) | Empathize; ask "do you have a Customer Relations case?"; request booking ref + CR ref + contacts **via DM** (15801, 12371, 15055) | Customer supplies refs; CR contacts them; BA confirms "glad this is getting resolved" | Partial: partner comp was corrected (15055); long-delayed refunds remain unresolved in-thread (15801) | Partial / escalation, off-thread outcome |
| Seat policy | Seat booking fee (~£25) (13199); Club Europe legroom == economy (14806); paid seats removed (14530, 4197) | Explain policy factually (free at 24h online check-in; "leg room in Euro Traveller is same as Club Europe"; "seats aren't guaranteed"); apologize | Customer pushes back; BA reiterates policy or refers internally (Customer Experience) | Factual question answered; the underlying dispute is **not** remediated in-thread | Information-only / unresolved dispute |
| Website/IT | Booking reference error (1895); search/nav broken (14810); server fault (966); reference to Sales line (6100) | Report to faults team; give repro steps; give patch ETA; step-by-step navigation | Customer retries; sometimes second round of guidance needed | Resolved when a concrete fix/ETA existed (1895 "patch on 1 Nov" + thanks; 14810 partial) | Useful resolution (1895) / partial (14810) / unresolved (6100) |
| Disruption | Flight diverted near Krakow/Budapest (15799, 13558); no airport staff | Apologize; confirm eligibility to look into compensation; "keep receipts" + DM (13558) | Customer DMs booking ref + receipts request | Commitment to investigate; no in-thread decision | Partial / escalation |
| Baggage | Forced check-in of soft-case guitar (3735); wheel broken DXB (6102); lost item Newark (13553) | Explain Oct-25 policy change (3735); ask for World Tracer ref + DM (6102); refer to lost property/link (13553) | Customer DMs details | Claim started; outcome off-thread (6102). Policy Q resolved info-only (3735) | DM handoff / info-only |
| Account security | Executive Club account hacked (961) | Ask for identity details via DM; route to Executive Club team | Customer instead phoned EC; BA closed gracefully | Handled off-channel; clean escalation | Escalation (resolved elsewhere) |
| Rebooking | Wants cost to move off code-share to BA metal (15804); cancel 1 of 2 passengers (5646) | "DM us booking ref/email/number and we'll check" | Customer provides details | Outcome off-thread | DM handoff |
| Contact routing | "How do I get a reply from CS? Worst CS 2017" (8975); fed-up cannot reach human (5844, 6100) | Ask what the situation is; request DM details; explain social team can't take calls; point to Sales (6100) | Customer frustrated; repeated rounds | Mostly **unresolved** complaint loops | Unresolved / information-only |
| Product info | Why is 787 air cleaner? (6036); seat 13 no air vent (9750) | Nice factual explanation (bleed-free design); offer crew move | Customer satisfied/benign | Resolved (informational) | Useful resolution |

Key qualitative finding: BA's support playbook is **apologetic-preface + factual/policy-answer-where-possible + (privacy-gated) DM/hand-off where account data is needed**. That is a clean, learnable pattern for the Phase-2 agent — it is exactly the retrieve-to-chat, escalate-to-act shape an intern project can implement well. But notice what the playbook rarely does in these threads: it rarely *executes* (refunds, seat changes, compensation) inside Twitter; it routes. Phase-2 ground truth must therefore label hand-off as a legitimate, high-quality "resolution".

## RAG suitability

**Strong examples** (retrieval of these threads would support a grounded answer to a *new* similar customer message):

- 129 — confirm which email corresponds to a name-change request ("that is the correct email"). Simple confirm-with-source.
- 6036 — 787 bleed-free air system explanation; the customer was satisfied. Textbook factual QA.
- 9185 — booking charged in the currency of the outbound destination (clear policy fact).
- 13199 / 3735 — seat-booking and cabin-baggage **policy** answers with the operative rule quoted (free at 24h check-in; Oct-25 soft-case guitar policy change) and a help link.
- 1895 — a *systemic* website bug with a stated fix ETA (patch on 1 Nov).
- 14810 — multi-step navigation troubleshooting (flight+hotel search) with two corrective rounds; strong trajectory for a conversational assistant.
- 1748 — precise contact routing (CR line, opening hours, webform, alternative number that eventually worked). A retrieval-augmented agent could learn *which channel to push*.

**Weak examples** (retrieval would draft the same template safely, but adds little grounded value because the real answer lives in private account data):

- 15801, 15055, 13558, 6102, 5646, 4722, 15804 — "please DM your booking ref, email and contact number / CR reference and we'll look into it." These are correct but account-gated; the informative part is just the *requested-field list* + the empathetic premise, neither of which needs heavy retrieval.

**Where retrieval would likely work**: policy/factual Q&A (fees, currency, baggage rules, seating), standard website troubleshooting, flight-mechanics questions, and — critically — **hand-off drafting** (which contact channel, which fields to collect, whether CR case exists).

**Where retrieval would likely be insufficient**:
- Status-of-claim / case-tracking (15801, 15055) — no public document states the current refund case state; must route.
- Compensation decisions and execution (4197, 15799, 328) — the decision is made off-platform; historical threads would just replay apologies that did not satisfy the customer.
- Unresolvable complaints where no factual answer exists (13198, 15259, 4726) — retrieval would reproduce a template apology the customer already rejected.
- Misparse-sensitive threads (1894) — an agent that blindly copies the "sorry this happened" empathy onto a praise or sarcasm message reproduces BA's own failure in-conversation.

## Escalation suitability

Real, in-sample evidence of appropriate escalation, categorized by reason (no escalation *policy* is invented here):

- **Account-specific issue** — 961 (hacked Executive Club account; identity details + DOB + security check), 15055 ("we need the details requested to pass our security check"), 5646 (partial cancellation of a specific booking), 4722 (account locked out of Manage My Booking), 9754 (multi-passenger luggage config), 5842 (email blacklist).
- **Customer Relations handoff** — 15055 (explicit case number 17058483; "Customer Relations team will contact you"), 15801 ("do you have a case with Customer Relations?... our Customer Relations team will contact you in due course"), 1748 (CR department 0344 493 0787, hours, webform, alternative phone that finally worked).
- **Complex / long-unresolved complaint** — 15801 (3-month refund wait), 1748 (compensation MasterCard unusable for weeks), 4197 (paid seats removed; small-claims-court threat), 14530 (exit-row seat repeatedly reassigned despite Elite status), 542 (misquoted phone-charge rate by an advisor).
- **Insufficient information** — 8975 ("please advise how we can help? Not sure what the situation is?"), 5844 (no problem stated; "DM us your issue"), 1389 (customer whose emails went unanswered — brand must reconcile an existing offline case).
- **Disruption / expenses eligibility** — 13558 (diversion; reimbursement of hotel + "keep receipts"; escalation to Budapest airport manager), 15799 (compensation eligibility after return).

This is the strongest escalation corpus of the three brands: BA escalations are *structured* (a case/CR reference, a security check, a requested-field list), not just "call us".

## Noise and limitations

From the n=50 sample:

- **Praise / humor / marketing / contest (yes, unusable for an intent model):** 9184, 1620, 7481, 11024, 1388, 14809, 9396, 15806, 14812, 13559 — **10/50 (~20%)**.
- **Borderline / low-value:** 14532 (connection worry answered with encouragement only), 5842 (no issue stated), 8975 (no problem state) — 3/50.
- **Misparse risk:** 1894 (praise misread as a complaint by BA itself; customer answers with sarcasm). Retrieval must not replay that pattern.
- **Broken/interleaved threads:** 1389 (a brand-side marketing tweet that collected several *different* customers' complaints + website tech issues in one component), 542 (a *third party* chimes in about 0844/0344 numbers), 13559 (two customers in one component). These are conversation-splitting hazards for the Phase-2 golden set.
- **Canned/template misuse:** 14812 — the brand answered a *thank-you/praise* with a data-protection boilerplate ("Due to data protection we do need to speak with our customers directly"). Shows the shared-template scaffold can misfire in retrieval too.

**Useful-share estimate (sample, n=50):** ~36/50 (~72%) of threads carry something genuinely reusable (a factual answer, a policy, a troubleshooting trajectory, or a correct hand-off scaffold). ~14/50 (~28%) are noise/problematic. Honest caveat: only ~8/50 (~16%) show an observable in-thread resolution; the majority of genuinely useful threads are useful *as escalation or hand-off templates*, not as demonstrations of closure.

## Challenge to response-diversity metric

The Phase-1 `unique_ratio_normalized ≈ 0.989` for BA means "nearly every brand message string is unique after normalization." From the concrete threads this is **mostly surface variation, not bespoke support**:

1. **Shared response scaffolds reappear verbatim with slots swapped.** Compare:
   - 15804: *"Feel free to DM us your booking ref, email and contact number and we'll certainly **check this out** for you, Aisnley."*
   - 13558: *"Please DM us your booking ref, email and contact number and we'll certainly **look into** this for you, James."*
   - 15801 / 12371 / 15055: same "DM booking ref + email + contacts (and CR reference)" structure.
   These are the same template with a swapped verb and injected name — each counts as a distinct normalized string and feeds the "unique" number.
2. **Agent sign-offs and name injection guarantee uniqueness for free.** Nearly every BA reply ends `^Jane / ^Corry / ^Kev / ^Rach / ^Lobby / ...` and many open `Hi <CustomerName>`. That alone (let alone `1/2 … 2/2` continuation fragments) makes verbatim repetition rare even for identical content.
3. **Directly parallel replies to the same event type.** 15799 and 13558 both address a November-29 diversion with "We're sorry your flight was diverted…" + "we'll look into compensation/expenses" — indistinguishable in intent, differentiated only in phrasing.
4. **Genuinely individualized content is a minority.** The real bespoke answers are things like the 787 bleed-free explanation (6036), the specific seat-13 A321 observation (9750), the step-by-step search navigation for Melissa (14810), and the precise CR phone number/hours (1748). Most other "unique" strings are variations of empathy + DM-request.

**Conclusion:** the uniqueness metric overstates BA's bespoke-support quality; it mostly captures (a) low verbatim template reuse, (b) a large, open-ended apology lexicon, and (c) name-injection + sign-off. BA's genuine strength is *intent clarity and escalation structure*, not 98.9%-bespoke writing. This should be reflected in how the diversity metric is quoted in the final report/defense, and Phase-2 response evaluation should cluster near-duplicate templates rather than treating them as distinct.

## BA vs Tesco vs AmazonHelp

Comparing ~10 representative threads from each of the companion samples (`Tesco.md`, `AmazonHelp.md`) against BA:

### Intent clarity
- **BA:** crisp, ~9 separable intents (refund/comp, seat policy, web/IT, disruption, baggage, security, rebooking, routing, product-info) + a clean 20% praise residue.
- **Tesco:** also crisp, but dominated by *product quality/date issues* (mouldy lasagne 516/10837, out-of-date dippers 15438, mouldy bread 7172), *store feedback* (trolleys 8694, staff complaints 15964/118, smoking 10838, car-park 16294), *delivery slots* (4127, 8851, 2649, 15675), *Clubcard/vouchers* (14951, 5536, 15960). Clearly distinguishable, but a narrower, more repetitive taxonomy.
- **AmazonHelp:** broadest but lowest-cleanliness — *delivery/logistics* (75782, 4610, 78679, 77373, 42789, 68925, 44966), *refunds/account* (3766, 38969, 78271, 69966), *device/Prime* (5815, 60725, 4180, 55567), plus heavy multilingual/informal English.

### Historical resolution quality
- **BA:** apologetic + facts + DM/CR hand-off; strong *escalation* quality; weak in-thread *closure*.
- **Tesco:** most *observable in-thread closure* of the three — e.g., abandoned-trolley collected and confirmed (8694), animal-testing policy question satisfied (12958), midnight-release availability (946), website correction (2859, 946), plus a *standardized refund apparatus* (Moneycard + barcode/SC/date-code form-request pattern in 10837, 516, 8854, 7172, 15438). Retained by Phase-1's B5 scoring.
- **AmazonHelp:** least observable closure; the dominant recurring pattern is a routing loop ("fill this form / revert our email / we can't access account over Twitter") that ends unresolved in-thread (77373, 38969, 71178, 78135, 78679).

### RAG usefulness
- **BA:** strong factual/policy QA + troubleshooting + precise hand-off scaffolds.
- **Tesco:** strong, *stable policy/refund templates* (highly repetitive but reliable facts e.g. 15675 "no automated deliveries", 12958 policy, 946) — great for retrieval, but the repetition explains its lower response-diversity score.
- **AmazonHelp:** some genuinely informative device/Prime answers (4180 Echo-India skills 3-part, 60725 free-Prime, 76550 JP Prime cancellation, 50865 skip-registration) — good grounding material — but a large tail of low-value routing loops and non-English text that would pollute a dense index.

### Escalation evidence
- **BA:** richest (CR cases/ref numbers, security check, compensation, small-claims, expenses/receipts).
- **Tesco:** store-manager/supplier escalation + account investigation (118 → Store Manager email; 16301 → account investigation; 2649/519 store calls) — decent but less formalized than BA.
- **AmazonHelp:** escalation mostly *fails* in public (red-tape loops, "I NEED A CALL ASAP" repeatedly routed to forms — 71178, 38969, 78135). Great *negative* examples, poor *modeling* examples.

### Noise
- **BA:** ~20% praise/humor/marketing; ~28% problematic overall; occasional interleaved multi-customer components.
- **Tesco:** least noise (~10% obvious social: 9366, 5717, 7173, 4133), plus some borderline promo (4133 is a long 8-tweet social chat). Lowest residue of the three.
- **AmazonHelp:** highest noise — ~20% clearly non-English (60861 JP, 76550 JP, 28351 ES, 26862 DE, 61274 DE, 70814 FR, 7604 IT, 66964 DE, 34663 PT, 29773 PT) and a further ~15–20% informal Hinglish/Anglo-Indian; plus promo/engagement (61929, 4378, 17926, 29773).

### Conversation richness
- **BA:** long threads are *substantive* — evidence-dense troubleshooting (6100 16 tweets), multi-step disputes (4197 15 tweets), CR saga (1748 20 tweets), seat-status saga (14530 10 tweets). High quality per turn.
- **Tesco:** medium-length procedural loops; the longest are info-gathering (10837, 516, 519).
- **AmazonHelp:** the longest threads are *frustration loops* (38969 17, 71178 18, 78135 16, 78679 11) — many customer assertions against repeated template replies. Rich in turns, poor in resolution modeling.

**Over-all qualitative verdict:** BA and Tesco are both clean-and-usable, and Tesco arguably has the best *in-thread closure*. But Tesco's taxonomy is narrow and template-repetitive (which Phase-1 already penalized via diversity), and its escalations are less structured. AmazonHelp has more data but materially less clean, more multilingual, more routing-loop-heavy material, and its own observed resolutions are rarer. BA remains the best overall balance — with the honest caveats in the sections above.

## Final recommendation

**Choose British_Airways** for the Hiver assignment, and state the decision in the report as *"recommended with reservations"* rather than a clean winner.

- What the sample supports: crisp, separable intents; a learnable two-part playbook (public answer where factual, structured DM/CR hand-off where account-gated); the strongest escalation corpus of the three candidates; and enough clean threads (~36/50 ≈ 72% of the sample) for conversation-level TRAIN/DEV/TEST + a 150–250 golden set.
- What must be fixed/acknowledged before Phase 2: (1) treat the ≈98.9% uniqueness as *template variability*, not bespoke support — deduplicate near-duplicate scaffolds during grounding; (2) design the golden set to distinguish *public-answer* from *hand-off* resolutions (do not require observable closure); (3) filter a ~20% praise/humor/marketing residue and the interleaved multi-customer components (1389, 542, 13559); (4) expect agent outputs that are helpful-but-routing for account-gated intents and let an escalation module own refunds/compensation/security cases.

No scorecard value was changed, and nothing in this audit replaces the metric-driven evidence — it adds the qualitative side needed to convert "highest-scoring brand" into "best-fit brand."

---

## Per-thread categorization (n=50)

Columns: **ID** = conversation id; **Turns** = tweets / brand_msgs; **Problem** (customer's primary issue); **Intent** (candidate); **C** = intent reasonably clear on the customer's first message?; **Resolution** = kind of brand resolution; **RAG** = response usable as historical grounding for a *new* similar message? (A=strong, M=moderate, W=weak/none); **Esc** = useful escalation evidence?; **Noise** = noisy/ambiguous/unusable?; **Reason** = short basis for the assessment.

Status shorthand: `ok` = thread supports an observable resolution; `info` = information-only; `partial` = partial/useful-but-open; `handoff` = structured DM / CR hand-off (outcome off-thread); `escal` = escalation in-thread; `unres` = unresolved in-thread; `social` = non-issue praise/humor/marketing.

| ID | Turns | Problem | Intent | C | Resolution | RAG | Esc | Noise | Reason |
|---|---|---|---|---|---|---|---|---|---|
| 9184 | 3/1 | Praise for Ghana flight + free-upgrade hint | Praise | n/a | social (thanks) | – | – | YES | Pure praise; no issue |
| 1620 | 2/1 | Praise of safety video | Praise | n/a | social | – | – | YES | Praise |
| 7481 | 2/1 | Humor (parking spot) | Praise | n/a | social | – | – | YES | Humor/engagement |
| 14806 | 13/6 | Club Europe legroom == economy; economy boarded faster; champagne/late | Seat/legroom + boarding complaint | yes | info (legroom fact confirmed: same 30"); feedback to Engineering/Catering | M (product-fact QA) | – | – | Ends "That's outrageous"; Q answered info-only, dispute unresolved |
| 12371 | 3/2 | No credit note/refund on cancelled flight; rude advisor said "do a no show" | Refund (cancelled flight) | yes | handoff (DM booking ref/email/contact) | W (account-gated) | YES (CR) | – | Clear claim; routed privately |
| 13199 | 4/2 | Seat-reservation fee (~£25) | Seat policy | yes | info (free at 24h online check-in; policy link) | A (policy QA) | – | – | Factual answer given; customer still angry; fee not waived |
| 15801 | 7/3 | 3-month-old promised refund; emails ignored | Refund (long-due) | yes | handoff/escal (case check; DM details) | W (account-gated) | YES (CR case) | – | Outcome off-thread; strong CR escalation example |
| 129 | 2/1 | Confirm which email accepts passport-name-change docs | Contact info confirm | yes | info (confirmed) | A | – | – | Clean resolved QA |
| 6036 | 6/3 | Why is 787 air cleaner? | Product/tech info | yes | info (bleed-free design) | A | – | – | Satisfied customer; ideal RAG QA |
| 15055 | 9/4 | Cancelled flight; seat refund; partner comp missing | Compensation/refund | yes | handoff/escal (CR case 17058483; security check) → partial | W (account-gated) | YES (CR case, security check) | – | Escalated, eventually "getting resolved" off-thread |
| 3735 | 5/3 | Forced to check guitar (soft case) at OSL | Baggage policy | yes | info (Oct-25 policy change; airport shouldn't accept) | A/M (policy QA) | – | – | Policy question answered; no remedy for the past |
| 5842 | 2/1 | On spam list; can't email support | Contact/access | weak | handoff (follow + DM) | W | – | borderline | Issue itself not disclosed |
| 1389 | 13/8 | Mixed: refund unanswered 2 months + website failures; starts with brand marketing tweet | Mixed (refund, web/IT) | mixed | handoff (CR ref via DM) + browser tips | M | partial (CR ref) | YES | Brand marketing tweet + several different customers in one component; split hazard |
| 15804 | 2/1 | Cost to switch code-share (AA metal) to BA | Rebooking/codeshare | yes | handoff (DM details) | W | – | – | Clean hand-off |
| 15806 | 2/1 | Lounge photo (Silver status) | Praise | n/a | social | – | – | YES | Praise |
| 5844 | 3/2 | Fed up; can't reach a human | Contact/complaint | weak | handoff (DM issue/details) | W | – | borderline | No problem stated publicly |
| 2388 | 3/2 | Online check-in failed (MAN-LHR-JFK); told use carrier | Web/check-in tech | yes | info (check in at airport) | M | – | – | Pragmatic; limits given |
| 13559 | 9/4 | 16-year anniversary; separate later praise (Tolkien/Tom Bombadil) | Praise | n/a | social | – | – | YES | Two customers in one component; praise |
| 4726 | 2/1 | Tiny screen / no phone charging | Onboard feedback | yes | info (feedback to CX team) | W | – | – | Feedback-only; unresolved |
| 14812 | 2/1 | Praise for Bali-volcano comms | Praise | n/a | canned data-protection boilerplate | – | – | borderline | Brand misfires canned privacy line onto praise |
| 1894 | 7/3 | Praise of cabin manager; brand reads as complaint; sarcasm ("I was being incredibly sarcastic") | (Praise→misparse) | unclear | apology (mistargeted) | – | – | YES | Misparse + sarcasm; retrieval must not copy this empathy replay |
| 8975 | 2/1 | "Worst CS 2017", how to get a reply | Contact/complaint | weak | clarification request ("not sure what the situation is") | W | – | borderline | No problem-state given |
| 9185 | 2/1 | Booking charged EUR; wants GBP | Booking/currency | yes | info (currency = outbound destination) | A | – | – | Clean resolved QA |
| 13553 | 2/1 | Lost item at Newark; no reply from Lost&Found | Baggage/lost property | yes | info (referral + link) | M/W | – | – | Referral only; no direct help |
| 15799 | 6/3 | Diverted 5h away near Krakow; missed tour; wants comp; no airport info | Disruption + compensation | yes | apologise + will check compensation eligibility on return | M (scaffold) | YES (comp) | – | Escalation committed; outcome pending |
| 966 | 3/2 | Server fault booking flight+car | Web/IT | yes | info (faults team; retry; contact link) | A/M | – | – | Correct troubleshooting |
| 14810 | 6/3 | Can't find flight+hotel search (Spain) | Web/nav | yes | info (2 rounds of step-by-step navigation) | A | – | – | Good trajectory; second round needed (partial) |
| 1895 | 3/1 | Booking reference error ("no flights in the booking") | Web/IT bug | yes | info (patch on 1 Nov) + thanks | A | – | – | Resolved via announced fix ETA |
| 5646 | 6/2 | Cancel 1 of 2 passengers (spouse ill) | Booking modification | yes | handoff (DM booking details) | W (account-gated) | partial | – | Privacy-gated action |
| 1235 | 3/2 | Turkey visa ban; passengers stranded (kid at university) | Disruption/policy | yes | handoff (DM details) | W | – | – | Policy-driven; needs private info |
| 13198 | 3/1 | Booking site "sucks"; no price options; high prices | Web/pricing complaint | yes | apology only ("hope you manage to book") | W | – | – | Unresolved; lost to competitor |
| 328 | 3/2 | #BA228 cancelled; wants free upgrade | Compensation (upgrade) | yes | info (no upgrade; fairness to others) | M/W | – | – | Dispute unresolved |
| 11024 | 2/1 | Praise: Vivienne's flight on time | Praise | n/a | social | – | – | YES | Praise |
| 9750 | 4/2 | Seat 13 on A321 has no air vent (curiosity) | Onboard/tech curiosity | yes | info (crew move if available; not aware) | M | – | – | Benign closed query |
| 961 | 6/4 | Executive Club account hacked | Account security | yes | handoff/escal (DM identity details; route to EC team) | W (account-gated) | YES (security) | – | Strong security-scratch escalation |
| 13558 | 7/3 | Diverted to Krakow; no staff; expenses | Disruption + reimbursement | yes | handoff/escal (apologise; local manager; DM + keep receipts) | W (account-gated) | YES (expenses) | – | Textbook escalation for expenses |
| 4197 | 15/5 | Paid seats removed; no refund; small-claims threat | Seat dispute/refund | yes | apology + call offer; no refund | W | YES (call/dispute) | – | Heated unresolved dispute; escalation appropriate |
| 6102 | 4/2 | Luggage broken at DXB (wheel) | Baggage damage | yes | handoff (World Tracer ref + DM) | W (account-gated) | partial (baggage claim) | – | Claim started; outcome off-thread |
| 14532 | 2/1 | Short (sprinting) connection at Gatwick | Connection concern | weak | encouragement only | – | – | borderline | No real info delivered |
| 4722 | 2/1 | Locked out of Manage My Booking; can't pick seats | Web/access + seat | yes | handoff (DM seat pref + ref) | W (account-gated) | – | – | Clean hand-off |
| 15259 | 3/1 | Catering stock (2 bacon butties / 150 pax) | Catering feedback | yes | info (apologise; pass to Catering) | W | – | – | Feedback-only; customer doubts follow-through |
| 6100 | 16/9 | Website unusable; wants phone; Social can't take calls | Web/IT + contact routing | yes | partial (fine Sales; cache tips; no callback) | M | – | – | Long unresolved loop; routing clarity varies |
| 1388 | 2/1 | Parking-photo humor (#a380) | Praise | n/a | social | – | – | YES | Humor |
| 14809 | 3/1 | Peppa Pig World contest (winner?) | Promo/contest | n/a | social (good luck) | – | – | YES | Contest engagement |
| 9754 | 3/1 | Mixed hold luggage across 3 adults + infant | Baggage config | yes | handoff (DM booking ref/address) | W (account-gated) | – | – | Config advising via DM |
| 15263 | 2/1 | Krakow queues; online check-in broken | Airport/check-in | yes | info (apologise; Airport Manager investigation) | W | partial (manager) | – | Feedback referral |
| 1748 | 20/10 | Compensation MasterCard broken; CR phones dead (30+ calls) | Compensation/card + contact | yes | escal (CR number/hours, webform, alt number) → resolved off-thread | M (routing knowledge) | YES (CR dept) | – | Longest; clean CR escalation that genuinely resolved elsewhere |
| 14530 | 10/5 | Exit-row seat reassigned 3×; Silver status | Seat/status | yes | info (seats not guaranteed; pass to CX) | M | partial (CX) | – | Recurring complaint unresolved |
| 542 | 8/2 | £32 phone charge on £3,700 booking; advisor misquote | Call-charge dispute | yes | info (charges on website) | W | – | borderline | 3rd party chimes in (0844/0344); dispute unresolved |
| 9396 | 2/1 | Praise of safety video | Praise | n/a | social | – | – | YES | Praise |

**Roll-up (sample n=50; these are sample counts, not population estimates):**
- Non-issue praise/humor/marketing/contest: **10** (9184, 1620, 7481, 11024, 1388, 14809, 9396, 15806, 14812, 13559).
- Borderline / no-problem-state / encouragement-only: **4** (5842, 8975, 14532, plus 14812 canned-misfire counted above) and misparse risk **1** (1894).
- Genuine support conversations with a reusable pattern: **~36 (~72%)**.
- Threads with an observable in-thread resolution the thread itself supports: **~8** (129, 6036, 1895, 9185, 9750 [benign close], 15055 [mostly], 1748 [off-thread but confirmed], 961 [via phone]).
- Structured DM / CR hand-off with off-thread outcome: **13** (12371, 15801, 15804, 5844, 5646, 4722, 6102, 9754, 1235, 13558, 15055, 961, plus 4197's offer-to-call).