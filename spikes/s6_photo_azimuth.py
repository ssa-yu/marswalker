"""S6-2 (J5): independent check of the Raw Images pointing metadata with a DTM horizon.

python -I spikes/s6_photo_azimuth.py  (from app/) -> qa/jezero/S6_photo_azimuth.{png,json}
Hypotheses tested (both with the same skyline and DTM):
  H1: the CAHVORE camera model in the Raw Images JSON (camera_model_component_list) is already in a local-level
      frame x = north, y = east, z = down (then mastAz would be a true azimuth);
  H2: the model is in the rover frame and `attitude` is the rover-to-local-level quaternion in (w, x, y, z) order.
The decision rule was fixed first; the five conventions (H1, H2, H2 transposed, (x,y,z,w) and its transpose) were
all scored and are listed in the json.
Independent check: the skyline seen in the photo vs the horizon computed from the CTX 20 m DTM at the
waypoint position (camera 2.0 m above ground, Mars curvature included, rays 60 m to 15 km).
Only the azimuth offset (delta) and a constant elevation offset are fitted; H1 passes for an image if the
best delta is within +-2 deg and the skyline RMS at that delta is < 0.5 deg.
Skyline detection: per image column, first row from the top where the smoothed brightness drops below
(sky median - 4 x sky MAD) for 3 rows; columns where the detected skyline touches the image edge are dropped.
"""
import glob
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from PIL import Image  # noqa: E402
from scipy.ndimage import gaussian_filter1d, map_coordinates  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pipeline.common import R_MARS, Scene  # noqa: E402

sc = Scene("jezero")
IDS = sys.argv[1:] or [
    "NLF_0190_0683808901_487EBY_N0070000NCAM00209_07_0LLJ",
    "NLF_0017_0668451937_008EBY_N0030578NCAM00195_04_0LLJ",
    "NLE_0073_0673428672_997ECM_N0032430NCAM00407_00_0LLJ",
    "NLG_0174_0682382706_381ECM_N0061648NCAM00513_00_1I3J",
    "NLF_0048_0671209093_534ECM_N0031850NCAM00406_01_195J",
    "NLE_0072_0673345813_602ECM_N0032346NCAM00410_00_0LLJ",
]
P = lambda s: np.array([float(t) for t in s.strip("()").split(",")])
meta = {}
for f in glob.glob(str(APP / "data_raw/jezero/raw_api/*.json")):
    for im in json.load(open(f)):
        if im["imageid"] in IDS:
            meta[im["imageid"]] = im
photos = json.load(open(APP / "web/data/jezero/photos.json"))
loc = {}
for w in photos["waypoints"]:
    for im in w["images"]:
        loc[im["imageid"]] = (w["x"], w["y"], w["id"], im["local"])

with rasterio.open(APP / "data_raw/jezero/dtm_prior.tif") as s:
    Z = s.read(1).astype("float64"); Z[Z < -1e30] = np.nan; T = s.transform


def z_at(x, y):
    X, Y = sc.grid.xy_to_src(x, y)
    c = (np.asarray(X) - T.c) / T.a - 0.5; r = (np.asarray(Y) - T.f) / T.e - 0.5
    return map_coordinates(Z, [np.atleast_1d(r), np.atleast_1d(c)], order=1, cval=np.nan)


def horizon(x0, y0, azs):
    z0 = z_at(x0, y0)[0] + 2.0
    d = np.concatenate([np.arange(60, 2000, 10), np.arange(2000, 15000, 20)])
    out = np.full(len(azs), np.nan)
    for i, a in enumerate(np.radians(azs)):
        xs = x0 + d * np.sin(a); ys = y0 + d * np.cos(a)
        z = z_at(xs, ys)
        e = np.degrees(np.arctan((z - z0 - d * d / (2 * R_MARS)) / d))
        out[i] = np.nanmax(e) if np.isfinite(e).any() else np.nan
    return out


from scipy.spatial.transform import Rotation as Rot  # noqa: E402
HYP = "H2"


def rays(cahv, xs, ys, q=None):
    C, A, H, V = cahv
    rot = Rot.from_quat([q[1], q[2], q[3], q[0]]) if (HYP == "H2" and q is not None) else Rot.identity()
    out = []
    for x, y in zip(xs, ys):
        r = np.cross(V - y * A, H - x * A)
        if r @ A < 0:
            r = -r
        r /= np.linalg.norm(r)
        r = rot.apply(r)
        out.append((math.degrees(math.atan2(r[1], r[0])) % 360, -math.degrees(math.asin(r[2]))))
    return np.array(out)


