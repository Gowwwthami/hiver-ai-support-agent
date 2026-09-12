"""Phase-2 golden-set candidate worksheet builder (British_Airways).

Deterministic, single-script sampling front-end for the manual annotation pass.

Inputs:
  analysis/cache/conversations.parquet / conversation_summary.parquet
  analysis/candidate_conversations/British_Airways.md   (audit-sample exclusion)

Outputs:
  evaluation/_candidates_worksheet.csv  200 candidate rows (labels blank)
  analysis/golden_sampling_summary.json pool sizes, quotas, seeds, env

Design notes (documented in PHASE2_REPORT.md):
  * One customer message per BA conversation -> one golden example (the
    conversation-level split integrity is guaranteed by construction).
  * ~85% of targets are the FIRST inbound message of the conversation;
    ~15% are a later inbound message (conversation-continuity slice).
  * The 50 conversations already used for the Phase-1 qualitative audit are
    EXCLUDED (taxonomy-motivation sample must not also be a gold-set example).
  * Keyword buckets are SAMPLING PRIORS only -- they are NOT ground-truth
    intent labels. Labels come from the manual annotation pass.
  * Stratified quota allocation (proportional to the eligible pool with
    floors for rare intents + a controlled borderline slice).
"""
import json
import os
import random
import re
import sys

import pandas as pd
import duckdb

SEED = 2026
TARGET_N = 200
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "analysis", "cache")
AUDIT_MD = os.path.join(BASE, "analysis", "candidate_conversations", "British_Airways.md")
EVAL_DIR = os.path.join(BASE, "evaluation")
ANALYSIS = os.path.join(BASE, "analysis")
os.makedirs(EVAL_DIR, exist_ok=True)

BRAND = "British_Airways"

# ---------------------------------------------------------------------------
# heuristic sampling buckets (PRIORS, not labels)
# ---------------------------------------------------------------------------
PRIORS = [
    ("account_or_security", [r"account", r"hack", r"password", r"\blog in\b", r"login",
                             r"sign in", r"fraud", r"unauthor[isz]", r"suspicious",
                             r"\bsecurity\b", r"identity", r"theft", r"scam",
                             r"someone else", r"not mine"]),
    ("baggage", [r"\bbag(s|gage)?\b", r"luggage", r"suitcase", r"cabin case", r"hold bag",
                 r"checked bag", r"stroller", r"pram", r"\bcase\b", r"lost baggage"]),
    ("seat_or_upgrade", [r"\bseat(s)?\b", r"legroom", r"leg room", r"exit row", r"upgrade",
                         r"pre-?book", r"bassinet", r"aisle", r"window seat", r"sit together",
                         r"seat reservation", r"extra leg"]),
    ("refund_or_compensation", [r"refund", r"compen[sz]", r"reimburs", r"money back",
                                r"\bcredit\b", r"charge[ds]?", r"\bfees?\b", r"\bowe\b",
                                r"expenses", r"discount", r"voucher", r"avios"]),
    ("website_or_app_issue", [r"website", r"web ?site", r"\bsite\b", r"\bapp\b", r"online",
                              r"manage my booking", r"\berror", r"\bfailed\b", r"unable to book",
                              r"can'?t (book|check in|log)", r"book a flight", r"booking reference",
                              r"\bpage\b", r"loads? (slow|not)", r"check in (online|on the app)",
                              r"otter", r"login", r"sign in"]),
    ("flight_disruption", [r"cancelled?", r"delayed?", r"\bdelay\b", r"diversion", r"diverted",
                           r"stranded", r"\bstuck\b", r"overbooked", r"stand-?by", r"rebook",
                           r"re-?route", r"alternative flight", r"next flight", r"missed (my )?flight",
                           r"missed connection", r"waiting (since|for)", r"hours (at|in)"]),
    ("booking_change_or_cancellation", [r"change my", r"change the (date|flight|name)", r"amend",
                                        r"date change", r"\bswap\b", r"switch (my |the )?",
                                        r"move my", r"change flight", r"different flight", r"\bflexible",
                                        r"name change", r"change of name", r"cancel",
                                        r"can I transfer", r"transfer my", r"postpone"]),
    ("contact_or_complaint", [r"complaint", r"complain", r"\bcontact\b", r"\bemail\b", r"phone",
                              r"\bcall\b", r"speak to", r"talk to", r"\bhuman\b", r"no response",
                              r"ignore", r"customer relations?", r"direct message", r"\bdm\b",
                              r"case (number|id)", r"worst", r"awful", r"appalling", r"disgusting",
                              r"refuse", r"no one", r"help me", r"still waiting"]),
    ("information_or_policy", [r"how (do |can |to |much )", r"what( is|'s| are| time| the)",
                               r"when (is|do|will|can)", r"\bpolicy", r"allow", r"requirements?",
                               r"is it possible", r"do you (offer|provide|allow|have)",
                               r"information", r"please advise", r"tell me", r"know if",
                               r"how many", r"what's the", r"is there", r"\bcost\b", r"price"]),
    ("noise_or_off_topic", [r"thank", r"\blove\b", r"\bgreat\b", r"amazing", r"awesome",
                            r"fantastic", r"wonderful", r"brilliant", r"haha", r"\blol\b",
                            r"😂", r"🤣", r"👍", r"👏", r"🙌", r"❤", r"😍", r"🎉", r"🛫", r"🛬",
                            r"✈", r"congrats", r"fan of", r"favourite airline", r"favorite airline",
                            r"glad", r"delighted", r"enjoy your", r"fabulous", r"safe flight",
                            r"best flight", r"good luck"]),
]
PRIOR_ORDER = [p[0] for p in PRIORS]


