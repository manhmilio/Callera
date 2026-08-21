"""
QAAggregator — cầm 1 danh sách QAService, thử LẦN LƯỢT theo đúng thứ tự
truyền vào (KHÔNG random như ImageAggregator của tầng ảnh) vì ở đây có 1
service chất lượng cao hơn muốn ưu tiên dùng trước (Gemini), và 1 service
chỉ đóng vai trò dự phòng khi service ưu tiên bị rate limit/lỗi (Groq
Compound).

Nếu service đầu tiên trong danh sách lỗi (rate limit, mất mạng, sai key...),
tự động thử service tiếp theo — người dùng trong Discord không biết/không
cần biết đang có chuyện fallback xảy ra phía sau.

Cách dùng (trong bot.py), theo đúng pattern của bot.image_aggregator:

    bot.qa_service = QAAggregator(services=[
        GeminiQAService(config.GEMINI_API_KEY),
        GroqCompoundQAService(config.GROQ_API_KEY),
    ])

cogs/ask.py gọi:

    await bot.qa_service.ask(question, history=history, system_prompt=system_prompt)

`system_prompt` (tính năng đổi persona) được truyền NGUYÊN VẸN xuống mọi
service con — kể cả khi Gemini lỗi và phải fallback sang Groq, service dự
phòng vẫn nhận đúng persona đang active cho guild đó, không bị "đổi giọng"
giữa chừng. Nếu không truyền (None), mỗi service tự fallback về persona
mặc định của riêng nó (xem services/qa_service.py, services/groq_qa_service.py).
"""

from __future__ import annotations

import logging

from services.qa_base import QAService, QAServiceError

logger = logging.getLogger(__name__)


class QAAggregator:
    def __init__(self, services: list[QAService]):
        self.services = services

    def available_services(self) -> list[QAService]:
        """Danh sách service đã được cấu hình đủ key, giữ nguyên thứ tự ưu tiên."""
        return [s for s in self.services if s.is_configured()]

    def is_configured(self) -> bool:
        """True nếu có ít nhất 1 service sẵn sàng dùng được."""
        return len(self.available_services()) > 0

    async def ask(
        self,
        question: str,
        history: list[tuple[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Thử từng service theo thứ tự ưu tiên, trả về câu trả lời của service
        đầu tiên thành công. Ném QAServiceError nếu không có service nào
        được cấu hình, hoặc tất cả service đều lỗi.

        `system_prompt`: truyền nguyên vẹn xuống mọi service con (xem
        docstring đầu file) — quyết định cá tính/giọng điệu trả lời theo
        persona đang được chọn (cogs/personality.py).
        """
        available = self.available_services()
        if not available:
            raise QAServiceError(
                "Không có QAService nào được cấu hình (thiếu hết API key: "
                "GEMINI_API_KEY, GROQ_API_KEY)."
            )

        last_error: Exception | None = None
        for service in available:
            try:
                return await service.ask(
                    question, history=history, system_prompt=system_prompt
                )
            except Exception as exc:  # noqa: BLE001 - cố ý bắt rộng để fallback
                logger.warning(
                    "QAService '%s' lỗi (%s) — thử service tiếp theo nếu còn.",
                    service.name,
                    exc,
                )
                last_error = exc
                continue

        raise QAServiceError(f"Tất cả QAService đều lỗi. Lỗi cuối cùng: {last_error}")