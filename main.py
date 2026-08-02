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

# 🔒 HÀM CHECK QUYỀN KÊNH TỰ ĐỘNG
@bot.check
async def restrict_channel(ctx):
    # Admin được dùng lệnh ở mọi kênh
    if ctx.author.guild_permissions.administrator: 
        return True
        
    allowed_channels = load_allowed_channels()
    # Check ID kênh hiện tại có trong channel_allow.json và là True không
    return allowed_channels.get(str(ctx.channel.id), False) == True

# 🛑 BẮT LỖI TỰ ĐỘNG KHI THÀNH VIÊN DÙNG SAI KÊNH
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        allowed_channels = load_allowed_channels()
        if not allowed_channels:
            await ctx.send("⚠️ **Hệ thống:** Chưa có kênh nào được cấp quyền dùng lệnh! Admin hãy dùng `k.channel_allow #kênh True` để thiết lập.")
        else:
            channel_mentions = ", ".join([f"<#{cid}>" for cid in allowed_channels.keys()])
            await ctx.send(f"⚠️ {ctx.author.mention}, bạn chỉ có thể dùng lệnh tại các kênh sau: {channel_mentions}")
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
        # Load trực tiếp các extension ở thư mục gốc
        await bot.load_extension("channel_lock")
        await bot.load_extension("checking")
        await bot.load_extension("member")
        await bot.load_extension("admin")
        
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
    
