"""T5 screenshot: Navcam viewing-direction wedges on the map-data page.
python tools/screenshot_views.py [--url http://127.0.0.1:8765] -> qa/screenshots/T5_navcam_*.png"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--url", default="http://127.0.0.1:8765"); a = ap.parse_args()
out = APP / "qa" / "screenshots"
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    pg = br.new_page(viewport={"width": 1600, "height": 950})
    errors = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(a.url + "/data.html#jezero")
    pg.wait_for_function("window.__mapIdle === true && S.photos && S.map.getLayer('photo-views')", timeout=120000)
    for name, z in (("01_landing_area", 16.3), ("02_close", 17.6)):
        pg.evaluate(f"S.map.jumpTo({{center:[S.scene.base.lon + 0.0004, S.scene.base.lat - 0.0002], zoom: {z}}})")
        pg.wait_for_timeout(1500)
        pg.evaluate("new Promise(r => { const t = setTimeout(() => r(false), 30000); S.map.once('idle', () => { clearTimeout(t); r(true); }); S.map.triggerRepaint(); })")
        pg.screenshot(path=str(out / f"T5_navcam_{name}.png")); print("saved", name)
    pg.evaluate("openPhotos(S.photos.waypoints[1].id)"); pg.wait_for_timeout(2500)
    pg.screenshot(path=str(out / "T5_navcam_03_photo_panel.png")); print("saved 03")
    print("errors:", errors)
    br.close()
