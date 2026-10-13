"""
VyceImageService — tạo ảnh từ prompt bằng model `grok-imagine-2` qua Vyce AI
(endpoint `/v1/images/generations`, tương thích chuẩn OpenAI Images API).

Dùng cho cogs/gen_image.py (`/gen_img`). KHÁC HẲN tầng ảnh cũ
(services/aggregator.py + Unsplash/Pexels/Pixabay): tầng kia TÌM ảnh có sẵn
trong kho miễn phí, tầng này SINH ảnh mới và TỐN TIỀN mỗi lần gọi — nên cố ý
tách riêng, không nhét vào ImageAggregator, để không bao giờ bị gọi nhầm bởi
/photo, /random_photo, nút "Ảnh khác"...

Cài đặt: không cần SDK mới, gọi REST bằng `aiohttp` như các service khác.

Biến môi trường cần có:
    VYCE_API_KEY - dùng chung với services/vyce_qa_service.py (cùng 1 key).

Những điểm đã kiểm chứng thực tế bằng cách gọi thẳng API (tháng 10/2026),
ghi lại ở đây để sau này không phải dò lại:
- Response thành công: {"created": ..., "data": [{"url": ..., "revised_prompt": ...}]}
- Ảnh trả về là URL public trên vyceai.com (tải được không cần auth), JPEG,
  cỡ ~400KB. KHÔNG rõ URL sống được bao lâu -> cogs/gen_image.py tải về rồi
  upload thẳng lên Discord thay vì chỉ embed URL, để ảnh không chết sau này.
- Thời gian sinh ảnh: ~13-19 giây -> BẮT BUỘC defer() interaction trước khi gọi.
- Tham số `model` thực tế bị server BỎ QUA (gửi "deepseek-v4-flash" vào
  endpoint này nó vẫn trả về ảnh grok). Vẫn gửi đúng tên model cho tường
  minh, nhưng đừng tin là đổi model ở đây sẽ đổi được engine.
- CHƯA xác minh được response lúc bị kiểm duyệt chặn trông thế nào: prompt
  thử nghiệm vô hại (nhân vật Disney có bản quyền) vẫn sinh ảnh bình thường,
  mà không đáng để gửi prompt thật sự độc hại chỉ để dò format. Vì vậy
  _raise_for_error() dưới đây nhận diện "bị chặn" bằng TỪ KHOÁ trong message
  trả về, và luôn có nhánh fallback hiển thị nguyên văn lỗi của API — nếu
  sau này thấy bot báo sai loại lỗi, sửa BLOCKED_KEYWORDS là đủ.
"""

from __future__ import annotations

from dataclasses import dataclass

import aiohttp

VYCE_IMAGE_API_URL = "https://vyceai.com/v1/images/generations"
DEFAULT_MODEL = "grok-imagine-2"
# Sinh ảnh mất ~13-19s, để rộng tay phòng lúc server chậm. Discord cho phép
# tới 15 phút sau khi defer() nên không sợ hết hạn interaction.
REQUEST_TIMEOUT_SECONDS = 120

# Từ khoá dùng để đoán lỗi thuộc nhóm "bị kiểm duyệt chặn" thay vì lỗi kỹ
# thuật — xem ghi chú ở docstring đầu file về lý do phải đoán.
BLOCKED_KEYWORDS = (
    "content_policy",
    "content policy",
    "moderation",
    "safety",
    "blocked",
    "rejected",
    "flagged",
    "violat",
    "nsfw",
    "not allowed",
    "prohibited",
)


class ImageGenError(Exception):
    """Lỗi kỹ thuật khi sinh ảnh: sai key, hết credit, rate limit, timeout,
    server lỗi, response sai format..."""


class ImageGenBlockedError(ImageGenError):
    """Prompt bị hệ thống kiểm duyệt từ chối — KHÁC lỗi kỹ thuật ở chỗ thử
    lại y nguyên sẽ lại hỏng, người dùng phải tự đổi prompt. cogs/gen_image.py
    bắt riêng loại này để báo cho đúng giọng thay vì kêu 'thử lại sau'."""


