"""Agent review: build work items from a cleaning run's output, write proposals.csv, and apply the approved ones."""

import csv
from pathlib import Path

from catalog_cleaner.agent import check_price, investigate
from catalog_cleaner.clean import read_catalog, write_catalog

HEADER = ["item", "kind", "rows", "field", "old", "new", "verdict", "reason", "status", "approve"]


def _read(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def work_items(out: Path, rows: list[dict]) -> list[tuple[str, list[int], str, str]]:
    """(kind, rows, task text, old value): unreadable prices first, then duplicate groups."""
    items = []
    for f in _read(out / "flags.csv"):
        if f["issue"] == "price could not be read":
            n = int(f["row"])
            items.append(("price", [n], f"Row {n} has the price text {f['value']!r}, which the cleaner could not read. "
                          "If it clearly contains exactly one INR price, propose it with set_price. Otherwise use leave.", f["value"]))
    groups: dict[str, list[dict]] = {}
    for d in _read(out / "duplicates.csv"):
        groups.setdefault(d["group"], []).append(d)
    for g in groups.values():
        ns = [int(d["row"]) for d in g]
        items.append(("duplicate", ns, f"Rows {ns} were grouped as possible duplicates ({g[0]['match']}). Compare them with get_row "
                      "and decide: same product (one item listed twice), different variants (size, colour or model), or unsure.", ""))
    return items


def review(out_dir, chat, max_items: int = 25, log=print) -> int:
    """Investigate up to max_items problems and write proposals.csv. Returns the number of items reviewed."""
    out = Path(out_dir)
    rows, _ = read_catalog(out / "cleaned.csv")
    items = work_items(out, rows)
    log(f"{len(items)} items need review; reviewing {min(len(items), max_items)}")
    records = []
    for k, (kind, ns, task, old) in enumerate(items[:max_items], 1):
        log(f"  [{k}] {kind} {ns} ...")
        p = investigate(kind, ns, task, old, rows, chat)
        field = "Variant Price" if kind == "price" else ""
        records.append([k, kind, ";".join(map(str, ns)), field, old, p.value, p.verdict, p.reason, p.status, ""])
    with open(out / "proposals.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(records)
    return len(records)


def apply(out_dir) -> tuple[int, int, int]:
    """Apply proposals marked approve=yes. Returns (prices changed, duplicate verdicts approved, skipped)."""
    out = Path(out_dir)
    rows, fields = read_catalog(out / "cleaned.csv")
    done, notes, skipped = [], 0, 0
    for p in _read(out / "proposals.csv"):
        if p["approve"].strip().lower() != "yes" or p["status"] != "proposed":
            continue
        if p["kind"] == "duplicate":
            notes += 1
            continue
        n = int(p["rows"])
        ok = (p["verdict"] == "set_price" and 1 <= n <= len(rows) and rows[n - 1]["Variant Price"] == p["old"]
              and not check_price(p["old"], p["new"]))          # re-checked: the CSV may have been edited by hand
        if not ok:
            skipped += 1
            continue
        rows[n - 1]["Variant Price"] = f"{float(p['new']):.2f}"
        done.append([n, rows[n - 1]["Handle"], "Variant Price", p["old"], rows[n - 1]["Variant Price"], "agent: " + p["reason"]])
    write_catalog(out / "cleaned_final.csv", rows, fields)
    with open(out / "agent_changes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["row", "handle", "field", "old", "new", "reason"])
        w.writerows(done)
    return len(done), notes, skipped
