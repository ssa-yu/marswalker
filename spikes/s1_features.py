# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""S1 dev: compute sand-field v2 features on the AOI and cache them (2 m grid + 0.5 m ortho)."""
import time, numpy as np, rasterio
from pipeline.sandfield import features, to_grid, block_mean
from pipeline.common import APP
t=time.time()
o = rasterio.open(APP/"data_work/jezero/ortho_025.tif").read(1).astype("float32"); o[o==0]=np.nan
o05 = block_mean(o, 2); del o
F = features(o05)
G = to_grid(F, 4)
np.savez_compressed(APP/"data_work/jezero/sand_v2_features.npz", **G)
np.save(APP/"data_work/jezero/ortho_05.npy", o05.astype("float32"))
print({k:(float(np.nanpercentile(v,10)),float(np.nanpercentile(v,50)),float(np.nanpercentile(v,90))) for k,v in G.items()}, time.time()-t)
