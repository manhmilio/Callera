# Callera — Discord Image Bot

Bot Discord chia sẻ ảnh theo từ khóa và các mini-game đoán địa danh, không lưu
trữ file ảnh nào lên server (chỉ dùng URL trực tiếp từ nguồn). Module lời tạm
biệt (`farewell`) là ngoại lệ duy nhất có lưu dữ liệu (SQLite) để lời tạm biệt
người dùng tự đặt không bị mất khi bot restart.

## Tính năng

### Chia sẻ ảnh
- `/photo tag:<từ khóa>` — lấy 1 ảnh khớp với tag (hỗ trợ cụm từ nhiều từ)
- `/random_photo` — lấy ảnh theo tag ngẫu nhiên trong danh sách có sẵn (71 tag)
- `/many_photos` — lấy nhiều ảnh cùng tag trong 1 lần gọi
- Nút "Ảnh khác 🔄" — lấy thêm ảnh khác cùng tag, tự vô hiệu hoá sau 5 phút
- Đa nguồn ảnh: **Unsplash**, **Pexels**, **Pixabay** — tự động fallback nếu
  1 nguồn lỗi, chỉ cần cấu hình tối thiểu 1 API key

### Mini-game
- Rating ảnh bằng reaction 👍/👎 + `/top_photos` — bảng xếp hạng theo tag
- `/photo_battle` — đấu ảnh, vote bằng reaction 🅰️/🅱️
- `/guess_location` — đoán địa danh qua ảnh (44 địa danh có sẵn)
- `/blur_guess` — đoán địa danh qua ảnh bị làm mờ (Pillow), tự reveal khi
  đoán đúng hoặc hết giờ

### Lời tạm biệt tự động (`farewell`)
- `/set_farewell message:<nội dung>` — đặt lời tạm biệt của riêng bạn
  (tối đa 200 ký tự)
- `/farewell` — xem lời tạm biệt hiện tại
- `/clear_farewell` — xoá lời tạm biệt
- Khi bạn rời **hẳn** khỏi voice channel (không còn ở kênh voice nào trong
  server), bot tự động tag bạn kèm lời tạm biệt đã đặt, gửi vào kênh chat
  **gần nhất** bạn vừa nhắn tin. Nếu chưa đặt lời tạm biệt hoặc chưa từng
  nhắn tin ở kênh nào, bot sẽ bỏ qua lặng lẽ.

## Cấu trúc dự án

```
discord-image-bot/
├── bot.py                   # Entry point — tạo bot, gắn ImageAggregator + DB, load cogs
├── config.py                 # Đọc toàn bộ biến môi trường (.env) ở 1 chỗ
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
│
├── data/                    # Data tag/địa danh (code) + file bot.sqlite3 (runtime, gitignore)
│   ├── random_tags.py
│   └── guess_locations.py
│
├── services/                # Strategy pattern — nguồn ảnh (Unsplash/Pexels/Pixabay)
│   ├── base.py
│   ├── unsplash.py
│   ├── pexels.py
│   ├── pixabay.py
│   └── aggregator.py
│
├── db/                      # Lớp dữ liệu SQLite — chỉ dùng cho module farewell
│   ├── connection.py         # init_db() — mở kết nối, tạo bảng nếu chưa có
│   └── farewell_repository.py # get/set/clear_farewell()
│
├── utils/                   # Hàm dùng chung
│   ├── text.py                # normalize_text()
│   ├── image_processing.py    # download_image_bytes(), blur_image_bytes()
│   ├── embeds.py               # build_image_embed()
│   └── last_channel_tracker.py # theo dõi kênh chat gần nhất mỗi user (RAM)
│
└── cogs/                    # Mỗi tính năng = 1 file
    ├── photo.py
    ├── rating.py
    ├── battle.py
    ├── guess.py
    ├── blur_guess.py
    └── farewell.py
```

