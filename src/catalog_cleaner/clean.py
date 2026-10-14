"""Rule-based cleaning for Shopify-style product rows. Every edit is recorded; nothing is changed silently."""

import csv
import re
from collections import Counter
from typing import NamedTuple

ACRONYMS = {"led", "usb", "tv", "hd", "uv", "pvc", "pu", "bpa"}
VENDOR_SUFFIX = re.compile(r"(?i)[\s,]+(pvt\.?\s*ltd\.?|private limited|ltd\.?|inc\.?|llc)$")
UNIT = re.compile(r"(?i)(?<![\w.])(\d+(?:\.\d+)?)\s*(millilit(?:re|er)s?|ml|lit(?:re|er)s?|l|cm|mm)\b")


class Change(NamedTuple):
    row: int        # 1-based data row
    handle: str
    field: str
    old: str
    new: str
    reason: str


class Flag(NamedTuple):
    row: int
    handle: str
    field: str
    value: str
    issue: str


def read_catalog(path) -> tuple[list[dict], list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def write_catalog(path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _cap(m: re.Match) -> str:
    w = m.group()
    return w.upper() if w.lower() in ACRONYMS else w[0].upper() + w[1:].lower()


def fix_case(s: str) -> str:
    """Only touch ALL CAPS or all lowercase text; mixed case is assumed deliberate."""
    if s == s.upper() or s == s.lower():
        return re.sub(r"[A-Za-z][A-Za-z0-9']*", _cap, s)
    return s


def _volume(ml: float) -> str:
    return f"{ml / 1000:g} L" if ml >= 1000 else f"{ml:g} ml"


def fix_units(s: str) -> str:
    """Volumes: under 1000 ml in ml, otherwise litres (0.5 L -> 500 ml, 1000 ml -> 1 L). Lengths: cm / mm."""
    def fmt(m: re.Match) -> str:
        num, unit = float(m.group(1)), m.group(2).lower()
        if unit in ("cm", "mm"):
            return f"{num:g} {unit}"
        return _volume(num if unit.startswith("milli") or unit == "ml" else num * 1000)
    return UNIT.sub(fmt, s)


TITLE_STEPS = [
    ("collapsed extra spaces", lambda s: " ".join(s.split())),
    ("removed trailing punctuation", lambda s: re.sub(r"[\s!?.,;:]+$", "", s)),
    ("fixed capitalisation", fix_case),
    ("standardised units", fix_units),
]


def clean_title(title: str) -> tuple[str, str]:
    reasons = []
    for name, step in TITLE_STEPS:
        new = step(title)
        if new != title:
            reasons.append(name)
        title = new
    return title, "; ".join(reasons)


def strip_vendor(v: str) -> str:
    return VENDOR_SUFFIX.sub("", v.strip()).strip()


def canonical_map(values) -> dict[str, str]:
    """lowercase -> preferred spelling: the most common mixed-case form, else a tidied one."""
    groups: dict[str, Counter] = {}
    for v in values:
        if v:
            groups.setdefault(v.lower(), Counter())[v] += 1
    return {k: next((s for s, _ in c.most_common() if s != s.upper() and s != s.lower()), fix_case(c.most_common(1)[0][0]))
            for k, c in groups.items()}


def clean_price(v: str) -> tuple[str, str]:
    """Returns (value, issue). Non-INR or unreadable prices are left as they are and flagged."""
    s = v.strip()
    if not s:
        return v, ""
    if re.search(r"[$€£]", s):
        return v, "price is not in INR; left unchanged"
    try:
        return f"{float(re.sub(r'(?i)rs\.?|inr|₹|[,\s]', '', s)):.2f}", ""
    except ValueError:
        return v, "price could not be read"


def clean_tags(v: str) -> str:
    seen: dict[str, None] = {}
    for t in v.split(","):
        if t.strip():
            seen.setdefault(t.strip().lower())
    return ", ".join(seen)


def clean(rows: list[dict]) -> tuple[list[dict], list[Change], list[Flag]]:
    vendors = canonical_map(strip_vendor(r["Vendor"]) for r in rows)
    types = canonical_map(r["Type"].strip() for r in rows)
    out, changes, flags = [], [], []
    for n, r in enumerate(rows, 1):
        new = dict(r)

        def put(field: str, value: str, reason: str) -> None:
            if value != r[field]:
                new[field] = value
                changes.append(Change(n, r["Handle"], field, r[field], value, reason))

        title, why = clean_title(r["Title"])
        put("Title", title, why)
        v = strip_vendor(r["Vendor"])
        put("Vendor", vendors.get(v.lower(), v), "standardised vendor name")
        put("Type", types.get(r["Type"].strip().lower(), r["Type"]), "standardised product type")
        put("Tags", clean_tags(r["Tags"]), "lowercased, deduplicated tags")
        price, issue = clean_price(r["Variant Price"])
        put("Variant Price", price, "standardised price format")
        if issue:
            flags.append(Flag(n, r["Handle"], "Variant Price", r["Variant Price"], issue))
        if not r["Variant SKU"].strip():
            flags.append(Flag(n, r["Handle"], "Variant SKU", "", "missing SKU"))
        out.append(new)
    return out, changes, flags
