"""Run the whole cleaning pipeline and write every output file."""

import csv
from pathlib import Path
from typing import NamedTuple

from catalog_cleaner.clean import clean, read_catalog, write_catalog
from catalog_cleaner.duplicates import find_duplicates
from catalog_cleaner.enrich import fill_types
from catalog_cleaner.report import write_report

REQUIRED = ["Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags", "Variant SKU", "Variant Price", "Image Src"]


class Result(NamedTuple):
    rows: list
    changes: list
    flags: list
    groups: list
    notes: list


def _write(path: Path, header: list[str], records) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(records)


def run(src, out_dir="out", ask=None) -> Result:
    """Read `src`, clean it, and write cleaned.csv, changes.csv, flags.csv, duplicates.csv and report.html to out_dir.
    `ask` is the LLM function used to fill blank Types; None skips that step. The input file is never modified."""
    rows, fields = read_catalog(src)
    missing = [c for c in REQUIRED if c not in fields]
    if missing:
        raise ValueError(f"the CSV is missing columns: {', '.join(missing)}")

    cleaned, changes, flags = clean(rows)
    groups = find_duplicates(cleaned)
    notes = []
    if ask is None:
        notes.append("Blank product Types were not filled (LLM step skipped).")
    else:
        try:
            cleaned, more_changes, more_flags = fill_types(cleaned, ask=ask)
            changes, flags = changes + more_changes, flags + more_flags
        except RuntimeError as e:        # no API key / Ollama not running: keep everything else
            notes.append(f"Blank product Types were not filled: {e}")
    changes.sort(key=lambda c: c.row)
    flags.sort(key=lambda f: f.row)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_catalog(out / "cleaned.csv", cleaned, fields)
    _write(out / "changes.csv", ["row", "handle", "field", "old", "new", "reason"], changes)
    _write(out / "flags.csv", ["row", "handle", "field", "value", "issue"], flags)
    _write(out / "duplicates.csv", ["group", "match", "row", "handle", "title", "suggestion"],
           [(i, g.kind, n, cleaned[n - 1]["Handle"], cleaned[n - 1]["Title"], "keep" if n == g.keep else "review")
            for i, g in enumerate(groups, 1) for n in g.rows])
    write_report(out / "report.html", Path(src).name, cleaned, changes, flags, groups, notes)
    return Result(cleaned, changes, flags, groups, notes)
