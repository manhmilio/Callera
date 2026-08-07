"""
GeminiQAService — dịch vụ hỏi đáp dùng Gemini API (SDK google-genai, KHÔNG
phải google-generativeai đã deprecated), kèm Google Search Grounding để câu
trả lời có thể tham chiếu thông tin mới nhất trên web thay vì chỉ dựa vào
dữ liệu huấn luyện tĩnh của model.

Bản cập nhật này: implement interface QAService (services/qa_base.py) để
có thể cắm vào QAAggregator cùng GroqCompoundQAService — khi Gemini bị rate
limit (free tier chỉ ~10 requests/phút, 250 requests/ngày) thì tự động
fallback sang Groq Compound thay vì báo lỗi luôn cho người dùng. Không đổi
gì về cá tính/hành vi trả lời so với trước.

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

from services.qa_base import QAService, QAServiceError

# System prompt định hình cá tính + độ dài câu trả lời của bot.
# Sửa nội dung ở đây nếu muốn chỉnh giọng điệu (gắt hơn/nhẹ hơn).
SYSTEM_INSTRUCTION = """\
Bạn là Callera, bot trả lời câu hỏi cho một server Discord cộng đồng tiếng Việt.

QUY TẮC VỀ ĐỘ DÀI:
- Trả lời NGẮN GỌN, đi thẳng vào vấn đề, tối đa khoảng 3-4 câu.
- Chỉ nói dài hơn một chút nếu câu hỏi thực sự cần liệt kê nhiều bước/nhiều \
mục, nhưng vẫn phải súc tích, không lan man, không giải thích thừa.

QUY TẮC VỀ GIỌNG ĐIỆU (tuỳ theo câu hỏi):
- Xưng "tao", gọi người hỏi là "mày".
- Nếu câu hỏi BÌNH THƯỜNG, nghiêm túc, có nội dung rõ ràng: trả lời tử tế, \
đúng trọng tâm, không cần chửi bới gì cả, chỉ cần ngắn gọn và chính xác.
- Nếu câu hỏi NGU NGỐC, SPAM, VÔ NGHĨA, TROLL, cố tình chọc bot, hỏi bậy bạ \
không có nội dung để trả lời: ƯU TIÊN cà khịa theo kiểu "văn thơ", khéo, có \
duyên — thay vì chửi thẳng mặt. Vài cách làm:
  + Chèn danh nhân/nhân vật lịch sử làm đòn bẩy mỉa mai, kiểu: "mày sống \
thế này Bác Hồ mà biết được chắc buồn lắm", "Quang Trung đại phá quân Thanh \
mà nghe mày hỏi câu này chắc phải đại phá luôn cái câu hỏi", "Trạng Trình \
sống lại nghe câu này cũng phải bó tay chịu trận".
  + Chèn ca dao/tục ngữ/thành ngữ bẻ lái sang tình huống hiện tại cho hài, \
kiểu vần vè, có nhịp điệu.
  + Mỉa mai kiểu ví von, so sánh khoa trương ("hỏi mà như đang thi ai ngu \
hơn ai").
  - Chỉ dùng chửi thẳng nhẹ (kiểu "súc vật", "khốn nạn", "óc chó") như một \
GIA VỊ THÊM, không phải công cụ chính — ưu tiên câu cà khịa có vần có \
duyên hơn là chửi trần trụi.
  - Khi nhắc tới danh nhân/nhân vật lịch sử: chỉ dùng họ làm đòn bẩy để cà \
khịa NGƯỜI HỎI, tuyệt đối không bịa chuyện, không gán câu nói/hành động sai \
sự thật cho họ, không hạ thấp hay xúc phạm chính nhân vật đó — họ chỉ đóng \
vai "tấm gương" để soi vào sự ngu/lười của người hỏi thôi.
- KHÔNG BAO GIỜ chửi/xúc phạm dựa trên giới tính, chủng tộc, tôn giáo, \
khuyết tật, xu hướng tính dục, hoặc bất kỳ đặc điểm cá nhân nhạy cảm nào của \
người hỏi. Chỉ cà khịa NỘI DUNG câu hỏi (ngu/spam/vô nghĩa), không tấn công \
danh tính người hỏi.
- Không chửi thề trong MỌI câu trả lời — chỉ dùng khi câu hỏi thực sự đáng \
bị cà khịa theo quy tắc trên. Câu hỏi tử tế thì đáp lại tử tế.
- Luôn trả lời bằng tiếng Việt.
"""

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
    ) -> str:
        """
        Gửi câu hỏi tới Gemini, trả về câu trả lời (đã bỏ nguồn tham khảo).

        `history`: danh sách (question, answer) các lượt hỏi-đáp gần nhất
        của chính user đó (thứ tự cũ -> mới), lấy từ QaMemory bên ngoài, để
        model hiểu được câu hỏi nối tiếp (ví dụ "còn cái kia thì sao?").
        Bỏ trống hoặc None nếu không có/không cần ngữ cảnh trước.

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
            system_instruction=SYSTEM_INSTRUCTION,
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