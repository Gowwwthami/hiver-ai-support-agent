"""Resolution-diversity + DM/private-channel analysis for candidate brands.

For conversations with a customer message followed by brand responses we
pair "problem" (first customer message) with "resolution behavior" (last brand
message) and classify brand responses by coarse heuristic resolution-action type.

TYPE MAP (heuristic; labelled as evidence, not ground truth):
  DM_INFO      - asks customer to DM / send private info / follow up privately
  SELF_SERVICE - points to URL / self-service channel / phone queue
  STATUS_UPDATE- informs of status/action taken, tickets, tracking
  COMPENSATION - refund / credit / compensation language
  FIXED        - declares issue fixed / workaround / resolved
  APOLOGY_ONLY - apology with no resolution action
  ACK          - acknowledgment / thanks / generic
  ESCALATION   - passed to team / someone will be in touch

Outputs analysis/resolution_diversity.csv/.json and analysis/dm_behavior.csv/.json
"""
import json
import os
import re
import sys
from collections import Counter

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(BASE, "analysis", "cache")
OUT = os.path.join(BASE, "analysis")
CONV = pd.read_parquet(os.path.join(CACHE, "conversations.parquet"))
SUM = pd.read_parquet(os.path.join(CACHE, "conversation_summary.parquet"))

CANDidate_BRANDS = ["AmazonHelp", "AppleSupport", "Uber_Support", "SpotifyCares",
                    "AmericanAir", "Delta", "Tesco", "British_Airways",
                    "VirginTrains", "XboxSupport", "VerizonSupport", "TMobileHelp"]

URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@[a-zA-Z0-9_]+")

DM_REGEX = re.compile(
    r"\b(dm|dms|direct message|private message|message us|pm us|send us a note|"
    r"reach out|contact us|inbox us|follow up|let['’]?s take this)\b", re.I)
PRIVACY_REGEX = re.compile(
    r"\b(dm us|send us a (dm|note|message|private)|share (your|the) (details|info)|"
    r"provide (your|the|us with) (details|info|email|phone)|email address|"
    r"booking reference|case reference|account details)\b", re.I)

TYPE_RULES = [
    ("DM_INFO", re.compile(r"\b(dm|direct message|private message|inbox|send us a note|"
                           r"message us|reach out|contact us|pm us|let['’]?s take this)\b", re.I)),
    ("SELF_SERVICE", re.compile(r"\b(check|visit|go to|follow|try|refer|see|download|visit|log ?in)\b.{0,40}"
                                r"(https?://|\.com|\.co\.uk|\.ca|\.br|\.de|\.fr|support|help center|app)\b", re.I)),
    ("COMPENSATION", re.compile(r"\b(refund|credit|reimburse|compensation|discount|voucher|gift card|"
                                r"money back|goodwill)\b", re.I)),
    ("FIXED", re.compile(r"\b(resolved|fixed|working now|sorted|should work|now? work|"
                         r"resolving|workaround|update (has )?(been|is )?(released|available)|"
                         r"back up and update)\b", re.I)),
    ("ESCALATION", re.compile(r"\b(pass(ed|ing)? (to|this on)|forward(ed|ing)?|team will be in touch|"
                              r"someone (will|is going to)|specialist|technician|we (will|'ll) (look|take|get back)|"
                              r"looking into|investigat|we('ve| have) shared|log(ged)? (a|the)? ticket|c[as]se reference)\b", re.I)),
    ("STATUS_UPDATE", re.compile(r"\b(status|update|on its way|arriv|deliver|track(all)?ing|"
                                 r"due to arrive|depart|delayed|cancel|gate|schedule|eta|"
                                 r"flight (blah )?information)\b", re.I)),
    ("APOLOGY_ONLY", re.compile(r"\b(sorry|apolog|apologies)\b", re.I)),
    ("ACK", re.compile(r"\b(thank|thanks|great|appreciate|no problem|you're welcome|absolutely|"
                       r"happy to help)\b", re.I)),
]


def classify(t):
    for typ, rx in TYPE_RULES:
        if rx.search(t):
            return typ
    return "OTHER"


