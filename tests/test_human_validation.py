"""Tests for the human response-quality validation tooling.

    python -X utf8 -m unittest discover -s tests -v

Covers (no live OpenAI; no network; no corpus/model fitting):
- finalized reviewed-state guards (200 rows, 181/19 accepted, 119/75/6);
- deterministic 50-example sample + stratification composition;
- leakage protection of the exported reviewer form;
- offline targeted judge integrity vs stored predictions;
- agreement statistics on synthetic human-vs-judge data (no fabrication).
"""

import json
import pandas as pd
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation import human_validation as hv  # noqa: E402
from ba_support import paths, taxonomy  # noqa: E402


class TestReviewedStateGuards(unittest.TestCase):
    def test_population_matches_finalized_review(self):
        pop = hv.sample_population()
        self.assertEqual(pop["n"], 200)
        self.assertEqual(pop["accept"], 181)
        self.assertEqual(pop["changed"], 19)
        self.assertEqual(pop["escalation"]["AUTO_HANDLE"], 119)
        self.assertEqual(pop["escalation"]["ESCALATE"], 75)
        self.assertEqual(pop["escalation"]["UNCERTAIN"], 6)

    def test_all_sample_ids_exist_in_reviewed_and_predictions(self):
        sample = hv.select_sample()
        rev = pd.read_csv(paths.EVAL_DIR / "golden_set_reviewed.csv",
                          dtype=str)["example_id"].tolist()
        pred = pd.read_csv(paths.PREDICTIONS_CSV,
                           dtype=str)["example_id"].tolist()
        for eid in sample["example_id"]:
            self.assertIn(eid, rev)
            self.assertIn(eid, pred)


class TestSample(unittest.TestCase):
    def test_sample_is_deterministic(self):
        a = hv.select_sample(seed=2026)
        b = hv.select_sample(seed=2026)
        self.assertTrue(a["example_id"].equals(b["example_id"]))

    def test_sample_size_and_quota_consistency(self):
        sample = hv.select_sample()
        self.assertEqual(len(sample), hv.SAMPLE_N)
        self.assertEqual(sum(hv.QUOTAS.values()), hv.SAMPLE_N)
        counts = sample.groupby(["final_intent", "human_final_escalation"]).size()
        for (intent, esc), want in hv.QUOTAS.items():
            self.assertEqual(int(counts.get((intent, esc), 0)), want,
                             f"cell ({intent},{esc})")

    def test_sample_covers_all_intents_and_escalations(self):
        sample = hv.select_sample()
        self.assertEqual(set(sample["final_intent"]),
                         set(taxonomy.INTENT_LABELS))
        self.assertEqual(set(sample["human_final_escalation"]),
                         {"AUTO_HANDLE", "ESCALATE", "UNCERTAIN"})

    def test_uncertain_near_census_and_balance(self):
        sample = hv.select_sample()
        unc = int(sample["human_final_escalation"].eq("UNCERTAIN").sum())
        self.assertGreaterEqual(unc, 5)      # near-census of 6
        self.assertLessEqual(unc, 6)
        self.assertGreaterEqual(int(sample["succeed"].sum()), 10)
        self.assertGreaterEqual(int((~sample["succeed"]).sum()), 10)
        self.assertGreaterEqual(
            int(sample["sample_slice"].eq("borderline").sum()), 1)
        self.assertLessEqual(
            int(sample["sample_slice"].eq("borderline").sum()), hv.BORDERLINE_CAP)


