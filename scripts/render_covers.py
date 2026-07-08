#!/usr/bin/env python3
"""Render flat book covers into realistic 3D book mockups (front + top + fore-edge
pages), thickness proportional to page count. Trims baked-in white borders first.
Output: assets/covers/3d/<slug>.png (transparent)."""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "covers"
OUT = SRC / "3d"
OUT.mkdir(exist_ok=True)

# slug : page count (estimates — edit freely; controls how thick the book looks)
BOOKS = {
    "remaining-human": 140,
    "big-god-little-devil": 224,
    "sick-seven": 32,
    "workbook": 80,
    "humanity": 208,
    "heart-of-exorcism": 176,
}

FH = 1160          # front cover height in px
PAD = 110          # canvas padding (room for shadow + top face)


def trim_white(im, thresh=16):
    """Crop uniform near-white border."""
    im = im.convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda p: 255 if p > thresh else 0)
    bbox = diff.getbbox()
    return im.crop(bbox) if bbox else im


def lerp(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def render(slug, pages):
    src = SRC / f"{slug}.jpg"
    if not src.exists():
        print("  skip (no source):", slug); return
    cover = trim_white(Image.open(src))
    aspect = cover.width / cover.height
    fw = round(FH * aspect)
    cover = cover.resize((fw, FH), Image.LANCZOS)

    # thickness (depth) in px, scaled by page count
    d = max(16, min(70, round(pages * 0.24)))
    dy = round(d * 0.58)                      # vertical skew of the extrusion (up-right)

    W = PAD * 2 + fw + d
    H = PAD * 2 + FH + dy
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # front cover anchor
    fx, fy = PAD, PAD + dy
    FLt, FRt = (fx, fy), (fx + fw, fy)
    FLb, FRb = (fx, fy + FH), (fx + fw, fy + FH)

    # ---- drop shadow (silhouette, blurred, offset down-right) ----
    ox, oy = 16, 22
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sil = [FLt, (FLt[0] + d, FLt[1] - dy), (FRt[0] + d, FRt[1] - dy),
           (FRb[0] + d, FRb[1] - dy), FRb, FLb]
    sil = [(x + ox, y + oy) for (x, y) in sil]
    sd.polygon(sil, fill=(18, 16, 40, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    canvas.alpha_composite(shadow)

    draw = ImageDraw.Draw(canvas)

    # ---- top face (page tops): horizontal stripes stepped along depth ----
    top_a, top_b = (247, 241, 227), (232, 223, 205)
    for k in range(d, -1, -1):
        t = k / d
        shade = 1 - 0.10 * t
        col = lerp(top_a, top_b, (k % 6) / 6.0)
        col = tuple(round(c * shade) for c in col)
        y_off = round(dy * t)
        draw.line([(FLt[0] + k, FLt[1] - y_off), (FRt[0] + k, FRt[1] - y_off)], fill=col + (255,))

    # ---- right fore-edge (pages): vertical stripes stepped along depth ----
    re_a, re_b = (238, 229, 211), (214, 203, 180)
    for k in range(d, -1, -1):
        t = k / d
        shade = 1 - 0.16 * t
        col = lerp(re_a, re_b, (k % 5) / 5.0)
        col = tuple(round(c * shade) for c in col)
        y_off = round(dy * t)
        draw.line([(FRt[0] + k, FRt[1] - y_off), (FRb[0] + k, FRb[1] - y_off)], fill=col + (255,))

    # ---- front cover ----
    canvas.paste(cover, (fx, fy))

    # binding shadow (left) + fore-edge contact shadow (right) on the cover
    grad = Image.new("L", (fw, 1), 0)
    gp = grad.load()
    for x in range(fw):
        left = max(0, 1 - x / (fw * 0.06)) * 90        # dark spine gradient
        right = max(0, 1 - (fw - 1 - x) / (fw * 0.02)) * 60
        gp[x, 0] = int(min(120, left + right))
    shade_col = grad.resize((fw, FH))
    dark = Image.new("RGBA", (fw, FH), (20, 16, 30, 255))
    dark.putalpha(shade_col)
    canvas.alpha_composite(dark, (fx, fy))

    # crisp edge around the front cover
    draw.rectangle([FLt, FRb], outline=(0, 0, 0, 60), width=1)
    # thin highlight along the very top edge of the cover
    draw.line([FLt, FRt], fill=(255, 255, 255, 40), width=1)

    canvas.save(OUT / f"{slug}.png")
    print(f"  {slug:22} pages={pages:<4} depth={d}px  {cover.width}x{cover.height} front")


if __name__ == "__main__":
    print("rendering 3D covers →", OUT)
    for slug, pages in BOOKS.items():
        render(slug, pages)
    print("done")
