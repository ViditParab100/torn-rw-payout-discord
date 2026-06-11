import os
import certifi
from pymongo import MongoClient
from datetime import datetime, timedelta

# 1. Setup Connection
# Using certifi.where() ensures a secure handshake with MongoDB Atlas
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())

# Database & Collections
db = client["FactionMemory"]
wars_collection = db["wars"]
keys_collection = db["user_keys"]
lore_col = db["lore"]
milestone_col = db["milestones"]
conversations_col = db["conversations"]
faction_stats_col = db["faction_stats"]
player_profiles_col = db["player_profiles"]
faction_members_col = db["faction_members"]

# ==========================================
# API KEY VAULT (Secure Storage)
# ==========================================

def save_user_key(discord_id, api_key):
    """Saves or updates a user's Torn API key permanently."""
    keys_collection.update_one(
        {"discord_id": str(discord_id)}, 
        {"$set": {"api_key": api_key}}, 
        upsert=True
    )

def get_user_key(discord_id):
    """Fetches the user's API key."""
    user = keys_collection.find_one({"discord_id": str(discord_id)})
    return user["api_key"] if user else None

# ==========================================
# WAR HISTORY & CACHE (AI Analytics)
# ==========================================

def save_war(data):
    """Dumps the modulated Torn API dictionary into the cloud."""
    if wars_collection.find_one({"war_id": data['war_id']}):
        return False 
    
    print(f"📦 Storing War {data['war_id']} in FactionMemory...")
    wars_collection.insert_one(data)
    return True

def get_cached_war(war_id):
    """Pulls the full dictionary back from the cloud."""
    return wars_collection.find_one({"war_id": war_id})

def get_last_5_wars_stats():
    """Calculates historical averages for AI 'Improver' and 'MIA' logic."""
    recent_wars = list(wars_collection.find().sort("war_id", -1).limit(5))
    
    if not recent_wars:
        return {}

    history = {}
    for war in recent_wars:
        for member in war.get('members', []):
            name = member['name']
            hits = member['war_hits']
            
            if name not in history:
                history[name] = {'total_hits': 0, 'war_count': 0, 'max_hits': 0}
            
            history[name]['total_hits'] += hits
            history[name]['war_count'] += 1
            if hits > history[name]['max_hits']:
                history[name]['max_hits'] = hits
                
    final_stats = {}
    for name, data in history.items():
        final_stats[name] = {
            "avg_hits": round(data['total_hits'] / data['war_count'], 1),
            "max_hits": data['max_hits']
        }
        
    return final_stats

# ==========================================
# DYNAMIC LORE (Jeremy's Personal Memories)
# ==========================================

def update_player_lore(username, new_bit):
    """
    Adds a new memory to a player's file.
    When the active lore_bits cap (10) is exceeded, displaced facts are moved to
    archived_lore_bits rather than being silently discarded.
    """
    username_lower = username.lower()
    doc = lore_col.find_one({"username": username_lower})
    bits = doc.get("lore_bits", []) if doc else []

    # Facts that will be displaced when we add one and keep only the last 10
    displaced = bits[:max(0, len(bits) + 1 - 10)]

    update_ops = {
        "$set": {"username_display": username},
        "$push": {
            "lore_bits": {
                "$each": [new_bit],
                "$slice": -10
            }
        }
    }
    if displaced:
        update_ops["$addToSet"] = {
            "archived_lore_bits": {"$each": displaced}
        }

    lore_col.update_one({"username": username_lower}, update_ops, upsert=True)

    # Mirror into ChromaDB for semantic search — lazy import to avoid circular load at module init
    try:
        import lore_db
        lore_db.index_player_lore(username, new_bit)
    except Exception:
        pass

def get_player_lore(username):
    """Fetches combined memory string."""
    data = lore_col.find_one({"username": username.lower()})
    if data and "lore_bits" in data:
        return " | ".join(data["lore_bits"])
    return "Nothing known yet."

# ==========================================
# FACTION MILESTONES (The Faction Record)
# ==========================================

