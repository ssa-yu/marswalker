# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""S5 (Jezero only): Perseverance waypoints, traverse and raw images located on the map.

python -m pipeline.rover_m20 --scene jezero

Photo location rule (exact, no interpolation): a raw image is attached to a waypoint only when its
`site` and `drive` (rover motion counter at acquisition) equal that waypoint's. Waypoints are drive end
points, so such images were taken while the rover stood at that waypoint.
Search window per waypoint: sols [waypoint sol, next waypoint's sol] (rover stays until the next drive).
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request

import numpy as np

from .common import APP, Scene, log, read_json, write_json
from .remote import UA

API = "https://mars.nasa.gov/rss/api/"


def api_sol(sc: Scene, sol: int, cams: list[str]) -> list[dict]:
    """All full-frame images of `cams` on `sol` (cached per sol)."""
    cdir = sc.raw / "raw_api"; cdir.mkdir(exist_ok=True)
    cp = cdir / f"sol_{sol:04d}.json"
    if cp.exists():
        return read_json(cp)
    imgs, page = [], 0
    while True:
        q = {"feed": "raw_images", "category": "mars2020", "feedtype": "json", "num": 100, "page": page,
             "order": "sol asc", "condition_2": f"{sol}:sol:gte", "condition_3": f"{sol}:sol:lte",
             "extended": "sample_type::full,", "search": "|".join(cams)}
        url = API + "?" + urllib.parse.urlencode(q, safe=":,")
        for k in range(5):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                    d = json.loads(r.read())
                break
            except Exception as ex:  # noqa: BLE001
                if k == 4:
                    raise RuntimeError(f"{url}: {ex}")
                time.sleep(3 * (k + 1))
        imgs += d.get("images", [])
        time.sleep(0.5)
        if (page + 1) * 100 >= int(d.get("total_results", 0)):
            break
        page += 1
    write_json(cp, imgs)
    return imgs


def _dim(im):
    try:
        w, h = [int(v) for v in im["extended"]["dimension"].strip("()").split(",")]
        return w, h
    except Exception:  # noqa: BLE001
        return 0, 0


def pick(images: list[dict], per_wp: int) -> list[dict]:
    """Prefer full-size Navcam frames with distinct pointing, then one Mastcam-Z colour, then Hazcam."""
    def score(im):
        w, h = _dim(im)
        return (h >= 0.5 * w, w * h)
    by = {c: sorted([i for i in images if i["camera"]["instrument"] == c], key=score, reverse=True)
          for c in ("NAVCAM_LEFT", "MCZ_LEFT", "FRONT_HAZCAM_LEFT_A")}
    out = []
    used_az = []
    for im in by["NAVCAM_LEFT"]:
        w, h = _dim(im)
        if h < 0.5 * w:  # skip thin strip sub-frames
            continue
        try:
            az = float(im["extended"]["mastAz"])
        except Exception:  # noqa: BLE001
            az = None
        if az is not None and any(abs(((az - u + 180) % 360) - 180) < 40 for u in used_az):
            continue
        out.append(im); used_az.append(az if az is not None else -999)
        if len(out) >= max(1, per_wp - 2):
            break
    for c in ("MCZ_LEFT", "FRONT_HAZCAM_LEFT_A"):
        for im in by[c]:
            w, h = _dim(im)
            if h >= 0.5 * w and len(out) < per_wp:
                out.append(im); break
    for im in by["NAVCAM_LEFT"]:  # top up
        if len(out) >= per_wp:
            break
        if im not in out and _dim(im)[1] >= 0.5 * _dim(im)[0]:
            out.append(im)
    return out


def download(url: str, out) -> int:
    if out.exists():
        return out.stat().st_size
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
            out.write_bytes(data)
            return len(data)
        except Exception:  # noqa: BLE001
            time.sleep(2 * (k + 1))
    return 0


def run(scene: str):
    sc = Scene(scene)
    rc = sc.cfg["rover"]
    wp_path = sc.raw_path("waypoints")
    if not wp_path.exists():
        wp_path = APP / sc.source("waypoints")["cache"]
    fc = read_json(wp_path)
    feats = sorted(fc["features"], key=lambda f: (f["properties"]["sol"], f["properties"]["site"], int(f["properties"]["drive"])))
    xmin, ymin, xmax, ymax = sc.extent("aoi")
    wps = []
    for i, f in enumerate(feats):
        p = f["properties"]
        x, y = sc.grid.lonlat_to_xy(p["lon"], p["lat"])
        nxt = feats[i + 1]["properties"]["sol"] if i + 1 < len(feats) else p["sol"]
        wps.append({"id": f"{p['site']}_{p['drive']}", "site": int(p["site"]), "drive": int(p["drive"]), "sol": int(p["sol"]),
                    "sol_next": int(nxt), "lon": p["lon"], "lat": p["lat"], "x": round(float(x), 2), "y": round(float(y), 2),
                    "elev_geoid": p.get("elev_geoid"), "yaw": p.get("yaw"), "dist_total_m": p.get("dist_total_m"),
                    "in_aoi": bool(xmin <= x <= xmax and ymin <= y <= ymax)})
    inside = [w for w in wps if w["in_aoi"]]
    log(scene, "rover", f"{len(wps)} waypoints, {len(inside)} inside AOI (sol {inside[0]['sol']}..{inside[-1]['sol']})")

    # waypoint + traverse GeoJSON (traverse clipped to the context extent for the web)
    write_json(sc.work / "waypoints_all.json", wps)
    tv = read_json(sc.raw_path("traverse"))
    write_json(sc.work / "traverse_raw.geojson", tv)

    photos_dir = sc.web / "photos"; photos_dir.mkdir(parents=True, exist_ok=True)
    cams = rc["photo_cameras"]
    out_wps, n_img, n_bytes, n_candidates = [], 0, 0, 0
    budget = rc.get("photo_bytes_max", 60_000_000)
    for w in inside:
        cand = []
        for sol in range(w["sol"], w["sol_next"] + 1):
            cand += [im for im in api_sol(sc, sol, cams) if int(im["site"]) == w["site"] and int(im["drive"]) == w["drive"]]
        n_candidates += len(cand)
        if not cand:
            out_wps.append({**w, "images": [], "n_candidates": 0})
            continue
        sel = pick(cand, rc["photos_per_waypoint"])
        imgs = []
        for im in sel:
            if n_bytes > budget:
                break
            url = im["image_files"].get("medium") or im["image_files"].get("small")
            fn = f"{im['imageid']}.jpg"
            nb = download(url, photos_dir / fn)
            if nb == 0:
                continue
            n_bytes += nb; n_img += 1
            ext = im.get("extended", {})
            imgs.append({"imageid": im["imageid"], "camera": im["camera"]["instrument"], "local": f"photos/{fn}",
                         "url_medium": im["image_files"].get("medium"), "url_full": im["image_files"].get("full_res"),
                         "page": im.get("link"), "sol": im["sol"], "site": int(im["site"]), "drive": int(im["drive"]),
                         "mast_az": _f(ext.get("mastAz")), "mast_el": _f(ext.get("mastEl")),
                         "date_mars": im.get("date_taken_mars"), "date_utc": im.get("date_taken_utc"),
                         "caption": (im.get("caption") or "").strip(), "credit": im.get("credit"), "title": im.get("title")})
        out_wps.append({**w, "images": imgs, "n_candidates": len(cand)})
    with_img = [w for w in out_wps if w["images"]]
    res = {"label": "measured", "location_rule": "site/drive equality with waypoint (exact)",
           "azimuth_confidence": "unverified", "cameras": cams,
           "n_waypoints_aoi": len(inside), "n_waypoints_with_photos": len(with_img),
           "n_candidate_images": n_candidates, "n_images": n_img, "bytes": n_bytes,
           "credit_default": "NASA/JPL-Caltech (Mastcam-Z: NASA/JPL-Caltech/ASU)",
           "source": "https://mars.nasa.gov/mars2020/multimedia/raw-images/", "waypoints": out_wps}
    write_json(sc.work / "photos.json", res)
    log(scene, "rover", f"photos: {n_img} images ({n_bytes/1e6:.1f} MB) at {len(with_img)}/{len(inside)} AOI waypoints; "
                        f"{n_candidates} candidate images matched site/drive")
    return res


def _f(v):
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    run(ap.parse_args().scene)
