"""
cogs/feature_toggle.py

Slash command chung để admin bật/tắt các tính năng tự động của bot theo
từng server: lời tạm biệt (farewell) và nhắc nhở học tập (study_reminder).

Dùng chung 1 lệnh /toggle_feature thay vì tách riêng từng lệnh cho mỗi
tính năng, theo yêu cầu đã chốt.
"""

import discord
from discord import app_commands
from discord.ext import commands

from db import feature_config_repository

FEATURE_CHOICES = [
    app_commands.Choice(name="Lời tạm biệt khi rời voice (farewell)", value="farewell"),
    app_commands.Choice(name="Nhắc nhở học tập (study_reminder)", value="study_reminder"),
]

FEATURE_DISPLAY_NAMES = {
    "farewell": "Lời tạm biệt khi rời voice",
    "study_reminder": "Nhắc nhở học tập",
}


class FeatureToggleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="toggle_feature",
        description="Bật/tắt 1 tính năng tự động của bot cho server này",
    )
    @app_commands.describe(ten="Tính năng cần bật/tắt", bat="Bật hay tắt")
    @app_commands.choices(ten=FEATURE_CHOICES)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle_feature(
        self,
        interaction: discord.Interaction,
        ten: app_commands.Choice[str],
        bat: bool,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong server.", ephemeral=True
            )
            return

        await feature_config_repository.set_feature_enabled(
            self.bot.db, interaction.guild.id, ten.value, bat
        )

        trang_thai = "BẬT ✅" if bat else "TẮT ❌"
        display_name = FEATURE_DISPLAY_NAMES.get(ten.value, ten.value)
        await interaction.response.send_message(
            f"Đã {trang_thai} tính năng **{display_name}** cho server này.",
            ephemeral=True,
        )

    @toggle_feature.error
    async def _admin_only_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Lệnh này chỉ dành cho admin (cần quyền Manage Server).",
                ephemeral=True,
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(FeatureToggleCog(bot))