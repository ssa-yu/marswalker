"""Remote readers tuned for slow trans-Pacific links to AWS us-west-2 (~30 KB/s per connection).

- download(): whole file, parallel HTTP Range chunks, resumable.
- cog_window(): only the TIFF header + the tiles that intersect a window are fetched in parallel into a
  sparse local copy of the remote file; GDAL then reads the window locally. Works for any tiled TIFF.
- strip_window(): uncompressed one-row-per-strip TIFFs (Mars 2020 TRN mosaics, MOLA 463 m): fetch only the
  needed byte span of each row.
All outputs are local GeoTIFFs in the source CRS.
"""
from __future__ import annotations

import concurrent.futures as cf
import math
import os
import time
import urllib.request
from pathlib import Path

import numpy as np

UA = {"User-Agent": "marswalk-recon-pipeline/0.1 (NASA Space Apps 2026 team project)"}


def _final_url_and_size(url: str):
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.geturl(), int(r.headers.get("Content-Length", 0))


def _get_range(url: str, s: int, e: int, tries: int = 8) -> bytes:
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, "Range": f"bytes={s}-{e}"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = r.read()
            if len(d) == e - s + 1:
                return d
            last = f"short read {len(d)} != {e - s + 1}"
        except Exception as ex:  # noqa: BLE001 - retry any network error
            last = repr(ex)
        time.sleep(min(30, 2 * (k + 1)))
    raise RuntimeError(f"range {s}-{e} failed: {last}")


def download(url: str, out: Path, conns: int = 16, chunk_mb: int = 4) -> dict:
    """Parallel ranged download with per-chunk resume. Returns a fetch-log record."""
    out = Path(out)
    if out.exists():
        return {"url": url, "path": str(out), "bytes": out.stat().st_size, "cached": True}
    t0 = time.time()
    final, size = _final_url_and_size(url)
    if size == 0 or size < 2 * 1024 * 1024:
        req = urllib.request.Request(final, headers=UA)
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        out.write_bytes(data)
        return {"url": url, "path": str(out), "bytes": len(data), "seconds": round(time.time() - t0, 1)}
    CH = chunk_mb * 1024 * 1024
    parts = Path(str(out) + ".parts")
    parts.mkdir(exist_ok=True)
    jobs = []
    for i, s in enumerate(range(0, size, CH)):
        e = min(s + CH, size) - 1
        fn = parts / f"{i:06d}"
        if not (fn.exists() and fn.stat().st_size == e - s + 1):
            jobs.append((fn, s, e))

    def work(job):
        fn, s, e = job
        fn.write_bytes(_get_range(final, s, e))

    with cf.ThreadPoolExecutor(conns) as ex:
        list(ex.map(work, jobs))
    n = (size + CH - 1) // CH
    with open(str(out) + ".tmp", "wb") as f:
        for i in range(n):
            f.write((parts / f"{i:06d}").read_bytes())
    os.replace(str(out) + ".tmp", out)
    for p in parts.iterdir():
        p.unlink()
    parts.rmdir()
    return {"url": url, "path": str(out), "bytes": size, "seconds": round(time.time() - t0, 1)}


def _merge_ranges(ranges, gap=16 * 1024, max_len=4 * 1024 * 1024):
    ranges = sorted(ranges)
    out = []
    for s, e in ranges:
        if out and s - out[-1][1] <= gap and e - out[-1][0] <= max_len:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return out


