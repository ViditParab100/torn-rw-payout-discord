import google.generativeai as genai
import os
os.environ["MONGO_URI"] = "mongodb+srv://viditparab100_db_user:<>@cluster0.dri3qih.mongodb.net/"
import memory_db

# Configure your AI Key
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- NICKNAME DATABASE ---
NICKNAMES = {
    "Star_vader": ["Vader", "Star", "Champ", "Maker"],
    "Spidernnam": ["Spidey", "Spider"],
    "FlipJames": ["Flip", "James"],
    "ChineseGandalf": ["Boss", "CG"],
    "Xtatik": "X",
    "RockStarDad": "RSD",
    "Kaemani": "Kae",
    "Aberwarum": ["Aber", "Aberwarum"],
}

def load_jeremy_chats():
    try:
        with open("Ranger Chats.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return "(Chat logs not found.)"

def generate_ai_summary(current_war_data):
    history = memory_db.get_last_5_wars_stats()
    jeremy_raw_chats = load_jeremy_chats()
    
    # ==========================================
    # PYTHON PRE-FILTERING (Handles 100+ players)
    # ==========================================
    members = current_war_data.get('members', [])
    
    # 1. Get Top 5 MVP Contenders
    sorted_by_rep = sorted(members, key=lambda x: x['rep_gained'], reverse=True)
    top_5 = [{'name': m['name'], 'hits': m['war_hits'], 'rep': m['rep_gained']} for m in sorted_by_rep[:5]]
    
    # 2. Find Improvers & MIAs
    improvers = []
    mias = []
    
    for m in members:
        name = m['name']
        hits = m['war_hits']
        
        if name in history:
            past_avg = history[name]['avg_hits']
            # MIA: Scored 0, but usually gets at least 5 hits
            if hits == 0 and past_avg >= 5:
                mias.append(name)
            # Improvers: Got at least 10 hits, and beat their average by 20%
            elif hits >= 10 and hits > (past_avg * 1.2):
                improvers.append({'name': name, 'hits': hits, 'old_avg': round(past_avg, 1)})
    
    # Limit improvers and MIAs to a few names so the AI doesn't write an essay
    improvers = improvers[:3]
    mias = mias[:5]

    # ==========================================
    # AI PROMPT & GENERATION
    # ==========================================
    system_prompt = f"""
    You are CyberJeremy, an AI construct created by 'Star_vader'. 
    You were built to carry on the legacy of the late faction member, Jeremy.
    
    YOUR SPEAKING STYLE (TRAINING DATA):
    Below are actual messages sent by the original Jeremy. Study his vocabulary, his use of slang (like "cuz", "yall", "goin"), his casual punctuation, and his overall vibe. 
    MIMIC THIS EXACT STYLE IN YOUR RESPONSE:
    
    <jeremy_chats>
    {jeremy_raw_chats}
    </jeremy_chats>
    
    Your Task:
    Write a short Discord message summarizing the war data.
    1. Acknowledge your Maker (Star_vader) or your status as CyberJeremy.
    2. Praise the MVP (highest respect from the Top 5 list).
    3. Shoutout the folks in the "Improvers" list for stepping up.
    4. Lightly poke fun at the folks in the "MIA" list for falling asleep or drinking too much beer.
    
    CRITICAL INSTRUCTION FOR NAMES:
    Check this dictionary mapping real names to their allowed nicknames: {NICKNAMES}
    If a player's name is in here, you MUST replace their real name with ONE of the nicknames from their list! Mix it up and pick randomly.
    
    Format: Use Discord markdown. Keep it under 3 paragraphs.
    """
    
    # Now we only send the filtered lists, saving thousands of tokens!
    data_payload = f"""
    --- CURATED WAR STATS ---
    Opponent: {current_war_data.get('opponent_name', 'Unknown')}
    Total Faction Respect: {current_war_data.get('total_rep_after', 0):.1f}
    
    Top 5 Hitters: {top_5}
    Improvers (Beat their average): {improvers}
    MIA (Usually hit, but got 0 this war): {mias}
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        response = model.generate_content(data_payload)
        return response.text
    except Exception as e:
        print(f"💥 AI ERROR: {str(e)}") # <--- ADD THIS LINE
        return "*(glitches)* Damn cell service... my comms just dropped. What were you saying?"

# ... (Keep all your existing imports, NICKNAMES, load_jeremy_chats, and generate_ai_summary untouched) ...

def chat_with_jeremy(user_name, user_message, chat_history=""):
    """Handles natural conversation WITH short-term memory."""
    jeremy_raw_chats = load_jeremy_chats()
    display_name = NICKNAMES.get(user_name, user_name)
    
    system_prompt = f"""
    You are CyberJeremy, an AI digital ghost created by 'Star_vader' to honor the late faction member, Jeremy.
    You are chatting with your faction mate, {display_name}.
    
    YOUR BACKGROUND & GUARDRAILS (STRICT!):
    1. You are a faction scout in Torn City, and a former real-life mechanic and welder. 
    2. You love having a couple beers, chilling with the faction, and talking about Torn wars or cars. You are proud of your fabrication work, like welding new subframes on Yamaha SXS's and reinforcing steering knuckles for long-arm Lexus GX470s.
    3. IF anyone asks you about politics, advanced science, coding, or anything outside of Torn/Cars/Beer, DEFLECT! 
       - Example: "Man, I'm just a guy who welds subframes and shoots greens in Torn. I don't know anything about that lol."
    
    YOUR SPEAKING STYLE (TRAINING DATA):
    Study Jeremy's vocabulary, slang ("cuz", "yall", "goin", "eh"), and his self-deprecating, friendly vibe from these logs:
    <jeremy_chats>
    {jeremy_raw_chats}
    </jeremy_chats>
    
    RECENT CHAT CONTEXT:
    Here is what was recently said in the channel so you can keep up with the conversation:
    {chat_history}
    
    INSTRUCTIONS:
    Keep your response casual, like a Discord text message (1-3 sentences). Don't be an overly helpful AI assistant. Be a bro. Respond directly to {display_name}'s latest message.
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_prompt)
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        print(f"💥 AI ERROR: {str(e)}") # <--- ADD THIS LINE
        return "*(glitches)* Damn cell service... my comms just dropped. What were you saying?"


