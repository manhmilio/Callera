"""Cog: lời tạm biệt tự động khi user rời hẳn khỏi voice channel.

Phạm vi (theo yêu cầu đã chốt):
- Chỉ trigger khi user rời HẲN khỏi voice (không còn ở kênh voice nào trong
  guild) — không trigger khi chỉ chuyển từ kênh voice này sang kênh khác.
- Gửi vào kênh chat TEXT gần nhất mà user vừa nhắn tin trước đó (không phải
  kênh cố định do admin cấu hình).
- Nếu user chưa từng set lời tạm biệt, hoặc chưa từng nhắn tin ở kênh text
  nào (tracker rỗng, ví dụ do bot vừa restart) → bỏ qua lặng lẽ, không gửi gì
  cả, tránh làm phiền/gây lỗi khó hiểu.

Đây là module MỚI, tách biệt hoàn toàn khỏi phần cog ảnh (`photo.py`,
`rating.py`,...). Dùng chung interface `bot.db` (aiosqlite connection) được
khởi tạo 1 lần ở `bot.py` qua `db/connection.py`.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from db import farewell_repository
from utils.last_channel_tracker import LastChannelTracker

logger = logging.getLogger(__name__)

MAX_FAREWELL_LENGTH = 200  # giới hạn độ dài lời tạm biệt, tránh spam/troll


class FarewellCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.tracker = LastChannelTracker()

    # ------------------------------------------------------------------ #
    # Theo dõi kênh chat gần nhất của mỗi user
    # ------------------------------------------------------------------ #
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        self.tracker.update(message.guild.id, message.author.id, message.channel.id)

    # ------------------------------------------------------------------ #
    # Trigger chính: user rời hẳn khỏi voice
    # ------------------------------------------------------------------ #
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        # Chỉ xử lý khi trước đó đang ở 1 kênh voice, và bây giờ không còn ở
        # kênh voice nào nữa (rời hẳn, không phải chuyển kênh).
        if before.channel is None or after.channel is not None:
            return

        guild_id = member.guild.id
        user_id = member.id

        message = await farewell_repository.get_farewell(
            self.bot.db, guild_id, user_id
        )
        if not message:
            return  # user chưa set lời tạm biệt -> bỏ qua lặng lẽ

        channel_id = self.tracker.get(guild_id, user_id)
        if channel_id is None:
            return  # chưa có kênh nào để gửi -> bỏ qua lặng lẽ

        channel = member.guild.get_channel(channel_id)
        if channel is None:
            return  # kênh đã bị xoá hoặc bot không thấy được nữa

        try:
            await channel.send(f"{member.mention} {message}")
        except discord.Forbidden:
            logger.warning(
                "Không có quyền gửi tin nhắn tạm biệt ở kênh %s (guild %s)",
                channel_id,
                guild_id,
            )
        except discord.HTTPException as e:
            logger.warning("Lỗi gửi tin nhắn tạm biệt: %s", e)

    # ------------------------------------------------------------------ #
    # Slash commands quản lý lời tạm biệt
    # ------------------------------------------------------------------ #
    @app_commands.command(
        name="set_farewell", description="Đặt lời tạm biệt tự động của bạn"
    )
    @app_commands.describe(message="Nội dung lời tạm biệt (tối đa 200 ký tự)")
    async def set_farewell(
        self, interaction: discord.Interaction, message: str
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong server.", ephemeral=True
            )
            return

        if len(message) > MAX_FAREWELL_LENGTH:
            await interaction.response.send_message(
                f"Lời tạm biệt tối đa {MAX_FAREWELL_LENGTH} ký tự "
                f"(bạn đang nhập {len(message)} ký tự).",
                ephemeral=True,
            )
            return

        await farewell_repository.set_farewell(
            self.bot.db, interaction.guild.id, interaction.user.id, message
        )
        await interaction.response.send_message(
            f"Đã lưu lời tạm biệt: \"{message}\"", ephemeral=True
        )

    @app_commands.command(
        name="farewell", description="Xem lời tạm biệt hiện tại của bạn"
    )
    async def view_farewell(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong server.", ephemeral=True
            )
            return

        message = await farewell_repository.get_farewell(
            self.bot.db, interaction.guild.id, interaction.user.id
        )
        if message:
            await interaction.response.send_message(
                f"Lời tạm biệt hiện tại của bạn: \"{message}\"", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Bạn chưa đặt lời tạm biệt. Dùng /set_farewell để đặt.",
                ephemeral=True,
            )

    @app_commands.command(
        name="clear_farewell", description="Xoá lời tạm biệt của bạn"
    )
    async def clear_farewell(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Lệnh này chỉ dùng được trong server.", ephemeral=True
            )
            return

        removed = await farewell_repository.clear_farewell(
            self.bot.db, interaction.guild.id, interaction.user.id
        )
        text = "Đã xoá lời tạm biệt." if removed else "Bạn chưa có lời tạm biệt nào."
        await interaction.response.send_message(text, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FarewellCog(bot))