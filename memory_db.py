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
history_col = db["faction_history"]

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

def add_faction_milestone(achievement):
    """Records a faction achievement with a timestamp."""
    milestone_col.insert_one({
        "achievement": achievement,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

def get_faction_milestones():
    """Returns the 5 most recent achievements for Jeremy to mention."""
    docs = list(milestone_col.find().sort("_id", -1).limit(5))
    return [{"Achievement": d["achievement"], "Date": d["date"]} for d in docs]


# ==========================================
# FACTION HISTORY (Version Controlled)
# ==========================================

def update_faction_history(topic, text, author_name):
    """Saves a historical record. If the topic exists, it adds a new version to the array."""
    from datetime import datetime
    
    # We use a lowercase topic to group things together (e.g. "The First War" == "the first war")
    history_col.update_one(
        {"topic_id": topic.lower().strip()},
        {
            "$set": {"topic_display": topic},
            "$push": {
                "versions": {
                    "text": text,
                    "author": author_name,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
            }
        },
        upsert=True
    )

def get_all_history():
    """Compiles the history, showing the paper trail of who edited what."""
    docs = history_col.find()
    history_str = ""
    
    for doc in docs:
        topic = doc.get("topic_display", "Unknown")
        versions = doc.get("versions", [])
        if not versions: 
            continue
            
        # If only one person recorded it:
        if len(versions) == 1:
            v = versions[0]
            history_str += f"Topic [{topic}]: {v['text']} (Recorded by {v['author']})\n"
        # If multiple people have overwritten/updated it, show the timeline:
        else:
            timeline = " -> ".join([f"'{v['text']}'(by {v['author']})" for v in versions[-3:]]) # Show last 3 edits
            history_str += f"Topic [{topic}] Edit History: {timeline}\n"
            
    return history_str if history_str else "No historical records yet."