"""Finalize the canonical golden set from the recorded human-final labels.

Phase 2.1 recorded the author's final (human) label decisions for all 200 rows
in `evaluation/golden_set_reviewed.csv` (`human_final_intent`,
`human_final_escalation`). This script promotes those decisions to the
canonical gold:

  * `intent`            = the human-final intent, stored under the repo-wide
                          legacy spellings (the three Phase-2.1 renamed classes
                          are stored via their legacy aliases and mapped at
                          eval time by `ba_support/taxonomy.to_canonical`), so
                          the shipped file keeps the documented legacy-enum
                          schema that `validate_golden_set.py` enforces.
  * `escalation_label`  = the human-final escalation decision.
  * `escalation_reason` = "" for AUTO_HANDLE; for ESCALATE/UNCERTAIN the prior
                          reason is kept when it was already non-empty, else the
                          note-grounded reason for the 7 rows that the review
                          moved AUTO_HANDLE -> ESCALATE/UNCERTAIN (see
                          MOVED_TO_ESC below, each grounded in human_notes).

Every other column is preserved exactly. `golden_set.jsonl` is rewritten to the
identical records so the two deliverables stay in lock-step. The original
assistant-drafted labels are preserved unchanged in `evaluation/_labels.tsv`,
`evaluation/golden_set_review_queue.csv` and
`evaluation/golden_set_recommendations.pre_human_review_backup.csv`.

Guard rails: only the three label columns may change; enum + cross-field rules
mirror `validate_golden_set.py`; and the post-transformation distributions must
match the human-recorded distributions. Re-running on an already-finalized file
is a no-op (idempotent).
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation"
GOLDEN_CSV = EVAL / "golden_set.csv"
GOLDEN_JSONL = EVAL / "golden_set.jsonl"
REVIEWED_CSV = EVAL / "golden_set_reviewed.csv"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis" / "scripts"))

from _taxonomy import ESCALATION_REASONS, INTENT_LABELS, ESCALATION_LABELS  # noqa: E402
from ba_support import taxonomy  # noqa: E402

# Canonical -> legacy (the inverse of taxonomy.LEGACY_TO_CANONICAL).
CANONICAL_TO_LEGACY = {v: k for k, v in taxonomy.LEGACY_TO_CANONICAL.items()}

# Escalation reasons for the 7 rows the human review moved AWAY from
# AUTO_HANDLE. Each is grounded in the reviewer's recorded
# `human_final_reason` (and `human_notes`) of golden_set_reviewed.csv:
#   BA_154364/BA_255518/BA_630270/BA_634124/BA_765259 -> account_specific
#     ("changing one passenger's return date is booking-specific", "wants to
#      change an international flight date", "name transfer/cancellation",
#      "£300 charge require account-specific handling", "cancellation of a
#      specific booking requires account action").
#   BA_51492/BA_783910 -> UNCERTAIN for lack of context ("passenger/boarding
#     situation lacks enough context to safely answer", "cannot determine what
#     EUR 50 refers to").
MOVED_TO_ESC = {
    "BA_154364": "account_specific",
    "BA_255518": "account_specific",
    "BA_630270": "account_specific",
    "BA_634124": "account_specific",
    "BA_765259": "account_specific",
    "BA_51492": "unresolved_or_insufficient_information",
    "BA_783910": "unresolved_or_insufficient_information",
}

CHANGEABLE = {"intent", "escalation_label", "escalation_reason"}


def reason_for(label, old_reason, example_id):
    if label == "AUTO_HANDLE":
        return ""
    if old_reason:
        return old_reason
    try:
        return MOVED_TO_ESC[example_id]
    except KeyError:
        raise SystemExit(
            f"FATAL: {example_id} final escalation={label} has no reason; "
            "add it to MOVED_TO_ESC (grounded in human_notes).") from None


def write_jsonl(out: pd.DataFrame) -> None:
    """Write golden_set.jsonl, preserving the original records' key order and
    scalar types: only intent / escalation_label / escalation_reason are
    overlaid with the finalized (string) values; every other field keeps its
    existing representation so the file stays byte-stable for unchanged rows."""
    overlay = {"intent": "intent", "escalation_label": "escalation_label",
               "escalation_reason": "escalation_reason"}
    if GOLDEN_JSONL.exists():
        old = [json.loads(l) for l in
               GOLDEN_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
        by_id = {r["example_id"]: r for r in old}
        if len(old) == len(out) and set(by_id) == set(out["example_id"]):
            new = []
            for _, row in out.iterrows():
                rec = dict(by_id[row["example_id"]])
                for k, src in overlay.items():
                    rec[k] = row[src]
                new.append(rec)
            GOLDEN_JSONL.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in new),
                encoding="utf-8")
            return
    # fallback: full regenerate from the CSV (identical records, string scalars)
    GOLDEN_JSONL.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out.to_dict("records")),
        encoding="utf-8")


def main():
    gold = pd.read_csv(GOLDEN_CSV, dtype=str, keep_default_na=False)
    rev = pd.read_csv(REVIEWED_CSV, dtype=str, keep_default_na=False)

    if len(gold) != 200 or len(rev) != 200:
        raise SystemExit(f"FATAL: expected 200 rows, got {len(gold)}/{len(rev)}")
    if set(gold["example_id"]) != set(rev["example_id"]):
        raise SystemExit("FATAL: example_id sets differ between golden and reviewed")

    human = rev.set_index("example_id")[
        ["human_final_intent", "human_final_escalation", "human_notes"]]

    old_intent = gold["intent"].map(taxonomy.to_canonical)
    old_esc = gold["escalation_label"]
    new_intent, new_esc, new_reason, changed_ids = [], [], [], set()
    for _, row in gold.iterrows():
        hid = row["example_id"]
        h = human.loc[hid]
        ci = CANONICAL_TO_LEGACY.get(h["human_final_intent"], h["human_final_intent"])
        if ci not in INTENT_LABELS:
            raise SystemExit(f"FATAL: {hid} intent {ci!r} not in legacy enums")
        if h["human_final_escalation"] not in ESCALATION_LABELS:
            raise SystemExit(f"FATAL: {hid} escalation {h['human_final_escalation']!r} not in enums")
        esc = h["human_final_escalation"]
        reason = reason_for(esc, row["escalation_reason"], hid)
        if reason and reason not in ESCALATION_REASONS:
            raise SystemExit(f"FATAL: {hid} reason {reason!r} not in escalation-taxonomy enums")
        new_intent.append(ci)
        new_esc.append(esc)
        new_reason.append(reason)
        if ci != row["intent"] or esc != row["escalation_label"] or reason != row["escalation_reason"]:
            changed_ids.add(hid)

    out = gold.copy()
    out["intent"] = new_intent
    out["escalation_label"] = new_esc
    out["escalation_reason"] = new_reason

    # ---- guard rails ----------------------------------------------------------
    for c in out.columns:
        if c not in CHANGEABLE and not gold[c].equals(out[c]):
            raise SystemExit(f"FATAL: column {c} changed - not allowed")
    for _, r in out.iterrows():
        if r["escalation_label"] == "AUTO_HANDLE" and r["escalation_reason"] != "":
            raise SystemExit(f"FATAL: {r['example_id']} AUTO_HANDLE with reason")
        if r["escalation_label"] in ("ESCALATE", "UNCERTAIN") and r["escalation_reason"] == "":
            raise SystemExit(f"FATAL: {r['example_id']} {r['escalation_label']} with empty reason")
        if r["noise_flag"] == "TRUE" and r["intent"] != "noise_or_off_topic_or_ack":
            raise SystemExit(f"FATAL: {r['example_id']} noise_flag TRUE but intent={r['intent']}")

    # post-state must equal the human-recorded distributions
    exp_intent = rev["human_final_intent"].map(
        lambda x: CANONICAL_TO_LEGACY.get(x, x)).value_counts().sort_index()
    if not out["intent"].value_counts().sort_index().equals(exp_intent):
        raise SystemExit("FATAL: final intent distribution != human-recorded\n"
                         f"got\n{out['intent'].value_counts().sort_index()}\nwant\n{exp_intent}")
    exp_esc = rev["human_final_escalation"].value_counts().sort_index()
    if not out["escalation_label"].value_counts().sort_index().equals(exp_esc):
        raise SystemExit("FATAL: final escalation distribution != human-recorded")

    # ---- write (LF line endings; git autocrlf normalizes on checkout) ---------
    out.to_csv(GOLDEN_CSV, index=False, encoding="utf-8")
    write_jsonl(out)

    # ---- summary --------------------------------------------------------------
    n_i = int((old_intent != out["intent"].map(taxonomy.to_canonical)).sum())
    n_e = int((old_esc != out["escalation_label"]).sum())
    n_to_esc = sum(1 for e in ("BA_154364", "BA_255518", "BA_630270",
                               "BA_634124", "BA_765259", "BA_51492",
                               "BA_783910") if e in changed_ids)
    print(f"Wrote {GOLDEN_CSV.name} / {GOLDEN_JSONL.name} ({len(out)} rows)")
    print(f"rows changed: {len(changed_ids)}  "
          f"(intent {n_i}, escalation {n_e}, {n_to_esc} newly-ESCALATE/UNCERTAIN reasons set)")
    print("--- final intent (legacy stored -> canonical) ---")
    cd = out["intent"].map(taxonomy.to_canonical).value_counts()
    for v in taxonomy.INTENT_ORDER:
        n = int(cd.get(v, 0))
        if n:
            print(f"  {v:38} {n}")
    print("--- final escalation ---")
    print(dict(out["escalation_label"].value_counts().sort_index()))


if __name__ == "__main__":
    main()