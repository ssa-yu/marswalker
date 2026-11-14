# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Headless screenshots of web/arcadia.html steps 1-3 -> qa/arcadia/step{1,2,3}.png
python tools/screenshot_arcadia.py [--url http://127.0.0.1:8765]"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--url", default="http://127.0.0.1:8765"); a = ap.parse_args()
out = APP / "qa" / "arcadia"; out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    pg = br.new_page(viewport={"width": 1600, "height": 950})
    errors = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pg.goto(a.url + "/arcadia.html")
    pg.wait_for_function("window.__mapIdle === true", timeout=120000)

    def shot(name, js):
        pg.evaluate(js)
        pg.wait_for_timeout(1200)
        pg.evaluate("new Promise(r => { const t = setTimeout(() => r(false), 30000); S.map.once('idle', () => { clearTimeout(t); r(true); }); S.map.triggerRepaint(); })")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(out / f"{name}.png")); print("saved", name)

    shot("step1_rover", "setStep(1)")
    shot("step2_heat_targets", "setStep(2)")
    shot("step2b_before_all", "S.when='before'; apply(); frame()")
    shot("step3_route", "setStep(3); showCard('整條路線', S.d.route.total)")
    print("errors:", errors)
    br.close()
