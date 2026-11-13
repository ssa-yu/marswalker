# Project page text (draft for the team; edit freely)

Numbers below are copied from `DATA_LOG.md` round 6 (route A vs B, frozen commit `e17452a`). If any rule or class changes, the numbers must be recomputed and both versions kept.

## Project Name

Marswalk Recon

## High-Level Summary

Marswalk Recon is a map an astronaut on Mars could use to plan a walk from the habitat: where the ground is firm, rough, sandy or too steep, which route reaches a point and comes back within the suit's oxygen, and how much margin is left at every step of the way home. The map gets better because a scout rover goes first: it leaves the habitat on its own, drives loops, comes home a different way and reveals the fine terrain that orbital data cannot show. We built it at Jezero Crater from NASA orbital terrain models and images and Perseverance ground data, and measured what the recon is worth at 63 fixed test points (oxygen in nominal minutes: 1 = one minute of walking on firm ground). First, planning from orbital data alone badly underestimates a walk: it plans 51 and the walk costs 195, 3.8 times as much, because the sand that covers about 40 % of the area is invisible at 20 m resolution. Second, a recon that saw only 11.3 % of the area, almost all within 600 m of the habitat, recovers about a quarter: after 30 simulated loops a walk steps on 251 m less hazard terrain and uses 28 less oxygen on average, 25 % of what perfect knowledge would save (about half at 300–600 m, n = 8; 23 % beyond 1,200 m, because every walk passes through the ring around the habitat the rover saw). Third, that is not enough, and the map shows it: after recon the plan still underestimates by 108 (plans 58, costs 167), loops 20 to 30 brought no further gain, and knowing part of the map is sometimes worse than knowing none, when a detour around seen sand runs into unseen sand. So the walk page shows both the return margin the plan believes and the true one.

## Project Details

**What it does.** Three steps. (1) A simulated scout rover explores from the habitat in loops within an energy budget; within 15 m of its path the high-resolution terrain replaces the orbital map ("scratch-off" map). (2) Choosing where the astronaut should go is the next step of the project (not in this version). (3) An astronaut walk planner finds the least-oxygen route, replays the walk, and shows two return-margin bars: the margin the plan believes and the true margin on the reference terrain.

**How it works.** An offline Python pipeline turns NASA data into static files; the web pages are plain HTML and JavaScript with a local copy of MapLibre, with no backend: any static file server can host it. Terrain classes on a 2 m grid: slope from the HiRISE 1 m terrain model, roughness, and a texture rule that finds fields of parallel sand ripples in the 0.25 m HiRISE image. The orbital prior is the CTX 20 m terrain model. The rover and the astronaut use the same least-cost path planner; the rover has a hard rule to keep enough energy to get home over ground it has already seen (tested: no loop of the recorded run exceeds its budget). Route A (orbital only) and route B (after recon) are both walked on the HiRISE reference terrain, and the comparison definitions were written down and frozen before the first number was computed.

**Benefits.** It turns "how far can I walk?" into numbers an astronaut can act on (oxygen left, oxygen needed to get home, metres of sand on the way) and shows how much a robotic recon improves them and where it does not help yet: the plan after recon still underestimates the walk, and the rover could not get far from the habitat.

**Honesty labels.** Every layer and number is tagged measured / derived / assumed / simulated. HiRISE is called the reference terrain, never ground truth. The sand classes are marked *heuristic, not yet reviewed* until a person checks the random check sheets. Limitations are listed on the page and in the README.

**Tools and languages.** Python (NumPy, SciPy, scikit-image, rasterio/GDAL, Pillow, Matplotlib, pytest, Playwright), JavaScript, HTML/CSS, MapLibre GL JS.

## NASA Data

Taken from the data summary table at the top of `DATA_LOG.md` (only data used in the results or on the pages):

| Data | Provider | How we used it |
|---|---|---|
| HiRISE orthoimage 0.25 m and DTM 1 m mosaics (Mars 2020 TRN) | MRO HiRISE; USGS Astrogeology | Reference terrain: slope, roughness, sand-ripple texture, terrain classes; basemap |
| CTX DTM 20 m and orthoimage 6 m mosaics (Mars 2020 TRN) | MRO CTX; USGS Astrogeology | Orbital prior for route A and for the rover before it sees anything; basemap |
| HiRISE ESP_071077_1985 (2021-09-24) | MRO HiRISE; USGS | Independent position check (parked Perseverance vs its waypoint, 2.0 m) |
| MOLA 463 m DEM and MOLA PEDR laser shots | MGS MOLA; USGS, PDS Geosciences Node | Elevation checks of both terrain models |
| THEMIS Day IR and MOLA/HRSC hillshade tiles | JPL Mars Trek (challenge resource) | Regional context basemaps |
| USGS SIM 3464 Jezero geologic map | USGS-NASA Planetary Geologic Mapping (challenge resource) | Geologic-unit layer |
| Perseverance waypoints and traverse | Mars 2020, NASA JPL MMGIS | Ground-data layers, photo locations, habitat position (landing site) |
| Perseverance Raw Images (Navcam, Front Hazcam, Mastcam-Z) | Mars 2020, NASA/JPL-Caltech (challenge resource) | 478 real photos placed on waypoints; Navcam viewing directions from the camera model and rover attitude |

Also checked but not used in the results: SuperCam LIBS chemistry, CRISM mineral maps (failed our registration check), the Perseverance sample list, JPL Horizons Sun positions.

## References

See `docs/REFERENCES.md` (data products, methods and parameter sources, software, design references).

## Use of AI

See `docs/AI_USE.md`. In short: the code, checks and drafts were written by AI coding agents (Anthropic Claude via Claude Code) under the team's direction; rules were fixed before each run; no AI-generated images; no language model makes decisions inside the product.
