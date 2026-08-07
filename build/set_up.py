import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timezone, timedelta
from database import load_allowed_channels, save_allowed_channels

# Giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Kích hoạt vòng lặp khóa tự động
        self.auto_lock_channel.start()

    def cog_unload(self):
        self.auto_lock_channel.cancel()

    # ==================== CƠ CHẾ TỰ ĐỘNG KHÓA KÊNH (00:00 HÀNG NGÀY) ====================
    @tasks.loop(time=time(hour=0, minute=0, second=0, tzinfo=VN_TZ))
    async def auto_lock_channel(self):
        # 1. Tải danh sách kênh từ database
        allowed_channels = await load_allowed_channels(self.bot)
        target_channel_ids = set()

        # Quét các kênh được bật quyền 'image' (điểm danh)
        for cid_str, perms in allowed_channels.items():
            if isinstance(perms, dict) and perms.get("image"):
                target_channel_ids.add(int(cid_str))

        # Thêm kênh DAILY_CHANNEL_ID từ file .env nếu có
        daily_id = os.environ.get("DAILY_CHANNEL_ID")
        if daily_id and daily_id.isdigit() and daily_id != "0":
            target_channel_ids.add(int(daily_id))

        if not target_channel_ids:
            return

        # 2. Tiến hành khóa từng kênh
        for cid in target_channel_ids:
            channel = self.bot.get_channel(cid)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(cid)
                except Exception:
                    continue

            if channel and isinstance(channel, discord.TextChannel):
                try:
                    overwrite = channel.overwrites_for(channel.guild.default_role)
                    # Nếu kênh đang mở thì mới tiến hành khóa
                    if overwrite.send_messages is not False:
                        overwrite.send_messages = False
                        await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
                        
                        embed = discord.Embed(
                            title="🔒 ĐÃ TỰ ĐỘNG KHÓA KÊNH",
                            description="Đã hết thời gian làm Daily Quest hôm nay! Kênh đã được khóa tự động.",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed)
                except Exception as e:
                    print(f"❌ Lỗi khi tự động khóa kênh {cid}: {e}")

    @auto_lock_channel.before_loop
    async def before_auto_lock(self):
        await self.bot.wait_until_ready()

    @auto_lock_channel.error
    async def auto_lock_error(self, error):
        print(f"❌ Lỗi trong vòng lặp auto_lock_channel: {error}")

    # Tự động xóa khỏi database khi Admin xóa kênh khỏi máy chủ
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        data = await load_allowed_channels()
        cid_str = str(channel.id)
        if cid_str in data:
            del data[cid_str]
            await save_allowed_channels(data)

    # ==================== CÁC LỆNH CÀI ĐẶT THỦ CÔNG ====================
    @commands.command(name="allow")
    @commands.has_permissions(administrator=True)
    async def allow(self, ctx, channel_input: str, perm_type: str, status: str):
        perm_type_clean = perm_type.lower()
        if perm_type_clean not in ["image", "command"]:
            embed = discord.Embed(
                title="⚠️ QUYỀN KHÔNG HỢP LỆ",
                description="Vui lòng chọn loại quyền là `image` (gửi ảnh điểm danh) hoặc `command` (dùng lệnh).\n**Cú pháp:** `k.allow <#kênh/ID> <image/command> <true/false>`",
                color=discord.Color.gold()
            )
            return await ctx.send(embed=embed)

        is_true = status.lower() in ["true", "1", "yes", "on"]
        is_false = status.lower() in ["false", "0", "no", "off"]

        if not (is_true or is_false):
            embed = discord.Embed(
                title="⚠️ TRẠNG THÁI KHÔNG HỢP LỆ",
                description="Vui lòng nhập `true` (cho phép) hoặc `false` (tắt/xóa).",
                color=discord.Color.gold()
            )
            return await ctx.send(embed=embed)

        clean_id = channel_input.strip("<#> ")
        if not clean_id.isdigit():
            embed = discord.Embed(title="⚠️ KÊNH KHÔNG HỢP LỆ", description="Vui lòng tag `#kênh` hoặc nhập đúng ID kênh!", color=discord.Color.gold())
            return await ctx.send(embed=embed)

        data = await load_allowed_channels()
        ch_info = data.get(clean_id, {})
        if isinstance(ch_info, bool):
            ch_info = {"command": ch_info, "image": False}

        type_label = "Gửi ảnh/link điểm danh (image)" if perm_type_clean == "image" else "Dùng lệnh bot (command)"

        if is_true:
            ch_info[perm_type_clean] = True
            data[clean_id] = ch_info
            await save_allowed_channels(data)
            embed = discord.Embed(title="✅ CẤP QUYỀN KÊNH THÀNH CÔNG", description=f"Kênh <#{clean_id}> đã được **bật** quyền **{type_label}**!", color=discord.Color.green())
        else:
            ch_info[perm_type_clean] = False
            if not ch_info.get("image") and not ch_info.get("command"):
                data.pop(clean_id, None)
            else:
                data[clean_id] = ch_info
            await save_allowed_channels(data)
            embed = discord.Embed(title="🗑️ TẮT QUYỀN KÊNH THÀNH CÔNG", description=f"Kênh <#{clean_id}> đã bị **tắt** quyền **{type_label}**!", color=discord.Color.red())

        await ctx.send(embed=embed)

    @allow.error
    async def allow_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name="allowlist", aliases=["al"])
    @commands.has_permissions(administrator=True)
    async def allowlist(self, ctx):
        data = await load_allowed_channels(self.bot)
        if not data:
            embed = discord.Embed(title="📋 DANH SÁCH KÊNH ĐƯỢC CẤP QUYỀN", description="Hiện chưa có kênh nào được cấp quyền!", color=discord.Color.gold())
            return await ctx.send(embed=embed)

        channel_list_str = ""
        for idx, (cid, perms) in enumerate(data.items(), start=1):
            if isinstance(perms, bool):
                perms = {"command": perms, "image": False}
            img_status = "✅ Cho phép" if perms.get("image") else "❌ Tắt"
            cmd_status = "✅ Cho phép" if perms.get("command") else "❌ Tắt"
            channel_list_str += f"**{idx}.** <#{cid}>\n   • 🖼️ Điểm danh (`image`): {img_status}\n   • 💬 Dùng lệnh (`command`): {cmd_status}\n\n"

        embed = discord.Embed(title="📋 DANH SÁCH KÊNH ĐƯỢC CẤP QUYỀN", description=channel_list_str, color=discord.Color.blue())
        embed.set_footer(text=f"Tổng số: {len(data)} kênh")
        await ctx.send(embed=embed)

    @commands.command(name="lock")
    @commands.has_permissions(administrator=True)
    async def lock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(title="🔒 ĐÃ KHÓA KÊNH", description=f"Kênh {ctx.channel.mention} đã bị khóa gửi tin nhắn.", color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(name="unlock")
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(title="🔓 ĐÃ MỞ KHÓA KÊNH", description=f"Kênh {ctx.channel.mention} đã được mở khóa gửi tin nhắn.", color=discord.Color.green())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
    
