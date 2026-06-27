#!/usr/bin/env python3
"""
Build an Anycubic Slicer Next / Orca / Bambu-compatible 3MF with multiple
colored parts assigned to separate ACE extruder slots.

Each input part becomes a <part> (sub-volume) inside ONE assembled <object>,
so the slicer keeps them aligned as a single model but prints each in its
own filament. Reuses a reference project_settings.config (printer/filament
profile) so the file opens with the correct Anycubic Kobra 3 V2 4-color setup.

Usage:
    build_orca_3mf.py <output.3mf> <ref_dir> name1:slot:file1.stl [name2:slot:file2.stl ...]
"""

import sys
import zipfile
import shutil
import json
import numpy as np
import trimesh
from pathlib import Path

CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
BBL_NS  = "http://schemas.bambulab.com/package/2021"
PROD_NS = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"


def mesh_to_xml(mesh: trimesh.Trimesh, obj_id: int, uuid_suffix: str) -> str:
    """Serialize one mesh as a standalone <object> with <mesh>."""
    lines = [
        f'  <object id="{obj_id}" p:UUID="000d0000-0000-4000-8000-{uuid_suffix:0>12}" type="model">',
        '   <mesh>',
        '    <vertices>',
    ]
    v = mesh.vertices
    lines.append("".join(
        f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in v
    ))
    lines.append('    </vertices>')
    lines.append('    <triangles>')
    lines.append("".join(
        f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.faces
    ))
    lines.append('    </triangles>')
    lines.append('   </mesh>')
    lines.append('  </object>')
    return "\n".join(lines)


