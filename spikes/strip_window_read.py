"""Window read for big *uncompressed, striped* GeoTIFFs (Mars 2020 TRN mosaics, MOLA 463 m): get strip offsets via
GDAL, then fetch only the needed byte span of each row with parallel HTTP range requests.
Usage: python strip_window_read.py URL OUT.tif --center-lonlat LON LAT --size-m 2400 [--conns 24]"""
import argparse, math, os, time, urllib.request, concurrent.futures as cf
import numpy as np
from osgeo import gdal
import rasterio
from rasterio.transform import Affine
p = argparse.ArgumentParser(); p.add_argument("url"); p.add_argument("out")
p.add_argument("--center-lonlat", nargs=2, type=float, required=True); p.add_argument("--size-m", type=float, default=2400)
p.add_argument("--conns", type=int, default=24); a = p.parse_args()
gdal.UseExceptions(); gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
t0 = time.time()
ds = gdal.Open("/vsicurl/" + a.url); b = ds.GetRasterBand(1)
assert ds.GetMetadataItem("COMPRESSION", "IMAGE_STRUCTURE") in (None, "NONE"), "compressed: use cog_window_read.py"
gt = ds.GetGeoTransform(); W, Hh = ds.RasterXSize, ds.RasterYSize
dt = gdal.GetDataTypeSize(b.DataType) // 8; npdt = {1: np.uint8, 2: np.int16, 4: np.float32}[dt] if b.DataType != gdal.GDT_UInt16 else np.uint16
R = 3396190.0; lon, lat = a.center_lonlat
cx, cy = math.radians(lon) * R, math.radians(lat) * R
hy = a.size_m / 2; hx = hy / math.cos(math.radians(lat))
c0 = int((cx - hx - gt[0]) / gt[1]); c1 = int(math.ceil((cx + hx - gt[0]) / gt[1]))
r0 = int((cy + hy - gt[3]) / gt[5]); r1 = int(math.ceil((cy - hy - gt[3]) / gt[5]))
c0, r0 = max(c0, 0), max(r0, 0); c1, r1 = min(c1, W), min(r1, Hh)
rows_per_strip = int(b.GetBlockSize()[1])
assert rows_per_strip == 1, f"expected 1 row per strip, got {rows_per_strip}"
offs = [int(b.GetMetadataItem(f"BLOCK_OFFSET_0_{r}", "TIFF")) for r in range(r0, r1)]
print(f"open+offsets {time.time()-t0:.1f}s; window rows {r0}:{r1} cols {c0}:{c1} ({(r1-r0)*(c1-c0)*dt/1e6:.1f} MB)")
final = urllib.request.urlopen(urllib.request.Request(a.url, method="HEAD"), timeout=60).geturl()
def fetch(i):
    s = offs[i] + c0 * dt; e = offs[i] + c1 * dt - 1
    for k in range(6):
        try:
            d = urllib.request.urlopen(urllib.request.Request(final, headers={"Range": f"bytes={s}-{e}"}), timeout=120).read()
            if len(d) == e - s + 1: return i, d
        except Exception: time.sleep(1 + k)
    raise RuntimeError(f"row {i} failed")
arr = np.empty((r1 - r0, c1 - c0), npdt); t1 = time.time()
bo = "<" if ds.GetMetadataItem("BYTEORDER", "IMAGE_STRUCTURE") in (None, "LSB") else ">"
with cf.ThreadPoolExecutor(a.conns) as ex:
    for i, d in ex.map(fetch, range(r1 - r0)): arr[i] = np.frombuffer(d, dtype=np.dtype(npdt).newbyteorder(bo))
print(f"fetched in {time.time()-t1:.1f}s")
tr = Affine(gt[1], 0, gt[0] + c0 * gt[1], 0, gt[5], gt[3] + r0 * gt[5])
nd = b.GetNoDataValue()
with rasterio.open(a.out, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1, dtype=arr.dtype, crs=ds.GetProjection(),
                   transform=tr, nodata=nd, tiled=True, compress="deflate") as dst: dst.write(arr, 1)
v = arr[arr != nd] if nd is not None else arr
print(f"-> {a.out} {os.path.getsize(a.out)/1e6:.1f} MB; min {v.min()} max {v.max()}; total {time.time()-t0:.1f}s")
