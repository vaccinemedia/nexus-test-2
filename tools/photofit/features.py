"""Photofit feature art for Nexus.

Every feature is described once as curves in the small-face coordinate space
(64 x 96, pixel-centre coordinates, face centred on x = 31.5) and rasterised at
two scales:

    SMALL  scale 1.0  ->  64 x 96   interrogation portrait (8 x 12 cells)
    LARGE  scale 1.5  ->  96 x 144  dossier intro face   (12 x 18 cells)

so the dossier and the interrogation always show the same person.

Each rendered feature is a pair of 1-bit layers:
    mask  cleared out of the line art before this feature's ink goes down,
          and added to the face silhouette
    ink   the feature's lines

Composition (identical on the Spectrum):  ink = (ink & ~mask) | feature_ink
                                          sil = sil | mask

Small-face cell rules (from the mock-ups):
    rows 0-3  hair / forehead          row 4   brows only
    row 5     eyes only, each eye fills two cells (cols 2-3 and 4-5)
    rows 6-7  nose                     row 8   mouth, x 24..39 (cols 3-4, red)
    rows 9-11 chin, neck, collar
"""
import math
from PIL import Image, ImageDraw

SMALL_W, SMALL_H = 64, 96
CX = 31.5


# ----------------------------------------------------------------- raster core
class Layer:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.p = bytearray(w * h)

    def set(self, x, y, v=1):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.p[y * self.w + x] = v

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.p[y * self.w + x]
        return 0

    def copy(self):
        n = Layer(self.w, self.h)
        n.p[:] = self.p
        return n

    def any(self):
        return any(self.p)


def catmull(pts, n=48):
    """Catmull-Rom spline through pts (ends clamped)."""
    if len(pts) < 3:
        return lerp_path(pts, n)
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def lerp_path(pts, n=48):
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        for k in range(n):
            t = k / n
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    out.append(pts[-1])
    return out


def mirror_pts(pts):
    return [(2 * CX - x, y) for x, y in pts]


def sym(left):
    """Closed outline from a left half running top -> bottom along x <= CX."""
    return list(left) + list(reversed(mirror_pts(left)))


def ellipse_pts(cx, cy, rx, ry, a0=0, a1=360, n=None):
    n = n or max(8, int((rx + ry) * 2))
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]


class Canvas:
    """Draws one feature at one scale."""

    def __init__(self, scale):
        self.s = scale
        self.W = round(SMALL_W * scale)
        self.H = round(SMALL_H * scale)
        self.ink = Layer(self.W, self.H)
        self.mask = Layer(self.W, self.H)

    # coordinate mapping (pixel-centre small coords -> output pixel)
    def px(self, x, y):
        return math.floor((x + 0.5) * self.s), math.floor((y + 0.5) * self.s)

    def _plot_path(self, layer, path, mirror, dy=0, clip=None):
        pix = []
        for x, y in path:
            p = self.px(x, y)
            p = (p[0], p[1] + dy)
            if pix and p == pix[-1]:
                continue
            if pix:
                lx, ly = pix[-1]
                # bridge gaps so the line stays 8-connected
                while max(abs(p[0] - lx), abs(p[1] - ly)) > 1:
                    lx += (p[0] > lx) - (p[0] < lx)
                    ly += (p[1] > ly) - (p[1] < ly)
                    pix.append((lx, ly))
                if (lx, ly) == p:
                    continue
            pix.append(p)
        # pixel-perfect: drop the corner pixel of every L-shaped step
        clean = []
        for p in pix:
            if len(clean) >= 2:
                a, b = clean[-2], clean[-1]
                if abs(p[0] - a[0]) == 1 and abs(p[1] - a[1]) == 1 and \
                        (abs(b[0] - a[0]) + abs(b[1] - a[1]) == 1):
                    clean.pop()
            clean.append(p)
        for x, y in clean:
            if clip and not clip(x, y):
                continue
            layer.set(x, y)
            if mirror:
                layer.set(self.W - 1 - x, y)

    def line(self, pts, mirror=False, smooth=True, thick=1, layer=None, clip=None):
        path = catmull(pts) if smooth else lerp_path(pts)
        n = max(1, round(thick * self.s)) if thick > 1 else 1
        for dy in range(n):
            self._plot_path(layer or self.ink, path, mirror, dy, clip)

    def fill(self, outline, mirror=False, layer=None, smooth=True):
        path = catmull(outline) if smooth else outline
        im = Image.new("1", (self.W, self.H), 0)
        d = ImageDraw.Draw(im)
        d.polygon([((x + 0.5) * self.s, (y + 0.5) * self.s) for x, y in path], fill=1, outline=1)
        tgt = layer or self.mask
        px = im.load()
        for y in range(self.H):
            for x in range(self.W):
                if px[x, y]:
                    tgt.set(x, y)
                    if mirror:
                        tgt.set(self.W - 1 - x, y)

    def blob(self, x, y, r, mirror=False, layer=None):
        cx, cy = (x + 0.5) * self.s, (y + 0.5) * self.s
        rr = r * self.s
        tgt = layer or self.ink
        for py in range(math.floor(cy - rr) - 1, math.ceil(cy + rr) + 2):
            for pxx in range(math.floor(cx - rr) - 1, math.ceil(cx + rr) + 2):
                if (pxx + 0.5 - cx) ** 2 + (py + 0.5 - cy) ** 2 <= rr * rr:
                    tgt.set(pxx, py)
                    if mirror:
                        tgt.set(self.W - 1 - pxx, py)

    def dot(self, x, y, mirror=False, layer=None):
        p = self.px(x, y)
        tgt = layer or self.ink
        tgt.set(*p)
        if mirror:
            tgt.set(self.W - 1 - p[0], p[1])

    def stipple(self, region, step, seed, keep=None, jitter=True):
        """Scatter dots over the mask region (small-unit spacing)."""
        rnd = _Rand(seed)
        y = 0.0
        row = 0
        while y < SMALL_H:
            x = (step / 2) * (row & 1)
            while x < SMALL_W:
                jx = (rnd.f() - 0.5) * step * 0.8 if jitter else 0
                jy = (rnd.f() - 0.5) * step * 0.8 if jitter else 0
                p = self.px(x + jx, y + jy)
                if region.get(*p) and (keep is None or keep(x + jx, y + jy)):
                    self.ink.set(*p)
                x += step
            y += step * 0.866
            row += 1


