import discord
from discord import app_commands
from discord.ext import commands
import main_logic

from flask import Flask
from threading import Thread
import os
import asyncio
import re  # <--- NEW: Required for extracting Jeremy's memories

import ai_engine
import chart_generator
import memory_db

# 1. Flask Keep-Alive Setup
app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000)) 
    app.run(host='0.0.0.0', port=port)

# 2. Bot Logic
intents = discord.Intents.default()
intents.message_content = True

class RWBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Slash commands synced for {self.user}")

bot = RWBot()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message):
        clean_message = message.content.replace(f'<@{bot.user.id}>', '').strip().lower()
        if not clean_message:
            clean_message = "Hey buddy."

        scout_keywords = ["scout", "war report", "stats", "war summary", "how are we doing", "status"]
        
        # --- ROUTE A: THE SCOUT / WAR REPORT ---
        if any(keyword in clean_message for keyword in scout_keywords):
            async with message.channel.typing():
                api_key = memory_db.get_user_key(message.author.id)
                if not api_key:
                    await message.channel.send(f"Hey {message.author.display_name}, I need your key first. Run `/set_key`.")
                    return

                try:
                    # 1. Fetch War Data
                    war_data = main_logic.process_war_request(api_key, 0, 0, 0, 0, 0, force_update=False)
                    
                    # 2. Generate AI Summary
                    ai_summary = ai_engine.generate_ai_summary(war_data)
                    
                    # 3. Generate Charts
                    clean_opp_name = war_data['opponent_name'].replace(" ", "")
                    base_name = f"War_{clean_opp_name}_{war_data['war_id']}"
                    chart_paths = chart_generator.generate_war_charts(war_data, base_name)
                    
                    # 4. Cleanup/Fallback Logic
                    final_text = ai_summary if ai_summary else "*(Jeremy wipes grease off his hands)* Stats are in, looks like a good scrap."
                    discord_files = [discord.File(path) for path in chart_paths]
                    
                    # 5. Send Summary + Charts in ONE message
                    await message.channel.send(content=final_text, files=discord_files)

                    # Cleanup image files
                    for path in chart_paths:
                        if os.path.exists(path): os.remove(path)

                except Exception as e:
                    print(f"CRITICAL ERROR IN SCOUT: {e}")
                    await message.channel.send(f"❌ **CyberJeremy Error:** Something's wrong in the shop. Check my logs.")

        # --- ROUTE B: NORMAL CHAT WITH STEALTH MEMORY ---
        else:
            async with message.channel.typing():
                # 1. Fetch recent history for context
                raw_history = [msg async for msg in message.channel.history(limit=7)]
                raw_history.reverse()
                
                history_text = ""
                for msg in raw_history:
                    if msg.id != message.id:
                        history_text += f"{msg.author.display_name}: {msg.content}\n"

                # 2. ASSOCIATIVE MEMORY: Who are we talking about?
                speaker_name = message.author.display_name
                people_to_load = [speaker_name] # Always load the speaker
                
                # Scan the message for other faction mates
                for real_name, nicks in ai_engine.NICKNAMES.items():
                    if real_name.lower() in clean_message.lower() or any(n.lower() in clean_message.lower() for n in nicks):
                        if real_name not in people_to_load:
                            people_to_load.append(real_name)
                
                # Fetch DB files for EVERYONE mentioned
                combined_lore = ""
                for person in people_to_load:
                    # Notice we fetch by NAME now, not Discord ID!
                    lore = memory_db.get_player_lore(person) 
                    combined_lore += f"[{person}'s File]: {lore}\n"

                # 3. Get AI Response
                ai_reply = ai_engine.chat_with_jeremy(
                    user_name=speaker_name, 
                    user_message=clean_message,
                    chat_history=history_text,
                    associative_lore=combined_lore # Pass the new combined brain!
                )

                # ==========================================
                # BULLETPROOF EXTRACTION LOGIC
                # ==========================================
                import re
                
                # 1. Extract Player Lore
                lore_matches = re.findall(r"\[SAVE_LORE:\s*([^|\]]+)\s*\|\s*([^\]]+)\]", ai_reply, re.IGNORECASE)
                for subject, fact in lore_matches:
                    memory_db.update_player_lore(subject.strip(), fact.strip()) 

                # 2. Extract Milestones
                milestone_matches = re.findall(r"\[MILESTONE:\s*([^\]]+)\]", ai_reply, re.IGNORECASE)
                for achievement in milestone_matches:
                    memory_db.add_faction_milestone(achievement.strip())
                    
                # 3. Extract Faction History
                history_matches = re.findall(r"\[SAVE_HISTORY:\s*([^|\]]+)\s*\|\s*([^\]]+)\]", ai_reply, re.IGNORECASE)
                for topic, fact in history_matches:
                    memory_db.update_faction_history(topic.strip(), fact.strip(), speaker_name)
                    print(f"📜 History logged for '{topic.strip()}': {fact.strip()} (by {speaker_name})")

                # WIPE ALL TAGS SO DISCORD DOESN'T SEE THEM
                final_reply = re.sub(r"\[SAVE_LORE:.*?\]", "", ai_reply, flags=re.IGNORECASE)
                final_reply = re.sub(r"\[MILESTONE:.*?\]", "", final_reply, flags=re.IGNORECASE)
                final_reply = re.sub(r"\[SAVE_HISTORY:.*?\]", "", final_reply, flags=re.IGNORECASE)

                # ==========================================
                # THE NOPING EMOJI TRIGGER
                # ==========================================
                # 1. Check if Jeremy decided to be funny
                use_noping = False
                if "[USE_NOPING]" in final_reply.upper():
                    use_noping = True
                
                # 2. Wipe the tag so Discord doesn't see the text
                final_reply = re.sub(r"\[USE_NOPING\]", "", final_reply, flags=re.IGNORECASE).strip()

                # 3. Add the actual emoji to the front if triggered
                if use_noping:
                    noping_emoji = "<:noPing:1469263150913290324>"
                    final_reply = f"{noping_emoji} {final_reply}"

                if not final_reply: 
                    final_reply = "*(Jeremy nods and goes back to work)*"
                
                await message.channel.send(final_reply)

    await bot.process_commands(message)

