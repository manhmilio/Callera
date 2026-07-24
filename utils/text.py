import unicodedata


def normalize_text(text: str) -> str:
    """Bỏ dấu tiếng Việt + viết thường, dùng để so khớp câu trả lời linh hoạt hơn."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()
