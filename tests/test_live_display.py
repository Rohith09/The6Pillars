from pillars.live_display import _pillar_phrase, _reconciler_phrase
from pillars.models import Conflict, Finding, PillarResult


def test_pillar_phrase_no_findings():
    result = PillarResult(pillar="security", findings=[])
    phrase = _pillar_phrase("security", result)
    assert "Security" in phrase
    assert "clean" in phrase
    assert "green" in phrase


def test_pillar_phrase_findings_no_blocking():
    result = PillarResult(
        pillar="cost_optimization",
        findings=[
            Finding(
                resource="aws_db_instance.main",
                severity="warning",
                message="Right-size the instance",
                recommendation="Use a smaller class",
            )
        ],
    )
    phrase = _pillar_phrase("cost_optimization", result)
    assert "Cost Optimization" in phrase
    assert "1 finding" in phrase
    assert "yellow" in phrase
    assert "blocking" not in phrase


def test_pillar_phrase_with_blocking():
    result = PillarResult(
        pillar="security",
        findings=[
            Finding(
                resource="aws_s3_bucket.data",
                severity="blocking",
                message="Public bucket",
                recommendation="Block public access",
            ),
            Finding(
                resource="aws_s3_bucket.data",
                severity="info",
                message="No tags",
                recommendation="Add tags",
            ),
        ],
    )
    phrase = _pillar_phrase("security", result)
    assert "2 issues" in phrase
    assert "1 blocking" in phrase
    assert "red" in phrase


def test_reconciler_phrase_no_conflicts():
    phrase = _reconciler_phrase([])
    assert "no cross-pillar conflicts" in phrase
    assert "green" in phrase


def test_reconciler_phrase_with_conflicts():
    conflicts = [
        Conflict(
            pillars=["reliability", "cost_optimization"],
            resource="aws_db_instance.main",
            summary="Multi-AZ vs cost",
            resolution="Your call",
            verdict="your_call",
        )
    ]
    phrase = _reconciler_phrase(conflicts)
    assert "1 cross-pillar conflict" in phrase
    assert "yellow" in phrase
