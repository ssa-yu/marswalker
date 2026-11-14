# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Summarize stac_arcadia.json: HiRISE DTMs with rationale + overlapping CTX DTMs.
Usage: python summarize_stac.py stac_arcadia.json"""
import json, math, re, sys
d = json.load(open(sys.argv[1]))
H, C = d["mro_hirise_socet_dtms"], d["mro_ctx_controlled_usgs_dtms"]
def km(bb):
    lat = math.radians((bb[1]+bb[3])/2); k = 3389.5*math.pi/180
    return (bb[2]-bb[0])*k*math.cos(lat), (bb[3]-bb[1])*k
def contains(a, b):  # a contains b
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]
def overlaps(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])
rows = []
for f in H:
    bb = f["bbox"]; w, h = km(bb)
    rat = re.search(r"rationale for creation was: (.*?)\. This DTM", f["properties"]["description"])
    ctx_full = [c["id"] for c in C if contains(c["bbox"], bb)]
    ctx_ov = [c["id"] for c in C if overlaps(c["bbox"], bb)]
    orthos = [k for k in f["assets"] if ("ORTHO" in k or k.startswith("ortho_")) and not any(s in k for s in ("thumb", "label"))]
    rows.append(((bb[1]+bb[3])/2, f["id"], ((bb[0]+bb[2])/2) % 360, w, h, f["properties"]["gsd"], rat.group(1) if rat else "?", len(ctx_full), len(ctx_ov), ctx_full[:2], orthos))
for r in sorted(rows):
    print(f"{r[1]} | {r[0]:.2f}N {r[2]:.2f}E | {r[3]:.1f}x{r[4]:.1f} km | {r[5]:.2f} m | CTX contain {r[7]} overlap {r[8]} {r[9]} | orthos {len(r[10])} | {r[6]}")
print("CTX gsd sample:", sorted({round(c['properties'].get('gsd', 0)) for c in C}))
