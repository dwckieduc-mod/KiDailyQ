import os
import asyncio
import discord
from discord.ext import commands
from keep_alive import keep_alive
from database import load_allowed_channels

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
    allowed_channels = load_allowed_channels()
    return allowed_channels.get(str(ctx.channel.id), False) == True

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        pass
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"❌ Lỗi thực thi lệnh: {error}")

@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user.name} đã kết nối thành công!")

async def main():
    keep_alive()
    async with bot:
        await bot.load_extension("main.lock")
        await bot.load_extension("main.check")
        await bot.load_extension("main.member")
        await bot.load_extension("main.admin")
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
    
