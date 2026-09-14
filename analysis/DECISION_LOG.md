# Decision Log — British_Airways Hiver Take-Home

Every entry records: **decision**, **alternatives**, **why chosen**, **evidence**,
**tradeoff**. Entries marked *Phase 1/2* were made earlier in the project and are
kept here for continuity; the rest are current implementation decisions made
during the Phase-3 build.

---

## D1. Brand: British_Airways
- **Decision:** support only British Airways.
- **Alternatives:** AmazonHelp, Delta, VirginTrains, Tesco, and 12 more brands in the scorecard.
- **Why:** BA had the dialogue structure the assignment needs (many-sided support threads, real resolutions, thousands of conversations) while staying small enough to review by hand.
- **Evidence:** `analysis/brand_analysis.md`, `analysis/brand_scorecard.csv`; BA has 16,452 conversations of which a healthy share are two-turn support interactions.
- **Tradeoff:** a single brand means the taxonomy and templates are BA-specific; transfer to other airlines is not demonstrated. *(Phase 1)*

## D2. Taxonomy: 10 mutually-exclusive intents + independent escalation axis
- **Decision:** 10 intents (see `ba_support/taxonomy.py`) with escalation decided separately.
- **Alternatives:** finer grain (20+) vs coarser (5–7); using escalation as a classifier target.
- **Why:** 10 labels match the data's dominant customer objectives and keep per-class support inspectable; keeping escalation **independent** prevents "escalate-anything" from becoming a lazy default label.
- **Evidence:** `analysis/intent_taxonomy.md`; Phase-2 worksheet; audit §1–§5.
- **Tradeoff:** some classes are tiny (account_access_or_security n=3) — macro-F1 must be read with that in mind. *(Phase 2)*

## D3. Canonical taxonomy names (the three Phase-2.1 renames adopted)
- **Decision:** `contact_or_human_escalation_request → complaint_or_human_assistance`, `noise_or_off_topic_or_ack → non_support_or_acknowledgement`, `account_or_security → account_access_or_security` are the **canonical** system labels; the golden file keeps legacy names, mapped at eval time via `taxonomy.to_canonical`.
- **Alternatives:** rewrite the golden CSV in place vs keep legacy forever.
- **Why:** names now encode the boundary rules (complaint ≠ contact-channel query; noise includes pure venting/ack; account covers access AND security) without destroying the shipped artifact or its validator.
- **Evidence:** `PHASE2_1_LABEL_AUDIT.md`; validator still passes; eval sees canonical labels.
- **Tradeoff:** two name-spaces coexist in one repo (legacy CSV + canonical system); the mapping is explicit and machine-checked.

## D4. Evaluation set: keep the existing 200 (regenerate nothing)
- **Decision:** the golden set is the held-out evaluation set, unchanged.
- **Alternatives:** re-sample a new eval set; enlarge or trim it.
- **Why:** the assignment forbids replacing the 200; they were sampled deterministically (seed 2026) and validated.
- **Evidence:** `validate_golden_set.py` PASS; `golden_sampling_summary.json`.
- **Tradeoff:** small n (200) and class imbalance restrict how much we can claim about precision/recall. *(Phase 2/2.1)*

## D5. Training signal: weak supervision only — golden labels never train the model
- **Decision:** the classifier fits only on weak-labelled, leakage-excluded corpus rows; gold labels are eval-only.
- **Alternatives:** (a) train on the 200 gold labels (tiny but fully supervised), (b) pseudo-label the corpus from the classifier.
- **Why:** (§D7) the corpus is 100× the gold set and keeps the eval clean; (a) would make F1 figures reflect 200 noisy samples.
- **Evidence:** `run_eval` overview `train_weak_confident_rows=11,987`; weak-confident share 0.451.
- **Tradeoff:** weak labels carry keyword priors, so the model inherits prior blind spots; reported honestly (rule-baseline is provided so the reader can isolate this).

## D6. Leakage isolation at conversation + customer level
- **Decision:** corpus excludes golden, audit, and any conversation whose customer appears in a golden conversation; near-duplicate exclusion at query time.
- **Alternatives:** tweet-level random splits; conversation-level only.
- **Why:** customers re-contact; a tweet-level split leaks personas/templates across splits. Conversation-level alone still lets a golden customer's *other* conversations leak the ask pattern.
- **Evidence:** `run_eval` leak printouts (0 overlap, 0 customer-overlap rows, evidence leak asserted 0).
- **Tradeoff:** the strongest isolation shrinks the pool (16,092 conversations usable) and removes some legitimately similar pairs.

