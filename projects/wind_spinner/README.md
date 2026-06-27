# Wind Spinner — parametric wings

Parametric generator for wind-spinner wings that mount on the fixed core ball and spin
on a vertical axle (horizontal-plane / cup-anemometer style) in a light breeze.

## Files
- `wings.scad` — parametric wing generator (styles: flower, helix, nautilus).
  Imports the normalized core ball and adds cupped + pitched + (optionally) twisted/waved
  blades that sweep up around the equator.
- `windtunnel.py` — simplified "virtual wind tunnel": quasi-static drag model (force along
  face normals) that rotates the rotor 360° and reports mean torque, whether it self-starts
  (sign-consistent torque), and an estimated startup wind speed. For comparing designs
  (not full CFD).
- `core_ball_norm.stl` — **NOT in git** (9MB; lives on NAS). Normalized core ball: centered,
  bore along Z, opening on the BOTTOM. Regenerate from the master core if needed (see below).

## HARD RULE
The core ball is **NEVER scaled** — it stays native so the **608 bearings (8×22×7mm, 22.5mm
bore)** fit exactly. Only the blade `length` scales to reach the target overall diameter.

## Regenerate the normalized ball
From the master `_bases/wind_spinner/core_spinner_base.stl` (on NAS): center it, rotate the
bore (Y in the raw STL) to Z, flip so the opening faces -Z (bottom), export
`core_ball_norm.stl`.

## Usage
```bash
# render a preview (PNG)
xvfb-run -a openscad -D 'STYLE="nautilus"' -D 'RENDER="preview"' \
  -D 'blade_count=6' -D 'twist=60' -D 'pitch=38' -D 'curve=0.8' -D 'rise=16' \
  -D 'wave=20' -D 'wave_n=2.2' -D 'wave_phase=60' -D 'length=158' \
  --camera "0,0,22,90,0,0,560" --imgsize 900,520 -o out.png wings.scad

# export blade STL (RENDER="blades"); SUBSET=even|odd splits blades across color slots
# wind tunnel
venv/bin/python projects/wind_spinner/windtunnel.py blades.stl 3.0
```

Final multi-color 3MF is assembled with `../../build_orca_3mf.py` (ball + blade subsets on
separate ACE slots). Project tracking + frozen recipes live in
`_bases/wind_spinner/WINDSPINNER_PROJECT.md` on the NAS.

## Key design facts
- Vertical axle (opening on bottom); blades spin in the horizontal plane.
- TWIST makes a vertical-axis rotor self-start (consistent torque at all angles); low-twist
  spiral/flower blades develop dead spots — add ~60° twist to fix.
- A per-blade `wave_phase` staggers the vertical wave so arms weave at different heights
  (side-profile visual impact) without blocking each other.
- Frozen design = Nautilus v2 (see WINDSPINNER_PROJECT.md for the full parameter recipe).