@dataclass
class GeneratedImage:
    """Kết quả 1 lần sinh ảnh."""

    url: str
    # Prompt mà model thực sự dùng — hiện Vyce trả về y hệt prompt gốc, nhưng
    # chuẩn OpenAI cho phép nó viết lại, nên cứ giữ để hiển thị cho trung thực.
    revised_prompt: str
    model: str


class VyceImageService:
    """Sinh ảnh từ prompt text qua Vyce AI."""

    name = "Vyce (Grok Imagine 2)"

    def __init__(self, api_key: str | None, model_name: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model_name = model_name

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate(self, prompt: str) -> GeneratedImage:
        """
        Sinh 1 ảnh từ `prompt`, trả về GeneratedImage.

        Ném ImageGenBlockedError nếu prompt bị kiểm duyệt từ chối, hoặc
        ImageGenError cho mọi lỗi còn lại (cả 2 đều có message tiếng Việt
        sẵn sàng hiển thị thẳng lên Discord).
        """
        if not self.is_configured():
            raise ImageGenError(
                "Tính năng tạo ảnh chưa được cấu hình (thiếu VYCE_API_KEY)."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model_name, "prompt": prompt}

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    VYCE_IMAGE_API_URL, json=payload, headers=headers
                ) as resp:
                    body = await resp.text()
                    if resp.status != 200:
                        self._raise_for_error(resp.status, body)
                    data = await resp.json()
        except aiohttp.ClientError as exc:
            raise ImageGenError(f"Không gọi được API tạo ảnh: {exc}") from exc
        except TimeoutError as exc:
            raise ImageGenError(
                f"Tạo ảnh quá {REQUEST_TIMEOUT_SECONDS}s mà chưa xong, bỏ qua lần này."
            ) from exc

        items = data.get("data") or []
        if not items:
            # 200 nhưng rỗng: nhiều provider trả về kiểu này khi prompt bị
            # chặn mềm (không báo lỗi, chỉ không sinh ảnh).
            raise ImageGenBlockedError(
                "API không trả về ảnh nào cho prompt này — nhiều khả năng bị "
                "hệ thống kiểm duyệt chặn."
            )

        url = items[0].get("url")
        if not url:
            raise ImageGenError(
                f"API trả về dữ liệu không đúng định dạng (thiếu url): {str(items[0])[:200]}"
            )

        return GeneratedImage(
            url=url,
            revised_prompt=items[0].get("revised_prompt") or prompt,
            model=self.model_name,
        )

    @staticmethod
    def _raise_for_error(status: int, body: str) -> None:
        """Chuyển HTTP lỗi thành ImageGenError/ImageGenBlockedError kèm message
        tiếng Việt. Luôn ném, không bao giờ return."""
        # Vyce nhét chi tiết lỗi thật vào field `request_id` (vd gửi prompt
        # rỗng thì error.message chỉ nói chung chung "Invalid request" còn
        # request_id mới là "prompt is required") — nên gộp cả 2 lại để dò
        # từ khoá và để hiển thị.
        detail = body[:300]
        lowered = detail.lower()

        if status == 429:
            raise ImageGenError("Bị giới hạn tốc độ (HTTP 429), thử lại sau một lát.")
        if status in (401, 402, 403):
            raise ImageGenError(
                f"Vyce từ chối (HTTP {status}) — sai API key hoặc đã hết credit. "
                f"Chi tiết: {detail}"
            )
        if any(keyword in lowered for keyword in BLOCKED_KEYWORDS):
            raise ImageGenBlockedError(
                f"Prompt bị hệ thống kiểm duyệt từ chối. Chi tiết: {detail}"
            )
        raise ImageGenError(f"API tạo ảnh trả lỗi HTTP {status}: {detail}")
