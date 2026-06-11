"""SVG composer: turn a RenderedNetlist into an SVG string."""

from __future__ import annotations

from typing import Dict, List, Tuple

from netlist2image.core.models import RenderedNetlist
from netlist2image.symbols.base import SymbolDef
from netlist2image.symbols.passive import RESISTOR, CAPACITOR, INDUCTOR, VOLTAGE_SOURCE, CURRENT_SOURCE
from netlist2image.symbols.active import DIODE, NPN, PNP, NMOS, PMOS, JFET, SUBCIRCUIT
from netlist2image.symbols.fallback import BLACK_BOX


_SYMBOL_MAP: Dict[str, SymbolDef] = {
    "R": RESISTOR,
    "C": CAPACITOR,
    "L": INDUCTOR,
    "V": VOLTAGE_SOURCE,
    "I": CURRENT_SOURCE,
    "D": DIODE,
    "Q": NPN,
    "M": NMOS,
    "J": JFET,
    "X": SUBCIRCUIT,
}


def _get_symbol(elem_type: str, model: str | None) -> SymbolDef:
    if elem_type == "Q" and model:
        mu = model.upper()
        if mu == "PNP":
            return PNP
    if elem_type == "M" and model:
        mu = model.upper()
        if mu == "PMOS":
            return PMOS
    return _SYMBOL_MAP.get(elem_type, BLACK_BOX)


def _format_value(elem) -> str:
    """Format a nice value string like '33kΩ' or '100nF'."""
    if elem.value_raw and elem.value_numeric:
        val = elem.value_numeric
        # Choose appropriate prefix
        if elem.type in ("R",):
            unit = "Ω"
        elif elem.type in ("C",):
            unit = "F"
        elif elem.type in ("L",):
            unit = "H"
        elif elem.type in ("V",):
            unit = "V"
        elif elem.type in ("I",):
            unit = "A"
        else:
            unit = elem.unit or ""
        # Format with SI prefix
        def _fmt(v: float) -> str:
            """Format without ugly scientific notation."""
            if v == int(v):
                return str(int(v))
            s = f"{v:.3g}"
            return s

        if val >= 1e9:
            return f"{_fmt(val/1e9)}G{unit}"
        elif val >= 1e6:
            return f"{_fmt(val/1e6)}M{unit}"
        elif val >= 1e3:
            return f"{_fmt(val/1e3)}k{unit}"
        elif val >= 1:
            return f"{_fmt(val)}{unit}"
        elif val >= 1e-3:
            return f"{_fmt(val*1e3)}m{unit}"
        elif val >= 1e-6:
            return f"{_fmt(val*1e6)}μ{unit}"
        elif val >= 1e-9:
            return f"{_fmt(val*1e9)}n{unit}"
        elif val >= 1e-12:
            return f"{_fmt(val*1e12)}p{unit}"
        else:
            return f"{_fmt(val)}{unit}"
    elif elem.value_raw:
        return elem.value_raw
    return ""


def _route_orthogonal_2pin(
    svg_parts: List[str],
    x1: float, y1: float,
    x2: float, y2: float,
) -> None:
    """Emit orthogonal wire segments for a two-pin net.

    Uses a three-segment mid-point "Z" route rather than the junction-star
    approach so simple two-element connections look clean and compact:

    * Same horizontal/vertical → a single straight line.
    * Otherwise:
      - Primarily horizontal (|dx| >= |dy|): H → V → H through mid_x.
      - Primarily vertical (|dy| > |dx|):    V → H → V through mid_y.
    """
    if abs(x1 - x2) < 1.0:
        # Exactly (or nearly) vertical
        svg_parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )
    elif abs(y1 - y2) < 1.0:
        # Exactly (or nearly) horizontal
        svg_parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>'
        )
    elif abs(x2 - x1) >= abs(y2 - y1):
        # Primarily horizontal — jog vertically at mid-x
        mx = (x1 + x2) / 2
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{mx:.1f}" y2="{y1:.1f}"/>')
        svg_parts.append(f'<line x1="{mx:.1f}" y1="{y1:.1f}" x2="{mx:.1f}" y2="{y2:.1f}"/>')
        svg_parts.append(f'<line x1="{mx:.1f}" y1="{y2:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    else:
        # Primarily vertical — jog horizontally at mid-y
        my = (y1 + y2) / 2
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x1:.1f}" y2="{my:.1f}"/>')
        svg_parts.append(f'<line x1="{x1:.1f}" y1="{my:.1f}" x2="{x2:.1f}" y2="{my:.1f}"/>')
        svg_parts.append(f'<line x1="{x2:.1f}" y1="{my:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')


