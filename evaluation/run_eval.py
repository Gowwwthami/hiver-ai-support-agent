"""Single reproducible evaluation command.

    python -m evaluation.run_eval [--judge offline] [--semantic] [--k 3]
                                  [--max-n 200] [--force]

Runs end-to-end: corpus ensure -> leak checks -> 4 intent models (majority,
keyword/rule, TF-IDF+LR, hybrid) -> retrieval quality -> full pipeline incl.
evidence-grounded generation -> escalation -> judge -> ablations A/B/C/D ->
failure analysis -> results.json + EVALUATION_REPORT.md + predictions.csv.

Ablation semantics (STEP 14 of the assignment brief):
    A  classifier only          : no retrieval; generic draft.
    B  + retrieval              : retrieval on, but generation ignores evidence.
    C  + grounded generation    : generation uses evidence; no escalation gating.
    D  + escalation policy      : full system (evidence-grounded + routing-aware).

Judge backend is "offline" (deterministic) by default. Set EVAL_JUDGE=openai
with OPENAI_API_KEY to run the live LLM judge; live outputs are never simulated.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ba_support import evaluate as evmod  # noqa: E402
from ba_support import judge as judgemod  # noqa: E402
from ba_support import leakage, recommend  # noqa: E402
from ba_support import corpus as corpus_mod  # noqa: E402
from ba_support import intent as intent_mod  # noqa: E402
from ba_support import paths, taxonomy  # noqa: E402
from ba_support import pipeline as pl  # noqa: E402
from ba_support import retrieval as retmod  # noqa: E402

ABLATIONS = [
    ("A_classifier_only", dict(use_evidence=False, intent_filter=False,
                               grounded=True, escalation_aware=True)),
    ("B_classifier_retrieval", dict(use_evidence=True, intent_filter=False,
                                    grounded=False, escalation_aware=False)),
    ("C_grounded_generation", dict(use_evidence=True, intent_filter=True,
                                   grounded=True, escalation_aware=False)),
    ("D_full", dict(use_evidence=True, intent_filter=True,
                    grounded=True, escalation_aware=True)),
]


def parse_args():
    ap = argparse.ArgumentParser(description="British_Airways support-agent evaluation")
    ap.add_argument("--judge", choices=["offline", "openai"], default="offline",
                    help="judge backend (default offline; openai requires OPENAI_API_KEY)")
    ap.add_argument("--semantic", action="store_true",
                    help="use optional sentence-transformers encoder for retrieval (needs package)")
    ap.add_argument("--k", type=int, default=paths.DEFAULT_TOP_K, help="retrieval top-k")
    ap.add_argument("--max-n", type=int, default=200, help="evaluate at most N golden examples")
    ap.add_argument("--force", action="store_true",
                    help="rebuild the corpus cache and refit models")
    return ap.parse_args()


def ensure_corpus(force: bool):
    corpus = corpus_mod.build_corpus(force=force)
    stats = corpus_mod.corpus_summary(corpus)
    print(f"[corpus] {stats['records']:,} records, {stats['conversations']:,} conversations")
    print(f"[corpus] weak-label distribution: {stats['weak_label_counts']}")
    print(f"[corpus] weak-confident share: {stats['weak_confident_share']}")
    return corpus, stats


def leak_audit(corpus: pd.DataFrame) -> dict:
    golden_ids = leakage.golden_conv_ids()
    audit_ids = leakage.audit_conv_ids()
    conv_overlap = set(corpus["conv_id"].astype(int)) & (golden_ids | audit_ids)
    cust = leakage.customer_isolation_stats(corpus)
    result = {
        "golden_conv_overlap": sorted(conv_overlap)[:5],
        "golden_customer_overlap_rows": cust["golden_customer_share_rows"],
        "golden_customer_overlap_convs": cust["golden_customer_share_convs"],
        "corpus_records": int(len(corpus)),
    }
    print(f"[leak] golden/audit conv overlap: {len(conv_overlap)} "
          f"| customer-overlap rows: {cust['golden_customer_share_rows']}")
    return result


def load_or_build_models(corpus: pd.DataFrame, force: bool):
    model_dir = paths.CACHE_DIR / "models"
    # Only the learned models are serialized; the cheap baselines are rebuilt.
    needs = ["tfidf_lr_baseline.joblib", "hybrid_main.joblib"]
    cached = all((model_dir / f).exists() for f in needs)
    if cached and not force:
        models = {
            "majority_baseline": intent_mod.MajorityBaseline(corpus),
            "rule_keyword_baseline": intent_mod.RuleKeywordBaseline(corpus),
            "tfidf_lr_baseline": intent_mod.TfidfLRBaseline.load(
                model_dir / "tfidf_lr_baseline.joblib"),
            "hybrid_main": intent_mod.HybridMainClassifier.load(
                model_dir / "hybrid_main.joblib"),
        }
        print("[models] loaded cached artifacts from "
              f"{model_dir} (use --force to refit)")
        return models
    t0 = time.time()
    maj = intent_mod.MajorityBaseline(corpus)
    rule = intent_mod.RuleKeywordBaseline(corpus)
    lr = intent_mod.TfidfLRBaseline(corpus)
    main = intent_mod.HybridMainClassifier(corpus)
    lr.save(model_dir / "tfidf_lr_baseline.joblib")
    main.save(model_dir / "hybrid_main.joblib")
    models = {"majority_baseline": maj, "rule_keyword_baseline": rule,
              "tfidf_lr_baseline": lr, "hybrid_main": main}
    print(f"[models] fitted majority/rule/tfidf+lr/hybrid in {time.time()-t0:.1f}s "
          f"and cached to {model_dir}")
    return models


def run_intent_block(golden: pd.DataFrame, models: dict) -> tuple[dict, dict]:
    y_true = golden["intent"].tolist()
    out = {}
    preds = {}
    for name, model in models.items():
        t0 = time.time()
        p = model.predict_with_confidence(golden["customer_message"].tolist())
        y_pred = [x["predicted_intent"] for x in p]
        out[name] = evmod.classification_metrics(y_true, y_pred)
        out[name]["fit_or_pred_seconds"] = round(time.time() - t0, 2)
        preds[name] = p
        print(f"[intent {name}] acc={out[name]['accuracy']} "
              f"macro_f1={out[name]['macro_f1']} "
              f"weighted_f1={out[name]['weighted_f1']}")
    return out, preds


def run_pipeline_block(golden: pd.DataFrame, pipeline, judge, max_n: int):
    judges, rows = [], []
    gold = golden.head(max_n)
    for _, r in gold.iterrows():
        pred = pipeline.run(r["customer_message"], conv_id=int(r["conv_id"]),
                            customer_author_id=r["target_author_id"])
        sample = pl.assemble_sample(pred, r.to_dict(), judge)
        j = judge.judge(sample)
        judges.append(j)
        rows.append({
            "example_id": r["example_id"],
            "customer_message": r["customer_message"],
            "gold_intent": r["intent"],
            "pred_intent": pred["intent"],
            "intent_confidence": pred["intent_confidence"],
            "gold_escalation": r["escalation_label"],
            "pred_escalation": pred["escalation"],
            "escalation_reason": pred["escalation_reason"],
            "draft_reply": pred["draft_reply"],
            "reply_mode": pred["reply_mode"],
            "n_evidence": len(pred["evidence"]),
            "top_evidence_sim": pred["evidence"][0]["similarity"] if pred["evidence"] else None,
            "top_evidence_conv": pred["evidence"][0]["conv_id"] if pred["evidence"] else None,
            "top_evidence_brand": pred["evidence"][0]["brand_reply"] if pred["evidence"] else "",
            "gold_reference_reply": r["reference_brand_reply"],
            "gold_prior_context": r["prior_context"],
            **{f"judge_{k}": v for k, v in j.items()
               if k in ("correctness", "groundedness", "completeness",
                        "hallucination", "escalation_appropriate", "overall")},
            "judge_why": j.get("why", ""),
            "judge_backend": j.get("judge_backend", ""),
        })
    return pd.DataFrame(rows), judges


def escalation_block(pred_df: pd.DataFrame) -> dict:
    gold = pred_df["gold_escalation"].tolist()
    pred = pred_df["pred_escalation"].tolist()
    overall = evmod.escalation_metrics(gold, pred)
    main_only = pred_df[pred_df["sample_slice"] == "main"]
    border = pred_df[pred_df["sample_slice"] == "borderline"]
    by_slice = {}
    for name, sub in (("main", main_only), ("borderline", border)):
        if len(sub):
            by_slice[name] = evmod.escalation_metrics(
                sub["gold_escalation"].tolist(), sub["pred_escalation"].tolist())
    return {
        "overall": overall,
        "by_slice": by_slice,
        "unsafe_auto_ids": pred_df.loc[
            pred_df["gold_escalation"].isin({"ESCALATE", "UNCERTAIN"})
            & (pred_df["pred_escalation"] == "AUTO_HANDLE"), "example_id"].tolist(),
    }


def ablation_block(golden: pd.DataFrame, retriever, main_model, judge,
                   max_n: int, top_k: int) -> dict:
    result = {}
    for name, cfg in ABLATIONS:
        pline = pl.Pipeline(main_model, retriever, pl.Config(top_k=top_k, **cfg))
        pred_df, judges = run_pipeline_block(golden, pline, judge, max_n)
        result[name] = {
            "config": cfg,
            "judge": evmod.aggregate_judge(judges),
            "escalation": evmod.escalation_metrics(
                pred_df["gold_escalation"].tolist(), pred_df["pred_escalation"].tolist()),
            "n": len(pred_df),
        }
        agg = result[name]["judge"]
        print(f"[ablation {name}] overall={agg.get('overall')} "
              f"grounded={agg.get('groundedness')} "
              f"hallucination_rate={agg.get('hallucination_rate')} "
              f"esc_appropriate={agg.get('escalation_appropriate_rate')}")
    return result


def top_failures(pred_df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    df = pred_df.copy()
    df["intent_mismatch"] = df["gold_intent"] != df["pred_intent"]
    df["unsafe_auto"] = df["gold_escalation"].isin({"ESCALATE", "UNCERTAIN"}) & (
        df["pred_escalation"] == "AUTO_HANDLE")
    df["halluc"] = df["judge_hallucination"].astype(bool)
    df["severity"] = (
        1.0 * df["unsafe_auto"].astype(int)
        + 0.6 * df["halluc"].astype(int)
        + 0.4 * df["intent_mismatch"].astype(int)
        + (5 - df["judge_overall"].astype(int)) / 5.0)
    df = df.sort_values("severity", ascending=False).head(n)
    return df.reset_index(drop=True)


def _diagnose_failure(r) -> tuple[str, str]:
    """Per-case (root cause, proposed fix), deterministic from row fields."""
    msg = r.customer_message.lower()
    danger = (
        "legal/regulatory" if re.search(r"lawyer|sue|lawsuit|\blaw\b|court|legal|solicitor", msg)
        else "security/identity" if re.search(r"hack|fraud|password|identity|scam|suspicious|unauthor", msg)
        else "money/compensation" if re.search(r"refund|compens|money|payment|charged|claim", msg)
        else "complaint" if re.search(r"complaint|worst|awful|disappoint|shock|dreadful|terrible|appall", msg)
        else None)
    if danger:
        if danger in ("legal/regulatory", "security/identity"):
            root = (
                f"The customer message carries a **{danger}** risk, but it still "
                f"reached AUTO_HANDLE. escalation.py's legal/security markers run "
                f"GLOBALLY before the intent branches (escalation.py §1), so the "
                f"regexes did not match this exact wording; the classifier's "
                f"predicted `{r.pred_intent}` branch then had no escalating rule, "
                f"and the evidence-sufficiency gate passed (top sim "
                f"{r.top_evidence_sim:.2f}). The gap is marker recall, not marker "
                f"placement."
            )
            fix = (
                f"Extend the global **{danger}** marker regex in escalation.py to "
                f"cover this wording (and add a regression test asserting the exact "
                f"message ESCALATEs), keeping the markers above the intent branches."
            )
        else:
            root = (
                f"The customer message carries **{danger}** wording, but the "
                f"classifier predicted `{r.pred_intent}` — a safe-by-default "
                f"intent. escalation.py's {danger} markers only fire inside "
                f"matching intent branches (not globally), so the misclassification "
                f"routed the message past them; the evidence-sufficiency gate "
                f"passed (top sim {r.top_evidence_sim:.2f}), so it was "
                f"auto-handled."
            )
            fix = (
                f"Add boundary-deciding rules between `{r.gold_intent}` and "
                f"`{r.pred_intent}` in `weak.py` (or promote the **{danger}** "
                f"marker family above the intent branches in `escalation.py`), "
                f"and add a regression test asserting the exact message "
                f"ESCALATEs."
            )
        return root, fix
    root = (f"Intent confusion: gold `{r.gold_intent}` vs predicted "
            f"`{r.pred_intent}` (confidence {r.intent_confidence:.2f}). The boundary "
            f"between these intents is weak in the weak-labelled corpus, so the policy "
            f"routed by the wrong intent.")
    fix = (f"Add explicit boundary/deciding rules between "
           f"`{r.gold_intent}` and `{r.pred_intent}` in `weak.py`, and sample "
           f"gold-set misclassified pairs as reviewer candidates.")
    return root, fix


def write_failures_md(df: pd.DataFrame, out_path) -> str:
    lines = [
        "# Top 5 Failures (real examples from the golden set)",
        "",
        "The five worst end-to-end golden-set cases by combined severity "
        "(unsafe AUTO_HANDLE + hallucination + intent mismatch + low judge "
        "score). Content is pulled verbatim from `evaluation/predictions.csv` "
        "and the golden set; nothing is manufactured.",
    ]
    for i, r in enumerate(df.itertuples(), 1):
        evid = (
            f"conv {r.top_evidence_conv} (sim={r.top_evidence_sim:.2f}): "
            f"{r.top_evidence_brand[:220]}" if r.top_evidence_conv else "none")
        root, fix = _diagnose_failure(r)
        lines += [
            f"## {i}. {r.example_id}",
            "",
            f"1. **Real customer message**: {r.customer_message}",
            f"2. **Prior context visible to the customer**: "
            f"{(r.gold_prior_context or '(none)')[:220]}",
            f"3. **Expected label**: `{r.gold_intent}`",
            f"4. **Predicted label**: `{r.pred_intent}` "
            f"(confidence {r.intent_confidence})",
            f"5. **Expected escalation**: `{r.gold_escalation}`",
            f"6. **Predicted escalation**: `{r.pred_escalation}` "
            f"(reason: {r.escalation_reason})",
            f"7. **Golden reference reply**: {(r.gold_reference_reply or '(none)')[:220]}",
            f"8. **Generated response**: {r.draft_reply}",
            f"9. **Retrieved evidence**: {evid}",
            f"10. **Judge verdict**: {r.judge_why}",
            f"11. **Likely root cause**: {root}",
            f"12. **Proposed fix**: {fix}",
        ]
        lines.append("")
    text = "\n".join(lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return text


def human_review_summary() -> dict:
    """Draft-vs-human agreement from golden_set_reviewed.csv (real numbers only).

    Returns a not_available marker when the reviewed file has not been produced
    (i.e. `analysis/scripts/apply_human_review.py` has not been run yet) instead
    of inventing figures."""
    reviewed_csv = paths.EVAL_DIR / "golden_set_reviewed.csv"
    if not reviewed_csv.exists():
        return {"available": False,
                "reason": "golden_set_reviewed.csv not present; run "
                          "analysis/scripts/apply_human_review.py"}
    rev = pd.read_csv(reviewed_csv, dtype=str, keep_default_na=False)
    draft_i = rev["recommended_intent"].map(taxonomy.to_canonical)
    final_i = rev["human_final_intent"].map(taxonomy.to_canonical)
    n = len(rev)
    intent_agree = float((draft_i == final_i).mean())
    esc_agree = float((rev["recommended_escalation"]
                       == rev["human_final_escalation"]).mean())
    return {
        "available": True,
        "n_reviewed": int(n),
        "intent_agreement": round(intent_agree, 4),
        "escalation_agreement": round(esc_agree, 4),
        "n_intent_changed": int((draft_i != final_i).sum()),
        "n_escalation_changed": int((rev["recommended_escalation"]
                                    != rev["human_final_escalation"]).sum()),
    }


def build_results_md(results: dict) -> str:
    L = ["# British_Airways Support-Agent — Evaluation Report",
         "",
         f"- Golden set evaluated: **{results['overview'].get('n_golden')}** "
         f"(final label decisions are the recorded human finals — see §G; the "
         "three Phase-2.1 renames are stored in legacy spelling and mapped at "
         "eval time via `taxonomy.to_canonical`).",
         f"- Judge backend: **{results['overview'].get('judge_backend')}** "
         "(offline deterministic unless OPENAI_API_KEY + EVAL_JUDGE=openai).",
         f"- Seed: {results['seed']}; top-k: {results['top_k']}.",
         f"- Measured wall-clock runtime of this run: "
         f"**{results.get('runtime_seconds')} s** (measured, not estimated).",
         "",
         "## A. Intent classification (golden held-out set)",
         "",
         "| system | accuracy | macro F1 | weighted F1 |",
         "|---|---:|---:|---:|"]
    for name, m in results["intent_classification"].items():
        L.append(f"| `{name}` | {m['accuracy']:.4f} | {m['macro_f1']:.4f} | "
                 f"{m['weighted_f1']:.4f} |")
    hy = results["intent_classification"]["hybrid_main"]
    L += [
        "",
        "Per-class precision/recall/F1 (hybrid main):",
        "",
        "| intent | support | precision | recall | F1 |",
        "|---|---:|---:|---:|---:|"]
    for p in hy["per_class"]:
        L.append(f"| `{p['intent']}` | {p['support']} | {p['precision']:.3f} | "
                 f"{p['recall']:.3f} | {p['f1']:.3f} |")
    L += [
        "",
        "Confusion matrix (labels sorted): see `results.json` → "
        "`intent_classification.hybrid_main.confusion_matrix`.",
        "",
        "## B. Retrieval",
        "",
        "| metric | value |",
        "|---|---:|"]
    for k, v in results["retrieval_quality"].items():
        L.append(f"| {k} | {v} |")
    L += [
        "",
        "Retrieval sim is TF-IDF cosine; `recall_at_k_intent_consistency` is a "
        "coarse coverage proxy against golden intent, not human relevance.",
        "",
        "## C. Response quality (full pipeline, judge)",
        "",
        "| metric | value |",
        "|---|---:|"]
    for k, v in results["response_quality"].items():
        L.append(f"| {k} | {v} |")
    L += [
        "",
        "## D. Escalation routing (full pipeline)",
        "",
        "| metric | value |",
        "|---|---:|"]
    for k, v in results["escalation"]["overall"].items():
        L.append(f"| {k} | {v} |")
    L += [
        "",
        "Unsafe AUTO_HANDLE ids: " +
        (", ".join(results["escalation"].get("unsafe_auto_ids", [])) or "none"),
        "",
        "## E. Ablations (judge)",
        "",
        "| config | overall | groundedness | hallucination rate | escalation-appropriate |",
        "|---|---:|---:|---:|---:|"]
    for name, blk in results["ablations"].items():
        j = blk["judge"]
        L.append(f"| `{name}` | {j['overall']:.2f} | {j['groundedness']:.2f} | "
                 f"{j['hallucination_rate']:.2f} | "
                 f"{j['escalation_appropriate_rate']:.2f} |")
    L += [
        "",
        "## F. Splits and leakage controls",
        "",
        f"- Train signal: weakly-labelled, confident corpus rows "
        f"(weak-confident share {results['overview'].get('corpus_confident_share')}).",
        f"- Eval: golden set `n={results['overview'].get('golden_total')}` "
        "(never in corpus, never in classifier training).",
        f"- Corpus: {results['leakage']['corpus_records']:,} records; "
        "golden/audit conversation overlap "
        f"{len(results['leakage']['golden_conv_overlap'])}; golden-customer "
        f"overlap rows {results['leakage']['golden_customer_overlap_rows']}.",
        f"- Evidence returned to eval examples that is itself a golden "
        f"conversation: **{results['leakage'].get('evidence_top_conv_golden_leak', 0)}** "
        "(must be 0).",
        "",
        "## G. Human-review status and honesty notes",
        "",
        "## H. Reproduce",
        "",
        "```",
        "python -m evaluation.run_eval --judge offline",
        "```"]
    hr = results["human_review"]
    if hr.get("available"):
        lines = [
            "Draft (assistant) recommendations vs. the recorded human final "
            "decisions — computed from `evaluation/golden_set_reviewed.csv` "
            "(no fabricated numbers):",
            f"- Rows with a recorded human final decision: **{hr['n_reviewed']}**.",
            f"- Intent agreement (draft vs. human final): "
            f"**{hr['intent_agreement']:.4f}** ({hr['n_intent_changed']} changed).",
            f"- Escalation agreement (draft vs. human final): "
            f"**{hr['escalation_agreement']:.4f}** "
            f"({hr['n_escalation_changed']} changed).",
            "",
            "The canonical golden set now carries those final decisions "
            "(`analysis/scripts/finalize_golden_set.py`). The pre-review "
            "assistant draft is preserved in `evaluation/_labels.tsv`, "
            "`evaluation/golden_set_review_queue.csv`, "
            "`evaluation/golden_set_recommendations.csv` and "
            "`golden_set_recommendations.pre_human_review_backup.csv`.",
        ]
    else:
        lines = [
            "Draft-vs-human agreement: **pending** — "
            f"{hr.get('reason', '')}.",
        ]
    lines += [
        "- LLM-as-judge agreement with humans: the recorded `human_final_*` "
        "values are label decisions, not response-quality ratings, so "
        "judge↔human response agreement is **not computable** (nothing "
        "fabricated).",
        "- Judge outputs here are from the **offline deterministic fallback**. A "
        "live LLM judge runs only with `OPENAI_API_KEY` + `EVAL_JUDGE=openai`; "
        "no live output is ever simulated.",
        "- Read the mandatory section: *\"What is misleading about my headline "
        "number?\"* in the project README.",
        "",
    ]
    mark = "## G. Human-review status and honesty notes"
    idx = L.index(mark)
    L[idx + 1:idx + 1] = lines
    return "\n".join(L) + "\n"


def main():
    args = parse_args()
    t_start = time.time()
    print("=" * 72)
    print("British_Airways support-agent evaluation (Hiver SDE Intern Take-Home)")
    print(f"judge={args.judge}  top_k={args.k}  max_n={args.max_n}  "
          f"semantic={args.semantic}  force={args.force}")
    print("=" * 72)

    corpus, corpus_stats = ensure_corpus(args.force)
    leak = leak_audit(corpus)

    golden = leakage.golden_panel()
    golden["intent"] = golden["intent"].map(taxonomy.to_canonical)
    n_golden = min(args.max_n, len(golden))

    models = load_or_build_models(corpus, args.force)

    # ---- intent classification ------------------------------------------------
    intent_metrics, _ = run_intent_block(golden, models)

    # ---- retrieval + pipeline + judge -----------------------------------------
    retriever = retmod.Retriever(corpus, semantic=args.semantic)
    print(f"[retrieval] encoder={retriever.encoder.name}")
    ref_quality = retmod.retrieval_quality(retriever, golden, "golden", top_k=args.k)
    print(f"[retrieval] R@{args.k} intent-consistency="
          f"{ref_quality.get('recall_at_k_intent_consistency')}")

    judge = judgemod.make_judge(args.judge)
    print(f"[judge] backend={judge.backend}")

    pline_full = pl.Pipeline(models["hybrid_main"], retriever,
                             pl.Config(top_k=args.k, judge_backend=args.judge))
    full_df, full_judges = run_pipeline_block(golden, pline_full, judge, n_golden)
    print(f"[pipeline] ran {len(full_df)} end-to-end examples")

    full_df = full_df.merge(golden[["example_id", "sample_slice"]],
                            on="example_id", how="left")
    ablations = ablation_block(golden, retriever, models["hybrid_main"], judge,
                               max_n=n_golden, top_k=args.k)
    escal = escalation_block(full_df)
    response_quality = evmod.aggregate_judge(full_judges)

    # ---- evidence-level leakage check -----------------------------------------
    golden_ids = leakage.golden_conv_ids()
    ev_leak = int(full_df["top_evidence_conv"].dropna().astype(int)
                  .isin(golden_ids).sum())
    if ev_leak:
        raise AssertionError(f"golden conversation leaked into retrieval evidence: {ev_leak}")
    leak["evidence_top_conv_golden_leak"] = ev_leak

    # ---- failures ---------------------------------------------------------------
    failures = top_failures(full_df, n=5)
    write_failures_md(failures, paths.FAILURES_MD)
    print(f"[failures] wrote {paths.FAILURES_MD}")

    # ---- golden-set review recommendations (Phase 2.1 completion) ---------------
    recommend.main()

    results = {
        "project": "Hiver SDE Intern Take-Home - British_Airways support agent",
        "generated_utc": pd.Timestamp.now("UTC").isoformat(),
        "seed": paths.EVAL_SEED,
        "top_k": args.k,
        "judge_backend": args.judge,
        "model_cards": intent_mod.system_descriptions(),
        "overview": {
            "n_golden": int(n_golden),
            "golden_total": int(len(golden)),
            "brand": paths.BRAND,
            "corpus_records": corpus_stats["records"],
            "corpus_conversations": corpus_stats["conversations"],
            "corpus_confident_share": corpus_stats["weak_confident_share"],
            "train_weak_confident_rows": int(
                (corpus["weak_confident"] & (corpus["weak_intent"] != "other")).sum()),
            "judge_backend": args.judge,
        },
        "leakage": leak,
        "corpus_weak_label_distribution": corpus_stats["weak_label_counts"],
        "intent_classification": intent_metrics,
        "imbalance": evmod.imbalance_summary(golden["intent"].tolist()),
        "retrieval_quality": ref_quality,
        "escalation": escal,
        "response_quality": response_quality,
        "ablations": ablations,
        "per_example": full_df.to_dict(orient="records"),
        "failure_top5_ids": failures["example_id"].tolist(),
        "human_agreement": judgemod.evaluate_judge_agreement_available(),
        "human_review": human_review_summary(),
        "runtime_seconds": round(time.time() - t_start, 1),
    }

    evmod.dump_results(results, paths.RESULTS_JSON)
    full_df.to_csv(paths.PREDICTIONS_CSV, index=False, encoding="utf-8")
    paths.RESULTS_MD.write_text(build_results_md(results), encoding="utf-8")

    print("\n" + "=" * 72)
    print(f"WRITTEN: {paths.RESULTS_JSON} / {paths.RESULTS_MD} / "
          f"{paths.PREDICTIONS_CSV} / {paths.FAILURES_MD}")
    print(f"runtime {results['runtime_seconds']}s (measured)")
    print(f"headline: esc-appropriate={response_quality.get('escalation_appropriate_rate')} "
          f"hallucination-rate={response_quality.get('hallucination_rate')} "
          f"intent macro F1 (hybrid)={intent_metrics['hybrid_main']['macro_f1']}")
    print("DONE")


if __name__ == "__main__":
    main()