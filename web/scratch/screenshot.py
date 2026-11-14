# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Headless screenshots of the scratch demo (scratch/index.html).
Run from app/:  .conda-env/bin/python web/scratch/screenshot.py [--url http://127.0.0.1:8765]
-> web/scratch/screenshots/{01_scratching,02_analysed,03_playing,04_mobile}.png; prints console errors."""
import argparse
import math
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(); ap.add_argument("--url", default="http://127.0.0.1:8765"); a = ap.parse_args()
out = HERE / "screenshots"; out.mkdir(exist_ok=True)


def zigzag(pg, pts):
    """Drag the mouse along local (x, y) metre points."""
    scr = pg.evaluate("(P) => P.map(([x, y]) => { const p = S.map.project(xyToLL(x, y)); const r = S.map.getCanvasContainer().getBoundingClientRect(); return [p.x + r.left, p.y + r.top]; })", pts)
    pg.mouse.move(*scr[0]); pg.mouse.down()
    for p in scr[1:]:
        pg.mouse.move(*p, steps=6)
    pg.mouse.up()


def idle(pg):
    pg.evaluate("new Promise(r => { const t = setTimeout(() => r(false), 20000); S.map.once('idle', () => { clearTimeout(t); r(true); }); S.map.triggerRepaint(); })")
    pg.wait_for_timeout(400)


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    errors = []

    def page(vp, touch=False):
        pg = br.new_page(viewport=vp, has_touch=touch)
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
        pg.goto(a.url + "/scratch/index.html")
        pg.wait_for_function("window.__ready === true", timeout=60000)
        return pg

    pg = page({"width": 1500, "height": 900})
    # a loop around the habitat and a sweep to the west
    ring = [[260 * math.cos(t / 20 * 2 * math.pi), 260 * math.sin(t / 20 * 2 * math.pi)] for t in range(21)]
    zigzag(pg, [[0, 0]] + ring)
    zigzag(pg, [[-100, 150], [-500, 300], [-800, 200], [-1000, 450], [-700, 650], [-350, 500], [-150, 650]])
    idle(pg); pg.screenshot(path=str(out / "01_scratching.png")); print("saved 01")
    zigzag(pg, [[200, -300], [450, -500], [300, -750], [-50, -600], [-400, -350], [-650, -150], [-900, -50]])
    zigzag(pg, [[-1100, 700], [-1300, 950], [-900, 1050], [-600, 900], [-300, 1000], [0, 850], [300, 600], [450, 300]])
    pg.click(".step[data-step='2']")
    pg.click("#analyse"); pg.wait_for_function("S.analysis != null", timeout=30000)
    print("analysis", pg.evaluate("({...S.analysis, revealed: (100*S.nRev/1440000).toFixed(1), targets: S.targets.map(t => [t.n, Math.round(t.x), Math.round(t.y), +t.score.toFixed(2), t.sites.length])})"))
    idle(pg); pg.screenshot(path=str(out / "02_analysed.png")); print("saved 02")
    pg.click(".step[data-step='3']")
    pg.click("#plan"); pg.wait_for_function("S.plan && S.plan.tl", timeout=30000)
    print("plan", pg.evaluate("({order: S.plan.order, o2Act: Math.round(S.plan.o2Act), o2Plan: Math.round(S.plan.o2Plan), U: S.plan.U, km: (S.plan.dist/1000).toFixed(2), minMargin: Math.round(S.plan.minMarginAct)})"))
    pg.select_option("#speed", "20"); pg.click("#play"); pg.wait_for_timeout(2500)
    pg.evaluate("stop(); setT(S.plan.tl.t.at(-1) * 0.3)")
    idle(pg); pg.wait_for_timeout(700); pg.screenshot(path=str(out / "03_playing.png")); print("saved 03")
    pg.close()

    pm = page({"width": 390, "height": 844}, touch=True)
    pm.evaluate("document.querySelector('#revealAll').click()")
    pm.evaluate("document.querySelector(\".step[data-step='2']\").click(); analyse(); setStep(3); planTour(); setT(S.plan.tl.t.at(-1) * 0.3)")
    idle(pm); pm.wait_for_timeout(700); pm.screenshot(path=str(out / "04_mobile.png"), full_page=True); print("saved 04")
    print("errors:", errors)
    br.close()
