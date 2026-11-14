# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Headless screenshots of web/arcadia.html steps 1-3 (+ zoomed-out context views) -> qa/arcadia/step*.png
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
    shot("step2c_mask_off", "document.querySelector('#lyrMask').checked = false; apply()")
    pg.evaluate("document.querySelector('#lyrMask').checked = true")
    shot("step1_loop3_mask", "setStep(1); S.loop = 3; document.querySelector('#loop').value = 3; apply()")
    shot("step3_route", "setStep(3); showCard('整條路線', S.d.route.total)")
    # in-browser plan from the habitat vs the Python plan (same rule, 8 m vs 4 m grid)
    cmp = pg.evaluate("""() => { const b = toXY(S.d.base); let i = xyToIdx(b[0], b[1]);
        if (!isFinite(S.cost.K[i])) i = nearestPassable(b[0], b[1]);
        const p = planFrom(i), t = S.d.route.total;
        return { js: { ...p.total, visited: p.visited, ms: p.ms }, py: { ...t, visited: S.d.route.order } }; }""")
    print("js vs python from base:", cmp)
    shot("step3_moved_start", "setStep(3); setStart(toLL(-600, 2600)); "
         "S.map.fitBounds([[Math.min(...S.plan.legs.flatMap(L => L.path).map(p => p[0])) - 0.004, Math.min(...S.plan.legs.flatMap(L => L.path).map(p => p[1])) - 0.004], "
         "[Math.max(...S.plan.legs.flatMap(L => L.path).map(p => p[0])) + 0.004, Math.max(...S.plan.legs.flatMap(L => L.path).map(p => p[1])) + 0.004]], { duration: 0 })")
    print("moved start plan ms:", pg.evaluate("window.__lastPlanMs"), pg.evaluate("({ n: S.plan.n_stops, v: S.plan.visited, t: S.plan.total })"))
    far = pg.evaluate("""() => { const t = S.d.targets.after.filter((t) => !(S.plan.rt[t.id] <= S.d.planner.usable_kcal)); return t.length; }""")
    print("dashed areas from the moved start:", far)
    pg.evaluate("document.querySelector('#home').click()")
    shot("step1_zoomed_out", "setStep(1); S.map.jumpTo({ center: S.d.centre, zoom: 10.3 })")
    shot("step1_regional", "setStep(1); S.map.jumpTo({ center: S.d.centre, zoom: 7.6 })")
    print("errors:", len(errors), errors[:5])
    br.close()
