"""First live test of the LLM step: fills blank Types in the sample catalog.
Needs ANTHROPIC_API_KEY set (or Ollama running). Run from the project folder: uv run python try_enrich.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))   # the project is not installed, so add src/ to the path

from catalog_cleaner.clean import clean, read_catalog, write_catalog  # noqa: E402
from catalog_cleaner.enrich import fill_types  # noqa: E402

rows, fields = read_catalog("data/sample_catalog.csv")
cleaned, _, _ = clean(rows)
filled, changes, flags = fill_types(cleaned)

Path("out").mkdir(exist_ok=True)
write_catalog("out/sample_with_types.csv", filled, fields)
print(f"{len(changes)} types filled, {len(flags)} flagged -> out/sample_with_types.csv")
for c in changes[:5]:
    print(f"  row {c.row}: {c.old!r} -> {c.new!r}   ({c.reason})")
for f in flags[:5]:
    print(f"  FLAG row {f.row}: {f.issue}")
