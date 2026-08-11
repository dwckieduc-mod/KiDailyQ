import os
import io
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from PIL import Image, ImageDraw, ImageFont
from database import load_data, get_streak_text, format_points

# Cấu hình ID kênh lưu trữ ảnh ngầm (Thay ID mặc định nếu không dùng os.environ)
STORAGE_CHANNEL_ID = int(os.environ.get("STORAGE_CHANNEL_ID", "123456789012345678"))

FONT_BOLD_PATH = "montserrat_bold.ttf"
FONT_MEDIUM_PATH = "montserrat_medium.ttf"

LOADED_FONTS = {}
DEFAULT_AVATAR = Image.new("RGBA", (54, 54), (100, 100, 100, 255))


async def init_fonts_and_download(session: aiohttp.ClientSession):
    global LOADED_FONTS
    urls = {
        FONT_BOLD_PATH: "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/static/Montserrat-Bold.ttf",
        FONT_MEDIUM_PATH: "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/static/Montserrat-Medium.ttf"
    }

    for path, url in urls.items():
        if not os.path.exists(path) or os.path.getsize(path) < 1000:
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        with open(path, "wb") as f:
                            f.write(data)
            except Exception as e:
                print(f"[CẢNH BÁO] Không thể tải font {path}: {e}")

    try:
        if os.path.exists(FONT_BOLD_PATH) and os.path.getsize(FONT_BOLD_PATH) > 1000:
            LOADED_FONTS["title"] = ImageFont.truetype(FONT_BOLD_PATH, 26)
            LOADED_FONTS["bold"] = ImageFont.truetype(FONT_BOLD_PATH, 22)
            LOADED_FONTS["small"] = ImageFont.truetype(
                FONT_MEDIUM_PATH if os.path.exists(FONT_MEDIUM_PATH) else FONT_BOLD_PATH, 19
            )
            return
    except Exception as e:
        print(f"[CẢNH BÁO] Lỗi load font ttf: {e}")

    default_font = ImageFont.load_default()
    LOADED_FONTS["title"] = default_font
    LOADED_FONTS["bold"] = default_font
    LOADED_FONTS["small"] = default_font


async def fetch_circle_avatar(session, user_id, url, size=(54, 54)):
    if not url:
        return DEFAULT_AVATAR

    try:
        async with session.get(str(url), timeout=aiohttp.ClientTimeout(total=1.2)) as resp:
            if resp.status == 200:
                data = await resp.read()
                avatar = Image.open(io.BytesIO(data)).convert("RGBA")
                avatar = avatar.resize(size, Image.Resampling.LANCZOS)

                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0], size[1]), fill=255)

                output = Image.new("RGBA", size, (0, 0, 0, 0))
                output.paste(avatar, (0, 0), mask)
                return output
    except Exception:
        pass

    return DEFAULT_AVATAR


