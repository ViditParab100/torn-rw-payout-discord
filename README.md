# Torn RW Payout Discord Bot & CyberJeremy AI

![Status](https://img.shields.io/badge/status-active-success?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![API](https://img.shields.io/badge/torn-v2_api-0ea5e9?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-Sarvam_105B-FF9900?style=for-the-badge)
![DB](https://img.shields.io/badge/Database-MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)

> [!TIP]
> **Precision Payout Reporting** combined with a **Living Faction AI**.
>
> This project calculates financial payouts for faction members based on their Ranked War (RW) performance with surgical accuracy, while also hosting "CyberJeremy" — an AI digital ghost of a late faction mechanic who remembers conversations, tracks faction lore, looks up live Torn player data, and roasts inactive players.

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
- **Tiered Memory:** Jeremy remembers through four layers — (1) **Working memory**: the last 7 channel messages as proper conversation turns; (2) **Episodic memory**: compressed summaries of past conversations stored in MongoDB; (3) **Semantic memory**: per-player fact files (max 10 facts, associatively loaded when someone is mentioned); (4) **Faction memory**: milestones, chain records, war history, and upgrade timestamps.
- **Semantic Lore Search (ChromaDB):** A vector index (all-MiniLM-L6-v2) lets Jeremy answer directional questions like "who leads KOWR" or "who was our mechanic" — even when phrased differently. The index is rebuilt from MongoDB at startup, with hard-coded static facts for key roles (ChineseGandalf as leader, Xtatik as co-leader, etc).
- **Live Torn Profile Enrichment:** When a player with a stored API key messages Jeremy, their Torn profile is fetched in the background — level, title, donator status, faction position, company info (name, type, stars, age, employee count, role). Cached for 1 hour in MongoDB. When a player asks directly about their own data ("what level am I?", "how many employees does my company have?"), Jeremy fetches fresh data synchronously before replying. Title promotions are auto-detected and stored as milestones.
- **Gender & Pronouns:** Every player in the nickname list has a gender entry — seeded from known context, completed via `/update_intel` which batch-fetches all current faction members' profiles from Torn. Jeremy uses correct he/him, she/her, or they/them pronouns automatically.
- **Battle Intelligence:** Jeremy can reference FFScouter battle stats in natural chat when relevant keywords appear (e.g., "can we beat them", "how strong is their faction"). Cached data from the last `/battle_intel` run is injected directly into his context window — no extra API call needed during chat.
- **Versioned Memory:** Old lore facts are never silently lost. When the active fact buffer (10 facts) fills up, displaced facts are archived to `archived_lore_bits` in MongoDB — keeping a full history of what Jeremy once knew about each player.
- **Background Consolidation:** After Jeremy replies, a separate LLM call silently extracts new facts and conversation summaries — memory writes never corrupt his reply.
- **Milestone Tracking:** Jeremy records faction achievements from conversations and weaves them into war summaries. Chain milestones (first 100/250/500/1000/2000/2500-hit chains), faction upgrade timestamps, and war records are all tracked automatically.
- **Visual Analytics:** Generates a **Top 10 Hitter bar chart** and a **Respect Distribution pie chart** (Top 5 vs Rest) with every scout report.
- **Custom Persona:** Built from a real chat log baseline (`Ranger Chats.txt`) — North Brampton/Caledon, mechanic/welder by real-life trade, Lexus GX470 enthusiast, beer drinker. Faction: *KnockOut WeightRoom* (Leader: ChineseGandalf, Co-Leader: Xtatik). Jeremy always refers to himself as "Jeremy" or "CyberJeremy" — never shortforms.
- **Nickname Map:** 30+ player aliases are hard-coded so Jeremy refers to players naturally (e.g., "Star_vader" → Vader/Star/Champ).
- **Curious Side:** Roughly 1 in 3 replies, Jeremy ends with a single personal question — game stats, IRL stuff, weekend plans. Never pushy.

---

## 🚀 Commands & Usage

### Slash Commands

| Command | Parameters | Description |
| :--- | :--- | :--- |
| `/set_key` | `api_key` | Securely stores your Torn public API key in the MongoDB vault (ephemeral — only you see the response). Required for `/payout`, `/battle_intel`, `/update_intel`, and player profile enrichment. |
| `/payout` | `total_payout`, `medical_cost`, `api_key` *(optional)*, `pay_per_assist`, `outside_hit_val`, `outside_hit_limit` | Runs the full payout engine and posts Excel + PDF files. Uses your vault key if `api_key` is omitted. |
| `/battle_intel` | `enemy_faction_id` *(optional)* | Pulls FFScouter battle stats for both factions. Defaults to the last war's opponent. Posts Jeremy's bro-style verdict + faction comparison table in chat, then generates and attaches a full per-player PDF report (see `battle_report.py`). |
| `/update_intel` | *(none)* | Batch-fetches all current faction members' Torn profiles (gender, level, title, Torn ID). Updates the in-memory gender dict and MongoDB `faction_members` collection. Run once after new members join. |

### Message Mentions

| Trigger | Description |
| :--- | :--- |
| `@CyberJeremy scout` | Fetches the latest war, generates two Matplotlib charts, and posts an AI-written narrative summary. Also triggered by "war report" or "war summary". |
| `@CyberJeremy [anything]` | Natural chat. Jeremy loads lore for any mentioned players, does a semantic "who is X" lookup when needed, checks your cached Torn profile for context, and replies in 1–3 casual sentences. Memory consolidation fires in the background after the reply. |
| `@CyberJeremy can we beat them` / `battle stats` / `ff data` | Triggers a live FFScouter fetch for both factions in parallel — Jeremy replies with the faction comparison table and a brief tactical take. |
| `@CyberJeremy stat difference` / `who to hit` / `matchup` | Triggers a live FFScouter fetch **plus** the per-player matchup report — Jeremy breaks down sweet-spot targets, who can run free, and which enemy players are threats. |
| `@CyberJeremy what level is [player]` / `how strong is [player]` | Looks up any faction member's live Torn profile by name — level, title, status, age — and feeds it directly into Jeremy's reply. |

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

MongoDB database **FactionMemory** with seven collections:

| Collection | Purpose |
| :--- | :--- |
| `user_keys` | Discord user ID → Torn API key vault |
| `wars` | Cached war data (war_id, members, opponent, scores) |
| `lore` | Per-player fact arrays (max 10, lowercase-normalised keys) |
| `milestones` | Faction achievements with timestamps and structured types |
| `conversations` | Compressed episode summaries for Jeremy's episodic recall |
| `faction_stats` | FFScouter battle stat cache keyed by faction ID |
| `player_profiles` | Torn profile cache keyed by Discord ID (1-hour TTL); includes gender, torn_id |
| `faction_members` | All faction member records — torn_id, torn_name, gender, level, title. Populated by `/update_intel`. |

- `get_last_5_wars_stats()` computes per-player historical averages used by the AI for Improver/MIA detection.
- `get_recent_summaries()` returns the last N conversation summaries so Jeremy has continuity across sessions.
- `get_faction_highlights()` returns a curated set of records (chain milestones, war records, upgrade timestamps) for Jeremy's system prompt.

### 3. The AI Engine — `ai_engine.py`

- Loads the last 50 lines of `Ranger Chats.txt` as Jeremy's personality baseline.
- `generate_ai_summary()`: Pulls last 5 wars + current war + faction milestones → sends a structured prompt to **Sarvam 105B** → returns a 3-paragraph in-character narrative.
- `chat_with_jeremy()`: Accepts proper `[{role, content}]` message history + player lore + semantic lore hits + live Torn profile context + cached battle intel → returns `(reply, use_noping)` with no embedded tags. FFScouter data is automatically injected when battle-related keywords are detected.
- `consolidate_and_save()`: Fires after the Discord reply is sent (background executor). One separate Sarvam call extracts a conversation SUMMARY + any new LORE/MILESTONE facts and writes them to MongoDB — memory writes are fully decoupled from reply generation.
- `present_battle_intel()`: Jeremy's bro-style 2–3 sentence take on a FFScouter comparison report.
- Automatic retry on rate limits; graceful fallback message if the API is unavailable.

### 4. Semantic Lore Layer — `lore_db.py`

ChromaDB in-memory vector index for answering "who is X / who leads Y / who has Z" questions:

- **Embedding model:** `all-MiniLM-L6-v2` ONNX (79MB, cached at `~/.cache/chroma/onnx_models/`). Cosine similarity space.
- **Static facts:** Hard-coded entries for key roles (ChineseGandalf=leader, Xtatik=co-leader, JNRanger=mechanic/welder by real-life trade, Stumptronic=sister faction leader, Star_vader=creator, Spidernnam=departed to reviver faction) with multiple phrasings per role to defeat embedding variance.
- **Rebuilt at startup** from MongoDB `lore` collection. EphemeralClient means no disk state — MongoDB is always the source of truth.
- `search_who(query, n_results, distance_threshold)` — triggered in `chat_with_jeremy()` whenever the message contains "who is / who leads / who runs / who left / which player" etc.
- New lore facts added via `memory_db.update_player_lore()` are automatically mirrored into ChromaDB via lazy import.

### 5. Player Intel — `player_intel.py`

Torn API profile enrichment using each player's own stored key:

- **v1 profile:** level, title, rank, age (days), donator status, gender, faction position, job/company name, torn_id
- **v2 /company:** detailed company profile — type, stars (rating), days old, employee count, director name
- **Caching:** profiles stored in MongoDB `player_profiles_col` with 1-hour TTL. `get_player_context()` returns empty string if stale.
- **On-demand fetch:** when a player asks about their own profile data in chat, `enrich_player()` runs synchronously before Jeremy replies — ensuring fresh data.
- **Bulk gender fetch:** `fetch_faction_genders(api_key)` retrieves all current faction members via `/v2/faction?selections=members`, then fetches each member's v1 profile to extract gender, level, title, and torn_id. Stores in `faction_members_col`. Rate: ~0.7s/member.
- **Title promotion detection:** compares new title against stored title using a 40-entry progression list. Promotions fire a lore update and a faction milestone.
- **Auto-lore:** title + company facts are automatically written to the lore layer after each profile fetch.
- Profile enrichment runs in a background thread after every Route B chat message (no blocking).

### 6. Battle Intelligence — `ffscouter.py` + `battle_report.py`

FFScouter integration for war preparation:

- `get_stats(player_ids)`: Batch query `ffscouter.com/api/v1/get-stats` — up to 205 IDs per request, 3s sleep between chunks to stay under 20 req/min. Returns `bs_estimate`, `bs_estimate_human`, `fair_fight`.
- `scout_faction(api_key, faction_id)`: Full pipeline — Torn member list → FFScouter stats → enriched summary dict. Cached in MongoDB `faction_stats_col`.
- `compare_factions(our_data, their_data)`: Faction-level summary table — verdict (WE OUTCLASS / EVEN MATCHUP / THEY OUTGUN US), average BS, total BS, top fighters, and threats (their players > 1.5x our avg).
- `player_matchup_report(our_data, their_data)`: Compact text breakdown for chat — sweet spot pairs, players who can run free (beat 50%+ of enemy roster at 1.2x), and incoming threats.
- **Route B live fetch:** When matchup or FFScouter keywords appear in chat ("stat difference", "who to hit", "matchup", "battle stats", etc.), Jeremy fetches both factions from FFScouter in parallel using `asyncio.gather()` and injects the results as `FRESH LIVE DATA` at the top of his context window — overriding any stale cache.
- **Natural chat fallback:** when battle keywords appear but no live fetch runs, `chat_with_jeremy()` injects the last cached comparison from MongoDB automatically.

#### `battle_report.py` — Per-Player PDF Report

Full A4 landscape PDF generated automatically by `/battle_intel`, mapping every player in both factions against every opponent. Handles 200–250 players with automatic page breaks and repeated column headers.

**Three sections:**

| Section | Content |
| :--- | :--- |
| Summary (page 1) | Side-by-side faction boxes (members, avg BS, total BS, top gun), verdict + ratio, mechanics legend, top 10 sweet-spot matchup pairs |
| Our Attack Profiles | One row per our member (sorted by BS desc) — Sweet Spot Targets (green), Domination Targets (blue), Threats to Them (red) |
| Enemy Profiles | One row per enemy member — Our Members in Their Sweet Spot, Our Members They Dominate, Our Members Who Beat Them |

**Battle mechanics encoded in every row:**
- **Sweet spot (0.8–1.1x):** target's BS is 80–110% of yours — max respect earned
- **Domination (≥1.2x):** your BS is 1.2x theirs — you win cleanly
- **Threat:** their BS is 1.2x yours — avoid unless necessary

The PDF is posted as a Discord file attachment immediately after the text verdict. The local file is deleted after upload.

### 7. Torn API Wrapper — `torn_api.py`

Torn v2 endpoints used:

| Function | Endpoint Purpose |
| :--- | :--- |
| `get_key_info()` | Validates API key; returns `user_id` and `faction_id` |
| `get_latest_war_id()` | Returns the most recently *finished* ranked war |
| `get_war_report_data()` | Full ranked war report with per-member attack counts and faction scores |
| `get_chains_for_war()` | All chains active in a given time window (limit 100) |
| `get_chain_report()` | Detailed chain report with attackers, assists, and milestone bonuses |
| `get_faction_levels()` | Bulk fetch of all faction member levels (used for newbie bonus logic) |

### 8. Visualizations — `chart_generator.py`

- **Bar chart**: Top 10 hitters by war hit count — lime green bars, dark Discord-friendly theme, value labels on bars.
- **Pie chart**: Respect share — Top 5 contributors (lime green, exploded slice) vs rest of faction (grey).
- Output files: `War_{opponent}_{war_id}_bar.png` / `War_{opponent}_{war_id}_pie.png`

### 9. Report Generators — `excel_generator.py` & `pdf_convertor.py`

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

Edit the `war_ids` list inside `seed_db.py` to specify which past wars to import.

### Seeding Chain & Upgrade Milestones

To backfill all historical chain milestones (first 100/250/500/1000/2000/2500-hit chains) and faction upgrade timestamps from the Torn API:

```bash
TORN_API_KEY=yourkey python seed_milestones.py
```

This is a one-time operation — the detector is idempotent and skips already-stored milestones.

---

## 🧪 Test Suite — `test_jeremy.py`

Six-layer test suite for the CyberJeremy AI:

```bash
python test_jeremy.py          # Layers 1, 2, 4, 5, 6 (fast, ~30s)
python test_jeremy.py --chat   # All layers including live Sarvam calls (~60s)
```

| Layer | Tests | Description |
| :--- | :--- | :--- |
| 1 — Semantic search | 16 | Direct `lore_db.search_who()` queries. Checks expected player appears in top N results. |
| 2 — Meaning equivalence | 4 | Two different phrasings of the same question must surface the same player. |
| 3 — Generative chat | 10 | Live Sarvam calls with keyword checks on Jeremy's reply. Includes identity test and a stat-difference matchup query. |
| 4 — Player intel | 22 | Title tier logic, context formatting, lore archive verification, and gender seed checks. |
| 5 — FFScouter matchup | 15 | Pure unit tests for `player_matchup_report()` — sweet-spot detection, win-zone classification, threat flagging, boundary precision (0.80/1.10/0.79/1.21), string-keyed cache format, and null-input guards. |
| 6 — Battle report | 26 | `_compute_matchups()` logic (sorting, per-player sweet/win/threat from both perspectives), zero-BS filtering, MAX_SHOW cap, string-keyed member dicts, PDF file output (3v3 and 20v20 page-break stress test). |

---

## 🏗️ Project Structure

```
torn-rw-payout-discord/
├── bot.py               # Discord entry point, slash commands, message handlers
├── main_logic.py        # Payout calculation engine (Research → Filter → Recalculate)  ← DO NOT MODIFY
├── torn_api.py          # Torn v2 API wrapper                                           ← DO NOT MODIFY
├── memory_db.py         # MongoDB interface (keys, wars, lore, milestones, profiles)
├── ai_engine.py         # Sarvam 105B integration, prompts, personality
├── lore_db.py           # ChromaDB semantic lore index (rebuilt from MongoDB at startup)
├── player_intel.py      # Torn profile + company enrichment (1h cache, auto-lore)
├── ffscouter.py         # FFScouter battle stats integration + matchup text report
├── battle_report.py     # A4 landscape per-player battle intelligence PDF generator
├── milestone_detector.py # Auto-detects war/chain/upgrade milestones from Torn API
├── chart_generator.py   # Matplotlib bar & pie chart generator                         ← DO NOT MODIFY
├── excel_generator.py   # XLSXWriter payout spreadsheet                                ← DO NOT MODIFY
├── pdf_convertor.py     # fpdf2 PDF report (landscape)                                 ← DO NOT MODIFY
├── seed_db.py           # Historical war data backfill utility                          ← DO NOT MODIFY
├── seed_milestones.py   # One-time chain + upgrade milestone seeder
├── test_jeremy.py       # 6-layer CyberJeremy test suite (83 tests)
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
| `chromadb` | In-memory vector index for semantic lore search |
