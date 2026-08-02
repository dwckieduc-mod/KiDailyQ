import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from database import (
    load_data, save_data, get_streak_text, format_points, 
    load_allowed_channels, save_allowed_channels
)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- ⚙️ LỆNH QUẢN LÝ KÊNH CHO PHÉP (channel_allow) ---
    @commands.command(name="allow")
    @commands.has_permissions(administrator=True)
    async def allow(self, ctx, channel_input: str, status: str):
        is_true = status.lower() in ["true", "1", "yes", "on"]
        is_false = status.lower() in ["false", "0", "no", "off"]

        if not (is_true or is_false):
            embed = discord.Embed(
                title="⚠️ TRẠNG THÁI KHÔNG HỢP LỆ",
                description="Vui lòng nhập `true` (cho phép) hoặc `false` (từ chối/xóa).\n**Ví dụ:** `k.allow <id kênh> true`",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        clean_id = channel_input.strip("<#> ")
        if not clean_id.isdigit():
            embed = discord.Embed(
                title="⚠️ KÊNH KHÔNG HỢP LỆ",
                description="Vui lòng tag `#kênh` hoặc nhập đúng **ID kênh**!",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        data = load_allowed_channels()

        if is_true:
            data[clean_id] = True
            save_allowed_channels(data)
            embed = discord.Embed(
                title="✅ CẤP QUYỀN KÊNH THÀNH CÔNG",
                description=f"Kênh <#{clean_id}> **đã được phép** sử dụng lệnh bot!\nTrạng thái: `True`",
                color=discord.Color.green()
            )
        else:
            if clean_id in data:
                del data[clean_id]
                save_allowed_channels(data)
                embed = discord.Embed(
                    title="🗑️ ĐÃ XÓA KÊNH KHỎI HỆ THỐNG",
                    description=f"Kênh <#{clean_id}> đã bị **từ chối và xóa khỏi** file `channel_allow.json`!",
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="⚠️ KÊNH CHƯA TỒN TẠI",
                    description=f"Kênh <#{clean_id}> vốn chưa có trong danh sách được cấp quyền.",
                    color=discord.Color.gold()
                )

        await ctx.send(embed=embed)

    @allow.error
    async def allow_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            embed = discord.Embed(
                title="⚠️ SAI CÚ PHÁP LỆNH CHANNEL_ALLOW",
                description="Vui lòng nhập đúng:\n• `k.allow <id kênh> true` (Cấp quyền)\n• `k.allow #kênh false` (Xóa khỏi danh sách)",
                color=discord.Color.gold()
            )
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

    # --- 📋 LỆNH XEM DANH SÁCH KÊNH ĐƯỢC PHÉP (channel_allow_list) ---
    @commands.command(name="allowlist", aliases=["al"])
    @commands.has_permissions(administrator=True)
    async def channel_allow_list(self, ctx):
        data = load_allowed_channels()
        if not data:
            embed = discord.Embed(
                title="📋 DANH SÁCH KÊNH ĐƯỢC PHÉP DÙNG LỆNH",
                description="Hiện chưa có kênh nào trong `channel_allow.json`!\nQuản trị viên hãy dùng lệnh `k.allow #kênh True` để thêm.",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)
            return

        channel_list_str = ""
        for idx, (cid, status) in enumerate(data.items(), start=1):
            channel_list_str += f"**{idx}.** <#{cid}> — `ID: {cid}` (Được phép: `{status}`)\n"

        embed = discord.Embed(
            title="📋 DANH SÁCH KÊNH ĐƯỢC PHÉP DÙNG LỆNH",
            description=channel_list_str,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Tổng số: {len(data)} kênh")
        await ctx.send(embed=embed)

    @allowlist.error
    async def channel_allow_list_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

    # --- CÁC LỆNH ADMIN KHÁC GIỮ NGUYÊN ---
    @commands.command(name="add")
    @commands.has_permissions(administrator=True)
    async def add_diem(self, ctx, member: discord.Member, amount: int):
        user_id = str(member.id)
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
        
        user_info["points"] += amount
        data[user_id] = user_info
        save_data(data)
        
        embed = discord.Embed(
            title="🔺 CỘNG KIPOINTS",
            description=f"Đã cộng **+{amount} KiPoints** cho {member.mention}!",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Tổng KiPoints Mới", value=f"**{format_points(user_info['points'])}** KiPoints")
        embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @add_diem.error
    async def add_diem_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH ADD", description="Vui lòng nhập đúng:\n• `k.add @User <số_KiPoints>`", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(name="remove", aliases=["rm"])
    @commands.has_permissions(administrator=True)
    async def remove_diem(self, ctx, member: discord.Member, amount: int):
        user_id = str(member.id)
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
        
        user_info["points"] = max(0, user_info["points"] - amount)
        data[user_id] = user_info
        save_data(data)
        
        embed = discord.Embed(
            title="🔻 TRỪ KIPOINTS",
            description=f"Đã trừ **-{amount} KiPoints** của {member.mention}!",
            color=discord.Color.red()
        )
        embed.add_field(name="💰 Tổng KiPoints Còn Lại", value=f"**{format_points(user_info['points'])}** KiPoints")
        embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @remove_diem.error
    async def remove_diem_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH REMOVE", description="Vui lòng nhập đúng:\n• `k.remove @User <số_KiPoints>`", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(name="addstreak", aliases=["adds"])
    @commands.has_permissions(administrator=True)
    async def add_streak(self, ctx, member: discord.Member, amount: int):
        user_id = str(member.id)
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
        
        user_info["streak"] = max(0, user_info.get("streak", 0) + amount)
        
        vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
        today = vietnam_now.date()
        yesterday = today - timedelta(days=1)
        
        if user_info.get("last_date") != str(today):
            user_info["last_date"] = str(yesterday)

        data[user_id] = user_info
        save_data(data)
        
        embed = discord.Embed(
            title="🔥 CỘNG STREAK",
            description=f"Đã cộng **+{amount} ngày streak** cho {member.mention}!",
            color=discord.Color.green()
        )
        embed.add_field(name="🔥 Chuỗi Streak Hiện Tại", value=f"**{get_streak_text(user_info['streak'])}**")
        embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @add_streak.error
    async def add_streak_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH ADDSTREAK", description="Vui lòng nhập đúng:\n• `k.addstreak @User <số_ngày>`", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(name="removestreak", aliases=["rms"])
    @commands.has_permissions(administrator=True)
    async def remove_streak(self, ctx, member: discord.Member, amount: int):
        user_id = str(member.id)
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
        
        user_info["streak"] = max(0, user_info.get("streak", 0) - amount)
        data[user_id] = user_info
        save_data(data)
        
        embed = discord.Embed(
            title="🔻 TRỪ STREAK",
            description=f"Đã trừ **-{amount} ngày streak** của {member.mention}!",
            color=discord.Color.red()
        )
        embed.add_field(name="🔥 Chuỗi Streak Còn Lại", value=f"**{get_streak_text(user_info['streak'])}**")
        embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @remove_streak.error
    async def remove_streak_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH REMOVESTREAK", description="Vui lòng nhập đúng:\n• `k.removestreak @User <số_ngày>`", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(name="reset", aliases=["rs"])
    @commands.has_permissions(administrator=True)
    async def reset_user(self, ctx, member: discord.Member):
        user_id = str(member.id)
        data = load_data()
        if user_id in data:
            del data[user_id]
            save_data(data)
            embed = discord.Embed(
                title="🔄 RESET DỮ LIỆU THÀNH CÔNG",
                description=f"Toàn bộ dữ liệu KiPoints & stats của {member.mention} đã được đưa về 0.",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="⚠️ KHÔNG TÌM THẤY DỮ LIỆU",
                description=f"{member.mention} chưa có dữ liệu điểm danh trong hệ thống.",
                color=discord.Color.gold()
            )
        await ctx.send(embed=embed)

    @reset_user.error
    async def reset_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH RESET", description="Vui lòng nhập đúng:\n• `k.reset @User`", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

    @commands.command(name="deny", aliases=["dn"])
    @commands.has_permissions(administrator=True)
    async def refund_user(self, ctx, member: discord.Member):
        user_id = str(member.id)
        data = load_data()
        
        user_info = data.get(user_id)

        if not user_info or user_info.get("total_quests", 0) == 0 or not user_info.get("last_date"):
            embed = discord.Embed(
                title="⚠️ KHÔNG THỂ HOÀN TRẢ",
                description=f"Thành viên {member.mention} **chưa từng làm nhiệm vụ nào**",
                color=discord.Color.gold()
            )
            embed.set_footer(text=f"Yêu cầu bởi Admin: {ctx.author.display_name}")
            await ctx.send(embed=embed)
            return

        vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
        today = vietnam_now.date()
        yesterday = today - timedelta(days=1)

        current_streak = user_info.get("streak", 0)
        
        if current_streak >= 3:
            amount = 105
            bonus_msg = " *(Trừ 100 KiPoints gốc + 5 KiPoints bonus streak)*"
        else:
            amount = 100
            bonus_msg = " *(Trừ 100 KiPoints gốc)*"

        restored_streak = max(0, current_streak - 1)

        user_info["points"] = max(0, user_info.get("points", 0) - amount)
        user_info["total_quests"] = max(0, user_info.get("total_quests", 0) - 1)
        user_info["streak"] = restored_streak
        user_info["last_date"] = str(yesterday)

        data[user_id] = user_info
        save_data(data)

        embed = discord.Embed(
            title="🔄 HOÀN TRẢ LƯỢT ĐIỂM DANH",
            description=f"📢 {member.mention}\n**Nhiệm vụ này đã kết thúc!\nHãy làm nhiệm vụ mới**",
            color=discord.Color.blue()
        )
        embed.add_field(name="🔻 KiPoints Trừ", value=f"**-{amount}** KiPoints{bonus_msg}", inline=False)
        embed.add_field(name="💰 KiPoints Còn Lại", value=f"**{format_points(user_info['points'])}** KiPoints", inline=True)
        embed.add_field(name="🔥 Streak Khôi Phục", value=f"**{get_streak_text(restored_streak)}**", inline=True)
        embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
        
        await ctx.send(embed=embed)

    @refund_user.error
    async def refund_user_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
            embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH REFUND", description="Vui lòng nhập đúng:\n• `k.refund @User` hoặc `k.rf @User`", color=discord.Color.gold())
        else:
            embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
            
