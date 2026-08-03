"""Đọc toàn bộ biến môi trường (.env) ở một chỗ duy nhất.

Mọi module khác import từ đây thay vì tự gọi os.getenv() rải rác, để sau này
đổi tên biến hoặc thêm nguồn mới chỉ cần sửa 1 file.
"""

import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

# Đường dẫn file SQLite dùng cho module farewell (db/connection.py).
# Mặc định nằm trong thư mục data/ — thư mục này được mount qua Docker volume
# (xem docker-compose.yml) để không mất dữ liệu khi container rebuild/xoá.
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/bot.sqlite3")