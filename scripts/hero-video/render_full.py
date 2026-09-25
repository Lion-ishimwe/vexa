"""
VEXA full-width hero video: live deliveries across Kigali.

    python scripts/hero-video/cutout.py            # once, after replacing source/founder.jpg
    python scripts/hero-video/render_full.py        # full render
    python scripts/hero-video/render_full.py --stills

The left ~half stays dark for the hero headline; the story plays on the right.
Everything important sits inside y 150..930 because wide screens crop top and bottom.
Outputs to src/assets/video/.
"""
import json
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "src")
OUT_DIR = os.path.join(SRC, "assets", "video")
FONTS = "C:/Windows/Fonts/"

W, H = 1920, 1080
FPS = 30
DELIVERY = 10.0                      # seconds per delivery story
TAU = 2 * math.pi
random.seed(11)

INK = (13, 12, 10)
INK2 = (23, 21, 15)
GOLD_HI = (243, 220, 155)
GOLD = (201, 161, 74)
GOLD_LO = (143, 109, 43)
MUTED = (176, 167, 150)
WHITE = (255, 255, 255)
GREEN = (47, 160, 94)

catalog = json.load(open(os.path.join(SRC, "_data", "catalog.json"), encoding="utf8"))
products = {p["slug"]: p for p in catalog["products"]}

# name, map position (0..1 inside the map area), product, payment line
DELIVERIES = [
    ("Kimihurura", (0.62, 0.42), "kit-of-4-cameras-colorvu", "Paid on delivery · MTN MoMo"),
    ("Nyarutarama", (0.76, 0.10), "hp-omnibook-ultra-5-new", "Paid on delivery · Airtel Money"),
    ("Kicukiro", (0.66, 0.84), "bosch-wall-mount-split-12-000-btu-inverter", "Delivered & installed · Cash"),
]
LOOP = DELIVERY * len(DELIVERIES)
SHOW_FOUNDER = False                 # the founder cut-out on the right; off since 25 Sep 2026
STORE = ("VEXA", (0.36, 0.50))
OTHER_PLACES = [("Kacyiru", (0.44, 0.16)), ("Remera", (0.92, 0.50)), ("Nyamirambo", (0.12, 0.74)),
                ("Gikondo", (0.44, 0.78)), ("Kimisagara", (0.16, 0.36))]


def font(name, size):
    return ImageFont.truetype(FONTS + name, size)


F_DISPLAY = "PERTIBD.TTF"
F_UI = "segoeui.ttf"
F_SEMI = "seguisb.ttf" if os.path.exists(FONTS + "seguisb.ttf") else "segoeuib.ttf"
F_BOLD = "segoeuib.ttf"


# ------------------------------------------------------------------ helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, s, d):
    return clamp((t - s) / d)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in(x):
    return x ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def with_alpha(img, a):
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * a)))
    return out


def place(canvas, img, cx, cy, scale=1.0, alpha=1.0):
    if alpha <= 0.003:
        return
    if abs(scale - 1) > 0.002:
        w, h = img.size
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    img = with_alpha(img, alpha)
    w, h = img.size
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(w, W - x), min(h, H - y)
    if ex > sx and ey > sy:
        canvas.alpha_composite(img, (x + sx, y + sy), (sx, sy, ex, ey))


def place_tl(canvas, img, x, y, alpha=1.0, scale=1.0):
    w, h = img.size
    place(canvas, img, x + w * scale / 2, y + h * scale / 2, scale, alpha)


def gold_gradient(w, h):
    y = np.linspace(0, 1, h)[:, None]
    out = np.zeros((h, w, 3))
    for (p0, c0), (p1, c1) in zip([(0, GOLD_HI), (0.55, GOLD)], [(0.55, GOLD), (1, GOLD_LO)]):
        m = ((y >= p0) & (y <= p1))[:, 0]
        k = ((y[m] - p0) / (p1 - p0))
        for i in range(3):
            out[m, :, i] = c0[i] + (c1[i] - c0[i]) * k
    return Image.fromarray(out.astype(np.uint8), "RGB")


