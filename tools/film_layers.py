# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Demo film helper layer -> web/data/film/film_layers.png (930x930 RGB, row 0 = north, same grid as brain_all.png).
R = brain score index from brain_all.png (0 = none, 1..255 = score 0..1).
G = rover reveal order: 0..250 = position along the loop (0 base .. 1 loop end) of the nearest rover path point
    for cells the rover saw (seen_loop.png > 0); 255 = never seen.  Display only (web/film.html).
python tools/film_layers.py"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

APP = Path(__file__).resolve().parents[1]
D = APP / "web" / "data" / "arcadia"
arc = json.loads((D / "arcadia.json").read_text())
geo = arc["geo"]
X0, Y0, X1, Y1 = arc["aoi_local_m"]
R_, lat0, lon0 = geo["R"], geo["lat0"], geo["lon0"]


def to_xy(lo, la):
    return ((lo - lon0) * math.pi / 180 * R_ * math.cos(lat0 * math.pi / 180), (la - lat0) * math.pi / 180 * R_)


score = np.array(Image.open(D / "brain_all.png"))             # palette indices
seen = np.array(Image.open(D / "seen_loop.png").convert("RGBA"))[..., 0]
n = score.shape[0]
cell = (X1 - X0) / n
pts, ss = [], []
for L in arc["rover"]["loops"]:
    p = np.array([to_xy(*q) for q in L["path"]])
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    # densify to ~4 m so the nearest point is close to the true nearest position on the path
    for a, b, sa, sb in zip(p[:-1], p[1:], seg[:-1], seg[1:]):
        k = max(1, int(math.ceil((sb - sa) / 4)))
        for t in np.arange(k) / k:
            pts.append(a + (b - a) * t); ss.append((sa + (sb - sa) * t) / seg[-1])
    pts.append(p[-1]); ss.append(1.0)
tree, ss = cKDTree(np.array(pts)), np.array(ss)
rr, cc = np.nonzero(seen > 0)
xy = np.c_[X0 + (cc + .5) * cell, Y1 - (rr + .5) * cell]
dist, idx = tree.query(xy, k=12)
near = dist <= dist[:, :1] + 24                                 # among the closest passes, take the earliest
s_cell = np.where(near, ss[idx], 9).min(axis=1)
G = np.full((n, n), 255, np.uint8)
G[rr, cc] = np.round(np.clip(s_cell, 0, 1) * 250).astype(np.uint8)
out = APP / "web" / "data" / "film"
out.mkdir(parents=True, exist_ok=True)
Image.fromarray(np.dstack([score.astype(np.uint8), G, np.zeros_like(G)]), "RGB").save(out / "film_layers.png", optimize=True)
print("film_layers.png", n, "seen cells", len(rr), "reveal pct", np.percentile(s_cell, [5, 50, 95]).round(2))
