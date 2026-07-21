import io

from rich.console import Console

from pillars.models import Conflict, Finding, PillarResult, Report
from pillars.render import render_report, render_summary


def _make_report() -> Report:
    blocking_finding = Finding(
        resource="aws_s3_bucket.data",
        severity="blocking",
        message="Bucket allows public read access",
        recommendation="Add an aws_s3_bucket_public_access_block resource",
    )
    your_call_finding = Finding(
        resource="aws_db_instance.main",
        severity="blocking",
        message="Single-AZ, no automatic failover",
        recommendation="Set multi_az = true (+~$15/mo)",
    )
    other_finding = Finding(
        resource="aws_db_instance.main",
        severity="info",
        message="No Name tag set",
        recommendation="Add a Name tag for identification",
    )

    pillar_results = [
        PillarResult(pillar="security", findings=[blocking_finding]),
        PillarResult(pillar="reliability", findings=[your_call_finding]),
        PillarResult(pillar="operational_excellence", findings=[other_finding]),
        PillarResult(pillar="cost_optimization", findings=[]),
        PillarResult(pillar="performance_efficiency", findings=[]),
        PillarResult(pillar="sustainability", findings=[]),
    ]
    conflicts = [
        Conflict(
            pillars=["reliability", "cost_optimization"],
            resource="aws_db_instance.main",
            summary="Reliability wants Multi-AZ, Cost flags doubled RDS spend",
            resolution="No clear winner for a personal project — your call",
            verdict="your_call",
        )
    ]

    return Report(
        pillar_results=pillar_results,
        conflicts=conflicts,
        blocking=[blocking_finding],
        your_call=[your_call_finding],
        other=[other_finding],
        passed_pillars=["cost_optimization", "performance_efficiency", "sustainability"],
    )


def test_render_report_sections_and_exit_code():
    report = _make_report()
    buffer = io.StringIO()
    console = Console(file=buffer, width=100, force_terminal=False)

    exit_code = render_report(report, console)
    output = buffer.getvalue()

    assert exit_code == 1  # blocking findings present
    assert "Cross-pillar conflicts" in output
    assert "BLOCKING (1)" in output
    assert "YOUR CALL (1)" in output
    assert "Other findings (1)" in output
    assert "aws_s3_bucket.data" in output
    assert "PASSED" in output


def test_render_report_no_blocking_returns_zero():
    report = Report(
        pillar_results=[PillarResult(pillar="security", findings=[])],
        passed_pillars=["security"],
    )
    buffer = io.StringIO()
    console = Console(file=buffer, width=100, force_terminal=False)

    exit_code = render_report(report, console)
    assert exit_code == 0


def test_render_summary_is_condensed_and_returns_exit_code():
    report = _make_report()
    buffer = io.StringIO()
    console = Console(file=buffer, width=100, force_terminal=False)

    exit_code = render_summary(report, console, "pillars-report.html")
    output = buffer.getvalue()

    assert exit_code == 1
    assert "1 blocking" in output
    assert "1 your call" in output
    assert "pillars-report.html" in output
    # the full per-finding detail should not be in the condensed summary
    assert "Add an aws_s3_bucket_public_access_block resource" not in output
    assert "Cross-pillar conflicts" not in output
