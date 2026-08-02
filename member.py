import discord
from discord.ext import commands
from database import load_data, get_streak_text
from database import load_data, get_streak_text, format_points

class LeaderboardView(discord.ui.View):
    def __init__(self, data, author_id, per_page=10):
        super().__init__(timeout=60)
        self.data = data
        self.author_id = author_id
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = max(1, (len(data) + per_page - 1) // per_page)
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = (self.current_page == 1)
        self.children[1].disabled = (self.current_page == self.total_pages)

    def create_embed(self):
        embed = discord.Embed(
            title="🏆 BẢNG XẾP HẠNG KIPOINTS 🏆",
            color=discord.Color.gold()
        )
        
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_data = self.data[start_idx:end_idx]
        
        description = ""
        for index, (user_id, info) in enumerate(page_data, start=start_idx + 1):
            points = info.get("points", 0)
            streak = info.get("streak", 0)
            streak_display = get_streak_text(streak)
            
            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"**#{index}**"
                
            description += f"{medal} <@{user_id}> - **{format_points(points)}** KiPoints (Chuỗi: {streak_display})\n"

        embed.description = description
        embed.set_footer(text=f"Trang {self.current_page}/{self.total_pages} • Tổng: {len(self.data)} thành viên")
        return embed

    @discord.ui.button(label="◀ Trang trước", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Chỉ người dùng lệnh mới có thể chuyển trang!", ephemeral=True)
        
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Trang sau ▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Chỉ người dùng lệnh mới có thể chuyển trang!", ephemeral=True)
        
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass

class MemberCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="profile", aliases=["pf"])
    async def point(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        user_id = str(target.id)
        
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})

        points = user_info.get("points", 0)
        streak = user_info.get("streak", 0)
        total_quests = user_info.get("total_quests", 0)
        last_date = user_info.get("last_date") or "Chưa điểm danh"

        rank_str = "Chưa xếp hạng"
        if data:
            sorted_users = sorted(data.items(), key=lambda item: item[1].get("points", 0), reverse=True)
            for idx, (uid, info) in enumerate(sorted_users, start=1):
                if uid == user_id:
                    if idx == 1:
                        rank_str = "🥇 Top 1"
                    elif idx == 2:
                        rank_str = "🥈 Top 2"
                    elif idx == 3:
                        rank_str = "🥉 Top 3"
                    else:
                        rank_str = f"#{idx} / {len(sorted_users)}"
                    break

        embed = discord.Embed(
            title="💳 HỒ SƠ NHIỆM VỤ CÁ NHÂN",
            description=f"Bảng thống kê hoạt động của {target.mention}",
            color=discord.Color.purple()
        )
        
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)

        embed.add_field(name="🏆 Thứ Hạng (Rank)", value=f"**{rank_str}**", inline=True)
        embed.add_field(name="💪 Điểm Sức Mạnh", value=f"**{format_points(points)}** KiPoints (`{format_points(points, shorten=True)}`)", inline=True)
        embed.add_field(name="🔥 Chuỗi Streak", value=f"**{get_streak_text(streak)}**", inline=True)
        embed.add_field(name="🎯 Daily Quest Đã Làm", value=f"**{total_quests}** nhiệm vụ", inline=True)
        embed.add_field(name="📅 Lần Cuối Điểm Danh", value=f"`{last_date}`", inline=True)

        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="top", aliases=["t"])
    async def top(self, ctx, page: int = 1):
        data = load_data()
        if not data:
            await ctx.send("📋 Chưa có dữ liệu điểm danh nào trong hệ thống!")
            return

        sorted_users = sorted(data.items(), key=lambda item: item[1].get("points", 0), reverse=True)
        
        per_page = 10
        total_pages = max(1, (len(sorted_users) + per_page - 1) // per_page)
        
        if page < 1 or page > total_pages:
            await ctx.send(f"⚠️ Trang không hợp lệ! Vui lòng chọn trang từ **1** đến **{total_pages}**.")
            return

        view = LeaderboardView(sorted_users, ctx.author.id, per_page=per_page)
        view.current_page = page
        view.update_buttons()
        
        embed = view.create_embed()
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name="help", aliases=["h"])
    async def help_command(self, ctx):
        embed = discord.Embed(
            title="📜 DANH SÁCH LỆNH BOT ĐIỂM DANH",
            description="Tiền tố của bot: `k.` hoặc `K.`",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="👤 Lệnh Cho Thành Viên",
            value=(
                "• `profile / pf @User`: Xem hồ sơ.\n"
                "• `top / t số trang`: Bảng xếp hạng.\n"
                "• `help / h`: Danh sách các lệnh."
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Lệnh Cho Quản Trị Viên (Admin)",
            value=(
                "• `add @User <số KiPoints>`: Cộng KiPoints.\n"
                "• `remove / rm @User <số KiPoints>`: Trừ KiPoints.\n"
                "• `addstreak / adds @User <số ngày>`: Cộng chuỗi streak.\n"
                "• `removestreak / rms @User` `<số ngày>`: Trừ chuỗi streak.\n"
                "• `reset / rs @User`: Đặt lại toàn bộ dữ liệu của thành viên.\n"
                "• `deny / dn @User`: Hủy kết quả và làm lại.\n"
                "• `unlock`: Mở kênh.\n"
                "• `lock`: Khóa kênh."
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Quy Tắc Điểm Danh",
            value=(
                "• Làm nhiệm vụ và gửi ảnh.\n"
                "• Mỗi ngày điểm danh nhận **+100 KiPoints**.\n"
                "• Duy trì chuỗi điểm danh từ **ngày thứ 3 trở đi** nhận thêm **+5 KiPoints bonus** mỗi ngày."
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MemberCog(bot))