def build(output_path: Path, ref_dir: Path, parts: list[dict]):
    """
    parts: list of {name, slot (1-based extruder), mesh (trimesh), color (#hex)}
    """
    tmp = output_path.parent / (output_path.stem + "_build")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "3D" / "Objects").mkdir(parents=True)
    (tmp / "3D" / "_rels").mkdir(parents=True)
    (tmp / "Metadata").mkdir(parents=True)
    (tmp / "_rels").mkdir(parents=True)

    # ── Orient for printing: layer axis (Y) → build axis (Z) ────────────
    # Source meshes stack colors along +Y. Rotate +90° about X so the badge
    # lies flat on the bed (black base down, colors building up in +Z).
    rot = trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0])
    for p in parts:
        p["mesh"].apply_transform(rot)

    # ── Center in XY, rest flat on the bed (min Z = 0) ──────────────────
    all_v = np.vstack([p["mesh"].vertices for p in parts])
    cx = (all_v[:, 0].min() + all_v[:, 0].max()) / 2
    cy = (all_v[:, 1].min() + all_v[:, 1].max()) / 2
    min_z = all_v[:, 2].min()
    for p in parts:
        p["mesh"].apply_translation([-cx, -cy, -min_z])
    all_v = np.vstack([p["mesh"].vertices for p in parts])

    # ── Per-part geometry: one .model file per part (matches reference) ──
    geo_files = []  # (objectid, path)
    for i, p in enumerate(parts, start=1):
        rel = f"3D/Objects/part_{i}_{p['name']}.model"
        geo_model = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE_NS}" '
            f'xmlns:BambuStudio="{BBL_NS}" xmlns:p="{PROD_NS}" requiredextensions="p">\n'
            ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
            ' <resources>\n'
            + mesh_to_xml(p["mesh"], i, f"{i:012d}") +
            '\n </resources>\n <build/>\n</model>\n'
        )
        (tmp / rel).write_text(geo_model)
        geo_files.append((i, rel))

    # ── Main 3dmodel.model: one assembled object referencing all parts ──
    ASSEMBLED_ID = 100
    components = "\n".join(
        f'    <component p:path="/{rel}" objectid="{oid}" '
        f'p:UUID="000d0000-0000-4000-9000-{oid:012d}" '
        f'transform="1 0 0 0 1 0 0 0 1 0 0 0"/>'
        for oid, rel in geo_files
    )
    main_model = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE_NS}" '
        f'xmlns:BambuStudio="{BBL_NS}" xmlns:p="{PROD_NS}" requiredextensions="p">\n'
        ' <metadata name="Application">CasaDeHodson-3DBuilder</metadata>\n'
        ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
        ' <metadata name="Copyright"></metadata>\n'
        ' <metadata name="CreationDate">2026-06-27</metadata>\n'
        ' <metadata name="ModificationDate">2026-06-27</metadata>\n'
        ' <resources>\n'
        f'  <object id="{ASSEMBLED_ID}" p:UUID="00000064-0000-4000-8000-000000000064" type="model">\n'
        '   <components>\n'
        f'{components}\n'
        '   </components>\n'
        '  </object>\n'
        ' </resources>\n'
        ' <build p:UUID="00000001-0000-4000-8000-000000000001">\n'
        # Place at bed center of Kobra 3 Max (420/2 = 210), resting on bed (Z=0).
        f'  <item objectid="{ASSEMBLED_ID}" p:UUID="00000002-0000-4000-8000-000000000002" '
        f'transform="1 0 0 0 1 0 0 0 1 210 210 0" printable="1"/>\n'
        ' </build>\n</model>\n'
    )
    (tmp / "3D" / "3dmodel.model").write_text(main_model)

    # ── model_settings.config: assign extruder per part ─────────────────
    part_xml = []
    for i, p in enumerate(parts, start=1):
        part_xml.append(
            f'    <part id="{i}" subtype="normal_part">\n'
            f'      <metadata key="name" value="{p["name"]}"/>\n'
            f'      <metadata key="matrix" value="1 0 0 0 1 0 0 0 1 0 0 0 0 0 0 1"/>\n'
            f'      <metadata key="extruder" value="{p["slot"]}"/>\n'
            f'      <mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" '
            f'facets_reversed="0" backwards_edges="0"/>\n'
            f'    </part>'
        )
    model_settings = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n'
        f'  <object id="{ASSEMBLED_ID}">\n'
        '    <metadata key="name" value="hood_ornament"/>\n'
        '    <metadata key="extruder" value="1"/>\n'
        + "\n".join(part_xml) + "\n"
        '  </object>\n'
        '  <plate>\n'
        '    <metadata key="plater_id" value="1"/>\n'
        '    <metadata key="plater_name" value=""/>\n'
        '    <metadata key="locked" value="false"/>\n'
        '    <model_instance>\n'
        f'      <metadata key="object_id" value="{ASSEMBLED_ID}"/>\n'
        '      <metadata key="instance_id" value="0"/>\n'
        '    </model_instance>\n'
        '  </plate>\n'
        '</config>\n'
    )
    (tmp / "Metadata" / "model_settings.config").write_text(model_settings)

    # ── project_settings.config: reuse reference profile, set our colors ─
    ref_cfg = ref_dir / "Metadata" / "project_settings.config"
    cfg = json.loads(ref_cfg.read_text())
    colors = [p["color"] for p in parts]
    n = len(parts)
    cfg["filament_colour"] = colors
    # Pad single-value/per-filament lists to n entries where appropriate
    def padlist(key, n):
        if key in cfg and isinstance(cfg[key], list) and len(cfg[key]) >= 1:
            base = cfg[key]
            if len(base) < n:
                cfg[key] = [base[0]] * n
            else:
                cfg[key] = base[:n]
    for key in ["filament_type","filament_settings_id","filament_ids","filament_vendor",
                "nozzle_temperature","nozzle_temperature_initial_layer","filament_diameter",
                "filament_density","filament_cost","filament_flow_ratio","filament_max_volumetric_speed",
                "default_filament_colour","filament_is_support"]:
        padlist(key, n)
    (tmp / "Metadata" / "project_settings.config").write_text(json.dumps(cfg, indent=4))

    # ── slice_info.config (minimal) ─────────────────────────────────────
    slice_info = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config>\n'
        '  <header>\n'
        '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n'
        '    <header_item key="X-BBL-Client-Version" value="01.03.09.03"/>\n'
        '  </header>\n'
        '  <plate>\n'
        '    <metadata key="index" value="1"/>\n'
        f'    <metadata key="filament_colors" value="{ ",".join(colors) }"/>\n'
        '  </plate>\n'
        '</config>\n'
    )
    (tmp / "Metadata" / "slice_info.config").write_text(slice_info)

    # ── Relationship + content-type files ──────────────────────────────
    (tmp / "[Content_Types].xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        ' <Default Extension="png" ContentType="image/png"/>\n'
        ' <Default Extension="gcode" ContentType="text/x.gcode"/>\n'
        '</Types>\n'
    )
    (tmp / "_rels" / ".rels").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>\n'
    )
    geo_rels = "\n".join(
        f' <Relationship Target="/{rel}" Id="rel-{oid}" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>'
        for oid, rel in geo_files
    )
    (tmp / "3D" / "_rels" / "3dmodel.model.rels").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        f'{geo_rels}\n'
        '</Relationships>\n'
    )

    # ── Zip it up ───────────────────────────────────────────────────────
    if output_path.exists():
        output_path.unlink()
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(tmp.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(tmp).as_posix())
    shutil.rmtree(tmp)
    return output_path


if __name__ == "__main__":
    out  = Path(sys.argv[1])
    ref  = Path(sys.argv[2])
    spec = sys.argv[3:]
    parts = []
    # default color cycle if not given: name:slot:file[:#hex]
    DEFAULT_COLORS = ["#000000", "#FFFFFF", "#1AB82E", "#FFDC14"]
    for i, s in enumerate(spec):
        bits = s.split(":")
        name, slot, fpath = bits[0], int(bits[1]), bits[2]
        color = bits[3] if len(bits) > 3 else DEFAULT_COLORS[i % len(DEFAULT_COLORS)]
        mesh = trimesh.load(fpath, force="mesh")
        parts.append({"name": name, "slot": slot, "mesh": mesh, "color": color})
    result = build(out, ref, parts)
    print(f"Built {result}  ({result.stat().st_size//1024} KB)")
