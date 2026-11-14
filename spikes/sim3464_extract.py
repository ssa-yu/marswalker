# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Extract SIM 3464 geologic units / contacts for the Jezero region from the remote USGS zip
(GDAL /vsizip//vsicurl; no full download) into data_raw/jezero/step2/sim3464/<layer>.geojson in lon/lat
(Mars sphere R = 3396190 m, east-positive).

python spikes/sim3464_extract.py
"""
import json
import os
import time
from pathlib import Path

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
import numpy as np  # noqa: E402
import pyogrio  # noqa: E402
from pyproj import Transformer  # noqa: E402
from shapely import box, transform, wkb  # noqa: E402
from shapely.geometry import mapping  # noqa: E402

APP = Path(__file__).resolve().parents[1]
G = "/vsizip//vsicurl/https://pubs.usgs.gov/sim/3464/sim3464_database.zip/sim3464_JezeroNili_FINAL/Geodatabase/Nili.gdb"
OUT = APP / "data_raw/jezero/step2/sim3464"
t = time.time()
layers = [l for l in pyogrio.list_layers(G)]
print("layers:", layers)
bb = box(76.9, 18.0, 78.0, 18.9)
for name, gtype in layers:
    if gtype is None:
        continue
    try:
        meta, _, geoms, fields = pyogrio.raw.read(G, layer=name)
    except Exception as e:  # noqa: BLE001
        print("skip", name, e); continue
    tr = Transformer.from_crs(meta["crs"], "+proj=longlat +R=3396190 +no_defs", always_xy=True)
    feats = []
    for i, g in enumerate(geoms):
        if g is None:
            continue
        s = transform(wkb.loads(g), lambda xy: np.c_[tr.transform(xy[:, 0], xy[:, 1])])
        if not s.intersects(bb):
            continue
        props = {k: (v[i].item() if hasattr(v[i], "item") else v[i]) for k, v in zip(meta["fields"], fields)}
        props = {k: (str(v) if not isinstance(v, (int, float, str, type(None))) else v) for k, v in props.items()}
        feats.append({"type": "Feature", "geometry": mapping(s), "properties": props})
    (OUT / f"{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    print(name, gtype, len(feats), "features kept", round(time.time() - t, 1), "s")
