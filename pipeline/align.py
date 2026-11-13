"""S3 align: registration shifts and the locked X3 positioning check.

python -m pipeline.align --scene jezero

X3 (locked by manager 2026-11-14, applies to every scene/AOI, not relaxed on failure):
  1. prior vs reference: exactly one global horizontal shift (from IMAGE registration only) and one
     global vertical offset, both recorded;
  2. after the shift, each of 4 quadrants registers within 20 m of the global shift;
  3. reference vs MOLA 463 m: |mean| <= 10 m and std <= 10 m;
  4. shifted prior vs MOLA: std <= 10 m.
Also: post-landing HiRISE image -> reference ortho (one global shift on terrain texture), used by the
independent rover-track check in qa.py.
All grids are local (base-centred) metres; shifts are (dx east, dy north) in metres.
"""
from __future__ import annotations

import argparse

import numpy as np
from rasterio.warp import Resampling
from scipy.ndimage import binary_erosion, gaussian_filter
from skimage.registration import phase_cross_correlation

from .common import Scene, log, write_json
from .grid import to_local

X3 = {"quadrant_dev_max_m": 20.0, "ref_mola_abs_mean_max_m": 10.0, "ref_mola_std_max_m": 10.0,
      "prior_mola_std_max_m": 10.0}


def norm_hp(a, sigma_px):
    """High-pass + local contrast normalisation; NaN -> 0 with mask returned."""
    ok = np.isfinite(a)
    f = np.where(ok, a, 0.0)
    w = gaussian_filter(ok.astype("float32"), sigma_px)
    lo = gaussian_filter(f, sigma_px) / np.maximum(w, 1e-6)
    hp = np.where(ok, a - lo, 0.0)
    sd = np.sqrt(gaussian_filter(hp ** 2, sigma_px * 2) / np.maximum(gaussian_filter(ok.astype("float32"), sigma_px * 2), 1e-6))
    z = np.where(ok, hp / np.maximum(sd, 1e-6), 0.0)
    return np.clip(z, -4, 4).astype("float32"), ok


def register(ref, mov, res, mask=None, upsample=20):
    """Shift (dx, dy) in metres to ADD to the moving image's georeference so it matches ref."""
    m = mask if mask is not None else np.ones(ref.shape, bool)
    s, err, _ = phase_cross_correlation(ref, mov, upsample_factor=upsample, reference_mask=m, moving_mask=m) \
        if mask is not None else phase_cross_correlation(ref, mov, upsample_factor=upsample)
    drow, dcol = float(s[0]), float(s[1])
    return (dcol * res, -drow * res)


def corr_at(ref, mov, ok):
    v = ok & (ref != 0) & (mov != 0)
    return float(np.corrcoef(ref[v], mov[v])[0, 1]) if v.sum() > 100 else float("nan")


