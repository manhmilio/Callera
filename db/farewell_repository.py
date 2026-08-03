"""Truy vấn CRUD cho bảng `farewell_messages`.

Tách riêng khỏi cog để cog chỉ lo phần Discord (event, slash command), còn
file này chỉ lo phần dữ liệu — giống tinh thần tách `services/` khỏi `cogs/`
ở phần lấy ảnh.
"""

from datetime import datetime, timezone

import aiosqlite


async def get_farewell(
    conn: aiosqlite.Connection, guild_id: int, user_id: int
) -> str | None:
    """Trả về nội dung lời tạm biệt đã set, hoặc None nếu user chưa set."""
    async with conn.execute(
        "SELECT message FROM farewell_messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ) as cursor:
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_farewell(
    conn: aiosqlite.Connection, guild_id: int, user_id: int, message: str
) -> None:
    """Tạo mới hoặc cập nhật lời tạm biệt của user trong 1 guild cụ thể."""
    now = datetime.now(timezone.utc).isoformat()
    await conn.execute(
        """
        INSERT INTO farewell_messages (guild_id, user_id, message, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (guild_id, user_id)
        DO UPDATE SET message = excluded.message, updated_at = excluded.updated_at
        """,
        (guild_id, user_id, message, now),
    )
    await conn.commit()


async def clear_farewell(conn: aiosqlite.Connection, guild_id: int, user_id: int) -> bool:
    """Xoá lời tạm biệt của user. Trả về True nếu có dòng bị xoá."""
    cursor = await conn.execute(
        "DELETE FROM farewell_messages WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    await conn.commit()
    return cursor.rowcount > 0