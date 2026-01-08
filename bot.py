import discord
from discord import app_commands
from discord.ext import commands
import main_logic
import os

# 1. Setup Intents and Bot Class
intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # This syncs your / commands with Discord's servers
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")

bot = MyBot()

# 2. The Slash Command
@bot.tree.command(name="payout", description="Calculate RW Payouts with smooth respect averages")
@app_commands.describe(
    total_payout="The total money received from the Ranked War",
    medical_cost="Total medical costs to deduct after the 10% faction cut",
    api_key="Your Torn API Key"
)
async def payout(interaction: discord.Interaction, total_payout: int, medical_cost: int, api_key: str):
    # 'ephemeral=True' means only YOU see the processing message, hiding your key entirely
    await interaction.response.send_message(
        f"⏳ Processing report... Deducting {medical_cost:,} medical costs.", 
        ephemeral=True
    )

    try:
        # Call your logic function
        saved_file = main_logic.process_war_and_get_file(api_key, total_payout, medical_cost)

        # Send the file to the channel for everyone to see
        # We use the follow-up because the initial response was ephemeral
        await interaction.channel.send(
            content=f"✅ **RW Payout Report Generated** by {interaction.user.mention}\n"
                    f"Total Payout: ${total_payout:,} | Medical: ${medical_cost:,}",
            file=discord.File(saved_file)
        )

        # Clean up the file from the server
        if os.path.exists(saved_file):
            os.remove(saved_file)

    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 3. Run the bot
# bot.run('YOUR_BOT_TOKEN_HERE')
token = os.getenv('DISCORD_TOKEN') 
bot.run(token)