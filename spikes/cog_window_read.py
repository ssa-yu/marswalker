# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Time a windowed /vsicurl read of a remote GeoTIFF; save window as local GeoTIFF.
Usage: python cog_window_read.py URL OUT.tif --center-lonlat LON LAT --size-m 2400 [--threads]
       python cog_window_read.py URL --info"""
import argparse, math, os, time
p = argparse.ArgumentParser()
p.add_argument("url"); p.add_argument("out", nargs="?")
p.add_argument("--center-lonlat", nargs=2, type=float)
p.add_argument("--size-m", type=float, default=2400)
p.add_argument("--threads", action="store_true")
p.add_argument("--info", action="store_true")
a = p.parse_args()
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  GDAL_HTTP_MULTIRANGE="YES", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE",
                  CPL_VSIL_CURL_CACHE_SIZE="200000000", GDAL_HTTP_MAX_RETRY="3")
if a.threads: os.environ["GDAL_NUM_THREADS"] = "ALL_CPUS"
import rasterio
from rasterio.windows import from_bounds
t0 = time.time()
with rasterio.open("/vsicurl/" + a.url) as src:
    t1 = time.time()
    tags = src.tags(ns="IMAGE_STRUCTURE")
    print(f"open {t1-t0:.1f}s size {src.width}x{src.height} dtype {src.dtypes[0]} block {src.block_shapes[0]} overviews {src.overviews(1)} layout {tags.get('LAYOUT')} comp {src.compression} res {src.res}")
    print("crs:", src.crs.to_proj4() if src.crs else None)
    print("bounds:", src.bounds)
    if a.info: raise SystemExit
    R = 3396190.0
    if src.crs and "lat_ts" in src.crs.to_proj4() or True:
        # all products here: eqc sphere R=3396190, lon_0=0, lat_ts=0 (checked via crs print)
        cx = math.radians(a.center_lonlat[0]) * R; cy = math.radians(a.center_lonlat[1]) * R
    h = a.size_m / 2
    # x-scale in eqc lat_ts=0: ground metres = source metres * cos(lat)
    hx = h / math.cos(math.radians(a.center_lonlat[1]))
    win = from_bounds(cx - hx, cy - h, cx + hx, cy + h, src.transform).round_offsets().round_lengths()
    t2 = time.time()
    arr = src.read(1, window=win)
    t3 = time.time()
    prof = src.profile.copy()
    prof.update(width=arr.shape[1], height=arr.shape[0], transform=src.window_transform(win), driver="GTiff",
                tiled=True, compress="deflate", blockxsize=512, blockysize=512, BIGTIFF="IF_SAFER")
    with rasterio.open(a.out, "w", **prof) as dst: dst.write(arr, 1)
    nd = src.nodata
    valid = arr[arr != nd] if nd is not None else arr
    print(f"window {win} shape {arr.shape} read {t3-t2:.1f}s -> {os.path.getsize(a.out)/1e6:.1f} MB local; valid {valid.size/arr.size:.1%} min {valid.min() if valid.size else None} max {valid.max() if valid.size else None}")
