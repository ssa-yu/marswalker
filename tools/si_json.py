# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Add the top-level "si" key to every existing JSON object under web/data and data_work (values untouched; top-level
lists and GeoJSON are left as they are and counted). Skips web/scratch. python tools/si_json.py"""
import json
from pathlib import Path

from pipeline.common import APP, SI_DATA

done = skipped = 0
for root in ("web/data", "data_work"):
    for p in sorted((APP / root).rglob("*.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            skipped += 1; continue
        if not isinstance(d, dict) or d.get("type") in ("FeatureCollection", "Feature"):
            skipped += 1; continue
        if "si" in d:
            continue
        d = {"si": SI_DATA, **d}
        p.write_text(json.dumps(d, indent=1, ensure_ascii=False))
        done += 1
print("si added:", done, "left as is (list/GeoJSON/unreadable):", skipped)
