#!/usr/bin/env python3
"""
3D Model Builder — generates multi-color STL/3MF files from text descriptions.
Uses Claude to write OpenSCAD code, renders headlessly via xvfb, assembles 3MF for ACE.
Supports starting from an uploaded STL as a base.
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import anthropic
import trimesh
import numpy as np

load_dotenv(Path(__file__).parent / ".env")

NAS_OUTPUT_DIR = Path("/mnt/mybook/3d_models")
NAS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are an expert OpenSCAD programmer generating 3D models for FDM printing.
The printer is an Anycubic Kobra 3 Max with ACE 4-color system (up to 4 colors).

Rules:
- Output ONLY valid OpenSCAD code, no markdown fences, no explanation outside comments.
- For multi-color models, define each color region as a separate named module.
- Include a comment on the very first line declaring parts:
  // PARTS: base, accent, detail, highlight  (up to 4 names, matching ACE slots 1-4)
- Each part module must be self-contained and renderable on its own.
- Default layer height: 0.2mm. Nozzle: 0.4mm. Bed: 420x420mm max.
- All dimensions in millimeters. Use $fn=64 for smooth curves.
- When a base STL is provided via import(), keep it intact and only add/subtract geometry.
"""

COLOR_MAP = [
    [0.85, 0.15, 0.15],  # slot 1 — red
    [0.15, 0.35, 0.95],  # slot 2 — blue
    [0.10, 0.78, 0.20],  # slot 3 — green
    [0.95, 0.85, 0.10],  # slot 4 — yellow
]

PREVIEW_CAMERA = "0,0,0,55,0,25,200"
PREVIEW_SIZE   = "900,600"


def generate_openscad(description: str, base_stl_info: dict | None = None) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_msg = description
    if base_stl_info:
        user_msg = (
            f"Start from the provided STL file imported as: import(\"{base_stl_info['import_path']}\");\n"
            f"Base model dimensions (mm): {base_stl_info['dims']}\n"
            f"Bounding box min/max: {base_stl_info['bounds']}\n\n"
            f"Modification request: {description}"
        )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return message.content[0].text.strip()


def analyze_stl(stl_path: Path) -> dict:
    """Extract dimensions and bounds from an uploaded STL for Claude context."""
    mesh = trimesh.load(str(stl_path), force="mesh")
    bounds = mesh.bounds
    dims = bounds[1] - bounds[0]
    return {
        "import_path": str(stl_path),
        "dims": f"X={dims[0]:.1f}  Y={dims[1]:.1f}  Z={dims[2]:.1f}",
        "bounds": f"min({bounds[0][0]:.1f},{bounds[0][1]:.1f},{bounds[0][2]:.1f})  "
                  f"max({bounds[1][0]:.1f},{bounds[1][1]:.1f},{bounds[1][2]:.1f})",
    }


def render_part(scad_code: str, module_name: str, output_stl: Path, extra_files: list[Path] = None) -> bool:
    """Render a single module to STL. Copies any extra files (e.g. base STL) alongside."""
    wrapper = scad_code + f"\n\n{module_name}();\n"
    with tempfile.NamedTemporaryFile(suffix=".scad", mode="w", delete=False,
                                      dir=output_stl.parent) as f:
        f.write(wrapper)
        scad_file = Path(f.name)
    try:
        result = subprocess.run(
            ["openscad", "--export-format", "binstl", "-o", str(output_stl), str(scad_file)],
            capture_output=True, text=True, timeout=120,
        )
        return output_stl.exists() and output_stl.stat().st_size > 0
    finally:
        scad_file.unlink(missing_ok=True)


def render_preview(scad_code: str, parts: list[str], output_png: Path) -> bool:
    """Render a coloured composite preview PNG via xvfb-run + OpenSCAD."""
    color_defs = ""
    for i, part in enumerate(parts):
        r, g, b = COLOR_MAP[i % len(COLOR_MAP)]
        color_defs += f"  color([{r},{g},{b}]) {part}();\n"

    preview_scad = scad_code + f"\n\n// Preview composite\n{color_defs}\n"

    with tempfile.NamedTemporaryFile(suffix=".scad", mode="w", delete=False,
                                      dir=output_png.parent) as f:
        f.write(preview_scad)
        scad_file = Path(f.name)
    try:
        result = subprocess.run(
            [
                "xvfb-run", "-a",
                "openscad",
                "--render",
                "--camera", PREVIEW_CAMERA,
                "--imgsize", PREVIEW_SIZE,
                "--colorscheme", "Tomorrow Night",
                "-o", str(output_png),
                str(scad_file),
            ],
            capture_output=True, text=True, timeout=180,
        )
        return output_png.exists() and output_png.stat().st_size > 0
    finally:
        scad_file.unlink(missing_ok=True)


