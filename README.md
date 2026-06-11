# netlist2image

Convert SPICE netlists to schematic images for machine-learning training data.

## Features

- Parse SPICE netlists (ngspice / LTspice / PSpice dialects)
- Export structured **Abstract Netlist JSON** + **Rendered Netlist JSON**
- Generate schematic diagrams as **PNG** (4K default) and **SVG**
- **Topology-aware layout engine** — detects series chains, parallel branches, and star nodes; seeds the spring layout with human-like initial positions
- **Ground-aware rotation** — elements with a ground pin are automatically oriented so the pin points downward
- **Smart orthogonal wire routing** — Z-shaped 2-pin routes and rectilinear bus routing for multi-pin nets
- **Two rendering backends** — the default custom SVG engine (topology-aware) and an optional `netlistsvg` backend powered by the Eclipse Layout Kernel (ELK)
- Produce **3–5 layout variants** per netlist with deterministic seeds
- Built-in symbol library for common analog components (R, C, L, V, I, D, Q, M, J, X)
- Black-box fallback for unsupported elements
- BJT/MOSFET polarity resolution via `.model` cards and built-in model map
- Ground alias normalization (`0`, `GND`, `VSS`, `VEE`, etc.)
- Lenient parsing with `parse_errors` and `warnings` tracking

## Layout Engine

The default renderer (`renderer/layout.py`) uses a hybrid pipeline:

1. **Topology analysis** — Builds a graph of elements connected through *degree-2 non-ground nodes* to find maximal series chains. The longest chain becomes the horizontal "spine" of the schematic.
2. **Initial placement** — Spine elements are laid out left-to-right; branch elements attach perpendicular to their nearest neighbour. Sources are biased left; ground-connected elements are biased down.
3. **Spring refinement** — NetworkX Fruchterman-Reingold (`k=2.0, iterations=150`) relaxes the layout while preserving the topology. Ground nets are *excluded* from the graph so series circuits stay linear instead of collapsing into triangles.
4. **Overlap removal** — Pairwise repulsion guarantees a configurable clearance between symbol bounding boxes.
5. **Ground-aware rotation** — A hard constraint forces any GND pin to point downward (SVG +y), so ground symbols always sit at the bottom of the page.
6. **Smart routing** — The SVG composer uses 3-segment Z-routes for 2-pin nets and horizontal/vertical bus trunks for 3+ pin nets.

## Installation

Requires Python >= 3.12 (pinned to 3.14 for development) and Node.js >= 18 if you want the `netlistsvg` backend.

```bash
# Python dependencies
uv sync

# Optional: install the ELK-based netlistsvg backend globally
npm install -g netlistsvg
```

## CLI Usage

```bash
# Single netlist
netlist2image circuit.cir --output-dir ./dataset/

# Directory of netlists
netlist2image ./netlists/ --output-dir ./dataset/ --variants 5

# Use the ELK-based netlistsvg backend instead of the default
netlist2image circuit.cir -o ./dataset/ --backend netlistsvg

# Override seed, show values, custom model map
netlist2image circuit.cir -o ./dataset/ --seed 42 --show-values --model-map ./my_models.yaml
```

### Output Layout

```
dataset/
├── manifest.jsonl
├── circuit_a.json              # Abstract Netlist JSON
└── circuit_a/
    ├── v0/
    │   ├── rendered.json       # Rendered Netlist JSON (with layout)
    │   ├── image.svg           # Vector schematic
    │   ├── image.png           # 4K raster schematic
    │   └── bboxes.json         # Per-element bounding boxes
    ├── v1/
    └── ...
```

## Library Usage

```python
from netlist2image import parse_netlist, render_netlist, rasterize_svg
from netlist2image.renderer.layout import compute_layout

# Parse
abstract = parse_netlist(open("circuit.cir").read())

# Render one variant
rendered = compute_layout(abstract, seed=0)
svg_string, bboxes = render_netlist(rendered)
png_bytes = rasterize_svg(svg_string)
```

## Project Structure

```
src/netlist2image/
├── cli.py           # Console entry point
├── core/
│   ├── models.py    # Pydantic v2 data models
│   ├── parser.py    # SPICE netlist parser
│   └── expressions.py  # Parameter expression evaluator
├── renderer/
│   ├── layout.py    # Topology-aware spring layout + overlap removal + ground-aware rotation
│   ├── composer.py  # SVG composition with smart orthogonal routing
│   └── rasterize.py # CairoSVG PNG rasterization
├── symbols/
│   ├── passive.py   # R, C, L, V, I symbols
│   ├── active.py    # D, Q, M, J, X symbols
│   └── fallback.py  # Black-box generic symbol
└── data/
    └── model_map.yaml  # Built-in model name → type mapping
```

## Running Tests

```bash
uv run pytest tests/ -v
```