## D7. Baseline ladder: majority → keyword/rule → TF-IDF+LR → hybrid
- **Decision:** report four systems; the main hybrid is rules-when-unambiguous else TF-IDF+LR.
- **Alternatives:** jump straight to a transformer; skip the rule baseline.
- **Why:** each rung isolates one mechanism (class prior, priors-as-rules, linear document model, rule+model blend), so a reader can see *where* accuracy comes from — the assignment prizes proof over architecture.
- **Evidence:** macro-F1 0.025 → 0.439 → 0.489 → 0.511; accuracy 0.145 → 0.43 → 0.55 → 0.545.
- **Tradeoff:** no neural model; the system is far from SOTA — acceptable given the 200-example eval and the 15-minute reproduction goal.

## D8. Retrieval: TF-IDF cosine with optional SBERT, evidence always exposed
- **Decision:** default encoder = TF-IDF (word, 1–2 gram, sublinear tf, English stopwords); `--semantic` switches to sentence-transformers when installed; every prediction returns its evidence records.
- **Alternatives:** embeddings-first; BM25; dense-only.
- **Why:** zero extra dependencies, deterministic, fast (33 s end-to-end), and inspectable — evaluators can read why a reply was grounded.
- **Evidence:** retrieval R@3 intent-consistency 1.0; mean top-1 sim 0.25; evidence-vs-reference word overlap 0.16 (i.e. recall-by-intent is high, semantic overlap modest — and we say so).
- **Tradeoff:** TF-IDF misses paraphrases that embeddings would catch; flagged in the disclosure section.

## D9. Escalation policy is intent-independent and evidence-gated
- **Decision:** AUTO_HANDLE iff a complete, safe public answer exists without account data/human judgment; ESCALATE with a structured reason otherwise; UNCERTAIN only when undecidable. Intent-routing is overridden by (1) security markers and (2) an evidence-sufficiency gate for factual auto intents.
- **Alternatives:** derive routing from predicted intent alone; mirror BA's historical "DM us" habit.
- **Why:** mirroring the archive would bless BA's automation as truth; intent-only routing would auto-handle $500 refund claims.
- **Evidence:** false-ESCALATE 9%, but false-AUTO 28% — the honest headline risk; failure analysis pins most on classifier intent confusions.
- **Tradeoff:** stricter policy increases false escalations to humans; we accept that bias in favour of safety, and report both numbers.

## D10. Generation: evidence-grounded, offline, never invents policy
- **Decision:** auto-handled factual intents are answered by safe extraction from the top retrieved reply; escalated intents only state the routing action; weak evidence ⇒ clarifying question or escalation. No amounts, eligibility, phone numbers, or account facts are ever asserted.
- **Alternatives:** a generative LLM for drafts; template-only fill-ins.
- **Why:** reproducible offline, and hallucination is structurally impossible for transactional facts (asserted by the offline judge: hallucination-rate 0.0 on 200).
- **Evidence:** judge completeness 4.7 / 5 for the full pipeline; `analysis/TOP_5_FAILURES.md` shows the residual (wrong-intent) cases.
- **Tradeoff:** replies can read stiffer than a human's; a live LLM judge path exists (`EVAL_JUDGE=openai`) but is not required.

## D11. LLM-as-judge: offline rubric judge by default, live judge opt-in only
- **Decision:** default judge is a deterministic rubric (`ba_support/judge.py`) labelled `backend=offline`; live OpenAI judge runs only with `OPENAI_API_KEY` + `EVAL_JUDGE=openai`.
- **Alternatives:** always call the LLM judge; skip judging.
- **Why:** reproducible and free of API cost/noise by default; the live judge exists so the harness is not a dead-end, but its outputs are never simulated.
- **Evidence:** `results.json → judge_backends_used: {"offline": 200}`.
- **Tradeoff:** offline rubric is a coarse proxy; the assignment's human-agreement requirement is acknowledged as *not yet measurable* (no human labels).

## D12. Ablation design A/B/C/D isolates each capability
- **Decision:** A classifier-only → B + retrieval (generation ignores evidence) → C + grounded generation → D + escalation policy.
- **Alternatives:** many single-knob runs; end-to-end only.
- **Why:** the assignment wants proof each component earns its place.
- **Evidence:** groundedness 3.00 → 3.33 → 3.61 → 4.05; overall 1.78 → 1.64 → 2.06 → 2.18. B barely moves overall (retrieval alone ≠ grounded answers) — reported as-is, not manufactured upward.
- **Tradeoff:** ablated runs 4× the pipeline cost (still only ~33 s total).

