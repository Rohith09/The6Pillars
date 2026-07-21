from datetime import datetime, timezone
from html import escape

from pillars.models import Finding, Report

_STYLE = """
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --fg: #1a1a1a;
  --muted: #666666;
  --card-bg: #f6f6f7;
  --border: #e2e2e4;
  --red: #b3261e;
  --red-bg: #fbeceb;
  --amber: #8a5a00;
  --amber-bg: #fdf3e2;
  --green: #1e6b3a;
  --green-bg: #eaf6ee;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14151a;
    --fg: #e8e8ea;
    --muted: #9a9aa2;
    --card-bg: #1d1e24;
    --border: #2c2d34;
    --red: #ff8a80;
    --red-bg: #3a1f1d;
    --amber: #ffca7a;
    --amber-bg: #3a2f16;
    --green: #7fd8a0;
    --green-bg: #16301f;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2rem 1rem 4rem;
  background: var(--bg);
  color: var(--fg);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
main { max-width: 860px; margin: 0 auto; }
h1 { font-size: 1.4rem; margin: 0 0 0.25rem; }
.timestamp { color: var(--muted); font-size: 0.85rem; margin: 0 0 1.5rem; }
.badges { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 2rem; }
.badge {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.35rem 0.75rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;
  text-decoration: none;
}
.badge-red { background: var(--red-bg); color: var(--red); }
.badge-amber { background: var(--amber-bg); color: var(--amber); }
.badge-green { background: var(--green-bg); color: var(--green); }
.badge-muted { background: var(--card-bg); color: var(--muted); }
h2 {
  font-size: 1.05rem; margin: 2.5rem 0 0.75rem; padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border);
}
.checklist { display: grid; gap: 0.4rem; }
.checklist-row {
  display: flex; justify-content: space-between; padding: 0.5rem 0.75rem;
  background: var(--card-bg); border-radius: 8px; font-size: 0.9rem;
}
.checklist-row .count { color: var(--muted); }
.card {
  background: var(--card-bg); border: 1px solid var(--border); border-left-width: 4px;
  border-radius: 8px; padding: 0.85rem 1rem; margin-bottom: 0.75rem;
}
.card-red { border-left-color: var(--red); }
.card-amber { border-left-color: var(--amber); }
.card-muted { border-left-color: var(--border); }
.resource {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85rem; font-weight: 600;
}
.message { margin: 0.35rem 0; }
.recommendation { color: var(--muted); font-size: 0.9rem; }
.recommendation::before { content: "\\2192  "; }
.conflict-pillars { font-weight: 600; font-size: 0.9rem; }
.verdict {
  display: inline-block; margin-top: 0.4rem; padding: 0.15rem 0.5rem;
  border-radius: 6px; font-size: 0.78rem; font-weight: 600;
}
details.card { padding: 0; }
details.card summary {
  cursor: pointer; padding: 0.85rem 1rem; font-weight: 600; list-style: none;
}
details.card summary::-webkit-details-marker { display: none; }
details.card summary::before { content: "\\25B8  "; }
details.card[open] summary::before { content: "\\25BE  "; }
details.card .card-inner { padding: 0 1rem 0.85rem; }
.passed { color: var(--green); font-size: 0.95rem; }
.empty { color: var(--muted); font-style: italic; }
"""


def _label(pillar: str) -> str:
    return pillar.replace("_", " ").title()


def _finding_card(f: Finding, accent: str) -> str:
    return f"""<div class="card card-{accent}">
  <div class="resource">{escape(f.resource)}</div>
  <p class="message">{escape(f.message)}</p>
  <p class="recommendation">{escape(f.recommendation)}</p>
</div>"""


def _section(title: str, anchor: str, findings: list[Finding], accent: str) -> str:
    if not findings:
        return ""
    cards = "\n".join(_finding_card(f, accent) for f in findings)
    return f"""<h2 id="{anchor}">{escape(title)} ({len(findings)})</h2>
{cards}"""


def _other_section(findings: list[Finding]) -> str:
    if not findings:
        return ""
    cards = "\n".join(_finding_card(f, "muted") for f in findings)
    return f"""<h2>Other findings ({len(findings)})</h2>
<details class="card card-muted">
  <summary>Show {len(findings)} lower-priority finding{"s" if len(findings) != 1 else ""}</summary>
  <div class="card-inner">
{cards}
  </div>
</details>"""


def _conflicts_section(report: Report) -> str:
    if not report.conflicts:
        return ""
    cards = []
    for c in report.conflicts:
        verdict_class = "badge-green" if c.verdict == "adopt" else "badge-amber"
        verdict_label = "adopted" if c.verdict == "adopt" else "your call"
        pillars_str = " &harr; ".join(escape(_label(p)) for p in c.pillars)
        cards.append(f"""<div class="card card-amber">
  <div class="conflict-pillars">{pillars_str} &mdash; <span class="resource">{escape(c.resource)}</span></div>
  <p class="message">{escape(c.summary)}</p>
  <p class="recommendation">{escape(c.resolution)}</p>
  <span class="verdict {verdict_class}">{verdict_label}</span>
</div>""")
    return f"""<h2>Cross-pillar conflicts ({len(report.conflicts)})</h2>
{"".join(cards)}"""


def render_html_report(report: Report) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    checklist_rows = []
    for pr in report.pillar_results:
        count = len(pr.findings)
        detail = f"{count} finding{'s' if count != 1 else ''}" if count else "clean"
        checklist_rows.append(
            f'<div class="checklist-row"><span>{escape(_label(pr.pillar))}</span>'
            f'<span class="count">{escape(detail)}</span></div>'
        )

    badges = [
        f'<a class="badge badge-red" href="#blocking">{len(report.blocking)} blocking</a>',
        f'<a class="badge badge-amber" href="#your-call">{len(report.your_call)} your call</a>',
        f'<span class="badge badge-muted">{len(report.other)} other</span>',
        f'<span class="badge badge-green">{len(report.passed_pillars)} pillars passed</span>',
    ]

    blocking_html = _section("Blocking", "blocking", report.blocking, "red")
    your_call_html = _section("Your call", "your-call", report.your_call, "amber")
    other_html = _other_section(report.other)
    conflicts_html = _conflicts_section(report)

    passed_html = ""
    if report.passed_pillars:
        names = ", ".join(escape(_label(p)) for p in report.passed_pillars)
        passed_html = f'<p class="passed">&#10003; PASSED &mdash; {names} clean</p>'

    body_sections = "\n".join(
        s for s in (conflicts_html, blocking_html, your_call_html, other_html, passed_html) if s
    )
    if not body_sections:
        body_sections = '<p class="empty">No findings.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The6Pillars Review</title>
<style>{_STYLE}</style>
</head>
<body>
<main>
  <h1>The6Pillars Review</h1>
  <p class="timestamp">Generated {timestamp}</p>
  <div class="badges">
    {"".join(badges)}
  </div>
  <h2>Pillar review</h2>
  <div class="checklist">
    {"".join(checklist_rows)}
  </div>
  {body_sections}
</main>
</body>
</html>"""
