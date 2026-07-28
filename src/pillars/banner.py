import pyfiglet
from rich.console import Console
from rich.text import Text

# Same hues as the column gradients in logo.svg / the HTML report's accent family, used as
# anchor points for a smooth left-to-right gradient across the big banner text.
_GRADIENT_ANCHORS = ["#2DD4BF", "#38BDF8", "#818CF8", "#A78BFA", "#E879F9", "#FB7185"]
_FONT = "big"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def _lerp(a: int, b: int, t: float) -> int:
    return round(a + (b - a) * t)


def _gradient_color(t: float) -> str:
    """t in [0, 1] -> an interpolated hex color across the anchor list."""
    anchors = [_hex_to_rgb(c) for c in _GRADIENT_ANCHORS]
    segments = len(anchors) - 1
    scaled = min(max(t, 0.0), 1.0) * segments
    i = min(int(scaled), segments - 1)
    local_t = scaled - i
    r1, g1, b1 = anchors[i]
    r2, g2, b2 = anchors[i + 1]
    r, g, b = _lerp(r1, r2, local_t), _lerp(g1, g2, local_t), _lerp(b1, b2, local_t)
    return f"#{r:02x}{g:02x}{b:02x}"


def print_banner(console: Console) -> None:
    """Print a big figlet-style banner with a smooth horizontal gradient across it (matching
    the logo's palette), once at the start of a review, before anything else prints."""
    art = pyfiglet.figlet_format("6 PILLARS", font=_FONT)
    lines = art.rstrip("\n").split("\n")
    width = max((len(line) for line in lines), default=1)

    console.print()
    for line in lines:
        text = Text()
        for x, char in enumerate(line):
            if char == " ":
                text.append(" ")
            else:
                text.append(char, style=_gradient_color(x / max(width - 1, 1)))
        console.print(text)
    console.print("[dim]  AWS Well-Architected review, six agents at a time[/]")
    console.print()
