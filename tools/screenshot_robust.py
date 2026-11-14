# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Round 7: full-table dialog, robustness section (T6, T7). -> qa/screenshots/T6T7_robustness.png"""
from pathlib import Path
from playwright.sync_api import sync_playwright
APP = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    pg = br.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://127.0.0.1:8765/index.html")
    pg.wait_for_function("window.__mapIdle === true && S.routes", timeout=120000)
    pg.click("#tableBtn"); pg.wait_for_selector("#robust table", timeout=20000)
    pg.evaluate("document.querySelector('#robust').scrollIntoView()"); pg.wait_for_timeout(800)
    pg.screenshot(path=str(APP / "qa/screenshots/T6T7_robustness.png"))
    print("errors:", errors); br.close()