class _Rand:
    def __init__(self, seed):
        self.v = seed * 2654435761 % (2 ** 32) or 1

    def f(self):
        self.v ^= (self.v << 13) & 0xFFFFFFFF
        self.v ^= self.v >> 17
        self.v ^= (self.v << 5) & 0xFFFFFFFF
        return (self.v & 0xFFFF) / 65536


# ------------------------------------------------------------------ head shapes
# Half-widths at skull (y20), temple (y34), cheekbone (y48), jaw (y66),
# jaw angle (y78), chin, and chin bottom y; ear size; neck half-width.
HEADS = [
    dict(name="oval",    ws=19.5, wt=21.0, wc=22.0, wj=18.5, wa=13.5, wch=6.0, chin=88, ear=5.5, neck=9.5),
    dict(name="square",  ws=20.5, wt=22.0, wc=22.5, wj=21.0, wa=18.0, wch=9.5, chin=88, ear=5.5, neck=11),
    dict(name="long",    ws=18.0, wt=19.0, wc=20.0, wj=16.5, wa=12.0, wch=5.0, chin=90, ear=5.0, neck=8.5),
    dict(name="round",   ws=21.5, wt=23.0, wc=23.5, wj=21.0, wa=16.0, wch=7.5, chin=86, ear=6.0, neck=10.5),
    dict(name="heart",   ws=21.0, wt=22.0, wc=21.5, wj=16.0, wa=11.0, wch=4.0, chin=89, ear=5.0, neck=8.5),
    dict(name="heavy",   ws=20.5, wt=22.0, wc=23.5, wj=22.5, wa=19.5, wch=11.0, chin=88, ear=6.5, neck=12),
]
CROWN = 5.0


def head_left(h):
    return [(CX, CROWN), (CX - h["ws"] * 0.62, CROWN + 2.2), (CX - h["ws"], 20),
            (CX - h["wt"], 34), (CX - h["wc"], 48), (CX - h["wj"], 66),
            (CX - h["wa"], 78), (CX - h["wch"], h["chin"] - 1.5), (CX, h["chin"])]


def span_fill(ink, mask):
    """Fill each row between its leftmost and rightmost ink pixel.

    The head's silhouette is not stored: the Spectrum rebuilds it this way
    from the head outline, so the art tools must use the same rule.
    """
    for y in range(ink.h):
        xs = [x for x in range(ink.w) if ink.get(x, y)]
        if xs:
            for x in range(xs[0], xs[-1] + 1):
                mask.set(x, y)


def draw_head(c, h):
    left = head_left(h)
    neck_y = 74
    nw = h["neck"]
    # ears: outer C bulging out from the side of the head
    ex = CX - h["wc"] + 0.6
    e = h["ear"]
    ear = [(ex + 0.5, 42), (ex - e * 0.55, 41), (ex - e, 44.5), (ex - e * 0.95, 50),
           (ex - e * 0.6, 55.5), (ex - e * 0.2, 59.5), (ex + 0.8, 60.5)]
    # lines
    head_ink = Layer(c.W, c.H)
    c.line(left, mirror=True, layer=head_ink)
    for i, v in enumerate(head_ink.p):
        if v:
            c.ink.p[i] = 1
    c.line(ear, mirror=True)
    c.line([(ex - e * 0.6, 46), (ex - e * 0.35, 45), (ex - e * 0.4, 49), (ex - e * 0.2, 54)], mirror=True)
    # neck sides, only where they fall outside the head
    inside = Layer(c.W, c.H)
    c.fill(sym(left), layer=inside)
    c.line([(CX - nw, neck_y), (CX - nw - 0.5, 95.5)], mirror=True, smooth=False,
           clip=lambda x, y: not inside.get(x, y - 1))
    # remove ear lines that cross into the face
    for y in range(c.H):
        for x in range(c.W):
            if inside.get(x, y) and not head_ink.get(x, y) and c.ink.get(x, y):
                c.ink.set(x, y, 0)
    span_fill(c.ink, c.mask)


