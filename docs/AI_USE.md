# AI use

This project was built with AI coding agents (Anthropic Claude, via Claude Code) working under the team's direction.

| What | AI role | Human role |
|---|---|---|
| Data discovery and feasibility checks (STAC queries, file structure, download speed tests) | Agent ran the queries and wrote the findings | Team decides direction and which sites to use |
| Pipeline code (`pipeline/`) and web viewer (`web/`) | Written by the agent | Team reviews; positioning check images need human sign-off (marked "heuristic, not yet reviewed" until then) |
| Positioning checks and their thresholds | Agent proposed thresholds and computed the checks | Thresholds locked by the team before any route numbers were produced |
| Text on the page (English UI, About, Limitations) | Drafted by the agent | Team edits |

No AI-generated imagery is used. All images and terrain shown are NASA mission data or values computed from them; every layer is labelled measured / derived / assumed / simulated.