def text_img(text, fnt, fill=WHITE, tracking=0, gradient=False, pad=6):
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    widths = [probe.textlength(ch, font=fnt) for ch in text] if tracking else None
    total = (sum(widths) + tracking * (len(text) - 1)) if tracking else probe.textlength(text, font=fnt)
    asc, desc = fnt.getmetrics()
    w, h = int(total + pad * 2), asc + desc + pad * 2
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    if tracking:
        x = pad
        for ch, cw in zip(text, widths):
            d.text((x, pad), ch, font=fnt, fill=255)
            x += cw + tracking
    else:
        d.text((pad, pad), text, font=fnt, fill=255)
    out = (gold_gradient(w, h) if gradient else Image.new("RGB", (w, h), fill)).convert("RGBA")
    out.putalpha(mask)
    return out


def radial(w, h, cx, cy, r, color, power=1.6, alpha=1.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    k = np.clip(1 - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r, 0, 1) ** power
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (k * 255 * alpha).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def rounded(w, h, r, fill, outline=None, width=1, ss=3):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill,
                                         outline=outline, width=width * ss if outline else 0)
    return im.resize((w, h), Image.LANCZOS)


def circle(d, fill, ss=4):
    im = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((0, 0, d * ss - 1, d * ss - 1), fill=fill)
    return im.resize((d, d), Image.LANCZOS)


def check_badge(d, fill=GREEN):
    ss = 4
    im = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse((0, 0, d * ss - 1, d * ss - 1), fill=fill + (255,))
    u = d * ss / 24
    dr.line([(6.5 * u, 12.5 * u), (10.5 * u, 16.5 * u), (17.5 * u, 8.5 * u)], fill=WHITE, width=int(2.6 * u), joint="curve")
    return im.resize((d, d), Image.LANCZOS)


def glass(w, h, r=22):
    """Dark glass panel with a hairline gold border and a soft shadow."""
    pad = 40
    out = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad + 6, pad + 18, pad + w - 6, pad + h + 8), r, fill=(0, 0, 0, 170))
    out.alpha_composite(sh.filter(ImageFilter.GaussianBlur(18)))
    panel = rounded(w, h, r, (22, 20, 15, 232), outline=(236, 208, 138, 70), width=1)
    out.alpha_composite(panel, (pad, pad))
    return out, pad


def rwf(n):
    return f"RWF {n:,}" if n else "Price on request"


# ------------------------------------------------------------------ background
BASE = Image.new("RGBA", (W, H), INK + (255,))
BASE.alpha_composite(radial(W, H, W * 0.74, H * 0.42, W * 0.55, (48, 38, 20), 1.7))


def contour_layer():
    """Faint gold contour lines: Kigali, city of a thousand hills."""
    ss = 2
    im = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    hills = [(1180, 260, 330, 0.0), (1560, 820, 420, 1.3), (1850, 180, 260, 2.2), (980, 900, 300, 3.1), (1400, 520, 220, 4.0)]
    for hx, hy, hr, ph in hills:
        for k in range(1, 9):
            r = hr * k / 8
            pts = []
            for i in range(121):
                a = TAU * i / 120
                wob = 1 + 0.10 * math.sin(3 * a + ph + k * 0.4) + 0.05 * math.sin(5 * a - ph)
                pts.append(((hx + math.cos(a) * r * wob * 1.25) * ss, (hy + math.sin(a) * r * wob * 0.8) * ss))
            d.line(pts, fill=(201, 161, 74, 38 + k * 3), width=ss)
    im = im.resize((W, H), Image.LANCZOS)
    # fade the lines out towards the headline side
    fade = np.clip((np.arange(W) - 760) / 520, 0, 1)[None, :] ** 1.4
    a = np.asarray(im).copy()
    a[..., 3] = (a[..., 3] * fade).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


CONTOURS = contour_layer()


def dot_sprite(r, soft):
    size = int(r * 2 + soft * 4 + 4)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    c = size / 2
    ImageDraw.Draw(im).ellipse((c - r, c - r, c + r, c + r), fill=GOLD_HI + (255,))
    return im.filter(ImageFilter.GaussianBlur(soft)) if soft else im


DUST = []
for _ in range(70):
    depth = random.random()
    DUST.append({
        "x": random.uniform(700, W), "y": random.uniform(0, H),
        "vy": -(1 if depth < 0.5 else 2) * (H + 40) / LOOP,
        "sway": random.choice([1, 2]), "tw": random.choice([3, 4, 5, 6]),
        "sprite": dot_sprite(1.2 + depth * 4.5, 0.8 + depth * 2), "a": 0.15 + depth * 0.5, "ph": random.uniform(0, TAU),
    })

