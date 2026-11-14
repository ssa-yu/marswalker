# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Regional context basemaps from NASA JPL Mars Trek (equirectangular WMTS tiles), stored locally.

python -m pipeline.trek --scene jezero
Output: data_raw/<scene>/trek_<layer>.png (+ .json with lon/lat bounds, tile list, URLs).
"""
from __future__ import annotations

import argparse
import io
import math
import time
import urllib.request

import numpy as np
from PIL import Image

from .common import Scene, log, write_json
from .remote import UA

TREK = {
    "themis_day": {
        "layer": "THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018", "ext": "png",
        "title": "THEMIS Day IR controlled mosaic 100 m (via Mars Trek)", "mission": "Mars Odyssey / THEMIS (ASU); served by NASA JPL Mars Trek",
        "label": "measured", "ref": "edwards2011", "resources": True,
    },
    "mola_hrsc": {
        "layer": "Mars_MOLA_blend200ppx_HRSC_ClrShade_clon0dd_200mpp_lzw", "ext": "jpg",
        "title": "MOLA + HRSC colour hillshade 200 m (via Mars Trek)", "mission": "MGS MOLA, Mars Express HRSC; served by NASA JPL Mars Trek",
        "label": "derived", "ref": "fergason2018", "resources": True,
    },
}
URL = "https://trek.nasa.gov/tiles/Mars/EQ/{layer}/1.0.0/default/default028mm/{z}/{row}/{col}.{ext}"


def fetch_layer(sc: Scene, key: str, zoom: int, half_m: float):
    meta = TREK[key]
    lat0, lon0 = sc.grid.lat0, sc.grid.lon0
    dlat = math.degrees(half_m / 3396190.0)
    dlon = dlat / math.cos(math.radians(lat0))
    W, E, S, N = lon0 - dlon, lon0 + dlon, lat0 - dlat, lat0 + dlat
    span = 180.0 / 2 ** zoom
    c0, c1 = int((W + 180) // span), int((E + 180) // span)
    r0, r1 = int((90 - N) // span), int((90 - S) // span)
    nc, nr = c1 - c0 + 1, r1 - r0 + 1
    mosaic = None
    urls = []
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            u = URL.format(layer=meta["layer"], z=zoom, row=r, col=c % (2 ** (zoom + 1)), ext=meta["ext"])
            urls.append(u)
            for k in range(5):
                try:
                    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as resp:
                        im = Image.open(io.BytesIO(resp.read())).convert("RGB")
                    break
                except Exception as ex:  # noqa: BLE001
                    if k == 4:
                        raise RuntimeError(f"{u}: {ex}")
                    time.sleep(2 + 2 * k)
            a = np.asarray(im)
            ts = a.shape[0]
            if mosaic is None:
                mosaic = np.zeros((nr * ts, nc * ts, 3), np.uint8)
            mosaic[(r - r0) * ts:(r - r0 + 1) * ts, (c - c0) * ts:(c - c0 + 1) * ts] = a
            time.sleep(0.1)
    ts = mosaic.shape[0] // nr
    px = span / ts
    # crop to requested window
    x0 = int((W - (c0 * span - 180)) / px); x1 = int(math.ceil((E - (c0 * span - 180)) / px))
    y0 = int(((90 - r0 * span) - N) / px); y1 = int(math.ceil(((90 - r0 * span) - S) / px))
    crop = mosaic[y0:y1, x0:x1]
    bounds = [c0 * span - 180 + x0 * px, 90 - r0 * span - y1 * px, c0 * span - 180 + x1 * px, 90 - r0 * span - y0 * px]
    out = sc.raw / f"trek_{key}.png"
    Image.fromarray(crop).save(out)
    info = {"key": key, **meta, "zoom": zoom, "deg_per_px": px, "bounds_lonlat": bounds, "shape": list(crop.shape),
            "tiles": len(urls), "url_template": URL.format(layer=meta["layer"], z="{z}", row="{row}", col="{col}", ext=meta["ext"]),
            "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    write_json(sc.raw / f"trek_{key}.json", info)
    log(sc.name, "trek", f"{key} z{zoom}: {len(urls)} tiles -> {crop.shape} ({px * 3396190 * math.pi / 180:.0f} m/px)")
    return info


def run(scene: str):
    sc = Scene(scene)
    reg = sc.cfg["regional"]
    for key in sc.cfg.get("trek_layers", []):
        if (sc.raw / f"trek_{key}.png").exists():
            continue
        z = reg.get("trek_zoom", 9) if key == "themis_day" else reg.get("trek_zoom_shade", 7)
        half = reg["half_size_m"] if key == "themis_day" else reg.get("shade_half_size_m", 250000)
        fetch_layer(sc, key, z, half)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    run(ap.parse_args().scene)
