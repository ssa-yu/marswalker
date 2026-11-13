"""X3 horizontal check by imagery: HiRISE ortho (1 m) averaged onto the CTX ortho grid (~22 m),
sub-pixel phase correlation on the overlap (both from the same MRO orbits -> same illumination).
Also a 5 m-grid check against a Trek/Esri CTX mosaic tile is possible later.
Usage: python register_ortho.py HIRISE_ORTHO CTX_ORTHO [--qa out.png]"""
import sys, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.windows import from_bounds
from skimage.registration import phase_cross_correlation
H = rasterio.open(sys.argv[1]); C = rasterio.open(sys.argv[2])
qa = sys.argv[sys.argv.index("--qa") + 1] if "--qa" in sys.argv else None
b = H.bounds; w, h = b.right - b.left, b.bottom - b.top
inner = (b.left + 0.2*(b.right-b.left), b.bottom + 0.15*(b.top-b.bottom), b.right - 0.2*(b.right-b.left), b.top - 0.15*(b.top-b.bottom))
win = from_bounds(*inner, C.transform).round_offsets().round_lengths()
c = C.read(1, window=win, masked=True).astype("float64").filled(np.nan); ctr = C.window_transform(win)
hh = np.full(c.shape, np.nan)
reproject(rasterio.band(H, 1), hh, src_nodata=0, dst_transform=ctr, dst_crs=C.crs, dst_nodata=np.nan, resampling=Resampling.average)
ok = np.isfinite(c) & np.isfinite(hh) & (hh > 0)
print(f"overlap grid {c.shape}, valid {ok.mean():.1%}, CTX res {C.res[0]:.2f} (source units)")
def norm(a):
    v = a[ok]; z = (a - v.mean()) / v.std(); z[~ok] = 0; return z
hn, cn = norm(hh), norm(c)
print(f"r at zero shift: {np.corrcoef(hn[ok], cn[ok])[0,1]:.3f}")
shift, err, _ = phase_cross_correlation(hn, cn, upsample_factor=50, reference_mask=ok, moving_mask=ok)
lat = np.radians((b.top + b.bottom) / 2 / 3396190.0)
dy, dx = shift[0] * C.res[1], shift[1] * C.res[0]
print(f"phase-corr shift (rows, cols) = ({shift[0]:+.2f}, {shift[1]:+.2f}) CTX px => dy {dy:+.1f} m, dx {dx:+.1f} m source; ground |d| = {np.hypot(dy, dx*np.cos(lat)):.1f} m")
# confirm with integer sliding search +-5 px (no wrap)
K = 25; best = (-2, 0, 0)
for i in range(-K, K+1):
    for j in range(-K, K+1):
        A = hn[K:-K, K:-K]; B = cn[K+i:cn.shape[0]-K+i, K+j:cn.shape[1]-K+j]; m = ok[K:-K, K:-K] & ok[K+i:ok.shape[0]-K+i, K+j:ok.shape[1]-K+j]
        r = np.corrcoef(A[m], B[m])[0, 1]
        if r > best[0]: best = (r, i, j)
print(f"sliding check: best r {best[0]:.3f} at (rows {best[1]:+d}, cols {best[2]:+d}) CTX px")
# local consistency after one global shift: phase-correlate 4 quadrants independently
ny, nx = hn.shape; qs = []
for qi, (r0, r1, c0, c1) in enumerate([(0, ny//2, 0, nx//2), (0, ny//2, nx//2, nx), (ny//2, ny, 0, nx//2), (ny//2, ny, nx//2, nx)]):
    s, _, _ = phase_cross_correlation(hn[r0:r1, c0:c1], cn[r0:r1, c0:c1], upsample_factor=50)
    qs.append(s); print(f"quadrant {qi}: shift rows {s[0]:+.2f} cols {s[1]:+.2f} CTX px")
qs = np.array(qs); dev = qs - shift
devm = np.hypot(dev[:, 0] * C.res[1], dev[:, 1] * C.res[0] * np.cos(lat))
print(f"quadrant deviation from global shift (ground m): {np.round(devm, 1)}; max {devm.max():.1f} m (X3 threshold 20 m)")
if qa:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 7))
    ax[0].imshow(np.where(ok, hn, np.nan), cmap="gray", vmin=-2.5, vmax=2.5); ax[0].set_title("HiRISE ortho avg -> CTX grid")
    ax[1].imshow(np.where(ok, cn, np.nan), cmap="gray", vmin=-2.5, vmax=2.5); ax[1].set_title("CTX orthoimage")
    plt.tight_layout(); plt.savefig(qa, dpi=70); print("qa ->", qa)
