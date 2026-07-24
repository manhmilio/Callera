"""Interface chung cho mọi nguồn ảnh (Strategy pattern).

Muốn thêm 1 nguồn ảnh mới (vd Wikimedia Commons): tạo file mới trong
services/, kế thừa ImageService, implement is_configured() + search(), rồi
thêm vào danh sách services truyền cho ImageAggregator ở bot.py — không cần
sửa gì ở cogs/ hay các service khác.
"""

from abc import ABC, abstractmethod


class ImageResult:
    """Kết quả ảnh thống nhất, dùng chung cho mọi service."""

    __slots__ = ("image_url", "author", "author_link", "photo_link", "source", "download_location")

    def __init__(
        self,
        image_url: str,
        author: str,
        source: str,
        author_link: str | None = None,
        photo_link: str | None = None,
        download_location: str | None = None,
    ):
        self.image_url = image_url
        self.author = author
        self.author_link = author_link
        self.photo_link = photo_link
        self.source = source
        self.download_location = download_location


class ImageService(ABC):
    """Interface chung cho mọi nguồn ảnh."""

    name: str = "Unknown"

    @abstractmethod
    def is_configured(self) -> bool:
        """Nguồn này đã có API key/sẵn sàng dùng chưa."""
        ...

    @abstractmethod
    async def search(self, query: str) -> list[ImageResult]:
        """Tìm ảnh theo từ khóa, trả về list ImageResult (rỗng nếu không có kết quả)."""
        ...

    async def on_image_used(self, result: ImageResult) -> None:
        """Hook tuỳ chọn: gọi sau khi 1 ảnh từ nguồn này được hiển thị cho người
        dùng (vd Unsplash bắt buộc gọi download_location theo API Guidelines).

        Mặc định không làm gì; service nào cần thì override.
        """
        return None
