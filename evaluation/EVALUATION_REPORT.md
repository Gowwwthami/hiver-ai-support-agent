# British_Airways Support-Agent — Evaluation Report

- Golden set evaluated: **200** (assistant-drafted labels; human review of the draft recommendations is recorded separately — see §G).
- Judge backend: **offline** (offline deterministic unless OPENAI_API_KEY + EVAL_JUDGE=openai).
- Seed: 42; top-k: 3.
- Measured wall-clock runtime of this run: **39.8 s** (measured, not estimated).

## A. Intent classification (golden held-out set)

| system | accuracy | macro F1 | weighted F1 |
|---|---:|---:|---:|
| `majority_baseline` | 0.1450 | 0.0253 | 0.0367 |
| `rule_keyword_baseline` | 0.4300 | 0.4394 | 0.4415 |
| `tfidf_lr_baseline` | 0.5500 | 0.4886 | 0.5448 |
| `hybrid_main` | 0.5450 | 0.5114 | 0.5463 |

Per-class precision/recall/F1 (hybrid main):

| intent | support | precision | recall | F1 |
|---|---:|---:|---:|---:|
| `non_support_or_acknowledgement` | 43 | 0.697 | 0.535 | 0.605 |
| `complaint_or_human_assistance` | 29 | 0.400 | 0.483 | 0.438 |
| `flight_disruption` | 27 | 0.742 | 0.852 | 0.793 |
| `refund_or_compensation` | 22 | 0.538 | 0.318 | 0.400 |
| `website_or_app_issue` | 21 | 0.769 | 0.476 | 0.588 |
| `information_or_policy` | 20 | 0.302 | 0.650 | 0.413 |
| `baggage` | 16 | 1.000 | 0.688 | 0.815 |
| `booking_change_or_cancellation` | 12 | 0.500 | 0.083 | 0.143 |
| `seat_or_upgrade` | 7 | 0.455 | 0.714 | 0.556 |
| `account_access_or_security` | 3 | 0.250 | 0.667 | 0.364 |

Confusion matrix (labels sorted): see `results.json` → `intent_classification.hybrid_main.confusion_matrix`.

## B. Retrieval

| metric | value |
|---|---:|
| records | 200 |
| hit_rate_at_k | 1.0 |
| mean_top1_similarity | 0.2513 |
| mean_topk_similarity | 0.2107 |
| mean_topk_similarity_median | 0.1971 |
| recall_at_k_intent_consistency | 1.0 |
| evidence_word_overlap_with_reference | 0.1645 |

Retrieval sim is TF-IDF cosine; `recall_at_k_intent_consistency` is a coarse coverage proxy against golden intent, not human relevance.

## C. Response quality (full pipeline, judge)

| metric | value |
|---|---:|
| correctness | 3.635 |
| correctness_n | 200 |
| groundedness | 4.055 |
| groundedness_n | 200 |
| completeness | 4.695 |
| completeness_n | 200 |
| overall | 2.185 |
| overall_n | 200 |
| hallucination_rate | 0.0 |
| escalation_appropriate_rate | 0.725 |
| judge_backends_used | {'offline': 200} |

## D. Escalation routing (full pipeline)

| metric | value |
|---|---:|
| accuracy | 0.63 |
| false_auto_handle_rate | 0.275 |
| n_false_auto_handle | 55 |
| false_escalation_rate | 0.09 |
| n_false_escalation | 18 |
| auto_handle_precision | 0.6309 |
| auto_handle_recall | 0.8393 |
| auto_handle_f1 | 0.7203 |
| confusion | {'AUTO_HANDLE': 112, 'ESCALATE': 83, 'UNCERTAIN': 5} |

Unsafe AUTO_HANDLE ids: BA_105364, BA_135900, BA_147482, BA_150929, BA_152445, BA_163041, BA_167696, BA_168706, BA_174566, BA_175984, BA_177915, BA_231852, BA_235380, BA_236326, BA_24151, BA_248481, BA_26002, BA_278441, BA_294773, BA_307083, BA_32854, BA_331684, BA_334633, BA_337964, BA_358073, BA_358078, BA_375254, BA_408652, BA_409290, BA_409640, BA_410230, BA_423824, BA_466171, BA_472183, BA_487360, BA_495495, BA_50753, BA_525809, BA_542898, BA_547282, BA_568345, BA_577348, BA_578442, BA_661009, BA_689051, BA_705493, BA_71387, BA_737110, BA_73767, BA_749232, BA_755281, BA_766761, BA_787976, BA_83067, BA_98911

## E. Ablations (judge)

| config | overall | groundedness | hallucination rate | escalation-appropriate |
|---|---:|---:|---:|---:|
| `A_classifier_only` | 1.78 | 3.00 | 0.00 | 0.72 |
| `B_classifier_retrieval` | 1.64 | 3.33 | 0.00 | 0.72 |
| `C_grounded_generation` | 2.06 | 3.61 | 0.00 | 0.72 |
| `D_full` | 2.19 | 4.05 | 0.00 | 0.72 |

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
- LLM-as-judge agreement with humans: the recorded `human_final_*` values are label decisions, not response-quality ratings, so judge↔human response agreement is **not computable** (nothing fabricated).
- Judge outputs here are from the **offline deterministic fallback**. A live LLM judge runs only with `OPENAI_API_KEY` + `EVAL_JUDGE=openai`; no live output is ever simulated.
- Read the mandatory section: *"What is misleading about my headline number?"* in the project README.


## H. Reproduce

```
python -m evaluation.run_eval --judge offline
```
