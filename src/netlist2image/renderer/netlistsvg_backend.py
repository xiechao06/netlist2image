"""Render schematics using netlistsvg as the backend."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple

from netlist2image.core.models import AbstractNetlist, RenderedNetlist
from netlist2image.core.netlistsvg_converter import convert_to_yosys_json
from netlist2image.renderer.rasterize import rasterize_svg


# Path to netlistsvg analog skin
_ANALOG_SKIN = Path(__file__).parents[1] / "data" / "analog.svg"


def _find_skin() -> Path:
    """Find the analog skin file."""
    if _ANALOG_SKIN.exists():
        return _ANALOG_SKIN
    # Fallback: look in node_modules if netlistsvg was installed globally
    for candidate in [
        Path("/usr/local/lib/node_modules/netlistsvg/lib/analog.svg"),
        Path.home() / ".nvm" / "versions" / "node" / "v26.0.0" / "lib" / "node_modules" / "netlistsvg" / "lib" / "analog.svg",
        Path.home() / ".local" / "lib" / "node_modules" / "netlistsvg" / "lib" / "analog.svg",
        Path("/opt/homebrew/lib/node_modules/netlistsvg/lib/analog.svg"),
    ]:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("netlistsvg analog skin not found. Install netlistsvg globally: npm install -g netlistsvg")


def render_with_netlistsvg(
    netlist: AbstractNetlist,
    canvas_width: int = 3840,
    canvas_height: int = 2160,
) -> Tuple[str, List[dict[str, object]]]:
    """Render an AbstractNetlist to SVG+PNG using netlistsvg.

    Returns:
        (svg_string, bboxes) — bboxes is empty because netlistsvg doesn't emit them.
    """
    yosys_json, bit_to_net = convert_to_yosys_json(netlist)

    skin_path = _find_skin()

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / "input.json"
        output_path = Path(tmpdir) / "output.svg"

        with open(input_path, "w") as f:
            json.dump(yosys_json, f)

        # Call netlistsvg CLI
        cmd = [
            "netlistsvg",
            str(input_path),
            "-o", str(output_path),
            "--skin", str(skin_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"netlistsvg failed: {result.stderr}")

        with open(output_path, "r") as f:
            svg = f.read()

    # Post-process: add node labels as text on wire midpoints
    svg = _add_node_labels(svg, bit_to_net)

    # Scale SVG to target canvas size and inject title
    svg = _scale_and_title(svg, netlist.title or "", canvas_width, canvas_height)

    # netlistsvg doesn't provide bounding boxes
    bboxes: List[dict[str, object]] = []

    return svg, bboxes


def _add_node_labels(svg: str, bit_to_net: Dict[int, str]) -> str:
    """Add text labels for non-GND nets at the midpoint of their wire segments."""
    # Parse lines: find all <line> elements and group by net_N class
    # netlistsvg emits lines like: <line class="net_1 width_1" ...>
    line_pattern = re.compile(
        r'<line\s+([^>]+)>'
    )

    net_lines: Dict[int, List[Tuple[float, float, float, float]]] = {}

    for match in line_pattern.finditer(svg):
        attrs = match.group(1)
        # Extract class attribute
        cls_match = re.search(r'class="([^"]+)"', attrs)
        if not cls_match:
            continue
        classes = cls_match.group(1).split()
        # Find net_N class
        net_id = None
        for c in classes:
            if c.startswith("net_"):
                try:
                    net_id = int(c.split("_")[1])
                except (ValueError, IndexError):
                    pass
                break
        if net_id is None:
            continue

        # Extract coordinates
        x1 = float(re.search(r'x1="([0-9.]+)"', attrs).group(1))
        y1 = float(re.search(r'y1="([0-9.]+)"', attrs).group(1))
        x2 = float(re.search(r'x2="([0-9.]+)"', attrs).group(1))
        y2 = float(re.search(r'y2="([0-9.]+)"', attrs).group(1))

        net_lines.setdefault(net_id, []).append((x1, y1, x2, y2))

    # Build label text elements
    labels_svg = ""
    for net_id, lines in net_lines.items():
        if net_id not in bit_to_net:
            continue
        net_name = bit_to_net[net_id]
        # Skip ground/power names and numeric-only names
        if net_name.upper() in {"GND", "0", "VSS", "VEE", "VCC", "VDD"}:
            continue
        if net_name.isdigit():
            continue

        # Compute average midpoint of all segments
        total_mx = 0.0
        total_my = 0.0
        for x1, y1, x2, y2 in lines:
            total_mx += (x1 + x2) / 2
            total_my += (y1 + y2) / 2
        mx = total_mx / len(lines)
        my = total_my / len(lines)

        # Offset slightly so text doesn't overlap the wire
        # Place above horizontal wires, right of vertical wires
        dx = 2
        dy = -3

        labels_svg += (
            f'<text x="{mx + dx}" y="{my + dy}" '
            f'font-size="6" font-family="Courier New, monospace" '
            f'fill="#666" stroke="none" text-anchor="start">{net_name}</text>'
        )

    if labels_svg:
        # Insert labels before the closing </svg> tag of the inner SVG
        svg = svg.replace("</svg>", labels_svg + "</svg>", 1)

    return svg


def _scale_and_title(svg: str, title: str, target_width: int, target_height: int) -> str:
    """Wrap netlistsvg output in a 4K SVG with white background, title, and centered content."""

    # Extract original width/height
    width_match = re.search(r'width="([0-9.]+)"', svg)
    height_match = re.search(r'height="([0-9.]+)"', svg)

    if width_match and height_match:
        orig_w = float(width_match.group(1))
        orig_h = float(height_match.group(1))
    else:
        orig_w, orig_h = 200, 200

    # Compute scale to fit within target while preserving aspect ratio
    scale = min(target_width / orig_w, target_height / orig_h)
    scaled_w = orig_w * scale
    scaled_h = orig_h * scale
    tx = (target_width - scaled_w) / 2
    ty = (target_height - scaled_h) / 2

    # Leave room for title at top
    title_margin = 60 if title else 0
    if title:
        ty = max(ty, title_margin + 20)

    # Remove original width/height from the inner svg tag
    svg = re.sub(r'width="[0-9.]+"', '', svg, count=1)
    svg = re.sub(r'height="[0-9.]+"', '', svg, count=1)

    title_svg = ""
    if title:
        title_svg = (
            f'<text x="{target_width / 2}" y="{title_margin - 10}" '
            f'font-size="48" font-family="Arial, sans-serif" '
            f'fill="#000" stroke="none" text-anchor="middle" font-weight="bold">'
            f'{title}</text>'
        )

    # Wrap in a new 4K SVG
    wrapped = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{target_width}" height="{target_height}" '
        f'viewBox="0 0 {target_width} {target_height}">\n'
        f'<rect width="{target_width}" height="{target_height}" fill="white"/>\n'
        f'{title_svg}\n'
        f'<g transform="translate({tx},{ty}) scale({scale})">\n'
        f'{svg}\n'
        f'</g>\n'
        f'</svg>'
    )

    return wrapped


def render_netlist_to_png(
    netlist: AbstractNetlist,
    canvas_width: int = 3840,
    canvas_height: int = 2160,
) -> bytes:
    """Render an AbstractNetlist to PNG bytes using netlistsvg."""
    svg, _ = render_with_netlistsvg(netlist, canvas_width, canvas_height)
    return rasterize_svg(svg, width=canvas_width, height=canvas_height)
