"""
VEXA hero video: an illustrated doorstep delivery in Kigali.

A courier (styled after the founder: short hair, black glasses, blue striped
shirt, gold watch) walks from his moto to a client's door, knocks, hands over
a VEXA box, waves and walks back. Flat illustration, drawn frame by frame.

    python scripts/hero-video/render_door.py            # full render
    python scripts/hero-video/render_door.py --stills

The left side stays dark for the hero headline. Everything important sits in
y 190..810 because wide screens crop the top and bottom of the video.
Outputs src/assets/video/vexa-hero-door-*.
"""
import math
import os
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(ROOT, "src", "assets", "video")
FONTS = "C:/Windows/Fonts/"

W, H = 1920, 1080
FPS = 30
LOOP = 16.0
TAU = 2 * math.pi
GROUND = 790
random.seed(5)

INK = (13, 12, 10)
GOLD_HI = (243, 220, 155)
GOLD = (201, 161, 74)
GOLD_LO = (143, 109, 43)
MUTED = (176, 167, 150)
WHITE = (255, 255, 255)
GREEN = (47, 160, 94)


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


def ease_io(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def lerp(a, b, k):
    return a + (b - a) * k


def lerp2(p, q, k):
    return (lerp(p[0], q[0], k), lerp(p[1], q[1], k))


def with_alpha(img, a):
    if a >= 0.999:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * a)))
    return out


def place(canvas, img, cx, cy, alpha=1.0, scale=1.0):
    if alpha <= 0.003:
        return
    if abs(scale - 1) > 0.002:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
    img = with_alpha(img, alpha)
    w, h = img.size
    x, y = int(round(cx - w / 2)), int(round(cy - h / 2))
    sx, sy = max(0, -x), max(0, -y)
    ex, ey = min(w, W - x), min(h, H - y)
    if ex > sx and ey > sy:
        canvas.alpha_composite(img, (x + sx, y + sy), (sx, sy, ex, ey))


def place_tl(canvas, img, x, y, alpha=1.0):
    place(canvas, img, x + img.width / 2, y + img.height / 2, alpha)


