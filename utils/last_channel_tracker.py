"""Theo dõi kênh chat text gần nhất mà mỗi user đã nhắn tin, theo từng guild.

Chỉ giữ tạm trong RAM (giống cơ chế rating/trending hiện có của bot) —
không cần persist vì đây chỉ là gợi ý "kênh gần nhất", mất khi bot restart
là chấp nhận được (lúc đó fallback về None, cog sẽ tự bỏ qua hoặc dùng kênh
hệ thống tuỳ cấu hình).

Key: (guild_id, user_id) -> channel_id
"""

from typing import Optional


class LastChannelTracker:
    def __init__(self) -> None:
        self._store: dict[tuple[int, int], int] = {}

    def update(self, guild_id: int, user_id: int, channel_id: int) -> None:
        self._store[(guild_id, user_id)] = channel_id

    def get(self, guild_id: int, user_id: int) -> Optional[int]:
        return self._store.get((guild_id, user_id))