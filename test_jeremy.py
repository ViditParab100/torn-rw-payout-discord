"""
CyberJeremy Test Suite
======================
Six layers:
  1. Semantic search (fast, deterministic) — expected player in top N results
  2. Meaning equivalence — two phrasings should surface the same player
  3. Jeremy chat (slower, generative) — keyword checks on live Sarvam responses
  4. Player intel — title tier logic, context formatting (no API needed)
  5. FFScouter matchup — per-player stat comparison text report (no API needed)
  6. Battle report — PDF generator: matchup computation + file output (no API needed)

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
    ("solid",    "company health note in context"),
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
# LAYER 6 — Battle report: matchup computation + PDF generation (no API needed)
# ══════════════════════════════════════════════════════════════════════════════
header("LAYER 6 — Battle report (matchup logic + PDF output)")

import battle_report
import os as _os

# Shared mock data — same 3v3 setup used in Layer 5 for consistency
_BR_OURS = [
    {"name": "AlphaStrike",   "bs_estimate": 10_000_000, "bs_estimate_human": "10.0m"},
    {"name": "BetaBrawler",   "bs_estimate":  5_000_000, "bs_estimate_human":  "5.0m"},
    {"name": "GammaGrappler", "bs_estimate":  2_000_000, "bs_estimate_human":  "2.0m"},
]
_BR_THEIRS = [
    {"name": "EnemyKing",  "bs_estimate": 8_000_000, "bs_estimate_human": "8.0m"},
    {"name": "EnemyMid",   "bs_estimate": 4_500_000, "bs_estimate_human": "4.5m"},
    {"name": "EnemyWeak",  "bs_estimate": 1_500_000, "bs_estimate_human": "1.5m"},
]

_our_p, _their_p = battle_report._compute_matchups(_BR_OURS, _BR_THEIRS)


def chk(cond, note, detail=""):
    global passed, failed
    if cond:
        ok(f"[battle_report] {note}")
        passed += 1
    else:
        fail(f"[battle_report] {note}" + (f" | {detail}" if detail else ""))
        failed += 1


# ── 6a: our_profiles sorted by BS descending ──────────────────────────────────
chk(_our_p[0]["name"] == "AlphaStrike",   "our_profiles[0] is highest-BS player (AlphaStrike 10m)")
chk(_our_p[-1]["name"] == "GammaGrappler","our_profiles[-1] is lowest-BS player (GammaGrappler 2m)")

# ── 6b: their_profiles sorted by BS descending ────────────────────────────────
chk(_their_p[0]["name"] == "EnemyKing",  "their_profiles[0] is highest-BS enemy (EnemyKing 8m)")
chk(_their_p[-1]["name"] == "EnemyWeak", "their_profiles[-1] is lowest-BS enemy (EnemyWeak 1.5m)")

# ── 6c: AlphaStrike (10m) sweet targets ───────────────────────────────────────
# EnemyKing (8m): 8/10 = 0.80 → exactly at lower bound → sweet spot
_alpha_sweet_names = [e[0] for e in _our_p[0]["sweet"]]
chk("EnemyKing" in _alpha_sweet_names,
    "AlphaStrike sweet-spot target: EnemyKing (ratio 0.80, lower bound inclusive)",
    str(_alpha_sweet_names))

# ── 6d: AlphaStrike (10m) domination targets ──────────────────────────────────
# EnemyMid (4.5m): 10 >= 1.2*4.5=5.4 → win
# EnemyWeak (1.5m): 10 >= 1.8 → win
_alpha_win_names = [e[0] for e in _our_p[0]["wins"]]
chk("EnemyMid"  in _alpha_win_names, "AlphaStrike dominates EnemyMid (10m >= 1.2*4.5m)", str(_alpha_win_names))
chk("EnemyWeak" in _alpha_win_names, "AlphaStrike dominates EnemyWeak (10m >= 1.2*1.5m)", str(_alpha_win_names))

# ── 6e: AlphaStrike (10m) has no threats ──────────────────────────────────────
# No enemy has >= 1.2*10=12m BS
chk(len(_our_p[0]["threats"]) == 0,
    "AlphaStrike has zero threats (no enemy >= 12m)",
    str([e[0] for e in _our_p[0]["threats"]]))

# ── 6f: BetaBrawler (5m) sweet/win/threat ─────────────────────────────────────
# EnemyMid (4.5m): 4.5/5 = 0.90 → sweet
# EnemyWeak (1.5m): 5 >= 1.8 → win
# EnemyKing (8m): 8 >= 1.2*5=6 → threat
_beta_sweet   = [e[0] for e in _our_p[1]["sweet"]]
_beta_wins    = [e[0] for e in _our_p[1]["wins"]]
_beta_threats = [e[0] for e in _our_p[1]["threats"]]
chk("EnemyMid"  in _beta_sweet,   "BetaBrawler sweet: EnemyMid (ratio 0.90)")
chk("EnemyWeak" in _beta_wins,    "BetaBrawler win:   EnemyWeak (5m >= 1.2*1.5m)")
chk("EnemyKing" in _beta_threats, "BetaBrawler threat: EnemyKing (8m >= 1.2*5m=6m)")

# ── 6g: GammaGrappler (2m) ────────────────────────────────────────────────────
# EnemyWeak (1.5m): 2 >= 1.2*1.5=1.8 → win
# EnemyMid (4.5m): 4.5 >= 1.2*2=2.4 → threat
# EnemyKing (8m): 8 >= 2.4 → threat
_gamma_wins    = [e[0] for e in _our_p[2]["wins"]]
_gamma_threats = [e[0] for e in _our_p[2]["threats"]]
chk("EnemyWeak" in _gamma_wins,    "GammaGrappler win:    EnemyWeak (2m >= 1.2*1.5m=1.8m)")
chk("EnemyMid"  in _gamma_threats, "GammaGrappler threat: EnemyMid (4.5m >= 1.2*2m=2.4m)")
chk("EnemyKing" in _gamma_threats, "GammaGrappler threat: EnemyKing (8m >= 2.4m)")

# ── 6h: EnemyKing (8m) — enemy perspective ────────────────────────────────────
# AlphaStrike (10m): ratio=10/8=1.25 → NOT sweet, NOT win, IS our_threat (10 >= 9.6)
# BetaBrawler (5m):  ratio=5/8=0.625 → NOT sweet (<0.8), IS win (8 >= 6)
# GammaGrappler (2m): ratio=2/8=0.25 → NOT sweet, IS win (8 >= 2.4)
_eking_wins    = [e[0] for e in _their_p[0]["wins"]]
_eking_threats = [e[0] for e in _their_p[0]["our_threats"]]
chk("BetaBrawler"   in _eking_wins,    "EnemyKing dominates BetaBrawler (8m >= 1.2*5m=6m)")
chk("GammaGrappler" in _eking_wins,    "EnemyKing dominates GammaGrappler (8m >= 2.4m)")
chk("AlphaStrike"   in _eking_threats, "AlphaStrike counters EnemyKing (10m >= 1.2*8m=9.6m)")

# ── 6i: EnemyWeak (1.5m) — all our members counter them ──────────────────────
# All three of our members have BS >= 1.2*1.5=1.8m
_eweak_threats = [e[0] for e in _their_p[2]["our_threats"]]
chk(
    all(n in _eweak_threats for n in ["AlphaStrike", "BetaBrawler", "GammaGrappler"]),
    "All 3 of our members counter EnemyWeak (all >= 1.2*1.5m=1.8m)",
    str(_eweak_threats),
)

# ── 6j: MAX_SHOW cap enforced ─────────────────────────────────────────────────
_cap = battle_report.MAX_SHOW
chk(
    all(len(p["sweet"]) <= _cap and len(p["wins"]) <= _cap and len(p["threats"]) <= _cap
        for p in _our_p),
    f"our_profiles: no cell exceeds MAX_SHOW={_cap} entries",
)
chk(
    all(len(p["sweet"]) <= _cap and len(p["wins"]) <= _cap and len(p["our_threats"]) <= _cap
        for p in _their_p),
    f"their_profiles: no cell exceeds MAX_SHOW={_cap} entries",
)

# ── 6k: Zero-BS and invalid members are filtered out ─────────────────────────
_dirty = _BR_OURS + [
    {"name": "ZeroGuy",    "bs_estimate": 0,    "bs_estimate_human": "0"},
    {"name": "NegativeGuy","bs_estimate": -500,  "bs_estimate_human": "-"},
    {"name": "NotADict"},   # wrong type
]
_clean_p, _ = battle_report._compute_matchups(_dirty, _BR_THEIRS)
_clean_names = [p["name"] for p in _clean_p]
chk("ZeroGuy"     not in _clean_names, "Zero-BS member filtered from profiles")
chk("NegativeGuy" not in _clean_names, "Negative-BS member filtered from profiles")
chk(len(_clean_p) == 3,               "Only the 3 valid members appear after filtering")

# ── 6l: String-keyed members dict (MongoDB cache format) ─────────────────────
_str_ours   = [{"name": m["name"], "bs_estimate": m["bs_estimate"],
                "bs_estimate_human": m["bs_estimate_human"]} for m in _BR_OURS]
_str_theirs = [{"name": m["name"], "bs_estimate": m["bs_estimate"],
                "bs_estimate_human": m["bs_estimate_human"]} for m in _BR_THEIRS]
try:
    _sp, _tp = battle_report._compute_matchups(_str_ours, _str_theirs)
    chk(len(_sp) == 3 and len(_tp) == 3,
        "String-keyed member list produces correct profile count (3+3)",
        f"our={len(_sp)}, their={len(_tp)}")
except Exception as e:
    chk(False, "String-keyed member list raises no exception", str(e))

# ── 6m: PDF generation — produces a valid non-empty file ─────────────────────
_PDF_MOCK_OURS = {
    "faction_name": "KO WeightRoom",
    "member_count": 3, "total_bs": 17_000_000,
    "avg_bs": 5_666_667, "avg_bs_human": "5.7m",
    "top_fighter": {"name": "AlphaStrike", "bs_human": "10.0m"},
    "members": {i: m for i, m in enumerate(_BR_OURS)},
}
_PDF_MOCK_THEIRS = {
    "faction_name": "Enemy Faction",
    "member_count": 3, "total_bs": 14_000_000,
    "avg_bs": 4_666_667, "avg_bs_human": "4.7m",
    "top_fighter": {"name": "EnemyKing", "bs_human": "8.0m"},
    "members": {i: m for i, m in enumerate(_BR_THEIRS)},
}
_pdf_path = "test_battle_report_TEMP.pdf"
try:
    battle_report.generate_battle_report(_PDF_MOCK_OURS, _PDF_MOCK_THEIRS, _pdf_path)
    _exists = _os.path.exists(_pdf_path)
    _size   = _os.path.getsize(_pdf_path) if _exists else 0
    chk(_exists and _size > 1024, f"PDF generated successfully ({_size} bytes)")
except Exception as e:
    chk(False, "PDF generation raised no exception", str(e))
finally:
    if _os.path.exists(_pdf_path):
        _os.remove(_pdf_path)

# ── 6n: PDF generation with large roster (page-break stress test) ─────────────
_big_ours = [
    {"name": f"OurPlayer{i:02d}", "bs_estimate": (30 - i) * 1_000_000,
     "bs_estimate_human": f"{30 - i}.0m"}
    for i in range(20)
]
_big_theirs = [
    {"name": f"Enemy{i:02d}", "bs_estimate": (25 - i) * 1_000_000,
     "bs_estimate_human": f"{25 - i}.0m"}
    for i in range(20)
]
_PDF_BIG_OURS = {
    "faction_name": "KO WeightRoom", "member_count": 20,
    "total_bs": sum(m["bs_estimate"] for m in _big_ours),
    "avg_bs": sum(m["bs_estimate"] for m in _big_ours) // 20,
    "avg_bs_human": "15.5m",
    "top_fighter": {"name": "OurPlayer00", "bs_human": "30.0m"},
    "members": {i: m for i, m in enumerate(_big_ours)},
}
_PDF_BIG_THEIRS = {
    "faction_name": "Enemy Faction", "member_count": 20,
    "total_bs": sum(m["bs_estimate"] for m in _big_theirs),
    "avg_bs": sum(m["bs_estimate"] for m in _big_theirs) // 20,
    "avg_bs_human": "12.5m",
    "top_fighter": {"name": "Enemy00", "bs_human": "25.0m"},
    "members": {i: m for i, m in enumerate(_big_theirs)},
}
_pdf_big_path = "test_battle_report_big_TEMP.pdf"
try:
    battle_report.generate_battle_report(_PDF_BIG_OURS, _PDF_BIG_THEIRS, _pdf_big_path)
    _big_size = _os.path.getsize(_pdf_big_path) if _os.path.exists(_pdf_big_path) else 0
    chk(_big_size > 4096, f"Large-roster PDF (20v20) generated without crash ({_big_size} bytes)")
except Exception as e:
    chk(False, "Large-roster PDF (20v20) raises no exception", str(e))
finally:
    if _os.path.exists(_pdf_big_path):
        _os.remove(_pdf_big_path)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 7 — player_intel enrichment (last_seen, donator flag, company health)
# ══════════════════════════════════════════════════════════════════════════════
header("Layer 7 — player_intel enrichment helpers + get_player_name_context")
import player_intel
from unittest.mock import patch


def pi(cond, note, detail=""):
    global passed, failed
    if cond:
        ok(f"[player_intel] {note}")
        passed += 1
    else:
        fail(f"[player_intel] {note}" + (f" | {detail}" if detail else ""))
        failed += 1


# ── 7a: _fmt_last_seen ────────────────────────────────────────────────────────
pi(
    player_intel._fmt_last_seen({"status": "Online", "relative": "Just now"}) == "Online RIGHT NOW",
    "_fmt_last_seen: Online status -> 'Online RIGHT NOW'",
)
pi(
    player_intel._fmt_last_seen({"status": "Idle", "relative": "5 minutes ago"}) == "5 minutes ago (Idle)",
    "_fmt_last_seen: Idle + relative -> 'X minutes ago (Idle)'",
)
pi(
    player_intel._fmt_last_seen({"status": "Offline", "relative": "3 days ago"}) == "3 days ago (Offline)",
    "_fmt_last_seen: Offline + relative -> 'X days ago (Offline)'",
)
pi(player_intel._fmt_last_seen(None) is None,    "_fmt_last_seen: None input -> None")
pi(player_intel._fmt_last_seen({}) is None,      "_fmt_last_seen: empty dict -> None")
pi(player_intel._fmt_last_seen("bad") is None,   "_fmt_last_seen: non-dict input -> None")

# ── 7b: _company_health_note ──────────────────────────────────────────────────
pi("booming"    in player_intel._company_health_note(5), "_company_health_note(5) -> booming")
pi("pretty well" in player_intel._company_health_note(4), "_company_health_note(4) -> doing pretty well")
pi("solid"      in player_intel._company_health_note(3), "_company_health_note(3) -> solid mid-tier")
pi("struggle"   in player_intel._company_health_note(2), "_company_health_note(2) -> struggle")
pi("struggle"   in player_intel._company_health_note(1), "_company_health_note(1) -> struggle")
pi(player_intel._company_health_note(None) == "",        "_company_health_note(None) -> empty string")

# ── 7c: get_player_name_context — player not in faction_members ───────────────
with patch("memory_db.get_member_torn_id", return_value=None):
    _ctx = player_intel.get_player_name_context("NoSuchPlayer", "FAKEKEY")
    pi(_ctx == "", "Unknown player (no torn_id) -> returns empty string")

# ── 7d: Shared mock profile setup ─────────────────────────────────────────────
_MOCK_PROFILE_BASE = {
    "name": "TestPlayer",
    "level": 55,
    "title": "Legend",
    "donator": False,
    "gender": "Female",
    "age": 730,
    "status": {"state": "Okay", "description": ""},
    "faction": {"position": "Member"},
    "job": {"position": "Director", "company_id": 999, "company_name": "TestCorp"},
    "last_action": {"status": "Idle", "relative": "2 hours ago"},
}

# ── 7e: Non-donator flag — explicitly highlighted ─────────────────────────────
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value={**_MOCK_PROFILE_BASE, "donator": False}),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("NO" in _ctx,       "Non-donator: context contains 'NO'")
    pi("pack" in _ctx,     "Non-donator: context mentions 'pack' (convo hook)")
    pi("asking" in _ctx,   "Non-donator: context includes 'worth asking' prompt for Jeremy")

# ── 7f: Donator flag ──────────────────────────────────────────────────────────
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value={**_MOCK_PROFILE_BASE, "donator": True}),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("Donator: YES" in _ctx, "Donator player: context shows 'Donator: YES'")

# ── 7g: Director company role phrasing ───────────────────────────────────────
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_MOCK_PROFILE_BASE),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("Director/Owner at" in _ctx,
       "Director job_pos -> 'Director/Owner at' phrasing",
       _ctx.split("\n")[-1])

# ── 7h: Employee company role phrasing ────────────────────────────────────────
_EMP_PROFILE = {**_MOCK_PROFILE_BASE, "job": {"position": "Manager", "company_id": 999, "company_name": "TestCorp"}}
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_EMP_PROFILE),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("Manager at" in _ctx,
       "Non-director job_pos -> 'Manager at' phrasing",
       _ctx.split("\n")[-1])

# ── 7i: Last seen appears in context ─────────────────────────────────────────
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_MOCK_PROFILE_BASE),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("Last seen:" in _ctx, "last_action present -> 'Last seen:' line appears in context")
    pi("2 hours ago" in _ctx, "last_action relative time appears verbatim")

# ── 7j: Online RIGHT NOW label ────────────────────────────────────────────────
_ONLINE_PROFILE = {**_MOCK_PROFILE_BASE, "last_action": {"status": "Online", "relative": "Just now"}}
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_ONLINE_PROFILE),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("Online RIGHT NOW" in _ctx, "Online player -> 'Online RIGHT NOW' in context")

# ── 7k: Company health from API (5-star) ──────────────────────────────────────
_CDATA_5STAR = {"type": {"name": "Oil Rig"}, "rating": 5, "employees": [1, 2, 3]}
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_MOCK_PROFILE_BASE),
    patch("player_intel.fetch_company", return_value=_CDATA_5STAR),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("5 stars" in _ctx,    "Company: 5-star rating appears in context")
    pi("booming" in _ctx,    "Company: 5-star health note 'booming' appears")
    pi("Oil Rig" in _ctx,    "Company type name appears in context")

# ── 7l: Company health (2-star — struggling) ──────────────────────────────────
_CDATA_2STAR = {"type": {"name": "Clothing Store"}, "rating": 2, "employees": [1]}
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_MOCK_PROFILE_BASE),
    patch("player_intel.fetch_company", return_value=_CDATA_2STAR),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("struggle" in _ctx,   "Company: 2-star health note 'struggle' appears")

# ── 7m: Non-OK status (hospital/jail) appears ────────────────────────────────
_HOSP_PROFILE = {**_MOCK_PROFILE_BASE, "status": {"state": "Hospital", "description": "Attacked"}}
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_HOSP_PROFILE),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("Hospital" in _ctx,  "Hospital status appears in context")
    pi("Attacked" in _ctx,  "Hospital description detail appears in context")

# ── 7n: No company → no Company line ──────────────────────────────────────────
_NO_JOB_PROFILE = {**_MOCK_PROFILE_BASE, "job": {}}
with (
    patch("memory_db.get_member_torn_id", return_value=12345),
    patch("player_intel.fetch_player_by_id", return_value=_NO_JOB_PROFILE),
    patch("player_intel.fetch_company", return_value=None),
):
    _ctx = player_intel.get_player_name_context("TestPlayer", "FAKEKEY")
    pi("Company:" not in _ctx, "No job -> no Company line in context")


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
