# Data Split & Leakage-Control Plan — British_Airways Phase 2

Controls are enforced by `analysis/scripts/validate_golden_set.py` (exit-code
validator) and by the artifact `evaluation/golden_split_ids.csv`.

## 1. The golden set is a single, reserved Eval split

All 200 examples live in one reserved split with `data_split = "golden_eval"`.
`evaluation/golden_split_ids.csv` lists the 200 `conv_id`s; **Phase-3 tooling
must never index those conversations** — they are the held-out evaluation
resource and are excluded from any retrieval index, RAG corpus, or model
fine-tuning set. This is the "golden conversations never enter the index"
rule from `analysis/brand_analysis.md` §15 made file-manifest.

| check | state |
|---|---|
| one conversation = one example | enforced (conv_id unique, n=200) |
| golden conversations reserved for eval only | `golden_split_ids.csv` + `data_split` column |
| excluded from retrieval index | Phase-3 requirement flowing from this manifest |
| excluded from the Phase-1 audit pool reuse | the 50 audit conversations are NOT in the golden set (validator checks overlap = 0 against `analysis/candidate_conversations/British_Airways.md`) |

## 2. Future train/dev/test (Phase 3)

The 200-example golden set is too small to be split into train/dev/test for
supervised fine-tuning; it is the *evaluation* set. Phase 3 fine-tuning data
should be selected from the **remaining 16,162 BA conversations** (16,452 pool
− 200 golden − 50 audit-manifest) under these rules:

- **Stratification mirrors the golden label distribution** and uses the same
  10-label taxonomy (labels are agnostic to future splits).
- **Time ordering.** The dataset is a 2017 snapshot; if temporal generalisation
  matters, place earliest conversations in train and hold out a later window,
  but do not share a conversation across splits.
- **Conversation-level disjointness.** Split boundaries cut at `conv_id`; no
  tweet of a train conversation may appear in dev/test and vice-versa
  (enforced by the same union-find reconstructed conversations used in Phase 1).

## 3. Input-constructed leakage controls (already applied to golden examples)

- `includes_future_context = False` on every row: `prior_context` contains only
  turns strictly before the target tweet's timestamp (ordered set), and the
  historical `reference_brand_reply` is stored in a separate reference column,
  never in `prior_context`.
- Labels and escalation routing were decided from the **customer message +
  preceding context**, with the brand reply deliberately not read for intent
  decisions (documented in `taxonomy_analysis.md` §4).
- Near-duplicate mitigation: `_candidates_worksheet.csv` keeps
  `bucket_hits` + `is_conflict` so multi-rule conversations are visible; exact
  and normalized-message deduplication is part of the worksheet build
  (`build_golden_worksheet.py`), preventing the same customer utterance being
  sampled twice.

## 4. Reproducibility

- Sampling: `analysis/scripts/build_golden_worksheet.py`, `seed=2026`, tuned
  quotas, eligible pool = 16,402 (16,452 minus 50 audit manifests). Output
  `analysis/golden_sampling_summary.json` fixes the pool and quotas.
- Labels: `evaluation/_labels.tsv` (assistant-drafted, awaiting human review;
  one row per `example_id`).
- Assembly: `analysis/scripts/assemble_golden_set.py` (deterministic merge,
  enum validation) → `golden_set.csv|jsonl`.
- Validation: `analysis/scripts/validate_golden_set.py` — self-contained,
  re-runnable, exit 0 on clean.