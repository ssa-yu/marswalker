"""SWIM values: AOI pixel and 30 km neighbourhood mean for Arcadia 060706 vs Jezero AOI.
Usage: python swim_compare_sites.py SWIM_DIR"""
import glob, os, sys, numpy as np, rasterio
SITES = {"Arcadia 060706 AOI (39.09N, 189.80E)": (189.80 - 360, 39.09), "Jezero AOI (18.448N, 77.442E)": (77.442, 18.448)}
R = 3396190.0
for f in ["SWIM4MIM_Ci_0_1.tif", "SWIM4MIM_Ci_1_5.tif", "SWIM4MIM_Ci_5.tif", "SWIM4MIM_OriginalCi.tif"]:
    with rasterio.open(os.path.join(sys.argv[1], f)) as s:
        a = s.read(1).astype(float); a[a == s.nodata] = np.nan
        for n, (lon, lat) in SITES.items():
            r, c = s.index(np.radians(lon) * R, np.radians(lat) * R)
            nb = a[r-5:r+6, c-5:c+6]
            print(f"{f:26s} {n:38s} AOI pixel {a[r, c]:+.3f} | 11x11 px (~33 km) mean {np.nanmean(nb):+.3f} min {np.nanmin(nb):+.3f} max {np.nanmax(nb):+.3f}")
