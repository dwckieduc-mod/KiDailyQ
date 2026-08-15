import os
import io
import asyncio
import aiohttp
import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pilmoji import Pilmoji
from database import load_data, get_streak_text, format_points

FONT_BOLD_PATH = "font/montserrat_bold.ttf"
FONT_MEDIUM_PATH = "font/montserrat_medium.ttf"

# --- BỘ NHỚ TẠM (CACHE) ---
AVATAR_CACHE = {}
LOADED_FONTS = {}


async def init_fonts_and_download(session: aiohttp.ClientSession):
    """Tải và Nạp Font 1 LẦN DUY NHẤT vào RAM khi khởi động"""
    global LOADED_FONTS

    os.makedirs(os.path.dirname(FONT_BOLD_PATH), exist_ok=True)

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
    """Tải avatar, cắt tròn và Cache vào RAM"""
    if not url:
        return Image.new("RGBA", size, (100, 100, 100, 255))

    cache_key = (str(user_id), str(url), size)
    if cache_key in AVATAR_CACHE:
        return AVATAR_CACHE[cache_key]

    try:
        async with session.get(str(url)) as resp:
            if resp.status == 200:
                data = await resp.read()
                avatar = Image.open(io.BytesIO(data)).convert("RGBA")
                avatar = ImageOps.fit(avatar, size, method=Image.Resampling.LANCZOS)

                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0], size[1]), fill=255)

                output = Image.new("RGBA", size, (0, 0, 0, 0))
                output.paste(avatar, (0, 0), mask)

                if len(AVATAR_CACHE) > 300:
                    AVATAR_CACHE.clear()

                AVATAR_CACHE[cache_key] = output
                return output
    except Exception as e:
        print(f"[CẢNH BÁO] Lỗi tải avatar ({url}): {e}")

    return Image.new("RGBA", size, (120, 120, 120, 255))


