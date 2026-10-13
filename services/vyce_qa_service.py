"""
VyceQAService — dịch vụ hỏi đáp DỰ PHÒNG CUỐI CÙNG, gọi model DeepSeek qua
Vyce AI (https://vyceai.com) — một API proxy tương thích OpenAI, cho phép
dùng nhiều model (DeepSeek, Claude, GPT, GLM...) qua 1 key duy nhất.

Vị trí trong chuỗi fallback (xem bot.py): Gemini -> Groq Compound -> Vyce.
Cố ý đặt CUỐI CÙNG vì khác với 2 nguồn trên (free tier), Vyce tính tiền
theo credit — chỉ nên tiêu credit khi cả 2 nguồn miễn phí đều đã chết
(hết quota/lỗi), không phải mặc định cho mọi câu hỏi.

Khác biệt so với 2 service kia, cần biết trước khi phụ thuộc vào nó:
- KHÔNG có web search tích hợp. Gemini có Google Search Grounding, Groq
  Compound có web search + code execution built-in; model DeepSeek qua Vyce
  chỉ trả lời bằng dữ liệu huấn luyện tĩnh. Câu hỏi về tin tức/sự kiện mới
  sẽ kém chính xác hơn hẳn khi rơi xuống tầng fallback này.
- Là proxy BÊN THỨ BA: câu hỏi của member đi qua server của họ. Đừng đẩy
  dữ liệu nhạy cảm qua đây.

Cài đặt: KHÔNG cần thêm SDK mới. Gọi thẳng REST endpoint tương thích OpenAI
bằng `aiohttp` (đã có sẵn trong dự án), giống hệt cách
services/groq_qa_service.py đang làm.

Biến môi trường cần có:
    VYCE_API_KEY - lấy tại https://vyceai.com (có credit miễn phí khi đăng ký)

Model: mặc định `deepseek-v4-flash` (context 270k, nhanh/rẻ). Muốn đổi sang
bản mạnh hơn thì truyền `model_name="deepseek-v4.1"` lúc khởi tạo trong
bot.py, không cần sửa file này. Danh sách model khả dụng có thể tự kiểm tra
bằng `GET https://vyceai.com/v1/models` với cùng API key.
"""

from __future__ import annotations

import aiohttp

from data.personas import DEFAULT_PERSONA, get_persona
from services.qa_base import QAService, QAServiceError

VYCE_API_URL = "https://vyceai.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"
MAX_TOKENS = 400
REQUEST_TIMEOUT_SECONDS = 30

# Fallback khi ask() không được truyền system_prompt (vd gọi trực tiếp
# service này để test) — lấy từ persona mặc định trong data/personas.py,
# KHÔNG hard-code cá tính riêng ở đây, để 3 service luôn cùng 1 giọng.
DEFAULT_SYSTEM_INSTRUCTION = get_persona(DEFAULT_PERSONA)["system_prompt"]


class VyceQAService(QAService):
    """Gọi model DeepSeek qua Vyce AI (OpenAI-compatible) để trả lời 1 câu hỏi."""

    name = "Vyce (DeepSeek)"

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
        Gửi câu hỏi tới Vyce AI, trả về câu trả lời dạng str.

        `system_prompt`: persona đang active cho guild, do cogs/ask.py truyền
        xuống qua QAAggregator. Nếu None, dùng DEFAULT_SYSTEM_INSTRUCTION.

        Ném QAServiceError nếu chưa cấu hình key, bị rate limit, hết credit,
        lỗi HTTP, hoặc dữ liệu trả về không đúng định dạng — vì đây là
        service cuối cùng trong danh sách, lỗi ở đây đồng nghĩa QAAggregator
        đã hết đường fallback và sẽ báo lỗi ra cho người dùng.
        """
        if not self.is_configured():
            raise QAServiceError(
                "VyceQAService chưa được cấu hình (thiếu VYCE_API_KEY)."
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
                VYCE_API_URL, json=payload, headers=headers
            ) as resp:
                if resp.status == 429:
                    raise QAServiceError("Vyce API bị rate limit (HTTP 429).")
                if resp.status in (401, 402, 403):
                    # Tách riêng nhóm này ra khỏi lỗi HTTP chung vì nguyên nhân
                    # thường là sai key hoặc HẾT CREDIT (Vyce tính tiền, khác
                    # free tier của Gemini/Groq) — đọc log sẽ biết ngay cần nạp
                    # tiền chứ không phải lỗi mạng tạm thời.
                    body = await resp.text()
                    raise QAServiceError(
                        f"Vyce API từ chối (HTTP {resp.status} — sai key hoặc "
                        f"hết credit): {body[:200]}"
                    )
                if resp.status != 200:
                    body = await resp.text()
                    raise QAServiceError(
                        f"Vyce API trả lỗi HTTP {resp.status}: {body[:200]}"
                    )
                data = await resp.json()

        try:
            answer = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, AttributeError, TypeError) as exc:
            raise QAServiceError(
                f"Vyce API trả về dữ liệu không đúng định dạng: {exc}"
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
