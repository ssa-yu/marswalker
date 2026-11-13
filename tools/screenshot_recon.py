"""Headless screenshots of the step-1 recon page (installed Google Chrome through Playwright).
python tools/screenshot_recon.py [--url http://127.0.0.1:8765]  -> qa/screenshots/recon_*.png"""
import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--url", default="http://127.0.0.1:8765"); a = ap.parse_args()
out = APP / "qa" / "screenshots"; out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    pg = br.new_page(viewport={"width": 1600, "height": 950})
    errors = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    t0 = time.time()
    pg.goto(a.url + "/recon.html")
    pg.wait_for_function("window.__mapIdle === true && S.rc", timeout=120000)
    print("loaded in", round(time.time() - t0, 2), "s")

    def shot(name, js=None, wait=1.5):
        if js:
            pg.evaluate(js)
        pg.wait_for_timeout(int(wait * 1000))
        pg.evaluate("new Promise(r => { const t = setTimeout(() => r(false), 30000); S.map.once('idle', () => { clearTimeout(t); r(true); }); S.map.triggerRepaint(); })")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(out / f"T1_recon_rerun_{name}.png")); print("saved", name)

    shot("00_before_departure", "setLoop(0)")
    shot("01_loop1_end", "setLoop(1)")
    L = pg.evaluate("S.rc.loops[1]")
    mid = (L["t0"] + L["t1"]) // 2
    shot("02_loop2_midway_replay", f"setT({mid}); S.map.jumpTo({{center: roverPos({mid}), zoom: 16.3}})")
    shot("03_loop5_end", "S.map.fitBounds([[S.rc.aoi_corners[0][0], S.rc.aoi_corners[2][1]],[S.rc.aoi_corners[1][0], S.rc.aoi_corners[0][1]]], {padding:30, duration:0}); setLoop(5)")
    shot("04_loop15_end", "setLoop(15)")
    shot("05_loop30_end", f"setLoop({pg.evaluate('S.N')})")
    shot("06_loop30_classes", "document.querySelector('#showClasses').checked = true; applyView()")
    shot("07_zoom_revealed_edge", "document.querySelector('#showClasses').checked = false; applyView(); S.map.jumpTo({center: roverPos(S.rc.loops[2].t0 + 400), zoom: 17.2})")
    shot("08_view_all_data", "S.map.fitBounds([[S.rc.aoi_corners[0][0], S.rc.aoi_corners[2][1]],[S.rc.aoi_corners[1][0], S.rc.aoi_corners[0][1]]], {padding:30, duration:0}); document.querySelector('input[value=all]').click()", wait=3)
    pg.evaluate("document.querySelector('input[value=recon]').click(); setLoop(3)")
    pg.click("#play"); pg.wait_for_timeout(2500)
    shot("09_playing", None, wait=0.2)
    pg.click("#play")
    shot("10_about", "renderAbout(); document.querySelector('#about').showModal()")
    print("errors:", errors)
    br.close()