def radial(w, h, cx, cy, r, color, power=1.6, alpha=1.0):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    k = np.clip(1 - np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / r, 0, 1) ** power
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = (k * 255 * alpha).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def text_img(text, fnt, fill=WHITE, tracking=0, pad=4):
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    widths = [probe.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    asc, desc = fnt.getmetrics()
    im = Image.new("RGBA", (int(total + pad * 2), asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for ch, cw in zip(text, widths):
        d.text((x, pad), ch, font=fnt, fill=fill)
        x += cw + tracking
    return im


def rounded(w, h, r, fill, outline=None, width=1, ss=3):
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=fill,
                                         outline=outline, width=width * ss if outline else 0)
    return im.resize((w, h), Image.LANCZOS)


def glass(w, h, r=18):
    pad = 36
    out = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    out.alpha_composite(rounded(w, h, r, (22, 20, 15, 235), outline=(236, 208, 138, 70)), (pad, pad))
    return out, pad


def check_badge(d):
    ss = 4
    im = Image.new("RGBA", (d * ss, d * ss), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.ellipse((0, 0, d * ss - 1, d * ss - 1), fill=GREEN + (255,))
    u = d * ss / 24
    dr.line([(6.5 * u, 12.5 * u), (10.5 * u, 16.5 * u), (17.5 * u, 8.5 * u)], fill=WHITE, width=int(2.6 * u), joint="curve")
    return im.resize((d, d), Image.LANCZOS)


# ------------------------------------------------------------------ static scene
def build_scene():
    ss = 2
    im = Image.new("RGBA", (W * ss, H * ss), INK + (255,))
    d = ImageDraw.Draw(im)

    def P(x, y):
        return (x * ss, y * ss)

    # Kigali hills, far to near, dotted with city lights
    rng = random.Random(3)
    layers = [(560, (30, 26, 19), 26, 0.004, 1.3), (610, (24, 21, 15), 34, 0.0055, 2.4), (665, (19, 17, 13), 28, 0.007, 0.4)]
    for base, col, amp, freq, ph in layers:
        pts = [P(0, H)]
        for x in range(0, W + 20, 10):
            y = base - amp * math.sin(x * freq + ph) - amp * 0.6 * math.sin(x * freq * 2.3 + ph * 2)
            pts.append(P(x, y))
        pts.append(P(W + 20, H))
        d.polygon(pts, fill=col + (255,))
        for _ in range(55):
            x = rng.uniform(760, W)
            ytop = base - amp * math.sin(x * freq + ph) - amp * 0.6 * math.sin(x * freq * 2.3 + ph * 2)
            y = rng.uniform(ytop + 6, ytop + 80)
            r = rng.uniform(1.0, 2.3)
            c = GOLD_HI if rng.random() < 0.7 else (255, 238, 205)
            d.ellipse((P(x - r, y - r), P(x + r, y + r)), fill=c + (int(rng.uniform(90, 220)),))

    # the Convention Centre dome on the far hill
    cx, cy, rw, rh = 1215, 548, 58, 50
    d.pieslice((P(cx - rw, cy - rh), P(cx + rw, cy + rh)), 180, 360, fill=(40, 34, 24, 255))
    for k in range(1, 6):
        f = k / 6
        d.arc((P(cx - rw * f, cy - rh), P(cx + rw * f, cy + rh)), 180, 360, fill=GOLD + (200,), width=2 * ss)
    for k in range(1, 4):
        y = cy - rh * k / 4
        half = rw * math.sqrt(1 - (k / 4) ** 2)
        d.line((P(cx - half, y), P(cx + half, y)), fill=GOLD + (150,), width=ss)
    d.line((P(cx - rw - 14, cy), P(cx + rw + 14, cy)), fill=GOLD + (170,), width=2 * ss)

    # street
    d.rectangle((P(0, GROUND), P(W, H)), fill=(17, 15, 12, 255))
    d.rectangle((P(0, GROUND), P(W, GROUND + 5)), fill=(58, 48, 30, 255))
    d.line((P(0, GROUND + 60), P(W, GROUND + 60)), fill=(34, 30, 22, 255), width=2 * ss)
    for x in range(20, W, 90):
        d.line((P(x, GROUND + 5), P(x - 40, GROUND + 60)), fill=(28, 25, 19, 255), width=ss)

    # house front
    d.rectangle((P(1560, 300), P(W, GROUND)), fill=(46, 38, 27, 255))
    d.rectangle((P(1545, 288), P(W, 304)), fill=(64, 52, 34, 255))
    d.line((P(1545, 288), P(W, 288)), fill=GOLD + (230,), width=2 * ss)
    # window with warm light
    d.rectangle((P(1830, 440), P(W, 600)), fill=(72, 56, 32, 255))
    d.rectangle((P(1842, 452), P(W, 588)), fill=(236, 190, 110, 255))
    d.line((P(1842, 520), P(W, 520)), fill=(72, 56, 32, 255), width=4 * ss)
    # door frame and threshold
    d.rectangle((P(1590, 410), P(1800, GROUND)), fill=(30, 25, 18, 255))
    d.rectangle((P(1580, GROUND - 6), P(1810, GROUND + 4)), fill=(80, 66, 44, 255))
    # house number plaque
    d.rounded_rectangle((P(1818, 640), P(1900, 676)), 6 * ss, fill=(22, 20, 15, 255), outline=GOLD + (255,), width=ss)
    plate = text_img("KG 548 St", font(F_SEMI, 15 * ss), GOLD_HI, pad=0)
    im.alpha_composite(plate, (int(1859 * ss - plate.width / 2), int(649 * ss)))
    # potted plant
    d.polygon([P(1848, GROUND), P(1900, GROUND), P(1908, GROUND - 52), P(1840, GROUND - 52)], fill=(92, 60, 36, 255))
    for a in (-0.9, -0.5, -0.15, 0.2, 0.55, 0.95):
        x0, y0 = 1874, GROUND - 52
        d.line((P(x0, y0), P(x0 + math.sin(a) * 60, y0 - math.cos(a) * 70)), fill=(46, 86, 50, 255), width=9 * ss)

    # parked moto with a VEXA top box
    mx = 1150
    for wx in (mx, mx + 132):
        d.ellipse((P(wx - 34, GROUND - 68), P(wx + 34, GROUND)), fill=(12, 11, 9, 255), outline=(70, 60, 44, 255), width=5 * ss)
        d.ellipse((P(wx - 9, GROUND - 43), P(wx + 9, GROUND - 25)), fill=(90, 78, 58, 255))
    d.polygon([P(mx + 10, GROUND - 60), P(mx + 120, GROUND - 60), P(mx + 132, GROUND - 34), P(mx + 30, GROUND - 30)], fill=(26, 24, 20, 255))
    d.polygon([P(mx + 30, GROUND - 90), P(mx + 110, GROUND - 92), P(mx + 118, GROUND - 60), P(mx + 22, GROUND - 60)], fill=(120, 26, 30, 255))
    d.rounded_rectangle((P(mx + 18, GROUND - 104), P(mx + 88, GROUND - 90)), 7 * ss, fill=(20, 18, 15, 255))
    d.line((P(mx + 120, GROUND - 92), P(mx + 140, GROUND - 130)), fill=(60, 56, 50, 255), width=6 * ss)
    d.line((P(mx + 128, GROUND - 132), P(mx + 158, GROUND - 126)), fill=(60, 56, 50, 255), width=6 * ss)
    d.rounded_rectangle((P(mx - 18, GROUND - 162), P(mx + 44, GROUND - 104)), 6 * ss, fill=(14, 13, 11, 255), outline=GOLD + (255,), width=2 * ss)
    lbl = text_img("VEXA", font(F_DISPLAY, 17 * ss), GOLD_HI, pad=0)
    im.alpha_composite(lbl, (int((mx + 13) * ss - lbl.width / 2), int((GROUND - 142) * ss)))

    return im.resize((W, H), Image.LANCZOS)


SCENE = build_scene()
def flat_polygon(w, h, pts, fill):
    """Solid, flat-coloured shape (no gradients), drawn at 2x for clean edges."""
    ss = 2
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(x * ss, y * ss) for x, y in pts], fill=fill)
    return im.resize((w, h), Image.LANCZOS)


# lamp light falls as one flat cone; the open door throws a flat patch on the street
LAMP_CONE = flat_polygon(300, 390, [(128, 0), (172, 0), (300, 388), (0, 388)], (243, 200, 120, 30))
DOOR_LIGHT = flat_polygon(360, 110, [(80, 0), (270, 0), (360, 108), (0, 108)], (243, 196, 110, 80))


def fireflies():
    parts = []
    for _ in range(40):
        parts.append({"x": random.uniform(900, W), "y": random.uniform(200, 760), "r": random.uniform(1.2, 2.8),
                      "sway": random.choice([1, 2]), "tw": random.choice([2, 3, 4, 5]), "ph": random.uniform(0, TAU),
                      "rise": random.choice([1, 2])})
    return parts


FLIES = fireflies()
DOT_CACHE = {}


def dot(r):
    key = round(r, 1)
    if key not in DOT_CACHE:
        s = int(r * 2 + 8)
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse((s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r), fill=GOLD_HI + (255,))
        DOT_CACHE[key] = im
    return DOT_CACHE[key]


# ------------------------------------------------------------------ door
def door_leaf(open_k):
    """Door leaf hinged on the right edge of the frame; open_k 0 closed .. 1 open."""
    w_full, h = 190, 372
    w = max(18, int(w_full * math.cos(open_k * 1.35)))
    ss = 2
    im = Image.new("RGBA", (w_full * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0 = (w_full - w) * ss
    shade = 1 - 0.45 * open_k
    wood = tuple(int(c * shade) for c in (104, 66, 36))
    d.rectangle((x0, 0, w_full * ss - 1, h * ss - 1), fill=wood + (255,))
    inset = tuple(int(c * shade) for c in (84, 52, 28))
    pw = w * ss
    for (py0, py1) in ((24, 170), (196, 346)):
        d.rectangle((x0 + int(pw * 0.14), py0 * ss, x0 + int(pw * 0.86), py1 * ss), outline=inset + (255,), width=4 * ss)
    hx = x0 + int(pw * 0.12)
    d.ellipse((hx - 7 * ss, 190 * ss, hx + 7 * ss, 204 * ss), fill=GOLD + (255,))
    return im.resize((w_full, h), Image.LANCZOS)


INTERIOR = Image.new("RGBA", (190, 372), (0, 0, 0, 0))
ImageDraw.Draw(INTERIOR).rectangle((0, 0, 189, 371), fill=(236, 186, 104, 255))
DOOR_X, DOOR_TOP = 1600, 418


# ------------------------------------------------------------------ characters
SS = 2
PW, PH, OX, OY = 320, 440, 160, 420     # person canvas and where the feet touch the ground


def two_bone(s, h, l1, l2, bend):
    dx, dy = h[0] - s[0], h[1] - s[1]
    dist = max(1e-3, min(math.hypot(dx, dy), l1 + l2 - 0.5))
    base = math.atan2(dy, dx)
    cosang = clamp((l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist), -1, 1)
    a = base + bend * math.acos(cosang)
    return (s[0] + l1 * math.cos(a), s[1] + l1 * math.sin(a))


class Style:
    def __init__(self, skin, shirt, stripe, trousers, shoes, glasses, hair, wrap=None, watch=False, height=1.0):
        self.skin, self.shirt, self.stripe = skin, shirt, stripe
        self.trousers, self.shoes = trousers, shoes
        self.glasses, self.hair, self.wrap, self.watch, self.height = glasses, hair, wrap, watch, height


COURIER = Style(skin=(112, 70, 46), shirt=(34, 56, 138), stripe=(62, 108, 214), trousers=(30, 28, 36),
                shoes=(52, 34, 24), glasses=True, hair=(16, 14, 14), watch=True)
CLIENT = Style(skin=(96, 58, 38), shirt=(232, 222, 200), stripe=None, trousers=(70, 44, 90),
               shoes=(40, 30, 26), glasses=False, hair=(16, 14, 14), wrap=(206, 126, 40), height=0.95)


def person(st, walk=0.0, phase=0.0, hand_l=None, hand_r=None, box=None, smile=True):
    """
    Draw a flat-illustration person. Coordinates are local: feet centre at (0, 0), y down.
    hand_l / hand_r: target hand positions (the arms solve to reach them).
    box: (cx, cy) local centre of a carried VEXA box, drawn in front of the torso.
    """
    im = Image.new("RGBA", (PW * SS, PH * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def P(x, y):
        return ((OX + x) * SS, (OY + y) * SS)

    def seg(a, b, w, col):
        d.line((P(*a), P(*b)), fill=col + (255,), width=int(w * SS))
        for p in (a, b):
            d.ellipse((P(p[0] - w / 2, p[1] - w / 2), P(p[0] + w / 2, p[1] + w / 2)), fill=col + (255,))

    k = st.height
    hip_y = -150 * k
    l1, l2 = 70 * k, 72 * k
    th = 0.42 * walk * math.sin(phase)
    legs = []
    for sgn, ph in ((1, 0.0), (-1, math.pi)):
        a = th * sgn
        bend = 0.55 * walk * max(0.0, math.sin(phase + ph + math.pi / 2))
        hip = (sgn * 13 * k, hip_y)
        knee = (hip[0] + l1 * math.sin(a), hip[1] + l1 * math.cos(a))
        foot = (knee[0] + l2 * math.sin(a - bend), knee[1] + l2 * math.cos(a - bend))
        legs.append((hip, knee, foot))
    drop = -8 - max(f[2][1] for f in legs)      # keep the lowest foot on the ground
    legs = [tuple((p[0], p[1] + drop) for p in leg) for leg in legs]
    bob = drop

    # legs and shoes (back leg first)
    for hip, knee, foot in sorted(legs, key=lambda L: L[2][0]):
        seg(hip, knee, 25 * k, st.trousers)
        seg(knee, foot, 22 * k, st.trousers)
        d.ellipse((P(foot[0] - 10, foot[1] - 7), P(foot[0] + 20, foot[1] + 8)), fill=st.shoes + (255,))

    # torso
    sh_y, sw, hw = -246 * k + bob, 42 * k, 34 * k
    torso = [P(-sw, sh_y), P(sw, sh_y), P(hw + 2, hip_y + bob + 6), P(-hw - 2, hip_y + bob + 6)]
    d.polygon(torso, fill=st.shirt + (255,))
    if st.stripe:
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).polygon(torso, fill=255)
        stripes = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(stripes)
        for x in range(int(-sw), int(sw) + 1, 7):
            sd.line((P(x, sh_y), P(x * 0.85, hip_y + bob + 6)), fill=st.stripe + (255,), width=int(2.2 * SS))
        im.paste(stripes, (0, 0), Image.fromarray((np.asarray(mask) * (np.asarray(stripes.getchannel("A")) > 0)).astype(np.uint8)))
    # collar
    d.polygon([P(-13 * k, sh_y - 2), P(0, sh_y + 16 * k), P(-4 * k, sh_y - 4)], fill=tuple(int(c * 0.75) for c in st.shirt) + (255,))
    d.polygon([P(13 * k, sh_y - 2), P(0, sh_y + 16 * k), P(4 * k, sh_y - 4)], fill=tuple(int(c * 0.75) for c in st.shirt) + (255,))
    # buttons
    for yy in range(int(sh_y + 26 * k), int(hip_y + bob), 22):
        d.ellipse((P(-2.2, yy - 2.2), P(2.2, yy + 2.2)), fill=(20, 24, 50, 255) if st.stripe else (190, 180, 160, 255))

    # neck and head
    head_c = (0, -292 * k + bob)
    seg((0, sh_y - 2), (0, head_c[1] + 20 * k), 17 * k, st.skin)
    r = 28 * k
    if st.wrap:
        d.ellipse((P(head_c[0] - r - 3, head_c[1] - r - 26), P(head_c[0] + r + 3, head_c[1] + 4)), fill=st.wrap + (255,))
    else:
        d.ellipse((P(head_c[0] - r - 2, head_c[1] - r - 8), P(head_c[0] + r + 2, head_c[1] + 10)), fill=st.hair + (255,))
    for sgn in (-1, 1):
        d.ellipse((P(sgn * r - 6, head_c[1] - 6), P(sgn * r + 6, head_c[1] + 8)), fill=st.skin + (255,))
    d.ellipse((P(head_c[0] - r, head_c[1] - r + 4), P(head_c[0] + r, head_c[1] + r + 4)), fill=st.skin + (255,))
    if st.wrap:  # knot of the head-wrap
        d.ellipse((P(-10, head_c[1] - r - 30), P(18, head_c[1] - r - 8)), fill=tuple(int(c * 0.85) for c in st.wrap) + (255,))
    else:  # hairline
        d.chord((P(head_c[0] - r, head_c[1] - r - 2), P(head_c[0] + r, head_c[1] + r - 26)), 205, 335, fill=st.hair + (255,))
        # short beard along the jaw
        dark = tuple(int(c * 0.7) for c in st.skin)
        d.chord((P(head_c[0] - r + 5, head_c[1] + 4), P(head_c[0] + r - 5, head_c[1] + r + 5)), 30, 150, fill=dark + (255,))
    ey = head_c[1] - 2
    if st.glasses:
        for sgn in (-1, 1):
            d.rounded_rectangle((P(sgn * 12 - 10, ey - 7), P(sgn * 12 + 10, ey + 7)), 3 * SS, outline=(12, 12, 12, 255), width=int(3 * SS))
        d.line((P(-2, ey - 2), P(2, ey - 2)), fill=(12, 12, 12, 255), width=int(3 * SS))
    for sgn in (-1, 1):
        d.ellipse((P(sgn * 12 - 2.4, ey - 2.4), P(sgn * 12 + 2.4, ey + 2.4)), fill=(20, 16, 14, 255))
    if smile:
        d.arc((P(-9, head_c[1] + 6), P(9, head_c[1] + 18)), 20, 160, fill=(60, 30, 26, 255), width=int(2.4 * SS))

    # arms, box, hands
    sho = {-1: (-sw + 2, sh_y + 8), 1: (sw - 2, sh_y + 8)}
    rest = {-1: (-sw - 6, hip_y + bob + 10), 1: (sw + 6, hip_y + bob + 10)}
    hands = {-1: hand_l or rest[-1], 1: hand_r or rest[1]}
    arm_parts = {}
    for sgn in (-1, 1):
        s, h = sho[sgn], hands[sgn]
        el = two_bone(s, h, 52 * k, 50 * k, -sgn if h[1] > s[1] - 20 else sgn)
        arm_parts[sgn] = (s, el, h)
    for sgn in (-1, 1):
        s, el, h = arm_parts[sgn]
        seg(s, el, 21 * k, st.shirt)
        cuff = lerp2(el, h, 0.18)
        seg(el, cuff, 22 * k, tuple(int(c * 0.8) for c in st.shirt))
        seg(cuff, h, 15 * k, st.skin)
        if st.watch and sgn == -1:
            wpt = lerp2(el, h, 0.78)
            d.ellipse((P(wpt[0] - 6, wpt[1] - 6), P(wpt[0] + 6, wpt[1] + 6)), fill=GOLD + (255,))
    if box is not None:
        draw_box(d, P, box, SS)
    for sgn in (-1, 1):
        h = arm_parts[sgn][2]
        d.ellipse((P(h[0] - 9, h[1] - 9), P(h[0] + 9, h[1] + 9)), fill=st.skin + (255,))
    return im.resize((PW, PH), Image.LANCZOS)


BOX_W, BOX_H = 86, 70
BOX_FONT = font(F_DISPLAY, 17 * SS)


def draw_box(d, P, c, ss):
    x0, y0 = c[0] - BOX_W / 2, c[1] - BOX_H / 2
    d.rectangle((P(x0, y0), P(x0 + BOX_W, y0 + BOX_H)), fill=(16, 15, 12, 255), outline=(60, 50, 34, 255), width=2 * ss)
    d.rectangle((P(x0, y0 + BOX_H * 0.38), P(x0 + BOX_W, y0 + BOX_H * 0.62)), fill=GOLD + (255,))
    d.text(P(x0 + 16, y0 + BOX_H * 0.39), "VEXA", font=BOX_FONT, fill=(20, 16, 10, 255))


def box_img():
    im = Image.new("RGBA", ((BOX_W + 10) * SS, (BOX_H + 10) * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    draw_box(d, lambda x, y: ((x + BOX_W / 2 + 5) * SS, (y + BOX_H / 2 + 5) * SS), (0, 0), SS)
    return im.resize((BOX_W + 10, BOX_H + 10), Image.LANCZOS)


BOX = box_img()
SHADOW = Image.new("RGBA", (160, 30), (0, 0, 0, 0))
ImageDraw.Draw(SHADOW).ellipse((10, 6, 149, 23), fill=(0, 0, 0, 110))


def put_person(canvas, img, x, alpha=1.0, mirror=False):
    if mirror:
        img = ImageOps.mirror(img)
    place(canvas, SHADOW, x, GROUND + 2, alpha * 0.8)
    place_tl(canvas, img, x - OX, GROUND - OY, alpha)


# ------------------------------------------------------------------ overlays
def toast():
    w, h = 400, 84
    img, pad = glass(w, h)
    img.alpha_composite(check_badge(40), (pad + 20, pad + 22))
    img.alpha_composite(text_img("Delivered to Kimihurura", font(F_BOLD, 20), WHITE, pad=0), (pad + 76, pad + 16))
    img.alpha_composite(text_img("Paid on delivery · MTN MoMo", font(F_UI, 16), MUTED, pad=0), (pad + 76, pad + 46))
    return img


TOAST = toast()
LABEL = text_img("VEXA DELIVERY  ·  KIGALI", font(F_SEMI, 17), GOLD, tracking=5, pad=0)
KNOCK = text_img("knock knock", font(F_SEMI, 22), GOLD_HI, tracking=2, pad=0)


def ripple(r, a):
    s = int(r * 2 + 8)
    im = Image.new("RGBA", (s * 2, s * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((s - r * 2, s - r * 2, s + r * 2, s + r * 2), outline=GOLD_HI + (int(255 * a),), width=5)
    return im.resize((s, s), Image.LANCZOS)


# ------------------------------------------------------------------ timeline
X_START, X_DOOR = 1330, 1500
HOLD_L, HOLD_R = (-40, -175), (40, -175)
BOX_HOLD = (0, -178)


def frame(t):
    t = t % LOOP
    canvas = SCENE.copy()

    # door light: lamp always on, interior spill while the door is open
    open_k = ease_io(prog(t, 5.6, 1.1)) * (1 - ease_io(prog(t, 11.2, 1.0)))
    place_tl(canvas, LAMP_CONE, DOOR_X + 95 - 150, 402)
    place_tl(canvas, DOOR_LIGHT, DOOR_X + 95 - 180, GROUND + 5, open_k)
    place_tl(canvas, INTERIOR, DOOR_X, DOOR_TOP, max(open_k, 0.001) if open_k > 0.01 else 0)
    # lamp fixture
    ImageDraw.Draw(canvas).rounded_rectangle((DOOR_X + 82, 380, DOOR_X + 108, 402), 5, fill=(255, 226, 160, 255))

    for p in FLIES:
        x = p["x"] + 18 * math.sin(TAU * p["sway"] * t / LOOP + p["ph"])
        y = (p["y"] - p["rise"] * 560 * t / LOOP - 200) % 560 + 200
        a = 0.25 + 0.35 * (0.5 + 0.5 * math.sin(TAU * p["tw"] * t / LOOP + p["ph"]))
        if x > 900:
            place(canvas, dot(p["r"]), x, y, a)

    # client appears in the doorway, takes the box, steps back
    c_in = ease_out(prog(t, 6.3, 0.8)) * (1 - ease_in(prog(t, 10.6, 0.6)))
    give = ease_io(prog(t, 7.6, 1.2))            # box travelling courier -> client
    client_reach = ease_io(prog(t, 7.4, 0.6)) * (1 - ease_io(prog(t, 10.2, 0.6)))
    if c_in > 0.01:
        holding = give >= 1
        ch_l = lerp2((-40, -150), (-60, -178), client_reach)
        ch_r = lerp2((40, -150), (20, -178), client_reach)
        if holding:
            ch_l, ch_r = (-40, -172), (40, -172)
        cimg = person(CLIENT, hand_l=ch_l, hand_r=ch_r, box=(0, -175) if holding else None)
        # stand inside the doorway, lit from behind
        place_tl(canvas, cimg, DOOR_X + 95 - OX + 6, GROUND - OY - 2, c_in)

    # door leaf over the doorway (hinged right) — drawn after the client so it frames them
    place_tl(canvas, door_leaf(open_k), DOOR_X, DOOR_TOP)

    # courier
    alpha = ease_out(prog(t, 0.0, 0.6)) * (1 - ease_in(prog(t, 14.2, 0.6)))
    walk_in = ease_io(prog(t, 0.6, 3.0))
    walk_out = ease_io(prog(t, 11.2, 3.3))
    x = lerp(X_START, X_DOOR, walk_in) - (X_DOOR - X_START) * walk_out
    moving_in = 0.6 < t < 3.6
    moving_out = 11.2 < t < 14.5
    walk_amt = (math.sin(math.pi * prog(t, 0.6, 3.0)) ** 0.5 if moving_in else 0) + \
               (math.sin(math.pi * prog(t, 11.2, 3.3)) ** 0.5 if moving_out else 0)
    phase = TAU * (abs(x - X_START) / 105)

    knock_k = ease_io(prog(t, 3.7, 0.4)) * (1 - ease_io(prog(t, 5.5, 0.5)))
    tap = 0.0
    for tk in (4.2, 4.6, 5.0):
        tap = max(tap, math.sin(math.pi * prog(t, tk, 0.22)))
    reach = ease_io(prog(t, 7.2, 0.5)) * (1 - ease_io(prog(t, 8.9, 0.4)))
    wave = ease_io(prog(t, 9.1, 0.3)) * (1 - ease_io(prog(t, 10.7, 0.4)))

    has_box = t < 7.6
    hand_l, hand_r = HOLD_L, HOLD_R
    box_local = BOX_HOLD
    if knock_k > 0:
        # box tucked on the left arm, right fist up at the door
        box_local = lerp2(BOX_HOLD, (-18, -182), knock_k)
        hand_l = lerp2(HOLD_L, (-56, -178), knock_k)
        fist = (86 + 10 * tap, -268)
        hand_r = lerp2(HOLD_R, fist, knock_k)
    if reach > 0:
        box_local = lerp2(BOX_HOLD, (48, -190), reach)
        hand_l = lerp2(HOLD_L, (8, -188), reach)
        hand_r = lerp2(HOLD_R, (88, -188), reach)
    if not has_box:
        hand_l = lerp2((-40, -150), hand_l, reach)
        hand_r = lerp2((40, -150), hand_r, reach)
        if wave > 0:
            hand_r = lerp2(hand_r, (70 + 14 * math.sin(TAU * 3 * t / 1.6), -300), wave)
    if t > 11.2:
        hand_l, hand_r = (-40, -150), (40, -150)

    cimg = person(COURIER, walk=walk_amt, phase=phase, hand_l=hand_l, hand_r=hand_r,
                  box=box_local if has_box else None)
    put_person(canvas, cimg, x, alpha, mirror=moving_out or t > 11.2)

    # box in flight between the two
    if 7.6 <= t and give < 1:
        start = (X_DOOR + 48, GROUND - 190)
        end = (DOOR_X + 101, GROUND - 175 * CLIENT.height)
        pos = lerp2(start, end, give)
        place(canvas, BOX, pos[0], pos[1] - 18 * math.sin(math.pi * give))

    # knock ripples and caption
    for tk in (4.2, 4.6, 5.0):
        k = prog(t, tk, 0.7)
        if 0 < k < 1:
            place(canvas, ripple(10 + 38 * k, 1 - k), DOOR_X + 8, GROUND - 268)
    ka = ease_out(prog(t, 4.1, 0.4)) * (1 - ease_in(prog(t, 5.6, 0.5)))
    place(canvas, KNOCK, DOOR_X - 10, GROUND - 330 - 10 * ka, ka)

    # label and delivered toast
    place_tl(canvas, LABEL, 1130, 214, 0.9)
    ta = ease_out(prog(t, 8.9, 0.6)) * (1 - ease_in(prog(t, 12.6, 0.6)))
    place_tl(canvas, TOAST, 1090 - 36 + 24 * (1 - ta), 250 - 36, ta)
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


MOBILE_CROP = (1020, 180, 900, 640)   # x, y, w, h


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if "--stills" in sys.argv:
        out = os.path.join(HERE, "stills")
        os.makedirs(out, exist_ok=True)
        for t in (2.0, 4.3, 6.9, 8.2, 9.8, 12.8):
            frame(t).save(os.path.join(out, f"door_{t:04.1f}.jpg"), quality=88)
        print("stills in", out)
        return
    x, y, w, h = MOBILE_CROP
    n = int(round(LOOP * FPS))
    encs = [
        encoder(os.path.join(OUT_DIR, "vexa-hero-door-1080.mp4"), "scale=1920:1080", 23),
        encoder(os.path.join(OUT_DIR, "vexa-hero-door-720.mp4"), "scale=1280:720:flags=lanczos", 24),
        encoder(os.path.join(OUT_DIR, "vexa-hero-door-mobile.mp4"), f"crop={w}:{h}:{x}:{y},scale=720:512:flags=lanczos", 24),
    ]
    for f in range(n):
        t = f / FPS
        img = frame(t)
        raw = img.tobytes()
        for e in encs:
            e.stdin.write(raw)
        if abs(t - 9.8) < 0.5 / FPS:
            img.save(os.path.join(OUT_DIR, "vexa-hero-door-poster.jpg"), quality=84)
        if f % 120 == 0:
            print(f"frame {f}/{n}", flush=True)
    for e in encs:
        e.stdin.close()
        e.wait()
    print("done", LOOP, "s")


if __name__ == "__main__":
    main()
