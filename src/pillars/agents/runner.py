import asyncio
import json
from pathlib import Path

from anthropic import AsyncAnthropic

from pillars.models import (
    PILLARS,
    Conflict,
    Finding,
    PillarResult,
    Report,
    ResourceChange,
)

RUBRICS_DIR = Path(__file__).parent / "rubrics"
DEFAULT_MODEL = "claude-sonnet-5"

_PILLAR_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "resource": {"type": "string"},
                    "severity": {"type": "string", "enum": ["blocking", "warning", "info"]},
                    "message": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
                "required": ["resource", "severity", "message", "recommendation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["findings"],
    "additionalProperties": False,
}

_CONFLICTS_SCHEMA = {
    "type": "object",
    "properties": {
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pillars": {"type": "array", "items": {"type": "string"}},
                    "resource": {"type": "string"},
                    "summary": {"type": "string"},
                    "resolution": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["adopt", "your_call"]},
                },
                "required": ["pillars", "resource", "summary", "resolution", "verdict"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["conflicts"],
    "additionalProperties": False,
}

_RECONCILER_SYSTEM_PROMPT = """You are the reconciler on an AWS Well-Architected review panel. \
You are given the findings from 6 specialist pillar reviewers (security, reliability, \
performance_efficiency, cost_optimization, operational_excellence, sustainability) on the same \
Terraform plan.

Your only job: find cases where two or more pillars have findings on the SAME resource whose \
recommendations are in tension (fixing one pillar's finding would work against another \
pillar's finding — e.g. Security wants encryption Cost flags as needless spend, or Reliability \
wants Multi-AZ Cost flags as doubled spend).

For each such conflict:
- If one side is clearly right given typical priorities (e.g. a trivial cost delta vs a real \
security exposure), resolve it: set verdict "adopt" and explain the resolution.
- If it's a genuine tradeoff with no objectively correct answer for a project whose scale and \
priorities you don't know (this is a personal/learning project, not a company with fixed SLAs), \
set verdict "your_call" and explain the tradeoff neutrally so the user can decide.

Do not restate findings that have no cross-pillar tension — only report actual conflicts. If \
there are none, return an empty list.
"""


def _load_rubric(pillar: str) -> str:
    return (RUBRICS_DIR / f"{pillar}.md").read_text()


def _resources_payload(resources: list[ResourceChange]) -> str:
    return json.dumps([r.model_dump(exclude_none=True) for r in resources], indent=2)


async def run_pillar_agent(
    client: AsyncAnthropic, pillar: str, resources: list[ResourceChange], model: str
) -> PillarResult:
    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=_load_rubric(pillar),
        messages=[
            {
                "role": "user",
                "content": (
                    "Here is the Terraform plan's resource changes as JSON. Review them per "
                    "your pillar's checklist and return findings.\n\n"
                    + _resources_payload(resources)
                ),
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": _PILLAR_RESULT_SCHEMA}},
    )
    data = json.loads(message.content[0].text)
    findings = [Finding(**f) for f in data["findings"]]
    return PillarResult(pillar=pillar, findings=findings)


async def run_all_pillars(
    client: AsyncAnthropic, resources: list[ResourceChange], model: str
) -> list[PillarResult]:
    return list(
        await asyncio.gather(
            *(run_pillar_agent(client, pillar, resources, model) for pillar in PILLARS)
        )
    )


async def run_reconciler(
    client: AsyncAnthropic, pillar_results: list[PillarResult], model: str
) -> list[Conflict]:
    payload = json.dumps([pr.model_dump() for pr in pillar_results], indent=2)
    message = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=_RECONCILER_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": "Here are all pillar findings as JSON:\n\n" + payload}
        ],
        output_config={"format": {"type": "json_schema", "schema": _CONFLICTS_SCHEMA}},
    )
    data = json.loads(message.content[0].text)
    return [Conflict(**c) for c in data["conflicts"]]


def build_report(pillar_results: list[PillarResult], conflicts: list[Conflict]) -> Report:
    """Assemble the final Report deterministically from pillar findings + the reconciler's
    conflict list, rather than trusting the reconciler to re-copy findings verbatim."""
    your_call_resources = {c.resource for c in conflicts if c.verdict == "your_call"}

    blocking: list[Finding] = []
    your_call: list[Finding] = []
    other: list[Finding] = []
    for pr in pillar_results:
        for finding in pr.findings:
            if finding.resource in your_call_resources:
                your_call.append(finding)
            elif finding.severity == "blocking":
                blocking.append(finding)
            else:
                other.append(finding)

    passed_pillars = [pr.pillar for pr in pillar_results if not pr.findings]

    return Report(
        pillar_results=pillar_results,
        conflicts=conflicts,
        blocking=blocking,
        your_call=your_call,
        other=other,
        passed_pillars=passed_pillars,
    )


async def review(resources: list[ResourceChange], model: str = DEFAULT_MODEL) -> Report:
    async with AsyncAnthropic() as client:
        pillar_results = await run_all_pillars(client, resources, model)
        conflicts = await run_reconciler(client, pillar_results, model)
    return build_report(pillar_results, conflicts)
