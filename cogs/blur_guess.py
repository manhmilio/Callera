import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

from data import GUESS_LOCATIONS
from utils import normalize_text, download_image_bytes, blur_image_bytes

DEFAULT_BLUR_RADIUS = 30  # higher = blurrier; tune to taste
ROUND_TIMEOUT_SECONDS = 180.0  # 3 phút


class BlurGuessCog(commands.Cog):
    """Mini-game /blur_guess — đoán địa danh qua 1 tấm ảnh bị làm mờ (Pillow),
    tự reveal ảnh gốc khi đoán đúng hoặc hết giờ."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # channel_id -> {"answer_tag", "accepted", "image_url", "source"}
        self.active_games: dict[int, dict] = {}

    @property
    def aggregator(self):
        return self.bot.image_aggregator

    @app_commands.command(name="blur_guess", description="Đoán địa danh qua 1 tấm ảnh bị làm mờ")
    async def blur_guess(self, interaction: discord.Interaction):
        if interaction.channel_id in self.active_games:
            await interaction.response.send_message(
                "Đang có 1 ván câu đố mù chưa kết thúc trong kênh này, chờ ván trước xong đã nhé.",
                ephemeral=True,
            )
            return

        answer_tag = random.choice(list(GUESS_LOCATIONS.keys()))

        await interaction.response.defer()
        try:
            results = await self.aggregator.search(answer_tag)
        except Exception as e:
            await interaction.followup.send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
            return

        if not results:
            await interaction.followup.send("Không tìm được ảnh cho vòng chơi này, thử lại sau nhé.")
            return

        chosen = random.choice(results)

        try:
            original_bytes = await download_image_bytes(chosen.image_url)
            blurred_buffer = blur_image_bytes(original_bytes, blur_radius=DEFAULT_BLUR_RADIUS)
        except Exception as e:
            await interaction.followup.send(f"Có lỗi xảy ra khi làm mờ ảnh: {e}")
            return

        file = discord.File(blurred_buffer, filename="blurred.png")
        embed = discord.Embed(
            title="🌫️ Câu đố mù — Đoán địa danh!",
            description="Ảnh này đang bị làm mờ. Trả lời trực tiếp trong kênh này, ai đúng đầu tiên thắng!",
            color=discord.Color.dark_teal(),
        )
        embed.set_image(url="attachment://blurred.png")
        embed.set_footer(text=f"Nguồn: {chosen.source}")

        await interaction.followup.send(embed=embed, file=file)
        await self.aggregator.notify_used(chosen)

        self.active_games[interaction.channel_id] = {
            "answer_tag": answer_tag,
            "accepted": GUESS_LOCATIONS[answer_tag],
            "image_url": chosen.image_url,
            "source": chosen.source,
        }
        asyncio.create_task(self._expire_round(interaction.channel_id, answer_tag))

    async def _expire_round(self, channel_id: int, answer_tag: str) -> None:
        """Tự động kết thúc ván /blur_guess nếu không ai đoán đúng trong
        ROUND_TIMEOUT_SECONDS, và công bố đáp án."""
        await asyncio.sleep(ROUND_TIMEOUT_SECONDS)
        game = self.active_games.get(channel_id)
        if game is None or game["answer_tag"] != answer_tag:
            return  # ván đã kết thúc (đoán đúng hoặc bị thay bởi ván khác)

        del self.active_games[channel_id]
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        reveal_embed = discord.Embed(
            title="⏰ Hết giờ!",
            description=f"Không ai đoán đúng. Địa danh trong ảnh là **{answer_tag}**.",
            color=discord.Color.orange(),
        )
        reveal_embed.set_image(url=game["image_url"])
        reveal_embed.set_footer(text=f"Nguồn: {game['source']}")
        await channel.send(embed=reveal_embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        game = self.active_games.get(message.channel.id)
        if not game:
            return

        guess = normalize_text(message.content)
        if any(normalize_text(ans) in guess for ans in game["accepted"]):
            del self.active_games[message.channel.id]
            reveal_embed = discord.Embed(
                title="✅ Đoán đúng rồi!",
                description=f"Địa danh trong ảnh là **{game['answer_tag']}**.",
                color=discord.Color.green(),
            )
            reveal_embed.set_image(url=game["image_url"])
            reveal_embed.set_footer(text=f"Nguồn: {game['source']}")
            await message.reply(f"🎉 Chính xác, {message.author.mention}!", embed=reveal_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(BlurGuessCog(bot))
