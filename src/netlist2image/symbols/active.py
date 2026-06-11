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
# Designed with axis-aligned pins so rotations produce predictable orientations:
#   rot=0: C up, B left, E down   (ideal for common-emitter)
#   rot=90: C left, B down, E right
#   rot=180: C down, B right, E up
#   rot=270: C right, B up, E left
NPN = SymbolDef(
    width=80,
    height=100,
    pins=[(0, -50), (-40, 0), (0, 50)],  # C, B, E
    svg_paths=[
        # Base lead
        "M -40 0 L -20 0",
        # Body bar
        "M -20 -30 L -20 30",
        # Collector lead
        "M -20 -20 L 0 -50",
        # Emitter lead
        "M -20 20 L 0 50",
        # Arrow on emitter pointing down (away from body)
        "M -6 40 L 0 50 L 6 40",
    ],
)

# PNP BJT
# Same geometry as NPN; arrow direction is the only difference
PNP = SymbolDef(
    width=80,
    height=100,
    pins=[(0, -50), (-40, 0), (0, 50)],  # C, B, E
    svg_paths=[
        "M -40 0 L -20 0",
        "M -20 -30 L -20 30",
        "M -20 -20 L 0 -50",
        "M -20 20 L 0 50",
        # Arrow on emitter pointing up (toward body)
        "M -6 60 L 0 50 L 6 60",
    ],
)

# NMOS MOSFET
# SPICE pin order: drain, gate, source, bulk  →  symbol pins [D, G, S, B]
# rot=0: D up, G right, S down, B right-up
NMOS = SymbolDef(
    width=80,
    height=100,
    pins=[(0, -50), (40, 0), (0, 50), (40, -30)],  # D, G, S, B
    svg_paths=[
        # Gate vertical channel
        "M 0 -35 L 0 35",
        # Drain lead
        "M 0 -35 L 0 -50",
        # Source lead
        "M 0 35 L 0 50",
        # Gate lead
        "M 0 0 L 40 0",
        # Bulk leads
        "M 0 -20 L 40 -30",
        "M 0 20 L 40 30",
        # Arrow on source pointing down (into device for NMOS)
        "M -6 40 L 0 50 L 6 40",
    ],
)

# PMOS MOSFET
# Same geometry as NMOS; arrow direction reversed
PMOS = SymbolDef(
    width=80,
    height=100,
    pins=[(0, -50), (40, 0), (0, 50), (40, -30)],  # D, G, S, B
    svg_paths=[
        "M 0 -35 L 0 35",
        "M 0 -35 L 0 -50",
        "M 0 35 L 0 50",
        "M 0 0 L 40 0",
        "M 0 -20 L 40 -30",
        "M 0 20 L 40 30",
        # Arrow on source pointing up (out of device for PMOS)
        "M -6 60 L 0 50 L 6 60",
    ],
)

# JFET (generic n-channel)
# SPICE pin order: drain, gate, source  →  symbol pins [D, G, S]
# rot=0: D up, G right, S down
JFET = SymbolDef(
    width=80,
    height=100,
    pins=[(0, -50), (40, 0), (0, 50)],  # D, G, S
    svg_paths=[
        # Channel vertical bar
        "M 0 -35 L 0 35",
        # Drain lead
        "M 0 -35 L 0 -50",
        # Source lead
        "M 0 35 L 0 50",
        # Gate lead
        "M 0 0 L 40 0",
        # Arrow on gate pointing right
        "M 30 -6 L 40 0 L 30 6",
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
