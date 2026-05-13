import os
# MONGO_URI and SARVAM_API_KEY: set in Windows User env or Render (Settings → Environment).
import random
import time
from sarvamai import SarvamAI
import memory_db

# 1. Configure Sarvam AI Client
# Make sure to set SARVAM_API_KEY in your Render environment variables!
SARVAM_KEY = os.environ.get("SARVAM_API_KEY")
client = SarvamAI(api_subscription_key=SARVAM_KEY)
MODEL_NAME = "sarvam-105b"

# --- NICKNAME DATABASE ---
NICKNAMES = {
    "Star_vader": ["Vader", "Star", "Champ", "Maker"],
    "Spidernnam": ["Spidey", "Spider", "BotBuster"],
    "FlipJames": ["Flip", "James"],
    "ChineseGandalf": ["Boss", "CG"],
    "Xtatik": ["X", "Chief"],
    "RockStarDad": ["RSD", "Dad"],
    "Kaemani": ["Kae", "Partner"],
    "Aberwarum": ["Aber", "Aberwarum"],
    "Helena" : ["Helen", "HeLen"],
    "Rockless" : ["Audy", "Rockless"],
    "KuroKrysel" : ["Kuro", "Madam Kuro", "Kuxi"],
    "DaEpicGamer" : ["Epic"],
    "Rehsirap" : ["Reh"],
    "Xirken" :  ["Xirken"],
    "Profu" : ["Profu", "Merit hunter"],
    "BulletToothKep" : ["kllepel", "Bullet"],
    "KisUziVertikal" : ["Kis" , "Uzi"],
    "vmurda" : ["vm"],
    "YoungDN" : ["Young", "Mr. Cop"],
    "_Andrew_" : ["Andrew"],
    "Drago3636" : ["Drago", "Real Star_Vader"],
    "Craig_Demon" : ["Craig", "Demon", "Big Guy"],
    "Venomjr"  : ["Venom"],
    "Dizzaster007" : ["Dizz"],
    "luriorealacc" : ["Lurio"],
    "PetrifiedSlug" : ["Slug"],
    "DontBustMyBalls" : ["DBMB", "Master"],
    "Mythkiller" : ["Myth", "Piyush", "Pi"],
    "MarmotMenace" : ["Marmot"]

}

def load_jeremy_chats():
    try:
        with open("Ranger Chats.txt", "r", encoding="utf-8") as file:
            lines = file.readlines()
            # Taking the last 50 lines keeps the prompt context high-quality but slim
            return "".join(lines[-50:])
    except FileNotFoundError:
        return "(Chat logs not found.)"

def get_random_activity():
    activities = [
        "You just finished welding a subframe on a Yamaha SXS and you're wiping grease off your hands.",
        "You are currently drinking a cold beer in the garage.",
        "You are admiring the heavy-duty gusseting you just did on some steering knuckles for a Lexus GX470.",
        "You just woke up from a nap on a shop creeper.",
        "You are loading ammo into your rifle for the next chain.",
        "You are trying to find the 10mm socket you just dropped."
    ]
    return random.choice(activities)

