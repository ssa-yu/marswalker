"""Headless screenshots of the step-3 skeleton page (installed Google Chrome through Playwright).
python tools/screenshot_astronaut.py [--url http://127.0.0.1:8765]  -> qa/screenshots/S5_astronaut_*.png"""
import argparse
import json
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
    pg.goto(a.url + "/astronaut.html")
    pg.wait_for_function("window.__mapIdle === true && S.plan && S.parity", timeout=120000)
    print("loaded in", round(time.time() - t0, 2), "s; parity", json.dumps(pg.evaluate("S.parity")))

    def shot(name, js=None, wait=0.8):
        if js:
            pg.evaluate(js)
        pg.wait_for_timeout(int(wait * 1000))
        pg.screenshot(path=str(out / f"S5_astronaut_{name}.png")); print("saved", name)

    shot("01_default_start")
    shot("02_default_midwalk", "setT(S.plan.time * 0.55)")
    shot("03_low_oxygen", "document.querySelector('#cap').value = 120; document.querySelector('#cap').dispatchEvent(new Event('input')); setT(S.plan.time * 0.6)")
    print("low-O2 plan:", pg.evaluate("({order: S.plan.order, skipped: S.plan.skipped, o2: S.plan.o2, U: S.plan.U, min: S.plan.minMargin})"))
    shot("04_near_end_warning", "document.querySelector('#cap').value = 90; document.querySelector('#cap').dispatchEvent(new Event('input')); setT(S.plan.T[S.plan.T.length - 3])")
    pg.click("#play"); pg.wait_for_timeout(1500)
    shot("05_playing", None, 0.1)
    pg.click("#play")
    shot("06_about", "renderAbout(); document.querySelector('#about').showModal()")
    print("errors:", errors)
    br.close()