def bucket_for(text: str):
    low = text.lower()
    hits = []
    for name, pats in PRIORS:
        if any(re.search(p, low) for p in pats):
            hits.append(name)
    if not hits:
        return "other", ["other"]
    return hits[0], hits


def allocate_quotas(pop, total, floors):
    """Proportional allocation with floors; exactly `total`. Deterministic."""
    buckets = sorted(pop.keys())
    psum = max(sum(pop.values()), 1)
    res = {}
    for b in buckets:
        res[b] = int(pop[b] / psum * total)

    for b in buckets:
        floor = min(floors.get(b, 0), pop[b])
        if res[b] < floor:
            res[b] = floor

    share = {b: pop[b] / psum for b in buckets}
    diff = total - sum(res.values())
    it = 0
    while diff != 0 and it < 10000:
        it += 1
        if diff > 0:
            order = sorted(buckets, key=lambda b: (-share[b], b))
            for b in order:
                if res[b] < pop[b]:
                    res[b] += 1
                    diff -= 1
                    break
        else:
            order = sorted(buckets, key=lambda b: (res[b] - floors.get(b, 0), b))
            for b in order:  # cut where slack is largest
                if res[b] > floors.get(b, 0) and res[b] > 0:
                    res[b] -= 1
                    diff += 1
                    break
    assert sum(res.values()) == total, res
    return res


