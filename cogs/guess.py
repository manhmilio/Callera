import random

import discord
from discord import app_commands
from discord.ext import commands

from data import GUESS_LOCATIONS
from utils import normalize_text


class GuessCog(commands.Cog):
    """Mini-game /guess_location — đoán tên địa danh qua 1 tấm ảnh (không làm mờ)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # channel_id -> {"answer_tag": str, "accepted": list[str]}
        self.active_games: dict[int, dict] = {}

    @property
    def aggregator(self):
        return self.bot.image_aggregator

    @app_commands.command(name="guess_location", description="Đoán tên địa danh qua 1 tấm ảnh (ẩn tên)")
    async def guess_location(self, interaction: discord.Interaction):
        if interaction.channel_id in self.active_games:
            await interaction.response.send_message(
                "Đang có 1 ván đoán địa danh chưa kết thúc trong kênh này, chờ ván trước xong đã nhé.",
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

        embed = discord.Embed(
            title="🗺️ Đoán địa danh!",
            description="Đây là địa danh nào? Trả lời trực tiếp trong kênh này, ai đúng đầu tiên thắng!",
            color=discord.Color.green(),
        )
        embed.set_image(url=chosen.image_url)
        embed.set_footer(text=f"Nguồn: {chosen.source}")

        await interaction.followup.send(embed=embed)
        await self.aggregator.notify_used(chosen)

        self.active_games[interaction.channel_id] = {
            "answer_tag": answer_tag,
            "accepted": GUESS_LOCATIONS[answer_tag],
        }

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
            await message.reply(
                f"🎉 Chính xác, {message.author.mention}! Địa danh trong ảnh là **{game['answer_tag']}**."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(GuessCog(bot))
