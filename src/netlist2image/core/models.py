"""Pydantic models for netlist data structures."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class BBox(BaseModel):
    """Bounding box in pixels."""

    x: float
    y: float
    width: float
    height: float


class Element(BaseModel):
    """A circuit element in the abstract netlist."""

    id: str = Field(..., description="Element identifier, e.g. R1, Q2")
    type: str = Field(..., description="Element type letter, e.g. R, C, Q")
    pins: List[str] = Field(default_factory=list, description="Node names for each pin")
    value_raw: Optional[str] = Field(None, description="Raw parameter string from netlist")
    value_numeric: Optional[float] = Field(None, description="Normalized numeric value if parseable")
    unit: Optional[str] = Field(None, description="Unit of the value")
    model: Optional[str] = Field(None, description="Referenced model name for Q, M, D")
    parameters: Dict[str, str] = Field(default_factory=dict, description="Additional parameters")


class Node(BaseModel):
    """A circuit node in the abstract netlist."""

    name: str = Field(..., description="Canonical node name")
    spice_name: Optional[str] = Field(None, description="Original SPICE node name before alias normalization")
    is_ground: bool = False


class Net(BaseModel):
    """A net (electrical connection) linking element pins."""

    name: str = Field(..., description="Net/node name")
    element_pins: List[Tuple[str, int]] = Field(
        default_factory=list,
        description="List of (element_id, pin_index) connected to this net",
    )


class SubcircuitInstance(BaseModel):
    """Provenance metadata for a flattened subcircuit instance."""

    name: str = Field(..., description="Instance name, e.g. XU1")
    subcircuit: str = Field(..., description="Subcircuit definition name")
    pins: Dict[str, str] = Field(default_factory=dict, description="Pin name -> node name mapping")


class RenderedElement(Element):
    """An element with layout information."""

    bbox: BBox = Field(..., description="Bounding box in image coordinates")
    rotation: int = Field(0, description="Rotation in degrees (0, 90, 180, 270)")
    pin_positions: List[Tuple[float, float]] = Field(
        default_factory=list,
        description="Absolute (x, y) positions for each pin in image coordinates",
    )


class RenderedNode(Node):
    """A node with layout position."""

    x: float = 0.0
    y: float = 0.0


class AbstractNetlist(BaseModel):
    """The canonical output of parsing a SPICE netlist."""

    title: Optional[str] = None
    elements: List[Element] = Field(default_factory=list)
    nodes: Dict[str, Node] = Field(default_factory=dict)
    nets: List[Net] = Field(default_factory=list)
    subcircuit_instances: List[SubcircuitInstance] = Field(default_factory=list)
    directives: List[str] = Field(default_factory=list)
    parse_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class RenderedNetlist(BaseModel):
    """The output of the rendering stage, with layout positions."""

    title: Optional[str] = None
    elements: List[RenderedElement] = Field(default_factory=list)
    nodes: Dict[str, RenderedNode] = Field(default_factory=dict)
    nets: List[Net] = Field(default_factory=list)
    subcircuit_instances: List[SubcircuitInstance] = Field(default_factory=list)
    directives: List[str] = Field(default_factory=list)
    parse_errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    seed: int = 0
    canvas_width: int = 3840
    canvas_height: int = 2160
