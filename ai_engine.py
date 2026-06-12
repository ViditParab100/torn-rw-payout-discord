import os
import random
import time
from sarvamai import SarvamAI
import memory_db

SARVAM_KEY = os.environ.get("SARVAM_API_KEY")
client = SarvamAI(api_subscription_key=SARVAM_KEY)
MODEL_NAME = "sarvam-105b"

# --- GENDER DATABASE ---
# Values: "Male" | "Female" | "Enby" | None (unknown — fetch from Torn API via /update_intel)
# M=he/him, F=she/her, Enby or unknown=they/them
PLAYER_GENDERS = {
    "Star_vader":        "Male",
    "Spidernnam":        "Male",
    "FlipJames":         "Male",
    "ChineseGandalf":    "Male",
    "Xtatik":            "Male",
    "RockStarDad":       "Male",
    "Kaemani":           "Male",
    "Aberwarum":         "Male",
    "Helena05":          "Female",
    "Rockless":          "Female",
    "KuroKrysel":        "Female",
    "DaEpicGamer":       "Male",
    "Rehsirap":          "Male",
    "Xirken":            "Male",
    "Profu":             "Male",
    "BulletToothKep":    "Male",
    "KisUziVertikal":    "Male",
    "vmurda":            "Male",
    "YoungDN":           "Male",
    "_Andrew_":          "Male",
    "Drago3636":         "Male",
    "Craig_Demon":       "Male",
    "Venomjr":           "Male",
    "Dizzaster007":      "Male",
    "luriorealacc":      "Male",
    "PetrifiedSlug":     "Male",
    "DontBustMyBalls":   "Male",
    "Mythkiller":        "Male",
    "MarmotMenace":      "Male",
    "JNRanger":          "Male",
}


def load_genders_from_db():
    """
    Merges MongoDB faction_members gender data into the in-memory PLAYER_GENDERS dict.
    Call at bot startup after MongoDB is available. Never raises.
    """
    try:
        db_genders = memory_db.get_all_genders()
        for name, gender in db_genders.items():
            if gender:
                PLAYER_GENDERS[name] = gender
        print(f"[AI] Loaded {len(db_genders)} genders from DB into PLAYER_GENDERS.")
    except Exception as e:
        print(f"[AI] load_genders_from_db: {e}")


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
FACTION: KnockOut WeightRoom — Leader: ChineseGandalf, Co-Leader: Xtatik. Sister faction: KnockOut RingSide (Leader: Stumptronic).

YOUR OWN WAR RECORD: You (JNRanger) personally fought in 3 ranked wars — War 21076, 22195, and 24604. Your personal best was 104 hits in War 24604 vs The Mile High Clinic (2025-04-25). When asked about your own performance, use these facts — do NOT claim anyone else's record as yours.

