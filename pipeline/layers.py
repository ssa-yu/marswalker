"""S4 layers: hillshade / slope for the reference (HiRISE) and prior (CTX) terrain + web image products.

python -m pipeline.layers --scene jezero
Writes web/data/<scene>/{tiles/..., *.webp|png|jpg} and data_work/<scene>/layers.json (manifest).
Hillshade and slope use identical parameters for reference and prior so the only difference you see is
the source resolution.
"""
from __future__ import annotations

import argparse
import math
import shutil

import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling
from scipy.ndimage import sobel

from .common import Scene, log, read_json, write_json
from .grid import to_local
from .tiles import make_tiles, overlay, overlay_ll

SUN_AZ, SUN_ALT = 315.0, 35.0
SLOPE_EDGES = [0, 2, 5, 10, 15, 20, 25, 30, 90]
# sequential, light -> dark (validated for CVD-safe lightness ramp: yellow -> red -> purple)
SLOPE_COLORS = ["#fff5c4", "#fde28a", "#fdba5a", "#f88b3b", "#e8562e", "#c42a3b", "#8e1547", "#4a0c4f"]
SLOPE_ALPHA = [40, 150, 190, 210, 225, 235, 240, 245]


def gradients(z, res):
    """Horn (Sobel) gradients; returns dz/dx (east), dz/dy (north)."""
    zz = np.where(np.isfinite(z), z, np.nanmean(z))
    gx = sobel(zz, axis=1) / (8.0 * res)
    gy = -sobel(zz, axis=0) / (8.0 * res)  # rows increase southward
    bad = ~np.isfinite(z)
    gx[bad] = np.nan; gy[bad] = np.nan
    return gx, gy


def hillshade(z, res, az=SUN_AZ, alt=SUN_ALT):
    gx, gy = gradients(z, res)
    a, h = math.radians(az), math.radians(alt)
    L = np.array([math.sin(a) * math.cos(h), math.cos(a) * math.cos(h), math.sin(h)])
    n = np.sqrt(gx ** 2 + gy ** 2 + 1)
    s = (-gx * L[0] - gy * L[1] + L[2]) / n
    return np.clip(s, 0, 1)


def slope_deg(z, res):
    gx, gy = gradients(z, res)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def gray_rgba(v01, valid):
    g = np.clip(v01 * 255 + 0.5, 0, 255).astype(np.uint8)
    rgba = np.dstack([g, g, g, np.where(valid, 255, 0).astype(np.uint8)])
    return rgba


def slope_rgba(s):
    rgba = np.zeros(s.shape + (4,), np.uint8)
    for i in range(len(SLOPE_COLORS)):
        m = (s >= SLOPE_EDGES[i]) & (s < SLOPE_EDGES[i + 1])
        c = SLOPE_COLORS[i]
        rgba[m] = [int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), SLOPE_ALPHA[i]]
    return rgba


def stretch(a, lo_p=0.5, hi_p=99.5):
    v = a[np.isfinite(a) & (a > 0)]
    lo, hi = np.percentile(v, [lo_p, hi_p])
    out = np.clip((a - lo) / (hi - lo) * 254 + 1, 1, 255)
    out[~np.isfinite(a) | (a <= 0)] = 0
    return out.astype(np.uint8), [float(lo), float(hi)]


