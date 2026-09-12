# British_Airways Support-Agent — Hiver SDE Intern Take-Home

An evaluation-first answer to: **can a small, reproducible system classify a
customer's intent, draft a historically-grounded reply, and decide when a human
must take over — and what do the numbers honestly say?**

Everything below is generated from artifacts in this repository that you can
re-derive with one command. No number is estimated from imagination; the
runtime, metrics, and leakage checks are all **measured** on the shipped state
of this repo.

---

## 1. Problem framing

British Airways' public Twitter support receives any mix of: factual questions,
booking/account actions, complaints, and noise. The system must:

1. classify intent (one of 10 labels),
2. retrieve the most useful **historical BA interactions** and their brand replies,
3. draft a reply that is grounded in that evidence and never invents policy,
4. decide **AUTO_HANDLE vs ESCALATE vs UNCERTAIN** independently of intent,
5. be evaluated so an evaluator can question **every** headline number.

## 2. Non-goals

* Not a chat assistant; no session memory, no free-form dialogue.
* No live booking/account integrations (it must *route*, never transact).
* Not claimed to mirror current 2026 BA policy — the corpus is the **2017
  Twcs archive**; it is *historical evidence* only.
* No production deployment decisions (SLA, team routing, warm transfer).
* No claim that assistant-drafted labels equal verified ground truth.

## 3. Dataset and sampling

