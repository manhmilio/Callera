"""
GeminiQAService — dịch vụ hỏi đáp dùng Gemini API (SDK google-genai, KHÔNG
phải google-generativeai đã deprecated), kèm Google Search Grounding để câu
trả lời có thể tham chiếu thông tin mới nhất trên web thay vì chỉ dựa vào
dữ liệu huấn luyện tĩnh của model.

Cài đặt:
    pip install google-genai

Biến môi trường cần có:
    GEMINI_API_KEY - lấy miễn phí tại https://aistudio.google.com/apikey

Free tier (model gemini-2.5-flash, tính đến giữa 2026): khoảng 10
requests/phút, 250 requests/ngày. Nếu cần hạn mức cao hơn, đổi
model_name sang "gemini-2.5-flash-lite" (15 RPM / 1.000 requests/ngày,
chất lượng thấp hơn 1 chút).
"""

from __future__ import annotations

from google import genai
from google.genai import types


class GeminiQAService:
    """Gọi Gemini API để trả lời 1 câu hỏi, có bật Google Search Grounding."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError(
                "Thiếu GEMINI_API_KEY — không thể khởi tạo GeminiQAService."
            )
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self._grounding_tool = types.Tool(google_search=types.GoogleSearch())

    async def ask(self, question: str) -> tuple[str, list[str]]:
        """
        Gửi câu hỏi tới Gemini, trả về (câu trả lời, danh sách nguồn tham khảo).

        Ném exception nếu gọi API lỗi (hết quota, mất mạng, sai key...) —
        cog gọi hàm này cần tự bắt exception để báo người dùng phù hợp.
        """
        config = types.GenerateContentConfig(tools=[self._grounding_tool])
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=question,
            config=config,
        )

        answer = (response.text or "").strip()
        if not answer:
            answer = "Xin lỗi, mình không tạo được câu trả lời cho câu hỏi này."

        sources = self._extract_sources(response)
        return answer, sources

    @staticmethod
    def _extract_sources(response) -> list[str]:
        """Lấy tối đa 3 link nguồn từ grounding_metadata (nếu Gemini có search)."""
        sources: list[str] = []
        try:
            candidate = response.candidates[0]
            chunks = candidate.grounding_metadata.grounding_chunks or []
            for chunk in chunks:
                web = getattr(chunk, "web", None)
                uri = getattr(web, "uri", None) if web else None
                if uri and uri not in sources:
                    sources.append(uri)
                if len(sources) >= 3:
                    break
        except (AttributeError, IndexError, TypeError):
            # Không có grounding_metadata (câu hỏi không cần search) — bỏ qua.
            pass
        return sources