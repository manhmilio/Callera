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

# Dùng cho cogs/ask.py (tính năng hỏi đáp qua tag bot) — services/qa_service.py.
# Lấy key miễn phí tại https://aistudio.google.com/apikey. Nếu để trống,
# QAAggregator sẽ tự bỏ qua nguồn này (xem GROQ_API_KEY bên dưới để biết
# nguồn dự phòng).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Dùng cho services/groq_qa_service.py — nguồn hỏi đáp DỰ PHÒNG, tự động
# được QAAggregator gọi tới khi GEMINI_API_KEY bị rate limit/lỗi (free tier
# Gemini chỉ ~10 requests/phút, 250 requests/ngày, rất dễ nghẽn khi nhiều
# người cùng hỏi). Lấy key miễn phí, không cần thẻ tín dụng, tại
# https://console.groq.com/keys. Nếu để trống, tính năng hỏi đáp vẫn chạy
# bình thường bằng mình Gemini (không bắt buộc phải có cả 2 key).
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Đường dẫn file SQLite dùng cho module farewell (db/connection.py).
# Mặc định nằm trong thư mục data/ — thư mục này được mount qua Docker volume
# (xem docker-compose.yml) để không mất dữ liệu khi container rebuild/xoá.
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/bot.sqlite3")