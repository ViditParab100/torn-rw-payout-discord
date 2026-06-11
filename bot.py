import discord
from discord import app_commands
from discord.ext import commands
import main_logic

from flask import Flask
from threading import Thread
import os
import asyncio

import ai_engine
import chart_generator
import memory_db
import milestone_detector
import ffscouter
import lore_db

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
        # Rebuild semantic lore index from MongoDB on startup
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, lore_db.rebuild_from_mongodb)

bot = RWBot()

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message):
        # Use clean_content to get rid of mentions cleanly
        clean_message = message.clean_content.replace(f'@{bot.user.display_name}', '').strip().lower()
        if not clean_message:
            clean_message = "hey buddy."

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

                    # 2. Auto-detect milestones in background (war hits + faction API)
                    loop = asyncio.get_event_loop()
                    loop.run_in_executor(None, lambda: milestone_detector.detect_war_milestones(war_data))
                    loop.run_in_executor(None, lambda: milestone_detector.detect_faction_api_milestones(api_key))

                    # 3. Generate AI Summary
                    ai_summary = ai_engine.generate_ai_summary(war_data)

                    # 4. Generate Charts
                    clean_opp_name = war_data['opponent_name'].replace(" ", "")
                    base_name = f"War_{clean_opp_name}_{war_data['war_id']}"
                    chart_paths = chart_generator.generate_war_charts(war_data, base_name)

                    # 5. Send Summary + Charts
                    final_text = ai_summary if ai_summary else "*(Jeremy wipes grease off his hands)* Stats are in, looks like a good scrap."
                    discord_files = [discord.File(path) for path in chart_paths]
                    await message.channel.send(content=final_text, files=discord_files)

                    for path in chart_paths:
                        if os.path.exists(path): os.remove(path)

                except Exception as e:
                    print(f"CRITICAL ERROR IN SCOUT: {e}")
                    await message.channel.send(f"❌ **CyberJeremy Error:** Something's wrong in the shop. {e}")

        # --- ROUTE B: NATURAL CHAT ---
        else:
            async with message.channel.typing():
                # 1. Build proper conversation turns from recent channel history
                raw_history = [msg async for msg in message.channel.history(limit=8)]
                raw_history.reverse()

                message_history = []
                for msg in raw_history:
                    if msg.id == message.id:
                        continue
                    if msg.author == bot.user:
                        message_history.append({"role": "assistant", "content": msg.clean_content})
                    else:
                        message_history.append({"role": "user", "content": f"{msg.author.display_name}: {msg.clean_content}"})

                # 2. Detect everyone mentioned for associative lore loading
                speaker_name = message.author.display_name
                people_mentioned = [speaker_name]
                for real_name, nicks in ai_engine.NICKNAMES.items():
                    if real_name.lower() in clean_message or any(n.lower() in clean_message for n in nicks):
                        if real_name not in people_mentioned:
                            people_mentioned.append(real_name)

                # 3. Get Jeremy's reply
                jeremy_reply, use_noping = ai_engine.chat_with_jeremy(
                    user_name=speaker_name,
                    user_message=clean_message,
                    message_history=message_history,
                    people_mentioned=people_mentioned
                )

                # 4. Send the reply immediately
                if use_noping:
                    jeremy_reply = f"<:noPing:1469263150913290324> {jeremy_reply}"
                if not jeremy_reply:
                    jeremy_reply = "*(Jeremy nods and goes back to work)*"

                await message.channel.send(jeremy_reply)

                # 5. Fire memory consolidation in the background (doesn't block the reply)
                loop = asyncio.get_event_loop()
                loop.run_in_executor(
                    None,
                    lambda: ai_engine.consolidate_and_save(speaker_name, clean_message, jeremy_reply, people_mentioned)
                )

    await bot.process_commands(message)

# ... (Keep /set_key exactly as you have it) ...

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
    api_key="Your Torn API Key (Optional if vault is set)",
    pay_per_assist="Payment per assist (Default 0$)",
    outside_hit_val="Cash per outside hit (Default 0$)",
    outside_hit_limit="Max rewarded outside hits per person"
)
async def payout(interaction: discord.Interaction, 
                 total_payout: int, 
                 medical_cost: int, 
                 api_key: str = None, 
                 pay_per_assist: int = 0,
                 outside_hit_val: int = 0, 
                 outside_hit_limit: int = 0):
    
    # CRITICAL: Use defer because API calls + File generation can take > 3 seconds
    await interaction.response.defer(ephemeral=True)

    try:
        # 0. Check Vault if api_key not provided
        if not api_key:
            api_key = memory_db.get_user_key(interaction.user.id)
            if not api_key:
                await interaction.followup.send("❌ No API key provided and none found in vault. Use `/set_key` first.")
                return

        # 1. Generate the files using your main_logic (Now cache-aware!)
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

# ==========================================
# BATTLE INTEL COMMAND
# ==========================================

@bot.tree.command(name="battle_intel", description="FFScouter war prediction — compare our stats vs an enemy faction")
@app_commands.describe(enemy_faction_id="Enemy faction ID (default: last war's opponent)")
async def battle_intel(interaction: discord.Interaction, enemy_faction_id: int = None):
    await interaction.response.defer()

    try:
        api_key = memory_db.get_user_key(interaction.user.id)
        if not api_key:
            await interaction.followup.send("Need your Torn API key first. Run `/set_key`.")
            return

        # Resolve enemy faction ID
        if not enemy_faction_id:
            last_war = memory_db.wars_collection.find_one(sort=[("war_id", -1)])
            if not last_war:
                await interaction.followup.send("No war history found. Provide an enemy faction ID.")
                return
            enemy_faction_id = last_war.get("opponent_id")
            enemy_name = last_war.get("opponent_name", f"Faction #{enemy_faction_id}")
        else:
            enemy_name = None  # scout_faction will fetch it from Torn

        await interaction.followup.send("*(Jeremy cracks his knuckles)* Pulling intel, give me a sec...")

        # Fetch both factions in sequence (FFScouter rate limit)
        our_data = ffscouter.scout_faction(api_key)
        their_data = ffscouter.scout_faction(api_key, faction_id=enemy_faction_id, faction_name=enemy_name)

        if not our_data or not their_data:
            await interaction.channel.send("❌ Couldn't pull stat data — check the faction ID or try again.")
            return

        comparison = ffscouter.compare_factions(our_data, their_data)
        jeremy_take = ai_engine.present_battle_intel(comparison)

        msg = f"{jeremy_take}\n```\n{comparison}\n```"
        # Discord has a 2000 char limit; truncate comparison if needed
        if len(msg) > 1990:
            msg = f"{jeremy_take}\n```\n{comparison[:1600]}\n...(truncated)\n```"

        await interaction.channel.send(msg)

    except Exception as e:
        print(f"BATTLE_INTEL ERROR: {e}")
        await interaction.followup.send(f"❌ Intel failed: {e}")


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