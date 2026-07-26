import base64
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from pillars.models import Finding, Report

_ASSETS_DIR = Path(__file__).parent / "assets"

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
  --accent: #6D5BD0;
  --accent-fg: #ffffff;
  --accent-soft: #efecfd;
  --shadow: 0 1px 2px rgba(20, 16, 40, 0.05), 0 4px 14px rgba(20, 16, 40, 0.05);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #121016;
    --fg: #e8e8ea;
    --muted: #9a9aa2;
    --card-bg: #1c1a24;
    --border: #2c2a36;
    --red: #ff8a80;
    --red-bg: #3a1f1d;
    --amber: #ffca7a;
    --amber-bg: #3a2f16;
    --green: #7fd8a0;
    --green-bg: #16301f;
    --accent: #A78BFA;
    --accent-fg: #17132b;
    --accent-soft: #2a2350;
    --shadow: 0 1px 2px rgba(0, 0, 0, 0.35), 0 6px 18px rgba(0, 0, 0, 0.35);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2.5rem 1.25rem 4rem;
  background: var(--bg);
  color: var(--fg);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
.page-wrap { max-width: 920px; margin: 0 auto; }

.masthead { display: flex; align-items: center; gap: 1.1rem; margin-bottom: 1.75rem; }
.masthead .logo svg { display: block; width: 56px; height: 56px; border-radius: 14px; box-shadow: var(--shadow); }
.masthead h1 { font-size: 1.55rem; margin: 0; letter-spacing: -0.01em; }
.masthead .subtitle { margin: 0.15rem 0 0; color: var(--muted); font-size: 0.9rem; }
.masthead .timestamp { margin: 0.3rem 0 0; color: var(--muted); font-size: 0.78rem; }

.badges { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.75rem; }
.badge {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.4rem 0.85rem; border-radius: 999px; font-size: 0.85rem; font-weight: 600;
  text-decoration: none; box-shadow: var(--shadow);
}
.badge-red { background: var(--red-bg); color: var(--red); }
.badge-amber { background: var(--amber-bg); color: var(--amber); }
.badge-green { background: var(--green-bg); color: var(--green); }
.badge-muted { background: var(--card-bg); color: var(--muted); }

.tabs {
  display: inline-flex; gap: 0.25rem; padding: 0.25rem; margin-bottom: 1.75rem;
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 999px;
}
.tab-btn {
  appearance: none; border: none; cursor: pointer; font: inherit; font-weight: 600;
  font-size: 0.85rem; padding: 0.5rem 1.15rem; border-radius: 999px;
  background: transparent; color: var(--muted); transition: background 0.15s ease, color 0.15s ease;
}
.tab-btn.active { background: var(--accent); color: var(--accent-fg); }
.tab-btn:hover:not(.active) { color: var(--fg); }

.page-transition { animation: pillarsFadeIn 0.15s ease; }
@keyframes pillarsFadeIn {
  from { opacity: 0; transform: translateY(3px); }
  to { opacity: 1; transform: translateY(0); }
}

h2 {
  font-size: 1.05rem; margin: 2.25rem 0 0.9rem; padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 0.55rem;
}
h2:first-child { margin-top: 0; }
h2::before { content: ""; width: 8px; height: 8px; border-radius: 2px; background: var(--accent); flex-shrink: 0; }

.checklist { display: grid; gap: 0.45rem; }
.checklist-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.65rem 0.9rem; background: var(--card-bg); border-radius: 10px;
  font-size: 0.92rem; box-shadow: var(--shadow);
}
.checklist-row .count { color: var(--muted); }

.card {
  background: var(--card-bg); border: 1px solid var(--border); border-left-width: 4px;
  border-radius: 12px; padding: 1rem 1.1rem; margin-bottom: 0.75rem; box-shadow: var(--shadow);
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
  cursor: pointer; padding: 1rem 1.1rem; font-weight: 600; list-style: none;
}
details.card summary::-webkit-details-marker { display: none; }
details.card summary::before { content: "\\25B8  "; }
details.card[open] summary::before { content: "\\25BE  "; }
details.card .card-inner { padding: 0 1.1rem 1rem; }
.passed { color: var(--green); font-size: 0.95rem; }
.empty { color: var(--muted); font-style: italic; }

