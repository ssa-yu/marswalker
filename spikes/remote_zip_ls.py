"""List (and optionally extract) members of a remote ZIP using HTTP range requests (no full download).
Usage: python remote_zip_ls.py URL [--grep PATTERN] [--extract REGEX OUTDIR]"""
import io, re, sys, urllib.request, zipfile, os
UA = {}  # extra headers (none); note pubs.usgs.gov answers 403 to the default Python-urllib UA, use curl for it
class HTTPRangeFile(io.RawIOBase):
    def __init__(self, url):
        r = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60)
        self.url, self.size, self.pos = r.geturl(), int(r.headers["Content-Length"]), 0
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos
    def read(self, n=-1):
        if n < 0: n = self.size - self.pos
        if n == 0 or self.pos >= self.size: return b""
        end = min(self.pos + n, self.size); out = bytearray()
        while self.pos < end:  # fetch in <=4 MB ranges with retries (Zenodo drops long transfers)
            e = min(self.pos + (4 << 20), end) - 1
            for attempt in range(6):
                try:
                    rq = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{e}", **UA})
                    b = urllib.request.urlopen(rq, timeout=300).read(); break
                except Exception:
                    if attempt == 5: raise
            out += b; self.pos += len(b)
        return bytes(out)
    def readinto(self, b):
        d = self.read(len(b)); b[:len(d)] = d; return len(d)
url = sys.argv[1]
f = io.BufferedReader(HTTPRangeFile(url), buffer_size=1 << 20)
z = zipfile.ZipFile(f)
pat = sys.argv[sys.argv.index("--grep") + 1] if "--grep" in sys.argv else None
for i in z.infolist():
    if pat is None or re.search(pat, i.filename, re.I):
        print(f"{i.file_size:>12} {i.compress_size:>12} {i.filename}")
if "--extract" in sys.argv:
    k = sys.argv.index("--extract"); rx, out = sys.argv[k + 1], sys.argv[k + 2]
    for i in z.infolist():
        if re.search(rx, i.filename, re.I) and not i.is_dir():
            z.extract(i, out); print("extracted", i.filename)
