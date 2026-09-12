"""LLM-as-judge harness with an explicit rubric.

Primary interface: `Judge.judge(sample) -> dict` with the mandated fields:

    correctness, groundedness, completeness, hallucination (bool),
    escalation_appropriate (bool), overall (1-5), reason.

Two implementations:
  - `OpenAIJudge`  : live LLM judge (OPENAI_API_KEY + `openai` package). Raw
                     model output is returned verbatim into results.json when
                     used. Requires explicit opt-in via env EVAL_JUDGE=openai.
  - `OfflineJudge` : deterministic, fully-reproducible fallback that implements
                     the same rubric from observable properties (evidence usage,
                     intent match, reply structure, PII/hallucination markers,
                     escalation safety). Results are ALWAYS labelled as
                     "offline" when produced this way.

Rule (honesty): live judge outputs are never simulated. If no API key is
available, the offline judge runs and the results file states so explicitly.
"""

import os
import re

from . import taxonomy
from .normalize import HALLUCINATION_MARKERS, PII_PATTERNS, redact

RUBRIC = {
    "correctness": "1-5: does the draft reply reflect the customer's actual "
                   "request (intent) and a safe routing choice?",
    "groundedness": "1-5: is every factual claim attributable to the retrieved "
                    "historical evidence or to a generic, safe template?",
    "completeness": "1-5: does the reply fully address the request / route it "
                    "actionably without leaving an unsafe gap?",
    "hallucination": "true/false: does the reply assert any unsupported policy, "
                     "refund/compensation amount, booking/account fact, or "
                     "resolution that the evidence does not support?",
    "escalation_appropriate": "true/false: is AUTO_HANDLE vs ESCALATE vs "
                              "UNCERTAIN the safe routing for this request?",
    "overall": "1-5: combined quality.",
}


class BaseJudge:
    backend = "base"

    def judge(self, sample: dict) -> dict:
        raise NotImplementedError


class OfflineJudge(BaseJudge):
    backend = "offline"

    def judge(self, sample: dict) -> dict:
        draft = sample.get("draft_reply", "")
        mode = sample.get("mode", "")
        intent_pred = sample.get("intent_predicted", "")
        intent_gold = sample.get("intent_gold", "")
        esc_pred = sample.get("escalation_predicted", "AUTO_HANDLE")
        esc_gold = sample.get("escalation_gold", "AUTO_HANDLE")
        evidence = sample.get("evidence_used", [])
        reasoning = []

        # ---- correctness (intent + routing coherence) ----------------------
        intent_ok = intent_pred == intent_gold
        correctness = 5
        if not intent_ok:
            correctness = 2
            reasoning.append("intent mismatch between prediction and gold")
        if mode == "auto_clarify":
            correctness = max(1, correctness - 1)
            reasoning.append("clarifying question used because no usable evidence")
        if esc_pred == "ESCALATE" and mode != "escalate":
            correctness = 2
            reasoning.append("escalation decision inconsistent with reply mode")

        # ---- groundedness ----------------------------------------------------
        grounded = 5
        if mode in ("escalate", "uncertain", "ack"):
            grounded = 5  # pure template routing/ack, no factual claims
        elif mode == "auto_grounded":
            sim = evidence[0].get("similarity", 0.0) if evidence else 0.0
            grounded = 4 if sim >= 0.3 else (3 if evidence else 2)
            reasoning.append(f"factual auto reply grounded on top evidence sim={sim:.2f}")
        elif mode == "auto_clarify":
            grounded = 3  # no claim made, question only
        if not evidence:
            grounded = min(grounded, 3)
            reasoning.append("no retrieved evidence available to the generator")

        # ---- completeness -----------------------------------------------------
        length = len(draft)
        neut = "Please DM us" in draft or "Could you share" in draft
        if intent_gold in ("information_or_policy", "website_or_app_issue", "baggage"):
            completeness = 5 if (mode == "auto_grounded" and length >= 60) else (
                4 if mode in ("auto_grounded", "escalate") else 2)
            if completeness <= 2:
                reasoning.append("information intent answered without factual evidence")
        else:
            completeness = 5 if length >= 40 else 4
            if neut and completeness == 5:
                completeness = 4

        # ---- hallucination -----------------------------------------------------
        has_markers = False
        low_draft = draft.lower()
        for k in HALLUCINATION_MARKERS:
            if k in low_draft:
                has_markers = True
                reasoning.append(f"hallucination marker: '{k}'")
                break
        pii_hits = [name for name, rx in PII_PATTERNS.items()
                    if rx.search(redact(draft)) and name != "mention"]
        if intent_pred in ("refund_or_compensation", "booking_change_or_cancellation",
                           "account_access_or_security") and mode == "auto_grounded":
            has_markers = has_markers or bool(pii_hits)
        hallucination = bool(has_markers)
        if has_markers:
            reasoning.append("unsupported/transactional claims in draft reply")

        # ---- escalation appropriateness (safety-first) -----------------------
        unsafe_auto = (
            esc_gold in {"ESCALATE", "UNCERTAIN"} and esc_pred == "AUTO_HANDLE")
        escalation_ok = (esc_pred == esc_gold) or unsafe_auto is False
        esc_appropriate = not unsafe_auto
        if unsafe_auto:
            reasoning.append("UNSAFE: gold routed away from AUTO_HANDLE but "
                             "predicted AUTO_HANDLE")

        # ---- overall -----------------------------------------------------------
        score = (0.30 * correctness + 0.20 * grounded + 0.15 * completeness)
        score -= 1.0 if hallucination else 0.0
        score -= 1.5 if unsafe_auto else 0.0
        score -= 0.3 if not intent_ok else 0.0
        overall = int(max(1.0, min(5.0, round(score))))

        return {
            "judge_backend": self.backend,
            "correctness": int(correctness),
            "groundedness": int(grounded),
            "completeness": int(completeness),
            "hallucination": bool(hallucination),
            "escalation_appropriate": bool(esc_appropriate),
            "overall": overall,
            "why": "; ".join(reasoning) if reasoning else "no issues detected",
        }


