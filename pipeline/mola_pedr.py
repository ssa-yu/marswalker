"""R1(b) MOLA PEDR supplementary check (spec locked by manager 2026-11-14 in direction.md, before results).

python -m pipeline.mola_pedr --scene jezero

Spec (not changed after seeing results):
  * MOLA PEDR shots (individual laser measurements, ODE GDS molapedr query, TOPOGRAPHY = radius - areoid)
    inside the valid extent of the HiRISE DTM mosaic (D1);
  * DTM value at a shot = mean of all DTM cells whose centres lie within 84 m (ground) of the shot
    (MOLA footprint ~168 m). A shot is inside the valid extent only if every D1 cell in that disc is valid
    (rule written here before the run). The same shots are used for the CTX DTM (D3);
  * D3 gets the X3-1 registration (shift and vertical offset from alignment.json); no other horizontal shift
    is fitted for anything;
  * thresholds as X3-3/4: HiRISE - PEDR |mean| <= 10 m and std <= 10 m; shifted CTX - PEDR std <= 10 m
    (mean reported);  fewer than 30 valid shots -> "insufficient to judge".
Result is reported next to the original X3-3/4 result; it does not replace it.
"""
from __future__ import annotations

import argparse
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.windows import Window  # noqa: E402

from .common import R_MARS, Scene, log, read_json, write_json  # noqa: E402

RADIUS_M = 84.0
MIN_SHOTS = 30
THR = {"abs_mean": 10.0, "std": 10.0}


def disc_mean(src, arr_reader, lon, lat, shift=(0.0, 0.0), dz=0.0, require_full=True):
    """Mean of DTM cells (centres) within RADIUS_M ground metres of (lon, lat). shift: local metres (E, N)
    ADDED to the DTM georeference (same convention as pipeline.grid.to_local)."""
    tr = src.transform
    k = math.cos(math.radians(lat))
    X = R_MARS * math.radians(lon); Y = R_MARS * math.radians(lat)
    X0 = tr.c + shift[0] / k; Y0 = tr.f + shift[1]
    rx = RADIUS_M / k  # source-CRS metres in x for 84 ground metres
    c0 = int(math.floor((X - rx - X0) / tr.a)) - 1; c1 = int(math.ceil((X + rx - X0) / tr.a)) + 1
    r0 = int(math.floor((Y + RADIUS_M - Y0) / tr.e)) - 1; r1 = int(math.ceil((Y - RADIUS_M - Y0) / tr.e)) + 1
    if c0 < 0 or r0 < 0 or c1 > src.width or r1 > src.height:
        return np.nan, 0, 0
    a = arr_reader(Window(c0, r0, c1 - c0, r1 - r0))
    cx = X0 + (np.arange(c0, c1) + 0.5) * tr.a; cy = Y0 + (np.arange(r0, r1) + 0.5) * tr.e
    dx = (cx[None, :] - X) * k; dy = cy[:, None] - Y
    m = dx ** 2 + dy ** 2 <= RADIUS_M ** 2
    v = a[m]
    ok = np.isfinite(v)
    if require_full and not ok.all():
        return np.nan, int(m.sum()), int(ok.sum())
    if not ok.any():
        return np.nan, int(m.sum()), 0
    return float(v[ok].mean() + dz), int(m.sum()), int(ok.sum())


def reader(src):
    nd = src.nodata

    def f(win):
        a = src.read(1, window=win).astype("float64")
        if nd is not None:
            a[a == nd] = np.nan
        a[(a < -1e30) | (a > 1e30)] = np.nan
        return a
    return f