def run(scene: str):
    sc = Scene(scene)
    g = sc.cfg["grid"]
    web = sc.web
    aoi = sc.extent("aoi")
    ctx = sc.extent("context")
    man = {}

    def rec(key, **kw):
        man[key] = kw
        log(scene, "layers", f"{key}: {kw.get('bytes', 0)/1e6:.2f} MB {kw.get('shape') or kw.get('tiles')}")

    # --- HiRISE ortho tiles (AOI) ---
    with rasterio.open(sc.work / "ortho_025.tif") as s:
        o = s.read(1)
    o8, st = stretch(o)
    rgba = np.dstack([o8, o8, o8, np.where(o8 > 0, 255, 0).astype(np.uint8)])
    tdir = web / "tiles" / "ortho"
    if tdir.exists():
        shutil.rmtree(tdir)
    info = make_tiles(rgba, sc.grid, aoi, g["ortho_res_m"], tdir, g.get("tile_zmin", 12), g.get("tile_zmax", 18))
    rec("hirise_ortho", kind="tiles", url="tiles/ortho/{z}/{x}/{y}.webp", stretch_dn=st, **info)
    del rgba, o

    # --- post-landing HiRISE tiles (AOI), Jezero only ---
    if (sc.work / "post_landing_025.tif").exists():
        with rasterio.open(sc.work / "post_landing_025.tif") as s:
            p = s.read(1)
        p8, st2 = stretch(p)
        rgba = np.dstack([p8, p8, p8, np.where(p8 > 0, 255, 0).astype(np.uint8)])
        tdir = web / "tiles" / "post_landing"
        if tdir.exists():
            shutil.rmtree(tdir)
        info = make_tiles(rgba, sc.grid, aoi, g["ortho_res_m"], tdir, g.get("tile_zmin", 12), g.get("tile_zmax", 18))
        rec("post_landing", kind="tiles", url="tiles/post_landing/{z}/{x}/{y}.webp", stretch_dn=st2, **info)
        del rgba, p

    # --- HiRISE DTM: hillshade at 1 m, slope at slope_res (6 m baseline with a 3 m grid) ---
    with rasterio.open(sc.work / "dtm_fine.tif") as s:
        zf = s.read(1)
    pad = int(round(30 / g["dtm_res_m"]))
    hs = hillshade(zf, g["dtm_res_m"])[pad:-pad, pad:-pad]
    valid = np.isfinite(zf[pad:-pad, pad:-pad])
    rec("hirise_hillshade", kind="image", url="hirise_hillshade.webp",
        **overlay(gray_rgba(hs, valid), sc.grid, aoi, web / "hirise_hillshade.webp", "webp", 85))
    sr = g["slope_res_m"]
    pad_aoi = (aoi[0] - 30, aoi[1] - 30, aoi[2] + 30, aoi[3] + 30)
    zs, _ = to_local(sc.raw_path("dtm_fine"), sc, pad_aoi, sr, Resampling.average)
    p3 = int(round(30 / sr))
    sf = slope_deg(zs, sr)[p3:-p3, p3:-p3]
    np.save(sc.work / "slope_fine.npy", sf.astype("float32"))
    rec("hirise_slope", kind="image", url="hirise_slope.png", baseline_m=2 * sr,
        **overlay(slope_rgba(sf), sc.grid, aoi, web / "hirise_slope.png", "png"))

    # --- CTX prior (context extent): hillshade + slope on the prior's own 20 m grid ---
    pres = g.get("prior_res_m", 20.0)
    with rasterio.open(sc.work / "dtm_prior_ctx.tif") as s:
        zp = s.read(1)
    hp = hillshade(zp, pres)
    rec("ctx_hillshade", kind="image", url="ctx_hillshade.png",
        **overlay(gray_rgba(hp, np.isfinite(zp)), sc.grid, ctx, web / "ctx_hillshade.png", "png"))
    sp = slope_deg(zp, pres)
    np.save(sc.work / "slope_prior_ctx.npy", sp.astype("float32"))
    rec("ctx_slope", kind="image", url="ctx_slope.png", baseline_m=2 * pres,
        **overlay(slope_rgba(sp), sc.grid, ctx, web / "ctx_slope.png", "png"))

    # --- CTX orthoimage (context) ---
    with rasterio.open(sc.work / "prior_ortho_ctx.tif") as s:
        co = s.read(1)
    c8, st3 = stretch(co)
    rec("ctx_ortho", kind="image", url="ctx_ortho.jpg", stretch_dn=st3,
        **overlay(np.dstack([c8, c8, c8, np.where(c8 > 0, 255, 0).astype(np.uint8)]), sc.grid, ctx,
                  web / "ctx_ortho.jpg", "jpg", 85))

    # --- Mars Trek regional basemaps (stored locally) ---
    for key in sc.cfg.get("trek_layers", []):
        tj = read_json(sc.raw / f"trek_{key}.json")
        im = np.asarray(Image.open(sc.raw / f"trek_{key}.png").convert("RGB"))
        rec(f"trek_{key}", kind="image", url=f"trek_{key}.jpg", trek=tj,
            **overlay_ll(im, tj["bounds_lonlat"], web / f"trek_{key}.jpg", "jpg", 85))

    man["_params"] = {"sun_azimuth_deg": SUN_AZ, "sun_altitude_deg": SUN_ALT, "slope_edges_deg": SLOPE_EDGES,
                      "slope_colors": SLOPE_COLORS, "slope_fine_grid_m": sr, "slope_fine_baseline_m": 2 * sr,
                      "slope_prior_grid_m": pres, "slope_prior_baseline_m": 2 * pres}
    write_json(sc.work / "layers.json", man)
    return man


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    run(ap.parse_args().scene)
