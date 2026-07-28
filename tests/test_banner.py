from rich.console import Console

from pillars.banner import _gradient_color, _hex_to_rgb, print_banner


def test_hex_to_rgb():
    assert _hex_to_rgb("#2DD4BF") == (0x2D, 0xD4, 0xBF)


def test_gradient_color_endpoints_match_anchors():
    assert _gradient_color(0.0).lower() == "#2dd4bf"
    assert _gradient_color(1.0).lower() == "#fb7185"


def test_gradient_color_is_a_valid_hex_color_mid_range():
    color = _gradient_color(0.5)
    assert color.startswith("#")
    assert len(color) == 7
    int(color[1:], 16)  # doesn't raise


def test_print_banner_does_not_crash_and_prints_something():
    console = Console(record=True, width=80)
    print_banner(console)
    output = console.export_text()
    assert output.strip()
    assert "AWS Well-Architected review" in output
