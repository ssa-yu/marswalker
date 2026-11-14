# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""S1 dev loop: classify with current SAND_V2 and draw DEV sheets (seed 777, NOT the check seed)."""
import sys, json, numpy as np, rasterio
from pipeline.common import APP
from pipeline import sandfield as sf
from pipeline.sand_check import crop_sheet, pick, overview
from pipeline.terrain import block
S="/private/tmp/claude-501/-Users-shan-Documents-NASA-challenge/57b56c1c-358d-46b4-8fa4-815f1d1368f8/scratchpad/s1"
P=dict(sf.SAND_V2); P.update(json.loads(sys.argv[1]) if len(sys.argv)>1 else {})
G=dict(np.load(APP/"data_work/jezero/sand_v2_features.npz")); T=dict(np.load(APP/"data_work/jezero/terrain_2m.npz"))
sand,parts=sf.classify(G,T["slope_ref"],2.0,P)
print("sand %", round(100*sand.mean(),2), "raw", round(100*parts['raw'].mean(),2), "fine", round(100*parts['fine'].mean(),2),"coarse",round(100*parts['coarse'].mean(),2))
o=rasterio.open(APP/"data_work/jezero/ortho_025.tif").read(1).astype("float32"); o[o==0]=np.nan
aoi=(-1700,-1000,700,1400); rng=np.random.default_rng(777); m=17
tag=sys.argv[2] if len(sys.argv)>2 else "dev"
toxy=lambda rc:(aoi[0]+(rc[1]+.5)*2, aoi[3]-(rc[0]+.5)*2)
sp=[toxy(p) for p in pick(sand,16,rng,m)]; npn=[toxy(p) for p in pick(~sand,16,rng,m)]
crop_sheet(f"{S}/{tag}_sand.png",o,sand,aoi,2.0,sp,"S","DEV sand",ncol=4)
crop_sheet(f"{S}/{tag}_non.png",o,sand,aoi,2.0,npn,"N","DEV non-sand",ncol=4)
v1=[(-659,1323),(-895,-797),(9,-747),(-957,1131),(-1199,261),(-1591,-309),(-1467,1153),(-157,159),(311,541),(-1425,-545),(-29,-807),(-181,-831)]
crop_sheet(f"{S}/{tag}_v1.png",o,sand,aoi,2.0,v1,"V","DEV v1 crops",ncol=4)
o2=block(o,8,"mean"); overview(f"{S}/{tag}_overview.png",o2,T["class_ref"]==2,sand,aoi,"v1","v2","DEV")