def draw_generic_page_sync(page_data, page_avatars, guild_member_names, current_page, total_pages):
    """Vẽ giao diện trang bảng xếp hạng chung"""
    card_height = 76
    card_gap = 10
    top_margin = 80
    bottom_margin = 25
    width = 950
    height = top_margin + len(page_data) * (card_height + card_gap) + bottom_margin

    bg_color = (30, 31, 34, 255)
    card_color = (43, 45, 49, 255)
    text_white = (255, 255, 255, 255)
    text_sub = (200, 205, 215, 255)
    accent_gold = (255, 215, 0, 255)
    accent_silver = (215, 220, 225, 255)
    accent_bronze = (230, 126, 34, 255)

    img = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    font_title = LOADED_FONTS.get("title")
    font_bold = LOADED_FONTS.get("bold")
    font_small = LOADED_FONTS.get("small")

    # Tiêu đề chung
    draw.text((25, 20), f"BANG XEP HANG KIPOINTS - TRANG {current_page}/{total_pages}", fill=accent_gold, font=font_title)

    y_pos = top_margin
    start_rank = (current_page - 1) * 10 + 1

    for index, ((user_id, info), avatar_img) in enumerate(zip(page_data, page_avatars), start=start_rank):
        points = info.get("points", 0)
        streak = info.get("streak", 0)
        user_display = guild_member_names.get(str(user_id), f"User {user_id}")

        if index == 1:
            rank_color = accent_gold
        elif index == 2:
            rank_color = accent_silver
        elif index == 3:
            rank_color = accent_bronze
        else:
            rank_color = text_white

        draw.rounded_rectangle([20, y_pos, width - 20, y_pos + card_height], radius=12, fill=card_color)

        draw.text((35, y_pos + 24), f"#{index}", fill=rank_color, font=font_bold)
        img.paste(avatar_img, (100, y_pos + 11), avatar_img)
        draw.text((170, y_pos + 24), user_display[:18], fill=text_white, font=font_bold)

        streak_str = f"Chuoi: {streak} ngay"
        draw.text((width - 170, y_pos + 25), streak_str, fill=text_sub, font=font_small)

        points_str = f"{format_points(points)} KiPoints"
        bbox = font_bold.getbbox(points_str)
        text_width = bbox[2] - bbox[0]
        points_x = (width - 190) - text_width

        draw.text((points_x, y_pos + 24), points_str, fill=accent_gold, font=font_bold)

        y_pos += card_height + card_gap

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", compress_level=1)
    buffer.seek(0)
    return buffer


