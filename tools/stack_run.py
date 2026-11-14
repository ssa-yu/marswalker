# SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
"""Launcher for pipeline.stack_check under `python -I` (isolated mode; Stack 2020 files are untrusted data).
.conda-env/bin/python -I tools/stack_run.py <stage>"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import stack_check  # noqa: E402

{"invariants": stack_check.stage_invariants, "align": stack_check.stage_align,
 "metrics": stack_check.stage_metrics, "figures": stack_check.stage_figures}[sys.argv[1]]()