# ------------------------------------------------------------------ founder figure
FIG_H = 1000
fig_src = Image.open(os.path.join(HERE, "source", "founder-cutout.png"))
FIG = fig_src.resize((int(fig_src.width * FIG_H / fig_src.height), FIG_H), Image.LANCZOS)
fa = np.asarray(FIG).astype(np.float32)
# warm grade to sit in the gold scene, and melt the torso into the bottom edge
fa[..., 0] *= 1.04
fa[..., 2] *= 0.93
fade = np.clip((FIG_H - np.arange(FIG_H)) / 170, 0, 1)[:, None]
fa[..., 3] *= fade
FIG = Image.fromarray(np.clip(fa, 0, 255).astype(np.uint8), "RGBA")
# rim light: blurred silhouette tinted gold, sitting just behind the figure
sil = FIG.getchannel("A").filter(ImageFilter.GaussianBlur(14))
RIM = Image.new("RGBA", FIG.size, GOLD_HI + (0,))
RIM.putalpha(sil.point(lambda v: int(v * 0.55)))
FIG_CX, FIG_TOP = 1560, 70
BACKLIGHT = radial(1100, 1100, 550, 550, 550, (201, 161, 74), 2.0, 0.42)

# ------------------------------------------------------------------ tracking panel (map)
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 1250, 176, 430, 330
MAP_X, MAP_Y, MAP_W, MAP_H = 22, 62, PANEL_W - 44, PANEL_H - 84


def map_xy(p):
    return (PANEL_X + MAP_X + p[0] * MAP_W, PANEL_Y + MAP_Y + p[1] * MAP_H)


def route_points(dest, n=90):
    """Curved road-like path from the store to a neighbourhood."""
    (x0, y0), (x1, y1) = map_xy(STORE[1]), map_xy(dest)
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    nx, ny = -(y1 - y0), (x1 - x0)
    ln = math.hypot(nx, ny) or 1
    bend = 0.22 * math.hypot(x1 - x0, y1 - y0)
    cx, cy = mx + nx / ln * bend, my + ny / ln * bend
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t ** 2 * x1
        y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t ** 2 * y1
        x += 3 * math.sin(t * 17)          # a little street wiggle
        pts.append((x, y))
    return pts


ROUTES = [route_points(d[1]) for d in DELIVERIES]


def build_panel():
    img, pad = glass(PANEL_W, PANEL_H)
    d = ImageDraw.Draw(img)
    ox, oy = pad, pad
    title = text_img("LIVE DELIVERIES", font(F_SEMI, 15), GOLD, tracking=4, pad=0)
    img.alpha_composite(title, (ox + 44, oy + 22))
    city = text_img("Kigali", font(F_UI, 17), MUTED, pad=0)
    img.alpha_composite(city, (ox + PANEL_W - city.width - 22, oy + 20))
    # map: faint roads between every place, as a street grid feel
    ss = 3
    mp = Image.new("RGBA", (MAP_W * ss, MAP_H * ss), (0, 0, 0, 0))
    md = ImageDraw.Draw(mp)
    places = [STORE] + [(n, p) for n, p, _, _ in DELIVERIES] + OTHER_PLACES
    for i, (_, a) in enumerate(places):
        for _, b in places[i + 1:]:
            if math.hypot(a[0] - b[0], a[1] - b[1]) < 0.42:
                md.line([(a[0] * MAP_W * ss, a[1] * MAP_H * ss), (b[0] * MAP_W * ss, b[1] * MAP_H * ss)],
                        fill=(201, 161, 74, 60), width=2 * ss)
    for k in range(5):  # hill rings
        cx, cy, r = [(0.3, 0.3, 0.2), (0.75, 0.65, 0.24), (0.9, 0.15, 0.14), (0.15, 0.8, 0.18), (0.5, 0.95, 0.15)][k]
        for j in (1, 2, 3):
            rr = r * j / 3
            md.ellipse(((cx - rr) * MAP_W * ss, (cy - rr * 0.8) * MAP_H * ss, (cx + rr) * MAP_W * ss, (cy + rr * 0.8) * MAP_H * ss),
                       outline=(201, 161, 74, 26), width=ss)
    mp = mp.resize((MAP_W, MAP_H), Image.LANCZOS)
    img.alpha_composite(mp, (ox + MAP_X, oy + MAP_Y))
    lab = font(F_UI, 14)
    for name, p in OTHER_PLACES + [(n, p) for n, p, _, _ in DELIVERIES]:
        x, y = ox + MAP_X + p[0] * MAP_W, oy + MAP_Y + p[1] * MAP_H
        d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(176, 167, 150, 200))
        t = text_img(name, lab, (150, 142, 126), pad=0)
        tx = x + 8 if p[0] < 0.8 else x - 8 - t.width
        img.alpha_composite(t, (int(tx), int(y - 10)))
    return img, pad