def cog_window(url: str, src_bounds, out: Path, conns: int = 24) -> dict:
    """Read window `src_bounds` (left, bottom, right, top; source CRS) of a remote tiled TIFF."""
    from osgeo import gdal
    import rasterio
    from rasterio.windows import from_bounds

    out = Path(out)
    if out.exists():
        return {"url": url, "path": str(out), "bytes": out.stat().st_size, "cached": True}
    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    t0 = time.time()
    final, size = _final_url_and_size(url)
    ds = gdal.Open("/vsicurl/" + final)
    gt = ds.GetGeoTransform()
    W, H = ds.RasterXSize, ds.RasterYSize
    b = ds.GetRasterBand(1)
    bx, by = b.GetBlockSize()
    left, bottom, right, top = src_bounds
    c0 = max(0, int(math.floor((left - gt[0]) / gt[1])))
    c1 = min(W, int(math.ceil((right - gt[0]) / gt[1])))
    r0 = max(0, int(math.floor((top - gt[3]) / gt[5])))
    r1 = min(H, int(math.ceil((bottom - gt[3]) / gt[5])))
    if c1 <= c0 or r1 <= r0:
        raise ValueError(f"window outside raster: cols {c0}:{c1} rows {r0}:{r1}")
    nb = ds.RasterCount
    ranges, first_data = [], None
    # smallest offset of any block in any IFD = end of the header/IFD area (COG layout)
    for ovi in range(b.GetOverviewCount() - 1, -1, -1):
        ob = b.GetOverview(ovi)
        off = ob.GetMetadataItem("BLOCK_OFFSET_0_0", "TIFF")
        if off:
            first_data = int(off) if first_data is None else min(first_data, int(off))
    for bi in range(1, nb + 1):
        band = ds.GetRasterBand(bi)
        for ty in range(r0 // by, (r1 - 1) // by + 1):
            for tx in range(c0 // bx, (c1 - 1) // bx + 1):
                off = band.GetMetadataItem(f"BLOCK_OFFSET_{tx}_{ty}", "TIFF")
                sz = band.GetMetadataItem(f"BLOCK_SIZE_{tx}_{ty}", "TIFF")
                if off is None or sz is None or int(sz) == 0:
                    continue
                off, sz = int(off), int(sz)
                first_data = off if first_data is None else min(first_data, off)
                ranges.append((max(0, off - 4), min(size - 1, off + sz + 3)))
    ds = None
    header = (0, max(16384, first_data or 16384) - 1)
    ranges = _merge_ranges([header] + ranges)
    total = sum(e - s + 1 for s, e in ranges)
    sparse = Path(str(out) + ".sparse.tif")
    with open(sparse, "wb") as f:
        f.truncate(size)
    fd = os.open(sparse, os.O_WRONLY)

    def work(r):
        d = _get_range(final, r[0], r[1])
        os.pwrite(fd, d, r[0])
        return len(d)

    t1 = time.time()
    with cf.ThreadPoolExecutor(conns) as ex:
        got = sum(ex.map(work, ranges))
    os.close(fd)
    t2 = time.time()
    with rasterio.open(sparse) as src:
        win = from_bounds(*src_bounds, src.transform).round_offsets().round_lengths()
        win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        arr = src.read(window=win)
        prof = src.profile.copy()
        prof.update(width=arr.shape[2], height=arr.shape[1], transform=src.window_transform(win), driver="GTiff",
                    tiled=True, blockxsize=512, blockysize=512, compress="deflate", BIGTIFF="IF_SAFER")
        for k in ("photometric",):
            prof.pop(k, None)
    with rasterio.open(out, "w", **prof) as dst:
        dst.write(arr)
    sparse.unlink()
    return {"url": url, "path": str(out), "method": "cog sparse tiles", "remote_bytes": size,
            "fetched_bytes": got, "requests": len(ranges), "seconds": round(t2 - t1, 1),
            "total_seconds": round(time.time() - t0, 1), "shape": list(arr.shape)}


def strip_window(url: str, src_bounds, out: Path, conns: int = 24) -> dict:
    """Window of an uncompressed, one-row-per-strip TIFF via per-row ranges."""
    from osgeo import gdal
    import rasterio
    from rasterio.transform import Affine

    out = Path(out)
    if out.exists():
        return {"url": url, "path": str(out), "bytes": out.stat().st_size, "cached": True}
    gdal.UseExceptions()
    gdal.SetConfigOption("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    t0 = time.time()
    final, size = _final_url_and_size(url)
    ds = gdal.Open("/vsicurl/" + final)
    b = ds.GetRasterBand(1)
    comp = ds.GetMetadataItem("COMPRESSION", "IMAGE_STRUCTURE")
    assert comp in (None, "NONE"), f"compressed ({comp}): use cog_window"
    assert b.GetBlockSize()[1] == 1, f"expected 1 row per strip, got {b.GetBlockSize()}"
    gt = ds.GetGeoTransform()
    W, H = ds.RasterXSize, ds.RasterYSize
    dt = gdal.GetDataTypeSize(b.DataType) // 8
    npdt = {gdal.GDT_Byte: np.uint8, gdal.GDT_Int16: np.int16, gdal.GDT_UInt16: np.uint16,
            gdal.GDT_Float32: np.float32}[b.DataType]
    left, bottom, right, top = src_bounds
    c0 = max(0, int(math.floor((left - gt[0]) / gt[1])))
    c1 = min(W, int(math.ceil((right - gt[0]) / gt[1])))
    r0 = max(0, int(math.floor((top - gt[3]) / gt[5])))
    r1 = min(H, int(math.ceil((bottom - gt[3]) / gt[5])))
    offs = [int(b.GetMetadataItem(f"BLOCK_OFFSET_0_{r}", "TIFF")) for r in range(r0, r1)]
    bo = "<" if ds.GetMetadataItem("BYTEORDER", "IMAGE_STRUCTURE") in (None, "LSB") else ">"
    nd = b.GetNoDataValue()
    proj = ds.GetProjection()
    ds = None
    arr = np.empty((r1 - r0, c1 - c0), npdt)

    def work(i):
        s = offs[i] + c0 * dt
        d = _get_range(final, s, s + (c1 - c0) * dt - 1)
        arr[i] = np.frombuffer(d, dtype=np.dtype(npdt).newbyteorder(bo))
        return len(d)

    t1 = time.time()
    with cf.ThreadPoolExecutor(conns) as ex:
        got = sum(ex.map(work, range(r1 - r0)))
    tr = Affine(gt[1], 0, gt[0] + c0 * gt[1], 0, gt[5], gt[3] + r0 * gt[5])
    with rasterio.open(out, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
                       dtype=arr.dtype, crs=proj, transform=tr, nodata=nd, tiled=True, compress="deflate",
                       BIGTIFF="IF_SAFER") as dst:
        dst.write(arr, 1)
    return {"url": url, "path": str(out), "method": "strip row ranges", "remote_bytes": size,
            "fetched_bytes": got, "seconds": round(time.time() - t1, 1),
            "total_seconds": round(time.time() - t0, 1), "shape": list(arr.shape)}
