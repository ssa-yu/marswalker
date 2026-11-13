"""S6 QA: positioning checks and check images (app/qa/<scene>/).

python -m pipeline.qa --scene jezero

C1 chain check   waypoint elev_geoid vs HiRISE DTM (NOT independent: same terrain model; proves our
                 coordinate chain only)
C2 track check   (independent) published traverse vs the rover's own tracks in a post-landing HiRISE image.
                 Track signal = gain in fine-scale texture energy post vs pre-landing image. The mean signal
                 along the traverse is evaluated for every trial offset (+-20 m); the peak offset is how far
                 the traverse sits from the tracks.
C3 DTM vs ortho  HiRISE hillshade vs orthoimage registration (pipeline internal consistency)
C4/C5            from alignment.json (X3)
"""
from __future__ import annotations

import argparse
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling  # noqa: E402
from scipy.ndimage import gaussian_filter, map_coordinates  # noqa: E402

from .align import norm_hp, register  # noqa: E402
from .common import Scene, log, read_json, write_json  # noqa: E402
from .grid import to_local  # noqa: E402
from .layers import SLOPE_COLORS, SLOPE_EDGES, hillshade, slope_deg  # noqa: E402

plt.rcParams.update({"font.size": 9, "figure.dpi": 110})


def read(p):
    with rasterio.open(p) as s:
        return s.read(1)


def sample(arr, extent, res, x, y, order=1):
    xmin, ymin, xmax, ymax = extent
    col = (np.asarray(x) - xmin) / res - 0.5
    row = (ymax - np.asarray(y)) / res - 0.5
    return map_coordinates(arr, [row, col], order=order, mode="constant", cval=np.nan)