# ---------------------------------------------------------------------- eyes
# Left eye spans x 17..27, centred y 43.5 (cell row 5). Right eye is mirrored.
def _eye(c, upper, lower, iris_r=1.6, iris=(22.5, 43.6), thick_upper=1):
    c.line(upper, mirror=True, thick=thick_upper)
    c.line(lower, mirror=True)
    if iris_r:
        # clip iris between the lids
        tmp = Canvas(c.s)
        tmp.blob(*iris, iris_r, mirror=True)
        lid = Canvas(c.s)
        lid.fill(upper + list(reversed(lower)), mirror=True, layer=lid.ink)
        for i, v in enumerate(tmp.ink.p):
            if v and lid.ink.p[i]:
                c.ink.p[i] = 1


def eye_almond(c):
    _eye(c, [(17, 44), (19, 42.2), (22, 41.4), (25, 41.9), (27.5, 44)],
         [(17, 44), (20, 45.6), (23.5, 45.8), (27.5, 44)])


def eye_round(c):
    _eye(c, [(17, 44), (18.8, 41.6), (22, 40.6), (25.2, 41.5), (27.3, 44)],
         [(17, 44), (19.3, 46.4), (22.3, 46.9), (25.5, 46.2), (27.3, 44)], iris_r=2.0, iris=(22.3, 43.8))


def eye_narrow(c):
    _eye(c, [(16.5, 44), (19.5, 42.9), (23, 42.6), (27.5, 43.7)],
         [(16.5, 44), (20.5, 45.0), (24, 45.0), (27.5, 43.7)], iris_r=1.3, iris=(22.5, 43.9))


def eye_hooded(c):
    c.line([(16.5, 42.3), (19.5, 40.6), (23, 40.4), (27, 41.8)], mirror=True)
    _eye(c, [(17, 44.3), (19.5, 42.8), (23, 42.4), (27.5, 44)],
         [(17, 44.3), (20.5, 45.7), (24, 45.7), (27.5, 44)], iris_r=1.5, iris=(22.7, 44.2), thick_upper=2)


def eye_lashes(c):
    eye_almond(c)
    for (x0, y0), (x1, y1) in [((17.3, 43.6), (15.6, 42.4)), ((18.6, 42.6), (17.3, 41.0)), ((20.2, 41.9), (19.6, 40.2))]:
        c.line([(x0, y0), (x1, y1)], mirror=True, smooth=False)


def eye_down(c):
    _eye(c, [(16.5, 45.2), (18.8, 42.6), (22, 41.7), (25.2, 42.0), (27.5, 43.6)],
         [(16.5, 45.2), (20.5, 46.2), (24.5, 45.6), (27.5, 43.6)], iris=(22.4, 43.9))


def eye_cat(c):
    _eye(c, [(16.5, 42.4), (19, 41.6), (23, 41.8), (27.5, 44.2)],
         [(16.5, 42.4), (19.5, 44.6), (23.5, 45.9), (27.5, 44.2)], iris=(22.4, 43.6))


def eye_tired(c):
    eye_almond(c)
    c.line([(18.5, 47.2), (22, 47.8), (25.5, 47.2)], mirror=True)


EYES = [("almond", eye_almond), ("round", eye_round), ("narrow", eye_narrow), ("hooded", eye_hooded),
        ("lashes", eye_lashes), ("downturned", eye_down), ("cat", eye_cat), ("tired", eye_tired)]


# --------------------------------------------------------------------- brows
# Cell row 4: y 32..39. Left brow spans x 15..28.
def brow_straight(c): c.line([(16, 37), (22, 36.4), (28, 36.6)], mirror=True, thick=2)
def brow_arched(c): c.line([(15, 38), (18, 35.6), (22, 34.6), (26, 35.0), (28.5, 36.6)], mirror=True)
def brow_stern(c): c.line([(15, 35.2), (21, 35.4), (28.5, 37.6)], mirror=True, thick=2)
def brow_worried(c): c.line([(15, 37.6), (21, 36.6), (28.5, 34.6)], mirror=True, thick=2)
def brow_thin(c): c.line([(16, 36.6), (22, 36.2), (27.5, 36.6)], mirror=True)
def brow_high(c): c.line([(15, 37.4), (18.5, 34.0), (23, 33.2), (28, 35.4)], mirror=True)


def brow_bushy(c):
    c.line([(15.5, 37.6), (22, 36.8), (28.5, 37.2)], mirror=True, thick=2)
    for x in range(16, 29, 2):
        c.line([(x, 36.0), (x + 1.3, 34.6)], mirror=True, smooth=False)


def brow_unibrow(c):
    c.line([(15.5, 37.2), (22, 36.2), (28.5, 36.6), (31.5, 37.0)], mirror=True, thick=2)


