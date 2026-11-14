_SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md_

# Submission fields: fact list (not finished text)

For the team to write the eight submission fields in their own words. Facts and numbers only, copied from `README.md`, `DATA_LOG.md`, `docs/REFERENCES.md` and `docs/AI_USE.md`. Nothing here is meant to be pasted as is. All numbers: oxygen in nominal minutes (1 = one minute of walking on firm ground; usable 384 = 480 with 20 % reserve).

## 1. Project Name
- Working name: Marswalk Recon (team to confirm).

## 2. High-Level Project Summary (what, how it answers the challenge, why it matters)
- Challenge: Interplanetary Survival Guide: Martian Map. Product: a layered map and walk planner for astronauts at Jezero Crater.
- Three steps: (1) a simulated scout rover explores from the habitat in loops and reveals fine terrain ("scratch-off" map); (2) Perseverance SuperCam chemistry is grouped and candidate stops are proposed; (3) an astronaut walk is planned within the suit's oxygen and checked on HiRISE terrain.
- Main result (version-2 rover, pre-registered, 63 test points): planning from orbital data alone: planned 50.8, actual 194.6 (3.8×); after recon (30 loops, 11.3 % of the area seen): 251 m less hazard terrain and 28.2 less oxygen per walk = 25 % of what perfect knowledge would save; plan still underestimates by 108 (58 vs 167).
- Six 2.4 km windows of the same HiRISE mosaic (rule fixed in advance): all six in the same direction; 22–47 % of the possible oxygen gain per window.
- Rover with published exploration methods (version 3; designed after version 2): 15.2 % seen, 46 % of the possible oxygen gain, still underestimates by 48.
- Why it matters (team to phrase): orbital data at 20 m cannot see the sand that covers ~40 % of the area; a recon changes how much oxygen a walk really needs.

## 3. Link to Project Demo
- Placeholder: 7-slide deck or 30 s video (to be made by the team; not started).
- Usable material: watermarked screenshots in `qa/submission/`.

## 4. Link to Final Project
- Placeholder: GitHub repository (public?) and GitHub Pages (static site, no backend) — waiting for Shan.

## 5. Detailed Project Description (what, how, benefits, goals, tools and languages)
- What: astronaut map (route A vs B, walk replay, two return-margin bars), rover recon replay, map-data page, step-2 cards, walk to all candidate stops, interactive demo page.
- How: offline Python pipeline → static files; web pages in plain HTML + JavaScript with a local MapLibre copy.
- Terrain: HiRISE 1 m DTM + 0.25 m image → firm / rough / sand / blocked on a 2 m grid (sand rule heuristic, awaiting a person's sign-off); prior = CTX 20 m.
- Rover: energy budget 4,000 per loop, sand ×6, 15 m sensing, 30 loops; hard rule to keep energy to get home over seen ground.
- Step 2: SuperCam LIBS 8 oxides ÷ RMSEP, Ward clustering, number of groups by a fixed rule; candidate stops = most typical and most unusual target per group; positions from the rover's site/drive.
- Checks: AI4MARS volunteer labels vs our sand class (ρ 0.55; 69 / 72 waypoints agree on "sand-dominant"; consistency with crowd labels, not validation); a model predicting photo sand from orbit did not beat the hand-written rule (negative result).
- Honesty: every number labelled measured / derived / assumed / simulated; Limitations in README and on the page; rules written before each run (`DATA_LOG.md`).
- Tools and languages: Python (NumPy, SciPy, scikit-image, scikit-learn, rasterio/GDAL, Shapely, Pillow, Matplotlib, pytest, Playwright), JavaScript, HTML/CSS, MapLibre GL JS.

## 6. Use of Super Intelligence (SI)
- Source: `docs/AI_USE.md` (table of what people decided — to be checked by Shan — and what AI proposed or produced). The field is not shown to judges but must match the labels in the project.

## 7. NASA Data (each item)
- HiRISE orthoimage 0.25 m and DTM 1 m mosaics (Mars 2020 TRN; MRO HiRISE, USGS Astrogeology) — reference terrain.
- HiRISE ESP_071077_1985 (2021-09-24) — position check (parked Perseverance vs waypoint, 2.0 m).
- CTX DTM 20 m and orthoimage 6 m mosaics (Mars 2020 TRN; MRO CTX, USGS) — orbital prior.
- MOLA 463 m DEM and MOLA PEDR laser shots (MGS MOLA; USGS, PDS Geosciences Node) — elevation checks.
- THEMIS Day IR and MOLA/HRSC hillshade tiles via NASA JPL Mars Trek (challenge Resource) — regional basemaps.
- USGS SIM 3464 Jezero geologic map (USGS-NASA Planetary Geologic Mapping; challenge Resource) — layer and step-2 evidence.
- Perseverance waypoints and traverse (Mars 2020, NASA JPL MMGIS) — positions, habitat at the landing site.
- Perseverance Raw Images, Navcam / Front Hazcam / Mastcam-Z (challenge Resource) — 478 photos on the map and on step-2 cards.
- Perseverance SuperCam LIBS major oxides and observation masterlist (PDS Geosciences Node) — step 2.
- Perseverance sample list (NASA Science) — descriptive check against sampling sites.
- AI4MARS Perseverance NAV labels (NASA JPL; Zenodo 15995036) — consistency check.
- Checked but not in the results: CRISM MTRDR (failed registration), JPL Horizons (Sun positions), SWIM ice maps and Arcadia data (paused site).

## 8. Space Agency Partner Data and Other References
- Partner-agency data: HRSC (ESA Mars Express) in the Mars Trek MOLA/HRSC hillshade basemap.
- Non-NASA data: Deahn et al. 2026 crater-rim map (Zenodo 10.5281/zenodo.20976631; checked, not in results).
- Papers for data products and methods: see `docs/REFERENCES.md` (Fergason 2020/2018, McEwen 2007, Malin 2007, Smith 2001, Edwards 2011, Sun & Stack 2020, Swan 2021 AI4Mars, Deans 2009, Fong 2010, NTRS 20090036808, Yamauchi 1997, Burgard 2005, Singh 2009, Bircher 2016, Sofman 2006, Koenig & Smirnov 1997, González-Baños & Latombe 2002, Shen 2020, Betke 1995, Hubert & Arabie 1985).
- Design references (challenge Resources, not data): Curiosity's Proposed Path up Mount Sharp; NASA Worldview.
- Software: MapLibre GL JS (BSD-3, unmodified, `web/lib/`), the Python libraries above.
- SI tools: Anthropic Claude (claude.ai, Claude Code) — see field 6.
- Before ticking "Confirm All Work is Original": read `docs/AI_USE.md` (team decision).
