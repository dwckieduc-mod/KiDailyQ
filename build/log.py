import discord
from discord.ext import commands
from datetime import datetime

# ==================== CẤU HÌNH ID ====================
MAIN_GUILD_ID = 123456789012345678  # Thay ID của Server chính (nơi chứa thành viên)
LOG_CHANNEL_ID = 987654321098765432 # Thay ID của Kênh Log (nằm ở server riêng)


class LogCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_display_name(self, user_id: int) -> str:
        """Lấy tên hiển thị của user tại Server chính (fallback về tên global hoặc ID nếu không tìm thấy)"""
        main_guild = self.bot.get_guild(MAIN_GUILD_ID)
        if main_guild:
            member = main_guild.get_member(user_id)
            if not member:
                try:
                    member = await main_guild.fetch_member(user_id)
                except Exception:
                    pass
            if member:
                return f"{member.display_name} ({member.name})"

        # Nếu không thấy trong server chính, fetch user toàn cục
        user = self.bot.get_user(user_id)
        if not user:
            try:
                user = await self.bot.fetch_user(user_id)
            except Exception:
                pass
        return user.display_name if user else f"User ID: {user_id}"

    async def _send_to_log(self, embed: discord.Embed):
        """Hàm phụ gửi Embed tới kênh Log ở server riêng"""
        try:
            channel = self.bot.get_channel(LOG_CHANNEL_ID)
            if not channel:
                channel = await self.bot.fetch_channel(LOG_CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
            else:
                print(f"[LOG ERROR] Không tìm thấy kênh log ID: {LOG_CHANNEL_ID}")
        except Exception as e:
            print(f"[LOG ERROR] Không thể gửi log: {e}")

    # ==================== HÀM GHI LOG: KHÓA / MỞ KÊNH ====================
    async def log_channel_state(self, channel: discord.TextChannel, actor: discord.User | discord.Member, is_locked: bool):
        """
        Ghi log Khóa hoặc Mở kênh (Embed Vàng)
        - is_locked: True nếu là Khóa, False nếu là Mở
        """
        actor_name = await self._get_display_name(actor.id)
        actor_type = "🤖 Bot" if actor.bot else "👤 Người dùng"
        
        action_text = "🔒 ĐÃ KHÓA KÊNH" if is_locked else "🔓 ĐÃ MỞ KÊNH"
        
        embed = discord.Embed(
            title=f"Lịch Sử Kênh: {action_text}",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="📌 Kênh", value=f"{channel.mention} (`{channel.name}`)", inline=False)
        embed.add_field(name="🛠 Thao tác bởi", value=f"{actor_name} [{actor_type}]", inline=True)
        embed.set_footer(text=f"Channel ID: {channel.id}")

        await self._send_to_log(embed)

    # ==================== HÀM GHI LOG: CỘNG ĐIỂM ====================
    async def log_add_points(self, target_id: int, points: int, actor: discord.User | discord.Member = None, reason: str = "Không có"):
        """
        Ghi log Cộng điểm (Embed Xanh)
        - actor: Người thực hiện cộng điểm (nếu là hệ thống tự động thì để None)
        """
        target_name = await self._get_display_name(target_id)
        
        if actor:
            actor_name = await self._get_display_name(actor.id)
            actor_str = f"{actor_name} {'[🤖 Bot]' if actor.bot else '[👤 Người]'}"
        else:
            actor_str = "⚙️ Hệ thống tự động"

        embed = discord.Embed(
            title="⚡ Lịch Sử Cộng Điểm",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="👤 Người nhận", value=target_name, inline=True)
        embed.add_field(name="➕ Điểm cộng", value=f"`+{points}` KiPoints", inline=True)
        embed.add_field(name="🛠 Người thực hiện", value=actor_str, inline=False)
        embed.add_field(name="📝 Lý do", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {target_id}")

        await self._send_to_log(embed)

    # ==================== HÀM GHI LOG: DENY (TỪ CHỐI) ====================
    async def log_deny(self, target_id: int, actor: discord.User | discord.Member, reason: str = "Không có lý do"):
        """
        Ghi log Từ chối / Deny (Embed Đỏ)
        """
        target_name = await self._get_display_name(target_id)
        actor_name = await self._get_display_name(actor.id)

        embed = discord.Embed(
            title="🚫 Lịch Sử Từ Chối (Deny)",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="👤 Đối tượng bị Deny", value=target_name, inline=True)
        embed.add_field(name="👑 Người thực hiện Deny", value=actor_name, inline=True)
        embed.add_field(name="📌 Lý do", value=reason, inline=False)
        embed.set_footer(text=f"Target ID: {target_id}")

        await self._send_to_log(embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LogCog(bot))
