"""
VEXA hero video renderer.

Draws every frame with Pillow + numpy from the live catalog and brand assets,
then pipes them to ffmpeg (the copy bundled with the imageio-ffmpeg package).

    python scripts/hero-video/render.py            # full render
    python scripts/hero-video/render.py --stills   # a few preview frames only

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

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
OUT_DIR = os.path.join(SRC, "assets", "video")
FONTS = "C:/Windows/Fonts/"

S = 1080          # square frame, matches the hero art slot
FPS = 30
LOOP = 48.4       # every background motion repeats exactly over this, so the video loops seamlessly
TAU = 2 * math.pi
random.seed(7)

INK = (13, 12, 10)
GOLD_HI = (243, 220, 155)
GOLD = (201, 161, 74)
GOLD_LO = (143, 109, 43)
MUTED = (176, 167, 150)
WHITE = (255, 255, 255)

site = {"phone": "+250 785 576 541"}
catalog = json.load(open(os.path.join(SRC, "_data", "catalog.json"), encoding="utf8"))
products = {p["slug"]: p for p in catalog["products"]}
depts = {c["slug"]: c for c in catalog["categories"]}


def font(name, size):
    return ImageFont.truetype(FONTS + name, size)


F_DISPLAY = "PERTIBD.TTF"   # Perpetua Titling Bold, closest local match to the site's Cinzel
F_UI = "segoeui.ttf"
F_UI_SEMI = "seguisb.ttf" if os.path.exists(FONTS + "seguisb.ttf") else "segoeuib.ttf"
F_UI_BOLD = "segoeuib.ttf"


# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_in(x):
    return x ** 3


# ---------------------------------------------------------------- drawing helpers
def with_alpha(img, alpha):
    if alpha >= 0.999:
        return img
    out = img.copy()
    a = out.getchannel("A").point(lambda v: int(v * alpha))
    out.putalpha(a)
    return out


def place(canvas, img, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    """Composite img centred at (cx, cy), clipped to the canvas."""
    if alpha <= 0.003:
        return
    if abs(scale - 1) > 0.002:
        w, h = img.size
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    if abs(rot) > 0.05:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    img = with_alpha(img, alpha)
    w, h = img.size
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(w, S - x), min(h, S - y)
    if ex <= sx or ey <= sy:
        return
    canvas.alpha_composite(img, (x + sx, y + sy), (sx, sy, ex, ey))


def place_tl(canvas, img, x, y, alpha=1.0):
    w, h = img.size
    place(canvas, img, x + w / 2, y + h / 2, 1.0, alpha)


def gold_gradient(w, h):
    y = np.linspace(0, 1, h)[:, None]
    stops = [(0.0, GOLD_HI), (0.55, GOLD), (1.0, GOLD_LO)]
    rgb = np.zeros((h, 1, 3))
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        m = (y >= p0) & (y <= p1)
        k = np.where(m, (y - p0) / (p1 - p0), 0)
        for i in range(3):
            rgb[..., i] += np.where(m, c0[i] + (c1[i] - c0[i]) * k, 0)[:, :1]
    rgb = np.repeat(rgb, w, axis=1)
    return Image.fromarray(rgb.astype(np.uint8), "RGB")


def text_img(text, fnt, fill=WHITE, tracking=0, gradient=False, pad=8):
    """Render a single line of text to a tight RGBA image."""
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    if tracking:
        widths = [probe.textlength(ch, font=fnt) for ch in text]
        total = sum(widths) + tracking * (len(text) - 1)
    else:
        total = probe.textlength(text, font=fnt)
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
    color = gold_gradient(w, h) if gradient else Image.new("RGB", (w, h), fill)
    out = color.convert("RGBA")
    out.putalpha(mask)
    return out


def glow(img, radius=18, strength=0.55):
    """Soft halo behind bright text or artwork."""
    halo = img.filter(ImageFilter.GaussianBlur(radius))
    halo = with_alpha(halo, strength)
    w, h = img.size
    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    base.alpha_composite(halo)
    base.alpha_composite(img)
    return base


def padded(img, pad):
    w, h = img.size
    out = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    out.alpha_composite(img, (pad, pad))
    return out


def wrap(text, fnt, max_w):
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if probe.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def rwf(n):
    return f"RWF {n:,}" if n else "Price on request"


# ---------------------------------------------------------------- background
def radial(size, cx, cy, r, color, power=1.6):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r
    k = np.clip(1 - d, 0, 1) ** power
    arr = np.zeros((size, size, 4), np.uint8)
    arr[..., 0], arr[..., 1], arr[..., 2] = color
    arr[..., 3] = (k * 255).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


BASE = Image.new("RGBA", (S, S), INK + (255,))
BASE.alpha_composite(radial(S, S * 0.5, S * 0.42, S * 0.85, (44, 36, 20), 1.8))
VIGNETTE = radial(S, S / 2, S / 2, S * 0.78, (0, 0, 0), 1.0)
vig = np.array(VIGNETTE)
vig[..., 3] = 255 - vig[..., 3]
vig[..., 3] = (vig[..., 3].astype(np.float32) * 0.75).astype(np.uint8)
VIGNETTE = Image.fromarray(vig, "RGBA")
ROAM_GLOW = radial(900, 450, 450, 450, (201, 161, 74), 2.4)
ROAM_GLOW = with_alpha(ROAM_GLOW, 0.22)


def dot_sprite(r, soft):
    size = int(r * 2 + soft * 4 + 4)
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    d.ellipse((c - r, c - r, c + r, c + r), fill=GOLD_HI + (255,))
    if soft:
        im = im.filter(ImageFilter.GaussianBlur(soft))
    return im


class Dust:
    def __init__(self, n=80):
        self.parts = []
        for _ in range(n):
            depth = random.random()
            r = 1.2 + depth * 5.5
            laps = 1 if depth < 0.45 else (2 if depth < 0.85 else 3)
            self.parts.append({
                "x": random.uniform(0, S), "y": random.uniform(0, S),
                "vy": -laps * (S + 40) / LOOP, "sway": random.choice([1, 2]),
                "sprite": dot_sprite(r, 1 + (1 - abs(depth - 0.55)) * 3.5 if depth > 0.8 else 0.8 + depth),
                "a": 0.18 + depth * 0.55, "tw": random.choice([3, 4, 5, 6, 7]), "ph": random.uniform(0, 6.28),
            })

    def draw(self, canvas, t, strength=1.0):
        for p in self.parts:
            x = (p["x"] + 16 * math.sin(TAU * p["sway"] * t / LOOP + p["ph"])) % (S + 40) - 20
            y = (p["y"] + p["vy"] * t) % (S + 40) - 20
            a = p["a"] * (0.55 + 0.45 * math.sin(TAU * p["tw"] * t / LOOP + p["ph"])) * strength
            place(canvas, p["sprite"], x, y, 1.0, a)


DUST = Dust()


def background(t, dust=1.0):
    canvas = BASE.copy()
    gx = S * 0.5 + S * 0.28 * math.sin(TAU * 2 * t / LOOP)
    gy = S * 0.45 + S * 0.18 * math.cos(TAU * 1 * t / LOOP)
    place(canvas, ROAM_GLOW, gx, gy, 1.0, 0.9)
    DUST.draw(canvas, t, dust)
    canvas.alpha_composite(VIGNETTE)
    return canvas


def finish(canvas):
    return canvas


# ---------------------------------------------------------------- logo
def load_logo(size):
    im = Image.open(os.path.join(SRC, "assets", "brand", "vexa-logo.jpg")).convert("RGB").resize((size, size), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32)
    lum = arr.max(axis=2)
    alpha = np.clip((lum - 8) / 70, 0, 1) ** 1.2
    # feather the square edge so no hard frame shows against the background
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    edge = np.minimum.reduce([xx, yy, 1 - xx, 1 - yy])
    alpha *= np.clip(edge / 0.12, 0, 1)
    rgba = np.dstack([arr, alpha * 255]).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


LOGO = load_logo(880)
LOGO_SMALL = load_logo(560)


def sweep(img, x):
    """Diagonal light band across the bright parts of the artwork; x in 0..1."""
    arr = np.asarray(img).astype(np.float32)
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    pos = (xx + yy * 0.45) / (w * 1.45)
    band = np.exp(-((pos - (x * 1.5 - 0.25)) / 0.05) ** 2)
    lum = arr[..., :3].max(axis=2) / 255
    boost = band * np.clip(lum - 0.35, 0, 1) * 1.9
    arr[..., 0] += boost * 255
    arr[..., 1] += boost * 235
    arr[..., 2] += boost * 175
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- product cards
CARD_W, CARD_H = 350, 500


def rounded_mask(w, h, r, ss=2):
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def product_card(slug, hero=False):
    p = products[slug]
    ss = 2
    W, H = CARD_W * ss, CARD_H * ss
    card = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    d = ImageDraw.Draw(card)
    # photo area
    photo = Image.open(os.path.join(SRC, p["img"].lstrip("/").replace("/", os.sep))).convert("RGBA")
    box_w, box_h = W - 36 * ss, 300 * ss
    photo.thumbnail((box_w, box_h), Image.LANCZOS)
    pw, ph = photo.size
    card.alpha_composite(photo, ((W - pw) // 2, 18 * ss + (box_h - ph) // 2))
    d.line((18 * ss, 334 * ss, W - 18 * ss, 334 * ss), fill=(231, 224, 208), width=ss)
    # text
    y = 346 * ss
    if p["brand"]:
        brand = text_img(p["brand"].upper(), font(F_UI_SEMI, 14 * ss), (120, 112, 98), tracking=2 * ss, pad=0)
        card.alpha_composite(brand, (20 * ss, y))
    y += 24 * ss
    tf = font(F_UI_SEMI, 20 * ss)
    for line in wrap(p["title"], tf, W - 40 * ss)[:2]:
        d.text((20 * ss, y), line, font=tf, fill=(27, 24, 18))
        y += 27 * ss
    pf = font(F_UI_BOLD, 25 * ss)
    d.text((20 * ss, (CARD_H - 54) * ss), rwf(p["price"]), font=pf, fill=(13, 12, 10))
    # add-to-cart dot, echoing the site's card
    cx, cy, r = W - 42 * ss, (CARD_H - 38) * ss, 21 * ss
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK)
    d.line((cx - 7 * ss, cy, cx + 7 * ss, cy), fill=GOLD_HI, width=3 * ss)
    d.line((cx, cy - 7 * ss, cx, cy + 7 * ss), fill=GOLD_HI, width=3 * ss)
    if hero:
        badge = text_img("BEST SELLER", font(F_UI_BOLD, 12 * ss), GOLD_HI, tracking=2 * ss, pad=10 * ss)
        bw, bh = badge.size
        pill = Image.new("RGBA", (bw, bh - 4 * ss), (0, 0, 0, 0))
        ImageDraw.Draw(pill).rounded_rectangle((0, 0, bw - 1, bh - 4 * ss - 1), (bh - 4 * ss) // 2, fill=INK + (255,))
        pill.alpha_composite(badge, (0, -2 * ss))
        card.alpha_composite(pill, (16 * ss, 16 * ss))
    card = card.resize((CARD_W, CARD_H), Image.LANCZOS)
    card.putalpha(rounded_mask(CARD_W, CARD_H, 20))
    if hero:
        ring = Image.new("RGBA", (CARD_W * ss, CARD_H * ss), (0, 0, 0, 0))
        ImageDraw.Draw(ring).rounded_rectangle((1, 1, CARD_W * ss - 2, CARD_H * ss - 2), 20 * ss, outline=GOLD + (255,), width=3 * ss)
        card.alpha_composite(ring.resize((CARD_W, CARD_H), Image.LANCZOS))
    # drop shadow
    pad = 60
    out = Image.new("RGBA", (CARD_W + pad * 2, CARD_H + pad * 2), (0, 0, 0, 0))
    shadow = Image.new("RGBA", out.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((pad + 8, pad + 26, pad + CARD_W - 8, pad + CARD_H + 16), 24, fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(22))
    out.alpha_composite(shadow)
    out.alpha_composite(card, (pad, pad))
    return out


# ---------------------------------------------------------------- icons (drawn at 4x, gold badge)
def icon_badge(kind, size=92):
    ss = 4
    W = size * ss
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    grad = gold_gradient(W, W).convert("RGBA")
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, W - 1, W - 1), fill=255)
    im.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(im)
    c = W / 2
    lw = int(4.2 * ss)
    col = INK + (255,)
    u = W / 92  # design units on a 92px badge

    def R(x0, y0, x1, y1, r=0):
        d.rounded_rectangle((c + x0 * u, c + y0 * u, c + x1 * u, c + y1 * u), int(r * u), outline=col, width=lw)

    def O(x, y, r):
        d.ellipse((c + (x - r) * u, c + (y - r) * u, c + (x + r) * u, c + (y + r) * u), outline=col, width=lw)

    def L(*pts):
        d.line([(c + x * u, c + y * u) for x, y in pts], fill=col, width=lw, joint="curve")

    if kind == "truck":
        R(-24, -14, 6, 10, 2)
        L((6, -6), (16, -6), (24, 3), (24, 10), (6, 10))
        O(-13, 13, 5.5)
        O(14, 13, 5.5)
    elif kind == "card":
        R(-24, -16, 24, 16, 4)
        L((-24, -6), (24, -6))
        L((-15, 7), (-4, 7))
    elif kind == "gear":
        O(0, 0, 9)
        for k in range(8):
            a = k * math.pi / 4
            L((math.cos(a) * 14, math.sin(a) * 14), (math.cos(a) * 21, math.sin(a) * 21))
        O(0, 0, 15)
    elif kind == "chat":
        R(-23, -18, 23, 12, 10)
        L((-10, 12), (-16, 22), (-2, 12))
        for x in (-9, 0, 9):
            d.ellipse((c + (x - 2.4) * u, c + (-3 - 2.4) * u, c + (x + 2.4) * u, c + (-3 + 2.4) * u), fill=col)
    return im.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- scenes
SHOWCASE = [
    ("cctv", ["kit-of-4-cameras-black-and-white", "4mp-analog-colorvu-hikvision", "wi-fi-ezviz-ec-dual-2k-3mp"]),
    ("computers", ["hp-omnibook-ultra-5-new", "hp-elitebook-g5", "hp-pavilion-x360-14inch-2-in-1-laptop"]),
    ("networking", ["tp-link-300-mbps-wi-fi-router", "hikvision-16-port-smart-managed-switch", "d-link-des-1005c-switch"]),
    ("air-conditioning", ["bosch-wall-mount-split-12-000-btu-inverter", "lg-cassette-24-000-btu-4-way", "bosch-vrf-outdoor-18-kw"]),
    ("fire-safety", ["photo-thermo-addressable-smoke-detector", "addressable-sounder-and-strobe", "emergency-exit-sign-with-light"]),
    ("accessories", ["logitech-wireless-mouse", "adjustable-laptop-stand", "type-c-laptop-charger"]),
]
for dslug, slugs in SHOWCASE:
    for s in slugs:
        if s not in products or not products[s]["img"]:
            sys.exit(f"missing product photo: {s}")

T_INTRO = 6.0
T_DEPT = 4.6
T_SERV = 8.2
T_OUTRO = 6.6
T_SHOW0 = T_INTRO
T_SERV0 = T_SHOW0 + T_DEPT * len(SHOWCASE)
T_OUTRO0 = T_SERV0 + T_SERV
DURATION = T_OUTRO0 + T_OUTRO
assert abs(DURATION - LOOP) < 1e-6, DURATION

# pre-rendered layers
INTRO_EYEBROW = text_img("WELCOME TO", font(F_UI_SEMI, 22), GOLD, tracking=9)
INTRO_LINE = glow(padded(text_img("GENUINE TECH, DELIVERED & INSTALLED", font(F_DISPLAY, 34), gradient=True, tracking=3), 24), 10, 0.45)

DEPT_LAYERS = []
for i, (dslug, slugs) in enumerate(SHOWCASE):
    dept = depts[dslug]
    priced = [p["price"] for p in catalog["products"] if p["category"] == dslug and p["price"]]
    title_font = font(F_DISPLAY, 76 if len(dept["name"]) < 17 else 68)
    DEPT_LAYERS.append({
        "eyebrow": text_img(f"SHOP  ·  {i + 1:02d} / {len(SHOWCASE):02d}", font(F_UI_SEMI, 21), GOLD, tracking=7),
        "title": glow(padded(text_img(dept["name"].upper(), title_font, gradient=True, tracking=2), 24), 12, 0.4),
        "tagline": [text_img(line, font(F_UI, 31), MUTED) for line in wrap(dept["tagline"], font(F_UI, 31), 900)],
        "foot": text_img(f"{dept['count']} products   ·   from {rwf(min(priced))}", font(F_UI_SEMI, 26), (225, 216, 196)),
        "cards": [product_card(slugs[0], hero=True), product_card(slugs[1]), product_card(slugs[2])],
    })

SPOT = with_alpha(radial(760, 380, 380, 380, (236, 208, 138), 2.2), 0.28)

SERV_EYEBROW = text_img("WHY SHOP WITH VEXA", font(F_UI_SEMI, 20), GOLD, tracking=8)
SERV_TITLE = [glow(padded(text_img(t, font(F_DISPLAY, 60), gradient=True, tracking=2), 24), 12, 0.4)
              for t in ("MORE THAN A STORE.", "WE DELIVER & INSTALL.")]
SERV_ROWS = []
for kind, head, sub in [
    ("truck", "Delivery across Rwanda", "Kigali and upcountry, fee confirmed before dispatch"),
    ("card", "Pay on delivery", "MTN MoMo, Airtel Money, bank transfer or cash"),
    ("gear", "Professional installation", "Cameras, Wi-Fi, air conditioning, fire alarms"),
    ("chat", "Help every day", "Call or WhatsApp us, 24 hours"),
]:
    SERV_ROWS.append((icon_badge(kind), text_img(head, font(F_UI_BOLD, 36), WHITE), text_img(sub, font(F_UI, 24), MUTED)))

OUT_LINE = glow(padded(text_img("SHOP GENUINE TECH.", font(F_DISPLAY, 58), gradient=True, tracking=3), 24), 12, 0.45)
OUT_SUB = text_img("Order online   ·   Pay on delivery   ·   Installed for you", font(F_UI, 25), (215, 206, 186))


def phone_pill():
    t = text_img(f"Call or WhatsApp  {site['phone']}", font(F_UI_SEMI, 26), INK, pad=0)
    tw, th = t.size
    w, h = tw + 72, 64
    ss = 2
    pill = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    m = Image.new("L", (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), h * ss // 2, fill=255)
    pill.paste(gold_gradient(w * ss, h * ss).convert("RGBA"), (0, 0), m)
    pill = pill.resize((w, h), Image.LANCZOS)
    pill.alpha_composite(t, (36, (h - th) // 2 - 3))
    return pill


OUT_PILL = phone_pill()


def slide_alpha(t, t_in, t_out, d_in=0.6, d_out=0.45):
    a = ease_out(prog(t, t_in, d_in))
    a *= 1 - ease_in(prog(t, t_out - d_out, d_out))
    return a


def scene_intro(canvas, t):
    a = ease_out(prog(t, 0.35, 2.0))
    exit_k = ease_in(prog(t, T_INTRO - 0.8, 0.8))
    scale = 1.10 - 0.10 * ease_out(prog(t, 0.35, 3.2)) - 0.02 * prog(t, 3.5, 2.5) + 0.22 * exit_k
    logo = LOGO
    sx = prog(t, 2.0, 1.5)
    if 0 < sx < 1:
        logo = sweep(LOGO, ease_in_out(sx))
    place(canvas, logo, S / 2, S * 0.46, scale, a * (1 - exit_k))
    ta = slide_alpha(t, 3.0, T_INTRO - 0.2)
    ty = 18 * (1 - ease_out(prog(t, 3.0, 0.8)))
    place(canvas, INTRO_EYEBROW, S / 2, 888 + ty, 1, ta)
    tb = slide_alpha(t, 3.35, T_INTRO - 0.2)
    ty = 18 * (1 - ease_out(prog(t, 3.35, 0.8)))
    place(canvas, INTRO_LINE, S / 2, 944 + ty, 1, tb)


def scene_dept(canvas, t, i):
    L = DEPT_LAYERS[i]
    T = T_DEPT
    out_k = ease_in(prog(t, T - 0.5, 0.5))
    shift = -150 * out_k

    # text block
    for k, (layer, y, delay) in enumerate([(L["eyebrow"], 84, 0.0), (L["title"], 116, 0.08)]):
        a = slide_alpha(t, delay, T, 0.55, 0.45)
        dy = 24 * (1 - ease_out(prog(t, delay, 0.6)))
        place_tl(canvas, layer, 64 - (24 if k else 0) + shift, y + dy - (24 if k else 0), a)
    for j, line in enumerate(L["tagline"]):
        a = slide_alpha(t, 0.18 + j * 0.06, T, 0.55, 0.45)
        dy = 24 * (1 - ease_out(prog(t, 0.18, 0.6)))
        place_tl(canvas, line, 64 + shift, 212 + j * 42 + dy, a)

    # spotlight + cards
    cy = 660
    place(canvas, SPOT, S / 2 + shift, cy, 1.0 + 0.04 * math.sin(t * 1.4), slide_alpha(t, 0.0, T, 0.8, 0.5))
    push = 1.0 + 0.035 * prog(t, 0, T)
    float_a = math.sin(t * 2.1)
    fan = ease_out(prog(t, 0.35, 0.8))
    rise = ease_out(prog(t, 0.0, 0.75))
    side_a = slide_alpha(t, 0.35, T, 0.6, 0.5)
    for side, sgn, ph in ((1, -1, 1.3), (2, 1, 2.6)):
        x = S / 2 + sgn * 322 * fan + shift * 1.2
        y = cy + 34 + 10 * math.sin(t * 2.1 + ph)
        place(canvas, L["cards"][side], x, y, 0.84 * push, side_a, rot=-sgn * 5 * fan)
    y = cy + 140 * (1 - rise) + 9 * float_a
    place(canvas, L["cards"][0], S / 2 + shift * 1.4, y, 1.0 * push, slide_alpha(t, 0.0, T, 0.6, 0.5))

    # footer
    a = slide_alpha(t, 0.7, T, 0.6, 0.45)
    fw = L["foot"].size[0]
    place(canvas, L["foot"], S / 2 + shift, 1016, 1, a)
    line = Image.new("RGBA", (int(fw * 0.5 * ease_out(prog(t, 0.7, 0.9))) + 1, 2), GOLD + (200,))
    place(canvas, line, S / 2 + shift, 984, 1, a)


def scene_services(canvas, t):
    T = T_SERV
    a = slide_alpha(t, 0.0, T, 0.6, 0.5)
    dy = 24 * (1 - ease_out(prog(t, 0, 0.6)))
    place_tl(canvas, SERV_EYEBROW, 72, 108 + dy, a)
    for j, layer in enumerate(SERV_TITLE):
        a = slide_alpha(t, 0.12 + j * 0.12, T, 0.6, 0.5)
        dy = 24 * (1 - ease_out(prog(t, 0.12 + j * 0.12, 0.6)))
        place_tl(canvas, layer, 48, 136 + j * 76 + dy, a)
    for k, (badge, head, sub) in enumerate(SERV_ROWS):
        start = 0.9 + k * 0.45
        a = slide_alpha(t, start, T, 0.6, 0.5)
        dx = -60 * (1 - ease_out(prog(t, start, 0.7)))
        y = 430 + k * 138
        pop = 0.6 + 0.4 * ease_out(prog(t, start, 0.5))
        place(canvas, badge, 118 + dx, y + 46, pop, a)
        place_tl(canvas, head, 190 + dx, y + 2, a)
        place_tl(canvas, sub, 192 + dx, y + 52, a)
        if k < 3:
            sep = Image.new("RGBA", (820, 1), (236, 208, 138, 40))
            place_tl(canvas, sep, 190 + dx, y + 116, a)


def scene_outro(canvas, t):
    T = T_OUTRO
    fade = 1 - ease_in_out(prog(t, T - 1.3, 1.2))
    a = ease_out(prog(t, 0.0, 1.2)) * fade
    logo = LOGO_SMALL
    sx = prog(t, 1.4, 1.4)
    if 0 < sx < 1:
        logo = sweep(LOGO_SMALL, ease_in_out(sx))
    place(canvas, logo, S / 2, 360, 0.92 + 0.08 * ease_out(prog(t, 0, 2.0)), a)
    for layer, y, delay in ((OUT_LINE, 716, 0.6), (OUT_SUB, 796, 0.8), (OUT_PILL, 884, 1.0)):
        k = ease_out(prog(t, delay, 0.7))
        place(canvas, layer, S / 2, y + 22 * (1 - k), 1, k * fade)


def frame(t):
    # dust dims slightly behind the product scenes so cards stay the focus
    in_show = T_SHOW0 <= t < T_SERV0
    canvas = background(t, 0.65 if in_show else 1.0)
    if t < T_INTRO:
        scene_intro(canvas, t)
    elif t < T_SERV0:
        i = int((t - T_SHOW0) // T_DEPT)
        scene_dept(canvas, t - T_SHOW0 - i * T_DEPT, i)
    elif t < T_OUTRO0:
        scene_services(canvas, t - T_SERV0)
    else:
        scene_outro(canvas, t - T_OUTRO0)
    return finish(canvas).convert("RGB")


# ---------------------------------------------------------------- output
def ffmpeg_exe():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(frames_iter, path, size, crf):
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{S}x{S}", "-r", str(FPS), "-i", "-",
           "-vf", f"scale={size}:{size}:flags=lanczos",
           "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if "--stills" in sys.argv:
        stills = os.path.join(os.path.dirname(__file__), "stills")
        os.makedirs(stills, exist_ok=True)
        for t in [1.2, 3.0, 4.6, T_SHOW0 + 2.0, T_SHOW0 + T_DEPT * 3 + 2.2, T_SHOW0 + T_DEPT * 1 + 4.3, T_SERV0 + 3.5, T_OUTRO0 + 3.0]:
            frame(t).save(os.path.join(stills, f"t{t:05.1f}.jpg"), quality=88)
        print("stills in", stills, "duration", round(DURATION, 1))
        return

    n = int(round(DURATION * FPS))
    big = encode(None, os.path.join(OUT_DIR, "vexa-hero-1080.mp4"), 1080, 23)
    small = encode(None, os.path.join(OUT_DIR, "vexa-hero-720.mp4"), 720, 25)
    for f in range(n):
        t = f / FPS
        img = frame(t)
        raw = img.tobytes()
        big.stdin.write(raw)
        small.stdin.write(raw)
        if abs(t - 3.3) < 0.5 / FPS:
            img.save(os.path.join(OUT_DIR, "vexa-hero-poster.jpg"), quality=86)
        if f % 150 == 0:
            print(f"frame {f}/{n}", flush=True)
    for p in (big, small):
        p.stdin.close()
        p.wait()
    print("done", round(DURATION, 1), "s")


if __name__ == "__main__":
    main()
