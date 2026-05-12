import os
# 1. Set your MongoDB URI locally
os.environ["MONGO_URI"] = "mongodb+srv://viditparab100_db_user:<>@cluster0.dri3qih.mongodb.net/"

import main_logic
import memory_db
import time



# 2. Your API Key
API_KEY = "ArdyKEZzOKwSZ1xy"

# 3. Put the 5 War IDs you want to backfill in this list
HISTORICAL_WARS = [
    37662, 
    38373, 
    39117, 
    40149, 
    40926
]

def modulate_for_ai(raw_data):
    """Strips out all the Excel/Financial junk so we only save what the AI needs."""
    slim_members = []
    
    # Only keep Name, Hits, and Respect for each member
    for m in raw_data.get('members', []):
        slim_members.append({
            'name': m['name'],
            'war_hits': m['war_hits'],
            'rep_gained': m['rep_gained']
        })
        
    # Return a much smaller, cleaner dictionary
    return {
        'war_id': raw_data['war_id'],
        'opponent_name': raw_data['opponent_name'],
        'members': slim_members
    }

def backfill_wars():
    print("🚀 Starting Historical Data Backfill...")
    
    for war_id in HISTORICAL_WARS:
        print(f"\n🔍 Scouting historical War ID: {war_id}...")
        
        try:
            # 1. Fetch the massive Accountant payload
            raw_war_data = main_logic.run_payout_logic(
                api_key=API_KEY, 
                total_payout_cash=0, 
                medical_cost=0, 
                assist_pay=0, 
                outside_hit_val=0, 
                outside_hit_limit=0, 
                manual_war_id=war_id
            )
            
            # 2. Modulate it! Strip out the junk.
            clean_war_data = modulate_for_ai(raw_war_data)
            
            print(f"Extracted Clean Data for vs {clean_war_data['opponent_name']}")
            
            # 3. Save the clean, tiny dictionary to MongoDB
            success = memory_db.save_war(clean_war_data)
            
            if success:
                print(f"✅ Successfully locked War {war_id} into MongoDB!")
            else:
                print(f"⚠️ War {war_id} is already in the database. Skipped.")
                
        except Exception as e:
            print(f"❌ Failed to fetch War {war_id}. Error: {e}")
            
        # Polite 3-second pause so we don't trip the Torn API rate limit
        time.sleep(3) 

    print("\n🎉 Backfill Complete! CyberJeremy now has his memories.")

if __name__ == "__main__":
    backfill_wars()