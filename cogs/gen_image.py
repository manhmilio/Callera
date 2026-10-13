"""
GenImageCog — lệnh `/gen_img` sinh ảnh từ prompt người dùng tự nhập, dùng
services/vyce_image_service.py (model Grok Imagine 2 qua Vyce AI).

Khác với /photo (tìm ảnh có sẵn trong kho miễn phí), lệnh này SINH ảnh mới
và TỐN CREDIT mỗi lần gọi — nên có cooldown per-user khá rát (xem
COOLDOWN_SECONDS) để 1 người không đốt sạch credit của server trong 2 phút.

Luồng xử lý:
  1. defer() ngay (sinh ảnh mất ~13-19s, quá 3s là Discord huỷ interaction).
  2. Gọi service -> nhận URL ảnh.
  3. TẢI ảnh về rồi upload thẳng lên Discord dưới dạng file đính kèm, thay vì
     chỉ embed URL gốc: URL trên vyceai.com không rõ sống được bao lâu, embed
     trỏ tới đó sẽ thành ảnh vỡ trong lịch sử chat sau này. Nếu tải thất bại
     (ảnh quá to / mạng lỗi) thì mới fallback về embed URL.
  4. Lỗi thì báo ngay vào Discord, TÁCH 2 loại cho người dùng biết đường xử lý:
     - Bị kiểm duyệt chặn -> bảo đổi prompt (thử lại y nguyên cũng vô ích).
     - Lỗi kỹ thuật (hết credit, rate limit, timeout) -> bảo thử lại sau.
"""

from __future__ import annotations

import io

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from services.vyce_image_service import ImageGenBlockedError, ImageGenError

# Mỗi user 1 ảnh / 60s. Con số này là đánh đổi tiền bạc chứ không phải giới
# hạn kỹ thuật — chỉnh thoải mái tuỳ ngân sách credit của server.
COOLDOWN_SECONDS = 60.0

# Discord cho upload tối đa 8MB với server không boost (ảnh thực tế ~400KB,
# nên ngưỡng này gần như không bao giờ chạm). Vượt ngưỡng -> fallback embed URL
# thay vì để Discord từ chối cả message.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 60

MAX_PROMPT_LENGTH = 1000


