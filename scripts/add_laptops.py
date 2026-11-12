"""
Add laptops from a supplier list to the Laptops aisle.

    python scripts/add_laptops.py scripts/laptops_2026_11.txt

Each line: NAME AND SPECS|cpu generation|display inches|price
Titles are cleaned (brand casing, Core/Ultra names), each product gets the next SKU,
and lines already in the catalog (same title) only get their price updated.
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATALOG = os.path.join(ROOT, "src", "_data", "catalog.json")

WORDS = {
    "HP": "HP", "ASUS": "ASUS", "DELL": "Dell", "MSI": "MSI", "LENOVO": "Lenovo", "INFINIX": "Infinix", "ACER": "Acer",
    "EXPERTBOOK": "ExpertBook", "PROBOOK": "ProBook", "ELITEBOOK": "EliteBook", "OMNIBOOK": "OmniBook",
    "THINKPAD": "ThinkPad", "THINKBOOK": "ThinkBook", "TRAVELMATE": "TravelMate", "INBOOK": "INBook",
    "MODERN": "Modern", "VICTUS": "Victus", "SPECTRE": "Spectre", "TUF": "TUF", "GAMING": "Gaming",
    "LATITUDE": "Latitude", "PRO": "Pro", "ESSENTIAL": "Essential", "LOQ": "LOQ", "PLUS": "Plus", "AIR": "Air",
    "FLIP": "Flip", "ULTRA": "Ultra", "AI": "AI", "AMD": "AMD", "RYZEN": "Ryzen", "TOUCH": "Touch", "LAPTOP": "Laptop",
    "GEN": "Gen", "X360": "x360", "2IN1": "2-in-1", "X": "X", "T14S": "T14s", "IAL": "IAL", "CVA": "CVA", "RTX": "RTX",
}
CPU = {"I3": "Core i3", "I5": "Core i5", "I7": "Core i7", "U5": "Core Ultra 5", "U7": "Core Ultra 7",
       "R5": "Ryzen 5", "R7": "Ryzen 7"}


def word(w):
    u = w.upper()
    if u in WORDS:
        return WORDS[u]
    if re.fullmatch(r"GEN\d+", u):
        return "Gen " + u[3:]
    if re.fullmatch(r"G\d+I?", u) and len(u) <= 4:   # G11, G2I
        return u[:-1] + "i" if u.endswith("I") and len(u) > 2 else u
    if u == "4G1I":
        return "4 G1i"
    return u


def parse(line):
    name, gen, disp, price = [s.strip() for s in line.split("|")]
    tokens = name.split()
    cpu_i = next(i for i, t in enumerate(tokens) if t.upper() in CPU)
    model_tokens = tokens[:cpu_i]
    rest = tokens[cpu_i + 1:]
    if model_tokens[-2:] and [t.upper() for t in model_tokens[-2:]] == ["AMD", "RYZEN"]:
        model_tokens = model_tokens[:-2]
    cpu = CPU[tokens[cpu_i].upper()]
    ram = next(t for t in rest if t.upper().endswith("GB") and int(t[:-2]) <= 64)
    storage = next(t for t in rest[rest.index(ram) + 1:] if re.fullmatch(r"\d+(GB|TB)", t.upper()))
    extra = [t for t in rest if t not in (ram, storage)]
    model = " ".join(word(t) for t in model_tokens)
    gpu = ""
    if "RTX" in [t.upper() for t in extra]:
        gpu = "RTX " + next(t for t in extra if t.isdigit())
    touch = "TOUCH" in [t.upper() for t in extra]
    gaming = "GAMING" in [t.upper() for t in model_tokens + extra]
    brand = word(tokens[0])
    gen_label = f"{gen}th Gen" if cpu.startswith("Core") else ""
    parts = [cpu, f"{ram.upper()} RAM", f"{storage.upper()} SSD", f'{disp}"']
    if gpu:
        parts.append(gpu)
    if touch:
        parts.append("Touch")
    title = f"{model} {', '.join(parts)}"
    inch = f"{disp} inch"
    bits = [f"{inch} {'touch ' if touch else ''}display", f"{gen_label + ' ' if gen_label else ''}{cpu}".strip(),
            f"{ram.upper()} RAM", f"{storage.upper()} SSD"]
    if gpu:
        bits.append(f"NVIDIA GeForce {gpu} graphics")
    desc = ("Gaming laptop with " if gaming else "Laptop with ") + ", ".join(bits[:-1]) + " and " + bits[-1] + "."
    return {"title": title, "brand": brand, "model": model, "price": int(price), "desc": desc, "display": disp}


def slugify(s):
    s = s.lower().replace('"', " inch").replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main():
    src = sys.argv[1]
    cat = json.load(open(CATALOG, encoding="utf8"))
    prods = cat["products"]
    # the website adds ", Touch Screen" / ", Non-Touch Screen" to laptop titles; match without it
    plain = lambda t: re.sub(r", (non-)?touch screen$", "", t.lower())
    by_title = {plain(p["title"]): p for p in prods}
    slugs = {p["slug"] for p in prods}
    top = max(int(p["sku"][3:]) for p in prods if p.get("sku"))
    last_laptop = max(i for i, p in enumerate(prods) if p["category"] == "computers" and p["aisle"] == "Laptops")
    added, repriced = [], []
    for line in open(src, encoding="utf8"):
        if not line.strip():
            continue
        row = parse(line)
        hit = by_title.get(plain(re.sub(r", Touch$", "", row["title"])))
        if hit:
            if hit.get("price") != row["price"]:
                repriced.append((hit["sku"], hit["title"], hit.get("price"), row["price"]))
                hit["price"] = row["price"]
            continue
        slug = slugify(row["title"])
        while slug in slugs:
            slug += "-2"
        slugs.add(slug)
        top += 1
        p = {"slug": slug, "title": row["title"], "brand": row["brand"], "model": row["model"],
             "category": "computers", "aisle": "Laptops", "price": row["price"], "desc": row["desc"],
             "img": "", "sku": f"VX-{top}"}
        last_laptop += 1
        prods.insert(last_laptop, p)
        by_title[plain(p["title"])] = p
        added.append(p)
    for c in cat["categories"]:
        items = [p for p in prods if p["category"] == c["slug"]]
        c["count"] = len(items)
        c["aisles"] = list(dict.fromkeys(p["aisle"] for p in items))
    if "--dry-run" not in sys.argv:
        with open(CATALOG, "w", encoding="utf8") as fh:
            fh.write(json.dumps(cat, indent=2, ensure_ascii=False) + "\n")
    for p in added:
        print(f"{p['sku']}  {p['price']:>9,}  {p['title']}")
    for r in repriced:
        print("repriced", r)
    print(f"{len(added)} added, {len(repriced)} repriced; catalog {len(prods)}")


if __name__ == "__main__":
    main()
