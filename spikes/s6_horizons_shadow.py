"""S6-6 (Q6): sun position at Jezero from JPL Horizons (saved locally) and cast-shadow fraction of the AOI.

python -I spikes/s6_horizons_shadow.py  (from app/) -> qa/jezero/S6_shadow.{png,json}
Input: data_raw/jezero/horizons/sun_azel_2026-11-15_2min.csv.txt (Horizons API, observer = coord@499 geodetic
-77.45088572 (Horizons wants east longitude negative for Mars), 18.44462715, -2.6 km; QUANTITIES=4 apparent
azimuth / elevation; date chosen arbitrarily = the day after today; table 2026-11-15 12:00 to 11-16 02:00 UTC = one daylight period).
Local true solar time is NOT a Horizons output for a Mars site (quantity 34 returns n.a.); it is derived here
from the hour angle: HA = atan2(-sin(az) cos(el), sin(el) cos(lat) - cos(el) cos(az) sin(lat)), LTST = 12 h + HA/15.
Shadow: HiRISE 1 m DTM (AOI + 30 m) averaged to 2 m; a cell is shadowed if the terrain toward the sun rises
above the sun ray within 1,500 m (cast shadow), or the surface faces away from the sun (self-shadow).
Rays that leave the DTM are treated as lit (underestimate near the AOI edge).
"""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from scipy.ndimage import shift as ndshift  # noqa: E402

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from pipeline.common import Scene  # noqa: E402

sc = Scene("jezero")
LAT = math.radians(18.44462715)
rows = []
for l in (APP / "data_raw/jezero/horizons/sun_azel_2026-11-15_2min.csv.txt").read_text().split("$$SOE")[1].split("$$EOE")[0].strip().splitlines():
    p = [s.strip() for s in l.split(",")]
    rows.append((p[0], float(p[3]), float(p[4])))
az = np.radians([r[1] for r in rows]); el = np.radians([r[2] for r in rows])
HA = np.degrees(np.arctan2(-np.sin(az) * np.cos(el), np.sin(el) * np.cos(LAT) - np.cos(el) * np.cos(az) * np.sin(LAT)))
ltst = (12 + HA / 15) % 24
with rasterio.open(sc.work / "dtm_fine.tif") as s:
    z = s.read(1).astype("float32")
z = z[: z.shape[0] // 2 * 2, : z.shape[1] // 2 * 2].reshape(z.shape[0] // 2, 2, -1, 2).mean((1, 3))
R = 2.0; pad = 15  # 30 m pad in 2 m cells
gy, gx = np.gradient(z, R)  # gy: d/drow (south), gx: d/dcol (east)
nrm = np.dstack([-gx, gy, np.ones_like(z)]); nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)  # (east, north, up)


def shadow(azd, eld):
    a = math.radians(azd); e = math.radians(eld)
    sx, sy = math.sin(a), math.cos(a)  # sun direction east, north
    sun = np.array([sx * math.cos(e), sy * math.cos(e), math.sin(e)])
    self_sh = (nrm @ sun) <= 0
    cast = np.zeros(z.shape, bool)
    t = math.tan(e)
    for d in np.arange(R, 1500 + R, R):
        # terrain at distance d toward the sun: row - d*sy/R, col + d*sx/R
        zz = ndshift(z, (d * sy / R, -d * sx / R), order=1, cval=-1e9, prefilter=False)
        cast |= zz > z + d * t
        if d * t > 200:  # higher than any relief in this window
            break
    sh = (cast | self_sh)[pad:-pad, pad:-pad]
    return float(sh.mean()), float(self_sh[pad:-pad, pad:-pad].mean()), sh


sel = []
day = el > 0
idx = np.nonzero(day)[0]
im = idx[np.argmax(el[idx])]
for target in (2, 5, 10, 20, 30):
    i = idx[np.argmax(el[idx] >= math.radians(target))]; sel.append(("morning", target, i))
sel.append(("max", None, im))
for target in (30, 20, 10, 5, 2):
    j = idx[::-1][np.argmax(el[idx[::-1]] >= math.radians(target))]; sel.append(("evening", target, j))
assert all(i < im for w, _, i in sel if w == "morning") and all(i > im for w, _, i in sel if w == "evening")
out = {"source": "JPL Horizons API (observer table, Sun, coord@499, -77.45088572 / 18.44462715 / -2.6 km), 2026-11-15 12:00 to 11-16 02:00 UTC, 2-min step",
       "lon_convention": "verified: Horizons states 'Input east-longitude as negative for IAU west-positive body #499'; with -77.45 the Sun elevation at 2021-03-02 00:31 UTC = 76.22 deg vs SuperCam telemetry solar_el 76.02 deg (sol 11, masterlist)",
       "ltst": "derived from hour angle (not a Horizons output for Mars sites)", "cases": []}
fig, axs = plt.subplots(2, 6, figsize=(24, 8.5)); axs = axs.ravel()
for k, (when, tgt, i) in enumerate(sel):
    f, fs, sh = shadow(math.degrees(az[i]), math.degrees(el[i]))
    out["cases"].append({"when": when, "utc": rows[i][0], "ltst_h": round(float(ltst[i]), 2), "sun_az_deg": round(float(np.degrees(az[i])), 1),
                         "sun_el_deg": round(float(np.degrees(el[i])), 1), "shadow_frac_aoi": round(f, 4), "self_shadow_frac": round(fs, 4)})
    a = axs[k]; a.imshow(sh, cmap="gray_r", vmin=0, vmax=1.5); a.set_xticks([]); a.set_yticks([])
    a.set_title(f"{when} LTST {ltst[i]:.2f} h\nsun el {np.degrees(el[i]):.0f}° az {np.degrees(az[i]):.0f}° · shadow {f*100:.1f}%", fontsize=9)
    print(out["cases"][-1])
axs[-1].plot(ltst[day], np.degrees(el[day]), ".", ms=2); axs[-1].set_xlabel("LTST (h)"); axs[-1].set_ylabel("sun elevation (deg)")
fig.suptitle("S6-6 shadow in the AOI (black = shadow: cast + self) from the HiRISE DTM, sun from JPL Horizons (2026-11-15)")
fig.tight_layout(); fig.savefig(APP / "qa/jezero/S6_shadow.png", dpi=60)
rs = (APP / "data_raw/jezero/horizons/sun_rise_set_2026-11-15.txt").read_text().split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
out["rise_set_transit_utc"] = [l.strip() for l in rs]
(APP / "qa/jezero/S6_shadow.json").write_text(json.dumps(out, indent=1))
