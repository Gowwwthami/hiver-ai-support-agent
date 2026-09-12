# Implementation Audit — British_Airways Hiver Take-Home

**Audit date:** 2026-09-11 (performed at the start of the Phase-3 build, and
re-verified after each major step).

Audited primary sources:

* `analysis/PHASE2_REPORT.md`, `analysis/PHASE2_1_LABEL_AUDIT.md`,
  `analysis/brand_analysis.md`, `analysis/README.md`, `analysis/data_split_plan.md`
* `analysis/scripts/*.py` (reconstruction, worksheet, golden assembly, review
  queue, validators)
* `evaluation/golden_set.csv`, `evaluation/golden_set_review_queue.csv`,
  `evaluation/HUMAN_REVIEW_GUIDE.md`, `evaluation/golden_set_README.md`
* `analysis/candidate_examples/*` (seat/upgrade + account populating pools)

## 1. Current state (at audit start)

| item | status | notes |
|---|---|------|
| Phase 1 (brand selection) | **complete** | British_Airways chosen; scorecard + candidate pools exist |
| Phase 2 (golden set) | **complete** | 200 examples, 10 intents, escalation labels, validator passes |
| Phase 2.1 (label audit) | **complete** | audit doc + review queue + recommendations artifacts; **human verification pending** |
| Phase 3 system | **incomplete** | bootstrap.py-style harness did not exist; no README, no tests, no pinned deps |
| Evaluation harness | **incomplete** | became `evaluation/run_eval.py` in this build |

## 2. Completed components (reused as-is)

* `analysis/scripts/reconstruct_conversations.py`
  → `analysis/cache/conversations.parquet` + `conversation_summary.parquet`
  (26,578… see §4) — the conversation backbone.
* `analysis/scripts/_taxonomy.py` — the Phase-2 enum source (legacy names).
* `analysis/scripts/validate_golden_set.py` — golden-set validator (still
  passes; interface unchanged, its canonical-name mapping lives in
  `ba_support.taxonomy.to_canonical`).
* `evaluation/golden_set.csv` — the 200-example golden set (untouched).
* `evaluation/golden_set_review_queue.csv`,
  `evaluation/HUMAN_REVIEW_GUIDE.md`, `evaluation/golden_set_README.md`,
  `evaluation/_candidates_worksheet.csv` — Phase 2.1 review machinery.
* `analysis/scripts/assemble_golden_set.py`, `build_golden_worksheet.py`,
  `build_review_queue.py` — Phase-2 artifact builders (unchanged).

## 3. Files created in the Phase-3 build

| file | purpose |
|---|---|
| `ba_support/taxonomy.py` | canonical label space + legacy→canonical map |
| `ba_support/normalize.py` | text normalisation, redaction, near-dup helpers |
| `ba_support/weak.py` | rule-based weak supervision (training signal, no golden labels) |
| `ba_support/leakage.py` | golden/audit manifests + customer-level isolation |
| `ba_support/corpus.py` | retrieval/training corpus builder (cached parquet) |
| `ba_support/intent.py` | majority / keyword-rule / TF-IDF+LR / hybrid classifiers (save/load) |
| `ba_support/escalation.py` | deterministic routing policy (intent-independent) |
| `ba_support/retrieval.py` | TF-IDF (+optional SBERT) historical-evidence retrieval |
| `ba_support/generate.py` | evidence-grounded draft generation (offline) |
| `ba_support/judge.py` | offline rubric judge + optional live LLM judge |
| `ba_support/evaluate.py` | metric aggregation + result serialisation |
| `ba_support/pipeline.py` | single-example end-to-end predictor + ablation config |
| `ba_support/recommend.py` | golden-set review recommendation artifacts |
| `evaluation/run_eval.py` | the single reproducible evaluation command |
| `analysis/scripts/apply_human_review.py` | applies human finals, draft error + IAA stats |
| `analysis/IMPLEMENTATION_AUDIT.md`, `analysis/DATA_CONTRACT.md`, `analysis/DECISION_LOG.md`, `analysis/TOP_5_FAILURES.md` | documentation deliverables |
| `README.md`, `PROJECT_STATUS.md`, `requirements.txt`, `pyproject.toml`, `.env.example`, `tests/` | packaging/reproducibility deliverables |

## 4. Files modified

| file | change |
|---|---|
| `ba_support/weak.py` | bucket names → canonical; docstring |
| `ba_support/escalation.py` | canonical intent names; evidence-sufficiency gate for factual AUTO intents |
| `ba_support/generate.py` | canonical intent names in openings/noise branch |
| `ba_support/judge.py` | canonical `account_access_or_security` in PII guard |
| `ba_support/retrieval.py` | precomputed token sets for fast per-query near-dup exclusion |
| `ba_support/normalize.py` | added `is_near_duplicate_tokens` |
| `ba_support/pipeline.py` | added `grounded` ablation flag; `mode` in judge sample |
| `ba_support/paths.py` | outputs → `EVALUATION_REPORT.md`, `analysis/TOP_5_FAILURES.md` |
| `ba_support/corpus.py` | `build_corpus(force=True)` support |
| `evaluation/run_eval.py` | full rewrite (see §3 + ablations) |

## 5. Key reuse decisions

* Conversation reconstruction and link semantics: **reused** exactly
  (`reconstruct_conversations.py`), no re-derivation.
* Golden set: **frozen**, never re-sampled; eval maps legacy labels to
  canonical via `taxonomy.to_canonical`.
* Intent definition/boundary rules: **preserved** from Phase-2 taxonomy docs and
  applied as the weak-labelling priors in `weak.py` — the model uses knowledge
  priors, not a re-created taxonomy.
* Taxonomy naming: the three Phase-2.1 renames are adopted as the **canonical
  namespace** of the final system (labels' meanings unchanged); the shipped
  golden-set file keeps legacy names.

## 6. Risks & mitigations

| risk | mitigation |
|---|---|
| Golden labels are assistant-drafted / human-unverified | everything downstream is labelled "proposed"; `human_final_*` blank; agreement infrastructure reports *not measurable* |
| Leakage of golden content into retrieval/training | conv-level + customer-level exclusion at build time; near-dup exclusion at query time; evidence leak asserted == 0 in `run_eval` |
| Classifier trains only on weak labels (noisy) | single-bucket confident rows only (0.451 share); reported honestly; baselines included |
| 2017 archive ≠ current BA policy | generator never states policy as fact beyond retrieved evidence; reader disclosure in README |
| Offline judge is a proxy, not a human | outputs always labelled `backend=offline`; live judge opt-in only |
| Runtime > 15 min | measured at **33 s** for the full 200-example run on this machine |

## 7. Recommended execution order (this build)

1. corpus → `--force` once after taxonomy-name changes 2. models fit/cached
3. intent classification baselines vs hybrid 4. retrieval quality 5. pipeline +
judge 6. ablations A/B/C/D 7. failures 8. review recommendations 9. report +
docs + tests 10. final validation + `PROJECT_STATUS.md`.