#!/usr/bin/env python3
"""
Dr K's Kurios — fluted pin-cushion bowl builder.

Builds the bowl as a CLEAN structured surface-of-revolution (vertices aligned in
theta x z rings) with the flutes baked into the math. This is the key technique:
deforming an imported/irregular mesh produces beaded flutes because the triangulation
isn't aligned to the flutes; a structured revolution gives continuous, G2-smooth,
finger-pressed-in-clay flutes with no facets or beads.

Features:
  - rounded "hand-thrown" belly (outer profile from a fitted curve)
  - broad, shallow, fully rounded vertical flutes (raised-cosine), fading into the
    foot and softly below the rim
  - smooth interior + inward retaining lip (built into the inner profile)
  - engraved tulip-bobbin logo + Studio lattice ring on the inside floor (boolean)

Output: STL + Orca/Anycubic 3MF (single color) -> /mnt/mybook/3d_models/Kurios_Fluted_Bowl/

Reuses: ../../build_orca_3mf.py ; logo cutter from the kurios_logo assets.
"""
import sys, numpy as np, trimesh, time
from pathlib import Path
sys.path.insert(0, "/home/themaddog1068/3d-builder")
from build_orca_3mf import build as orca_build

HERE = Path(__file__).parent
OUT  = Path("/mnt/mybook/3d_models/Kurios_Fluted_Bowl")
LOGO_CUTTER = Path("/tmp/.../logo_ring.stl")  # see README: extrude kurios_symbol_traced.svg + Studio ring

# --- geometry params ---
H, FLOORZ, WALL = 76.1, 11.0, 6.0
NT = 240                 # angular resolution (>=10 per flute -> smooth)
N_FLUTES, FLUTE_DEPTH = 23, 1.35
LIP_IN = 2.8             # inward lip projection (mm)
ofit = np.load(HERE / "outer_profile_fit.npy")   # outer radius vs z (fitted from foundation)

def Rout(z): return np.polyval(ofit, np.clip(z, 0, H))
def ss(t): t = np.clip(t, 0, 1); return t*t*(3-2*t)
def fade(z): return ss((z-14)/8.0) * (1-ss((z-71)/4.0))         # foot blend + rim fade
def flute(theta, z): return FLUTE_DEPTH*(0.5+0.5*np.cos(N_FLUTES*theta))*fade(z)

def build_bowl():
    th = np.linspace(0, 2*np.pi, NT, endpoint=False)
    Vout = np.array([np.stack([(Rout(z)-flute(th,z))*np.cos(th),
                               (Rout(z)-flute(th,z))*np.sin(th), np.full(NT,z)],1)
                     for z in np.linspace(0,H,150)])
    Vin = []
    for z in np.linspace(FLOORZ,H,120):
        rin = Rout(z)-WALL - LIP_IN*ss((z-(H-5))/5.0)          # lip pulls inner in near top
        Vin.append(np.stack([rin*np.cos(th), rin*np.sin(th), np.full(NT,z)],1))
    Vin = np.array(Vin)
    verts, faces = [], []
    def grid(G, flip):
        base=len(verts); nz,nt,_=G.shape
        for ring in G: verts.extend(ring)
        for i in range(nz-1):
            for j in range(nt):
                j2=(j+1)%nt
                a,b=base+i*nt+j,base+i*nt+j2; c,d=base+(i+1)*nt+j,base+(i+1)*nt+j2
                faces.extend([[a,b,d],[a,d,c]] if not flip else [[a,d,b],[a,c,d]])
        return base, nz
    ob,onz = grid(Vout,False); ib,inz = grid(Vin,True)
    cb=len(verts); verts.append([0,0,0])
    for j in range(NT): faces.append([cb,ob+(j+1)%NT,ob+j])
    cf=len(verts); verts.append([0,0,FLOORZ])
    for j in range(NT): faces.append([cf,ib+j,ib+(j+1)%NT])
    otop,itop = ob+(onz-1)*NT, ib+(inz-1)*NT
    for j in range(NT):
        j2=(j+1)%NT
        faces.extend([[otop+j,otop+j2,itop+j2],[otop+j,itop+j2,itop+j]])
    m=trimesh.Trimesh(vertices=np.array(verts),faces=np.array(faces),process=True)
    m.merge_vertices(); trimesh.repair.fix_normals(m)
    return m

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    bowl = build_bowl()
    print(f"bowl: {len(bowl.faces):,}f watertight={bowl.is_watertight}")
    logo = trimesh.load(str(LOGO_CUTTER), force="mesh")
    logo.apply_translation([0,0,(FLOORZ-0.5)-logo.bounds[0][2]])   # engrave 0.5mm
    bowl = trimesh.boolean.difference([bowl,logo], engine="blender", check_volume=False)
    bowl.export(str(OUT/"Kurios_Fluted_Bowl_150mm.stl"))
    orca_build(OUT/"Kurios_Fluted_Bowl_150mm.3mf",
               [{"name":"kurios_fluted_bowl","slot":1,"mesh":bowl,"color":"#EDE3CF"}],
               orient_rotate=False)
    print("saved STL + 3MF")
