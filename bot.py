import os
import random
import asyncio
import unicodedata
from collections import defaultdict

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

intents = discord.Intents.default()
# Cần bật "MESSAGE CONTENT INTENT" trong Discord Developer Portner > Bot,
# nếu không lệnh /guess_location sẽ không đọc được nội dung tin nhắn đoán.
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# Mỗi hàm search_* trả về list[dict] với format thống nhất:
# {
#   "image_url": str,
#   "author": str,
#   "author_link": str | None,
#   "photo_link": str | None,
#   "source": "Unsplash" | "Pexels" | "Pixabay",
#   "download_location": str | None,  # chỉ Unsplash cần dùng
# }
# ---------------------------------------------------------------------------


async def search_unsplash(query: str) -> list[dict]:
    """Tìm ảnh trên Unsplash. Bắt buộc ghi nguồn tác giả (theo API Guidelines)."""
    if not UNSPLASH_ACCESS_KEY:
        return []

    url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "per_page": 10, "content_filter": "high"}
    headers = {
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
        "Accept-Version": "v1",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Unsplash API lỗi {resp.status}: {text}")
            data = await resp.json()

    images = []
    for item in data.get("results", []):
        urls = item.get("urls", {})
        image_url = urls.get("regular") or urls.get("full")
        if not image_url:
            continue
        images.append(
            {
                "image_url": image_url,
                "author": item.get("user", {}).get("name", "Unknown"),
                "author_link": item.get("user", {}).get("links", {}).get("html", ""),
                "photo_link": item.get("links", {}).get("html", ""),
                "source": "Unsplash",
                "download_location": item.get("links", {}).get("download_location", ""),
            }
        )
    return images


async def search_pexels(query: str) -> list[dict]:
    """Tìm ảnh trên Pexels. Không bắt buộc ghi nguồn, nhưng vẫn nên ghi."""
    if not PEXELS_API_KEY:
        return []

    url = "https://api.pexels.com/v1/search"
    params = {"query": query, "per_page": 10}
    headers = {"Authorization": PEXELS_API_KEY}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Pexels API lỗi {resp.status}: {text}")
            data = await resp.json()

    images = []
    for item in data.get("photos", []):
        src = item.get("src", {})
        image_url = src.get("large2x") or src.get("original")
        if not image_url:
            continue
        images.append(
            {
                "image_url": image_url,
                "author": item.get("photographer", "Unknown"),
                "author_link": item.get("photographer_url", ""),
                "photo_link": item.get("url", ""),
                "source": "Pexels",
                "download_location": None,
            }
        )
    return images


async def search_pixabay(query: str) -> list[dict]:
    """Tìm ảnh trên Pixabay. Không bắt buộc ghi nguồn, không giới hạn request."""
    if not PIXABAY_API_KEY:
        return []

    url = "https://pixabay.com/api/"
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "image_type": "photo",
        "per_page": 10,
        "safesearch": "true",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Pixabay API lỗi {resp.status}: {text}")
            data = await resp.json()

    images = []
    for item in data.get("hits", []):
        image_url = item.get("largeImageURL") or item.get("webformatURL")
        if not image_url:
            continue
        images.append(
            {
                "image_url": image_url,
                "author": item.get("user", "Unknown"),
                "author_link": None,
                "photo_link": item.get("pageURL", ""),
                "source": "Pixabay",
                "download_location": None,
            }
        )
    return images


# Danh sách tag mẫu dùng cho lệnh /random_photo - có thể tự thêm/bớt tùy ý
RANDOM_TAGS = [
    "hoàng hôn", "bình minh", "biển", "núi", "rừng", "sa mạc", "thác nước",
    "hồ nước", "cánh đồng lúa", "ruộng bậc thang", "đường phố", "kiến trúc cổ",
    "chùa", "cầu", "hòn đảo", "bầu trời sao", "mây", "tuyết", "hoa",
    "Trường Sa", "Hoàng Sa", "Hạ Long", "Sapa", "Đà Lạt", "Hội An", "Phú Quốc",
    "Tokyo", "Paris", "New York", "Rome", "Iceland", "Switzerland Alps",
]

# Danh sách địa danh dùng cho mini-game /guess_location, kèm các đáp án được
# chấp nhận (không dấu, viết thường). Có thể tự thêm/bớt tùy ý.
GUESS_LOCATIONS = {
    "Hạ Long": ["ha long", "vinh ha long", "halong", "halong bay"],
    "Sapa": ["sapa", "sa pa"],
    "Đà Lạt": ["da lat", "dalat"],
    "Hội An": ["hoi an", "hoian"],
    "Phú Quốc": ["phu quoc"],
    "Trường Sa": ["truong sa", "spratly"],
    "Tokyo": ["tokyo"],
    "Paris": ["paris"],
    "New York": ["new york", "nyc"],
    "Rome": ["rome", "roma"],
    "Iceland": ["iceland"],
    "Switzerland Alps": ["swiss alps", "switzerland", "alps", "thuy si"],
}


def build_image_embed(tag: str, chosen: dict, requester_name: str) -> discord.Embed:
    """Tạo embed hiển thị 1 ảnh kèm thông tin nguồn/tác giả. Dùng chung cho
    lệnh /photo, /random_photo, /many_photos và nút "Ảnh khác" để tránh lặp code."""
    embed = discord.Embed(title=f"Kết quả cho: {tag}", color=discord.Color.blue())
    embed.set_image(url=chosen["image_url"])
    embed.set_footer(text=f"Yêu cầu bởi {requester_name} · Nguồn: {chosen['source']}")

    if chosen["author_link"]:
        credit = f"[{chosen['author']}]({chosen['author_link']})"
    else:
        credit = chosen["author"]
    embed.add_field(name="Ảnh của", value=credit, inline=True)
    return embed


# ---------------------------------------------------------------------------
# Rating ảnh bằng reaction (RAM only, không ghi ra file/DB)
# ---------------------------------------------------------------------------

RATING_EMOJIS = ("👍", "👎")

# message_id -> {"tag": str, "image_url": str}
rated_messages: dict[int, dict] = {}

# tag -> { image_url: {"up": int, "down": int} }
photo_ratings: dict[str, dict[str, dict]] = defaultdict(dict)


async def add_rating_reactions(message: discord.Message) -> None:
    for emoji in RATING_EMOJIS:
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            pass


def register_rated_message(message: discord.Message, tag: str, image_url: str) -> None:
    rated_messages[message.id] = {"tag": tag, "image_url": image_url}


async def fetch_and_reply(interaction: discord.Interaction, tag: str, use_followup: bool = True) -> None:
    """Tìm ảnh theo tag, gửi embed kèm nút 'Ảnh khác' + reaction rating, xử lý lỗi/rỗng.

    use_followup=True: dùng cho slash command (đã defer trước đó).
    use_followup=False: dùng khi bấm nút, gửi message mới (không edit) để giữ
    lại lịch sử các ảnh đã xem trong kênh.
    """
    send = interaction.followup.send

    try:
        images = await search_all_sources(tag)
    except Exception as e:
        await send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
        return

    if not images:
        await send(f"Không tìm thấy ảnh nào cho từ khóa **{tag}**.")
        return

    chosen = random.choice(images)
    embed = build_image_embed(tag, chosen, interaction.user.display_name)
    view = ImageView(tag=tag)

    message = await send(embed=embed, view=view)
    if message is not None:
        register_rated_message(message, tag, chosen["image_url"])
        await add_rating_reactions(message)

    if chosen["source"] == "Unsplash":
        await trigger_unsplash_download(chosen.get("download_location", ""))


class ImageView(discord.ui.View):
    """View chứa nút 'Ảnh khác' để lấy thêm 1 ảnh khác cùng tag, không cần
    gõ lại lệnh. Tự vô hiệu hoá nút sau 5 phút để tránh spam vô thời hạn."""

    def __init__(self, tag: str, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.tag = tag

    @discord.ui.button(label="Ảnh khác", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def another_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()  # tìm kiếm có thể mất vài giây
        await fetch_and_reply(interaction, self.tag)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True


SOURCES = [
    ("Unsplash", search_unsplash),
    ("Pexels", search_pexels),
    ("Pixabay", search_pixabay),
]


async def search_all_sources(query: str) -> list[dict]:
    """Random thứ tự các nguồn đang khả dụng, thử lần lượt tới khi có kết quả.

    Nếu 1 nguồn lỗi (rate limit, sai key, mất mạng...) thì tự động fallback
    sang nguồn tiếp theo thay vì báo lỗi luôn cho người dùng.
    """
    available = [(name, fn) for name, fn in SOURCES if _has_key(name)]
    if not available:
        raise RuntimeError(
            "Chưa cấu hình API key nào (UNSPLASH_ACCESS_KEY / PEXELS_API_KEY / PIXABAY_API_KEY)."
        )

    random.shuffle(available)
    last_error = None

    for name, fn in available:
        try:
            images = await fn(query)
            if images:
                return images
        except Exception as e:
            last_error = e
            print(f"[{name}] Lỗi khi tìm ảnh, thử nguồn khác: {e}")
            continue

    if last_error:
        raise last_error
    return []  # tất cả nguồn đều không có kết quả cho từ khóa này


def _has_key(source_name: str) -> bool:
    return {
        "Unsplash": bool(UNSPLASH_ACCESS_KEY),
        "Pexels": bool(PEXELS_API_KEY),
        "Pixabay": bool(PIXABAY_API_KEY),
    }.get(source_name, False)


async def trigger_unsplash_download(download_location: str) -> None:
    """Báo cho Unsplash biết ảnh vừa được sử dụng/hiển thị (bắt buộc theo API Guidelines).

    Chỉ áp dụng cho ảnh lấy từ Unsplash; Pexels/Pixabay không yêu cầu bước này.
    """
    if not download_location:
        return

    headers = {
        "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
        "Accept-Version": "v1",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(download_location, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    print(f"[Unsplash] Cảnh báo: gọi download_location lỗi {resp.status}: {text}")
    except Exception as e:
        print(f"[Unsplash] Cảnh báo: không thể gọi download_location: {e}")


# ---------------------------------------------------------------------------
# Tính năng mới #1: /many_photos — lấy nhiều ảnh cùng tag trong 1 lần gọi
# ---------------------------------------------------------------------------

async def send_many_photos(interaction: discord.Interaction, tag: str, quantity: int) -> None:
    try:
        images = await search_all_sources(tag)
    except Exception as e:
        await interaction.followup.send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
        return

    if not images:
        await interaction.followup.send(f"Không tìm thấy ảnh nào cho từ khóa **{tag}**.")
        return

    chosen_list = random.sample(images, k=min(quantity, len(images)))

    for chosen in chosen_list:
        embed = build_image_embed(tag, chosen, interaction.user.display_name)
        view = ImageView(tag=tag)
        message = await interaction.followup.send(embed=embed, view=view)
        if message is not None:
            register_rated_message(message, tag, chosen["image_url"])
            await add_rating_reactions(message)
        if chosen["source"] == "Unsplash":
            await trigger_unsplash_download(chosen.get("download_location", ""))

    if len(chosen_list) < quantity:
        await interaction.followup.send(
            f"Chỉ tìm được {len(chosen_list)}/{quantity} ảnh khác nhau cho tag **{tag}**."
        )


@bot.tree.command(name="many_photos", description="Lấy nhiều ảnh cùng lúc theo 1 từ khóa")
@app_commands.describe(
    tag="Từ khóa tìm kiếm, ví dụ: núi, hoàng hôn (có thể gõ nhiều từ)",
    quantity="Số lượng ảnh muốn lấy (1-10, mặc định 3)",
)
async def many_photos(
    interaction: discord.Interaction,
    tag: str,
    quantity: app_commands.Range[int, 1, 10] = 3,
):
    tag = tag.strip()
    if not tag:
        await interaction.response.send_message("Vui lòng nhập từ khóa hợp lệ.", ephemeral=True)
        return

    await interaction.response.defer()
    await send_many_photos(interaction, tag, quantity)


# ---------------------------------------------------------------------------
# Tính năng mới #2: rating ảnh bằng reaction 👍/👎 + bảng xếp hạng /top_photos
# ---------------------------------------------------------------------------

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if bot.user is not None and payload.user_id == bot.user.id:
        return  # bỏ qua reaction do chính bot tự thêm vào

    emoji = str(payload.emoji)
    if emoji not in RATING_EMOJIS:
        return

    info = rated_messages.get(payload.message_id)
    if info is None:
        return

    tag, image_url = info["tag"], info["image_url"]
    entry = photo_ratings[tag].setdefault(image_url, {"up": 0, "down": 0})
    if emoji == "👍":
        entry["up"] += 1
    else:
        entry["down"] += 1


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    emoji = str(payload.emoji)
    if emoji not in RATING_EMOJIS:
        return

    info = rated_messages.get(payload.message_id)
    if info is None:
        return

    tag, image_url = info["tag"], info["image_url"]
    entry = photo_ratings[tag].get(image_url)
    if entry is None:
        return
    if emoji == "👍":
        entry["up"] = max(0, entry["up"] - 1)
    else:
        entry["down"] = max(0, entry["down"] - 1)


@bot.tree.command(name="top_photos", description="Xem bảng xếp hạng ảnh được rating cao nhất theo tag")
@app_commands.describe(tag="Tag muốn xem bảng xếp hạng")
async def top_photos(interaction: discord.Interaction, tag: str):
    tag = tag.strip()
    ratings = photo_ratings.get(tag)
    if not ratings:
        await interaction.response.send_message(
            f"Chưa có ảnh nào được rating cho tag **{tag}**.", ephemeral=True
        )
        return

    ranked = sorted(ratings.items(), key=lambda kv: kv[1]["up"] - kv[1]["down"], reverse=True)[:5]

    embed = discord.Embed(title=f"🏆 Top ảnh — {tag}", color=discord.Color.gold())
    lines = []
    for i, (url, score) in enumerate(ranked, start=1):
        lines.append(f"**#{i}** 👍 {score['up']} · 👎 {score['down']} — [Xem ảnh]({url})")
    embed.description = "\n".join(lines)
    embed.set_footer(text="Rating được tính từ reaction 👍/👎, chỉ lưu tạm trong RAM (mất khi bot restart).")

    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# Tính năng mới #3: /photo_battle — 2 ảnh cùng tag đấu nhau bằng vote reaction
# ---------------------------------------------------------------------------

BATTLE_EMOJIS = ("🅰️", "🅱️")


@bot.tree.command(name="photo_battle", description="Đấu ảnh: 2 ảnh cùng tag, mọi người vote ảnh đẹp hơn")
@app_commands.describe(
    tag="Từ khóa cho 2 ảnh đối đầu",
    duration_minutes="Thời gian cho phép vote, tính bằng phút (1-30, mặc định 3)",
)
async def photo_battle(
    interaction: discord.Interaction,
    tag: str,
    duration_minutes: app_commands.Range[int, 1, 30] = 3,
):
    tag = tag.strip()
    if not tag:
        await interaction.response.send_message("Vui lòng nhập từ khóa hợp lệ.", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        images = await search_all_sources(tag)
    except Exception as e:
        await interaction.followup.send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
        return

    if len(images) < 2:
        await interaction.followup.send(f"Không đủ ảnh khác nhau cho tag **{tag}** để đấu ảnh.")
        return

    photo_a, photo_b = random.sample(images, 2)

    embed_a = discord.Embed(
        title=f"⚔️ Đấu ảnh: {tag}",
        description=(
            f"Vote 🅰️ hoặc 🅱️ cho ảnh đẹp hơn! Kết quả sẽ công bố sau {duration_minutes} phút.\n\n"
            f"🅰️ — Nguồn: {photo_a['source']} · Ảnh của {photo_a['author']}\n"
            f"🅱️ — Nguồn: {photo_b['source']} · Ảnh của {photo_b['author']}"
        ),
        color=discord.Color.purple(),
    )
    embed_a.set_image(url=photo_a["image_url"])

    embed_b = discord.Embed(color=discord.Color.purple())
    embed_b.set_image(url=photo_b["image_url"])

    message = await interaction.followup.send(embeds=[embed_a, embed_b])
    for emoji in BATTLE_EMOJIS:
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            pass

    for chosen in (photo_a, photo_b):
        if chosen["source"] == "Unsplash":
            await trigger_unsplash_download(chosen.get("download_location", ""))

    await asyncio.sleep(duration_minutes * 60)
    await announce_battle_result(message, tag)


async def announce_battle_result(message: discord.Message, tag: str) -> None:
    try:
        message = await message.channel.fetch_message(message.id)
    except discord.HTTPException:
        return

    votes_a = votes_b = 0
    for reaction in message.reactions:
        emoji = str(reaction.emoji)
        if emoji == "🅰️":
            votes_a = max(0, reaction.count - 1)  # trừ reaction do bot tự thêm
        elif emoji == "🅱️":
            votes_b = max(0, reaction.count - 1)

    if votes_a > votes_b:
        result = f"🅰️ thắng với {votes_a} vote (so với {votes_b} vote của 🅱️)!"
    elif votes_b > votes_a:
        result = f"🅱️ thắng với {votes_b} vote (so với {votes_a} vote của 🅰️)!"
    else:
        result = f"Hoà! Cả hai ảnh đều có {votes_a} vote."

    await message.reply(f"⏰ Hết giờ đấu ảnh **{tag}**! {result}")


# ---------------------------------------------------------------------------
# Tính năng mới #4: /guess_location — đoán tên địa danh qua ảnh
# ---------------------------------------------------------------------------

# channel_id -> {"answer_tag": str, "accepted": list[str]}
active_guess_games: dict[int, dict] = {}


def normalize_text(text: str) -> str:
    """Bỏ dấu tiếng Việt + viết thường, dùng để so khớp câu trả lời linh hoạt hơn."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


@bot.tree.command(name="guess_location", description="Đoán tên địa danh qua 1 tấm ảnh (ẩn tên)")
async def guess_location(interaction: discord.Interaction):
    if interaction.channel_id in active_guess_games:
        await interaction.response.send_message(
            "Đang có 1 ván đoán địa danh chưa kết thúc trong kênh này, chờ ván trước xong đã nhé.",
            ephemeral=True,
        )
        return

    answer_tag = random.choice(list(GUESS_LOCATIONS.keys()))

    await interaction.response.defer()
    try:
        images = await search_all_sources(answer_tag)
    except Exception as e:
        await interaction.followup.send(f"Có lỗi xảy ra khi tìm ảnh: {e}")
        return

    if not images:
        await interaction.followup.send("Không tìm được ảnh cho vòng chơi này, thử lại sau nhé.")
        return

    chosen = random.choice(images)

    embed = discord.Embed(
        title="🗺️ Đoán địa danh!",
        description="Đây là địa danh nào? Trả lời trực tiếp trong kênh này, ai đúng đầu tiên thắng!",
        color=discord.Color.green(),
    )
    embed.set_image(url=chosen["image_url"])
    embed.set_footer(text=f"Nguồn: {chosen['source']}")

    await interaction.followup.send(embed=embed)

    if chosen["source"] == "Unsplash":
        await trigger_unsplash_download(chosen.get("download_location", ""))

    active_guess_games[interaction.channel_id] = {
        "answer_tag": answer_tag,
        "accepted": GUESS_LOCATIONS[answer_tag],
    }


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    game = active_guess_games.get(message.channel.id)
    if game:
        guess = normalize_text(message.content)
        if any(normalize_text(ans) in guess for ans in game["accepted"]):
            del active_guess_games[message.channel.id]
            await message.reply(
                f"🎉 Chính xác, {message.author.mention}! Địa danh trong ảnh là **{game['answer_tag']}**."
            )

    # Vẫn cần gọi để các lệnh dạng prefix (!) nếu có trong tương lai vẫn hoạt động
    await bot.process_commands(message)


# ---------------------------------------------------------------------------
# Sự kiện & lệnh gốc
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    active_sources = [name for name, _ in SOURCES if _has_key(name)]
    print(f"Đã đăng nhập với tên {bot.user}. Nguồn ảnh đang bật: {', '.join(active_sources) or 'KHÔNG CÓ'}")


@bot.tree.command(name="photo", description="Lấy một ảnh ngẫu nhiên theo từ khóa")
@app_commands.describe(tag="Từ khóa tìm kiếm, ví dụ: hoàng hôn, trường sa (có thể gõ nhiều từ)")
async def photo(interaction: discord.Interaction, tag: str):
    tag = tag.strip()
    if not tag:
        await interaction.response.send_message("Vui lòng nhập từ khóa hợp lệ.", ephemeral=True)
        return

    await interaction.response.defer()  # tìm kiếm có thể mất vài giây
    await fetch_and_reply(interaction, tag)


@bot.tree.command(name="random_photo", description="Lấy một ảnh với chủ đề ngẫu nhiên, không cần nhập từ khóa")
async def random_photo(interaction: discord.Interaction):
    tag = random.choice(RANDOM_TAGS)
    await interaction.response.defer()
    await fetch_and_reply(interaction, tag)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("Thiếu DISCORD_TOKEN trong file .env.")
    if not any([UNSPLASH_ACCESS_KEY, PEXELS_API_KEY, PIXABAY_API_KEY]):
        raise SystemExit(
            "Cần ít nhất 1 API key ảnh: UNSPLASH_ACCESS_KEY, PEXELS_API_KEY, hoặc PIXABAY_API_KEY."
        )
    bot.run(DISCORD_TOKEN)