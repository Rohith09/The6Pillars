from pathlib import Path

DEFAULT_CONTEXT_PATH = Path(".pillars/context.md")


def load_context(explicit: Path | None) -> str | None:
    """Load user-supplied architecture context. Returns the explicit file's contents if given,
    otherwise the default `.pillars/context.md` in the current directory if it exists, otherwise
    None (context is optional)."""
    path = explicit or DEFAULT_CONTEXT_PATH
    if not path.exists():
        return None
    return path.read_text()
