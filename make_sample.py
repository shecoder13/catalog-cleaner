"""Generate a deliberately messy 500-row Shopify-style catalog: data/sample_catalog.csv (seeded, repeatable).
It contains 450 unique products plus 25 exact and 25 near duplicates (handles end in -copy / -v2)."""
import csv
import random
import re
from pathlib import Path

random.seed(42)
N, EXACT_DUPS, NEAR_DUPS = 500, 25, 25
COLS = ["Handle", "Title", "Body (HTML)", "Vendor", "Product Category", "Type", "Tags",
        "Variant SKU", "Variant Price", "Image Src"]

# base title, vendor, type, tags, price range, sizes, colours
PRODUCTS = [
    ("Stainless Steel Water Bottle", "HydroPeak", "Drinkware", "bottle,steel", (399, 999), ["500 ml", "750 ml", "1 L"], ["Black", "Blue", "Silver"]),
    ("Cotton Crew Neck T-Shirt", "UrbanLoom", "Apparel", "tshirt,cotton", (299, 799), ["S", "M", "L", "XL"], ["White", "Navy", "Olive"]),
    ("Wireless Bluetooth Earbuds", "SoundNest", "Electronics", "audio,bluetooth", (1299, 3999), ["Standard"], ["Black", "White"]),
    ("Non-Stick Frying Pan", "KitchenKraft", "Cookware", "pan,non-stick", (599, 1899), ["20 cm", "24 cm", "28 cm"], ["Black", "Red"]),
    ("Yoga Mat", "FlexFit", "Fitness", "yoga,mat", (499, 1499), ["4 mm", "6 mm"], ["Purple", "Teal", "Grey"]),
    ("LED Desk Lamp", "BrightWorks", "Lighting", "lamp,led", (699, 2199), ["Standard"], ["White", "Black"]),
    ("Leather Bifold Wallet", "CraftHide", "Accessories", "wallet,leather", (449, 1599), ["Standard"], ["Brown", "Black", "Tan"]),
    ("Ceramic Coffee Mug", "BrewHaus", "Drinkware", "mug,ceramic", (199, 549), ["300 ml", "350 ml"], ["White", "Green", "Yellow"]),
]
SIZE_VARIANTS = {"500 ml": ["500ml", "500 ML", "0.5 L"], "750 ml": ["750ml", "750 ML"], "1 L": ["1L", "1 litre", "1000 ml"],
                 "300 ml": ["300ml", "300 ML"], "350 ml": ["350ml", "350 ML"], "20 cm": ["20cm", "20 CM"],
                 "24 cm": ["24cm", "24 CM"], "28 cm": ["28cm", "28 CM"], "4 mm": ["4mm"], "6 mm": ["6mm"]}


def messy_title(t):
    r = random.random()
    if r < 0.25: t = t.upper()
    elif r < 0.40: t = t.lower()
    elif r < 0.55: t = "  " + t.replace(" ", "  ", 1) + " "
    elif r < 0.65: t += " !!"
    return t


def messy_price(p):
    return random.choice([f"{p}", f"{p}.00", f"Rs. {p:,}", f"₹{p:,}", f"${p / 83:.2f}", f"{p:,}.00"])


def messy_vendor(v):
    return random.choice([v, v, v.upper(), v.lower(), f"{v} Pvt Ltd", f" {v} "])


def messy_tags(tags):
    t = tags.split(",") + random.sample(["new", "sale", "gift", "bestseller"], random.randint(0, 2))
    return random.choice([", ".join(t), ",".join(x.upper() for x in t), " , ".join(t + t[:1])])


SERIES = ["Classic", "Pro", "Lite", "Eco", "Max", "Mini", "Premium", "Sport", "Travel", "Studio", "Nova", "Prime"]
combos = [(p, s, c, ser) for p in PRODUCTS for s in p[5] for c in p[6] for ser in SERIES]
rows = []
for i, ((base, vendor, typ, tags, (lo, hi), sizes, colours), size, colour, series) in enumerate(
        random.sample(combos, N - EXACT_DUPS - NEAR_DUPS)):   # every product unique, so only planted duplicates are real
    size_txt = random.choice([size] + SIZE_VARIANTS.get(size, []))
    title = f"{base} {series} {size_txt} {colour}".replace(" Standard", "")
    price = random.randrange(lo, hi, 10) + random.choice([0, 9])
    rows.append({
        "Handle": re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") + f"-{i}",
        "Title": messy_title(title),
        "Body (HTML)": random.choice([f"<p>{base} &amp; more. <b>Great</b> value.</p>", f"<p>{title}</p><br>", "", f"{base}\n\n\nBuy now!!!"]),
        "Vendor": messy_vendor(vendor),
        "Product Category": "",
        "Type": random.choice([typ, typ, typ.lower(), ""]) if random.random() > 0.3 else "",
        "Tags": messy_tags(tags),
        "Variant SKU": "" if random.random() < 0.08 else f"{vendor[:3].upper()}-{i:04d}",
        "Variant Price": messy_price(price),
        "Image Src": "" if random.random() < 0.1 else f"https://cdn.example.com/img/{i}.jpg",
    })

for r in random.sample(rows, EXACT_DUPS):                      # exact duplicates, new handle/SKU
    d = dict(r); d["Handle"] += "-copy"; d["Variant SKU"] = ""
    rows.append(d)
for r in random.sample(rows[:N - EXACT_DUPS - NEAR_DUPS], NEAR_DUPS):   # near duplicates: typo or word order
    d = dict(r); words = d["Title"].split()
    d["Title"] = " ".join(reversed(words[:2])) + " " + " ".join(words[2:]) if random.random() < 0.5 else d["Title"].replace("e", "", 1)
    d["Handle"] += "-v2"; d["Variant SKU"] = ""
    rows.append(d)

random.shuffle(rows)
for k, i in enumerate([11, 97, 203, 288, 371, 455]):             # unreadable prices, for the review agent to look at
    n = 500 + i * 7
    rows[i]["Variant Price"] = [f"{n}/-", f"Rs {n} only", f"about {n}", f"{n} per piece", "call us", f"{n}-{n + 200}"][k]
out = Path(__file__).parent / "data" / "sample_catalog.csv"
out.parent.mkdir(exist_ok=True)
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    w.writerows(rows)
print(f"wrote {len(rows)} rows to {out}")
