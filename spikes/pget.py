# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Parallel HTTP range downloader (resumable per chunk). Stdlib only.
Usage: python pget.py URL OUT [--conns 16] [--chunk-mb 8]"""
import argparse, os, threading, time, urllib.request, queue
p = argparse.ArgumentParser(); p.add_argument("url"); p.add_argument("out")
p.add_argument("--conns", type=int, default=16); p.add_argument("--chunk-mb", type=int, default=8)
a = p.parse_args()
req = urllib.request.Request(a.url, method="HEAD")
with urllib.request.urlopen(req, timeout=60) as r:
    size = int(r.headers["Content-Length"]); final = r.geturl()
CH = a.chunk_mb * 1024 * 1024
parts_dir = a.out + ".parts"; os.makedirs(parts_dir, exist_ok=True)
q = queue.Queue()
for i, s in enumerate(range(0, size, CH)):
    e = min(s + CH, size) - 1
    fn = os.path.join(parts_dir, f"{i:06d}")
    if not (os.path.exists(fn) and os.path.getsize(fn) == e - s + 1): q.put((i, s, e, fn))
done_bytes = [sum(os.path.getsize(os.path.join(parts_dir, f)) for f in os.listdir(parts_dir))]
lock = threading.Lock(); t0 = time.time()
def worker():
    while True:
        try: i, s, e, fn = q.get_nowait()
        except queue.Empty: return
        for attempt in range(6):
            try:
                rq = urllib.request.Request(final, headers={"Range": f"bytes={s}-{e}"})
                with urllib.request.urlopen(rq, timeout=120) as r, open(fn + ".tmp", "wb") as f:
                    while True:
                        b = r.read(1 << 16)
                        if not b: break
                        f.write(b)
                        with lock: done_bytes[0] += len(b)
                if os.path.getsize(fn + ".tmp") == e - s + 1:
                    os.replace(fn + ".tmp", fn); break
            except Exception as ex:
                time.sleep(2 * (attempt + 1))
def report():
    while any(t.is_alive() for t in ts):
        time.sleep(15); el = time.time() - t0
        print(f"{done_bytes[0]/1e6:.1f}/{size/1e6:.1f} MB  {done_bytes[0]/max(el,1)/1e3:.0f} KB/s avg(incl. resumed)", flush=True)
ts = [threading.Thread(target=worker) for _ in range(a.conns)]
for t in ts: t.start()
threading.Thread(target=report, daemon=True).start()
for t in ts: t.join()
n = (size + CH - 1) // CH
missing = [i for i in range(n) if not os.path.exists(os.path.join(parts_dir, f"{i:06d}"))]
if missing: raise SystemExit(f"missing chunks {missing[:10]}... rerun to resume")
with open(a.out, "wb") as out:
    for i in range(n):
        with open(os.path.join(parts_dir, f"{i:06d}"), "rb") as f: out.write(f.read())
for f in os.listdir(parts_dir): os.remove(os.path.join(parts_dir, f))
os.rmdir(parts_dir)
print(f"done {size/1e6:.1f} MB in {time.time()-t0:.0f}s -> {a.out}")
