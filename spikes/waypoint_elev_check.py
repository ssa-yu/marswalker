# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Localization check: Perseverance waypoint elev_geoid vs HiRISE DTM (D1 window) sampled at waypoint lon/lat.
Usage: python waypoint_elev_check.py M20_waypoints.json DTM.tif"""
import json, math, sys, numpy as np, rasterio
fc = json.load(open(sys.argv[1])); s = rasterio.open(sys.argv[2]); a = s.read(1)
R = 3396190.0; rows = []
for f in fc["features"]:
    p = f["properties"]; x, y = math.radians(p["lon"]) * R, math.radians(p["lat"]) * R
    r, c = s.index(x, y)
    if 0 <= r < s.height and 0 <= c < s.width and a[r, c] > -1e30:
        rows.append((p["sol"], p["elev_geoid"], float(a[r, c])))
d = np.array([e - z for _, e, z in rows])
print(f"waypoints inside window: {len(rows)}; waypoint - DTM: mean {d.mean():+.2f} m, median {np.median(d):+.2f}, MAE {np.abs(d).mean():.2f}, std {d.std():.2f}, max|d| {np.abs(d).max():.2f}")
dm = d - np.median(d)
print(f"after removing median offset: MAE {np.abs(dm).mean():.2f} m, p95 |d| {np.percentile(np.abs(dm),95):.2f} m")
