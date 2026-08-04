"""
cogs/study_reminder.py

Nhắc nhở học tập khi user chơi game liên tục quá 1 tiếng.

Luồng hoạt động:
1. on_presence_update: phát hiện lúc 1 activity kiểu "Playing" xuất hiện/biến mất
   khỏi member.activities -> mở/đóng 1 "phiên chơi game" trong utils.playtime_tracker.
2. Task chạy mỗi 5 phút (check_playtime): duyệt các phiên đang mở, nếu phiên nào
   đã chơi liên tục >= 1 tiếng và CHƯA được nhắc, thì:
     - User đang ở trong 1 kênh voice -> bot join kênh đó, phát file audio đã
       cấu hình sẵn (dùng chung cho mọi người, admin upload qua /set_study_audio).
     - User không ở voice nào -> tag @user kèm lời nhắc vào kênh chat chung
       (admin cấu hình qua /set_reminder_channel).
3. Mỗi phiên chỉ nhắc đúng 1 lần (đánh dấu session["reminded"] = True).
   Thoát game rồi chơi lại (cùng game hay game khác) = phiên mới -> nhắc lại được.

Yêu cầu thêm so với các cog khác:
- Cần bật thêm intents.voice_states = True (bên cạnh intents.presences,
  intents.members đã bật cho tính năng detect activity) trong bot.py, để
  member.voice.channel đọc được chính xác.
- Cần cài `PyNaCl` (pip install PyNaCl) để discord.py hỗ trợ voice.
- Cần cài đặt FFmpeg ở máy chạy bot (không phải pip package — cài qua hệ
  điều hành, vd `apt install ffmpeg` trên Ubuntu) để phát được file audio.
- bot.db (kết nối SQLite) phải đã được gán sẵn trước khi cog này load,
  giống cách farewell cog đang dùng.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db.study_reminder_repository import get_config, set_reminder_channel, set_audio_path
from utils.playtime_tracker import active_sessions, start_session, end_session

logger = logging.getLogger(__name__)

STUDY_REMINDER_THRESHOLD = timedelta(hours=1)
CHECK_INTERVAL_MINUTES = 5
ALLOWED_AUDIO_EXT = (".mp3", ".wav", ".ogg", ".m4a")
REMINDER_TEXT = (
    "⏰ Bạn đã chơi game liên tục hơn 1 tiếng rồi đó! "
    "Nghỉ tay chút và dành thời gian học bài nhé 📚"
)


def _playing_game_names(member: discord.Member) -> set[str]:
    """Tập tên các activity kiểu 'Playing' hiện tại của 1 member."""
    return {
        activity.name
        for activity in member.activities
        if activity.type == discord.ActivityType.playing and activity.name
    }


class StudyReminderCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_playtime.start()

    def cog_unload(self):
        self.check_playtime.cancel()

    # ------------------------------------------------------------------
    # Theo dõi bắt đầu / kết thúc phiên chơi game
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if after.bot:
            return

        before_games = _playing_game_names(before)
        after_games = _playing_game_names(after)

        # Game mới xuất hiện trong activities -> mở phiên mới
        for game in after_games - before_games:
            start_session(after.id, game)
            logger.info(f"[study_reminder] {after} bắt đầu chơi: {game}")

        # Game vừa biến mất khỏi activities -> đóng phiên tương ứng
        for game in before_games - after_games:
            session = active_sessions.get(after.id)
            if session and session["game"] == game:
                end_session(after.id)
                logger.info(f"[study_reminder] {after} dừng chơi: {game}")

    # ------------------------------------------------------------------
    # Task định kỳ kiểm tra thời lượng chơi
    # ------------------------------------------------------------------
    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_playtime(self):
        now = datetime.now(timezone.utc)

        # Duyệt trên bản copy vì end_session() có thể làm thay đổi dict
        # ngay trong lúc đang loop (user thoát game giữa chừng).
        for user_id, session in list(active_sessions.items()):
            if session["reminded"]:
                continue
            if now - session["start"] < STUDY_REMINDER_THRESHOLD:
                continue

            await self._send_reminder(user_id, session["game"])
            session["reminded"] = True

    @check_playtime.before_loop
    async def before_check_playtime(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Gửi nhắc nhở: join voice phát audio, hoặc tag vào kênh chat chung
    # ------------------------------------------------------------------
    async def _send_reminder(self, user_id: int, game_name: str):
        member = self._find_member(user_id)
        if member is None:
            return

        if member.voice and member.voice.channel:
            await self._remind_via_voice(member)
        else:
            await self._remind_via_text(member)

    def _find_member(self, user_id: int) -> discord.Member | None:
        for guild in self.bot.guilds:
            member = guild.get_member(user_id)
            if member:
                return member
        return None

    async def _remind_via_voice(self, member: discord.Member):
        config = await get_config(self.bot.db)
        audio_path = config.get("audio_file_path")

        if not audio_path or not os.path.exists(audio_path):
            logger.warning(
                "[study_reminder] Chưa cấu hình audio hoặc file không tồn tại "
                "-> fallback sang nhắc bằng text."
            )
            await self._remind_via_text(member)
            return

        channel = member.voice.channel
        voice_client = None
        try:
            voice_client = await channel.connect()
            voice_client.play(discord.FFmpegPCMAudio(audio_path))

            while voice_client.is_playing():
                await discord.utils.sleep_until(
                    discord.utils.utcnow() + timedelta(seconds=1)
                )
        except Exception:
            logger.exception(
                f"[study_reminder] Lỗi khi phát audio nhắc nhở trong voice cho {member}"
            )
        finally:
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()

    async def _remind_via_text(self, member: discord.Member):
        config = await get_config(self.bot.db)
        channel_id = config.get("reminder_channel_id")

        if not channel_id:
            logger.warning(
                "[study_reminder] Chưa cấu hình kênh nhắc nhở (dùng /set_reminder_channel)."
            )
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            logger.warning(f"[study_reminder] Không tìm thấy kênh id={channel_id}")
            return

        await channel.send(f"{member.mention} {REMINDER_TEXT}")

    # ------------------------------------------------------------------
    # Slash commands cấu hình (chỉ admin)
    # ------------------------------------------------------------------
    @app_commands.command(
        name="set_reminder_channel",
        description="Đặt kênh chat chung để tag nhắc nhở học tập",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_reminder_channel_cmd(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        await set_reminder_channel(self.bot.db, channel.id)
        await interaction.response.send_message(
            f"✅ Đã đặt kênh nhắc nhở học tập: {channel.mention}", ephemeral=True
        )

    @app_commands.command(
        name="set_study_audio",
        description="Tải lên file audio phát khi bot vào voice nhắc nhở học tập",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def set_study_audio_cmd(
        self, interaction: discord.Interaction, file: discord.Attachment
    ):
        if not file.filename.lower().endswith(ALLOWED_AUDIO_EXT):
            await interaction.response.send_message(
                f"❌ Định dạng file không hỗ trợ. Vui lòng dùng: {', '.join(ALLOWED_AUDIO_EXT)}",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        os.makedirs("data", exist_ok=True)
        ext = os.path.splitext(file.filename)[1]
        save_path = f"data/study_reminder_audio{ext}"

        await file.save(save_path)
        await set_audio_path(self.bot.db, save_path)

        await interaction.followup.send(
            f"✅ Đã lưu file audio nhắc nhở: `{file.filename}`", ephemeral=True
        )

    @set_reminder_channel_cmd.error
    @set_study_audio_cmd.error
    async def _admin_only_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Lệnh này chỉ dành cho admin.", ephemeral=True
            )
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(StudyReminderCog(bot))