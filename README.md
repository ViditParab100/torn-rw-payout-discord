# Torn RW Payout Discord Bot & CyberJeremy AI

![Status](https://img.shields.io/badge/status-active-success?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![API](https://img.shields.io/badge/torn-v2_api-0ea5e9?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-Sarvam_105B-FF9900?style=for-the-badge)
![DB](https://img.shields.io/badge/Database-MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)

> [!TIP]
> **Precision Payout Reporting** combined with a **Living Faction AI**.
>
> This project calculates financial payouts for faction members based on their Ranked War (RW) performance with surgical accuracy, while also hosting "CyberJeremy" — an AI digital ghost of a late faction mechanic who remembers conversations, tracks faction lore, and roasts inactive players.

---

## ✨ Key Features

### 💰 Automated RW Payouts (The Accountant)

- **Precision Calculation:** Calculates individual payouts based on respect gained, medical deductions, war assists, outside hit bonuses, and newbie bonuses for members at or below level 20.
- **Overflow Chain Logic:** Chains that continue after a war ends are handled with custom pagination — post-war attacks are fetched individually (100 at a time), matched to specific chain bonuses, and subtracted so only valid war-time respect is rewarded.
- **Chain Deduction Smoothing:** Instead of deducting the full chain bonus value, only the difference above that player's personal average is deducted — preventing unfair penalties.
- **Excel & PDF Reports:** Generates professional financial spreadsheets (XLSXWriter) and landscape PDF reports (fpdf2) with summary sections, member payout tables, and chain bonus correction tables — posted directly to Discord and cleaned up after upload.
- **Smart Caching:** War data is stored in MongoDB after the first fetch. Recalculating payouts with different financial parameters uses the cache, never hitting the Torn API twice for the same war.

### 🤖 CyberJeremy (Living AI Engine)

CyberJeremy runs on **Sarvam 105B** with a Karpathy-style tiered memory system that keeps him feeling like a real person across sessions.

- **Dynamic War Summaries:** Tag `@CyberJeremy scout` for an in-character 3-paragraph narrative. He identifies **Top 5 MVPs**, **Improvers** (members 20%+ above their historical average with 10+ hits), and **MIA** players (0 hits when their historical average is ≥ 5), plus references faction milestones.
- **Tiered Memory:** Jeremy remembers through three layers — (1) **Working memory**: the last 7 channel messages as proper conversation turns; (2) **Episodic memory**: compressed summaries of past conversations stored in MongoDB; (3) **Semantic memory**: per-player fact files (max 10 facts, associatively loaded when someone is mentioned).
- **Background Consolidation:** After Jeremy replies, a separate LLM call silently extracts new facts and conversation summaries — memory writes never corrupt his reply.
- **Milestone Tracking:** Jeremy records faction achievements from conversations and weaves them into war summaries.
- **Visual Analytics:** Generates a **Top 10 Hitter bar chart** and a **Respect Distribution pie chart** (Top 5 vs Rest) with every scout report.
- **Custom Persona:** Built from a real chat log baseline (`Ranger Chats.txt`) — North Brampton/Caledon, mechanic/welder, Lexus GX470 enthusiast, beer drinker. Faction: *KnockOut WeightRoom* (Leader: ChineseGandalf, Co-Leader: Xtatik).
- **Nickname Map:** 30+ player aliases are hard-coded so Jeremy refers to players naturally (e.g., "Star_vader" → Vader/Star/Champ).

---

## 🚀 Commands & Usage

### Slash Commands

| Command | Parameters | Description |
| :--- | :--- | :--- |
| `/set_key` | `api_key` | Securely stores your Torn public API key in the MongoDB vault (ephemeral — only you see the response). |
| `/payout` | `total_payout`, `medical_cost`, `api_key` *(optional)*, `pay_per_assist`, `outside_hit_val`, `outside_hit_limit` | Runs the full payout engine and posts Excel + PDF files. Uses your vault key if `api_key` is omitted. |

### Message Mentions

| Trigger | Description |
| :--- | :--- |
| `@CyberJeremy scout` | Fetches the latest war, generates two Matplotlib charts, and posts an AI-written narrative summary. |
| `@CyberJeremy [anything]` | Natural chat. Jeremy loads lore for any mentioned players, replies in 1–3 casual sentences, and may save new facts or milestones back to MongoDB. |

---

## 🧮 Payout Formula

```
Payout Pool = (Total_Payout × 0.9) - Medical_Cost - Newbie_Bonus_Pool - Assist_Pay_Total

Price_Per_Rep  = Payout_Pool / Sum(Net_Rep for all members)

Individual Pay = (Rep_Gained - Chain_Deductions) × Price_Per_Rep
              + Newbie_Bonus            # level ≤ 20: capped_outside_hits × outside_hit_val
              + Assists × pay_per_assist
```

- **Outside hit cap** (`outside_hit_limit`): Caps the number of outside-war hits credited per member.
- **Chain deduction**: `max(0, bonus_value - player_average_rep)` — only the excess above average is deducted.
- **Newbie bonus pool** is subtracted from the global pool before `Price_Per_Rep` is calculated, ensuring senior members aren't penalised.

---

## 🧠 Technical Architecture

### 1. The Payout Engine — `main_logic.py`

**Research → Filter → Recalculate** workflow:

1. Fetches the **Ranked War Report** (member scores, faction totals) and every **Chain Report** active during the war window.
2. Identifies **overflow chains** — chains started during the war but continuing past the end timestamp.
3. For overflowing chains, paginates individual faction attacks (100 per request) to find every post-war hit and maps each one to any chain bonus it generated.
4. Subtracts those invalid bonuses from the relevant members before final calculation.
5. Applies the payout formula above and hands results to the report generators.

### 2. The Living Memory — `memory_db.py`

MongoDB database **FactionMemory** with five collections:

| Collection | Purpose |
| :--- | :--- |
| `user_keys` | Discord user ID → Torn API key vault |
| `wars` | Cached war data (war_id, members, opponent, scores) |
| `lore` | Per-player fact arrays (max 10, lowercase-normalised keys) |
| `milestones` | Faction achievements with timestamps |
| `conversations` | Compressed episode summaries for Jeremy's episodic recall |

- `get_last_5_wars_stats()` computes per-player historical averages used by the AI for Improver/MIA detection.
- `get_recent_summaries()` returns the last N conversation summaries so Jeremy has continuity across sessions.

### 3. The AI Engine — `ai_engine.py`

- Loads the last 50 lines of `Ranger Chats.txt` as Jeremy's personality baseline.
- `generate_ai_summary()`: Pulls last 5 wars + current war + faction milestones → sends a structured prompt to **Sarvam 105B** → returns a 3-paragraph in-character narrative.
- `chat_with_jeremy()`: Accepts a proper `[{role, content}]` message history array + relevant player lore + episodic summaries → returns `(reply, use_noping)` with no embedded tags.
- `consolidate_and_save()`: Fires after the Discord reply is sent (background executor). One separate Sarvam call extracts a conversation SUMMARY + any new LORE/MILESTONE facts and writes them to MongoDB — memory writes are fully decoupled from reply generation.
- Automatic retry on rate limits; graceful fallback message if the API is unavailable.

### 4. Torn API Wrapper — `torn_api.py`

Torn v2 endpoints used:

| Function | Endpoint Purpose |
| :--- | :--- |
| `get_key_info()` | Validates API key; returns `user_id` and `faction_id` |
| `get_latest_war_id()` | Returns the most recently *finished* ranked war |
| `get_war_report_data()` | Full ranked war report with per-member attack counts and faction scores |
| `get_chains_for_war()` | All chains active in a given time window (limit 100) |
| `get_chain_report()` | Detailed chain report with attackers, assists, and milestone bonuses |
| `get_faction_levels()` | Bulk fetch of all faction member levels (used for newbie bonus logic) |

### 5. Visualizations — `chart_generator.py`

- **Bar chart**: Top 10 hitters by war hit count — lime green bars, dark Discord-friendly theme, value labels on bars.
- **Pie chart**: Respect share — Top 5 contributors (lime green, exploded slice) vs rest of faction (grey).
- Output files: `War_{opponent}_{war_id}_bar.png` / `War_{opponent}_{war_id}_pie.png`

### 6. Report Generators — `excel_generator.py` & `pdf_convertor.py`

Both produce two sections:

1. **Summary**: War title, initial payout, medical cost, newbie pool, assist rates, respect pool, price-per-rep.
2. **Member Table**: Name, War Hits, Outside Hits, Assists, Rep Gained, Chain Deduction, Net Rep, Newbie Bonus, Assist Pay, Final Payout — sorted by payout descending.
3. **Chain Bonus Correction Table**: Attacker, Defender ID, bonus value, player average, net deduction, clickable chain report link.

Excel uses lime green (#92D050) headers with currency formatting. PDF is A4 landscape with page numbers.

---

## 🛠️ Setup & Deployment

### Requirements

1. **Discord Bot Token** — Message Content Intent and application commands enabled.
2. **MongoDB Atlas URI** — Any free-tier cluster works.
3. **Sarvam AI API Key** — For the 105B conversational brain.
4. **Python 3.10+**

### Environment Variables

```env
DISCORD_TOKEN=your_discord_bot_token
MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
SARVAM_API_KEY=your_sarvam_api_key
```

### Installation & Run

```bash
pip install -r requirements.txt
python bot.py
```

### Heroku Deployment

The `Procfile` declares a **worker** dyno:

```
worker: python bot.py
```

A lightweight Flask server runs on port 10000 inside `bot.py` to keep the dyno alive and prevent Heroku from sleeping the process.

### Seeding Historical War Data

To backfill MongoDB with historical war stats (for accurate Improver/MIA detection):

```bash
# Set TORN_API_KEY and MONGO_URI in your environment, then:
python seed_db.py
```

Edit the `war_ids` list inside `seed_db.py` to specify which past wars to import. The script pauses 3 seconds between requests to respect API rate limits.

---

## 🏗️ Project Structure

```
torn-rw-payout-discord/
├── bot.py               # Discord entry point, slash commands, message handlers
├── main_logic.py        # Payout calculation engine (Research → Filter → Recalculate)
├── torn_api.py          # Torn v2 API wrapper
├── memory_db.py         # MongoDB interface (keys, wars, lore, milestones)
├── ai_engine.py         # Sarvam 105B integration, prompts, personality
├── chart_generator.py   # Matplotlib bar & pie chart generator
├── excel_generator.py   # XLSXWriter payout spreadsheet
├── pdf_convertor.py     # fpdf2 PDF report (landscape)
├── seed_db.py           # Historical war data backfill utility
├── Ranger Chats.txt     # Jeremy's personality baseline (last 50 lines loaded)
├── Sad_Chats.txt        # Archive of memorial/sad messages
├── requirements.txt     # Python dependencies
└── Procfile             # Heroku worker dyno config
```

---

## 📦 Dependencies

| Package | Purpose |
| :--- | :--- |
| `discord.py` | Discord bot framework |
| `requests` | Torn API HTTP calls |
| `pandas` | Data manipulation |
| `xlsxwriter` | Excel report generation |
| `fpdf2` | PDF report generation |
| `matplotlib` | Chart visualizations |
| `pymongo` + `certifi` | MongoDB Atlas driver with SSL |
| `sarvamai` | Sarvam 105B AI client |
| `flask` | Keep-alive server for Heroku |
| `openpyxl` | Excel utilities |
