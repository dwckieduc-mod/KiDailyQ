import discord
from discord.ext import commands, tasks
import json
import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from threading import Thread

# ==================== 1. TẠO WEB SERVER GIỮ MẠNG CHO RENDER ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord đang chạy 24/7 trên Render!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ==================== 2. CẤU HÌNH BOT & MÔI TRƯỜNG ====================

QUEST_CHANNEL_ID = 1531955248481177731

BOT_TOKEN = os.environ.get("BOT_TOKEN")

DATA_FILE = "user_data.json"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=["k.", "K."], 
    intents=intents, 
    case_insensitive=True,
    help_command=None
)

bot.remove_command("help")

# ==================== 3. HÀM QUẢN LÝ DỮ LIỆU & HELPER ====================

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_streak_text(streak: int) -> str:
    """Trả về định dạng hiển thị Streak: >=3 ngày 🔥, <3 ngày ❄️"""
    if streak >= 3:
        return f"{streak} ngày 🔥"
    return f"{streak} ngày ❄️"

# ==================== 4. CLASS NÚT BẤM CHUYỂN TRANG CHO BXH ====================

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
                
            description += f"{medal} <@{user_id}> - **{points}** KiPoints (Chuỗi: {streak_display})\n"

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

# ==================== TỰ ĐỘNG KHÓA KÊNH LÚC 00:00 ====================

@tasks.loop(minutes=1)
async def auto_lock_channel():
    # Lấy giờ Việt Nam (UTC+7)
    vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
    
    # 🔒 KHÓA KÊNH LÚC 00:00 ĐÊM
    if vietnam_now.hour == 0 and vietnam_now.minute == 0:
        channel = bot.get_channel(QUEST_CHANNEL_ID)
        if channel:
            overwrite = channel.overwrites_for(channel.guild.default_role)
            
            if overwrite.send_messages != False:
                overwrite.send_messages = False
                await channel.set_permissions(channel.guild.default_role, overwrite=overwrite)
                
                embed = discord.Embed(
                    title="🔒 KÊNH ĐÃ KHÓA NỘP BÀI",
                    description="⏰ **Đã 00:00!** Hết thời gian nộp bài/điểm danh ngày hôm nay.\nKênh đã tự động khóa. Quản trị viên sẽ mở lại thủ công sau!",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)

# ==================== 5. SỰ KIỆN BOT ====================

