"""
db/study_reminder_repository.py

CRUD cho cấu hình module nhắc nhở học tập. Lưu dạng 1 dòng duy nhất
(id = 1) trong bảng study_reminder_config — vì đây là cấu hình chung
cho cả bot (1 kênh nhắc nhở + 1 file audio dùng chung), không cần
nhiều dòng.

Cần thêm đoạn CREATE TABLE sau vào db/connection.py (trong hàm init_db,
cạnh chỗ tạo bảng farewell_messages):

    CREATE TABLE IF NOT EXISTS study_reminder_config (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        reminder_channel_id INTEGER,
        audio_file_path TEXT
    );
"""

import aiosqlite

_TABLE = "study_reminder_config"


async def get_config(db: aiosqlite.Connection) -> dict:
    """Trả về {'reminder_channel_id': int|None, 'audio_file_path': str|None}."""
    async with db.execute(
        f"SELECT reminder_channel_id, audio_file_path FROM {_TABLE} WHERE id = 1"
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return {"reminder_channel_id": None, "audio_file_path": None}

    return {"reminder_channel_id": row[0], "audio_file_path": row[1]}


async def set_reminder_channel(db: aiosqlite.Connection, channel_id: int) -> None:
    await db.execute(
        f"""
        INSERT INTO {_TABLE} (id, reminder_channel_id)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET reminder_channel_id = excluded.reminder_channel_id
        """,
        (channel_id,),
    )
    await db.commit()


async def set_audio_path(db: aiosqlite.Connection, path: str) -> None:
    await db.execute(
        f"""
        INSERT INTO {_TABLE} (id, audio_file_path)
        VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET audio_file_path = excluded.audio_file_path
        """,
        (path,),
    )
    await db.commit()