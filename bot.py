import discord
from discord import app_commands
from discord.ext import commands
import main_logic

from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run():
    # Render assigns a port dynamically via the PORT environment variable
    port = int(os.environ.get("PORT", 10000)) 
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- CALL THIS BEFORE bot.run(token) ---
keep_alive()


# Code ->

intents = discord.Intents.default()
intents.message_content = True

class RWBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"✅ Slash commands synced for {self.user}")

bot = RWBot()

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
    
    await interaction.response.send_message("⏳ Generating Excel and PDF reports...", ephemeral=True)

    try:
        # 1. Call plural function
        saved_files = main_logic.process_war_and_get_files(
            api_key, total_payout, medical_cost, pay_per_assist, outside_hit_val, outside_hit_limit
        )
        
        # 2. Prepare files for Discord
        discord_files = [discord.File(f) for f in saved_files]
        
        # 3. Send both files
        await interaction.channel.send(
            content=f"✅ **RW Payout Reports** (Limit: {outside_hit_limit} hits/newbie)",
            files=discord_files
        )

        # 4. Cleanup both files
        for f in saved_files:
            if os.path.exists(f):
                os.remove(f)

    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 3. Run the bot
# bot.run('YOUR_BOT_TOKEN_HERE')
token = os.getenv('DISCORD_TOKEN') 
bot.run(token)