# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Add the one-line SI notice to the top of every tracked .py/.js/.html/.css/.md file (third-party web/lib and the
separately owned web/scratch are skipped), idempotent. python tools/si_headers.py"""
import subprocess
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SI = "SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md"
files = subprocess.run(["git", "ls-files"], cwd=APP, capture_output=True, text=True).stdout.split()
n = 0
for f in files:
    if f.startswith(("web/lib/", "web/scratch/")) or not f.endswith((".py", ".js", ".html", ".css", ".md")):
        continue
    p = APP / f
    s = p.read_text()
    if SI in s[:600]:
        continue
    if f.endswith(".py"):
        s = f"# {SI}\n" + s
    elif f.endswith(".js"):
        s = f"// {SI}\n" + s
    elif f.endswith(".css"):
        s = f"/* {SI} */\n" + s
    elif f.endswith(".html"):
        i = s.lower().find("<!doctype")
        j = s.find(">", i) + 1 if i >= 0 else 0
        s = s[:j] + f"\n<!-- {SI} -->" + s[j:] if i >= 0 else f"<!-- {SI} -->\n" + s
    elif f.endswith(".md"):
        s = f"_{SI}_\n\n" + s
    p.write_text(s); n += 1
print("headers added:", n)
