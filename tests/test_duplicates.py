from pathlib import Path

import pytest

from catalog_cleaner.clean import clean, read_catalog
from catalog_cleaner.duplicates import find_duplicates, similarity, tokens


def _row(title, vendor="Acme", sku="S", image="x.jpg", body=""):
    return {"Title": title, "Vendor": vendor, "Variant SKU": sku, "Image Src": image, "Body (HTML)": body}


@pytest.mark.parametrize("a,b,match", [
    ("Steel Bottle 500 ml Black", "Steel Bottle 500 ml Black", True),
    ("Steel Bottle 500 ml Black", "Bottle Steel 500 ml Black", True),     # words reordered
    ("Steel Bottle 500 ml Black", "Stel Bottle 500 ml Black", True),      # typo
    ("Steel Bottle 500 ml Black", "Steel Bottle 750 ml Black", False),    # different size
    ("Steel Bottle 500 ml Black", "Steel Bottle 500 ml Blue", False),     # different colour
    ("Cotton Tee Pro L", "Cotton Tee Pro XL", False),                     # different size letter
    ("Steel Bottle 500 ml Black", "Steel Bottle 500 ml Black Lid", False),
])
def test_similarity(a, b, match):
    assert bool(similarity(tokens(a), tokens(b))) is match


def test_groups_only_within_same_vendor_and_pick_richest_row():
    rows = [_row("Steel Bottle", sku="", image=""), _row("Steel Bottle", sku="A1"),
            _row("Steel Bottle", vendor="Other"), _row("Mug")]
    (g,) = find_duplicates(rows)
    assert g.rows == [1, 2] and g.keep == 2 and g.kind == "same title"


def test_kind_is_similar_when_titles_differ():
    (g,) = find_duplicates([_row("Steel Bottle 500 ml"), _row("Bottle Steel 500 ml")])
    assert g.kind == "similar title"


def test_blank_titles_are_never_grouped():
    assert find_duplicates([_row(""), _row("")]) == []


def test_sample_catalog_finds_exactly_the_planted_duplicates():
    rows, _ = read_catalog(Path(__file__).parent.parent / "data" / "sample_catalog.csv")
    cleaned, _, _ = clean(rows)
    base = lambda h: h.removesuffix("-copy").removesuffix("-v2")   # noqa: E731
    groups = find_duplicates(cleaned)
    for g in groups:                                               # precision: no false matches
        assert len({base(cleaned[n - 1]["Handle"]) for n in g.rows}) == 1
    found = {n for g in groups for n in g.rows}
    planted = {n for n, r in enumerate(cleaned, 1)
               if r["Handle"].endswith(("-copy", "-v2")) or base(r["Handle"]) + "-copy" in {x["Handle"] for x in cleaned}
               or base(r["Handle"]) + "-v2" in {x["Handle"] for x in cleaned}}
    assert found == planted                                        # recall: every planted duplicate found
    assert len(found) >= 90
