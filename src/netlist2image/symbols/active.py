"""Active component symbols: D, Q, M, J."""

from netlist2image.symbols.base import SymbolDef

DIODE = SymbolDef(
    width=60,
    height=40,
    pins=[(-30, 0), (30, 0)],
    svg_paths=[
        "M -30 0 L -10 0",
        "M -10 -12 L -10 12 L 10 0 Z",  # triangle
        "M 10 -12 L 10 12",             # bar
        "M 10 0 L 30 0",
    ],
)

# NPN BJT
# SPICE pin order: collector, base, emitter  →  symbol pins [C, B, E]
NPN = SymbolDef(
    width=60,
    height=80,
    pins=[(-30, -30), (30, 0), (-30, 30)],
    svg_paths=[
        # Base line
        "M -30 0 L -10 0",
        # Collector line up-left
        "M -10 -10 L 30 -30",
        # Emitter line down-left
        "M -10 10 L 30 30",
        # Arrow on emitter pointing out
        "M 18 24 L 30 30 L 22 18",
    ],
)

# PNP BJT
# SPICE pin order: collector, base, emitter  →  symbol pins [C, B, E]
PNP = SymbolDef(
    width=60,
    height=80,
    pins=[(-30, -30), (30, 0), (-30, 30)],
    svg_paths=[
        "M -30 0 L -10 0",
        "M -10 -10 L 30 -30",
        "M -10 10 L 30 30",
        # Arrow on emitter pointing in
        "M 30 30 L 18 24 L 24 36",
    ],
)

# NMOS MOSFET
# SPICE pin order: drain, gate, source, bulk  →  symbol pins [D, G, S, B]
NMOS = SymbolDef(
    width=80,
    height=80,
    pins=[(-40, -30), (40, -30), (-40, 30), (40, 30)],
    svg_paths=[
        # Gate line vertical
        "M 0 -30 L 0 30",
        # Drain line
        "M -40 -30 L -15 -30 L -15 -20",
        # Source line
        "M -40 30 L -15 30 L -15 20",
        # Gate connection
        "M -15 0 L 0 0",
        # Bulk/substrate line
        "M 0 0 L 15 0 L 15 -10 L 40 -30",
        "M 15 0 L 15 10 L 40 30",
        # Arrow on source pointing in (NMOS: n-channel, arrow on source pointing into device)
        "M -22 20 L -15 12 L -8 20",
    ],
)

# PMOS MOSFET
# SPICE pin order: drain, gate, source, bulk  →  symbol pins [D, G, S, B]
PMOS = SymbolDef(
    width=80,
    height=80,
    pins=[(-40, -30), (40, -30), (-40, 30), (40, 30)],
    svg_paths=[
        "M 0 -30 L 0 30",
        "M -40 -30 L -15 -30 L -15 -20",
        "M -40 30 L -15 30 L -15 20",
        "M -15 0 L 0 0",
        "M 0 0 L 15 0 L 15 -10 L 40 -30",
        "M 15 0 L 15 10 L 40 30",
        # Arrow on source pointing out (PMOS: p-channel, arrow on source pointing out of device)
        "M -15 12 L -22 20 L -15 28",
    ],
)

# JFET (generic n-channel)
# SPICE pin order: drain, gate, source  →  symbol pins [D, G, S]
JFET = SymbolDef(
    width=60,
    height=80,
    pins=[(-30, -30), (30, 0), (-30, 30)],
    svg_paths=[
        "M -30 0 L 0 0",
        "M 0 -30 L 0 30",
        "M -30 -30 L 0 -20",
        "M -30 30 L 0 20",
        # Arrow on gate/channel
        "M 10 -5 L 20 0 L 10 5",
    ],
)


SUBCIRCUIT = SymbolDef(
    width=80,
    height=60,
    pins=[(-40, 0), (40, 0), (0, -30), (0, 30)],  # left, right, top, bottom
    svg_paths=[
        "M -40 -30 L 40 -30 L 40 30 L -40 30 Z",
    ],
)
