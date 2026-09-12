"""Generate analysis/brand_analysis.md — the human-readable phase-1 report.

All tables are pulled from the evidence artifacts (CSV/JSON produced by
inspect/analyze scripts). Narrative sections are static text that cite those
numbers. Run everything before this step so artifacts exist.
"""
import json
import os

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A = os.path.join(BASE, "analysis")


def load(name):
    return pd.read_csv(os.path.join(A, name))


SCHEMA = json.load(open(os.path.join(A, "schema_report.json"), encoding="utf-8"))
BS = load("brand_statistics.csv")
CQ = load("conversation_quality.csv")
DQ = load("data_quality.csv")
RD = load("response_diversity.csv")
DMB = load("dm_behavior.csv")
RES = load("resolution_diversity.csv") if os.path.exists(os.path.join(A, "resolution_diversity.csv")) else None
SC = load("brand_scorecard.csv")

RDC = json.load(open(os.path.join(A, "resolution_diversity_by_cluster.json"), encoding="utf-8"))
RDC = {r["brand"]: r for r in RDC}

top = SC.sort_values("total", ascending=False).head(8)["brand"].tolist()


def md(df, **kw):
    return df.to_markdown(index=False, **kw) if 'to_markdown' in dir(df) else df.to_string(index=False)


def section(title):
    return f"\n## {title}\n"


