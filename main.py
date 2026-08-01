import os
import asyncio
import discord
from discord.ext import commands
from keep_alive import keep_alive

BOT_CHANNEL_ID = int(os.environ.get("BOT_CHANNEL_ID", 0))
BOT_TOKEN = os.environ.get("BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=["k.", "K."], 
    intents=intents, 
    case_insensitive=True,
    help_command=None
)

@bot.check
async def restrict_channel(ctx):
    if ctx.author.guild_permissions.administrator: 
        return True
    return ctx.channel.id == BOT_CHANNEL_ID

@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user.name} đã kết nối thành công!")

async def main():
    keep_alive()
    async with bot:
        await bot.load_extension("channel_lock")
        await bot.load_extension("checkin")
        await bot.load_extension("member")
        await bot.load_extension("admin")
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
asyncio.run(main())
