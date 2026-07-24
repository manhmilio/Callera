from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

RATING_EMOJIS = ("👍", "👎")


class RatingCog(commands.Cog):
    """Rating ảnh bằng reaction 👍/👎 (RAM only, mất khi bot restart) +
    bảng xếp hạng /top_photos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # message_id -> {"tag": str, "image_url": str}
        self.rated_messages: dict[int, dict] = {}
        # tag -> { image_url: {"up": int, "down": int} }
        self.photo_ratings: dict[str, dict[str, dict]] = defaultdict(dict)

    async def register(self, message: discord.Message, tag: str, image_url: str) -> None:
        """Gọi từ cog khác (vd PhotoCog) sau khi gửi 1 ảnh, để bật rating cho
        message đó (thêm reaction 👍/👎 + theo dõi vote)."""
        self.rated_messages[message.id] = {"tag": tag, "image_url": image_url}
        for emoji in RATING_EMOJIS:
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if self.bot.user is not None and payload.user_id == self.bot.user.id:
            return  # bỏ qua reaction do chính bot tự thêm vào

        emoji = str(payload.emoji)
        if emoji not in RATING_EMOJIS:
            return

        info = self.rated_messages.get(payload.message_id)
        if info is None:
            return

        tag, image_url = info["tag"], info["image_url"]
        entry = self.photo_ratings[tag].setdefault(image_url, {"up": 0, "down": 0})
        if emoji == "👍":
            entry["up"] += 1
        else:
            entry["down"] += 1

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        emoji = str(payload.emoji)
        if emoji not in RATING_EMOJIS:
            return

        info = self.rated_messages.get(payload.message_id)
        if info is None:
            return

        tag, image_url = info["tag"], info["image_url"]
        entry = self.photo_ratings[tag].get(image_url)
        if entry is None:
            return
        if emoji == "👍":
            entry["up"] = max(0, entry["up"] - 1)
        else:
            entry["down"] = max(0, entry["down"] - 1)

    @app_commands.command(
        name="top_photos",
        description="Xem bảng xếp hạng ảnh được rating cao nhất theo tag",
    )
    @app_commands.describe(tag="Tag muốn xem bảng xếp hạng")
    async def top_photos(self, interaction: discord.Interaction, tag: str):
        tag = tag.strip()
        ratings = self.photo_ratings.get(tag)
        if not ratings:
            await interaction.response.send_message(
                f"Chưa có ảnh nào được rating cho tag **{tag}**.", ephemeral=True
            )
            return

        ranked = sorted(ratings.items(), key=lambda kv: kv[1]["up"] - kv[1]["down"], reverse=True)[:5]

        embed = discord.Embed(title=f"🏆 Top ảnh — {tag}", color=discord.Color.gold())
        lines = [
            f"**#{i}** 👍 {score['up']} · 👎 {score['down']} — [Xem ảnh]({url})"
            for i, (url, score) in enumerate(ranked, start=1)
        ]
        embed.description = "\n".join(lines)
        embed.set_footer(text="Rating được tính từ reaction 👍/👎, chỉ lưu tạm trong RAM (mất khi bot restart).")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RatingCog(bot))
