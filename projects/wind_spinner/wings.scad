// Wind Spinner — parametric wing generator (v2: wind-driven, cupped + pitched, large)
// Core ball: bore along Z = VERTICAL AXLE; opening on the BOTTOM; equator outer r ~28.4 at z=0.
// Blades radiate around the vertical axle and sweep UP (self-supporting, ball = low point).
// For a vertical-axis turbine driven by a light breeze, each blade is:
//   - CUPPED  (concave scoop cross-section) to catch air (drag torque, self-starting)
//   - PITCHED (angled face) so horizontal wind pushes it tangentially
//   - LARGE   (long radial blades on the 420mm Max bed) for leverage in slight wind
// All blades share cup+pitch sign => consistent spin direction.
//
// Render: -D RENDER="preview|blades|ball"   Style: -D STYLE="flower|helix|nautilus"

STYLE        = "flower";
RENDER       = "preview";
BALL_STL     = "core_ball_norm.stl";

blade_count  = 6;
root_r       = 20;     // start inside the equator so roots fuse into the ball
length       = 150;    // radial blade length (BIG for light-wind torque; ~2*(28+150)=356mm dia < 420 bed)
thickness    = 2.4;    // plate thickness
rise         = 34;     // upward sweep (deg) — self-support + lift
base_w       = 34;     // chord width at root
tip_w        = 14;     // chord width at tip
cup          = 9;      // scoop concavity depth (mm) — wind catch
pitch        = 38;     // blade angle of attack (deg) — converts wind to tangential torque
twist        = 0;      // extra twist along blade (helix uses this)
curve        = 0.0;    // tangential bend (nautilus uses this)
wave         = 0;      // vertical wave amplitude (mm) along the blade
wave_n       = 1.5;    // number of wave cycles along the blade
wave_phase   = 0;      // per-blade wave phase offset (deg) — staggers blades vertically
taper_pow    = 1.2;
$fn          = 40;
STEPS        = 24;

// ---- cupped (concave) chord: width w along local Y, scoop bulges in local Z, thin in X ----
module chord(w, th, cupd) {
    N = 12;
    top = [for (i=[0:N]) let(t=i/N, y=-w/2+w*t) [y,  cupd*(1-pow(2*t-1,2)) + th/2]];
    bot = [for (i=[N:-1:0]) let(t=i/N, y=-w/2+w*t) [y, cupd*(1-pow(2*t-1,2)) - th/2]];
    rotate([0,90,0])                    // extrude axis Z -> X (thin radial)
      linear_extrude(0.9, center=true)
        polygon(concat(top,bot));
}

// ---- swept blade: hull cupped chords along a rising (optionally bending/twisting) path ----
module swept_blade(ph=0) {
    for (i=[0:STEPS-1]) hull() for (j=[i,i+1]) {
        t  = j/STEPS;
        px = root_r + length*t*cos(rise);
        pz = length*t*sin(rise) + wave*sin(360*wave_n*t + ph);
        py = curve*(t*t)*length;
        cw = max(base_w*pow(1-t,taper_pow) + tip_w*t, 1.0);
        cd = cup*(0.3+0.7*t);                  // cup deepens toward tip
        translate([px,py,pz])
          rotate([0,-rise,0])                  // align to rise
          rotate([twist*t,0,0])                // progressive twist (helix)
          chord(cw, thickness, cd);
    }
}

module one_blade(ph=0) { swept_blade(ph); }

SUBSET = "all";   // "all" | "even" | "odd" — to split blades across color slots
module blades() {
    for (i=[0:blade_count-1])
        if (SUBSET=="all" || (SUBSET=="even" && (i%2==0)) || (SUBSET=="odd" && (i%2==1)))
        rotate([0,0,360*i/blade_count])
          rotate([pitch,0,0])              // angle of attack about the radial axis
            one_blade(i*wave_phase);       // stagger each blade's wave for a layered side profile
}

module ball() { import(BALL_STL, convexity=8); }

if      (RENDER=="ball")   color([0.78,0.6,0.2]) ball();
else if (RENDER=="blades") blades();
else { color([0.80,0.55,0.15]) ball(); color([0.85,0.2,0.2]) blades(); }
