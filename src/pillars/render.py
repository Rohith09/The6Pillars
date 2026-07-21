from rich.console import Console

from pillars.models import Finding, Report

_ICON_OK = "[green]✓[/]"
_ICON_WARN = "[yellow]⚠[/]"


def _label(pillar: str) -> str:
    return pillar.replace("_", " ").title()


def _print_finding(console: Console, finding: Finding, color: str) -> None:
    console.print(f"  [{color}]•[/] [bold]{finding.resource}[/] — {finding.message}")
    console.print(f"      → {finding.recommendation}")


def _print_checklist(report: Report, console: Console) -> None:
    console.print("[bold]Pillar review[/]")
    for pr in report.pillar_results:
        icon = _ICON_OK if not pr.findings else _ICON_WARN
        count = len(pr.findings)
        blocking_count = sum(1 for f in pr.findings if f.severity == "blocking")
        detail = ""
        if count:
            detail = f"{count} finding{'s' if count != 1 else ''}"
            if blocking_count:
                detail += f" ({blocking_count} blocking)"
        console.print(f"  {icon} {_label(pr.pillar):<24} {detail}")


def render_summary(report: Report, console: Console, html_path: str) -> int:
    """Print a short terminal summary (checklist + counts) and point to the full HTML report.
    Returns an exit code (1 if any blocking findings remain, 0 otherwise)."""
    console.print()
    _print_checklist(report, console)
    console.print(
        f"\n[bold red]{len(report.blocking)}[/] blocking · "
        f"[bold yellow]{len(report.your_call)}[/] your call · "
        f"{len(report.other)} other — see [bold]{html_path}[/]\n"
    )
    return 1 if report.blocking else 0


def render_report(report: Report, console: Console | None = None) -> int:
    """Print the full triaged report to the terminal. Returns an exit code (1 if any
    blocking findings remain, 0 otherwise)."""
    console = console or Console()

    console.print()
    _print_checklist(report, console)

    if report.conflicts:
        console.print()
        console.rule("[bold yellow]Cross-pillar conflicts[/]")
        for c in report.conflicts:
            pillars_str = " ↔ ".join(_label(p) for p in c.pillars)
            console.print(f"[bold]{pillars_str}[/] — {c.resource}")
            console.print(f"  {c.summary}")
            verdict = "[green]adopted[/]" if c.verdict == "adopt" else "[yellow]your call[/]"
            console.print(f"  → {verdict}: {c.resolution}")
            console.print()

    if report.blocking:
        console.print()
        console.rule(f"[bold red]BLOCKING ({len(report.blocking)})[/]")
        for f in report.blocking:
            _print_finding(console, f, "red")

    if report.your_call:
        console.print()
        console.rule(f"[bold yellow]YOUR CALL ({len(report.your_call)})[/]")
        for f in report.your_call:
            _print_finding(console, f, "yellow")

    if report.other:
        console.print()
        console.rule(f"[dim]Other findings ({len(report.other)})[/]")
        for f in report.other:
            _print_finding(console, f, "dim")

    if report.passed_pillars:
        console.print()
        names = ", ".join(_label(p) for p in report.passed_pillars)
        console.print(f"[green]PASSED[/] — {names} clean")

    console.print()
    return 1 if report.blocking else 0
