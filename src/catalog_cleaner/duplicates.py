"""Find likely duplicate products among cleaned rows. Suggests which to keep; never deletes anything."""

import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from typing import NamedTuple

TYPO = 0.8  # a single differing word counts as a typo only if the two spellings are this similar


class Group(NamedTuple):
    rows: list[int]   # 1-based row numbers, ascending
    keep: int         # suggested row to keep
    kind: str         # "same title" or "similar title"


def tokens(title: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", title.lower())


def similarity(a: list[str], b: list[str]) -> float:
    """1.0 = same words (any order); ~0.8-0.99 = one word differs by a typo; 0 = different product.
    A differing word that contains a digit (a size) or is a different word (a colour) is never a match."""
    only_a, only_b = Counter(a) - Counter(b), Counter(b) - Counter(a)
    if not only_a and not only_b:
        return 1.0
    if sum(only_a.values()) == 1 == sum(only_b.values()):
        x, y = next(iter(only_a)), next(iter(only_b))
        if not re.search(r"\d", x + y):
            ratio = SequenceMatcher(None, x, y).ratio()
            return ratio if ratio >= TYPO else 0.0
    return 0.0


def find_duplicates(rows: list[dict]) -> list[Group]:
    # Only compare rows with the same vendor, word count and size numbers: it is both faster and safer.
    buckets = defaultdict(list)
    for n, r in enumerate(rows, 1):
        t = tokens(r["Title"])
        if t:
            sizes = tuple(sorted(w for w in t if re.search(r"\d", w)))
            buckets[(r["Vendor"].lower(), len(t), sizes)].append((n, t))

    parent = list(range(len(rows) + 1))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    loose = set()  # rows involved in a match that was not an identical title
    for items in buckets.values():
        for (i, a), (j, b) in combinations(items, 2):
            if similarity(a, b):
                parent[find(i)] = find(j)
                if rows[i - 1]["Title"] != rows[j - 1]["Title"]:
                    loose.update((i, j))

    members = defaultdict(list)
    for n in range(1, len(rows) + 1):
        members[find(n)].append(n)

    def richness(n: int):  # prefer the row with a SKU, then an image, then the longest description
        r = rows[n - 1]
        return (bool(r["Variant SKU"].strip()), bool(r["Image Src"].strip()), len(r["Body (HTML)"]), -n)

    groups = [Group(m, max(m, key=richness), "similar title" if loose.intersection(m) else "same title")
              for m in members.values() if len(m) > 1]
    return sorted(groups, key=lambda g: g.rows[0])