def normalize(t):
    t = URL_RE.sub("{URL}", str(t))
    t = MENTION_RE.sub("@USER", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


def main():
    bot = CONV.loc[CONV["inbound"] == False]
    cust = CONV.loc[CONV["inbound"] == True]
    conv2brand = {b: set(g["conv_id"].unique()) for b, g in bot.groupby("author_id")}

    dm_rows, res_rows = [], []
    for brand in CANDidate_BRANDS:
        conv_ids = conv2brand.get(brand, set())
        sub = CONV[CONV["conv_id"].isin(conv_ids)].copy()
        sub = sub.sort_values(["conv_id", "created_ts"])

        brand_msgs = sub.loc[(sub["author_id"] == brand) & (~sub["inbound"])]
        n_brand_msg = len(brand_msgs)
        dm_hits = brand_msgs["text"].apply(lambda t: bool(DM_REGEX.search(str(t))))
        priv_hits = brand_msgs["text"].apply(lambda t: bool(PRIVACY_REGEX.search(str(t))))
        any_private = sum(bool(DM_REGEX.search(str(t)) or PRIVACY_REGEX.search(str(t))) for t in brand_msgs["text"])

        # first-customer-message problem -> last-brand-message resolution
        pairs = []
        for cid, g in sub.groupby("conv_id"):
            cust_msgs = g[g["inbound"] == True]
            bm = g[g["author_id"] == brand]
            if cust_msgs.empty or bm.empty:
                continue
            prob = cust_msgs.iloc[0]["text"]
            last_resp = bm.iloc[-1]["text"]
            n_brand_in_conv = len(bm)
            pairs.append((str(prob), str(last_resp), n_brand_in_conv))
        dfp = pd.DataFrame(pairs, columns=["problem", "last_response", "n_brand_in_conv"]) if pairs else \
            pd.DataFrame(columns=["problem", "last_response", "n_brand_in_conv"])

        # resolution action type distribution (last brand response per conv)
        if len(dfp):
            dfp["type"] = dfp["last_response"].apply(classify)
            type_dist = dfp["type"].value_counts(normalize=True).to_dict()
            type_counts = dfp["type"].value_counts().to_dict()
            n_conv_with_resp = len(dfp)
            # problem->resolution distinctness: how often does the SAME problem
            # cluster receive the SAME resolution type? (coarse)
            dfp["problem_norm"] = dfp["problem"].apply(lambda t: normalize(t)[:80])
            # how many problems got DM_INFO as the resolution (concentration)
            dm_resp_share = dfp["type"].eq("DM_INFO").mean()
            # response behavior: resolutions are unique?
            uniq_last = dfp["last_response"].apply(normalize).nunique() / max(len(dfp), 1)
            n_multi_turn = int((dfp["n_brand_in_conv"] >= 2).sum())
        else:
            type_dist = type_counts = {}
            n_conv_with_resp = 0
            dm_resp_share = float("nan")
            uniq_last = float("nan")
            n_multi_turn = 0

        dm_rows.append({
            "brand": brand,
            "n_brand_messages": int(n_brand_msg),
            "n_conv_with_at_least_one_brand_response": int(n_conv_with_resp),
            "brand_msgs_with_dm_phrase": int(dm_hits.sum()),
            "brand_msgs_with_private_info_phrase": int(priv_hits.sum()),
            "brand_msgs_with_either_dm_or_private_phrase": int(any_private),
            "share_brand_msgs_dm_or_private": round(any_private / n_brand_msg, 4) if n_brand_msg else 0,
        })
        res_rows.append({
            "brand": brand,
            "n_convs_with_problem_and_response": int(n_conv_with_resp),
            "response_type_distribution": {k: round(v, 4) for k, v in sorted(type_dist.items(), key=lambda x: -x[1])},
            "share_last_responses_of_type_DM_INFO": round(dm_resp_share, 4) if isinstance(dm_resp_share, float) and not pd.isna(dm_resp_share) else None,
            "unique_ratio_of_last_responses(normalized)": round(uniq_last, 4) if isinstance(uniq_last, float) and not pd.isna(uniq_last) else None,
            "n_convs_with_ge2_brand_responses": int(n_multi_turn),
        })

    dm_df = pd.DataFrame(dm_rows)
    dm_df.to_csv(os.path.join(OUT, "dm_behavior.csv"), index=False)
    res_df = pd.DataFrame(res_rows)
    res_df.to_csv(os.path.join(OUT, "resolution_diversity.csv"), index=False)

    with open(os.path.join(OUT, "dm_behavior.json"), "w", encoding="utf-8") as f:
        json.dump({"method": "regex heuristics on brand outbound messages; DM==private-channel pivot",
                   "results": dm_df.to_dict("records")}, f, indent=2, default=str)
    with open(os.path.join(OUT, "resolution_diversity.json"), "w", encoding="utf-8") as f:
        json.dump({"method": ("heuristic action-type classifier on LAST brand response per conversation; "
                              "types: DM_INFO, SELF_SERVICE, COMPENSATION, FIXED, ESCALATION, "
                              "STATUS_UPDATE, APOLOGY_ONLY, ACK, OTHER"),
                   "results": res_df.to_dict("records")}, f, indent=2, default=str)

    print("=== DM / PRIVATE-CHANNEL BEHAVIOR ===")
    print(dm_df.to_string(index=False))
    print("\n=== RESOLUTION ACTION-TYPES (last brand response per conversation) ===")
    for rec in res_df.to_dict("records"):
        print(f"\n{rec['brand']}  (n_pairs={rec['n_convs_with_problem_and_response']})")
        print("  ", rec["response_type_distribution"])
        print(f"   DM_INFO share of last-responses: {rec['share_last_responses_of_type_DM_INFO'] or 'n/a'} | "
              f"unique last-response ratio: {rec['unique_ratio_of_last_responses(normalized)'] or 'n/a'} | "
              f">=2 brand resp: {rec['n_convs_with_ge2_brand_responses']}")
    print("\nWrote analysis/dm_behavior.csv/.json and resolution_diversity.csv/.json")


if __name__ == "__main__":
    main()