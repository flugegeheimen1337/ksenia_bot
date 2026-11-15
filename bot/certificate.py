"""Сертификат в конце квеста: имя из Telegram встаёт в пустую строку шаблона."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from bot.config import MEDIA_DIR
from bot.content import CERTIFICATE

FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf")
# Прямоугольник внутри пустой плашки шаблона 1280×853.
NAME_BOX = (210, 366, 950, 448)
INK = (18, 44, 72)
FALLBACK_NAME = "Путешественник"


def traveler_name(user: object | None) -> str:
    if user is None:
        return FALLBACK_NAME
    first = str(getattr(user, "first_name", "") or "").strip()
    last = str(getattr(user, "last_name", "") or "").strip()
    name = " ".join(part for part in (first, last) if part)
    if name:
        return name
    username = str(getattr(user, "username", "") or "").strip()
    return username or FALLBACK_NAME


def render_certificate(name: str) -> Image.Image:
    image = Image.open(MEDIA_DIR / CERTIFICATE).convert("RGB")
    draw = ImageDraw.Draw(image)
    text = _clean(name)
    left, top, right, bottom = NAME_BOX
    font = _fit(draw, text, right - left, bottom - top)
    draw.text(
        ((left + right) / 2, (top + bottom) / 2),
        text,
        font=font,
        fill=INK,
        anchor="mm",
    )
    return image


def _clean(name: str) -> str:
    text = " ".join(str(name).replace("\n", " ").split())
    text = "".join(char for char in text if char.isprintable())
    return text[:80] or FALLBACK_NAME


def _fit(draw: ImageDraw.ImageDraw, text: str, max_width: int, max_height: int) -> ImageFont.FreeTypeFont:
    size = 56
    while size > 16:
        font = ImageFont.truetype(FONT_PATH, size)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            return font
        size -= 2
    return ImageFont.truetype(FONT_PATH, 16)
