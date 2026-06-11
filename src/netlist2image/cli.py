"""Command-line interface for netlist2image."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import click
import yaml

from netlist2image.core.models import AbstractNetlist
from netlist2image.core.parser import parse_netlist
from netlist2image.renderer.composer import render_netlist
from netlist2image.renderer.layout import compute_layout
from netlist2image.renderer.netlistsvg_backend import render_with_netlistsvg
from netlist2image.renderer.rasterize import rasterize_svg


def _load_model_map(path: Optional[Path]) -> dict[str, str]:
    """Load model name -> device type mapping."""
    built_in = Path(__file__).with_name("data") / "model_map.yaml"
    data: dict[str, str] = {}
    if built_in.exists():
        with open(built_in, "r") as f:
            data.update(yaml.safe_load(f) or {})
    if path and path.exists():
        with open(path, "r") as f:
            data.update(yaml.safe_load(f) or {})
    return {k.upper(): v.upper() for k, v in data.items()}


def _resolve_model_type(
    model_name: Optional[str],
    models_from_netlist: dict[str, str],
    model_map: dict[str, str],
) -> Optional[str]:
    """Resolve a model name to a device type (NPN, PNP, NMOS, PMOS)."""
    if not model_name:
        return None
    mu = model_name.upper()
    if mu in models_from_netlist:
        return models_from_netlist[mu]
    if mu in model_map:
        return model_map[mu]
    return None


@click.command()
@click.argument("input_path", type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", "-o", type=click.Path(path_type=Path), default=Path("output"))
@click.option("--variants", "-n", type=int, default=3, help="Number of layout variants per netlist.")
@click.option("--seed", type=int, default=None, help="Override base seed for deterministic layout.")
@click.option("--random-seed", is_flag=True, help="Use random seed instead of deterministic.")
@click.option("--wire-style", type=click.Choice(["straight", "orthogonal"]), default="orthogonal")
@click.option("--show-labels/--no-labels", default=True, help="Show element IDs on schematic.")
@click.option("--show-values/--no-values", default=True, help="Show component values.")
@click.option("--show-node-names/--no-node-names", default=True, help="Show node names on wires.")
@click.option("--model-map", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--canvas-width", type=int, default=3840)
@click.option("--canvas-height", type=int, default=2160)
@click.option("--backend", type=click.Choice(["internal", "netlistsvg"]), default="internal",
              help="Rendering backend: internal (custom SVG) or netlistsvg (ELK-based layout).")
def main(
    input_path: Path,
    output_dir: Path,
    variants: int,
    seed: Optional[int],
    random_seed: bool,
    wire_style: str,
    show_labels: bool,
    show_values: bool,
    show_node_names: bool,
    model_map: Optional[Path],
    canvas_width: int,
    canvas_height: int,
    backend: str,
) -> None:
    """Convert SPICE netlist(s) to schematic images for ML training."""
    output_dir.mkdir(parents=True, exist_ok=True)
    model_map_data = _load_model_map(model_map)

    files: List[Path] = []
    if input_path.is_file():
        files = [input_path]
    elif input_path.is_dir():
        files = sorted(
            p for p in input_path.iterdir() if p.suffix.lower() in {".cir", ".sp", ".net"}
        )
        if not files:
            click.echo("No .cir, .sp, or .net files found in directory.", err=True)
            sys.exit(1)

    manifest: List[dict[str, object]] = []

    for netlist_file in files:
        click.echo(f"Processing {netlist_file.name} ...")
        text = netlist_file.read_text(encoding="utf-8", errors="replace")
        abstract = parse_netlist(text)

        # Resolve model types from netlist .model cards
        models_from_netlist: dict[str, str] = {}
        for line in text.splitlines():
            tokens = line.strip().split()
            if len(tokens) >= 3 and tokens[0].upper() == ".MODEL":
                models_from_netlist[tokens[1].upper()] = tokens[2].upper()

        # Apply model map to elements
        for elem in abstract.elements:
            if elem.model:
                resolved = _resolve_model_type(elem.model, models_from_netlist, model_map_data)
                if resolved:
                    elem.model = resolved
                else:
                    abstract.warnings.append(
                        f"Could not resolve model type for {elem.id} model={elem.model}"
                    )

        # Write abstract JSON
        stem = netlist_file.stem
        abstract_path = output_dir / f"{stem}.json"
        with open(abstract_path, "w") as f:
            json.dump(abstract.model_dump(), f, indent=2)

        # Create variant directory
        variant_dir = output_dir / stem
        variant_dir.mkdir(exist_ok=True)

        # Determine base seed
        if random_seed:
            import random

            base_seed = random.randint(0, 2**31 - 1)
        elif seed is not None:
            base_seed = seed
        else:
            base_seed = int(hashlib.sha256(str(netlist_file).encode()).hexdigest(), 16) % (2**31)

        for v in range(variants):
            variant_seed = base_seed + v
            v_dir = variant_dir / f"v{v}"
            v_dir.mkdir(exist_ok=True)

            if backend == "netlistsvg":
                # Use netlistsvg backend — one variant only (no seed variation)
                if v > 0:
                    # netlistsvg doesn't support seeded variants; skip extras
                    continue
                svg_string, bboxes = render_with_netlistsvg(
                    abstract,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                )
                # No rendered.json for netlistsvg backend (layout is opaque)
                rendered_path = v_dir / "rendered.json"
                with open(rendered_path, "w") as f:
                    json.dump({"backend": "netlistsvg"}, f)
            else:
                rendered = compute_layout(
                    abstract,
                    seed=variant_seed,
                    canvas_width=canvas_width,
                    canvas_height=canvas_height,
                )
                # Rendered JSON
                rendered_path = v_dir / "rendered.json"
                with open(rendered_path, "w") as f:
                    json.dump(rendered.model_dump(), f, indent=2)

                # SVG
                svg_string, bboxes = render_netlist(
                    rendered,
                    show_labels=show_labels,
                    show_values=show_values,
                    show_node_names=show_node_names,
                    wire_style=wire_style,
                )

            svg_path = v_dir / "image.svg"
            with open(svg_path, "w") as f:
                f.write(svg_string)

            # PNG
            png_bytes = rasterize_svg(svg_string, width=canvas_width, height=canvas_height)
            png_path = v_dir / "image.png"
            with open(png_path, "wb") as f:
                f.write(png_bytes)

            # Bounding boxes
            bboxes_path = v_dir / "bboxes.json"
            with open(bboxes_path, "w") as f:
                json.dump(bboxes, f, indent=2)

            manifest.append(
                {
                    "netlist": str(netlist_file),
                    "variant": v,
                    "seed": variant_seed if backend == "internal" else 0,
                    "abstract_json": str(abstract_path.relative_to(output_dir)),
                    "rendered_json": str(rendered_path.relative_to(output_dir)),
                    "svg": str(svg_path.relative_to(output_dir)),
                    "png": str(png_path.relative_to(output_dir)),
                    "bboxes": str(bboxes_path.relative_to(output_dir)),
                }
            )

    # Write manifest
    manifest_path = output_dir / "manifest.jsonl"
    with open(manifest_path, "w") as f:
        for entry in manifest:
            f.write(json.dumps(entry) + "\n")

    click.echo(f"Done. Output in {output_dir}")


if __name__ == "__main__":
    main()
