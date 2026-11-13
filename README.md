# Marswalk Recon

**A layered map and walking route for astronauts on Mars, made better by a scout rover that goes first.**
Scene: Jezero Crater, built from real NASA orbital terrain and imagery and Perseverance ground data.
Challenge: NASA Space Apps 2026, *Interplanetary Survival Guide: Martian Map*.

1. **Scout rover recon** (simulated): a rover leaves the habitat on its own, drives loops within an energy budget, comes home a different way, and "scratches off" the fine terrain it sees.
2. **Analysis** (where it is worth sending the astronaut): Perseverance's SuperCam laser chemistry is grouped by a rule fixed in advance, and each group's most typical and most unusual rock become candidate stops, each with a card (chemistry with the instrument's error, geologic unit, nearby Perseverance photos). The rover is simulated; the measurements are Perseverance's, and our rover "unlocks" one only by driving within 15 m of where it was taken. Switchable: `config/step2.json` (`enabled`, `link_rule`).
3. **Astronaut walk**: a route planned to keep enough oxygen to walk home; the page shows whether it really does on the reference terrain, with a walk replay and two return-margin bars (as the plan sees it, and true).

Status: working prototype. Every output that depends on the terrain classes is labelled *heuristic, not yet reviewed* until a person signs off the sand check sheets.

## What the recon is worth (route A vs route B)

63 test points on a fixed 300 m grid around the habitat. For each, a walk habitat → point → habitat is planned on a map, then walked on the HiRISE reference terrain. Route A is planned from orbital data only (CTX 20 m, which cannot see sand ripples); route B from the rover's map after 30 recon loops (11.3 % of the area seen). Means per walk; oxygen in nominal minutes (1 = one minute of walking on firm ground; usable budget 384):

| Planned on | Planned O2 | Actual O2 | Metres in hazard zones | Hazard crossings* |
|---|---|---|---|---|
| A: orbital data only | 50.8 | 194.6 | 1,156 | 10.8 |
| B: after 30 recon loops | 58.3 | 166.5 | 905 | 9.2 |
| Perfect knowledge (upper bound, not a recon result) | 83.5 | 83.5 | 147 | 3.7 |

\* Crossings do not fall steadily with more recon loops (B after 20 loops has more than after 10); they are listed, not used as a conclusion.

1. **Planning from orbital data alone badly underestimates the walk.** It plans 51 nominal minutes of oxygen per walk on average; the same walks cost 195 on the reference terrain (3.8 times), because sand covers about 40 % of the area and is invisible at 20 m resolution. This is a property of the data resolution (CTX 20 m vs HiRISE 1 m), not something the rover did.
2. **A recon that saw about a tenth of the area recovers about a quarter.** In 30 loops the rover saw 11.3 % of the study area, almost all within 600 m of the habitat. Route B then walks 251 m less on hazard terrain and uses 28 nominal minutes less oxygen than route A per walk on average: 25 % of what perfect knowledge would save. Near the habitat (300–600 m, only n = 8 points) it is about half (46 % of the oxygen, 53 % of the hazard metres); beyond 1,200 m it is still 23 %, because every walk goes out and back through the ring around the habitat that the rover did see. In the other five 2.4 km windows of the same HiRISE mosaic (rule fixed in advance) the result has the same direction in all six: route B after 30 loops walks less hazard terrain and uses less oxygen than route A, recovering 22–47 % of the possible oxygen gain and 22–45 % of the hazard-metre gain per window. Point by point (B after 30 loops vs A, actual oxygen): 56 of 63 walks better, 6 worse, 1 the same; mean −28.2, 95 % resampling interval −36.4 to −20.5 (this describes the spread of the 63 points; it is not a significance test, the points are not independent).
3. **It is not enough, and the map has to show it.** After recon the plan still underestimates the oxygen by 108 nominal minutes per walk (plans 58, costs 167). Loops 20 to 30 brought no further improvement (the rover could not get out of the sand near home). Knowing only part of the map is sometimes worse than knowing none of it: a route that detours around sand the rover has seen can run into sand it has not seen (after 1 loop route B is marginally worse than A). Doubling or quadrupling the rover's budget (19.8 % / 24.1 % seen) recovers only 27 % / 30 %, and the plan still underestimates by about 100 nominal minutes (sensitivity runs written after the locked run's coverage was seen). That is why the astronaut page shows both the return margin the plan believes and the true one.

## Step 2: where to go (SuperCam chemistry, option A)

