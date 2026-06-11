# ADR 0001: Rendering Stack — NetworkX + Custom SVG + CairoSVG

## Status
Accepted

## Context

`netlist2image` needs to convert parsed SPICE netlists into schematic diagrams for machine-learning training data. The core requirement is to generate **multiple randomized layout variants** per netlist so that downstream ML models learn that circuit topology (connectivity), not absolute position, is the ground truth.

We evaluated three broad approaches:

1. **schemdraw** — Purpose-built Python schematic library with high-quality symbols. Limited automatic layout; mostly manual placement. Would require us to write our own graph-to-placement logic on top of it.
2. **LCapy** — Python circuit analysis package that can draw schematics from netlists. Powerful but opinionated about symbol orientation and page layout; difficult to force randomized variant generation and custom styling.
3. **NetworkX + custom SVG renderer + CairoSVG** — Use NetworkX for spring-based graph layout, compose SVG ourselves from hand-authored path primitives, and rasterize with CairoSVG.

## Decision

We chose **NetworkX + custom SVG renderer + CairoSVG**.

## Consequences

### Positive

- **Full control over layout randomization**: We can generate N variants per netlist by varying the spring-layout seed, grid snapping, and overlap-removal parameters.
- **Consistent ML-friendly styling**: Black line-art on white background, no shadows or gradients. Easy to augment.
- **Bounded symbol set**: We only need to author SVG paths for the element types we care about. Everything else falls back to a labeled black box.
- **Lightweight dependencies**: No need for EDA toolchains, X11, or heavy GUI frameworks.
- **PNG + SVG dual output**: SVG sources are preserved for vector-based ML tasks; PNG is produced for raster-based models.

### Negative

- **More code to maintain**: We own the symbol library, wire routing, and layout algorithms.
- **Layout quality**: Spring layout does not produce publication-quality schematics. For very complex circuits the output can look like a "hairball." This is acceptable for ML training data but not for human documentation.
- **No autorouting**: Wires are straight lines (or optional orthogonal segments) without advanced crossing minimization.

## Alternatives Considered

| Approach | Why Rejected |
|---|---|
| schemdraw | No automatic graph layout; would still need NetworkX or similar for placement. Adds dependency without solving the hard problem. |
| LCapy | Too opinionated about schematic style; fights us on randomized layout and custom canvas sizes. |
| KiCad / NGSPICE CLI | Most realistic schematics, but CLI automation is brittle, slow, and requires external tool installation. Not suitable for batch dataset generation. |

## Notes

If layout quality becomes a bottleneck for ML accuracy, we can incrementally improve the renderer (hierarchical placement hints, better overlap removal, orthogonal wire routing) without changing the overall architecture.
