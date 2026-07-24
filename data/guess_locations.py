"""Danh sách địa danh dùng cho /guess_location và /blur_guess, kèm các đáp án
được chấp nhận (không dấu, viết thường).

Tự thêm/bớt tùy ý ở đây — không ảnh hưởng đến phần code logic khác.
"""

GUESS_LOCATIONS = {
    # --- Việt Nam ---
    "Hạ Long": ["ha long", "vinh ha long", "halong", "halong bay"],
    "Sapa": ["sapa", "sa pa"],
    "Đà Lạt": ["da lat", "dalat"],
    "Hội An": ["hoi an", "hoian"],
    "Phú Quốc": ["phu quoc"],
    "Trường Sa": ["truong sa", "spratly"],
    "Hoàng Sa": ["hoang sa", "paracel"],
    "Ninh Bình": ["ninh binh", "trang an", "tam coc"],
    "Đà Nẵng": ["da nang", "danang", "ba na hills", "cau vang", "golden bridge"],
    "Huế": ["hue", "hoang thanh hue", "imperial city hue"],
    "Hà Nội": ["ha noi", "hanoi"],
    "TP. Hồ Chí Minh": ["tp hcm", "ho chi minh city", "saigon", "sai gon"],
    "Mộc Châu": ["moc chau"],
    "Hà Giang": ["ha giang", "dong van", "ma pi leng"],
    "Phong Nha - Kẻ Bàng": ["phong nha", "ke bang", "phong nha ke bang"],
    "Mũi Né": ["mui ne", "doi cat mui ne"],
    "Côn Đảo": ["con dao"],
    "Cần Thơ": ["can tho", "cho noi cai rang"],

    # --- Châu Á (quốc tế) ---
    "Tokyo": ["tokyo"],
    "Kyoto": ["kyoto"],
    "Bangkok": ["bangkok"],
    "Bali": ["bali"],
    "Angkor Wat": ["angkor wat", "angkor"],
    "Singapore": ["singapore"],
    "Seoul": ["seoul"],
    "Great Wall of China": ["great wall", "great wall of china", "van ly truong thanh"],
    "Taj Mahal": ["taj mahal"],

    # --- Châu Âu ---
    "Paris": ["paris"],
    "Rome": ["rome", "roma"],
    "Venice": ["venice", "venezia"],
    "Santorini": ["santorini"],
    "Iceland": ["iceland"],
    "Switzerland Alps": ["swiss alps", "switzerland", "alps", "thuy si"],
    "London": ["london"],
    "Barcelona": ["barcelona"],
    "Prague": ["prague", "praha"],

    # --- Châu Mỹ ---
    "New York": ["new york", "nyc"],
    "Grand Canyon": ["grand canyon"],
    "Machu Picchu": ["machu picchu"],
    "Rio de Janeiro": ["rio de janeiro", "rio"],
    "Niagara Falls": ["niagara falls", "niagara"],

    # --- Châu Đại Dương / Châu Phi ---
    "Sydney Opera House": ["sydney opera house", "sydney"],
    "Great Barrier Reef": ["great barrier reef"],
    "Pyramids of Giza": ["pyramids of giza", "giza pyramids", "kim tu thap"],
}