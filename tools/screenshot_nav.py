# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Top-bar screenshots of every page at several widths (W0 menu check).
python tools/screenshot_nav.py --tag before|after [--port 8765]  -> qa/screenshots/nav_<tag>_<page>_<width>.png
Uses an already-running static server on the port."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8765); ap.add_argument("--tag", required=True)
ap.add_argument("--pages", default="jezero.html,recon.html,data.html")
a = ap.parse_args()
out = APP / "qa" / "screenshots"; out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    for w in (1600, 1280, 1024):
        pg = br.new_page(viewport={"width": w, "height": 700})
        for page in a.pages.split(","):
            pg.goto(f"http://127.0.0.1:{a.port}/{page}")
            pg.wait_for_timeout(2500)
            box = pg.evaluate("(() => { const h = document.querySelector('header#top'); const r = h.getBoundingClientRect();"
                              " const n = h.querySelector('nav#pages'); const nr = n ? n.getBoundingClientRect() : null;"
                              " return {h: r.height, sw: h.scrollWidth, cw: h.clientWidth, sl: h.scrollLeft, nav: nr && [Math.round(nr.left), Math.round(nr.top)]}; })()")
            name = page.replace(".html", "").replace("/", "_") or "root"
            pg.screenshot(path=str(out / f"nav_{a.tag}_{name}_{w}.png"), clip={"x": 0, "y": 0, "width": w, "height": 90})
            print(a.tag, w, page, box)
        pg.close()
    br.close()
