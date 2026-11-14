# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Headless screenshots of the astronaut map (jezero.html: route A vs B on reference terrain).
python tools/screenshot_astronaut.py [--url http://127.0.0.1:8765]  -> qa/screenshots/T3_walk_*.png"""
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
    pg.goto(a.url + "/jezero.html")
    pg.wait_for_function("window.__mapIdle === true && S.routes", timeout=120000)
    print("loaded in", round(time.time() - t0, 2), "s")

    def shot(name, js=None, wait=1.0):
        if js:
            pg.evaluate(js)
        pg.wait_for_timeout(int(wait * 1000))
        pg.evaluate("new Promise(r => { const t = setTimeout(() => r(false), 20000); S.map.once('idle', () => { clearTimeout(t); r(true); }); S.map.triggerRepaint(); })")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(out / f"T3_walk_{name}.png")); print("saved", name)

    shot("01_first_view")
    shot("02_routeA_midwalk", "S.route='A'; document.querySelector('#rSel').value='A'; setT(cur().act_t.at(-1) * 0.4)")
    shot("03_routeB_midwalk", "S.route='B'; document.querySelector('#rSel').value='B'; drawRoutes(); setT(cur().act_t.at(-1) * 0.4)")
    shot("04_rover_seen_loop5", "document.querySelector('#showSeen').click(); S.k=5; refresh()")
    shot("05_west_target_bracket", "document.querySelector('#showAp').click(); document.querySelector('#showRef').click(); S.k=30; "
         "selectTarget(S.C.rows.findIndex(r => r.x === -600 && r.y === 0))", 2.0)
    shot("06_full_table", "renderTable(); document.querySelector('#table').showModal()")
    pg.evaluate("document.querySelector('#table').close()")
    shot("07_about", "renderAbout(); document.querySelector('#about').showModal()")
    print("errors:", errors)
    br.close()
