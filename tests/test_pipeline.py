import csv
import hashlib
import json
from pathlib import Path

import pytest

from catalog_cleaner.pipeline import REQUIRED, run

SAMPLE = Path(__file__).parent.parent / "data" / "sample_catalog.csv"
KEYWORDS = {"Bottle": "Drinkware", "Mug": "Drinkware", "T-Shirt": "Apparel", "Earbuds": "Electronics",
            "Pan": "Cookware", "Yoga": "Fitness", "Lamp": "Lighting", "Wallet": "Accessories"}


def fake_ask(system, user):
    lines = user.split("Products:\n")[1].splitlines()
    return json.dumps([{"row": int(ln.split(":")[0]), "type": next((t for k, t in KEYWORDS.items() if k in ln), "UNKNOWN")}
                       for ln in lines])


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_full_run_writes_every_file_and_never_touches_the_input(tmp_path):
    before = hashlib.md5(SAMPLE.read_bytes()).hexdigest()
    r = run(SAMPLE, tmp_path / "out", ask=fake_ask)
    assert hashlib.md5(SAMPLE.read_bytes()).hexdigest() == before
    for name in ["cleaned.csv", "changes.csv", "flags.csv", "duplicates.csv", "report.html"]:
        assert (tmp_path / "out" / name).stat().st_size > 0
    cleaned = _read(tmp_path / "out" / "cleaned.csv")
    assert len(cleaned) == 500 and all(x["Type"] for x in cleaned)         # nothing deleted, no blank Types
    assert len(_read(tmp_path / "out" / "changes.csv")) == len(r.changes) > 1000
    assert len(r.groups) == 49 and len(_read(tmp_path / "out" / "duplicates.csv")) == 99
    html = (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert "Possible duplicates" in html and "KEEP" in html and "<title>Catalog cleaning report</title>" in html


def test_no_llm_leaves_blank_types_and_says_so(tmp_path):
    r = run(SAMPLE, tmp_path, ask=None)
    assert any("not filled" in n for n in r.notes) and any(not x["Type"] for x in r.rows)


def test_llm_setup_error_does_not_lose_the_rest(tmp_path):
    def boom(s, u):
        raise RuntimeError("Ollama call failed")
    r = run(SAMPLE, tmp_path, ask=boom)
    assert any("Ollama call failed" in n for n in r.notes)
    assert (tmp_path / "report.html").exists() and len(_read(tmp_path / "cleaned.csv")) == 500


def test_missing_columns_are_named(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Title,Vendor\nMug,Acme\n", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        run(bad, tmp_path / "out")
    assert "Handle" in str(e.value) and "Variant Price" in str(e.value)


def test_report_escapes_product_text(tmp_path):
    src = tmp_path / "in.csv"
    row = dict.fromkeys(REQUIRED, "")
    row.update({"Handle": "h", "Title": "Mug", "Vendor": "Acme", "Variant Price": "<script>alert(1)</script>"})
    with open(src, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=REQUIRED)
        w.writeheader()
        w.writerow(row)
    run(src, tmp_path / "out")
    html = (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert "<script>alert" not in html and "&lt;script&gt;" in html
