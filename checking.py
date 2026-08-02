import os
import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from database import load_data, save_data

# 👉 CỐ ĐỊNH KÊNH ĐIỂM DANH QUA BIẾN MÔI TRƯỜNG DAILY_CHANNEL_ID
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
            # 🔒 CHỈ XỬ LÝ KHI GỬI ĐÚNG VÀO KÊNH DAILY_CHANNEL_ID
            if message.channel.id != DAILY_CHANNEL_ID:
                return

            user_id = str(message.author.id)
            vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
            today = vietnam_now.date()
            
            data = load_data()
            user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})
            
            last_date_str = user_info.get("last_date", "")
            
            # ❌ TRƯỜNG HỢP 1: ĐÃ ĐIỂM DANH HÔM NAY RỒI
            if last_date_str:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                if last_date == today:
                    try:
                        await message.add_reaction("❌")
                    except discord.HTTPException:
                        pass
                    return
                elif last_date == today - timedelta(days=1):
                    user_info["streak"] += 1
                else:
                    user_info["streak"] = 1
            else:
                user_info["streak"] = 1

            # ⚙️ TÍNH ĐIỂM KIPOINTS
            base_points = 100
            is_streak_active = user_info["streak"] >= 3  # Kích hoạt streak bonus (từ ngày thứ 3)
            bonus_points = 5 if is_streak_active else 0

            total_gained = base_points + bonus_points
            user_info["points"] += total_gained
            user_info["last_date"] = str(today)
            user_info["total_quests"] = user_info.get("total_quests", 0) + 1
            
            # 💾 LƯU DỮ LIỆU
            data[user_id] = user_info
            save_data(data)

            # ✅ TRƯỜNG HỢP 2: ĐIỂM DANH THÀNH CÔNG
            try:
                await message.add_reaction("✅")
                
                # 🔥 TRƯỜNG HỢP 3: KÍCH HOẠT THƯỞNG STREAK (TỪ NGÀY 3 TRỞ ĐI)
                if is_streak_active:
                    await message.add_reaction("🔥")
            except discord.HTTPException as e:
                print(f"❌ Lỗi khi bot thả emoji: {e}")

async def setup(bot):
    await bot.add_cog(CheckinCog(bot))
    
