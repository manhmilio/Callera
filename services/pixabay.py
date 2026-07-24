import aiohttp

from .base import ImageService, ImageResult


class PixabayService(ImageService):
    """Nguồn ảnh Pixabay. Không bắt buộc ghi nguồn, không giới hạn request."""

    name = "Pixabay"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[ImageResult]:
        if not self.is_configured():
            return []

        url = "https://pixabay.com/api/"
        params = {
            "key": self.api_key,
            "q": query,
            "image_type": "photo",
            "per_page": 10,
            "safesearch": "true",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Pixabay API lỗi {resp.status}: {text}")
                data = await resp.json()

        results = []
        for item in data.get("hits", []):
            image_url = item.get("largeImageURL") or item.get("webformatURL")
            if not image_url:
                continue
            results.append(
                ImageResult(
                    image_url=image_url,
                    author=item.get("user", "Unknown"),
                    photo_link=item.get("pageURL", ""),
                    source=self.name,
                )
            )
        return results