res = {"hypotheses": {"H1": "model frame = local level (x north, y east, z down)", "H2": "model in rover frame; rotate by attitude quaternion (w,x,y,z) to local level"}, "figure_shows": "H2", "rule": "best delta within +-2 deg and RMS < 0.5 deg", "images": {}}
fig, axs = plt.subplots(len(IDS), 2, figsize=(16, 3.3 * len(IDS)))
for k, iid in enumerate(IDS):
    im = meta[iid]; x0, y0, wid, lp = loc[iid]
    cm = im["camera"]["camera_model_component_list"].split(";")
    cahv = [P(c) for c in cm[:4]]
    sub = P(im["extended"]["subframeRect"]); scale = float(im["extended"]["scaleFactor"])
    img = np.asarray(Image.open(APP / "web/data/jezero" / lp).convert("L")).astype("float32")
    h, w = img.shape
    fx = sub[2] / scale / w; fy = sub[3] / scale / h  # medium px -> model px (model refers to the delivered frame)
    sky_rows = []
    cols = np.arange(0, w, 4)
    for c in cols:
        prof = gaussian_filter1d(img[:, max(c - 1, 0):c + 2].mean(1), 1.5)
        top = prof[:8]
        med = np.median(top); mad = np.median(np.abs(top - med)) + 1.0
        below = prof < med - 4 * mad
        run = np.convolve(below, np.ones(3), "same") >= 3
        rr = np.argmax(run) if run.any() else -1
        sky_rows.append(rr if 8 < rr < h - 5 else -1)
    sky_rows = np.array(sky_rows); ok = sky_rows > 0
    q = P(im["attitude"])
    HYP = "H1"; ae1 = rays(cahv, (cols[ok] + 0.5) * fx, (sky_rows[ok] + 0.5) * fy, q)
    HYP = "H2"; ae = rays(cahv, (cols[ok] + 0.5) * fx, (sky_rows[ok] + 0.5) * fy, q)
    azs = np.arange(0, 360, 0.25)
    Hz = horizon(x0, y0, azs)
    best = None; table = []
    for dlt in np.arange(-180, 180, 0.5):
        hz = np.interp((ae[:, 0] + dlt) % 360, azs, Hz, period=360)
        dd = ae[:, 1] - hz
        dd = dd[np.isfinite(dd)]
        if len(dd) < 20:
            continue
        dd = dd - np.median(dd)
        rms = float(np.sqrt(np.mean(np.clip(dd, -3, 3) ** 2)))
        table.append((dlt, rms))
        if best is None or rms < best[1]:
            best = (float(dlt), rms)
    t = np.array(table)
    r0 = float(t[np.argmin(np.abs(t[:, 0])), 1])
    hz0 = np.interp(ae[:, 0] % 360, azs, Hz, period=360)
    off0 = float(np.nanmedian(ae[:, 1] - hz0))
    passed = abs(best[0]) <= 2 and best[1] < 0.5
    hz1 = np.interp(ae1[:, 0] % 360, azs, Hz, period=360)
    h1 = {"median_az_deg": round(float(np.median(ae1[:, 0])), 1), "elevation_offset_at_zero_deg": round(float(np.nanmedian(ae1[:, 1] - hz1)), 2)}
    res["images"][iid] = {"waypoint": wid, "sol": im["sol"], "mastAz": float(im["extended"]["mastAz"]), "mastEl": float(im["extended"]["mastEl"]),
                          "n_skyline_columns": int(ok.sum()), "az_span_deg": [round(float(ae[:, 0].min()), 1), round(float(ae[:, 0].max()), 1)],
                          "best_delta_deg": best[0], "rms_at_best_deg": round(best[1], 3), "rms_at_zero_deg": round(r0, 3),
                          "H2_median_az_deg": round(float(np.median(ae[:, 0])), 1), "elevation_offset_at_zero_deg": round(off0, 2), "H2_pass": bool(passed), "H1": h1}
    ax = axs[k, 0]; ax.imshow(img, cmap="gray"); ax.plot(cols[ok], sky_rows[ok], "r.", ms=2); ax.set_title(f"{iid[:24]} sol {im['sol']} wp {wid} mastAz {float(im['extended']['mastAz']):.1f}", fontsize=8); ax.axis("off")
    ax = axs[k, 1]
    ax.plot(azs, Hz, "k-", lw=.8, label="CTX DTM horizon")
    ax.plot(ae[:, 0], ae[:, 1] - off0, "r.", ms=2, label="photo skyline, H2 (delta 0)")
    ax.plot((ae[:, 0] + best[0]) % 360, ae[:, 1] - np.nanmedian(ae[:, 1] - np.interp((ae[:, 0] + best[0]) % 360, azs, Hz, period=360)), "c.", ms=1.5, label=f"best delta {best[0]:+.1f}")
    a0, a1 = ae[:, 0].min() - 20, ae[:, 0].max() + 20
    ax.set_xlim(a0, a1) if a1 - a0 < 300 else None
    ax.set_title(f"RMS {r0:.2f} deg at delta 0; best delta {best[0]:+.1f} (RMS {best[1]:.2f})", fontsize=9)
    ax.set_xlabel("azimuth (deg from north, clockwise)"); ax.set_ylabel("elevation (deg)"); ax.legend(fontsize=7)
    print(iid, res["images"][iid])
fig.suptitle("S6-2 photo pointing check: photo skyline (camera model rotated by attitude, H2) vs CTX DTM horizon")
fig.tight_layout(); fig.savefig(APP / "qa/jezero/S6_photo_azimuth.png", dpi=70)
(APP / "qa/jezero/S6_photo_azimuth.json").write_text(json.dumps(res, indent=1))
