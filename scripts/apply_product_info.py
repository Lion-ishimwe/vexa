"""
Merge researched product information into src/_data/productInfo.json.

    python scripts/apply_product_info.py info_a.json [info_b.json ...] [--no-check]

Each file is a list of {slug, summary, highlights, specs, inBox, images, spin, source, confidence, note}.
Text is cleaned to the site's style (no long dashes, no spaced hyphens), extra photos are checked
(dead links dropped), and netlify.toml's image allowlist is refreshed to cover every photo host.
"""
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATALOG = os.path.join(ROOT, "src", "_data", "catalog.json")
INFO = os.path.join(ROOT, "src", "_data", "productInfo.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
# hosts that refuse plain requests but serve browsers (linked directly, not through the image CDN)
BROWSER_ONLY = ("assets.hikvision.com",)


def clean(text):
    text = str(text or "").strip()
    text = re.sub(r"(\d)\s*[–—]\s*(\d)", r"\1 to \2", text)
    text = re.sub(r"\s*[–—]\s*", ", ", text)
    text = re.sub(r"\s+-\s+", ", ", text)
    return re.sub(r"\s{2,}", " ", text)


def alive(url):
    args = ["curl", "-s", "-o", os.devnull, "-w", "%{http_code} %{content_type}", "--max-time", "40", "-L", url]
    if urlparse(url).netloc in BROWSER_ONLY:
        args[1:1] = ["-A", UA]
    out = subprocess.run(args, capture_output=True, text=True).stdout
    return out.startswith("200") and "image" in out


def main():
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--no-check" not in sys.argv
    main_img = {p["slug"]: p.get("img", "") for p in json.load(open(CATALOG, encoding="utf8"))["products"]}
    slugs = set(main_img)
    info = json.load(open(INFO, encoding="utf8")) if os.path.exists(INFO) else {}
    entries, unknown = [], []
    for f in files:
        for e in json.load(open(f, encoding="utf8")):
            (entries if e.get("slug") in slugs else unknown).append(e)

    urls = sorted({u for e in entries for u in (e.get("images") or []) + (e.get("spin") or []) if u})
    ok = set(urls)
    if check and urls:
        with ThreadPoolExecutor(12) as ex:
            ok = {u for u, good in zip(urls, ex.map(alive, urls)) if good}
    dropped = len(urls) - len(ok)

    for e in entries:
        spin = [u for u in (e.get("spin") or []) if u in ok]
        info[e["slug"]] = {
            "summary": clean(e.get("summary")),
            "highlights": [clean(h) for h in e.get("highlights") or [] if str(h).strip()],
            "specs": [[clean(k), clean(v)] for k, v in (e.get("specs") or []) if str(k).strip() and str(v).strip()],
            "inBox": [clean(b) for b in e.get("inBox") or [] if str(b).strip()],
            "images": [u for u in (e.get("images") or []) if u in ok and u != main_img[e["slug"]]][:5],
            "spin": spin if len(spin) >= 12 and len(spin) == len(e.get("spin") or []) else [],
            "source": e.get("source") or "",
            "confidence": e.get("confidence") or "",
        }
    with open(INFO, "w", encoding="utf8") as fh:
        fh.write(json.dumps(info, indent=1, ensure_ascii=False) + "\n")

    # every photo host (catalog photos and extra angles) must be allowed for Netlify's image CDN
    cat = json.load(open(CATALOG, encoding="utf8"))
    all_urls = [p["img"] for p in cat["products"] if p.get("img", "").startswith("http")]
    all_urls += [u for v in info.values() for u in v.get("images", []) + v.get("spin", [])]
    hosts = sorted({urlparse(u).netloc for u in all_urls})
    block = "[images]\n  remote_images = [\n" + ",\n".join(f"    'https://{re.escape(h)}/.*'" for h in hosts) + "\n  ]\n"
    toml_path = os.path.join(ROOT, "netlify.toml")
    toml = open(toml_path, encoding="utf8").read()
    toml = re.sub(r"\[images\]\n  remote_images = \[\n.*?\n  \]\n", "", toml, flags=re.S).rstrip() + "\n\n" + block
    with open(toml_path, "w", encoding="utf8") as fh:
        fh.write(toml)

    print(f"merged {len(entries)} products ({len(unknown)} unknown slugs skipped); "
          f"{len(ok)} extra photos kept, {dropped} dead links dropped; "
          f"{sum(1 for v in info.values() if v['spin'])} with 360 view; {len(info)} products have full info")


if __name__ == "__main__":
    main()
