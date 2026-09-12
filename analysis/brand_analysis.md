# Customer Support on Twitter — Dataset Forensics & Brand Selection

Phase-1 evidence report. All numbers are computed from `twcs/twcs.csv` via the scripts in `analysis/scripts/`. No metric is estimated by an LLM; where a value is a heuristic it is labelled.


## 1. Dataset schema (facts)

| metric                          | value                                                                                                                                                                                  |
|:--------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| file size (uncompressed)        | 516.5 MB                                                                                                                                                                               |
| rows                            | 2,811,774                                                                                                                                                                              |
| columns                         | 7                                                                                                                                                                                      |
| exact duplicate rows            | 0                                                                                                                                                                                      |
| rows whose tweet_id repeats     | 0                                                                                                                                                                                      |
| tweet_id unique                 | yes (2,811,774 distinct)                                                                                                                                                               |
| created_at (PARSED, true range) | 2008-05-08 20:13:59+00:00 (parsed) -> 2017-12-03 23:14:01+00:00 (parsed)                                                                                                               |
| note on 2016 date-range claim   | WARNING: earlier min/max were computed with string (lexical) ordering on created_at and were WRONG. Corrected values parsed via pd.to_datetime. 99.94% of rows are 2017-10 -> 2017-12. |

Columns (as read by DuckDB `read_csv_auto`):

| column_name             | column_type   |
|:------------------------|:--------------|
| tweet_id                | BIGINT        |
| author_id               | VARCHAR       |
| inbound                 | BOOLEAN       |
| created_at              | VARCHAR       |
| text                    | VARCHAR       |
| response_tweet_id       | VARCHAR       |
| in_response_to_tweet_id | BIGINT        |

**Column semantics (based on direct data inspection, not assumptions):**
- `tweet_id` — unique id of the tweet (BIGINT; never missing).
- `author_id` — author account id (string; may be a retired numeric handle such as `115850`).
- `inbound` — `True` = customer→brand (the support *inbound* side); `False` = brand/outbound tweet.
- `created_at` — RFC-style timestamp string.
- `text` — tweet text (never empty in this file).
- `response_tweet_id` — **the tweet believed to be the response to this one (forward child link)**; for
  inbound rows it points to the brand reply ~80% of the time. May contain a comma-separated list of tweet
  ids belonging to the same thread (crawler artifact; 222,426 rows, ~7.9%). NULL otherwise.
- `in_response_to_tweet_id` — **parent/backward link**: the tweet this row replies to. For outbound rows it
  matches the inbound customer tweet 99.3% of the time → the primary brand→customer edge.

Nulls (key columns): `response_tweet_id` 1,040,629 (37.0%); `in_response_to_tweet_id` 794,335 (28.3%).
Other columns: 0 nulls.


## 2. Brand identification (method)


