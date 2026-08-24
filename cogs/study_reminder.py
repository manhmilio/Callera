"""
cogs/study_reminder.py

Nhắc nhở học tập khi user chơi game liên tục (đã gộp các khoảng nghỉ ngắn
<=10 phút) quá 1 tiếng THỜI GIAN CHƠI THỰC.

Luồng hoạt động:
1. on_presence_update: phát hiện activity "Playing" xuất hiện/biến mất khỏi
   member.activities -> gọi utils.playtime_tracker để mở/tạm dừng/tiếp tục
   phiên chơi. Nếu user dừng rồi chơi lại trong vòng 10 phút, phiên được
   GỘP LẠI (không reset thời gian đã tích luỹ) — vì một số game có ngắt
   nghỉ giữa chừng (loading, chuyển màn, thoát vào menu...) không nên bị
   tính là "đã ngừng chơi".
2. Task chạy mỗi 5 phút (check_playtime): duyệt các phiên đang mở, nếu tổng
   thời gian chơi thực >= 1 tiếng và CHƯA được nhắc, thì gửi nhắc nhở (nếu
   tính năng đang BẬT cho server đó — xem cogs/feature_toggle.py). Đồng
   thời dọn các phiên đã nghỉ quá 10 phút (coi như kết thúc hẳn).
3. Mỗi phiên (đã gộp) chỉ nhắc đúng 1 lần. Nghỉ quá 10 phút rồi chơi lại =
   phiên mới -> nhắc lại được từ đầu.

Yêu cầu thêm so với các cog khác:
- intents.presences, intents.members, intents.voice_states phải bật (đã
  cấu hình trong bot.py).
- Cần cài `davey` (không phải `PyNaCl`/`dave.py`) để hỗ trợ voice + DAVE.
- Cần cài FFmpeg ở máy chạy bot.
- bot.db (kết nối SQLite) phải đã được gán sẵn trước khi cog này load.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks

from db.study_reminder_repository import get_config, set_reminder_channel, set_audio_path
from db import feature_config_repository
from utils.playtime_tracker import (
    active_sessions,
    start_or_resume_session,
    pause_session,
    update_game_name,
    get_total_playtime,
    is_expired,
    clear_session,
)

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
    # Theo dõi bắt đầu / tạm dừng / tiếp tục phiên chơi game
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if after.bot:
            return

        before_games = _playing_game_names(before)
        after_games = _playing_game_names(after)

        was_playing = bool(before_games)
        now_playing = bool(after_games)

        if now_playing and not was_playing:
            # Bắt đầu chơi (hoặc chơi lại sau khi nghỉ ngắn -> tự động gộp)
            game_name = next(iter(after_games))
            start_or_resume_session(after.id, game_name)
            logger.info(f"[study_reminder] {after} bắt đầu/tiếp tục chơi: {game_name}")
        elif was_playing and not now_playing:
            # Dừng chơi -> vào trạng thái chờ gộp (tối đa 10 phút)
            pause_session(after.id)
            logger.info(f"[study_reminder] {after} tạm dừng chơi (chờ gộp tối đa 10 phút)")
        elif now_playing and was_playing:
            # Vẫn đang chơi nhưng đổi game -> chỉ cập nhật tên hiển thị,
            # KHÔNG reset thời gian đã tích luỹ (vẫn tính là chơi liên tục).
            game_name = next(iter(after_games))
            update_game_name(after.id, game_name)

    # ------------------------------------------------------------------
    # Task định kỳ kiểm tra thời lượng chơi
    # ------------------------------------------------------------------
    @tasks.loop(minutes=CHECK_INTERVAL_MINUTES)
    async def check_playtime(self):
        now = datetime.now(timezone.utc)

        # Duyệt trên bản copy vì pause_session()/clear_session() có thể làm
        # thay đổi dict ngay trong lúc đang loop.
        for user_id, session in list(active_sessions.items()):
            if is_expired(session, now):
                # Đã nghỉ quá 10 phút -> coi như kết thúc phiên thật sự
                clear_session(user_id)
                continue

            if session["reminded"]:
                continue

            if get_total_playtime(user_id) < STUDY_REMINDER_THRESHOLD:
                continue

            sent = await self._send_reminder(user_id, session["game"])
            if sent:
                session["reminded"] = True

    @check_playtime.before_loop
    async def before_check_playtime(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Gửi nhắc nhở: join voice phát audio, hoặc tag vào kênh chat chung
    # ------------------------------------------------------------------
    async def _send_reminder(self, user_id: int, game_name: str) -> bool:
        member = self._find_member(user_id)
        if member is None:
            return False

        enabled = await feature_config_repository.is_feature_enabled(
            self.bot.db, member.guild.id, "study_reminder"
        )
        if not enabled:
            return False

        if member.voice and member.voice.channel:
            await self._remind_via_voice(member)
        else:
            await self._remind_via_text(member)
        return True

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