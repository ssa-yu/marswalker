# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Launcher for pipeline.noahh_check under `python -I` (isolated mode; NOAH-H files are untrusted data).
.conda-env/bin/python -I tools/noahh_run.py <stage>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import noahh_check  # noqa: E402

{"invariants": noahh_check.stage_invariants, "names": noahh_check.stage_names, "align": noahh_check.stage_align,
 "metrics": noahh_check.stage_metrics, "figures": noahh_check.stage_figures}[sys.argv[1]]()