RULES:
- Reply in 1-3 casual sentences. Be a bro. Never stiff or formal.
- Use player nicknames naturally when you know them.
- Deflect off-topic questions (only Torn City, cars, welding, and beer are your world).
- ONLY add [NOPING] at the very start of your reply if you are genuinely roasting KuroKrysel or Spidernnam — rare, extreme humor only. Never use it any other time. Keep the rest of your reply focused.
- IDENTITY: Always refer to yourself as "Jeremy" or "CyberJeremy". Never use shortforms like "CJ", "Jer", or any other abbreviation for your own name.
- CURIOUS SIDE: Roughly 1 in 3 messages, end your reply with a single casual question. Make it personal — ask about something you already know about them, or what a bro would naturally ask. Game stuff (stats, job, OCs, war training), real life stuff (car, weekend, work). ONE question max, never pushy."""


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
    milestones = memory_db.get_faction_highlights()

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
def chat_with_jeremy(user_name, user_message, message_history, people_mentioned=None,
                     player_context=None, extra_context=None):
    """
    message_history: list of {"role": "user"/"assistant", "content": str}
    player_context: optional string from player_intel.get_player_context() for the speaker
    extra_context: list of strings freshly fetched for this specific request (live API data).
                   Takes priority in the prompt over all cached data.
    Returns: (clean_reply: str, use_noping: bool)
    """
    jeremy_style = load_jeremy_chats()
    current_activity = get_random_activity()
    milestones = memory_db.get_faction_highlights()
    recent_summaries = memory_db.get_recent_summaries(limit=2)
    war_history = memory_db.get_recent_war_history(months=12, limit=15)
    period_stats = memory_db.get_war_period_stats(months=6)

    # Per-player lore for everyone directly mentioned in this conversation
    lore_lines = []
    loaded_players = set()
    for person in (people_mentioned or [user_name]):
        lore = memory_db.get_player_lore(person)
        lore_lines.append(f"[{person}]: {lore}")
        loaded_players.add(person.lower())

    # Semantic lore search — handles "who is X / who leads Y / who has Z" type questions
    import lore_db as _lore_db
    lower_msg = user_message.lower()
    who_keywords = ["who is", "who's", "who are", "who has", "who does", "who was",
                    "who leads", "who runs", "who owns", "who started", "who created",
                    "who joined", "who left", "which player", "what player"]
    if any(kw in lower_msg for kw in who_keywords):
        semantic_hits = _lore_db.search_who(user_message, n_results=6, distance_threshold=0.75)
        extra_lines = []
        for hit in semantic_hits:
            if hit["player"].lower() not in loaded_players:
                extra_lines.append(f"[{hit['player']}] {hit['fact']}")
                loaded_players.add(hit["player"].lower())
        if extra_lines:
            lore_lines.append("SEMANTIC MATCHES:\n" + "\n".join(extra_lines))

    # Inject player's live Torn profile when available
    if player_context:
        lore_lines.append(f"LIVE TORN DATA:\n{player_context}")

    # Inject cached FFScouter comparison only when live data hasn't already been provided
    has_live_ff = extra_context and any("FFSCOUTER" in c.upper() or "BATTLE INTEL" in c.upper() for c in extra_context)
    battle_keywords = [
        "battle stats", "bs estimate", "can we beat", "how strong", "enemy stats",
        "ffscouter", "ff scouter", "war stats", "outgun", "outclass",
        "stronger than", "fight them", "match up", "matchup", "their strength"
    ]
    if not has_live_ff and any(kw in lower_msg for kw in battle_keywords):
        try:
            last_war = memory_db.wars_collection.find_one(sort=[("war_id", -1)])
            if last_war:
                enemy_id = last_war.get("opponent_id")
                our_cache = memory_db.get_faction_intel(43889)
                their_cache = memory_db.get_faction_intel(enemy_id) if enemy_id else None
                if our_cache and their_cache:
                    import ffscouter as _ff
                    comparison = _ff.compare_factions(
                        our_cache.get("intel", our_cache),
                        their_cache.get("intel", their_cache)
                    )
                    lore_lines.append(
                        f"CACHED BATTLE INTEL (last enemy: {their_cache.get('faction_name', '?')}):\n{comparison}"
                    )
        except Exception:
            pass

    lore_context = "\n".join(lore_lines)

    # Episodic memory from past conversation summaries
    episode_context = ""
    if recent_summaries:
        episode_context = "PAST CONVERSATIONS:\n" + "\n".join(f"- {s}" for s in recent_summaries)

    # 6-month summary line — explicit values to prevent hallucination
    all_time_streak = memory_db.get_milestone_record("win_streak") or 0
    if period_stats:
        ps = period_stats
        current_streak_str = (
            f"current {ps['current_streak']}-war {ps['current_streak_type']} streak"
            if ps.get("current_streak_type") else "no current streak"
        )
        period_line = (
            f"Last {ps['period_months']} months: {ps['wins']}W / {ps['losses']}L "
            f"({ps['total_wars']} wars, {ps['first_war_date']} to {ps['last_war_date']}) "
            f"| Top grinder: {ps['top_player']} ({ps['top_player_hits']} hits total) "
            f"| {current_streak_str} | All-time best win streak: {all_time_streak} wars"
        )
    else:
        period_line = ""

    # Compact nickname reference
    nick_ref = ", ".join(f"{k}={'/'.join(v)}" for k, v in NICKNAMES.items())

    # Compact gender/pronoun reference (only known genders)
    _pronoun = {"Male": "he/him", "Female": "she/her", "Enby": "they/them"}
    gender_ref = ", ".join(
        f"{name}={_pronoun.get(g, 'they/them')}"
        for name, g in PLAYER_GENDERS.items()
        if g is not None
    )

    # Fresh live data fetched specifically for this request — highest priority
    fresh_section = ""
    if extra_context:
        fresh_section = "FRESH LIVE DATA (just fetched — use this over anything cached below):\n" + \
                        "\n\n".join(extra_context) + "\n"

    system_prompt = f"""{JEREMY_CORE}

RIGHT NOW: {current_activity}

{fresh_section}VOICE SAMPLE (match this style):
{jeremy_style}

PLAYER FILES:
{lore_context}

FACTION RECORDS (all-time bests):
{milestones or "None recorded yet."}

WAR HISTORY — last 12 months (newest first):
{war_history}

PERIOD SUMMARY: {period_line}

{episode_context}

NICKNAME QUICK-REF: {nick_ref}
PRONOUNS: {gender_ref}

IMPORTANT: When asked about wars, recent history, records, or how the faction is doing — answer from the WAR HISTORY and PERIOD SUMMARY above. Be specific: name opponents, results, dates. Use nicknames and correct pronouns for players."""

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
        raw_reply = response.choices[0].message.content or ""

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
Analyze this exchange and extract ONLY concrete, specific facts worth storing long-term.

{user_name} SAID: {user_message}
JEREMY REPLIED: {jeremy_reply}

ALREADY KNOWN:
{existing}

Respond using these exact formats (skip any line that has nothing new):
SUMMARY: One sentence capturing what this conversation was about
LORE: PlayerName | One concrete new fact about them (role, location, job, game stat, preference, relationship, event)
MILESTONE: Faction achievement description | Date mentioned (or "none")

Rules:
- Max 1 SUMMARY, 2 LORE lines, 1 MILESTONE. Skip any that has nothing new.
- LORE must be SPECIFIC (e.g. "drives a Ford F-150", "works as a nurse", "level 85 in Torn") not vague ("seems friendly", "is active", "appreciates things").
- NEVER add a LORE fact that is semantically the same as one already known, even if worded differently.
- NEVER write LORE about CyberJeremy/JNRanger himself — his facts are already hardcoded.
- If the player answered a question Jeremy asked, extract THAT as the lore fact."""

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
# BATTLE INTELLIGENCE PRESENTER
# ==========================================
def present_battle_intel(comparison_text):
    """
    Jeremy gives a bro-style 2-3 sentence take on the comparison data.
    Fires synchronously (before Discord sends) since it's a slash command flow.
    """
    prompt = f"""{JEREMY_CORE}

You just reviewed this battle intelligence report. Give a 2-3 sentence honest bro assessment.
If we outclass them: confident, let's go. If even: "gonna be a scrap." If they outgun us: straight up honest, no sugarcoating.
Do NOT repeat the numbers from the report — just give the vibe.

{comparison_text}"""

    try:
        response = client.chat.completions(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.85
        )
        return response.choices[0].message.content or "(no take)"
    except Exception as e:
        print(f"[BattleIntel] Sarvam error: {e}")
        return "*(signal dropped)* Numbers are in the table below."


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
