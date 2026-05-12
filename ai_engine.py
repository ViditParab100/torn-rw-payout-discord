import google.generativeai as genai
import os
import memory_db

# Configure your AI Key
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# --- NICKNAME DATABASE ---
NICKNAMES = {
    "Star_vader": "Maker",
    "Spidernnam": "Spidey",
    "FlipJames": "Flip",
    "ChineseGandalf": "Boss",
    "Xtatik": "X",
    "RockStarDad": "RSD",
    "Kaemani": "Kae",
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
    Check this dictionary: {NICKNAMES}
    If a player's name is in here, you MUST call them by their assigned nickname!
    
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
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_prompt)
        response = model.generate_content(data_payload)
        return response.text
    except Exception as e:
        return f"*(CyberJeremy's systems glitch)* Damn cell service got me killed. Error: {e}"

# ... (Keep all your existing imports, NICKNAMES, load_jeremy_chats, and generate_ai_summary untouched) ...

def chat_with_jeremy(user_name, user_message, chat_history=""):
    """Handles natural conversation WITH short-term memory."""
    jeremy_raw_chats = load_jeremy_chats()
    display_name = NICKNAMES.get(user_name, user_name)
    
    system_prompt = f"""
    You are CyberJeremy, an AI digital ghost created by 'Star_vader' to honor the late faction member, Jeremy.
    You are chatting with your faction mate, {display_name}.
    
    YOUR BACKGROUND & GUARDRAILS (STRICT!):
    1. You are a faction scout in Torn City, and a former real-life mechanic. You know a LOT about cars, engines, and fixing vehicles.
    2. You love having a couple beers, chilling with the faction, and talking about Torn wars or cars.
    3. IF anyone asks you about politics, advanced science, coding, or anything outside of Torn/Cars/Beer, DEFLECT! 
       - Example: "Man, I just turn wrenches and shoot greens in Torn, I have no clue what you're talking about lol."
    
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
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=system_prompt)
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        return "*(glitches)* Damn cell service... my comms just dropped. What were you saying?"