"""SPICE netlist parser."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from netlist2image.core.expressions import parse_numeric_value, parse_unit
from netlist2image.core.models import AbstractNetlist, Element, Net, Node, SubcircuitInstance

# Ground aliases normalized to "GND"
_GROUND_ALIASES = {"0", "GND", "VSS", "VEE", "AGND", "DGND", "PGND", "SGND"}

# Element types and their expected pin counts (for common elements)
# None means variable
_ELEMENT_PIN_COUNTS: Dict[str, Optional[int]] = {
    "R": 2,
    "C": 2,
    "L": 2,
    "V": 2,
    "I": 2,
    "E": 4,
    "F": 2,
    "G": 4,
    "H": 2,
    "D": 2,
    "Q": None,  # 3 or 4
    "M": None,  # 4 or 5
    "J": 3,
    "Z": 3,
    "B": 2,
    "S": 4,
    "W": 2,
    "T": 4,
    "O": 4,
    "U": 3,
    "X": None,
}


def _normalize_node(name: str) -> Tuple[str, Optional[str]]:
    """Normalize a node name, returning (canonical_name, original_name_if_aliased)."""
    upper = name.upper()
    if upper in _GROUND_ALIASES:
        return "GND", name
    return name, None


class SpiceParser:
    """Line-based SPICE netlist parser with lenient error handling."""

    def __init__(self) -> None:
        self.netlist = AbstractNetlist()
        self._subckt_stack: List[SubcircuitContext] = []
        self._models: Dict[str, str] = {}  # model_name -> type (e.g., NPN, NMOS)
        self._params: Dict[str, str] = {}  # param_name -> expression
        self._first_line = True

    def parse(self, text: str) -> AbstractNetlist:
        """Parse a complete netlist string."""
        lines = text.splitlines()
        for line_no, raw_line in enumerate(lines, start=1):
            self._parse_line(raw_line, line_no)
        self._build_nets()
        return self.netlist

    def _parse_line(self, raw_line: str, line_no: int) -> None:
        """Parse a single line."""
        # Strip inline comments
        line = raw_line.split("$")[0].strip()
        if not line:
            return

        # Continuation lines: if line ends with +, it continues next line
        # For simplicity we don't handle multi-line continuations here;
        # they should be pre-joined by the caller or handled in a preprocessor.

        first_char = line[0].upper()

        if first_char == "*":
            # First comment line is the title
            if self._first_line:
                self.netlist.title = line[1:].strip()
            self._first_line = False
            return

        self._first_line = False

        if first_char == ".":
            self._parse_directive(line, line_no)
        elif first_char in _ELEMENT_PIN_COUNTS:
            self._parse_element(line, line_no)
        elif first_char == "+":
            # Continuation line without preceding context — can't handle standalone
            self.netlist.parse_errors.append(f"Line {line_no}: orphaned continuation: {raw_line.strip()}")
        else:
            self.netlist.parse_errors.append(f"Line {line_no}: unrecognized line: {raw_line.strip()}")

    def _parse_directive(self, line: str, line_no: int) -> None:
        """Parse a dot directive."""
        tokens = line.split()
        if not tokens:
            return
        directive = tokens[0].upper()

        if directive == ".SUBCKT":
            self._parse_subckt(tokens, line_no)
        elif directive == ".ENDS":
            self._parse_ends(tokens, line_no)
        elif directive == ".MODEL":
            self._parse_model(tokens, line_no)
        elif directive == ".PARAM":
            self._parse_param(tokens, line)
        elif directive in {".INCLUDE", ".LIB", ".INC"}:
            # Record for completeness; we don't recursively load here
            self.netlist.directives.append(line)
        elif directive == ".TITLE":
            self.netlist.title = " ".join(tokens[1:]) if len(tokens) > 1 else None
        else:
            # Simulation directives and options
            self.netlist.directives.append(line)

    def _parse_subckt(self, tokens: List[str], line_no: int) -> None:
        """Parse .subckt directive."""
        if len(tokens) < 2:
            self.netlist.parse_errors.append(f"Line {line_no}: malformed .subckt")
            return
        name = tokens[1]
        pins = tokens[2:]
        self._subckt_stack.append(SubcircuitContext(name, pins))

    def _parse_ends(self, tokens: List[str], line_no: int) -> None:
        """Parse .ends directive."""
        if not self._subckt_stack:
            self.netlist.parse_errors.append(f"Line {line_no}: .ends without .subckt")
            return
        self._subckt_stack.pop()

    def _parse_model(self, tokens: List[str], line_no: int) -> None:
        """Parse .model directive to extract device type."""
        if len(tokens) < 3:
            self.netlist.parse_errors.append(f"Line {line_no}: malformed .model")
            return
        model_name = tokens[1]
        model_type = tokens[2].upper()
        self._models[model_name.upper()] = model_type

    def _parse_param(self, tokens: List[str], line: str) -> None:
        """Parse .param directive."""
        # .param name=value [name2=value2 ...]
        # The line may contain spaces in expressions, so we try to split by =
        rest = line[len(".param"):].strip()
        # Simple split by whitespace then by =
        for part in rest.split():
            if "=" in part:
                name, val = part.split("=", 1)
                self._params[name.strip().upper()] = val.strip()

    def _parse_element(self, line: str, line_no: int) -> None:
        """Parse an element line."""
        tokens = line.split()
        if not tokens:
            return

        name = tokens[0]
        elem_type = name[0].upper()

        # Determine pin count and value/model position
        pin_count = _ELEMENT_PIN_COUNTS.get(elem_type)

        if elem_type == "X":
            self._parse_subcircuit_instance(tokens, line_no)
            return

        if pin_count is None:
            # Variable pin count: Q (3 or 4), M (4 or 5)
            if elem_type == "Q":
                pin_count = 3 if len(tokens) < 6 else 4
            elif elem_type == "M":
                pin_count = 4 if len(tokens) < 7 else 5
            else:
                pin_count = len(tokens) - 2  # guess

        if len(tokens) < pin_count + 2:
            self.netlist.parse_errors.append(
                f"Line {line_no}: not enough nodes for {elem_type}: {line}"
            )
            return

        raw_pins = tokens[1:1 + pin_count]
        pins = []
        for rp in raw_pins:
            canonical, original = _normalize_node(rp)
            pins.append(canonical)
            if canonical not in self.netlist.nodes:
                self.netlist.nodes[canonical] = Node(name=canonical, spice_name=original, is_ground=(canonical == "GND"))

        # Everything after pins is value/model + parameters
        remainder = tokens[1 + pin_count:]
        value_raw: Optional[str] = None
        model: Optional[str] = None
        parameters: Dict[str, str] = {}

        if elem_type in {"R", "C", "L", "V", "I"}:
            if remainder:
                # For V/I sources, AC/DC are keywords followed by their value
                if elem_type in {"V", "I"} and remainder[0].upper() in {"AC", "DC", "PULSE", "SIN", "EXP", "PWL", "SFFM"}:
                    # Collect keyword + following numeric args until we hit a param
                    val_tokens = [remainder[0]]
                    for tok in remainder[1:]:
                        if "=" in tok:
                            k, v = tok.split("=", 1)
                            parameters[k] = v
                        else:
                            val_tokens.append(tok)
                    value_raw = " ".join(val_tokens)
                else:
                    value_raw = remainder[0]
                    for param in remainder[1:]:
                        if "=" in param:
                            k, v = param.split("=", 1)
                            parameters[k] = v
        elif elem_type in {"D", "Q", "M", "J", "Z"}:
            if remainder:
                model = remainder[0]
                for param in remainder[1:]:
                    if "=" in param:
                        k, v = param.split("=", 1)
                        parameters[k] = v
        elif elem_type in {"E", "F", "G", "H", "B", "S", "W", "T", "O", "U"}:
            # Controlled sources, switches, transmission lines — may have values or models
            if remainder:
                # Try to determine if first token is a model or value
                first = remainder[0]
                if first.upper() in self._models:
                    model = first
                else:
                    value_raw = first
                for param in remainder[1:]:
                    if "=" in param:
                        k, v = param.split("=", 1)
                        parameters[k] = v

        value_numeric = parse_numeric_value(value_raw) if value_raw else None
        unit = parse_unit(value_raw) if value_raw else None

        element = Element(
            id=name,
            type=elem_type,
            pins=pins,
            value_raw=value_raw,
            value_numeric=value_numeric,
            unit=unit,
            model=model,
            parameters=parameters,
        )
        self.netlist.elements.append(element)

    def _parse_subcircuit_instance(self, tokens: List[str], line_no: int) -> None:
        """Parse a subcircuit instance X...."""
        if len(tokens) < 3:
            self.netlist.parse_errors.append(
                f"Line {line_no}: malformed subcircuit instance: {' '.join(tokens)}"
            )
            return
        name = tokens[0]
        # Last token is subcircuit name, everything in between is nodes
        subckt_name = tokens[-1]
        raw_pins = tokens[1:-1]
        pins = {}
        for i, rp in enumerate(raw_pins):
            canonical, original = _normalize_node(rp)
            pin_name = f"pin{i}"
            pins[pin_name] = canonical
            if canonical not in self.netlist.nodes:
                self.netlist.nodes[canonical] = Node(name=canonical, spice_name=original, is_ground=(canonical == "GND"))

        # Record the instance but don't flatten here
        self.netlist.subcircuit_instances.append(
            SubcircuitInstance(name=name, subcircuit=subckt_name, pins=pins)
        )
        # Also add a black-box element for rendering
        element = Element(
            id=name,
            type="X",
            pins=list(pins.values()),
            model=subckt_name,
        )
        self.netlist.elements.append(element)

    def _build_nets(self) -> None:
        """Build net connectivity from elements."""
        net_map: Dict[str, List[Tuple[str, int]]] = {}
        for elem in self.netlist.elements:
            for pin_idx, node_name in enumerate(elem.pins):
                net_map.setdefault(node_name, []).append((elem.id, pin_idx))

        self.netlist.nets = [
            Net(name=name, element_pins=pins)
            for name, pins in net_map.items()
        ]


class SubcircuitContext:
    """Temporary context while parsing inside a .subckt definition."""

    def __init__(self, name: str, pins: List[str]) -> None:
        self.name = name
        self.pins = pins


def parse_netlist(text: str) -> AbstractNetlist:
    """Parse a SPICE netlist string into an AbstractNetlist."""
    parser = SpiceParser()
    return parser.parse(text)
