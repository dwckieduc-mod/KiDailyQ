import discord
from discord.ext import commands
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

# ==================== 3. HÀM QUẢN LÝ DỮ LIỆU JSON ====================

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
            title="🏆 BẢNG XẾP HẠNG ĐIỂM SỨC MẠNH 🏆",
            color=discord.Color.gold()
        )
        
        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_data = self.data[start_idx:end_idx]
        
        description = ""
        for index, (user_id, info) in enumerate(page_data, start=start_idx + 1):
            points = info.get("points", 0)
            streak = info.get("streak", 0)
            
            if index == 1:
                medal = "🥇"
            elif index == 2:
                medal = "🥈"
            elif index == 3:
                medal = "🥉"
            else:
                medal = f"**#{index}**"
                
            description += f"{medal} <@{user_id}> - **{points}** điểm (Chuỗi: {streak}/3)\n"

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

# ==================== 5. SỰ KIỆN BOT ====================

@bot.event
async def on_ready():
    print(f"✅ Bot đã kết nối thành công với tên: {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    has_image = any(
        att.content_type and att.content_type.startswith("image/") 
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
                await message.channel.send(f"⚠️ {message.author.mention}, bạn đã điểm danh ngày hôm nay rồi!")
                await bot.process_commands(message)
                return
            elif last_date == today - timedelta(days=1):
                user_info["streak"] += 1
            else:
                user_info["streak"] = 1
        else:
            user_info["streak"] = 1

        base_points = 10
        bonus_points = 0
        
        if user_info["streak"] == 3:
            bonus_points = 5
            user_info["streak"] = 0
            streak_msg = "\n🎉 **CHÚC MỪNG!** Bạn duy trì chuỗi 3 ngày liên tiếp và nhận thêm **+15 Điểm Sức Mạnh** bonus!"
        else:
            streak_msg = f"\n🔥 Chuỗi hiện tại: **{user_info['streak']}/3** ngày."

        total_gained = base_points + bonus_points
        user_info["points"] += total_gained
        user_info["last_date"] = str(today)
        user_info["total_quests"] = user_info.get("total_quests", 0) + 1
        
        data[user_id] = user_info
        save_data(data)

        await message.channel.send(
            f"✅ {message.author.mention} Đã nộp ảnh điểm danh hôm nay thành công!\n"
            f"💪 **+{total_gained} Điểm Sức Mạnh** (Tổng: **{user_info['points']}** điểm)."
            f"{streak_msg}"
        )

    await bot.process_commands(message)

# ==================== 6. LỆNH DÀNH CHO THÀNH VIÊN ====================

@bot.command(name="point", aliases=["pt", "profile"])
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
        # Sắp xếp danh sách người chơi theo điểm từ cao xuống thấp
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
        value=f"**{points}** điểm", 
        inline=True
    )
    embed.add_field(
        name="🔥 Chuỗi Streak", 
        value=f"**{streak}/3** ngày", 
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

@bot.command(name="top")
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

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="📜 DANH SÁCH LỆNH BOT DIỂM DANH",
        description="Tiền tố của bot là: `k.` hoặc `K.`",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="👤 Lệnh Cho Thành Viên",
        value=(
            "• `k.pt` / `k.point` / `k.profile` `[@User]`: Xem hồ sơ điểm danh & thông số cá nhân.\n"
            "• `k.top [số trang]`: Bảng xếp hạng thành viên.\n"
            "• `k.help`: Hiển thị bảng hướng dẫn này."
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Lệnh Cho Quản Trị Viên (Admin)",
        value=(
            "• `k.add @User <số điểm>`: Cộng thêm điểm cho thành viên.\n"
            "• `k.remove @User <số điểm>`: Trừ điểm của thành viên.\n"
            "• `k.reset @User`: Đặt lại toàn bộ điểm và streak của thành viên về 0."
        ),
        inline=False
    )

    embed.add_field(
        name="💡 Quy Tắc Điểm Danh",
        value=(
            "• Gửi **1 tấm ảnh** vào kênh nhiệm vụ để điểm danh mỗi ngày.\n"
            "• Mỗi ngày điểm danh nhận **+10 Điểm Sức Mạnh**.\n"
            "• Duy trì đủ **3 ngày liên tiếp** nhận thưởng thêm **+5 điểm bonus** và reset chuỗi mới."
        ),
        inline=False
    )
    
    embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

# ==================== 7. LỆNH DÀNH CHO ADMIN ====================

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def add_diem(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
    
    user_info["points"] += amount
    data[user_id] = user_info
    save_data(data)
    
    await ctx.send(f"✅ Đã **cộng {amount} điểm** cho {member.mention}. Tổng điểm mới: **{user_info['points']}** điểm.")

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def remove_diem(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
    
    user_info["points"] = max(0, user_info["points"] - amount)
    data[user_id] = user_info
    save_data(data)
    
    await ctx.send(f"🔻 Đã **trừ {amount} điểm** của {member.mention}. Tổng điểm còn lại: **{user_info['points']}** điểm.")

@bot.command(name="reset")
@commands.has_permissions(administrator=True)
async def reset_user(ctx, member: discord.Member):
    user_id = str(member.id)
    data = load_data()
    if user_id in data:
        del data[user_id]
        save_data(data)
        await ctx.send(f"🔄 Đã đặt lại (reset) toàn bộ dữ liệu của {member.mention}.")
    else:
        await ctx.send(f"⚠️ {member.mention} chưa có dữ liệu điểm danh.")

@add_diem.error
@remove_diem.error
@reset_user.error
async def admin_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn cần có quyền **Administrator** để dùng lệnh này!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Sai cú pháp!\n👉 Ví dụ: `k.add @User 50` hoặc `k.remove @User 20` hoặc `k.reset @User` ")

# ==================== 8. KHỞI CHẠY BOT ====================

if __name__ == "__main__":
    keep_alive()
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt biến môi trường 'BOT_TOKEN' trên Render!")
