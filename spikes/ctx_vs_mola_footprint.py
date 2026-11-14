# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""CTX DTM vs MOLA 463 m inside the HiRISE footprint only (bias + spread), before/after the HiRISE-derived offset.
Usage: python ctx_vs_mola_footprint.py HIRISE_DTM CTX_DTM MOLA_WINDOW"""
import sys, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from scipy.ndimage import binary_erosion
H, C, M = (rasterio.open(p) for p in sys.argv[1:4])
m = M.read(1).astype(float)
def toM(src):
    o = np.full(m.shape, np.nan)
    reproject(rasterio.band(src, 1), o, src_nodata=src.nodata, dst_transform=M.transform, dst_crs=M.crs, dst_nodata=np.nan, resampling=Resampling.average)
    return o
h, c = toM(H), toM(C)
fp = binary_erosion(np.isfinite(h) & np.isfinite(c), iterations=1)
for name, g in (("HiRISE", h), ("CTX", c)):
    d = (g - m)[fp]; print(f"{name} - MOLA in HiRISE footprint: n={fp.sum()} mean {d.mean():+.2f} std {d.std():.2f} max|d| {np.abs(d).max():.1f} m")
d = (c - m)[fp] + 39.62; print(f"CTX + 39.62 m (HiRISE-derived offset) - MOLA: mean {d.mean():+.2f} std {d.std():.2f} m")
