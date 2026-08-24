"""Quản lý kết nối SQLite dùng chung cho toàn bộ module database.

File .sqlite3 được lưu trong thư mục `data/` — thư mục này sẽ được mount qua
Docker volume để dữ liệu không mất khi container bị xoá/rebuild.

Chỉ dùng 1 connection dùng chung (aiosqlite), phù hợp với quy mô dữ liệu nhỏ
của bot (vài trăm/nghìn dòng lời tạm biệt), không cần connection pool phức tạp.
"""

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS farewell_messages (
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    message    TEXT    NOT NULL,
    updated_at TEXT    NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS study_reminder_config (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    reminder_channel_id INTEGER,
    audio_file_path     TEXT
);

CREATE TABLE IF NOT EXISTS personality_config (
    guild_id INTEGER PRIMARY KEY,
    persona  TEXT NOT NULL DEFAULT 'lao'
);

CREATE TABLE IF NOT EXISTS feature_config (
    guild_id INTEGER NOT NULL,
    feature_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (guild_id, feature_name)
);
"""


async def init_db(db_path: str) -> aiosqlite.Connection:
    """Mở kết nối SQLite tại `db_path`, tạo bảng nếu chưa tồn tại.

    Gọi 1 lần lúc khởi động bot (trong bot.py), gán vào `bot.db`, rồi truyền
    xuống cho các cog cần dùng qua `self.bot.db`.
    """
    conn = await aiosqlite.connect(db_path)
    await conn.executescript(_SCHEMA)
    await conn.commit()
    return conn


async def close_db(conn: aiosqlite.Connection) -> None:
    """Đóng kết nối lúc bot tắt (gọi trong on_close / signal handler nếu có)."""
    await conn.close()