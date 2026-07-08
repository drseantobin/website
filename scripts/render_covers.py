#!/usr/bin/env python3
"""Render flat book covers into realistic 3/4-view 3D book mockups:
perspective-turned front cover, thin receding fore-edge pages, soft ground
shadow. Thickness scales with page count. Trims baked-in white borders first.
Output: assets/covers/3d/<slug>.png (transparent)."""
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "covers"
OUT = SRC / "3d"
OUT.mkdir(exist_ok=True)

# DEPRECATED / SUPERSEDED. All six 3D covers in assets/covers/3d/ are now real
# photorealistic mockups: big-god-little-devil is the transparent render from
# biggodlittledevil.com; the other five were generated in the ChatGPT app from
# the flat covers in My Drive/Website/covers-to-render (paperback, transparent).
# Do NOT run this script — it would clobber those good renders. Kept for history.
BOOKS = {}

FH = 1180          # front cover height (px) before perspective
PAD = 130          # canvas padding


def trim_white(im, thresh=16):
    im = im.convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg).convert("L").point(lambda p: 255 if p > thresh else 0)
    bbox = diff.getbbox()
    return im.crop(bbox) if bbox else im


def lerp(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def solve8(A, b):
    n = 8
    M = [A[i][:] + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        pv = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pv
        for r in range(n):
            if r != col and M[r][col]:
                f = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= f * M[col][j]
    return [M[i][n] for i in range(n)]


def find_coeffs(dst, src):
    """coeffs mapping OUTPUT quad `dst` back to INPUT points `src` for PIL."""
    A, b = [], []
    for (X, Y), (u, v) in zip(dst, src):
        A.append([X, Y, 1, 0, 0, 0, -X * u, -Y * u]); b.append(u)
        A.append([0, 0, 0, X, Y, 1, -X * v, -Y * v]); b.append(v)
    return solve8(A, b)


def render(slug, pages):
    src = SRC / f"{slug}.jpg"
    if not src.exists():
        print("  skip (no source):", slug); return
    cover = trim_white(Image.open(src)).convert("RGBA")
    aspect = cover.width / cover.height
    fw = round(FH * aspect)
    cover = cover.resize((fw, FH), Image.LANCZOS)

    # bake edge detail onto the flat cover so it follows the perspective
    cd = ImageDraw.Draw(cover)
    # left binding: soft dark gradient over ~7%
    bw = max(8, round(fw * 0.07))
    band = Image.new("L", (bw, 1), 0)
    bl = band.load()
    for x in range(bw):
        bl[x, 0] = int(max(0, (1 - x / bw)) * 120)
    band = band.resize((bw, FH))
    dark = Image.new("RGBA", (bw, FH), (18, 14, 24, 255)); dark.putalpha(band)
    cover.alpha_composite(dark, (0, 0))
    # fore-edge crease at right + crisp border
    cd.line([(fw - 2, 0), (fw - 2, FH)], fill=(120, 104, 78, 150), width=2)
    cd.rectangle([0, 0, fw - 1, FH - 1], outline=(34, 27, 19, 170), width=2)
    cd.line([(1, 0), (fw - 2, 0)], fill=(255, 255, 255, 55), width=1)

    # ---- geometry (subtle 3/4 turn: right edge shorter & receding) ----
    turn = round(FH * 0.045)
    d = max(14, min(60, round(pages * 0.22)))     # page thickness
    px, py = PAD, PAD
    TL = (px, py)
    TR = (px + fw, py + turn)
    BR = (px + fw, py + FH - turn)
    BL = (px, py + FH)
    cover_quad = [TL, TR, BR, BL]

    W = PAD * 2 + fw + d
    H = PAD * 2 + FH
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # far corners of the fore-edge page block (recede up-right)
    def rec(pt, k):
        return (pt[0] + k, pt[1] - round(0.30 * k))
    TR2, BR2 = rec(TR, d), rec(BR, d)

    # ---- soft ground shadow ----
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sil = [TL, TR, TR2, BR2, BR, BL]
    sil = [(x + 6, y + 30) for (x, y) in sil]
    ImageDraw.Draw(shadow).polygon(sil, fill=(20, 17, 34, 120))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(34)))

    draw = ImageDraw.Draw(canvas)

    # ---- fore-edge pages (vertical stripes stepped along depth) ----
    pa, pb = (240, 231, 213), (207, 195, 171)
    for k in range(d, -1, -1):
        t = k / max(1, d)
        shade = 1 - 0.20 * t
        col = lerp(pa, pb, (k % 5) / 5.0)
        col = tuple(round(c * shade) for c in col)
        a = rec(TR, k); b2 = rec(BR, k)
        draw.line([a, b2], fill=col + (255,), width=1)
    # seam line where pages meet the cover
    draw.line([TR, BR], fill=(90, 78, 58, 160), width=1)

    # ---- perspective-warped front cover ----
    coeffs = find_coeffs(cover_quad, [(0, 0), (fw, 0), (fw, FH), (0, FH)])
    warped = cover.transform((W, H), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC)
    canvas.alpha_composite(warped)

    canvas.save(OUT / f"{slug}.png")
    print(f"  {slug:22} pages={pages:<4} depth={d}px  front {fw}x{FH}")


if __name__ == "__main__":
    print("rendering 3D covers →", OUT)
    for slug, pages in BOOKS.items():
        render(slug, pages)
    print("done")