def run(scene: str, dtm_full: str, pedr_csv: str):
    sc = Scene(scene)
    al = read_json(sc.work / "alignment.json")
    P = np.genfromtxt(pedr_csv, delimiter=",", skip_header=1, usecols=(0, 1, 2))
    lon = np.where(P[:, 0] > 180, P[:, 0] - 360, P[:, 0]); lat = P[:, 1]; top = P[:, 2]
    sh = tuple(al["prior"]["applied_shift_m"]); dz = al["prior"]["applied_vertical_offset_m"]
    rows = []
    with rasterio.open(dtm_full) as H, rasterio.open(sc.raw_path("dtm_prior")) as C:
        rh, rc = reader(H), reader(C)
        for i in range(len(lon)):
            h, nh, okh = disc_mean(H, rh, lon[i], lat[i])
            c, nc, okc = disc_mean(C, rc, lon[i], lat[i], shift=sh, dz=dz)
            rows.append((lon[i], lat[i], top[i], h, c, nh, okh, nc))
    A = np.array(rows, float)
    valid = np.isfinite(A[:, 3]) & np.isfinite(A[:, 4])
    dh = A[valid, 3] - A[valid, 2]; dc = A[valid, 4] - A[valid, 2]
    n = int(valid.sum())

    def st(d):
        return {"mean_m": round(float(d.mean()), 2), "std_m": round(float(d.std()), 2),
                "median_m": round(float(np.median(d)), 2), "max_abs_m": round(float(np.abs(d).max()), 2)} if d.size else None
    res = {"spec": {"shots": "ODE GDS molapedr TOPOGRAPHY (radius - areoid), query box 18.31-18.67 N, 77.22-77.58 E",
                    "disc_radius_m": RADIUS_M, "valid_rule": "every HiRISE DTM cell in the disc is valid; same shots for CTX",
                    "horizontal_shift_fitted": False, "ctx_registration_applied": {"shift_m": list(sh), "dz_m": dz},
                    "thresholds": "HiRISE |mean|<=10 & std<=10 m; CTX std<=10 m; n<30 -> insufficient"},
           "n_shots_query": int(len(lon)), "n_shots_valid": n}
    if n < MIN_SHOTS:
        res["verdict"] = "insufficient to judge (fewer than 30 valid shots)"
    else:
        res["hirise_minus_pedr"] = st(dh); res["ctx_shifted_minus_pedr"] = st(dc)
        res["hirise_pass"] = bool(abs(dh.mean()) <= THR["abs_mean"] and dh.std() <= THR["std"])
        res["ctx_pass"] = bool(dc.std() <= THR["std"])
        res["verdict"] = f"HiRISE {'pass' if res['hirise_pass'] else 'fail'}; CTX {'pass' if res['ctx_pass'] else 'fail'}"
    # local terrain context for the figure (not part of the verdict)
    x, y = sc.grid.lonlat_to_xy(A[valid, 0], A[valid, 1])
    write_json(sc.qa / "R1_mola_pedr.json", res)
    np.savetxt(sc.qa / "R1_mola_pedr_shots.csv", np.c_[A[valid, :5]], delimiter=",", fmt="%.5f",
               header="lon_e,lat_n,pedr_topo_m,hirise_disc_mean_m,ctx_shifted_disc_mean_m", comments="")
    if n:
        fig, ax = plt.subplots(1, 3, figsize=(16, 5.2))
        s = ax[0].scatter(x / 1000, y / 1000, c=dh, cmap="RdBu_r", vmin=-30, vmax=30, s=8)
        plt.colorbar(s, ax=ax[0], label="HiRISE - PEDR (m)")
        aoi = sc.extent("aoi")
        ax[0].add_patch(plt.Rectangle((aoi[0] / 1000, aoi[1] / 1000), (aoi[2] - aoi[0]) / 1000, (aoi[3] - aoi[1]) / 1000, fill=False, ec="k", ls="--"))
        ax[0].set_xlabel("km east of base"); ax[0].set_ylabel("km north of base"); ax[0].set_title(f"{n} PEDR shots in the HiRISE mosaic (AOI dashed)")
        b = np.arange(-60, 61, 2)
        ax[1].hist(dh, b, alpha=.6, label=f"HiRISE: {dh.mean():+.1f} ± {dh.std():.1f} m"); ax[1].hist(dc, b, alpha=.6, label=f"CTX (shifted): {dc.mean():+.1f} ± {dc.std():.1f} m")
        ax[1].axvspan(-10, 10, color="g", alpha=.08); ax[1].legend(); ax[1].set_xlabel("DTM (84 m disc mean) - PEDR (m)")
        ax[1].set_title("Supplementary check, no horizontal shift fitted")
        ax[2].scatter(A[valid, 2], dh, s=5, label="HiRISE"); ax[2].scatter(A[valid, 2], dc, s=5, label="CTX")
        ax[2].axhline(0, c="k", lw=.5); ax[2].set_xlabel("PEDR topography (m)"); ax[2].set_ylabel("DTM - PEDR (m)"); ax[2].legend()
        fig.suptitle(f"R1(b) MOLA PEDR vs HiRISE / CTX DTM — {res['verdict']}")
        fig.tight_layout(); fig.savefig(sc.qa / "R1_mola_pedr.png"); plt.close(fig)
    log(scene, "pedr", str(res))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    ap.add_argument("--dtm", default="data_raw/jezero/step2/hirise_dtm_full.tif")
    ap.add_argument("--pedr", default=None)
    a = ap.parse_args()
    from pathlib import Path
    pedr = a.pedr or str(next(Path("data_raw/jezero/step2/pedr").glob("*topo_csv.csv")))
    run(a.scene, a.dtm, pedr)
