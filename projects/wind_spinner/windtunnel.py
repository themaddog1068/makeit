#!/usr/bin/env python3
"""
Simplified 'virtual wind tunnel' for a vertical-axis wind spinner.

Quasi-static drag model (NOT full CFD): wind blows horizontally; each mesh face
that the wind strikes gets a pressure force ~ projected area; we sum the torque
about the vertical (Z) axis. Sweeping the rotor through 360 deg tells us:
  - mean torque  (drive strength in a given wind)
  - whether torque keeps a consistent sign at every angle (self-starts from any
    rest position) or has dead spots (could stall)
Useful for COMPARING blade designs and checking light-wind starting.

Usage: windtunnel.py blades.stl [wind_mps] [n_angles]
"""
import sys, numpy as np, trimesh

RHO = 1.225          # air density kg/m^3
CD  = 1.2            # flat-plate-ish drag coefficient

def torque_curve(mesh, wind_dir=np.array([1,0,0.0]), V=3.0, n=72):
    wind_dir = wind_dir/np.linalg.norm(wind_dir)
    q = 0.5*RHO*CD*V*V                      # dynamic pressure (Pa)
    tris = mesh.triangles
    centroids = tris.mean(axis=1)/1000.0    # mm -> m
    normals = mesh.face_normals
    areas = mesh.area_faces/1e6             # mm^2 -> m^2
    angles = np.linspace(0,360,n,endpoint=False)
    taus=[]
    for a in angles:
        th=np.radians(a); c,s=np.cos(th),np.sin(th)
        R=np.array([[c,-s,0],[s,c,0],[0,0,1]])
        nz=normals@R.T; cz=centroids@R.T
        d=nz@wind_dir                       # Wdir . normal ; <0 = windward face
        wind=d<0
        # flat-plate force acts along the face NORMAL (pressure perpendicular to surface):
        # F = q*A*(Wdir.n)*n  for windward faces -> magnitude ~ |Wdir.n|, dir along -n (downwind-ish)
        mag=(q*areas*d)[:,None]             # negative for windward
        F=mag*nz                            # force vectors along normals
        F[~wind]=0
        tau=(cz[:,0]*F[:,1]-cz[:,1]*F[:,0]).sum()   # torque about Z (N*m)
        taus.append(tau)
    return angles, np.array(taus)

if __name__=="__main__":
    f=sys.argv[1]; V=float(sys.argv[2]) if len(sys.argv)>2 else 3.0
    n=int(sys.argv[3]) if len(sys.argv)>3 else 72
    m=trimesh.load(f,force="mesh")
    ang,tau=torque_curve(m,V=V,n=n)
    mean=tau.mean();
    consistent = (tau>0).all() or (tau<0).all()
    # mNm for readability
    print(f"Wind {V} m/s ({V*3.6:.0f} km/h, V*2.24={V*2.237:.0f} mph)")
    print(f"  mean torque : {mean*1000:+.2f} mNm")
    print(f"  range       : {tau.min()*1000:+.2f} .. {tau.max()*1000:+.2f} mNm")
    print(f"  self-starts : {'YES (no dead spots)' if consistent else 'NO (sign flips -> possible stall angle)'}")
    # crude startup wind: torque scales V^2; find V where mean torque overcomes ~0.3 mNm bearing stiction
    STIC=0.3e-3
    if abs(mean)>1e-12:
        Vstart=V*np.sqrt(STIC/abs(mean))
        print(f"  est. startup wind (vs 0.3 mNm stiction): ~{Vstart:.1f} m/s ({Vstart*2.237:.1f} mph)")
