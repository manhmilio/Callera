"""Entry point của Discord Image Bot.

File này CHỈ chịu trách nhiệm: tạo bot instance, gắn ImageAggregator dùng
chung, load các cogs (mỗi tính năng nằm ở cogs/), rồi chạy bot. Toàn bộ logic
tính năng nằm trong cogs/, services/, data/, utils/ — xem README/các file docs
để biết chi tiết từng phần.
"""

import asyncio
import logging

import discord
from discord.ext import commands

import config
from services import ImageAggregator, UnsplashService, PexelsService, PixabayService

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
# Cần bật "MESSAGE CONTENT INTENT" trong Discord Developer Portal > Bot,
# nếu không /guess_location và /blur_guess sẽ không đọc được nội dung tin
# nhắn người chơi gõ để đoán.
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ImageAggregator dùng chung cho mọi cog — gắn thẳng vào bot instance để các
# cog truy cập qua self.bot.image_aggregator, tránh phải truyền tham số
# xuyên suốt hoặc import vòng giữa các module.
bot.image_aggregator = ImageAggregator(
    services=[
        UnsplashService(config.UNSPLASH_ACCESS_KEY),
        PexelsService(config.PEXELS_API_KEY),
        PixabayService(config.PIXABAY_API_KEY),
    ]
)

# Danh sách cogs cần load — thêm tính năng mới = thêm 1 dòng ở đây.
INITIAL_EXTENSIONS = [
    "cogs.photo",
    "cogs.rating",
    "cogs.battle",
    "cogs.guess",
    "cogs.blur_guess",
]


@bot.event
async def on_ready():
    await bot.tree.sync()
    active_sources = [s.name for s in bot.image_aggregator.available_services()]
    print(f"Đã đăng nhập với tên {bot.user}. Nguồn ảnh đang bật: {', '.join(active_sources) or 'KHÔNG CÓ'}")


async def main() -> None:
    async with bot:
        for extension in INITIAL_EXTENSIONS:
            await bot.load_extension(extension)
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("Thiếu DISCORD_TOKEN trong file .env.")
    if not any([config.UNSPLASH_ACCESS_KEY, config.PEXELS_API_KEY, config.PIXABAY_API_KEY]):
        raise SystemExit(
            "Cần ít nhất 1 API key ảnh: UNSPLASH_ACCESS_KEY, PEXELS_API_KEY, hoặc PIXABAY_API_KEY."
        )
    asyncio.run(main())
