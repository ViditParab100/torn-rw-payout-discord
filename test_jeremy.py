"""
CyberJeremy Test Suite
======================
Five layers:
  1. Semantic search (fast, deterministic) — expected player in top N results
  2. Meaning equivalence — two phrasings should surface the same player
  3. Jeremy chat (slower, generative) — keyword checks on live Sarvam responses
  4. Player intel — title tier logic, context formatting (no API needed)
  5. FFScouter matchup — per-player stat comparison logic (no API needed)

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

    # Layer 3 matchup test: Jeremy mentions stat comparison when asked
    CHAT_CASES.append((
        "Star_vader",
        "hey jeremy how was the stat difference last war? who should we be hitting?",
        ["ratio", "stat", "bs", "hit", "sweet", "matchup", "0.8", "1.1", "1.2",
         "dominate", "outclass", "run free", "battle"],
        "stat difference query → Jeremy references matchup mechanics"
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

# 4c: Lore archiving — add 11 facts, verify the oldest is archived
TEST_PLAYER_ARCHIVE = "ArchiveTestPlayer_999"
memory_db.lore_col.delete_one({"username": TEST_PLAYER_ARCHIVE.lower()})  # clean slate

for i in range(11):
    memory_db.update_player_lore(TEST_PLAYER_ARCHIVE, f"Fact number {i}")

doc = memory_db.lore_col.find_one({"username": TEST_PLAYER_ARCHIVE.lower()})
active_bits = doc.get("lore_bits", []) if doc else []
archived_bits = doc.get("archived_lore_bits", []) if doc else []

# Active should have last 10 (Facts 1-10), archived should have Fact 0
archive_ok = "Fact number 0" in archived_bits
active_ok = len(active_bits) == 10 and "Fact number 10" in active_bits

if archive_ok:
    ok("[lore archive] displaced fact stored in archived_lore_bits")
    passed += 1
else:
    fail(f"[lore archive] 'Fact number 0' not in archived: {archived_bits[:3]}")
    failed += 1

if active_ok:
    ok("[lore archive] active lore_bits capped at 10 with newest fact present")
    passed += 1
else:
    fail(f"[lore archive] active bits={len(active_bits)}, expected 10: {active_bits[:3]}")
    failed += 1

memory_db.lore_col.delete_one({"username": TEST_PLAYER_ARCHIVE.lower()})

# 4d: Gender dict loaded correctly
import ai_engine
known_female = ["KuroKrysel", "Helena05", "Rockless"]
known_male   = ["Star_vader", "ChineseGandalf", "RockStarDad", "FlipJames", "JNRanger"]

for name in known_female:
    if ai_engine.PLAYER_GENDERS.get(name) == "Female":
        ok(f"[gender seed] {name} = Female")
        passed += 1
    else:
        fail(f"[gender seed] {name} expected Female, got {ai_engine.PLAYER_GENDERS.get(name)}")
        failed += 1

for name in known_male:
    if ai_engine.PLAYER_GENDERS.get(name) == "Male":
        ok(f"[gender seed] {name} = Male")
        passed += 1
    else:
        fail(f"[gender seed] {name} expected Male, got {ai_engine.PLAYER_GENDERS.get(name)}")
        failed += 1


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 5 — FFScouter matchup logic (pure unit tests, no API needed)
# ══════════════════════════════════════════════════════════════════════════════
header("LAYER 5 — FFScouter matchup logic (pure unit tests)")

import ffscouter

# Mock data mirrors the structure returned by ffscouter.scout_faction():
#   members: {player_id (int or str): {name, bs_estimate, bs_estimate_human, fair_fight}}
#   avg_bs, total_bs, member_count, faction_name, top_fighter

_MOCK_OURS = {
    "faction_name": "KO WeightRoom",
    "member_count": 3,
    "total_bs": 17_000_000,
    "avg_bs": 5_666_667,
    "avg_bs_human": "5.7m",
    "top_fighter": {"name": "AlphaStrike", "bs_human": "10.0m"},
    "members": {
        1001: {
            "name": "AlphaStrike",
            "bs_estimate": 10_000_000,
            "bs_estimate_human": "10.0m",
            "fair_fight": 1.0,
        },
        1002: {
            "name": "BetaBrawler",
            "bs_estimate": 5_000_000,
            "bs_estimate_human": "5.0m",
            "fair_fight": 1.0,
        },
        1003: {
            "name": "GammaGrappler",
            "bs_estimate": 2_000_000,
            "bs_estimate_human": "2.0m",
            "fair_fight": 1.0,
        },
    },
}

_MOCK_THEIRS = {
    "faction_name": "Enemy Faction",
    "member_count": 3,
    "total_bs": 14_000_000,
    "avg_bs": 4_666_667,
    "avg_bs_human": "4.7m",
    "top_fighter": {"name": "EnemyKing", "bs_human": "8.0m"},
    "members": {
        2001: {
            "name": "EnemyKing",
            "bs_estimate": 8_000_000,
            "bs_estimate_human": "8.0m",
            "fair_fight": 1.0,
        },
        2002: {
            "name": "EnemyMid",
            "bs_estimate": 4_500_000,
            "bs_estimate_human": "4.5m",
            "fair_fight": 1.0,
        },
        2003: {
            "name": "EnemyWeak",
            "bs_estimate": 1_500_000,
            "bs_estimate_human": "1.5m",
            "fair_fight": 1.0,
        },
    },
}

_report = ffscouter.player_matchup_report(_MOCK_OURS, _MOCK_THEIRS)
_report_lower = _report.lower()


def check_report(condition, note, detail=""):
    global passed, failed
    if condition:
        ok(f"[matchup] {note}")
        passed += 1
    else:
        fail(f"[matchup] {note}" + (f" | {detail}" if detail else ""))
        failed += 1


# 5a: Sweet spot detection
# BetaBrawler (5m) vs EnemyMid (4.5m): ratio = 4.5/5.0 = 0.90 → sweet spot ✅
check_report(
    "betabrawler" in _report_lower and "enemymid" in _report_lower,
    "BetaBrawler vs EnemyMid appears as sweet-spot pair (ratio 0.90)",
    _report[:300],
)
# AlphaStrike (10m) vs EnemyKing (8m): ratio = 8/10 = 0.80 → sweet spot (boundary) ✅
check_report(
    "alphastrike" in _report_lower and "enemyking" in _report_lower,
    "AlphaStrike vs EnemyKing appears as sweet-spot pair (ratio 0.80 boundary)",
    _report[:300],
)

# 5b: Win zone / can-run-free detection
# AlphaStrike (10m) vs EnemyMid (4.5m): 10m >= 1.2 * 4.5m = 5.4m ✅
# AlphaStrike (10m) vs EnemyWeak (1.5m): 10m >= 1.8m ✅
# AlphaStrike (10m) vs EnemyKing (8m): 10m >= 1.2 * 8m = 9.6m ✅ → beats all 3 → can run free
check_report(
    "alphastrike" in _report_lower and ("run free" in _report_lower or "3/3" in _report),
    "AlphaStrike flagged as can-run-free (beats all 3 enemies at 1.2x)",
    _report,
)

# 5c: GammaGrappler (2m) vs EnemyMid (4.5m): 4.5/2 = 2.25 → NOT sweet spot, NOT win zone
# GammaGrappler should NOT appear paired with EnemyMid
check_report(
    not ("gammagrappler" in _report_lower and "enemymid" in _report_lower),
    "GammaGrappler NOT paired with EnemyMid (ratio 2.25 is outside sweet spot)",
    _report[:400],
)

# 5d: Threat detection
# EnemyKing (8m) vs our avg (5.67m): 8m > 5.67m * 1.2 = 6.8m → threat ✅
check_report(
    "enemyking" in _report_lower and ("watch out" in _report_lower or "threat" in _report_lower),
    "EnemyKing flagged as threat (8m > 1.2x our avg 5.67m)",
    _report,
)
# EnemyWeak (1.5m) is NOT a threat (below our avg)
check_report(
    "watch out" not in _report_lower or "enemyweak" not in _report_lower.split("watch out", 1)[-1][:200],
    "EnemyWeak NOT listed as a threat",
    _report,
)

# 5e: Report contains mechanics legend
check_report(
    "1.2" in _report and "0.8" in _report and "1.1" in _report,
    "Report header contains mechanics ratios (1.2x win / 0.8-1.1 sweet spot)",
    _report[:200],
)

# 5f: Report summary line
check_report(
    "sweet-spot" in _report_lower or "sweet spot" in _report_lower,
    "Report summary mentions sweet-spot count",
    _report[-200:],
)

# 5g: Empty data guards
check_report(
    "not enough" in ffscouter.player_matchup_report(None, None).lower(),
    "Returns error message when both args are None",
)
check_report(
    "not enough" in ffscouter.player_matchup_report({}, _MOCK_THEIRS).lower()
    or "insufficient" in ffscouter.player_matchup_report({}, _MOCK_THEIRS).lower(),
    "Returns error message when our_data is empty dict (no members)",
)

# 5h: Works with string keys (cached MongoDB data has str keys, not int keys)
_mock_theirs_str_keys = dict(_MOCK_THEIRS)
_mock_theirs_str_keys["members"] = {
    str(k): v for k, v in _MOCK_THEIRS["members"].items()
}
_report_str = ffscouter.player_matchup_report(_MOCK_OURS, _mock_theirs_str_keys)
check_report(
    "betabrawler" in _report_str.lower() or "alphastrike" in _report_str.lower(),
    "Report works correctly with string-keyed members dict (MongoDB cache format)",
    _report_str[:200],
)

# 5i: Ratio boundary precision
# Ratio exactly 0.8 is sweet spot (lower bound inclusive)
# Ratio exactly 1.1 is sweet spot (upper bound inclusive)
# Ratio 0.79 is NOT sweet spot
_border_ours = {
    "faction_name": "KOWR", "member_count": 1, "total_bs": 1_000_000,
    "avg_bs": 1_000_000, "avg_bs_human": "1.0m",
    "top_fighter": {"name": "Tester", "bs_human": "1.0m"},
    "members": {99: {"name": "Tester", "bs_estimate": 1_000_000, "bs_estimate_human": "1.0m", "fair_fight": 1.0}},
}
_fmt_bs_simple = lambda v: f"{v/1_000_000:.1f}m" if v >= 1_000_000 else f"{v/1_000:.0f}k"
_border_cases = [
    (800_000,   True,  "ratio 0.80 exactly → sweet spot (lower bound inclusive)"),
    (1_100_000, True,  "ratio 1.10 exactly → sweet spot (upper bound inclusive)"),
    (790_000,   False, "ratio 0.79 → NOT sweet spot (below lower bound)"),
    (1_210_000, False, "ratio 1.21 → NOT sweet spot (win zone, above upper bound)"),
]
for enemy_bs, expect_sweet, note in _border_cases:
    _b_theirs = {
        "faction_name": "Enemy", "member_count": 1, "total_bs": enemy_bs,
        "avg_bs": enemy_bs, "avg_bs_human": _fmt_bs_simple(enemy_bs),
        "top_fighter": {"name": "EnemyBorder", "bs_human": _fmt_bs_simple(enemy_bs)},
        "members": {88: {"name": "EnemyBorder", "bs_estimate": enemy_bs,
                         "bs_estimate_human": _fmt_bs_simple(enemy_bs), "fair_fight": 1.0}},
    }
    ratio = enemy_bs / 1_000_000
    r2 = ffscouter.player_matchup_report(_border_ours, _b_theirs)
    # Check if EnemyBorder appears specifically in the sweet-spot section of the report
    sweet_section = r2.lower().split("sweet spot targets")[-1].split("─")[0] if "sweet spot targets" in r2.lower() else ""
    is_sweet = "enemyborder" in sweet_section
    check_report(is_sweet == expect_sweet, note, f"ratio={ratio:.2f}, sweet_section: {sweet_section[:120]}")


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