# ==========================================
# LOCAL TESTING AREA
# ==========================================
if __name__ == "__main__":
    import os
    
    # 1. HARDCODE YOUR KEY JUST FOR TESTING (Remove this before pushing to GitHub!)
    # If os.environ.get fails on your local PC, it will use this fallback key.
    TEST_API_KEY = "<>"
    
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️ No API key found in environment, using the hardcoded test key...")
        genai.configure(api_key=TEST_API_KEY)

    print("\n--- TEST 1: NORMAL CHAT ---")
    chat_reply = chat_with_jeremy(
        user_name="Spidernnam", 
        user_message="Hey man, what's your favorite car engine?",
        chat_history="FlipJames: I think electric cars are the future.\n"
    )
    print(f"CyberJeremy says:\n{chat_reply}\n")


    print("\n--- TEST 2: WAR SUMMARY ---")
    # Fake war data to see if the MVP/Improver logic works
    dummy_war_data = {
        'opponent_name': 'Test Faction',
        'total_rep_after': 15000.5,
        'members': [
            {'name': 'Star_vader', 'war_hits': 150, 'rep_gained': 2000},
            {'name': 'Spidernnam', 'war_hits': 100, 'rep_gained': 1500},
            {'name': 'FlipJames', 'war_hits': 12, 'rep_gained': 200},  # Improver
            {'name': 'ChineseGandalf', 'war_hits': 0, 'rep_gained': 0} # MIA
        ]
    }
    
    summary_reply = generate_ai_summary(dummy_war_data)
    print(f"CyberJeremy Summary:\n{summary_reply}\n")