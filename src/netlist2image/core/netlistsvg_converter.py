"""Convert AbstractNetlist to Yosys JSON format for netlistsvg.

Rules from netlistsvg's own working analog test cases:
  1. Every cell MUST have port_directions – without them ELK won't route edges.
  2. GND/power nodes are split: each pin that touches GND gets its own unique bit ID
     plus its own gnd/vcc symbol. This is how real schematics work (GND rails, not wires).
  3. Use vertical variants (r_v, c_v, l_v, d_v) because ELK's layout direction is DOWN.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from netlist2image.core.models import AbstractNetlist

# Map SPICE element type → netlistsvg skin alias (vertical preferred for DOWN layout)
_TYPE_MAP: Dict[str, str] = {
    "R": "r_v",
    "C": "c_v",
    "L": "l_v",
    "V": "v",
    "I": "i",
    "D": "d_v",
    "Q": "q_npn",   # overridden by polarity
    "M": "generic",
    "J": "generic",
    "X": "generic",
}

# Port name lists per element type (index matches elem.pins order)
_PORT_NAMES: Dict[str, List[str]] = {
    "R": ["A", "B"],
    "C": ["A", "B"],
    "L": ["A", "B"],
    "V": ["+", "-"],
    "I": ["+", "-"],
    "D": ["+", "-"],
    "Q": ["C", "B", "E"],
    "M": ["D", "G", "S"],
    "J": ["D", "G", "S"],
}

# port_directions per element type
_PORT_DIRS: Dict[str, Dict[str, str]] = {
    "R":     {"A": "input",  "B": "output"},
    "C":     {"A": "input",  "B": "output"},
    "L":     {"A": "input",  "B": "output"},
    "V":     {"+": "output", "-": "input"},
    "I":     {"+": "output", "-": "input"},
    "D":     {"+": "input",  "-": "output"},
    "q_npn": {"C": "input",  "B": "input",  "E": "output"},
    "q_pnp": {"C": "output", "B": "input",  "E": "input"},
    "M":     {"D": "input",  "G": "input",  "S": "output"},
    "J":     {"D": "input",  "G": "input",  "S": "output"},
}

# Canonical ground/power net names (upper-cased for comparison)
_GND_NAMES  = {"GND", "0", "VSS", "VEE", "AGND", "DGND", "PGND", "SGND"}
_VCC_NAMES  = {"VCC", "VDD", "VPP", "AVCC", "DVCC", "VBAT", "V3V3", "V5"}


def convert_to_yosys_json(netlist: AbstractNetlist) -> Tuple[Dict[str, Any], Dict[int, str]]:
    """Convert an AbstractNetlist to Yosys JSON suitable for netlistsvg.

    Returns:
        (yosys_json_dict, bit_to_net_name_mapping)
    """

    # ------------------------------------------------------------------ #
    # 1. Assign integer bit IDs to element pins                           #
    #    – GND/VCC pins each get a UNIQUE ID + their own power symbol     #
    #    – Ordinary shared nets get ONE ID for all connected pins         #
    # ------------------------------------------------------------------ #
    bit_counter = [1]

    def _next_bit() -> int:
        b = bit_counter[0]
        bit_counter[0] += 1
        return b

    # (elem_id, pin_idx) → bit int
    pin_bits: Dict[Tuple[str, int], int] = {}

    # bit_id → net_name (for labeling wires later)
    bit_to_net: Dict[int, str] = {}

    # Extra power/ground cells to add
    extra_cells: Dict[str, Any] = {}

    for net in netlist.nets:
        upper = net.name.upper()
        is_gnd = upper in _GND_NAMES
        is_vcc = upper in _VCC_NAMES

        if is_gnd or is_vcc:
            # Each pin gets its own isolated bit + a power symbol
            for elem_id, pin_idx in net.element_pins:
                b = _next_bit()
                pin_bits[(elem_id, pin_idx)] = b
                bit_to_net[b] = net.name
                cell_id = f"{'gnd' if is_gnd else 'vcc'}_{b}"
                if is_gnd:
                    extra_cells[cell_id] = {
                        "type": "gnd",
                        "port_directions": {"A": "input"},
                        "connections": {"A": [b]},
                    }
                else:
                    extra_cells[cell_id] = {
                        "type": "vcc",
                        "port_directions": {"A": "output"},
                        "connections": {"A": [b]},
                        "attributes": {"name": net.name},
                    }
        else:
            # All pins on this net share a single bit
            shared = _next_bit()
            bit_to_net[shared] = net.name
            for elem_id, pin_idx in net.element_pins:
                pin_bits[(elem_id, pin_idx)] = shared

    # ------------------------------------------------------------------ #
    # 2. Build cell definitions                                            #
    # ------------------------------------------------------------------ #
    cells: Dict[str, Any] = {}

    for elem in netlist.elements:
        # Resolve skin type alias
        elem_type = elem.type
        if elem_type == "Q" and elem.model:
            mu = elem.model.upper()
            if mu == "PNP":
                type_alias = "q_pnp"
            else:
                type_alias = "q_npn"
        else:
            type_alias = _TYPE_MAP.get(elem_type, "generic")

        # Port names for this element
        port_names = _PORT_NAMES.get(elem_type, [])

        # Build connections dict
        connections: Dict[str, List[int]] = {}
        for pin_idx, node_name in enumerate(elem.pins):
            port = port_names[pin_idx] if pin_idx < len(port_names) else f"pin{pin_idx}"
            b = pin_bits.get((elem.id, pin_idx))
            if b is not None:
                connections[port] = [b]

        # Resolve port_directions
        if type_alias in _PORT_DIRS:
            port_directions = _PORT_DIRS[type_alias]
        elif elem_type in _PORT_DIRS:
            port_directions = _PORT_DIRS[elem_type]
        else:
            # generic fallback: all inputs except last which is output
            port_directions = {p: "output" if i == len(connections) - 1 else "input"
                               for i, p in enumerate(connections)}

        cell: Dict[str, Any] = {
            "type": type_alias,
            "port_directions": port_directions,
            "connections": connections,
            "attributes": {"ref": elem.id},
        }
        if elem.value_raw:
            cell["attributes"]["value"] = elem.value_raw

        cells[elem.id] = cell

    # Merge extra power/ground cells
    cells.update(extra_cells)

    yosys_json = {
        "modules": {
            "circuit": {
                "cells": cells,
            }
        }
    }

    return yosys_json, bit_to_net