Rules fixed before any group was seen (DATA_LOG round 8, W1): calibration targets excluded; each target's 8 oxides averaged and divided by the instrument's prediction error (RMSEP); Ward clustering; number of groups = the largest k ≤ 4 whose centres all differ by ≥ 5 RMSEP in some oxide; candidate stops = each group's most typical and most unusual target, no score. Positions are Perseverance's site/drive (the rock is within ~7 m of the rover).
- **Brought back by our rover (link rule i, the product):** after 30 loops it unlocked 62 targets at 25 places, all on the crater-floor unit (Njf) → 2 groups (59 low-MgO targets; 3 targets with MgO 14 wt%) → 4 candidate stops, all within 311 m of the habitat.
- **All Perseverance measurements in the area (not brought back by this rover; "View all data"):** 208 targets at 64 places → 3 groups (MgO 4.3, 15.8, 24.8 wt%) → 5 candidate stops 0.5–0.9 km south and south-west of the habitat.
- **Check against where Perseverance actually drilled (descriptive, 4 sites):** with all measurements, the rocks named after the Brac and Issole sampling sites fall in the two high-MgO groups, and the Issole site has both candidate stops of its group within 15 m (one is `robine_hole`, the Robine drill hole); the Rochette and Sid sites fall in the low-MgO group. Our rover unlocked only the Sid site. No test: the stops are not ranked.

## One walk to all the stops (round 7)

Designed after seeing the 63-point comparison, which stays the pre-registered main result. One walk visits every candidate stop (18 minutes and 18 nominal minutes of oxygen at each, assumed), planned on each map and walked on the reference terrain. Main table (4 stops the rover brought back): route A actual 114.6, route B after 30 loops 104.0 (−10.5; hazard metres −74), perfect knowledge 96.2; after 5 loops B is worse than A (+7.1). Second table (5 stops from all measurements, not brought back by this rover): A 246.4, B after 30 loops 225.5 with its own order (−20.9) or 204.9 keeping A's order (−41.5), perfect knowledge 153.2; A underestimates that walk by 105 nominal minutes. Every map reaches every stop here, because all stops are within about 0.9 km of the habitat: these walks do not show the case "route A thinks it can reach all stops, route B knows it can only reach some". The oxygen slider on the astronaut page lets you shrink the budget yourself (interactive only, no table).

- Whether a walk stays within the 384 budget is not evidence for either route: the counts differ only at the 5 westernmost points, where route A comes within 1.1 minutes of the limit.
- The definitions were written before the first number and frozen at commit `e17452a`; the run was done once (`DATA_LOG.md` round 6, T2, full tables by distance band, A+ bracket and loops 1/5/10/20). The per-point summary (`spikes/u2_pointwise.py`) was added after the numbers were seen and changes none of them.

## View it

```
cd web && python3 -m http.server 8000
# open http://localhost:8000/          astronaut map (route A vs B), the first page
#      http://localhost:8000/recon.html   step 1: rover recon replay
#      http://localhost:8000/data.html    map data and positioning checks
```
No build step and no backend: any static file server works (`file://` cannot load the JSON).

## Rebuild

```
conda env create -p ./.conda-env -f environment.yml
./.conda-env/bin/python -m pipeline.run --scene jezero          # maps, ground data, photos, Navcam directions
./.conda-env/bin/python -m pipeline.terrain --scene jezero      # terrain classes (2 m)
./.conda-env/bin/python -m pipeline.rover_sim --scene jezero    # step 1 recon (about 9 min)
./.conda-env/bin/python -m pipeline.export_recon --scene jezero
./.conda-env/bin/python -m pipeline.compare_ab --scene jezero   # route A vs B (frozen definitions)
./.conda-env/bin/python -m pipeline.export_compare --scene jezero
./.conda-env/bin/python -m pytest -q tests
```

## Data

The full list with links, roles and labels (measured / derived / assumed / simulated) is the table at the top of `DATA_LOG.md`; citations are in `docs/REFERENCES.md`. Challenge Resources used as data: JPL Mars Trek (regional context tiles), USGS SIM 3464 geologic map (layer), Perseverance Raw Images (ground photos). Used as references, not data: *Curiosity's Proposed Path up Mount Sharp* (route map style) and NASA Worldview (layer list). Main terrain: HiRISE and CTX Mars 2020 TRN mosaics (USGS Astrogeology).

## Limitations

