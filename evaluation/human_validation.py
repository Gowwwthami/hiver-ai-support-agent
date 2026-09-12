"""Human response-quality validation tooling (additive evaluation tooling).

Performs three jobs around the approved 50-example stratified review:

1. `select`   - build the deterministic 50-example review sample from the
                FINAL reviewed labels (`golden_set_reviewed.csv`) and current
                model outputs (`predictions.csv`), and write a manifest CSV.
2. `export`   - write the reviewer-facing CSV/HTML form for that sample with a
                blank `human_*` scoring block (no judge scores, gold labels,
                slices, or success flags exposed).
3. `judge`    - run the existing judge interface over exactly the selected
                example_ids (targeted path), writing per-example scores with
                `example_id` + `judge_backend` columns.
4. `agree`    - compute human-vs-judge agreement statistics from the returned
                scores CSV (Spearman + bootstrap CI, MAD, exact/within-one,
                Cohen's kappa + raw agreement).

Design rules (pre-registered):
- sample size N=50, deterministic seed 2026;
- UNCERTAIN near-census (5 of 6) because it is the rarest, highest-risk class;
  the sample is for JUDGE VALIDATION, not population prevalence estimation;
- the human reviewer is the PROJECT AUTHOR - reports never claim an
  independent annotator or compute human-human kappa;
- judge vs human comparisons are run offline and live separately and are
  NEVER mixed;
- thresholds are declared here, before any results exist.

    python -X utf8 -m evaluation.human_validation select  --seed 2026
    python -X utf8 -m evaluation.human_validation export  --seed 2026
    python -X utf8 -m evaluation.human_validation judge   --backend offline
    python -X utf8 -m evaluation.human_validation agree   --human <scores.csv>
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ba_support import judge as judgemod  # noqa: E402
from ba_support import paths, taxonomy  # noqa: E402

# ---- pre-registered constants -------------------------------------------------
SAMPLE_N = 50
SAMPLE_SEED = 2026          # deterministic sample (same constant as paths.SAMPLING_SEED)
BORDERLINE_CAP = 8          # population borderline share 14.5% -> ~7-8 of 50
OUT_DIR = paths.HUMAN_VALIDATION_DIR

# Final reviewed escalation populations (must match golden_set_reviewed.csv).
POP_ESC = {"AUTO_HANDLE": 119, "ESCALATE": 75, "UNCERTAIN": 6}

# Stratified quota: (final_intent, final_escalation) -> n. Sums to 50.
QUOTAS = {
    ("non_support_or_acknowledgement", "AUTO_HANDLE"): 12,
    ("non_support_or_acknowledgement", "UNCERTAIN"): 2,
    ("flight_disruption", "AUTO_HANDLE"): 3,
    ("flight_disruption", "ESCALATE"): 3,
    ("flight_disruption", "UNCERTAIN"): 1,
    ("information_or_policy", "AUTO_HANDLE"): 5,
    ("information_or_policy", "UNCERTAIN"): 1,
    ("refund_or_compensation", "ESCALATE"): 5,
    ("website_or_app_issue", "AUTO_HANDLE"): 4,
    ("website_or_app_issue", "ESCALATE"): 1,
    ("baggage", "AUTO_HANDLE"): 2,
    ("baggage", "ESCALATE"): 1,
    ("baggage", "UNCERTAIN"): 1,
    ("booking_change_or_cancellation", "ESCALATE"): 3,
    ("complaint_or_human_assistance", "ESCALATE"): 3,
    ("seat_or_upgrade", "AUTO_HANDLE"): 1,
    ("seat_or_upgrade", "ESCALATE"): 1,
    ("account_access_or_security", "ESCALATE"): 1,
}

# Pre-registered agreement thresholds (decision criteria, not measured results).
THRESHOLDS = {
    "spearman_weak": 0.50,
    "spearman_good": 0.70,
    "kappa_weak": 0.40,
    "kappa_good": 0.60,
    "mad_max": 1.0,
    "within_one_min": 0.80,
}

ORDINAL_COLS = ["overall", "correctness", "groundedness", "completeness"]
BINARY_COLS = ["hallucination", "escalation_appropriate"]

# Columns the reviewer form may contain.
FORM_FIXED = [
    "example_id", "customer_message", "predicted_intent", "predicted_escalation",
    "predicted_escalation_reason", "draft_reply", "n_evidence",
    "evidence1_brand_reply", "evidence1_similarity",
    "evidence2_brand_reply", "evidence2_similarity",
]
FORM_HUMAN = [
    "human_correctness", "human_groundedness", "human_completeness",
    "human_hallucination", "human_escalation_appropriate", "human_overall",
    "human_why",
]
FORBIDDEN = ["judge_", "gold_", "sample_slice", "success", "failure",
             "known_failure"]


# ---- data loading -------------------------------------------------------------
def load_merged() -> pd.DataFrame:
    """Final reviewed labels joined with current stored model predictions."""
    rev = pd.read_csv(paths.EVAL_DIR / "golden_set_reviewed.csv",
                      dtype=str, keep_default_na=False)
    pred = pd.read_csv(paths.PREDICTIONS_CSV)
    rev["final_intent"] = rev["human_final_intent"].map(taxonomy.to_canonical)
    m = rev[["example_id", "final_intent", "human_final_escalation",
             "human_decision_accept"]].merge(pred, on="example_id")
    m["succeed"] = (m["pred_intent"] == m["final_intent"]) & ~(
        m["human_final_escalation"].isin({"ESCALATE", "UNCERTAIN"})
        & (m["pred_escalation"] == "AUTO_HANDLE"))
    return m


def sample_population() -> dict:
    """Final reviewed population counts (must match approved constants)."""
    m = load_merged()
    esc = m["human_final_escalation"].value_counts().to_dict()
    intent = m["final_intent"].value_counts().to_dict()
    return {
        "n": int(len(m)),
        "escalation": esc,
        "intent": intent,
        "succeed": int(m["succeed"].sum()),
        "fail": int((~m["succeed"]).sum()),
        "accept": int(m["human_decision_accept"].eq("TRUE").sum()),
        "changed": int(m["human_decision_accept"].ne("TRUE").sum()),
        "borderline": int(m["sample_slice"].eq("borderline").sum()),
    }


# ---- sample selection ----------------------------------------------------------
def select_sample(seed: int = SAMPLE_SEED, n: int = SAMPLE_N,
                  borderline_cap: int = BORDERLINE_CAP) -> pd.DataFrame:
    """Deterministic stratified 50-row sample from final reviewed state."""
    m = load_merged()
    claimed = sum(QUOTAS.values())
    if claimed != n:
        raise ValueError(f"QUOTAS sum to {claimed}, expected {n}")
    rng = np.random.default_rng(seed)
    picked, border_used = [], 0
    for (intent, esc), want in QUOTAS.items():
        pool = m[(m["final_intent"] == intent)
                 & (m["human_final_escalation"] == esc)]
        if len(pool) < want:
            raise ValueError(f"cell ({intent}, {esc}) has {len(pool)} < {want}")
        # Inside each cell prefer a mix of borderline/main, success/fail.
        border = pool[pool["sample_slice"] == "borderline"]
        main = pool[pool["sample_slice"] == "main"]
        n_b = min(len(border), want - 0 if want else 0,
                  borderline_cap - border_used)
        n_b = min(n_b, want)
        part_a = border.sample(n=n_b, random_state=rng) if n_b > 0 else None
        part_b = main.sample(n=want - n_b, random_state=rng) if want - n_b > 0 else None
        cell = pd.concat([part_a, part_b]) if n_b > 0 else part_b
        if len(cell) < want:  # main pool too small; top up from border/main combo
            need = want - len(cell)
            extra = border.sample(n=need, random_state=rng)
            cell = pd.concat([cell, extra])
        border_used += n_b
        picked.append(cell)
    sample = pd.concat(picked)
    # maintain main/borderline balance close to population share
    if border_used > borderline_cap:
        raise ValueError("borderline quota exceeded design cap")
    if len(sample) != n:
        raise ValueError(f"selected {len(sample)} != {n}")
    return sample


def select_with_manifest(seed: int = SAMPLE_SEED) -> pd.DataFrame:
    """Sample + composition report + manifest CSV (the exact 50 ids)."""
    m = load_merged()
    pop = sample_population()
    sample = select_sample(seed=seed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest_cols = ["example_id", "final_intent", "human_final_escalation",
                     "human_decision_accept", "pred_intent", "pred_escalation",
                     "sample_slice", "succeed"]
    sample[manifest_cols].to_csv(OUT_DIR / "review_sample_manifest.csv",
                                 index=False, encoding="utf-8")
    report = {
        "n": int(len(sample)),
        "seed": int(seed),
        "population": pop,
        "sample_escalation": sample["human_final_escalation"].value_counts().to_dict(),
        "sample_intent": sample["final_intent"].value_counts().to_dict(),
        "sample_succeed": int(sample["succeed"].sum()),
        "sample_fail": int((~sample["succeed"]).sum()),
        "sample_borderline": int(sample["sample_slice"].eq("borderline").sum()),
        "sample_accept": int(sample["human_decision_accept"].eq("TRUE").sum()),
        "sample_overall_dist": sample["judge_overall"].value_counts().sort_index().to_dict(),
        "sample_grounded_dist": sample["judge_groundedness"].value_counts().sort_index().to_dict(),
        "sample_example_ids": sorted(sample["example_id"].tolist()),
    }
    (OUT_DIR / "review_sample_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return sample


# ---- review form export ---------------------------------------------------------
def build_review_form(sample_ids, seed: int = SAMPLE_SEED) -> pd.DataFrame:
    """Blinded reviewer form (fixed columns + blank human_* block), shuffled."""
    pred = pd.read_csv(paths.PREDICTIONS_CSV)
    p = pred[pred["example_id"].isin(set(sample_ids))].copy()
    if len(p) != len(sample_ids):
        raise ValueError("some sample ids are missing from predictions.csv")
    form = pd.DataFrame({
        "example_id": p["example_id"],
        "customer_message": p["customer_message"],
        "predicted_intent": p["pred_intent"],
        "predicted_escalation": p["pred_escalation"],
        "predicted_escalation_reason": p["escalation_reason"],
        "draft_reply": p["draft_reply"],
        "n_evidence": p["n_evidence"],
        "evidence1_brand_reply": p["top_evidence_brand"],
        "evidence1_similarity": p["top_evidence_sim"],
    })
    # second evidence is not stored per-example in predictions.csv; the retriever
    # top-2 is reconstructed by the targeted judge pathway when available.
    form["evidence2_brand_reply"] = ""
    form["evidence2_similarity"] = np.nan
    for col in FORM_HUMAN:
        form[col] = ""
    form = form[FORM_FIXED + FORM_HUMAN]
    rng = np.random.default_rng(seed)
    form = form.sample(frac=1.0, random_state=rng).reset_index(drop=True)
    _assert_blinded(form)
    return form


def _assert_blinded(form: pd.DataFrame) -> None:
    for col in form.columns:
        for bad in FORBIDDEN:
            if bad in col.lower():
                raise AssertionError(
                    f"forbidden column leaked into review form: {col}")


def export_form(sample_ids, seed: int = SAMPLE_SEED) -> pd.DataFrame:
    """Write reviewer CSV + a rendering-friendly HTML mirror."""
    form = build_review_form(sample_ids, seed=seed)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    form.to_csv(OUT_DIR / "review_form_round1.csv", index=False, encoding="utf-8")
    _write_html(form, OUT_DIR / "review_form_round1.html")
    return form


def _write_html(form: pd.DataFrame, path: Path) -> None:
    rows = []
    for _, r in form.iterrows():
        rows.append(
            "<div class='ex'>"
            f"<h3>{r['example_id']}</h3>"
            f"<p><b>customer_message:</b> {_esc(r['customer_message'])}</p>"
            f"<p><b>predicted_intent:</b> {_esc(r['predicted_intent'])} &middot; "
            f"<b>predicted_escalation:</b> {_esc(r['predicted_escalation'])} &middot; "
            f"<b>reason:</b> {_esc(r['predicted_escalation_reason'])}</p>"
            f"<p><b>draft_reply:</b> {_esc(r['draft_reply'])}</p>"
            f"<p><b>evidence ({r['n_evidence']}):</b> "
            f"{_esc(r['evidence1_brand_reply'])} <i>(sim {r['evidence1_similarity']})</i>"
            + (f" <br/>{_esc(r['evidence2_brand_reply'])} <i>(sim {r['evidence2_similarity']})</i>"
               if r["evidence2_brand_reply"] else "")
            + "</p>"
            + "<br/>".join(f"{c} = <input name='{c}' id='{c}'>"
                           for c in FORM_HUMAN)
            + "</div>")
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>"
        "Response-quality review round 1</title><style>body{font-family:sans-serif;"
        "max-width:900px;margin:2em auto;padding:0 1em}.ex{border:1px solid #ccc;"
        "border-radius:8px;padding:1em;margin:1.5em 0}input{width:6em;margin:0 .4em}"
        "</style></head><body><h1>Response-quality review (blinded)</h1>"
        "<p>Score each draft with the six-criterion rubric. You will not see "
        "judge scores, gold labels, slices, or success flags.</p>"
        + "".join(rows) + "</body></html>")
    path.write_text(html, encoding="utf-8")


def _esc(text) -> str:
    s = "" if pd.isna(text) else str(text)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---- targeted judge pathway -----------------------------------------------------
def targeted_judge(sample_ids, backend: str = "offline") -> pd.DataFrame:
    """Run the EXISTING judge interface over exactly the selected examples.

    Uses the stored predictions.csv rows so the judge sees the same customer
    message, retrieved evidence, draft reply, predicted intent and escalation
    as the shipped evaluation. Offline judge scores are verified to reproduce
    the stored judge_* columns (determinism guard).
    """
    try:
        judge = judgemod.make_judge(backend)
    except (ImportError, RuntimeError) as e:
        raise RuntimeError(
            f"live judge backend '{backend}' is not usable here: {e}; "
            "use `--backend offline` for the reproducible target run") from e
    pred = pd.read_csv(paths.PREDICTIONS_CSV)
    p = pred[pred["example_id"].isin(set(sample_ids))].copy()
    if len(p) != len(sample_ids):
        raise ValueError("some sample ids are missing from predictions.csv")
    rows = []
    for _, r in p.iterrows():
        evidence = [] if r["n_evidence"] == 0 or pd.isna(r["top_evidence_sim"]) else [
            {"brand_reply": (r["top_evidence_brand"] or ""),
             "similarity": float(r["top_evidence_sim"])}]
        sample = {
            "customer_message": r["customer_message"],
            "draft_reply": r["draft_reply"],
            "mode": r["reply_mode"],
            "reply_mode": r["reply_mode"],
            "intent_predicted": r["pred_intent"],
            "intent_gold": r["gold_intent"],
            "escalation_predicted": r["pred_escalation"],
            "escalation_gold": r["gold_escalation"],
            "evidence_used": evidence,
            "example_id": r["example_id"],
        }
        verdict = judge.judge(sample)
        if backend == "offline":
            for k in ("correctness", "groundedness", "completeness",
                      "hallucination", "escalation_appropriate", "overall"):
                if verdict[k] != r[f"judge_{k}"]:
                    raise AssertionError(
                        f"offline targeted judge diverged from stored score "
                        f"for {r['example_id']} on {k}")
        rows.append({
            "example_id": r["example_id"],
            "judge_backend": verdict["judge_backend"],
            "judge_overall": verdict["overall"],
            "judge_correctness": verdict["correctness"],
            "judge_groundedness": verdict["groundedness"],
            "judge_completeness": verdict["completeness"],
            "judge_hallucination": verdict["hallucination"],
            "judge_escalation_appropriate": verdict["escalation_appropriate"],
            "judge_why": verdict["why"],
        })
    out = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_DIR / f"targeted_judge_{backend}.csv", index=False,
               encoding="utf-8")
    return out


# ---- agreement statistics ----------------------------------------------------------
def _spearman(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    with np.errstate(all="ignore"):
        if np.allclose(a, a[0]) or np.allclose(b, b[0]):
            if np.allclose(a, a[0]) and np.allclose(b, b[0]) and float(a[0]) == float(b[0]):
                return 1.0
            return float("nan")
        return float(stats.spearmanr(a, b).statistic)


def _coerce_bool(series: pd.Series) -> pd.Series:
    """Map review-schema strings (true/false/yes/1...) to bool/NaN."""
    def _one(x):
        if isinstance(x, float) and np.isnan(x):
            return np.nan
        if isinstance(x, str):
            s = x.strip().lower()
            if s in ("", "nan", "none"):
                return np.nan
            return s in ("true", "1", "yes", "t", "y")
        return bool(x)
    return series.map(_one)


def _bootstrap_spearman_ci(a, b, n_boot: int = 1000, seed: int = 2026):
    """Percentile 95% CI for Spearman via paired resampling (fixed seed)."""
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = len(a)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        if np.allclose(a[idx], a[idx][0]) or np.allclose(b[idx], b[idx][0]):
            vals.append(np.nan)
        else:
            vals.append(_spearman(a[idx], b[idx]))
    finite = np.array([v for v in vals if v == v])
    if finite.size == 0:
        return None, None
    lo, hi = np.percentile(finite, [2.5, 97.5])
    return float(lo), float(hi)


def _kappa(labels1, labels2):
    """Cohen's kappa (manual; avoids sklearn dependency) with PABAK variant.

    Convention for degenerate constant inputs: both raters constant and equal
    means perfect agreement (kappa 1.0); both constant but different means
    systematic total disagreement (kappa 0.0).
    """
    a = np.asarray(labels1, dtype=bool)
    b = np.asarray(labels2, dtype=bool)
    n = len(a)
    if n == 0:
        return float("nan"), float("nan")
    if bool(np.all(a == a[0])) and bool(np.all(b == b[0])):
        return (1.0, 1.0) if bool(a[0]) == bool(b[0]) else (0.0, -1.0)
    po = float((a == b).mean())
    classes = sorted(set(a) | set(b))
    pa, pb = {}, {}
    for c in classes:
        pa[c] = float((a == c).mean())
        pb[c] = float((b == c).mean())
    pe = float(sum(pa[c] * pb[c] for c in classes))
    kappa = (po - pe) / (1.0 - pe) if pe < 1.0 else float("nan")
    pabak = (2 * po - 1.0)
    return float(kappa), float(pabak)


def compute_agreement(human_df: pd.DataFrame, judge_df: pd.DataFrame) -> dict:
    """Statistics comparing a human review CSV with a targeted judge CSV."""
    backends = judge_df["judge_backend"].unique().tolist()
    if len(backends) != 1:
        raise ValueError(f"judge CSV mixes backends: {backends}")
    backend = backends[0]
    join = human_df.merge(judge_df, on="example_id", how="inner")
    n_missing = len(human_df) - len(join)
    if n_missing != 0:
        raise ValueError(f"{n_missing} human rows have no judge output")

    ordinal = {}
    for col in ORDINAL_COLS:
        h = pd.to_numeric(join[f"human_{col}"], errors="coerce").astype(float)
        j = pd.to_numeric(join[f"judge_{col}"], errors="coerce").astype(float)
        mask = h.notna() & j.notna()
        h, j = h[mask], j[mask]
        if len(h) < 3:
            ordinal[col] = {"n": int(len(h)), "note": "too few paired values"}
            continue
        spearman = _spearman(h, j)
        lo, hi = _bootstrap_spearman_ci(h, j)
        mad = float(np.abs(h - j).mean())
        exact = float((h == j).mean())
        within = float((np.abs(h - j) <= 1).mean())
        ordinal[col] = {
            "n": int(len(h)),
            "spearman": round(spearman, 4),
            "spearman_ci95": [None if lo is None else round(lo, 4),
                              None if hi is None else round(hi, 4)],
            "mean_abs_diff": round(mad, 4),
            "exact_agreement": round(exact, 4),
            "within_one": round(within, 4),
        }

    binary = {}
    for col in BINARY_COLS:
        h = _coerce_bool(join[f"human_{col}"])
        j = _coerce_bool(join[f"judge_{col}"])
        mask = h.notna() & j.notna()
        h, j = h[mask], j[mask]
        if len(h) < 3:
            binary[col] = {"n": int(len(h)), "note": "too few paired values"}
            continue
        kappa, pabak = _kappa(h.astype(bool), j.astype(bool))
        hb, jb = h.astype(bool), j.astype(bool)
        constant_notes = []
        if bool(np.all(hb == hb[0])):
            constant_notes.append(f"human constant (all {hb[0]})")
        if bool(np.all(jb == jb[0])):
            constant_notes.append(f"judge constant (all {jb[0]})")
        binary[col] = {
            "n": int(len(h)),
            "kappa": round(kappa, 4) if kappa == kappa else None,
            "pabak": round(pabak, 4) if pabak == pabak else None,
            "raw_agreement": round(float((h == j).mean()), 4),
        }
        if constant_notes:
            binary[col]["note"] = "; ".join(constant_notes)

    headline = {
        "backend": backend,
        "n": int(len(join)),
        "human_vs_judge_overall_spearman":
            ordinal.get("overall", {}).get("spearman"),
        "human_vs_judge_escalation_appropriate_kappa":
            binary.get("escalation_appropriate", {}).get("kappa"),
        "human_vs_judge_correctness_spearman":
            ordinal.get("correctness", {}).get("spearman"),
        "human_vs_judge_groundedness_spearman":
            ordinal.get("groundedness", {}).get("spearman"),
    }
    result = {
        "design": {
            "sample_n": SAMPLE_N,
            "sample_seed": SAMPLE_SEED,
            "thresholds": THRESHOLDS,
            "reviewer": "project author (single reviewer; rater/author bias "
                        "present; no inter-annotator reliability computed)",
        },
        "n_missing_judge_rows": n_missing,
        "headline": headline,
        "ordinal": ordinal,
        "binary": binary,
    }
    return result


def agree(human_csv: str, backend: str | None = None) -> dict:
    human = pd.read_csv(human_csv, dtype=str, keep_default_na=False)
    if backend is None:
        judges = sorted(OUT_DIR.glob("targeted_judge_*.csv"))
        if len(judges) == 0:
            raise SystemExit("no targeted judge outputs found; run `judge` first")
        if len(judges) != 1:
            raise SystemExit(
                f"multiple judge outputs ({[j.name for j in judges]}); "
                f"pass --backend")
        judge_df = pd.read_csv(judges[0])
    else:
        judge_df = pd.read_csv(OUT_DIR / f"targeted_judge_{backend}.csv")
    result = compute_agreement(human, judge_df)
    (OUT_DIR / "human_judge_agreement.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return result


# ---- CLI ------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_sel = sub.add_parser("select", help="build + manifest the 50-sample")
    p_sel.add_argument("--seed", type=int, default=SAMPLE_SEED)
    p_sel.add_argument("--check", action="store_true",
                       help="print population/sample composition only; no manifest")

    p_exp = sub.add_parser("export", help="write blinded reviewer form")
    p_exp.add_argument("--seed", type=int, default=SAMPLE_SEED)
    p_exp.add_argument("--manifest", type=str,
                       default=str(OUT_DIR / "review_sample_manifest.csv"))

    p_j = sub.add_parser("judge", help="targeted judge on the selected ids")
    p_j.add_argument("--backend",
                     choices=["offline", "openai", "gemini"], default="offline")
    p_j.add_argument("--manifest", type=str,
                     default=str(OUT_DIR / "review_sample_manifest.csv"))

    p_a = sub.add_parser("agree", help="human-vs-judge agreement statistics")
    p_a.add_argument("--human", required=True, help="returned human scores CSV")
    p_a.add_argument("--backend",
                     choices=["offline", "openai", "gemini"], default=None)

    return ap


def main():
    ap = build_parser()
    args = ap.parse_args()
    if args.cmd == "select":
        if args.check:
            print("population:", json.dumps(sample_population(), indent=2))
            sample = select_sample(seed=args.seed)
            print("sample escalation:", sample["human_final_escalation"]
                  .value_counts().to_dict())
            print("sample succeed/fail:",
                  int(sample["succeed"].sum()), int((~sample["succeed"]).sum()))
            print("sample borderline:",
                  int(sample["sample_slice"].eq("borderline").sum()))
            return
        select_with_manifest(seed=args.seed)
        return
    if args.cmd == "export":
        ids = pd.read_csv(args.manifest, dtype=str)["example_id"].tolist()
        form = export_form(ids, seed=args.seed)
        print(f"wrote {OUT_DIR / 'review_form_round1.csv'} "
              f"({len(form)} rows, {form.shape[1]} cols)")
        return
    if args.cmd == "judge":
        ids = pd.read_csv(args.manifest, dtype=str)["example_id"].tolist()
        out = targeted_judge(ids, backend=args.backend)
        print(f"judged {len(out)} examples -> targeted_judge_{args.backend}.csv")
        return
    if args.cmd == "agree":
        agree(args.human, backend=args.backend)
        return


if __name__ == "__main__":
    main()