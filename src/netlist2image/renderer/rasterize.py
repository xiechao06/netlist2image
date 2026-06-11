"""Rasterize SVG to PNG using cairosvg."""

from __future__ import annotations

from typing import Tuple

import cairosvg


def rasterize_svg(svg_string: str, width: int = 3840, height: int = 2160) -> bytes:
    """Convert an SVG string to PNG bytes."""
    return cairosvg.svg2png(
        bytestring=svg_string.encode("utf-8"),
        output_width=width,
        output_height=height,
    )
