"""How much hazard does the 1 m reference show that the ~20 m prior misses? (Map B premise check)
Slope on a 2 m grid from HiRISE (avg-aggregated) vs CTX (bilinear-upsampled); thresholds from MVP_PLAN §5.4.
Usage: python hazard_contrast.py HIRISE_DTM CTX_DTM [--qa out.png]"""
import sys, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
H = rasterio.open(sys.argv[1]); C = rasterio.open(sys.argv[2])
qa = sys.argv[sys.argv.index("--qa") + 1] if "--qa" in sys.argv else None
b = H.bounds; lat = np.radians((b.top + b.bottom) / 2 / 3396190.0)
res_y = 2.0; res_x = 2.0 / np.cos(lat)  # source eqc units -> ~2 m ground in both axes
w, h = b.right - b.left, b.top - b.bottom
bb = (b.left + 0.15*w, b.bottom + 0.1*h, b.right - 0.15*w, b.top - 0.1*h)
nx, ny = int((bb[2]-bb[0]) / res_x), int((bb[3]-bb[1]) / res_y)
tr = rasterio.transform.from_bounds(*bb, nx, ny)
def grid(src, rs):
    out = np.full((ny, nx), np.nan)
    reproject(rasterio.band(src, 1), out, src_nodata=src.nodata, dst_transform=tr, dst_crs=src.crs, dst_nodata=np.nan, resampling=rs)
    return out
zr, zp = grid(H, Resampling.average), grid(C, Resampling.bilinear)
def slope(z):
    gy, gx = np.gradient(z, 2.0, 2.0); return np.degrees(np.arctan(np.hypot(gx, gy)))
sr, sp = slope(zr), slope(zp)
ok = np.isfinite(sr) & np.isfinite(sp)
print(f"grid {nx}x{ny} @2 m ground ({nx*2/1000:.1f} x {ny*2/1000:.1f} km), valid {ok.mean():.1%}")
for name, s in (("reference HiRISE", sr), ("prior CTX", sp)):
    v = s[ok]; print(f"{name}: slope p50 {np.percentile(v,50):.2f} p95 {np.percentile(v,95):.2f} p99 {np.percentile(v,99):.2f} max {v.max():.1f} deg; >8 {np.mean(v>8):.2%} >15 {np.mean(v>15):.2%} >25 {np.mean(v>25):.3%}")
for th in (8, 15, 25):
    hidden = ok & (sr > th) & (sp <= th)
    print(f"cells steeper than {th} deg in reference but not in prior: {hidden.sum()} ({hidden.sum()/ok.sum():.2%} of area); of all reference>{th}: {hidden.sum()/max((ok&(sr>th)).sum(),1):.0%}")
# baseline sensitivity: slope of the reference after smoothing to 6 m and 10 m (HiRISE DTM noise inflates 2 m slopes)
from scipy.ndimage import uniform_filter as _uf
for L in (3, 5):
    s2 = slope(np.where(np.isfinite(zr), _uf(np.nan_to_num(zr), L), np.nan)); v = s2[ok]
    print(f"reference smoothed {2*L} m: slope p50 {np.percentile(v,50):.2f} p95 {np.percentile(v,95):.2f} p99 {np.percentile(v,99):.2f}; >8 {np.mean(v>8):.2%} >15 {np.mean(v>15):.2%} >25 {np.mean(v>25):.3%}")
# roughness: std of 1 m DTM detrended within 5 m windows -> use residual of 2 m grid vs 10 m smooth
from scipy.ndimage import uniform_filter
rough = np.sqrt(np.maximum(uniform_filter(zr**2, 3) - uniform_filter(zr, 3)**2, 0))
print(f"reference local relief (3x3 @2 m) p50 {np.nanpercentile(rough,50):.2f} p95 {np.nanpercentile(rough,95):.2f} p99 {np.nanpercentile(rough,99):.2f} m")
if qa:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 7))
    ax[0].imshow(sr, vmin=0, vmax=20, cmap="magma"); ax[0].set_title("reference slope (deg, HiRISE @2 m)")
    ax[1].imshow(sp, vmin=0, vmax=20, cmap="magma"); ax[1].set_title("prior slope (deg, CTX upsampled)")
    plt.tight_layout(); plt.savefig(qa, dpi=70); print("qa ->", qa)
