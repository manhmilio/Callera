import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

BATTLE_EMOJIS = ("🅰️", "🅱️")


class BattleCog(commands.Cog):
    """Đấu ảnh: 2 ảnh cùng tag đối đầu nhau, mọi người vote bằng reaction."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def aggregator(self):
        return self.bot.image_aggregator

    @app_commands.command(
        name="photo_battle",
        description="Đấu ảnh: 2 ảnh cùng tag, mọi người vote ảnh đẹp hơn",
    )
    @app_commands.describe(
        tag="Từ khóa cho 2 ảnh đối đầu",
        duration_minutes="Thời gian cho phép vote, tính bằng phút (1-30, mặc định 3)",
    )
    async def photo_battle(
        self,
        interaction: discord.Interaction,
        tag: str,
        duration_minutes: app_commands.Range[int, 1, 30] = 3,
    ):
        tag = tag.strip()
        if not tag:
            await interaction.response.send_message("Vui lòng nhập từ khóa hợp lệ.", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            results = await self.aggregator.search(tag)
        except Exception as e:
            await interaction.followup.send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
            return

        if len(results) < 2:
            await interaction.followup.send(f"Không đủ ảnh khác nhau cho tag **{tag}** để đấu ảnh.")
            return

        photo_a, photo_b = random.sample(results, 2)

        embed_a = discord.Embed(
            title=f"⚔️ Đấu ảnh: {tag}",
            description=(
                f"Vote 🅰️ hoặc 🅱️ cho ảnh đẹp hơn! Kết quả sẽ công bố sau {duration_minutes} phút.\n\n"
                f"🅰️ — Nguồn: {photo_a.source} · Ảnh của {photo_a.author}\n"
                f"🅱️ — Nguồn: {photo_b.source} · Ảnh của {photo_b.author}"
            ),
            color=discord.Color.purple(),
        )
        embed_a.set_image(url=photo_a.image_url)

        embed_b = discord.Embed(color=discord.Color.purple())
        embed_b.set_image(url=photo_b.image_url)

        message = await interaction.followup.send(embeds=[embed_a, embed_b])
        for emoji in BATTLE_EMOJIS:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass

        for chosen in (photo_a, photo_b):
            await self.aggregator.notify_used(chosen)

        asyncio.create_task(self._announce_result_later(message, tag, duration_minutes * 60))

    async def _announce_result_later(self, message: discord.Message, tag: str, delay_seconds: float) -> None:
        await asyncio.sleep(delay_seconds)
        try:
            message = await message.channel.fetch_message(message.id)
        except discord.HTTPException:
            return

        votes_a = votes_b = 0
        for reaction in message.reactions:
            emoji = str(reaction.emoji)
            if emoji == "🅰️":
                votes_a = max(0, reaction.count - 1)  # trừ reaction do bot tự thêm
            elif emoji == "🅱️":
                votes_b = max(0, reaction.count - 1)

        if votes_a > votes_b:
            result = f"🅰️ thắng với {votes_a} vote (so với {votes_b} vote của 🅱️)!"
        elif votes_b > votes_a:
            result = f"🅱️ thắng với {votes_b} vote (so với {votes_a} vote của 🅰️)!"
        else:
            result = f"Hoà! Cả hai ảnh đều có {votes_a} vote."

        await message.reply(f"⏰ Hết giờ đấu ảnh **{tag}**! {result}")


async def setup(bot: commands.Bot):
    await bot.add_cog(BattleCog(bot))