# ... (Keep /set_key and /payout exactly as you have them) ...

# ==========================================
# THE VAULT COMMAND
# ==========================================
@bot.tree.command(name="set_key", description="Securely save your Torn API key to CyberJeremy's vault.")
@app_commands.describe(api_key="Your public Torn API Key")
async def set_key(interaction: discord.Interaction, api_key: str):
    # Ephemeral=True ensures the key is hidden from everyone else in the server
    await interaction.response.defer(ephemeral=True)
    
    try:
        memory_db.save_user_key(interaction.user.id, api_key)
        await interaction.followup.send("✅ Key securely locked in the vault. You won't need to type it again for `/scout` or `/payout`.")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to lock the vault: {e}")


# ==========================================
# THE PAYOUT COMMAND
# ==========================================

@bot.tree.command(name="payout", description="Calculate RW Payouts (Excel + PDF)")
@app_commands.describe(
    total_payout="Total money received",
    medical_cost="Medical costs to deduct",
    api_key="Your Torn API Key",
    pay_per_assist="Payment per assist (Default 0$)",
    outside_hit_val="Cash per outside hit (Default 0$)",
    outside_hit_limit="Max rewarded outside hits per person"
)
async def payout(interaction: discord.Interaction, 
                 total_payout: int, 
                 medical_cost: int, 
                 api_key: str, 
                 pay_per_assist: int = 0,
                 outside_hit_val: int = 0, 
                 outside_hit_limit: int = 0):
    
    # CRITICAL: Use defer because API calls + File generation can take > 3 seconds
    # This prevents the "Interaction Failed" error
    await interaction.response.defer(ephemeral=True)

    try:
        # 1. Generate the files using your main_logic
        saved_files = main_logic.process_war_and_get_files(
            api_key, total_payout, medical_cost, pay_per_assist, outside_hit_val, outside_hit_limit
        )
        
        # 2. Prepare files for Discord
        discord_files = [discord.File(f) for f in saved_files]
        
        # 3. Send files to the channel
        await interaction.channel.send(
            content=f"✅ **RW Payout Reports** | Pool: ${total_payout:,}",
            files=discord_files
        )

        # 4. Notify the user the task is done
        await interaction.followup.send("📊 Reports generated and sent to the channel!")

        # 5. Cleanup files from the server
        for f in saved_files:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        # Use followup since the interaction was deferred
        await interaction.followup.send(f"❌ **Error:** {str(e)}")

# 3. Safe Startup Loop
async def start_bot():
    token = os.getenv('DISCORD_TOKEN')
    
    # Start the Flask thread only once
    t = Thread(target=run_web_server)
    t.daemon = True
    t.start()

    while True:
        try:
            # This handles the actual connection to Discord
            async with bot:
                await bot.start(token)
        except discord.errors.HTTPException as e:
            if e.status == 429:
                # Cloudflare/Discord Rate Limit - Wait before retrying
                print("⚠️ Rate limited (429). Waiting 60 seconds to retry...")
                await asyncio.sleep(60)
            else:
                print(f"❌ HTTP Error {e.status}: {e.text}")
                break # Stop if it's a critical error like Invalid Token
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("Bot shutting down...")