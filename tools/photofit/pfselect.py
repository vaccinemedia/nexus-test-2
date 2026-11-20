"""Subject -> photofit feature selection, shared by the previews and the Z80 tables.

The Z80 code in photofit6.asm performs exactly the same steps, so a preview
rendered here for a given (name index, seed) matches the game pixel for pixel.
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

M, F, EITHER = 0, 1, 2
GENDER = {
    "KIRA": F, "LEON": M, "YUKI": F, "COLE": M, "REINA": F, "DANA": F, "ALEX": EITHER, "NASH": M,
    "JUDE": EITHER, "MIRA": F, "ANJA": F, "SEV": M, "IRIS": F, "MARCO": M, "TESS": F, "OMAR": M,
    "LENA": F, "KAI": EITHER, "NOOR": F, "VIC": M, "ESME": F, "BRAM": M, "SUNI": F, "HALE": M,
    "PIA": F, "GIL": M, "ZOE": F, "IVO": M, "RUTH": F, "EDEN": EITHER, "TOMA": M, "ADA": F,
}

# Selection record order (pf_sel): matches build_data.CATS.
CAT_ORDER = ["head", "collar", "marks", "eyes", "brows", "nose", "mouth", "facial", "hair"]

# Eight weighted choices per category and gender (repeats raise the odds).
LISTS = {
    "head":   ([0, 1, 2, 3, 5, 1, 5, 3], [0, 2, 4, 0, 4, 2, 3, 0]),
    "collar": ([0, 1, 2, 0, 0, 1, 2, 0], [0, 1, 2, 1, 0, 1, 2, 2]),
    "marks":  ([0, 0, 0, 1, 2, 3, 4, 7], [0, 0, 0, 1, 2, 5, 6, 7]),
    "eyes":   ([0, 1, 2, 3, 5, 6, 7, 3], [0, 1, 4, 4, 6, 2, 5, 7]),
    "brows":  ([0, 2, 3, 4, 6, 7, 0, 2], [1, 5, 4, 1, 5, 3, 0, 4]),
    "nose":   ([0, 1, 2, 3, 4, 5, 6, 7], [0, 3, 4, 6, 3, 0, 4, 1]),
    "mouth":  ([0, 1, 2, 4, 5, 6, 0, 2], [3, 3, 1, 0, 5, 6, 7, 3]),
    "facial": ([0, 0, 1, 2, 3, 4, 5, 6], [0, 0, 0, 0, 0, 0, 0, 0]),
    "hair":   ([0, 1, 2, 3, 4, 5, 9, 10], [1, 2, 6, 7, 8, 9, 10, 11]),
}

# The mirror level's subject is always the same man.
DECKARD = dict(head=1, collar=0, marks=0, eyes=3, brows=2, nose=0, mouth=2, facial=4, hair=2)
DECKARD_SKIN, DECKARD_HAIR = 0, 1


def subject_names():
    src = open(os.path.join(ROOT, "src", "subjects.asm")).read()
    return re.findall(r'^\s*SNAME\s+"([^"]+)"', src, re.M)


def genders():
    out = []
    for n in subject_names():
        first = n.split()[0]
        if first not in GENDER:
            raise SystemExit(f"no gender listed for subject name {n!r} in tools/photofit/select.py")
        out.append(GENDER[first])
    return out


class XorShift16:
    """Z80 16-bit xorshift (ld a,h : rra : ld a,l : rra : xor h ...)."""

    def __init__(self, seed):
        self.hl = seed & 0xFFFF or 1

    def next(self):
        h, l = self.hl >> 8, self.hl & 0xFF
        h = ((((h & 1) << 7) | (l >> 1)) ^ h) & 0xFF
        l = ((((l & 1) << 7) | (h >> 1)) ^ l) & 0xFF
        h = l ^ h
        self.hl = (h << 8) | l
        return h


def select(name_index, seed):
    """Returns (sel dict, skin index, hair-colour index)."""
    if name_index is None:
        return dict(DECKARD), DECKARD_SKIN, DECKARD_HAIR
    rng = XorShift16(seed)
    g = genders()[name_index]
    if g == EITHER:
        g = rng.next() & 1
    sel = {cat: LISTS[cat][g][rng.next() & 7] for cat in CAT_ORDER}
    skin = rng.next() & 3
    hair = rng.next() & 3
    return sel, skin, hair


def asm_tables():
    lines = ["; Selection tables (generated from tools/photofit/select.py)", "pf_gender:"]
    g = genders()
    lines.append("    DB " + ",".join(str(v) for v in g))
    lines.append(f"    ASSERT $ - pf_gender == SUBJ_NAME_COUNT, \"photofit gender table out of step with subj_names\"")
    lines.append("pf_lists:                ; per category: 8 male choices, then 8 female")
    for cat in CAT_ORDER:
        m, f = LISTS[cat]
        lines.append("    DB " + ",".join(str(v) for v in m + f) + f"   ; {cat}")
    lines.append("pf_deckard:")
    lines.append("    DB " + ",".join(str(DECKARD[c]) for c in CAT_ORDER) + f", {DECKARD_SKIN}, {DECKARD_HAIR}")
    return lines
