from typing import Literal

from pydantic import BaseModel, Field

PILLARS: list[str] = [
    "security",
    "reliability",
    "performance_efficiency",
    "cost_optimization",
    "operational_excellence",
    "sustainability",
]

Severity = Literal["blocking", "warning", "info"]


class ResourceChange(BaseModel):
    address: str
    type: str
    name: str
    provider: str
    actions: list[str]
    after: dict | None = None
    references: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    resource: str
    severity: Severity
    message: str
    recommendation: str


class PillarResult(BaseModel):
    pillar: str
    findings: list[Finding] = Field(default_factory=list)


class Conflict(BaseModel):
    pillars: list[str]
    resource: str
    summary: str
    resolution: str
    verdict: Literal["adopt", "your_call"]


class Report(BaseModel):
    pillar_results: list[PillarResult]
    conflicts: list[Conflict] = Field(default_factory=list)
    blocking: list[Finding] = Field(default_factory=list)
    your_call: list[Finding] = Field(default_factory=list)
    other: list[Finding] = Field(default_factory=list)
    passed_pillars: list[str] = Field(default_factory=list)
