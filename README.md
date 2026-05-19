# Torn RW Payout Discord Bot & CyberJeremy AI

![Status](https://img.shields.io/badge/status-active-success?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![API](https://img.shields.io/badge/torn-v2_api-0ea5e9?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-Sarvam_105B-FF9900?style=for-the-badge)
![DB](https://img.shields.io/badge/Database-MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)

> [!TIP]
> **Precision Payout Reporting** combined with a **Living Faction AI**.
>  
> This project calculates financial payouts for faction members based on their Ranked War (RW) performance with surgical accuracy, while also hosting "CyberJeremy"—an AI digital ghost of a faction mechanic who remembers conversations, tracks faction lore, and roasts inactive players.

---

## ✨ Key Features

### 💰 Automated RW Payouts (The Accountant)
*   **Precision Calculation:** Automatically calculates faction payouts, medical deductions, assist pay, and outside hit bonuses.
*   **Overflow Chain Logic:** Sophisticated filtering for chains that continue after a war ends. It matches post-war attacks to specific bonuses to ensure only valid war-time respect is rewarded.
*   **Excel & PDF Reports:** Generates professional-grade financial spreadsheets and visual charts (Matplotlib) posted directly to Discord.
*   **Smart Caching:** Stores war data in MongoDB for instant report recalculations without re-fetching from the Torn API.

### 🤖 CyberJeremy (Living AI Engine)
CyberJeremy is powered by the **Sarvam 105B** model, acting as a "digital ghost" with a persistent memory.
*   **Dynamic War Summaries:** Tag `@CyberJeremy scout` for an in-character summary of the latest war. He identifies MVPs, "Improvers" (beating their historical average), and "MIA" players.
*   **Associative Stealth Memory:** Jeremy extracts lore from chat (e.g., jobs, hobbies, cars) and saves it to MongoDB. He natively recalls these facts in future conversations.
*   **Visual Analytics:** Generates bar charts and pie charts of faction performance to accompany war summaries.
*   **Custom Persona:** Programmed with faction-specific lore (welding, GX470s, Brampton garage life).

---

## 🚀 Commands & Usage

| Command / Trigger | Description |
| :--- | :--- |
| `/set_key [api_key]` | Securely locks your public Torn API key into the MongoDB vault (Ephemeral). |
| `/payout [...]` | Calculates payouts. Uses vault key if `api_key` is omitted. Supports custom bonus limits. |
| `@CyberJeremy scout` | Jeremy fetches latest war data, generates charts, and writes an AI-driven summary. |
| `@CyberJeremy [chat]`| Natural chat with Jeremy. He uses associative memory to recall facts about mentioned players. |

---

## 🧠 Technical Architecture

### 1. The Payout Engine (`main_logic.py`)
Uses a **Research -> Filter -> Recalculate** workflow:
*   Fetches the **Ranked War Report** and all **Chain Reports** during the war period.
*   Cross-references individual **Faction Attacks** to identify and subtract "Overflow" hits performed after the war conclusion.
*   Matches bonuses (milestones) to specific post-war attacks to ensure financial integrity.

### 2. The Living Memory (`memory_db.py`)
*   **Key Vault:** Encrypted-style storage for user API keys.
*   **Lore Storage:** Associative player facts stored as "lore bits" keyed by username.
*   **War History:** Historical stats for calculating "Improver" and "MIA" status.

### 3. Visualizations (`chart_generator.py`)
*   Uses **Matplotlib** with a dark theme tailored for Discord.
*   Generates Top 10 Hitter bar charts and Faction Respect Share pie charts.

---

## 🛠️ Setup & Deployment

### Requirements
1.  **Discord Bot Token** (Message Content Intent enabled).
2.  **MongoDB Atlas URI** (Cluster 0 or similar).
3.  **Sarvam AI API Key** (For the 105B brain).
4.  **Python 3.10+**

### Environment Variables
```env
DISCORD_TOKEN=your_discord_bot_token
MONGO_URI=mongodb+srv://...
SARVAM_API_KEY=your_sarvam_api_key
```

### Installation
```bash
pip install -r requirements.txt
python bot.py
```

---

## 🏗️ Project Structure
*   `bot.py`: Discord entry point and slash command handler.
*   `ai_engine.py`: Sarvam AI integration and prompt engineering.
*   `main_logic.py`: The core financial and chain-processing engine.
*   `torn_api.py`: Robust Torn v2 API wrapper.
*   `memory_db.py`: MongoDB interface for lore, keys, and history.
*   `excel_generator.py` / `pdf_convertor.py`: Reporting modules.
*   `chart_generator.py`: Visual analytics module.
