import os
from openai import OpenAI
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@bot.event
async def on_ready():
    print(f"Bot konekte kòm {bot.user}")

@bot.command()
async def hello(ctx):
    await ctx.send("Hello! WCA Bot la anliy 🚀")
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    response = client.responses.create(
        model="gpt-5-mini",
        input=message.content
    )

    await message.channel.send(response.output_text)

TOKEN = os.getenv("DISCORD_TOKEN")
 
bot.run(TOKEN)

