import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone

DAILY_CHANNEL_ID = int(os.environ.get("DAILY_CHANNEL_ID", 0))

class ChannelLockCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_lock_channel.start()

    def cog_unload(self):
        self.auto_lock_channel.cancel()

    @tasks.loop(minutes=1)
    async def auto_lock_channel(self):
        vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
        
        if vietnam_now.hour == 0 and vietnam_now.minute == 0:
            channel = self.bot.get_channel(DAILY_CHANNEL_ID)
            if channel:
                overwrite = channel.overwrites_for(channel.guild.default_role)
                if overwrite.send_messages != False:
                    overwrite.send_messages = False
                    await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
                    
                    embed = discord.Embed(
                        title="🔒 ĐÃ KHÓA KÊNH ",
                        description="⏰ **Đã sang ngày mới!**\nHãy đợi đến khi có nhiệm vụ mới",
                        color=discord.Color.red()
                    )
                    await channel.send(embed=embed)

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock_channel(self, ctx):
        try:
            channel = self.bot.get_channel(DAILY_CHANNEL_ID) or ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = True
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            
            embed = discord.Embed(
                title="🔓 ĐÃ MỞ KHOÁ KÊNH",
                description="☀️ **Kênh đã được mở!**\nHãy làm nhiệm vụ nào!",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ **Lỗi Discord:** `{e}`")

    @unlock_channel.error
    async def unlock_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Manage Channels** để dùng lệnh này!", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock_channel(self, ctx):
        try:
            channel = self.bot.get_channel(DAILY_CHANNEL_ID) or ctx.channel
            overwrite = channel.overwrites_for(ctx.guild.default_role)
            overwrite.send_messages = False
            await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
            
            embed = discord.Embed(
                title="🔒 ĐÃ KHOÁ KÊNH",
                description=f"Quản lý {ctx.author.mention} đã khóa kênh.\nHãy đợi tới khi có quest mới",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ **Lỗi Discord:** `{e}`")

    @lock_channel.error
    async def lock_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Manage Channels** để dùng lệnh này!", color=discord.Color.red())
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ChannelLockCog(bot))
