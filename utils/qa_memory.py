"""
QaMemory — lưu tạm lịch sử hỏi-đáp (memory ngắn hạn) theo từng user, giúp
tính năng hỏi đáp (@Callera) trả lời được câu hỏi nối tiếp (ví dụ: "còn cái
kia thì sao?", "vậy so với X thì thế nào?") mà không cần người dùng lặp lại
toàn bộ ngữ cảnh.

Thiết kế theo đúng pattern đã dùng ở utils/playtime_tracker.py và
utils/last_channel_tracker.py: chỉ lưu trong RAM, KHÔNG lưu SQLite/file —
mất khi bot restart là chấp nhận được vì đây chỉ là ngữ cảnh hội thoại tạm
thời, không phải dữ liệu cần giữ lâu dài.

Quy tắc quên (2 điều kiện, cái nào tới trước thì áp dụng):
- Chỉ giữ tối đa `max_turns` lượt hỏi-đáp gần nhất mỗi user (mặc định 5).
- Tự xoá toàn bộ lịch sử của user nếu quá `ttl_seconds` không hỏi tiếp câu
  nào (mặc định 900s = 15 phút).
"""

from __future__ import annotations

import time
from collections import deque


class QaMemory:
    def __init__(self, max_turns: int = 5, ttl_seconds: float = 900.0):
        self.max_turns = max_turns
        self.ttl_seconds = ttl_seconds
        # user_id -> {"turns": deque[(question, answer)], "last_active": float}
        self._store: dict[int, dict] = {}

    def get_history(self, user_id: int) -> list[tuple[str, str]]:
        """
        Trả về lịch sử (question, answer) gần nhất của user, theo thứ tự cũ
        -> mới. Nếu đã hết hạn (quá ttl_seconds không hỏi tiếp), tự xoá và
        trả về [] (coi như quên sạch, hỏi lại từ đầu).
        """
        entry = self._store.get(user_id)
        if entry is None:
            return []

        if time.monotonic() - entry["last_active"] > self.ttl_seconds:
            del self._store[user_id]
            return []

        return list(entry["turns"])

    def add_turn(self, user_id: int, question: str, answer: str) -> None:
        """Ghi thêm 1 lượt hỏi-đáp vào lịch sử của user, cập nhật thời gian."""
        entry = self._store.get(user_id)
        if entry is None:
            entry = {"turns": deque(maxlen=self.max_turns), "last_active": 0.0}
            self._store[user_id] = entry

        entry["turns"].append((question, answer))
        entry["last_active"] = time.monotonic()

    def clear(self, user_id: int) -> bool:
        """Xoá lịch sử của user (dùng cho lệnh /quen_di). Trả về True nếu có gì để xoá."""
        return self._store.pop(user_id, None) is not None