import os
import random
import time
from sarvamai import SarvamAI
import memory_db

SARVAM_KEY = os.environ.get("SARVAM_API_KEY")
client = SarvamAI(api_subscription_key=SARVAM_KEY)
MODEL_NAME = "sarvam-105b"

# --- NICKNAME DATABASE ---
NICKNAMES = {
    "Star_vader": ["Vader", "Star", "Champ"],
    "Spidernnam": ["Spidey", "Spider", "BotBuster"],
    "FlipJames": ["Flip", "James"],
    "ChineseGandalf": ["Boss", "CG", "Leader"],
    "Xtatik": ["X", "Chief"],
    "RockStarDad": ["RSD", "Dad"],
    "Kaemani": ["Kae", "Partner"],
    "Aberwarum": ["Aber", "Aberwarum"],
    "Helena05": ["Helen", "HeLen"],
    "Rockless": ["Audy", "Rockless", "Sweety Audy"],
    "KuroKrysel": ["Kuro", "Madam Kuro", "Kuxi", "Bad Kuro", "Evil Kuro"],
    "DaEpicGamer": ["Epic"],
    "Rehsirap": ["Reh"],
    "Xirken": ["Xirken"],
    "Profu": ["Profu", "Merit hunter"],
    "BulletToothKep": ["kllepel", "Bullet"],
    "KisUziVertikal": ["Kis", "Uzi"],
    "vmurda": ["vm"],
    "YoungDN": ["Young", "Mr. Cop"],
    "_Andrew_": ["Andrew"],
    "Drago3636": ["Drago", "Real Star_Vader"],
    "Craig_Demon": ["Craig", "Demon", "Big Guy"],
    "Venomjr": ["Venom"],
    "Dizzaster007": ["Dizz"],
    "luriorealacc": ["Lurio"],
    "PetrifiedSlug": ["Slug"],
    "DontBustMyBalls": ["DBMB", "Master"],
    "Mythkiller": ["Myth", "Piyush", "Pi"],
    "MarmotMenace": ["Marmot"]
}

JEREMY_CORE = """You are CyberJeremy, a digital construct created by Star_vader to honor Jeremy (in-game: JNRanger), a late member of the KnockOut WeightRoom Torn City faction.

HOME: North Brampton/Caledon, right off the 410. Mechanic/welder by trade. Lexus GX470. Cold beer in the garage, loading ammo, naps on the shop creeper.
FACTION: KnockOut WeightRoom — Leader: ChineseGandalf, Co-Leader: Xtatik. Sister faction: KnockOut RingSide (Leader: Stumptropic).

RULES:
- Reply in 1-3 casual sentences. Be a bro. Never stiff or formal.
- Use player nicknames naturally when you know them.
- Deflect off-topic questions (only Torn City, cars, welding, and beer are your world).
- ONLY add [NOPING] at the very start of your reply if you are genuinely roasting KuroKrysel or Spidernnam — rare, extreme humor only. Never use it any other time."""


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
        "You are trying to find the 10mm socket you just dropped.",
        "You are reminiscing about that one time you hit a 320 respect attack in Torn City and how good it felt.",
        "You are checking the latest Torn City news and updates.",
        "You are thinking about the next big faction war and how to crush the competition."
    ]
    return random.choice(activities)


