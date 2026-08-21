"""
GeminiQAService — dịch vụ hỏi đáp dùng Gemini API (SDK google-genai, KHÔNG
phải google-generativeai đã deprecated), kèm Google Search Grounding để câu
trả lời có thể tham chiếu thông tin mới nhất trên web thay vì chỉ dựa vào
dữ liệu huấn luyện tĩnh của model.

Bản cập nhật này: implement interface QAService (services/qa_base.py) để
có thể cắm vào QAAggregator cùng GroqCompoundQAService — khi Gemini bị rate
limit (free tier chỉ ~10 requests/phút, 250 requests/ngày) thì tự động
fallback sang Groq Compound thay vì báo lỗi luôn cho người dùng.

Bản cập nhật (tính năng đổi persona): KHÔNG còn giữ 1 bản cá tính
SYSTEM_INSTRUCTION hard-code cố định trong file này nữa. `ask()` giờ nhận
thêm tham số `system_prompt` — do cogs/ask.py truyền xuống theo persona
đang được chọn cho từng guild (xem cogs/personality.py, data/personas.py).
Nếu không truyền `system_prompt` (vd gọi trực tiếp service này để test),
tự fallback về persona mặc định ("lao") lấy từ data/personas.py — đảm bảo
hành vi không đổi nếu ai đó gọi ask() kiểu cũ mà quên truyền persona.

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

from data.personas import DEFAULT_PERSONA, get_persona
from services.qa_base import QAService, QAServiceError

# Fallback khi ask() không được truyền system_prompt — lấy từ persona mặc
# định trong data/personas.py, KHÔNG hard-code cá tính riêng ở đây nữa.
DEFAULT_SYSTEM_INSTRUCTION = get_persona(DEFAULT_PERSONA)["system_prompt"]

MAX_OUTPUT_TOKENS = 300  # giới hạn thêm để ép câu trả lời không bị dài dòng


class GeminiQAService(QAService):
    """Gọi Gemini API để trả lời 1 câu hỏi, có bật Google Search Grounding."""

    name = "Gemini"

    def __init__(self, api_key: str | None, model_name: str = "gemini-2.5-flash"):
        # Không raise nếu thiếu key nữa (khác bản trước) — để QAAggregator có
        # thể tự construct service này ngay cả khi chưa cấu hình, rồi tự bỏ
        # qua qua is_configured(), giống cách ImageService xử lý key rỗng.
        self.api_key = api_key
        self.model_name = model_name
        self.client = genai.Client(api_key=api_key) if api_key else None
        self._grounding_tool = types.Tool(google_search=types.GoogleSearch())

    def is_configured(self) -> bool:
        return self.client is not None

    async def ask(
        self,
        question: str,
        history: list[tuple[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Gửi câu hỏi tới Gemini, trả về câu trả lời (đã bỏ nguồn tham khảo).

        `history`: danh sách (question, answer) các lượt hỏi-đáp gần nhất
        của chính user đó (thứ tự cũ -> mới), lấy từ QaMemory bên ngoài, để
        model hiểu được câu hỏi nối tiếp (ví dụ "còn cái kia thì sao?").
        Bỏ trống hoặc None nếu không có/không cần ngữ cảnh trước.

        `system_prompt`: system instruction quyết định cá tính/giọng điệu
        trả lời — do cogs/ask.py truyền xuống theo persona đang chọn cho
        guild (xem cogs/personality.py). Nếu None, dùng
        DEFAULT_SYSTEM_INSTRUCTION (persona "lao" mặc định).

        Ném QAServiceError nếu chưa cấu hình key, hoặc để lỗi gốc của
        google-genai (hết quota, mất mạng, sai key...) bay lên nguyên vẹn —
        QAAggregator sẽ bắt mọi Exception để quyết định fallback.
        """
        if not self.is_configured():
            raise QAServiceError(
                "GeminiQAService chưa được cấu hình (thiếu GEMINI_API_KEY)."
            )

        config = types.GenerateContentConfig(
            tools=[self._grounding_tool],
            system_instruction=system_prompt or DEFAULT_SYSTEM_INSTRUCTION,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

        contents = self._build_contents(question, history)

        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
        )

        answer = (response.text or "").strip()
        if not answer:
            answer = "Hỏi cái kiểu gì mà tao không trả lời được vậy, hỏi lại đi."

        return answer

    @staticmethod
    def _build_contents(
        question: str, history: list[tuple[str, str]] | None
    ) -> list[types.Content]:
        """
        Dựng list `Content` nhiều lượt (multi-turn) từ history + câu hỏi
        hiện tại. Nếu không có history, kết quả chỉ gồm 1 lượt (tương đương
        gọi single-turn như cũ).
        """
        contents: list[types.Content] = []
        for past_question, past_answer in history or []:
            contents.append(
                types.Content(
                    role="user", parts=[types.Part(text=past_question)]
                )
            )
            contents.append(
                types.Content(role="model", parts=[types.Part(text=past_answer)])
            )
        contents.append(types.Content(role="user", parts=[types.Part(text=question)]))
        return contents