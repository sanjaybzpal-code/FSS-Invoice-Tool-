"""Provide a stamp image for invoices.

If the user drops their own scanned stamp at the configured path
(assets/stamp.png), it is used as-is. Otherwise a clean default round
rubber-stamp is generated automatically so a stamp always appears.
"""

from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
NAVY = (31, 56, 100, 255)


def _font(size: int):
    for name in ("seguibd.ttf", "arialbd.ttf", "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_size(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _draw_arc_text(draw, center, radius, text, font, color, top=True):
    cx, cy = center
    total = math.radians(min(len(text) * 9, 200))
    start = -math.pi / 2 - total / 2 if top else math.pi / 2 - total / 2
    step = total / max(len(text) - 1, 1)
    for i, ch in enumerate(text):
        ang = start + i * step
        if not top:
            ang = math.pi / 2 + total / 2 - i * step
        x = cx + radius * math.cos(ang)
        y = cy + radius * math.sin(ang)
        img = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w, h = _text_size(d, ch, font)
        d.text(((60 - w) / 2, (60 - h) / 2 - 4), ch, font=font, fill=color)
        rot = -math.degrees(ang) - 90 if top else -math.degrees(ang) + 90
        img = img.rotate(rot, resample=Image.BICUBIC, center=(30, 30))
        draw._image.paste(img, (int(x - 30), int(y - 30)), img)


def generate_default_stamp(path: str, seller: dict) -> None:
    size = 620
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw._image = img  # used by _draw_arc_text

    cx = cy = size // 2
    # concentric rings
    draw.ellipse([18, 18, size - 18, size - 18], outline=NAVY, width=9)
    draw.ellipse([70, 70, size - 70, size - 70], outline=NAVY, width=4)

    name = (seller.get("name") or "FACADE STRUCTURAL SERVICES").upper()
    gstin = seller.get("gstin", "")

    _draw_arc_text(draw, (cx, cy), 240, name, _font(40), NAVY, top=True)
    _draw_arc_text(draw, (cx, cy), 240, f"GSTIN {gstin}", _font(30), NAVY,
                   top=False)

    # center star + label
    f_center = _font(34)
    label = "AUTHORISED"
    w, h = _text_size(draw, label, f_center)
    draw.text((cx - w / 2, cy - 58), label, font=f_center, fill=NAVY)
    label2 = "SIGNATORY"
    w2, h2 = _text_size(draw, label2, f_center)
    draw.text((cx - w2 / 2, cy - 14), label2, font=f_center, fill=NAVY)
    # small star
    star_f = _font(48)
    sw, sh = _text_size(draw, "*", star_f)
    draw.text((cx - sw / 2, cy + 34), "*", font=star_f, fill=NAVY)

    img.save(path)


def ensure_stamp(config: dict) -> str | None:
    """Return a path to a stamp image, generating a default if needed."""
    seller = config.get("seller", {})
    rel = seller.get("stamp_image") or os.path.join("assets", "stamp.png")
    path = rel if os.path.isabs(rel) else os.path.join(HERE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        return path
    try:
        generate_default_stamp(path, seller)
        return path
    except Exception:  # noqa: BLE001 - stamp is optional, never block invoice
        return None
