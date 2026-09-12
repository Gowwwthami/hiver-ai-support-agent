# Golden Evaluation Set — British_Airways (Phase 2)

Annotated, deterministic, leakage-controlled golden set for Phase-3 evaluation
of a customer-support assistant on the **British Airways** 2017 support
conversations (dataset: `thoughtvector/customer-support-on-twitter`, twcs).

**Canonical file:** `evaluation/golden_set.csv` (200 rows). Same data is also
shipped as `golden_set.jsonl`.

## Files

| file | content |
|---|---|
| `golden_set.csv` | 200 examples, one per conversation, all label + context columns |
| `golden_set.jsonl` | identical records, JSON-lines |
| `golden_split_ids.csv` | manifest of reserved `conv_id`s (`data_split=golden_eval`) — the leakage-control artifact |
| `intent_taxonomy.csv` | `analysis/intent_taxonomy.csv` — the 10-label intent taxonomy: definitions, deciding rules, per-label counts |
| `escalation_taxonomy.csv` | `analysis/escalation_taxonomy.csv` — escalation label/reason taxonomy with routing guidance |
| `taxonomy_analysis.md` | `analysis/taxonomy_analysis.md` — derivation, label conventions, distribution, sampling-vs-label drift, label-production procedure, limitations |
| `data_split_plan.md` | `analysis/data_split_plan.md` — split policy, leakage controls, Phase-3 train/dev/test plan |
| `PHASE2_REPORT.md` | `analysis/PHASE2_REPORT.md` — full phase deliverable report |
| `scripts/_taxonomy.py` | `analysis/scripts/_taxonomy.py` — single source of truth for label enums |
| `scripts/assemble_golden_set.py` | `analysis/scripts/assemble_golden_set.py` — worksheet + labels → golden_set (with enum/integrity gates) |
| `scripts/validate_golden_set.py` | `analysis/scripts/validate_golden_set.py` — re-runnable exit-code validator (files + cache + audit-overlap) |
| `_candidates_worksheet.csv` | raw sampled worksheet (label columns blank; input artifact) |
| `_labels.tsv` | drafted labels (assistant-drafted, awaiting independent human review), one row per `example_id` (TSV, 11 columns) |
| `golden_set_review_queue.csv` | **Phase 2.1** human-review queue: 200 rows × 17 cols (`current_*`, `proposed_*`, priority; `human_final_*` blank) |
| `HUMAN_REVIEW_GUIDE.md` | **Phase 2.1** reviewer instructions (intent → escalation → ambiguity; never use the historical reply as proof) |

## Schema (golden_set.csv)

**Identity / provenance**
- `example_id` (BA_<conv_id>), `conv_id`, `target_tweet_id`, `target_author_id`,
  `target_created_ts`, `data_split` (`golden_eval`), `sample_source`,
  `includes_future_context` (always False), `leakage_safe` (always True).

**Inputs (what the assistant would be given)**
- `customer_message` — the target inbound customer tweet.
- `prior_context` — earlier turns of the same conversation, strictly before the
  target tweet (never contains a later brand reply).

**Labels (decided on the customer side; see taxonomy_analysis.md §4)**
- `intent` — one of 10 (`intent_taxonomy.csv`).
- `intent_confidence` — high/medium/low.
- `secondary_intent` — another of the 10, or empty.
- `resolution_observable` — RESOLVED_IN_THREAD / HANDOFF_OUTCOME_OFF_THREAD /
  INFORMATION_PROVIDED / APOLOGY_ONLY / UNRESOLVED / UNCLEAR.
- `resolution_type` — direct_answer / action_offered / link_or_reference /
  empathy_only / status_update / none.
- `escalation_label` — AUTO_HANDLE / ESCALATE / UNCERTAIN.
- `escalation_reason` — from `escalation_taxonomy.csv`, empty iff AUTO_HANDLE.
- `noise_flag` — TRUE/FALSE.
- `ambiguity_flag` — none / multi_intent / unclear_intent / truncated_captured /
  template_or_bot / multilingual / other.
- `annotator_notes` — free-text rationale.

**Sampling provenance (prior, NOT label)**
- `sampling_bucket_primary` (auto-rule/oracle category used to stratify),
  `bucket_hits`-equivalent info lives in the worksheet, `is_conflict`,
  `sample_slice` (`main`/`borderline`), `is_first_inbound`, `target_position`,
  `n_inbound_total`, `conv_tweets_total`, `n_brand_tweets_total`,
  `message_chars`, `message_words`.

**Reference (for resolution reading only)**
- `has_brand_reply_after`, `reference_brand_reply` — the historical brand reply
  to the target turn, kept as gold/reference text. It is **not** part of the
  input context and was not used to decide customer intent.

## Reproduce

```powershell
python analysis\scripts\assemble_golden_set.py   # rebuilt from _candidates_worksheet.csv + _labels.tsv
python analysis\scripts\validate_golden_set.py   # PASS / FAIL, exit code
```

## Headline statistics

- 200 conversations, 200 unique `conv_id`s; 94% of targets are the thread's
  first inbound message; sample slices 171 `main` / 29 `borderline`.
- Intent counts, escalation routing, confidence and ambiguity distributions:
  see `taxonomy_analysis.md` §2.
- Pool used: 16,402 eligible BA conversations of 16,452 total; the 50
  Phase-1 audit conversations are excluded (validator re-checks).

## Limitations (must-read)

- **Labels are assistant-drafted, not human-verified.** No human annotator and
  no second reviewer have reviewed them; **no inter-annotator agreement was
  performed** in this phase and none is reported. Confidence + ambiguity +
  UNCERTAIN routing fields exist so downstream consumers can weight or drop
  uncertain labels; any future IAA claim requires a real (human) second pass.
  See `analysis/taxonomy_analysis.md` §4 for the full honest account.
- `resolution_observable` describes what the **thread** shows, not a real-world
  outcome; most BA resolutions happen off-Twitter (DM / Customer Relations).
- Intent class imbalance is real (noise 43 vs account_or_security 3) and
  mirrors the conversation pool; re-weight rather than over-sample.
- Labels describe the *customer turn*, never company performance.