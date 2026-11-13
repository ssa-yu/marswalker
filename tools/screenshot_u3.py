"""Round 7 U1-U3 screenshots: first view with the shortcut buttons, the three shortcut walks, the per-point table.
python tools/screenshot_u3.py [--url http://127.0.0.1:8765] -> qa/screenshots/U3_*.png"""
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
    pg.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pg.goto(a.url + "/index.html")
    pg.wait_for_function("window.__mapIdle === true && S.routes", timeout=120000)

    def shot(name, js=None, wait=1.5):
        if js:
            pg.evaluate(js)
        pg.wait_for_timeout(int(wait * 1000))
        pg.screenshot(path=str(out / f"U3_{name}.png")); print("saved", name)

    shot("01_first_view")
    for k in ("median", "most_improved", "most_worsened"):
        shot(f"02_{k}", f"document.querySelector('#shortcuts button[data-sc={k}]').click()", 2.5)
    shot("03_full_table_pointwise", "renderTable(); document.querySelector('#table').showModal(); "
         "document.querySelector('#tableBody h3:nth-last-of-type(1)')?.scrollIntoView()")
    print("console errors:", errors)
    br.close()
