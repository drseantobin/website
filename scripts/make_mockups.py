#!/usr/bin/env python3
"""Turn a flat book cover into a 3D angled paperback mockup (white bg),
matching the look of the Big God, Little Devil render. Zero deps beyond Pillow.

Reads assets/covers/src/*.{png,jpg} and writes assets/covers/<name>.jpg
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "covers" / "src"
OUT = ROOT / "assets" / "covers"


def solve(A, b):
    """Solve A x = b for an 8x8 system via Gaussian elimination (pure Python)."""
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        M[col], M[piv] = M[piv], M[col]
        pivot = M[col][col]
        for j in range(col, n + 1):
            M[col][j] /= pivot
        for r in range(n):
            if r != col and M[r][col]:
                factor = M[r][col]
                for j in range(col, n + 1):
                    M[r][j] -= factor * M[col][j]
    return [M[i][n] for i in range(n)]


def find_coeffs(dest, src):
    """Perspective coeffs mapping OUTPUT (dest) coords back to INPUT (src)."""
    A, b = [], []
    for (x, y), (u, v) in zip(dest, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); b.append(v)
    return solve(A, b)


def mockup(src_path, out_path):
    cover = Image.open(src_path).convert("RGBA")
    w, h = cover.size

    Hf = 1180                       # front-face height at the near (left) edge
    scale = Hf / h
    Wt = w * scale                  # true cover width at that scale
    Wf = Wt * 0.90                  # projected width once turned a little
    rf = 0.965                      # far (right) edge foreshortening
    D = int(Hf * 0.03)              # page thickness

    ml, mt = 96, 96
    X, Y = ml, mt
    inset = Hf * (1 - rf) / 2

    TL = (X, Y)
    TR = (X + Wf, Y + inset)
    BR = (X + Wf, Y + Hf - inset)
    BL = (X, Y + Hf)

    off_y = D * 0.42
    PT = (X + Wf + D, Y + inset - off_y)
    PB = (X + Wf + D, Y + Hf - inset - off_y)

    CW = int(X + Wf + D + ml)
    CH = int(Y + Hf + mt + 40)
    canvas = Image.new("RGBA", (CW, CH), (255, 255, 255, 255))

    # soft drop shadow
    shadow = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx, sy = 26, 34
    sd.polygon([(TL[0] + sx, TL[1] + sy), (PT[0] + sx, PT[1] + sy),
                (PB[0] + sx, PB[1] + sy), (BL[0] + sx, BL[1] + sy)],
               fill=(30, 32, 40, 115))
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    canvas.alpha_composite(shadow)

    # page slab (fore-edge): warm off-white with thin page striations
    slab_w = max(2, int(D * 1.4))
    slab = Image.new("RGBA", (slab_w, int(Hf)), (238, 233, 222, 255))
    sdraw = ImageDraw.Draw(slab)
    for i in range(0, int(Hf), 3):
        shade = 205 if (i // 3) % 2 == 0 else 226
        sdraw.line([(0, i), (slab_w, i)], fill=(shade, shade - 6, shade - 16, 255))
    slab_dest = [TR, PT, PB, BR]
    slab_src = [(0, 0), (slab_w, 0), (slab_w, Hf), (0, Hf)]
    slab_warp = slab.transform((CW, CH), Image.PERSPECTIVE,
                               find_coeffs(slab_dest, slab_src), Image.BICUBIC)
    canvas.alpha_composite(slab_warp)

    # front face
    face_dest = [TL, TR, BR, BL]
    face_src = [(0, 0), (w, 0), (w, h), (0, h)]
    face = cover.transform((CW, CH), Image.PERSPECTIVE,
                           find_coeffs(face_dest, face_src), Image.BICUBIC)
    canvas.alpha_composite(face)

    # spine shading: subtle dark gradient down the near edge
    spine = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    spd = ImageDraw.Draw(spine)
    sw = int(Wf * 0.06)
    for i in range(sw):
        a = int(60 * (1 - i / sw))
        spd.line([(X + i, Y), (X + i, Y + Hf)], fill=(20, 22, 30, a))
    spine = spine.filter(ImageFilter.GaussianBlur(1))
    canvas.alpha_composite(spine)

    canvas.convert("RGB").save(out_path, "JPEG", quality=88)
    print(f"  {out_path.name}  ({CW}x{CH})")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("*")):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        name = f.stem.replace("-flat", "")
        mockup(f, OUT / f"{name}.jpg")


if __name__ == "__main__":
    main()
