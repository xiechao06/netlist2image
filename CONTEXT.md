# Domain Glossary: netlist2image

## Netlist
A SPICE-format textual description of an electronic circuit. Contains element statements that instantiate components and define connectivity via named nodes.

## Element
A single circuit component declared in a netlist. Examples: resistor (`R`), capacitor (`C`), inductor (`L`), independent voltage source (`V`), independent current source (`I`), diode (`D`), BJT (`Q`), MOSFET (`M`), subcircuit instance (`X`).

## Device Polarity
The specific semiconductor subtype rendered for a BJT or MOSFET element: `NPN` / `PNP` for BJTs, `NMOS` / `PMOS` for MOSFETs. Determined by looking up the referenced `.model` card in the netlist, then referenced `.lib` includes, then a built-in model map, then falling back to a generic symbol.

## Model Map
A mapping from SPICE model names (e.g., `2N3904`, `IRF540`) to Device Polarity values. Shipped as a built-in default and user-extensible via a YAML or JSON config file passed to the CLI.

## Parser Architecture
The netlist parser combines a line-based dispatcher for element type and node extraction with a small recursive-descent parser for parameter expressions and behavioral sources. Gives correctness where needed without the weight of a full SPICE grammar.

## Structural Directive
A SPICE directive required to understand circuit structure: `.subckt`, `.ends`, `.include`, `.lib`, and `.model`.

## Simulation Directive
A SPICE directive that controls analysis but does not affect connectivity or image generation: `.tran`, `.ac`, `.dc`, `.op`, `.noise`, `.tf`, `.print`, `.plot`, `.probe`. Recorded in the Abstract Netlist JSON for completeness but ignored by the renderer.

## Parameter Resolution
The limited evaluation of `.param` values needed to determine concrete element values or `.model` types. Does not include full SPICE-level expression evaluation for simulation analysis.

## Warnings
A list of non-fatal issues recorded in the Abstract Netlist JSON, separate from Parse Errors. Examples: an element was parsed successfully but its model name could not be resolved, so a generic symbol will be used.

## Label Style
The text rendered on Schematic Images. Configured globally per CLI run. Default is element identifiers only (e.g., `R1`, `Q2`). Optional flags include component values and node names. Keeps images clean and ML-friendly while preserving human inspectability.

## Netlist JSON
A structured representation of a SPICE netlist optimized for downstream image generation and ML training. Captures element types, node connectivity, parameter values, and positional metadata. Excludes raw SPICE simulation directives and `.model` card details unless explicitly opted in.

## Supported Dialect
The parser targets the common subset of ngspice, LTspice, and PSpice netlist syntax, plus widely-used extensions (behavioral sources, switches, subcircuits). Vendor-specific `.option` cards and proprietary device models are parsed best-effort.

## Black-Box Fallback
A generic rectangular symbol used in the schematic image when an element type is recognized by the parser but has no dedicated visual symbol in the symbol library. The element's name, pins, and connectivity are preserved so the rendered circuit remains complete and the training data is not silently corrupted.

## Schematic Image
A rendered 2-D diagram generated from a Netlist JSON. Shows circuit elements as recognizable symbols connected by wires. Produced as PNG raster and SVG vector sources for ML training.

## Flattened Netlist
A Netlist JSON in which every subcircuit instance (`X`) has been expanded into its constituent primitive elements. Original `X` instance names and pin mappings are retained as provenance metadata so hierarchical patterns remain recoverable.

## Abstract Netlist JSON
The canonical output of parsing. Contains element types, names, node connectivity, raw parameter strings, normalized numeric values, and net definitions. Contains no layout or visual information.

## Rendered Netlist JSON
The output of the rendering stage. Extends an Abstract Netlist JSON with layout positions, element rotations, and bounding boxes for Schematic Image generation.

## Rendering Stack
The image-generation pipeline: NetworkX for spring-based graph layout, a custom Python SVG composer for symbol placement and wire routing, hand-authored SVG path primitives for each element symbol, and cairosvg for rasterizing SVG to PNG.

## CLI
The command-line entry point installed as `netlist2image`. Accepts either a single `.cir`/`.sp` netlist file or a directory of netlist files. Writes Training Samples to a specified output directory.

## Library API
The Python package API exposed by `netlist2image`. Provides `parse()`, `render()`, `rasterize()`, and `convert_file()`/`convert_directory()` so the tool can be embedded in training pipelines or notebooks.

## Package Structure
The source-code organization: layered `src/netlist2image/` layout with `core/` (parsing, expression evaluation, netlist data models), `renderer/` (layout, SVG composition, rasterization), `symbols/` (hand-authored SVG path primitives), and `data/` (built-in model map).

## Netlist Models
The Pydantic v2 data classes that define the Abstract Netlist JSON and Rendered Netlist JSON schemas. Provide runtime validation, serialization, and JSON Schema generation for the domain objects.

## Output Layout
The directory structure produced by the CLI for a single input netlist: one Abstract Netlist JSON at the root, a subdirectory named after the netlist, and one subdirectory per Layout Variant containing `rendered.json`, `image.png`, `image.svg`, and `bboxes.json`. A `manifest.jsonl` at the output root maps each input netlist and variant to its output paths.

## Training Sample
One complete data record produced from a single input netlist. Contains: (1) the Abstract Netlist JSON, (2) one or more Schematic Image variants, (3) SVG sources, and (4) bounding-box annotations for each element symbol.

## Layout Variant
One possible visual arrangement of the same Netlist JSON. Multiple variants are generated per netlist (typically 3–5) using spring-based graph layout with randomized seeds to teach downstream models that connectivity, not absolute position, carries meaning.

## Symbol Style
The default visual appearance of Schematic Images: black line-art symbols on a white background, with no shadows, gradients, or decorative effects. Keeps the dataset visually consistent and easy to augment.

## Parse Errors
A list of netlist lines that could not be parsed or were skipped during conversion, recorded in the Abstract Netlist JSON. Allows downstream training scripts to filter or audit samples without failing the entire batch.

## Ground Alias
Any node name commonly used as circuit ground in SPICE netlists (e.g., `0`, `GND`, `VSS`, `VEE`, `AGND`, `DGND`). The parser normalizes all recognized ground aliases to a canonical `GND` node while preserving the original SPICE name as metadata.

## Layout Engine
The placement algorithm for Schematic Images. Uses NetworkX spring layout followed by grid snapping, overlap removal, and auto-scaling. Configurable via seed and iteration count to produce Layout Variants.

## Base Seed
The deterministic starting seed for a netlist's Layout Variants. Derived from a stable hash of the input netlist file path by default. Combined with the variant index to produce per-variant seeds. Can be overridden via CLI flags.

## Canvas
The fixed-size drawing surface for each Schematic Image. Default resolution is 4K (3840 × 2160 pixels). The Layout Engine auto-scales the circuit to fit within the Canvas while preserving aspect ratio.

## Wire Style
The visual routing mode for wires connecting element pins. `straight` draws direct point-to-point lines. `orthogonal` draws only horizontal and vertical segments, like a traditional schematic editor. Default is `straight` with `orthogonal` available as a CLI option.

## Ground Symbol
The standard schematic earth/ground symbol rendered at any node normalized to `GND`, replacing a plain node dot.