def add_faction_milestone(achievement, provided_date=None, milestone_type="general",
                          value=0, war_id=None, player=None, auto=False):
    """
    Records a faction achievement.
    milestone_type: "general" for manual chat additions, or a structured type for auto-detected records.
    value: numeric value used for record comparison (hits, chain length, respect total, etc).
    auto: True when computed from API data, False when extracted from chat.
    Backward-compatible: callers that only pass (achievement, date) still work fine.
    """
    if provided_date and provided_date.lower().strip() not in ["none", "n/a", "today", "now", ""]:
        record_date = provided_date.strip()
    else:
        record_date = datetime.now().strftime("%Y-%m-%d")

    milestone_col.insert_one({
        "type": milestone_type,
        "achievement": achievement,
        "value": value,
        "date": record_date,
        "war_id": war_id,
        "player": player,
        "auto": auto
    })

def get_milestone_record(milestone_type, player=None):
    """
    Returns the highest stored value for a given milestone type.
    Used by milestone_detector to check whether a new result beats the current record.
    Returns None if no record exists yet.
    """
    query = {"type": milestone_type}
    if player:
        query["player"] = player
    doc = milestone_col.find_one(query, sort=[("value", -1)])
    return doc["value"] if doc else None

def get_faction_milestones():
    """Returns the 5 most recent achievements (any type). Used for backward compat."""
    docs = list(milestone_col.find().sort("_id", -1).limit(5))
    return [{"Achievement": d["achievement"], "Date": d["date"]} for d in docs]

def get_faction_highlights():
    """
    Smart milestone context for Jeremy:
    - Best record of each auto-detected type (chain record, hit record, respect milestone)
    - Last 4 manually-added (general) milestones from chat
    Combined, this gives Jeremy both historical records and recent achievements.
    """
    highlights = []
    record_types = [
        "faction_chain_record",
        "chain_first_100",
        "chain_first_1000",
        "chain_first_2500",
        "faction_top_single_war_hits",
        "member_hit_record",
        "faction_respect_total",
        "win_streak",
        "faction_wars_won",
        "biggest_win_margin",
    ]
    for rtype in record_types:
        doc = milestone_col.find_one({"type": rtype}, sort=[("value", -1)])
        if doc:
            highlights.append({"Achievement": doc["achievement"], "Date": doc["date"]})

    # Include both new "general" type and legacy docs that predate the type field
    manual = list(milestone_col.find(
        {"$or": [{"type": "general"}, {"type": {"$exists": False}}]}
    ).sort("_id", -1).limit(4))
    for d in manual:
        highlights.append({"Achievement": d["achievement"], "Date": d["date"]})

    return highlights if highlights else [{"Achievement": "No milestones recorded yet.", "Date": ""}]

# ==========================================
# EPISODIC MEMORY (Conversation Summaries)
# ==========================================

def save_conversation_summary(summary, players_mentioned=None):
    """Stores a compressed summary of a conversation for Jeremy's episodic recall."""
    conversations_col.insert_one({
        "summary": summary,
        "players": players_mentioned or [],
        "timestamp": datetime.now()
    })

def get_recent_summaries(limit=3):
    """Returns recent conversation summaries so Jeremy can recall past exchanges."""
    docs = list(conversations_col.find().sort("timestamp", -1).limit(limit))
    return [d["summary"] for d in docs]

# ==========================================
# WAR HISTORY CONTEXT (for Jeremy's answers)
# ==========================================

def get_recent_war_history(months=12, limit=15):
    """
    Returns a formatted war history string for Jeremy's context window.
    Includes win/loss, opponent, date, score margin, and top hitter per war.
    """
    cutoff_ts = int((datetime.now() - timedelta(days=months * 30)).timestamp())
    wars = list(wars_collection.find(
        {"start_ts": {"$gte": cutoff_ts}}
    ).sort("start_ts", -1).limit(limit))

    if not wars:
        return "No war history available for the requested period."

    lines = []
    for w in wars:
        result = w.get("result", "?").upper()
        opp = w.get("opponent_name", "?")
        date = w.get("date", "?")
        our = w.get("our_score", 0)
        their = w.get("their_score", 0)
        margin = w.get("margin", 0)
        sign = "+" if margin >= 0 else ""

        members = w.get("members", [])
        if members:
            top = max(members, key=lambda m: m.get("war_hits", 0))
            top_str = f"MVP: {top['name']} {top['war_hits']} hits"
        else:
            top_str = ""

        lines.append(
            f"{date} | {result:<4} | vs {opp:<30} | Score {our:.0f}–{their:.0f} ({sign}{margin:.0f}) | {top_str}"
        )

    return "\n".join(lines)


