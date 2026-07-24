import aiohttp

from .base import ImageService, ImageResult


class UnsplashService(ImageService):
    """Nguồn ảnh Unsplash. Bắt buộc ghi nguồn tác giả + gọi download_location
    sau khi hiển thị ảnh (theo Unsplash API Guidelines)."""

    name = "Unsplash"

    def __init__(self, access_key: str | None):
        self.access_key = access_key

    def is_configured(self) -> bool:
        return bool(self.access_key)

    async def search(self, query: str) -> list[ImageResult]:
        if not self.is_configured():
            return []

        url = "https://api.unsplash.com/search/photos"
        params = {"query": query, "per_page": 10, "content_filter": "high"}
        headers = {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Unsplash API lỗi {resp.status}: {text}")
                data = await resp.json()

        results = []
        for item in data.get("results", []):
            urls = item.get("urls", {})
            image_url = urls.get("regular") or urls.get("full")
            if not image_url:
                continue
            results.append(
                ImageResult(
                    image_url=image_url,
                    author=item.get("user", {}).get("name", "Unknown"),
                    author_link=item.get("user", {}).get("links", {}).get("html", ""),
                    photo_link=item.get("links", {}).get("html", ""),
                    source=self.name,
                    download_location=item.get("links", {}).get("download_location", ""),
                )
            )
        return results

    async def on_image_used(self, result: ImageResult) -> None:
        """Báo cho Unsplash biết ảnh vừa được hiển thị (bắt buộc theo API
        Guidelines — điều kiện để được duyệt lên gói Production)."""
        if not result.download_location:
            return

        headers = {
            "Authorization": f"Client-ID {self.access_key}",
            "Accept-Version": "v1",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(result.download_location, headers=headers) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        print(f"[Unsplash] Cảnh báo: gọi download_location lỗi {resp.status}: {text}")
        except Exception as e:
            print(f"[Unsplash] Cảnh báo: không thể gọi download_location: {e}")
