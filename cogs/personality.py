"""
Cog quản lý tính cách (persona) của Callera — cho phép admin đổi cá tính trả
lời của bot (dùng bởi cogs/ask.py và các cog khác có gọi LLM có cá tính).
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from data.personas import DEFAULT_PERSONA, PERSONAS, get_persona
from db import personality_repository as repo

logger = logging.getLogger(__name__)

PERSONA_CHOICES = [
    app_commands.Choice(name=f"{cfg['emoji']} {cfg['label']}", value=key)
    for key, cfg in PERSONAS.items()
]


class PersonalityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_current_persona_key(self, guild_id: int | None) -> str:
        """Trả về persona key (vd 'lao', 'de_thuong') đang set cho guild.

        Dùng khi cần key thuần (vd để ghép vào cache key theo persona ở
        AskCog), không cần build nguyên system prompt.
        """
        db = getattr(self.bot, "db", None)
        if db is None or guild_id is None:
            return DEFAULT_PERSONA
        return await repo.get_persona_key(db, guild_id)

    async def get_current_persona_prompt(self, guild_id: int | None) -> str:
        """Hàm tiện ích cho cog khác (vd AskCog) gọi để lấy system prompt hiện tại.

        Cách dùng trong cogs/ask.py:

            personality_cog = self.bot.get_cog("PersonalityCog")
            if personality_cog:
                system_prompt = await personality_cog.get_current_persona_prompt(
                    message.guild.id if message.guild else None
                )
            else:
                system_prompt = get_persona(None)["system_prompt"]  # fallback
        """
        key = await self.get_current_persona_key(guild_id)
        return get_persona(key)["system_prompt"]

    @app_commands.command(
        name="personality", description="Đổi tính cách trả lời của Callera"
    )
    @app_commands.describe(persona="Chọn tính cách mới")
    @app_commands.choices(persona=PERSONA_CHOICES)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def personality(
        self, interaction: discord.Interaction, persona: app_commands.Choice[str]
    ):
        db = getattr(self.bot, "db", None)
        if db is None:
            await interaction.response.send_message(
                "❌ Database chưa sẵn sàng, thử lại sau nha.", ephemeral=True
            )
            return

        await repo.set_persona_key(db, interaction.guild_id, persona.value)
        cfg = get_persona(persona.value)
        await interaction.response.send_message(
            f"{cfg['emoji']} Đã đổi tính cách sang **{cfg['label']}** cho server này.\n"
            f"_{cfg['description']}_"
        )
        logger.info(
            "Guild %s đổi persona sang '%s' (bởi %s)",
            interaction.guild_id,
            persona.value,
            interaction.user,
        )

    @app_commands.command(
        name="current_personality", description="Xem tính cách hiện tại của Callera"
    )
    async def current_personality(self, interaction: discord.Interaction):
        db = getattr(self.bot, "db", None)
        if db is None:
            await interaction.response.send_message(
                "❌ Database chưa sẵn sàng, thử lại sau nha.", ephemeral=True
            )
            return

        key = await repo.get_persona_key(db, interaction.guild_id)
        cfg = get_persona(key)
        await interaction.response.send_message(
            f"Tính cách hiện tại: {cfg['emoji']} **{cfg['label']}**\n_{cfg['description']}_"
        )

    @personality.error
    async def personality_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Chỉ admin (quyền Manage Server) mới được đổi tính cách bot nha.",
                ephemeral=True,
            )
        else:
            logger.exception("Lỗi không xác định ở /personality", exc_info=error)
            await interaction.response.send_message(
                "❌ Có lỗi xảy ra, thử lại sau.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(PersonalityCog(bot))