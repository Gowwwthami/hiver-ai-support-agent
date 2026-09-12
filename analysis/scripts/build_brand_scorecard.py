"""Assemble the brand-selection scorecard from all evidence artifacts.

Dimensions (1-5):
  A data volume        B conversation richness  C problem diversity
  D resolution diversity  E grounding potential  F escalation potential
  G noise/manageability   H evaluation potential  I reproducibility

Every score carries raw evidence + reason. Nothing is invented: values come
from the analysis CSV/JSON artifacts in analysis/.
Output: analysis/brand_scorecard.csv, analysis/brand_analysis.md, and
analysis/scorecard_evidence.json
"""
import json
import os

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
A = os.path.join(BASE, "analysis")


def load(name):
    return pd.read_csv(os.path.join(A, name))


BS = load("brand_statistics.csv").set_index("brand")
CQ = load("conversation_quality.csv").set_index("brand")
DQ = load("data_quality.csv").set_index("brand")
RD = load("response_diversity.csv").set_index("brand")
RDC = json.load(open(os.path.join(A, "resolution_diversity_by_cluster.json"), encoding="utf-8"))
RDC = {r["brand"]: r for r in RDC}
DM = load("dm_behavior.csv").set_index("brand")
RES = load("resolution_diversity.csv").set_index("brand")

CANDIDATES = ["AmazonHelp", "British_Airways", "AmericanAir", "Delta",
              "VirginTrains", "SpotifyCares", "Tesco", "XboxSupport", "TMobileHelp"]


def s(series, key, default="n/a"):
    return series[key] if series is not None and key in series else default


def evidence_table(brand):
    bs, cq, dq, rd, dm, res = (t.loc[brand] for t in (BS, CQ, DQ, RD, DM, RES))
    rdc = RDC.get(brand, {})
    return {
        "n_brand_tweets": int(bs["total_tweets"]),
        "n_inbound": int(bs["inbound_tweets"]),
        "n_outbound": int(bs["outbound_tweets"]),
        "n_conversations": int(cq["n_conversations"]),
        "median_len": cq["median_conversation_length"],
        "mean_len": cq["mean_conversation_length"],
        "max_len": int(cq["max_conversation_length"]),
        "pct_ge2_brand_resp": cq["pct_ge2_brand_responses"],
        "pct_ge3_brand_resp": cq["pct_ge3_brand_responses"],
        "unique_customers": int(cq["unique_customers"]),
        "avg_cust_msgs": cq["avg_customer_messages_per_conv"],
        "avg_brand_msgs": cq["avg_brand_messages_per_conv"],
        "brand_dup_texts": int(dq["brand_duplicate_texts"]),
        "url_only_brand": int(dq["brand_url_only"]),
        "uniq_norm_ratio": rd["unique_ratio_normalized"] if "unique_ratio_normalized" in rd else "n/a",
        "top20_template_share": rd["top20_template_share"],
        "dm_or_private_share_msgs": dm["share_brand_msgs_dm_or_private"],
        "dm_info_share_last_resp": res["share_last_responses_of_type_DM_INFO"],
        "bhatt_problem_resolution": rdc.get("mean_pairwise_bhattacharyya_between_problem_clusters"),
        "n_problem_resp_pairs": int(res["n_convs_with_problem_and_response"]),
        "n_ge2_brand_resp_convs": int(cq["n_ge2_brand_responses"]),
    }


