"""
Cog cho tính năng hỏi đáp: tag bot (@Callera) kèm câu hỏi -> bot trả lời
bằng Gemini API (bật Google Search Grounding để có thông tin cập nhật).

Cách dùng trong Discord:
    @Callera thủ đô của Nhật Bản là gì?

Bản cập nhật này: bỏ hiển thị "Nguồn tham khảo" trong embed (qa_service.ask()
giờ chỉ trả về str thay vì tuple), câu trả lời cũng ngắn gọn hơn do đã chỉnh
ở qa_service.py.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from services.qa_service import GeminiQAService
from utils.qa_ratelimit import QaRateLimiter

logger = logging.getLogger(__name__)

MAX_EMBED_DESCRIPTION = 4096  # giới hạn ký tự của Discord embed description
USER_COOLDOWN_SECONDS = 10.0
CACHE_TTL_SECONDS = 600.0


class AskCog(commands.Cog):
    def __init__(self, bot: commands.Bot, qa_service: GeminiQAService):
        self.bot = bot
        self.qa_service = qa_service
        self.rate_limiter = QaRateLimiter(
            user_cooldown_seconds=USER_COOLDOWN_SECONDS,
            cache_ttl_seconds=CACHE_TTL_SECONDS,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if self.bot.user not in message.mentions:
            return

        question = self._extract_question(message)
        if not question:
            await message.reply(
                "Bạn tag mình kèm câu hỏi nhé, ví dụ: "
                "`@Callera thủ đô của Nhật Bản là gì?`"
            )
            return

        remaining = self.rate_limiter.is_on_cooldown(message.author.id)
        if remaining is not None:
            await message.reply(
                f"Từ từ đã, chờ khoảng {remaining:.0f} giây nữa rồi hỏi tiếp nhé 😅"
            )
            return

        cached = self.rate_limiter.get_cached(question)
        if cached is not None:
            answer, _sources = cached
            await message.reply(embed=self._build_embed(answer, cached=True))
            return

        self.rate_limiter.mark_asked(message.author.id)

        async with message.channel.typing():
            try:
                answer = await self.qa_service.ask(question)
            except Exception:
                logger.exception(
                    "Lỗi khi gọi Gemini API cho câu hỏi: %s", question
                )
                await message.reply(
                    "Xin lỗi, mình đang gặp lỗi hoặc hết quota tạm thời, "
                    "thử lại sau một lát nhé 🙏"
                )
                return

        # QaRateLimiter.set_cached hiện vẫn nhận tham số sources (list) để
        # không phải sửa file utils/qa_ratelimit.py — luôn truyền [] vì bot
        # không còn hiển thị nguồn tham khảo nữa.
        self.rate_limiter.set_cached(question, answer, [])
        await message.reply(embed=self._build_embed(answer))

    def _extract_question(self, message: discord.Message) -> str:
        """Bỏ phần tag @bot khỏi nội dung tin nhắn, trả về câu hỏi thuần."""
        content = message.content
        for mention in message.mentions:
            content = content.replace(f"<@{mention.id}>", "")
            content = content.replace(f"<@!{mention.id}>", "")
        return content.strip()

    def _build_embed(self, answer: str, cached: bool = False) -> discord.Embed:
        description = answer[:MAX_EMBED_DESCRIPTION]
        embed = discord.Embed(description=description, color=discord.Color.blue())
        footer = "Câu trả lời do AI tạo, có thể không chính xác 100%."
        if cached:
            footer += " (đã lưu tạm cho câu hỏi giống trước đó)"
        embed.set_footer(text=footer)
        return embed


async def setup(bot: commands.Bot) -> None:
    api_key = getattr(bot, "gemini_api_key", None)
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY chưa được cấu hình trong config.py/.env — "
            "bỏ qua load AskCog."
        )
        return
    qa_service = GeminiQAService(api_key=api_key)
    await bot.add_cog(AskCog(bot, qa_service))