BROWS = [("straight", brow_straight), ("arched", brow_arched), ("stern", brow_stern), ("worried", brow_worried),
         ("thin", brow_thin), ("high arch", brow_high), ("bushy", brow_bushy), ("unibrow", brow_unibrow)]


# ---------------------------------------------------------------------- noses
# Cell rows 6-7: y 48..63.
def _nostrils(c, y=60.2, dx=2.3):
    c.dot(CX - dx, y)
    c.dot(CX + dx, y)


def nose_straight(c):
    c.line([(29.2, 49), (28.6, 54), (28.4, 58)])
    c.line([(27, 59.2), (28.4, 61), (31.5, 61.7), (34.6, 61), (36, 59.2)])
    _nostrils(c)


def nose_wide(c):
    c.line([(29.5, 50), (28.6, 54), (28.0, 57)])
    c.line([(25, 58.2), (25.8, 60.8), (28.5, 61.4), (31.5, 62.2), (34.5, 61.4), (37.2, 60.8), (38, 58.2)])
    _nostrils(c, 60.0, 3.2)


def nose_hooked(c):
    c.line([(29.4, 48.5), (28.0, 52.5), (27.4, 56.5), (28.6, 60.6)])
    c.line([(28.6, 60.6), (31.5, 62.0), (34.5, 61.0), (35.8, 59.3)])
    _nostrils(c, 60.4, 2.0)


def nose_button(c):
    c.line([(29.5, 55.5), (29.2, 57.5)])
    c.line([(28.2, 59.4), (29.6, 60.8), (31.5, 61.2), (33.4, 60.8), (34.8, 59.4)])
    _nostrils(c, 59.8, 2.0)


def nose_long(c):
    c.line([(30.0, 48), (29.6, 54), (29.2, 60.5)])
    c.line([(28.2, 61.4), (31.5, 62.8), (34.8, 61.4)])
    _nostrils(c, 61.5, 2.6)


def nose_broad(c):
    c.line([(27.2, 56.5), (25.6, 58.6), (26.4, 60.8), (28.8, 61.0)], mirror=True)
    c.line([(29.6, 62), (33.4, 62)], smooth=False)
    c.line([(29.4, 50), (29.0, 55)])


def nose_pointed(c):
    c.line([(29.4, 49), (29.6, 54), (30.4, 60.0)])
    c.line([(30.4, 60.0), (32.6, 62.0), (34.4, 60.0)])
    c.dot(28.5, 60.6)


def nose_crooked(c):
    c.line([(29.0, 49), (30.6, 52.6), (29.6, 56), (29.0, 59)])
    c.line([(27.5, 59.6), (29.2, 61.2), (31.8, 61.8), (34.6, 61.0), (35.8, 59.4)])
    _nostrils(c)


NOSES = [("straight", nose_straight), ("wide", nose_wide), ("hooked", nose_hooked), ("button", nose_button),
         ("long", nose_long), ("broad", nose_broad), ("pointed", nose_pointed), ("crooked", nose_crooked)]


# --------------------------------------------------------------------- mouths
# Cell row 8: y 64..71, x 24..39 (cols 3-4, drawn in red).
def mouth_neutral(c):
    c.line([(25, 67.8), (28, 68.2), (31.5, 68.4), (35, 68.2), (38, 67.8)])
    c.line([(29.5, 70.6), (33.5, 70.6)], smooth=False)


def mouth_smile(c):
    c.line([(24.2, 66.4), (27.5, 68.4), (31.5, 69.0), (35.5, 68.4), (38.8, 66.4)])
    c.line([(29.5, 70.8), (31.5, 71.0), (33.5, 70.8)])


def mouth_frown(c):
    c.line([(24.4, 69.6), (28, 67.8), (31.5, 67.4), (35, 67.8), (38.6, 69.6)])
    c.line([(30, 70.4), (33, 70.4)], smooth=False)


def mouth_full(c):
    c.line([(24.5, 68), (27, 66.2), (29.8, 65.4), (31.5, 66.2), (33.2, 65.4), (36, 66.2), (38.5, 68)])
    c.line([(24.5, 68), (28, 68.6), (31.5, 68.8), (35, 68.6), (38.5, 68)])
    c.line([(25.5, 68.8), (28.5, 70.6), (31.5, 71.1), (34.5, 70.6), (37.5, 68.8)])


def mouth_thin(c):
    c.line([(24.2, 68), (39, 68)], smooth=False)
    c.line([(30, 70), (33, 70)], smooth=False)


def mouth_smirk(c):
    c.line([(25, 68.6), (28.5, 68.6), (32, 68.3), (35.5, 67.5), (38.8, 66.2)])
    c.line([(29.5, 70.6), (33, 70.4)], smooth=False)


def mouth_open(c):
    c.line([(25, 67.4), (28, 66.7), (31.5, 66.6), (35, 66.7), (38, 67.4)])
    c.line([(25.4, 67.8), (28.5, 69.4), (31.5, 69.9), (34.5, 69.4), (37.6, 67.8)])


