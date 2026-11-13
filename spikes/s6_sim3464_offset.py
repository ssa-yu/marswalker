"""S6-1: how far are the SIM 3464 contacts from the matching boundaries in the HiRISE reference?

python -I spikes/s6_sim3464_offset.py   (from app/) -> qa/jezero/S6_sim3464_offset.{png,json}
Method (written before running): take every SIM 3464 GeoContacts line inside the main AOI (densified to
2 m spacing). Build two edge-strength images of the HiRISE reference over the AOI at 4 m: (a) gradient
magnitude of the orthoimage smoothed with sigma 8 m, (b) DTM slope (6 m baseline) smoothed with sigma 8 m;
each normalised to z-scores. For every trial shift (dx, dy) in [-200, 200] m at 4 m steps, score = mean edge
z-score sampled under the shifted contacts. Best shift = argmax; report it, its score, and the score at (0,0).
Peak width (score >= 90 % of the peak) is reported as the uncertainty. No shift is applied to any layer.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.enums import Resampling  # noqa: E402
from scipy.ndimage import gaussian_filter, map_coordinates  # noqa: E402
from shapely.geometry import shape  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pipeline.common import Scene  # noqa: E402

sc = Scene("jezero"); g = sc.grid; A = sc.extent("aoi")
R = 4.0
with rasterio.open(sc.work / "ortho_025.tif") as o:
    img = o.read(1, out_shape=(o.height // 16, o.width // 16), resampling=Resampling.average).astype("float32")
img[img == 0] = np.nan; img = np.where(np.isfinite(img), img, np.nanmean(img))
with rasterio.open(sc.work / "dtm_fine.tif") as d:
    z = d.read(1).astype("float32")
pad = 30; z = z[pad:-pad, pad:-pad]
gy, gx = np.gradient(gaussian_filter(z, 3.0), 1.0)
slope = np.degrees(np.arctan(np.hypot(gx, gy)))
slope = slope[: slope.shape[0] // 4 * 4, : slope.shape[1] // 4 * 4].reshape(slope.shape[0] // 4, 4, -1, 4).mean((1, 3))


def edge(a, sig_px):
    s = gaussian_filter(a, sig_px)
    gy_, gx_ = np.gradient(s)
    m = np.hypot(gx_, gy_)
    return (m - m.mean()) / m.std()


E = {"ortho_gradient": edge(img, 2.0), "dtm_slope": (lambda s: (s - s.mean()) / s.std())(gaussian_filter(slope, 2.0))}
pts = []
fc = json.load(open(APP / "data_raw/jezero/step2/sim3464/GeoContacts.geojson"))
types = {}
for f in fc["features"]:
    s = shape(f["geometry"])
    for gg in getattr(s, "geoms", [s]):
        xy = np.array(gg.coords)
        x, y = g.lonlat_to_xy(xy[:, 0], xy[:, 1])
        for i in range(len(x) - 1):
            n = max(1, int(np.hypot(x[i + 1] - x[i], y[i + 1] - y[i]) / 2))
            t = np.linspace(0, 1, n, endpoint=False)
            px = x[i] + t * (x[i + 1] - x[i]); py = y[i] + t * (y[i + 1] - y[i])
            k = (px > A[0] + 250) & (px < A[2] - 250) & (py > A[1] + 250) & (py < A[3] - 250)
            if k.any():
                pts.append(np.c_[px[k], py[k]]); types[f["properties"].get("TYPE")] = types.get(f["properties"].get("TYPE"), 0) + int(k.sum())
P = np.vstack(pts)
shifts = np.arange(-200, 201, 4.0)
out = {"method": __doc__.split("Method")[1].strip(), "n_points_2m": int(len(P)), "contact_types": types, "results": {}}
fig, axs = plt.subplots(1, 3, figsize=(18, 6))
for k, (name, e) in enumerate(E.items()):
    S = np.zeros((len(shifts), len(shifts)))
    for i, dy in enumerate(shifts):
        for j, dx in enumerate(shifts):
            c = (P[:, 0] + dx - A[0]) / R - 0.5; r = (A[3] - (P[:, 1] + dy)) / R - 0.5
            S[i, j] = map_coordinates(e, [r, c], order=1).mean()
    i, j = np.unravel_index(np.argmax(S), S.shape)
    peak = S[i, j]; z0 = S[len(shifts) // 2, len(shifts) // 2]
    w = S >= 0.9 * peak
    out["results"][name] = {"best_shift_to_add_to_SIM3464_m": [float(shifts[j]), float(shifts[i])],
                            "best_shift_magnitude_m": round(float(np.hypot(shifts[j], shifts[i])), 1),
                            "score_at_best": round(float(peak), 3), "score_at_zero": round(float(z0), 3),
                            "peak_90pct_extent_m": {"dx": [float(shifts[w.any(0)].min()), float(shifts[w.any(0)].max())],
                                                    "dy": [float(shifts[w.any(1)].min()), float(shifts[w.any(1)].max())]}}
    im = axs[k].imshow(S, extent=[shifts[0], shifts[-1], shifts[0], shifts[-1]], origin="lower", cmap="viridis")
    axs[k].plot(shifts[j], shifts[i], "r+", ms=14); axs[k].plot(0, 0, "wx")
    axs[k].set_title(f"{name}: best ({shifts[j]:+.0f} E, {shifts[i]:+.0f} N) m\nscore {peak:.2f} vs {z0:.2f} at 0"); axs[k].set_xlabel("dx (m)"); axs[k].set_ylabel("dy (m)")
    plt.colorbar(im, ax=axs[k], fraction=.046)
e = [A[0], A[2], A[1], A[3]]
axs[2].imshow(img, cmap="gray", extent=e, vmin=np.percentile(img, 1), vmax=np.percentile(img, 99))
axs[2].plot(P[:, 0], P[:, 1], "r.", ms=1, label="SIM 3464 contacts (as published)")
b = out["results"]["ortho_gradient"]["best_shift_to_add_to_SIM3464_m"]
axs[2].plot(P[:, 0] + b[0], P[:, 1] + b[1], "c.", ms=1, label=f"shifted by best ortho shift {b}")
axs[2].legend(loc="lower left", fontsize=8); axs[2].set_title("contacts used (AOI interior, 250 m inset)")
fig.suptitle("S6-1 SIM 3464 contacts vs HiRISE reference edges (score = mean edge z-score under the shifted contacts)")
fig.tight_layout(); fig.savefig(APP / "qa/jezero/S6_sim3464_offset.png", dpi=75)
(APP / "qa/jezero/S6_sim3464_offset.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out["results"], indent=1), out["n_points_2m"], types)
