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

# 1. Flask Keep-Alive Setup
app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run_web_server():
    # Render assigns a port dynamically
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

# ==========================================
# THE SCOUT / WAR REPORT COMMAND
# ==========================================


@bot.event
async def on_message(message):
    # 1. Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # 2. Check if CyberJeremy was @mentioned
    if bot.user.mentioned_in(message):
        
        # Remove the bot's @ping from the text
        clean_message = message.content.replace(f'<@{bot.user.id}>', '').strip().lower()
        if not clean_message:
            clean_message = "Hey buddy."

        # Define keywords that trigger a War Report
        scout_keywords = ["scout", "war report", "stats", "war summary", "how are we doing", "status"]
        
        # --- ROUTE A: THE SCOUT / WAR REPORT ---
        # --- Update this part of your on_message in bot.py ---

        # --- ROUTE A: THE SCOUT / WAR REPORT ---
        if any(keyword in clean_message for keyword in scout_keywords):
            async with message.channel.typing():
                api_key = memory_db.get_user_key(message.author.id)
                if not api_key:
                    await message.channel.send(f"Hey {message.author.display_name}, I need your key first. Run `/set_key`.")
                    return

                try:
                    # 1. First status update
                    status_msg = await message.channel.send("*Grabbin' my binoculars, let me see what's happenin'...*")
                    
                    # 2. Fetch Data
                    war_data = main_logic.process_war_request(api_key, 0, 0, 0, 0, 0, force_update=False)
                    
                    # 3. Generate AI Summary (And print to terminal to verify it's working!)
                    ai_summary = ai_engine.generate_ai_summary(war_data)
                    print(f"DEBUG: AI Summary Output -> {ai_summary}") # <--- Check your terminal for this!

                    # 4. Generate Charts
                    clean_opp_name = war_data['opponent_name'].replace(" ", "")
                    base_name = f"War_{clean_opp_name}_{war_data['war_id']}"
                    chart_paths = chart_generator.generate_war_charts(war_data, base_name)
                    
                    # 5. Safety: If AI failed, use a fallback so the message isn't empty
                    final_content = ai_summary if ai_summary else "*(Jeremy scratches his head)* My comms are fuzzy, but here's the data anyway."
                    
                    # 6. Send everything
                    discord_files = [discord.File(path) for path in chart_paths]
                    await message.channel.send(content=final_content, files=discord_files)
                    
                    # Cleanup
                    await status_msg.delete() # Remove the "binoculars" message to keep chat clean
                    for path in chart_paths:
                        if os.path.exists(path): os.remove(path)

                except Exception as e:
                    print(f"CRITICAL ERROR IN SCOUT: {e}")
                    await message.channel.send(f"❌ **CyberJeremy Error:** Something went wrong in the shop. Check my logs.")

        # --- ROUTE B: NORMAL CHAT WITH MEMORY ---
        else:
            async with message.channel.typing():
                # Fetch the last 7 messages in the channel to build short-term memory
                raw_history = [msg async for msg in message.channel.history(limit=7)]
                raw_history.reverse() # Put them in chronological order
                
                # Format the history into a readable script for the AI
                history_text = ""
                for msg in raw_history:
                    # Skip the current message we are responding to
                    if msg.id != message.id:
                        speaker = msg.author.display_name
                        history_text += f"{speaker}: {msg.content}\n"

                # Send it all to the AI Engine
                ai_reply = ai_engine.chat_with_jeremy(
                    user_name=message.author.display_name, 
                    user_message=clean_message,
                    chat_history=history_text
                )
                
                await message.channel.send(ai_reply)

    # 3. Process Slash Commands (like /payout and /set_key)
    await bot.process_commands(message)

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