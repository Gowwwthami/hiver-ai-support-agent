# British_Airways Support-Agent — Evaluation Report

- Golden set evaluated: **200** (final label decisions are the recorded human finals — see §G; the three Phase-2.1 renames are stored in legacy spelling and mapped at eval time via `taxonomy.to_canonical`).
- Judge backend: **offline** (offline deterministic unless OPENAI_API_KEY + EVAL_JUDGE=openai).
- Seed: 42; top-k: 3.
- Measured wall-clock runtime of this run: **208.3 s** (measured, not estimated).

## A. Intent classification (golden held-out set)

| system | accuracy | macro F1 | weighted F1 |
|---|---:|---:|---:|
| `majority_baseline` | 0.0550 | 0.0104 | 0.0057 |
| `rule_keyword_baseline` | 0.3550 | 0.4029 | 0.4064 |
| `tfidf_lr_baseline` | 0.5050 | 0.4490 | 0.5183 |
| `hybrid_main` | 0.5100 | 0.4768 | 0.5252 |

Per-class precision/recall/F1 (hybrid main):

| intent | support | precision | recall | F1 |
|---|---:|---:|---:|---:|
| `non_support_or_acknowledgement` | 58 | 0.758 | 0.431 | 0.549 |
| `flight_disruption` | 27 | 0.742 | 0.852 | 0.793 |
| `information_or_policy` | 23 | 0.302 | 0.565 | 0.394 |
| `refund_or_compensation` | 22 | 0.538 | 0.318 | 0.400 |
| `website_or_app_issue` | 21 | 0.769 | 0.476 | 0.588 |
| `baggage` | 16 | 1.000 | 0.688 | 0.815 |
| `booking_change_or_cancellation` | 13 | 0.500 | 0.077 | 0.133 |
| `complaint_or_human_assistance` | 11 | 0.171 | 0.545 | 0.261 |
| `seat_or_upgrade` | 6 | 0.364 | 0.667 | 0.471 |
| `account_access_or_security` | 3 | 0.250 | 0.667 | 0.364 |

Confusion matrix (labels sorted): see `results.json` → `intent_classification.hybrid_main.confusion_matrix`.

## B. Retrieval

| metric | value |
|---|---:|
| records | 200 |
| hit_rate_at_k | 1.0 |
| mean_top1_similarity | 0.2478 |
| mean_topk_similarity | 0.2085 |
| mean_topk_similarity_median | 0.194 |
| recall_at_k_intent_consistency | 1.0 |
| evidence_word_overlap_with_reference | 0.1595 |

Retrieval sim is TF-IDF cosine; `recall_at_k_intent_consistency` is a coarse coverage proxy against golden intent, not human relevance.

## C. Response quality (full pipeline, judge)

| metric | value |
|---|---:|
| correctness | 3.53 |
| correctness_n | 200 |
| groundedness | 4.055 |
| groundedness_n | 200 |
| completeness | 4.695 |
| completeness_n | 200 |
| overall | 2.2 |
| overall_n | 200 |
| hallucination_rate | 0.0 |
| escalation_appropriate_rate | 0.75 |
| judge_backends_used | {'offline': 200} |

## D. Escalation routing (full pipeline)

| metric | value |
|---|---:|
| accuracy | 0.645 |
| false_auto_handle_rate | 0.25 |
| n_false_auto_handle | 50 |
| false_escalation_rate | 0.1 |
| n_false_escalation | 20 |
| auto_handle_precision | 0.6644 |
| auto_handle_recall | 0.8319 |
| auto_handle_f1 | 0.7388 |
| confusion | {'AUTO_HANDLE': 119, 'ESCALATE': 75, 'UNCERTAIN': 6} |

Unsafe AUTO_HANDLE ids: BA_135900, BA_147482, BA_150929, BA_154364, BA_168706, BA_174566, BA_175984, BA_177915, BA_231852, BA_235380, BA_236326, BA_24151, BA_248481, BA_255518, BA_294773, BA_307083, BA_331684, BA_358078, BA_375254, BA_408652, BA_409290, BA_409640, BA_410230, BA_423824, BA_472183, BA_487360, BA_495495, BA_50753, BA_51492, BA_525809, BA_542898, BA_547282, BA_568345, BA_578442, BA_630270, BA_634124, BA_661009, BA_689051, BA_705493, BA_71387, BA_737110, BA_73767, BA_749232, BA_755281, BA_765259, BA_766761, BA_783910, BA_787976, BA_83067, BA_98911

## E. Ablations (judge)

| config | overall | groundedness | hallucination rate | escalation-appropriate |
|---|---:|---:|---:|---:|
| `A_classifier_only` | 1.79 | 3.00 | 0.00 | 0.75 |
| `B_classifier_retrieval` | 1.66 | 3.33 | 0.00 | 0.75 |
| `C_grounded_generation` | 2.09 | 3.61 | 0.00 | 0.75 |
| `D_full` | 2.20 | 4.05 | 0.00 | 0.75 |

## F. Splits and leakage controls

- Train signal: weakly-labelled, confident corpus rows (weak-confident share 0.451).
- Eval: golden set `n=200` (never in corpus, never in classifier training).
- Corpus: 26,578 records; golden/audit conversation overlap 0; golden-customer overlap rows 0.
- Evidence returned to eval examples that is itself a golden conversation: **0** (must be 0).

## G. Human-review status and honesty notes
Draft (assistant) recommendations vs. the recorded human final decisions — computed from `evaluation/golden_set_reviewed.csv` (no fabricated numbers):
- Rows with a recorded human final decision: **200**.
- Intent agreement (draft vs. human final): **0.9500** (10 changed).
- Escalation agreement (draft vs. human final): **0.9550** (9 changed).

The canonical golden set now carries those final decisions (`analysis/scripts/finalize_golden_set.py`). The pre-review assistant draft is preserved in `evaluation/_labels.tsv`, `evaluation/golden_set_review_queue.csv`, `evaluation/golden_set_recommendations.csv` and `golden_set_recommendations.pre_human_review_backup.csv`.
- LLM-as-judge agreement with humans: the recorded `human_final_*` values are label decisions, not response-quality ratings, so judge↔human response agreement is **not computable** (nothing fabricated).
- Judge outputs here are from the **offline deterministic fallback**. A live LLM judge runs only with `OPENAI_API_KEY` + `EVAL_JUDGE=openai`; no live output is ever simulated.
- Read the mandatory section: *"What is misleading about my headline number?"* in the project README.


## H. Reproduce

```
python -m evaluation.run_eval --judge offline
```
