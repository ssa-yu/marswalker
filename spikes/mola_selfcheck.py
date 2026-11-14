# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""R1(a) MOLA self-check: is the X3-3/4 misfit at Jezero caused by OUR sampling, or by the MOLA 463 m mosaic?

python -I spikes/mola_selfcheck.py            (run from app/; writes qa/jezero/R1_mola_selfcheck.json + .png)

Checks (none of them changes the locked X3 verdict):
 S1  our strip-window reader vs GDAL's own reader of the same remote window (values + georeference)
 S2  header of the remote mosaic: pixel registration (AREA_OR_POINT), pixel size vs the sphere in its CRS
 S3  MOLA PEDR shots (the measurements the mosaic was gridded from) vs the mosaic itself, read by GDAL:
     residual at zero offset and the best-fit mosaic offset (grid search, 1/8 cell). This compares MOLA with
     MOLA: it does not involve HiRISE, CTX or our local grid.
 S4  the same PEDR-vs-mosaic test at Arcadia 060706 (USGS ARD shot list stored with that product) and the
     CTX-vs-mosaic offset search there (same code path as Jezero)
"""
import json
import math
import os
import sys
from pathlib import Path

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np
import rasterio
from osgeo import gdal
from scipy.ndimage import map_coordinates

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
URL = "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
R = 3396190.0
gdal.UseExceptions()
out = {}


def gdal_window(lon0, lon1, lat0, lat1, margin_cells=4):
    ds = gdal.Open("/vsicurl/" + URL)
    gt = ds.GetGeoTransform()
    X0, X1 = R * math.radians(lon0), R * math.radians(lon1)
    Y0, Y1 = R * math.radians(lat0), R * math.radians(lat1)
    c0 = int(math.floor((X0 - gt[0]) / gt[1])) - margin_cells; c1 = int(math.ceil((X1 - gt[0]) / gt[1])) + margin_cells
    r0 = int(math.floor((Y1 - gt[3]) / gt[5])) - margin_cells; r1 = int(math.ceil((Y0 - gt[3]) / gt[5])) + margin_cells
    a = ds.GetRasterBand(1).ReadAsArray(c0, r0, c1 - c0, r1 - r0).astype("float64")
    nd = ds.GetRasterBand(1).GetNoDataValue()
    a[a == nd] = np.nan
    tr = (gt[0] + c0 * gt[1], gt[1], gt[3] + r0 * gt[5], gt[5])  # x0, dx, y0, dy (pixel edges)
    return a, tr, gt, ds.GetMetadataItem("AREA_OR_POINT"), (ds.RasterXSize, ds.RasterYSize)


def interp(a, tr, lon, lat, dcol=0.0, drow=0.0):
    """Bilinear value of grid `a` at lon/lat; pixel-is-area (values at cell centres). dcol/drow shift the GRID
    georeference by that many cells (+col = east, +row = south)."""
    X = R * np.radians(lon); Y = R * np.radians(lat)
    col = (X - (tr[0] + dcol * tr[1])) / tr[1] - 0.5
    row = (Y - (tr[2] + drow * tr[3])) / tr[3] - 0.5
    return map_coordinates(a, [row, col], order=1, mode="constant", cval=np.nan)


def offset_search(a, tr, lon, lat, z, k):
    best = None
    grid = np.arange(-2, 2.001, 0.125)
    for dc in grid:
        for dr in grid:
            d = interp(a, tr, lon, lat, dc, dr) - z
            m = np.isfinite(d)
            if m.sum() < 30:
                continue
            s = float(np.std(d[m]))
            if best is None or s < best[0]:
                best = (s, float(dc), float(dr), float(np.mean(d[m])), int(m.sum()))
    s, dc, dr, mu, n = best
    return {"best_offset_cells_col_row": [dc, dr],
            "best_offset_m_east_north": [round(dc * tr[1] * k, 0), round(-dr * abs(tr[3]), 0)],
            "mosaic_minus_shots_at_best": {"mean_m": round(mu, 2), "std_m": round(s, 2), "n": n}}


# ---- S1: our reader vs GDAL -------------------------------------------------------------------------
with rasterio.open(APP / "data_raw/jezero/mola.tif") as M:
    ours = M.read(1).astype("float64"); otr = M.transform
ds = gdal.Open("/vsicurl/" + URL); gt = ds.GetGeoTransform()
c0 = int(round((otr.c - gt[0]) / gt[1])); r0 = int(round((otr.f - gt[3]) / gt[5]))
ref = ds.GetRasterBand(1).ReadAsArray(c0, r0, ours.shape[1], ours.shape[0]).astype("float64")
out["S1_reader"] = {"window_col_row": [c0, r0], "shape": list(ours.shape),
                    "georef_offset_cells": [round((otr.c - gt[0]) / gt[1] - c0, 6), round((otr.f - gt[3]) / gt[5] - r0, 6)],
                    "max_abs_value_diff_m": float(np.nanmax(np.abs(ours - ref))),
                    "same_pixel_size": bool(abs(otr.a - gt[1]) < 1e-9 and abs(otr.e - gt[5]) < 1e-9)}

# ---- S2: header -------------------------------------------------------------------------------------
W, H = ds.RasterXSize, ds.RasterYSize
out["S2_header"] = {"AREA_OR_POINT": ds.GetMetadataItem("AREA_OR_POINT"), "size": [W, H], "pixel_m": gt[1],
                    "pixel_m_if_1_128_deg_on_R3396190": round(R * math.pi / 180 / 128, 4),
                    "sphere_radius_implied_by_pixel_m": round(gt[1] * 128 * 180 / math.pi, 1),
                    "origin_lon_deg": round(math.degrees(gt[0] / R), 6), "origin_lat_deg": round(math.degrees(gt[3] / R), 6),
                    "note": "Pixel size implies R = 3,396,263 m while the CRS says 3,396,190 m; origin is half a cell beyond -180 E / 90 N. "
                            "If the data are on an exact 1/128 deg grid, the georeference is off at Jezero by the amount below."}
lon, lat = 77.45088572, 18.44462715
c = (lon + 180) * 128; r = (90 - lat) * 128
Xg = gt[0] + c * gt[1]; Yg = gt[3] - r * gt[1]
k = math.cos(math.radians(lat))
out["S2_header"]["implied_misplacement_at_base_m_east_north_if_exact_1_128_grid_from_edges"] = [
    round((math.degrees(Xg / R) - lon) * math.pi / 180 * R * k, 1), round((math.degrees(Yg / R) - lat) * math.pi / 180 * R, 1)]

# ---- S3: PEDR vs mosaic at Jezero -------------------------------------------------------------------
pedr_csv = next((APP / "data_raw/jezero/step2/pedr").glob("*topo_csv.csv"))
P = np.genfromtxt(pedr_csv, delimiter=",", skip_header=1, usecols=(0, 1, 2))
plon, plat, ptop = P[:, 0], P[:, 1], P[:, 2]
a, tr, _, _, _ = gdal_window(77.22, 77.58, 18.31, 18.67)
d0 = interp(a, tr, plon, plat) - ptop; m0 = np.isfinite(d0)
out["S3_jezero_pedr_vs_mosaic"] = {"n_shots": int(m0.sum()),
                                  "mosaic_minus_shots_zero_offset": {"mean_m": round(float(d0[m0].mean()), 2), "std_m": round(float(d0[m0].std()), 2)},
                                  **offset_search(a, tr, plon, plat, ptop, k),
                                  "pedr_query": "ODE GDS molapedr, 18.31-18.67 N, 77.22-77.58 E, TOPOGRAPHY = planet radius - areoid"}

# ---- S4: Arcadia 060706 -----------------------------------------------------------------------------
ar = APP / "data_raw/arcadia_starship_060706"
S = np.genfromtxt(next(ar.glob("*mola_shots.csv")), delimiter=",", skip_header=1)
slat, slon, srad = S[:, 0], S[:, 1], S[:, 2]
slon = np.where(slon > 180, slon - 360, slon)
a2, tr2, _, _, _ = gdal_window(slon.min(), slon.max(), slat.min(), slat.max())
# shots carry planetary radius; the mosaic is radius - areoid. Areoid is smooth (varies << 1 m over 20 km),
# so the offset search on (mosaic - radius) is still valid; only its mean includes the areoid radius.
k2 = math.cos(math.radians(float(np.mean(slat))))
r4 = offset_search(a2, tr2, slon, slat, srad, k2)
d = interp(a2, tr2, slon, slat) - srad; mm = np.isfinite(d)
r4["mosaic_minus_shots_zero_offset_std_m"] = round(float(d[mm].std()), 2)
r4["n_shots"] = int(mm.sum())
r4["note"] = "shots: USGS ARD product file *_mola_shots.csv (radius); mean includes areoid radius, only std/offset are meaningful"
out["S4_arcadia_060706_pedr_vs_mosaic"] = r4
# CTX DTM vs mosaic offset search at 060706 (same idea as the Jezero diagnostic)
ctx = next(ar.glob("*_dtm.tif"))
with rasterio.open(ctx) as C:
    from rasterio.warp import reproject, Resampling, transform_bounds
    b = transform_bounds(C.crs, "+proj=longlat +R=3396190 +no_defs", *C.bounds)
    lo0, la0, lo1, la1 = b
    lo0, lo1 = [(v + 180) % 360 - 180 for v in (lo0, lo1)]
    a3, tr3, gt3, _, _ = gdal_window(lo0, lo1, la0, la1, margin_cells=0)
    carr = C.read(1, masked=True).astype("float64").filled(np.nan)
    ccrs, ctr = C.crs, C.transform
res = []
k3 = math.cos(math.radians((la0 + la1) / 2))
mcrs = "+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +R=3396190 +units=m +no_defs"
from affine import Affine
for dc in np.arange(-2, 2.001, 0.25):
    for dr in np.arange(-2, 2.001, 0.25):
        t = Affine(tr3[1], 0, tr3[0] + dc * tr3[1], 0, tr3[3], tr3[2] + dr * tr3[3])
        o = np.full(a3.shape, np.nan)
        reproject(carr, o, src_transform=ctr, src_crs=ccrs, src_nodata=np.nan, dst_transform=t, dst_crs=mcrs,
                  dst_nodata=np.nan, resampling=Resampling.average)
        dd = o - a3; q = np.isfinite(dd); q[[0, -1], :] = False; q[:, [0, -1]] = False
        if q.sum() > 30:
            res.append((float(dd[q].std()), float(dc), float(dr), int(q.sum())))
res.sort()
z0 = [r_ for r_ in res if r_[1] == 0 and r_[2] == 0]
out["S4_arcadia_060706_ctx_vs_mosaic"] = {"best_offset_cells_col_row": [res[0][1], res[0][2]],
                                          "best_offset_m_east_north": [round(res[0][1] * tr3[1] * k3, 0), round(-res[0][2] * abs(tr3[3]), 0)],
                                          "std_at_best_m": round(res[0][0], 2), "std_zero_offset_m": round(z0[0][0], 2) if z0 else None,
                                          "n_cells": res[0][3], "note": "CTX DTM is the uncontrolled USGS ARD product; its own 506 m shift is not applied here"}

(APP / "qa/jezero").mkdir(parents=True, exist_ok=True)
Path(APP / "qa/jezero/R1_mola_selfcheck.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
