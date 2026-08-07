"""
Interface chung cho các dịch vụ hỏi đáp (QA) — áp dụng đúng Strategy pattern
đang dùng cho services/base.py (ImageService) sang tầng Q&A, để có thể cắm
nhiều nguồn trả lời (Gemini, Groq Compound, ...) và tự động fallback khi 1
nguồn bị rate limit / lỗi, thay vì phụ thuộc cứng vào 1 mình Gemini free tier
(vốn chỉ ~10 requests/phút, 250 requests/ngày — rất dễ nghẽn khi nhiều
người cùng hỏi).

Thêm 1 nguồn QA mới (vd sau này muốn thêm OpenRouter, Cerebras...):
1. Tạo file mới trong services/, kế thừa QAService, implement is_configured()
   + ask().
2. Thêm instance vào list truyền cho QAAggregator trong bot.py.
Không cần sửa gì trong cogs/ask.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class QAServiceError(Exception):
    """Lỗi chung khi gọi 1 QAService thất bại (rate limit, mất mạng, sai
    key, dữ liệu trả về không đúng định dạng...).

    QAAggregator bắt exception này (và thực tế là mọi Exception khác) để
    quyết định có fallback sang service tiếp theo hay không.
    """


class QAService(ABC):
    """Interface chung mọi dịch vụ hỏi đáp phải implement."""

    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        """True nếu đã có đủ API key/cấu hình cần thiết để gọi được service này."""
        raise NotImplementedError

    @abstractmethod
    async def ask(
        self,
        question: str,
        history: list[tuple[str, str]] | None = None,
    ) -> str:
        """Gửi câu hỏi, trả về câu trả lời dạng str.

        `history`: danh sách (question, answer) các lượt hỏi-đáp gần nhất
        của user (thứ tự cũ -> mới), để trả lời được câu hỏi nối tiếp.

        Ném QAServiceError (hoặc bất kỳ Exception nào) nếu gọi thất bại —
        QAAggregator sẽ bắt và thử service tiếp theo trong danh sách.
        """
        raise NotImplementedError