* Source: *Customer Support on Twitter* (Twcs) dataset. Place it at
  `data_extracted/twcs/twcs.csv` (the conversation cache is rebuilt from it;
  see [Reproduce](#reproduce)).
* Brand: **British_Airways** (Phase-1 scorecard: `analysis/brand_analysis.md`),
  chosen for its many-sided support threads and inspectable size.
* Conversations reconstructed by the existing, validated Twitter reply-link
  semantics (`analysis/scripts/reconstruct_conversations.py`).
* Golden set: **200 examples**, 10 intents, escalation labels + reasoning,
  sampling seed 2026, validator-clean. **Currently assistant-drafted and NOT
  human-verified** — see §9 and [Human verification](#human-verification).

## 4. Intent taxonomy (canonical)

| intent | golden n |
|---|---:|
| `non_support_or_acknowledgement` | 43 |
| `complaint_or_human_assistance` | 29 |
| `flight_disruption` | 27 |
| `refund_or_compensation` | 22 |
| `website_or_app_issue` | 21 |
| `information_or_policy` | 20 |
| `baggage` | 16 |
| `booking_change_or_cancellation` | 12 |
| `seat_or_upgrade` | 7 |
| `account_access_or_security` | 3 |

Boundary rules: complaint ≠ contact-channel query (`information_or_policy`);
pure venting/praise/ack → `non_support_or_acknowledgement`; account covers
access **and** security. Escalation is decided separately (§5). The three
names adopted from `PHASE2_1_LABEL_AUDIT.md` are canonical; the golden CSV keeps
legacy spellings, mapped at eval time (`ba_support/taxonomy.py`).

## 5. System architecture

```
customer message
  └→ intent classifier        (hybrid: rules-when-unambiguous, else TF-IDF+LR)
  └→ historical retrieval     (TF-IDF cosine over leakage-excluded corpus)
  └→ escalation policy        (intent-independent; security + evidence gates)
  └→ grounded generation      (evidence-extracted auto answers / routing-only)
  └→ judge                    (offline rubric by default; live LLM opt-in)
```

Leakage controls: the corpus excludes golden+audit conversations **and** any
conversation whose customer appears in the golden set (customer-level
separation); retrieval also excludes the query's own conversation, the query
customer, and near-duplicates. `run_eval` asserts zero evidence leakage.

## 6. Evaluation

All on the 200-example golden set (offline judge, k=3). Baselines and ablations:

**Intent classification (machine-evaluated):**

| system | accuracy | macro F1 | weighted F1 |
|---|---:|---:|---:|
| majority baseline | 0.145 | 0.025 | 0.037 |
| keyword/rule baseline | 0.430 | 0.439 | 0.442 |
| TF-IDF + logistic regression | 0.550 | 0.489 | 0.545 |
| **hybrid main** | **0.545** | **0.511** | **0.546** |

Per-class F1 (hybrid): baggage **0.81**, disruption **0.79**, non-support
0.61, website 0.59, seat 0.56, complaint 0.44, info 0.41, refund 0.40, account
0.36, booking-change 0.14. Tiny classes carry tiny evidence — read macro-F1
with §9.

**Retrieval (machine-evaluated):** hit-rate@3 **1.0**, mean top-1 sim 0.25,
**R@3 intent-consistency 1.0**, evidence-vs-reference word overlap 0.16
(coarse overlap, not semantic quality — see §9).

**Ablations (offline judge, 200 examples):**

| config | groundedness | completeness | overall |
|---|---:|---:|---:|
| A — classifier only | 3.00 | 3.58 | 1.78 |
| B — + retrieval (generation ignores evidence) | 3.33 | 3.58 | 1.64 |
| C — + grounded generation | 3.61 | 4.13 | 2.06 |
| D — full + escalation policy | **4.05** | **3.96** | **2.18** |

Grounding improves monotonically as each capability is added; retrieval alone
(B) does **not** raise quality — evidence must be *used* to matter. Reported
as-is.

**Escalation (full pipeline):** accuracy 0.63; **false-AUTO_HANDLE rate
0.275** (55 of 200) and false-ESCALATE rate 0.09 (18). 0.72 escalation-
appropriateness per the offline judge. The 27.5% false-auto is the single most
important honesty finding of this submission (§8).

## 7. Headline results

Every number is attributed to its source; nothing is manufactured.

| result | value | measured by |
|---|---:|---|
| hybrid intent macro F1 | **0.511** | machine, on assistant-drafted gold |
| hybrid intent accuracy | **0.545** | machine, on assistant-drafted gold |
| full-pipeline overall | **2.18 / 5** | offline rubric judge (backend=offline) |
| full-pipeline groundedness | **4.05 / 5** | offline rubric judge |
| hallucination rate (transactional facts) | **0.00** | offline rubric judge |
| escalation-appropriate | **0.72** | offline rubric judge |
| eval runtime | **39.0 s** | measured wall-clock on this machine (per run) |

**LLM-as-judge:** infrastructure exists and requires `OPENAI_API_KEY` (run with
`--judge openai`; the backend is a CLI flag, not an env var); live outputs are
never simulated. The shipped results use
the offline judge (labelled `backend=offline` in `results.json`).

**Human review:** recorded for **200/200** recommendations
(`evaluation/golden_set_recommendations.csv` → `apply_human_review.py` →
`evaluation/golden_set_reviewed.csv`). Draft-vs-human agreement: intent
**0.95**, escalation **0.955** (real numbers, no fabrication). These are the
candidate's recorded decisions on the *recommended* labels — a single reviewer,
so no inter-annotator agreement (Cohen's kappa) is claimed. LLM/human
*response-quality* agreement is still "**not measurable**": `human_final_*`
are label decisions, not response-ratings (see §9 and
`evaluation/HUMAN_REVIEW_GUIDE.md`).

## 8. Top 5 failures

`analysis/TOP_5_FAILURES.md` (also logged in `results.json → failure_top5_ids`).
The dominant failure family is **intent-boundary confusion producing unsafe
auto-handling** (complaints and legal-adjacent venting routed to a
safe-by-default intent). Cases (current run): `BA_105364`, `BA_294773`,
`BA_32854`, `BA_358073`, `BA_334633`. Each entry lists the customer message,
prior context, gold vs predicted labels, generated reply, retrieved evidence,
judge verdict, root cause and proposed fix. (BA_351856, the previous #4
lawsuit auto-handled case, is fixed: legal/security markers now run before
intent branches.)

## 9. What is misleading about my headline number?

Read this before quoting any number above.

* **The gold labels are assistant-drafted; human review touches the
  recommendations, not the gold mix.** Every metric is correct *given the golden
  set's labels*, which are machine-validated assistant drafts. The recorded human
  review (200/200 rows) re-decides the *recommended* labels: intent agreement
  0.95, escalation agreement 0.955. The golden set itself was deliberately left
  untouched. If the reviewer had changed gold labels, the headline numbers would
  shift — that decision is still open.
* **200 examples is tiny.** Intent macro-F1 (0.51) has wide error bars; per-class
  numbers on 3–12 samples (`account_access_or_security` n=3,
  `booking_change_or_cancellation` n=12) are not statistically meaningful.
* **Class imbalance.** `non_support_or_acknowledgement` (43) dominates; the
  majority baseline only reaches 0.145 accuracy because the *golden* mix differs
  from the corpus prior — so even the trivial baseline is entangled with
  sampling.
* **Weak supervision, not human labels.** Training uses 11,987 keyword-priored,
  weakly-labelled rows. The model inherits the priors' blind spots (e.g.
  complaint-vs-info confusion) — visible in the top failures.
* **2017 archive, not current policy.** Historical BA replies are evidence, not
  ground truth. The generator's policy answers are only as current as the
  archive.
* **Offline judge is a proxy.** Scores reflect a deterministic rubric
  (intent match, evidence usage, PII/marker checks), not a human, and not a
  frontier LLM. A live LLM judge would give different (probably higher, less
  reproducible) numbers.
* **Retrieval metrics overstate usefulness.** R@3 intent-consistency 1.0 only
  means *some* same-intent example was retrieved within 3; mean top-1 similarity
  0.25 and reference-overlap 0.16 show semantic relevance is modest.
* **A single aggregate (overall 2.18) hides the real risk.** The system's
  bottleneck is escalation safety (28% false-auto), not raw answer quality.
  Quoting only "overall" would mislead.
* **Test-set construction effects.** The golden set was stratified by design
  (main vs borderline slices); the borderline slice behaves worse
  (false-auto 0.31 vs 0.27) and any equal-weight average mixes two different
  difficulties.
* **Runtime is this machine's runtime.** 39.0 s was measured here (per run; a
  prior run measured 34.8 s) with cached corpus/models; a cold run from the raw
  CSV takes longer (still under the 15-minute budget on a normal dev box).

## 10. One-week next steps

1. **Finalize the human review.** The 200/200 recommendation decisions are
   recorded (`golden_set_reviewed.csv`); the last personal sign-off on those
   decisions and on whether the *gold* set should adopt any changed label
   remains, plus a second independent annotator if IAA is wanted
   (`--annotator2`).
2. **Safety markers above intent routing** — done in `escalation.py`, with
   regression tests for legal/money/security sentences.
3. Add complaint-vs-info boundary rules and more `seat_or_upgrade` /
   `account_access_or_security` review candidates (currently the thinnest
   classes).
4. Swap the offline judge for a live LLM judge with a fixed rubric and audit
   judge-human agreement once human response-quality ratings exist.
5. Embedding retrieval (SBERT is wired but optional) and a real human-relevance
   evaluation for retrieval.
6. Track confidence → escalate threshold selection on the borderline slice.

---

## Files to inspect

* `evaluation/EVALUATION_REPORT.md` — the human-readable evaluation report.
* `evaluation/results.json` — full machine-readable results (per-class, confusion
  matrices, per-example judgements, leakage, timings).
* `evaluation/predictions.csv` — 200 rows of (input, gold, prediction, reply,
  evidence, judge).
* `analysis/TOP_5_FAILURES.md`, `analysis/DECISION_LOG.md`,
  `analysis/IMPLEMENTATION_AUDIT.md`, `analysis/DATA_CONTRACT.md`.
* `ba_support/` — the implementation; `evaluation/run_eval.py` — the harness.
* `evaluation/golden_set_recommendations.csv`,
  `evaluation/golden_set_review_queue.csv`, `evaluation/HUMAN_REVIEW_GUIDE.md`.

## Reproduce

```bash
# 1) environment
python -m venv .venv && ./.venv/Scripts/activate
pip install -r requirements.txt

# 2) dataset (download Twcs: https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter)
#    place the CSV at  data_extracted/twcs/twcs.csv

# 3) full evaluation (headline) — measured ~33 s with caches on this machine
python -X utf8 -m evaluation.run_eval --judge offline

# 4) optional live LLM judge (backend chosen by --judge; only OPENAI_API_KEY is read from env)
python -X utf8 -m evaluation.run_eval --judge openai   # requires OPENAI_API_KEY set

# 5) tests (stdlib unittest)
python -X utf8 -m unittest discover -s tests -v
```

Outputs: `evaluation/results.json`, `evaluation/EVALUATION_REPORT.md`,
`evaluation/predictions.csv`, `analysis/TOP_5_FAILURES.md`, plus the review
artifacts. Rebuilding from scratch (delete `analysis/cache/retrieval_corpus.parquet`,
then `--force`) stays inside the 15-minute budget; the headline run measured
**39.0 s** (prior run 34.8 s).

## Human verification

Status: **recorded (single reviewer, the candidate); final personal sign-off
pending.** The 200 recommendation decisions have been applied:
`human_decision_accept` / `human_final_intent` / `human_final_escalation` /
`human_notes` are filled in `evaluation/golden_set_recommendations.csv`, and

```bash
python -X utf8 analysis/scripts/apply_human_review.py
```

wrote `evaluation/golden_set_reviewed.csv` (intent agreement 0.95, escalation
agreement 0.955 vs. the assistant draft). A second independent reviewer, if one
is added, produces inter-annotator agreement:

```bash
python -X utf8 analysis/scripts/apply_human_review.py --annotator2 <second_reviewer.csv>
```

The golden set itself is untouched and its labels remain
`ASSISTANT-RECOMMENDED / AWAITING HUMAN CONFIRMATION`.