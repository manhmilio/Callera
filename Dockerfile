FROM python:3.12-slim

WORKDIR /app

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