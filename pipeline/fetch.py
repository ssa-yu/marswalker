"""S1 fetch: download / window-read every source listed in the scene config into data_raw/<scene>/.

python -m pipeline.fetch --scene jezero [--only ortho,dtm_fine]
"""
from __future__ import annotations

import argparse
import shutil
import time

from .common import APP, Scene, log, read_json, write_json
from . import remote


def fetch_source(sc: Scene, sid: str) -> dict:
    s = sc.source(sid)
    out = sc.raw_path(sid)
    if out.exists():
        return {"id": sid, "url": s["url"], "path": str(out.relative_to(APP)), "bytes": out.stat().st_size, "cached": True}
    cache = s.get("cache")
    if cache and (APP / cache).exists():
        shutil.copyfile(APP / cache, out)
        return {"id": sid, "url": s["url"], "path": str(out.relative_to(APP)), "bytes": out.stat().st_size,
                "copied_from": cache}
    kind = s["kind"]
    t0 = time.time()
    if kind == "download":
        rec = remote.download(s["url"], out)
    elif kind in ("cog_window", "strip_window"):
        b = sc.grid.src_bounds(*sc.extent(s.get("extent", "fetch")))
        fn = remote.cog_window if kind == "cog_window" else remote.strip_window
        rec = fn(s["url"], b, out)
    else:
        raise ValueError(f"unknown kind {kind}")
    rec.update(id=sid, path=str(out.relative_to(APP)), wall_seconds=round(time.time() - t0, 1),
               fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return rec


def run(scene: str, only=None):
    sc = Scene(scene)
    logp = sc.raw / "fetch_log.json"
    book = read_json(logp) if logp.exists() else {}
    for sid in sc.cfg["sources"]:
        if only and sid not in only:
            continue
        log(scene, "fetch", f"{sid} ...")
        rec = fetch_source(sc, sid)
        if not rec.get("cached") or sid not in book:
            book[sid] = rec
        log(scene, "fetch", f"{sid} -> {rec.get('path')} {rec.get('fetched_bytes', rec.get('bytes'))} B "
                            f"{rec.get('wall_seconds', 0)} s")
        write_json(logp, book)
    return book


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--only")
    a = ap.parse_args()
    run(a.scene, set(a.only.split(",")) if a.only else None)