## D13. Review workflow: assistant recommendations → human finals via a CSV contract
- **Decision:** `golden_set_recommendations.csv` (ASSISTANT-RECOMMENDED / AWAITING HUMAN) is the human input surface; `analysis/scripts/apply_human_review.py` converts human finals into draft-error-rate + inter-annotator agreement.
- **Alternatives:** human reviews directly into golden_set.csv.
- **Why:** the golden file stays pristine; review decisions remain auditable; IAA is computable when a second annotator file is supplied.
- **Evidence:** `human_final fields all blank: True` printed until a human acts.
- **Tradeoff:** an extra file to keep in sync; the human never overwrites an assistant label in place.

## D14. Reproducibility target: <15 minutes, measured not claimed
- **Decision:** a single command re-produces headline results; the corpus and models are cached so re-runs are fast.
- **Alternatives:** require full re-derivation from raw CSV every run.
- **Why:** an evaluator must be able to re-run; but we still measure, not estimate.
- **Evidence:** `results.json → runtime_seconds = 32.8` on this machine (200 examples, offline judge).
- **Tradeoff:** caching means a taxonomy change needs `--force` (documented in README).

## D15. Honesty vs gold: no fabricated human/judge agreement, ever
- **Decision:** any metric requiring human labels (draft-error rate, IAA, judge-human agreement) is reported as "not computable — pending human review" unless real labels exist; `human_final_*` stay blank until filled.
- **Alternatives:** report hypothetical agreement; treat assistant labels as ground truth.
- **Why:** an evaluator will question every headline number; fake agreement destroys the entire submission.
- **Evidence:** `evaluate_judge_agreement_available()` returns `agreement_computable: False`; review script prints `HUMAN REVIEW PENDING`.
- **Tradeoff:** the headline "accuracy" still depends on assistant-drafted gold — disclosed in the README's mandatory section.

## D16. Finalize the golden set: promote the recorded human finals into the canonical gold (2026-09-15)
- **Decision:** `analysis/scripts/finalize_golden_set.py` overwrites the assistant-drafted draft labels in `evaluation/golden_set.csv` / `.jsonl` with the reviewer's recorded `human_final_*` decisions (200/200 reviewed; 181 accepted, 19 overridden). 29 rows change (20 intent + 21 escalation; some overlap; 7 ESC/UNC rows gain an explicit `escalation_reason`). The pre-review draft is archived in `evaluation/_labels.tsv` and `evaluation/golden_set_recommendations.pre_human_review_backup.csv`; the script is idempotent (re-run = 0 rows changed) and the golden-set validator still passes.
- **Alternatives:** keep gold assistant-drafted (rejected: mislabels the shipped gold as verified); have the reviewer hand-edit 200 CSVs; treat recommendations.csv as gold.
- **Why:** the assignment demands hand-labelled, evaluable ground truth; the recorded finals **are** the human labels. Legacy spellings are preserved in the CSV and mapped at eval time via `taxonomy.to_canonical`, so no validator/architecture change was needed.
- **Evidence:** validator PASS; `python -X utf8 analysis/scripts/finalize_golden_set.py` reports 29 changed rows on the first run and 0 on replay; `git diff --stat` on the golden files.
- **Tradeoff:** single reviewer means no IAA is claimed; every metric is re-derivable against the archived pre-review gold aliases.

## D17. Final metrics on the human-final gold + sole external blocker (2026-09-15)
- **Decision:** after finalization, the full offline evaluation was rerun with `--force` (fresh corpus/models; runtime 208.3 s measured; cached reruns ~40 s). Headline changes vs the draft gold: intent accuracy 0.545→0.510 / macro-F1 0.511→0.477; escalation false-auto 0.275→0.25 (50) and false-ESC 0.09→0.10 (20); overall 2.18→2.20 (groundedness 4.06). Top-5 failures became BA_248481, BA_255518, BA_331684, BA_294773, BA_150929 (booking-change/account-specific boundary family).
- **Alternatives:** leave numbers on the draft gold (rejected: they would not match the shipped gold); fabricate live-judge results (rejected explicitly).
- **Why:** shipped artifacts must match the shipped gold, and no number may be invented.
- **Evidence:** `evaluation/results.json` (generated_utc 2026-09-14T18:41Z, runtime 208.3), `evaluation/EVALUATION_REPORT.md`, `analysis/TOP_5_FAILURES.md`, leakage section all-zero.
- **Tradeoff:** the live Gemini/OpenAI judge runs remain unexecuted (quota exhausted / no key) — the only external blocker; all shipped numbers are `backend=offline`.