# Data Contract — British_Airways Support-Agent Pipeline

This document freezes the dataset pipeline: what the system reads, how
conversations become training/retrieval material, and — critically — which
leakage controls guarantee the evaluation set is never learned from.

## 1. Input

`data_extracted/twcs/twcs.csv` — the *Customer Support on Twitter* (Twcs) CSV
(2.8M tweets). Privacy/Attribution: per the dataset README we store the
substantive message fields the support task needs and section headers/counts
only; we do not republish the full corpus, and no account-specific fields
(birth dates, locations, phone numbers, etc.) travel into any artifact.

## 2. Brand filter

Conversations containing at least one tweet authored by the support account
named exactly **`British_Airways`** (defined via `conversation_summary` brand
author detection from Phase 1). Only tweet-level columns
`conv_id, tweet_id, author_id, inbound, created_ts, text` are used.

## 3. Conversation reconstruction

**Reused unmodified** from Phase 2:

* `analysis/scripts/reconstruct_conversations.py` builds
  `analysis/cache/conversations.parquet` from the validated Twitter reply-link
  semantics (`in_reply_to_status_id` edges), with `inbound` marking any tweet
  not authored by the brand account.
* `analysis/cache/conversation_summary.parquet` carries per-conversation
  metadata incl. brand authors.

## 4. Classification input (customer message)

For a support conversation, each **inbound (customer) turn** is a candidate
classification input. The corpus keeps every inbound turn that has at least one
later brand reply in the same conversation (`_extract_pairs`), so a record =
`(customer_msg, prior_context ≤2 prior turns, next brand_reply)`.

For the **golden evaluation set**, the shipped golden.csv already fixes the exact
target inbound message per conversation (`customer_message`, first-inbound bias
with later-position borderline rows), unchanged.

## 5. Historical resolution evidence

For a given inbound turn, eligible evidence = the **next brand-authored reply**
in the same conversation after that turn. It is stored as `brand_reply` and
exposed (as retrieval evidence) as `{rank, similarity, conv_id, weak_intent,
brand_reply, prior_context}`.

Historical BA replies are **evidence**, never ground-truth policy. Generation
must not copy them blindly and must not assert facts beyond retrieved evidence.

## 6. Exclusions (applied at corpus build time)

1. The **200 golden conversations** (evaluation hold-out).
2. The **50 Phase-1 audit-pool conversations**.
3. **Customer-level separation**: any record whose customer author also appears
   inside a golden conversation is dropped (strictly stronger than
   conversation-level splitting), because customers re-contact.
4. Records with no usable later brand reply (no resolution evidence).
5. Duplicate/near-duplicate **target** messages across examples are detected and
   reported by the validator (any found would be a validation error).

Per-query exclusions at retrieval time:
* query conversation id and query customer id excluded;
* near-duplicate corpus messages excluded (token-set Jaccard ≥ 0.85);
* optional predicted-intent candidate filter.

**Answer-leakage rule:** a golden example whose reference reply contains the
literal answer cannot appear in the retrieval/training pool (it is excluded by
(1)); messages whose next brand reply *only* says "DM us" without an answer are
kept (realistic) but are answered by generation as routing, not as fact.

## 7. Splits (documented, reproducible)

| split | n | construction |
|---|---|---|
| eval | 200 | golden set (assistant-drafted; human reviews pending) |
| train (weak) | 11,987 confident rows | `weak_confident && weak_intent != other` records from the leakage-excluded corpus (deduplicated by customer_msg) |
| retrieval | 26,578 records / 16,092 conversations | leakage-excluded corpus (confident or not) |

`run_eval` writes these counts into `results.json` (`overview.*`,
`leakage.*`). Seeds: golden sampling `SAMPLING_SEED=2026` (Phase 2, unchanged);
evaluation/model `EVAL_SEED=42`.

## 8. Leakage checks (asserted, not assumed)

* corpus ∩ {golden ∪ audit} conversations = **0** ;
* corpus rows sharing a customer with the golden set = **0** ;
* `run_eval` asserts the top retrieved evidence conversation of any eval query is
  never a golden conversation (recorded as `leakage.evidence_top_conv_golden_leak`,
  must be 0);
* the classifier trains on weak labels only — golden labels never enter a fit.