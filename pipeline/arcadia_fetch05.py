# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Arcadia: window of the RED_A COG at overview level 1 (~0.53 m source pixels) covering the fetch extent.
python -m pipeline.arcadia_fetch05"""
import time

import rasterio
from rasterio.windows import from_bounds

from .common import Scene, log

if __name__ == "__main__":
    sc = Scene("arcadia")
    out = sc.raw / sc.source("ortho_05")["file"]
    X0, Y0, X1, Y1 = sc.grid.src_bounds(*sc.extent("fetch"))
    t0 = time.time()
    with rasterio.Env(GDAL_HTTP_MULTIRANGE="YES", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE"):
        with rasterio.open("/vsicurl/" + sc.source("ortho_05")["url"], overview_level=0) as s:
            w = from_bounds(X0, Y0, X1, Y1, s.transform).round_offsets().round_lengths()
            w = w.intersection(rasterio.windows.Window(0, 0, s.width, s.height))
            a = s.read(1, window=w)
            prof = dict(driver="GTiff", width=a.shape[1], height=a.shape[0], count=1, dtype=a.dtype, crs=s.crs,
                        transform=s.window_transform(w), nodata=0, tiled=True, compress="deflate", BIGTIFF="IF_SAFER")
    with rasterio.open(out, "w", **prof) as d:
        d.write(a, 1)
    log("arcadia", "fetch05", f"{a.shape} res {prof['transform'].a:.3f} in {time.time() - t0:.0f} s -> {out.name}")
