# 3D Model Builder — Jarvishelper Pi

AI-powered 3D model generator running on Raspberry Pi 5.
Describe a model in plain English → get STL + 3MF files ready to slice for the Anycubic Kobra 3 Max with ACE color system.

---

## Hardware

| Item | Detail |
|---|---|
| Pi | Raspberry Pi 5 Model B Rev 1.1, 8 GB RAM |
| IP | 192.168.4.62 |
| NAS (primary storage) | WD My Book — `//192.168.5.244/My_Book_1230-1` → mounted at `/mnt/mybook` |
| NAS (media) | `//192.168.5.244/Public` → mounted at `/mnt/mytvs` |
| Printer | Anycubic Kobra 3 V2 Max, bed 420×420 mm |
| Color system | ACE (4 filament slots) |

---

## Web UI

Open in any browser on the local network:

```
http://192.168.4.62:5050
```

### Generating a new model
1. Type a description in the text box — be specific about colors, dimensions, and purpose.
2. *(Optional)* Drop or browse to an existing STL/3MF to use as a base to modify.
3. Click **Generate Model** — takes 30–90 seconds.
4. A rendered preview image appears on the right.
5. Download the `.3mf` (multi-color, ready for slicer) and/or individual `.stl` parts.

**Good description examples:**
- `A cable tidy clip with a red body and blue locking tab. 30mm wide, snaps onto a 20mm rail.`
- `Phone stand: black base 120mm wide, white arm, blue phone cradle. Adjustable angle.`
- `Modify the uploaded bracket to add four M3 mounting holes in the corners.` *(with base STL attached)*

### Previous projects
All past jobs appear as cards at the bottom with thumbnail previews. Click any card to load its download links.

---

## Output files

All output lands on the NAS at:
```
/mnt/mybook/3d_models/<job_name>/
  <job_name>.scad      — OpenSCAD source (editable)
  <part>.stl           — one STL per color part
  <job_name>.3mf       — combined multi-color file for Anycubic Slicer Next
  preview.png          — rendered preview image
```

NAS path from Windows/Mac: `\\192.168.5.244\My_Book_1230-1\3d_models\`

---

## Command-line usage (SSH)

```bash
ssh themaddog1068@192.168.4.62
cd /home/themaddog1068/3d-builder

# Generate from description
venv/bin/python generate.py "your description here" job_name

# Generate with a base STL to modify
venv/bin/python generate.py "add mounting holes to the corners" my_bracket /path/to/base.stl
```

---

## How the pipeline works

```
User description
       │
       ▼
  Claude API (claude-sonnet-4-6)
  Generates OpenSCAD code with per-color modules
       │
       ├─► OpenSCAD (headless via xvfb) ─► one .stl per part
       │
       ├─► OpenSCAD + xvfb ─► preview.png (colour composite render)
       │
       └─► trimesh ─► combined .3mf with per-part color metadata
                         │
                         └─► saved to NAS /3d_models/<job>/
```

**Multi-color:** Claude generates one `module` per ACE filament slot. OpenSCAD renders each separately to its own STL. The 3MF bundles all parts — Anycubic Slicer Next maps each part to an ACE slot automatically.

**Base STL workflow:** Upload an existing STL → trimesh extracts bounding box + dimensions → Claude generates OpenSCAD that `import()`s the original and adds/subtracts geometry → re-rendered to new STL + 3MF.

---

## Service management

```bash
sudo systemctl status 3d-builder     # check status
sudo systemctl restart 3d-builder    # restart
sudo systemctl stop 3d-builder       # stop
journalctl -u 3d-builder -f          # live logs
```

The service starts automatically on boot.

---

## File locations

| Path | Purpose |
|---|---|
| `/home/themaddog1068/3d-builder/` | Application root |
| `/home/themaddog1068/3d-builder/.env` | API key (chmod 600, do not share) |
| `/home/themaddog1068/3d-builder/generate.py` | Core pipeline |
| `/home/themaddog1068/3d-builder/app.py` | Flask web server |
| `/home/themaddog1068/3d-builder/templates/index.html` | Web UI |
| `/home/themaddog1068/3d-builder/venv/` | Python virtual environment |
| `/mnt/mybook/3d_models/` | All generated output (NAS) |
| `/etc/systemd/system/3d-builder.service` | Systemd service unit |

---

## Dependencies

- **Python 3.13** + venv
- `anthropic` — Claude API client
- `trimesh` — STL/3MF mesh handling
- `flask` — web server
- `python-dotenv` — `.env` loading
- `numpy` — mesh math
- **OpenSCAD 2021.01** — headless 3D rendering
- **Xvfb** — virtual display for OpenSCAD PNG export

---

## API key

Stored in `/home/themaddog1068/3d-builder/.env` as `ANTHROPIC_API_KEY`.
The key was retrieved from `//192.168.5.244/My_Book_1230-1/Livingroom_new_claude_key.txt`.
To rotate: replace the value in `.env` and `sudo systemctl restart 3d-builder`.
