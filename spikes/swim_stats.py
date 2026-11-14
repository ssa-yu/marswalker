# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Read SWIM4MIM GeoTIFFs + RZ shapefile; print metadata and value distribution over Arcadia and at candidate sites.
Usage: python swim_stats.py SWIM_DIR"""
import glob, os, sys
import numpy as np, rasterio, pyogrio
d = sys.argv[1]
SITES = {"Starship 060706 (39.09N,189.80E)": (189.80, 39.09), "Starship 060719 (39.81N,195.62E)": (195.62, 39.81),
         "Starship 061075 (39.18N,195.61E)": (195.61, 39.18), "Starship 060363 (39.82N,192.06E)": (192.06, 39.82),
         "Starship 061128 (38.64N,190.16E)": (190.16, 38.64), "Jezero base (18.44N,77.45E)": (77.45, 18.44)}
BOX = (150, 35, 220, 50)  # Arcadia broad, lon E 0-360
for f in sorted(glob.glob(os.path.join(d, "SWIM4MIM_*.tif"))):
    with rasterio.open(f) as s:
        a = s.read(1).astype("float64"); nd = s.nodata
        print(f"\n== {os.path.basename(f)} {s.width}x{s.height} {s.dtypes[0]} nodata={nd} res={s.res} bounds={tuple(round(v,1) for v in s.bounds)}")
        print("   crs:", s.crs.to_proj4() if s.crs else None)
        v = a[(a != nd) & np.isfinite(a)] if nd is not None else a[np.isfinite(a)]
        print(f"   global valid {v.size}, min {v.min():.3f} max {v.max():.3f}, unique~{len(np.unique(np.round(v,3)))}")
        # convert box to pixel: assume geographic or eqc; use s.index on projected coords
        crs = s.crs
        from pyproj import Transformer
        tr = Transformer.from_crs("+proj=longlat +R=3396190 +no_defs", crs, always_xy=True)
        def pix(lon, lat):
            x, y = tr.transform(lon - 360 if lon > 180 else lon, lat)
            return s.index(x, y)
        parts = [(BOX[0], 180), (-180, BOX[2] - 360)] if BOX[2] > 180 else [(BOX[0], BOX[2])]
        subs = []
        for lo0, lo1 in parts:
            if lo1 <= lo0: continue
            r0, c0 = pix(lo0, BOX[3]); r1, c1 = pix(lo1 - 1e-6, BOX[1])
            subs.append(a[r0:r1+1, c0:c1+1].ravel())
        sub = np.concatenate(subs)
        sv = sub[(sub != nd) & np.isfinite(sub)]
        if sv.size:
            q = np.percentile(sv, [5, 25, 50, 75, 95])
            print(f"   Arcadia box 150-220E 35-50N: n={sv.size} pct5/25/50/75/95 = {np.round(q,3)}; frac>0.5={np.mean(sv>0.5):.2f} frac<0={np.mean(sv<0):.2f}")
        for name, (lon, lat) in SITES.items():
            r, c = pix(lon, lat)
            val = a[r, c] if 0 <= r < s.height and 0 <= c < s.width else None
            win = a[max(r-2,0):r+3, max(c-2,0):c+3]
            print(f"   {name}: {val if val is None else round(float(val),3)} (5x5 px range {np.nanmin(win):.2f}..{np.nanmax(win):.2f})")
for shp in glob.glob(os.path.join(d, "**/*.shp"), recursive=True):
    info = pyogrio.read_info(shp); df = pyogrio.read_dataframe(shp) if False else None
    print("\n== RZ", os.path.basename(shp), info["features"], "features; fields", list(info["fields"]), "crs", info["crs"][:80] if info["crs"] else None)
    from shapely import wkb, Point
    from pyproj import Transformer
    _, _, geoms, _ = pyogrio.raw.read(shp)
    g = wkb.loads(geoms[0]); tr = Transformer.from_crs("+proj=longlat +R=3396190 +no_defs", info["crs"], always_xy=True)
    print("   RZ bounds (proj m):", [round(v) for v in g.bounds], "area-ish parts:", len(getattr(g, "geoms", [g])))
    for name, (lon, lat) in SITES.items():
        x, y = tr.transform(lon - 360 if lon > 180 else lon, lat)
        print(f"   {name}: inside RZ = {g.contains(Point(x, y))}, distance to RZ = {g.distance(Point(x, y))/1000:.0f} km")
