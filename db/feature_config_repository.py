"""
db/feature_config_repository.py

CRUD cho bảng feature_config — bật/tắt các tính năng tự động (farewell,
study_reminder) theo TỪNG SERVER (guild), theo đúng pattern per-guild đã
dùng cho personality_config.

Nếu guild chưa từng cấu hình 1 feature nào đó -> mặc định BẬT (giữ nguyên
hành vi hiện có, tránh phá server đang chạy khi mới thêm tính năng này).

Cần thêm đoạn CREATE TABLE sau vào db/connection.py (cạnh các bảng khác,
trong cùng khối _SCHEMA chạy qua conn.executescript()):

    CREATE TABLE IF NOT EXISTS feature_config (
        guild_id INTEGER NOT NULL,
        feature_name TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (guild_id, feature_name)
    );
"""

import aiosqlite

_TABLE = "feature_config"
DEFAULT_ENABLED = True


async def is_feature_enabled(db: aiosqlite.Connection, guild_id: int, feature_name: str) -> bool:
    async with db.execute(
        f"SELECT enabled FROM {_TABLE} WHERE guild_id = ? AND feature_name = ?",
        (guild_id, feature_name),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return DEFAULT_ENABLED
    return bool(row[0])


async def set_feature_enabled(
    db: aiosqlite.Connection, guild_id: int, feature_name: str, enabled: bool
) -> None:
    await db.execute(
        f"""
        INSERT INTO {_TABLE} (guild_id, feature_name, enabled)
        VALUES (?, ?, ?)
        ON CONFLICT(guild_id, feature_name) DO UPDATE SET enabled = excluded.enabled
        """,
        (guild_id, feature_name, int(enabled)),
    )
    await db.commit()