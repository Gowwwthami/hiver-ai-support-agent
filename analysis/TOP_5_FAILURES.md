# Top 5 Failures (real examples from the golden set)

The five worst end-to-end golden-set cases by combined severity (unsafe AUTO_HANDLE + hallucination + intent mismatch + low judge score). Content is pulled verbatim from `evaluation/predictions.csv` and the golden set; nothing is manufactured.
## 1. BA_105364

1. **Real customer message**: @British_Airways not the best performance at JFK flight BA113 from Heathrow
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `complaint_or_human_assistance`
4. **Predicted label**: `information_or_policy` (confidence 0.3014)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @226431 Oh, dear! What happened, Andy? ^Beth S.
8. **Generated response**: Thanks for reaching out, ^Kieran
9. **Retrieved evidence**: conv 233481 (sim=0.32): @350004 Hi Carolyn, can you please DM us what happened?  ^Kieran
10. **Judge verdict**: intent mismatch between prediction and gold; factual auto reply grounded on top evidence sim=0.32; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: Intent confusion: gold `complaint_or_human_assistance` vs predicted `information_or_policy` (confidence 0.30). The boundary between these intents is weak in the weak-labelled corpus, so the policy routed by the wrong intent.
12. **Proposed fix**: Add explicit boundary/deciding rules between `complaint_or_human_assistance` and `information_or_policy` in `weak.py`, and sample gold-set misclassified pairs as reviewer candidates.

## 2. BA_294773

1. **Real customer message**: @British_Airways How can I contact you regarding cancelling a return flight? I can not phone as I live abroad and you do not have an email address???
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `booking_change_or_cancellation`
4. **Predicted label**: `complaint_or_human_assistance` (confidence 0.9953)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @405293 We're sorry you're having problems contacting our Change Booking team. Please DM us the booking reference, full name, address and mobile 1/2
8. **Generated response**: We're sorry to hear this, @British_Airways Sorry for the late reply. Can you please advise us what information your looking for.
9. **Retrieved evidence**: conv 254627 (sim=0.42): @369266 Sorry for the late reply.  Can you please advise us what information your looking for. ^Karen
10. **Judge verdict**: intent mismatch between prediction and gold; factual auto reply grounded on top evidence sim=0.42; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: Intent confusion: gold `booking_change_or_cancellation` vs predicted `complaint_or_human_assistance` (confidence 1.00). The boundary between these intents is weak in the weak-labelled corpus, so the policy routed by the wrong intent.
12. **Proposed fix**: Add explicit boundary/deciding rules between `booking_change_or_cancellation` and `complaint_or_human_assistance` in `weak.py`, and sample gold-set misclassified pairs as reviewer candidates.

## 3. BA_32854

1. **Real customer message**: Well @British_Airways has definitely gone downhill quite sharply recently. This is the current food situation in the Business Class lounge. 📸 by my Dad. https://t.co/3sXtIgLNUz
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `complaint_or_human_assistance`
4. **Predicted label**: `non_support_or_acknowledgement` (confidence 0.3023)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @151888 Hi Michelle. Sorry for the late reply. I hope the food situation has improved since. Please pass our apologies on to your dad. Which airport are we talking about so we can feed this back? ^Monica
8. **Generated response**: Thanks for getting in touch! We'll share your feedback with the team — is there anything else we can help with?
9. **Retrieved evidence**: conv 1893 (sim=0.25): @117980 We're very glad to hear it, Andy! Although we know it's always nice to be away, there's something even nicer about coming home. ^HP
10. **Judge verdict**: intent mismatch between prediction and gold; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: Intent confusion: gold `complaint_or_human_assistance` vs predicted `non_support_or_acknowledgement` (confidence 0.30). The boundary between these intents is weak in the weak-labelled corpus, so the policy routed by the wrong intent.
12. **Proposed fix**: Add explicit boundary/deciding rules between `complaint_or_human_assistance` and `non_support_or_acknowledgement` in `weak.py`, and sample gold-set misclassified pairs as reviewer candidates.

## 4. BA_358073

1. **Real customer message**: @British_Airways Shockingly-bleak connection from Montego Bay to Kingston. A disappointing start to my trip back to London today.
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `complaint_or_human_assistance`
4. **Predicted label**: `information_or_policy` (confidence 0.2157)
5. **Expected escalation**: `UNCERTAIN`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @381717 Hi Milla, what was it about the flight that you didn't enjoy? ^Kimbers
8. **Generated response**: Thanks for reaching out, @British_Airways Hi Rohan. We're sorry to hear this.
9. **Retrieved evidence**: conv 687031 (sim=0.16): @737637 Hi Rohan.  We're sorry to hear this.  Can you tell us what has gone wrong and at which airport? ^N
10. **Judge verdict**: intent mismatch between prediction and gold; factual auto reply grounded on top evidence sim=0.16; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: The customer message carries a **complaint** risk, but the classifier predicted `information_or_policy` — a safe-by-default intent whose AUTO_HANDLE branch does not re-run escalation.py's safety markers (those only fire inside the complaint branch). The evidence-sufficiency gate also passed (top sim 0.16), so the request was auto-handled instead of routed to a human.
12. **Proposed fix**: Move the legal/security/money safety markers in `escalation.py` ABOVE the intent branches so they override every prediction, regardless of intent. Add regression tests asserting a lawsuit/legal sentence always ESCALATEs.

## 5. BA_334633

1. **Real customer message**: @British_Airways flew on your 777 to St Lucia from Gatwick. Big disappointment. Poor food and enterntainment system from the 80’s 👎🏽
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `complaint_or_human_assistance`
4. **Predicted label**: `non_support_or_acknowledgement` (confidence 0.2071)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @391303 Hi Rahul.  We're sorry you didn't enjoy your experience with us today.  We hope your child is feeling better soon.  ^N
8. **Generated response**: Thanks for getting in touch! We'll share your feedback with the team — is there anything else we can help with?
9. **Retrieved evidence**: conv 517926 (sim=0.25): @600541 Thanks for getting in touch about your St Lucia flight, and for the round of applause! We hope to see you on board again soon. ^Cec
10. **Judge verdict**: intent mismatch between prediction and gold; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: The customer message carries a **complaint** risk, but the classifier predicted `non_support_or_acknowledgement` — a safe-by-default intent whose AUTO_HANDLE branch does not re-run escalation.py's safety markers (those only fire inside the complaint branch). The evidence-sufficiency gate also passed (top sim 0.25), so the request was auto-handled instead of routed to a human.
12. **Proposed fix**: Move the legal/security/money safety markers in `escalation.py` ABOVE the intent branches so they override every prediction, regardless of intent. Add regression tests asserting a lawsuit/legal sentence always ESCALATEs.

