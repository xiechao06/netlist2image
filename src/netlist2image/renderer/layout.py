"""Graph layout engine using NetworkX with topology-aware heuristics."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Dict, List, Tuple

import networkx

from netlist2image.core.models import (
    AbstractNetlist,
    BBox,
    RenderedElement,
    RenderedNetlist,
    RenderedNode,
)
from netlist2image.symbols.base import SymbolDef
from netlist2image.symbols.passive import (
    CAPACITOR,
    CURRENT_SOURCE,
    INDUCTOR,
    RESISTOR,
    VOLTAGE_SOURCE,
)
from netlist2image.symbols.active import (
    DIODE,
    JFET,
    NMOS,
    NPN,
    PMOS,
    PNP,
    SUBCIRCUIT,
)
from netlist2image.symbols.fallback import BLACK_BOX

# Mapping from element type to default symbol
_DEFAULT_SYMBOLS: Dict[str, SymbolDef] = {
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

# Grid snap size
_GRID = 20.0

# Canvas margin
_MARGIN = 150.0

# Maximum scale (px per layout unit) at reference 1920-px-wide canvas.
# Scales proportionally for 4K or other sizes. Spring layout with k=2 places
# connected nodes ~2 units apart, so at 300 px/unit that is ~600 px of wire
# between neighbours on a 1920-px canvas — well-spaced without over-spreading.
_MAX_SCALE_REF = 300.0          # reference max-scale (at 1920-px width)
_CANVAS_REF_WIDTH = 1920.0      # reference canvas width for scale cap

# Minimum clearance between element edges (px) during overlap removal.
_ELEM_CLEARANCE = 60.0


def _order_chain(chain: List[str], adj: Dict[str, List[str]]) -> List[str]:
    """Order a chain from one endpoint to the other.

    A chain is a sequence of elements where consecutive elements share a
    degree-2 non-ground node.  The ordering is important so the spring
    layout sees a left-to-right (or top-to-bottom) signal flow rather than
    an arbitrary DFS order.
    """
    if len(chain) <= 1:
        return chain
    chain_set = set(chain)
    chain_adj = {e: [n for n in adj.get(e, []) if n in chain_set] for e in chain}
    endpoints = [e for e in chain if len(chain_adj[e]) == 1]
    if len(endpoints) != 2:
        return chain
    ordered = [endpoints[0]]
    seen = {endpoints[0]}
    while len(ordered) < len(chain):
        current = ordered[-1]
        for neighbor in chain_adj[current]:
            if neighbor not in seen:
                ordered.append(neighbor)
                seen.add(neighbor)
                break
    return ordered


def _topology_initial_positions(
    netlist: AbstractNetlist,
    rng: random.Random,
) -> Dict[str, Tuple[float, float]]:
    """Compute topology-aware initial positions for the spring layout.

    The algorithm works in three stages:

    1. **Series-chain detection** — build a graph where two elements are
       adjacent if they share a *degree-2 non-ground node*.  A degree-2 node
       is a wire that connects exactly two elements; these are the interior
       points of a series chain.  Connected components in this graph are
       maximal series chains.

    2. **Spine placement** — the longest chain is placed horizontally from
       left (-1) to right (+1) at y = 0.  Sources (V, I) are nudged further
       left; elements with a ground pin are nudged downward so the ground
       symbol tends to end up at the bottom after the spring layout.

    3. **Branch placement** — remaining elements are attached iteratively to
       their already-placed neighbours, offset perpendicular to the local
       neighbour arrangement.  This handles T-junctions, parallel branches,
       and star nodes gracefully.

    The result is passed as ``pos`` to ``networkx.spring_layout``, so the
    force-directed solver starts from a nearly-human arrangement and
    converges to a clean schematic in far fewer iterations.
    """
    # 1. node -> elements (excluding ground)
    node_elems: Dict[str, List[str]] = defaultdict(list)
    for elem in netlist.elements:
        for pin in elem.pins:
            if pin == "GND":
                continue
            node_elems[pin].append(elem.id)

    # 2. element adjacency through degree-2 nodes
    adj: Dict[str, List[str]] = defaultdict(list)
    for node, elems in node_elems.items():
        if len(elems) == 2:
            a, b = elems
            adj[a].append(b)
            adj[b].append(a)

    # 3. find chains (connected components in adj)
    visited: set[str] = set()
    chains: List[List[str]] = []
    for eid in list(adj.keys()):
        if eid in visited:
            continue
        chain: List[str] = []
        stack = [eid]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            chain.append(cur)
            for nb in adj.get(cur, []):
                if nb not in visited:
                    stack.append(nb)
        chains.append(chain)

    chains.sort(key=len, reverse=True)

    positions: Dict[str, Tuple[float, float]] = {}
    placed: set[str] = set()

    # 4. place longest chain horizontally with seed-dependent variation
    if chains and chains[0]:
        main = _order_chain(chains[0], adj)
        n = len(main)
        step = 2.0 / max(n, 1)
        # Randomly flip chain direction so variants aren't all identical
        flip = rng.choice([True, False])
        for i, eid in enumerate(main):
            idx = (n - 1 - i) if flip else i
            x = -1.0 + idx * step + rng.uniform(-0.08, 0.08)
            y = rng.uniform(-0.08, 0.08)
            elem = next((e for e in netlist.elements if e.id == eid), None)
            if elem:
                if elem.type in ("V", "I"):
                    x -= 0.3
                if any(p == "GND" for p in elem.pins):
                    y -= 0.5
            positions[eid] = (x, y)
            placed.add(eid)

    # 5. full adjacency through *any* shared non-ground node
    full_adj: Dict[str, List[str]] = defaultdict(list)
    for node, elems in node_elems.items():
        for i, a in enumerate(elems):
            for b in elems[i + 1 :]:
                if b not in full_adj[a]:
                    full_adj[a].append(b)
                if a not in full_adj[b]:
                    full_adj[b].append(a)

    # 6. iteratively place remaining elements near their placed neighbours
    unplaced = [e.id for e in netlist.elements if e.id not in placed]
    while unplaced:
        # pick the unplaced element with the most placed neighbours
        best = None
        best_count = -1
        for eid in unplaced:
            count = sum(1 for n in full_adj.get(eid, []) if n in placed)
            if count > best_count:
                best_count = count
                best = eid

        if best is None or best_count == 0:
            # disconnected components — random fallback
            for eid in unplaced:
                positions[eid] = (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5))
            break

        neighbours = [n for n in full_adj.get(best, []) if n in placed]
        x = sum(positions[n][0] for n in neighbours) / len(neighbours)
        y = sum(positions[n][1] for n in neighbours) / len(neighbours)

        # offset perpendicular to the neighbour arrangement
        if len(neighbours) >= 2:
            dx = positions[neighbours[-1]][0] - positions[neighbours[0]][0]
            dy = positions[neighbours[-1]][1] - positions[neighbours[0]][1]
            if abs(dx) > abs(dy):
                # neighbours are roughly horizontal → offset vertically
                y += rng.choice([0.5, -0.5])
            else:
                # neighbours are roughly vertical → offset horizontally
                x += rng.choice([0.5, -0.5])
        else:
            angle = rng.uniform(0, 2 * math.pi)
            x += 0.4 * math.cos(angle)
            y += 0.4 * math.sin(angle)

        elem = next((e for e in netlist.elements if e.id == best), None)
        if elem:
            if elem.type in ("V", "I"):
                x -= 0.3
            if any(p == "GND" for p in elem.pins):
                y -= 0.3

        positions[best] = (x, y)
        placed.add(best)
        unplaced.remove(best)

    return positions


def _resolve_symbol(elem_type: str, model_type: str | None) -> SymbolDef:
    """Choose the right symbol based on element type and model type."""
    if elem_type == "Q":
        if model_type == "PNP":
            return PNP
        return NPN
    if elem_type == "M":
        if model_type == "PMOS":
            return PMOS
        return NMOS
    return _DEFAULT_SYMBOLS.get(elem_type, BLACK_BOX)


def _rotate_point(px: float, py: float, rotation: int) -> Tuple[float, float]:
    """Rotate a point around the origin."""
    if rotation == 0:
        return (px, py)
    elif rotation == 90:
        return (py, -px)
    elif rotation == 180:
        return (-px, -py)
    elif rotation == 270:
        return (-py, px)
    else:
        raise ValueError(f"Invalid rotation: {rotation}")


def compute_layout(
    netlist: AbstractNetlist,
    seed: int = 0,
    canvas_width: int = 3840,
    canvas_height: int = 2160,
) -> RenderedNetlist:
    """Compute spring layout for a netlist and return a RenderedNetlist."""
    rng = random.Random(seed)

    # Build a graph where elements are nodes and nets are edges
    G = networkx.Graph()
    elem_ids = [e.id for e in netlist.elements]
    G.add_nodes_from(elem_ids)

    # Add edges between elements that share a *non-ground* net.
    # Ground is a common reference point, not a signal connection; treating it
    # as an edge pulls all ground-referenced elements together and destroys
    # the natural series-chain topology that the layout engine tries to
    # preserve (e.g. a voltage divider becomes a triangle instead of a path).
    for net in netlist.nets:
        if net.name == "GND":
            continue
        pins = net.element_pins
        for i in range(len(pins)):
            for j in range(i + 1, len(pins)):
                elem_a, _ = pins[i]
                elem_b, _ = pins[j]
                if elem_a in elem_ids and elem_b in elem_ids:
                    G.add_edge(elem_a, elem_b)

    # Identify sources and ground-connected elements for anchoring
    source_ids = [e.id for e in netlist.elements if e.type in ("V", "I")]
    ground_elem_ids = []
    for net in netlist.nets:
        if net.name == "GND":
            for elem_id, _ in net.element_pins:
                if elem_id in elem_ids:
                    ground_elem_ids.append(elem_id)

    # Initial positions: topology-aware placement instead of crude bias.
    # The spring layout still has freedom to refine, but it now starts from
    # a near-human arrangement (series chains horizontal, branches perpendicular,
    # sources left, ground downward).
    initial_pos = _topology_initial_positions(netlist, rng)

    # Spring layout — higher k and more iterations spread nodes more evenly
    # and produce cleaner schematics.  k is the "ideal edge length" in
    # normalised layout units; 2.0 gives ~600–800 px spacing at the default
    # max-scale cap of 400 px/unit.
    if len(G.nodes) == 0:
        pos = {}
    elif len(G.nodes) == 1:
        pos = {list(G.nodes)[0]: (0.0, 0.0)}
    else:
        pos = networkx.spring_layout(
            G,
            seed=seed,
            k=2.0,
            iterations=150,
            weight=None,
            pos=initial_pos if initial_pos else None,
        )

    # If spring_layout returns empty (disconnected graph with no edges), place randomly
    if not pos and G.nodes:
        for node in G.nodes:
            pos[node] = (rng.uniform(-1, 1), rng.uniform(-1, 1))

    # Post-process: shift so sources are on the left, ground is at the bottom
    dx = dy = 0.0
    if source_ids:
        source_x = sum(pos[sid][0] for sid in source_ids) / len(source_ids)
        dx = -0.8 - source_x  # move sources toward x = -0.8
    if ground_elem_ids:
        ground_y = sum(pos[gid][1] for gid in ground_elem_ids) / len(ground_elem_ids)
        dy = -0.8 - ground_y  # move ground toward y = -0.8 (bottom in math coords)

    for eid in pos:
        pos[eid] = (pos[eid][0] + dx, pos[eid][1] + dy)

    # Convert positions to canvas coordinates
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]

    if xs:
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 0.01)
        span_y = max(max_y - min_y, 0.01)
    else:
        min_x = min_y = span_x = span_y = 0.0

    available_w = canvas_width - 2 * _MARGIN
    available_h = canvas_height - 2 * _MARGIN

    if span_x > 0 and span_y > 0:
        scale = min(available_w / span_x, available_h / span_y)
    else:
        scale = 1.0

    # Cap scale so small/sparse circuits don't over-spread across the canvas.
    # The cap scales proportionally with canvas width so 4K and 1080p both look
    # right: at 1920 px wide cap = 300 px/unit → ~600 px between neighbours;
    # at 3840 px (4K) cap = 600 px/unit → ~1200 px between neighbours.
    max_scale = _MAX_SCALE_REF * canvas_width / _CANVAS_REF_WIDTH
    scale = min(scale, max_scale)

    center_x = canvas_width / 2
    center_y = canvas_height / 2
    offset_x = center_x - (min_x + max_x) / 2 * scale
    offset_y = center_y - (min_y + max_y) / 2 * scale

    def _to_canvas(px: float, py: float) -> Tuple[float, float]:
        """Map a normalised layout coordinate to canvas pixels (no grid snap)."""
        x = px * scale + offset_x
        y = py * scale + offset_y
        return (x, y)

    # Build element -> symbol map
    elem_symbols: Dict[str, SymbolDef] = {}
    for elem in netlist.elements:
        model_type = None
        if elem.model:
            model_upper = elem.model.upper()
            if model_upper in ("NPN", "PNP", "NMOS", "PMOS"):
                model_type = model_upper
        elem_symbols[elem.id] = _resolve_symbol(elem.type, model_type)

    elem_positions: Dict[str, Tuple[float, float]] = {}
    for eid, (px, py) in pos.items():
        elem_positions[eid] = _to_canvas(px, py)

    # Overlap removal pass.
    # min_dist is the required centre-to-centre separation: half the largest
    # dimension of each element plus a clearance gap.  Using the sum of half-
    # extents (rather than a single max) ensures elements of different sizes
    # are also kept apart properly.
    for _ in range(100):
        moved = False
        for i, eid_a in enumerate(elem_ids):
            sym_a = elem_symbols[eid_a]
            x_a, y_a = elem_positions[eid_a]
            for eid_b in elem_ids[i + 1 :]:
                sym_b = elem_symbols[eid_b]
                x_b, y_b = elem_positions[eid_b]
                dx_ = x_b - x_a
                dy_ = y_b - y_a
                dist = max((dx_ * dx_ + dy_ * dy_) ** 0.5, 0.01)
                half_a = max(sym_a.width, sym_a.height) / 2
                half_b = max(sym_b.width, sym_b.height) / 2
                min_dist = half_a + half_b + _ELEM_CLEARANCE
                if dist < min_dist:
                    force = (min_dist - dist) / dist * 0.5
                    fx = dx_ * force
                    fy = dy_ * force
                    elem_positions[eid_a] = (x_a - fx, y_a - fy)
                    elem_positions[eid_b] = (x_b + fx, y_b + fy)
                    moved = True
        if not moved:
            break

    # Clamp element centres to canvas (with margin).
    for eid in elem_positions:
        sym = elem_symbols[eid]
        half_ext = max(sym.width, sym.height) / 2
        lo_x = _MARGIN + half_ext
        hi_x = canvas_width - _MARGIN - half_ext
        lo_y = _MARGIN + half_ext
        hi_y = canvas_height - _MARGIN - half_ext
        cx, cy = elem_positions[eid]
        cx = max(lo_x, min(hi_x, cx))
        cy = max(lo_y, min(hi_y, cy))
        elem_positions[eid] = (cx, cy)

    # Grid-snap AFTER overlap removal so the repulsion forces don't push
    # elements off the grid.
    for eid in elem_positions:
        cx, cy = elem_positions[eid]
        cx = round(cx / _GRID) * _GRID
        cy = round(cy / _GRID) * _GRID
        elem_positions[eid] = (cx, cy)

    # ------------------------------------------------------------------
    # Rotation selection — iterative refinement.
    #
    # The naive approach (compute node positions from unrotated pins, then
    # pick rotations) is circular: node positions depend on rotations, but
    # rotations are chosen before node positions are known.  For 3-pin
    # devices like transistors this often picks nonsense orientations (e.g.
    # emitter pointing up when the emitter node is 200 px below).
    #
    # We solve this by iterating:
    #   1. Start with all rotations = 0.
    #   2. Compute node positions from the CURRENT rotations.
    #   3. Recompute the best rotation for every element using those nodes.
    #   4. Repeat until no rotation changes (usually 2-3 iterations).
    #
    # The ground-down constraint is applied at every iteration.
    # ------------------------------------------------------------------

    def _valid_rots_for(elem: Element, sym: SymbolDef) -> List[int]:
        """Return rotations that satisfy the ground-down constraint."""
        has_ground = "GND" in elem.pins
        if not has_ground:
            return [0, 90, 180, 270]
        valid = []
        for rot in [0, 90, 180, 270]:
            ok = True
            for pin_idx, node_name in enumerate(elem.pins):
                if node_name == "GND" and pin_idx < len(sym.pins):
                    _rx, ry = _rotate_point(sym.pins[pin_idx][0], sym.pins[pin_idx][1], rot)
                    if ry <= 0:
                        ok = False
                        break
            if ok:
                valid.append(rot)
        return valid if valid else [0, 90, 180, 270]

    def _compute_node_centers(rots: Dict[str, int]) -> Dict[str, Tuple[float, float]]:
        """Compute node positions from rotated pin positions."""
        pos: Dict[str, List[Tuple[float, float]]] = {}
        for elem in netlist.elements:
            sym = elem_symbols[elem.id]
            ex, ey = elem_positions[elem.id]
            rot = rots[elem.id]
            for pin_idx, node_name in enumerate(elem.pins):
                if pin_idx < len(sym.pins):
                    px, py = sym.pins[pin_idx]
                    rx, ry = _rotate_point(px, py, rot)
                    if node_name not in pos:
                        pos[node_name] = []
                    pos[node_name].append((ex + rx, ey + ry))
        return {
            name: (sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts))
            for name, pts in pos.items()
        }

    # Precompute which nodes connect to sources (Vcc/Vdd) and which to GND
    _nodes_with_sources: set[str] = set()
    _nodes_with_ground: set[str] = set()
    for net in netlist.nets:
        for elem_id, _pin_idx in net.element_pins:
            elem = next((e for e in netlist.elements if e.id == elem_id), None)
            if elem:
                if elem.type in ("V", "I"):
                    _nodes_with_sources.add(net.name)
                if "GND" in elem.pins:
                    # This element has a ground pin; check if this net is that pin
                    for pi, pn in enumerate(elem.pins):
                        if pn == net.name and pi == _pin_idx:
                            _nodes_with_ground.add(net.name)

    def _best_rotation(elem: Element, valid: List[int], nodes: Dict[str, Tuple[float, float]]) -> int:
        """Pick the rotation with minimal pin-to-node squared error.

        For transistors (Q, M) an additional topology bias is applied:
        * pins on nodes that connect to sources (Vcc) are nudged UPWARD,
        * pins on nodes that connect to GND are nudged DOWNWARD.
        This prevents the absurd outcome where a CE amp's emitter points
        up toward the collector node 200 px above it.
        """
        sym = elem_symbols[elem.id]
        ex, ey = elem_positions[elem.id]
        is_transistor = elem.type in ("Q", "M")
        best_rot = valid[0]
        best_err = float("inf")
        for rot in valid:
            err = 0.0
            for pin_idx, node_name in enumerate(elem.pins):
                if pin_idx >= len(sym.pins):
                    break
                px, py = sym.pins[pin_idx]
                rx, ry = _rotate_point(px, py, rot)
                nx, ny = nodes.get(node_name, (ex + rx, ey + ry))
                err += (ex + rx - nx) ** 2 + (ey + ry - ny) ** 2

                # Topology bias for transistors ---------------------------------
                if is_transistor:
                    pin_y_global = ey + ry
                    # Pin on a source node (Vcc) should point UP (lower y)
                    if node_name in _nodes_with_sources and pin_y_global > ey - 5:
                        err += 25_000.0
                    # Pin on a ground node should point DOWN (higher y)
                    if node_name in _nodes_with_ground and pin_y_global < ey + 5:
                        err += 25_000.0
                    # Prefer vertical orientation (90 or 270) for transistors
                    if rot not in (90, 270):
                        err += 8_000.0
                # ----------------------------------------------------------------

            if err < best_err:
                best_err = err
                best_rot = rot
        return best_rot

    # Seed rotations: start from previous guess or 0
    elem_rotations: Dict[str, int] = {e.id: 0 for e in netlist.elements}
    elem_valid_rots = {e.id: _valid_rots_for(e, elem_symbols[e.id]) for e in netlist.elements}

    for _ in range(10):
        node_centers = _compute_node_centers(elem_rotations)
        changed = False
        for elem in netlist.elements:
            new_rot = _best_rotation(elem, elem_valid_rots[elem.id], node_centers)
            if elem_rotations[elem.id] != new_rot:
                elem_rotations[elem.id] = new_rot
                changed = True
        if not changed:
            break

    # ------------------------------------------------------------------
    # Hard post-process for transistors: emitter/source must point toward
    # its node, collector/drain must point away from it.  This catches the
    # cases where the iterative metric still picks the wrong orientation
    # because the spring layout placed neighbour nodes asymmetrically.
    # ------------------------------------------------------------------
    node_centers = _compute_node_centers(elem_rotations)
    for elem in netlist.elements:
        if elem.type not in ("Q", "M", "J"):
            continue
        sym = elem_symbols[elem.id]
        rot = elem_rotations[elem.id]
        ex, ey = elem_positions[elem.id]

        # Find emitter/source pin by name
        e_pin_idx = None
        for idx, pin_name in enumerate(elem.pins):
            if pin_name.lower() in {"emitter", "source"}:
                e_pin_idx = idx
                break

        if e_pin_idx is not None and e_pin_idx < len(sym.pins):
            e_name = elem.pins[e_pin_idx]
            epx, epy = sym.pins[e_pin_idx]
            erx, ery = _rotate_point(epx, epy, rot)
            e_pin_y = ey + ery
            e_node_y = node_centers.get(e_name, (ex, e_pin_y))[1]

            # If emitter/source points UP (ery < 0) but node is BELOW,
            # or points DOWN (ery > 0) but node is ABOVE, flip 180°.
            if ery < 0 and e_node_y > e_pin_y + 40:
                new_rot = (rot + 180) % 360
                if new_rot in elem_valid_rots[elem.id]:
                    elem_rotations[elem.id] = new_rot
            elif ery > 0 and e_node_y < e_pin_y - 40:
                new_rot = (rot + 180) % 360
                if new_rot in elem_valid_rots[elem.id]:
                    elem_rotations[elem.id] = new_rot

    # Build RenderedNetlist
    rendered = RenderedNetlist(
        title=netlist.title,
        nets=netlist.nets,
        subcircuit_instances=netlist.subcircuit_instances,
        directives=netlist.directives,
        parse_errors=netlist.parse_errors,
        warnings=netlist.warnings,
        seed=seed,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )

    # Compute node positions from rotated pins
    node_positions_rotated: Dict[str, List[Tuple[float, float]]] = {}
    for elem in netlist.elements:
        sym = elem_symbols[elem.id]
        ex, ey = elem_positions[elem.id]
        rot = elem_rotations[elem.id]
        for pin_idx, node_name in enumerate(elem.pins):
            if pin_idx < len(sym.pins):
                px, py = sym.pins[pin_idx]
            else:
                px, py = 0, 0
            rx, ry = _rotate_point(px, py, rot)
            if node_name not in node_positions_rotated:
                node_positions_rotated[node_name] = []
            node_positions_rotated[node_name].append((ex + rx, ey + ry))

    for name, pts in node_positions_rotated.items():
        cx = sum(x for x, _ in pts) / len(pts)
        cy = sum(y for _, y in pts) / len(pts)
        orig = netlist.nodes.get(name)
        rendered.nodes[name] = RenderedNode(
            name=name,
            spice_name=orig.spice_name if orig else None,
            is_ground=orig.is_ground if orig else False,
            x=cx,
            y=cy,
        )

    # Build rendered elements
    for elem in netlist.elements:
        sym = elem_symbols[elem.id]
        ex, ey = elem_positions[elem.id]
        rot = elem_rotations[elem.id]

        # Compute rotated pin positions
        pin_positions = []
        for pin_idx in range(len(elem.pins)):
            if pin_idx < len(sym.pins):
                px, py = sym.pins[pin_idx]
            else:
                px, py = 0, 0
            rx, ry = _rotate_point(px, py, rot)
            pin_positions.append((ex + rx, ey + ry))

        # Compute rotated bbox
        if rot in (90, 270):
            bw, bh = sym.height, sym.width
        else:
            bw, bh = sym.width, sym.height

        rendered.elements.append(
            RenderedElement(
                id=elem.id,
                type=elem.type,
                pins=elem.pins,
                value_raw=elem.value_raw,
                value_numeric=elem.value_numeric,
                unit=elem.unit,
                model=elem.model,
                parameters=elem.parameters,
                bbox=BBox(x=ex - bw / 2, y=ey - bh / 2, width=bw, height=bh),
                rotation=rot,
                pin_positions=pin_positions,
            )
        )

    return rendered
