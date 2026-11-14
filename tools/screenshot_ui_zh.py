# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""UI simplification / zh-TW interface check: one screenshot per page (+ About, + scratch step 3), console errors.
python tools/screenshot_ui_zh.py --tag before|after [--port 8765] [--lang zh|en]
-> qa/screenshots/ui_zh_<tag>_<page>.png. Uses an already-running static server on the port."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8765); ap.add_argument("--tag", required=True)
ap.add_argument("--lang", default="")
a = ap.parse_args()
out = APP / "qa" / "screenshots"; out.mkdir(parents=True, exist_ok=True)
base = f"http://127.0.0.1:{a.port}/"
q = f"?lang={a.lang}" if a.lang else ""
sfx = f"_{a.lang}" if a.lang else ""
errors = {}


def open_page(br, path, ready, vp=(1440, 900)):
    pg = br.new_page(viewport={"width": vp[0], "height": vp[1]})
    errs = errors.setdefault(path, [])
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pg.goto(base + path + q)
    pg.wait_for_function(ready, timeout=60000)
    pg.wait_for_timeout(1500)
    return pg


def shot(pg, name):
    p = out / f"ui_zh_{a.tag}{sfx}_{name}.png"
    pg.screenshot(path=str(p)); print("saved", p.name)


def about(pg, name):
    pg.click("#aboutBtn"); pg.wait_for_timeout(400); shot(pg, name)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)


with sync_playwright() as p:
    br = p.chromium.launch(channel="chrome", headless=True)
    pg = open_page(br, "jezero.html", "window.__mapIdle === true && document.querySelector('#cmp table') !== null")
    pg.wait_for_timeout(1500)
    shot(pg, "index"); about(pg, "index_about")
    pg.click("#tableBtn"); pg.wait_for_timeout(1200); shot(pg, "index_table")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.evaluate("document.querySelector('#s2Stops button') && document.querySelector('#s2Stops button').click()")
    pg.wait_for_timeout(600)
    pg.evaluate("document.querySelector('#step2') && document.querySelector('#step2').scrollIntoView()")
    pg.wait_for_timeout(300); shot(pg, "index_step2")
    pg.close()
    pg = open_page(br, "recon.html", "window.__mapIdle === true")
    shot(pg, "recon")
    pg.evaluate("setLoop(S.N)"); pg.wait_for_timeout(1200); shot(pg, "recon_loop30"); about(pg, "recon_about")
    pg.close()
    pg = open_page(br, "data.html", "window.__mapIdle === true")
    shot(pg, "data"); about(pg, "data_about")
    pg.close()
    pg = open_page(br, "scratch/index.html", "window.__ready === true")
    shot(pg, "scratch")
    pg.evaluate("document.querySelector('#revealAll').click()")
    pg.evaluate("setStep(2); analyse(); setStep(3); planTour(); setT(S.plan.tl.t.at(-1) * 0.3)")
    pg.wait_for_timeout(1500); shot(pg, "scratch_walk")
    pg.close()
    br.close()
for k, v in errors.items():
    print("errors", k, v)
