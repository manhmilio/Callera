import random

from .base import ImageService, ImageResult


class ImageAggregator:
    """Gom nhiều ImageService lại: mỗi lần tìm ảnh sẽ random thứ tự các nguồn
    đang có API key, thử lần lượt tới khi có kết quả. Nếu 1 nguồn lỗi (hết
    quota, rate limit, sai key, mất mạng...) thì tự động fallback sang nguồn
    tiếp theo thay vì báo lỗi luôn cho người dùng.
    """

    def __init__(self, services: list[ImageService]):
        self.services = services

    def available_services(self) -> list[ImageService]:
        return [s for s in self.services if s.is_configured()]

    async def search(self, query: str) -> list[ImageResult]:
        available = self.available_services()
        if not available:
            raise RuntimeError(
                "Chưa cấu hình API key nào (UNSPLASH_ACCESS_KEY / PEXELS_API_KEY / PIXABAY_API_KEY)."
            )

        order = available[:]
        random.shuffle(order)
        last_error: Exception | None = None

        for service in order:
            try:
                results = await service.search(query)
                if results:
                    return results
            except Exception as e:
                last_error = e
                print(f"[{service.name}] Lỗi khi tìm ảnh, thử nguồn khác: {e}")
                continue

        if last_error:
            raise last_error
        return []  # tất cả nguồn đều không có kết quả cho từ khóa này

    async def notify_used(self, result: ImageResult) -> None:
        """Gọi hook on_image_used() của đúng service đã trả về ảnh này
        (vd để Unsplash gọi download_location)."""
        for service in self.services:
            if service.name == result.source:
                await service.on_image_used(result)
                return
