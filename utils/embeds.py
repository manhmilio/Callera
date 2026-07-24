import discord

from services import ImageResult


def build_image_embed(tag: str, result: ImageResult, requester_name: str) -> discord.Embed:
    """Tạo embed hiển thị 1 ảnh kèm thông tin nguồn/tác giả. Dùng chung cho
    /photo, /random_photo, /many_photos và nút "Ảnh khác" để tránh lặp code."""
    embed = discord.Embed(title=f"Kết quả cho: {tag}", color=discord.Color.blue())
    embed.set_image(url=result.image_url)
    embed.set_footer(text=f"Yêu cầu bởi {requester_name} · Nguồn: {result.source}")

    credit = f"[{result.author}]({result.author_link})" if result.author_link else result.author
    embed.add_field(name="Ảnh của", value=credit, inline=True)
    return embed
