"""S7 export: web/data/<scene>/scene.json (+ traverse/waypoints/photos for Jezero) and web/data/scenes.json.

python -m pipeline.export --scene jezero
Every layer carries `source` and a `label` in {measured, derived, assumed, simulated}.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .common import APP, Scene, log, read_json, write_json

REVIEW = "heuristic, not yet reviewed"


def src_meta(sc: Scene, sid: str) -> dict:
    s = sc.source(sid)
    return {"title": s["title"], "mission": s["mission"], "url": s["url"], "ref": s.get("ref"),
            "in_resources": s.get("resources", False)}


def dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def run(scene: str):
    sc = Scene(scene)
    L = read_json(sc.work / "layers.json")
    al = read_json(sc.work / "alignment.json")
    qa = read_json(sc.qa / "checks.json") if (sc.qa / "checks.json").exists() else {}
    P = L["_params"]
    sh = al["prior"]["applied_shift_m"]; dz = al["prior"]["applied_vertical_offset_m"]
    slope_legend = {"type": "bins", "unit": "deg", "edges": P["slope_edges_deg"], "colors": P["slope_colors"]}
    layers = []

    def add(lid, key, group, title, label, source, desc, visible=False, opacity=1.0, legend=None, extra=None):
        m = L.get(key)
        if m is None:
            return
        d = {"id": lid, "group": group, "title": title, "kind": m["kind"], "url": m["url"], "label": label,
             "source": source, "description": desc, "visible": visible, "opacity": opacity,
             "bytes": m.get("bytes"), "legend": legend}
        if m["kind"] == "image":
            d["coordinates"] = m["coordinates"]
        else:
            d.update(minzoom=m["minzoom"], maxzoom=m["maxzoom"], bounds=m["bounds"], tiles=m["tiles"])
        if extra:
            d.update(extra)
        layers.append(d)

    for key in reversed(sc.cfg.get("trek_layers", [])):
        t = L[f"trek_{key}"]["trek"]
        add(f"trek_{key}", f"trek_{key}", "Regional context", t["title"], t["label"],
            {"title": t["title"], "mission": t["mission"], "url": t["url_template"], "ref": t["ref"], "in_resources": True},
            f"NASA JPL Mars Trek WMTS tiles (zoom {t['zoom']}, ~{t['deg_per_px'] * 59274:.0f} m/px), saved locally.",
            visible=(key == "themis_day"))
    add("ctx_ortho", "ctx_ortho", "Prior terrain (CTX, orbital)", "CTX orthoimage", "measured", src_meta(sc, "prior_ortho"),
        f"Context Camera image around the study area. Registered to HiRISE with one global shift ({sh[0]:+.1f} m E, {sh[1]:+.1f} m N).",
        visible=True)
    add("ctx_hillshade", "ctx_hillshade", "Prior terrain (CTX, orbital)", "CTX DTM hillshade (prior, 20 m)", "derived",
        src_meta(sc, "dtm_prior"),
        f"What a planner knows before any scouting. Same sun ({P['sun_azimuth_deg']:.0f}°, {P['sun_altitude_deg']:.0f}° up) as the HiRISE hillshade; "
        f"shift {sh[0]:+.1f}/{sh[1]:+.1f} m, vertical {dz:+.1f} m applied.", opacity=0.85)
    add("ctx_slope", "ctx_slope", "Prior terrain (CTX, orbital)", f"CTX slope ({P['slope_prior_baseline_m']:.0f} m baseline)", "derived",
        src_meta(sc, "dtm_prior"), "Slope from the 20 m CTX DTM (Horn kernel).", legend=slope_legend, opacity=0.85)
    add("hirise_ortho", "hirise_ortho", "Reference terrain (HiRISE, orbital)", "HiRISE orthoimage 0.25 m", "measured",
        src_meta(sc, "ortho"), "High-resolution basemap of the study area (AOI).", visible=True)
    add("hirise_hillshade", "hirise_hillshade", "Reference terrain (HiRISE, orbital)", "HiRISE DTM hillshade (reference, 1 m)",
        "derived", src_meta(sc, "dtm_fine"), "HiRISE reference terrain, same sun as the CTX hillshade.", opacity=0.85)
    add("hirise_slope", "hirise_slope", "Reference terrain (HiRISE, orbital)",
        f"HiRISE slope ({P['slope_fine_baseline_m']:.0f} m baseline)", "derived", src_meta(sc, "dtm_fine"),
        f"Slope from the HiRISE DTM averaged to {P['slope_fine_grid_m']:.0f} m (Horn kernel).", legend=slope_legend, opacity=0.85)
    if "post_landing" in L:
        pl = al.get("post_landing", {})
        add("post_landing", "post_landing", "Rover ground data", "HiRISE 2021-09-24 (rover visible at its sol-212 stop)", "measured",
            src_meta(sc, "post_landing"),
            f"Taken ~sol 212, after the drives shown. Registered to the basemap on terrain texture only "
            f"(shift {pl.get('applied_shift_m')} m); the traverse was not used to place it.")

    out = {"scene": sc.name, "title": sc.cfg["title"], "subtitle": sc.cfg.get("subtitle", ""), "status": sc.cfg.get("status", "active"),
           "base": {**sc.cfg["base"], "local_origin": True},
           "aoi": {"extent_local_m": list(sc.extent("aoi")), "corners": sc.grid.corners_lonlat(*sc.extent("aoi")),
                   "rule": sc.cfg["aoi"].get("rule"), "label": sc.cfg["aoi"].get("label", "derived")},
           "context_corners": sc.grid.corners_lonlat(*sc.extent("context")),
           "layers": layers, "review": REVIEW,
           "alignment": {"x3": al["x3"], "prior_shift_m": sh, "prior_vertical_offset_m": dz,
                         "prior_registration": al["prior"]["image_registration"], "mola": al["mola"],
                         "post_landing": al.get("post_landing"),
                         "mola_pedr": read_json(sc.qa / "R1_mola_pedr.json") if (sc.qa / "R1_mola_pedr.json").exists() else None},
           "checks": qa.get("summary"), "ground_data": sc.cfg.get("ground_data")}

    # rover data (Jezero)
    if (sc.work / "photos.json").exists():
        import json
        ph = read_json(sc.work / "photos.json")
        xmin, ymin, xmax, ymax = sc.extent("context")
        wps = read_json(sc.work / "waypoints_all.json")
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [w["lon"], w["lat"]]},
             "properties": {"id": w["id"], "sol": w["sol"], "site": w["site"], "drive": w["drive"], "in_aoi": w["in_aoi"],
                            "elev_geoid": w["elev_geoid"], "x": w["x"], "y": w["y"]}}
            for w in wps if xmin <= w["x"] <= xmax and ymin <= w["y"] <= ymax]}
        write_json(sc.web / "waypoints.geojson", fc)
        tv = read_json(sc.work / "traverse_raw.geojson")
        feats = []
        for f in tv["features"]:
            cs = [[round(c[0], 7), round(c[1], 7)] for c in f["geometry"]["coordinates"]]
            xy = [sc.grid.lonlat_to_xy(c[0], c[1]) for c in cs]
            if any(xmin <= x <= xmax and ymin <= y <= ymax for x, y in xy):
                feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": cs},
                              "properties": {k: f["properties"].get(k) for k in ("sol", "fromRMC", "toRMC", "length")}})
        write_json(sc.web / "traverse.geojson", {"type": "FeatureCollection", "features": feats})
        pw = [w for w in ph["waypoints"] if w["images"]]
        web_ph = {k: v for k, v in ph.items() if k != "waypoints"}
        web_ph["waypoints"] = [{k: w[k] for k in ("id", "site", "drive", "sol", "lon", "lat", "x", "y", "images")} for w in pw]
        write_json(sc.web / "photos.json", web_ph)
        src_wp = src_meta(sc, "waypoints"); src_tv = src_meta(sc, "traverse")
        out["rover"] = {
            "traverse": {"url": "traverse.geojson", "label": "measured", "source": src_tv, "n_segments": len(feats)},
            "waypoints": {"url": "waypoints.geojson", "label": "measured", "source": src_wp, "n": len(fc["features"])},
            "photos": {"url": "photos.json", "label": "measured", "n_images": ph["n_images"],
                       "n_waypoints": ph["n_waypoints_with_photos"], "n_waypoints_aoi": ph["n_waypoints_aoi"],
                       "location_rule": ph["location_rule"], "azimuth_confidence": ph["azimuth_confidence"],
                       "source": {"title": "Mars Perseverance Raw Images", "mission": "Mars 2020 / NASA JPL-Caltech",
                                  "url": ph["source"], "in_resources": True}},
        }
        out["sizes"] = {"photos_bytes": dir_bytes(sc.web / "photos")}
    out.setdefault("sizes", {})
    out["sizes"].update({"tiles_bytes": dir_bytes(sc.web / "tiles"), "total_bytes": dir_bytes(sc.web)})
    write_json(sc.web / "scene.json", out)

    # scene index
    idx_p = APP / "web" / "data" / "scenes.json"
    idx = read_json(idx_p) if idx_p.exists() else {"scenes": []}
    idx["scenes"] = [s for s in idx["scenes"] if s["id"] != sc.name] + [
        {"id": sc.name, "title": sc.cfg["title"], "subtitle": sc.cfg.get("subtitle", ""), "status": sc.cfg.get("status", "active"),
         "order": sc.cfg.get("order", 9)}]
    idx["scenes"].sort(key=lambda s: s["order"])
    write_json(idx_p, idx)
    log(scene, "export", f"scene.json: {len(layers)} layers, web data {out['sizes']['total_bytes']/1e6:.1f} MB")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    run(ap.parse_args().scene)
