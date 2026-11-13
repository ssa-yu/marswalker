"""S4 multi-window positioning check (X3 items 1-2; items 3-4 reported, not used to drop a window).

python -m pipeline.multiwindow_x3 [--windows "-1,0;-1,1"] [--fetch-only]

Windows = the main Jezero AOI (x -1700..700, y -1000..1400 m from the habitat) shifted by whole cells of
2400 m: window (i, j) covers x + 2400 i, y + 2400 j. Its habitat = main habitat + (2400 i, 2400 j)
(rule locked in direction.md "多視窗"; no waypoint is used for anything here).
Method = pipeline/align.py, unchanged: CTX 6 m ortho vs HiRISE ortho averaged to 6 m on the window's
"inner" extent (window + 300 m fetch margin - 50 m), high-pass sigma 60 m, phase correlation -> one
global shift; re-register the 4 quadrants after the shift; X3-2 passes if every quadrant deviation
<= 20 m. Vertical offset = median(CTX DTM shifted - HiRISE DTM) on a 20 m grid.
X3-3/4: MOLA 463 m cells fully covered by the product inside the window's fetch extent (interior cells).
Differs from the main-AOI run in one respect: there the prior-vs-MOLA statistic used the whole CTX
mosaic over a 12 km MOLA window; here both statistics are restricted to the window's fetch extent.
No routes, terrain classes or comparison numbers are computed.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from affine import Affine  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from scipy.ndimage import binary_erosion  # noqa: E402

from . import remote  # noqa: E402
from .align import X3, corr_at, norm_hp, quadrants, register  # noqa: E402
from .common import APP, Scene, log, read_json, write_json  # noqa: E402

CELL = 2400.0
WINDOWS = [(-1, 0), (-1, 1), (-2, 1), (-3, 1), (-4, 0)]
ORTHO_URLS = [
    "https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first.tif",
    "https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first.tif",
]
MOLA_URL = "https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif"
DTM_FULL = APP / "data_raw/jezero/step2/hirise_dtm_full.tif"


def win_extent(sc: Scene, i: int, j: int):
    a = sc.aoi
    return (a[0] + CELL * i, a[1] + CELL * j, a[2] + CELL * i, a[3] + CELL * j)


def grow(e, m):
    return (e[0] - m, e[1] - m, e[2] + m, e[3] + m)


def to_local_win(path, sc: Scene, extent, res, resampling, shift_xy=(0.0, 0.0)):
    """Like grid.to_local, but reads only a source window around `extent` (the full HiRISE DTM is 1.8 GB)."""
    xmin, ymin, xmax, ymax = extent
    W = int(round((xmax - xmin) / res)); H = int(round((ymax - ymin) / res))
    dst_tr = sc.grid.src_transform(xmin, ymax, res)
    out = np.full((H, W), np.nan, dtype="float32")
    with rasterio.open(path) as src:
        b = sc.grid.src_bounds(*grow(extent, 200.0))
        win = from_bounds(*b, src.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        arr = src.read(1, window=win, masked=True).astype("float32").filled(np.nan)
        arr[(arr < -1e30) | (arr > 1e30)] = np.nan
        if src.nodata is not None and src.dtypes[0] == "uint8":
            arr[arr == src.nodata] = np.nan
        tr = src.window_transform(win)
        if shift_xy != (0.0, 0.0):
            tr = Affine(tr.a, tr.b, tr.c + shift_xy[0] / sc.grid.k, tr.d, tr.e, tr.f + shift_xy[1])
        reproject(arr, out, src_transform=tr, src_crs=src.crs, src_nodata=np.nan,
                  dst_transform=dst_tr, dst_crs=src.crs, dst_nodata=np.nan, resampling=resampling)
    return out


def fetch_ortho(sc: Scene, i, j):
    d = APP / "data_raw/jezero/windows" / f"{i}_{j}"
    d.mkdir(parents=True, exist_ok=True)
    out = d / "ortho.tif"
    rec_p = d / "fetch_log.json"
    if out.exists():
        return read_json(rec_p) if rec_p.exists() else {"path": str(out), "cached": True}
    fet = grow(win_extent(sc, i, j), sc.cfg.get("fetch_margin_m", 300))
    b = sc.grid.src_bounds(*fet)
    last = None
    for url in ORTHO_URLS:
        try:
            t0 = time.time()
            rec = remote.strip_window(url, b, out)
            rec["wall_seconds"] = round(time.time() - t0, 1)
            rec["fetched_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            write_json(rec_p, rec)
            return rec
        except Exception as ex:  # noqa: BLE001
            last = ex
            log("jezero", "mwx3", f"ortho {i},{j} from {url} failed: {ex!r}")
    raise RuntimeError(last)


def fetch_mola(sc: Scene):
    out = APP / "data_raw/jezero/windows/mola_wide.tif"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    xs = [win_extent(sc, i, j) for i, j in WINDOWS + [(0, 0)]]
    e = (min(x[0] for x in xs) - 3000, min(x[1] for x in xs) - 3000, max(x[2] for x in xs) + 3000, max(x[3] for x in xs) + 3000)
    rec = remote.strip_window(MOLA_URL, sc.grid.src_bounds(*e), out)
    write_json(out.with_suffix(".json"), rec)
    return out


def mola_stats(sc: Scene, mola_path, product, fet, shift=(0.0, 0.0), dz=0.0):
    """Mean/std of product - MOLA over MOLA cells fully covered inside `fet` (interior cells)."""
    with rasterio.open(mola_path) as M:
        b = sc.grid.src_bounds(*fet)
        win = from_bounds(*b, M.transform).round_offsets().round_lengths()
        mola = M.read(1, window=win).astype("float64"); mtr = M.window_transform(win)
        mola[mola == M.nodata] = np.nan
        crs = M.crs
    with rasterio.open(product) as S:
        bb = sc.grid.src_bounds(*grow(fet, 1000.0))
        w2 = from_bounds(*bb, S.transform).round_offsets().round_lengths()
        w2 = w2.intersection(rasterio.windows.Window(0, 0, S.width, S.height))
        a = S.read(1, window=w2, masked=True).astype("float64").filled(np.nan)
        a[(a < -1e30) | (a > 1e30)] = np.nan
        tr = S.window_transform(w2)
    # keep only product data inside the fetch extent
    X0, Y0, X1, Y1 = sc.grid.src_bounds(*fet)
    cols = tr.c + (np.arange(a.shape[1]) + 0.5) * tr.a
    rows = tr.f + (np.arange(a.shape[0]) + 0.5) * tr.e
    a[:, (cols < X0) | (cols > X1)] = np.nan
    a[(rows < Y0) | (rows > Y1), :] = np.nan
    if shift != (0.0, 0.0):
        tr = Affine(tr.a, tr.b, tr.c + shift[0] / sc.grid.k, tr.d, tr.e, tr.f + shift[1])
    o = np.full(mola.shape, np.nan); cov = np.full(mola.shape, np.nan)
    reproject(a, o, src_transform=tr, src_crs=crs, src_nodata=np.nan, dst_transform=mtr, dst_crs=crs,
              dst_nodata=np.nan, resampling=Resampling.average)
    reproject(np.isfinite(a).astype("float64"), cov, src_transform=tr, src_crs=crs, dst_transform=mtr,
              dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.average)
    o[~(cov > 0.98)] = np.nan
    o = o + dz
    m = np.isfinite(o) & np.isfinite(mola)
    m = binary_erosion(m, iterations=1) if m.sum() > 50 else m
    d = (o - mola)[m]
    if d.size == 0:
        return {"n_cells": 0}
    return {"n_cells": int(d.size), "mean_m": round(float(d.mean()), 2), "std_m": round(float(d.std()), 2),
            "max_abs_m": round(float(np.abs(d).max()), 2)}


def run_window(sc: Scene, i, j, ortho_path, mola_path, fetch_rec):
    win = win_extent(sc, i, j)
    fet = grow(win, sc.cfg.get("fetch_margin_m", 300))
    inner = grow(fet, -50.0)
    rr = 6.0
    Hh = to_local_win(ortho_path, sc, inner, rr, Resampling.average); Hh[Hh == 0] = np.nan
    C = to_local_win(APP / "data_raw/jezero/prior_ortho.tif", sc, inner, rr, Resampling.bilinear); C[C <= 0] = np.nan
    sig = 60.0 / rr
    hz, hok = norm_hp(Hh, sig); cz, cok = norm_hp(C, sig)
    r0 = corr_at(hz, cz, hok & cok)
    sh = register(hz, cz, rr)
    C2 = to_local_win(APP / "data_raw/jezero/prior_ortho.tif", sc, inner, rr, Resampling.bilinear, shift_xy=sh); C2[C2 <= 0] = np.nan
    cz2, cok2 = norm_hp(C2, sig)
    r1 = corr_at(hz, cz2, hok & cok2)
    resid = register(hz, cz2, rr)
    q = quadrants(hz, cz2, rr)
    qdev = [float(np.hypot(a, b)) for a, b in q]
    # HiRISE coverage of the window itself (DTM, 20 m sampling, like Q5) and of the ortho
    dt20 = to_local_win(DTM_FULL, sc, win, 20.0, Resampling.nearest)
    cov_dtm = float(np.isfinite(dt20).mean())
    o20 = to_local_win(ortho_path, sc, win, 20.0, Resampling.nearest); o20[o20 == 0] = np.nan
    cov_ortho = float(np.isfinite(o20).mean())
    # vertical offset on 20 m grid
    Hp = to_local_win(DTM_FULL, sc, inner, 20.0, Resampling.average)
    Cp = to_local_win(APP / "data_raw/jezero/dtm_prior.tif", sc, inner, 20.0, Resampling.bilinear, shift_xy=sh)
    d = (Cp - Hp)[np.isfinite(Cp) & np.isfinite(Hp)]
    dz_med = float(np.median(d)); nmad = float(1.4826 * np.median(np.abs(d - dz_med)))
    ref_m = mola_stats(sc, mola_path, DTM_FULL, fet)
    pri_m = mola_stats(sc, mola_path, APP / "data_raw/jezero/dtm_prior.tif", fet, sh, -dz_med)
    checks = {
        "1_single_global_shift_recorded": True,
        "2_quadrants_within_20m": bool(max(qdev) <= X3["quadrant_dev_max_m"]),
        "3_ref_vs_mola": bool(ref_m.get("n_cells", 0) > 0 and abs(ref_m["mean_m"]) <= X3["ref_mola_abs_mean_max_m"] and ref_m["std_m"] <= X3["ref_mola_std_max_m"]),
        "4_prior_vs_mola_std": bool(pri_m.get("n_cells", 0) > 0 and pri_m["std_m"] <= X3["prior_mola_std_max_m"]),
    }
    rec = {
        "window": [i, j], "extent_local_m": list(win), "fetch_extent_local_m": list(fet),
        "habitat_local_m": [CELL * i, CELL * j],
        "habitat_lonlat": [round(float(v), 7) for v in sc.grid.xy_to_lonlat(CELL * i, CELL * j)],
        "hirise_dtm_coverage_frac": round(cov_dtm, 4), "hirise_ortho_coverage_frac": round(cov_ortho, 4),
        "image_registration": {"grid_res_m": rr, "measured_shift_m": [round(sh[0], 2), round(sh[1], 2)],
                               "shift_magnitude_m": round(float(np.hypot(*sh)), 2),
                               "r_before": round(r0, 3), "r_after": round(r1, 3),
                               "residual_after_shift_m": [round(resid[0], 2), round(resid[1], 2)],
                               "quadrant_shift_after_m": [[round(a, 2), round(b, 2)] for a, b in q],
                               "quadrant_dev_m": [round(v, 2) for v in qdev]},
        "vertical": {"prior_minus_ref_median_m": round(dz_med, 2), "nmad_m": round(nmad, 2), "n": int(d.size),
                     "applied_vertical_offset_m": round(-dz_med, 2)},
        "mola": {"reference_minus_mola": ref_m, "shifted_prior_minus_mola": pri_m,
                 "note": "MOLA 463 m cells fully covered inside the window fetch extent, interior cells; reported, not used to drop the window"},
        "x3": {"checks": checks, "items_1_2_pass": checks["1_single_global_shift_recorded"] and checks["2_quadrants_within_20m"]},
        "ortho_fetch": {k: fetch_rec.get(k) for k in ("url", "fetched_bytes", "seconds", "wall_seconds", "total_seconds", "cached") if k in fetch_rec},
    }
    log("jezero", "mwx3", f"({i},{j}) shift {sh[0]:+.1f},{sh[1]:+.1f} r {r0:.3f}->{r1:.3f} qdev {np.round(qdev, 1)} "
                         f"dz {dz_med:+.2f} cov {cov_dtm:.3f} ref-MOLA {ref_m} prior-MOLA {pri_m}")
    figure(sc, i, j, inner, hz, cz2, q, qdev, rec)
    return rec


def figure(sc, i, j, inner, hz, cz2, q, qdev, rec):
    out = APP / "qa/jezero/multiwindow"; out.mkdir(parents=True, exist_ok=True)
    e = [inner[0], inner[2], inner[1], inner[3]]
    ny, nx = hz.shape
    t = 25  # checkerboard tile (cells of 6 m = 150 m)
    yy, xx = np.mgrid[0:ny, 0:nx]
    chk = ((yy // t + xx // t) % 2).astype(bool)
    comb = np.where(chk, hz, cz2)
    fig, ax = plt.subplots(1, 3, figsize=(20, 7.2))
    for a_, im, ttl in ((ax[0], hz, "HiRISE ortho (reference), 6 m, high-pass"),
                        (ax[1], cz2, "CTX ortho (prior) after global shift, 6 m, high-pass"),
                        (ax[2], comb, "checkerboard 150 m: HiRISE / shifted CTX")):
        a_.imshow(im, cmap="gray", vmin=-2.5, vmax=2.5, extent=e)
        a_.set_title(ttl, fontsize=10); a_.set_xlabel("x east of main habitat (m)")
    ax[0].set_ylabel("y north of main habitat (m)")
    w = rec["extent_local_m"]
    for a_ in ax:
        a_.plot([w[0], w[2], w[2], w[0], w[0]], [w[1], w[1], w[3], w[3], w[1]], c="#ffcc00", lw=1)
        a_.plot(*rec["habitat_local_m"], marker="^", c="#ff5a4e", ms=9)
    cx = (inner[0] + inner[2]) / 2; cy = (inner[1] + inner[3]) / 2
    pos = [((inner[0] + cx) / 2, (cy + inner[3]) / 2), ((cx + inner[2]) / 2, (cy + inner[3]) / 2),
           ((inner[0] + cx) / 2, (inner[1] + cy) / 2), ((cx + inner[2]) / 2, (inner[1] + cy) / 2)]
    for (px, py), (dx, dy), dv in zip(pos, q, qdev):
        ax[2].annotate(f"({dx:+.1f}, {dy:+.1f}) m\n|{dv:.1f}| m", (px, py), color="#00e0ff", fontsize=11,
                       ha="center", va="center", bbox=dict(fc="black", alpha=.6, lw=0))
    ax[2].axvline(cx, c="#00e0ff", lw=.6); ax[2].axhline(cy, c="#00e0ff", lw=.6)
    ir = rec["image_registration"]; v = "PASS" if rec["x3"]["checks"]["2_quadrants_within_20m"] else "FAIL"
    fig.suptitle(f"Window ({i},{j}) X3-1/2: global CTX->HiRISE shift ({ir['measured_shift_m'][0]:+.1f} E, "
                 f"{ir['measured_shift_m'][1]:+.1f} N) m, r {ir['r_before']}->{ir['r_after']}; quadrant residuals "
                 f"after shift (cyan) max {max(qdev):.1f} m <= 20 m: {v}. Yellow = window, red = habitat (shifted, assumed). "
                 f"HiRISE DTM coverage {rec['hirise_dtm_coverage_frac']:.1%}", fontsize=10)
    fig.tight_layout(); fig.savefig(out / f"X3_{i}_{j}.png", dpi=80); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--windows", default=None, help='e.g. "-1,0;-4,0"; default = the five windows + (0,0) self-test')
    ap.add_argument("--fetch-only", action="store_true")
    a = ap.parse_args()
    sc = Scene("jezero")
    wins = [tuple(int(v) for v in s.split(",")) for s in a.windows.split(";")] if a.windows else WINDOWS
    recs = {}
    for i, j in wins:
        if (i, j) == (0, 0):
            continue
        log("jezero", "mwx3", f"fetch ortho ({i},{j}) ...")
        recs[(i, j)] = fetch_ortho(sc, i, j)
        log("jezero", "mwx3", f"  -> {recs[(i, j)]}")
    mola_path = fetch_mola(sc)
    if a.fetch_only:
        return
    outp = APP / "qa/jezero/multiwindow/x3_windows.json"
    book = read_json(outp) if outp.exists() else {}
    book["thresholds"] = X3
    book["method"] = __doc__.strip().split("\n\n", 1)[1]
    book.setdefault("windows", {})
    # main AOI, original run (pipeline/align.py)
    al = read_json(sc.work / "alignment.json")
    book["windows"]["0,0"] = {"window": [0, 0], "source": "data_work/jezero/alignment.json (pipeline/align.py, checkpoint 1)",
                              "habitat_local_m": [0, 0], "image_registration": al["prior"]["image_registration"],
                              "vertical": al["prior"]["vertical"], "mola": al["mola"], "x3": al["x3"]}
    # same code on the main AOI as a self-test (does not replace the original)
    st = run_window(sc, 0, 0, sc.raw_path("ortho"), mola_path, {"cached": True})
    book["self_test_0_0_this_code"] = st
    for (i, j) in recs:
        p = APP / "data_raw/jezero/windows" / f"{i}_{j}" / "ortho.tif"
        book["windows"][f"{i},{j}"] = run_window(sc, i, j, p, mola_path, recs[(i, j)])
        write_json(outp, book)
    write_json(outp, book)
    log("jezero", "mwx3", f"wrote {outp}")


if __name__ == "__main__":
    main()