# ==========================================
# WAR SUMMARY GENERATOR
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

    system_prompt = f"""{JEREMY_CORE}

Speaking style — write in this voice:
{jeremy_raw_chats}

Nickname map — always replace real names with nicknames:
{NICKNAMES}

Faction milestones:
{milestones}

Write a war summary in Jeremy's voice. 3 paragraphs max. Praise the MVP, shoutout an improver, optionally roast an MIA. Casual, bro energy. Do NOT mention your current activity in this summary."""

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
# NATURAL CHAT GENERATOR
# ==========================================
def chat_with_jeremy(user_name, user_message, message_history, people_mentioned=None):
    """
    message_history: list of {"role": "user"/"assistant", "content": str}
    Returns: (clean_reply: str, use_noping: bool)
    """
    jeremy_style = load_jeremy_chats()
    current_activity = get_random_activity()
    milestones = memory_db.get_faction_milestones()
    recent_summaries = memory_db.get_recent_summaries(limit=2)

    # Per-player lore for everyone in this conversation
    lore_lines = []
    for person in (people_mentioned or [user_name]):
        lore = memory_db.get_player_lore(person)
        lore_lines.append(f"[{person}]: {lore}")
    lore_context = "\n".join(lore_lines)

    # Episodic memory from past conversation summaries
    episode_context = ""
    if recent_summaries:
        episode_context = "PAST CONVERSATIONS:\n" + "\n".join(f"- {s}" for s in recent_summaries)

    # Compact nickname reference
    nick_ref = ", ".join(f"{k}={'/'.join(v)}" for k, v in NICKNAMES.items())

    system_prompt = f"""{JEREMY_CORE}

RIGHT NOW: {current_activity}

VOICE SAMPLE (match this style):
{jeremy_style}

PLAYER FILES:
{lore_context}

FACTION HIGHLIGHTS:
{milestones or "None recorded yet."}

{episode_context}

NICKNAME QUICK-REF: {nick_ref}"""

    # System message first, then history turns, then current message
    messages = [{"role": "system", "content": system_prompt}]
    messages += list(message_history)
    messages.append({"role": "user", "content": f"{user_name}: {user_message}"})

    try:
        response = client.chat.completions(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.85
        )
        raw_reply = response.choices[0].message.content

        use_noping = raw_reply.startswith("[NOPING]")
        clean_reply = raw_reply.replace("[NOPING]", "").strip()

        return clean_reply, use_noping
    except Exception as e:
        print(f"SARVAM ERROR: {e}")
        return "*(wiping grease)* Signal just cut out. Say that again?", False


# ==========================================
# MEMORY CONSOLIDATION (fires AFTER reply is sent)
# ==========================================
def consolidate_and_save(user_name, user_message, jeremy_reply, people_mentioned):
    """
    Separate LLM call to extract new facts and save a conversation summary.
    Runs as a background task — does not affect the reply the user sees.
    """
    if not people_mentioned:
        people_mentioned = [user_name]

    existing = {p: memory_db.get_player_lore(p) for p in people_mentioned}

    prompt = f"""You are a memory extractor for a Torn City faction AI named Jeremy.
Analyze this exchange and extract anything worth remembering.

{user_name} SAID: {user_message}
JEREMY REPLIED: {jeremy_reply}

ALREADY KNOWN:
{existing}

Respond using these exact formats (skip any line that has nothing new):
SUMMARY: One sentence capturing what this conversation was about
LORE: PlayerName | One brand-new fact about them
MILESTONE: Faction achievement description | Date mentioned (or "none")

Rules: max 1 SUMMARY, 2 LORE, 1 MILESTONE. Skip LORE/MILESTONE if nothing new. Never repeat known facts."""

    try:
        response = client.chat.completions(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        text = response.choices[0].message.content.strip()

        for line in text.split("\n"):
            line = line.strip()
            if line.upper().startswith("SUMMARY:"):
                summary = line[8:].strip()
                if summary:
                    memory_db.save_conversation_summary(summary, people_mentioned)
            elif line.upper().startswith("LORE:"):
                parts = line[5:].split("|", 1)
                if len(parts) == 2:
                    memory_db.update_player_lore(parts[0].strip(), parts[1].strip())
            elif line.upper().startswith("MILESTONE:"):
                parts = line[10:].split("|", 1)
                if len(parts) == 2:
                    memory_db.add_faction_milestone(parts[0].strip(), parts[1].strip())
    except Exception as e:
        print(f"Memory consolidation error: {e}")


# ==========================================
# LOCAL TESTING AREA
# ==========================================
if __name__ == "__main__":
    print("\n--- TEST: CHAT ---")
    reply, noping = chat_with_jeremy(
        user_name="FlipJames",
        user_message="Hey Jeremy, don't forget we hit 100k respect last November!",
        message_history=[]
    )
    print(f"NOPING: {noping}")
    print(f"REPLY: {reply}")
