import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread

# ==================== 1. TẠO WEB SERVER GIỮ MẠNG CHO RENDER ====================
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord đang chạy 24/7 trên Render!"

def run_web():
    # Render sẽ tự cấp cổng PORT ngẫu nhiên qua biến môi trường
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# ==================== 2. CẤU HÌNH BOT & MÔI TRƯỜNG ====================

# ID Kênh nộp ảnh điểm danh
QUEST_CHANNEL_ID = 1531955248481177731

# Lấy Token an toàn từ Environment Variables của Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Tệp lưu trữ dữ liệu điểm
DATA_FILE = "user_data.json"

# Thiết lập Intents cho Discord
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=["k.", "K."], 
    intents=intents, 
    case_insensitive=True
)

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

# ==================== 4. SỰ KIỆN BOT ====================

@bot.event
async def on_ready():
    print(f"✅ Bot đã kết nối thành công với tên: {bot.user.name}")

@bot.event
async def on_message(message):
    # Bỏ qua tin nhắn từ chính con bot hoặc các bot khác
    if message.author.bot:
        return

    # Kiểm tra tin nhắn có chứa ảnh đính kèm không
    has_image = any(
        att.content_type and att.content_type.startswith("image/") 
        for att in message.attachments
    )

    if has_image:
        # Nếu gửi ảnh ở kênh khác kênh nhiệm vụ -> Bỏ qua phần tính điểm danh
        if message.channel.id != QUEST_CHANNEL_ID:
            await bot.process_commands(message)
            return

        user_id = str(message.author.id)
        
        # Lấy ngày hôm nay chuẩn theo MÚI GIỜ VIỆT NAM (UTC+7) trên Server Render
        vietnam_now = datetime.utcnow() + timedelta(hours=7)
        today = vietnam_now.date()
        
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0})
        
        last_date_str = user_info.get("last_date", "")
        
        if last_date_str:
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            
            # Trường hợp 1: Đã điểm danh hôm nay rồi
            if last_date == today:
                await message.channel.send(f"⚠️ {message.author.mention}, bạn đã điểm danh ngày hôm nay rồi! Hãy quay lại vào ngày mai nhé.")
                await bot.process_commands(message)
                return
            
            # Trường hợp 2: Điểm danh liên tiếp (Hôm qua có điểm danh)
            elif last_date == today - timedelta(days=1):
                user_info["streak"] += 1
            
            # Trường hợp 3: Bỏ lỡ từ 1 ngày trở lên -> Reset chuỗi streak về 1
            else:
                user_info["streak"] = 1
        else:
            # Lần đầu tiên điểm danh
            user_info["streak"] = 1

        base_points = 10
        bonus_points = 0
        
        # TÍNH THƯỞNG VÀ RESET STREAK KHI ĐẠT MỐC 3 NGÀY
        if user_info["streak"] == 3:
            bonus_points = 20
            user_info["streak"] = 0  # Reset streak về 0 để tính vòng mới
            streak_msg = "\n🎉 **CHÚC MỪNG!** Bạn duy trì chuỗi 3 ngày liên tiếp và nhận thêm **+20 Điểm Sức Mạnh** bonus!"
        else:
            streak_msg = f"\n🔥 Chuỗi hiện tại: **{user_info['streak']}/3** ngày."

        total_gained = base_points + bonus_points
        user_info["points"] += total_gained
        user_info["last_date"] = str(today)
        
        data[user_id] = user_info
        save_data(data)

        await message.channel.send(
            f"✅ {message.author.mention} Đã nộp ảnh điểm danh hôm nay thành công!\n"
            f"💪 **+{total_gained} Điểm Sức Mạnh** (Tổng: **{user_info['points']}** điểm)."
            f"{streak_msg}"
        )

    # Đảm bảo các lệnh prefix (k.point, k.top,...) vẫn hoạt động bình thường
    await bot.process_commands(message)

# ==================== 5. LỆNH DÀNH CHO THÀNH VIÊN ====================

@bot.command(name="point", aliases=["pt"])
async def point(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "streak": 0})
    await ctx.send(f"📊 {target.mention} đang có **{user_info.get('points', 0)} Điểm Sức Mạnh** (Chuỗi: {user_info.get('streak', 0)}/3 ngày).")

