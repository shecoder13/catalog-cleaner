"""Run the cleaner:
  uv run python run.py clean data/sample_catalog.csv [--out out] [--no-llm]
  uv run python run.py review out [--max-items 25]
  uv run python run.py apply out
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))   # the project is not installed, so add src/ to the path

from catalog_cleaner.cli import app  # noqa: E402

if __name__ == "__main__":
    app()
