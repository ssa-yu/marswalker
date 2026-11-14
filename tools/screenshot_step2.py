# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Step-2 / round-7 screenshots on the astronaut page (server on --port must be running).
python tools/screenshot_step2.py -> qa/screenshots/W1_*.png"""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8765); a = ap.parse_args()
out = APP / "qa" / "screenshots"
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    pg = br.new_page(viewport={"width": 1600, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(f"http://127.0.0.1:{a.port}/index.html"); pg.wait_for_timeout(5000)
    pg.evaluate("document.querySelector('#step2').scrollIntoView()")
    pg.evaluate("document.querySelector('#s2Stops button') && document.querySelector('#s2Stops button').click()"); pg.wait_for_timeout(2500)
    pg.screenshot(path=str(out / "W1_01_step2_unlocked_card.png")); print("saved 1")
    pg.evaluate("document.querySelector('#round7').scrollIntoView()"); pg.wait_for_timeout(800)
    pg.screenshot(path=str(out / "W2_01_round7_table_i.png")); print("saved 2")
    pg.evaluate("document.querySelector('#s2Mode button[data-ds=ii]').click()"); pg.wait_for_timeout(1500)
    pg.evaluate("document.querySelector('#step2').scrollIntoView()"); pg.wait_for_timeout(1500)
    pg.screenshot(path=str(out / "W1_02_step2_view_all_data.png")); print("saved 3")
    pg.evaluate("document.querySelector('#round7').scrollIntoView()"); pg.wait_for_timeout(800)
    pg.screenshot(path=str(out / "W2_02_round7_table_ii.png")); print("saved 4")
    print("errors:", errs)
    br.close()