@bot.event
async def on_ready():
    print(f"🤖 Bot {bot.user.name} đã kết nối thành công!")
    if not auto_lock_channel.is_running():
        auto_lock_channel.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Kiểm tra ảnh (bằng cả content_type lẫn đuôi file ảnh)
    image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
    has_image = any(
        (att.content_type and att.content_type.startswith("image/")) or
        att.filename.lower().endswith(image_extensions)
        for att in message.attachments
    )

    if has_image:
        if message.channel.id != QUEST_CHANNEL_ID:
            await bot.process_commands(message)
            return

        user_id = str(message.author.id)
        
        vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
        today = vietnam_now.date()
        
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
        
        last_date_str = user_info.get("last_date", "")
        
        if last_date_str:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            
            if last_date == today:
                embed = discord.Embed(
                    title="⚠️ ĐÃ ĐIỂM DANH HÔM NAY",
                    description=f"{message.author.mention}, bạn đã nộp ảnh điểm danh ngày hôm nay rồi!",
                    color=discord.Color.gold()
                )
                await message.channel.send(embed=embed)
                await bot.process_commands(message)
                return
            elif last_date == today - timedelta(days=1):
                user_info["streak"] += 1
            else:
                user_info["streak"] = 1
        else:
            user_info["streak"] = 1

        base_points = 100
        bonus_points = 0
        
        # Từ ngày thứ 3 trở đi nhận thêm 5 KiPoints bonus mỗi ngày
        if user_info["streak"] >= 3:
            bonus_points = 5
            is_bonus = True
        else:
            is_bonus = False

        total_gained = base_points + bonus_points
        user_info["points"] += total_gained
        user_info["last_date"] = str(today)
        user_info["total_quests"] = user_info.get("total_quests", 0) + 1
        
        data[user_id] = user_info
        save_data(data)

        # EMBED THÔNG BÁO THÀNH CÔNG
        embed = discord.Embed(
            title="✅ ĐIỂM DANH THÀNH CÔNG!",
            description=f"{message.author.mention} đã hoàn thành nhiệm vụ hôm nay!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.add_field(name="💪 KiPoints Nhận Được", value=f"**+{total_gained}** KiPoints", inline=True)
        embed.add_field(name="💰 Tổng KiPoints Hiện Có", value=f"**{user_info['points']}** KiPoints", inline=True)
        
        if is_bonus:
            embed.add_field(
                name="🎉 THƯỞNG CHUỖI STREAK!", 
                value=f"Bạn duy trì chuỗi **{user_info['streak']} ngày** liên tiếp và nhận thêm **+5 KiPoints Bonus**!", 
                inline=False
            )
        
        embed.add_field(
            name="🔥 Chuỗi Streak", 
            value=f"**{get_streak_text(user_info['streak'])}**", 
            inline=False
        )

        await message.channel.send(embed=embed)

    await bot.process_commands(message)

# ==================== 6. LỆNH DÀNH CHO THÀNH VIÊN ====================

@bot.command(name="profile", aliases=["pf"])
async def point(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})

    points = user_info.get("points", 0)
    streak = user_info.get("streak", 0)
    total_quests = user_info.get("total_quests", 0)
    last_date = user_info.get("last_date") or "Chưa điểm danh"

    # ================= TÍNH THỨ HẠNG (RANK) =================
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

    embed.add_field(
        name="🏆 Thứ Hạng (Rank)", 
        value=f"**{rank_str}**", 
        inline=True
    )
    embed.add_field(
        name="💪 Điểm Sức Mạnh", 
        value=f"**{points}** KiPoints", 
        inline=True
    )
    embed.add_field(
        name="🔥 Chuỗi Streak", 
        value=f"**{get_streak_text(streak)}**", 
        inline=True
    )
    embed.add_field(
        name="🎯 Daily Quest Đã Làm", 
        value=f"**{total_quests}** nhiệm vụ", 
        inline=True
    )
    embed.add_field(
        name="📅 Lần Cuối Điểm Danh", 
        value=f"`{last_date}`", 
        inline=True
    )

    embed.set_footer(
        text=f"Yêu cầu bởi {ctx.author.display_name}", 
        icon_url=ctx.author.display_avatar.url
    )

    await ctx.send(embed=embed)

@bot.command(name="top", aliases=["t"])
async def top(ctx, page: int = 1):
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

