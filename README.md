# Marswalk Recon

**A layered map and walking route for astronauts on Mars, made better by a scout rover that goes first.**
Scene: Jezero Crater, built from real NASA orbital terrain and imagery and Perseverance ground data.
Challenge: NASA Space Apps 2026, *Interplanetary Survival Guide: Martian Map*.

1. **Scout rover recon** (simulated): a rover leaves the habitat on its own, drives loops within an energy budget, comes home a different way, and "scratches off" the fine terrain it sees.
2. **Analysis** (where it is worth sending the astronaut): method not decided yet; not in this version.
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
2. **A recon that saw about a tenth of the area recovers about a quarter.** In 30 loops the rover saw 11.3 % of the study area, almost all within 600 m of the habitat. Route B then walks 251 m less on hazard terrain and uses 28 nominal minutes less oxygen than route A per walk on average: 25 % of what perfect knowledge would save. Near the habitat (300–600 m, only n = 8 points) it is about half (46 % of the oxygen, 53 % of the hazard metres); beyond 1,200 m it is still 23 %, because every walk goes out and back through the ring around the habitat that the rover did see. Point by point (B after 30 loops vs A, actual oxygen): 56 of 63 walks better, 6 worse, 1 the same; mean −28.2, 95 % resampling interval −36.4 to −20.5 (this describes the spread of the 63 points; it is not a significance test, the points are not independent).
3. **It is not enough, and the map has to show it.** After recon the plan still underestimates the oxygen by 108 nominal minutes per walk (plans 58, costs 167). Loops 20 to 30 brought no further improvement (the rover could not get out of the sand near home). Knowing only part of the map is sometimes worse than knowing none of it: a route that detours around sand the rover has seen can run into sand it has not seen (after 1 loop route B is marginally worse than A). That is why the astronaut page shows both the return margin the plan believes and the true one.

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
- **The rover rarely gets beyond ~600 m.** With sand at 40 % and costing 6× firm ground, a 4,000-unit loop is used up close to home (0–600 m: 49.8 % seen; 600–1,200 m: 3.3 %; beyond: 0 %). The budget and costs are assumptions locked before the run and were not changed to make the rover go further. Runs with budgets 8,000 and 16,000 and with sand ×3 were written down after seeing this coverage and before any route A/B number; they have not been run yet.
- **CRISM mineral maps and the SIM 3464 geologic map are not registered to HiRISE.** CRISM failed our four-quadrant check (worst quadrant 31.7 m and 42.0 m, limit 20 m) and is not on the map; SIM 3464 is shown as a layer only, labelled *not registered to HiRISE* (its offset could not be determined).
- **When the rules were fixed.** The study area (AOI) was kept by decision rather than moved, before any route number existed. The multi-window rule (6 windows of 2.4 km, HiRISE coverage ≥ 95 %, ≥ 16 waypoints) was fixed after the coverage of each window was known and before any route number; the multi-window comparison has not been run yet. A second site (Arcadia Planitia) was evaluated and paused by team decision before any route number.
- **Walk and rover parameters are assumptions** from the team's earlier prototype (2.5 km/h; speed and oxygen factors per terrain class; 480 nominal minutes with 20 % reserve); teammates are checking the original sources. No physiological values are modelled. Rover energy units are relative (1 = 1 m of firm ground).
- **Test points are not science targets.** Where it is worth sending the astronaut (step 2) is not decided yet; the comparison uses a fixed grid.
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
