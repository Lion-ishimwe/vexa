"""
Cut the founder portrait out of its grey studio backdrop.

    python scripts/hero-video/cutout.py

Reads source/founder.jpg, writes source/founder-cutout.png (RGBA).
The backdrop is a flat neutral grey, so background = low colour + mid brightness,
flood-filled from the frame edges so grey details inside the figure are kept.
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(__file__)
src = Image.open(os.path.join(HERE, "source", "founder.jpg")).convert("RGB")
a = np.asarray(src).astype(np.int32)
r, g, b = a[..., 0], a[..., 1], a[..., 2]
chroma = a.max(axis=2) - a.min(axis=2)
lum = (r * 299 + g * 587 + b * 114) // 1000

bg_like = (chroma < 14) & (lum > 42) & (lum < 100)
m = Image.fromarray((bg_like * 255).astype(np.uint8), "L")
# close pin-holes in the backdrop, then flood from the frame edge
m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
w, h = m.size
for x in range(0, w, 25):
    for y in (0, h - 1):
        if m.getpixel((x, y)) == 255:
            ImageDraw.floodfill(m, (x, y), 128)
for y in range(0, h, 25):
    for x in (0, w - 1):
        if m.getpixel((x, y)) == 255:
            ImageDraw.floodfill(m, (x, y), 128)

outside = np.asarray(m) == 128
alpha = Image.fromarray(((~outside) * 255).astype(np.uint8), "L")
# drop specks, smooth the silhouette, feather the edge
alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
alpha = alpha.filter(ImageFilter.MinFilter(3))
alpha = alpha.filter(ImageFilter.GaussianBlur(1.6))

# pull grey backdrop spill out of the soft edge pixels
arr = np.asarray(src).astype(np.float32)
al = np.asarray(alpha).astype(np.float32) / 255
edge = (al > 0.02) & (al < 0.98)
bg = np.array([70, 68, 69], np.float32)
k = np.clip(al, 0.05, 1)[..., None]
clean = np.where(edge[..., None], np.clip((arr - bg * (1 - k)) / k, 0, 255), arr)

out = np.dstack([clean, al * 255]).astype(np.uint8)
Image.fromarray(out, "RGBA").save(os.path.join(HERE, "source", "founder-cutout.png"))
print("saved", out.shape)