SCORES = {
    "AmazonHelp": {
        "A_volume": (5, "82,556 conversations; 169,840 outbound; largest by 3x next brand."),
        "B_richness": (4, "49.6% of convs have >=2 brand responses; 23% >=3; mean len 4.5. Long dialogs like account-hacked (10 tweets) resolved publicly step-by-step."),
        "C_problem": (4, "Clusters: delivery/tracking, refunds, account/hacked, order issues, prime billing, device setup; BUT ~8% non-Latin + promotion/thanks noise."),
        "D_resolution": (4, "Highest problem->resolution differentiation (Bhatt 0.196). Responses individualized (unique-ratio 0.91). Many public form-URL resolvers; 13% DM."),
        "E_grounding": (4, "Rich public troubleshooting (setup guides, check-junk-box steps, form links). PII asked mostly via links/DM."),
        "F_escalation": (4, "Clear escalation patterns: account compromised, refund disputes, repeated no-resolve complaints -> 'team will contact you'."),
        "G_noise": (2, "8%+ non-English/noise; brand handle fragmented across @115821/@115850/@116935 etc.; promo/joke customers; needs aggressive filtering."),
        "H_eval": (5, "Easily reach 150-250 labelled examples; large pool for train/dev/test with conversation-level splits."),
        "I_repro": (4, "Subsample easily; filters needed for language/threading make pipeline slightly heavier."),
    },
    "British_Airways": {
        "A_volume": (4, "16,452 convs; 29,361 outbound; top-5 volume."),
        "B_richness": (4, "44.3% convs >=2 brand responses; 17.4% >=3; many long rebooking/refund dialogs (6 brand msgs in one)."),
        "C_problem": (4, "Airline-specific distinct intents: check-in web issues, booking refs, seat policy, refunds/cancellations, baggage, chauffeur/delays."),
        "D_resolution": (5, "98.9% unique normalized responses; problem->resolution exist per-flight/per-case; 16% DM only."),
        "E_grounding": (4, "Public answers to policy & process questions (e.g., seat policy URL, check-in windows); specifics moved to DM."),
        "F_escalation": (4, "Refund/complaint chains, customer-relations escalation clearly visible."),
        "G_noise": (4, "Very clean, near-zero empty/short/url-only; occasional marketing-brand-early tweets in conversations."),
        "H_eval": (5, "Great pool; intents are crisp (check-in, refund, baggage, seat, booking change)."),
        "I_repro": (5, "Clean data -> trivial reproducible subsampling; small enough to iterate fast."),
    },
    "AmericanAir": {
        "A_volume": (4, "26,386 convs; 36,764 outbound."),
        "B_richness": (3, "27.3% ge2; 7.5% ge3 brand responses; mean 3.3."),
        "C_problem": (4, "Delays/cancellations, rebooking, bag fees, refunds, WiFi, customer-service complaints."),
        "D_resolution": (4, "96.8% unique normalized responses; 20% DM; varied free-text resolutions (Some policy stance e.g. animal trophies)."),
        "E_grounding": (4, "Policy + flight-status answers public; rebooking moved to DM."),
        "F_escalation": (4, "Refund/rebooking escalations present."),
        "G_noise": (4, "Very clean; 100% latin; some singletons are praise/banter (natural Twitter noise)."),
        "H_eval": (5, "Similar crisp airline intent set."),
        "I_repro": (5, "Clean + manageable."),
    },
    "Delta": {
        "A_volume": (4, "26,168 convs; 42,253 outbound."),
        "B_richness": (4, "33.3% ge2; 13.3% ge3 brand responses; long convs incl. repeated update chains."),
        "C_problem": (4, "Flight changes, baggage, meal/veg options, app issues, sky club, delays; some praise noise."),
        "D_resolution": (4, "Unique-ratio 0.91; 18% DM; some template ACK (0.28) which is polite thank-you behavior."),
        "E_grounding": (4, "Public status updates & recovery guidance."),
        "F_escalation": (4, "Clear escalations in refund/baggage chains."),
        "G_noise": (4, "Clean."),
        "H_eval": (5, "Good pool."),
        "I_repro": (5, "Clean + manageable."),
    },
    "VirginTrains": {
        "A_volume": (3, "14,853 convs; 27,817 outbound; regional scope."),
        "B_richness": (4, "42.2% ge2; 17.8% ge3; long real-time delay/reroute dialogs."),
        "C_problem": (4, "Train cancellations/delays, refunds, seat reservations, onboard climate/wifi, lost items."),
        "D_resolution": (5, "Only 3.2% DM share — resolutions happen PUBLICLY in-thread (status, coach numbers, taxi policy); unique-ratio 0.93."),
        "E_grounding": (5, "Highest public-resolution grounding: the brand answers fully in public."),
        "F_escalation": (3, "Some referrals to aftersales/phone lines; fewer private escalations (by design)."),
        "G_noise": (3, "Moderate banter/praise; cross-operator referral noise (@120576 etc.) requires care with reply-target interpretation."),
        "H_eval": (4, "Intents are clear but temporal (train status) -> some golden labels age poorly; still usable."),
        "I_repro": (4, "Small + clean; referral edges need care."),
    },
    "SpotifyCares": {
        "A_volume": (3, "28,280 convs; 43,265 outbound."),
        "B_richness": (3, "29.2% ge2; 11.4% ge3."),
        "C_problem": (4, "Premium billing/upgrades, account access, playback bugs, country availability, missing content."),
        "D_resolution": (3, "42% DM_INFO last-responses; 'feedback passed on' for feature asks reduces observable resolutions."),
        "E_grounding": (3, "Good for billing/account/technical; weak for feature-request resolution (vacuously resolved)."),
        "F_escalation": (3, "Some; many canned 'passed to right folks'."),
        "G_noise": (4, "Clean but high ratio of feature requests/humor (non-resolvable)."),
        "H_eval": (4, "Intent set OK but many 'feature request' labels."),
        "I_repro": (4, "Small + clean."),
    },
    "Tesco": {
        "A_volume": (3, "16,722 convs; 38,573 outbound; UK grocery."),
        "B_richness": (5, "61.0% convs >=2 brand responses (highest of candidates); 34.3% >=3; supplier-detail exchanges."),
        "C_problem": (5, "Product quality complaints, delivery/click-collect, refunds, store staff, website/slots, price — broad retail intents."),
        "D_resolution": (4, "Unique-ratio 0.95; notable supplier referral + compensation patterns; 29% DM."),
        "E_grounding": (4, "Real problem->resolution pairs incl. compensation."),
        "F_escalation": (4, "Supplier escalation & refund chains present."),
        "G_noise": (4, "Clean, some praise."),
        "H_eval": (5, "Broad intent set is great for a classifier demo."),
        "I_repro": (4, "UK-only data; a bit heavier volume."),
    },
    "XboxSupport": {
        "A_volume": (3, "13,455 convs; 24,557 outbound."),
        "B_richness": (4, "42.5% ge2; 15.7% ge3."),
        "C_problem": (4, "Hardware (controllers), store purchases/errors, game-specific bugs, live sign-in, refunds, preorders."),
        "D_resolution": (3, "33% DM_INFO last-responses; heavy 'DM us your gamertag' — resolutions mostly private."),
        "E_grounding": (3, "Public grounding mostly funneling to DM/live chat."),
        "F_escalation": (3, "Some (live-chat referral)."),
        "G_noise": (4, "Clean; banter present."),
        "H_eval": (4, "Clear intents."),
        "I_repro": (4, "Small + clean."),
    },
    "TMobileHelp": {
        "A_volume": (3, "22,820 convs; 34,317 outbound."),
        "B_richness": (3, "23.3% ge2; 7% ge3."),
        "C_problem": (4, "Activation, billing, iPhone preorders, coverage, insurance claims, promos."),
        "D_resolution": (2, "83% DM; 85% last-responses are DM funnel; near-identical resolution behavior across problems (Bhatt 0.004)."),
        "E_grounding": (2, "Weak public resolution evidence (privacy-policy driven)."),
        "F_escalation": (2, "Mostly 'DM me' one-step."),
        "G_noise": (4, "Clean."),
        "H_eval": (3, "Hard to build grounded gold labels when resolution hidden."),
        "I_repro": (3, "Clean but resolution-poor."),
    },
}

