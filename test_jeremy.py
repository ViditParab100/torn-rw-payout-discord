"""
CyberJeremy Test Suite
======================
Four layers:
  1. Semantic search (fast, deterministic) — expected player in top N results
  2. Meaning equivalence — two phrasings should surface the same player
  3. Jeremy chat (slower, generative) — keyword checks on live Sarvam responses
  4. Player intel — title tier logic, context formatting (no API needed)

Run:  python test_jeremy.py
      python test_jeremy.py --chat   # include the slower generative tests
"""

import sys
import time
import argparse

sys.stdout.reconfigure(encoding="utf-8")

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}PASS{RESET}  {msg}")
def fail(msg): print(f"  {RED}FAIL{RESET}  {msg}")
def skip(msg): print(f"  {YELLOW}SKIP{RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{CYAN}{'─'*60}\n{msg}\n{'─'*60}{RESET}")

passed = failed = 0


# ── SETUP ─────────────────────────────────────────────────────────────────────
header("SETUP")
print("Loading lore_db + rebuilding ChromaDB index from MongoDB...")
t0 = time.time()
import lore_db, memory_db
lore_db.rebuild_from_mongodb()
print(f"Ready in {time.time()-t0:.1f}s  |  "
      f"{lore_db._col.count()} facts indexed")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Semantic search
# ══════════════════════════════════════════════════════════════════════════════
header("LAYER 1 — Semantic search (lore_db.search_who)")

# (query, expected_player, top_n, note)
SEMANTIC_CASES = [
    # Leadership
    ("who is the leader of KOWR",              "ChineseGandalf",  5, "direct role lookup"),
    ("who leads the faction",                  "ChineseGandalf",  3, "phrasing: leads"),
    ("who runs KOWR",                          "ChineseGandalf",  4, "phrasing: runs"),
    ("who is in charge of the faction",        "ChineseGandalf",  4, "phrasing: in charge"),
    # Co-leadership
    ("who is the co-leader",                   "Xtatik",          6, "co-leader lookup"),
    ("who is second in command",               "Xtatik",          4, "phrasing: second in command"),
    ("who handles leadership with ChineseGandalf", "Xtatik",      5, "association-based"),
    # JNRanger / Jeremy (real-life trade — mechanic and welder, NOT a faction role)
    ("who was a mechanic and welder by trade", "JNRanger",        3, "real-life trade"),
    ("who was the welder from North Brampton", "JNRanger",        4, "phrasing: welder + location"),
    ("who scored 104 hits in a war",           "JNRanger",        3, "personal best stat"),
    ("who is CyberJeremy based on",            "JNRanger",        4, "JNRanger identity"),
    # Members
    ("who lives in Bangalore",                 "Star_vader",      3, "location fact"),
    ("who left to train in a reviver faction",  "Spidernnam",      4, "reviver faction departure"),
    ("who left KOWR to train reviving",        "Spidernnam",      5, "departure to reviver faction"),
    # Sister faction
    ("who leads KnockOut RingSide",            "Stumptronic",     3, "sister faction leader"),
    ("who runs the sister faction",            "Stumptronic",     4, "phrasing: sister faction"),
]

def run_semantic(query, expected, top_n, note):
    global passed, failed
    hits = lore_db.search_who(query, n_results=top_n, distance_threshold=0.85)
    found_players = [h["player"].lower() for h in hits]
    if expected.lower() in found_players:
        rank = found_players.index(expected.lower()) + 1
        ok(f"[{note}] '{query}' → {expected} (rank {rank}/{top_n})")
        passed += 1
    else:
        fail(f"[{note}] '{query}' → expected {expected}, got {[h['player'] for h in hits[:3]]}")
        failed += 1

for case in SEMANTIC_CASES:
    run_semantic(*case)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — Meaning equivalence
# ══════════════════════════════════════════════════════════════════════════════
header("LAYER 2 — Meaning equivalence (same player via different phrasings)")

