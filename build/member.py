import discord
from discord.ext import commands
from database import load_allowed_channels

class MemberCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="avatar", aliases=["av"])
    async def avatar_command(self, ctx, member: discord.Member = None):
        try:
            target = member or ctx.author
            avatar_url = target.display_avatar.with_size(4096).url

            embed = discord.Embed(
                title=f"🖼️ AVATAR CỦA {target.display_name.upper()}",
                description=f"🔗 [Nhấn vào đây để tải ảnh gốc HD]({avatar_url})",
                color=discord.Color.blue()
            )
            embed.set_image(url=avatar_url)
            embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Xảy ra lỗi khi thực thi lệnh `avatar`: `{e}`")

    @commands.command(name="rule", aliases=["r"])
    async def rule_command(self, ctx):
        try:
            allowed_data = await load_allowed_channels(self.bot)
            image_channels = []
            command_channels = []

            if allowed_data:
                for cid, perms in allowed_data.items():
                    if isinstance(perms, dict):
                        if perms.get("image"):
                            image_channels.append(f"<#{cid}>")
                        if perms.get("command"):
                            command_channels.append(f"<#{cid}>")
                    elif isinstance(perms, bool) and perms:
                        command_channels.append(f"<#{cid}>")

            image_channels_str = ", ".join(image_channels) if image_channels else "*kênh chưa được thiết lập*"
            command_channels_str = ", ".join(command_channels) if command_channels else "*kênh chưa được thiết lập*"

            embed = discord.Embed(
                title="📜 QUY ĐỊNH & NỘI QUY ĐIỂM DANH",
                description="",
                color=discord.Color.gold()
            )

            embed.add_field(
                name="📖 . Hình thức làm Daily Quest:",
                value=(
                    "- Mỗi ngày **Ki Ki** sẽ đưa ra một nhiệm vụ.\n"
                    f"- Mọi người sẽ làm nhiệm vụ và gửi vào {image_channels_str} để điểm danh.\n"
                ),
                inline=False
            )

            embed.add_field(
                name="📊 . Cách tính điểm:",
                value=(
                    "- Khi bạn gửi nội dung vào, bot sẽ thông báo và thả biểu cảm với các emoji sau:\n"
                    "- - ✅ Hoàn thành.\n"
                    "- - ❌ Đã làm nhiệm vụ trước đó.\n"
                    "- - 🔥 Bạn đã đạt điều kiện thưởng streak.\n"
                    "- Hoàn thành nhiệm vụ sẽ được cộng **100 KiPoints**.\n"
                    "- Khi đạt điều kiện streak **( ≥ 3 ngày)** thì bạn sẽ được cộng thêm **5 KiPoints** thưởng giữ chuỗi.\n"
                    "- Khi qua ngày mới bot sẽ khoá kênh lại kết thúc nhiệm vụ hôm đó.\n"
                ),
                inline=False
            )

            embed.add_field(
                name="🚫 . Về hành vi sai phạm:",
                value=(
                    "- Làm sai nhiệm vụ / nội dung không phù hợp sẽ bị từ chối và yêu cầu làm lại.\n"
                    "- Các nội dung phải theo luật của server. Những trường hợp sai phạm sẽ được xử lý.\n"
                ),
                inline=False
            )

            embed.add_field(
                name="📃 . Về lệnh của bot:",
                value=(
                    "- Bot dùng cú pháp `k.<lệnh>` / `K.<lệnh>`\n"
                    f"- Kênh được phép dùng lệnh: <#1427911211424678019>\n"
                    "- Để biết về tên lệnh, hãy nhập lệnh `help` để xem danh sách các lệnh.\n"
                ),
                inline=False
            )

            embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Xảy ra lỗi khi thực thi lệnh `rule`: `{e}`")

    @commands.command(name="help", aliases=["h"])
    async def help_command(self, ctx, *, group: str = None):
        try:
            if not group:
                embed = discord.Embed(
                    title="📜 HƯỚNG DẪN SỬ DỤNG LỆNH (HELP)",
                    description="Sử dụng cú pháp `k.help <nhóm lệnh>` để xem chi tiết danh sách lệnh.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="📂 Các nhóm lệnh khả dụng:",
                    value=(
                        "- `k.help member`: Nhóm lệnh dành cho tất cả thành viên.\n"
                        "- `k.help admin`: Nhóm lệnh quản trị điểm số & streak (Chỉ Admin).\n"
                        "- `k.help set up`: Nhóm lệnh cài đặt phân quyền & kênh (Chỉ Admin)."
                    ),
                    inline=False
                )
                embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)
                return

            group_clean = group.lower().strip()

            if group_clean in ["member", "mem"]:
                embed = discord.Embed(
                    title="👤 NHÓM LỆNH THÀNH VIÊN (MEMBER)",
                    description="Các lệnh sử dụng cho tất cả thành viên trong máy chủ:",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📌 Danh sách lệnh:",
                    value=(
                        "- `help`: Xem hướng dẫn sử dụng lệnh.\n"
                        "- `rule`: Xem quy định & cách tính điểm.\n"
                        "- `profile @User`: Xem hồ sơ nhiệm vụ cá nhân.\n"
                        "- `top <số trang>`: Xem bảng xếp hạng KiPoints.\n"
                        "- `avatar @User`: Xem ảnh đại diện (avatar) chất lượng HD (4096px)."
                    ),
                    inline=False
                )
                embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)

            elif group_clean in ["admin", "ad"]:
                embed = discord.Embed(
                    title="⚙️ NHÓM LỆNH QUẢN TRỊ (ADMIN)",
                    description="",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="📌 Danh sách lệnh:",
                    value=(
                        "- `add @User <số KiPoints>`: Cộng KiPoints cho thành viên.\n"
                        "- `remove @User <số KiPoints>`: Trừ KiPoints của thành viên.\n"
                        "- `addstreak @User <số ngày>`: Cộng chuỗi streak.\n"
                        "- `removestreak @User <số ngày>`: Trừ chuỗi streak.\n"
                        "- `deny @User`: Hủy kết quả điểm danh hôm nay.\n"
                        "- `reset @User/all`: Đặt lại toàn bộ dữ liệu của 1 người hoặc tất cả."
                    ),
                    inline=False
                )
                embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)

            elif group_clean in ["set up", "setup", "set_up"]:
                embed = discord.Embed(
                    title="🛠️ NHÓM LỆNH CÀI ĐẶT (SET UP)",
                    description="",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="📌 Danh sách lệnh:",
                    value=(
                        "- `allow <#kênh/ID> <image/command> <true/false>`: Quản lý quyền gửi ảnh/dùng lệnh theo kênh.\n"
                        "- `allowlist`: Xem danh sách phân quyền các kênh hiện tại.\n"
                        "- `lock`: Khóa kênh làm nhiệm vụ.\n"
                        "- `unlock`: Mở khóa kênh làm nhiệm vụ."
                    ),
                    inline=False
                )
                embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                await ctx.send(embed=embed)

            else:
                embed = discord.Embed(
                    title="⚠️ NHÓM LỆNH KHÔNG HỢP LỆ",
                    description="Vui lòng chọn 1 trong các nhóm lệnh sau:\n• `k.help member`\n• `k.help admin`\n• `k.help set up`",
                    color=discord.Color.gold()
                )
                await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ Xảy ra lỗi khi thực thi lệnh `help`: `{e}`")


async def setup(bot):
    await bot.add_cog(MemberCog(bot))
                
