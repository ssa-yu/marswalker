# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""S6-4: CRISM four-quadrant check (same rule as X3 item 2: after ONE global shift, each quadrant's own
registration must be within 20 m of it). Products: the two MTRDR cubes covering ~100 % of the main AOI.

python -I spikes/s6_crism_quadrants.py  (from app/) -> qa/jezero/S6_crism_quadrants.{png,json}
Method = spikes/q3_crism.py: R770 band vs HiRISE ortho averaged to 18 m, high-pass (sigma 4 px) + contrast
normalisation, phase correlation (skimage). Global shift on the whole AOI, then the shifted product is
registered again in each AOI quadrant (1200 m x 1200 m).
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.argv = [sys.argv[0]]
from pipeline.align import norm_hp, register  # noqa: E402
import importlib.util  # noqa: E402

# reuse the readers of q3 without running its main body: copy the two helpers
from pipeline.common import Scene  # noqa: E402
sc = Scene("jezero")
CR = APP / "data_raw/jezero/step2/crism"
AOI = sc.extent("aoi")
GR = 18.0
import os
RS = Resampling.nearest if os.environ.get("RS", "nearest") == "nearest" else Resampling.bilinear
TAG = os.environ.get("RS", "nearest")


def band_names(hdr):
    t = hdr.read_text()
    i = t.lower().index("band names"); j = t.index("}", i)
    return [b.strip() for b in t[t.index("{", i) + 1:j].split(",")]


def to_local(path, bidx, extent, res, shift=(0.0, 0.0)):
    from affine import Affine
    from rasterio.warp import reproject
    xmin, ymin, xmax, ymax = extent
    W = int(round((xmax - xmin) / res)); H = int(round((ymax - ymin) / res))
    out = np.full((H, W), np.nan, "float32")
    dst = sc.grid.src_transform(xmin, ymax, res)
    dst = Affine(dst.a, 0, dst.c - shift[0] / sc.grid.k, 0, dst.e, dst.f - shift[1])
    with rasterio.open(path) as s:
        a = s.read(bidx).astype("float32")
        a[(a >= 65534) | (a <= -1e30) | ~np.isfinite(a)] = np.nan
        reproject(a, out, src_transform=s.transform, src_crs=s.crs, src_nodata=np.nan, dst_transform=dst,
                  dst_crs="+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +R=3396190 +units=m +no_defs", dst_nodata=np.nan,
                  resampling=RS)
    return out


with rasterio.open(sc.work / "ortho_025.tif") as o:
    hi = o.read(1, out_shape=(o.height // 72, o.width // 72), resampling=Resampling.average).astype("float32")
hi[hi == 0] = np.nan
a, oka = norm_hp(hi, 4.0)
res = {"rule": "X3 item 2 (locked): after one global shift, each quadrant registration within 20 m", "grid_m": GR,
       "method": "R770 vs HiRISE ortho at 18 m, high-pass sigma 4 px, phase correlation (same as Q3)", "products": {}}
fig, axs = plt.subplots(2, 3, figsize=(15, 10))
for row, pid in enumerate(("frt00005c5e", "hrl000040ff")):
    img = next(CR.glob(pid + "_07_su*_mtr3.img"))
    names = band_names(img.with_suffix(".hdr")); bi = names.index("R770") + 1
    with rasterio.open(img) as s:
        native = [abs(s.res[0]), abs(s.res[1])]
    r770 = to_local(img, bi, AOI, GR)
    b, okb = norm_hp(r770, 4.0); m = oka & okb
    sh = register(np.where(m, a, 0), np.where(m, b, 0), GR)
    r2 = to_local(img, bi, AOI, GR, shift=sh)
    b2, okb2 = norm_hp(r2, 4.0); m2 = oka & okb2
    r0 = float(np.corrcoef(a[m], b[m])[0, 1]); r1 = float(np.corrcoef(a[m2], b2[m2])[0, 1])
    ny, nx = a.shape
    q = []
    for r_0, r_1, c_0, c_1 in [(0, ny // 2, 0, nx // 2), (0, ny // 2, nx // 2, nx), (ny // 2, ny, 0, nx // 2), (ny // 2, ny, nx // 2, nx)]:
        A = np.where(m2, a, 0)[r_0:r_1, c_0:c_1]; B = np.where(m2, b2, 0)[r_0:r_1, c_0:c_1]
        q.append(register(A, B, GR))
    dev = [float(np.hypot(*v)) for v in q]
    # stability: quadrant shift measured on the UNSHIFTED product minus the global shift (independent estimate)
    q_raw = []
    for r_0, r_1, c_0, c_1 in [(0, ny // 2, 0, nx // 2), (0, ny // 2, nx // 2, nx), (ny // 2, ny, 0, nx // 2), (ny // 2, ny, nx // 2, nx)]:
        q_raw.append(register(np.where(m, a, 0)[r_0:r_1, c_0:c_1], np.where(m, b, 0)[r_0:r_1, c_0:c_1], GR))
    res["products"][pid] = {"native_pixel_m_in_file_crs": native, "global_shift_m": [round(sh[0], 1), round(sh[1], 1)],
                            "r_before": round(r0, 3), "r_after": round(r1, 3),
                            "quadrant_residual_after_shift_m": [[round(x, 1), round(y, 1)] for x, y in q],
                            "quadrant_dev_m": [round(v, 1) for v in dev],
                            "quadrant_shift_on_unshifted_m (UL, UR, LL, LR)": [[round(x, 1), round(y, 1)] for x, y in q_raw],
                            "pass_20m": bool(max(dev) <= 20.0)}
    e = [AOI[0], AOI[2], AOI[1], AOI[3]]
    axs[row, 0].imshow(a, cmap="gray", extent=e, vmin=-2, vmax=2); axs[row, 0].set_title("HiRISE ortho, 18 m, high-pass")
    axs[row, 1].imshow(b2, cmap="gray", extent=e, vmin=-2, vmax=2); axs[row, 1].set_title(f"{pid} R770 shifted {sh[0]:+.0f} E, {sh[1]:+.0f} N m")
    chk = ((np.indices(a.shape) // 11).sum(0) % 2).astype(bool)
    axs[row, 2].imshow(np.where(chk, a, b2), cmap="gray", extent=e, vmin=-2, vmax=2)
    axs[row, 2].set_title("checkerboard (HiRISE / shifted CRISM)\nquadrant dev m: " + ", ".join(f"{v:.0f}" for v in dev), fontsize=9)
    print(pid, res["products"][pid])
fig.suptitle("S6-4 CRISM four-quadrant check (rule: each quadrant within 20 m of the global shift)")
fig.tight_layout(); fig.savefig(APP / ("qa/jezero/S6_crism_quadrants_" + TAG + ".png"), dpi=80)
(APP / ("qa/jezero/S6_crism_quadrants_" + TAG + ".json")).write_text(json.dumps(res, indent=1))
