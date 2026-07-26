from pillars.models import Conflict, Finding, PillarResult, Report
from pillars.render_html import render_html_report


def _make_report(message: str = "Bucket allows public read access") -> Report:
    blocking_finding = Finding(
        resource="aws_s3_bucket.data",
        severity="blocking",
        message=message,
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
        passed_pillars=["cost_optimization"],
    )


def test_render_html_report_is_well_formed():
    html = render_html_report(_make_report())

    assert html.startswith("<!doctype html>")
    assert "aws_s3_bucket.data" in html
    assert "aws_db_instance.main" in html
    assert "<details" in html  # other findings collapsed by default
    assert "PASSED" in html


def test_render_html_report_escapes_untrusted_finding_text():
    html = render_html_report(_make_report(message="<script>alert(1)</script>"))

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_html_report_handles_empty_report():
    empty = Report(pillar_results=[PillarResult(pillar="security", findings=[])])
    html = render_html_report(empty)

    assert html.startswith("<!doctype html>")
    assert "No findings." in html


def test_render_html_report_omits_tab_bar_when_no_diagram():
    html = render_html_report(_make_report(), diagram_png=None)
    assert "Architecture" not in html
    assert "data:image/png;base64," not in html
    assert 'class="tabs"' not in html
    assert 'id="page-architecture"' not in html


def test_render_html_report_adds_architecture_tab_when_diagram_present():
    html = render_html_report(_make_report(), diagram_png=b"\x89PNG\r\n\x1a\nfake")
    assert 'class="tabs"' in html
    assert 'id="page-overview"' in html
    assert 'id="page-architecture"' in html
    assert ">Architecture<" in html
    assert "data:image/png;base64," in html
    assert "pillarsShowPage" in html


def test_render_html_report_inlines_logo_svg_in_header():
    html = render_html_report(_make_report())
    assert '<div class="logo"><svg' in html