**Defensible method — no assumption that 'every non-inbound author is a brand'.**
A *support account* is an author that posts outbound (`inbound=False`) tweets that *directly reply to a
customer tweet* (i.e. the outbound row's `in_response_to_tweet_id` resolves to an existing inbound tweet).
Customers are the authors on the other side of those links. Threshold: ≥100 such responses.
Result: **101 support-account candidates**; full ranked table in `brand_statistics.csv`.


## 3. Ranked brands/support accounts (top 25 by responses-to-customers)

| brand           |   total_tweets |   inbound_tweets |   outbound_tweets |   tweets_responding_to_customer_tweets |   unique_customers_interacted_with |
|:----------------|---------------:|-----------------:|------------------:|---------------------------------------:|-----------------------------------:|
| AmazonHelp      |         169840 |                0 |            169840 |                                  74127 |                              38041 |
| AppleSupport    |         106860 |                0 |            106860 |                                  28373 |                              20941 |
| Uber_Support    |          56270 |                0 |             56270 |                                  15339 |                              11113 |
| VirginTrains    |          27817 |                0 |             27817 |                                  13246 |                               6913 |
| SpotifyCares    |          43265 |                0 |             43265 |                                  12709 |                               8158 |
| AmericanAir     |          36764 |                0 |             36764 |                                  12317 |                               8354 |
| Delta           |          42253 |                0 |             42253 |                                  10535 |                               7013 |
| Tesco           |          38573 |                0 |             38573 |                                  10107 |                               6643 |
| GWRHelp         |          19364 |                0 |             19364 |                                   9468 |                               4632 |
| VerizonSupport  |          17966 |                0 |             17966 |                                   8972 |                               4218 |
| British_Airways |          29361 |                0 |             29361 |                                   8671 |                               5655 |
| TMobileHelp     |          34317 |                0 |             34317 |                                   8486 |                               5677 |
| XboxSupport     |          24557 |                0 |             24557 |                                   7810 |                               5153 |
| SouthwestAir    |          28977 |                0 |             28977 |                                   7723 |                               5787 |
| sainsburys      |          19466 |                0 |             19466 |                                   7428 |                               4914 |
| AskPlayStation  |          19098 |                0 |             19098 |                                   6811 |                               4731 |
| comcastcares    |          33031 |                0 |             33031 |                                   6786 |                               4912 |
| hulu_support    |          21872 |                0 |             21872 |                                   6755 |                               4582 |
| Ask_Spectrum    |          25860 |                0 |             25860 |                                   6625 |                               4481 |
| O2              |          16212 |                0 |             16212 |                                   6350 |                               3723 |
| sprintcare      |          22381 |                0 |             22381 |                                   6192 |                               4091 |
| Safaricom_Care  |          16077 |                0 |             16077 |                                   5605 |                               3307 |
| ATVIAssist      |          17650 |                0 |             17650 |                                   5603 |                               3805 |
| idea_cares      |          15724 |                0 |             15724 |                                   5591 |                               2904 |
| ChipotleTweets  |          18749 |                0 |             18749 |                                   5562 |                               4390 |

## 4. Conversation reconstruction (method)


Conversations = connected components of the tweet-reply graph. Edges are added from **both** link fields:
`in_response_to_tweet_id` (parent) and every numeric member of `response_tweet_id`
(including comma-separated chain values). Missing parents are handled gracefully: they contribute no turn.

Results: **798,197 connected components** from 4,027,154 resolved edges.
Per-brand conversation stats in `conversation_quality.csv`. Because a component may (rarely) contain two
brand accounts, per-brand stats count each component under every brand it contains.


## 5. Conversation quality (candidate brands)

| brand           |   n_conversations |   median_conversation_length |   mean_conversation_length |   pct_ge2_brand_responses |   pct_ge3_brand_responses |   unique_customers |   avg_customer_messages_per_conv |   avg_brand_messages_per_conv |
|:----------------|------------------:|-----------------------------:|---------------------------:|--------------------------:|--------------------------:|-------------------:|---------------------------------:|------------------------------:|
| AmazonHelp      |             82556 |                            3 |                       4.53 |                    0.4963 |                    0.2305 |              88682 |                             2.47 |                          2.06 |
| SpotifyCares    |             28280 |                            2 |                       3.25 |                    0.2918 |                    0.114  |              30793 |                             1.72 |                          1.53 |
| AmericanAir     |             26386 |                            2 |                       3.32 |                    0.2726 |                    0.0746 |              28945 |                             1.9  |                          1.39 |
| Delta           |             26168 |                            2 |                       3.36 |                    0.3334 |                    0.1327 |              28230 |                             1.73 |                          1.61 |
| Tesco           |             16722 |                            4 |                       4.38 |                    0.6098 |                    0.343  |              18685 |                             2.05 |                          2.31 |
| British_Airways |             16452 |                            3 |                       3.69 |                    0.4433 |                    0.1744 |              17944 |                             1.9  |                          1.78 |
| VirginTrains    |             14853 |                            3 |                       4.43 |                    0.4223 |                    0.1783 |              18237 |                             2.55 |                          1.87 |
| XboxSupport     |             13455 |                            3 |                       4.29 |                    0.4247 |                    0.1572 |              17563 |                             2.41 |                          1.83 |

## 6. Data quality / noise (candidate brands)


No empty texts, near-zero extremely-short or URL-only messages across all candidates.
Relevant noise types found by inspection of sampled threads:
- **cross-language/noise** (mainly AmazonHelp: ~8% of first customer messages are non-Latin),
- **non-support content** (praise, promos, jokes, feature requests — present in every Twitter brand),
- **brand-initiated (marketing) tweets** inside reply components (e.g. British_Airways #AFairTaxOnFlying),
- **fragmented brand identity** (AmazonHelp + numeric partner handles as separate authors),
- **referrals to other support accounts** (VirginTrains → @120576 etc.).
Numbers in `data_quality.csv`.


## 7. Response (template) diversity (candidate brands)


Normalized templates: URLs→`{URL}`, mentions→`@USER`, numbers→`{NUM}`, lowercased, whitespace collapsed.
High uniqueness = individualized historical replies; low uniqueness = canned funnels.

| brand           |   n_brand_outbound_tweets |   unique_ratio_normalized |   top10_template_share |   top20_template_share |
|:----------------|--------------------------:|--------------------------:|-----------------------:|-----------------------:|
| AmazonHelp      |                    169840 |                    0.9074 |                 0.006  |                 0.0095 |
| SpotifyCares    |                     43265 |                    0.8222 |                 0.0174 |                 0.0253 |
| Delta           |                     42253 |                    0.9209 |                 0.0156 |                 0.0215 |
| Tesco           |                     38573 |                    0.9408 |                 0.0122 |                 0.0191 |
| AmericanAir     |                     36764 |                    0.9677 |                 0.0068 |                 0.01   |
| British_Airways |                     29361 |                    0.9896 |                 0.0033 |                 0.0048 |
| VirginTrains    |                     27817 |                    0.9352 |                 0.0115 |                 0.0171 |
| XboxSupport     |                     24557 |                    0.7178 |                 0.0843 |                 0.106  |

## 8. Customer-problem diversity (TF-IDF clustering)


Deterministic sample (seed 42, ≤20k first customer messages per brand), TF-IDF (1-2 grams) + KMeans(6).
Full cluster summaries in `customer_diversity.json`. Representative recurring problem areas:

- **British_Airways**: online check-in/web errors, flight delay/cancellation & refunds, booking changes & seat policy, baggage / lost luggage, customer-service complaints

- **Tesco**: product quality (rotten/faulty), delivery & click&collect, refunds & pricing, store/staff complaints, website/slots & product-specific queries

- **Delta**: flight change/rebooking, baggage handling, meal/seat requests, app issues, sky club & praise feedback

- **AmericanAir**: delays/cancellations, rebooking & refunds, seat & baggage fees, customer-service complaints, praise/thanks

- **AmazonHelp**: delivery/tracking, refund claims, account access/hacked, order issues, prime/billing, non-Latin & promo noise

- **VirginTrains**: train cancellations/delays, refunds, seat reservations, onboard issues (heat/wifi), cross-operator referrals

- **XboxSupport**: game-specific bugs (CoD WW2, etc.), hardware (controller), store purchase/errors, Xbox Live sign-in/gold, preorders/refunds

- **SpotifyCares**: premium billing/upgrades, account access, playback bugs, missing songs/availability, feature requests & feedback


## 9. Resolution diversity (problem → resolution)


For each conversation with ≥1 customer message and ≥1 brand response, problem = first customer message,
resolution = last brand response. Brand responses are classified by a heuristic action-type regex.
`mean_Bhatt` = mean pairwise Bhattacharyya distance of resolution-type distributions across problem
clusters (higher = problems handled differently; heuristic, labelled).

| brand | n pairs | mean_Bhatt | unique last-resp ratio | DM_INFO share of last resp |
|---|---|---|---|---|
| British_Airways | 16,452 | 0.0309 | 0.9894 | 0.1575 |
| Tesco | 16,722 | 0.0068 | 0.9535 | 0.3558 |
| Delta | 26,166 | 0.0499 | 0.9149 | 0.2241 |
| AmericanAir | 26,386 | 0.0255 | 0.9679 | 0.1959 |
| AmazonHelp | 82,556 | 0.1964 | 0.9279 | 0.1216 |
| VirginTrains | 14,851 | 0.0103 | 0.9329 | 0.0387 |
| XboxSupport | 13,435 | 0.018 | 0.6938 | 0.3268 |
| SpotifyCares | 28,277 | 0.1467 | 0.8026 | 0.4217 |

Interpretation: BA/AA/Delta/Tesco respond **individually** (unique-ratio ≥0.91) and mostly in public;
Uber/T-Mobile resolve almost everything via a DM funnel (Bhatt ≈ 0.00–0.006). High unique-ratio must be
interpreted carefully: it indicates individualized replies, not automatically better support.


## 10. DM / private-channel behavior

| brand           |   n_brand_messages |   share_brand_msgs_dm_or_private |
|:----------------|-------------------:|---------------------------------:|
| AmazonHelp      |             169840 |                           0.1309 |
| SpotifyCares    |              43265 |                           0.3202 |
| AmericanAir     |              36764 |                           0.2015 |
| Delta           |              42253 |                           0.1826 |
| Tesco           |              38573 |                           0.285  |
| British_Airways |              29361 |                           0.1641 |
| VirginTrains    |              27817 |                           0.0316 |
| XboxSupport     |              24557 |                           0.2496 |

A high DM share is a *design consideration*, not a quality verdict: Uber/T-Mobile defensibly go private for
PII. For a RAG-grounded agent it reduces *publicly observable* resolution evidence.


## 11. Sampled complete conversations


`analysis/candidate_conversations/BRAND.md` — deterministic stratified samples (seed 137, ~50 complete
threads/brand) spanning short/medium/long threads and problem clusters. Inspected manually for this report.


## 12. Brand-selection scorecard

Scale: 1=poor 2=weak 3=adequate 4=strong 5=excellent. Every score's raw evidence and reason are in `analysis/scorecard_evidence.json`.

| brand           |   A_volume |   B_richness |   C_problem |   D_resolution |   E_grounding |   F_escalation |   G_noise |   H_eval |   I_repro |   total |
|:----------------|-----------:|-------------:|------------:|---------------:|--------------:|---------------:|----------:|---------:|----------:|--------:|
| British_Airways |          4 |            4 |           4 |              5 |             4 |              4 |         4 |        5 |         5 |      39 |
| Tesco           |          3 |            5 |           5 |              4 |             4 |              4 |         4 |        5 |         4 |      38 |
| Delta           |          4 |            4 |           4 |              4 |             4 |              4 |         4 |        5 |         5 |      38 |
| AmericanAir     |          4 |            3 |           4 |              4 |             4 |              4 |         4 |        5 |         5 |      37 |
| AmazonHelp      |          5 |            4 |           4 |              4 |             4 |              4 |         2 |        5 |         4 |      36 |
| VirginTrains    |          3 |            4 |           4 |              5 |             5 |              3 |         3 |        4 |         4 |      35 |
| XboxSupport     |          3 |            4 |           4 |              3 |             3 |              3 |         4 |        4 |         4 |      32 |
| SpotifyCares    |          3 |            3 |           4 |              3 |             3 |              3 |         4 |        4 |         4 |      31 |
| TMobileHelp     |          3 |            3 |           4 |              2 |             2 |              2 |         4 |        3 |         3 |      26 |

## 13. Recommendation


### Recommended winner: **British_Airways**
Strengths: cleanest high-volume candidate (G=4, I=5) with a *crisp, well-attested intent taxonomy*
(check-in/web, cancellation/refund, booking/seat, baggage, complaints); **98.9% unique normalized
historic responses** (top-20 template share 0.48%) → historical grounding reflects real case variety;
**44.3% of conversations have ≥2 brand responses**; resolutions happen publicly for policy/status questions
and escalate to Customer Relations for refund disputes (real escalation cases). 16,452 conversations are
enough for conversation-level TRAIN/DEV/TEST + a 150–250 golden set, and the clean data keeps the whole
pipeline reproducible in minutes.

Weaknesses: 16% of brand messages still move to DM (typical for PII); some marketing brand-tweets inside
threads; airline-intent temporal sensitivity (a 2017 flight issue is an easy intent, a modern reader sees
the era).

### Runner-up: **AmazonHelp**
Most data (82K+ conversations), richest multi-turn (≥2 brand responses in 49.6%), and the **highest
problem→resolution differentiation** (Bhatt 0.196). It loses to BA on **manageability/noise** (score G=2 vs
4): ~8% non-Latin text, fragmented brand identity across several Amazon handles, and promo/joke noise
would force the <15-min reproducible pipeline to carry a heavier cleaning step — a real risk for a
take-home with tight time budget.

### Why not Tesco/Delta (equal-score runners)?
Tesco has the highest multi-turn rate (61% ≥2 responses) and broad retail intents but a thinner pool
(16.7K) and modest template concentration around supplier referrals. Delta is excellent and clean but its
final responses include a large polite-acknowledgement share (28% ACK), so 'resolution' is less often a
tangible action in public text than BA's policy/process answers.


## 14. Challenging the recommendation


1. **Why not simply pick the brand with the most data?** Volume alone selects AmazonHelp. Its usable
   English, both-party, multi-turn subset is still huge — but the *fixed* cost of de-noising
   multilingual/promotional/fragmented-handle data is high for a 15-min reproducibility constraint, and
   interview attention drains into 'why did we filter X' instead of the agent itself.
2. **Can high conversation volume mislead?** Yes — see (1). Volume also concentrates in AmazonHelp where a
   large share of threads are 2-tweet exchanges ("help"→"link"), inflating raw counts without adding
   resolution evidence.
3. **Can high response diversity signal noise?** Yes. AmazonHelp's top response templates included
   truncated fragments (`et`, `tn`) from multilingual text — its high "uniqueness" is partly fragmentation
   noise, not richer support. We therefore never score diversity alone; we pair it with DM-share,
   multi-turn rate, and manual thread inspection.
4. **Do long conversations indicate BAD support?** Sometimes yes. Some very long threads are
   *never-resolved* complaint spirals (e.g. BA refund case spanning 7 days), which are valuable escalation
   examples but not good RAG "resolutions". We treat long threads as evidence of *escalation material*,
   not automatically of good resolution.
5. **Are repeated responses actually good?** Often yes — canned-but-effective ("DM us") is the correct
   privacy-preserving act and is exactly what an escalation classifier should learn. We penalize brands
   only for *uniform* canned handling with no differentiation (Uber/T-Mobile), because that leaves no
   per-intent grounding signal.
6. **Best overall balance?** British_Airways: enough data (top-5 volume), 7+ crisp intents, 99%-unique
   individual resolutions, real public agreements + clear escalations, clean enough to be flawless under a
   time budget. Data-volume leaders trade their scale for noise; Tesco/Delta trade some resolution
   sharpness for politeness templates.


## 15. Data leakage — how splits must work later


The final pipeline must split at **conversation level**: a `conversation_id` (the reconstructed
component) can appear in exactly one of TRAIN / DEV / TEST / GOLDEN.
- Splitting individual tweets independently leaks: a reply and its parent land in different sets, so the
  model has effectively seen the customer message (or the brand's own draft) before evaluation → inflated,
  indefensible metrics.
- Conversations sharing a **customer** (the same person tweeting on different days) are a minor additional
  leakage: we recommend holding out full customers from TRAIN when feasible (deterministic, seeded) so the
  test measures behaviour on *unseen people*, matching the live product setting.
- `created_at` guarantees nothing by itself; conversation-level `conv_id` is the required unit.


## 16. Reproducibility


Environment: Python 3.14.7; `pandas`, `duckdb`, `scikit-learn`, `pyarrow`.
All randomness is seeded (sampling seed 42 for clustering; 137 for conversation samples; 42 in KMeans).
Scripts run bottom-up:

```
pip install pandas duckdb scikit-learn pyarrow
# from analysis/scripts, in this order:
python inspect_dataset.py          # -> analysis/schema_report.json
python explore_link_semantics.py   # (diagnostic, not required for pipeline)
python analyze_brands.py           # -> brand_statistics.csv/.json
python reconstruct_conversations.py# -> cache/conversations*.parquet  (~4.5 min)
python analyze_conversation_quality.py
python analyze_data_quality.py
python analyze_response_diversity.py
python analyze_customer_diversity.py        # (few minutes)
python analyze_resolution_and_dm.py
python analyze_resolution_diversity.py
python sample_candidate_conversations.py
python build_brand_scorecard.py
```

Determinism caveat: `reconstruct_conversations.py` parses timestamps with a fixed format and union-find is
order-independent, so outputs are byte-deterministic given the same input. No automation (e.g. DuckDB
view reuse) writes outside `analysis/`.
