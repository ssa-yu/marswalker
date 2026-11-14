_SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md_

# AI use

This project was built with AI coding agents (Anthropic Claude, via Claude Code) working under the team's direction. One agent acted as the technical lead (code, data checks, documents); another reviewed proposals and made the rule decisions that the team had not yet made, marked as such and open to the team's veto.

| What | AI role | Human role |
|---|---|---|
| Data discovery and feasibility checks (STAC queries, file structure, download speed tests, PDS labels) | Agent ran the queries and wrote the findings | Team decides direction, site and which data to use |
| Pipeline code (`pipeline/`), tests (`tests/`) and web pages (`web/`) | Written by the agent | Team reviews the pages before release |
| Positioning checks (X3) and their thresholds | Agent proposed thresholds and computed the checks | Thresholds locked before any route numbers existed |
| Terrain classes, especially sand | Agent wrote the texture rule and the random check sheets | **Pending human sign-off**: until a person reviews the check sheets, every output that depends on the classes is labelled "heuristic, not yet reviewed" |
| Rover goal rule, comparison definitions (route A vs B, hazard zones, crossings, test points) | Agent drafted; written into `DATA_LOG.md` before each run | Rules locked before the numbers; nothing was tuned after seeing them |
| Text on the pages (English UI, About, Limitations) and these documents | Drafted by the agent | Team edits |

What AI did not do:

- No AI-generated imagery. Every image and terrain shown is NASA mission data or a value computed from it, and every layer and number is labelled measured / derived / assumed / simulated.
- No language model makes any decision inside the product: rover goals, routes and numbers come from fixed, documented rules (`pipeline/`).
- The scout rover is simulated; ground measurements and photos are Perseverance's and are never presented as our rover's.