def quadrants(ref, mov, res):
    ny, nx = ref.shape
    out = []
    for r0, r1, c0, c1 in [(0, ny // 2, 0, nx // 2), (0, ny // 2, nx // 2, nx), (ny // 2, ny, 0, nx // 2), (ny // 2, ny, nx // 2, nx)]:
        out.append(register(ref[r0:r1, c0:c1], mov[r0:r1, c0:c1], res))
    return out


def run(scene: str):
    sc = Scene(scene)
    out = {"x3_thresholds": X3, "method": "phase correlation of high-pass, contrast-normalised images (skimage)"}
    aoi = sc.extent("aoi")
    fet = sc.extent("fetch")
    inner = (fet[0] + 50, fet[1] + 50, fet[2] - 50, fet[3] - 50)

    # ---- C4: prior (CTX) vs reference (HiRISE) by imagery -------------------------------------------
    rr = sc.cfg["grid"].get("prior_ortho_res_m", 6.0)
    H, _ = to_local(sc.raw_path("ortho"), sc, inner, rr, Resampling.average)
    H[H == 0] = np.nan
    C, _ = to_local(sc.raw_path("prior_ortho"), sc, inner, rr, Resampling.bilinear)
    C[C <= 0] = np.nan
    sig = 60.0 / rr
    hz, hok = norm_hp(H, sig); cz, cok = norm_hp(C, sig)
    ok = hok & cok
    r0 = corr_at(hz, cz, ok)
    sh = register(hz, cz, rr)
    C2, _ = to_local(sc.raw_path("prior_ortho"), sc, inner, rr, Resampling.bilinear, shift_xy=sh)
    C2[C2 <= 0] = np.nan
    cz2, cok2 = norm_hp(C2, sig)
    r1 = corr_at(hz, cz2, hok & cok2)
    resid = register(hz, cz2, rr)
    q = quadrants(hz, cz2, rr)
    qdev = [float(np.hypot(a, b)) for a, b in q]
    log(scene, "align", f"prior shift {sh[0]:+.1f},{sh[1]:+.1f} m (|{np.hypot(*sh):.1f}| m); r {r0:.3f}->{r1:.3f}; "
                        f"residual {resid[0]:+.1f},{resid[1]:+.1f}; quadrant dev {np.round(qdev, 1)} m")

    # DTM-based cross-check (not applied; manager rule: shift comes from imagery only)
    dres = 10.0
    Hd, _ = to_local(sc.raw_path("dtm_fine"), sc, inner, dres, Resampling.average)
    Cd, _ = to_local(sc.raw_path("dtm_prior"), sc, inner, dres, Resampling.bilinear)
    hdz, _ = norm_hp(gaussian_filter(np.nan_to_num(Hd, nan=np.nanmean(Hd)), 2.0), 300 / dres)
    cdz, _ = norm_hp(np.nan_to_num(Cd, nan=np.nanmean(Cd)), 300 / dres)
    sh_dtm = register(hdz, cdz, dres)

    # vertical offset (prior shifted) on the prior's own grid
    pres = sc.cfg["grid"].get("prior_res_m", 20.0)
    Hp, _ = to_local(sc.raw_path("dtm_fine"), sc, inner, pres, Resampling.average)
    Cp, _ = to_local(sc.raw_path("dtm_prior"), sc, inner, pres, Resampling.bilinear, shift_xy=sh)
    d = (Cp - Hp)[np.isfinite(Cp) & np.isfinite(Hp)]
    dz_med = float(np.median(d))
    nmad = float(1.4826 * np.median(np.abs(d - dz_med)))
    out["prior"] = {
        "image_registration": {"grid_res_m": rr, "measured_shift_m": [round(sh[0], 2), round(sh[1], 2)],
                               "shift_magnitude_m": round(float(np.hypot(*sh)), 2),
                               "r_before": round(r0, 3), "r_after": round(r1, 3),
                               "residual_after_shift_m": [round(resid[0], 2), round(resid[1], 2)],
                               "quadrant_shift_after_m": [[round(a, 2), round(b, 2)] for a, b in q],
                               "quadrant_dev_m": [round(v, 2) for v in qdev]},
        "dtm_crosscheck_shift_m": [round(sh_dtm[0], 2), round(sh_dtm[1], 2)],
        "vertical": {"prior_minus_ref_median_m": round(dz_med, 2), "nmad_m": round(nmad, 2), "n": int(d.size)},
        "applied_shift_m": [round(sh[0], 2), round(sh[1], 2)],
        "applied_vertical_offset_m": round(-dz_med, 2),
    }

    # ---- C5: MOLA ----------------------------------------------------------------------------------
    import rasterio
    with rasterio.open(sc.raw_path("mola")) as M:
        mola = M.read(1).astype("float64"); mtr = M.transform; mnd = M.nodata
    mola[mola == mnd] = np.nan
    from rasterio.warp import reproject
    from affine import Affine

    def to_mola(path, shift=(0.0, 0.0), dz=0.0):
        with rasterio.open(path) as S:
            a = S.read(1, masked=True).astype("float64").filled(np.nan); a[(a < -1e30) | (a > 1e30)] = np.nan
            tr = S.transform
            if shift != (0.0, 0.0):
                tr = Affine(tr.a, tr.b, tr.c + shift[0] / sc.grid.k, tr.d, tr.e, tr.f + shift[1])
            o = np.full(mola.shape, np.nan)
            reproject(a, o, src_transform=tr, src_crs=S.crs, src_nodata=np.nan, dst_transform=mtr, dst_crs=S.crs,
                      dst_nodata=np.nan, resampling=Resampling.average)
            # keep cells fully covered
            cov = np.full(mola.shape, np.nan)
            reproject(np.isfinite(a).astype("float64"), cov, src_transform=tr, src_crs=S.crs, dst_transform=mtr,
                      dst_crs=S.crs, dst_nodata=np.nan, resampling=Resampling.average)
            o[~(cov > 0.98)] = np.nan
            return o + dz

    def stats(g):
        m = np.isfinite(g) & np.isfinite(mola)
        m = binary_erosion(m, iterations=1) if m.sum() > 50 else m
        d = (g - mola)[m]
        return {"n_cells": int(d.size), "mean_m": round(float(d.mean()), 2), "std_m": round(float(d.std()), 2),
                "max_abs_m": round(float(np.abs(d).max()), 2)}
    ref_m = stats(to_mola(sc.raw_path("dtm_fine")))
    pri_m = stats(to_mola(sc.raw_path("dtm_prior"), sh, -dz_med))
    # Diagnostic only (does NOT change the X3 verdict): is the residual driven by a horizontal offset of
    # the MOLA gridded mosaic? Slide the MOLA grid by +-3 cells against the shifted prior.
    with rasterio.open(sc.raw_path("dtm_prior")) as S:
        pa = S.read(1, masked=True).astype("float64").filled(np.nan); pa[(pa < -1e30) | (pa > 1e30)] = np.nan
        ptr = Affine(S.transform.a, 0, S.transform.c + sh[0] / sc.grid.k, 0, S.transform.e, S.transform.f + sh[1])
        pcrs = S.crs
    diag = []
    for ddx in np.arange(-3, 3.01, 0.25):
        for ddy in np.arange(-3, 3.01, 0.25):
            t2 = Affine(mtr.a, 0, mtr.c + ddx * mtr.a, 0, mtr.e, mtr.f + ddy * mtr.e)
            o = np.full(mola.shape, np.nan)
            reproject(pa, o, src_transform=ptr, src_crs=pcrs, src_nodata=np.nan, dst_transform=t2, dst_crs=pcrs,
                      dst_nodata=np.nan, resampling=Resampling.average)
            dd = o - dz_med - mola; k = np.isfinite(dd); k[[0, -1], :] = False; k[:, [0, -1]] = False
            diag.append((float(dd[k].std()), float(ddx), float(ddy), float(dd[k].mean())))
    diag.sort()
    b = diag[0]
    gy, gx = np.gradient(mola, mtr.a)
    msl = np.degrees(np.arctan(np.hypot(gx, gy)))
    o = to_mola(sc.raw_path("dtm_prior"), sh, -dz_med); k = np.isfinite(o) & np.isfinite(mola) & (msl < 2)
    out["mola"] = {"reference_minus_mola": ref_m, "shifted_prior_minus_mola": pri_m,
                   "note": "MOLA 463 m cells fully covered by the product, interior cells only",
                   "diagnostic_not_used_for_verdict": {
                       "best_mola_grid_offset_m": [round(b[1] * mtr.a * sc.grid.k, 0), round(-b[2] * mtr.a, 0)],
                       "prior_minus_mola_at_best_offset": {"mean_m": round(b[3], 2), "std_m": round(b[0], 2)},
                       "prior_minus_mola_gentle_cells_lt2deg": {"n": int(k.sum()), "mean_m": round(float((o - mola)[k].mean()), 2) if k.any() else None,
                                                                "std_m": round(float((o - mola)[k].std()), 2) if k.any() else None}}}
    log(scene, "align", f"MOLA: ref {ref_m}; prior {pri_m}")

    # ---- X3 verdict ---------------------------------------------------------------------------------
    checks = {
        "1_single_global_shift_recorded": True,
        "2_quadrants_within_20m": bool(max(qdev) <= X3["quadrant_dev_max_m"]),
        "3_ref_vs_mola": bool(abs(ref_m["mean_m"]) <= X3["ref_mola_abs_mean_max_m"] and ref_m["std_m"] <= X3["ref_mola_std_max_m"]),
        "4_prior_vs_mola_std": bool(pri_m["std_m"] <= X3["prior_mola_std_max_m"]),
    }
    out["x3"] = {"checks": checks, "pass": all(checks.values())}
    log(scene, "align", f"X3 {'PASS' if out['x3']['pass'] else 'FAIL'} {checks}")

    # ---- post-landing image -> reference ortho ------------------------------------------------------
    if "post_landing" in sc.cfg["sources"]:
        pr = 1.0
        A, _ = to_local(sc.raw_path("ortho"), sc, aoi, pr, Resampling.average); A[A == 0] = np.nan
        B, _ = to_local(sc.raw_path("post_landing"), sc, aoi, pr, Resampling.average); B[B == 0] = np.nan
        az, aok = norm_hp(A, 15.0); bz, bok = norm_hp(B, 15.0)
        r_0 = corr_at(az, bz, aok & bok)
        s1 = register(az, bz, pr)
        B2, _ = to_local(sc.raw_path("post_landing"), sc, aoi, pr, Resampling.average, shift_xy=s1); B2[B2 == 0] = np.nan
        bz2, bok2 = norm_hp(B2, 15.0)
        r_1 = corr_at(az, bz2, aok & bok2)
        res2 = register(az, bz2, pr)
        qp = quadrants(az, bz2, pr)
        shp = (s1[0] + res2[0], s1[1] + res2[1])
        out["post_landing"] = {"grid_res_m": pr, "measured_shift_m": [round(shp[0], 2), round(shp[1], 2)],
                               "r_before": round(r_0, 3), "r_after": round(r_1, 3),
                               "quadrant_shift_after_m": [[round(a, 2), round(b, 2)] for a, b in qp],
                               "applied_shift_m": [round(shp[0], 2), round(shp[1], 2)],
                               "note": "terrain texture only; the rover traverse is not used to estimate this shift"}
        log(scene, "align", f"post-landing shift {shp[0]:+.1f},{shp[1]:+.1f} m; r {r_0:.3f}->{r_1:.3f}; quadrants {qp}")
    write_json(sc.work / "alignment.json", out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    run(ap.parse_args().scene)
