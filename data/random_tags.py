"""Danh sách tag dùng cho lệnh /random_photo.

Tự thêm/bớt tùy ý ở đây — không ảnh hưởng đến phần code logic khác.
Các tag được nhóm theo chủ đề chỉ để dễ đọc/dễ chỉnh sửa; khi chạy,
/random_photo vẫn chọn ngẫu nhiên trên toàn bộ danh sách phẳng bên dưới.
"""

# --- Phong cảnh chung (giữ từ bản gốc) ---
_LANDSCAPE = [
    "hoàng hôn", "bình minh", "biển", "núi", "rừng", "sa mạc", "thác nước",
    "hồ nước", "cánh đồng lúa", "ruộng bậc thang", "hòn đảo", "bầu trời sao",
    "mây", "tuyết", "hoa",
]

# --- Địa danh Việt Nam + quốc tế (giữ từ bản gốc) ---
_LANDMARKS = [
    "Trường Sa", "Hoàng Sa", "Hạ Long", "Sapa", "Đà Lạt", "Hội An", "Phú Quốc",
    "Tokyo", "Paris", "New York", "Rome", "Iceland", "Switzerland Alps",
]

# --- Kiến trúc / đô thị ---
_ARCHITECTURE_URBAN = [
    "phố cổ", "chợ đêm", "ga tàu", "cầu vượt biển", "tòa nhà chọc trời",
    "đường phố", "kiến trúc cổ", "chùa", "cầu", "phố đi bộ", "quảng trường",
    "nhà thờ cổ", "lâu đài",
]

# --- Ẩm thực / đời sống ---
_FOOD_LIFESTYLE = [
    "quán cà phê", "chợ nổi", "đường phố ẩm thực", "chợ truyền thống",
    "quán ăn đường phố", "vườn trà", "cánh đồng hoa hướng dương",
]

# --- Thiên nhiên / động vật ---
_NATURE_WILDLIFE = [
    "rừng nhiệt đới", "sa mạc tuyết", "động vật hoang dã", "san hô",
    "vịnh biển", "hang động", "suối nước nóng", "rừng tre", "chim hoang dã",
    "đại dương",
]

# --- Mùa / thời tiết ---
_SEASONS_WEATHER = [
    "mùa thu lá vàng", "mùa hoa anh đào", "mưa phùn", "sương mù",
    "mùa đông tuyết rơi", "mùa hè nắng vàng", "cầu vồng sau mưa",
]

# --- Không gian / vũ trụ ---
_SPACE_SKY = [
    "dải ngân hà", "cực quang", "nhật thực", "bầu trời đêm", "sao băng",
    "mặt trăng",
]

RANDOM_TAGS = (
    _LANDSCAPE
    + _LANDMARKS
    + _ARCHITECTURE_URBAN
    + _FOOD_LIFESTYLE
    + _NATURE_WILDLIFE
    + _SEASONS_WEATHER
    + _SPACE_SKY
)