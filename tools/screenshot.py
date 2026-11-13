"""Headless screenshots of the viewer (uses the installed Google Chrome through Playwright).
python tools/screenshot.py [--port 8765]   -> qa/screenshots/*.png, prints load timing per scene."""
import argparse, json, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

APP = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=8765); a = ap.parse_args()
out = APP / "qa" / "screenshots"; out.mkdir(parents=True, exist_ok=True)
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(a.port), "--directory", str(APP / "web")],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.0)
scenes = json.loads((APP / "web/data/scenes.json").read_text())["scenes"]
timing = {}
try:
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome", headless=True)
        pg = br.new_page(viewport={"width": 1600, "height": 950})
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        def shot(name, setup=None, wait=2.5):
            if setup: pg.evaluate(setup)
            pg.wait_for_timeout(int(wait * 1000))
            pg.evaluate("new Promise(r => { const t = setTimeout(() => r(false), 60000); S.map.once('idle', () => { clearTimeout(t); r(true); }); S.map.triggerRepaint(); })")
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(out / f"{name}.png")); print("saved", name)
        for sc in scenes:
            sid = sc["id"]; t0 = time.time()
            pg.goto(f"http://localhost:{a.port}/data.html#{sid}")
            pg.wait_for_function("window.__mapIdle === true", timeout=120000)
            timing[sid] = round(time.time() - t0, 2)
            shot(f"{sid}_01_default")
            shot(f"{sid}_02_reference_hillshade", "document.querySelector('[data-preset=ref]').click()")
            shot(f"{sid}_03_prior_hillshade", "document.querySelector('[data-preset=prior]').click()")
            shot(f"{sid}_04_swipe", "document.querySelector('[data-preset=swipe]').click()")
            pg.evaluate("setSwipe(false); setVis('hirise_ortho', true); setVis('hirise_slope', true); setVis('ctx_slope', false)")
            shot(f"{sid}_05_slope_reference")
            pg.evaluate("setVis('hirise_slope', false); setVis('hirise_ortho', false); setVis('ctx_slope', true); setOp('ctx_slope',1)")
            shot(f"{sid}_06_slope_prior")
            pg.evaluate("['ctx_slope','hirise_hillshade','ctx_hillshade','hirise_slope'].forEach(i => setVis(i, false)); setVis('hirise_ortho', true); setVis('ctx_ortho', true)")
            if sc["id"] == "jezero":
                pg.evaluate("S.map.jumpTo({center:[S.scene.base.lon, S.scene.base.lat], zoom: 17.2})")
                shot(f"{sid}_07_landing_zoom_traverse")
                pg.evaluate("setVis('post_landing', true)")
                shot(f"{sid}_08_post_landing_tracks")
                pg.evaluate("setVis('post_landing', false); S.map.fitBounds([[S.scene.aoi.corners[0][0], S.scene.aoi.corners[2][1]],[S.scene.aoi.corners[1][0], S.scene.aoi.corners[0][1]]], {padding:30, duration:0}); openPhotos(S.photos.waypoints[Math.floor(S.photos.waypoints.length/3)].id)")
                shot(f"{sid}_09_photo_panel", wait=4)
                pg.evaluate("document.querySelector('#photoClose').click(); S.map.setZoom(8.5)")
                shot(f"{sid}_10_regional_context", wait=3)
            pg.evaluate("document.querySelector('#checks').scrollIntoView()")
            shot(f"{sid}_12_checks_panel", wait=0.5)
            pg.evaluate("renderAbout(); document.querySelector('#about').showModal()")
            shot(f"{sid}_11_about", wait=1)
            pg.evaluate("document.querySelector('#about').close()")
        # offline check: block every non-localhost request and reload
        ctx = br.new_context(viewport={"width": 1600, "height": 950}); pg2 = ctx.new_page()
        ext = []
        def route(r):
            if r.request.url.startswith(f"http://localhost:{a.port}/"): r.continue_()
            else: ext.append(r.request.url); r.abort()
        pg2.route("**/*", route)
        pg2.goto(f"http://localhost:{a.port}/data.html#{scenes[0]['id']}")
        pg2.wait_for_function("window.__mapIdle === true", timeout=120000); pg2.wait_for_timeout(2000)
        pg2.screenshot(path=str(out / "offline_check.png"))
        print("timing (s, page load to first map idle):", timing)
        print("external requests attempted while offline:", len(ext), ext[:5])
        print("console errors:", errors[:10])
        br.close()
finally:
    srv.terminate()
