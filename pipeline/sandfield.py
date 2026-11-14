# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""S1 sand-field indicator, version 2 (round 5). Status: proposed, review pending.

Version 1 (ripple index >= P90) outlined only the bright crests of the large ripples (TARs); the
troughs between them, and fields of fine ripples (wavelength 2-3 m), stayed "firm". Version 2 asks a
different question: is this patch of ground, over a window of tens of metres, covered by a field of
parallel ripples (either the fine 2-3 m ripples or the large 6-25 m ripples/TARs)?

Image: HiRISE orthoimage averaged to 0.5 m, divided by its 25 m local mean (scale-free contrast).
For each of two wavelength bands (difference of Gaussians):
    fine   band: sigma 0.5 m - 1.5 m  (passes roughly 2-6 m wavelengths: fine ripples)
    coarse band: sigma 1.5 m - 5.0 m  (passes roughly 6-25 m wavelengths: large ripples / TARs)
  coherence C = orientation coherence of the band image's structure tensor, integrated with a
                Gaussian window (fine 6 m, coarse 12 m sigma). 0 = no preferred direction, 1 = parallel lines.
  energy    E = RMS of the band image in the same window (relative contrast; fixed numbers).
A cell is a ripple field in a band if C >= C_thr and E >= E_thr of that band.
sand_field = fine OR coarse; then (2 m grid) closing + opening with a disc, holes smaller than
min_hole_m2 filled, patches smaller than min_patch_m2 dropped, slope < 15 deg.
All thresholds are FIXED NUMBERS (direction.md: no percentiles). They were set by looking at a
development set of image crops drawn with a different seed from the check figure (see DATA_LOG).
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import (binary_closing, binary_fill_holes, binary_opening, gaussian_filter, label,
                           sobel)

SAND_V2 = {
    "version": 2,
    "image_res_m": 0.5,
    "norm_sigma_m": 25.0,
    "fine_dog_m": [0.5, 1.5], "fine_window_sigma_m": 6.0,
    "coarse_dog_m": [1.5, 5.0], "coarse_window_sigma_m": 12.0,
    "fine_coh_min": 0.45, "fine_energy_min": 0.040,
    "coarse_coh_min": 0.50, "coarse_energy_min": 0.050,
    "morph_radius_m": 4.0,
    "min_hole_m2": 400.0,
    "min_patch_m2": 400.0,
    "slope_max_deg": 15.0,
}


def _disc(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def block_mean(a, f):
    H, W = a.shape[0] // f * f, a.shape[1] // f * f
    return a[:H, :W].reshape(H // f, f, W // f, f).mean(axis=(1, 3))


def band_features(img, res, dog, win):
    """Return (coherence, energy) of one DoG band; img is contrast-normalised, finite."""
    b = gaussian_filter(img, dog[0] / res) - gaussian_filter(img, dog[1] / res)
    gx = sobel(b, 1) / 8.0; gy = sobel(b, 0) / 8.0
    s = win / res
    jxx = gaussian_filter(gx * gx, s); jyy = gaussian_filter(gy * gy, s); jxy = gaussian_filter(gx * gy, s)
    tr = jxx + jyy
    coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (tr + 1e-12)
    en = np.sqrt(gaussian_filter(b * b, s))
    return coh.astype("float32"), en.astype("float32")


def features(ortho05, P=SAND_V2):
    """ortho05: 0.5 m image (NaN = no data). Returns dict of 0.5 m feature arrays."""
    res = P["image_res_m"]
    ok = np.isfinite(ortho05) & (ortho05 > 0)
    f = np.where(ok, ortho05, np.nanmean(ortho05[ok]))
    img = f / np.maximum(gaussian_filter(f, P["norm_sigma_m"] / res), 1e-3) - 1.0
    cf, ef = band_features(img, res, P["fine_dog_m"], P["fine_window_sigma_m"])
    cc, ec = band_features(img, res, P["coarse_dog_m"], P["coarse_window_sigma_m"])
    return {"fine_coh": cf, "fine_en": ef, "coarse_coh": cc, "coarse_en": ec, "ok": ok}


def to_grid(F, factor):
    return {k: block_mean(v.astype("float32"), factor) for k, v in F.items()}


def classify(G, slope, res, P=SAND_V2):
    """G: features on the planning grid (res m). Returns (sand bool, parts dict)."""
    fine = (G["fine_coh"] >= P["fine_coh_min"]) & (G["fine_en"] >= P["fine_energy_min"])
    coarse = (G["coarse_coh"] >= P["coarse_coh_min"]) & (G["coarse_en"] >= P["coarse_energy_min"])
    raw = fine | coarse
    r = max(1, int(round(P["morph_radius_m"] / res)))
    d = _disc(r)
    m = binary_opening(binary_closing(raw, d), d)
    # fill small holes
    holes = binary_fill_holes(m) & ~m
    lab, n = label(holes)
    if n:
        sz = np.bincount(lab.ravel()) * res * res
        small = sz < P["min_hole_m2"]; small[0] = False
        m |= small[lab]
    lab, n = label(m)
    if n:
        sz = np.bincount(lab.ravel()) * res * res
        keep = sz >= P["min_patch_m2"]; keep[0] = False
        m = keep[lab]
    m &= slope < P["slope_max_deg"]
    return m, {"fine": fine, "coarse": coarse, "raw": raw}
