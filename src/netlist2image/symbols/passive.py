"""Passive component symbols: R, C, L, V, I."""

from netlist2image.symbols.base import SymbolDef

# Larger symbols for readability
_W = 120
_H = 60

RESISTOR = SymbolDef(
    width=_W,
    height=_H,
    pins=[(-_W / 2, 0), (_W / 2, 0)],
    svg_paths=[
        # Zig-zag resistor — larger and cleaner
        "M -60 0 L -48 -18 L -36 18 L -24 -18 L -12 18 L 0 -18 L 12 18 L 24 -18 L 36 18 L 48 -18 L 60 0",
    ],
)

CAPACITOR = SymbolDef(
    width=_W,
    height=_H,
    pins=[(-_W / 2, 0), (_W / 2, 0)],
    svg_paths=[
        # Two parallel lines — thicker gap
        "M -60 0 L -12 0",
        "M -12 -24 L -12 24",
        "M 12 -24 L 12 24",
        "M 12 0 L 60 0",
    ],
)

INDUCTOR = SymbolDef(
    width=_W,
    height=_H,
    pins=[(-_W / 2, 0), (_W / 2, 0)],
    svg_paths=[
        # Coiled inductor
        "M -60 0 L -48 0",
        "M -48 0 Q -48 -18 -36 -18 Q -24 -18 -24 0",
        "M -24 0 Q -24 -18 -12 -18 Q 0 -18 0 0",
        "M 0 0 Q 0 -18 12 -18 Q 24 -18 24 0",
        "M 24 0 Q 24 -18 36 -18 Q 48 -18 48 0",
        "M 48 0 L 60 0",
    ],
)

# Voltage source: circle with + and −
VOLTAGE_SOURCE = SymbolDef(
    width=80,
    height=80,
    pins=[(-40, 0), (40, 0)],
    svg_paths=[
        "M 0 0 m -28 0 a 28 28 0 1 0 56 0 a 28 28 0 1 0 -56 0",
        "M -8 -12 L -8 12",
        "M -14 0 L -2 0",
        "M 8 -8 L 8 8",
    ],
)

# Current source: circle with arrow
CURRENT_SOURCE = SymbolDef(
    width=80,
    height=80,
    pins=[(-40, 0), (40, 0)],
    svg_paths=[
        "M 0 0 m -28 0 a 28 28 0 1 0 56 0 a 28 28 0 1 0 -56 0",
        # Arrow pointing down
        "M 0 -14 L 0 14 L -6 8 M 0 14 L 6 8",
    ],
)