def main():
    L = []
    L.append("# Customer Support on Twitter — Dataset Forensics & Brand Selection\n")
    L.append("Phase-1 evidence report. All numbers are computed from "
            "`twcs/twcs.csv` via the scripts in `analysis/scripts/`. "
            "No metric is estimated by an LLM; where a value is a heuristic it is labelled.\n")

    L.append(section("1. Dataset schema (facts)"))
    L.append(md(pd.DataFrame([
        {"metric": "file size (uncompressed)", "value": f"{SCHEMA['file_size_bytes']/1e6:.1f} MB"},
        {"metric": "rows", "value": f"{SCHEMA['total_rows']:,}"},
        {"metric": "columns", "value": str(len(SCHEMA["columns"]))},
        {"metric": "exact duplicate rows", "value": SCHEMA["exact_dup_rows"]},
        {"metric": "rows whose tweet_id repeats", "value": SCHEMA["dup_tweet_id_rows"]},
        {"metric": "tweet_id unique", "value": "yes (2,811,774 distinct)"},
        {"metric": "created_at (PARSED, true range)", "value": f"{SCHEMA['created_at_min']} -> {SCHEMA['created_at_max']}"},
        {"metric": "note on 2016 date-range claim", "value": SCHEMA["note"]},
    ])))
    L.append("\nColumns (as read by DuckDB `read_csv_auto`):\n")
    L.append(md(pd.DataFrame(SCHEMA["columns"])))
    L.append("""
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
""")

    L.append(section("2. Brand identification (method)"))
    L.append("""
**Defensible method — no assumption that 'every non-inbound author is a brand'.**
A *support account* is an author that posts outbound (`inbound=False`) tweets that *directly reply to a
customer tweet* (i.e. the outbound row's `in_response_to_tweet_id` resolves to an existing inbound tweet).
Customers are the authors on the other side of those links. Threshold: ≥100 such responses.
Result: **101 support-account candidates**; full ranked table in `brand_statistics.csv`.
""")

    L.append(section("3. Ranked brands/support accounts (top 25 by responses-to-customers)"))
    L.append(md(BS[["brand", "total_tweets", "inbound_tweets", "outbound_tweets",
                    "tweets_responding_to_customer_tweets", "unique_customers_interacted_with"]].head(25),
                floatfmt=",.0f"))

    L.append(section("4. Conversation reconstruction (method)"))
    L.append("""
Conversations = connected components of the tweet-reply graph. Edges are added from **both** link fields:
`in_response_to_tweet_id` (parent) and every numeric member of `response_tweet_id`
(including comma-separated chain values). Missing parents are handled gracefully: they contribute no turn.

Results: **798,197 connected components** from 4,027,154 resolved edges.
Per-brand conversation stats in `conversation_quality.csv`. Because a component may (rarely) contain two
brand accounts, per-brand stats count each component under every brand it contains.
""")

    L.append(section("5. Conversation quality (candidate brands)"))
    L.append(md(CQ[CQ.brand.isin(top)][["brand", "n_conversations", "median_conversation_length",
                                        "mean_conversation_length", "pct_ge2_brand_responses",
                                        "pct_ge3_brand_responses", "unique_customers",
                                        "avg_customer_messages_per_conv", "avg_brand_messages_per_conv"]]))

    L.append(section("6. Data quality / noise (candidate brands)"))
    L.append("""
No empty texts, near-zero extremely-short or URL-only messages across all candidates.
Relevant noise types found by inspection of sampled threads:
- **cross-language/noise** (mainly AmazonHelp: ~8% of first customer messages are non-Latin),
- **non-support content** (praise, promos, jokes, feature requests — present in every Twitter brand),
- **brand-initiated (marketing) tweets** inside reply components (e.g. British_Airways #AFairTaxOnFlying),
- **fragmented brand identity** (AmazonHelp + numeric partner handles as separate authors),
- **referrals to other support accounts** (VirginTrains → @120576 etc.).
Numbers in `data_quality.csv`.
""")

    L.append(section("7. Response (template) diversity (candidate brands)"))
    L.append("""
Normalized templates: URLs→`{URL}`, mentions→`@USER`, numbers→`{NUM}`, lowercased, whitespace collapsed.
High uniqueness = individualized historical replies; low uniqueness = canned funnels.
""")
    L.append(md(RD[RD.brand.isin(top)][["brand", "n_brand_outbound_tweets", "unique_ratio_normalized",
                                        "top10_template_share", "top20_template_share"]]))

    L.append(section("8. Customer-problem diversity (TF-IDF clustering)"))
    L.append("""
Deterministic sample (seed 42, ≤20k first customer messages per brand), TF-IDF (1-2 grams) + KMeans(6).
Full cluster summaries in `customer_diversity.json`. Representative recurring problem areas:
""")
    CUST = {
        "British_Airways": ["online check-in/web errors", "flight delay/cancellation & refunds",
                            "booking changes & seat policy", "baggage / lost luggage", "customer-service complaints"],
        "Tesco": ["product quality (rotten/faulty)", "delivery & click&collect", "refunds & pricing",
                  "store/staff complaints", "website/slots & product-specific queries"],
        "Delta": ["flight change/rebooking", "baggage handling", "meal/seat requests", "app issues",
                  "sky club & praise feedback"],
        "AmericanAir": ["delays/cancellations", "rebooking & refunds", "seat & baggage fees",
                        "customer-service complaints", "praise/thanks"],
        "AmazonHelp": ["delivery/tracking", "refund claims", "account access/hacked", "order issues",
                       "prime/billing", "non-Latin & promo noise"],
        "VirginTrains": ["train cancellations/delays", "refunds", "seat reservations", "onboard issues (heat/wifi)",
                         "cross-operator referrals"],
        "XboxSupport": ["game-specific bugs (CoD WW2, etc.)", "hardware (controller)", "store purchase/errors",
                        "Xbox Live sign-in/gold", "preorders/refunds"],
        "SpotifyCares": ["premium billing/upgrades", "account access", "playback bugs",
                         "missing songs/availability", "feature requests & feedback"],
    }
    for b in top:
        L.append(f"- **{b}**: " + ", ".join(CUST.get(b, [])) + "\n")

    L.append(section("9. Resolution diversity (problem → resolution)"))
    L.append("""
For each conversation with ≥1 customer message and ≥1 brand response, problem = first customer message,
resolution = last brand response. Brand responses are classified by a heuristic action-type regex.
`mean_Bhatt` = mean pairwise Bhattacharyya distance of resolution-type distributions across problem
clusters (higher = problems handled differently; heuristic, labelled).
""")
    L.append("| brand | n pairs | mean_Bhatt | unique last-resp ratio | DM_INFO share of last resp |")
    L.append("|---|---|---|---|---|")
    for b in top:
        rr = RES[RES.brand == b].iloc[0] if RES is not None else None
        rdc = RDC.get(b, {})
        bhatt = rdc.get("mean_pairwise_bhattacharyya_between_problem_clusters")
        bhatt = round(bhatt, 4) if bhatt is not None else "n/a"
        L.append(f"| {b} | {rdc.get('n_problem_response_pairs', 'n/a'):,} | {bhatt} | "
                 f"{rr['unique_ratio_of_last_responses(normalized)'] if rr is not None else 'n/a'} | "
                 f"{rr['share_last_responses_of_type_DM_INFO'] if rr is not None else 'n/a'} |")
    L.append("""
Interpretation: BA/AA/Delta/Tesco respond **individually** (unique-ratio ≥0.91) and mostly in public;
Uber/T-Mobile resolve almost everything via a DM funnel (Bhatt ≈ 0.00–0.006). High unique-ratio must be
interpreted carefully: it indicates individualized replies, not automatically better support.
""")

    L.append(section("10. DM / private-channel behavior"))
    L.append(md(DMB[DMB.brand.isin(top)][["brand", "n_brand_messages",
                                          "share_brand_msgs_dm_or_private"]]))
    L.append("""
A high DM share is a *design consideration*, not a quality verdict: Uber/T-Mobile defensibly go private for
PII. For a RAG-grounded agent it reduces *publicly observable* resolution evidence.
""")

    L.append(section("11. Sampled complete conversations"))
    L.append("""
`analysis/candidate_conversations/BRAND.md` — deterministic stratified samples (seed 137, ~50 complete
threads/brand) spanning short/medium/long threads and problem clusters. Inspected manually for this report.
""")

    L.append(section("12. Brand-selection scorecard"))
    L.append("Scale: 1=poor 2=weak 3=adequate 4=strong 5=excellent. Every score's raw evidence and reason "
             "are in `analysis/scorecard_evidence.json`.\n")
    L.append(md(SC[["brand", "A_volume", "B_richness", "C_problem", "D_resolution", "E_grounding",
                    "F_escalation", "G_noise", "H_eval", "I_repro", "total"]]))

    L.append(section("13. Recommendation"))
    L.append("""
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
""")

    L.append(section("14. Challenging the recommendation"))
    L.append("""
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
""")

    L.append(section("15. Data leakage — how splits must work later"))
    L.append("""
The final pipeline must split at **conversation level**: a `conversation_id` (the reconstructed
component) can appear in exactly one of TRAIN / DEV / TEST / GOLDEN.
- Splitting individual tweets independently leaks: a reply and its parent land in different sets, so the
  model has effectively seen the customer message (or the brand's own draft) before evaluation → inflated,
  indefensible metrics.
- Conversations sharing a **customer** (the same person tweeting on different days) are a minor additional
  leakage: we recommend holding out full customers from TRAIN when feasible (deterministic, seeded) so the
  test measures behaviour on *unseen people*, matching the live product setting.
- `created_at` guarantees nothing by itself; conversation-level `conv_id` is the required unit.
""")

    L.append(section("16. Reproducibility"))
    L.append("""
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
""")

    md_text = "\n".join(L)
    with open(os.path.join(A, "brand_analysis.md"), "w", encoding="utf-8") as f:
        f.write(md_text)
    print(f"Wrote analysis/brand_analysis.md ({len(md_text):,} chars)")


if __name__ == "__main__":
    main()