def mouth_pursed(c):
    c.line([(27.8, 68.0), (29.8, 67.4), (31.5, 67.7), (33.2, 67.4), (35.2, 68.0)])
    c.line([(29.2, 70.2), (31.5, 70.7), (33.8, 70.2)])


MOUTHS = [("neutral", mouth_neutral), ("smile", mouth_smile), ("frown", mouth_frown), ("full lips", mouth_full),
          ("thin", mouth_thin), ("smirk", mouth_smirk), ("parted", mouth_open), ("pursed", mouth_pursed)]


# ---------------------------------------------------------------------- hair
# Hair masks clear the skull outline beneath them and join the silhouette.
def _hair_region(c, outer, inner_left, mirror_inner=True):
    """Fill between an outer outline (closed) and an inner hairline."""
    c.fill(outer)
    face = Layer(c.W, c.H)
    inner = sym(inner_left) if mirror_inner else inner_left
    c.fill(inner, layer=face)
    for i, v in enumerate(face.p):
        if v:
            c.mask.p[i] = 0
    return face


def _outline_mask(c):
    """Draw the mask's boundary as ink."""
    m = c.mask
    for y in range(c.H):
        for x in range(c.W):
            if m.get(x, y) and (not m.get(x - 1, y) or not m.get(x + 1, y) or not m.get(x, y - 1) or not m.get(x, y + 1)):
                c.ink.set(x, y)


def _strands(c, paths, region=None):
    for p in paths:
        c.line(p, clip=(lambda x, y: region.get(x, y)) if region else None)


def hair_bald(c):
    c.line([(23.5, 10.5), (26.5, 8.6), (29.5, 8.0)])


def hair_crew(c):
    outer = sym([(CX, 3.2), (17, 6.5), (10.6, 16), (9.3, 28), (9.4, 42), (12, 42)])
    _hair_region(c, outer, [(CX, 14), (24, 14.3), (16.5, 16.5), (12.5, 22), (11.6, 30), (12, 43)])
    _outline_mask(c)
    c.stipple(c.mask, 2.6, 7)


def hair_parted(c):
    outer = [(9.4, 42), (8.8, 28), (9.6, 16), (14, 7), (21, 2.6), (32, 1.4), (43, 3.0), (51, 8.5), (54, 17), (54.4, 30), (54, 42),
             (51.5, 42), (51.2, 30), (49, 19), (40, 15.5), (31, 15.8), (22, 15.0), (16, 18), (12.5, 25), (11.8, 42)]
    c.fill(outer, smooth=False)
    _outline_mask(c)
    region = c.mask
    c.line([(21.5, 5.0), (21.0, 9), (20.5, 13)], clip=lambda x, y: region.get(x, y))
    paths = []
    for k in range(5):
        y0 = 4.5 + k * 2.3
        paths.append([(22.5, y0), (32, y0 - 1.5 + k * 0.2), (42, y0 + 0.5), (49, y0 + 6 + k), (52, 22 + k * 3)])
    for k in range(3):
        paths.append([(19.5, 5 + k * 3), (14, 10 + k * 3.2), (11.2, 20 + k * 6)])
    _strands(c, paths, region)


def hair_slick(c):
    outer = sym([(CX, 2.2), (18, 4.6), (11.2, 12), (9.4, 24), (9.4, 40), (12, 40)])
    _hair_region(c, outer, [(CX, 11.8), (25, 12.4), (18.5, 15), (13.5, 20), (11.8, 28), (12.2, 40)])
    _outline_mask(c)
    region = c.mask
    paths = []
    for x in (19, 23.5, 27.5, 31.5):
        paths.append([(x, 13.5 if x > 20 else 15.5), (x - 0.5, 8), (x * 0.82 + 3, 3.5)])
    paths += [[(x2[0], y), (x2[1], y - 8)] for x2, y in [((14.5, 15.5), 24), ((12.5, 13.6), 33)]]
    paths = paths + [mirror_pts(p) for p in paths]
    _strands(c, paths, region)


def hair_receding(c):
    c.fill([(14.5, 13), (10.4, 19), (9.3, 30), (9.4, 42), (12, 42), (12.2, 30), (14.2, 21), (18, 16.5)], mirror=True)
    _outline_mask(c)
    c.stipple(c.mask, 2.4, 11)
    c.line([(26, 10.5), (29.5, 9.4)])


def hair_quiff(c):
    outer = sym([(CX, 0.4), (21, 1.2), (14.5, 5), (11, 13), (9.6, 24), (9.6, 40), (12, 40)])
    _hair_region(c, outer, [(CX, 15), (25, 15.6), (18.5, 17.4), (13.8, 22), (12, 30), (12.2, 40)])
    _outline_mask(c)
    region = c.mask
    paths = []
    for k, x in enumerate((17, 21.5, 26, 30.5, 35, 39.5, 44)):
        paths.append([(x + 1.5, 15.2), (x - 1.5, 9), (x + 2.5, 2.2)])
    _strands(c, paths, region)