Chi tiết kiến trúc: xem `KIEN_TRUC.md`. Danh sách tính năng đầy đủ: xem
`TINH_NANG_DA_LAM.md`. Đề xuất tính năng tương lai: xem `DE_XUAT_CHUC_NANG.md`.

## Yêu cầu hệ thống

- Python 3.12+ (nếu chạy local không qua Docker)
- Docker + Docker Compose (nếu chạy qua container — khuyến khích)
- Tài khoản Discord Developer + 1 trong 3 API key ảnh (Unsplash/Pexels/Pixabay)

## Cấu hình `.env`

Copy `.env.example` thành `.env` rồi điền giá trị thật:

| Biến | Bắt buộc | Ghi chú |
|---|---|---|
| `DISCORD_TOKEN` | Có | Token bot, lấy từ [Discord Developer Portal](https://discord.com/developers/applications) |
| `UNSPLASH_ACCESS_KEY` | Không* | Free 50/giờ (Demo) → 5000/giờ (Production) |
| `PEXELS_API_KEY` | Không* | Free 200/giờ, 20.000/tháng |
| `PIXABAY_API_KEY` | Không* | Free, không giới hạn request |
| `SQLITE_DB_PATH` | Không | Mặc định `data/bot.sqlite3`, dùng cho module farewell |

*Cần ít nhất 1 trong 3 API key ảnh, không bắt buộc phải có đủ cả 3.

### Đăng ký Discord Bot

1. Tạo application tại [Discord Developer Portal](https://discord.com/developers/applications)
2. Vào tab **Bot** → tạo token → dán vào `DISCORD_TOKEN`
3. Bật **MESSAGE CONTENT INTENT** ở tab Bot (bắt buộc, nếu không
   `/guess_location` và `/blur_guess` không đọc được nội dung tin nhắn đoán)
4. Vào tab **OAuth2 > URL Generator**, chọn scope `bot` + `applications.commands`,
   permissions tối thiểu: `Send Messages`, `Read Message History`,
   `Add Reactions`, `Embed Links`, `Attach Files`
5. Dùng URL sinh ra để mời bot vào server

## Chạy local (không qua Docker)

```bash
# 1. Tạo virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Cài dependency
pip install -r requirements.txt

# 3. Cấu hình .env
cp .env.example .env
# ... điền DISCORD_TOKEN và ít nhất 1 API key ảnh

# 4. Chạy bot
python bot.py
```

File SQLite (`data/bot.sqlite3`) sẽ tự tạo ở lần chạy đầu tiên, không cần
setup gì thêm.

## Chạy bằng Docker (khuyến khích)

```bash
# 1. Cấu hình .env (giống bước trên)
cp .env.example .env

# 2. Build và chạy
docker compose up -d --build

# 3. Xem log
docker compose logs -f bot

# 4. Dừng bot
docker compose down
```

`docker-compose.yml` mount thư mục `./data` từ host vào `/app/data` trong
container — file `bot.sqlite3` được lưu bền vững trên host, không mất khi
container bị rebuild hoặc xoá.

## Slash sync khi thêm/đổi lệnh

- **Guild-specific sync**: cập nhật gần như tức thì
- **Global sync** (mặc định trong `bot.py` hiện tại qua `bot.tree.sync()`):
  có thể mất tới 1 giờ để Discord cập nhật trên tất cả server
- Đổi tên command chỉ cần **restart bot**, không cần mời lại bot vào server

## Lưu ý kỹ thuật

- `403 error code 160002` khi bot cố gửi tin nhắn = thiếu quyền
  **Read Message History** ở role của bot trong server đó (lỗi cấp quyền
  guild, không phải cấu hình Developer Portal).
- Google Custom Search JSON API không dùng được cho project mới — đây là lý
  do bot dùng Unsplash/Pexels/Pixabay thay vì Google Images.
- Pinterest không có API search công khai theo từ khóa nên không được tích
  hợp làm nguồn ảnh thứ 4.