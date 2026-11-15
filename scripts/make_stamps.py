#!/usr/bin/env python3
"""Рисует штампы паспорта и общий разворот.

На Яндекс.Диске отдельных картинок штампов не было. Скрипт собирает их сам.
Если положить свои файлы media/stamps/01.png … 10.png и запустить скрипт
без --force, он не перезапишет штампы, а только заново соберёт разворот.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "media" / "stamps"

SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

PAPER = (251, 246, 236, 255)
INK_ALPHA = 235


@dataclass(frozen=True)
class StampSpec:
    num: str
    line1: str
    line2: str
    rgb: tuple[int, int, int]


STAMPS = (
    StampSpec("01", "СЕВЕРНАЯ", "ГОСТИНИЦА", (148, 32, 48)),
    StampSpec("02", "ВЕЧНЫЙ", "ОГОНЬ", (22, 58, 112)),
    StampSpec("03", "ПРОСПЕКТ", "К. МАРКСА", (20, 92, 64)),
    StampSpec("04", "УНИВЕРМАГ", "КАРЕЛИЯ", (128, 52, 18)),
    StampSpec("05", "ТЕАТРАЛЬНАЯ", "ПЛОЩАДЬ", (116, 28, 62)),
    StampSpec("06", "СОБОРНЫЙ", "СКВЕР", (26, 64, 102)),
    StampSpec("07", "ПУШКА", "ЗАВОДА", (98, 52, 24)),
    StampSpec("08", "НАЦИОНАЛЬНАЯ", "БИБЛИОТЕКА", (32, 48, 96)),
    StampSpec("09", "ДВОРЕЦ", "ЗАГС", (132, 36, 52)),
    StampSpec("10", "РОТОНДА", "ОНЕЖСКАЯ", (74, 44, 28)),
)

ROTATIONS = (-8, 5, -4, 7, -6, 4, -3, 6, -5, 3)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    if not Path(path).exists():
        raise SystemExit(f"Нет шрифта {path}. Установите fonts-dejavu-core.")
    return ImageFont.truetype(path, size)


def ink(rgb: tuple[int, int, int], alpha: int = INK_ALPHA) -> tuple[int, int, int, int]:
    return (rgb[0], rgb[1], rgb[2], alpha)


def paper_background(size: int) -> Image.Image:
    base = Image.new("RGBA", (size, size), PAPER)
    noise = Image.effect_noise((size, size), 18).convert("L")
    noise = ImageEnhance.Contrast(noise).enhance(0.35)
    grain = Image.new("RGBA", (size, size), (120, 96, 64, 0))
    alpha = noise.point(lambda p: int((p - 128) * 0.18 + 28))
    grain.putalpha(alpha)
    return Image.alpha_composite(base, grain)


def fit_font(text: str, max_width: int, start: int, face: str) -> ImageFont.FreeTypeFont:
    size = start
    while size > 18:
        current = font(face, size)
        if current.getlength(text) <= max_width:
            return current
        size -= 2
    return font(face, 18)


def paste_rotated_text(
    base: Image.Image,
    text: str,
    cx: float,
    cy: float,
    radius: float,
    face: str,
    size: int,
    fill: tuple[int, int, int, int],
    start_deg: float,
    end_deg: float,
) -> None:
    """Кладет буквы по дуге. 0° — верх, угол растет по часовой стрелке."""
    used = font(face, size)
    widths = []
    for ch in text:
        widths.append(used.getlength(ch) + (size * 0.12 if ch == " " else size * 0.04))
    total = sum(widths) or 1
    span = end_deg - start_deg
    angle = start_deg
    for ch, width in zip(text, widths):
        mid = angle + (span * (width / total)) / 2
        if ch != " ":
            glyph = Image.new("RGBA", (size * 3, size * 3), (0, 0, 0, 0))
            draw = ImageDraw.Draw(glyph)
            draw.text((size, size), ch, font=used, fill=fill, anchor="mm")
            bbox = glyph.getbbox()
            if bbox:
                glyph = glyph.crop(bbox)
            # Низ буквы смотрит к центру круга.
            rotated = glyph.rotate(-mid, expand=True, resample=Image.Resampling.BICUBIC)
            x = cx + radius * math.sin(math.radians(mid))
            y = cy - radius * math.cos(math.radians(mid))
            base.alpha_composite(
                rotated,
                (int(x - rotated.width / 2), int(y - rotated.height / 2)),
            )
        angle += span * (width / total)


def draw_rings(img: Image.Image, rgb: tuple[int, int, int]) -> None:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx = cy = img.size[0] // 2
    color = ink(rgb)
    soft = ink(rgb, 90)
    draw.ellipse((cx - 390, cy - 390, cx + 390, cy + 390), outline=soft, width=28)
    draw.ellipse((cx - 372, cy - 372, cx + 372, cy + 372), outline=color, width=8)
    draw.ellipse((cx - 348, cy - 348, cx + 348, cy + 348), outline=color, width=3)
    draw.ellipse((cx - 250, cy - 250, cx + 250, cy + 250), outline=ink(rgb, 160), width=2)
    img.alpha_composite(overlay)


def draw_center(img: Image.Image, spec: StampSpec) -> None:
    draw = ImageDraw.Draw(img)
    cx = cy = img.size[0] // 2
    color = ink(spec.rgb, 245)
    number_font = font(SERIF, 42)
    draw.text((cx, cy - 118), f"№ {spec.num}", font=number_font, fill=color, anchor="mm")
    accent = ink(spec.rgb, 190)
    for dx in (-46, 0, 46):
        draw.regular_polygon((cx + dx, cy - 68, 8), 4, rotation=45, fill=accent)
    line1 = fit_font(spec.line1, 460, 64, SERIF)
    line2 = fit_font(spec.line2, 460, 64, SERIF)
    draw.text((cx, cy - 10), spec.line1, font=line1, fill=color, anchor="mm")
    draw.text((cx, cy + 62), spec.line2, font=line2, fill=color, anchor="mm")
    small = font(SANS, 22)
    draw.text((cx, cy + 130), "ПЕТРОЗАВОДСК", font=small, fill=ink(spec.rgb, 200), anchor="mm")


def make_stamp(spec: StampSpec) -> Image.Image:
    img = paper_background(900)
    draw_rings(img, spec.rgb)
    cx = cy = 450
    color = ink(spec.rgb, 230)
    paste_rotated_text(
        img,
        "ПЕТРОЗАВОДСК  ·  КАРЕЛИЯ",
        cx,
        cy,
        312,
        SANS,
        28,
        color,
        -78,
        78,
    )
    paste_rotated_text(
        img,
        "ПАСПОРТ  ПУТЕШЕСТВЕННИКА",
        cx,
        cy,
        312,
        SANS,
        26,
        color,
        102,
        258,
    )
    # Fix the accidental triple S if I typed it. Checked below.
    draw_center(img, spec)
    return img


def circular(image: Image.Image) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).ellipse((1, 1, image.size[0] - 2, image.size[1] - 2), fill=255)
    result = image.copy()
    result.putalpha(mask)
    return result


def make_spread(stamps: list[Image.Image]) -> Image.Image:
    width, height = 2800, 1900
    page = Image.new("RGBA", (width, height), (92, 42, 36, 255))
    sheet = Image.new("RGBA", (width - 64, height - 64), PAPER)
    noise = Image.effect_noise(sheet.size, 14).convert("L")
    grain = Image.new("RGBA", sheet.size, (140, 110, 70, 0))
    grain.putalpha(noise.point(lambda p: 22))
    sheet = Image.alpha_composite(sheet, grain)
    page.paste(sheet, (32, 32))
    draw = ImageDraw.Draw(page)
    spine_top, spine_bottom = 200, height - 110
    draw.rectangle((width // 2 - 16, spine_top, width // 2 + 16, spine_bottom), fill=(126, 36, 44, 255))
    for y in range(spine_top + 24, spine_bottom - 10, 28):
        draw.arc((width // 2 - 10, y, width // 2 + 10, y + 16), 200, 340, fill=(255, 236, 214, 180), width=2)

    title_font = font(SERIF, 58)
    sub_font = font(SERIF_REG, 30)
    draw.text((700, 88), "ПАСПОРТ", font=title_font, fill=(126, 36, 44, 255), anchor="mm")
    draw.text((2100, 88), "ПУТЕШЕСТВЕННИКА", font=title_font, fill=(126, 36, 44, 255), anchor="mm")
    draw.text(
        (width // 2, 158),
        "Петрозаводск за один день",
        font=sub_font,
        fill=(90, 62, 48, 255),
        anchor="mm",
    )

    # По пять штампов на страницу: два, два и один по центру.
    left = ((460, 560), (980, 560), (460, 980), (980, 980), (720, 1400))
    right = ((1820, 560), (2340, 560), (1820, 980), (2340, 980), (2080, 1400))
    positions = left + right
    for image, (x, y), rotation in zip(stamps, positions, ROTATIONS):
        tile = circular(image).resize((340, 340), Image.Resampling.LANCZOS)
        tile = tile.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
        page.alpha_composite(tile, (x - tile.width // 2, y - tile.height // 2))

    foot = font(SANS, 26)
    draw.text(
        (width // 2, height - 62),
        "Штампы девяти точек маршрута",
        font=foot,
        fill=(90, 62, 48, 220),
        anchor="mm",
    )
    return page.filter(ImageFilter.SMOOTH_MORE)


def build(force: bool) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    images: list[Image.Image] = []
    for spec in STAMPS:
        path = OUT / f"{spec.num}.png"
        if force or not path.exists():
            image = make_stamp(spec)
            image.save(path, "PNG")
            print(f"stamp {path.name}")
        images.append(Image.open(path).convert("RGBA"))
    spread = make_spread(images)
    spread_path = OUT / "spread.png"
    spread.convert("RGB").save(spread_path, "PNG")
    print(f"spread {spread_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="перерисовать и сами штампы")
    args = parser.parse_args()
    build(force=args.force)


if __name__ == "__main__":
    main()