def hair_bob(c):
    outer = sym([(CX, 1.4), (19, 3.2), (11, 10), (7.4, 22), (6.0, 40), (5.6, 58), (6.2, 70), (9.5, 73), (13.5, 71)])
    face = [(CX, 30.6), (20, 30.6), (14.6, 31), (12.0, 36), (11.4, 50), (12.5, 64), (13.8, 71)]
    _hair_region(c, outer, face)
    _outline_mask(c)
    region = c.mask
    paths = [[(x, 30.2), (x - 0.2, 20), (x * 0.9 + 3.3, 4)] for x in (16, 20, 24, 28)]
    paths += [[(x, 9 + (14 - x)), (x - 0.8, 40), (x - 0.4, 69)] for x in (8.5, 11)]
    paths = paths + [mirror_pts(p) for p in paths]
    _strands(c, paths, region)


def hair_long(c):
    outer = sym([(CX, 1.0), (19.5, 2.8), (11.5, 9), (7.6, 20), (5.0, 40), (3.4, 66), (2.4, 95.5), (12, 95.5), (15.5, 82)])
    face = [(CX, 6.8), (27, 9.5), (19.5, 15), (14.2, 24), (12.4, 36), (11.8, 52), (13.4, 70), (17, 84)]
    _hair_region(c, outer, face)
    _outline_mask(c)
    region = c.mask
    paths = [[(29.5, 4), (24, 9), (16, 18), (12, 30)]]
    paths += [[(x, 20 + (12 - x) * 2), (x - 1.2, 50), (x - 1.8, 94)] for x in (6.5, 9.5)]
    paths += [[(13.5, 78), (14.5, 94)]]
    paths = paths + [mirror_pts(p) for p in paths]
    _strands(c, paths, region)


def hair_bun(c):
    outer = sym([(CX, 4.2), (18, 6), (11.2, 13), (9.4, 24), (9.6, 40), (12, 40)])
    _hair_region(c, outer, [(CX, 13.2), (24.5, 13.8), (18, 16), (13.5, 21), (11.8, 29), (12.2, 40)])
    c.fill(ellipse_pts(CX, 4.6, 6.6, 4.4))
    _outline_mask(c)
    region = c.mask
    paths = [[(x, 13.4 + (31.5 - x) * 0.12), (x * 0.9 + 3, 6.5)] for x in (18, 22, 26)]
    paths = paths + [mirror_pts(p) for p in paths]
    paths += [ellipse_pts(CX, 4.6, 3.6, 2.0, 200, 340)]
    _strands(c, paths, region)


def hair_curly(c):
    pts = []
    for k in range(25):
        a = math.radians(180 + 180 * k / 24)
        r = 29.4 + (1.6 if k % 2 else 0)
        pts.append((CX + r * math.cos(a) * 1.02, 31 + r * math.sin(a) * 1.0))
    left_down = [(CX - 30.2, 34), (CX - 29.4, 41), (CX - 27.6, 46), (CX - 22, 46)]
    outer = list(reversed(left_down)) + pts + [(2 * CX - x, y) for x, y in left_down]
    outer = [(min(max(x, 1.6), 61.4), max(y, 0.5)) for x, y in outer]
    _hair_region(c, outer, [(CX, 16.4), (24, 17), (17, 20), (13, 26), (11.8, 34), (12, 46)])
    _outline_mask(c)
    region = c.mask
    rnd = _Rand(5)
    placed = []
    for k in range(400):
        x, y = 3 + rnd.f() * 58, 2 + rnd.f() * 44
        if any((x - px) ** 2 + (y - py) ** 2 < 4.2 ** 2 for px, py in placed):
            continue
        cs = ellipse_pts(x, y, 1.4, 1.2, 40, 250, 10)
        probe = [c.px(xx, yy) for xx, yy in ellipse_pts(x, y, 2.6, 2.6, 0, 360, 12)]
        if not all(region.get(*p) for p in probe):
            continue
        placed.append((x, y))
        c.line(cs, smooth=False)


def hair_mohawk(c):
    strip = [(25.5, 15), (25.5, 6), (26.5, 0.6), (28.5, 4.0), (30.5, 0.4), (32.5, 4.0), (34.5, 0.4), (36.5, 4.0), (37.5, 0.6),
             (37.5, 6), (37.5, 15)]
    c.fill(strip, smooth=False)
    _outline_mask(c)
    region = c.mask.copy()
    c.line([(28.5, 13), (28.5, 5)], smooth=False, clip=lambda x, y: region.get(x, y))
    c.line([(34.5, 13), (34.5, 5)], smooth=False, clip=lambda x, y: region.get(x, y))
    shaved = Canvas(c.s)
    shaved.fill([(13, 16), (10.4, 22), (9.8, 34), (11.6, 40), (12.4, 30), (14.6, 21), (17.5, 18)], mirror=True, layer=shaved.mask)
    c.stipple(shaved.mask, 3.0, 3)


