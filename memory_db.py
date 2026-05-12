import os
from pymongo import MongoClient

# 1. Connect to the Cloud Database
mongo_uri = os.environ.get("MONGO_URI")
client = MongoClient(mongo_uri)

# Create/Connect to a database called "FactionMemory"
db = client["FactionMemory"]

# Create/Connect to specific "collections" (folders)
wars_collection = db["wars"]
keys_collection = db["user_keys"]

# ==========================================
# API KEY VAULT
# ==========================================
def save_user_key(discord_id, api_key):
    """Saves or updates a user's Torn API key permanently."""
    keys_collection.update_one(
        {"discord_id": str(discord_id)}, 
        {"$set": {"api_key": api_key}}, 
        upsert=True # Creates it if it doesn't exist, updates if it does
    )

def get_user_key(discord_id):
    """Fetches the user's API key."""
    user = keys_collection.find_one({"discord_id": str(discord_id)})
    return user["api_key"] if user else None

# ==========================================
# WAR HISTORY & CACHE
# ==========================================
def save_war(data):
    """Dumps the entire Torn API dictionary into the cloud permanently."""
    # Check if we already saved this war
    if wars_collection.find_one({"war_id": data['war_id']}):
        return False 
    
    print("I am here in save_war")
    # Just drop the whole dictionary right into MongoDB. It handles the rest.
    wars_collection.insert_one(data)
    return True

def get_cached_war(war_id):
    """Pulls the full dictionary back from the cloud."""
    return wars_collection.find_one({"war_id": war_id})

def get_last_5_wars_stats():
    """Calculates the historical average for players over the last 5 wars."""
    # Grab the 5 most recent wars
    # Changed from "start_time" to "war_id"
    recent_wars = list(wars_collection.find().sort("war_id", -1).limit(5))
    
    if not recent_wars:
        return {}

    history = {}
    
    # Loop through the raw data and calculate the averages ourselves
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
                
    # Format it for the AI Engine
    final_stats = {}
    for name, data in history.items():
        final_stats[name] = {
            "avg_hits": round(data['total_hits'] / data['war_count'], 1),
            "max_hits": data['max_hits']
        }
        
    return final_stats