# (query_a, query_b, expected_player, note)
EQUIV_CASES = [
    ("who leads KOWR",
     "who runs the faction",
     "ChineseGandalf",
     "leader phrasing A vs B"),
    ("who is the co-leader",
     "who is second in command",
     "Xtatik",
     "co-leader phrasing A vs B"),
    ("who was a mechanic by trade",
     "who was a welder from North Brampton",
     "JNRanger",
     "JNRanger real-life trade phrasing A vs B"),
    ("who left to train as a reviver",
     "who joined a reviver faction to practice reviving",
     "Spidernnam",
     "Spider reviver faction phrasing A vs B"),
]

def run_equiv(qa, qb, expected, note):
    global passed, failed
    hits_a = lore_db.search_who(qa, n_results=5, distance_threshold=0.85)
    hits_b = lore_db.search_who(qb, n_results=5, distance_threshold=0.85)
    players_a = [h["player"].lower() for h in hits_a]
    players_b = [h["player"].lower() for h in hits_b]
    exp = expected.lower()
    a_ok = exp in players_a
    b_ok = exp in players_b
    if a_ok and b_ok:
        ok(f"[{note}] Both phrasings surface {expected}")
        passed += 1
    elif a_ok or b_ok:
        which = "A" if a_ok else "B"
        fail(f"[{note}] Only phrasing {which} finds {expected}  |  A={players_a[:3]}  B={players_b[:3]}")
        failed += 1
    else:
        fail(f"[{note}] Neither phrasing finds {expected}  |  A={players_a[:3]}  B={players_b[:3]}")
        failed += 1

for case in EQUIV_CASES:
    run_equiv(*case)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — Jeremy chat (generative — requires --chat flag)
# ══════════════════════════════════════════════════════════════════════════════

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--chat", action="store_true")
args, _ = parser.parse_known_args()

if not args.chat:
    header("LAYER 3 — Jeremy chat  (skipped — run with --chat to enable)")
    skip("Generative tests skipped. Add --chat to run them (30–60s extra).")
else:
    header("LAYER 3 — Jeremy chat (live Sarvam calls — this takes ~30s)")
    import ai_engine

    # (speaker, message, keywords_any_of, description)
    CHAT_CASES = [
        ("FlipJames",
         "who is the leader of KOWR?",
         ["chinesegandalf", "cg", "gandalf"],
         "leader lookup → should name ChineseGandalf"),

        ("Kaemani",
         "who is our co-leader?",
         ["xtatik"],
         "co-leader → should name Xtatik"),

        ("Star_vader",
         "what happened in our last war?",
         ["combat ready", "combat", "war", "hits"],
         "last war recap → mentions Combat Ready HQ or war details"),

        ("FlipJames",
         "how many ranked wars have we won in total?",
         ["24", "won", "wins", "win"],
         "all-time wins → should say 24"),

        ("Kaemani",
         "who has the faction hit record in a single war?",
         ["rehsirap", "reh", "223"],
         "hit record → should mention Rehsirap and 223"),

        ("Star_vader",
         "what's our best ever chain?",
         ["2520", "2,520", "chain"],
         "chain record → should mention 2520"),

        ("FlipJames",
         "when did we first hit a 1000-hit chain?",
         ["2025", "october", "oct", "1000", "1,000"],
         "chain milestone → 2025-10-29 context"),

        ("Kaemani",
         "jeremy what was your personal best in wars?",
         ["104", "24604", "mile high", "war 24604"],
         "jeremy own record → 104 hits, War 24604"),
    ]

    def run_chat(speaker, message, keywords, desc):
        global passed, failed
        t = time.time()
        try:
            reply, _ = ai_engine.chat_with_jeremy(
                user_name=speaker,
                user_message=message,
                message_history=[]
            )
            elapsed = time.time() - t
            reply_lower = reply.lower()
            matched = [kw for kw in keywords if kw in reply_lower]
            if matched:
                ok(f"[{desc}]  ({elapsed:.1f}s)\n         Reply: {reply[:120]}")
                passed += 1
            else:
                fail(f"[{desc}]  ({elapsed:.1f}s)\n         Expected any of {keywords}\n         Got: {reply[:160]}")
                failed += 1
        except Exception as e:
            fail(f"[{desc}] Exception: {e}")
            failed += 1

    # Extra Layer 3 test: Jeremy never uses shortforms for his own name
    CHAT_CASES.append((
        "FlipJames",
        "hey CJ whats up, how you doing?",
        ["jeremy", "cyberjeremy", "cyber jeremy"],
        "Jeremy self-identifies as Jeremy/CyberJeremy, not CJ"
    ))

    for case in CHAT_CASES:
        run_chat(*case)
        time.sleep(1)  # small pause between Sarvam calls


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — Player Intel (unit tests, no API needed)
# ══════════════════════════════════════════════════════════════════════════════
header("LAYER 4 — Player Intel (title tiers, context formatting)")

