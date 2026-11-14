_SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md_

# Use of SI (AI) in this project

**Draft by the tech-lead agent from the project records; every row in the left-hand table is marked "to be checked by Shan" until a person confirms it.** Nothing here is meant to make the AI share look smaller than it was.

Summary (for the "Use of SI" field): the idea — a scout rover goes first, the data it brings back are analysed, and then an astronaut walk is planned that stays within the suit's oxygen, at Jezero, with a "scratch-off" map and the check "treat the data as unknown and see whether the method finds the known answer" — comes from the team (Discord and the team meeting, 13 Nov 2026, before any AI plan). The way to prove it works (route A planned on orbital data vs route B planned after a simulated recon, both checked on HiRISE terrain), nearly all rules and parameters, all code, all tests, the data checks, and the drafts of every document and page text were proposed and produced by AI agents (Anthropic Claude: claude.ai and Claude Code). Several of the agents' rule decisions were made by an AI "manager" agent, with the team able to overrule; Shan made the direction decisions listed below. No image, video or audio is AI-generated; all imagery is NASA data or computed from it by AI-written code, and figures meant for the project page carry a visible SI watermark.

## 1. What people decided (to be checked by Shan)

| Date (2026) | Decision or idea | Who | Evidence |
|---|---|---|---|
| 26 Sep (pre-challenge concept) | "Marswalk" concept: walking routes for astronauts on Mars | Shooyunn | team files (`source/`, Discord); **to be checked by Shan** |
| before 13 Nov | Robot scouts first, then the astronaut EVA is planned (citing Deans et al. 2009) | shoorong | Discord; **to be checked by Shan** |
| 13 Nov, daytime | "The robot scouts first, brings data back for analysis, then we plan the astronaut's path"; Jezero chosen | team | Discord export, 13 Nov; **to be checked by Shan** |
| 13 Nov, evening meeting | Three steps; out one way, back another; several loops; autonomous return; scouting ahead; **scratch-off map**; "treat the data as unknown and see whether we find the known answer"; explore beyond the original traverse; ML extrapolation with train/test split; oxygen "health bar" | team meeting | Notion meeting notes (written 2026-11-13T18:43Z); **to be checked by Shan** |
| 14 Nov | Start implementation now; no schedule cuts | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | Any NASA data may be used, not only the challenge Resources; downloads over 2 GB approved | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | Project skeleton = the three steps; step 2's target not fixed to water/ice | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | Arcadia dropped, Jezero is the main scene | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | AI4MARS terrain classification to be done; HUD and old prototypes not in the product | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | Step 2 = option A (SuperCam chemistry groups), as a switchable feature | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | Rover to use classic, published exploration methods instead of a home-made rule | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | Interactive scratch-off demo page | Shan | `team/decisions.md`; **to be checked by Shan** |
| 14 Nov | AI4MARS option (b) with HiRISE as the input, CTX as the comparison | Shan | `team/decisions.md`; **to be checked by Shan** |
| throughout | Veto and release points (page release, sand check sheets, repo publication, submission) | Shan / team | `team/direction.md` "需要人放行"; **to be checked by Shan** |

## 2. What AI proposed or produced

| Date (2026) | What | AI | Evidence |
|---|---|---|---|
| 13 Nov, late night | `MVP_PLAN` implementation plan; it states that the team had decided only three directions and that the rest of the design, parameters, algorithms and schedule were Claude's proposals: the route A vs B comparison, the prior/reference (CTX vs HiRISE) design, terrain classes and cost model, the measured / derived / assumed / simulated labels | claude.ai | `team/plans/MVP_PLAN.md` |
| 13–15 Nov | Four Claude Code agents with roles: **manager** (decides rules, priorities and what is locked; reviews the other agents; the team can overrule), **tech-lead** (all code, data checks, runs, documents), **shan-proxy** (proposes ideas "as Shan might think"; proposals go to the manager), **data-curator** (collects and summarises team files, Discord, downloads) | Claude Code | `CLAUDE.md` (team table), `team/` |
| 13–15 Nov | Rules and parameters: positioning thresholds (X3), slope/roughness thresholds, the sand texture rule, hazard zones and crossings, test-point lattice, rover goal rules v1–v3 (v3 from published methods the agents selected), budgets and costs, multi-window rule and statistics, step-2 options A–D and the locked option-A rules, round-7 definitions, the AI4MARS check rules, the gap rule — proposed by tech-lead and/or decided by manager, written into `DATA_LOG.md` before each run | manager, tech-lead | `DATA_LOG.md`, `team/decisions.md`, `team/plans/TECH_LEAD_BRIEF.md` |
| 13–15 Nov | All code in `pipeline/`, `tests/`, `tools/`, `spikes/` and `web/` (except the third-party MapLibre library in `web/lib/`) | tech-lead (`web/scratch/`: a second tech-lead agent) | file headers; git history |
| 13–15 Nov | Data discovery and checks (STAC, PDS, AI4MARS subset, downloads), the data summary table | tech-lead, data-curator | `DATA_LOG.md`, `team/reports/` |
| 13–15 Nov | Drafts of README, PROJECT_PAGE, About/Limitations, page text, this file | tech-lead, manager | file headers |
| 13–15 Nov | Literature search for the rover methods and the citations | a research agent, tech-lead | `team/tech/exploration-algorithms.md`, `docs/REFERENCES.md` |

## 3. Labels in the project

- Every source file starts with the line `SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md`.
- Every JSON output has a top-level `"si"` field saying it was computed by AI-written code from NASA data. NumPy arrays (`.npz`) are listed in the `DATA_LOG.md` data table instead.
- Figures and screenshots for the project page or slides are copied to `qa/submission/` with a visible watermark (`Made with AI-written code · data: NASA/JPL-Caltech/UArizona/MSSS/USGS · see AI_USE`) and the same sentence in the PNG `SI` text field (`tools/si_watermark.py`). Perseverance raw images are NASA data, not generated: no watermark, credit kept.
- No NASA logo, flag or mission insignia is used in anything the project generated; text credits are data attributions.

## 4. What AI did not do

- No AI-generated imagery, video or audio.
- No language model makes decisions inside the product: rover goals, routes, groups and numbers come from fixed, documented rules in `pipeline/`.
- The scout rover is simulated; ground measurements and photos are Perseverance's and are never presented as our rover's.