def hair_pixie(c):
    outer = [(9.4, 42), (8.8, 26), (10.4, 14), (16, 5.8), (25, 2.2), (36, 2.0), (46, 5.0), (52.4, 13), (54.6, 26), (54.2, 42), (51.8, 42),
             (51.2, 28), (48, 19.5), (40, 20.5), (30, 23), (20, 26.5), (14.8, 28.5), (12.2, 34), (11.8, 42)]
    c.fill(outer, smooth=False)
    _outline_mask(c)
    region = c.mask
    paths = [[(16 + k * 5, 27.5 - k * 1.6), (20 + k * 5, 15 - k * 0.5), (26 + k * 5, 4)] for k in range(6)]
    paths += [[(11, 34), (12, 22)], [(53, 34), (52, 22)]]
    _strands(c, paths, region)


HAIRS = [("bald", hair_bald), ("crew cut", hair_crew), ("side parting", hair_parted), ("slicked back", hair_slick),
         ("receding", hair_receding), ("quiff", hair_quiff), ("bob", hair_bob), ("long", hair_long),
         ("bun", hair_bun), ("curly", hair_curly), ("mohawk", hair_mohawk), ("pixie", hair_pixie)]


# --------------------------------------------------------------- facial hair
def fh_none(c):
    pass


def _moustache(c, outline):
    c.fill(outline)
    _outline_mask(c)
    region = c.mask.copy()
    for x in range(24, 40, 2):
        c.line([(x, 62), (x + 0.4, 68)], smooth=False, clip=lambda xx, yy: region.get(xx, yy))


def fh_moustache(c):
    _moustache(c, sym([(CX, 62.4), (27, 62.6), (24.4, 64.4), (23.4, 67.6), (26, 66.6), (29, 65.8), (CX, 66.0)]))


def fh_beard(c):
    outer = sym([(CX - 1, 62.2), (25, 62.4), (21.5, 64), (16.0, 56), (13.4, 52), (11.0, 54), (11.4, 66), (14.8, 79), (21, 88), (CX, 92)])
    c.fill(outer)
    hole = Layer(c.W, c.H)
    c.fill(sym([(CX, 66.6), (27, 66.8), (24.6, 67.8), (25.6, 70.6), (28.5, 72.4), (CX, 72.8)]), layer=hole)
    for i, v in enumerate(hole.p):
        if v:
            c.mask.p[i] = 0
    _outline_mask(c)
    region = c.mask.copy()
    c.stipple(region, 2.2, 21)


def fh_goatee(c):
    _moustache(c, sym([(CX, 62.6), (27, 62.8), (24.8, 64.6), (24.4, 67.4), (26.5, 66.4), (29, 65.8), (CX, 66.0)]))
    c2 = Canvas(c.s)
    c2.fill(sym([(CX, 72.6), (27.5, 72.4), (26.2, 77), (27.5, 84), (CX, 88.4)]))
    for i, v in enumerate(c2.mask.p):
        if v:
            c.mask.p[i] = 1
    _outline_mask(c)
    c.stipple(c2.mask, 1.9, 4)


def fh_stubble(c):
    region = Canvas(c.s)
    region.fill(sym([(CX, 63.4), (24, 63.6), (17, 58), (12.8, 56), (13.2, 66), (16.0, 78), (22, 86), (CX, 88.8)]), layer=region.mask)
    hole = Canvas(c.s)
    # keep stubble out of the red mouth cells (x 24..39, y 64..71)
    hole.fill([(23.5, 63.5), (39.5, 63.5), (39.5, 71.5), (23.5, 71.5)], layer=hole.mask, smooth=False)
    for i, v in enumerate(hole.mask.p):
        if v:
            region.mask.p[i] = 0
    c.stipple(region.mask, 2.4, 9)


def fh_chops(c):
    c.fill([(13.2, 40), (11.4, 46), (11.6, 60), (14.4, 72), (19, 74.5), (20.5, 68), (17.4, 58), (15.4, 48), (14.2, 40)], mirror=True)
    _outline_mask(c)
    region = c.mask.copy()
    c.stipple(region, 2.0, 14)


def fh_handlebar(c):
    _moustache(c, sym([(CX, 62.2), (27, 62.4), (24, 64.0), (21.6, 64.6), (20.2, 62.6), (20.0, 64.8), (22.6, 66.8), (26, 66.0), (CX, 65.8)]))


FACIAL = [("clean shaven", fh_none), ("moustache", fh_moustache), ("full beard", fh_beard), ("goatee", fh_goatee),
          ("stubble", fh_stubble), ("mutton chops", fh_chops), ("handlebar", fh_handlebar)]


# ------------------------------------------------------------------- marks
def mk_none(c):
    pass


def mk_glasses_round(c):
    c.line(ellipse_pts(22.4, 43.6, 6.6, 5.4), mirror=True, smooth=False)
    c.line([(28.6, 41.6), (30.2, 40.8), (CX, 40.8)], mirror=True)
    c.line([(15.8, 42.4), (11.6, 41.4)], mirror=True, smooth=False)


def mk_glasses_square(c):
    c.line([(15.4, 39.8), (29.2, 39.8), (29.2, 46.6), (27.5, 48.0), (17.2, 48.0), (15.4, 46.6), (15.4, 39.8)], mirror=True, smooth=False)
    c.line([(29.2, 41.0), (CX, 40.4)], mirror=True, smooth=False)
    c.line([(15.4, 41.0), (11.6, 40.6)], mirror=True, smooth=False)


