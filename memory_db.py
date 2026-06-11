import os
import certifi
from pymongo import MongoClient
from datetime import datetime

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
    """Adds a new memory to a player's file using their Name as the key."""
    lore_col.update_one(
        {"username": username.lower()}, # Standardize to lowercase for searching
        {
            "$set": {"username_display": username},
            "$push": {
                "lore_bits": {
                    "$each": [new_bit],
                    "$slice": -10 
                }
            }
        },
        upsert=True
    )

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
        "faction_top_single_war_hits",
        "member_hit_record",
        "faction_respect_total",
        "win_streak",
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