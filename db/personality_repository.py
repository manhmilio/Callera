"""
CRUD cho bảng personality_config — lưu tính cách bot đang chọn theo từng guild.

Tái dùng kết nối SQLite chung (bot.db), theo đúng pattern của
db/farewell_repository.py và db/study_reminder_repository.py đã có sẵn.
"""

from data.personas import DEFAULT_PERSONA


async def get_persona_key(db, guild_id: int) -> str:
    """Lấy persona key hiện tại của guild. Trả về DEFAULT_PERSONA nếu chưa từng set."""
    async with db.execute(
        "SELECT persona FROM personality_config WHERE guild_id = ?", (guild_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row else DEFAULT_PERSONA


async def set_persona_key(db, guild_id: int, persona: str) -> None:
    await db.execute(
        """
        INSERT INTO personality_config (guild_id, persona)
        VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET persona = excluded.persona
        """,
        (guild_id, persona),
    )
    await db.commit()