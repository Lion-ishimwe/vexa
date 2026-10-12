"""
Apply product photo links to the catalog and allow their hosts in Netlify's Image CDN.

    python scripts/apply_image_links.py results1.json [results2.json ...]

Each results file is a JSON list of {"slug": ..., "image": url or null, "page": url or null}.
Only products that have no photo yet are filled (use --replace to overwrite).
Afterwards netlify.toml's [images] remote_images list is rewritten to cover every
external host the catalog links to, so the live site can resize those photos.
"""
import json
import os
import re
import sys
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATALOG = os.path.join(ROOT, "src", "_data", "catalog.json")
NETLIFY = os.path.join(ROOT, "netlify.toml")


def main():
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    replace = "--replace" in sys.argv
    cat = json.load(open(CATALOG, encoding="utf8"))
    by_slug = {p["slug"]: p for p in cat["products"]}
    applied = skipped = missing = 0
    for f in files:
        for item in json.load(open(f, encoding="utf8")):
            p = by_slug.get(item.get("slug"))
            if not p:
                missing += 1
                continue
            url = item.get("image")
            if not url:
                continue
            if p.get("img") and not replace:
                skipped += 1
                continue
            p["img"] = url
            if item.get("page"):
                p["imgSource"] = item["page"]
            applied += 1
    with open(CATALOG, "w", encoding="utf8") as fh:
        fh.write(json.dumps(cat, indent=2, ensure_ascii=False) + "\n")

    hosts = sorted({urlparse(p["img"]).netloc for p in cat["products"] if p.get("img", "").startswith("http")})
    block = "[images]\n  remote_images = [\n" + ",\n".join(
        f"    'https://{re.escape(h)}/.*'" for h in hosts) + "\n  ]\n"   # TOML literal strings keep the regex backslashes
    toml = open(NETLIFY, encoding="utf8").read()
    toml = re.sub(r"\[images\]\n  remote_images = \[\n.*?\n  \]\n", "", toml, flags=re.S).rstrip() + "\n\n" + block
    with open(NETLIFY, "w", encoding="utf8") as fh:
        fh.write(toml)
    left = sum(1 for p in cat["products"] if not p.get("img"))
    print(f"applied {applied}, kept existing {skipped}, unknown slugs {missing}; {len(hosts)} image hosts allowed; {left} products still without a photo")


if __name__ == "__main__":
    main()
