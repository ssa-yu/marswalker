# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Assets for web/arcadia3d.html (teammate Shooyunn's first-person walk page, adapted to Arcadia):
  data/arcadia/walk3d_ortho.jpg   HiRISE 0.5 m ortho of the study square at 1.5 m (2480 px, about the size of the Jezero
                                  hirise_1m.jpg the page was written for; same grey stretch as the map tiles)
  data/arcadia/walk3d_dtm.tif     HiRISE DTM (1 m, USGS) averaged to 4 m over the square, float32 GeoTIFF whose
                                  bounding box is in local metres (x east, y north of the grid origin), as the page reads it
The class image is the map's own data/arcadia/classes.png (4 m). Display only; no computed result uses these.
python -m pipeline.arcadia_3d"""
from __future__ import annotations

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import Affine

from .common import Scene, log, read_json
from .terrain import block

SCENE = "arcadia"
DEM_RES = 4.0
ORTHO_PX = 2480


def run():
    sc = Scene(SCENE)
    out = sc.web
    aoi = sc.extent("aoi")
    with rasterio.open(sc.work / "ortho_05.tif") as s:
        o = s.read(1).astype(np.float32)
    lo, hi = read_json(out / "arcadia.json")["tiles"]["stretch"]
    g = block(o, 2, "mean")
    del o
    g8 = (np.clip((np.nan_to_num(g, nan=lo) - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(g8, "L").resize((ORTHO_PX, ORTHO_PX), Image.LANCZOS).save(out / "walk3d_ortho.jpg", quality=75,
                                                                              optimize=True)
    # DTM: v2 local 1 m grid (padded 30 m) -> rows / cols of the square -> 4 m mean
    gm = read_json(sc.work / "v2_strip" / "grid.json")["products"]["dtm_fine"]
    ex = gm["extent_local_m"]
    with rasterio.open(sc.work / "v2_strip" / "dtm_fine.tif" if (sc.work / "v2_strip" / "dtm_fine.tif").exists()
                       else sc.work / "dtm_fine.tif") as s:
        z = s.read(1).astype(np.float32)
    r0 = int(round(ex[3] - aoi[3])); c0 = int(round(aoi[0] - ex[0]))
    n_r = int(aoi[3] - aoi[1]); n_c = int(aoi[2] - aoi[0])
    z = z[r0:r0 + n_r, c0:c0 + n_c]
    dem = block(z, int(DEM_RES), "mean").astype(np.float32)
    dem[~np.isfinite(dem)] = -1e9
    with rasterio.open(out / "walk3d_dtm.tif", "w", driver="GTiff", width=dem.shape[1], height=dem.shape[0], count=1,
                       dtype="float32", nodata=-1e9, compress="deflate",
                       transform=Affine(DEM_RES, 0, aoi[0], 0, -DEM_RES, aoi[3])) as d:
        d.write(dem, 1)
    log(SCENE, "3d", f"ortho {g8.shape} {(out / 'walk3d_ortho.jpg').stat().st_size / 1e6:.2f} MB, dtm {dem.shape} "
        f"{(out / 'walk3d_dtm.tif').stat().st_size / 1e6:.2f} MB, z {np.nanmin(z):.1f}..{np.nanmax(z):.1f} m")


if __name__ == "__main__":
    run()