ORDER = ["AmazonHelp", "British_Airways", "AmericanAir", "Delta", "Tesco",
         "VirginTrains", "SpotifyCares", "XboxSupport", "TMobileHelp"]


def main():
    rows = []
    for b in ORDER:
        ev = evidence_table(b)
        dims = SCORES[b]
        total = sum(v[0] for v in dims.values())
        rows.append({"brand": b, **{k: v[0] for k, v in dims.items()},
                     "total": total, "evidence": json.dumps(ev),
                     "reasons": json.dumps({k: v[1] for k, v in dims.items()})})
    df = pd.DataFrame(rows).sort_values("total", ascending=False)
    df.to_csv(os.path.join(A, "brand_scorecard.csv"), index=False)

    with open(os.path.join(A, "scorecard_evidence.json"), "w", encoding="utf-8") as f:
        json.dump({"scale": "1=poor 2=weak 3=adequate 4=strong 5=excellent",
                   "candidates": [{"brand": r["brand"],
                                    "scores": {k: r[k] for k in ["A_volume", "B_richness", "C_problem",
                                                                 "D_resolution", "E_grounding", "F_escalation",
                                                                 "G_noise", "H_eval", "I_repro"]},
                                    "evidence": json.loads(r["evidence"]),
                                    "reasons": json.loads(r["reasons"]),
                                    "total": r["total"]} for r in df.to_dict("records")]},
                  f, indent=2, default=str)
    pd.set_option("display.width", 250)
    show = df[["brand", "A_volume", "B_richness", "C_problem", "D_resolution",
               "E_grounding", "F_escalation", "G_noise", "H_eval", "I_repro", "total"]]
    print(show.to_string(index=False))
    print("Wrote analysis/brand_scorecard.csv + scorecard_evidence.json")


if __name__ == "__main__":
    main()