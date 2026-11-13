"""X3 check: does the coarse prior DTM (CTX ~20 m) line up with the HiRISE reference DTM (~1 m)?
Steps: aggregate HiRISE to CTX grid (average) -> vertical stats; sub-pixel horizontal shift by phase
correlation of detrended elevation on a common 5 m grid; optional MOLA DEM comparison.
Usage: python align_prior_reference.py HIRISE_DTM CTX_DTM [MOLA_DTM] [--qa out.png]"""
import sys, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from skimage.registration import phase_cross_correlation
hp, cp = sys.argv[1], sys.argv[2]
mp = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else None
qa = sys.argv[sys.argv.index("--qa") + 1] if "--qa" in sys.argv else None

def read_masked(path, bounds=None):
    s = rasterio.open(path)
    win = from_bounds(*bounds, s.transform).round_offsets().round_lengths() if bounds else None
    a = s.read(1, window=win, masked=True).astype("float64").filled(np.nan)
    a[a < -1e30] = np.nan
    tr = s.window_transform(win) if win is not None else s.transform
    return s, a, tr

H = rasterio.open(hp); C = rasterio.open(cp)
assert H.crs == C.crs, (H.crs, C.crs)
b = H.bounds
# 1) HiRISE -> CTX grid (average), vertical comparison
cs, carr, ctr = read_masked(cp, (b.left, b.bottom, b.right, b.top))
hagg = np.full(carr.shape, np.nan)
reproject(rasterio.band(H, 1), hagg, src_nodata=H.nodata, dst_transform=ctr, dst_crs=C.crs, dst_nodata=np.nan,
          resampling=Resampling.average)
m = np.isfinite(hagg) & np.isfinite(carr)
dz = (carr - hagg)[m]
nmad = 1.4826 * np.median(np.abs(dz - np.median(dz)))
print(f"[vertical] CTX - HiRISE(avg to CTX grid): n={m.sum()} mean {dz.mean():.2f} m median {np.median(dz):.2f} std {dz.std():.2f} NMAD {nmad:.2f} p5/p95 {np.percentile(dz,5):.2f}/{np.percentile(dz,95):.2f}")

# 2) horizontal shift on a common 5 m grid (central 80% of HiRISE footprint, detrended)
res = 5.0
w, h = b.right - b.left, b.top - b.bottom
bb = (b.left + 0.1*w, b.bottom + 0.1*h, b.right - 0.1*w, b.top - 0.1*h)
nx, ny = int((bb[2]-bb[0])/res), int((bb[3]-bb[1])/res)
tr5 = rasterio.transform.from_bounds(*bb, nx, ny)
def to5(src, rs):
    out = np.full((ny, nx), np.nan)
    reproject(rasterio.band(src, 1), out, src_nodata=src.nodata, dst_transform=tr5, dst_crs=src.crs, dst_nodata=np.nan, resampling=rs)
    return out
h5 = to5(H, Resampling.average); c5 = to5(C, Resampling.bilinear)
ok = np.isfinite(h5) & np.isfinite(c5)
yy, xx = np.mgrid[0:ny, 0:nx]
def detrend(a):
    A = np.c_[xx[ok], yy[ok], np.ones(ok.sum())]; coef, *_ = np.linalg.lstsq(A, a[ok], rcond=None)
    out = a - (coef[0]*xx + coef[1]*yy + coef[2]); out[~ok] = 0; return out
hd, cd = detrend(h5), detrend(c5)
# smooth HiRISE to CTX-like effective resolution before correlating
from scipy.ndimage import gaussian_filter
hd_s = gaussian_filter(hd, 20 / res)
shift, err, _ = phase_cross_correlation(hd_s, cd, upsample_factor=20)
print(f"[horizontal] shift (rows, cols) on 5 m grid = {shift}; => dy {shift[0]*res:.1f} m (+=south), dx {shift[1]*res:.1f} m; |d| {np.hypot(*shift)*res:.1f} m (source-projection metres; x ground = x*cos(lat))")
# Horizontal check without wrap-around: high-pass both surfaces (remove >200 m wavelengths, which carry
# DTM warping rather than position), then slide CTX over HiRISE by integer 5 m steps (+-150 m) using slices
# of the valid interior only, and take the Pearson-r peak; refine with a parabola fit.
def highpass(a):
    f = np.where(ok, a, 0.0); w = gaussian_filter(ok.astype(float), 200 / res)
    lo = gaussian_filter(f, 200 / res) / np.maximum(w, 1e-6)
    return np.where(ok, a - lo, np.nan)
hh = highpass(gaussian_filter(np.where(ok, h5, 0), 20 / res) / np.maximum(gaussian_filter(ok.astype(float), 20 / res), 1e-6))
ch = highpass(c5)
K = 30; m0 = K
Hc = hh[m0:-m0, m0:-m0]
rmap = np.full((2*K+1, 2*K+1), np.nan)
for i, dy in enumerate(range(-K, K+1)):
    for j, dx in enumerate(range(-K, K+1)):
        Cs = ch[m0+dy:ch.shape[0]-m0+dy, m0+dx:ch.shape[1]-m0+dx]
        v = np.isfinite(Hc) & np.isfinite(Cs)
        if v.sum() > 1000: rmap[i, j] = np.corrcoef(Hc[v], Cs[v])[0, 1]
