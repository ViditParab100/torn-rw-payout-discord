import discord
from discord.ext import commands
import main_logic
import excel_generator
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.command()
async def payout(ctx, total_amount: int, medical_cost: int, api_key: str):
    await ctx.send(f"Processing... Deducting {medical_cost:,} for medical from the payout pool.")
    try:
        # Pass medical_cost to the logic
        data = main_logic.run_payout_logic(api_key, total_amount, medical_cost)
        file_name = excel_generator.create_payout_excel(data)
        await ctx.send(content=f"Report for **{data['title']}** generated.", file=discord.File(file_name))
    except Exception as e:
        await ctx.send(f"An error occurred: {e}")

bot.run('YOUR_BOT_TOKEN_HERE')