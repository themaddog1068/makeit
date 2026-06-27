#!/usr/bin/env python3
"""Flask web interface for the 3D model builder."""

import os
import re
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from generate import generate, NAS_OUTPUT_DIR

app = Flask(__name__)
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTS = {".stl", ".3mf"}


def safe_job_name(description: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", description.lower())[:40].strip("_")
    return f"{slug}_{uuid.uuid4().hex[:6]}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def api_generate():
    description = request.form.get("description", "").strip()
    if not description:
        return jsonify({"error": "No description provided"}), 400

    job_name = safe_job_name(description)

    # Handle optional base STL upload
    base_stl = None
    if "base_file" in request.files:
        f = request.files["base_file"]
        if f and f.filename and Path(f.filename).suffix.lower() in ALLOWED_EXTS:
            base_stl = UPLOAD_DIR / f"{uuid.uuid4().hex}{Path(f.filename).suffix}"
            f.save(str(base_stl))

    try:
        result = generate(description, job_name, base_stl)
        # Convert absolute NAS paths to web-relative download paths
        def nas_to_web(p):
            return str(Path(p).relative_to(NAS_OUTPUT_DIR)) if p else None

        result["stl_files"] = [nas_to_web(s) for s in result.get("stl_files", [])]
        result["3mf"]     = nas_to_web(result.get("3mf"))
        result["scad"]    = nas_to_web(result.get("scad"))
        result["preview"] = nas_to_web(result.get("preview"))
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if base_stl and base_stl.exists():
            base_stl.unlink(missing_ok=True)


@app.route("/download/<path:filepath>")
def download(filepath):
    full = NAS_OUTPUT_DIR / filepath
    resolved = full.resolve()
    if not resolved.exists() or not str(resolved).startswith(str(NAS_OUTPUT_DIR.resolve())):
        return "Not found", 404
    return send_file(str(resolved), as_attachment=True)


@app.route("/preview/<path:filepath>")
def preview(filepath):
    full = NAS_OUTPUT_DIR / filepath
    resolved = full.resolve()
    if not resolved.exists() or not str(resolved).startswith(str(NAS_OUTPUT_DIR.resolve())):
        return "Not found", 404
    return send_file(str(resolved), mimetype="image/png")


@app.route("/jobs")
def list_jobs():
    jobs = []
    if not NAS_OUTPUT_DIR.exists():
        return jsonify(jobs)
    for d in sorted(NAS_OUTPUT_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if d.is_dir():
            files = [f.name for f in d.iterdir() if f.is_file() and not f.name.startswith(".")]
            has_preview = any(f == "preview.png" for f in files)
            jobs.append({"name": d.name, "files": files, "has_preview": has_preview})
    return jsonify(jobs)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
