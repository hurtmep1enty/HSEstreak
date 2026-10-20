
from markupsafe import Markup

CX = 60        
BASE = 126      

# ключ: (название, цвет по умолчанию, короткое описание)
SPECIES = {
    "sunflower": ("Подсолнух", "#fdd835", "Тянется к солнцу"),
    "daisy":     ("Ромашка",   "#ffb300", "Простая и милая"),
    "tulip":     ("Тюльпан",   "#e53935", "Любит весну"),
    "lavender":  ("Лаванда",   "#8e24aa", "Пахнет спокойствием"),
    "rose":      ("Роза",      "#d81b60", "Капризная красавица"),
    "cactus":    ("Кактус",    "#f06292", "Выносливый, как ты"),
    "tree":      ("Дерево",    "#e53935", "Растёт медленно, но надолго"),
    "bamboo":    ("Бамбук",    "#26a69a", "Самый быстрый рост"),
}
DEFAULT_SPECIES = "sunflower"
STAGE_COUNT = 6


#кирпичики

def _num(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _leaf(x, y, angle, scale=1.0, cls="leaf"):
    return (f'<path class="{cls}" d="M0 0C5-7 15-7 20 0C15 7 5 7 0 0Z" '
            f'transform="translate({_num(x)} {_num(y)}) rotate({_num(angle)}) scale({_num(scale)})"/>')


def _stem(height, bend=3):
    top = BASE - height
    path = (f'<path class="stem" d="M{CX} {BASE} Q{CX + bend} {_num(BASE - height / 2)} {CX} {_num(top)}" '
            f'fill="none" stroke-width="3.4" stroke-linecap="round"/>')
    return path, top


def _leaf_pairs(height, count, scale=1.0):
    out = []
    for i in range(count):
        y = BASE - height * (0.22 + 0.5 * i / max(count - 1, 1)) if count > 1 else BASE - height * 0.4
        s = scale * (1.15 - 0.25 * i / max(count - 1, 1))
        out.append(_leaf(CX, y, -32, s))
        out.append(_leaf(CX, y - 4, 212, s))
    return "".join(out)


def _petals(cy, count, length, width, cls, center_r, rot=0.0):
    out = []
    d = center_r + length * 0.72
    for i in range(count):
        a = rot + i * 360 / count
        out.append(f'<ellipse class="{cls}" cx="{CX}" cy="{_num(cy - d)}" rx="{_num(width)}" ry="{_num(length)}" '
                   f'transform="rotate({_num(a)} {CX} {_num(cy)})"/>')
    return "".join(out)


def _sparkle(x, y, size=4):
    s = size
    return (f'<path class="spark" d="M{_num(x)} {_num(y - s)}Q{_num(x)} {_num(y)} {_num(x + s)} {_num(y)}'
            f'Q{_num(x)} {_num(y)} {_num(x)} {_num(y + s)}Q{_num(x)} {_num(y)} {_num(x - s)} {_num(y)}'
            f'Q{_num(x)} {_num(y)} {_num(x)} {_num(y - s)}Z"/>')


def _bud(cy, big=False):
    k = 1.15 if big else 1
    return (f'<ellipse class="leaf-d" cx="{CX}" cy="{_num(cy)}" rx="{_num(6 * k)}" ry="{_num(8 * k)}"/>'
            f'<ellipse class="hc" cx="{CX}" cy="{_num(cy - 4 * k)}" rx="{_num(4 * k)}" ry="{_num(6 * k)}"/>')


def _seed():
    return ('<ellipse class="seed" cx="60" cy="121" rx="5.5" ry="3.6" transform="rotate(-22 60 121)"/>'
            '<path class="seed-line" d="M56 121.5Q60 119.5 64 120" fill="none" stroke-width="1"/>')


#цветущие растения

# Высота стебля по стадиям 1..5 для цветов
FLOWER_H = [0, 15, 36, 54, 64, 72]


def _flower(kind, stage):
    h = FLOWER_H[stage]
    stem, top = _stem(h)
    parts = [stem]
    if stage == 1:
        parts += [_leaf(CX, top + 1, -30, 0.7), _leaf(CX, top + 1, 210, 0.7)]
        return "".join(parts)
    parts.append(_leaf_pairs(h, 1 if stage == 2 else 2, 1.0 if stage < 5 else 1.2))
    if stage == 2:
        parts += [_leaf(CX, top + 2, -40, 0.8), _leaf(CX, top + 2, 220, 0.8)]
        return "".join(parts)

    cy = top
    if stage == 3:                                   # бутон
        if kind == "lavender":
            parts.append(_lavender_head(cy, 3, green=True))
        elif kind == "tulip":
            parts.append(f'<ellipse class="hc" cx="{CX}" cy="{_num(cy - 6)}" rx="6" ry="10"/>'
                         f'<path class="leaf" d="M54 {_num(cy - 2)}Q60 {_num(cy + 6)} 66 {_num(cy - 2)}Z"/>')
        else:
            parts.append(_bud(cy - 4, big=kind in ("sunflower", "rose")))
        return "".join(parts)

    big = stage == 5
    if kind == "sunflower":
        parts.append(_petals(cy - 8, 14 if not big else 18, 12 if not big else 15, 4.2, "hc", 9 if not big else 11))
        if big:
            parts.append(_petals(cy - 8, 18, 11, 3.6, "hc-d", 10, rot=10))
        parts.append(f'<circle class="ctr" cx="{CX}" cy="{_num(cy - 8)}" r="{9 if not big else 11}"/>'
                     f'<circle class="ctr-l" cx="{CX}" cy="{_num(cy - 8)}" r="{4.5 if not big else 6}"/>')
    elif kind == "daisy":
        parts.append(_petals(cy - 6, 12 if not big else 16, 10 if not big else 12, 3.2, "petal-w", 6 if not big else 7))
        parts.append(f'<circle class="hc" cx="{CX}" cy="{_num(cy - 6)}" r="{6 if not big else 7.5}"/>'
                     f'<circle class="hc-l" cx="{CX - 2}" cy="{_num(cy - 8)}" r="2"/>')
    elif kind == "tulip":
        k = 1 if not big else 1.25
        for ang, cls in ((-24, "hc-d"), (24, "hc-d"), (0, "hc")):
            parts.append(f'<ellipse class="{cls}" cx="{CX}" cy="{_num(cy - 11 * k)}" rx="{_num(6.5 * k)}" ry="{_num(13 * k)}" '
                         f'transform="rotate({ang} {CX} {_num(cy)})"/>')
        parts.append(f'<path class="hc-l" d="M{CX} {_num(cy - 22 * k)}Q{CX + 3} {_num(cy - 12 * k)} {CX} {_num(cy - 3)}'
                     f'Q{CX - 3} {_num(cy - 12 * k)} {CX} {_num(cy - 22 * k)}Z" opacity=".55"/>')
    elif kind == "rose":
        k = 1 if not big else 1.25
        c = cy - 8
        for i in range(5):
            a = i * 72
            parts.append(f'<circle class="hc-d" cx="{CX}" cy="{_num(c - 8 * k)}" r="{_num(7 * k)}" transform="rotate({a} {CX} {_num(c)})"/>')
        for i in range(5):
            a = i * 72 + 36
            parts.append(f'<circle class="hc" cx="{CX}" cy="{_num(c - 4.5 * k)}" r="{_num(5 * k)}" transform="rotate({a} {CX} {_num(c)})"/>')
        parts.append(f'<circle class="hc-l" cx="{CX}" cy="{_num(c)}" r="{_num(3 * k)}"/>'
                     f'<path class="hc-ds" d="M{CX - 2} {_num(c)}Q{CX} {_num(c - 4)} {CX + 3} {_num(c - 1)}" '
                     f'stroke-width="1" stroke-linecap="round"/>')
    elif kind == "lavender":
        parts.append(_lavender_head(cy, 7 if not big else 9))
        if big:
            for dx, dy in ((-9, 8), (9, 6)):
                parts.append(f'<path class="stem" d="M{CX} {BASE - 24}Q{CX + dx} {BASE - 40} {CX + dx * 1.4} {_num(BASE - 62 + dy)}" '
                             f'fill="none" stroke-width="2.6" stroke-linecap="round"/>')
                parts.append(_lavender_head(BASE - 62 + dy, 7, dx=dx * 1.4))
    if big:
        parts += [_sparkle(CX + 26, cy - 22, 4), _sparkle(CX - 28, cy - 6, 3)]
    return "".join(parts)


def _lavender_head(cy, buds, green=False, dx=0):
    cls = "leaf-d" if green else "hc"
    out = []
    x0 = CX + dx
    for i in range(buds):
        y = cy - i * 5.2 + 4
        side = -3.2 if i % 2 else 3.2
        out.append(f'<ellipse class="{cls}" cx="{_num(x0 + side)}" cy="{_num(y)}" rx="3.2" ry="4.2" '
                   f'transform="rotate({"-" if i % 2 else ""}25 {_num(x0 + side)} {_num(y)})"/>')
    out.append(f'<ellipse class="{cls}" cx="{_num(x0)}" cy="{_num(cy - buds * 5.2 + 4)}" rx="2.8" ry="4"/>')
    return "".join(out)


#кактус

CACTUS_H = [0, 14, 28, 44, 56, 66]


def _cactus(stage):
    h = CACTUS_H[stage]
    top = BASE - h
    parts = []
    if stage >= 3:
        y = BASE - h * 0.45
        parts.append(f'<path class="cac-s" d="M{CX - 8} {_num(y)}H{CX - 18}Q{CX - 23} {_num(y)} {CX - 23} {_num(y - 6)}V{_num(y - 16)}" '
                     f'fill="none" stroke-width="8" stroke-linecap="round"/>')
    if stage >= 4:
        y = BASE - h * 0.6
        parts.append(f'<path class="cac-s" d="M{CX + 8} {_num(y)}H{CX + 17}Q{CX + 22} {_num(y)} {CX + 22} {_num(y - 6)}V{_num(y - 14)}" '
                     f'fill="none" stroke-width="8" stroke-linecap="round"/>')
    parts.append(f'<rect class="cac" x="{CX - 10}" y="{_num(top)}" width="20" height="{_num(h + 2)}" rx="10"/>')
    if stage >= 2:
        parts.append(f'<path class="cac-d" d="M{CX} {_num(top + 6)}V{BASE - 2}" fill="none" stroke-width="1.6" stroke-linecap="round"/>'
                     f'<path class="cac-d" d="M{CX - 5} {_num(top + 9)}Q{CX - 5.5} {_num(BASE - h / 2)} {CX - 5} {BASE - 2}" fill="none" stroke-width="1.2"/>'
                     f'<path class="cac-d" d="M{CX + 5} {_num(top + 9)}Q{CX + 5.5} {_num(BASE - h / 2)} {CX + 5} {BASE - 2}" fill="none" stroke-width="1.2"/>')
        for i in range(min(stage + 1, 5)):
            y = top + 12 + i * 8
            parts.append(f'<path class="spine" d="M{CX - 7} {_num(y)}l-3 -1.5M{CX + 7} {_num(y + 3)}l3 -1.5" stroke-width="1" stroke-linecap="round"/>')
    if stage == 3:
        parts.append(f'<ellipse class="hc" cx="{CX}" cy="{_num(top - 1)}" rx="3.5" ry="4.5"/>')
    if stage >= 4:
        r = 4 if stage == 4 else 5
        for i in range(6):
            parts.append(f'<ellipse class="hc" cx="{CX}" cy="{_num(top - 4 - r * 0.6)}" rx="{_num(r * 0.55)}" ry="{_num(r)}" '
                         f'transform="rotate({i * 60} {CX} {_num(top - 3)})"/>')
        parts.append(f'<circle class="hc-l" cx="{CX}" cy="{_num(top - 3)}" r="2.4"/>')
    if stage == 5:
        parts += [_sparkle(CX + 24, top - 8, 4), _sparkle(CX - 26, top + 6, 3)]
    return "".join(parts)


#дерево

def _tree(stage):
    parts = []
    if stage == 1:
        stem, top = _stem(16)
        return stem + _leaf(CX, top + 1, -30, 0.75) + _leaf(CX, top + 1, 210, 0.75)
    trunk_h = [0, 16, 26, 38, 46, 52][stage]
    tw = [0, 3, 6, 8, 10, 12][stage]
    top = BASE - trunk_h
    parts.append(f'<path class="trunk" d="M{CX - tw / 2 - 1} {BASE}Q{CX - tw / 2 + 1} {_num(BASE - trunk_h / 2)} {CX - tw / 2} {_num(top)}'
                 f'H{CX + tw / 2}Q{CX + tw / 2 - 1} {_num(BASE - trunk_h / 2)} {CX + tw / 2 + 1} {BASE}Z"/>')
    if stage >= 4:   # ветки
        parts.append(f'<path class="trunk-s" d="M{CX} {_num(top + 14)}L{CX - 14} {_num(top)}M{CX} {_num(top + 20)}L{CX + 14} {_num(top + 4)}" '
                     f'fill="none" stroke-width="3.2" stroke-linecap="round"/>')
    crowns = {
        2: [(0, -6, 12)],
        3: [(0, -12, 16), (-12, -2, 11), (12, -2, 11)],
        4: [(0, -16, 19), (-16, -4, 14), (16, -4, 14), (0, -2, 13)],
        5: [(0, -20, 22), (-20, -6, 16), (20, -6, 16), (-8, 0, 14), (9, 1, 14), (0, -6, 18)],
    }[stage]
    for dx, dy, r in crowns:
        parts.append(f'<circle class="leaf" cx="{CX + dx}" cy="{_num(top + dy)}" r="{r}"/>')
    hl = crowns[0]
    parts.append(f'<circle class="leaf-l" cx="{CX + hl[0] - hl[2] * 0.3}" cy="{_num(top + hl[1] - hl[2] * 0.3)}" r="{_num(hl[2] * 0.5)}"/>')
    if stage == 4:    # цветение
        for dx, dy in ((-10, -18), (6, -24), (14, -8), (-18, -4), (0, -6), (-4, -28)):
            parts.append(f'<circle class="hc-l" cx="{CX + dx}" cy="{_num(top + dy)}" r="2.6"/>')
    if stage == 5:    # плоды
        for dx, dy in ((-14, -14), (6, -26), (18, -8), (-22, -2), (2, -8), (-6, 4), (12, 4)):
            parts.append(f'<circle class="hc" cx="{CX + dx}" cy="{_num(top + dy)}" r="3.6"/>'
                         f'<circle class="hl" cx="{CX + dx - 1}" cy="{_num(top + dy - 1.2)}" r="1"/>')
        parts += [_sparkle(CX + 32, top - 28, 4), _sparkle(CX - 34, top - 10, 3)]
    return "".join(parts)


#бамбук

def _bamboo(stage):
    stalks = {
        1: [(0, 16)],
        2: [(0, 34)],
        3: [(0, 52), (11, 30)],
        4: [(0, 66), (11, 44), (-11, 38)],
        5: [(0, 80), (12, 58), (-12, 50), (23, 32)],
    }[stage]
    parts = []
    for dx, h in sorted(stalks, key=lambda s: s[1]):
        x = CX + dx
        top = BASE - h
        parts.append(f'<path class="bam" d="M{x} {BASE}V{top}" fill="none" stroke-width="6" stroke-linecap="round"/>')
        n = int(h // 14)
        for i in range(1, n + 1):
            y = BASE - i * 14
            parts.append(f'<path class="hc-ds" d="M{x - 3.6} {y}H{x + 3.6}" stroke-width="1.8" stroke-linecap="round"/>')
            if stage >= 3 and i >= n - 1 and i > 1:
                side = 1 if (i + dx) % 2 else -1
                parts.append(_leaf(x, y, -25 if side > 0 else 205, 0.9))
                parts.append(_leaf(x, y + 1, -75 if side > 0 else 255, 0.7))
        if stage >= 2:
            parts.append(_leaf(x, top + 2, -40, 0.9))
            parts.append(_leaf(x, top + 4, 220, 0.9))
        else:
            parts.append(_leaf(x, top + 1, -30, 0.7))
            parts.append(_leaf(x, top + 1, 210, 0.7))
    if stage == 5:
        parts += [_sparkle(CX + 30, BASE - 76, 4), _sparkle(CX - 26, BASE - 60, 3)]
    return "".join(parts)


#главный вход

def _ground():
    return ('<ellipse class="soil" cx="60" cy="129" rx="44" ry="9"/>'
            '<ellipse class="soil-l" cx="60" cy="126.5" rx="35" ry="6"/>'
            '<path class="grass" d="M22 126l-2-9 5 7 2-8 3 9M92 127l1-8 4 7 3-6 1 8" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')


def plant_svg(species, stage, color, wilting=False, label=None):
    if species not in SPECIES:
        species = DEFAULT_SPECIES
    stage = max(0, min(STAGE_COUNT - 1, int(stage)))
    if stage == 0:
        body = _seed()
    elif species == "cactus":
        body = _cactus(stage)
    elif species == "tree":
        body = _tree(stage)
    elif species == "bamboo":
        body = _bamboo(stage)
    else:
        body = _flower(species, stage)

    name = SPECIES[species][0]
    text = label or name
    wilt = " wilt" if wilting else ""
    style = f' style="--hc:{Markup.escape(color)}"' if color else ""
    return Markup(
        f'<svg class="plant{wilt}" viewBox="0 0 120 140" role="img" aria-label="{Markup.escape(text)}"'
        f'{style} xmlns="http://www.w3.org/2000/svg">'
        f'{_ground()}<g class="body">{body}</g></svg>'
    )
