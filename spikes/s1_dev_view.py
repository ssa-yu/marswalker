"""S1 dev viewer: image crops with feature maps (dev only, not the check figure)."""
import sys, numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pipeline.common import APP
G = dict(np.load(APP/"data_work/jezero/sand_v2_features.npz")); o05 = np.load(APP/"data_work/jezero/ortho_05.npy")
AOI=(-1700,-1000,700,1400)
def crop(a, res, cx, cy, half):
    r0=int((AOI[3]-cy-half)/res); c0=int((cx-half-AOI[0])/res); n=int(2*half/res); return a[r0:r0+n, c0:c0+n]
pts=[tuple(map(float,p.split(','))) for p in sys.argv[2].split(';')]
out=sys.argv[1]; half=float(sys.argv[3]) if len(sys.argv)>3 else 30
keys=["fine_coh","fine_en","coarse_coh","coarse_en"]
fig,axs=plt.subplots(len(pts),5,figsize=(17,3.4*len(pts)))
axs=np.atleast_2d(axs)
for i,(cx,cy) in enumerate(pts):
    s=crop(o05,.5,cx,cy,half); axs[i,0].imshow(s,cmap="gray",vmin=np.nanpercentile(s,1),vmax=np.nanpercentile(s,99)); axs[i,0].set_title(f"x {cx:.0f} y {cy:.0f}",fontsize=8)
    for j,k in enumerate(keys):
        v=crop(G[k],2,cx,cy,half); vm=(0,1) if "coh" in k else (0,.15)
        im=axs[i,j+1].imshow(v,cmap="viridis",vmin=vm[0],vmax=vm[1]); axs[i,j+1].set_title(f"{k} c={v[v.shape[0]//2,v.shape[1]//2]:.2f} med={np.median(v):.2f}",fontsize=8)
    for a in axs[i]: a.set_xticks([]); a.set_yticks([])
fig.tight_layout(); fig.savefig(out,dpi=70)