@bot.command(name="top")
async def top(ctx):
    data = load_data()
    if not data:
        await ctx.send("📋 Chưa có dữ liệu điểm danh nào trong hệ thống!")
        return

    # Sắp xếp người dùng theo số điểm từ cao xuống thấp
    sorted_users = sorted(data.items(), key=lambda item: item[1].get("points", 0), reverse=True)
    
    embed = discord.Embed(
        title="🏆 BẢNG XẾP HẠNG ĐIỂM SỨC MẠNH 🏆",
        color=discord.Color.gold()
    )
    
    description = ""
    for index, (user_id, info) in enumerate(sorted_users[:10], start=1):
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
    await ctx.send(embed=embed)

# ==================== 6. LỆNH DÀNH CHO QUẢN TRỊ VIÊN (ADMIN) ====================

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def add_diem(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0})
    
    user_info["points"] += amount
    data[user_id] = user_info
    save_data(data)
    
    await ctx.send(f"✅ Đã **cộng {amount} điểm** cho {member.mention}. Tổng điểm mới: **{user_info['points']}** điểm.")

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def remove_diem(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0})
    
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

# Bắt lỗi khi người dùng không có quyền Admin hoặc gõ sai cú pháp
@add_diem.error
@remove_diem.error
@reset_user.error
async def admin_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Bạn cần có quyền **Administrator** để dùng lệnh này!")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Sai cú pháp!\n👉 Ví dụ: `k.add @User 50` hoặc `k.remove @User 20` hoặc `k.reset @User` ")

# ==================== 7. CHẠY BOT ====================

if __name__ == "__main__":
    keep_alive()  # Khởi động Flask Server giữ mạng 24/7
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("❌ LỖI: Chưa cài đặt biến môi trường 'BOT_TOKEN' trên Render!")
    intents=intents, 
    case_insensitive=True
    
DATA_FILE = "user_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

@bot.event
async def on_ready():
    print(f"✅ Bot đã hoạt động thành công với tên: {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    has_image = any(att.content_type and att.content_type.startswith("image/") for att in message.attachments)

    if has_image:
        if message.channel.id != QUEST_CHANNEL_ID:
            await bot.process_commands(message)
            return

        user_id = str(message.author.id)
        today = datetime.now().date()
        
        data = load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0})
        
        last_date_str = user_info["last_date"]
        
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
            bonus_points = 20
            user_info["streak"] = 0
            streak_msg = "\n🎉 **CHÚC MỪNG!** Bạn duy trì chuỗi 3 ngày liên tiếp và nhận thêm **+20 Điểm Sức Mạnh** bonus!"
        else:
            streak_msg = f"\n🔥 Chuỗi hiện tại: **{user_info['streak']}/3** ngày."

        total_gained = base_points + bonus_points
        user_info["points"] += total_gained
        user_info["last_date"] = str(today)
        
        data[user_id] = user_info
        save_data(data)

        await message.channel.send(
            f"✅ {message.author.mention} Đã nộp ảnh điểm danh hôm nay!\n"
            f"💪 **+{total_gained} Điểm Sức Mạnh** (Tổng: **{user_info['points']}** điểm)."
            f"{streak_msg}"
        )

    await bot.process_commands(message)

# ----------------- LỆNH USER -----------------

@bot.command(name="point", aliases=["pt"])
async def point(ctx, member: discord.Member = None):
    target = member or ctx.author
    user_id = str(target.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "streak": 0})
    await ctx.send(f"📊 {target.mention} đang có **{user_info['points']} Điểm Sức Mạnh** (Chuỗi: {user_info['streak']}/3).")

@bot.command(name="top")
async def top(ctx):
    data = load_data()
    if not data:
        await ctx.send("📋 Chưa có dữ liệu điểm danh nào!")
        return

    sorted_users = sorted(data.items(), key=lambda item: item[1].get("points", 0), reverse=True)
    
    embed = discord.Embed(
        title="🏆 BẢNG XẾP HẠNG ĐIỂM SỨC MẠNH 🏆",
        color=discord.Color.gold()
    )
    
    description = ""
    for index, (user_id, info) in enumerate(sorted_users[:10], start=1):
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
    await ctx.send(embed=embed)

# ----------------- LỆNH ADMIN -----------------

@bot.command(name="add")
@commands.has_permissions(administrator=True)
async def add_diem(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0})
    
    user_info["points"] += amount
    data[user_id] = user_info
    save_data(data)
    
    await ctx.send(f"✅ Đã **cộng {amount} điểm** cho {member.mention}. Tổng điểm mới: **{user_info['points']}** điểm.")

@bot.command(name="remove")
@commands.has_permissions(administrator=True)
async def remove_diem(ctx, member: discord.Member, amount: int):
    user_id = str(member.id)
    data = load_data()
    user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0})
    
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

if __name__ == "__main__":
    keep_alive()
    bot.run(BOT_TOKEN)