IS_PATTERN = re.compile(r"(intent|agency)", re.IGNORECASE)


class OpenAIJudge(BaseJudge):  # pragma: no cover - requires live key & package
    backend = "openai"

    def __init__(self, model: str = "gpt-4o-mini", api_key_env: str = "OPENAI_API_KEY"):
        import openai  # lazily imported; raises a clear error if absent

        self._openai = openai
        key = os.environ.get(api_key_env, "")
        if not key:
            raise RuntimeError(
                f"{api_key_env} is not set; refusing to run a live judge without "
                f"credentials. Use EVAL_JUDGE=offline for the reproducible run.")
        self._openai.api_key = key
        self.model = model

    def judge(self, sample: dict) -> dict:
        prompt = (
            "You are a careful evaluation judge for a customer-support assistant "
            "that drafts British Airways replies from retrieved historical "
            "evidence.\n\nRUBRIC (score each 1-5 unless Boolean):\n"
            + "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
            + "\n\nJudging rules:\n"
            "- The draft must be grounded in the retrieved evidence; grade "
            "groundedness LOW when a factual claim has no supporting evidence.\n"
            "- Untrue or unsupported policy / amounts / bookings = hallucination "
            "= true.\n"
            "- Escalation is appropriate when the request needs account data, "
            "money adjudication, identity/security, legal exposure, or human "
            "judgment, unless the safe public answer is complete.\n\n"
            "CUSTOMER MESSAGE:\n"
            f"{sample['customer_message']}\n\nRETRIEVED EVIDENCE:\n"
            + ("\n".join(f"[sim={e.get('similarity', 0.0):.2f}] {e.get('brand_reply', '')}"
                         for e in sample.get("evidence_used", [])) or "(none)")
            + "\n\nDRAFT REPLY:\n" + sample.get("draft_reply", "")
            + "\n\nPREDICTED intent=" + str(sample.get("intent_predicted"))
            + " escalation=" + str(sample.get("escalation_predicted"))
            + "\nGOLD intent=" + str(sample.get("intent_gold"))
            + " escalation=" + str(sample.get("escalation_gold"))
            + "\n\nReturn ONLY valid JSON: {\"correctness\": int, "
              "\"groundedness\": int, \"completeness\": int, \"hallucination\": bool, "
              "\"escalation_appropriate\": bool, \"overall\": int, \"reason\": str}"
        )
        resp = self._openai.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content
        import json

        data = json.loads(text)
        data["judge_backend"] = self.backend
        data["why"] = data.pop("reason", "")
        return data


def make_judge(backend: str = "offline") -> BaseJudge:
    if backend == "offline":
        return OfflineJudge()
    if backend == "openai":
        return OpenAIJudge()
    raise ValueError(f"unknown judge backend: {backend}")


def evaluate_judge_agreement_available() -> dict:
    """Human/judge agreement status with the golden-set review artifacts.

    `human_final_intent` / `human_final_escalation` are recorded (200/200 rows
    of the review). Those cover label decisions, NOT judge-response scores
    (correctness/groundedness/overall), so judge-vs-human agreement on response
    quality is still not computable; nothing is fabricated.
    """
    return {
        "agreement_computable": False,
        "reason": ("human_final_* label decisions exist but are not response-"
                   "quality ratings, so judge-vs-human agreement on response "
                   "quality is not computable"),
        "metrics_when_available": [
            "exact agreement (intent, escalation)",
            "Cohen's kappa (intent)",
            "correlation for ordinal scores (overall/correctness)",
            "agreement on grounded vs not-grounded",
            "agreement on escalation safety",
        ],
    }