class GenImageCog(commands.Cog):
    """Lệnh sinh ảnh bằng AI: /gen_img."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def service(self):
        # Lazy lookup qua bot instance theo đúng pattern của PhotoCog
        # (self.bot.image_aggregator) — service được gắn trong bot.py.
        return getattr(self.bot, "image_generator", None)

    @app_commands.command(
        name="gen_img",
        description="Tạo ảnh mới bằng AI từ mô tả của bạn (không phải tìm ảnh có sẵn)",
    )
    @app_commands.describe(
        prompt="Mô tả ảnh muốn tạo, càng chi tiết càng tốt. Tiếng Anh thường cho kết quả đẹp hơn."
    )
    @app_commands.checks.cooldown(1, COOLDOWN_SECONDS, key=lambda i: i.user.id)
    async def gen_img(self, interaction: discord.Interaction, prompt: str):
        prompt = prompt.strip()
        if not prompt:
            await interaction.response.send_message(
                "Phải nhập mô tả ảnh thì tao mới vẽ được chứ.", ephemeral=True
            )
            return
        if len(prompt) > MAX_PROMPT_LENGTH:
            await interaction.response.send_message(
                f"Mô tả dài quá ({len(prompt)} ký tự), rút xuống dưới "
                f"{MAX_PROMPT_LENGTH} ký tự giúp tao.",
                ephemeral=True,
            )
            return

        service = self.service
        if service is None or not service.is_configured():
            await interaction.response.send_message(
                "Tính năng tạo ảnh đang tắt (chưa cấu hình VYCE_API_KEY).",
                ephemeral=True,
            )
            return

        # Sinh ảnh mất ~13-19s, vượt xa giới hạn 3s của Discord -> phải defer.
        await interaction.response.defer()

        try:
            result = await service.generate(prompt)
        except ImageGenBlockedError as exc:
            await interaction.followup.send(
                embed=self._error_embed(
                    title="🚫 Prompt bị chặn",
                    description=(
                        f"Mô tả của mày bị hệ thống kiểm duyệt từ chối, thử lại "
                        f"y nguyên cũng vô ích — đổi mô tả khác đi.\n\n"
                        f"```{str(exc)[:500]}```"
                    ),
                    prompt=prompt,
                    requester=interaction.user.display_name,
                    color=discord.Color.orange(),
                )
            )
            return
        except ImageGenError as exc:
            await interaction.followup.send(
                embed=self._error_embed(
                    title="⚠️ Tạo ảnh thất bại",
                    description=f"Lỗi phía dịch vụ tạo ảnh, thử lại sau nhé.\n\n```{str(exc)[:500]}```",
                    prompt=prompt,
                    requester=interaction.user.display_name,
                    color=discord.Color.red(),
                )
            )
            return
        except Exception as exc:  # noqa: BLE001 - không để lỗi lạ làm treo interaction
            await interaction.followup.send(
                embed=self._error_embed(
                    title="⚠️ Tạo ảnh thất bại",
                    description=f"Lỗi không xác định.\n\n```{type(exc).__name__}: {str(exc)[:400]}```",
                    prompt=prompt,
                    requester=interaction.user.display_name,
                    color=discord.Color.red(),
                )
            )
            return

        embed = discord.Embed(
            title="🎨 Ảnh AI theo yêu cầu",
            description=f"**Prompt:** {result.revised_prompt[:1000]}",
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=f"Yêu cầu bởi {interaction.user.display_name} · Model: {result.model}"
        )

        image_bytes = await self._download(result.url)
        if image_bytes is None:
            # Fallback: không tải được thì vẫn cho người dùng xem ảnh qua URL
            # gốc, kèm cảnh báo là link có thể chết sau này.
            embed.set_image(url=result.url)
            embed.add_field(
                name="Lưu ý",
                value="Không tải được ảnh về để đính kèm, đang hiển thị qua link gốc — link này có thể hết hạn.",
                inline=False,
            )
            await interaction.followup.send(embed=embed)
            return

        filename = "gen_img.jpg"
        file = discord.File(io.BytesIO(image_bytes), filename=filename)
        embed.set_image(url=f"attachment://{filename}")
        await interaction.followup.send(embed=embed, file=file)

    @gen_img.error
    async def gen_img_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Bắt riêng lỗi cooldown của app_commands — mặc định discord.py chỉ
        log ra console chứ không báo gì cho người dùng, nhìn như bot chết."""
        if isinstance(error, app_commands.CommandOnCooldown):
            message = (
                f"Từ từ thôi, tạo ảnh tốn tiền đấy. Đợi thêm "
                f"**{error.retry_after:.0f} giây** nữa rồi gọi lại."
            )
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return
        raise error

    @staticmethod
    async def _download(url: str) -> bytes | None:
        """Tải ảnh về dạng bytes để upload lên Discord. Trả về None nếu lỗi
        hoặc ảnh to quá ngưỡng upload — caller tự fallback sang embed URL."""
        timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return None
                    # Chặn sớm theo Content-Length nếu server có khai báo, để
                    # không tải hết 1 file khổng lồ rồi mới phát hiện quá cỡ.
                    length = resp.headers.get("Content-Length")
                    if length and int(length) > MAX_UPLOAD_BYTES:
                        return None
                    data = await resp.read()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

        if len(data) > MAX_UPLOAD_BYTES:
            return None
        return data

    @staticmethod
    def _error_embed(
        title: str,
        description: str,
        prompt: str,
        requester: str,
        color: discord.Color,
    ) -> discord.Embed:
        """Embed báo lỗi, luôn kèm lại prompt gốc để người dùng copy sửa."""
        embed = discord.Embed(title=title, description=description, color=color)
        embed.add_field(name="Prompt đã gửi", value=f"```{prompt[:900]}```", inline=False)
        embed.set_footer(text=f"Yêu cầu bởi {requester}")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(GenImageCog(bot))
