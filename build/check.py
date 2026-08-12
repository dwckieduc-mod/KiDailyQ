import re
import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta, timezone
from database import load_data, save_data, load_allowed_channels, get_streak_text, format_points

# Múi giờ Việt Nam (UTC+7)
VN_TZ = timezone(timedelta(hours=7))

# Biểu thức chính quy nhận diện link
URL_REGEX = re.compile(r'https?://[^\s]+', re.IGNORECASE)

class CheckCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Khởi động vòng lặp kiểm tra 00:00 hàng ngày
        self.daily_checkin_reset.start()

    def cog_unload(self):
        self.daily_checkin_reset.cancel()

    # ==================== VÒNG LẶP CHECK STREAK & RESET LÚC 00:00 ====================
    @tasks.loop(time=time(hour=0, minute=0, second=0, tzinfo=VN_TZ))
    async def daily_checkin_reset(self):
        data = await load_data()
        if not data:
            return

        for user_id, user_info in data.items():
            # Nếu giá trị checkin_today == 0 (chưa điểm danh hoặc bị deny) -> reset streak = 0
            if user_info.get("checkin_today", 0) == 0:
                user_info["streak"] = 0
            
            # Đưa giá trị checkin_today về 0 ban đầu cho ngày mới
            user_info["checkin_today"] = 0

        await save_data(data)

    @daily_checkin_reset.before_loop
    async def before_daily_reset(self):
        await self.bot.wait_until_ready()

    # ==================== 1. LẮNG NGHE TIN NHẮN ĐIỂM DANH ====================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        allowed_channels = await load_allowed_channels(self.bot)
        channel_id = str(message.channel.id)

        if channel_id not in allowed_channels:
            return

        perm = allowed_channels[channel_id]
        has_image_perm = perm.get("image", False) if isinstance(perm, dict) else False

        if not has_image_perm:
            return

        has_attachment = len(message.attachments) > 0
        has_link = bool(URL_REGEX.search(message.content))

        if not (has_attachment or has_link):
            return

        user_id = str(message.author.id)
        data = await load_data()
        user_info = data.get(user_id, {
            "points": 0, 
            "last_date": "", 
            "streak": 0, 
            "total_quests": 0,
            "checkin_today": 0
        })

        vietnam_now = datetime.now(timezone.utc) + timedelta(hours=7)
        today_str = str(vietnam_now.date())
        yesterday_str = str((vietnam_now - timedelta(days=1)).date())

        if user_info.get("last_date") == today_str:
            await message.add_reaction("❌")
            embed = discord.Embed(
                title="❌ ĐÃ HOÀN THÀNH NHIỆM VỤ",
                description=f"{message.author.mention} Bạn đã làm nhiệm vụ và nhận điểm ngày hôm nay rồi!",
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed, delete_after=3)
            return

        current_streak = user_info.get("streak", 0)
        last_date = user_info.get("last_date")

        if last_date == yesterday_str:
            new_streak = current_streak + 1
        else:
            new_streak = 1

        base_points = 100
        bonus_points = 5 if new_streak >= 3 else 0
        total_earned = base_points + bonus_points

        # Lưu dữ liệu mới & gán lượt điểm danh = 1
        user_info["points"] += total_earned
        user_info["streak"] = new_streak
        user_info["last_date"] = today_str
        user_info["total_quests"] = user_info.get("total_quests", 0) + 1
        user_info["checkin_today"] = 1  # Gán lượt điểm danh hôm nay = 1

        data[user_id] = user_info
        await save_data(data)

        await message.add_reaction("✅")
        if bonus_points > 0:
            await message.add_reaction("🔥")
        await message.add_reaction("🔄")

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

        await message.channel.send(embed=embed, delete_after=3)

    # ==================== 2. ADMIN THẢ EMOJI 🔄 ĐỂ DENY (TỪ CHỐI) ====================
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id or str(payload.emoji) != "🔄":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if not member or member.bot or not member.guild_permissions.administrator:
            return

        allowed_channels = await load_allowed_channels(self.bot)
        channel_id_str = str(payload.channel_id)
        if channel_id_str not in allowed_channels:
            return

        perm = allowed_channels[channel_id_str]
        has_image_perm = perm.get("image", False) if isinstance(perm, dict) else False
        if not has_image_perm:
            return

        channel = self.bot.get_channel(payload.channel_id) or await self.bot.fetch_channel(payload.channel_id)
        if not channel:
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

        if user_info.get("last_date") != today_str:
            return

        current_streak = user_info.get("streak", 0)
        bonus_points = 5 if current_streak >= 3 else 0
        deduct_points = 100 + bonus_points

        user_info["points"] = max(0, user_info.get("points", 0) - deduct_points)
        user_info["streak"] = max(0, current_streak - 1)
        user_info["total_quests"] = max(0, user_info.get("total_quests", 1) - 1)
        user_info["last_date"] = ""
        
        # Khi bị Deny -> trừ 1 lượt điểm danh (Tối thiểu là 0)
        user_info["checkin_today"] = max(0, user_info.get("checkin_today", 0) - 1)

        data[user_id] = user_info
        await save_data(data)

        try:
            await message.clear_reactions()
        except Exception:
            for reaction in message.reactions:
                try:
                    await reaction.remove(self.bot.user)
                except Exception:
                    pass

        try:
            await message.add_reaction("❌")
        except Exception:
            pass

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
        embed.add_field(name="💡 Hướng dẫn", value="Bạn có thể làm lại nhưng phải đúng nhiệm vụ hôm nay.", inline=False)

        await channel.send(embed=embed, delete_after=5)

async def setup(bot):
    await bot.add_cog(CheckCog(bot))