# ==========================================
# FFSCOUTER INTEL CACHE
# ==========================================

def save_faction_intel(faction_id, faction_name, intel_data):
    """Caches FFScouter intel for a faction. Upserts by faction_id."""
    faction_stats_col.replace_one(
        {"faction_id": faction_id},
        {
            "faction_id": faction_id,
            "faction_name": faction_name,
            "intel": intel_data,
            "fetched_at": datetime.now()
        },
        upsert=True
    )

def get_faction_intel(faction_id):
    """Returns cached FFScouter data for a faction, or None."""
    return faction_stats_col.find_one({"faction_id": faction_id})


# ==========================================
# PLAYER PROFILE CACHE (Torn API enrichment)
# ==========================================

def save_player_profile(discord_id, profile_data):
    """Upserts a player's Torn profile cache (keyed by Discord ID)."""
    player_profiles_col.replace_one(
        {"discord_id": str(discord_id)},
        {**profile_data, "discord_id": str(discord_id)},
        upsert=True
    )

def get_player_profile(discord_id):
    """Returns the cached Torn profile dict for a player, or None."""
    return player_profiles_col.find_one(
        {"discord_id": str(discord_id)},
        {"_id": 0}
    )


# ==========================================
# FACTION MEMBER REGISTRY (genders + torn IDs)
# ==========================================

def save_faction_member(torn_id, torn_name, gender=None, extra=None):
    """
    Upserts a faction member record. Used primarily for gender + torn_id storage.
    extra: optional dict of additional fields to merge in.
    """
    doc = {"torn_id": torn_id, "torn_name": torn_name}
    if gender is not None:
        doc["gender"] = gender
    if extra:
        doc.update(extra)
    faction_members_col.update_one(
        {"torn_id": torn_id},
        {"$set": doc},
        upsert=True
    )

def get_all_genders():
    """Returns {torn_name: gender} for all stored members. None values excluded."""
    docs = list(faction_members_col.find(
        {"gender": {"$exists": True, "$ne": None}},
        {"torn_name": 1, "gender": 1, "_id": 0}
    ))
    return {d["torn_name"]: d["gender"] for d in docs}

def get_member_torn_id(torn_name):
    """Look up a player's Torn ID by their display name. Returns None if not found."""
    doc = faction_members_col.find_one({"torn_name": torn_name}, {"torn_id": 1})
    return doc["torn_id"] if doc else None


def get_war_period_stats(months=6):
    """
    Returns aggregate stats for the last N months: record, top performer, win/loss streak.
    Used when Jeremy is asked about overall recent performance.
    """
    cutoff_ts = int((datetime.now() - timedelta(days=months * 30)).timestamp())
    wars = list(wars_collection.find(
        {"start_ts": {"$gte": cutoff_ts}}
    ).sort("start_ts", 1))

    if not wars:
        return {}

    wins = sum(1 for w in wars if w.get("result") == "win")
    losses = len(wars) - wins

    # Top performer across the period
    player_hits = {}
    for w in wars:
        for m in w.get("members", []):
            name = m["name"]
            player_hits[name] = player_hits.get(name, 0) + m.get("war_hits", 0)
    top_player = max(player_hits.items(), key=lambda x: x[1], default=("?", 0))

    # Current streak from most recent wars
    streak, streak_type = 0, None
    for w in reversed(wars):
        r = w.get("result")
        if streak_type is None:
            streak_type = r
        if r == streak_type:
            streak += 1
        else:
            break

    return {
        "period_months": months,
        "total_wars": len(wars),
        "wins": wins,
        "losses": losses,
        "top_player": top_player[0],
        "top_player_hits": top_player[1],
        "current_streak": streak,
        "current_streak_type": streak_type,
        "first_war_date": wars[0].get("date", ""),
        "last_war_date": wars[-1].get("date", "")
    }