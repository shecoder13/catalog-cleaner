from pathlib import Path

import pytest

from catalog_cleaner.clean import (canonical_map, clean, clean_price, clean_tags, clean_title,
                                   fix_units, read_catalog)


@pytest.mark.parametrize("raw,expected", [
    ("  Steel   Bottle  500ml ", "Steel Bottle 500 ml"),
    ("Steel Bottle !!", "Steel Bottle"),
    ("STEEL BOTTLE 500 ML BLACK", "Steel Bottle 500 ml Black"),
    ("steel bottle 1l black", "Steel Bottle 1 L Black"),
    ("LED DESK LAMP WHITE", "LED Desk Lamp White"),
    ("COTTON T-SHIRT", "Cotton T-Shirt"),
    ("MEN'S WALLET", "Men's Wallet"),
    ("Steel Bottle iPhone Edition", "Steel Bottle iPhone Edition"),   # mixed case left alone
])
def test_title(raw, expected):
    assert clean_title(raw)[0] == expected


@pytest.mark.parametrize("raw,expected", [
    ("0.5 L", "500 ml"), ("1000 ml", "1 L"), ("1 litre", "1 L"), ("750ML", "750 ml"),
    ("20CM", "20 cm"), ("4mm", "4 mm"), ("2.5 liters", "2.5 L"), ("1500 ml", "1.5 L"), ("Size L", "Size L"),
])
def test_units(raw, expected):
    assert fix_units(raw) == expected


def test_title_reports_why():
    assert clean_title("pan  20cm!!")[1] == "collapsed extra spaces; removed trailing punctuation; fixed capitalisation; standardised units"
    assert clean_title("Pan 20 cm")[1] == ""


@pytest.mark.parametrize("raw,expected", [
    ("1299", ("1299.00", "")), ("Rs. 1,299", ("1299.00", "")), ("₹1,299.50", ("1299.50", "")),
    ("1,299.00", ("1299.00", "")), ("", ("", "")),
])
def test_price_ok(raw, expected):
    assert clean_price(raw) == expected


def test_price_flags_not_converts():
    assert clean_price("$22.28") == ("$22.28", "price is not in INR; left unchanged")
    assert clean_price("call us")[1] == "price could not be read"


def test_tags():
    assert clean_tags("MUG, Ceramic ,mug,,new") == "mug, ceramic, new"


def test_canonical_vendor_and_type():
    m = canonical_map(["HydroPeak", "HYDROPEAK", "hydropeak", "HydroPeak", "SOLO", "solo"])
    assert m == {"hydropeak": "HydroPeak", "solo": "Solo"}


def _row(**kw):
    base = {"Handle": "h", "Title": "T", "Body (HTML)": "", "Vendor": "Acme", "Product Category": "",
            "Type": "Cups", "Tags": "a", "Variant SKU": "S1", "Variant Price": "10.00", "Image Src": ""}
    return {**base, **kw}


def test_clean_records_changes_flags_and_keeps_input():
    rows = [_row(Title="mug  300ml", Vendor="ACME Pvt Ltd", **{"Variant SKU": "", "Variant Price": "$5"}),
            _row(Handle="h2", Vendor="Acme")]
    before = [dict(r) for r in rows]
    out, changes, flags = clean(rows)
    assert rows == before                                     # input untouched
    assert out[0]["Title"] == "Mug 300 ml" and out[0]["Vendor"] == "Acme"
    assert out[0]["Variant Price"] == "$5"
    assert {(c.row, c.field) for c in changes} == {(1, "Title"), (1, "Vendor")}
    assert all(c.old != c.new and c.reason for c in changes)
    assert {(f.row, f.issue) for f in flags} == {(1, "price is not in INR; left unchanged"), (1, "missing SKU")}
    assert out[0]["Type"] == "Cups"                            # blank/other fields never invented


def test_blank_type_stays_blank():
    out, changes, _ = clean([_row(Type=""), _row(Handle="h2", Type="Cups")])
    assert out[0]["Type"] == "" and not [c for c in changes if c.field == "Type"]


def test_sample_catalog_is_cleaned_and_second_pass_changes_nothing():
    path = Path(__file__).parent.parent / "data" / "sample_catalog.csv"
    rows, _ = read_catalog(path)
    once, changes, flags = clean(rows)
    assert len(once) == 500 and len(changes) > 500
    twice, changes2, flags2 = clean(once)
    assert changes2 == [] and twice == once                    # idempotent
    assert {f.issue for f in flags} >= {"missing SKU", "price is not in INR; left unchanged"}
