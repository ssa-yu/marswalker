# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Headless stills (15 s demo film) of web/film.html at chosen times -> qa/film/t<sec>.jpg (1920x1080), prints console errors and the HUD.
python tools/screenshot_film.py [--url http://127.0.0.1:8765] [--times 1 2.5 ...]"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--url", default="http://127.0.0.1:8765")
ap.add_argument("--times", type=float, nargs="*", default=[0.0, 1.0, 2.2, 3.5, 5.0, 6.5, 8.0, 8.9, 9.0, 9.8, 10.6, 10.9, 11.2, 11.5, 12.0, 13.0, 14.0, 14.4, 15.0])
a = ap.parse_args()
out = APP / "qa" / "film"; out.mkdir(parents=True, exist_ok=True)
for f in out.glob("t*.jpg"):
    f.unlink()
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True, args=["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist"])
    pg = br.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    errors = []
    pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pg.goto(a.url + "/film.html?pause=1&dpr=1")
    pg.wait_for_function("window.film && window.film.ready", timeout=120000)
    pg.wait_for_timeout(800)
    for t in a.times:
        pg.evaluate(f"film.seek({t})")
        pg.wait_for_timeout(500)
        name = f"t{t:05.1f}".replace(".", "_") + ".jpg"
        pg.screenshot(path=str(out / name), quality=88)
        hud = pg.evaluate("['tag','hk','ho','sub','be','next'].map(id => id == 'be' ? document.getElementById(id).style.width : document.getElementById(id).textContent)")
        print("saved", name, "HUD", hud if t >= 9.6 else "-")
    print("errors:", len(errors), errors[:8])
    br.close()
