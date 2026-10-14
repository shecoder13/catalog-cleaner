"""Write a self-contained HTML report of what the cleaner did."""

from collections import Counter
from html import escape

CSS = """body{font:15px/1.5 system-ui,sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;color:#1a1a1a}
h2{margin-top:2rem}table{border-collapse:collapse;width:100%;margin:.5rem 0}th,td{border-bottom:1px solid #ddd;padding:.35rem .5rem;text-align:left;vertical-align:top}
th{background:#f5f5f5}.cards{display:flex;gap:1rem;flex-wrap:wrap}.card{border:1px solid #ddd;border-radius:8px;padding:.7rem 1rem;min-width:150px}
.card b{display:block;font-size:1.6rem}.keep{color:#0a7d33;font-weight:600}.note{background:#fff8e1;border:1px solid #f0d98c;padding:.5rem .8rem;border-radius:6px;margin:.5rem 0}
.old{color:#b3261e}.new{color:#0a7d33}small{color:#777}
@media(prefers-color-scheme:dark){body{background:#16181c;color:#e6e6e6}th{background:#23262b}th,td,.card{border-color:#3a3d44}.note{background:#3a3320;border-color:#6b5c2a;color:#f3e6b5}.old{color:#ff8a80}.new{color:#7ddc9a}.keep{color:#7ddc9a}}"""


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def write_report(path, source: str, rows: list[dict], changes, flags, groups, notes: list[str]) -> None:
    e = escape
    cards = "".join(f'<div class="card"><b>{v}</b>{k}</div>' for k, v in
                    [("rows", len(rows)), ("changes made", len(changes)), ("flagged for review", len(flags)),
                     ("duplicate groups", len(groups))])
    by_field = Counter(c.field for c in changes)
    by_issue = Counter(f.issue for f in flags)
    sample = [[str(c.row), e(c.field), f'<span class="old">{e(c.old) or "<small>(blank)</small>"}</span>',
               f'<span class="new">{e(c.new)}</span>', e(c.reason)] for c in changes[:40]]
    dup = [[str(i), e(g.kind), "<br>".join(
        f'<span class="keep">KEEP</span> ' + f"row {n}: {e(rows[n - 1]['Title'])}" if n == g.keep
        else f"row {n}: {e(rows[n - 1]['Title'])}" for n in g.rows)] for i, g in enumerate(groups[:50], 1)]
    flagged = [[str(f.row), e(f.field), e(f.value) or "<small>(blank)</small>", e(f.issue)] for f in flags[:40]]
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Catalog cleaning report</title><style>{CSS}</style></head><body>
<h1>Catalog cleaning report</h1><p><small>Source: {e(source)}. Your original file was not modified.</small></p>
<div class="cards">{cards}</div>
{"".join(f'<div class="note">{e(n)}</div>' for n in notes)}
<h2>Changes by field</h2>{_table(["Field", "Changes"], [[e(k), str(v)] for k, v in by_field.most_common()])}
<h2>Needs your review</h2><p>These were left unchanged. Showing {len(flagged)} of {len(flags)}.</p>
{_table(["Issue", "Rows"], [[e(k), str(v)] for k, v in by_issue.most_common()])}{_table(["Row", "Field", "Value", "Issue"], flagged)}
<h2>Possible duplicates</h2><p>Nothing was deleted. Showing {min(len(groups), 50)} of {len(groups)} groups; the suggested row to keep is marked.</p>
{_table(["Group", "Match", "Rows"], dup)}
<h2>Sample of changes</h2><p>Showing {len(sample)} of {len(changes)}. The full list is in changes.csv.</p>
{_table(["Row", "Field", "Before", "After", "Why"], sample)}
</body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
