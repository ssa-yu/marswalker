# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Compare HiRISE ortho position with the Trek/Esri global CTX mosaic tiles (z11, geographic tile matrix).
Usage: python register_vs_trek_ctx.py HIRISE_ORTHO OUTDIR"""
import io, os, sys, math, urllib.request, numpy as np, rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
from PIL import Image
from skimage.registration import phase_cross_correlation
H = rasterio.open(sys.argv[1]); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
R = 3396190.0
cx, cy = (H.bounds.left + H.bounds.right) / 2, (H.bounds.top + H.bounds.bottom) / 2
lon, lat = math.degrees(cx / R), math.degrees(cy / R)
z = 11; ncol, nrow = 2 ** (z + 1), 2 ** z; deg = 360 / ncol  # tile size in degrees; 512 px per tile
c0, r0 = int((lon + 180) / deg), int((90 - lat) / deg)
mos = np.zeros((1024, 1024), np.float32)
for dr in (0, 1):
    for dc in (0, 1):
        url = f"https://astro.arcgis.com/arcgis/rest/services/OnMars/CTX/MapServer/tile/{z}/{r0+dr-0}/{c0+dc-0}"
        im = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=120).read())).convert("L")
        mos[dr*512:(dr+1)*512, dc*512:(dc+1)*512] = np.asarray(im, np.float32)
px = deg / 512
west, north = -180 + c0 * deg, 90 - r0 * deg
# express the mosaic grid in the same eqc metres as HiRISE (R=3396190, lat_ts=0)
tr = from_origin(math.radians(west) * R, math.radians(north) * R, math.radians(px) * R, math.radians(px) * R)
print(f"tiles z{z} r{r0}-{r0+1} c{c0}-{c0+1}; pixel {math.radians(px)*R:.2f} m (source units)")
hh = np.full(mos.shape, np.nan, np.float64)
reproject(rasterio.band(H, 1), hh, src_nodata=0, dst_transform=tr, dst_crs=H.crs, dst_nodata=np.nan, resampling=Resampling.average)
ok = np.isfinite(hh) & (hh > 0) & (mos > 0)
print("overlap fraction:", round(ok.mean(), 3))
def norm(a):
    v = a[ok]; z_ = (a - v.mean()) / v.std(); z_[~ok] = 0; return z_
s, _, _ = phase_cross_correlation(norm(hh), norm(mos.astype(float)), upsample_factor=20, reference_mask=ok, moving_mask=ok)
pm = math.radians(px) * R
print(f"shift rows {s[0]:+.2f} cols {s[1]:+.2f} px => ground |d| {math.hypot(s[0]*pm, s[1]*pm*math.cos(math.radians(lat))):.0f} m")
