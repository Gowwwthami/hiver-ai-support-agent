"""Find additional British_Airways corpus candidates (NOT golden-set additions).

Scans the Phase-1 reconstructed BA conversations (analysis/cache/conversations.parquet
+ conversation_summary.parquet) for human-inbound messages matching the
seat/upgrade and the account/access/security keywords, excluding:
  - conversations already in the golden set (evaluation/golden_split_ids.csv);
  - the 50 Phase-1 audit conversations (analysis/candidate_conversations/British_Airways.md).

Outputs (candidates only — never auto-added to the golden set):
  analysis/candidate_examples/seat_or_upgrade_candidates.csv          (<=18 rows)
  analysis/candidate_examples/account_access_or_security_candidates.csv (<=12 rows)

Deterministic: ordering is (number of distinct keyword groups DESC, message
length ASC, conv_id ASC). No random source. Human review decides final picks.
"""

import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "analysis" / "cache"
AUDIT_POOL = ROOT / "analysis" / "candidate_conversations" / "British_Airways.md"
SPLIT_IDS = ROOT / "evaluation" / "golden_split_ids.csv"
OUT_DIR = ROOT / "analysis" / "candidate_examples"

SEAT_KW = [
    r"seat", r"upgrade", r"leg ?room", r"exit row", r"row \d+|cabin",
    r"premium", r"business class", r"club europe", r"club world",
    r"first class", r"extra legroom",
]
ACCOUNT_KW = [
    r"executive club", r"password", r"hack", r"log in|login|loggin",
    r"user ?name|username", r"account", r"reset", r"id", r"security",
]

SEAT_RE = re.compile("|".join(SEAT_KW), re.IGNORECASE)
ACCT_RE = re.compile("|".join(ACCOUNT_KW), re.IGNORECASE)

# Praise/ack markers that match our keywords but are NOT support requests.
PRAISE_RE = re.compile(
    r"^thanks|thank you|excellent (crew|service|cabin)|delightful|great (change|cabin|crew)|"
    r"well done|spot on|lovely|amazing (cabin|crew)|always a pleasure",
    re.IGNORECASE,
)


def distinct_groups(text: str, groups: list) -> list:
    found = []
    for g in groups:
        if re.search(g, text, re.IGNORECASE):
            found.append(g)
    return found


def load_ba_conversations():
    con = duckdb.connect()
    convs = con.execute(
        "SELECT conv_id, tweet_id, author_id, inbound, created_ts, text "
        "FROM read_parquet(?) WHERE conv_id IN ("
        "   SELECT conv_id FROM read_parquet(?) "
        "   WHERE brand_authors::VARCHAR LIKE '%British_Airways%')",
        [str(CACHE / "conversations.parquet"), str(CACHE / "conversation_summary.parquet")],
    ).fetchdf()
    convs = convs[convs["inbound"].astype(bool) & (convs["author_id"] != "British_Airways")]
    return convs


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    convs = load_ba_conversations()
    print(f"BA inbound customer messages loaded: {len(convs)}")

    exclusion = set(pd.read_csv(SPLIT_IDS, dtype=str)["conv_id"].astype("int64"))
    body = AUDIT_POOL.read_text(encoding="utf-8", errors="ignore")
    audit = {int(m) for m in re.findall(r"## Conversation (\d+)", body)}
    exclusion |= audit
    print(f"excluded conversations: golden {200 - len(exclusion | set(convs['conv_id'].unique()))} / audit {len(audit & set(convs['conv_id'].unique()))}")

    keep = ~convs["conv_id"].isin(list(exclusion))
    convs = convs[keep].copy()
    print(f"BA convs after exclusion of golden+audit: {convs['conv_id'].nunique()}")

    for label, regex, groups, limit, outname in [
        ("seat", SEAT_RE, SEAT_KW, 24, "seat_or_upgrade_candidates.csv"),
        ("account", ACCT_RE, ACCOUNT_KW, 12, "account_access_or_security_candidates.csv"),
    ]:
        mask = convs["text"].map(lambda t: bool(regex.search(t)) and not bool(PRAISE_RE.search(t)))
        cand = convs[mask].copy()
        cand["matched_groups"] = cand["text"].map(lambda t: "|".join(distinct_groups(t, groups)))
        cand["n_groups"] = cand["matched_groups"].map(lambda s: len(s.split("|")) if s else 0)
        cand["msg_chars"] = cand["text"].map(len)
        # prefer the earliest inbound per conversation that matched
        cand = cand.sort_values(["conv_id", "created_ts"]).drop_duplicates("conv_id", keep="first")
        cand = cand.sort_values(["n_groups", "msg_chars", "conv_id"],
                                ascending=[False, True, True])
        cand = cand.reset_index(drop=True).head(limit)
        out = pd.DataFrame({
            "candidate_id": [f"SEAT_{i:04d}" if label == "seat" else f"ACCT_{i:04d}" for i in range(len(cand))],
            "conv_id": cand["conv_id"].astype("int64"),
            "tweet_id": cand["tweet_id"].astype("int64"),
            "created_ts": cand["created_ts"],
            "matched_keywords": cand["matched_groups"],
            "n_keyword_groups": cand["n_groups"],
            "msg_chars": cand["msg_chars"],
            "customer_message": cand["text"],
        })
        out.to_csv(OUT_DIR / outname, index=False, encoding="utf-8")
        print(f"Wrote {OUT_DIR / outname} ({len(out)} rows)")


if __name__ == "__main__":
    main()