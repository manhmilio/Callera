FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Thư mục chứa file SQLite — sẽ được mount qua volume ở docker-compose.yml
# để dữ liệu không mất khi container bị xoá/rebuild.
RUN mkdir -p /app/data

CMD ["python", "bot.py"]