def _route_orthogonal_bus(
    svg_parts: List[str],
    points: List[Tuple[float, float]],
) -> None:
    """Emit orthogonal wire segments for a multi-pin net (3+ pins).

    Draws a rectilinear bus:
    * Horizontal trunk at the median y of all pins, spanning min-x to max-x;
      each pin gets a vertical stub down/up to the trunk.
    * Or a vertical trunk if the net is taller than it is wide.

    Junction dots are added wherever a branch taps the trunk.
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)

    if span_x >= span_y:
        # Horizontal trunk at median y
        sorted_ys = sorted(ys)
        bus_y = sorted_ys[len(sorted_ys) // 2]
        svg_parts.append(
            f'<line x1="{min(xs):.1f}" y1="{bus_y:.1f}" '
            f'x2="{max(xs):.1f}" y2="{bus_y:.1f}"/>'
        )
        for px, py in points:
            if abs(py - bus_y) > 1.0:
                svg_parts.append(
                    f'<line x1="{px:.1f}" y1="{py:.1f}" '
                    f'x2="{px:.1f}" y2="{bus_y:.1f}"/>'
                )
            # Junction dot at each tap point
            svg_parts.append(
                f'<circle cx="{px:.1f}" cy="{bus_y:.1f}" r="6" '
                'fill="black" stroke="none"/>'
            )
    else:
        # Vertical trunk at median x
        sorted_xs = sorted(xs)
        bus_x = sorted_xs[len(sorted_xs) // 2]
        svg_parts.append(
            f'<line x1="{bus_x:.1f}" y1="{min(ys):.1f}" '
            f'x2="{bus_x:.1f}" y2="{max(ys):.1f}"/>'
        )
        for px, py in points:
            if abs(px - bus_x) > 1.0:
                svg_parts.append(
                    f'<line x1="{px:.1f}" y1="{py:.1f}" '
                    f'x2="{bus_x:.1f}" y2="{py:.1f}"/>'
                )
            # Junction dot at each tap point
            svg_parts.append(
                f'<circle cx="{bus_x:.1f}" cy="{py:.1f}" r="6" '
                'fill="black" stroke="none"/>'
            )


def render_netlist(
    netlist: RenderedNetlist,
    show_labels: bool = True,
    show_values: bool = True,
    show_node_names: bool = True,
    wire_style: str = "orthogonal",
) -> Tuple[str, List[Dict[str, object]]]:
    """Render a RenderedNetlist to an SVG string and bounding-box list."""
    w = netlist.canvas_width
    h = netlist.canvas_height

    svg_parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]

    # Title
    if netlist.title:
        svg_parts.append(
            f'<text x="{w/2}" y="60" text-anchor="middle" font-size="32" '
            'font-weight="bold" fill="black">'
            f'{netlist.title}</text>'
        )

    svg_parts.append('<g stroke="black" stroke-width="3" fill="none">')

    bboxes: List[Dict[str, object]] = []

    # Draw wires
    for net in netlist.nets:
        pins = net.element_pins
        if len(pins) < 2:
            continue
        points: List[Tuple[float, float]] = []
        for elem_id, pin_idx in pins:
            for elem in netlist.elements:
                if elem.id == elem_id:
                    if pin_idx < len(elem.pin_positions):
                        points.append(elem.pin_positions[pin_idx])
                    break
        if not points:
            continue

        if wire_style == "orthogonal":
            if len(points) == 2:
                _route_orthogonal_2pin(svg_parts, *points[0], *points[1])
            else:
                _route_orthogonal_bus(svg_parts, points)
        else:
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                svg_parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')

    # Draw ground symbols
    for node in netlist.nodes.values():
        if node.is_ground:
            gx, gy = node.x, node.y
            svg_parts.append(
                f'<g transform="translate({gx:.1f},{gy:.1f})" stroke-width="3">'
                '<line x1="0" y1="0" x2="0" y2="15"/>'
                '<line x1="-18" y1="15" x2="18" y2="15"/>'
                '<line x1="-12" y1="22" x2="12" y2="22"/>'
                '<line x1="-6" y1="29" x2="6" y2="29"/>'
                '</g>'
            )

    # Draw elements
    for elem in netlist.elements:
        sym = _get_symbol(elem.type, elem.model)
        ex = elem.bbox.x + elem.bbox.width / 2
        ey = elem.bbox.y + elem.bbox.height / 2

        svg_parts.append(f'<g transform="translate({ex:.1f},{ey:.1f}) rotate({elem.rotation})" stroke-width="3">')
        for path in sym.svg_paths:
            svg_parts.append(f'<path d="{path}"/>')
        svg_parts.append('</g>')

        bboxes.append(
            {
                "element_id": elem.id,
                "bbox": {
                    "x": elem.bbox.x,
                    "y": elem.bbox.y,
                    "width": elem.bbox.width,
                    "height": elem.bbox.height,
                },
            }
        )

        # Labels: ID + value, placed to avoid the element body.
        # For tall (vertically oriented) elements the label goes to the right;
        # for wide (horizontal) elements it goes above.
        if show_labels:
            val_str = _format_value(elem) if show_values else ""
            label = f"{elem.id} {val_str}" if val_str else elem.id
            if elem.rotation in (90, 270):
                # Tall element — label to the right, vertically centred
                lx = elem.bbox.x + elem.bbox.width + 18
                ly = ey + 7
                anchor = "start"
            else:
                # Wide element — label above
                lx = ex
                ly = elem.bbox.y - 22
                anchor = "middle"
            svg_parts.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" '
                f'text-anchor="{anchor}" font-size="22" fill="black" stroke="none">'
                f'{label}</text>'
            )

    # Node name labels: offset 28 px above the node position so they don't
    # sit on top of junction dots or wire segments.
    if show_node_names:
        for node in netlist.nodes.values():
            if node.is_ground:
                continue
            nx, ny = node.x, node.y
            svg_parts.append(
                f'<text x="{nx:.1f}" y="{ny - 28:.1f}" '
                'text-anchor="middle" font-size="18" fill="#444" stroke="none" '
                'style="font-style:italic">'
                f'{node.name}</text>'
            )

    svg_parts.append('</g>')
    svg_parts.append('</svg>')

    return "\n".join(svg_parts), bboxes
