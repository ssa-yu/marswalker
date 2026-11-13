"""S2 grid: resample source rasters onto base-centred local metre grids.

python -m pipeline.grid --scene jezero
Outputs (data_work/<scene>/): ortho_025.tif, dtm_fine.tif, dtm_prior.tif (+ shift applied, see align),
post_landing_025.tif (if configured), prior_ortho_ctx.tif, dtm_prior_ctx.tif, grid.json
"""
from __future__ import annotations

import argparse
import math

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

from .common import Scene, log, read_json, save_local_tif, write_json


def to_local(src_path, sc: Scene, extent, res, resampling=Resampling.bilinear, dtype="float32",
             shift_xy=(0.0, 0.0), band=1):
    """Resample band of `src_path` onto the local grid covering `extent` (local m) at `res` m.
    shift_xy: (dx, dy) local metres added to the source georeference (global registration shift)."""
    xmin, ymin, xmax, ymax = extent
    W = int(round((xmax - xmin) / res)); H = int(round((ymax - ymin) / res))
    dst_tr = sc.grid.src_transform(xmin, ymax, res)
    out = np.full((H, W), np.nan, dtype="float32")
    with rasterio.open(src_path) as src:
        tr = src.transform
        if shift_xy != (0.0, 0.0):
            from affine import Affine
            dX = shift_xy[0] / sc.grid.k; dY = shift_xy[1]
            tr = Affine(tr.a, tr.b, tr.c + dX, tr.d, tr.e, tr.f + dY)
        arr = src.read(band, masked=True).astype("float32").filled(np.nan)
        arr[(arr < -1e30) | (arr > 1e30)] = np.nan
        reproject(arr, out, src_transform=tr, src_crs=src.crs, src_nodata=np.nan,
                  dst_transform=dst_tr, dst_crs=src.crs, dst_nodata=np.nan, resampling=resampling)
    return out.astype(dtype) if dtype != "float32" else out, dst_tr


def grid_meta(sc: Scene, extent, res):
    xmin, ymin, xmax, ymax = extent
    return {"extent_local_m": list(extent), "res_m": res,
            "shape": [int(round((ymax - ymin) / res)), int(round((xmax - xmin) / res))],
            "corners_lonlat": sc.grid.corners_lonlat(*extent)}


def run(scene: str):
    sc = Scene(scene)
    g = sc.cfg["grid"]
    aoi = sc.extent("aoi")
    pad = 30.0
    aoi_pad = (aoi[0] - pad, aoi[1] - pad, aoi[2] + pad, aoi[3] + pad)
    ctx = sc.extent("context")
    meta = {"base": sc.cfg["base"], "aoi": grid_meta(sc, aoi, g["ortho_res_m"]),
            "local_crs": f"+proj=eqc +lat_ts={sc.grid.lat0} +lat_0={sc.grid.lat0} +lon_0={sc.grid.lon0} +R=3396190 +units=m",
            "products": {}}
    al_path = sc.work / "alignment.json"
    al = read_json(al_path) if al_path.exists() else {}

    def save(name, arr, tr, extent, res, note=""):
        save_local_tif(sc.work / f"{name}.tif", arr, tr, nodata=np.nan if arr.dtype.kind == "f" else None)
        v = arr[np.isfinite(arr)] if arr.dtype.kind == "f" else arr.ravel()
        nan = float(np.mean(~np.isfinite(arr))) if arr.dtype.kind == "f" else 0.0
        meta["products"][name] = {**grid_meta(sc, extent, res), "nan_frac": round(nan, 5),
                                  "min": float(v.min()), "max": float(v.max()), "note": note}
        log(scene, "grid", f"{name}: {arr.shape} res {res} m, NaN {nan:.2%}, range {v.min():.2f}..{v.max():.2f}")

    # reference (HiRISE)
    a, tr = to_local(sc.raw_path("ortho"), sc, aoi, g["ortho_res_m"], Resampling.bilinear)
    save("ortho_025", a, tr, aoi, g["ortho_res_m"], "HiRISE orthoimage, raw DN")
    a, tr = to_local(sc.raw_path("dtm_fine"), sc, aoi_pad, g["dtm_res_m"], Resampling.bilinear)
    save("dtm_fine", a, tr, aoi_pad, g["dtm_res_m"], "HiRISE DTM, m (padded 30 m for derivatives)")

    # prior (CTX): global horizontal shift + vertical offset from align (applied only after align has run)
    sh = al.get("prior", {}).get("applied_shift_m", [0.0, 0.0])
    dz = al.get("prior", {}).get("applied_vertical_offset_m", 0.0)
    pres = sc.cfg["grid"].get("prior_res_m", 20.0)
    a, tr = to_local(sc.raw_path("dtm_prior"), sc, ctx, pres, Resampling.bilinear, shift_xy=tuple(sh))
    save("dtm_prior_ctx", a + dz, tr, ctx, pres, f"CTX DTM, shift {sh} m, vertical {dz:+.2f} m")
    po_res = sc.cfg["grid"].get("prior_ortho_res_m", 6.0)
    a, tr = to_local(sc.raw_path("prior_ortho"), sc, ctx, po_res, Resampling.bilinear, shift_xy=tuple(sh))
    save("prior_ortho_ctx", a, tr, ctx, po_res, f"CTX orthoimage, shift {sh} m")

    if "post_landing" in sc.cfg["sources"]:
        psh = al.get("post_landing", {}).get("applied_shift_m", [0.0, 0.0])
        a, tr = to_local(sc.raw_path("post_landing"), sc, aoi, g["ortho_res_m"], Resampling.bilinear, shift_xy=tuple(psh))
        save("post_landing_025", a, tr, aoi, g["ortho_res_m"], f"post-landing HiRISE, shift {psh} m")

    meta["alignment_applied"] = {"prior_shift_m": sh, "prior_dz_m": dz,
                                 "post_landing_shift_m": al.get("post_landing", {}).get("applied_shift_m")}
    write_json(sc.work / "grid.json", meta)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    run(ap.parse_args().scene)
