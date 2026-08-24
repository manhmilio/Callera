"""
utils/playtime_tracker.py

Theo dõi tổng thời gian chơi game THỰC của user, có gộp các khoảng chơi
cách nhau không quá GRACE_PERIOD (10 phút) thành 1 phiên liên tục.

Cách hoạt động:
- Khi user bắt đầu chơi: mở segment mới (segment_start = now).
- Khi user dừng chơi (không còn activity Playing nào): cộng dồn thời gian
  vừa chơi vào "accumulated", đóng segment, ghi lại "last_stop" -> phiên
  chuyển sang trạng thái CHỜ (không tính là kết thúc hẳn).
- Nếu user chơi lại trong vòng GRACE_PERIOD kể từ last_stop: mở segment mới,
  GIỮ NGUYÊN accumulated + reminded đã có (coi như chơi liên tục).
- Nếu quá GRACE_PERIOD mà không chơi lại: phiên coi như kết thúc thật, bị
  dọn (clear_session) ở task định kỳ -> lần chơi sau tính lại từ đầu.

accumulated CHỈ cộng thời gian chơi thực sự, không tính thời gian nghỉ giữa
chừng — đúng theo lựa chọn đã chốt.

Không dùng activity.start (Discord Rich Presence timestamp) vì giá trị này
phụ thuộc game có tích hợp Discord SDK hay không, không đáng tin cậy.
"""

from datetime import datetime, timedelta, timezone

GRACE_PERIOD = timedelta(minutes=10)

# key: user_id
# value: {
#   "game": str,
#   "accumulated": timedelta,       # tổng thời gian đã chơi thực (không tính lúc nghỉ)
#   "segment_start": datetime|None, # None nếu đang trong lúc nghỉ (chờ gộp)
#   "last_stop": datetime|None,     # thời điểm dừng gần nhất, dùng để check grace period
#   "reminded": bool,
# }
active_sessions: dict[int, dict] = {}


def start_or_resume_session(user_id: int, game_name: str) -> None:
    """Gọi khi phát hiện user bắt đầu chơi (activity Playing xuất hiện)."""
    now = datetime.now(timezone.utc)
    session = active_sessions.get(user_id)

    if (
        session is not None
        and session["segment_start"] is None
        and session["last_stop"] is not None
        and now - session["last_stop"] <= GRACE_PERIOD
    ):
        # Nghỉ ngắn (<=10 phút) -> gộp tiếp, không reset accumulated/reminded
        session["game"] = game_name
        session["segment_start"] = now
        session["last_stop"] = None
        return

    # Phiên hoàn toàn mới (chưa từng chơi, hoặc nghỉ quá lâu)
    active_sessions[user_id] = {
        "game": game_name,
        "accumulated": timedelta(0),
        "segment_start": now,
        "last_stop": None,
        "reminded": False,
    }


def pause_session(user_id: int) -> None:
    """Gọi khi user vừa dừng chơi (không còn activity Playing nào)."""
    session = active_sessions.get(user_id)
    if session is None or session["segment_start"] is None:
        return

    now = datetime.now(timezone.utc)
    session["accumulated"] += now - session["segment_start"]
    session["segment_start"] = None
    session["last_stop"] = now


def update_game_name(user_id: int, game_name: str) -> None:
    """User vẫn đang chơi nhưng đổi sang game khác -> chỉ cập nhật tên hiển thị."""
    session = active_sessions.get(user_id)
    if session is not None:
        session["game"] = game_name


def get_total_playtime(user_id: int) -> timedelta:
    """Tổng thời gian đã chơi thực tính đến hiện tại (bao gồm segment đang mở)."""
    session = active_sessions.get(user_id)
    if session is None:
        return timedelta(0)

    total = session["accumulated"]
    if session["segment_start"] is not None:
        total += datetime.now(timezone.utc) - session["segment_start"]
    return total


def is_expired(session: dict, now: datetime) -> bool:
    """True nếu phiên đang ở trạng thái chờ và đã quá GRACE_PERIOD -> coi như đã dừng hẳn."""
    return (
        session["segment_start"] is None
        and session["last_stop"] is not None
        and now - session["last_stop"] > GRACE_PERIOD
    )


def clear_session(user_id: int) -> None:
    active_sessions.pop(user_id, None)


def get_session(user_id: int) -> dict | None:
    return active_sessions.get(user_id)