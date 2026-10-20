"""
AEGIS Logo Asset Extraction & Keying Utility (tools/extract_logo.py)
Extracts embedded logo image from AEGIS_logo_exact.svg, applies luminance keying
for smooth glow falloff over transparency, and exports:
 - Frontend/assets/aegis-lockup.png (transparent, 1200px wide)
 - Frontend/assets/aegis-mark.png (transparent, square)
 - Frontend/assets/aegis-mark-64.png (64x64 icon)
 - Frontend/favicon.ico (multi-res favicon from mark)
"""

import base64
import io
import re
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
SVG_PATH = BASE_DIR / "Frontend" / "assets" / "AEGIS_logo_exact.svg"
ASSETS_DIR = BASE_DIR / "Frontend" / "assets"
FAVICON_PATH = BASE_DIR / "Frontend" / "favicon.ico"


def extract_and_key():
    print(f"Reading {SVG_PATH}...")
    with open(SVG_PATH, "r", encoding="utf-8") as f:
        svg_text = f.read()

    m = re.search(r'href=["\']data:image/png;base64,([^"\']+)["\']', svg_text)
    if not m:
        raise ValueError("Could not find embedded PNG in SVG")

    raw_bytes = base64.b64decode(m.group(1))
    src_img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    w, h = src_img.size
    print(f"Extracted source image: {w}x{h}")

    # Estimate background dark tone from outer 2-pixel borders
    border_pixels = []
    for x in range(w):
        border_pixels.append(src_img.getpixel((x, 0)))
        border_pixels.append(src_img.getpixel((x, h - 1)))
    for y in range(h):
        border_pixels.append(src_img.getpixel((0, y)))
        border_pixels.append(src_img.getpixel((w - 1, y)))

    bg_r = sum(p[0] for p in border_pixels) / len(border_pixels)
    bg_g = sum(p[1] for p in border_pixels) / len(border_pixels)
    bg_b = sum(p[2] for p in border_pixels) / len(border_pixels)
    print(f"Sampled background: R={bg_r:.2f}, G={bg_g:.2f}, B={bg_b:.2f}")

    # Process pixels with luminance key
    src_bytes = src_img.tobytes()
    rgba_bytes = bytearray(w * h * 4)
    noise_floor = 12.0

    for i in range(w * h):
        r = src_bytes[i * 3]
        g = src_bytes[i * 3 + 1]
        b = src_bytes[i * 3 + 2]

        r_net = max(0.0, float(r) - bg_r)
        g_net = max(0.0, float(g) - bg_g)
        b_net = max(0.0, float(b) - bg_b)

        lum = 0.2126 * r_net + 0.7152 * g_net + 0.0722 * b_net
        max_c = max(r_net, g_net, b_net)
        val = max(lum, max_c * 0.75)

        if val <= noise_floor:
            rgba_bytes[i * 4] = 0
            rgba_bytes[i * 4 + 1] = 0
            rgba_bytes[i * 4 + 2] = 0
            rgba_bytes[i * 4 + 3] = 0
        else:
            t = (val - noise_floor) / (220.0 - noise_floor)
            t = min(1.0, max(0.0, t))
            alpha = t ** 0.85
            a = int(round(alpha * 255.0))

            factor = max(alpha, 0.15)
            out_r = min(255, int(round(r_net / factor)))
            out_g = min(255, int(round(g_net / factor)))
            out_b = min(255, int(round(b_net / factor)))

            rgba_bytes[i * 4] = out_r
            rgba_bytes[i * 4 + 1] = out_g
            rgba_bytes[i * 4 + 2] = out_b
            rgba_bytes[i * 4 + 3] = a

    full_keyed = Image.frombytes("RGBA", (w, h), bytes(rgba_bytes))

    # 1. aegis-lockup.png (eye plus wordmark, cropped to content, ~1200px wide)
    lockup_bbox = full_keyed.getbbox()
    print(f"Lockup bounding box: {lockup_bbox}")
    lockup_crop = full_keyed.crop(lockup_bbox)
    lw, lh = lockup_crop.size

    target_w = 1200
    target_h = int(round(lh * (target_w / lw)))
    lockup_1200 = lockup_crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    lockup_path = ASSETS_DIR / "aegis-lockup.png"
    lockup_1200.save(lockup_path, "PNG", optimize=True)
    print(f"Saved {lockup_path} ({target_w}x{target_h})")

    # 2. aegis-mark.png (eye only, transparent, cropped square)
    # The gap between mark and wordmark is around y=795
    mark_crop_raw = full_keyed.crop((0, 0, w, 795))
    mark_bbox = mark_crop_raw.getbbox()
    mark_content = mark_crop_raw.crop(mark_bbox)
    mw, mh = mark_content.size
    print(f"Mark content dimensions: {mw}x{mh}")

    # Make square with centered content
    square_size = max(mw, mh)
    mark_square = Image.new("RGBA", (square_size, square_size), (0, 0, 0, 0))
    pad_x = (square_size - mw) // 2
    pad_y = (square_size - mh) // 2
    mark_square.paste(mark_content, (pad_x, pad_y))

    mark_path = ASSETS_DIR / "aegis-mark.png"
    mark_square.save(mark_path, "PNG", optimize=True)
    print(f"Saved {mark_path} ({square_size}x{square_size})")

    # 3. aegis-mark-64.png and favicon.ico
    mark_64 = mark_square.resize((64, 64), Image.Resampling.LANCZOS)
    mark_64_path = ASSETS_DIR / "aegis-mark-64.png"
    mark_64.save(mark_64_path, "PNG", optimize=True)
    print(f"Saved {mark_64_path} (64x64)")

    # Save favicon.ico (multi-resolution: 16, 32, 48, 64)
    mark_square.save(
        FAVICON_PATH,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )
    print(f"Saved {FAVICON_PATH} (multi-size ICO)")

    # Also save in ASSETS_DIR just in case
    mark_square.save(
        ASSETS_DIR / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )


if __name__ == "__main__":
    extract_and_key()
