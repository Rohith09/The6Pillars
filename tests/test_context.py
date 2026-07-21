from pathlib import Path

from pillars.context import load_context


def test_load_context_returns_none_when_nothing_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_context(None) is None


def test_load_context_reads_default_pillars_context_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pillars").mkdir()
    (tmp_path / ".pillars" / "context.md").write_text("DataBucket is a CDN origin.")

    assert load_context(None) == "DataBucket is a CDN origin."


def test_load_context_prefers_explicit_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".pillars").mkdir()
    (tmp_path / ".pillars" / "context.md").write_text("default context")

    explicit = tmp_path / "notes.md"
    explicit.write_text("explicit context")

    assert load_context(explicit) == "explicit context"
