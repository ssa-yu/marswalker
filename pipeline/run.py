"""Run the checkpoint-1 pipeline for one scene: fetch -> trek -> align -> grid -> rover -> layers -> qa -> export -> heading.

python -m pipeline.run --scene jezero [--from layers]
"""
from __future__ import annotations

import argparse

from . import align, export, fetch, grid, layers, photo_heading, qa, rover_m20, trek
from .common import Scene

STEPS = ["fetch", "trek", "align", "grid", "rover", "layers", "qa", "export", "heading"]


def main(scene: str, start: str = "fetch"):
    sc = Scene(scene)
    for st in STEPS[STEPS.index(start):]:
        if st == "fetch":
            fetch.run(scene)
        elif st == "trek":
            trek.run(scene)
        elif st == "align":
            align.run(scene)          # measures shifts from raw sources (never from shifted products)
        elif st == "grid":
            grid.run(scene)           # applies the recorded shifts
        elif st == "rover" and "waypoints" in sc.cfg["sources"]:
            rover_m20.run(scene)
        elif st == "layers":
            layers.run(scene)
        elif st == "qa":
            qa.run(scene)
        elif st == "export":
            export.run(scene)
        elif st == "heading" and "waypoints" in sc.cfg["sources"]:
            photo_heading.run(scene)  # T5: Navcam viewing directions into web photos.json


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--from", dest="start", default="fetch", choices=STEPS)
    a = ap.parse_args()
    main(a.scene, a.start)
