"""Render Spectrum-accurate previews of the photofit feature set.

    python3 tools/photofit/preview.py [out_dir]

Writes one sheet per feature category (each variant on a reference face, in
the interrogation colour scheme) plus a gallery of random subjects at both
sizes, picked exactly as the game picks them.
"""
import os
import random
import sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(__file__))
import features as F
import pfselect

BLACK, BLUE, RED, MAG, GREEN, CYAN, YELLOW, WHITE = range(8)
PAL = [(0, 0, 0), (0, 0, 205), (205, 0, 0), (205, 0, 205), (0, 205, 0), (0, 205, 205), (205, 205, 0), (205, 205, 205)]
BPAL = [(0, 0, 0), (0, 0, 255), (255, 0, 0), (255, 0, 255), (0, 255, 0), (0, 255, 255), (255, 255, 0), (255, 255, 255)]

SKINS = [(WHITE, True), (YELLOW, True), (CYAN, True), (WHITE, False)]
HAIRCOLS = [BLUE, RED, MAG, GREEN]

EYE_CELLS = {(2, 5), (3, 5), (4, 5), (5, 5)}
MOUTH_CELLS = {(3, 8), (4, 8)}


def hair_cells(sel):
    return F.hair_cells("hair", sel["hair"]) | F.hair_cells("facial", sel["facial"])


def mouth_hidden(sel):
    return sel["facial"] in F.MOUTH_HIDING_FACIAL


def render_small(sel, skin=0, hair=0, mood="calm"):
    """Interrogation portrait, 64x96, with the hybrid attribute scheme."""
    ink, sil = F.compose(sel, 1.0)
    hc = hair_cells(sel)
    skin_col, bright = SKINS[skin]
    hair_col = HAIRCOLS[hair]
    im = Image.new("RGB", (64, 96))
    px = im.load()
    for r in range(12):
        for c in range(8):
            cells = [(c * 8 + x, r * 8 + y) for y in range(8) for x in range(8)]
            n = sum(sil.get(x, y) for x, y in cells)
            colour = hair_col if (c, r) in hc else skin_col
            pal = BPAL if bright or (c, r) in hc else PAL
            if n == 0:
                for x, y in cells:
                    px[x, y] = (0, 0, 0)
            elif n == 64:
                inkc = BLACK
                if (c, r) in EYE_CELLS:
                    inkc = {"calm": BLACK, "stressed": RED, "blink": colour}[mood]
                if (c, r) in MOUTH_CELLS and not mouth_hidden(sel):
                    inkc = RED
                for x, y in cells:
                    px[x, y] = pal[inkc] if ink.get(x, y) else pal[colour]
            else:
                for x, y in cells:
                    px[x, y] = pal[colour] if sil.get(x, y) and not ink.get(x, y) else (0, 0, 0)
    return im


def render_large(sel, skin=0):
    """Dossier face, 96x144, monochrome black lines on the subject's skin colour."""
    ink, _ = F.compose(sel, 1.5)
    skin_col, bright = SKINS[skin]
    paper = (BPAL if bright else PAL)[skin_col]
    im = Image.new("RGB", (ink.w, ink.h), paper)
    px = im.load()
    for y in range(ink.h):
        for x in range(ink.w):
            if ink.get(x, y):
                px[x, y] = (0, 0, 0)
    return im


REF = dict(head=0, collar=0, marks=0, eyes=0, brows=0, nose=0, mouth=0, facial=0, hair=2)


def label(im, text, scale):
    out = Image.new("RGB", (im.width * scale, im.height * scale + 14), (30, 30, 30))
    out.paste(im.resize((im.width * scale, im.height * scale), Image.NEAREST), (0, 0))
    ImageDraw.Draw(out).text((2, im.height * scale + 1), text, fill=(230, 230, 230))
    return out


def sheet(tiles, cols, path):
    w, h = tiles[0].width, tiles[0].height
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new("RGB", (cols * (w + 8) + 8, rows * (h + 8) + 8), (60, 60, 60))
    for i, t in enumerate(tiles):
        s.paste(t, (8 + (i % cols) * (w + 8), 8 + (i // cols) * (h + 8)))
    s.save(path)


def main(out):
    os.makedirs(out, exist_ok=True)
    cats = [("head", F.HEADS), ("hair", F.HAIRS), ("eyes", F.EYES), ("brows", F.BROWS), ("nose", F.NOSES),
            ("mouth", F.MOUTHS), ("facial", F.FACIAL), ("marks", F.MARKS), ("collar", F.COLLARS)]
    for cat, items in cats:
        tiles = []
        for i, it in enumerate(items):
            sel = dict(REF)
            sel[cat] = i
            name = it["name"] if isinstance(it, dict) else it[0]
            tiles.append(label(render_small(sel, skin=2, hair=0), f"{i} {name}", 3))
        sheet(tiles, 6, os.path.join(out, f"sheet_{cat}.png"))

    # Gallery: real subjects through the game's own selection
    rnd = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    names = pfselect.subject_names()
    small, large = [], []
    for k in range(18):
        idx = rnd.randrange(len(names))
        sel, skin, hair = pfselect.select(idx, rnd.randrange(65536))
        small.append(label(render_small(sel, skin, hair), names[idx], 3))
        large.append(label(render_large(sel, skin), names[idx], 2))
    sel, skin, hair = pfselect.select(None, 0)
    small.append(label(render_small(sel, skin, hair), "DECKARD (mirror)", 3))
    large.append(label(render_large(sel, skin), "DECKARD (mirror)", 2))
    sheet(small, 7, os.path.join(out, "gallery_small.png"))
    sheet(large, 7, os.path.join(out, "gallery_large.png"))
    moods = [label(render_small(REF, 2, 0, m), m, 4) for m in ("calm", "stressed", "blink")]
    sheet(moods, 3, os.path.join(out, "moods.png"))
    print("written to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "photofit-previews")
