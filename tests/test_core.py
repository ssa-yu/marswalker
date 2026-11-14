# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Key checks: coordinate round trip, local<->source affine, exported JSON parses and carries source labels."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from pipeline.common import R_MARS, LocalGrid

APP = Path(__file__).resolve().parents[1]
LABELS = {"measured", "derived", "assumed", "simulated"}


@pytest.mark.parametrize("lon0,lat0", [(77.45088572, 18.44462715), (-164.39, 39.18), (195.61, 39.18)])
def test_roundtrip(lon0, lat0):
    g = LocalGrid(lon0, lat0)
    x = np.array([-1700.0, 0.0, 700.0, 1234.5]); y = np.array([-1000.0, 0.0, 1400.0, -77.7])
    lon, lat = g.xy_to_lonlat(x, y)
    x2, y2 = g.lonlat_to_xy(lon, lat)
    assert np.max(np.abs(x2 - x)) < 1e-6 and np.max(np.abs(y2 - y)) < 1e-6
    X, Y = g.xy_to_src(x, y)
    assert np.allclose(np.degrees(X / R_MARS), lon) and np.allclose(np.degrees(Y / R_MARS), lat)


def test_local_metres_are_ground_metres():
    g = LocalGrid(77.45, 18.44)
    lon, lat = g.xy_to_lonlat(np.array([1000.0]), np.array([0.0]))
    d = R_MARS * math.radians(lon[0] - 77.45) * math.cos(math.radians(18.44))
    assert abs(d - 1000.0) < 1e-6


def scenes():
    p = APP / "web" / "data" / "scenes.json"
    return [s["id"] for s in json.loads(p.read_text())["scenes"]] if p.exists() else []


@pytest.mark.parametrize("sid", scenes())
def test_scene_json_has_sources_and_labels(sid):
    d = json.loads((APP / "web" / "data" / sid / "scene.json").read_text())
    assert d["layers"], "no layers"
    for L in d["layers"]:
        assert L["label"] in LABELS, L["id"]
        assert L["source"]["title"] and L["source"]["url"], L["id"]
        if L["kind"] == "image":
            assert (APP / "web" / "data" / sid / L["url"]).exists(), L["url"]
    assert d["base"]["label"] == "assumed"
    if d.get("rover"):
        ph = json.loads((APP / "web" / "data" / sid / "photos.json").read_text())
        for w in ph["waypoints"]:
            for im in w["images"]:
                assert im["site"] == w["site"] and im["drive"] == w["drive"]
                assert im["credit"]
                assert (APP / "web" / "data" / sid / im["local"]).exists()
