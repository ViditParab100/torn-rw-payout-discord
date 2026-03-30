import discord
from discord import app_commands
from discord.ext import commands
import main_logic

from flask import Flask
from threading import Thread
import os
import asyncio

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