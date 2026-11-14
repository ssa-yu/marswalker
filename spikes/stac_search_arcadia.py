# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Search USGS Astrogeology STAC for HiRISE/CTX DTMs over Arcadia Planitia.
Usage: python stac_search_arcadia.py [out.json]
bbox in planetocentric lon -180..180."""
import json, sys, urllib.request

API = "https://stac.astrogeology.usgs.gov/api/search"
BBOXES = [[-180, 30, -140, 55], [150, 30, 180, 55]]  # Arcadia Planitia broad (150E..220E)
COLLS = ["mro_hirise_socet_dtms", "mro_ctx_controlled_usgs_dtms"]

def search(coll, bbox):
    out, url, body = [], API, {"collections": [coll], "bbox": bbox, "limit": 200}
    while True:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=120))
        out += d["features"]
        nxt = [l for l in d.get("links", []) if l.get("rel") == "next"]
        if not nxt: return out
        url = nxt[0]["href"]; body = nxt[0].get("body", body)

res = {}
for c in COLLS:
    feats = []
    for b in BBOXES:
        feats += search(c, b)
    res[c] = feats
    print(f"== {c}: {len(feats)} items")
    for f in feats:
        bb = f.get("bbox"); a = f["assets"]
        cx = (bb[0]+bb[2])/2; cy = (bb[1]+bb[3])/2
        print(f"{f['id']} | center {cy:.3f}N {cx%360:.3f}E | bbox {[round(v,3) for v in bb]} | gsd {f['properties'].get('gsd')} | assets {list(a)[:8]}")
if len(sys.argv) > 1:
    json.dump(res, open(sys.argv[1], "w"), indent=1)
