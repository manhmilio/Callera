"""
Quản lý cooldown per-user + cache câu trả lời cho tính năng hỏi đáp.

Mục đích: hạn mức free tier của Gemini khá thấp (vd gemini-2.5-flash chỉ
~10 requests/phút, 250 requests/ngày) — nếu nhiều người cùng hỏi dồn dập
trong server rất dễ bị lỗi 429. Class này giúp:
  1. Chặn spam: mỗi user chỉ được hỏi 1 câu / N giây.
  2. Cache: câu hỏi giống hệt nhau (đã chuẩn hoá) hỏi lại trong TTL sẽ trả
     lời ngay từ cache, không tốn thêm request tới Gemini.

Toàn bộ lưu tạm trong RAM, mất khi bot restart — chấp nhận được vì đây chỉ
là cơ chế tiết kiệm quota, không phải yêu cầu nghiệp vụ cần bền vững.
"""

from __future__ import annotations

import time

from utils.text import normalize_text


class QaRateLimiter:
    def __init__(
        self,
        user_cooldown_seconds: float = 10.0,
        cache_ttl_seconds: float = 600.0,
    ):
        self.user_cooldown_seconds = user_cooldown_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self._last_asked: dict[int, float] = {}
        self._answer_cache: dict[str, tuple[str, list[str], float]] = {}

    def is_on_cooldown(self, user_id: int) -> float | None:
        """Trả về số giây còn lại nếu đang cooldown, None nếu được phép hỏi."""
        last = self._last_asked.get(user_id)
        if last is None:
            return None
        remaining = self.user_cooldown_seconds - (time.monotonic() - last)
        return remaining if remaining > 0 else None

    def mark_asked(self, user_id: int) -> None:
        self._last_asked[user_id] = time.monotonic()

    def get_cached(self, question: str) -> tuple[str, list[str]] | None:
        key = normalize_text(question)
        entry = self._answer_cache.get(key)
        if entry is None:
            return None
        answer, sources, timestamp = entry
        if time.monotonic() - timestamp > self.cache_ttl_seconds:
            del self._answer_cache[key]
            return None
        return answer, sources

    def set_cached(self, question: str, answer: str, sources: list[str]) -> None:
        key = normalize_text(question)
        self._answer_cache[key] = (answer, sources, time.monotonic())