from io import BytesIO

import aiohttp
from PIL import Image, ImageFilter


async def download_image_bytes(url: str) -> bytes:
    """Tải bytes ảnh gốc về (chỉ giữ trong RAM, không ghi ra file).

    Đây là chỗ duy nhất trong bot thực sự tải bytes ảnh về thay vì chỉ dùng
    URL, do /blur_guess cần xử lý ảnh (làm mờ) trước khi hiển thị.
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Failed to download the source image (status {resp.status}).")
            return await resp.read()


def blur_image_bytes(image_bytes: bytes, blur_radius: int = 30) -> BytesIO:
    """Áp Gaussian blur lên bytes ảnh, trả về buffer PNG sẵn sàng gửi qua Discord."""
    with Image.open(BytesIO(image_bytes)) as img:
        img = img.convert("RGB")
        blurred = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        buffer = BytesIO()
        blurred.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