def main():
    rng = random.Random(SEED)

    # ---- load BA conversations -------------------------------------------------
    con = duckdb.connect()
    con.execute(f"CREATE TEMP TABLE conv AS SELECT * FROM read_parquet('{CACHE}\\conversations.parquet')")
    con.execute(f"CREATE TEMP TABLE summ AS SELECT * FROM read_parquet('{CACHE}\\conversation_summary.parquet')")
    convs = con.execute(f"""
        SELECT c.conv_id, c.tweet_id, c.author_id, c.inbound, c.created_ts, c.text
        FROM conv c
        WHERE EXISTS (SELECT 1 FROM summ s
                      WHERE s.conv_id = c.conv_id
                        AND EXISTS (SELECT 1 FROM unnest(s.brand_authors) AS t(a) WHERE t.a = '{BRAND}'))
        ORDER BY c.conv_id, c.created_ts, c.tweet_id
    """).df()

    summ = con.execute(f"""
        SELECT conv_id, n_customer_tweets, n_tweets, n_brand_tweets
        FROM summ
        WHERE EXISTS (SELECT 1 FROM unnest(brand_authors) AS t(a) WHERE t.a = '{BRAND}')
        ORDER BY conv_id
    """).df()

    audited = set()
    with open(AUDIT_MD, encoding="utf-8") as f:
        for m in re.finditer(r"## Conversation (\d+)", f.read()):
            audited.add(int(m.group(1)))
    print(f"audit-sample conversation ids to exclude: {len(audited)}")

    eligible = [cid for cid in sorted(convs["conv_id"].unique()) if cid not in audited]
    print(f"eligible BA conversations: {len(eligible):,}  (BA total {len(audited) + len(eligible):,})")

    # ---- pick target message per conversation (deterministic rng) -------------- 
    rows = []
    for conv_id in eligible:
        sub = convs[convs["conv_id"] == conv_id].reset_index(drop=True)
        inb = sub[sub["inbound"]].index.tolist()
        n_in = len(inb)
        if rng.random() < 0.85:
            pos = inb[0]
            is_first = True
        else:
            if n_in >= 2:
                pos = inb[rng.randint(1, n_in - 1)]
                is_first = False
            else:
                pos = inb[0]
                is_first = True

        target = sub.loc[pos]
        idx = int(pos)
        ctx_msgs = []
        for j in range(idx - 1, -1, -1):
            if j < 0:
                break
            pre = sub.loc[j]
            role = "BRAND" if not pre["inbound"] else "CUSTOMER"
            ctx_msgs.append(f"[{role} @ {pre['created_ts']}] {pre['text']}")
            if len(ctx_msgs) >= 2:
                break
        ctx_msgs.reverse()
        prior_context = "\n".join(ctx_msgs)

        ref_candidates = sub[(sub.index > idx) & (~sub["inbound"]) & (sub["author_id"] == BRAND)]
        if len(ref_candidates):
            ref = ref_candidates.iloc[0]
            ref_text = ref["text"]
        else:
            ref_text = ""
        has_ref = bool(ref_candidates.shape[0] > 0)

        srow = summ.loc[summ["conv_id"] == conv_id].iloc[0]
        text = target["text"]
        low = text.lower()
        prim, hits = bucket_for(text)
        non_noise_hits = [h for h in hits if h != "noise_or_off_topic"]
        is_conflict = len(set(non_noise_hits)) >= 2
        rows.append({
            "conv_id": int(conv_id),
            "target_tweet_id": int(target["tweet_id"]),
            "target_author_id": target["author_id"],
            "target_created_ts": str(target["created_ts"]),
            "customer_message": text,
            "message_chars": len(text),
            "message_words": len(text.split()),
            "is_first_inbound": is_first,
            "target_position": int(pos + 1),
            "n_inbound_total": int(n_in),
            "conv_tweets_total": int(srow["n_tweets"]),
            "n_brand_tweets_total": int(srow["n_brand_tweets"]),
            "prior_context": prior_context,
            "reference_brand_reply": ref_text,
            "has_brand_reply_after": has_ref,
            "bucket_primary": prim,
            "bucket_hits": "|".join(hits),
            "is_conflict": is_conflict,
        })

    df = pd.DataFrame(rows)
    pop = df["bucket_primary"].value_counts().to_dict()
    print("\neligible target-message pool by sampling prior:")
    for b in sorted(pop, key=lambda x: -pop[x]):
        print(f"  {b:<38} {pop[b]:,}")

    # ---- quota allocation ------------------------------------------------------
    floors = {
        "account_or_security": 10,
        "baggage": 12,
        "seat_or_upgrade": 12,
        "refund_or_compensation": 26,
        "website_or_app_issue": 15,
        "flight_disruption": 26,
        "booking_change_or_cancellation": 12,
        "contact_or_complaint": 12,
        "information_or_policy": 16,
        "noise_or_off_topic": 16,
        "other": 4,
    }
    quotas = allocate_quotas(pop, TARGET_N, floors)
    print("\nallocated quotas (sum = %d):" % sum(quotas.values()))
    for b in sorted(quotas, key=lambda x: -quotas[x]):
        print(f"  {b:<38} {quotas[b]}")

    # ---- sampled rows per bucket (deterministic rng) ---------------------------
    selected = []
    for bucket in sorted(quotas):
        q = quotas[bucket]
        pool = df[df["bucket_primary"] == bucket].sort_values("conv_id")
        if len(pool) < q:
            raise RuntimeError(f"not enough candidates for {bucket}: {len(pool)} < {q}")
        border = pool[pool["is_conflict"]]
        main = pool[~pool["is_conflict"]]
        n_border = min(len(border), max(0, int(q * 0.25)))
        n_main = q - n_border
        sel_b = rng.sample(border.index.tolist(), n_border)
        sel_m = rng.sample(main.index.tolist(), n_main)
        sel_idx = sel_b + sel_m
        for i in sel_idx:
            row = pool.loc[i].to_dict()
            row["sample_slice"] = "borderline" if i in sel_b else "main"
            selected.append(row)

    sel = pd.DataFrame(selected).sort_values("conv_id").reset_index(drop=True)
    sel.insert(0, "example_id", "BA_" + sel["conv_id"].astype(str))
    assert len(sel) == TARGET_N, len(sel)
    assert len(sel) == sel["conv_id"].nunique()

    # blank label columns (filled by the manual annotation pass)
    label_cols = ["intent", "intent_confidence", "secondary_intent",
                  "resolution_observable", "resolution_type",
                  "escalation_label", "escalation_reason",
                  "noise_flag", "ambiguity_flag", "annotator_notes"]
    for c in label_cols:
        sel[c] = ""

    out_csv = os.path.join(EVAL_DIR, "_candidates_worksheet.csv")
    sel.to_csv(out_csv, index=False, encoding="utf-8")

    summary = {
        "seed": SEED,
        "target_n": TARGET_N,
        "brand": BRAND,
        "python_version": sys.version.split()[0],
        "pandas_version": pd.__version__,
        "pool_ba_conversations_total": len(audited) + len(eligible),
        "audit_excluded_conversations": sorted(audited),
        "eligible_conversations": len(eligible),
        "target_selection_policy": "first inbound ~85%, later inbound ~15% (continuity slice)",
        "bucket_pool_proportions": {k: pop.get(k, 0) for k in sorted(pop)},
        "allocated_quotas": {k: quotas.get(k, 0) for k in sorted(pop)},
        "selected_bucket_counts": sel["bucket_primary"].value_counts().to_dict(),
        "selected_slice_counts": sel["sample_slice"].value_counts().to_dict(),
        "selected_is_first_inbound": bool(sel["is_first_inbound"].mean() > 0.8),
        "selected_pct_first_inbound": round(float(sel["is_first_inbound"].mean()), 4),
        "candidate_file": "_candidates_worksheet.csv",
        "notes": "Keyword priors are SAMPLING PRIORS only, not labels. Labels are assigned by the "
                 "manual annotation pass (single annotator, documented limitation).",
    }
    with open(os.path.join(ANALYSIS, "golden_sampling_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nselected examples: {len(sel)}")
    print(sel["sample_slice"].value_counts().to_string())
    print(f"\nWrote {out_csv}")
    print(f"Wrote {os.path.join(ANALYSIS, 'golden_sampling_summary.json')}")


if __name__ == "__main__":
    main()