.diagram-card {
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px;
  padding: 2rem; text-align: center; box-shadow: var(--shadow);
}
.diagram-card img { max-width: 100%; height: auto; border-radius: 10px; background: #fff; padding: 1rem; }
.diagram-caption { color: var(--muted); font-size: 0.85rem; text-align: center; margin: 1rem 0 0; }
"""


def _load_logo() -> str:
    try:
        return (_ASSETS_DIR / "logo.svg").read_text()
    except FileNotFoundError:
        return ""


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


def _overview_page(report: Report) -> str:
    checklist_rows = []
    for pr in report.pillar_results:
        count = len(pr.findings)
        detail = f"{count} finding{'s' if count != 1 else ''}" if count else "clean"
        checklist_rows.append(
            f'<div class="checklist-row"><span>{escape(_label(pr.pillar))}</span>'
            f'<span class="count">{escape(detail)}</span></div>'
        )

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

    return f"""<h2>Pillar review</h2>
  <div class="checklist">
    {"".join(checklist_rows)}
  </div>
  {body_sections}"""


def _architecture_page(diagram_png: bytes) -> str:
    encoded = base64.b64encode(diagram_png).decode("ascii")
    return f"""<div class="diagram-card">
    <img src="data:image/png;base64,{encoded}" alt="Architecture diagram">
  </div>
  <p class="diagram-caption">
    Generated from the same resources and cross-resource references the pillar agents reviewed.
  </p>"""


def render_html_report(report: Report, diagram_png: bytes | None = None) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    badges = [
        f'<a class="badge badge-red" href="#blocking">{len(report.blocking)} blocking</a>',
        f'<a class="badge badge-amber" href="#your-call">{len(report.your_call)} your call</a>',
        f'<span class="badge badge-muted">{len(report.other)} other</span>',
        f'<span class="badge badge-green">{len(report.passed_pillars)} pillars passed</span>',
    ]

    overview_content = _overview_page(report)

    if diagram_png:
        tabs_html = """<nav class="tabs">
    <button type="button" class="tab-btn active" data-page="overview" onclick="pillarsShowPage('overview')">Overview</button>
    <button type="button" class="tab-btn" data-page="architecture" onclick="pillarsShowPage('architecture')">Architecture</button>
  </nav>"""
        pages_html = f"""<section id="page-overview" class="page">
    {overview_content}
  </section>
  <section id="page-architecture" class="page" hidden>
    {_architecture_page(diagram_png)}
  </section>"""
        script_html = """<script>
  function pillarsShowPage(id) {
    document.querySelectorAll('.page').forEach(function (el) {
      var show = el.id === 'page-' + id;
      el.hidden = !show;
      if (show) {
        el.classList.remove('page-transition');
        void el.offsetWidth;
        el.classList.add('page-transition');
      }
    });
    document.querySelectorAll('.tab-btn').forEach(function (el) {
      el.classList.toggle('active', el.dataset.page === id);
    });
  }
  </script>"""
    else:
        tabs_html = ""
        pages_html = f"""<section id="page-overview" class="page">
    {overview_content}
  </section>"""
        script_html = ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The6Pillars Review</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="page-wrap">
  <header class="masthead">
    <div class="logo">{_load_logo()}</div>
    <div>
      <h1>The6Pillars Review</h1>
      <p class="subtitle">AWS Well-Architected multi-agent review</p>
      <p class="timestamp">Generated {timestamp}</p>
    </div>
  </header>
  <div class="badges">
    {"".join(badges)}
  </div>
  {tabs_html}
  {pages_html}
</div>
{script_html}
</body>
</html>"""