i, j = np.unravel_index(np.nanargmax(rmap), rmap.shape)
def para(a, b, c): d = a - 2*b + c; return 0.0 if d == 0 else 0.5 * (a - c) / d
fy = para(rmap[i-1, j], rmap[i, j], rmap[i+1, j]) if 0 < i < 2*K else 0.0
fx = para(rmap[i, j-1], rmap[i, j], rmap[i, j+1]) if 0 < j < 2*K else 0.0
dy_m, dx_m = (i - K + fy) * res, (j - K + fx) * res
lat_c = np.degrees((b.top + b.bottom) / 2 / 3396190.0)
print(f"[horizontal] high-pass r at zero shift {rmap[K, K]:.3f}; peak r {rmap[i, j]:.3f} at CTX offset dy {dy_m:+.1f} m (rows, +=south), dx {dx_m:+.1f} m (source units; ground dx {dx_m*np.cos(np.radians(lat_c)):+.1f} m); |d| ground {np.hypot(dy_m, dx_m*np.cos(np.radians(lat_c))):.1f} m; peak on search edge: {i in (0, 2*K) or j in (0, 2*K)}")
# same sliding search on the detrended long-wavelength surfaces (NaN outside footprint, no wrap)
hl = np.where(ok, hd_s, np.nan); cl = np.where(ok, cd, np.nan)
Hc2 = hl[m0:-m0, m0:-m0]; r2 = np.full((2*K+1, 2*K+1), np.nan)
for i2, dy in enumerate(range(-K, K+1)):
    for j2, dx in enumerate(range(-K, K+1)):
        Cs = cl[m0+dy:cl.shape[0]-m0+dy, m0+dx:cl.shape[1]-m0+dx]; v = np.isfinite(Hc2) & np.isfinite(Cs)
        if v.sum() > 1000: r2[i2, j2] = np.corrcoef(Hc2[v], Cs[v])[0, 1]
i2, j2 = np.unravel_index(np.nanargmax(r2), r2.shape)
print(f"[horizontal] detrended-surface r at zero {r2[K, K]:.3f}; peak {r2[i2, j2]:.3f} at dy {(i2-K)*res:+.0f} m dx {(j2-K)*res:+.0f} m (source units); on edge: {i2 in (0, 2*K) or j2 in (0, 2*K)}")
# plane-removed vertical residual on the 5 m grid
dd = (c5 - h5)[ok]
A = np.c_[xx[ok], yy[ok], np.ones(ok.sum())]; coef, *_ = np.linalg.lstsq(A, dd, rcond=None)
resid = dd - A @ coef
print(f"[vertical] CTX-HiRISE on 5 m grid: plane tilt dz/dx {coef[0]/res*1000:.2f} m/km, dz/dy {coef[1]/res*1000:.2f} m/km; residual std {resid.std():.2f} m, NMAD {1.4826*np.median(np.abs(resid-np.median(resid))):.2f} m")
# correlation sanity
r = np.corrcoef(hd_s[ok], cd[ok])[0, 1]
print(f"[horizontal] correlation of detrended surfaces before shift: r={r:.3f}")

# 3) MOLA comparison (optional): MOLA DEM vs CTX and HiRISE averaged to MOLA grid
if mp:
    M = rasterio.open(mp)
    marr = M.read(1, masked=True).astype("float64").filled(np.nan)
    def toM(src):
        out = np.full(marr.shape, np.nan)
        reproject(rasterio.band(src, 1), out, src_nodata=src.nodata, dst_transform=M.transform, dst_crs=M.crs, dst_nodata=np.nan, resampling=Resampling.average)
        return out
    for name, src in (("CTX", C), ("HiRISE", H)):
        g = toM(src); mm = np.isfinite(g) & np.isfinite(marr)
        # only use MOLA cells fully covered: require cell count criteria approximated by interior mask erosion
        from scipy.ndimage import binary_erosion
        mm = binary_erosion(mm, iterations=1)
        d = (g - marr)[mm]
        print(f"[MOLA] {name} - MOLA463 (avg to MOLA grid): n={mm.sum()} mean {d.mean():.2f} median {np.median(d):.2f} std {d.std():.2f} m")
if qa:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 6))
    ax[0].imshow(np.where(ok, hd_s, np.nan), cmap="terrain"); ax[0].set_title("HiRISE detrended, smoothed 20 m")
    ax[1].imshow(np.where(ok, cd, np.nan), cmap="terrain"); ax[1].set_title("CTX detrended")
    ax[2].imshow(np.where(ok, hd_s - cd, np.nan), cmap="RdBu", vmin=-5, vmax=5); ax[2].set_title("difference (m)")
    plt.tight_layout(); plt.savefig(qa, dpi=80); print("qa ->", qa)
