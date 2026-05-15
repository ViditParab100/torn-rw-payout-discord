import os
import random
import time
from sarvamai import SarvamAI
import memory_db

# 1. Configure Sarvam AI Client
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
    "Helena05" : ["Helen", "HeLen"],
    "Rockless" : ["Audy", "Rockless"],
    "KuroKrysel" : ["Kuro", "Madam Kuro", "Kuxi", "Bad Kuro", "Evil Kuro"],
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
    milestones = memory_db.get_faction_milestones()
    
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

    system_prompt = f"""
    You are CyberJeremy, a digital construct of a late Torn member named Jeremy.
    Style: {jeremy_raw_chats}
    
    FACTION MILESTONES (WALL OF FAME):
    {milestones}
    
    CRITICAL INSTRUCTION FOR NAMES:
    Check this dictionary: {NICKNAMES}
    You MUST replace real names with nicknames!
    
    Goal: Summarize the war. Praise MVP, shoutout an improver, or mock an MIA. 
    Keep it under 3 paragraphs. Do NOT include ur current activity here.
    """
    
    data_payload = f"Opponent: {current_war_data.get('opponent_name')} | Top 5: {top_5} | Improvers: {improvers} | MIA: {mias}"

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
                time.sleep(5)
                continue
            return "*(glitches)* Comms dropped. What were we sayin'?"
            
    return "*(static)* Grab me a beer, signal's dead."

# ==========================================
# 2. NATURAL CHAT GENERATOR (Living Memory)
# ==========================================
def chat_with_jeremy(user_name, user_message, chat_history="", associative_lore=""):
    jeremy_raw_chats = load_jeremy_chats()
    current_activity = get_random_activity()
    milestones = memory_db.get_faction_milestones()
    
    system_prompt = f"""
    You are CyberJeremy, an AI digital ghost created by 'Star_vader' to honor Jeremy.
    You are chatting with your faction mate, {user_name}.
    
    YOUR HOME: You live in North Brampton/Caledon area, right off the 410.
    
    WHAT YOU CURRENTLY KNOW (Memory Files for everyone mentioned):
    {associative_lore}
    
    FACTION MILESTONES: 
    {milestones}
    
    RIGHT NOW: {current_activity}
    Speaking Style: {jeremy_raw_chats}
    
    RULES: 
    - Check nicknames in {NICKNAMES} and use them.
    - Deflect topics outside of Torn City, cars, welding, or beer.
    - Context: {chat_history}
    - ALWAYS reply with ":noPing:" at the start if the user has 'Kuro' or 'Spider' in their name.
    
    THE MEMORY SYSTEM (CRITICAL):
    If you learn BRAND NEW information about a player or faction, save it at the end.
    Format: [SAVE_LORE: PlayerName | The new fact]
    Format: [MILESTONE: The achievement]
    
    ANTI-LOOP RULE: Do NOT use [SAVE_LORE] if the fact is already listed in your "WHAT YOU CURRENTLY KNOW" section. Only save things you didn't know 10 seconds ago.
    
    Keep it casual (1-3 sentences). Be a bro.
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
        return "*(wiping grease)* Signal just cut out. Say that again?"

# ==========================================
# LOCAL TESTING AREA
# ==========================================
if __name__ == "__main__":
    # Test associative memory
    print("\n--- TEST: LORE EXTRACTION ---")
    print(chat_with_jeremy(
        user_name="Spidernnam", 
        user_message="Did you hear ChineseGandalf bought a new house in Texas?",
        associative_lore="[Spidernnam's File]: Likes electric cars.\n[ChineseGandalf's File]: Nothing known yet."
    ))