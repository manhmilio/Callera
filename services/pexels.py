import aiohttp

from .base import ImageService, ImageResult


class PexelsService(ImageService):
    """Nguồn ảnh Pexels. Không bắt buộc ghi nguồn, nhưng vẫn nên ghi."""

    name = "Pexels"

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> list[ImageResult]:
        if not self.is_configured():
            return []

        url = "https://api.pexels.com/v1/search"
        params = {"query": query, "per_page": 10}
        headers = {"Authorization": self.api_key}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Pexels API lỗi {resp.status}: {text}")
                data = await resp.json()

        results = []
        for item in data.get("photos", []):
            src = item.get("src", {})
            image_url = src.get("large2x") or src.get("original")
            if not image_url:
                continue
            results.append(
                ImageResult(
                    image_url=image_url,
                    author=item.get("photographer", "Unknown"),
                    author_link=item.get("photographer_url", ""),
                    photo_link=item.get("url", ""),
                    source=self.name,
                )
            )
        return results
