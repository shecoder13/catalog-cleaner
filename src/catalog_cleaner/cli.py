"""Command line: clean a Shopify-style product CSV and write the results to an output folder."""

from pathlib import Path

import typer

from catalog_cleaner.llm import chat, generate
from catalog_cleaner.pipeline import run
from catalog_cleaner.review import apply, review

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("clean")
def main(
    csv_file: Path = typer.Argument(..., exists=True, dir_okay=False, help="Product CSV to clean"),
    out: Path = typer.Option(Path("out"), help="Folder for the results"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip filling blank Types with an LLM"),
):
    """Clean a product CSV. Writes cleaned.csv, changes.csv, flags.csv, duplicates.csv and report.html."""
    calls = 0

    def ask(system: str, user: str) -> str:
        nonlocal calls
        calls += 1
        typer.echo(f"  asking the LLM, batch {calls} ...", err=True)
        return generate(system, user)

    try:
        r = run(csv_file, out, None if no_llm else ask)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{len(r.rows)} rows | {len(r.changes)} changes | {len(r.flags)} flagged | {len(r.groups)} duplicate groups")
    for note in r.notes:
        typer.echo(f"note: {note}")
    typer.echo(f"results in {out}{'/' if not str(out).endswith('/') else ''}  (open report.html first)")


@app.command("review")
def review_cmd(
    out: Path = typer.Argument(..., exists=True, file_okay=False, help="Results folder from `clean`"),
    max_items: int = typer.Option(25, help="Most problems to investigate (each costs several LLM calls)"),
):
    """Let the agent investigate unreadable prices and possible duplicates. Writes proposals.csv; changes nothing else."""
    try:
        n = review(out, chat, max_items, log=lambda s: typer.echo(s, err=True))
    except (RuntimeError, FileNotFoundError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1)
    typer.echo(f"{n} proposals written to {out / 'proposals.csv'}. Put 'yes' in the approve column, then run `apply`.")


@app.command("apply")
def apply_cmd(out: Path = typer.Argument(..., exists=True, file_okay=False, help="Results folder")):
    """Apply the proposals you marked approve=yes. Writes cleaned_final.csv and agent_changes.csv."""
    prices, dups, skipped = apply(out)
    typer.echo(f"{prices} prices changed, {dups} duplicate verdicts approved (advisory, no data changed), {skipped} skipped")
    typer.echo(f"wrote {out / 'cleaned_final.csv'}")
