# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""T5: true viewing direction of the Navcam photos (derived), for the map's photo layer.

python -m pipeline.photo_heading --scene jezero

Method verified in round 5 (S6-2, `spikes/s6_photo_azimuth.py`, 3 Navcam images matched to the CTX DTM horizon,
azimuth offset <= 1.0 deg): the CAHVORE camera model in the Raw Images JSON is in the rover frame; rotating its rays
by the `attitude` quaternion (w, x, y, z; rover -> local level, x north, y east, z down) gives true azimuths.
For each NAVCAM_LEFT image: azimuth of the rays through the centre and the left and right edges (mid-height) of the
delivered frame (CAHV part of the model, as in the verification). Other cameras: not verified,
no direction. `mast_az` from the metadata is relative to the rover body and is renamed `mast_az_rover_frame`.
"""
from __future__ import annotations

import argparse
import glob
import json
import math

import numpy as np
from scipy.spatial.transform import Rotation as Rot

from .common import Scene, log, write_json

P = lambda s: np.array([float(t) for t in s.strip("()").split(",")])


def ray(cahv, x, y):
    C, A, H, V = cahv
    r = np.cross(V - y * A, H - x * A)
    if r @ A < 0:
        r = -r
    return r / np.linalg.norm(r)


def az_el(r):
    return math.degrees(math.atan2(r[1], r[0])) % 360, -math.degrees(math.asin(max(-1.0, min(1.0, r[2]))))


def heading(im):
    cahv = [P(c) for c in im["camera"]["camera_model_component_list"].split(";")[:4]]
    q = P(im["attitude"])
    rot = Rot.from_quat([q[1], q[2], q[3], q[0]])
    sub = P(im["extended"]["subframeRect"]); sc = float(im["extended"]["scaleFactor"])
    w, h = sub[2] / sc, sub[3] / sc
    az, el = az_el(rot.apply(ray(cahv, w / 2, h / 2)))  # centre of the delivered frame (may be a subframe)
    left, _ = az_el(rot.apply(ray(cahv, 0.0, h / 2)))
    right, _ = az_el(rot.apply(ray(cahv, w, h / 2)))
    return {"heading_deg": round(az, 1), "elevation_deg": round(el, 1), "edge_left_deg": round(left, 1), "edge_right_deg": round(right, 1)}


def run(scene: str):
    sc = Scene(scene)
    pj = sc.web / "photos.json"
    photos = json.loads(pj.read_text())
    meta = {}
    for f in glob.glob(str(sc.raw / "raw_api" / "*.json")):
        for im in json.load(open(f)):
            meta[im["imageid"]] = im
    n = nv = 0
    for w in photos["waypoints"]:
        for im in w["images"]:
            if "mast_az" in im:
                im["mast_az_rover_frame"] = im.pop("mast_az")
            if "mast_el" in im:
                im["mast_el_rover_frame"] = im.pop("mast_el")
            im.pop("view", None)
            if im["camera"] != "NAVCAM_LEFT":
                continue
            n += 1
            m = meta.get(im["imageid"])
            if not m or not m.get("attitude") or "camera_model_component_list" not in m.get("camera", {}):
                continue
            im["view"] = {**heading(m), "label": "derived (camera model + rover attitude; method checked on 3 Navcam skylines, <= 1 deg)"}
            nv += 1
    photos["azimuth_confidence"] = ("Navcam: derived from the camera model rotated by the rover attitude (checked on 3 images against the "
                                    "CTX horizon, <= 1.0 deg). Front Hazcam and Mastcam-Z: not verified, no direction drawn. "
                                    "mast_az_rover_frame is relative to the rover body, not a compass bearing.")
    write_json(pj, photos)
    log(scene, "photo_heading", f"{nv} of {n} Navcam images got a viewing direction")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="jezero")
    run(ap.parse_args().scene)