@bot.command(name="help", aliases=["h"])
async def help_command(ctx):
    embed = discord.Embed(
        title="📜 DANH SÁCH LỆNH BOT ĐIỂM DANH",
        description="Tiền tố của bot: `k.` hoặc `K.`",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="👤 Lệnh Cho Thành Viên",
        value=(
            "• `profile` / `pf` `[@User]`: Xem hồ sơ.\n"
            "• `top` / `t` `[số trang]`: Bảng xếp hạng.\n"
            "• `help` / `h`: Danh sách các lệnh."
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Lệnh Cho Quản Trị Viên (Admin)",
        value=(
            "• `unlock`: Mở kênh điểm danh.\n"
            "• `lock`: Khóa kênh điểm danh.\n"
            "• `add` `[@User]` `<số KiPoints>`: Cộng KiPoints.\n"
            "• `remove` / `rm` `[@User]` `<số KiPoints>`: Trừ KiPoints.\n"
            "• `addstreak` / `adds` `[@User]` `<số ngày>`: Cộng chuỗi streak.\n"
            "• `removestreak` / `rms` `[@User]` `<số ngày>`: Trừ chuỗi streak.\n"
            "• `reset` / `rs` `[@User]`: Đặt lại toàn bộ dữ liệu của thành viên.\n"
            "• `refund` / `rf` `[@User]`: Hủy kết quả và làm lại"
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

# ==================== 7. LỆNH DÀNH CHO ADMIN ====================

@bot.command(name="unlock")
@commands.has_permissions(administrator=True)
async def unlock_channel(ctx):
    channel = bot.get_channel(QUEST_CHANNEL_ID) or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    
    embed = discord.Embed(
        title="🔓 KÊNH ĐÃ MỞ NỘP BÀI",
        description="☀️ **Kênh điểm danh nhiệm vụ đã được Admin mở!**\nHãy gửi 1 tấm ảnh bài tập để nhận KiPoints ngay hôm nay.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@unlock_channel.error
async def unlock_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name="lock")
@commands.has_permissions(administrator=True)
async def lock_channel(ctx):
    channel = bot.get_channel(QUEST_CHANNEL_ID) or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    
    embed = discord.Embed(
        title="🔒 KHÓA KÊNH THỦ CÔNG",
        description=f"Admin {ctx.author.mention} đã khóa kênh nộp bài.",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@lock_channel.error
async def lock_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
        await ctx.send(embed=embed)

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def add_diem(ctx, member: discord.Member, amount: int):
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
    embed.add_field(name="💰 Tổng KiPoints Mới", value=f"**{user_info['points']}** KiPoints")
    embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@add_diem.error
async def add_diem_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH ADD", description="Vui lòng nhập đúng:\n• `k.add @User <số_KiPoints>`", color=discord.Color.gold())
    else:
        embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="remove", aliases=["rm"])
@commands.has_permissions(administrator=True)
async def remove_diem(ctx, member: discord.Member, amount: int):
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
    embed.add_field(name="💰 Tổng KiPoints Còn Lại", value=f"**{user_info['points']}** KiPoints")
    embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
    await ctx.send(embed=embed)

@remove_diem.error
async def remove_diem_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH REMOVE", description="Vui lòng nhập đúng:\n• `k.remove @User <số_KiPoints>`", color=discord.Color.gold())
    else:
        embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="addstreak", aliases=["adds"])
@commands.has_permissions(administrator=True)
async def add_streak(ctx, member: discord.Member, amount: int):
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
async def add_streak_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH ADDSTREAK", description="Vui lòng nhập đúng:\n• `k.addstreak @User <số_ngày>`", color=discord.Color.gold())
    else:
        embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="removestreak", aliases=["rms"])
@commands.has_permissions(administrator=True)
async def remove_streak(ctx, member: discord.Member, amount: int):
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
async def remove_streak_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH REMOVESTREAK", description="Vui lòng nhập đúng:\n• `k.removestreak @User <số_ngày>`", color=discord.Color.gold())
    else:
        embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="reset", aliases=["rs"])
@commands.has_permissions(administrator=True)
async def reset_user(ctx, member: discord.Member):
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
async def reset_user_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG COF QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH RESET", description="Vui lòng nhập đúng:\n• `k.reset @User`", color=discord.Color.gold())
    else:
        embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
    await ctx.send(embed=embed)

@bot.command(name="refund", aliases=["rf"])
@commands.has_permissions(administrator=True)
async def refund_user(ctx, member: discord.Member):
    user_id = str(member.id)
    data = load_data()
    
    user_info = data.get(user_id)

    if not user_info or user_info.get("total_quests", 0) == 0 or not user_info.get("last_date"):
        embed = discord.Embed(
            title="⚠️ KHÔNG THỂ HOÀN TRẢ",
            description=f"Thành viên {member.mention} **chưa từng làm nhiệm vụ nào**, không thể thực hiện refund!",
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
    embed.add_field(name="💰 KiPoints Còn Lại", value=f"**{user_info['points']}** KiPoints", inline=True)
    embed.add_field(name="🔥 Streak Khôi Phục", value=f"**{get_streak_text(restored_streak)}**", inline=True)
    embed.set_footer(text=f"Thực hiện bởi Admin: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@refund_user.error
async def refund_user_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(title="❌ KHÔNG CÓ QUYỀN", description="Bạn cần quyền **Administrator** để dùng lệnh này!", color=discord.Color.red())
    elif isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        embed = discord.Embed(title="⚠️ SAI CÚ PHÁP LỆNH REFUND", description="Vui lòng nhập đúng:\n• `k.refund @User` hoặc `k.rf @User`", color=discord.Color.gold())
    else:
        embed = discord.Embed(title="❌ LỖI HỆ THỐNG", description=f"`{error}`", color=discord.Color.red())
    await ctx.send(embed=embed)

# ==================== 8. KHỞI CHẠY BOT ====================

if __name__ == "__main__":
    keep_alive()
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt biến môi trường 'BOT_TOKEN' trên Render!")
