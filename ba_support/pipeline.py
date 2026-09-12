"""End-to-end single-example predictor.

Order of operations (full system):

    customer message
      -> intent classifier (predicted_intent, confidence, top-k)
      -> historical retrieval (leakage-filtered evidence)
      -> escalation policy (using predicted intent + evidence sufficiency)
      -> evidence-grounded generation (escalation-aware)
      -> offline/live judge (outside this module, in run_eval)

The output dict matches the required structured JSON contract:

    {"intent", "escalation", "escalation_reason", "draft_reply", "evidence"}
"""

from . import escalation as esc_mod
from . import generate as gen_mod
from . import paths, taxonomy


class Config:
    def __init__(self, use_evidence: bool = True, intent_filter: bool = True,
                 escalation_aware: bool = True, grounded: bool = True,
                 top_k: int = paths.DEFAULT_TOP_K,
                 semantic: bool = False, judge_backend: str = "offline"):
        self.use_evidence = use_evidence
        self.intent_filter = intent_filter
        self.escalation_aware = escalation_aware
        self.grounded = grounded
        self.top_k = top_k
        self.semantic = semantic
        self.judge_backend = judge_backend

    def label(self) -> str:
        if not self.use_evidence:
            return "A_classifier_only"
        if not self.grounded:
            return "B_classifier_retrieval"
        if self.escalation_aware:
            return "D_full"
        return "C_grounded_generation"


class Pipeline:
    def __init__(self, model, retriever, config: Config | None = None):
        self.model = model
        self.retriever = retriever
        self.config = config or Config()

    def run(self, customer_message: str, conv_id: int | None = None,
            customer_author_id: str | None = None) -> dict:
        cfg = self.config
        intent_out = self.model.predict_with_confidence([customer_message])[0]
        predicted_intent = intent_out["predicted_intent"]
        confidence = intent_out["confidence"]

        evidence = []
        if cfg.use_evidence:
            intent_filter = predicted_intent if cfg.intent_filter else None
            evidence = self.retriever.search(
                customer_message, top_k=cfg.top_k,
                query_conv_id=conv_id, query_customer=customer_author_id,
                intent_filter=intent_filter,
                exclude_near_duplicates=True,
            )

        can_handle_public = len(evidence) > 0 and evidence[0]["similarity"] >= paths.MIN_EVIDENCE_SIMILARITY
        decision = esc_mod.decide(
            customer_message, predicted_intent, confidence,
            can_handle_public=can_handle_public or not cfg.use_evidence)

        gen = gen_mod.generate(
            customer_message, predicted_intent, confidence, decision, evidence,
            use_evidence=cfg.grounded,
            escalation_aware=cfg.escalation_aware,
            min_similarity=paths.MIN_EVIDENCE_SIMILARITY)

        return {
            "intent": predicted_intent,
            "intent_confidence": round(float(confidence), 4),
            "top_k_intents": intent_out["top_k"],
            "intent_evidence": intent_out["evidence"],
            "escalation": decision["label"],
            "escalation_reason": decision["reason"],
            "escalation_policy_note": decision["policy_debug"],
            "draft_reply": gen["draft_reply"],
            "reply_mode": gen["mode"],
            "evidence": [
                {"rank": e["rank"], "similarity": round(float(e["similarity"]), 4),
                 "conv_id": int(e["conv_id"]), "weak_intent": e["weak_intent"],
                 "brand_reply": e["brand_reply"]}
                for e in evidence[:cfg.top_k]
            ],
            "evidence_used": gen["evidence_used"],
        }


def assemble_sample(pred: dict, example: dict, judge: object) -> dict:
    """Build the judge input for one example (prediction + gold + evidence)."""
    return {
        "customer_message": example["customer_message"],
        "draft_reply": pred["draft_reply"],
        "reply_mode": pred["reply_mode"],
        "mode": pred["reply_mode"],
        "intent_predicted": pred["intent"],
        "intent_gold": example["intent"],
        "escalation_predicted": pred["escalation"],
        "escalation_gold": example["escalation_label"],
        "evidence_used": pred["evidence_used"] or [
            {"brand_reply": e["brand_reply"], "similarity": e["similarity"]}
            for e in pred["evidence"][:2]
        ],
        "example_id": example["example_id"],
    }