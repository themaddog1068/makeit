# Dr K's Kurios — Fluted Pin-Cushion Bowl

Final production bowl: rounded hand-thrown belly, broad/shallow/rounded clay-pressed
flutes, smooth interior, inward retaining lip, and an engraved tulip-bobbin + Studio-ring
logo medallion on the inside floor.

- **Size:** 150 × 150 × 76mm, single color (filament choice: Pastel Beige / Arctic Teal /
  Charcoal). Print upright; supports ON for the inward lip overhang.
- **Output:** `/mnt/mybook/3d_models/Kurios_Fluted_Bowl/Kurios_Fluted_Bowl_150mm.3mf` (+ .stl, previews)

## KEY LESSON — why this is a from-scratch surface of revolution
Deforming the imported foundation mesh to add flutes produced **beaded** flutes, because
that mesh has an irregular triangulation whose vertices don't line up vertically — a
23-flute angular deformation samples each valley unevenly along its height. The fix:
**rebuild the bowl as a structured θ×z revolution grid** with the flutes baked into the
radius (`R = Rout(z) - A·(0.5+0.5·cos(N·θ))·fade(z)`). Vertices align with the flutes →
continuous, G2-smooth, no facets, no beads. Also: do NOT Taubin-smooth a fluted mesh
(it ripples across the corrugations = egg-carton beads).

## Files
- `build_fluted_bowl.py` — the parametric builder (structured revolution + flutes + lip,
  then boolean-engraves the logo).
- `outer_profile_fit.npy` — fitted outer-radius-vs-z curve (the hand-thrown belly profile).
- Logo cutter: extrude `kurios_symbol_traced.svg` (offset r=0.18, scale 0.78) + a Studio
  lattice ring (ro=15, ri=12.5, n=18, w=1.0), 4mm tall. Logo assets live in
  `/mnt/mybook/3d_models/pin cushion holders/kurios_logo/`.

## Tunable params (top of build_fluted_bowl.py)
`N_FLUTES=23`, `FLUTE_DEPTH=1.35`, `LIP_IN=2.8`, `fade()` controls foot-blend & rim-fade,
`NT=240` angular resolution.

## Print settings
See `/mnt/mybook/3d_models/Kurios_Fluted_Bowl/PRINT_SETTINGS.md` (Grid infill 10–15%,
3 walls, 5 top / 4 bottom layers, 0.2mm, supports on).