def mk_scar(c):
    c.line([(43.5, 50), (47, 56), (49.5, 62)], smooth=False)
    for t in (0.25, 0.55, 0.85):
        x, y = 43.5 + 6 * t, 50 + 12 * t
        c.line([(x - 1.5, y + 0.6), (x + 1.5, y - 0.6)], smooth=False)


def mk_wrinkles(c):
    c.line([(20, 23), (25, 22.2), (31.5, 22.0), (38, 22.2), (43, 23)])
    c.line([(22.5, 26.4), (31.5, 25.6), (40.5, 26.4)])
    c.line([(22.8, 56), (21.6, 60), (22.4, 63.4)], mirror=True)


def mk_freckles(c):
    for x, y in [(16, 50), (19, 51.5), (17.5, 53.5), (21, 54), (14.5, 52.5), (20, 49.5)]:
        c.dot(x, y, mirror=True)


def mk_mole(c):
    c.blob(40.5, 64.2, 0.9)


def mk_cheekbones(c):
    c.line([(12.4, 50), (16.5, 55), (20.5, 57.6)], mirror=True)


MARKS = [("none", mk_none), ("round glasses", mk_glasses_round), ("square glasses", mk_glasses_square), ("scar", mk_scar),
         ("wrinkles", mk_wrinkles), ("freckles", mk_freckles), ("mole", mk_mole), ("cheekbones", mk_cheekbones)]


# ------------------------------------------------------------------- collars
def col_coat(c):
    c.fill([(13, 95.5), (14.5, 88), (19.5, 82.5), (22.0, 86), (25.5, 95.5)], mirror=True, smooth=False)
    _outline_mask(c)


def col_shirt(c):
    c.fill([(10, 95.5), (12, 92), (21, 89.5), (25.5, 93), (27.5, 95.5)], mirror=True, smooth=False)
    _outline_mask(c)
    c.line([(CX, 92), (CX, 95)], smooth=False)


def col_turtleneck(c):
    c.fill([(20, 95.5), (20.6, 86.5), (CX, 87.6), (42.4, 86.5), (43, 95.5)], smooth=False)
    _outline_mask(c)
    c.line([(21.4, 90.5), (CX, 91.4), (41.6, 90.5)])


COLLARS = [("coat collar", col_coat), ("shirt", col_shirt), ("turtleneck", col_turtleneck)]

# Drawing order on the face. Marks go under the hair; glasses are drawn last.
CATEGORIES = [
    ("head", None), ("collar", COLLARS), ("marks", MARKS), ("eyes", EYES), ("brows", BROWS),
    ("nose", NOSES), ("mouth", MOUTHS), ("facial", FACIAL), ("hair", HAIRS),
]
GLASSES = {1, 2}


FACE_ZONE = {(c, r) for c in range(2, 6) for r in range(4, 9)}
COLOURED_FACIAL = {2, 5}          # full beard, mutton chops
MOUTH_HIDING_FACIAL = {1, 2, 3, 6}


def hair_cells(cat, idx):
    """Small-face cells this hair/facial variant paints in hair colour.

    A cell qualifies when the variant covers at least half of the silhouette
    there (measured against the reference head). The eye/nose/mouth zone
    always stays skin-coloured so the eye and mouth attributes keep working.
    """
    if cat == "facial" and idx not in COLOURED_FACIAL:
        return set()
    f = render_feature(cat, idx, 1.0)
    head = render_feature("head", 0, 1.0)
    cells = set()
    for r in range(12):
        for c in range(8):
            if (c, r) in FACE_ZONE:
                continue
            hp = sp = 0
            for y in range(8):
                for x in range(8):
                    m = f.mask.get(c * 8 + x, r * 8 + y)
                    hp += m
                    sp += m or head.mask.get(c * 8 + x, r * 8 + y)
            if hp >= 8 and hp * 2 >= sp:
                cells.add((c, r))
    return cells


def render_feature(cat, idx, scale):
    c = Canvas(scale)
    if cat == "head":
        draw_head(c, HEADS[idx])
    else:
        dict(CATEGORIES)[cat][idx][1](c)
    return c


def compose(sel, scale):
    """sel: dict category -> index. Returns (ink, sil) layers."""
    W, H = round(SMALL_W * scale), round(SMALL_H * scale)
    ink, sil = Layer(W, H), Layer(W, H)
    order = ["head", "collar", "marks_under", "eyes", "brows", "nose", "mouth", "facial", "hair", "marks_over"]
    for cat in order:
        if cat.startswith("marks"):
            over = sel["marks"] in GLASSES
            if over != (cat == "marks_over"):
                continue
            f = render_feature("marks", sel["marks"], scale)
        else:
            f = render_feature(cat, sel[cat], scale)
        for i in range(W * H):
            if f.mask.p[i]:
                ink.p[i] = 0
                sil.p[i] = 1
            if f.ink.p[i]:
                ink.p[i] = 1
    return ink, sil
