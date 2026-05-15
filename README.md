# Torn RW Payout Discord Bot & CyberJeremy AI

![Status](https://img.shields.io/badge/status-active-success?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![API](https://img.shields.io/badge/torn-public_api-0ea5e9?style=for-the-badge)
![AI](https://img.shields.io/badge/AI-Sarvam_105B-FF9900?style=for-the-badge)
![DB](https://img.shields.io/badge/Database-MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)

> [!TIP]
> **Fast and simple payout reporting** combined with a **Living Faction AI**.
>  
> This project calculates financial payouts for faction members based on their Ranked War (RW) performance, while also hosting "CyberJeremy"—an AI digital ghost of a faction mechanic who remembers conversations, tracks faction lore, and roasts inactive players.

---

## ✨ Key Features

### 💰 Automated RW Payouts
* **Instant Calculation:** Calculates exact faction payouts, medical deductions, assist pay, and outside hit bonuses.
* **Excel & PDF Reports:** Automatically generates and posts detailed financial spreadsheets and clean PDF charts directly into Discord.
* **Key Vault:** Users securely save their Torn API keys via `/set_key` so they never have to type them in chat again.

### 🤖 CyberJeremy (Living AI Engine)
CyberJeremy isn't just a chatbot; he's a faction mate with an associative memory, powered by the Sarvam 105B model.
* **Dynamic War Summaries:** Tag `@CyberJeremy scout` to get an in-character summary of the latest war. He praises the MVP, shouts out "Improvers" who beat their average, and mocks "MIA" players who fell asleep.
* **Associative Stealth Memory:** Jeremy listens to faction chat. If someone mentions a new job, a favorite beer, or a new car, Jeremy extracts that lore in the background and saves it to MongoDB. The next time he talks to that player, he brings it up natively.
* **Faction Milestones:** Tracks and remembers major faction achievements automatically.
* **Custom Lore:** Programmed with mechanic lore (welding SXS subframes, Lexus GX470s) and operates out of a virtual garage in Brampton. 

---

## 🚀 Commands & Usage

| Command / Trigger | Description |
| :--- | :--- |
| `/set_key [api_key]` | Securely locks your public Torn API key into the MongoDB vault (Ephemeral). |
| `/payout [...]` | Generates the Excel and PDF war payout reports based on pool size and deductions. |
| `@CyberJeremy scout` | Jeremy pulls the latest war data, generates charts, and writes an AI-driven summary. |
| `@CyberJeremy [chat]`| Talk naturally with Jeremy. He uses associative memory to recall facts about anyone mentioned in the sentence. |

> [!NOTE]
> To generate older reports, pass the **specific War ID** into the payout command.

---

## 🧠 The "Living Memory" Architecture
CyberJeremy operates on a multi-layered memory system to prevent AI hallucination and echo-looping:
1. **Short-Term Memory:** Reads the last 7 messages in the Discord channel to maintain conversation context.
2. **Pre-Filtering:** Python scripts pre-process 100+ member faction lists down to Top 5s and MIAs *before* sending data to the AI, saving tokens and speeding up response times.
3. **Regex Extraction:** The bot scrubs Jeremy's internal thoughts (e.g., `[SAVE_LORE: Spider | Bought a Mustang]`) before the message hits Discord, saving the fact silently to the DB.

---

## 🛠️ Requirements & Setup

To host this bot yourself, you will need:
1. A **Discord Bot Token** (with Message Content Intents enabled).
2. A **MongoDB Atlas URI** (For the Vault and Lore storage).
3. A **Sarvam AI API Key** (For the 105B parameter brain).
4. A **Public Torn API Key** (For fetching war data).

### Environment Variables
Ensure the following variables are set in your host environment (e.g., Render, Heroku) or your local PowerShell session:
```env
DISCORD_TOKEN=your_discord_bot_token
MONGO_URI=mongodb+srv://<username>:<password>@cluster...
SARVAM_API_KEY=your_sarvam_api_key