class FastLeaderboardView(discord.ui.View):
    def __init__(self, data, author_id, page_urls, per_page=10):
        super().__init__(timeout=60)
        self.data = data
        self.author_id = author_id
        self.page_urls = page_urls
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = max(1, (len(data) + per_page - 1) // per_page)
        self.message = None
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = (self.current_page == 1)
        self.children[1].disabled = (self.current_page == self.total_pages)

    def build_embed(self, guild: discord.Guild) -> discord.Embed:
        author_rank_str = "Chưa xếp hạng"
        author_info_str = ""
        for idx, (uid, info) in enumerate(self.data, start=1):
            if str(uid) == str(self.author_id):
                a_points = info.get("points", 0)
                a_streak = info.get("streak", 0)
                a_icon = "🔥" if a_streak >= 3 else "🧊"
                author_rank_str = f"**#{idx}**"
                author_info_str = f"⚡ **{format_points(a_points)}** KiPoints | {a_icon} Chuỗi: **{a_streak}** ngày"
                break

        author_member = guild.get_member(int(self.author_id)) if guild else None
        author_name = author_member.display_name if author_member else f"User {self.author_id}"

        embed = discord.Embed(color=discord.Color.gold())
        embed.add_field(
            name="📌 Hạng Hiện Tại Của Bạn",
            value=f"{author_rank_str} • **{author_name}**\n└ {author_info_str}",
            inline=False
        )

        image_url = self.page_urls.get(self.current_page)
        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(text=f"Trang {self.current_page}/{self.total_pages} • Tổng: {len(self.data)} thành viên")
        return embed

    @discord.ui.button(label="◀ Trang trước", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Chỉ người dùng lệnh mới có thể chuyển trang!", ephemeral=True)

        self.current_page -= 1
        self.update_buttons()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Trang sau ▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Chỉ người dùng lệnh mới có thể chuyển trang!", ephemeral=True)

        self.current_page += 1
        self.update_buttons()
        embed = self.build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class RankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        self.page_urls = {}  # Lưu trữ URL ảnh pre-render {page_num: url}

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        await init_fonts_and_download(self.session)
        self.preload_leaderboard_loop.start()

    async def cog_unload(self):
        self.preload_leaderboard_loop.cancel()
        if self.session:
            await self.session.close()

    @tasks.loop(minutes=10)
    async def preload_leaderboard_loop(self):
        """Vòng lặp chạy ngầm rendering ảnh và đăng lên Kênh Lưu Trữ"""
        try:
            await self.bot.wait_until_ready()
            data = await load_data()
            if not data:
                return

            storage_channel = self.bot.get_channel(STORAGE_CHANNEL_ID)
            if not storage_channel:
                print(f"[CẢNH BÁO] Không tìm thấy Kênh Lưu Trữ ID: {STORAGE_CHANNEL_ID}")
                return

            sorted_users = sorted(data.items(), key=lambda item: item[1].get("points", 0), reverse=True)
            per_page = 10
            total_pages = max(1, (len(sorted_users) + per_page - 1) // per_page)

            # Chỉ render tối đa 5 trang đầu tiên để tiết kiệm tài nguyên
            max_preload_pages = min(total_pages, 5)

            for page in range(1, max_preload_pages + 1):
                start_idx = (page - 1) * per_page
                end_idx = start_idx + per_page
                page_data = sorted_users[start_idx:end_idx]

                guild_member_names = {}
                tasks_list = []

                for uid, _ in page_data:
                    m = storage_channel.guild.get_member(int(uid)) if str(uid).isdigit() else None
                    url = m.display_avatar.url if m else None
                    if m:
                        guild_member_names[str(uid)] = m.display_name
                    tasks_list.append(fetch_circle_avatar(self.session, uid, url, size=(54, 54)))

                page_avatars = await asyncio.gather(*tasks_list)

                buffer = await asyncio.to_thread(
                    draw_generic_page_sync,
                    page_data=page_data,
                    page_avatars=page_avatars,
                    guild_member_names=guild_member_names,
                    current_page=page,
                    total_pages=total_pages
                )

                file = discord.File(fp=buffer, filename=f"lb_p{page}.png")
                msg = await storage_channel.send(file=file)
                if msg.attachments:
                    self.page_urls[page] = msg.attachments[0].url
                await asyncio.sleep(1)  # Tránh dính Rate limit Discord API

        except Exception as e:
            print(f"[LỖI PRELOAD LEADERBOARD]: {e}")

    @commands.command(name="top", aliases=["t"])
    async def top(self, ctx, page: int = 1):
        try:
            data = await load_data()
            if not data:
                await ctx.send("📋 Chưa có dữ liệu điểm danh nào trong hệ thống!")
                return

            sorted_users = sorted(data.items(), key=lambda item: item[1].get("points", 0), reverse=True)
            per_page = 10
            total_pages = max(1, (len(sorted_users) + per_page - 1) // per_page)

            if page < 1 or page > total_pages:
                await ctx.send(f"⚠️ Trang không hợp lệ! Vui lòng chọn trang từ **1** đến **{total_pages}**.")
                return

            view = FastLeaderboardView(sorted_users, ctx.author.id, self.page_urls, per_page=per_page)
            view.current_page = page
            view.update_buttons()

            embed = view.build_embed(ctx.guild)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
        except Exception as e:
            await ctx.send(f"❌ Xảy ra lỗi khi thực thi lệnh `top`: `{e}`")

    @commands.command(name="profile", aliases=["pf"])
    async def point(self, ctx, member: discord.Member = None):
        try:
            target = member or ctx.author
            user_id = str(target.id)

            data = await load_data()
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
            embed.add_field(name="💪 Điểm Sức Mạnh", value=f"**{format_points(points)}** KiPoints", inline=True)
            embed.add_field(name="🔥 Chuỗi Streak", value=f"**{get_streak_text(streak)}**", inline=True)
            embed.add_field(name="🎯 Daily Quest Đã Làm", value=f"**{total_quests}** nhiệm vụ", inline=True)
            embed.add_field(name="📅 Lần Cuối Điểm Danh", value=f"`{last_date}`", inline=True)

            embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Xảy ra lỗi khi thực thi lệnh `profile`: `{e}`")


async def setup(bot):
    await bot.add_cog(RankCog(bot))
        