# ==================== HÀM VẼ PROFILE ĐẦY ĐỦ THÔNG TIN ====================
def draw_profile_sync(target_name, user_info, rank_str, avatar_img):
    """Vẽ thẻ Profile tràn lề, không viền chữ và không viền Avatar"""
    global LOADED_FONTS

    width = 820
    height = 240
    card_color = (43, 45, 49, 255)
    text_white = (255, 255, 255, 255)
    text_sub = (200, 205, 215, 255)
    accent_gold = (255, 215, 0, 255)

    img = Image.new("RGBA", (width, height), card_color)

    # 1. Load & Ghép Banner phía trên
    banner_height = 130
    banner_size = (width, banner_height)
    banner_path = "banner.png" if os.path.exists("banner.png") else "font/banner.png"

    if os.path.exists(banner_path):
        try:
            raw_banner = Image.open(banner_path).convert("RGBA")
            banner_img = ImageOps.fit(raw_banner, banner_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        except Exception:
            banner_img = Image.new("RGBA", banner_size, (70, 90, 120, 255))
    else:
        banner_img = Image.new("RGBA", banner_size, (70, 90, 120, 255))

    # Mask bo góc trên cho Banner
    mask_banner = Image.new("L", banner_size, 0)
    draw_mb = ImageDraw.Draw(mask_banner)
    draw_mb.rounded_rectangle([0, 0, width, banner_height + 20], radius=16, fill=255)
    img.paste(banner_img, (0, 0), mask_banner)

    # 2. Avatar Hình Tròn (ĐÃ XOÁ HOÀN TOÀN VIỀN OUTER RING)
    avatar_size = 110
    avatar_x = 30
    avatar_y = 15

    avatar_img = ImageOps.fit(avatar_img, (avatar_size, avatar_size), method=Image.Resampling.LANCZOS)
    img.paste(avatar_img, (avatar_x, avatar_y), avatar_img)

    # Đảm bảo font sẵn sàng
    if not LOADED_FONTS.get("title") and os.path.exists(FONT_BOLD_PATH):
        try:
            LOADED_FONTS["title"] = ImageFont.truetype(FONT_BOLD_PATH, 26)
            LOADED_FONTS["bold"] = ImageFont.truetype(FONT_BOLD_PATH, 22)
            LOADED_FONTS["small"] = ImageFont.truetype(
                FONT_MEDIUM_PATH if os.path.exists(FONT_MEDIUM_PATH) else FONT_BOLD_PATH, 19
            )
        except Exception:
            pass

    font_title = LOADED_FONTS.get("title", ImageFont.load_default())
    font_bold = LOADED_FONTS.get("bold", ImageFont.load_default())
    font_small = LOADED_FONTS.get("small", ImageFont.load_default())

    points = user_info.get("points", 0)
    streak = user_info.get("streak", 0)
    total_quests = user_info.get("total_quests", 0)
    last_date = user_info.get("last_date") or "Chưa điểm danh"
    streak_icon = "🔥" if streak >= 3 else "🧊"

    text_x = 160  # Vị trí bên phải Avatar

    with Pilmoji(img) as pilmoji:
        # A. TÊN & THỨ HẠNG
        pilmoji.text((text_x, 30), target_name[:20], fill=text_white, font=font_title)
        pilmoji.text((text_x, 70), f"Thứ hạng: {rank_str}", fill=accent_gold, font=font_bold)

        # B. THÔNG SỐ ĐIỂM DANH (Hàng dưới)
        pilmoji.text((35, 150), f"⚡ KiPoints: {format_points(points)}", fill=text_white, font=font_bold)
        pilmoji.text((420, 150), f"{streak_icon} Chuỗi Streak: {streak} ngày", fill=text_white, font=font_bold)

        pilmoji.text((35, 195), f"🎯 Nhiệm vụ hoàn thành: {total_quests}", fill=text_sub, font=font_small)
        pilmoji.text((420, 195), f"📅 Lần cuối: {last_date}", fill=text_sub, font=font_small)

    # Bo tròn góc toàn bộ ảnh thẻ Profile
    mask_card = Image.new("L", (width, height), 0)
    draw_mc = ImageDraw.Draw(mask_card)
    draw_mc.rounded_rectangle([0, 0, width, height], radius=16, fill=255)

    final_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    final_img.paste(img, (0, 0), mask_card)

    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG", compress_level=1)
    buffer.seek(0)
    return buffer


# ==================== HÀM VẼ BẢNG XẾP HẠNG ====================
def draw_leaderboard_sync(page_data, page_avatars, author_id, author_rank_idx, author_info, author_avatar, guild_member_names, current_page, total_pages):
    card_height = 76
    card_gap = 10
    top_margin = 150
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

    font_title = LOADED_FONTS.get("title", ImageFont.load_default())
    font_bold = LOADED_FONTS.get("bold", ImageFont.load_default())
    font_small = LOADED_FONTS.get("small", ImageFont.load_default())

    with Pilmoji(img) as pilmoji:
        pilmoji.text((25, 12), "📌 HẠNG HIỆN TẠI CỦA BẠN", fill=accent_gold, font=font_title)
        draw.rounded_rectangle([20, 50, width - 20, 130], radius=12, fill=card_color)
        img.paste(author_avatar, (35, 63), author_avatar)

        author_name = guild_member_names.get(str(author_id), f"User {author_id}")
        rank_str = f"#{author_rank_idx}" if author_rank_idx else "Chưa xếp hạng"
        a_points = author_info.get("points", 0) if author_info else 0
        a_streak = author_info.get("streak", 0) if author_info else 0
        author_streak_icon = "🔥" if a_streak >= 3 else "🧊"

        pilmoji.text((105, 60), f"{rank_str}  •  {author_name[:22]}", fill=text_white, font=font_bold)
        pilmoji.text((105, 92), f"⚡ {format_points(a_points)} KiPoints   |   {author_streak_icon} Chuỗi: {a_streak} ngày", fill=text_sub, font=font_small)

        y_pos = top_margin
        start_rank = (current_page - 1) * 10 + 1

        for index, ((user_id, info), avatar_img) in enumerate(zip(page_data, page_avatars), start=start_rank):
            points = info.get("points", 0)
            streak = info.get("streak", 0)
            user_display = guild_member_names.get(str(user_id), f"User {user_id}")

            rank_color = accent_gold if index == 1 else (accent_silver if index == 2 else (accent_bronze if index == 3 else text_white))
            streak_icon = "🔥" if streak >= 3 else "🧊"

            draw.rounded_rectangle([20, y_pos, width - 20, y_pos + card_height], radius=12, fill=card_color)

            pilmoji.text((35, y_pos + 24), f"#{index}", fill=rank_color, font=font_bold)
            img.paste(avatar_img, (100, y_pos + 11), avatar_img)
            pilmoji.text((170, y_pos + 24), user_display[:16], fill=text_white, font=font_bold)

            streak_str = f"{streak_icon} {streak} ngày"
            pilmoji.text((width - 150, y_pos + 25), streak_str, fill=text_sub, font=font_small)

            points_str = f"{format_points(points)} KiPoints"
            try:
                bbox = font_bold.getbbox(points_str)
                text_width = bbox[2] - bbox[0]
            except Exception:
                text_width = 120

            points_x = (width - 170) - text_width

            pilmoji.text((points_x, y_pos + 24), points_str, fill=accent_gold, font=font_bold)

            y_pos += card_height + card_gap

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", compress_level=1)
    buffer.seek(0)
    return buffer


class LeaderboardView(discord.ui.View):
    def __init__(self, data, author_id, guild, per_page=10):
        super().__init__(timeout=60)
        self.data = data
        self.author_id = author_id
        self.guild = guild
        self.per_page = per_page
        self.current_page = 1
        self.total_pages = max(1, (len(data) + per_page - 1) // per_page)
        self.message = None
        self.page_cache = {}
        self.update_buttons()

    def update_buttons(self):
        self.children[0].disabled = (self.current_page == 1)
        self.children[1].disabled = (self.current_page == self.total_pages)

    async def get_page_file_and_embed(self):
        if self.current_page in self.page_cache:
            raw_bytes = self.page_cache[self.current_page]
            file = discord.File(fp=io.BytesIO(raw_bytes), filename="leaderboard.png")
            embed = discord.Embed(color=discord.Color.gold())
            embed.set_image(url="attachment://leaderboard.png")
            embed.set_footer(text=f"Trang {self.current_page}/{self.total_pages} • Tổng: {len(self.data)} thành viên")
            return file, embed

        author_rank_idx = None
        author_info = None
        for idx, (uid, info) in enumerate(self.data, start=1):
            if str(uid) == str(self.author_id):
                author_rank_idx = idx
                author_info = info
                break

        start_idx = (self.current_page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_data = self.data[start_idx:end_idx]

        async with aiohttp.ClientSession() as session:
            author_member = self.guild.get_member(int(self.author_id)) if self.guild and str(self.author_id).isdigit() else None
            author_url = author_member.display_avatar.url if author_member else None
            author_avatar_task = fetch_circle_avatar(session, self.author_id, author_url, size=(54, 54))

            tasks = []
            guild_member_names = {}

            if author_member:
                guild_member_names[str(self.author_id)] = author_member.display_name

            for uid, _ in page_data:
                m = self.guild.get_member(int(uid)) if self.guild and str(uid).isdigit() else None
                url = m.display_avatar.url if m else None
                if m:
                    guild_member_names[str(uid)] = m.display_name
                tasks.append(fetch_circle_avatar(session, uid, url, size=(54, 54)))

            author_avatar = await author_avatar_task
            page_avatars = await asyncio.gather(*tasks)

        buffer = await asyncio.to_thread(
            draw_leaderboard_sync,
            page_data=page_data,
            page_avatars=page_avatars,
            author_id=self.author_id,
            author_rank_idx=author_rank_idx,
            author_info=author_info,
            author_avatar=author_avatar,
            guild_member_names=guild_member_names,
            current_page=self.current_page,
            total_pages=self.total_pages,
        )

        raw_bytes = buffer.getvalue()
        self.page_cache[self.current_page] = raw_bytes

        file = discord.File(fp=io.BytesIO(raw_bytes), filename="leaderboard.png")
        embed = discord.Embed(color=discord.Color.gold())
        embed.set_image(url="attachment://leaderboard.png")
        embed.set_footer(text=f"Trang {self.current_page}/{self.total_pages} • Tổng: {len(self.data)} thành viên")
        return file, embed

    @discord.ui.button(label="◀ Trang trước", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Chỉ người dùng lệnh mới có thể chuyển trang!", ephemeral=True)

        self.current_page -= 1
        self.update_buttons()
        file, embed = await self.get_page_file_and_embed()
        await interaction.response.edit_message(attachments=[file], embed=embed, view=self)

    @discord.ui.button(label="Trang sau ▶", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("❌ Chỉ người dùng lệnh mới có thể chuyển trang!", ephemeral=True)

        self.current_page += 1
        self.update_buttons()
        file, embed = await self.get_page_file_and_embed()
        await interaction.response.edit_message(attachments=[file], embed=embed, view=self)

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

    async def cog_load(self):
        async with aiohttp.ClientSession() as session:
            await init_fonts_and_download(session)

    # ==================== LỆNH PROFILE ====================
    @commands.command(name="profile", aliases=["pf"])
    async def point(self, ctx, member: discord.Member = None):
        try:
            target = member or ctx.author
            user_id = str(target.id)

            data = await load_data()
            user_info = data.get(user_id, {"points": 0, "last_date": "", "streak": 0, "total_quests": 0})

            # Format chuỗi Thứ hạng (#35 / 110)
            rank_str = "Chưa xếp hạng"
            if data:
                sorted_users = sorted(data.items(), key=lambda item: item[1].get("points", 0), reverse=True)
                for idx, (uid, info) in enumerate(sorted_users, start=1):
                    if uid == user_id:
                        if idx == 1:
                            rank_str = f"🥇 Top 1"
                        elif idx == 2:
                            rank_str = f"🥈 Top 2"
                        elif idx == 3:
                            rank_str = f"🥉 Top 3"
                        else:
                            rank_str = f"#{idx}"
                        break

            async with aiohttp.ClientSession() as session:
                avatar_img = await fetch_circle_avatar(session, target.id, target.display_avatar.url, size=(110, 110))

            buffer = await asyncio.to_thread(
                draw_profile_sync,
                target_name=target.display_name,
                user_info=user_info,
                rank_str=rank_str,
                avatar_img=avatar_img
            )

            file = discord.File(fp=buffer, filename="profile.png")
            await ctx.send(file=file)
        except Exception as e:
            await ctx.send(f"❌ Xảy ra lỗi khi thực thi lệnh `profile`: `{e}`")

    # ==================== LỆNH TOP ====================
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

            view = LeaderboardView(sorted_users, ctx.author.id, ctx.guild, per_page=per_page)
            view.current_page = page
            view.update_buttons()

            file, embed = await view.get_page_file_and_embed()
            message = await ctx.send(file=file, embed=embed, view=view)
            view.message = message
        except Exception as e:
            await ctx.send(f"❌ Xảy ra lỗi khi thực thi lệnh `top`: `{e}`")


async def setup(bot):
    await bot.add_cog(RankCog(bot))
    
