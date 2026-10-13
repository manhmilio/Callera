"""
GroqCompoundQAService — dịch vụ hỏi đáp dự phòng (fallback) dùng model
Compound của Groq (`groq/compound`). Model này có web search + code
execution tích hợp sẵn ngay bên trong, đóng vai trò tương tự Google Search
Grounding của Gemini, nhưng free tier rộng hơn hẳn (RPM/RPD cao hơn nhiều
lần so với Gemini Flash free tier — xem QAAggregator để biết cách 2 service
phối hợp).

Dùng khi nào: QAAggregator sẽ tự thử GeminiQAService trước (chất lượng cao
hơn), nếu Gemini bị rate limit (429) hoặc lỗi thì tự động fallback sang
service này — không cần AskCog biết chuyện đó xảy ra.

Cài đặt: KHÔNG cần thêm SDK mới. Gọi thẳng REST endpoint tương thích OpenAI
của Groq bằng `aiohttp` (thư viện đã có sẵn trong dự án), tránh phát sinh
dependency mới trong requirements.txt.

Biến môi trường cần có:
    GROQ_API_KEY - lấy miễn phí (không cần thẻ tín dụng) tại
    https://console.groq.com/keys

Lưu ý về free tier (tính đến giữa 2026, CHƯA kiểm chứng 100% cho riêng
model `groq/compound` — cần tự confirm lại trong Groq Console trước khi
build phụ thuộc cứng vào con số cụ thể, giống ghi chú đã làm với Gemini
image models trước đây):
- Free tier tổng quát của Groq: khoảng 30 requests/phút, hàng nghìn
  requests/ngày tuỳ model — cao hơn hẳn 10 RPM / 250 RPD của Gemini Flash.
- Nếu `groq/compound` không khả dụng hoặc đổi tên, thử `groq/compound-mini`
  (nhẹ hơn, nhanh hơn, ít tốn quota hơn) — chỉ cần đổi DEFAULT_MODEL bên
  dưới, không cần sửa gì khác.
"""

from __future__ import annotations

import aiohttp

from data.personas import DEFAULT_PERSONA, get_persona
from services.qa_base import QAService, QAServiceError

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "groq/compound"
MAX_TOKENS = 400
REQUEST_TIMEOUT_SECONDS = 30

# Fallback khi ask() không được truyền system_prompt (vd gọi trực tiếp
# service này để test). Trước đây file này hard-code sẵn 1 bản cá tính
# riêng, nhưng từ khi có tính năng đổi persona thì cá tính do cogs/ask.py
# truyền xuống — giữ bản hard-code chỉ làm 2 service lệch giọng nhau, nên
# lấy chung từ data/personas.py giống services/qa_service.py.
DEFAULT_SYSTEM_INSTRUCTION = get_persona(DEFAULT_PERSONA)["system_prompt"]


class GroqCompoundQAService(QAService):
    """Gọi Groq Compound (web search tích hợp sẵn) để trả lời 1 câu hỏi."""

    name = "Groq Compound"

    def __init__(self, api_key: str | None, model_name: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model_name = model_name

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def ask(
        self,
        question: str,
        history: list[tuple[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Gửi câu hỏi tới Groq Compound, trả về câu trả lời dạng str.

        `system_prompt`: persona đang active cho guild, do cogs/ask.py truyền
        xuống qua QAAggregator. Nếu None, dùng DEFAULT_SYSTEM_INSTRUCTION.

        Ném QAServiceError nếu chưa cấu hình key, bị rate limit, lỗi HTTP,
        hoặc dữ liệu trả về không đúng định dạng — QAAggregator bắt lỗi
        này để thử service tiếp theo (Vyce) nếu còn.
        """
        if not self.is_configured():
            raise QAServiceError(
                "GroqCompoundQAService chưa được cấu hình (thiếu GROQ_API_KEY)."
            )

        messages = self._build_messages(question, history, system_prompt)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": MAX_TOKENS,
        }

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                GROQ_API_URL, json=payload, headers=headers
            ) as resp:
                if resp.status == 429:
                    raise QAServiceError("Groq API bị rate limit (HTTP 429).")
                if resp.status != 200:
                    body = await resp.text()
                    raise QAServiceError(
                        f"Groq API trả lỗi HTTP {resp.status}: {body[:200]}"
                    )
                data = await resp.json()

        try:
            answer = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            raise QAServiceError(
                f"Groq API trả về dữ liệu không đúng định dạng: {exc}"
            ) from exc

        return answer or "Hỏi cái kiểu gì mà tao không trả lời được vậy, hỏi lại đi."

    @staticmethod
    def _build_messages(
        question: str,
        history: list[tuple[str, str]] | None,
        system_prompt: str | None,
    ) -> list[dict]:
        """Dựng list message theo format chat của OpenAI-compatible API."""
        messages: list[dict] = [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_INSTRUCTION}
        ]
        for past_question, past_answer in history or []:
            messages.append({"role": "user", "content": past_question})
            messages.append({"role": "assistant", "content": past_answer})
        messages.append({"role": "user", "content": question})
        return messages