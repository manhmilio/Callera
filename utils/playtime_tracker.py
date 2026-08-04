"""
utils/playtime_tracker.py

Theo dõi thời điểm bắt đầu 1 "phiên chơi game" của user, lưu tạm trong RAM
(mất khi bot restart — chấp nhận được vì mỗi lần chơi lại tính là phiên mới).

Không dùng activity.start (Discord Rich Presence timestamp) vì giá trị này
phụ thuộc hoàn toàn vào việc game đó có tích hợp Discord SDK hay không —
nhiều game không gửi lên, không đáng tin cậy. Thay vào đó bot tự ghi lại
thời điểm phát hiện activity kiểu Playing xuất hiện, qua on_presence_update.
"""

from datetime import datetime, timezone

# key: user_id
# value: {"game": str, "start": datetime, "reminded": bool}
active_sessions: dict[int, dict] = {}


def start_session(user_id: int, game_name: str) -> None:
    """Mở 1 phiên chơi game mới cho user (ghi đè phiên cũ nếu có)."""
    active_sessions[user_id] = {
        "game": game_name,
        "start": datetime.now(timezone.utc),
        "reminded": False,
    }


def end_session(user_id: int) -> None:
    """Đóng phiên chơi game hiện tại của user (nếu có)."""
    active_sessions.pop(user_id, None)


def get_session(user_id: int) -> dict | None:
    return active_sessions.get(user_id)