"""Shared helpers: scene config, base-centred local metric grid, raster I/O.

Local grid ("local"): metres east (x) / north (y) of the habitat (base), on the Mars 2015 sphere
R = 3,396,190 m (same sphere as every USGS source product used here). All source products are
equirectangular (eqc, lat_ts = 0, lon_0 = 0) on that sphere, so

    X_src = R * lon_rad            Y_src = R * lat_rad
    x     = (X_src - R*lon0_rad) * cos(lat0)
    y     =  Y_src - R*lat0_rad

i.e. local <-> source is affine. A local grid with square pixels of `res` metres is therefore a
source-CRS grid with pixel width res / cos(lat0) and height res; no cross-body CRS transform needed.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from affine import Affine

R_MARS = 3396190.0
APP = Path(__file__).resolve().parents[1]
SRC_PROJ4 = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R=3396190 +units=m +no_defs"


def norm_lon(lon: float) -> float:
    """Longitude to [-180, 180)."""
    return ((lon + 180.0) % 360.0) - 180.0


@dataclass
class LocalGrid:
    lon0: float  # degrees east, [-180, 180)
    lat0: float  # degrees north

    def __post_init__(self):
        self.lon0 = norm_lon(self.lon0)
        self.k = math.cos(math.radians(self.lat0))
        self.X0 = R_MARS * math.radians(self.lon0)
        self.Y0 = R_MARS * math.radians(self.lat0)

    # local <-> source CRS (eqc clon0, metres on the sphere)
    def xy_to_src(self, x, y):
        return self.X0 + np.asarray(x) / self.k, self.Y0 + np.asarray(y)

    def src_to_xy(self, X, Y):
        return (np.asarray(X) - self.X0) * self.k, np.asarray(Y) - self.Y0

    # local <-> lon/lat (degrees; planetocentric, east-positive, [-180,180))
    def xy_to_lonlat(self, x, y):
        X, Y = self.xy_to_src(x, y)
        return np.degrees(X / R_MARS), np.degrees(Y / R_MARS)

    def lonlat_to_xy(self, lon, lat):
        lon = np.asarray(lon, dtype=float)
        lon = ((lon - self.lon0 + 180.0) % 360.0) - 180.0 + self.lon0  # unwrap around base
        return self.src_to_xy(R_MARS * np.radians(lon), R_MARS * np.radians(lat))

    def src_transform(self, xmin: float, ymax: float, res: float) -> Affine:
        """Affine (source CRS) of a local grid whose top-left corner is (xmin, ymax), square local pixels."""
        X, Y = self.xy_to_src(xmin, ymax)
        return Affine(res / self.k, 0.0, float(X), 0.0, -res, float(Y))

    def src_bounds(self, xmin, ymin, xmax, ymax):
        X0, Y0 = self.xy_to_src(xmin, ymin)
        X1, Y1 = self.xy_to_src(xmax, ymax)
        return float(X0), float(Y0), float(X1), float(Y1)

    def corners_lonlat(self, xmin, ymin, xmax, ymax):
        """MapLibre image-source order: top-left, top-right, bottom-right, bottom-left, as [lon, lat]."""
        pts = [(xmin, ymax), (xmax, ymax), (xmax, ymin), (xmin, ymin)]
        out = []
        for x, y in pts:
            lon, lat = self.xy_to_lonlat(x, y)
            out.append([round(float(lon), 8), round(float(lat), 8)])
        return out


class Scene:
    """Loads config/scenes/<name>.json and exposes paths and the local grid."""

    def __init__(self, name: str):
        self.name = name
        self.cfg_path = APP / "config" / "scenes" / f"{name}.json"
        self.cfg = json.loads(self.cfg_path.read_text())
        b = self.cfg["base"]
        self.grid = LocalGrid(b["lon"], b["lat"])
        a = self.cfg["aoi"]
        self.aoi = (a["xmin"], a["ymin"], a["xmax"], a["ymax"])
        self.raw = APP / "data_raw" / name
        self.work = APP / "data_work" / name
        self.qa = APP / "qa" / name
        self.web = APP / "web" / "data" / name
        for p in (self.raw, self.work, self.qa, self.web):
            p.mkdir(parents=True, exist_ok=True)

    def extent(self, which: str):
        """Local-metre bounds (xmin, ymin, xmax, ymax) for 'aoi', 'fetch' (aoi + margin) or 'context'."""
        xmin, ymin, xmax, ymax = self.aoi
        if which == "aoi":
            return self.aoi
        if which == "fetch":
            m = self.cfg.get("fetch_margin_m", 300)
            return (xmin - m, ymin - m, xmax + m, ymax + m)
        if which == "context":
            h = self.cfg["context"]["half_size_m"]
            cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
            return (cx - h, cy - h, cx + h, cy + h)
        raise ValueError(which)

    def source(self, sid: str) -> dict:
        return self.cfg["sources"][sid]

    def raw_path(self, sid: str) -> Path:
        s = self.source(sid)
        ext = s.get("ext") or Path(s["url"].split("?")[0]).suffix or ".bin"
        return self.raw / f"{sid}{ext}"


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, default=_json_default)
    os.replace(tmp, path)


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


def read_json(path: Path):
    return json.loads(Path(path).read_text())


def save_local_tif(path: Path, arr: np.ndarray, transform: Affine, nodata=None, crs=SRC_PROJ4):
    """Write a local-grid array as a georeferenced GeoTIFF (source CRS, non-square pixels)."""
    import rasterio
    arr = np.asarray(arr)
    count = 1 if arr.ndim == 2 else arr.shape[0]
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[-1], height=arr.shape[-2], count=count,
                       dtype=arr.dtype, crs=crs, transform=transform, nodata=nodata, tiled=True,
                       compress="deflate", blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER") as dst:
        if arr.ndim == 2:
            dst.write(arr, 1)
        else:
            dst.write(arr)


def log(scene: str, step: str, msg: str) -> None:
    print(f"[{scene}:{step}] {msg}", flush=True)
