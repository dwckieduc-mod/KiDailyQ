import re
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from database import load_data, save_data, load_allowed_channels, get_streak_text, format_points

# Biểu thức chính quy (Regex) nhận diện đường link (http:// hoặc https://)
URL_REGEX = re.compile(r'https?://[^\s]+', re.IGNORECASE)

class CheckCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # Bỏ qua tin nhắn từ Bot hoặc tin nhắn riêng (DM)
        if message.author.bot or not message.guild:
            return

        # Kiểm tra xem kênh hiện tại có quyền gửi ảnh/minh chứng ('image') không
        allowed_channels = await load_allowed_channels(self.bot)
        channel_id = str(message.channel.id)

        if channel_id not in allowed_channels:
            return

        perm = allowed_channels[channel_id]
        has_image_perm = perm.get("image", False) if isinstance(perm, dict) else False

        if not has_image_perm:
            return

        # 1. KIỂM TRA MINH CHỨNG (Có file đính kèm HOẶC chứa đường link bất kỳ)
        has_attachment = len(message.attachments) > 0
        has_link = bool(URL_REGEX.search(message.content))

        # Nếu tin nhắn KHÔNG có cả file đính kèm lẫn link -> Bỏ qua
        if not (has_attachment or has_link):
            return

        # 2. XỬ LÝ DUY NHẤT 1 LẦN CHO MỖI TIN NHẮN (Ngăn lặp lại gây spam lỗi)
        user_id = str(message.author.id)
        data = await load_data()
        user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})

        # Lấy ngày theo giờ Việt Nam (UTC+7)
        vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
        today_str = str(vietnam_now.date())
        yesterday_str = str((vietnam_now - timedelta(days=1)).date())

        # TRƯỜNG HỢP A: Đã điểm danh trong ngày hôm nay rồi
        if user_info.get("last_date") == today_str:
            await message.add_reaction("❌")
            embed = discord.Embed(
                title="❌ ĐÃ HOÀN THÀNH NHIỆM VỤ",
                description=f"{message.author.mention} Bạn đã làm nhiệm vụ và nhận điểm ngày hôm nay rồi!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=10)
            return

        # TRƯỜNG HỢP B: Chưa điểm danh hôm nay -> Tiến hành cộng điểm danh
        current_streak = user_info.get("streak", 0)
        last_date = user_info.get("last_date")

        # Cập nhật chuỗi Streak
        if last_date == yesterday_str:
            new_streak = current_streak + 1
        else:
            new_streak = 1

        # Tính toán điểm thưởng (Thưởng thêm 5 KiPoints nếu Streak >= 3 ngày)
        base_points = 100
        bonus_points = 5 if new_streak >= 3 else 0
        total_earned = base_points + bonus_points

        # Lưu dữ liệu mới
        user_info["points"] += total_earned
        user_info["streak"] = new_streak
        user_info["last_date"] = today_str
        user_info["total_quests"] = user_info.get("total_quests", 0) + 1

        data[user_id] = user_info
        await save_data(data)

        # Thả thả cảm xúc thông báo
        await message.add_reaction("✅")
        if bonus_points > 0:
            await message.add_reaction("🔥")

        # Gửi thông báo thành công
        embed = discord.Embed(
            title="🎉 HOÀN THÀNH DAILY QUEST!",
            description=f"Chúc mừng {message.author.mention} đã nộp minh chứng thành công!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="💰 KiPoints Nhận Được", 
            value=f"**+{total_earned}** KiPoints" + (f" *(bao gồm +{bonus_points} thưởng streak)*" if bonus_points else ""), 
            inline=False
        )
        embed.add_field(name="🔥 Chuỗi Streak", value=f"**{get_streak_text(new_streak)}**", inline=True)
        embed.add_field(name="💳 Tổng KiPoints", value=f"**{format_points(user_info['points'])}** KiPoints", inline=True)

        await message.channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CheckCog(bot))
        
