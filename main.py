import os
import asyncio
import discord
from discord.ext import commands
from keep_alive import keep_alive

# 👉 Lấy ID kênh dùng lệnh và BOT_TOKEN từ Environment Variables
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

# 🔒 Giới hạn kênh dùng lệnh (Chỉ Admin hoặc đúng kênh BOT_CHANNEL_ID)
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
        # ⚠️ Lưu ý: Nếu các file nằm TRONG thư mục cogs/ thì giữ nguyên "cogs."
        # Nếu các file nằm NGOÀI cùng cấp với main.py thì bỏ chữ "cogs." đi nhé!
        await bot.load_extension("channel_lock")
        await bot.load_extension("checking")
        await bot.load_extension("member")
        await bot.load_extension("admin")
        
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())

