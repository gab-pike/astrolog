"""
astrolog — Flask API + static frontend server.

Endpoints:
  GET  /api/now?lat=&lon=            current sky (positions, houses, aspects, moon)
  GET  /api/charts                   list saved natal charts
  POST /api/charts                   compute + save a natal chart
  GET  /api/charts/<name>            a saved natal chart
  DELETE /api/charts/<name>          remove a saved chart
  GET  /api/transits/<name>?lat=&lon=  current sky + aspects to that natal chart
  GET  /api/ha?lat=&lon=             flat JSON, friendly for Home Assistant REST sensors
"""

import json
import os
import re
import threading

from flask import Flask, jsonify, request, send_from_directory

import astrology_engine as engine

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
CHARTS_FILE = os.path.join(DATA_DIR, "charts.json")
DEFAULT_LAT = float(os.environ.get("DEFAULT_LAT", "43.55"))
DEFAULT_LON = float(os.environ.get("DEFAULT_LON", "-96.73"))
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = Flask(__name__, static_folder=None)
_lock = threading.Lock()


def _load_charts() -> dict:
    if not os.path.exists(CHARTS_FILE):
        return {}
    with open(CHARTS_FILE) as f:
        return json.load(f)


def _save_charts(charts: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CHARTS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(charts, f, indent=2)
    os.replace(tmp, CHARTS_FILE)


def _geo():
    lat = float(request.args.get("lat", DEFAULT_LAT))
    lon = float(request.args.get("lon", DEFAULT_LON))
    return lat, lon


# --- API -------------------------------------------------------------------

@app.get("/api/now")
def api_now():
    lat, lon = _geo()
    return jsonify(engine.current_chart(lat, lon))


@app.get("/api/charts")
def api_list_charts():
    charts = _load_charts()
    return jsonify([
        {"name": name, "birth_local": c["chart"]["birth_local"]}
        for name, c in sorted(charts.items())
    ])


@app.post("/api/charts")
def api_create_chart():
    body = request.get_json(force=True)
    required = ("name", "date", "time", "tz", "lat", "lon")
    missing = [k for k in required if k not in body]
    if missing:
        return jsonify({"error": f"missing fields: {', '.join(missing)}"}), 400
    name = re.sub(r"[^a-zA-Z0-9 _-]", "", body["name"]).strip()
    if not name:
        return jsonify({"error": "name must contain letters or numbers"}), 400
    try:
        chart = engine.natal_chart(body["date"], body["time"], body["tz"],
                                   float(body["lat"]), float(body["lon"]))
    except Exception as exc:  # bad date/tz input
        return jsonify({"error": str(exc)}), 400
    with _lock:
        charts = _load_charts()
        charts[name] = {
            "input": {k: body[k] for k in ("date", "time", "tz", "lat", "lon")},
            "chart": chart,
        }
        _save_charts(charts)
    return jsonify({"saved": name, "chart": chart}), 201


@app.get("/api/charts/<name>")
def api_get_chart(name):
    charts = _load_charts()
    if name not in charts:
        return jsonify({"error": "no chart with that name"}), 404
    return jsonify(charts[name])


@app.delete("/api/charts/<name>")
def api_delete_chart(name):
    with _lock:
        charts = _load_charts()
        if name not in charts:
            return jsonify({"error": "no chart with that name"}), 404
        del charts[name]
        _save_charts(charts)
    return jsonify({"deleted": name})


@app.get("/api/transits/<name>")
def api_transits(name):
    charts = _load_charts()
    if name not in charts:
        return jsonify({"error": "no chart with that name"}), 404
    lat, lon = _geo()
    return jsonify(engine.transits_to_natal(charts[name]["chart"], lat, lon))


@app.get("/api/ha")
def api_ha():
    """Flat structure so Home Assistant REST sensors need only shallow
    value_template paths."""
    lat, lon = _geo()
    chart = engine.current_chart(lat, lon)
    p = chart["positions"]
    flat = {
        "sun_sign": p["Sun"]["sign"],
        "moon_sign": p["Moon"]["sign"],
        "moon_phase": chart["moon"]["phase"],
        "moon_illumination": chart["moon"]["illumination_pct"],
        "mercury_retrograde": p["Mercury"]["retrograde"],
        "ascendant": chart["houses"]["ascendant"]["sign"],
        "retrogrades": sorted(n for n, d in p.items() if d["retrograde"]),
        "tightest_aspect": chart["aspects"][0] if chart["aspects"] else None,
    }
    return jsonify(flat)


# --- Frontend --------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "static"), filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
