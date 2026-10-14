# catalog-cleaner

Clean a messy product catalog CSV and get a **before/after report** of every change.

Rules do the fixing. An LLM is used only to fill blank product **Types**, and it may only choose from Types that already exist in your file. Nothing is deleted, nothing is invented, and your input file is never modified.

## What it does

| Step | What happens |
|---|---|
| **Clean** | Fixes title casing, units (`2.5 liters` → `2.5 L`, `500 millilitres` → `500 ml`, cm/mm), repeated vendor names in titles, price formats (`Rs. 1,299` → `1299.00`), and tag casing/duplicates. Every edit is recorded with the old value, new value and reason. |
| **Flag** | Things it can't safely fix are left unchanged and listed for review: missing SKUs, prices in a non-INR currency (`$`, `€`, `£`), unreadable prices. |
| **Find duplicates** | Groups products from the same vendor with the same title words in any order, or one small typo. Different numbers or colours never match. Suggests which row to keep (has SKU, then image, then longest description). Nothing is removed. |
| **Fill Types** *(optional)* | For rows with a blank Type, asks an LLM to pick from the Types already in your catalog. Any other answer is rejected and the row is flagged instead. |

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```
uv sync
```

Windows + OneDrive: keep the project outside OneDrive (e.g. `C:\dev\catalog-cleaner`). If uv fails with a hardlink error, run `$env:UV_LINK_MODE="copy"` first.

## Usage

```
uv run python run.py clean data/sample_catalog.csv
uv run python run.py clean my_products.csv --out results
uv run python run.py clean my_products.csv --no-llm
```

| Option | Meaning |
|---|---|
| `--out FOLDER` | Where to write results (default `out`). |
| `--no-llm` | Skip filling blank Types. No API key or Ollama needed. |

Progress lines like `asking the LLM, batch 3 ...` appear while Types are being filled (20 rows per call).

### Output files

| File | Contents |
|---|---|
| `cleaned.csv` | The cleaned catalog, same columns and row order as the input. |
| `changes.csv` | Every edit: `row, handle, field, old, new, reason`. |
| `flags.csv` | Items left unchanged for your review: `row, handle, field, value, issue`. |
| `duplicates.csv` | Duplicate groups with a `keep` / `review` suggestion per row. |
| `report.html` | Open this first: counts, changes by field, review items, duplicates. |

Row numbers match the input CSV (row 1 is the first product).

### Input format

A Shopify-style CSV with these columns (others are preserved):

`Handle, Title, Body (HTML), Vendor, Type, Tags, Variant SKU, Variant Price, Image Src`

A missing column stops the run with a message naming it.

## Agent review (optional)

The cleaner leaves two kinds of problem for a human: prices it could not read (`1299/-`, `Rs 1299 only`) and possible duplicates. The review agent investigates them and **proposes** answers. It never edits your data.

```
uv run python run.py clean data/sample_catalog.csv --no-llm
uv run python run.py review out --max-items 10
# open out/proposals.csv, put "yes" in the approve column for the ones you accept
uv run python run.py apply out
```

| Item | What the agent does | What you get |
|---|---|---|
| Unreadable price | Looks at the row and similar rows, then proposes a number or says `leave`. Code rejects any number that does not already appear in the original text, so it can reinterpret `1299/-` but not guess a price. | A `set_price` proposal you can approve. |
| Duplicate group | Compares the rows and decides `same product`, `different variants` or `unsure`, with a reason. | Advisory verdicts. Nothing is deleted or merged. |

- Tools are read-only (`get_row`, `search_rows`) plus a final `propose`. Each item gets at most 5 turns, then is marked `unresolved`.
- `--max-items` (default 25) caps how many problems are investigated; each one costs several Claude calls. The count is printed before the first call.
- `apply` writes `cleaned_final.csv` and `agent_changes.csv`. It only applies rows marked `yes`, and re-checks each price and that the cell still holds the old value, so a stale or hand-edited proposal is skipped.
- Needs `ANTHROPIC_API_KEY`. Tool use is not supported with the local Ollama model.

## Choosing the LLM for Types

| Setup | How |
|---|---|
| **Claude** (recommended) | Set `ANTHROPIC_API_KEY`. Default model `claude-sonnet-5-5`; override with `CATALOG_MODEL`. |
| **Ollama** (local, free) | Used when no API key is set. Run `ollama serve` and `ollama pull qwen2.5-coder:7b`. Override with `CATALOG_OLLAMA_MODEL` and `OLLAMA_URL`. A 7B model on CPU can take minutes per batch. |

If the LLM is unavailable, the run still completes and the report notes that Types were not filled.

On PowerShell, environment variables last only for that window: `$env:ANTHROPIC_API_KEY="sk-ant-..."`.

## Safety design

- Product text is treated as untrusted data. The model must answer with an allowed Type or `UNKNOWN`; anything else is dropped, so text inside a product description can't inject new values.
- Every change has a reason; the report is generated from the same records that produced the output.
- The report escapes all product text before putting it in HTML.

## Try it on sample data

`data/sample_catalog.csv` is 500 generated rows (seeded) with planted problems: 25 exact and 25 near duplicates, blank Types and SKUs, mixed price formats. Regenerate with `uv run python make_sample.py`.

Without the LLM step it produces about 1,397 changes, 200 flags (6 of them unreadable prices) and 49 duplicate groups, which are exactly the planted duplicates.

## Tests

```
uv run python -m pytest -q
```

64 tests, none need network or an API key (the LLM and the agent are faked).

## Limitations

- Prices are only normalised for INR formats; other currencies are flagged, not converted.
- Duplicate detection is title-based within a vendor; it won't catch the same product listed under different vendors.
- One CSV at a time; variant rows sharing a handle are treated as separate rows.
- Cleaning rules are tuned for English titles.

## Project layout

```
run.py                     entry point
src/catalog_cleaner/
  clean.py                 cleaning rules, Change/Flag records
  duplicates.py            duplicate grouping
  enrich.py                LLM Type filling with strict validation
  llm.py                   Claude or Ollama
  agent.py                 tool-using agent loop and proposal checks
  review.py                review / apply commands' logic, proposals.csv
  pipeline.py              runs everything, writes files
  report.py                HTML report
  cli.py                   command-line options
tests/                     unit and end-to-end tests
```
