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
  sampling seed 2026, validator-clean. **Labels are the recorded final human
  decisions** (single reviewer, the candidate — no independent second
  annotator); the pre-review assistant draft is preserved as an archive (see §9
  and [Human verification](#human-verification)).

## 4. Intent taxonomy (canonical)

| intent | golden n |
|---|---:|
| `non_support_or_acknowledgement` | 58 |
| `flight_disruption` | 27 |
| `information_or_policy` | 23 |
| `refund_or_compensation` | 22 |
| `website_or_app_issue` | 21 |
| `baggage` | 16 |
| `booking_change_or_cancellation` | 13 |
| `complaint_or_human_assistance` | 11 |
| `seat_or_upgrade` | 6 |
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

**Intent classification (machine-evaluated, on human-final gold):**

| system | accuracy | macro F1 | weighted F1 |
|---|---:|---:|---:|
| majority baseline | 0.055 | 0.010 | 0.006 |
| keyword/rule baseline | 0.355 | 0.403 | 0.406 |
| TF-IDF + logistic regression | 0.505 | 0.449 | 0.518 |
| **hybrid main** | **0.510** | **0.477** | **0.525** |

Per-class F1 (hybrid): baggage **0.82**, disruption **0.79**, website 0.59,
non-support 0.55, seat 0.47, refund 0.40, info 0.39, account 0.36, complaint
0.26, booking-change 0.13. Tiny classes carry tiny evidence — read macro-F1
with §9.

**Retrieval (machine-evaluated):** hit-rate@3 **1.0**, mean top-1 sim 0.25,
**R@3 intent-consistency 1.0**, evidence-vs-reference word overlap 0.16
(coarse overlap, not semantic quality — see §9).

**Ablations (offline judge, 200 examples):**

| config | groundedness | completeness | overall |
|---|---:|---:|---:|
| A — classifier only | 3.00 | 3.70 | 1.80 |
| B — + retrieval (generation ignores evidence) | 3.33 | 3.55 | 1.66 |
| C — + grounded generation | 3.61 | 4.93 | 2.09 |
| D — full + escalation policy | **4.06** | **4.70** | **2.20** |

Grounding improves monotonically as each capability is added; retrieval alone
(B) does **not** raise quality — evidence must be *used* to matter. Reported
as-is.

**Escalation (full pipeline):** accuracy 0.645; **false-AUTO_HANDLE rate
0.25** (50 of 200) and false-ESCALATE rate 0.10 (20). 0.75 escalation-
appropriateness per the offline judge. The 25% false-auto — concentrated in
booking-change and complaint cases the human review labelled ESCALATE — is the
single most important honesty finding of this submission (§8).

## 7. Headline results

Every number is attributed to its source; nothing is manufactured.

| result | value | measured by |
|---|---:|---|
| hybrid intent macro F1 | **0.477** | machine, on human-final gold |
| hybrid intent accuracy | **0.510** | machine, on human-final gold |
| full-pipeline overall | **2.20 / 5** | offline rubric judge (backend=offline) |
| full-pipeline groundedness | **4.06 / 5** | offline rubric judge |
| hallucination rate (transactional facts) | **0.00** | offline rubric judge |
| escalation-appropriate | **0.75** | offline rubric judge |
| eval runtime | **208 s** (fresh `--force` run); ~40 s cached | measured wall-clock on this machine (per run) |

**LLM-as-judge:** the report's judge is the **offline deterministic rubric**
(backend chosen by `--judge`; a live run needs `OPENAI_API_KEY` +
`EVAL_JUDGE=openai`). Separately, `evaluation/human_validation.py judge
--backend gemini|openai|offline` scores a fixed 50-example sample for
judge↔human agreement; live outputs are never simulated. At submission time the
live runs were **not executed**: no OpenAI key is set, and the Gemini free-tier
quota was exhausted (all real probe calls returned HTTP 429/RESOURCE_EXHAUSTED
and the SDK's auto-retry is deliberately disabled so nothing is retried
silently). The shipped numbers are all backend=offline.

**Human review:** recorded for **200/200** recommendations
(`evaluation/golden_set_recommendations.csv` → `apply_human_review.py` →
`evaluation/golden_set_reviewed.csv`). Draft-vs-human agreement: intent
**0.95** (10 changed), escalation **0.955** (9 changed) — real numbers, no
fabrication; versus the pre-review *gold* the finals changed **20 intent + 21
escalation** labels. The canonical golden set now carries those final
decisions (`analysis/scripts/finalize_golden_set.py`); the pre-review draft is
archived in `evaluation/_labels.tsv` and
`golden_set_recommendations.pre_human_review_backup.csv`. Single reviewer, so
no inter-annotator agreement (Cohen's kappa) is claimed. LLM/human
*response-quality* agreement remains "**not computable**": `human_final_*`
are label decisions, not response-ratings (see §9 and
`evaluation/HUMAN_REVIEW_GUIDE.md`).

## 8. Top 5 failures

`analysis/TOP_5_FAILURES.md` (also logged in `results.json → failure_top5_ids`).
The five worst cases of the final run are `BA_248481`, `BA_255518`, `BA_331684`,
`BA_294773`, `BA_150929` — four of five are booking-change requests that the
human review labelled ESCALATE (account-specific) and the system AUTO_HANDLED,
i.e. **intent-boundary confusion producing unsafe auto-handling**. Each entry
lists the customer message, prior context, gold vs predicted labels, generated
reply, retrieved evidence, judge verdict, root cause and proposed fix.
(`BA_351856`, the lawsuit auto-handled case, is fixed: legal/security markers
now run before intent branches.)

## 9. What is misleading about my headline number?

Read this before quoting any number above.

* **The gold labels are single-human-reviewed, not independently annotated.**
  The 200 golden labels are the candidate's recorded final decisions (200/200
  reviewed; 181 accepted, 19 overridden — 20 intent + 21 escalation gold labels
  differ from the pre-review draft). No second annotator ran, so no
  inter-annotator agreement is reported and the headline numbers are entangled
  with one reviewer's judgement. The assistant-drafted pre-review labels are
  archived (`_labels.tsv`, `golden_set_recommendations.pre_human_review_backup.csv`),
  so every metric can be re-derived against either label set.
* **200 examples is tiny.** Intent macro-F1 (0.477) has wide error bars; per-class
  numbers on 3–13 samples (`account_access_or_security` n=3,
  `booking_change_or_cancellation` n=13) are not statistically meaningful.
* **Class imbalance.** `non_support_or_acknowledgement` (58) dominates; the
  majority baseline only reaches 0.055 accuracy because the *golden* mix differs
  from the corpus prior — so even the trivial baseline is entangled with
  sampling.
* **Weak supervision, not human labels.** Training uses keyword-priored,
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
* **A single aggregate (overall 2.20) hides the real risk.** The system's
  bottleneck is escalation safety (25% false-auto), not raw answer quality.
  Quoting only "overall" would mislead.
* **Test-set construction effects.** The golden set was stratified by design
  (main vs borderline slices); the borderline slice behaves worse
  (false-auto 0.345 vs 0.234) and any equal-weight average mixes two different
  difficulties.
* **Runtime is this machine's runtime.** 208 s was measured for the fresh
  `--force` run (corpus + model rebuild); the cached rerun is ~40 s. A cold run
  from the raw CSV takes longer (still under the 15-minute budget on a normal
  dev box).

## 10. One-week next steps

1. Add a **second independent annotator** and compute **Cohen's kappa / IAA**;
   then decide boundary rules between the complaint, information and
   booking-change intents — the four-of-five top-failure family.
2. Promote **complaint / money-family markers globally** (like legal/security
   already are), or lock in explicit booking-change boundary rules, and add
   regression tests.
3. Expand review candidates for the thinnest classes (`account_access_or_security`
   n=3, `seat_or_upgrade` n=6) to reduce the per-class error bars.
4. Wire a **live LLM judge** (`evaluation/human_validation.py judge
   --backend gemini` or `--backend openai`) on the 50-example sample and
   measure judge↔human response-quality agreement once human response-quality
   ratings exist.
5. Swap TF-IDF cosine for **embedding retrieval** (SBERT is wired but
   optional) and add a real human-relevance retrieval evaluation.
6. Calibrate the **confidence → escalation threshold** on the borderline slice
   (false-auto 34.5% vs 23.4% on main) instead of the current fixed rule.

---

## Files to inspect

* `evaluation/EVALUATION_REPORT.md` — the human-readable evaluation report.
* `evaluation/results.json` — full machine-readable results (per-class, confusion
  matrices, per-example judgements, leakage, timings).
* `evaluation/predictions.csv` — 200 rows of (input, gold, prediction, reply,
  evidence, judge).
* `analysis/TOP_5_FAILURES.md`, `analysis/DECISION_LOG.md`,
  `analysis/IMPLEMENTATION_AUDIT.md`, `analysis/DATA_CONTRACT.md`.
* `analysis/scripts/finalize_golden_set.py` — the idempotent script that
  promoted the recorded human final decisions into the canonical golden set.
* `evaluation/golden_set_reviewed.csv` — the reviewer's own recorded final
  decisions, the audit source of the final gold.
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

# 3) full evaluation (headline) — ~40 s with caches on this machine
python -X utf8 -m evaluation.run_eval --judge offline --force

# 4) optional live LLM judge (backend chosen by --judge; a key must be set)
python -X utf8 -m evaluation.run_eval --judge openai     # OPENAI_API_KEY
python -X utf8 -m evaluation.run_eval --judge gemini     # GEMINI_API_KEY

# 5) 50-example judge-human agreement probe
python -X utf8 -m evaluation.human_validation judge --backend offline|openai|gemini

# 6) tests (stdlib unittest)
python -X utf8 -m unittest discover -s tests -v
```

Outputs: `evaluation/results.json`, `evaluation/EVALUATION_REPORT.md`,
`evaluation/predictions.csv`, `analysis/TOP_5_FAILURES.md`, plus the review
artifacts. Rebuilding from scratch (delete `analysis/cache/retrieval_corpus.parquet`,
then `--force`) stays inside the 15-minute budget; the fresh `--force` run
measured **208 s** (cached reruns ~40 s).

## Human verification

Status: **complete (single reviewer, the candidate); final sign-off applied.**

The 200 recommendation decisions have been applied:
`human_decision_accept` / `human_final_intent` / `human_final_escalation` /
`human_notes` are filled in `evaluation/golden_set_recommendations.csv`, and

```bash
python -X utf8 analysis/scripts/apply_human_review.py
```

wrote `evaluation/golden_set_reviewed.csv` (draft-vs-final intent agreement
0.95, escalation 0.955). The golden set itself was then promoted to carry
those finals by:

```bash
python -X utf8 analysis/scripts/finalize_golden_set.py
```

Draft-vs-gold: 20 intent + 21 escalation labels changed; the pre-review
assistant-drafted gold remains archived in `_labels.tsv` and
`golden_set_recommendations.pre_human_review_backup.csv` for full reproducibility.
Single reviewer, so no independent annotation or inter-annotator agreement is
claimed. A second independent reviewer, if one is added, produces
inter-annotator agreement:

```bash
python -X utf8 analysis/scripts/apply_human_review.py --annotator2 <second_reviewer.csv>
```