# ==========================================
# 1. WAR SUMMARY GENERATOR
# ==========================================
def generate_ai_summary(current_war_data):
    history = memory_db.get_last_5_wars_stats()
    jeremy_raw_chats = load_jeremy_chats()
    
    # --- PYTHON PRE-FILTERING ---
    members = current_war_data.get('members', [])
    sorted_by_rep = sorted(members, key=lambda x: x['rep_gained'], reverse=True)
    top_5 = [{'name': m['name'], 'hits': m['war_hits'], 'rep': m['rep_gained']} for m in sorted_by_rep[:5]]
    
    improvers = []
    mias = []
    for m in members:
        name, hits = m['name'], m['war_hits']
        if name in history:
            past_avg = history[name]['avg_hits']
            if hits == 0 and past_avg >= 5: 
                mias.append(name)
            elif hits >= 10 and hits > (past_avg * 1.2):
                improvers.append({'name': name, 'hits': hits, 'old_avg': round(past_avg, 1)})
    
    improvers, mias = improvers[:3], mias[:5]
    current_activity = get_random_activity()

    system_prompt = f"""
    You are CyberJeremy, a digital construct of a late Torn member named Jeremy.
    Speaking Style: {jeremy_raw_chats}
    Right Now: {current_activity}
    
    CRITICAL INSTRUCTION FOR NAMES:
    Check this dictionary: {NICKNAMES}
    If a player's name is in here, you MUST replace their real name with ONE of the nicknames from their list! Mix it up and pick randomly.
    
    Goal: Summarize the war. Praise MVP, shoutout an improver, or mock an MIA. Pick 2-3 options. Keep it under 3 paragraphs. It will always be our team player. 
    Don't add ur current_activity when you're making the summary.
    """
    
    data_payload = f"Opponent: {current_war_data.get('opponent_name')} | Top 5: {top_5} | Improvers: {improvers} | MIA: {mias}"

    # RETRY LOGIC (Handle 429 errors)
    for attempt in range(3):
        try:
            response = client.chat.completions(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": data_payload}
                ],
                temperature=0.85
            )
            return response.choices[0].message.content
        except Exception as e:
            if "429" in str(e):
                print(f"⚠️ Sarvam Rate Limit. Attempt {attempt+1}/3. Waiting...")
                time.sleep(5)
                continue
            print(f"💥 SARVAM ERROR: {e}")
            return "*(glitches)* Damn cell service... my comms just dropped. What were you saying?"
            
    return "*(static)* Comms are too busy right now, man. Grab me a beer and try in a minute."

# ==========================================
# 2. NATURAL CHAT GENERATOR
# ==========================================
def chat_with_jeremy(user_name, user_message, chat_history=""):
    jeremy_raw_chats = load_jeremy_chats()
    current_activity = get_random_activity()
    
    system_prompt = f"""
    You are CyberJeremy, an AI digital ghost created by 'Star_vader' to honor the late faction member, Jeremy.
    You are chatting with your faction mate, {user_name}.
    
    RIGHT NOW: {current_activity}
    Speaking Style: {jeremy_raw_chats}
    
    RULES: 
    - Check nicknames in {NICKNAMES} and use them if applicable.
    - Deflect topics outside of Torn City, cars, welding, or beer.
    - Use the provided chat history to stay in context: {chat_history}
    
    Keep it casual (1-3 sentences). Be a bro, not an assistant.
    """
    
    try:
        response = client.chat.completions(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{user_name} says: {user_message}"}
            ],
            temperature=0.85
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"💥 SARVAM ERROR: {e}")
        return "*(wiping grease)* Sorry man, my signal just cut out. What was that?"

# ==========================================
# LOCAL TESTING AREA (15 Folks Stress Test)
# ==========================================
if __name__ == "__main__":
    #SET YOUR KEY HERE LOCALLY FOR THE TEST
    

    print("\n--- TEST 1: CHAT VIBE ---")
    print(chat_with_jeremy("Spidernnam", "Yo Jeremy, you think electric cars are gonna kill the hobby?"))

    print("\n--- TEST 2: 15-MEMBER WAR SUMMARY ---")
    dummy_war_data = {
        'opponent_name': 'The Velvet Cartel',
        'total_rep_after': 42069.8,
        'members': [
            {'name': 'Star_vader', 'war_hits': 165, 'rep_gained': 3200.5},
            {'name': 'Spidernnam', 'war_hits': 142, 'rep_gained': 2850.2},
            {'name': 'RockStarDad', 'war_hits': 110, 'rep_gained': 2100.0},
            {'name': 'ChineseGandalf', 'war_hits': 95, 'rep_gained': 1950.8},
            {'name': 'Xtatik', 'war_hits': 88, 'rep_gained': 1800.3},
            {'name': 'Kaemani', 'war_hits': 75, 'rep_gained': 1200.0}, 
            {'name': 'Aberwarum', 'war_hits': 68, 'rep_gained': 1100.5},
            {'name': 'FlipJames', 'war_hits': 0, 'rep_gained': 0}
        ]
    }
    
    print(generate_ai_summary(dummy_war_data))