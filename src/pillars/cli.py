import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from pillars import terraform
from pillars.agents import runner as agent_runner
from pillars.render import render_report

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """Multi-agent AWS Well-Architected review for your Terraform plan."""


@app.command()
def review(
    path: Path = typer.Argument(
        ..., exists=True, file_okay=False, help="Directory containing your Terraform config"
    ),
    plan_json: Optional[Path] = typer.Option(
        None,
        "--plan-json",
        help="Use a pre-generated `terraform show -json` file instead of running terraform",
    ),
    model: str = typer.Option(
        agent_runner.DEFAULT_MODEL, "--model", help="Anthropic model to use for each agent"
    ),
) -> None:
    """Review a Terraform plan against the 6 AWS Well-Architected pillars."""
    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/] Set it in your environment or a .env file."
        )
        raise typer.Exit(1)

    if plan_json is not None:
        console.print(f"Loading plan from {plan_json}...")
        plan = json.loads(plan_json.read_text())
    else:
        console.print("Synthesizing... (terraform plan)")
        try:
            plan = terraform.run_plan(path)
        except terraform.TerraformError as e:
            console.print(f"[red]{e}[/]")
            raise typer.Exit(1) from e

    resources = terraform.normalize(plan)
    if not resources:
        console.print("No resource changes to review.")
        raise typer.Exit(0)

    console.print(f"✓ {len(resources)} resource change(s)\n")
    console.print("Consulting pillar agents...")

    report = asyncio.run(agent_runner.review(resources, model=model))
    exit_code = render_report(report, console)
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