PANEL, PANEL_PAD = build_panel()
LIVE_DOT = circle(12, GREEN + (255,))
LIVE_HALO = circle(28, GREEN + (90,))
STORE_PIN = circle(22, GOLD + (255,))
STORE_HALO = radial(90, 90, 45, 45, 45, (236, 208, 138), 1.8, 0.8)
STORE_LABEL = text_img("VEXA store", font(F_SEMI, 14), GOLD_HI, pad=0)
RIDER = circle(16, GOLD_HI + (255,))
RIDER_HALO = radial(70, 70, 35, 35, 35, (243, 220, 155), 1.6, 0.9)
DEST_PIN = circle(16, WHITE + (255,))
DONE_PIN = check_badge(20)


def box_icon(size=18):
    ss = 4
    im = Image.new("RGBA", (size * ss, size * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = size * ss / 24
    col = INK + (255,)
    d.polygon([(12 * u, 3 * u), (21 * u, 7.5 * u), (21 * u, 17 * u), (12 * u, 21.5 * u), (3 * u, 17 * u), (3 * u, 7.5 * u)], outline=col, width=int(2 * u))
    d.line([(3 * u, 7.5 * u), (12 * u, 12 * u), (21 * u, 7.5 * u)], fill=col, width=int(2 * u))
    d.line([(12 * u, 12 * u), (12 * u, 21.5 * u)], fill=col, width=int(2 * u))
    return im.resize((size, size), Image.LANCZOS)


BOX = box_icon(16)


# ------------------------------------------------------------------ order cards
CARD_W, CARD_H = 430, 190


def order_card(dest, slug):
    p = products[slug]
    img, pad = glass(CARD_W, CARD_H)
    ox, oy = pad, pad
    thumb = rounded(118, 118, 16, (255, 255, 255, 255))
    ph = Image.open(os.path.join(SRC, p["img"].lstrip("/").replace("/", os.sep))).convert("RGBA")
    ph.thumbnail((100, 100), Image.LANCZOS)
    thumb.alpha_composite(ph, ((118 - ph.width) // 2, (118 - ph.height) // 2))
    img.alpha_composite(thumb, (ox + 20, oy + 20))
    x = ox + 156
    img.alpha_composite(text_img("YOUR ORDER", font(F_SEMI, 13), GOLD, tracking=3, pad=0), (x, oy + 22))
    tf = font(F_SEMI, 20)
    title = p["title"] if len(p["title"]) <= 30 else p["title"][:29].rstrip() + "…"
    img.alpha_composite(text_img(title, tf, WHITE, pad=0), (x, oy + 44))
    img.alpha_composite(text_img(rwf(p["price"]), font(F_BOLD, 22), GOLD_HI, pad=0), (x, oy + 74))
    img.alpha_composite(text_img(f"To {dest}, Kigali", font(F_UI, 16), MUTED, pad=0), (x, oy + 106))
    return img, pad


CARDS = [order_card(n, s) for n, _, s, _ in DELIVERIES]
STEP_FONT = font(F_SEMI, 14)
STEPS = [text_img(s, STEP_FONT, (215, 206, 186), pad=0) for s in ("Confirmed", "On the way", "Delivered")]


def delivered_toast(line):
    w, h = 430, 86
    img, pad = glass(w, h, 18)
    img.alpha_composite(check_badge(40), (pad + 20, pad + 23))
    img.alpha_composite(text_img("Delivered", font(F_BOLD, 21), WHITE, pad=0), (pad + 76, pad + 16))
    img.alpha_composite(text_img(line, font(F_UI, 16), MUTED, pad=0), (pad + 76, pad + 46))
    return img, pad


TOASTS = [delivered_toast(line) for _, _, _, line in DELIVERIES]


def name_tag():
    w, h = 330, 74
    img, pad = glass(w, h, 37)
    dot = Image.new("RGBA", (46, 46), (0, 0, 0, 0))
    g = gold_gradient(46, 46).convert("RGBA")
    m = Image.new("L", (46, 46), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 45, 45), fill=255)
    dot.paste(g, (0, 0), m)
    dot.alpha_composite(box_icon(22), (12, 12))
    img.alpha_composite(dot, (pad + 14, pad + 14))
    img.alpha_composite(text_img("Lionnel Ishimwe", font(F_BOLD, 19), WHITE, pad=0), (pad + 72, pad + 12))
    img.alpha_composite(text_img("Founder · delivering across Kigali", font(F_UI, 14), MUTED, pad=0), (pad + 72, pad + 40))
    return img, pad


TAG, TAG_PAD = name_tag()


# ------------------------------------------------------------------ frame
def draw_route(canvas, pts, upto, alpha):
    """Gold route line drawn up to fraction `upto`, with a soft glow."""
    n = max(2, int(len(pts) * upto))
    if n < 2 or alpha <= 0:
        return
    xs = [p[0] for p in pts[:n]]
    ys = [p[1] for p in pts[:n]]
    x0, y0, x1, y1 = int(min(xs)) - 12, int(min(ys)) - 12, int(max(xs)) + 12, int(max(ys)) + 12
    ss = 3
    lay = Image.new("RGBA", ((x1 - x0) * ss, (y1 - y0) * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    seg = [((x - x0) * ss, (y - y0) * ss) for x, y in pts[:n]]
    d.line(seg, fill=GOLD_HI + (255,), width=4 * ss, joint="curve")
    lay = lay.resize((x1 - x0, y1 - y0), Image.LANCZOS)
    glow = lay.filter(ImageFilter.GaussianBlur(5))
    place_tl(canvas, glow, x0, y0, alpha * 0.9)
    place_tl(canvas, lay, x0, y0, alpha)


def frame(t):
    t = t % LOOP
    canvas = BASE.copy()
    # drifting warm light and hills
    gx = W * 0.72 + 110 * math.sin(TAU * t / LOOP)
    place(canvas, BACKLIGHT, gx, 430 + 40 * math.cos(TAU * t / LOOP), 1.0, 1.0)
    place(canvas, CONTOURS, W / 2 + 14 * math.sin(TAU * t / LOOP), H / 2, 1.0, 1.0)
    for p in DUST:
        x = p["x"] + 16 * math.sin(TAU * p["sway"] * t / LOOP + p["ph"])
        y = (p["y"] + p["vy"] * t) % (H + 40) - 20
        a = p["a"] * (0.55 + 0.45 * math.sin(TAU * p["tw"] * t / LOOP + p["ph"]))
        place(canvas, p["sprite"], x, y, 1.0, a)

    # founder, breathing slowly
    s = 1.0 + 0.018 * (0.5 - 0.5 * math.cos(TAU * t / LOOP))
    fw, fh = FIG.size
    cy = FIG_TOP + fh * s / 2 - (fh * s - fh) * 0.15
    if SHOW_FOUNDER:
        place(canvas, RIM, FIG_CX, cy, s * 1.012, 0.9)
        place(canvas, FIG, FIG_CX, cy, s, 1.0)

    # which delivery is running
    k = int(t // DELIVERY)
    lt = t - k * DELIVERY
    name, dest, slug, _ = DELIVERIES[k]

    # tracking panel (always on)
    place_tl(canvas, PANEL, PANEL_X - PANEL_PAD, PANEL_Y - PANEL_PAD)
    pulse = 0.5 + 0.5 * math.sin(TAU * 10 * t / LOOP)
    place(canvas, LIVE_HALO, PANEL_X + 30, PANEL_Y + 31, 0.7 + 0.5 * pulse, 0.8 * (1 - pulse))
    place(canvas, LIVE_DOT, PANEL_X + 30, PANEL_Y + 31)
    # finished deliveries from earlier in this loop keep a green check; all clear as the loop restarts
    for j in range(k):
        x, y = map_xy(DELIVERIES[j][1])
        place(canvas, DONE_PIN, x, y, 1.0, 1 - ease_in(prog(t, LOOP - 0.8, 0.8)))
    # store pin
    sx, sy = map_xy(STORE[1])
    place(canvas, STORE_HALO, sx, sy, 0.9 + 0.2 * pulse, 0.9)
    place(canvas, STORE_PIN, sx, sy)
    place_tl(canvas, STORE_LABEL, sx - STORE_LABEL.width / 2, sy + 12)

    route = ROUTES[k]
    travel = ease_in_out(prog(lt, 1.4, 4.8))
    fade_route = 1 - ease_in(prog(lt, DELIVERY - 0.9, 0.9))
    draw_route(canvas, route, max(travel, 0.001) if lt > 1.4 else 0, 0.95 * fade_route)
    dx, dy = map_xy(dest)
    delivered = lt >= 6.2
    if delivered:
        pop = ease_out(prog(lt, 6.2, 0.35))
        place(canvas, DONE_PIN, dx, dy, 0.6 + 0.4 * pop + 0.25 * (1 - pop), 1.0)
    else:
        place(canvas, DEST_PIN, dx, dy, 1.0 + 0.25 * pulse, ease_out(prog(lt, 0.4, 0.5)))
    if 1.4 < lt < 6.4:
        i = min(len(route) - 1, int(travel * (len(route) - 1)))
        rx, ry = route[i]
        place(canvas, RIDER_HALO, rx, ry, 1.0, 0.9)
        place(canvas, RIDER, rx, ry)
        place(canvas, BOX, rx, ry - 22)

    # order card
    card, cpad = CARDS[k]
    cin = ease_out(prog(lt, 0.2, 0.7))
    cout = ease_in(prog(lt, DELIVERY - 0.6, 0.6))
    cyy = 540 + 40 * (1 - cin) - 30 * cout
    ca = cin * (1 - cout)
    place_tl(canvas, card, PANEL_X - cpad, cyy - cpad, ca)
    # three-step progress bar inside the card
    bx, by = PANEL_X + 22, cyy + 150
    seg_w = (CARD_W - 44) / 3
    for si in range(3):
        start = [0.6, 1.4, 6.2][si]
        done = prog(lt, start, 0.4 if si != 1 else 4.8)
        bar_bg = Image.new("RGBA", (int(seg_w - 10), 4), (255, 255, 255, 30))
        place_tl(canvas, bar_bg, bx + si * seg_w, by, ca)
        if done > 0:
            fill = Image.new("RGBA", (max(1, int((seg_w - 10) * done)), 4), (GREEN if si == 2 else GOLD_HI) + (255,))
            place_tl(canvas, fill, bx + si * seg_w, by, ca)
        place_tl(canvas, STEPS[si], bx + si * seg_w, by + 10, ca * (0.55 + 0.45 * (done > 0)))

    # delivered toast
    toast, tpad = TOASTS[k]
    tin = ease_out(prog(lt, 6.4, 0.6))
    tout = ease_in(prog(lt, DELIVERY - 0.6, 0.6))
    place_tl(canvas, toast, PANEL_X - tpad + 30 * (1 - tin), 760 - tpad, tin * (1 - tout))

    # founder name tag, gently floating
    if SHOW_FOUNDER:
        place_tl(canvas, TAG, 1530 - TAG_PAD, 716 - TAG_PAD + 5 * math.sin(TAU * 2 * t / LOOP))
    return canvas.convert("RGB")


# ------------------------------------------------------------------ output
def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def encoder(path, vf, crf):
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-vf", vf, "-c:v", "libx264", "-preset", "slow", "-crf", str(crf),
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if "--stills" in sys.argv:
        out = os.path.join(HERE, "stills")
        os.makedirs(out, exist_ok=True)
        for t in (3.8, 7.4):
            frame(t).save(os.path.join(out, f"full_{t:04.1f}.jpg"), quality=88)
        print("stills in", out)
        return
    n = int(round(LOOP * FPS))
    encs = [
        encoder(os.path.join(OUT_DIR, "vexa-hero-wide-1080.mp4"), "scale=1920:1080", 24),
        encoder(os.path.join(OUT_DIR, "vexa-hero-wide-720.mp4"), "scale=1280:720:flags=lanczos", 25),
        # phones: the delivery panel and cards only
        encoder(os.path.join(OUT_DIR, "vexa-hero-mobile.mp4"), "crop=720:780:1200:120,scale=648:702:flags=lanczos", 25),
    ]
    for f in range(n):
        t = f / FPS
        img = frame(t)
        raw = img.tobytes()
        for e in encs:
            e.stdin.write(raw)
        if abs(t - 7.4) < 0.5 / FPS:
            img.save(os.path.join(OUT_DIR, "vexa-hero-wide-poster.jpg"), quality=84)
            img.crop((1200, 120, 1920, 900)).resize((648, 702), Image.LANCZOS).save(
                os.path.join(OUT_DIR, "vexa-hero-mobile-poster.jpg"), quality=84)
        if f % 150 == 0:
            print(f"frame {f}/{n}", flush=True)
    for e in encs:
        e.stdin.close()
        e.wait()
    print("done", LOOP, "s")


if __name__ == "__main__":
    main()