def block_mean(a, f):
    H, W = a.shape[0] // f * f, a.shape[1] // f * f
    return np.nanmean(a[:H, :W].reshape(H // f, f, W // f, f), axis=(1, 3))


def run(scene: str):
    sc = Scene(scene)
    gm = read_json(sc.work / "grid.json")
    al = read_json(sc.work / "alignment.json")
    aoi = sc.extent("aoi")
    summary, out = [], {}
    ortho = read(sc.work / "ortho_025.tif").astype("float32")
    ortho[ortho == 0] = np.nan
    o1 = block_mean(ortho, 4)  # 1 m
    dtm_ext = tuple(gm["products"]["dtm_fine"]["extent_local_m"])
    zf = read(sc.work / "dtm_fine.tif")

    # ---- C3: DTM hillshade vs ortho ---------------------------------------------------------------
    pad = 30
    best = None
    for az in range(0, 360, 30):
        hs = hillshade(zf, 1.0, az, 30.0)[pad:-pad, pad:-pad]
        a, ok = norm_hp(o1, 20.0); b, okb = norm_hp(hs.astype("float32"), 20.0)
        m = ok & okb
        r = float(np.corrcoef(a[m], b[m])[0, 1])
        if best is None or r > best[0]:
            best = (r, az, a, b)
    r, az, a, b = best
    sh = register(a, b, 1.0)
    c3 = {"best_sun_azimuth_deg": az, "r_zero_shift": round(r, 3), "offset_m": [round(sh[0], 2), round(sh[1], 2)],
          "offset_mag_m": round(float(np.hypot(*sh)), 2)}
    out["C3_dtm_vs_ortho"] = c3
    summary.append({"name": "C3 HiRISE DTM vs orthoimage (pipeline consistency)", "value": f"offset {c3['offset_mag_m']} m, r {r:.2f}",
                    "pass": c3["offset_mag_m"] <= 2.0})
    log(scene, "qa", f"C3 {c3}")

    rover = (sc.work / "photos.json").exists()
    if rover:
        wps = read_json(sc.work / "waypoints_all.json")
        W = [w for w in wps if w["in_aoi"] and w["elev_geoid"] is not None]
        # ---- C1: chain check ----
        z = sample(zf, dtm_ext, 1.0, [w["x"] for w in W], [w["y"] for w in W])
        d = np.array([w["elev_geoid"] for w in W]) - z
        d = d[np.isfinite(d)]
        c1 = {"n": int(d.size), "mean_m": round(float(d.mean()), 3), "mae_m": round(float(np.abs(d).mean()), 3),
              "max_abs_m": round(float(np.abs(d).max()), 3),
              "note": "waypoint elevations were derived from the same HiRISE terrain model: proves the coordinate chain only"}
        out["C1_waypoint_elevation_chain"] = c1
        summary.append({"name": "C1 waypoint elevation vs DTM (chain only, not independent)",
                        "value": f"MAE {c1['mae_m']} m, max {c1['max_abs_m']} m, n={c1['n']}", "pass": c1["mae_m"] < 5})
        log(scene, "qa", f"C1 {c1}")

        # ---- C2: post-landing HiRISE (independent observation) ----
        post = read(sc.work / "post_landing_025.tif").astype("float32"); post[post == 0] = np.nan
        res = 0.25
        img_sol = sc.cfg["sources"]["post_landing"].get("sol_at_image", 212)

        def hpn(img, s=8.0):
            ok = np.isfinite(img); f = np.where(ok, img, np.nanmean(img))
            hp = f - gaussian_filter(f, s / res)
            sd = np.sqrt(gaussian_filter(hp ** 2, 2 * s / res))
            return np.clip(hp / np.maximum(sd, 1e-6), -4, 4).astype("float32")
        Hpost, Hpre = hpn(post), hpn(ortho)

        # C2a: the rover itself. At image time it was parked at the waypoint whose [sol, sol_next) contains img_sol.
        park = [w for w in wps if w["sol"] <= img_sol < max(w["sol_next"], w["sol"] + 1) and w["in_aoi"]]
        c2a = None
        if park:
            w = park[-1]; h = 15.0
            r0 = int((aoi[3] - (w["y"] + h)) / res); c0 = int((w["x"] - h - aoi[0]) / res); k = int(2 * h / res)
            D = gaussian_filter(Hpost[r0:r0 + k, c0:c0 + k] - Hpre[r0:r0 + k, c0:c0 + k], 2)
            i, j = np.unravel_index(np.argmax(D), D.shape)
            blob = D > 0.5 * D[i, j]
            from scipy.ndimage import label
            lab, _ = label(blob); bm = lab == lab[i, j]
            yy, xx = np.nonzero(bm)
            bx = w["x"] - h + (xx.mean() + 0.5) * res; by = w["y"] + h - (yy.mean() + 0.5) * res
            dz = (D[i, j] - np.median(D)) / (1.4826 * np.median(np.abs(D - np.median(D))))
            c2a = {"waypoint": w["id"], "waypoint_sol": w["sol"], "next_drive_sol": w["sol_next"], "image_sol": img_sol,
                   "waypoint_xy_m": [w["x"], w["y"]], "detected_rover_xy_m": [round(float(bx), 2), round(float(by), 2)],
                   "offset_m": [round(float(bx - w["x"]), 2), round(float(by - w["y"]), 2)],
                   "distance_m": round(float(np.hypot(bx - w["x"], by - w["y"])), 2), "blob_area_m2": round(float(bm.sum() * res * res), 1),
                   "contrast_robust_z": round(float(dz), 1),
                   "method": "brightest new object (post minus pre, high-pass normalised) within 15 m of the parked waypoint; blob centroid"}
            out["C2a_rover_in_hirise"] = c2a
            summary.append({"name": "C2a rover visible in 2021 HiRISE vs published waypoint (independent)",
                            "value": f"{c2a['distance_m']} m apart (waypoint {w['id']})", "pass": bool(c2a["distance_m"] <= 5)})
            log(scene, "qa", f"C2a {c2a}")
            fig, ax = plt.subplots(1, 2, figsize=(11, 5.6))
            for a_, img, t in ((ax[0], post, "HiRISE ESP_071077_1985, 2021-09-24 (registered)"), (ax[1], ortho, "pre-landing TRN basemap")):
                s_ = img[r0:r0 + k, c0:c0 + k]
                a_.imshow(s_, cmap="gray", extent=[w["x"] - h, w["x"] + h, w["y"] - h, w["y"] + h],
                          vmin=np.nanpercentile(s_, 1), vmax=np.nanpercentile(s_, 99.8))
                a_.plot(w["x"], w["y"], "+", c="#00e5ff", ms=22, mew=1.2, label=f"published waypoint {w['id']} (sol {w['sol']}-{w['sol_next']})")
                a_.plot(bx, by, "o", mfc="none", mec="#ffd166", ms=16, mew=1.2, label="detected rover (centroid)")
                a_.set_title(t); a_.set_xlabel("x east of base (m)")
            ax[0].legend(loc="lower left", fontsize=7); ax[0].set_ylabel("y north of base (m)")
            fig.suptitle(f"C2a: Perseverance parked during sols {w['sol']}-{w['sol_next']}; HiRISE saw it on sol ~{img_sol}. Offset {c2a['distance_m']} m")
            fig.tight_layout(); fig.savefig(sc.qa / "C2a_rover_in_hirise.png"); plt.close(fig)

        # C2b: traverse vs dark linear features (tracks) along the path; pre-landing image as control.
        tv = read_json(sc.work / "traverse_raw.geojson")
        pts, nrm = [], []
        for f in tv["features"]:
            if f["properties"].get("sol") is None or f["properties"]["sol"] > img_sol:
                continue
            cs = np.array([c[:2] for c in f["geometry"]["coordinates"]], float)
            x, y = sc.grid.lonlat_to_xy(cs[:, 0], cs[:, 1])
            for i in range(len(x) - 1):
                L = math.hypot(x[i + 1] - x[i], y[i + 1] - y[i])
                if L < 0.05:
                    continue
                n = max(1, int(L / 1.0)); t = np.arange(n) / n
                pts.append(np.c_[x[i] + t * (x[i + 1] - x[i]), y[i] + t * (y[i + 1] - y[i])])
                nrm.append(np.repeat([[-(y[i + 1] - y[i]) / L, (x[i + 1] - x[i]) / L]], n, 0))
        P = np.vstack(pts); N = np.vstack(nrm)
        m = (P[:, 0] > aoi[0] + 30) & (P[:, 0] < aoi[2] - 30) & (P[:, 1] > aoi[1] + 30) & (P[:, 1] < aoi[3] - 30)
        P, N = P[m], N[m]
        s_in = np.array([-1.0, -0.5, 0, 0.5, 1.0]); s_out = np.array([-6, -5, -4, -3, 3, 4, 5, 6.0])

        def band(img, dx, dy):
            X = P[:, 0] + dx; Y = P[:, 1] + dy
            g = lambda s_: sample(img, aoi, res, X + s_ * N[:, 0], Y + s_ * N[:, 1])
            return float(np.mean(np.mean([g(s_) for s_ in s_out], 0) - np.mean([g(s_) for s_ in s_in], 0)))
        offs = np.arange(-15, 15.01, 0.5)
        S = np.array([[band(Hpost, dx, dy) for dx in offs] for dy in offs])
        S0 = np.array([[band(Hpre, dx, dy) for dx in offs] for dy in offs])

        def peak(A):
            i, j = np.unravel_index(np.argmax(A), A.shape); bg = A[np.hypot(*np.meshgrid(offs, offs)) > 6]
            return float(offs[j]), float(offs[i]), float((A[i, j] - bg.mean()) / bg.std()), float(A[i, j])
        pk, pk0 = peak(S), peak(S0)
        c2b = {"traverse_points": int(len(P)), "sol_max": img_sol,
               "post_peak_offset_m": [pk[0], pk[1]], "post_peak_z": round(pk[2], 1), "post_peak_value": round(pk[3], 3),
               "control_pre_peak_offset_m": [pk0[0], pk0[1]], "control_pre_peak_z": round(pk0[2], 1), "control_pre_peak_value": round(pk0[3], 3),
               "method": "mean darkness of a 2 m band centred on the traverse vs 3-6 m to each side, both images high-pass normalised; trial offsets +-15 m",
               "reading": "the pre-landing basemap shows a weaker dark band at nearly the same offset: the rover tends to drive on darker, smoother ground, so this signal is not purely tracks"}
        out["C2b_traverse_vs_dark_band"] = c2b
        summary.append({"name": "C2b traverse vs dark band along path (post vs pre control)",
                        "value": f"post peak {np.hypot(pk[0], pk[1]):.1f} m off (z {pk[2]:.0f}); pre control {np.hypot(pk0[0], pk0[1]):.1f} m (z {pk0[2]:.0f})", "pass": None})
        log(scene, "qa", f"C2b {c2b}")
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.8))
        for a_, A, pk_, t in ((ax[0], S, pk, "2021 HiRISE (tracks present)"), (ax[1], S0, pk0, "pre-landing basemap (control)")):
            im = a_.imshow(A, extent=[offs[0], offs[-1], offs[0], offs[-1]], origin="lower", cmap="magma")
            a_.plot(pk_[0], pk_[1], "c+", ms=14, mew=2); a_.axhline(0, c="w", lw=.4); a_.axvline(0, c="w", lw=.4)
            a_.set_title(f"{t}\npeak {pk_[0]:+.1f} E {pk_[1]:+.1f} N m, z={pk_[2]:.1f}"); a_.set_xlabel("trial offset east (m)")
            plt.colorbar(im, ax=a_, fraction=.046)
        ax[0].set_ylabel("trial offset north (m)")
        fig.suptitle("C2b: dark band along the published traverse (sol <= %d) vs trial offset" % img_sol)
        fig.tight_layout(); fig.savefig(sc.qa / "C2b_traverse_dark_band.png"); plt.close(fig)
        del Hpost, Hpre

        # crops along the traverse
        idx = np.linspace(0, len(P) - 1, 8).astype(int)
        fig, axs = plt.subplots(2, 8, figsize=(22, 6.2))
        half = 40
        for k, ii in enumerate(idx):
            cx, cy = P[ii]
            for row, (img, name) in enumerate(((post, "2021-09-24 (post)"), (ortho, "TRN mosaic (pre-landing)"))):
                r0 = int((aoi[3] - (cy + half)) / 0.25); c0 = int((cx - half - aoi[0]) / 0.25)
                sub = img[max(r0, 0):r0 + int(2 * half / 0.25), max(c0, 0):c0 + int(2 * half / 0.25)]
                axs[row, k].imshow(sub, cmap="gray", extent=[cx - half, cx + half, cy - half, cy + half],
                                   vmin=np.nanpercentile(sub, 1), vmax=np.nanpercentile(sub, 99))
                mm = (np.abs(P[:, 0] - cx) < half) & (np.abs(P[:, 1] - cy) < half)
                axs[row, k].plot(P[mm, 0], P[mm, 1], ",", c="#00e5ff", alpha=.35)
                axs[row, k].set_xticks([]); axs[row, k].set_yticks([])
                if k == 0:
                    axs[row, k].set_ylabel(name)
            axs[0, k].set_title(f"x {cx:.0f}, y {cy:.0f} m", fontsize=8)
        fig.suptitle("C2 crops (80 m): traverse (cyan dots) over the 2021 HiRISE image (top) and the pre-landing basemap (bottom)")
        fig.tight_layout(); fig.savefig(sc.qa / "C2_traverse_crops.png", dpi=90); plt.close(fig)

        # waypoint/photo overview
        ph = read_json(sc.work / "photos.json")
        fig, ax = plt.subplots(figsize=(9, 9))
        ax.imshow(o1, cmap="gray", extent=[aoi[0], aoi[2], aoi[1], aoi[3]], vmin=np.nanpercentile(o1, 1), vmax=np.nanpercentile(o1, 99))
        tvx = []
        for f in tv["features"]:
            cs = np.array([c[:2] for c in f["geometry"]["coordinates"]], float)
            x, y = sc.grid.lonlat_to_xy(cs[:, 0], cs[:, 1]); ax.plot(x, y, c="#00c8ff", lw=1)
        ws = [w for w in ph["waypoints"]]
        ax.scatter([w["x"] for w in ws if not w["images"]], [w["y"] for w in ws if not w["images"]], s=10, c="#00c8ff", label="waypoint, no photo")
        ax.scatter([w["x"] for w in ws if w["images"]], [w["y"] for w in ws if w["images"]], s=22, c="#ffd166", edgecolors="k", label="waypoint with photos")
        ax.plot(0, 0, "o", ms=10, c="#e8743b", mec="w", label="base (assumed)")
        ax.set_xlim(aoi[0], aoi[2]); ax.set_ylim(aoi[1], aoi[3]); ax.legend(loc="lower left")
        ax.set_title(f"Jezero AOI: {ph['n_images']} Perseverance images at {ph['n_waypoints_with_photos']}/{ph['n_waypoints_aoi']} waypoints"); ax.set_xlabel("x east of base (m)"); ax.set_ylabel("y north (m)")
        fig.tight_layout(); fig.savefig(sc.qa / "overview_waypoints_photos.png"); plt.close(fig)
        summary.append({"name": "Ground photos located (site/drive exact match)",
                        "value": f"{ph['n_images']} images at {ph['n_waypoints_with_photos']} of {ph['n_waypoints_aoi']} AOI waypoints", "pass": None})

    # ---- C4 figure: prior registration -------------------------------------------------------------
    pr = al["prior"]["image_registration"]
    rr = pr["grid_res_m"]
    fet = sc.extent("fetch"); inner = (fet[0] + 50, fet[1] + 50, fet[2] - 50, fet[3] - 50)
    H, _ = to_local(sc.raw_path("ortho"), sc, inner, rr, Resampling.average); H[H == 0] = np.nan
    C0, _ = to_local(sc.raw_path("prior_ortho"), sc, inner, rr, Resampling.bilinear); C0[C0 <= 0] = np.nan
    C1_, _ = to_local(sc.raw_path("prior_ortho"), sc, inner, rr, Resampling.bilinear, shift_xy=tuple(al["prior"]["applied_shift_m"])); C1_[C1_ <= 0] = np.nan
    hz, _ = norm_hp(H, 60 / rr); c0z, _ = norm_hp(C0, 60 / rr); c1z, _ = norm_hp(C1_, 60 / rr)

    def checker(a, b, n=8):
        out = a.copy(); hh, ww = a.shape
        for i in range(n):
            for j in range(n):
                if (i + j) % 2:
                    out[i * hh // n:(i + 1) * hh // n, j * ww // n:(j + 1) * ww // n] = b[i * hh // n:(i + 1) * hh // n, j * ww // n:(j + 1) * ww // n]
        return out
    fig, ax = plt.subplots(1, 3, figsize=(16, 5.6))
    ext = [inner[0], inner[2], inner[1], inner[3]]
    ax[0].imshow(hz, cmap="gray", vmin=-2.5, vmax=2.5, extent=ext); ax[0].set_title(f"HiRISE ortho averaged to {rr:.0f} m (high-pass)")
    ax[1].imshow(checker(hz, c0z), cmap="gray", vmin=-2.5, vmax=2.5, extent=ext); ax[1].set_title(f"checkerboard HiRISE/CTX before shift (r={pr['r_before']})")
    ax[2].imshow(checker(hz, c1z), cmap="gray", vmin=-2.5, vmax=2.5, extent=ext)
    ax[2].set_title(f"after one global shift {pr['measured_shift_m']} m (r={pr['r_after']})\nquadrant dev {pr['quadrant_dev_m']} m")
    fig.suptitle("C4 / X3: CTX prior registered to HiRISE reference by imagery"); fig.tight_layout()
    fig.savefig(sc.qa / "C4_prior_registration.png"); plt.close(fig)

    # ---- layer comparison figure ----------------------------------------------------------------
    zp = read(sc.work / "dtm_prior_ctx.tif")
    ctx = tuple(gm["products"]["dtm_prior_ctx"]["extent_local_m"]); pres = gm["products"]["dtm_prior_ctx"]["res_m"]
    xs = np.arange(aoi[0] + 1, aoi[2], 2.0); ys = np.arange(aoi[3] - 1, aoi[1], -2.0)
    X, Y = np.meshgrid(xs, ys)
    zp2 = sample(zp, ctx, pres, X, Y)  # bilinear to 2 m (how the prior is used downstream)
    hs_p = hillshade(zp2, 2.0); hs_f = hillshade(zf, 1.0)[pad:-pad, pad:-pad]
    sf = np.load(sc.work / "slope_fine.npy"); sp = sample(np.load(sc.work / "slope_prior_ctx.npy"), ctx, pres, X, Y)
    fig, ax = plt.subplots(2, 3, figsize=(16, 10.5))
    e = [aoi[0], aoi[2], aoi[1], aoi[3]]
    ax[0, 0].imshow(hs_f, cmap="gray", extent=e); ax[0, 0].set_title("HiRISE reference hillshade (1 m DTM)")
    ax[0, 1].imshow(hs_p, cmap="gray", extent=e); ax[0, 1].set_title("CTX prior hillshade (20 m DTM, bilinear to 2 m)")
    ax[0, 2].imshow(o1, cmap="gray", extent=e, vmin=np.nanpercentile(o1, 1), vmax=np.nanpercentile(o1, 99)); ax[0, 2].set_title("HiRISE orthoimage (shown at 1 m)")
    from matplotlib.colors import BoundaryNorm, ListedColormap
    cm = ListedColormap(SLOPE_COLORS); nm = BoundaryNorm(SLOPE_EDGES, cm.N)
    ax[1, 0].imshow(sf, cmap=cm, norm=nm, extent=e); ax[1, 0].set_title("HiRISE slope (6 m baseline)")
    im = ax[1, 1].imshow(sp, cmap=cm, norm=nm, extent=e); ax[1, 1].set_title("CTX slope (40 m baseline)")
    plt.colorbar(im, ax=ax[1, 1], fraction=.046, label="deg")
    bins = np.arange(0, 41, 1)
    ax[1, 2].hist(sf[np.isfinite(sf)].ravel(), bins, alpha=.6, density=True, label="HiRISE 6 m")
    ax[1, 2].hist(sp[np.isfinite(sp)].ravel(), bins, alpha=.6, density=True, label="CTX 40 m")
    ax[1, 2].set_yscale("log"); ax[1, 2].legend(); ax[1, 2].set_xlabel("slope (deg)"); ax[1, 2].set_title("slope distribution in AOI")
    fig.suptitle(f"{sc.cfg['title']}: reference vs prior terrain (same sun, same colour bins)"); fig.tight_layout()
    fig.savefig(sc.qa / "layers_compare.png"); plt.close(fig)
    pct = {f"ref_gt{t}": round(float(np.mean(sf[np.isfinite(sf)] > t)) * 100, 2) for t in (10, 15, 20, 25)}
    pct.update({f"prior_gt{t}": round(float(np.mean(sp[np.isfinite(sp)] > t)) * 100, 2) for t in (10, 15, 20, 25)})
    out["slope_percent_area"] = pct
    summary.append({"name": "Slope > 15° share of AOI (reference vs prior)", "value": f"{pct['ref_gt15']}% vs {pct['prior_gt15']}%", "pass": None})
    write_json(sc.qa / "checks.json", {"summary": summary, "details": out, "x3": al["x3"]})
    log(scene, "qa", f"slope area %: {pct}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    run(ap.parse_args().scene)
