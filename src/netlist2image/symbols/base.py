"""Base symbol class and utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class SymbolDef:
    """Definition of a schematic symbol."""

    width: float
    height: float
    pins: List[Tuple[float, float]]  # relative pin positions, centered at origin
    svg_paths: List[str]  # SVG path data strings
    labels: List[Tuple[str, float, float]] = ()  # (text, x, y)


@dataclass(frozen=True)
class PlacedSymbol:
    """A symbol placed at a specific position and rotation."""

    symbol: SymbolDef
    x: float
    y: float
    rotation: int  # 0, 90, 180, 270
    element_id: str

    def transform_point(self, px: float, py: float) -> Tuple[float, float]:
        """Rotate and translate a local point to global coordinates."""
        if self.rotation == 0:
            return (self.x + px, self.y + py)
        elif self.rotation == 90:
            return (self.x - py, self.y + px)
        elif self.rotation == 180:
            return (self.x - px, self.y - py)
        elif self.rotation == 270:
            return (self.x + py, self.y - px)
        else:
            raise ValueError(f"Invalid rotation: {self.rotation}")

    @property
    def pin_positions(self) -> List[Tuple[float, float]]:
        """Global pin positions."""
        return [self.transform_point(px, py) for px, py in self.symbol.pins]

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        """Global bounding box as (x, y, width, height)."""
        # Compute rotated bbox
        corners = [
            self.transform_point(self.symbol.width / 2, self.symbol.height / 2),
            self.transform_point(-self.symbol.width / 2, self.symbol.height / 2),
            self.transform_point(self.symbol.width / 2, -self.symbol.height / 2),
            self.transform_point(-self.symbol.width / 2, -self.symbol.height / 2),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        return (min_x, min_y, max_x - min_x, max_y - min_y)