import player_intel
from datetime import datetime as _dt

# 4a: Title tier ordering
TIER_CASES = [
    ("recruit",     "captain",     True,  "military tier progression"),
    ("samaritan",   "avenger",     True,  "samaritan < avenger"),
    ("grandmaster", "recruit",     False, "grandmaster > recruit"),
    ("recruit",     "recruit",     False, "same title = not a promotion"),
    ("unknowntitle","avenger",     True,  "unknown old title treated as promotion"),
]

def run_tier(old_t, new_t, expect_promo, note):
    global passed, failed
    old_rank = player_intel._title_rank(old_t)
    new_rank = player_intel._title_rank(new_t)
    is_promo = new_rank > old_rank or old_rank == -1
    if is_promo == expect_promo:
        ok(f"[{note}] '{old_t}'→'{new_t}' promo={is_promo}")
        passed += 1
    else:
        fail(f"[{note}] Expected promo={expect_promo}, got {is_promo} "
             f"(ranks: {old_rank}→{new_rank})")
        failed += 1

for case in TIER_CASES:
    run_tier(*case)

# 4b: Context formatting with a mock profile
mock_discord_id = "TEST_PLAYER_INTEL_999"
mock_profile = {
    "discord_id": mock_discord_id,
    "torn_name": "TestWarrior",
    "level": 55,
    "title": "Veteran",
    "donator": True,
    "status": "Okay",
    "faction_position": "Member",
    "age_days": 730,
    "company": {
        "name": "Warriors Auto Shop",
        "type": "Auto Dealership",
        "days_old": 45,
        "rating": 3,
        "employee_count": 6,
        "director_name": "TestWarrior",
    },
    "job_position": "Director",
    "company_name": "Warriors Auto Shop",
    "fetched_at": _dt.now(),
}
memory_db.save_player_profile(mock_discord_id, mock_profile)
ctx = player_intel.get_player_context(mock_discord_id)

ctx_checks = [
    ("Level 55", "level in context"),
    ("Veteran",  "title in context"),
    ("Donator",  "donator flag in context"),
    ("Warriors Auto Shop", "company name in context"),
    ("3 stars",  "company stars in context"),
    ("45 days",  "company age in context"),
    ("6 staff",  "employee count in context"),
]
for keyword, note in ctx_checks:
    if keyword.lower() in ctx.lower():
        ok(f"[{note}] '{keyword}' found in context")
        passed += 1
    else:
        fail(f"[{note}] '{keyword}' MISSING from context: {ctx[:200]}")
        failed += 1

# Cleanup mock
memory_db.player_profiles_col.delete_one({"discord_id": mock_discord_id})


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
total = passed + failed
header("RESULTS")
print(f"  {GREEN}{passed}{RESET} passed  |  {RED}{failed}{RESET} failed  |  {total} total")
if failed == 0:
    print(f"  {GREEN}{BOLD}All tests passed!{RESET}")
elif failed / total > 0.3:
    print(f"  {RED}More than 30% failure rate — investigate.{RESET}")
else:
    print(f"  {YELLOW}Some failures — check above.{RESET}")
sys.exit(0 if failed == 0 else 1)
