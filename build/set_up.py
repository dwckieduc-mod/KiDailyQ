import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timezone, timedelta
from database import load_allowed_channels, save_allowed_channels

VN_TZ = timezone(timedelta(hours=7))

# Custom Check kiểm tra Admin hoặc User được cấp quyền
def is_admin_or_allowed():
    async def predicate(ctx):
        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True
        allowed_data = await load_allowed_channels()
        allowed_users = allowed_data.get("allowed_users", [])
        return str(ctx.author.id) in allowed_users
    return commands.check(predicate)


class UnlockView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔓 Mở khóa kênh", style=discord.ButtonStyle.green, custom_id="unlock_channel_button")
    async def unlock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        allowed_data = await load_allowed_channels()
        allowed_users = allowed_data.get("allowed_users", [])

        if not (interaction.user.guild_permissions.administrator or str(interaction.user.id) in allowed_users):
            return await interaction.response.send_message(
                "❌ Chỉ Quản trị viên hoặc User được cấp quyền mới có thể sử dụng nút này!", 
                ephemeral=True
            )

        await interaction.response.defer()

        channel = interaction.channel
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

        button.disabled = True
        button.label = "🔓 Kênh đã mở khóa"
        button.style = discord.ButtonStyle.secondary
        await interaction.message.edit(view=self)

        embed = discord.Embed(
            title="🔓 KÊNH ĐÃ MỞ",
            description=f"Bắt đầu làm nhiệm vụ nào!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_lock_channel.start()

    async def cog_load(self):
        self.bot.add_view(UnlockView())

    def cog_unload(self):
        self.auto_lock_channel.cancel()

    @tasks.loop(time=time(hour=0, minute=0, second=0, tzinfo=VN_TZ))
    async def auto_lock_channel(self):
        allowed_channels = await load_allowed_channels(self.bot)
        target_channel_ids = set()

        for cid_str, perms in allowed_channels.items():
            if cid_str == "allowed_users":
                continue
            if isinstance(perms, dict) and perms.get("image"):
                target_channel_ids.add(int(cid_str))

        daily_id = os.environ.get("DAILY_CHANNEL_ID")
        if daily_id and daily_id.isdigit() and daily_id != "0":
            target_channel_ids.add(int(daily_id))

        if not target_channel_ids:
            return

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
                    if overwrite.send_messages is not False:
                        overwrite.send_messages = False
                        await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
                        
                        embed = discord.Embed(
                            title="🔒 ĐÃ KHÓA KÊNH",
                            description="Đã hết thời gian làm Daily Quest hôm nay!\nHãy đợi tới khi có Daily Quest mới.",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed, view=UnlockView())
                except Exception as e:
                    print(f"❌ Lỗi khi tự động khóa kênh {cid}: {e}")

    @auto_lock_channel.before_loop
    async def before_auto_lock(self):
        await self.bot.wait_until_ready()

    @commands.command(name="allow")
    @is_admin_or_allowed()
    async def allow(self, ctx, target_input: str, perm_type: str, status: str):
        perm_type_clean = perm_type.lower()
        if perm_type_clean not in ["image", "command", "user"]:
            embed = discord.Embed(
                title="⚠️ QUYỀN KHÔNG HỢP LỆ",
                description="Vui lòng chọn loại quyền:\n• `image`: Gửi ảnh điểm danh\n• `command`: Dùng lệnh bot ở kênh\n• `user`: Cấp quyền Admin Bot cho thành viên\n\n**Cú pháp:**\n• `k.allow <#kênh/ID> <image/command> <true/false>`\n• `k.allow <@User/ID> user <true/false>`",
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

        clean_id = target_input.strip("<#@!> ")
        if not clean_id.isdigit():
            embed = discord.Embed(title="⚠️ ID KHÔNG HỢP LỆ", description="Vui lòng tag `#kênh`, `@User` hoặc nhập đúng ID!", color=discord.Color.gold())
            return await ctx.send(embed=embed)

        data = await load_allowed_channels()

        # XỬ LÝ CẤP QUYỀN CHO USER
        if perm_type_clean == "user":
            allowed_users = data.get("allowed_users", [])
            if is_true:
                if clean_id not in allowed_users:
                    allowed_users.append(clean_id)
                data["allowed_users"] = allowed_users
                await save_allowed_channels(data)
                embed = discord.Embed(title="✅ CẤP QUYỀN USER THÀNH CÔNG", description=f"Thành viên <@{clean_id}> đã được **cấp quyền Admin Bot**!", color=discord.Color.green())
            else:
                if clean_id in allowed_users:
                    allowed_users.remove(clean_id)
                data["allowed_users"] = allowed_users
                await save_allowed_channels(data)
                embed = discord.Embed(title="🗑️ TẮT QUYỀN USER THÀNH CÔNG", description=f"Thành viên <@{clean_id}> đã bị **tước quyền Admin Bot**!", color=discord.Color.red())
            return await ctx.send(embed=embed)

        # XỬ LÝ CẤP QUYỀN CHO KÊNH
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
        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** hoặc được cấp quyền **user** để dùng lệnh này!", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name="allowlist", aliases=["al"])
    @is_admin_or_allowed()
    async def allowlist(self, ctx):
        data = await load_allowed_channels(self.bot)
        if not data:
            embed = discord.Embed(title="📋 DANH SÁCH ĐƯỢC CẤP QUYỀN", description="Hiện chưa có kênh/user nào được cấp quyền!", color=discord.Color.gold())
            return await ctx.send(embed=embed)

        channel_list_str = ""
        user_list_str = ""

        # Phân loại Channels và Users
        for cid, perms in data.items():
            if cid == "allowed_users":
                if isinstance(perms, list) and perms:
                    user_list_str = "\n".join([f"• <@{u_id}> (`{u_id}`)" for u_id in perms])
                continue

            if isinstance(perms, bool):
                perms = {"command": perms, "image": False}
            img_status = "✅ Cho phép" if perms.get("image") else "❌ Tắt"
            cmd_status = "✅ Cho phép" if perms.get("command") else "❌ Tắt"
            channel_list_str += f"• <#{cid}>\n   └ 🖼️ `image`: {img_status} | 💬 `command`: {cmd_status}\n"

        embed = discord.Embed(title="📋 DANH SÁCH ĐƯỢC CẤP QUYỀN HỆ THỐNG", color=discord.Color.blue())
        embed.add_field(name="👑 Thành viên Admin Bot (`user`)", value=user_list_str if user_list_str else "Chưa có user nào", inline=False)
        embed.add_field(name="📺 Kênh được phân quyền", value=channel_list_str if channel_list_str else "Chưa có kênh nào", inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="lock")
    @is_admin_or_allowed()
    async def lock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(title="🔒 ĐÃ KHÓA KÊNH", description=f"Đã tạm dừng nhiệm vụ", color=discord.Color.red())
        await ctx.send(embed=embed, view=UnlockView())

    @commands.command(name="unlock")
    @is_admin_or_allowed()
    async def unlock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        embed = discord.Embed(title="🔓 KÊNH ĐÃ MỞ", description=f"Bắt đầu làm nhiệm vụ nào!", color=discord.Color.green())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
        