def extract_parts(scad_code: str) -> list[str]:
    for line in scad_code.splitlines():
        if "// PARTS:" in line:
            parts_str = line.split("// PARTS:")[1].strip()
            return [p.strip() for p in parts_str.split(",") if p.strip()]
    # Fallback: collect all module names
    modules = []
    for line in scad_code.splitlines():
        if line.startswith("module "):
            name = line.split("module ")[1].split("(")[0].strip()
            modules.append(name)
    return modules


def build_3mf(stl_paths: list[Path], part_names: list[str], out_path: Path) -> Path:
    scene = trimesh.scene.Scene()
    for i, (stl, name) in enumerate(zip(stl_paths, part_names)):
        mesh = trimesh.load(str(stl), force="mesh")
        if mesh.is_empty:
            continue
        rgb = COLOR_MAP[i % len(COLOR_MAP)]
        mesh.visual.face_colors = [int(c * 255) for c in rgb] + [255]
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    scene.export(str(out_path))
    return out_path


def generate(description: str, job_name: str = "model", base_stl: Path | None = None) -> dict:
    job_dir = NAS_OUTPUT_DIR / job_name
    job_dir.mkdir(parents=True, exist_ok=True)

    base_stl_info = None
    if base_stl and base_stl.exists():
        # Copy base STL into job dir so OpenSCAD import() can find it
        dest = job_dir / base_stl.name
        dest.write_bytes(base_stl.read_bytes())
        base_stl_info = analyze_stl(dest)
        base_stl_info["import_path"] = base_stl.name  # relative, for OpenSCAD
        print(f"[base]  {base_stl.name}  {base_stl_info['dims']}")

    print(f"[1/5] Asking Claude to design: {description}")
    scad_code = generate_openscad(description, base_stl_info)

    scad_out = job_dir / f"{job_name}.scad"
    scad_out.write_text(scad_code)
    print(f"[2/5] OpenSCAD saved → {scad_out.relative_to(NAS_OUTPUT_DIR.parent)}")

    parts = extract_parts(scad_code)
    if not parts:
        return {"error": "No parts found in generated code", "scad": str(scad_out)}

    print(f"[3/5] Rendering {len(parts)} part(s): {parts}")
    stl_files = []
    for part in parts:
        stl_path = job_dir / f"{part}.stl"
        ok = render_part(scad_code, part, stl_path)
        if ok:
            stl_files.append(stl_path)
            print(f"       OK  {stl_path.name}")
        else:
            print(f"       FAIL {part}")

    if not stl_files:
        return {"error": "All renders failed — check generated .scad", "scad": str(scad_out)}

    print(f"[4/5] Rendering preview image...")
    preview_png = job_dir / "preview.png"
    preview_ok = render_preview(scad_code, parts, preview_png)
    if preview_ok:
        print(f"       OK  preview.png")
    else:
        print(f"       WARN preview render failed (non-fatal)")
        preview_png = None

    print(f"[5/5] Assembling 3MF...")
    tmf_path = job_dir / f"{job_name}.3mf"
    build_3mf(stl_files, parts, tmf_path)

    result = {
        "job": job_name,
        "parts": parts,
        "scad": str(scad_out),
        "stl_files": [str(s) for s in stl_files],
        "3mf": str(tmf_path),
        "preview": str(preview_png) if preview_png else None,
        "nas_path": str(job_dir),
    }
    print(f"\nDone!  {job_dir}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: generate.py 'description' [job_name] [base.stl]")
        sys.exit(1)
    desc    = sys.argv[1]
    name    = sys.argv[2] if len(sys.argv) > 2 else "model"
    base    = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    result  = generate(desc, name, base)
    print(json.dumps(result, indent=2))
