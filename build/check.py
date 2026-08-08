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

    # ==================== 1. LẮNG NGHE TIN NHẮN ĐIỂM DANH ====================
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

        # KIỂM TRA MINH CHỨNG (Có file đính kèm HOẶC chứa đường link bất kỳ)
        has_attachment = len(message.attachments) > 0
        has_link = bool(URL_REGEX.search(message.content))

        # Nếu tin nhắn KHÔNG có cả file đính kèm lẫn link -> Bỏ qua
        if not (has_attachment or has_link):
            return

        # XỬ LÝ DUY NHẤT 1 LẦN CHO MỖI TIN NHẮN
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
            await message.channel.send(embed=embed, delete_after=3)
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

        # Thả cảm xúc thông báo
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

        await message.channel.send(embed=embed, deleted_after=3)

    # ==================== 2. ADMIN THẢ EMOJI 🔄 ĐỂ DENY (TỪ CHỐI) ====================
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        # Bỏ qua nếu là bot tự thả emoji
        if payload.user_id == self.bot.user.id:
            return

        # Chỉ xử lý emoji 🔄
        if str(payload.emoji) != "🔄":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        # KIỂM TRA QUYỀN ADMIN: Chỉ Admin mới được dùng emoji này
        if not member.guild_permissions.administrator:
            return

        # Kiểm tra kênh có thuộc danh sách điểm danh không
        allowed_channels = await load_allowed_channels(self.bot)
        channel_id_str = str(payload.channel_id)
        if channel_id_str not in allowed_channels:
            return

        perm = allowed_channels[channel_id_str]
        has_image_perm = perm.get("image", False) if isinstance(perm, dict) else False
        if not has_image_perm:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(payload.channel_id)
            except Exception:
                return

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        if message.author.bot:
            return

        user_id = str(message.author.id)
        data = await load_data()
        user_info = data.get(user_id)

        if not user_info:
            return

        vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
        today_str = str(vietnam_now.date())

        # Nếu người dùng chưa điểm danh hôm nay hoặc đã bị deny rồi thì không xử lý thêm
        if user_info.get("last_date") != today_str:
            return

        # TIẾN HÀNH HOÀN TÁC (DENY)
        current_streak = user_info.get("streak", 0)
        bonus_points = 5 if current_streak >= 3 else 0
        deduct_points = 100 + bonus_points

        user_info["points"] = max(0, user_info.get("points", 0) - deduct_points)
        user_info["streak"] = max(0, current_streak - 1)
        user_info["total_quests"] = max(0, user_info.get("total_quests", 1) - 1)
        user_info["last_date"] = ""  # Xóa ngày điểm danh để thành viên có thể nộp lại bài mới

        data[user_id] = user_info
        await save_data(data)

        # Gỡ cảm xúc ✅ và 🔥 của Bot trên tin nhắn, thả cảm xúc ❌
        try:
            for reaction in message.reactions:
                if str(reaction.emoji) in ["✅", "🔥"]:
                    await reaction.remove(self.bot.user)
            await message.add_reaction("❌")
        except Exception:
            pass

        # Gửi thông báo từ chối
        embed = discord.Embed(
            title="🔄 NHIỆM VỤ BỊ TỪ CHỐI (DENY)",
            description=f"Bài điểm danh của {message.author.mention} đã bị Admin {member.mention} từ chối!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="📉 Hoàn tác điểm số",
            value=f"• Đã trừ: **-{deduct_points}** KiPoints\n• Chuỗi Streak còn lại: **{get_streak_text(user_info['streak'])}**\n• Tổng KiPoints còn lại: **{format_points(user_info['points'])}** KiPoints",
            inline=False
        )
        embed.add_field(
            name="💡 Hướng dẫn",
            value="Bạn có thể làm lại nhưng phải đúng nhiệm vụ hôm nay.",
            inline=False
        )

        await channel.send(embed=embed, delete_after=5)

async def setup(bot):
    await bot.add_cog(CheckCog(bot))
        
