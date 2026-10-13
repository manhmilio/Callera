FROM python:3.12-slim

WORKDIR /app

# Không buffer stdout: mặc định Python block-buffer stdout khi không chạy
# trong terminal, nên mọi print() trong bot.py (log nguồn ảnh/hỏi đáp/gen_img
# đang bật lúc on_ready) bị kẹt trong buffer và KHÔNG BAO GIỜ hiện ra
# `docker compose logs`. Chỉ thấy log của discord.py vì thư viện đó ghi qua
# `logging` ra stderr (vốn không bị buffer kiểu này).
ENV PYTHONUNBUFFERED=1

# ffmpeg: bắt buộc để cogs/study_reminder.py phát audio nhắc nhở trong voice
# channel (discord.FFmpegPCMAudio gọi binary ffmpeg qua subprocess, không
# phải thư viện pip nên phải cài ở tầng OS, trước khi cài requirements.txt).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Thư mục chứa file SQLite — sẽ được mount qua volume ở docker-compose.yml
# để dữ liệu không mất khi container bị xoá/rebuild.
RUN mkdir -p /app/data

CMD ["python", "bot.py"]