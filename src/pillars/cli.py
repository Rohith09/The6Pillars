import asyncio
import json
import os
import webbrowser
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console

from pillars import cloudformation, context as context_module, terraform
from pillars.agents import runner as agent_runner
from pillars.live_display import review_with_animation
from pillars.render import render_summary
from pillars.render_html import render_html_report

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """Multi-agent AWS Well-Architected review for your Terraform plan."""


@app.command()
def review(
    path: Path = typer.Argument(
        ...,
        exists=True,
        help="Directory containing your Terraform config, or a CloudFormation template file",
    ),
    plan_json: Optional[Path] = typer.Option(
        None,
        "--plan-json",
        help="Use a pre-generated `terraform show -json` file instead of running terraform",
    ),
    model: str = typer.Option(
        agent_runner.DEFAULT_MODEL, "--model", help="Anthropic model to use for each agent"
    ),
    context_path: Optional[Path] = typer.Option(
        None,
        "--context",
        exists=True,
        help="Architecture notes for the agents to weigh (defaults to .pillars/context.md if present)",
    ),
    html_path: Path = typer.Option(
        Path("pillars-report.html"), "--html-path", help="Where to write the HTML report"
    ),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Don't automatically open the HTML report when done"
    ),
) -> None:
    """Review a Terraform plan or CloudFormation template against the 6 AWS Well-Architected
    pillars."""
    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(
            "[red]ANTHROPIC_API_KEY is not set.[/] Set it in your environment or a .env file."
        )
        raise typer.Exit(1)

    if plan_json is not None:
        console.print(f"Loading plan from {plan_json}...")
        plan = json.loads(plan_json.read_text())
        resources = terraform.normalize(plan)
    elif path.is_file():
        console.print(f"Loading CloudFormation template from {path}...")
        template = cloudformation.parse_template(path)
        resources = cloudformation.normalize(template)
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

    console.print(f"✓ {len(resources)} resource change(s)")

    context_text = context_module.load_context(context_path)
    used_context_path = context_path or context_module.DEFAULT_CONTEXT_PATH
    if context_text:
        console.print(f"✓ Using context from {used_context_path}")

    console.print()

    report = asyncio.run(review_with_animation(resources, model, context_text, console))

    html_path.write_text(render_html_report(report))
    exit_code = render_summary(report, console, str(html_path))

    if not no_browser:
        webbrowser.open(f"file://{html_path.resolve()}")

    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
