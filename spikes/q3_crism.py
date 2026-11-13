"""R4 Q3: CRISM MTRDR summary parameters over the Jezero AOI (check images + facts only).

python -I spikes/q3_crism.py   (from app/) -> qa/jezero/step2/Q3_*.png, q3_results.json

Parameters (Viviano-Beck et al. 2014 summary products, as delivered in the *_su*_mtr3 cubes):
  carbonate: MIN2345_2537, BD2500_2 · Fe/Mg phyllosilicate: D2300 · hydrated: BD1900R2 · mafic: OLINDEX3 (olivine), LCPINDEX2 (low-Ca pyroxene)
Registration: R770 band vs HiRISE orthoimage averaged to 18 m, one global shift per product (phase correlation).
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pipeline.align import norm_hp, register  # noqa: E402
from pipeline.common import Scene  # noqa: E402

sc = Scene("jezero")
CR = APP / "data_raw/jezero/step2/crism"
OUT = APP / "qa/jezero/step2"
AOI = sc.extent("aoi")
RES = 6.0
PARAMS = ["R770", "MIN2345_2537", "BD2500_2", "D2300", "BD1900R2", "OLINDEX3", "LCPINDEX2"]
SHOW = [("MIN2345_2537", "carbonate (MIN2345_2537)"), ("D2300", "Fe/Mg phyllosilicate (D2300)"),
        ("BD1900R2", "hydrated (BD1900R2)"), ("OLINDEX3", "olivine (OLINDEX3)")]


def band_names(hdr):
    t = hdr.read_text()
    i = t.lower().index("band names"); j = t.index("}", i)
    return [b.strip() for b in t[t.index("{", i) + 1:j].split(",")]


def to_local(path, bidx, extent, res, shift=(0.0, 0.0)):
    xmin, ymin, xmax, ymax = extent
    W = int(round((xmax - xmin) / res)); H = int(round((ymax - ymin) / res))
    out = np.full((H, W), np.nan, "float32")
    dst = sc.grid.src_transform(xmin, ymax, res)
    from affine import Affine
    dst = Affine(dst.a, 0, dst.c - shift[0] / sc.grid.k, 0, dst.e, dst.f - shift[1])
    with rasterio.open(path) as s:
        a = s.read(bidx).astype("float32")
        a[(a >= 65534) | (a <= -1e30) | ~np.isfinite(a)] = np.nan
        reproject(a, out, src_transform=s.transform, src_crs=s.crs, src_nodata=np.nan, dst_transform=dst,
                  dst_crs="+proj=eqc +lat_ts=0 +lat_0=0 +lon_0=0 +R=3396190 +units=m +no_defs", dst_nodata=np.nan,
                  resampling=Resampling.nearest)
    return out


res = {"products": {}}
# HiRISE ortho at 18 m for registration
with rasterio.open(sc.work / "ortho_025.tif") as o:
    hi = o.read(1, out_shape=(o.height // 72, o.width // 72), resampling=Resampling.average).astype("float32")
hi[hi == 0] = np.nan
maps = {}
for img in sorted(CR.glob("*_su*_mtr3.img")):
    pid = img.name[:11]
    names = band_names(img.with_suffix(".hdr"))
    idx = {n: names.index(n) + 1 for n in PARAMS}
    r770 = to_local(img, idx["R770"], AOI, 18.0)
    cov = float(np.isfinite(r770).mean())
    rec = {"aoi_coverage": round(cov, 3), "pixel_m": 18.0, "n_bands": len(names)}
    if cov > 0.2:
        a, oka = norm_hp(hi, 4.0); b, okb = norm_hp(r770, 4.0)
        m = oka & okb
        r0 = float(np.corrcoef(a[m], b[m])[0, 1])
        sh = register(np.where(m, a, 0), np.where(m, b, 0), 18.0)
        r2 = to_local(img, idx["R770"], AOI, 18.0, shift=sh)
        b2, okb2 = norm_hp(r2, 4.0); m2 = oka & okb2
        r1 = float(np.corrcoef(a[m2], b2[m2])[0, 1])
        rec.update({"shift_to_hirise_m": [round(sh[0], 1), round(sh[1], 1)], "r_before": round(r0, 3), "r_after": round(r1, 3)})
        maps[pid] = {p: to_local(img, idx[p], AOI, RES, shift=sh if r1 > r0 else (0, 0)) for p in PARAMS}
    res["products"][pid] = rec
    print(pid, rec)

# check images: product with the largest coverage, plus per-product coverage panel
best = max(maps, key=lambda k: res["products"][k]["aoi_coverage"]) if maps else None
res["primary_product"] = best
with rasterio.open(sc.work / "ortho_025.tif") as o:
    hb = o.read(1, out_shape=(o.height // 8, o.width // 8), resampling=Resampling.average).astype("float32")
hb[hb == 0] = np.nan
e = [AOI[0], AOI[2], AOI[1], AOI[3]]
if best:
    fig, axs = plt.subplots(2, 3, figsize=(17, 11))
    axs = axs.ravel()
    axs[0].imshow(hb, cmap="gray", extent=e, vmin=np.nanpercentile(hb, 1), vmax=np.nanpercentile(hb, 99))
    for k, pid in enumerate(maps):
        v = np.isfinite(maps[pid]["R770"])
        axs[0].contour(np.linspace(e[0], e[1], v.shape[1]), np.linspace(e[3], e[2], v.shape[0]), v.astype(float), levels=[.5], colors=[f"C{k}"], linewidths=1.2)
    axs[0].set_title("CRISM footprints in the AOI: " + ", ".join(f"C{k}={p}" for k, p in enumerate(maps)), fontsize=8)
    for ax, (p, t) in zip(axs[1:5], SHOW):
        a = maps[best][p]
        ax.imshow(hb, cmap="gray", extent=e, vmin=np.nanpercentile(hb, 1), vmax=np.nanpercentile(hb, 99))
        hi_ = np.nanpercentile(a, 99) if np.isfinite(a).any() else 1
        im = ax.imshow(np.ma.masked_invalid(np.where(a > 0, a, np.nan)), cmap="magma", extent=e, vmin=0, vmax=max(hi_, 1e-4), alpha=.75)
        plt.colorbar(im, ax=ax, fraction=.046); ax.set_title(f"{t} · {best}")
    a = maps[best]["LCPINDEX2"]
    ax = axs[5]; ax.imshow(hb, cmap="gray", extent=e, vmin=np.nanpercentile(hb, 1), vmax=np.nanpercentile(hb, 99))
    im = ax.imshow(np.ma.masked_invalid(np.where(a > 0, a, np.nan)), cmap="magma", extent=e, vmin=0, vmax=np.nanpercentile(a, 99), alpha=.75)
    plt.colorbar(im, ax=ax, fraction=.046); ax.set_title(f"low-Ca pyroxene (LCPINDEX2) · {best}")
    fig.suptitle("Q3 CRISM MTRDR summary parameters over the AOI (orbital PRIOR, 18 m pixels; values <= 0 not drawn). Question for a person: any visible spatial pattern?")
    fig.tight_layout(); fig.savefig(OUT / "Q3_crism_parameters.png", dpi=85); plt.close(fig)

# correlation at SuperCam locations (location = waypoint by sol; 3x3 CRISM pixels around it)
q = json.loads((OUT / "q_results.json").read_text()) if (OUT / "q_results.json").exists() else None
import re  # noqa: E402
W = sorted(json.loads((sc.work / "waypoints_all.json").read_text()), key=lambda w: (w["sol"], w["site"], w["drive"]))
wsol = np.array([w["sol"] for w in W])
lines = (APP / "data_raw/jezero/step2/supercam/supercam_libs_moc.csv").read_text().splitlines()
hi_ = next(i for i, l in enumerate(lines) if l.startswith("cdr_fname")); cols = lines[hi_].split(",")
acc = {}
for l in lines[hi_ + 1:]:
    p_ = l.split(","); m = re.match(r"scam_(\d{4})_\d+_\d+_\w{3}_scam\d+_(.+?)_*(\d{2})p$", p_[0])
    if not m or m.group(2).lower().startswith("scct"):
        continue
    i = int(np.searchsorted(wsol, int(m.group(1)), side="right")) - 1
    w = W[i]
    if not (AOI[0] <= w["x"] <= AOI[2] and AOI[1] <= w["y"] <= AOI[3]):
        continue
    try:
        mg = float(p_[cols.index("MgO")]); fe = float(p_[cols.index("FeOT")])
    except ValueError:
        continue
    acc.setdefault(w["id"], [w["x"], w["y"], []])[2].append((mg, fe))
from scipy.stats import spearmanr  # noqa: E402
corr = {}
if best:
    for p in ("OLINDEX3", "LCPINDEX2", "D2300", "BD1900R2"):
        xs, mgs, fes = [], [], []
        a = maps[best][p]
        for wid, (x, y, v) in acc.items():
            c = int((x - AOI[0]) / RES); r = int((AOI[3] - y) / RES)
            win = a[max(r - 4, 0):r + 5, max(c - 4, 0):c + 5]  # ~ 3x3 CRISM pixels
            if np.isfinite(win).sum() < 10:
                continue
            xs.append(float(np.nanmean(win))); mgs.append(np.mean([t[0] for t in v])); fes.append(np.mean([t[1] for t in v]))
        if len(xs) >= 8:
            r1 = spearmanr(xs, mgs); r2 = spearmanr(xs, fes)
            corr[p] = {"n_locations": len(xs), "spearman_vs_MgO": round(float(r1.statistic), 3), "p_MgO": round(float(r1.pvalue), 4),
                       "spearman_vs_FeOT": round(float(r2.statistic), 3), "p_FeOT": round(float(r2.pvalue), 4)}
        else:
            corr[p] = {"n_locations": len(xs)}
res["supercam_correlation_primary_product"] = corr
res["note"] = "location = Perseverance waypoint chosen by sol; Spearman over location means; n is the number of distinct locations"
(OUT / "q3_results.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
