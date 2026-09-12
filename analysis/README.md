# Phase 1 — Dataset Forensics & Brand Selection (Hiver SDE Intern Assignment)

Goal of this phase: produce trustworthy, defensible evidence to select ONE brand
from the **Customer Support on Twitter** dataset (`thoughtvector/customer-support-on-twitter})
before any modeling begins. **No AI agent / classifier / RAG / golden set was built.**

## Dataset
- Source: `archive.zip → twcs/twcs.csv` (516.5 MB uncompressed), extracted to `data_extracted/twcs/twcs.csv`.
- Rows: 2,811,774. Columns: 7 (`tweet_id`, `author_id`, `inbound`, `created_at`, `text`,
  `response_tweet_id`, `in_response_to_tweet_id`).
- True timestamp range (parsed): **2008-05-08 → 2017-12-03**, with **99.94% of rows in Oct–Dec 2017**
  (an earlier "2016" range in `schema_report.json` was a lexical-string artifact and has been corrected).
- No duplicate rows; `tweet_id` unique.

## Methods (all deterministic; seeds 42 and 137)
1. **Schema** — DuckDB on 1M-row sample; full-scan nulls/uniques (`inspect_dataset.py`).
2. **Link semantics** — empirically verified that `in_response_to_tweet_id` = parent link
   (outbound→customer tweet hits 99.3%) and `response_tweet_id` = response/forward link, sometimes a
   comma-separated thread-chains artifact (`explore_link_semantics.py`, `verify_edges.py`).
3. **Brand identification** — a support account = author with ≥100 outbound tweets whose
   `in_response_to_tweet_id` resolves to an inbound customer tweet. Customers = other side of the edge.
   Result: 101 support accounts (`analyze_brands.py`).
4. **Conversation reconstruction** — union-find connected components over reply edges
   (4,027,154 resolved edges → 798,197 conversations). See Section 15 of `brand_analysis.md` for the
   conversation-level leakage policy that the later TRAIN/DEV/TEST/GOLDEN split must follow.
5. **Per-brand quality / noise / diversity / DM analyses** — scripts referenced below.

## Files produced (all in `analysis/`)
| artifact | content |
|---|---|
| `schema_report.json` | schema facts (see corrected date-range note) |
| `brand_statistics.csv/.json` | ranked support accounts (101) |
| `conversation_quality.csv/.json` | multi-turn richness per brand |
| `data_quality.csv/.json` | noise heuristics per brand |
| `response_diversity.csv/.json` | normalized template diversity per brand |
| `customer_diversity.json` | TF-IDF+KMeans problem clusters + examples |
| `resolution_diversity.csv/.json` | heuristic resolution-action-type distribution |
| `resolution_diversity_by_cluster.json` | problem→resolution differentiation (Bhattacharyya) |
| `dm_behavior.csv/.json` | DM / private-channel pivot rates |
| `candidate_conversations/*.md` | 8 brands × ~50 complete sampled threads |
| `brand_scorecard.csv`, `scorecard_evidence.json` | 9-dimension transparent scorecard (1–5) |
| `brand_analysis.md` | human-readable report incl. recommendation & challenge section |
| `cache/*.parquet` | row-level conversations + summary (reusable by later phases) |

## Reproduce
```powershell
pip install pandas duckdb scikit-learn pyarrow tabulate
$scripts = Get-ChildItem analysis\scripts\inspect_dataset.py, analysis\scripts\analyze_brands.py,
          analysis\scripts\reconstruct_conversations.py, analysis\scripts\analyze_conversation_quality.py,
          analysis\scripts\analyze_data_quality.py, analysis\scripts\analyze_response_diversity.py,
          analysis\scripts\analyze_customer_diversity.py, analysis\scripts\analyze_resolution_and_dm.py,
          analysis\scripts\analyze_resolution_diversity.py, analysis\scripts\sample_candidate_conversations.py,
          analysis\scripts\build_brand_scorecard.py, analysis\scripts\build_report.py
foreach ($s in $scripts) { python -X utf8 $s.FullName }
```
`reconstruct_conversations.py` is the only heavy step (~4.5 min). Everything else runs in seconds–minutes.

## Headline result
- **Recommended: British_Airways** — cleanest top-volume candidate, crisp intent taxonomy, 98.9% unique
  historic responses, 44.3% of conversations ≥2 brand responses, public + escalation resolutions.
- **Runner-up: AmazonHelp** — most data and best problem→resolution differentiation (Bhatt 0.196), but
  penalized by multilingual noise (~8%), fragmented brand handles, and promo/joke content.

Full rationale, scorecard evidence, the anti-recommendation challenge section, and data-leakage policy are
in `brand_analysis.md`.