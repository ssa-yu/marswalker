# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Stats for M20_waypoints.json: count, sol range, fields, images ratio, AOI search per MVP_PLAN §5.2.
Usage: python waypoints_stats.py M20_waypoints.json"""
import json, math, sys
from collections import Counter
fc = json.load(open(sys.argv[1]))
F = [f["properties"] for f in fc["features"]]
print("name:", fc.get("name"), "features:", len(F))
print("fields:", sorted(F[0].keys()))
sols = [p["sol"] for p in F]; print("sol range:", min(sols), max(sols))
img = [p for p in F if p.get("images")]
print("with images:", len(img), f"({len(img)/len(F):.1%})")
for lo, hi in [(0, 400), (401, 800), (801, 1200), (1201, 99999)]:
    sub = [p for p in F if lo <= p["sol"] <= hi]
    if sub: print(f"  sol {lo}-{hi}: {len(sub)} wps, images {sum(1 for p in sub if p.get('images'))}")
c = Counter(k for p in img for im in p["images"] for k in im.keys()); print("image keys:", dict(c))
print("example image:", img[5]["images"][0] if len(img) > 5 else img[0]["images"][0])
print("n images per wp (first 10 with images):", [len(p["images"]) for p in img[:10]])
# AOI per §5.2
R = 3389500.0; b = F[0]; blon, blat = b["lon"], b["lat"]
def xy(p):
    return ((p["lon"]-blon)*math.pi/180*R*math.cos(math.radians(blat)), (p["lat"]-blat)*math.pi/180*R)
pts = [xy(p) for p in F if p["sol"] <= 400]
S, best = 2400, None
for x0 in range(-S+300, -300+1, 100):
    for y0 in range(-S+300, -300+1, 100):
        n = sum(1 for x, y in pts if x0 <= x < x0+S and y0 <= y < y0+S)
        if best is None or n > best[0]: best = (n, x0, y0)
n, x0, y0 = best
print(f"AOI (sol<=400): {n} of {len(pts)} wps; x[{x0},{x0+S}] y[{y0},{y0+S}] (m, base origin)")
inaoi = [p for p in F if p["sol"] <= 400 and x0 <= xy(p)[0] < x0+S and y0 <= xy(p)[1] < y0+S]
print("  AOI wps with images:", sum(1 for p in inaoi if p.get("images")), " elev_geoid present:", sum(1 for p in inaoi if p.get("elev_geoid") is not None))
