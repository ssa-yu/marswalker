# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia context basemaps for web/arcadia.html (display only, no analysis uses them).

python -m pipeline.arcadia_context
  1. (no longer exported, study area v3) whole HiRISE strip: RED_C 1 m ortho averaged to ~3 m -> strip.webp
  2. NASA JPL Mars Trek THEMIS Day IR mosaic around the site (pipeline.trek, zoom 9, +-75 km) -> trek_themis_day.jpg
Output: web/data/arcadia/context.json (image files + lon/lat corners + credits).
"""
from __future__ import annotations

import math

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling

from . import trek
from .common import R_MARS, Scene, log, read_json, write_json

SCENE = "arcadia"
STRIP_RES_M = 3.0
TREK_KEY, TREK_ZOOM, TREK_HALF_M = "themis_day", 9, 75000.0


def corners(b):
    """lon/lat corners (NW, NE, SE, SW) of an equirectangular (clon 0, lat_ts 0) box in metres."""
    W, S, E, N = (math.degrees(v / R_MARS) for v in (b[0], b[1], b[2], b[3]))
    return [[round(W, 7), round(N, 7)], [round(E, 7), round(N, 7)], [round(E, 7), round(S, 7)], [round(W, 7), round(S, 7)]]


def strip(sc: Scene, out):
    src = sc.raw / sc.source("ortho_1m")["file"]
    aoi_ll = sc.grid.corners_lonlat(*sc.extent("aoi"))
    with rasterio.open(src) as s:
        assert s.crs.to_dict().get("lon_0", 0) == 0 and s.crs.to_dict().get("lat_ts", 0) == 0
        f = STRIP_RES_M / s.res[0]
        h, w = round(s.height / f), round(s.width / f)
        a = s.read(1, out_shape=(h, w), resampling=Resampling.average, masked=True)
        b = s.bounds
    valid = ~np.ma.getmaskarray(a) & (a.filled(0) > 0)
    v = a.filled(0).astype(float)
    # stretch from the study-area pixels, same percentiles as hirise.jpg (pipeline/arcadia_export.py)
    lon = np.linspace(b.left, b.right, w + 1)[:-1] + (b.right - b.left) / w / 2
    lat = np.linspace(b.top, b.bottom, h + 1)[:-1] - (b.top - b.bottom) / h / 2
    lon, lat = np.degrees(lon / R_MARS), np.degrees(lat / R_MARS)
    cx = (lon >= aoi_ll[0][0]) & (lon <= aoi_ll[1][0]); cy = (lat <= aoi_ll[0][1]) & (lat >= aoi_ll[2][1])
    inside = v[np.ix_(cy, cx)][valid[np.ix_(cy, cx)]]
    lo, hi = np.percentile(inside, [0.5, 99.5])
    g = (np.clip((v - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    rgba = np.dstack([g, g, g, np.where(valid, 255, 0).astype(np.uint8)])
    Image.fromarray(rgba).save(out / "strip.webp", quality=72, method=6)
    log(SCENE, "context", f"strip {w}x{h} at {STRIP_RES_M} m -> strip.webp {(out / 'strip.webp').stat().st_size / 1e6:.2f} MB")
    return {"file": "strip.webp", "coordinates": corners(b), "res_m": STRIP_RES_M,
            "size_km": [round((b.right - b.left) / 1000, 2), round((b.top - b.bottom) / 1000, 2)],
            "source": sc.source("ortho_1m")["title"], "url": sc.source("ortho_1m")["url"]}


def themis(sc: Scene, out):
    raw = sc.raw / f"trek_{TREK_KEY}.png"
    if not raw.exists():
        trek.fetch_layer(sc, TREK_KEY, TREK_ZOOM, TREK_HALF_M)
    info = read_json(sc.raw / f"trek_{TREK_KEY}.json")
    Image.open(raw).convert("RGB").save(out / f"trek_{TREK_KEY}.jpg", quality=80)
    W, S, E, N = info["bounds_lonlat"]
    return {"file": f"trek_{TREK_KEY}.jpg", "coordinates": [[W, N], [E, N], [E, S], [W, S]],
            "res_m": round(info["deg_per_px"] * math.pi / 180 * R_MARS), "title": info["title"],
            "mission": info["mission"], "url": info["url_template"], "zoom": info["zoom"]}


def run():
    sc = Scene(SCENE)
    out = sc.web
    # the whole-strip HiRISE image (strip()) is no longer shown (study area v3: HiRISE only inside the square)
    (out / "strip.webp").unlink(missing_ok=True)
    doc = {"note": "display-only context basemaps; no computed result uses them", "trek": themis(sc, out)}
    write_json(out / "context.json", doc)
    log(SCENE, "context", f"wrote {out / 'context.json'}")


if __name__ == "__main__":
    run()
