"""
Cog cho tính năng hỏi đáp: tag bot (@Callera) kèm câu hỏi -> bot trả lời
bằng QAAggregator (thử Gemini + Google Search Grounding trước, tự động
fallback sang Groq Compound nếu Gemini bị rate limit/lỗi).

Cách dùng trong Discord:
    @Callera thủ đô của Nhật Bản là gì?

Bản cập nhật này: đọc system prompt ĐỘNG theo tính cách (persona) đang được
chọn cho từng guild (xem cogs/personality.py, đổi qua slash command
/personality), thay vì cá tính hard-code cố định. Nếu PersonalityCog chưa
load được vì lý do gì đó, tự fallback về persona mặc định
(data.personas.DEFAULT_PERSONA) để tính năng hỏi đáp không bao giờ crash.

LƯU Ý QUAN TRỌNG (cần đối chiếu với code thật của bạn):
QAAggregator.ask() / GeminiQAService.ask() / GroqCompoundQAService.ask()
cần nhận thêm tham số `system_prompt: str` và dùng nó khi build request,
thay vì có cá tính hard-code sẵn bên trong service như trước. Nếu các
service này hiện đang hard-code cá tính ở đâu đó (system instruction cố
định trong qa_service.py/groq_qa_service.py), cần dọn cá tính cứng đó ra,
để cog truyền `system_prompt` xuống mỗi lần gọi.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from data.personas import DEFAULT_PERSONA, get_persona
from services.qa_aggregator import QAAggregator
from utils.qa_memory import QaMemory
from utils.qa_ratelimit import QaRateLimiter

logger = logging.getLogger(__name__)

MAX_EMBED_DESCRIPTION = 4096  # giới hạn ký tự của Discord embed description
USER_COOLDOWN_SECONDS = 10.0
CACHE_TTL_SECONDS = 600.0
MEMORY_MAX_TURNS = 5  # nhớ tối đa 5 lượt hỏi-đáp gần nhất mỗi user
MEMORY_TTL_SECONDS = 900.0  # tự quên nếu 15 phút không hỏi tiếp


class AskCog(commands.Cog):
    def __init__(self, bot: commands.Bot, qa_service: QAAggregator):
        self.bot = bot
        self.qa_service = qa_service
        self.rate_limiter = QaRateLimiter(
            user_cooldown_seconds=USER_COOLDOWN_SECONDS,
            cache_ttl_seconds=CACHE_TTL_SECONDS,
        )
        self.memory = QaMemory(
            max_turns=MEMORY_MAX_TURNS, ttl_seconds=MEMORY_TTL_SECONDS
        )

    async def _get_persona(self, guild_id: int | None) -> tuple[str, str]:
        """Trả về (persona_key, system_prompt) hiện tại cho guild.

        Đọc qua PersonalityCog nếu cog đó đã load; fallback về persona mặc
        định nếu chưa có (vd cogs.personality lỡ chưa được thêm vào
        INITIAL_EXTENSIONS, hoặc lệnh gọi từ DM không có guild).
        """
        personality_cog = self.bot.get_cog("PersonalityCog")
        if personality_cog is None:
            return DEFAULT_PERSONA, get_persona(DEFAULT_PERSONA)["system_prompt"]
        key = await personality_cog.get_current_persona_key(guild_id)
        return key, get_persona(key)["system_prompt"]

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

        guild_id = message.guild.id if message.guild else None
        persona_key, system_prompt = await self._get_persona(guild_id)

        # Ghép persona_key vào cache key: cùng 1 câu hỏi nhưng khác tính
        # cách (khác guild, hoặc guild đổi persona) sẽ KHÔNG dùng chung
        # cache, tránh trả lời sai giọng văn so với persona đang chọn.
        cache_key = f"{persona_key}:{question}"

        cached = self.rate_limiter.get_cached(cache_key)
        if cached is not None:
            answer, _sources = cached
            # Vẫn ghi vào memory của user để các câu hỏi nối tiếp sau đó
            # (dù câu này trả lời từ cache chung) vẫn có ngữ cảnh đúng.
            self.memory.add_turn(message.author.id, question, answer)
            await message.reply(embed=self._build_embed(answer, cached=True))
            return

        self.rate_limiter.mark_asked(message.author.id)

        history = self.memory.get_history(message.author.id)

        async with message.channel.typing():
            try:
                answer = await self.qa_service.ask(
                    question, history=history, system_prompt=system_prompt
                )
            except Exception:
                logger.exception(
                    "Lỗi khi gọi QAAggregator cho câu hỏi: %s", question
                )
                await message.reply(
                    "Xin lỗi, mình đang gặp lỗi hoặc hết quota tạm thời, "
                    "thử lại sau một lát nhé 🙏"
                )
                return

        # QaRateLimiter.set_cached hiện vẫn nhận tham số sources (list) để
        # không phải sửa file utils/qa_ratelimit.py — luôn truyền [] vì bot
        # không còn hiển thị nguồn tham khảo nữa.
        self.rate_limiter.set_cached(cache_key, answer, [])
        self.memory.add_turn(message.author.id, question, answer)
        await message.reply(embed=self._build_embed(answer))

    @app_commands.command(
        name="quen_di",
        description="Xoá lịch sử hỏi-đáp tạm của bạn với bot (ngữ cảnh hội thoại)",
    )
    async def quen_di(self, interaction: discord.Interaction) -> None:
        had_something = self.memory.clear(interaction.user.id)
        if had_something:
            message = "Đã quên hết rồi, coi như lần đầu gặp mày."
        else:
            message = "Có gì đâu mà quên, tao có nhớ gì mày đâu."
        await interaction.response.send_message(message, ephemeral=True)

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
    qa_service = getattr(bot, "qa_service", None)
    if qa_service is None or not qa_service.is_configured():
        logger.warning(
            "Chưa cấu hình GEMINI_API_KEY hay GROQ_API_KEY nào trong "
            "config.py/.env — bỏ qua load AskCog."
        )
        return
    await bot.add_cog(AskCog(bot, qa_service))