- **The scout rover is simulated.** Its routes come from our planner, not from Perseverance. HiRISE stands in for what the rover's cameras would see; HiRISE is orbital data and is called the *reference terrain*, never ground truth.
- **Sand classes have not been reviewed by a person** (*heuristic, not yet reviewed*). They come from a fixed texture rule (parallel ripples over tens of metres). Known errors from the random check sheets: long bright/dark edges (scarps, crater rims, albedo contacts) are sometimes called sand (2 of 24 "sand" crops); thin small ripples and large ripples get the same cost. Sand is 40.3 % of the study area.
- **The orbital map (prior) has no sand.** The same texture test on the CTX 6 m image did not find the sand fields (AUC 0.48, recall 0.2 %; figure `qa/jezero/S2_ctx_vs_hirise_sand.png`). An experienced image interpreter might guess the large sand belt from CTX; our prior does not have that layer, and nobody drew it by hand because everyone involved had already seen the HiRISE answer. The A+ column (orbital map plus sand where a 60 m block is at least half sand on the reference) brackets that case; it uses the reference terrain and is not real pre-departure knowledge.
- **Elevation check against the MOLA 463 m grid fails** (X3 items 3–4: HiRISE − MOLA −11.0 ± 10.7 m, CTX − MOLA std 14.3 m; limit 10 m). A supplementary check written before it was run, against 1,067 individual MOLA laser shots, passes (−2.6 ± 7.4 m and −3.3 ± 7.2 m); it is reported next to the fail, not instead of it. Keeping Jezero after this fail was decided after seeing the result. The thresholds were fixed after measuring a first Arcadia site and before any route number.
- **The first run of the rover goal rule had a defect**: 5 of 30 loops ended 1.3–4.8 energy units over the 4,000 budget. The reserve rule was fixed (margin of two steps instead of one) and the simulation was re-run once; the rerun (0 loops over budget, same coverage 11.3 %) is the record and both runs are in `DATA_LOG.md`.
- **The rover rarely gets beyond ~600 m.** With sand at 40 % and costing 6× firm ground, a 4,000-unit loop is used up close to home (0–600 m: 49.8 % seen; 600–1,200 m: 3.3 %; beyond: 0 %). The budget and costs are assumptions locked before the run and were not changed to make the rover go further. Runs with budgets 8,000 and 16,000 and with sand ×3 were written down after seeing this coverage and before any route A/B number, and run once each (DATA_LOG round 7, T7): coverage 19.8 % / 24.1 % / 14.6 %, share of the possible gain 27 % / 30 % / 24 %, and route B still underestimates by about 100 nominal minutes in all of them. They are sensitivity checks; the locked setting stays the result.
- **CRISM mineral maps and the SIM 3464 geologic map are not registered to HiRISE.** CRISM failed our four-quadrant check (worst quadrant 31.7 m and 42.0 m, limit 20 m) and is not on the map; SIM 3464 is shown as a layer only, labelled *not registered to HiRISE* (its offset could not be determined).
- **When the rules were fixed.** The study area (AOI) was kept by decision rather than moved, before any route number existed. The multi-window rule (6 windows of 2.4 km, HiRISE coverage ≥ 95 %, ≥ 16 waypoints) was fixed after the coverage of each window was known and before any route number; each window was run once (DATA_LOG rounds 7 and 8). The statistic details (mean over a window's test points; bootstrap of the median over windows, 10,000 draws, seed 20261114; exact two-sided Wilcoxon only if all six windows agree) were proposed by the implementer before any window number and ratified by the manager after five windows' numbers were seen. The rule for the crater-rim window's 2.6 % HiRISE gap (gap blocked in every map and for the rover, outside hazard zones and the "seen" share, test points within 50 m dropped) was set by the manager after the other five windows' numbers and before any number of that window; it treats the gap identically for routes A and B. Applied literally, the A+ bracket counts gap cells as non-sand in the 60 m blocks at the gap, and the version-2 rover counts gap cells as unseen area in its goal gain (only the west-edge strip of that window). Result: all six windows have B < A (hazard metres −251, −202, −65, −185, −198, −77; oxygen −28.2, −22.6, −9.6, −24.8, −21.3, −18.6); exact two-sided Wilcoxon p = 0.031, which is the smallest p six windows can give, equals the sign test and says nothing about the size of the differences. Test points inside a window are not independent; the window is the sample. A second site (Arcadia Planitia) was evaluated and paused by team decision before any route number. The T6 and T7 runs were set up in the same commit before either ran and were run at the same time.
- **Rover goal rule version 3** (literature methods: frontier candidates, expected cost of unseen ground, repeat penalty; designed after seeing version 2's repeat coverage) is written and tested but not in this version's results: its first run was stopped after loop 1 because the candidate rule as written cannot reach beyond the first lattice points (DATA_LOG round 8, W3). With the version-2 driving distance (46.5 km) and a 30 m sensing swath the rover could see at most 24.2 % of the area if no swath ever overlapped, and overlap within ~290 m of the habitat is unavoidable.
- An exploratory variant of route B that prices unseen ground by the sand share seen so far (B*, rule written after the first comparison) is kept in DATA_LOG only, labelled exploratory; it is not part of the results.
- **Walk and rover parameters are assumptions** from the team's earlier prototype (2.5 km/h; speed and oxygen factors per terrain class; 480 nominal minutes with 20 % reserve); teammates are checking the original sources. No physiological values are modelled. Rover energy units are relative (1 = 1 m of firm ground).
- **Test points are not science targets.** The 63-point comparison uses a fixed grid chosen before step 2 existed; the walks to the step-2 stops (round 7) were designed after it.
- **Step 2 is a grouping, not a value judgement.** "Chemically different" does not by itself mean "worth a walk"; there is no science score. Group differences smaller than the RMSEP are not treated as different rock. Positions are the rover's position, not the rock's. The number-of-groups rule was written after looking at a check table made with the earlier sol-based positions (k = 4 at 5.6 RMSEP); the site/drive positions were chosen when option A was adopted; both were fixed before the run. With the site/drive positions the area holds 2 more targets, k = 4 drops to 4.3 RMSEP and the rule gives k = 3 — the k = 4 boundary was fragile from the start. k = 4 was not computed.
- **Agreement between the rover's groups and the all-data groups** is reported as cross-tables (the record) and, as metrics specified by the manager after the cross-tables were seen, the adjusted Rand index and the majority-match share (loop 30: ARI 1.0, 100 %; loop 20: 0.70, 96 %; loop 5: 0.57, 100 %).
- **Round 7 (walks to the step-2 stops)** was designed after round 6; its order, dwell and "stops reached" definitions were confirmed before its single run. Its stops are close to the habitat, so every map reaches every stop.
- Routes are not replanned during the walk: route A walks into what it did not know about.
- **Three comparison definitions were set by the implementer** before the computation and ratified by the manager only after the numbers were seen (recorded as a process violation): hazard metres count only metres inside hazard zones (metres on any sand are listed separately; the means differ by 2 m); a merged crossing is measured by its in-zone metres; no dwell time at the test point. A dwell time would add the same constant to every column's planned and actual oxygen; with 18 minutes, A would have 2 more walks over budget and B after 30 loops none, which only shows that the "within budget" counts are unstable.
- **The 63 test points are not independent samples**: they share the walk out of the habitat, one recon run and one study area. No per-point p-value is reported.
- **One study area, one recon run** for the main result. Hazard zones: 156 patches of sand or blocked ground ≥ 400 m² on the reference terrain that are not marked on the orbital map (≥ 80 % of their cells firm or rough there); one 28,832 m² patch on steep ground is 21 % blocked on the orbital map and therefore not counted.
- Perseverance waypoint elevations match the HiRISE DTM to centimetres because they come from the same terrain model; that checks our coordinate chain only. The independent position check is the parked rover visible in a 2021 HiRISE image, 2.0 m from its waypoint.
- Navcam photo directions are derived from the camera model and rover attitude (checked on 3 images against the CTX horizon, within 1°); Front Hazcam and Mastcam-Z directions are not checked and not drawn.
- MapLibre draws Mars coordinates with Earth Web Mercator maths; the scale bar and coordinates are computed on the Mars sphere.

## Layout

| Path | Content |
|---|---|
| `config/scenes/` | scene configs |
| `pipeline/` | Python pipeline (see module docstrings) |
| `web/` | static pages (HTML + vanilla JS + local MapLibre); `web/data/` is generated |
| `tests/` | invariants and synthetic-terrain tests (rover budget, planner isolation, comparison definitions) |
| `qa/` | check images, reports, screenshots |
| `DATA_LOG.md` | data summary table and processing log (rules written before each run) |
| `docs/` | `REFERENCES.md`, `AI_USE.md`, `PROJECT_PAGE.md` (text for the challenge project page) |
| `spikes/` | feasibility and evaluation scripts kept for the record |

Data credits: NASA/JPL-Caltech/UArizona (HiRISE), NASA/JPL-Caltech/MSSS (CTX), USGS Astrogeology, NASA JPL Mars Trek, NASA/JPL-Caltech (Perseverance; Mastcam-Z NASA/JPL-Caltech/ASU).
