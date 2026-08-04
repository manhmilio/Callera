"""Entry point của Discord Image Bot.

File này CHỈ chịu trách nhiệm: tạo bot instance, gắn ImageAggregator dùng
chung, khởi tạo kết nối DB cho module farewell/study_reminder, load các cogs
(mỗi tính năng nằm ở cogs/), rồi chạy bot. Toàn bộ logic tính năng nằm trong
cogs/, services/, data/, utils/, db/ — xem README/các file docs để biết chi
tiết từng phần.
"""

import asyncio
import logging
import os

import discord
from discord.ext import commands

import config
from db.connection import close_db, init_db
from services import ImageAggregator, UnsplashService, PexelsService, PixabayService

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
# Cần bật "MESSAGE CONTENT INTENT" trong Discord Developer Portal > Bot,
# nếu không /guess_location và /blur_guess sẽ không đọc được nội dung tin
# nhắn người chơi gõ để đoán.
intents.message_content = True

# 3 intent dưới đây đều là Privileged Gateway Intent — phải bật thủ công ở
# Discord Developer Portal > Bot (ngoài việc set True ở code), nếu không
# on_presence_update sẽ không bắn và member.activities/member.voice sẽ rỗng.
# Dùng cho cogs/study_reminder.py:
intents.presences = True       # đọc được activity (đang chơi game gì)
intents.members = True         # presence data cần intent này đi kèm mới đầy đủ
intents.voice_states = True    # đọc được member.voice.channel (có đang ở voice không)

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
    "cogs.farewell",
    "cogs.study_reminder",
]


@bot.event
async def on_ready():
    await bot.tree.sync()
    active_sources = [s.name for s in bot.image_aggregator.available_services()]
    print(f"Đã đăng nhập với tên {bot.user}. Nguồn ảnh đang bật: {', '.join(active_sources) or 'KHÔNG CÓ'}")


async def main() -> None:
    # Đảm bảo thư mục chứa file SQLite tồn tại (khi chạy local không qua
    # Docker thì thư mục data/ có thể chưa được tạo sẵn).
    os.makedirs(os.path.dirname(config.SQLITE_DB_PATH) or ".", exist_ok=True)

    async with bot:
        # Gắn kết nối DB dùng chung vào bot instance — các cog truy cập qua
        # self.bot.db (xem cogs/farewell.py, cogs/study_reminder.py).
        bot.db = await init_db(config.SQLITE_DB_PATH)
        try:
            for extension in INITIAL_EXTENSIONS:
                await bot.load_extension(extension)
            await bot.start(config.DISCORD_TOKEN)
        finally:
            await close_db(bot.db)


if __name__ == "__main__":
    if not config.DISCORD_TOKEN:
        raise SystemExit("Thiếu DISCORD_TOKEN trong file .env.")
    if not any([config.UNSPLASH_ACCESS_KEY, config.PEXELS_API_KEY, config.PIXABAY_API_KEY]):
        raise SystemExit(
            "Cần ít nhất 1 API key ảnh: UNSPLASH_ACCESS_KEY, PEXELS_API_KEY, hoặc PIXABAY_API_KEY."
        )
    asyncio.run(main())