class TestReviewForm(unittest.TestCase):
    def test_form_contains_all_required_columns_in_order(self):
        sample = hv.select_sample()
        form = hv.build_review_form(sample["example_id"].tolist())
        expect = hv.FORM_FIXED + hv.FORM_HUMAN
        self.assertEqual(list(form.columns), expect)
        self.assertEqual(len(form), hv.SAMPLE_N)

    def test_no_leakage_of_judge_gold_slice_flags(self):
        sample = hv.select_sample()
        form = hv.build_review_form(sample["example_id"].tolist())
        for col in form.columns:
            for bad in hv.FORBIDDEN:
                self.assertNotIn(bad, col.lower(), f"leaked column: {col}")

    def test_human_fields_are_blank(self):
        sample = hv.select_sample()
        form = hv.build_review_form(sample["example_id"].tolist())
        for col in hv.FORM_HUMAN:
            self.assertTrue(form[col].fillna("").eq("").all(), col)

    def test_form_order_is_shuffled_and_deterministic(self):
        ids = hv.select_sample()["example_id"].tolist()
        f1 = hv.build_review_form(ids, seed=2026)
        f2 = hv.build_review_form(ids, seed=2026)
        self.assertTrue(f1["example_id"].equals(f2["example_id"]))
        self.assertFalse(list(f1["example_id"]) == ids,
                         "form order must be shuffled vs manifest order")

    def test_form_exported_files_round_trip(self):
        sample = hv.select_sample()
        ids = sample["example_id"].tolist()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            form = hv.build_review_form(ids)
            csv = tmp / "form.csv"
            form.to_csv(csv, index=False, encoding="utf-8")
            back = pd.read_csv(csv, dtype=str, keep_default_na=False)
            self.assertEqual(list(back.columns), list(form.columns))
            self.assertEqual(len(back), hv.SAMPLE_N)
            for col in hv.FORM_FIXED:
                self.assertNotIn("", back[col].fillna(""), col)
            text = "\n".join(dict(zip(back.columns,
                                     back.iloc[0].astype(str))).values())
            for bad in hv.FORBIDDEN:
                self.assertNotIn(bad, text.lower(), f"leaked token: {bad}")


class TestTargetedJudge(unittest.TestCase):
    def test_offline_targeted_judge_matches_stored_predictions(self):
        sample = hv.select_sample()
        ids = sample["example_id"].tolist()
        out = hv.targeted_judge(ids, backend="offline")
        self.assertEqual(len(out), hv.SAMPLE_N)
        self.assertEqual(out["judge_backend"].unique().tolist(), ["offline"])
        pred = pd.read_csv(paths.PREDICTIONS_CSV,
                           dtype=str, keep_default_na=False).set_index("example_id")
        for _, r in out.iterrows():
            s = pred.loc[r["example_id"]]
            for k in ("overall", "correctness", "groundedness", "completeness"):
                self.assertEqual(int(r[f"judge_{k}"]), int(s[f"judge_{k}"]),
                                 f"{r['example_id']} {k}")
            self.assertEqual(r["judge_why"], s["judge_why"])


