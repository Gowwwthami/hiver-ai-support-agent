# Top 5 Failures (real examples from the golden set)

The five worst end-to-end golden-set cases by combined severity (unsafe AUTO_HANDLE + hallucination + intent mismatch + low judge score). Content is pulled verbatim from `evaluation/predictions.csv` and the golden set; nothing is manufactured.
## 1. BA_248481

1. **Real customer message**: @British_Airways hi. I need to change my passport no. on upcoming flight. Asked for help online but haven't heard back. Can you help please?
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `booking_change_or_cancellation`
4. **Predicted label**: `complaint_or_human_assistance` (confidence 0.9783)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @363665 Hi Hayley, can you DM your booking reference, full name and contact number? Please also include the passport number, expiry date (1/2)
8. **Generated response**: We're sorry to hear this, Could you also give us more information about what you need help with and we’ll happily look at your booking for you. ^Amy
9. **Retrieved evidence**: conv 732367 (sim=0.35): @772980 Would you mind sending us a DM including your full name, booking ref and email address please? Could you also give us more information about what you need help with and we’ll happily look at your booking for you.
10. **Judge verdict**: intent mismatch between prediction and gold; factual auto reply grounded on top evidence sim=0.35; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: Intent confusion: gold `booking_change_or_cancellation` vs predicted `complaint_or_human_assistance` (confidence 0.98). The boundary between these intents is weak in the weak-labelled corpus, so the policy routed by the wrong intent.
12. **Proposed fix**: Add explicit boundary/deciding rules between `booking_change_or_cancellation` and `complaint_or_human_assistance` in `weak.py`, and sample gold-set misclassified pairs as reviewer candidates.

## 2. BA_255518

1. **Real customer message**: @British_Airways Who do i contact to get an international flight  datechanged?
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `booking_change_or_cancellation`
4. **Predicted label**: `complaint_or_human_assistance` (confidence 0.8683)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @300160 Hi Mike, you should be able to make changes on https://t.co/2Ty8CEO0Dq, under Manage My Booking using your booking reference, or you can 1/2
8. **Generated response**: We're sorry to hear this, @British_Airways If the passenger would like to reach out to us on twitter, we'd be happy to assist, Rebeca. ^Lisa
9. **Retrieved evidence**: conv 55894 (sim=0.62): @176421 If the passenger would like to reach out to us on twitter, we'd be happy to assist, Rebeca. Many thanks. ^Lisa
10. **Judge verdict**: intent mismatch between prediction and gold; factual auto reply grounded on top evidence sim=0.62; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: Intent confusion: gold `booking_change_or_cancellation` vs predicted `complaint_or_human_assistance` (confidence 0.87). The boundary between these intents is weak in the weak-labelled corpus, so the policy routed by the wrong intent.
12. **Proposed fix**: Add explicit boundary/deciding rules between `booking_change_or_cancellation` and `complaint_or_human_assistance` in `weak.py`, and sample gold-set misclassified pairs as reviewer candidates.

## 3. BA_331684

1. **Real customer message**: Filthy seat, careless service and 6500€ wasted on a business class ticket @British_Airways to LA with the new A380. Another disappointment. https://t.co/y8a3WeLnVz
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `complaint_or_human_assistance`
4. **Predicted label**: `seat_or_upgrade` (confidence 0.7835)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @286385 That's disappointing to hear, Giovanna! If you let me know your flight number, I'll be happy to feed this back for you. ^BS
8. **Generated response**: Thanks for your message, @British_Airways Sorry to hear of your disappointment, Daniel. You will be able to select a seat for free at online check-in.
9. **Retrieved evidence**: conv 46963 (sim=0.30): @166903 Sorry to hear of your disappointment, Daniel. You will be able to select a seat for free at online check-in. ^Anthony
10. **Judge verdict**: intent mismatch between prediction and gold; factual auto reply grounded on top evidence sim=0.30; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: The customer message carries **complaint** wording, but the classifier predicted `seat_or_upgrade` — a safe-by-default intent. escalation.py's complaint markers only fire inside matching intent branches (not globally), so the misclassification routed the message past them; the evidence-sufficiency gate passed (top sim 0.30), so it was auto-handled.
12. **Proposed fix**: Add boundary-deciding rules between `complaint_or_human_assistance` and `seat_or_upgrade` in `weak.py` (or promote the **complaint** marker family above the intent branches in `escalation.py`), and add a regression test asserting the exact message ESCALATEs.

## 4. BA_294773

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

## 5. BA_150929

1. **Real customer message**: @British_Airways I have a tkt for a flt 2moro fm BHD-LHR AT 0645 which allows me to change the time of flight on the same day if there is1/3
2. **Prior context visible to the customer**: (none)
3. **Expected label**: `booking_change_or_cancellation`
4. **Predicted label**: `information_or_policy` (confidence 0.3501)
5. **Expected escalation**: `ESCALATE`
6. **Predicted escalation**: `AUTO_HANDLE` (reason: )
7. **Golden reference reply**: @271448 Could we give you a call please, Ryan? We'll need your booking ref, full name, email and contact number. Could you also let us know the 1/2
8. **Generated response**: Thanks for reaching out, @British_Airways Hi Aga, you would need to speak to some one to make this change, as we would need to split the booking. 1/2
9. **Retrieved evidence**: conv 464590 (sim=0.29): @555856 Hi Aga, you would need to speak to some one to make this change, as we would need to split the booking. 1/2
10. **Judge verdict**: intent mismatch between prediction and gold; factual auto reply grounded on top evidence sim=0.29; UNSAFE: gold routed away from AUTO_HANDLE but predicted AUTO_HANDLE
11. **Likely root cause**: Intent confusion: gold `booking_change_or_cancellation` vs predicted `information_or_policy` (confidence 0.35). The boundary between these intents is weak in the weak-labelled corpus, so the policy routed by the wrong intent.
12. **Proposed fix**: Add explicit boundary/deciding rules between `booking_change_or_cancellation` and `information_or_policy` in `weak.py`, and sample gold-set misclassified pairs as reviewer candidates.

