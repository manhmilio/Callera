import random

import discord
from discord import app_commands
from discord.ext import commands

from data import RANDOM_TAGS
from utils import build_image_embed


class ImageView(discord.ui.View):
    """View chứa nút 'Ảnh khác' để lấy thêm 1 ảnh khác cùng tag, không cần
    gõ lại lệnh. Tự vô hiệu hoá nút sau 5 phút để tránh bị bấm spam vô thời hạn."""

    def __init__(self, cog: "PhotoCog", tag: str, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.tag = tag

    @discord.ui.button(label="Ảnh khác", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def another_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()  # tìm kiếm có thể mất vài giây
        await self.cog.fetch_and_reply(interaction, self.tag)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


class PhotoCog(commands.Cog):
    """Lệnh lấy ảnh theo tag: /photo, /random_photo, /many_photos."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def aggregator(self):
        return self.bot.image_aggregator

    def _rating_cog(self):
        # Truy cập RatingCog để bật rating 👍/👎 cho message mới gửi. Lazy
        # lookup thay vì import trực tiếp để tránh phụ thuộc vòng giữa các cog.
        return self.bot.get_cog("RatingCog")

    async def fetch_and_reply(self, interaction: discord.Interaction, tag: str) -> None:
        """Tìm ảnh theo tag, gửi embed kèm nút 'Ảnh khác' + reaction rating,
        xử lý lỗi/rỗng. Dùng chung cho slash command và nút 'Ảnh khác'."""
        try:
            results = await self.aggregator.search(tag)
        except Exception as e:
            await interaction.followup.send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
            return

        if not results:
            await interaction.followup.send(f"Không tìm thấy ảnh nào cho từ khóa **{tag}**.")
            return

        chosen = random.choice(results)
        embed = build_image_embed(tag, chosen, interaction.user.display_name)
        view = ImageView(cog=self, tag=tag)

        message = await interaction.followup.send(embed=embed, view=view)
        rating_cog = self._rating_cog()
        if message is not None and rating_cog is not None:
            await rating_cog.register(message, tag, chosen.image_url)

        await self.aggregator.notify_used(chosen)

    async def send_many_photos(self, interaction: discord.Interaction, tag: str, quantity: int) -> None:
        try:
            results = await self.aggregator.search(tag)
        except Exception as e:
            await interaction.followup.send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
            return

        if not results:
            await interaction.followup.send(f"Không tìm thấy ảnh nào cho từ khóa **{tag}**.")
            return

        chosen_list = random.sample(results, k=min(quantity, len(results)))
        rating_cog = self._rating_cog()

        for chosen in chosen_list:
            embed = build_image_embed(tag, chosen, interaction.user.display_name)
            view = ImageView(cog=self, tag=tag)
            message = await interaction.followup.send(embed=embed, view=view)
            if message is not None and rating_cog is not None:
                await rating_cog.register(message, tag, chosen.image_url)
            await self.aggregator.notify_used(chosen)

        if len(chosen_list) < quantity:
            await interaction.followup.send(
                f"Chỉ tìm được {len(chosen_list)}/{quantity} ảnh khác nhau cho tag **{tag}**."
            )

    @app_commands.command(name="photo", description="Lấy một ảnh ngẫu nhiên theo từ khóa")
    @app_commands.describe(tag="Từ khóa tìm kiếm, ví dụ: hoàng hôn, trường sa (có thể gõ nhiều từ)")
    async def photo(self, interaction: discord.Interaction, tag: str):
        tag = tag.strip()
        if not tag:
            await interaction.response.send_message("Vui lòng nhập từ khóa hợp lệ.", ephemeral=True)
            return

        await interaction.response.defer()  # tìm kiếm có thể mất vài giây
        await self.fetch_and_reply(interaction, tag)

    @app_commands.command(
        name="random_photo",
        description="Lấy một ảnh với chủ đề ngẫu nhiên, không cần nhập từ khóa",
    )
    async def random_photo(self, interaction: discord.Interaction):
        tag = random.choice(RANDOM_TAGS)
        await interaction.response.defer()
        await self.fetch_and_reply(interaction, tag)

    @app_commands.command(name="many_photos", description="Lấy nhiều ảnh cùng lúc theo 1 từ khóa")
    @app_commands.describe(
        tag="Từ khóa tìm kiếm, ví dụ: núi, hoàng hôn (có thể gõ nhiều từ)",
        quantity="Số lượng ảnh muốn lấy (1-10, mặc định 3)",
    )
    async def many_photos(
        self,
        interaction: discord.Interaction,
        tag: str,
        quantity: app_commands.Range[int, 1, 10] = 3,
    ):
        tag = tag.strip()
        if not tag:
            await interaction.response.send_message("Vui lòng nhập từ khóa hợp lệ.", ephemeral=True)
            return

        await interaction.response.defer()
        await self.send_many_photos(interaction, tag, quantity)


async def setup(bot: commands.Bot):
    await bot.add_cog(PhotoCog(bot))
