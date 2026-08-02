import os
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from database import load_data, save_data, get_streak_text, format_points

# 👉 LẤY ID KÊNH ĐIỂM DANH TỪ ENVIRONMENT (Biến DAILY_CHANNEL_ID)
DAILY_CHANNEL_ID = int(os.environ.get("DAILY_CHANNEL_ID", 0))

class CheckinCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        # Bỏ qua tin nhắn của bot
        if message.author.bot:
            return

        # Kiểm tra xem tin nhắn có đính kèm hình ảnh không
        image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
        has_image = any(
            (att.content_type and att.content_type.startswith("image/")) or
            att.filename.lower().endswith(image_extensions)
            for att in message.attachments
        )

        if has_image:
            # Chỉ xử lý nếu gửi ảnh ĐÚNG trong kênh DAILY_CHANNEL_ID
            if message.channel.id != DAILY_CHANNEL_ID:
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
                    return
                elif last_date == today - timedelta(days=1):
                    user_info["streak"] += 1
                else:
                    user_info["streak"] = 1
            else:
                user_info["streak"] = 1

            base_points = 100
            bonus_points = 5 if user_info["streak"] >= 3 else 0
            is_bonus = user_info["streak"] >= 3

            total_gained = base_points + bonus_points
            user_info["points"] += total_gained
            user_info["last_date"] = str(today)
            user_info["total_quests"] = user_info.get("total_quests", 0) + 1
            
            data[user_id] = user_info
            save_data(data)

            embed = discord.Embed(
                title="✅ ĐIỂM DANH THÀNH CÔNG!",
                description=f"{message.author.mention} đã hoàn thành nhiệm vụ hôm nay!",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="💪 KiPoints Nhận Được", value=f"**+{total_gained}** KiPoints", inline=True)
            embed.add_field(name="💰 Tổng KiPoints Hiện Có", value=f"**{format_points(user_info['points'])}** KiPoints", inline=True)
            
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

async def setup(bot):
    await bot.add_cog(CheckinCog(bot))
    
