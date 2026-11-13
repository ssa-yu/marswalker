"""Web output helpers for MapLibre.

MapLibre draws Mars lon/lat with its (Earth) Web Mercator maths. We only borrow that projection for
display; every distance shown in the UI is computed on the Mars sphere.

- make_tiles(): XYZ raster tiles sampled directly from a local-grid image (exact per-pixel mapping).
- overlay(): single image for a MapLibre image source; rows are resampled to uniform Web-Mercator y so
  the linear quad MapLibre draws matches the data (matters for multi-km images at 18-40 deg N).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates

from .common import LocalGrid

TILE = 256


def merc_y(lat_deg):
    return np.log(np.tan(np.pi / 4 + np.radians(lat_deg) / 2))


def inv_merc_y(y):
    return np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)


def _pyramid(img: np.ndarray, levels: int):
    """Area-average pyramid; img float32 (H, W, C) with NaN = transparent."""
    out = [img]
    for _ in range(levels):
        a = out[-1]
        H, W = a.shape[0] // 2 * 2, a.shape[1] // 2 * 2
        a = a[:H, :W]
        blocks = a.reshape(H // 2, 2, W // 2, 2, a.shape[2])
        with np.errstate(invalid="ignore"):
            out.append(np.nanmean(blocks, axis=(1, 3)).astype("float32"))
    return out


def make_tiles(img: np.ndarray, grid: LocalGrid, extent, res: float, out_dir: Path, zmin: int, zmax: int,
               fmt: str = "webp", quality: int = 82) -> dict:
    """img: uint8 (H, W) or (H, W, 3); NaN-free; pixels outside data must be marked via alpha (H, W, 4)."""
    out_dir = Path(out_dir)
    if img.ndim == 2:
        img = np.repeat(img[:, :, None], 3, axis=2)
    f = img.astype("float32")
    if f.shape[2] == 3:
        f = np.concatenate([f, np.full(f.shape[:2] + (1,), 255, "float32")], axis=2)
    f[f[:, :, 3] == 0, :3] = np.nan
    xmin, ymin, xmax, ymax = extent
    corners = grid.corners_lonlat(*extent)
    W_, E_ = corners[0][0], corners[1][0]
    N_, S_ = corners[0][1], corners[2][1]
    m_per_deg_lon = math.radians(1) * 3396190.0 * grid.k
    pyr = _pyramid(f, 8)
    # per level: contiguous channels with NaN->0, plus a NaN mask (computed once, reused for every tile)
    prep = []
    for a in pyr:
        nanm = np.isnan(a[:, :, 0])
        chans = [np.ascontiguousarray(np.where(nanm, 0.0, a[:, :, c]).astype("float32")) for c in range(4)]
        prep.append((chans, nanm.astype("float32")))
    del f
    n_tiles, n_bytes = 0, 0
    for z in range(zmin, zmax + 1):
        n = 2 ** z
        tx0 = int((W_ + 180) / 360 * n); tx1 = int((E_ + 180) / 360 * n)
        ty0 = int((1 - merc_y(N_) / np.pi) / 2 * n); ty1 = int((1 - merc_y(S_) / np.pi) / 2 * n)
        tile_px_m = 360.0 / (TILE * n) * m_per_deg_lon
        lvl = max(0, min(len(pyr) - 1, int(math.floor(math.log2(max(tile_px_m / res, 1.0))))))
        chans, nanf = prep[lvl]; r = res * 2 ** lvl
        sh = nanf.shape
        for tx in range(tx0, tx1 + 1):
            lon = -180 + (tx + (np.arange(TILE) + 0.5) / TILE) * 360 / n
            for ty in range(ty0, ty1 + 1):
                my = np.pi * (1 - 2 * (ty + (np.arange(TILE) + 0.5) / TILE) / n)
                lat = inv_merc_y(my)
                LON, LAT = np.meshgrid(lon, lat)
                x, y = grid.lonlat_to_xy(LON, LAT)
                col = (x - xmin) / r - 0.5; row = (ymax - y) / r - 0.5
                inside = (col >= -0.5) & (col <= sh[1] - 0.5) & (row >= -0.5) & (row <= sh[0] - 0.5)
                rgba = np.zeros((TILE, TILE, 4), np.uint8)
                if not inside.any():  # edge tile inside MapLibre's floor()ed bounds: write it transparent (avoids 404s)
                    d = out_dir / str(z) / str(tx); d.mkdir(parents=True, exist_ok=True)
                    p = d / f"{ty}.{fmt}"; Image.fromarray(rgba, "RGBA").save(p, "WEBP", lossless=True) if fmt == "webp" else Image.fromarray(rgba[:, :, :3]).save(p)
                    n_tiles += 1; n_bytes += p.stat().st_size
                    continue
                for ch in range(4):
                    v = map_coordinates(chans[ch], [row, col], order=1, mode="nearest")
                    rgba[:, :, ch] = np.clip(v + 0.5, 0, 255).astype(np.uint8)
                nanmask = map_coordinates(nanf, [row, col], order=1, mode="nearest") > 0.5
                rgba[~inside | nanmask, 3] = 0
                d = out_dir / str(z) / str(tx); d.mkdir(parents=True, exist_ok=True)
                p = d / f"{ty}.{fmt}"
                im = Image.fromarray(rgba, "RGBA")
                if fmt == "webp":
                    im.save(p, "WEBP", quality=quality, method=4)
                else:
                    im.convert("RGB").save(p, "JPEG", quality=quality)
                n_tiles += 1; n_bytes += p.stat().st_size
    return {"tiles": n_tiles, "bytes": n_bytes, "minzoom": zmin, "maxzoom": zmax,
            "bounds": [W_, S_, E_, N_]}


def overlay(img_rgba: np.ndarray, grid: LocalGrid, extent, out_path: Path, fmt: str = "png", quality: int = 85) -> dict:
    """Save an (H, W, 4) uint8 local-grid image as a MapLibre image-source overlay."""
    c = grid.corners_lonlat(*extent)
    return overlay_ll(img_rgba, (c[0][0], c[2][1], c[1][0], c[0][1]), out_path, fmt, quality)


def overlay_ll(img_rgba: np.ndarray, bounds, out_path: Path, fmt: str = "png", quality: int = 85) -> dict:
    """Image whose rows are uniform in latitude, bounds = (W, S, E, N) degrees -> mercator-row image."""
    if img_rgba.ndim == 3 and img_rgba.shape[2] == 3:
        img_rgba = np.concatenate([img_rgba, np.full(img_rgba.shape[:2] + (1,), 255, np.uint8)], axis=2)
    H = img_rgba.shape[0]
    W_, S_, E_, N_ = bounds
    yN, yS = merc_y(N_), merc_y(S_)
    yj = yN + (np.arange(H) + 0.5) / H * (yS - yN)
    lat = inv_merc_y(yj)
    rows = (N_ - lat) / (N_ - S_) * H - 0.5
    r0 = np.clip(np.floor(rows).astype(int), 0, H - 1); r1 = np.clip(r0 + 1, 0, H - 1)
    w = (rows - r0)[:, None, None]
    out = (img_rgba[r0].astype("float32") * (1 - w) + img_rgba[r1].astype("float32") * w)
    out = np.clip(out + 0.5, 0, 255).astype(np.uint8)
    im = Image.fromarray(out, "RGBA")
    out_path = Path(out_path)
    if fmt == "png":
        im.save(out_path, optimize=True)
    elif fmt == "webp":
        im.save(out_path, "WEBP", quality=quality, method=4)
    else:
        im.convert("RGB").save(out_path, "JPEG", quality=quality)
    coords = [[round(W_, 8), round(N_, 8)], [round(E_, 8), round(N_, 8)], [round(E_, 8), round(S_, 8)], [round(W_, 8), round(S_, 8)]]
    return {"coordinates": coords, "bytes": out_path.stat().st_size, "shape": list(out.shape[:2])}
