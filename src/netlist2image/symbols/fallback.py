"""Fallback black-box symbol for unrecognized elements."""

from netlist2image.symbols.base import SymbolDef

BLACK_BOX = SymbolDef(
    width=80,
    height=60,
    pins=[(-40, 0), (40, 0), (0, -30), (0, 30)],  # generic 4 pins
    svg_paths=[
        "M -40 -30 L 40 -30 L 40 30 L -40 30 Z",
    ],
)
