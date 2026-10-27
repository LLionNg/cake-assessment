from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from src.core.config import load_settings
from src.services.matcher import KOLMatcher
from src.utils.log import setup_logging

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def match(
    facebook: Annotated[str, typer.Option(help="Client Facebook page URL")],
    website: Annotated[str | None, typer.Option(help="Client website URL")] = None,
    top: Annotated[int | None, typer.Option(help="Number of KOLs to return")] = None,
    config: Annotated[Path, typer.Option(help="Path to config.yml")] = Path("config.yml"),
    output: Annotated[Path | None, typer.Option(help="Write the full report as JSON")] = None,
) -> None:

    settings = load_settings(config)
    setup_logging(settings.log_level)
    report = KOLMatcher(settings).run(facebook, website, top)

    console.print(
        f"[bold]{report.brand.brand_name}[/] ({report.brand.industry})  mode: {report.mode}"
    )
    console.print(report.brand.summary)
    table = Table("#", "Score", show_lines=True)
    table.add_column("Profile", no_wrap=True)
    for name in ("Followers", "Tier", "ER", "Reason"):
        table.add_column(name)
    for i, m in enumerate(report.matches, 1):
        table.add_row(
            str(i),
            f"{m.score:.2f}",
            m.creator.url,
            f"{m.creator.followers:,}",
            str(m.metrics.tier),
            f"{m.metrics.engagement_rate:.1%}",
            m.reason,
        )
    console.print(table)

    if output:
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"Saved report to {output}")
