import asyncio

from anthropic import AsyncAnthropic
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table

from pillars.agents.runner import build_report, run_pillar_agent, run_reconciler
from pillars.models import PILLARS, Conflict, PillarResult, Report, ResourceChange

_RECONCILER_KEY = "__reconciler__"

_PILLAR_META: dict[str, tuple[str, str]] = {
    "security": ("🔒", "Security"),
    "reliability": ("🛡️", "Reliability"),
    "performance_efficiency": ("⚡", "Performance Efficiency"),
    "cost_optimization": ("💰", "Cost Optimization"),
    "operational_excellence": ("🛠️", "Operational Excellence"),
    "sustainability": ("🌱", "Sustainability"),
    _RECONCILER_KEY: ("🧭", "Reconciler"),
}

_ROW_ORDER = [*PILLARS, _RECONCILER_KEY]


def _pillar_phrase(pillar: str, result: PillarResult) -> str:
    emoji, label = _PILLAR_META[pillar]
    count = len(result.findings)
    blocking = sum(1 for f in result.findings if f.severity == "blocking")

    if count == 0:
        return f"{emoji} [green]{label} agent[/]: looks clean, no findings."
    if blocking:
        plural = "s" if count != 1 else ""
        return f"{emoji} [red]{label} agent[/]: found {count} issue{plural} — {blocking} blocking."
    plural = "s" if count != 1 else ""
    return f"{emoji} [yellow]{label} agent[/]: found {count} finding{plural} worth a look."


def _reconciler_phrase(conflicts: list[Conflict]) -> str:
    emoji, label = _PILLAR_META[_RECONCILER_KEY]
    if not conflicts:
        return f"{emoji} [green]{label} agent[/]: no cross-pillar conflicts, all clear."
    plural = "s" if len(conflicts) != 1 else ""
    return f"{emoji} [yellow]{label} agent[/]: found {len(conflicts)} cross-pillar conflict{plural} to weigh in on."


def _render(lines: dict[str, str | None]) -> Table:
    table = Table.grid(padding=(0, 1))
    for key in _ROW_ORDER:
        line = lines[key]
        if line is None:
            emoji, label = _PILLAR_META[key]
            table.add_row(
                Spinner("dots", style="dim"), f"[dim]{emoji} {label} agent is reviewing...[/]"
            )
        else:
            table.add_row(" ", line)
    return table


async def _labeled_pillar(
    client: AsyncAnthropic,
    pillar: str,
    resources: list[ResourceChange],
    model: str,
    context: str | None,
) -> tuple[str, PillarResult]:
    result = await run_pillar_agent(client, pillar, resources, model, context)
    return pillar, result


async def review_with_animation(
    resources: list[ResourceChange],
    model: str,
    context: str | None,
    console: Console,
) -> Report:
    """Run the 6 pillar agents + reconciler while animating a live terminal feed: each row
    starts as a spinner and flips to a real result-derived line the moment that agent's actual
    API call completes."""
    lines: dict[str, str | None] = {key: None for key in _ROW_ORDER}

    async with AsyncAnthropic() as client:
        with Live(_render(lines), console=console, refresh_per_second=8) as live:
            coros = [
                _labeled_pillar(client, pillar, resources, model, context) for pillar in PILLARS
            ]
            pillar_results: list[PillarResult] = []
            for coro in asyncio.as_completed(coros):
                pillar, result = await coro
                pillar_results.append(result)
                lines[pillar] = _pillar_phrase(pillar, result)
                live.update(_render(lines))

            pillar_results.sort(key=lambda r: PILLARS.index(r.pillar))

            conflicts = await run_reconciler(client, pillar_results, model, context)
            lines[_RECONCILER_KEY] = _reconciler_phrase(conflicts)
            live.update(_render(lines))

    return build_report(pillar_results, conflicts)