class TestAgreement(unittest.TestCase):
    def test_perfect_agreement_yields_expected_values(self):
        n = 50
        human = pd.DataFrame({
            "example_id": [f"BA_{i}" for i in range(n)],
            "human_overall": [3] * n,
            "human_correctness": [3] * n,
            "human_groundedness": [3] * n,
            "human_completeness": [3] * n,
            "human_hallucination": ["False"] * n,
            "human_escalation_appropriate": ["True"] * n,
        })
        judge = human.copy()
        judge.columns = [c.replace("human_", "judge_") for c in judge.columns]
        judge.rename(columns={"judge_example_id": "example_id"}, inplace=True)
        judge["judge_backend"] = "offline"
        res = hv.compute_agreement(human, judge)
        self.assertEqual(res["headline"]["backend"], "offline")
        self.assertEqual(res["headline"]["n"], n)
        self.assertEqual(res["headline"]["human_vs_judge_overall_spearman"], 1.0)
        self.assertEqual(
            res["headline"]["human_vs_judge_escalation_appropriate_kappa"], 1.0)
        for col in hv.ORDINAL_COLS:
            self.assertEqual(res["ordinal"][col]["spearman"], 1.0)
            self.assertEqual(res["ordinal"][col]["mean_abs_diff"], 0.0)
            self.assertEqual(res["ordinal"][col]["exact_agreement"], 1.0)
            self.assertEqual(res["ordinal"][col]["within_one"], 1.0)
        for col in hv.BINARY_COLS:
            self.assertEqual(res["binary"][col]["kappa"], 1.0)
            self.assertEqual(res["binary"][col]["raw_agreement"], 1.0)

    def test_series_with_no_random_variation_reports_cis(self):
        rng = __import__("numpy").random.default_rng(7)
        n = 50
        human = pd.DataFrame({
            "example_id": [f"BA_{i}" for i in range(n)],
            "human_overall": rng.integers(1, 6, size=n).astype(str),
            "human_correctness": rng.integers(1, 6, size=n).astype(str),
            "human_groundedness": rng.integers(1, 6, size=n).astype(str),
            "human_completeness": rng.integers(1, 6, size=n).astype(str),
            "human_hallucination": ["False"] * n,
            "human_escalation_appropriate": ["True"] * n,
        })
        judge = pd.DataFrame({
            "example_id": [f"BA_{i}" for i in range(n)],
            "judge_overall": [i % 5 + 1 for i in range(n)],
            "judge_correctness": [i % 5 + 1 for i in range(n)],
            "judge_groundedness": [i % 5 + 1 for i in range(n)],
            "judge_completeness": [i % 5 + 1 for i in range(n)],
            "judge_hallucination": ["False"] * n,
            "judge_escalation_appropriate": ["True"] * n,
            "judge_backend": "offline",
        })
        res = hv.compute_agreement(human, judge)
        ov = res["ordinal"]["overall"]
        self.assertIsNotNone(ov["spearman"])
        self.assertTrue(isinstance(ov["spearman_ci95"], list))
        self.assertEqual(res["headline"]["n"], n)

    def test_backend_mixing_is_rejected(self):
        n = 10
        human = pd.DataFrame({"example_id": [f"BA_{i}" for i in range(n)]})
        judge = pd.DataFrame({
            "example_id": [f"BA_{i}" for i in range(n)],
            "judge_backend": ["offline"] * (n // 2) + ["openai"] * (n // 2),
        })
        with self.assertRaises(ValueError):
            hv.compute_agreement(human, judge)

    # ---- regression: constant-rater kappa detection ----
    def test_kappa_mixed_human_constant_judge(self):
        human = [False, False, True, False, True, False, False, True,
                 False, False] * 5
        judge = [False] * 50
        self.assertEqual(len(human), len(judge))
        kappa, _ = hv._kappa(human, judge)
        self.assertEqual(kappa, 0.0)

    def test_kappa_exact_hallucination_pair(self):
        human = [False, True, True, False, False, True, True, False, False,
                 False, False, True, True, False, True, False, False, True,
                 True, False, False, False, False, False, True, False, False,
                 True, False, False, True, True, False, False, False, True,
                 True, False, True, False, True, True, False, False, False,
                 True, True, True, False, False]
        judge = [False] * 50
        self.assertEqual(len(human), len(judge))
        self.assertEqual(human.count(True), 21)
        kappa, pabak = hv._kappa(human, judge)
        self.assertAlmostEqual(kappa, 0.0, places=6)
        self.assertAlmostEqual(pabak, 0.16, places=6)
        raw = float(sum(a == b for a, b in zip(human, judge)) / len(human))
        self.assertAlmostEqual(raw, 0.58, places=6)

    def test_kappa_both_constant_equal(self):
        self.assertEqual(hv._kappa([True] * 10, [True] * 10), (1.0, 1.0))

    def test_kappa_both_constant_different(self):
        self.assertEqual(hv._kappa([True] * 10, [False] * 10), (0.0, -1.0))

    def test_kappa_exact_escalation_pair(self):
        human = [True, False, False, True, True, False, False, True, False,
                 True, True, True, True, False, False, False, False, True,
                 False, False, False, True, False, True, True, True, True,
                 True, True, True, True, True, True, True, False, True, False,
                 True, False, True, False, False, False, True, False, False,
                 True, True, True, True]
        judge = [True, True, False, False, True, True, False, True, True,
                 False, True, False, False, False, True, False, True, True,
                 True, True, True, False, True, True, False, False, True,
                 True, True, False, True, False, True, True, True, False,
                 False, False, False, False, True, True, False, True, True,
                 True, False, True, True, True]
        self.assertEqual(len(human), len(judge))
        self.assertEqual(human.count(True), 29)
        self.assertEqual(judge.count(True), 30)
        kappa, _ = hv._kappa(human, judge)
        self.assertAlmostEqual(kappa, -0.1157, places=4)
        raw = float(sum(a == b for a, b in zip(human, judge)) / len(human))
        self.assertAlmostEqual(raw, 0.46, places=6)


if __name__ == "__main__":
    unittest.main()