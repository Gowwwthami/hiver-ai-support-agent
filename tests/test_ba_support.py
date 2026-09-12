"""Unit tests for the British_Airways support-agent pipeline (stdlib unittest).

Run from the repository root:

    python -X utf8 -m unittest discover -s tests -v

Tests are designed to run from a clean checkout:
  - pure unit tests build tiny synthetic frames inline (no dataset required);
  - tests against the reconstructed conversation cache / retrieval corpus are
    skipped with a clear message when those artifacts are absent.
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ba_support import (escalation as esc_mod, evaluate as evmod,  # noqa: E402
                        generate as gen_mod, intent as intent_mod, judge as judgemod,
                        leakage, normalize, pipeline as pl, taxonomy,
                        weak)

try:
    from ba_support import corpus as corpus_mod
except Exception:  # pragma: no cover - optional import path
    corpus_mod = None

try:
    from ba_support import retrieval as ret_mod
except Exception:  # pragma: no cover
    ret_mod = None


def mini_corpus(n_per_class: int = 4) -> pd.DataFrame:
    """Deterministic synthetic weak-labelled corpus for model unit tests."""
    msgs = {
        "non_support_or_acknowledgement": ["thanks for the update", "great service today",
                                           "love british airways", "congrats on the award"],
        "complaint_or_human_assistance": ["this is a complaint about my flight",
                                          "i am very disappointed with your service",
                                          "no one is responding to me", "what a shambles"],
        "flight_disruption": ["my flight was cancelled", "we were delayed for hours",
                              "stranded at the airport", "missed connection in london"],
        "refund_or_compensation": ["i want a refund please", "i claim compensation under eu261",
                                   "give my money back", "you owe me expenses"],
        "website_or_app_issue": ["the website keeps failing", "app error on checkout",
                                 "unable to book online", "check in page is broken"],
        "information_or_policy": ["what is the baggage allowance", "how much does it cost",
                                  "when can i check in", "is my cat allowed onboard"],
        "baggage": ["my luggage is lost", "the bag did not arrive", "cabin bag too big",
                    "they lost my suitcase"],
        "booking_change_or_cancellation": ["change my booking date", "cancel my flight",
                                           "move my flight to friday", "amend my booking"],
        "seat_or_upgrade": ["can i pick a window seat", "legroom upgrade please",
                            "pre book a seat", "exit row availability"],
        "account_access_or_security": ["i cannot log in", "my account was hacked",
                                       "forgot my password", "unusual activity on account"],
    }
    rows = []
    for intent, texts in msgs.items():
        for i in range(n_per_class):
            t = texts[i % len(texts)]
            rows.append({"corpus_id": f"CR_{len(rows):05d}", "conv_id": len(rows) + 1,
                         "customer_author_id": f"cust_{len(rows) % 5:03d}",
                         "customer_msg": t,
                         "prior_context": "",
                         "brand_reply": "Thank you for contacting British Airways. Please DM us.",
                         "weak_intent": intent, "weak_confident": True})
    return pd.DataFrame(rows)


def mini_retriever() -> "ret_mod.Retriever":
    assert ret_mod is not None
    return ret_mod.Retriever(mini_corpus(6))


class TestTaxonomy(unittest.TestCase):
    def test_ten_canonical_labels(self):
        self.assertEqual(len(taxonomy.INTENT_LABELS), 10)
        self.assertEqual(len(set(taxonomy.INTENT_LABELS)), 10)
        self.assertIn("complaint_or_human_assistance", taxonomy.INTENT_LABELS)
        self.assertIn("account_access_or_security", taxonomy.INTENT_LABELS)
        self.assertNotIn("contact_or_human_escalation_request", taxonomy.INTENT_LABELS)

    def test_legacy_mapping(self):
        self.assertEqual(taxonomy.to_canonical("contact_or_human_escalation_request"),
                         "complaint_or_human_assistance")
        self.assertEqual(taxonomy.to_canonical("noise_or_off_topic_or_ack"),
                         "non_support_or_acknowledgement")
        self.assertEqual(taxonomy.to_canonical("account_or_security"),
                         "account_access_or_security")
        self.assertEqual(taxonomy.to_canonical("baggage"), "baggage")


class TestNormalize(unittest.TestCase):
    def test_normalize_lowercases_and_strips_mentions(self):
        t = normalize.normalize_text("@British_Airways Please HELP me!")
        self.assertEqual(t, "user please help me!")

    def test_tokenize_hides_pii(self):
        joined = " ".join(normalize.tokenize(
            "Call me on 07700 900123, ref A1B2C3, email a@b.co"))
        for leak in ("a1b2c3", "A1B2C3", "07700", "a@b.co", "@b"):
            self.assertNotIn(leak, joined)
        self.assertNotIn("pnr", joined.upper())

    def test_tokenize_keeps_common_words(self):
        joined = " ".join(normalize.tokenize("please refund my flight today"))
        for word in ("please", "refund", "flight"):
            self.assertIn(word, joined)

    def test_redact(self):
        out = normalize.redact("My ref UK456Q and card £500 thanks")
        self.assertNotIn("UK456Q", out)
        self.assertNotIn("500", out)

    def test_near_duplicate(self):
        self.assertTrue(normalize.is_near_duplicate(
            "my flight was cancelled", "my flight was cancelled"))
        self.assertFalse(normalize.is_near_duplicate(
            "my flight was cancelled", "i love the new seats"))

    def test_hallucination_markers_not_on_requests(self):
        self.assertTrue(normalize.HALLUCINATION_MARKERS["your booking reference is"])
        self.assertNotIn("your booking reference", normalize.HALLUCINATION_MARKERS)
        self.assertTrue("your booking reference" in normalize.redact(
            "Please DM us your booking reference."))


class TestWeak(unittest.TestCase):
    def test_single_bucket_confident(self):
        label, _, confident = weak.weak_label("I want a refund please")
        self.assertEqual(label, "refund_or_compensation")
        self.assertTrue(confident)

    def test_noise_fallback_only_when_alone(self):
        label, _, confident = weak.weak_label("thanks a lot!")
        self.assertEqual(label, "non_support_or_acknowledgement")
        self.assertTrue(confident)

    def test_ambiguous_not_confident(self):
        _, _, confident = weak.weak_label("refund my baggage claim please")
        self.assertFalse(confident)


class TestEscalation(unittest.TestCase):
    def test_security_always_escalates(self):
        d = esc_mod.decide("someone hacked my account", "non_support_or_acknowledgement", 0.9)
        self.assertEqual(d["label"], "ESCALATE")
        self.assertEqual(d["reason"], "security_or_identity")

    def test_info_auto_when_public_answer_possible(self):
        d = esc_mod.decide("what is the baggage allowance", "information_or_policy", 0.8,
                           can_handle_public=True)
        self.assertEqual(d["label"], "AUTO_HANDLE")

    def test_info_escalates_without_evidence(self):
        d = esc_mod.decide("what is the baggage allowance", "information_or_policy", 0.8,
                           can_handle_public=False)
        self.assertEqual(d["label"], "ESCALATE")
        self.assertEqual(d["reason"], "unresolved_or_insufficient_information")

    def test_refund_escalates(self):
        d = esc_mod.decide("i want a refund for my cancelled flight", "refund_or_compensation", 0.7)
        self.assertEqual(d["label"], "ESCALATE")

    def test_ack_is_auto(self):
        d = esc_mod.decide("thanks for the quick reply", "non_support_or_acknowledgement", 0.9)
        self.assertEqual(d["label"], "AUTO_HANDLE")

    def test_lawsuit_escalates_regardless_of_intent(self):
        msg = "I'm filing a lawsuit against you guys. Where should I have my lawyer send the paperwork?"
        for intent in taxonomy.INTENT_LABELS:
            d = esc_mod.decide(msg, intent, 0.9)
            self.assertEqual(d["label"], "ESCALATE", intent)
            self.assertEqual(d["reason"], "legal_or_regulatory_risk", intent)

    def test_legal_or_regulatory_threat_escalates(self):
        for msg in ["this is a legal issue and I will take statutory action",
                    "my lawyer is preparing a small claims case",
                    "the court will hear about this",
                    "we will sue you under regulation 261"]:
            d = esc_mod.decide(msg, "website_or_app_issue", 0.9)
            self.assertEqual(d["label"], "ESCALATE", msg)
            self.assertEqual(d["reason"], "legal_or_regulatory_risk", msg)

    def test_security_compromise_escalates_any_intent(self):
        d = esc_mod.decide("someone else logged into my account", "information_or_policy", 0.9)
        self.assertEqual(d["label"], "ESCALATE")
        self.assertEqual(d["reason"], "security_or_identity")

    def test_ordinary_policy_question_still_auto(self):
        d = esc_mod.decide("what is the baggage allowance", "information_or_policy", 0.8,
                           can_handle_public=True)
        self.assertEqual(d["label"], "AUTO_HANDLE")

    def test_issue_and_courtesy_not_read_as_legal(self):
        d1 = esc_mod.decide("there is still an issue doing online checkin",
                            "website_or_app_issue", 0.9)
        d2 = esc_mod.decide("always good to see this view, courtesy of a smooth flight",
                            "non_support_or_acknowledgement", 0.9)
        self.assertEqual(d1["label"], "AUTO_HANDLE")
        self.assertEqual(d2["label"], "AUTO_HANDLE")

    def test_ordinary_complaint_behavior_unchanged(self):
        worst = esc_mod.decide("worst airline experience ever",
                               "complaint_or_human_assistance", 0.9)
        self.assertEqual(worst["label"], "ESCALATE")
        self.assertEqual(worst["reason"], "complaint_or_human_judgment")
        plain = esc_mod.decide("thanks for your reply",
                               "complaint_or_human_assistance", 0.9)
        self.assertEqual(plain["label"], "AUTO_HANDLE")


class TestGenerate(unittest.TestCase):
    def test_evidence_answer(self):
        out = gen_mod.generate(
            "what is the baggage allowance", "information_or_policy", 0.9,
            {"label": "AUTO_HANDLE", "reason": ""},
            [{"similarity": 0.4, "brand_reply": "Our Economy baggage allowance is one "
                                               "23kg bag. Please DM us for more."}],
            use_evidence=True, escalation_aware=True)
        self.assertEqual(out["mode"], "auto_grounded")
        self.assertIn("23kg", out["draft_reply"])
        self.assertNotIn("DM us", out["draft_reply"])  # routing tail not copied as answer

    def test_escalate_states_routing_only(self):
        out = gen_mod.generate(
            "i want a refund", "refund_or_compensation", 0.7,
            {"label": "ESCALATE", "reason": "payment_or_refund"},
            [{"similarity": 0.4, "brand_reply": "refund processed"}],
            use_evidence=True, escalation_aware=True)
        self.assertEqual(out["mode"], "escalate")
        self.assertIn("DM us", out["draft_reply"])
        self.assertNotIn("processed", out["draft_reply"].lower())

    def test_no_fabricated_facts(self):
        for msg, intent, esc in [
            ("how long is the delay", "flight_disruption", {"label": "AUTO_HANDLE", "reason": ""}),
            ("i want compensation", "refund_or_compensation",
             {"label": "ESCALATE", "reason": "compensation"}),
        ]:
            out = gen_mod.generate(msg, intent, 0.8, esc,
                                   [{"similarity": 0.5, "brand_reply": "we are sorry"}],
                                   use_evidence=True, escalation_aware=True)
            low = out["draft_reply"].lower()
            for marker in normalize.HALLUCINATION_MARKERS.values():
                self.assertNotIn(marker, low,
                                 f"{marker!r} must not appear in a draft for {intent}")


class TestIntent(unittest.TestCase):
    def setUp(self):
        self.corpus = mini_corpus(4)

    def test_majority_predicts_majority_class(self):
        m = intent_mod.MajorityBaseline(self.corpus)
        p = m.predict_with_confidence(["help me please"])[0]
        self.assertIn(p["predicted_intent"], taxonomy.INTENT_LABELS)

    def test_rule_baseline_uses_bucket(self):
        m = intent_mod.RuleKeywordBaseline(self.corpus)
        p = m.predict_with_confidence(["please refund my flight now"])[0]
        self.assertEqual(p["predicted_intent"], "refund_or_compensation")

    def test_hybrid_uses_rule(self):
        m = intent_mod.HybridMainClassifier(self.corpus)
        p = m.predict_with_confidence(["i want a refund please"])[0]
        self.assertEqual(p["predicted_intent"], "refund_or_compensation")
        self.assertTrue(0.0 <= p["confidence"] <= 1.0)

    def test_lr_predict_schema(self):
        m = intent_mod.TfidfLRBaseline(self.corpus)
        p = m.predict_with_confidence(["my baggage is lost"])[0]
        self.assertIn(p["predicted_intent"], taxonomy.INTENT_LABELS)
        self.assertTrue(0.0 <= p["confidence"] <= 1.0)
        self.assertTrue(len(p["top_k"]) >= 1)

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            lr = intent_mod.TfidfLRBaseline(self.corpus)
            hy = intent_mod.HybridMainClassifier(self.corpus)
            lr_path = Path(d) / "lr.joblib"
            hy_path = Path(d) / "hy.joblib"
            lr.save(lr_path)
            hy.save(hy_path)
            lr2 = intent_mod.TfidfLRBaseline.load(lr_path)
            hy2 = intent_mod.HybridMainClassifier.load(hy_path)
            for t in ["my flight was cancelled", "i want a refund"]:
                a = lr.predict_with_confidence([t])[0]["predicted_intent"]
                b = lr2.predict_with_confidence([t])[0]["predicted_intent"]
                self.assertEqual(a, b)
                self.assertEqual(
                    hy.predict_with_confidence([t])[0]["predicted_intent"],
                    hy2.predict_with_confidence([t])[0]["predicted_intent"])


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.retriever = mini_retriever()

    def test_search_schema_and_ordering(self):
        hits = self.retriever.search("i want a refund please", top_k=3)
        self.assertLessEqual(len(hits), 3)
        sims = [h["similarity"] for h in hits]
        self.assertEqual(sims, sorted(sims, reverse=True))
        for h in hits:
            self.assertIn("conv_id", h)
            self.assertIn("brand_reply", h)
            self.assertIn("weak_intent", h)

    def test_excludes_query_conv_and_customer(self):
        hits = self.retriever.search(
            "i want a refund please", top_k=5, query_conv_id=-999,
            query_customer="customerc")
        for h in hits:
            self.assertNotEqual(int(h["conv_id"]), -999)
            self.assertNotEqual(h["customer_msg"], h["customer_msg"] + "x")

    def test_intent_filter(self):
        rows = []
        for intent, texts in {
            "refund_or_compensation": ["i want a refund please",
                                       "please process my refund",
                                       "refund for my ticket",
                                       "i need the refund soon",
                                       "claiming the refund now",
                                       "refund owed to me"],
            "account_access_or_security": ["account hacked", "login failed",
                                           "reset my password"],
        }.items():
            for t in texts:
                rows.append({"corpus_id": f"CR_{len(rows):04d}", "conv_id": len(rows) + 1,
                             "customer_author_id": "cust_a", "customer_msg": t,
                             "prior_context": "", "brand_reply": "reply",
                             "weak_intent": intent, "weak_confident": True})
        ret = ret_mod.Retriever(pd.DataFrame(rows))
        hits = ret.search("i want a refund please", top_k=2,
                          intent_filter="refund_or_compensation")
        self.assertTrue(hits)
        for h in hits:
            self.assertEqual(h["weak_intent"], "refund_or_compensation")


class TestPipeline(unittest.TestCase):
    def test_pipeline_contract_and_ablations(self):
        model = intent_mod.RuleKeywordBaseline(mini_corpus(5))
        retriever = mini_retriever()
        judge = judgemod.make_judge("offline")
        for label, cfg in [
            ("A_classifier_only", dict(use_evidence=False, grounded=True, escalation_aware=True)),
            ("B_classifier_retrieval", dict(use_evidence=True, grounded=False, escalation_aware=False)),
            ("C_grounded_generation", dict(use_evidence=True, grounded=True, escalation_aware=False)),
            ("D_full", dict(use_evidence=True, grounded=True, escalation_aware=True)),
        ]:
            pline = pl.Pipeline(model, retriever, pl.Config(**cfg))
            self.assertEqual(pline.config.label(), label)
            pred = pline.run("please refund my cancelled flight",
                             conv_id=-1, customer_author_id="me")
            for key in ("intent", "intent_confidence", "escalation", "draft_reply",
                        "evidence", "reply_mode", "escalation_reason"):
                self.assertIn(key, pred)
            self.assertIn(pred["intent"], taxonomy.INTENT_LABELS)
            self.assertIn(pred["escalation"],
                          taxonomy.ESCALATION_LABELS + ["AUTO_HANDLE"])
            j = judge.judge(pl.assemble_sample(pred, {
                "customer_message": "please refund my cancelled flight",
                "intent": "refund_or_compensation",
                "escalation_label": "ESCALATE",
                "example_id": "BA_-1",
            }, judge))
            self.assertEqual(j["judge_backend"], "offline")


class TestEvaluate(unittest.TestCase):
    def test_classification_metrics(self):
        y_true = ["a", "a", "b"]
        y_pred = ["a", "a", "a"]
        m = evmod.classification_metrics(y_true, y_pred, labels=["a", "b"])
        self.assertAlmostEqual(m["accuracy"], round(2 / 3, 4), places=4)
        self.assertEqual(len(m["per_class"]), 2)
        self.assertEqual(m["confusion_matrix"]["labels"], ["a", "b"])
        self.assertIn("macro_f1", m)

    def test_escalation_safety_metrics(self):
        m = evmod.escalation_metrics(["ESCALATE", "AUTO_HANDLE"],
                                     ["AUTO_HANDLE", "AUTO_HANDLE"])
        self.assertEqual(m["n_false_auto_handle"], 1)
        self.assertAlmostEqual(m["false_auto_handle_rate"], 0.5)

    def test_aggregate_judge(self):
        js = [{"correctness": 5, "groundedness": 4, "completeness": 5,
               "overall": 5, "hallucination": False, "escalation_appropriate": True,
               "judge_backend": "offline"}] * 2
        agg = evmod.aggregate_judge(js)
        self.assertEqual(agg["overall"], 5.0)
        self.assertEqual(agg["hallucination_rate"], 0.0)
        self.assertEqual(agg["judge_backends_used"], {"offline": 2})

    def test_imbalance_summary(self):
        s = evmod.imbalance_summary(["a"] * 10 + ["b"])
        self.assertEqual(s["counts"]["a"], 10)
        self.assertEqual(s["share_max_over_min"], 10.0)

    def test_dump_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            evmod.dump_results({"x": 1, "n": np.int64(42)}, p)
            self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["n"], "42")


class TestJudge(unittest.TestCase):
    def test_auto_grounded_with_good_evidence(self):
        j = judgemod.OfflineJudge().judge({
            "draft_reply": "Our allowance is one 23kg bag. Thanks for asking.",
            "mode": "auto_grounded", "intent_predicted": "information_or_policy",
            "intent_gold": "information_or_policy",
            "escalation_predicted": "AUTO_HANDLE", "escalation_gold": "AUTO_HANDLE",
            "evidence_used": [{"similarity": 0.5, "brand_reply": "one 23kg bag"}],
        })
        self.assertEqual(j["hallucination"], False)
        self.assertGreaterEqual(j["groundedness"], 3)

    def test_unsafe_auto_flagged(self):
        j = judgemod.OfflineJudge().judge({
            "draft_reply": "Thanks for reaching out.",
            "mode": "auto_grounded", "intent_predicted": "complaint_or_human_assistance",
            "intent_gold": "complaint_or_human_assistance",
            "escalation_predicted": "AUTO_HANDLE", "escalation_gold": "ESCALATE",
            "evidence_used": [{"similarity": 0.5, "brand_reply": "we are sorry"}],
        })
        self.assertFalse(j["escalation_appropriate"])
        self.assertIn("UNSAFE", j["why"])

    def test_agreement_not_fabricated(self):
        info = judgemod.evaluate_judge_agreement_available()
        self.assertFalse(info["agreement_computable"])


class TestLeakage(unittest.TestCase):
    def test_golden_panel_shape(self):
        panel = leakage.golden_panel()
        self.assertEqual(len(panel), 200)
        self.assertEqual(panel["example_id"].nunique(), 200)

    def test_golden_conv_ids(self):
        ids = leakage.golden_conv_ids()
        self.assertEqual(len(ids), 200)
        self.assertIn(358073, ids)

    def test_audit_pool_not_in_golden(self):
        audit = leakage.audit_conv_ids()
        overlap = audit & leakage.golden_conv_ids()
        self.assertEqual(overlap, set())


@unittest.skipUnless(corpus_mod and (ROOT / "analysis" / "cache" / "retrieval_corpus.parquet").exists(),
                     "retrieval corpus cache not built yet")
class TestCorpus(unittest.TestCase):
    def setUp(self):
        self.corpus = corpus_mod.load_corpus()

    def test_schema(self):
        for c in ("conv_id", "corpus_id", "customer_msg", "brand_reply",
                  "weak_intent", "weak_confident", "customer_author_id",
                  "normalized_msg"):
            self.assertIn(c, self.corpus.columns)

    def test_weak_intent_canonical(self):
        unknown = set(self.corpus["weak_intent"].unique()) - set(
            taxonomy.INTENT_LABELS) - {"other"}
        self.assertEqual(unknown, set())

    def test_no_golden_conversations(self):
        self.assertTrue(leakage.is_golden_isolated(self.corpus))

    def test_no_golden_customers(self):
        stats = leakage.customer_isolation_stats(self.corpus)
        self.assertEqual(stats["golden_customer_share_rows"], 0)


class TestHumanReviewScript(unittest.TestCase):
    def test_review_metrics_functions(self):
        script = ROOT / "analysis" / "scripts" / "apply_human_review.py"
        spec = importlib.util.spec_from_file_location("apply_human_review", script)
        mod = importlib.util.module_from_spec(spec)
        # import its dependencies without executing main()
        sys.argv = ["apply_human_review.py"]
        spec.loader.exec_module(mod)
        m = mod.intent_error_rate(["a", "b", "b"], ["a", "b", "a"])
        self.assertAlmostEqual(m["draft_error_rate"], round(1 / 3, 4), places=4)
        e = mod.escalation_metrics(["AUTO_HANDLE", "AUTO_HANDLE"],
                                   ["ESCALATE", "AUTO_HANDLE"])
        self.assertEqual(e["n_draft_auto_on_human_escalate"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)