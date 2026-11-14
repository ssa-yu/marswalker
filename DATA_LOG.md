# DATA_LOG

## Data summary table (使用資料統整表)

Label: measured = instrument data as published; derived = computed by us from measured data; assumed = our choice; simulated = model output.
"Resources" = listed on the challenge Resources tab (Interplanetary Survival Guide: Martian Map).

| Name | Mission / instrument, provider | Link | Used for (step / layer) | Label | Resources | Status |
|---|---|---|---|---|---|---|
| HiRISE orthoimage mosaic 0.25 m (Mars 2020 TRN) | MRO HiRISE; USGS Astrogeology | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first.tif | Jezero basemap tiles; registration reference | measured | no | in use (AOI window only, ~150 MB of 6.9 GB) |
| HiRISE DTM mosaic 1 m (Mars 2020 TRN) | MRO HiRISE; USGS Astrogeology | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif | Jezero reference terrain: hillshade, slope | measured (layers: derived) | no | in use (AOI window only) |
| CTX DTM mosaic 20 m (Mars 2020 TRN) | MRO CTX; USGS Astrogeology | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_DTM_MOLAtopography_DeltaGeoid_20m_Eqc_latTs0_lon0.tif | Jezero prior terrain: hillshade, slope | measured (layers: derived) | no | in use |
| CTX orthoimage mosaic 6 m (Mars 2020 TRN) | MRO CTX; USGS Astrogeology | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0.tif | Jezero context image; X3 image registration | measured | no | in use |
| HiRISE ESP_071077_1985 RED (2021-09-24) | MRO HiRISE; USGS ARD COG (uncontrolled RDR) | https://astrogeo-ard.s3-us-west-2.amazonaws.com/mars/mro/hirise/uncontrolled/ESP_071077_1985_RED/ESP_071077_1985_RED.tif | Independent check C2: rover tracks vs traverse; optional layer | measured | no | in use (AOI window) |
| MOLA MEGDR DEM 463 m | MGS MOLA; USGS mosaic | https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif | X3 elevation check | measured | no | in use (12 km window) |
| THEMIS Day IR mosaic 100 m | Mars Odyssey THEMIS (ASU); NASA JPL Mars Trek tiles | https://trek.nasa.gov/tiles/Mars/EQ/THEMIS_DayIR_ControlledMosaics_100m_v2_oct2018/1.0.0/default/default028mm/{z}/{row}/{col}.png | Regional context basemap (±60 km), stored locally | measured | yes (Mars Trek) | in use |
| MOLA + HRSC colour hillshade 200 m | MGS MOLA + MEx HRSC; NASA JPL Mars Trek tiles | https://trek.nasa.gov/tiles/Mars/EQ/Mars_MOLA_blend200ppx_HRSC_ClrShade_clon0dd_200mpp_lzw/1.0.0/default/default028mm/{z}/{row}/{col}.jpg | Regional context basemap (±250 km), stored locally | derived | yes (Mars Trek) | in use |
| Perseverance waypoints (M20_waypoints.json) | Mars 2020, NASA JPL MMGIS | https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_waypoints.json | Waypoint layer; photo location; base position; C1 chain check | measured | no | in use |
| Perseverance traverse (M20_traverse.json) | Mars 2020, NASA JPL MMGIS | https://mars.nasa.gov/mmgis-maps/M20/Layers/json/M20_traverse.json | Traverse layer; C2 check | measured | no | in use |
| Perseverance Raw Images (Navcam, Front Hazcam, Mastcam-Z left) | Mars 2020, NASA/JPL-Caltech (Mastcam-Z: ASU) | https://mars.nasa.gov/mars2020/multimedia/raw-images/ (JSON API `https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020`) | Ground photos stored locally, placed on waypoints by site/drive; Navcam viewing directions (camera model + rover attitude, T5) | measured (directions: derived) | yes | in use |
| Habitat (base) location | — | — | Local grid origin (Octavia E. Butler Landing) | assumed | — | in use |
| USGS SIM 3464 Jezero geologic map | USGS-NASA Planetary Geologic Mapping | https://pubs.usgs.gov/sim/3464/sim3464_database.zip | Map layer (GeoUnits_v1, 12 km context window; read remotely via /vsizip, 216 kB GeoJSON); Q1 unit at SuperCam sites | measured | yes | in use (layer, not registered to HiRISE) |
| SWIM ice-consistency maps | PSI/JPL (NASA) | https://swim.psi.edu/ | Regional layer, Arcadia | measured (consistency, not detection) | no | paused (Arcadia paused 2026-11-14) |
| HiRISE DTM 061075_2195 + CTX K20_061141/061075 (Arcadia) | MRO HiRISE / CTX; USGS ARD | see `team/tech/official-sources.md` | Arcadia scene | measured | no | paused: CTX DTM + ortho downloaded; HiRISE DTM download stopped; X3 not re-run |
| HiRISE DTM 060706_2195 + CTX (Arcadia, second region) | MRO HiRISE / CTX; USGS ARD | see `team/tech/official-sources.md` | Arcadia second region | measured | no | paused (data from feasibility spike kept in `data_raw/arcadia_starship_060706/`) |
| MOLA PEDR laser shots (ODE GDS molapedr query, 1,608 shots in 18.31–18.67°N, 77.22–77.58°E) | MGS MOLA; PDS Geosciences Node ODE | https://oderest.rsl.wustl.edu/livegds/?query=molapedr&results=v&minlat=18.31&maxlat=18.67&westernlon=77.22&easternlon=77.58 | R1 supplementary elevation check | measured | no | in use (QA only) |
| HiRISE DTM mosaic 1 m, full file (same product as above, 1.84 GB, S3 mirror) | MRO HiRISE; USGS Astrogeology | https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/HiRISE/JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif | PEDR check over the whole mosaic; multi-window coverage | measured | no | downloaded 2026-11-14 (357 s) |
| SuperCam LIBS major oxides (supercam_libs_moc.csv) + Raman table | Mars 2020 SuperCam; PDS Geosciences | https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/data_derived_spectra/ | Step-2 verification Q1/Q4/Q10 only (no product use until Shan picks option A/C/D) | measured | no | verification only |
| CRISM MTRDR summary parameters (4 products: frt00005c5e, frt0001fb74, hrl000040ff, frt000047a3; _su cubes, 0.6 GB) | MRO CRISM; PDS Geosciences | https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/mtrdr/ | Step-2 verification Q3 only | measured (parameters derived by the CRISM team) | no | verification only |
| Mars rock samples list (30 samples) | NASA Science | https://science.nasa.gov/mission/mars-2020-perseverance/mars-rock-samples/ | Q2 sample locations (test set only) | measured | no | verification only |
| Deahn et al. 2026 crater-rim map (crater_rim_mapping_v4.gdb) | Mars 2020 team; Zenodo 10.5281/zenodo.20976631 | https://doi.org/10.5281/zenodo.20976631 | Q9 rim window facts only | measured (expert mapping) | no | verification only (rim scene waits for Shan) |
| Curiosity's Proposed Path up Mount Sharp | NASA | https://science.nasa.gov/resource/curiositys-proposed-path-up-mount-sharp/ | Design reference for route maps | — | yes | reference only |
| NASA Worldview | NASA | https://worldview.earthdata.nasa.gov/ | Design reference for layer list | — | yes | reference only |
| JPL Horizons Sun azimuth/elevation at Jezero (2026-11-15, 2 min) | JPL Solar System Dynamics | https://ssd.jpl.nasa.gov/api/horizons.api | Step 3 daylight window (Q6); shadow check | derived (ephemeris) | no | stored locally (`data_raw/jezero/horizons/`), not in the web yet |
| SuperCam PDS calibrated-spectra labels + masterlist (2 labels, masterlist header) | Mars 2020 SuperCam; PDS Geosciences | https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/ | S6-5 check: site/drive in labels | measured | no | checked only (not stored in app) |
| AI4MARS (status update) | NASA JPL, Zenodo | https://zenodo.org/records/15995036 | Terrain classes on rover photos (later step) | measured labels (crowd; Perseverance has no expert test set) | no | subset stored (2026-11-14): Perseverance NAV labels 3,827 + main-AOI Navcam images 2,215 (6,043 files, 0.63 GB, CRC checked) in `data_raw/jezero/ai4mars/`, index `index.csv`; no GEO/mcam/HAFIQ |
| DONKI SEP / WSA-ENLIL | NASA CCMC via api.nasa.gov | https://api.nasa.gov/ | Step 3 space-weather scenario (Q7) | archived | no | not fetched (DEMO_KEY rate limit) |

## Log

### 2026-11-14 checkpoint 1 (maps & real imagery)

- Local grid: base-centred eqc on the Mars 2015 sphere R = 3,396,190 m (same as all USGS sources; MVP_PLAN used 3,389,500 — difference < 5 m over the AOI). Source↔local is affine, so resampling is done in the source CRS with non-square pixels (width res / cos(lat0)).
- Jezero AOI: x [-1700, 700], y [-1000, 1400] m from base (MVP_PLAN §5.2 rule; 118 of 122 waypoints with sol ≤ 400). Base = first waypoint (site 3, drive 0, sol 13): 77.45088572°E, 18.44462715°N (assumed).
- Slope display: reference = HiRISE DTM averaged to 3 m, Horn kernel (6 m baseline); prior = CTX 20 m (40 m baseline). Same colour bins 0/2/5/10/15/20/25/30°. Display only; terrain-class thresholds are not set yet.
- Hillshade: sun azimuth 315°, altitude 35° for both terrains.
- X3 thresholds (locked by manager 2026-11-14 after the 060706 measurements, before any route numbers): one global image-registration shift + one vertical offset; quadrant deviation ≤ 20 m; reference vs MOLA |mean| ≤ 10 m and std ≤ 10 m; shifted prior vs MOLA std ≤ 10 m.
- Arcadia paused by Shan's decision (2026-11-14): no further downloads; pipeline stays scene-config driven.
- Results: see "Checkpoint 1 results" below (filled by the pipeline run).

### Checkpoint 1 results — Jezero (pipeline run 2026-11-14)

Downloads (AOI windows only; network to AWS us-west-2 ~120–300 KB/s): HiRISE ortho window 152 MB of 7.36 GB in 1244 s; HiRISE DTM window 38 MB in 524 s; CTX DTM 9.7 MB; CTX ortho 36 MB; MOLA window 1.6 kB; ESP_071077 window 149 MB (COG sparse tiles) in 289 s; Trek 49 + 56 tiles.

| Check | Result | Verdict |
|---|---|---|
| X3-1 one global CTX→HiRISE shift (image registration, 6 m grid) | (−2.1 m E, +1.8 m N), r 0.79→0.81; vertical offset −1.03 m (CTX−HiRISE median +1.03, NMAD 2.6 m); DTM-based cross-check shift 0 m | recorded |
| X3-2 quadrant deviation after shift ≤ 20 m | 0.3, 0.3, 0.7, 0.4 m | pass |
| X3-3 HiRISE − MOLA 463 m, \|mean\| ≤ 10, std ≤ 10 m | −11.0 ± 10.7 m (30 cells) | **fail** |
| X3-4 shifted CTX − MOLA std ≤ 10 m | −11.6 ± 14.3 m (675 cells) | **fail** |
| Diagnostic (not used for verdict) | MOLA grid best fit offset (−439 m E, +232 m N) → CTX − MOLA −1.0 ± 9.2 m; MOLA cells < 2° slope: −6.0 ± 9.3 m | — |
| C1 waypoint elev_geoid vs HiRISE DTM (chain only) | MAE 0.018 m, max 0.15 m, n = 122 | pass (not independent) |
| C2a parked rover in HiRISE ESP_071077_1985 (sol ~212) vs waypoint 7_2050 (sols 210–237) | 2.04 m (−0.5 E, −2.0 N); image registered to basemap on terrain texture: shift (+30.5, +189.6) m, r 0.00→0.53, quadrant residual ≤ 2.8 m | pass (independent) |
| C2b dark band along traverse (sol ≤ 212) | post peak at 2.5 m (z 7.0); pre-landing control peak 2.2 m (z 4.6) → path-selection bias, informative only | info |
| C3 HiRISE DTM hillshade vs ortho | 0.34 m offset | pass |
| Photos | 478 images (Navcam L, Front Hazcam L, Mastcam-Z L) at 121/122 AOI waypoints, 33 MB; 43,863 candidate full-frame images matched site/drive | — |
| Slope > 15° share of AOI | HiRISE (6 m) 1.54 % vs CTX (40 m) 1.08 %; > 10°: 4.47 % vs 1.54 % | display only |

X3 is reported as failing at Jezero (items 3–4); thresholds not relaxed. Decision for manager.

Web output `web/data/jezero/`: 61.7 MB total (ortho tiles 10.6 MB / 1435 files, post-landing tiles 13.2 MB / 1435, photos 33.3 MB, overlays 2.8 MB). Headless Chrome: first map idle 0.43 s on localhost; offline run made 0 external requests.


### 2026-11-14 round 4 (R1–R3, tech-lead)

#### R1 MOLA: self-check and PEDR supplementary check (original X3-3/4 "fail" stays)

The original result above is unchanged: X3-3 HiRISE − MOLA 463 m −11.0 ± 10.7 m **fail**; X3-4 CTX − MOLA std 14.3 m **fail**. No bug was found in our code, so items 3–4 were not re-run.

(a) Self-check (`spikes/mola_selfcheck.py` → `qa/jezero/R1_mola_selfcheck.json`)

| Check | Result |
|---|---|
| S1 our strip-window reader vs GDAL reading the same remote window | identical values (max diff 0 m), identical georeference |
| S2 mosaic header | AREA_OR_POINT=Area; pixel 463.0935 m (implies R 3,396,263 m, CRS says 3,396,190 m); origin −180.0039°E / 90.0019°N (half a cell beyond the edge). If the data sit on an exact 1/128° grid this displaces Jezero by ~94 m E, 24 m N — too small to explain the misfit |
| Vertical datum | HiRISE/CTX TRN metadata: "elevation values ... refer to the Mars 2020 IAU sphere, R 3,396,190 m", but the values (≈ −2,600 m) match areoid-referenced MOLA topography (sphere heights here would be ≈ −4,270 m); "MOLAtopography_DeltaGeoid" is not explained in the metadata (not verified further). CTX was aligned to the HRSC DTM (+183.3 m vertical), HiRISE to CTX (median 0.4 m). Same datum as MOLA in practice → not the cause |
| S3 MOLA PEDR shots vs the MOLA 463 m mosaic itself (MOLA vs MOLA, no HiRISE/CTX involved) | 1,608 shots: mosaic − shots +8.7 ± 28.7 m at zero offset; best agreement when the mosaic is moved (−0.75, −0.5) cells = −329 m E, +232 m N → −0.1 ± 13.1 m. Same direction and size as the earlier diagnostic. The gridded mosaic disagrees with its own source shots here; our sampling is not the cause |
| S4 same code at Arcadia 060706 | PEDR-vs-mosaic (shots from the USGS ARD file, radius): flat terrain, std 61.0 → 60.0 m: inconclusive. CTX-vs-mosaic: best offset −180 m E, +695 m N but that CTX product carries its own 506 m shift: inconclusive |

(b) PEDR supplementary check, spec locked in direction.md before running (`pipeline/mola_pedr.py` → `qa/jezero/R1_mola_pedr.{json,png,_shots.csv}`): shots inside the HiRISE mosaic where every DTM cell in the 84 m disc is valid (rule written before the run); same shots for CTX (X3-1 shift and −1.03 m applied); no horizontal shift fitted.

| | n | DTM − PEDR | Threshold | Verdict |
|---|---|---|---|---|
| HiRISE (D1) | 1,067 | −2.58 ± 7.38 m (median −1.63, max 52.8) | \|mean\| ≤ 10, std ≤ 10 | pass |
| CTX shifted (D3) | 1,067 | −3.34 ± 7.19 m | std ≤ 10 | pass |

Reported next to the original fail, not instead of it. Visible pattern: west part of the mosaic negative (−10 to −20 m), east part positive (+5 to +10 m): a regional tilt between the DTMs and MOLA, not examined further.

Side observation (Q3): the CRISM MTRDR products register to HiRISE only after shifts of −171…−320 m E, +188…+261 m N — the same direction as the MOLA mosaic offset. Cause not verified.

#### R2 Step 1 scout-rover recon simulation (`pipeline/rover_sim.py`, `pipeline/export_recon.py`, `web/recon.html`) — simulated, review pending

Run 2026-11-14 with the R3 proposals below, 30 loops, 413 s. No route A/B comparison was computed.

| Item | Value |
|---|---|
| Loops / distance | 30 loops, 79.9 km driven |
| Study area observed (reference revealed) | 1.3 % after loop 1, 10.8 % after 10, 18.6 % after 20, 23.7 % after 30 |
| Class agreement belief vs reference | 76.4 % before departure → 82.6 % after 30 loops |
| Goals reached | 17 of 30 (13 turned back on the soft rule) |
| Return events | 13 turn-back, 18 return switched to cheapest route, 6 reserve-rule returns |
| Replans | 4,817 (most are "cost ×2 ahead": prior firm, reference rough/sand) |
| Acceptance (MVP_PLAN P6, `tests/test_recon.py`) | every loop starts/ends at base: pass; max loop energy 3,987 / 4,000: pass; never on impassable reference cells: pass; never on a cell before it was observed: pass; median return-on-outbound overlap 13 % (< 30 %): pass |

Deviations from MVP_PLAN P6 (made before any comparison number existed): goal score = unobserved area within 150 m (+0.25 × within 450 m) among goals at 25–45 % of the planning budget (MVP score picked a goal 20 m from base every loop); a 25 % energy reserve with a hard rule "always keep enough energy to get home over already-seen terrain" (guarantees the budget); learned margin = paid / prior-predicted cost (stayed at the 1.15 floor in this run). Web: CTX basemap dimmed; HiRISE drawn only where revealed (browser composites reveal_t.png); "View all data" shows the full HiRISE. Output size 2.8 MB.

#### R3 parameter proposals (status: proposed, waiting for manager to lock; none tuned on route comparisons)

| Parameter | Proposed value | Basis | Label | Human check |
|---|---|---|---|---|
| Slope baseline | 6 m (central difference ±3 m on the 1 m HiRISE DTM; max to 2 m) | ~2× the effective resolution of HiRISE DTMs (≈3 m for 1 m posts; Kirk et al. 2008 — page not re-verified); 10 m in the sensitivity run | assumed | — |
| Prior slope | CTX 20 m Horn (40 m baseline), bilinear to 2 m | only scale the product supports | derived | — |
| Terrain classes | rough ≥ 8° or roughness ≥ P85 (0.059 m); sand = ripple index ≥ P90 (0.266) and slope < 15°; blocked ≥ 25° (astronaut), rover-blocked ≥ 20°; 3×3 majority | MVP_PLAN 5.4 values (from the team's earlier prototype; original source not found) | assumed | `qa/jezero/R3_terrain_classes.png` |
| Resulting areas (AOI) | reference: firm 75.5 %, rough 15.3 %, sand 8.9 %, blocked 0.4 %; prior: firm 97.9 %, rough 1.9 %, blocked 0.2 % | — | derived | — |
| Sand (ripples) | needs a person: in `qa/jezero/R3_ripple_check.png` the sand outlines follow ripple crests, and two "firm" crops (x 9,y −747; x −1199,y 261) lie inside ripple fields between crests | tech-lead's own look, not a review | heuristic, not yet reviewed | **Shan / teammate** |
| Hazard zone (for the A/B table, not computed) | 8-connected component of reference cells in sand or blocked, area ≥ 400 m² (100 cells), and ≥ 80 % of its cells are firm or rough on the prior | MVP_PLAN wording; area chosen so a single ripple crest does not count | assumed | after classes are reviewed |
| Comparison targets (independent of step 2) | every point of a 300 m lattice aligned to the base inside the AOI, ≥ 300 m from the base, not blocked on prior or reference; each base→target→base is one test route; report the distribution | rule fixed before any route exists | assumed | — |
| Sensing radius | 15 m | MVP_PLAN; Navcam/Hazcam terrain range not verified | assumed | — |
| Rover loop budget | 4,000 energy units (1 unit = 1 m firm; rough 2.5, sand 6), 75 % planning / 25 % reserve, home margin ≥ 1.15, revisit penalty ×2.5 | assumed (no rover power model) | assumed | — |
| Astronaut budget | MVP_PLAN 5.6 unchanged: 2.5 km/h, O2 480 nominal min, 20 % reserve, factors firm/rough/sand speed 1/0.6/0.35, effort 1/1.5/2.1 | team prototype; Apollo 15 20 % reserve (not re-verified) | assumed | teammates: sources |
| Unlock radius (link rule (i), only if Shan picks it) | 15 m = sensing radius | SuperCam LIBS distance in the table: median 3.1 m, p90 5.2 m, max 6.5 m; location precision = rover waypoint | assumed | — |

### 2026-11-14 round 5 (S1–S6, tech-lead)

#### S3 rover goal rule, version 2 — written here BEFORE the run (run once, after S1 v2 classes)

Inputs allowed (direction.md 車的目標選擇 "可以用"): AOI boundary, habitat position, the rover's own belief map (prior CTX classes + what it has observed), its own observed mask. Not loaded by the planner: waypoints, traverse, sols, SuperCam, photos, samples, Deahn map, unrevealed HiRISE (test: `tests/test_recon.py::test_planner_loads_no_perseverance_files`). Unlock counts are reported only, never used to change this rule.

1. Candidate goals: 40 m lattice cells that are passable on the belief map and whose belief cost from the habitat is ≤ outbound_frac (0.45) × planning budget (no minimum distance any more; v1 required 25–45 % of the budget, which only allowed goals 750–1350 m away).
2. Each candidate gets a **sector** (8 compass sectors of 45° centred on N, NE, E, … by bearing from the habitat) and a **distance band** by straight-line distance from the habitat: near 100–600 m, mid 600–1200 m, far > 1200 m.
3. Loop k uses sector `ORDER[(k−1) mod 8]` with ORDER = N, S, E, W, NE, SW, SE, NW (opposite sectors alternate), and band `BANDS[((k−1) // 8) mod 3]` = near (loops 1–8), mid (9–16), far (17–24), near (25–30) …
4. Gain of a candidate = unobserved area within 150 m + 0.25 × unobserved area within 450 m (same as v1). Among candidates in (sector, band) whose gain ≥ 5 % of the first loop's gain, pick the highest gain; ties (within 1 m²) → lower belief cost from the habitat.
5. Fallbacks, in this order, when (sector, band) has no eligible candidate: same sector, any band; then the next sector in ORDER with the scheduled band; then any candidate. Each loop records which rule picked its goal.
6. Everything else is unchanged from v1 (outbound replanning, soft turn-back, different-way-home penalty, adaptive margin, hard energy rule, budget 4,000, sensing radius 15 m).
Reported after the run: coverage by 8 directions within 1200 m and over the whole AOI, near/mid/far coverage, unlocked SuperCam sites (15 m) next to v1's 12/59 with the SIM 3464 unit of each, and how many of the 59 sites are within reach of one loop's budget at all (upper bound).

#### S1 sand classification, version 2 (proposed; heuristic, not yet reviewed — needs Shan / teammate sign-off)

Round 1 of at most 2 (direction.md 沙地的修正與放行). Code `pipeline/sandfield.py` (SAND_V2), wired into `pipeline/terrain.py`.
- Method: question changed from "is this pixel a bright ripple crest?" to "is this patch, over tens of metres, a field of parallel ripples?". HiRISE image at 0.5 m divided by its 25 m local mean; two difference-of-Gaussian bands — fine 0.5–1.5 m (2–3 m ripples) and coarse 1.5–5 m (large ripples/TARs); per band the orientation coherence of the structure tensor (window σ 6 m / 12 m) and the RMS band contrast. Sand if (fine coherence ≥ 0.45 and fine contrast ≥ 0.040) or (coarse coherence ≥ 0.50 and coarse contrast ≥ 0.050); 2 m grid; closing + opening with a 4 m disc; holes < 400 m² filled; patches < 400 m² dropped; slope < 15°. All thresholds are fixed numbers (no percentiles).
- How the numbers were set: on DEVELOPMENT crops drawn with seed 777 (not the check seed). Two settings were looked at: coherence 0.50/0.55 (dev non-sand sheet still had ripple fields under the cross: 3 of 16) → 0.45/0.50 (dev sheets clean). No route, recon or unlock number was looked at.
- Roughness now uses the locked fixed value 0.059 m (was P85, same number in the main AOI).
- Class priority (proposed): blocked > sand > rough > firm; then 3×3 majority; blocked re-imposed.

| Class share of AOI (reference, HiRISE) | v1 (withdrawn) | v2 (proposed) |
|---|---|---|
| firm | 75.5 % | 48.6 % |
| rough | 15.3 % | 10.8 % |
| sand | 8.9 % | 40.3 % |
| blocked | 0.4 % | 0.4 % |
| prior (CTX), unchanged | firm 97.9 / rough 1.9 / sand 0 / blocked 0.2 % | same |

Check figures v2 (seed 20261114; each crop 60 m at 0.25 m, plain | orange translucent fill, cross at centre; question: "is the ground under the cross part of a continuous sand/ripple field?"):
`qa/jezero/S1_sand_check_v2_A_sand.png` (24 classified sand), `S1_sand_check_v2_B_notsand.png` (24 classified not sand), `S1_sand_check_v2_C_v1crops.png` (the 12 v1 crops), `S1_sand_overview_v2.png` (whole AOI, v1 | v2), `S1_terrain_classes_v2.png`, points in `S1_sand_check_v2_points.json`.
tech-lead self-check (not a review): A — cross clearly not on sand: A08 (bright/dark contact on the plain), A16 (edge of the bright scarp, NW corner); borderline A12 → 2 ≤ 4. B — cross clearly on sand: B16 (patch of small ripples); borderline B20, B22 → 1 ≤ 2. The three must-flip points (x 9,y −747; x −1199,y 261; x −1591,y −309) are now sand (C09, C11, C12). Known failure mode: a single long, high-contrast brightness edge (scarp, crater rim, albedo contact) also scores high coherence.
- Hazard zone (for the A/B table; not computed): connected sand/blocked components. With v2 sand the AOI has 193 components; 157 ≥ 400 m² holding 99.9 % of the area, and one belt of 1.84 km². Proposal: keep 400 m² (= smallest sand patch) but note that "number of zones entered" becomes coarse (one giant zone); the "metres on hazard terrain" row will carry most of the signal.

#### S2 does the CTX 6 m image show the sand fields? (`spikes/s2_ctx_sand.py`, rule written in its header before running)

Same indicator on the CTX orthoimage with the band moved to the shortest scale CTX carries (DoG 6–18 m, window 30 m), same fixed coherence/contrast thresholds, nothing tuned on HiRISE. Scored on 60 m blocks (block = sand if ≥ 50 % HiRISE v2 sand; 38.4 % of blocks): CTX AUC 0.48, precision 0.04, recall 0.002 (maps 1.6 % of the AOI, mostly the dark scarp); control = HiRISE averaged to 6 m: AUC 0.55, recall 0.08. Decision rule (AUC ≥ 0.80 and recall ≥ 0.5 with precision ≥ 0.7): **not met → the prior keeps no sand class**; figure `qa/jezero/S2_ctx_vs_hirise_sand.png` for Limitations. Observation, not tested: to the eye the large sand belt is faintly visible on CTX as a smoother, slightly darker band; only a manual CTX-only mapping could capture it (decision for manager).

#### S3 result — the single run of goal rule v2 (on sand v2 classes, proposed), 2026-11-14 (simulated, review pending)

30 loops, 46.5 km, 544 s. Observed 11.3 % of the AOI (v1 rule on v1 classes: 23.7 %, 79.9 km). Reported only; nothing was changed because of these numbers.

| Observed share | N | NE | E | SE | S | SW | W | NW |
|---|---|---|---|---|---|---|---|---|
| v1, within 1200 m | 42.8 | 20.8 | 1.9 | 15.7 | 15.2 | 34.2 | 62.0 | 60.9 |
| v2, within 1200 m | 11.7 | 23.2 | 27.1 | 22.2 | 27.8 | 16.8 | 14.1 | 10.4 |
| v2, whole AOI | 8.2 | 19.9 | 27.1 | 22.1 | 27.8 | 10.3 | 6.7 | 4.3 |

By distance from the habitat (v1 → v2): 0–600 m 51.7 → 49.8 %; 600–1200 m 29.7 → 3.3 %; > 1200 m 1.2 → 0.0 %. Directions are now within 10–28 % of each other, but the rover rarely gets beyond ~600 m: with sand now 40 % of the reference terrain at cost ×6 (locked), a 4,000-unit loop is used up close to home (loops 17–19 and 22–24 fell back to "any band" because no mid/far goal fitted). Goal choices per loop are in `recon_loops.json` (`goal_rule`).
SuperCam sites unlocked (15 m, AOI 59 sites): v2 22 (loops 1/5/10/20/30: 2/10/12/19/22), all in SIM 3464 unit Njf; v1 12 (9 Njf, 3 Nle). AOI sites: 35 Njf, 24 Nle. Upper bound: all 59 sites have a habitat→site→habitat round trip ≤ 3,000 units on the reference classes (full knowledge), so reach is not the limit. Report `qa/jezero/S3_rover_v2_report.json`, figure `qa/jezero/S3_coverage_v1_v2.png`, screenshots `qa/screenshots/S3_recon_v2_*.png`.
**Defect found:** 5 loops ended 1.3–4.8 units over the 4,000 budget (1, 12, 13, 20, 24; each after a "safety return"). Cause: the hard energy rule kept a margin of one step, but one step can also lengthen the way home by one step. Fixed in `rover_sim.py` (margin 2 × max step) with a synthetic regression test; the run above was NOT repeated (one run per version) — the acceptance test is marked xfail with this reason, and the rerun after S1 is locked will use the fixed code.
Test added: `test_planner_loads_no_perseverance_files` (static: rover_sim.py names no waypoint/traverse/SuperCam/photo/sample/Deahn file; dynamic: a simulation opens no file at all).

#### S5 Step 3 skeleton: astronaut walk planner (`pipeline/astro_plan.py`, `web/astronaut.html`) — planned values, review pending

- What it does: least-oxygen path on a class grid (8-connected; a step costs the mean of the two cells' per-metre O2 times the step length; skimage MCP_Geometric in Python, Dijkstra in the browser); stop order = visits the most stops, then the least O2, subject to "after each stop the astronaut can still walk home within the usable O2" (brute force over orders, ≤ 7 stops; greedy nearest-feasible beyond); stops that do not fit are skipped and reported. Per-step timeline: elapsed time, distance, O2 used, O2 needed to get home (cheapest route), return margin = usable O2 left − O2 needed to get home.
- Parameters (locked R3, assumed): 2.5 km/h on firm; speed factor firm/rough/sand 1/0.6/0.35; O2 factor 1/1.5/2.1; blocked ≥ 25°; suit O2 480 nominal min, reserve 20 % → 384 usable. Unit: 1 nominal minute = O2 of one minute walking on firm ground. Interface-only warning threshold: margin < 15 % of usable O2 (assumed).
- Knowledge state on real terrain: prior only (CTX 20 m classes, `class_prior` of terrain_2m.npz) on a 4 m grid (each 4 m cell takes the most costly 2 m class). Planned values only: no evaluation on the HiRISE reference terrain, no route A vs B, no comparison numbers.
- Targets: PLACEHOLDER (step 2 not decided). Rule written before the first run: the four points of the 300 m comparison lattice aligned to the base nearest to 600 m east, west, north and south of the base (nearest passable cell if blocked) → P1 (602, −2), P2 (2, 598), P3 (−598, −2), P4 (2, −602) m (4 m cell centres). No science values, no Perseverance measurement or sample locations.
- Default plan (Python): all 4 stops, 3.75 km, 89.9 min walking, 89.9 of 384 usable O2, lowest margin 294 min. Browser planner reproduces it (O2 diff 0.004 min, same order); shown on the page as a consistency check.
- Tests (`tests/test_astro.py`, synthetic grids only, 7 pass): analytic all-firm round trip; sand band costs more / detour never costs more; wall with a gap (path goes through the gap, never on blocked cells); unreachable stop skipped; stop beyond the O2 budget skipped; more O2 never visits fewer stops; best order is the cheaper loop. Every plan: ends at base, O2 ≤ usable, margin ≥ 0 at every step.
- Web: oxygen and reserve sliders (recompute in the browser), include/exclude stops, walk replay (play/pause, scrubber, speed), "Oxygen left" bar (reserve hatched) and "Return margin" bar, low-margin warning, skeleton banner. Output `web/data/jezero/astronaut/` (astronaut.json 2.7 kB + class_prior_4m.png 1.4 kB). Screenshots `qa/screenshots/S5_astronaut_*.png` (`tools/screenshot_astronaut.py`, 0 console errors).

#### S6 supplementary checks (tech-lead, 2026-11-14; details in team/tech/feasibility-step2-analysis.md "第五輪補件")

Scripts `spikes/s6_*.py`, outputs `qa/jezero/S6_*.{png,json}`. No web change.

- SIM 3464 vs HiRISE offset: not determined. Metadata: base map = CTX 6 m mosaic (Caltech, Feb 2018), publication scale 1:75,000, no positional accuracy stated. Edge-matching of the AOI contacts (method fixed before running) gave contradictory shifts (ortho gradient +64 E/−124 N m; DTM slope −36 E/+84 N m), so no number is claimed. Layer stays "not registered to HiRISE".
- Photo azimuth (J5): verified on 3 Navcam images (sols 48, 73, 174) by matching the photo skyline to the CTX DTM horizon: true azimuth = camera-model (CAHVORE) A vector rotated by the `attitude` quaternion (w,x,y,z; rover → north-east-down); best azimuth offset ≤ 1.0°, RMS ≤ 0.18°. `mastAz` is rover-relative (off by the rover heading, 156–295° here) and must not be drawn as a heading. 3 other images not informative (skyline blocked). Front Hazcam / Mastcam-Z not verified.
- CRISM four-quadrant check (X3-2 rule, ≤ 20 m): frt00005c5e quadrant deviations 8.9/11.8/19.9/31.7 m, hrl000040ff 7.7/7.7/17.8/42.0 m → both fail with the Q3 method (nearest resampling). With bilinear resampling hrl000040ff passes (≤ 6.6 m) and frt00005c5e still fails (21.8 m); verdict kept on the original method. Correction: hrl000040ff native pixel is 36 m (Q3 recorded 18 m).
- SuperCam PDS label: each calibrated-spectra label carries ROVER_NAV_FRAME SITE/DRIVE and the rover pose in the site frame (no target coordinates); the masterlist EDR file names also encode site/drive, so measurements can be placed on waypoints by site/drive instead of by sol (not re-done this round).
- Horizons (Q6): east longitude must be entered negative for Mars (stated by Horizons; Sun elevation 76.22° vs rover telemetry 76.02° at sol 11). Local true solar time derived from the hour angle (Horizons gives n.a.). AOI shadow from the HiRISE DTM: < 5 % whenever the Sun is ≥ 10° high (LTST ~6.5–17.5 h); 7–20 % at 5°, 28–64 % at 2°. Recommendation: remaining-daylight only.
- DONKI (Q7): **not done — DEMO_KEY rate-limited (429, retried once in the main session too); waiting for a team api.nasa.gov key.** CCMC endpoint timed out. No key requested and no workaround tried.
- AI4MARS (Q8): v0.6, CC-BY-4.0, 16.2 GB merged zip; Perseverance Navcam 4,573 (+2,122 early-named) images, 3,827 NAV labels (2,191 at 72 main-AOI waypoints), 8,508 geology labels; no expert test set for Perseverance; paper baseline (Curiosity only) 94.97 % overall; no public weights found. Not downloaded.

#### S4 multi-window X3 positioning check (`pipeline/multiwindow_x3.py` → `qa/jezero/multiwindow/x3_windows.json`, `X3_<i>_<j>.png`)

Same method as `pipeline/align.py` (CTX 6 m ortho vs HiRISE ortho on a 6 m grid, high-pass σ 60 m, phase correlation, one global shift, then four quadrant registrations; vertical offset = median CTX − HiRISE DTM on 20 m after the shift). Window (i, j) = main AOI shifted by (2400 i, 2400 j) m; habitat = main habitat shifted the same (assumed; no waypoint used). HiRISE ortho per window from the USGS S3 mirror (strip rows, window + 300 m margin); DTM from the local full HiRISE mosaic; MOLA from a new wide 463 m window (`data_raw/jezero/windows/mola_wide.tif`). Self-test: the same code on (0,0) reproduces the checkpoint-1 numbers exactly. No routes, classes or comparison numbers were computed. Items 3–4 are reported and not used to drop a window (decision 2026-11-14).

| Window | Habitat x, y (m) | HiRISE DTM cover | Global shift E, N (m) | Vertical offset applied to CTX (m) | Quadrant dev (m) | X3-1/2 | X3-3 ref − MOLA (m) | X3-4 prior − MOLA std (m) | Ortho download |
|---|---|---|---|---|---|---|---|---|---|
| (0,0) main | 0, 0 | 100 % | −2.1, +1.8 | −1.03 | 0.3 / 0.3 / 0.7 / 0.4 | pass | −11.0 ± 10.7 (fail) | 11.7 (fail) | checkpoint 1 |
| (−1,0) | −2400, 0 | 100 % | −1.8, +0.6 | −1.96 | 0.4 / 0.4 / 0.9 / 0.7 | pass | −17.7 ± 10.7 (fail) | 10.3 (fail) | 152 MB / 355 s |
| (−1,1) | −2400, 2400 | 100 % | −1.2, +0.9 | +0.57 | 0.0 / 0.7 / 0.3 / 0.4 | pass | −12.2 ± 7.6 (fail) | 8.4 (pass) | 152 MB / 354 s |
| (−2,1) | −4800, 2400 | 100 % | −0.9, +0.3 | +0.38 | 0.6 / 0.3 / 0.3 / 0.3 | pass | −9.2 ± 13.1 (fail) | 13.9 (fail) | 152 MB / 327 s |
| (−3,1) | −7200, 2400 | 100 % | −0.9, +0.3 | +0.55 | 0.3 / 0.7 / 0.0 / 0.0 | pass | −32.0 ± 24.6 (fail) | 23.2 (fail) | 152 MB / 319 s |
| (−4,0) rim | −9600, 0 | 97.5 % | −0.6, −1.2 | +2.98 | 0.7 / 0.3 / 1.2 / 0.7 | pass | −24.7 ± 49.9 (fail) | 47.3 (fail) | 152 MB / 329 s |

All six windows pass X3 items 1–2 (largest quadrant deviation 1.2 m against 20 m) → none is dropped; the locked multi-window rule keeps all 6. Items 3–4 (MOLA 463 m grid) fail in every window except item 4 in (−1,1), the same pattern as the main AOI; the larger misfits at (−3,1) and (−4,0) are on the rough crater-rim terrain, where the 463 m grid is coarsest relative to relief (observation, not tested). The (0,0) item-4 value here (11.7 m, 30 interior cells) differs from checkpoint 1 (14.3 m, 675 cells) because this code samples MOLA cells inside the window only; the checkpoint-1 value stays the record.

### 2026-11-14 round 6 (T1–T7, tech-lead)

#### T1 rover recon: the single rerun with the fixed hard energy rule

Run 2026-11-14 04:20–04:30 (local), commit `bc3068a`, 30 loops, 556 s. Code difference from the first v2 run (round 5): only the hard energy rule's margin (one → two maximum steps, `rover_sim.py`, two lines; already in commit `c0ddfdc`) and the test file (xfail removed from `test_no_loop_over_budget`). Goal rule v2, sand v2 classes (manager lock), budget 4,000, sand ×6, 15 m, 30 loops: unchanged. Run once; acceptance tests 7/7 pass (`tests/test_recon.py`). **The rerun is the record**; the first run stays here marked "budget defect". Report `qa/jezero/T1_rover_v2_rerun_report.json` (`spikes/t1_report.py`, evaluation only), figure `qa/jezero/T1_coverage_run1_rerun.png`; first-run outputs kept as `data_work/jezero/recon_*_v2_run1_defect.*`.

| | First v2 run (budget defect) | **Rerun (record)** |
|---|---|---|
| Loops over the 4,000 budget | 5 (loops 1, 12, 13, 20, 24: 4,003.9 / 4,004.5 / 4,004.8 / 4,003.7 / 4,001.3) | **0** (max 3,987.5) |
| Distance / AOI observed | 46.5 km / 11.3 % | 46.5 km / 11.3 % |
| Observed after loops 1/5/10/20/30 | 0.5 / 3.2 / 5.4 / 9.0 / 11.3 % | 0.5 / 3.2 / 5.4 / 8.9 / 11.3 % |
| Goals reached / safety returns | 12 / 14 | 12 / 14 |
| Within 1200 m: N NE E SE S SW W NW | 11.7 23.2 27.1 22.2 27.8 16.8 14.1 10.4 | 11.7 23.2 27.1 22.2 27.9 16.8 13.9 10.7 |
| By distance 0–600 / 600–1200 / > 1200 m | 49.8 / 3.3 / 0.0 % | 49.8 / 3.3 / 0.0 % |
| SuperCam sites unlocked (15 m, of 59) after loops 1/5/10/20/30 | 2 / 10 / 12 / 19 / 22 | 2 / 10 / 12 / 19 / 22 |
| Units of unlocked sites | all 22 Njf | all 22 Njf |

The fix changed only where a few safety returns start (a few metres earlier); the trajectories and every reported statistic are the same within 0.3 percentage points. Nothing else was changed and the simulation was not run again.

#### T2 route A vs B — definitions, written here BEFORE the first real-terrain run (locked afterwards)

Code `pipeline/compare_ab.py` (docstring repeats this), tests `tests/test_compare.py` (synthetic grids only; 8 pass before the real run). Sources of each rule: direction.md 第六次改版「偵察前後的量化對比」「參數鎖定狀態」, TECH_LEAD_BRIEF 第六次更新 T2, R3 proposals above, MVP_PLAN P7-3/P7-6.

- Knowledge states (2 m class grids, 0 firm / 1 rough / 2 sand / 3 blocked; astronaut blocked = slope ≥ 25°):
  - **A** prior only (CTX 20 m classes; no sand class).
  - **A+** `optimistic prior, uses reference, bracket only`: A plus sand on every cell of each 60 m block (30 × 30 cells aligned to the AOI corner, the S2 blocks) whose reference cells are ≥ 50 % sand; prior-blocked cells stay blocked.
  - **B@k** rover knowledge after loop k = 1, 5, 10, 20, 30 of the T1 rerun (the record): reference class where the rover had observed the cell by the end of loop k, prior elsewhere.
  - **REF** reference classes everywhere = upper bound of what recon can give; **not route B**.
- Targets (locked R3): every point of the 300 m lattice aligned to the habitat inside the AOI, ≥ 300 m from the habitat, whose 2 m cell is not blocked on the prior nor on the reference. Independent of step 2. Distance bands by straight-line distance: [300, 600), [600, 1200), ≥ 1200 m (same bands as the rover rule).
- One test route per target: habitat → target on the least-O2 path of the knowledge state (locked astronaut model, `pipeline/astro_plan.py`: 2.5 km/h, speed 1/0.6/0.35, O2 factor 1/1.5/2.1; 8-connected; step cost = mean of the two cells × step length), then back along the same path reversed. Grid: the native 2 m class grid (the 4 m grid of the step-3 skeleton was a web-display choice). No dwell time at the target (the locked parameters have none).
- Evaluated on the reference (same path, nothing replanned on the way):
  - predicted time / O2 = on the state the route was planned on; actual = on the reference classes, with reference-blocked cells charged at the sand rate and counted separately (MVP_PLAN P7-3);
  - O2 error = actual − predicted (nominal min) and 100 × (actual − predicted) / predicted; time error likewise;
  - within budget = O2 ≤ usable 384 nominal min (480 × 0.8), predicted and actual;
  - **hazard metres** (main signal) = metres walked inside hazard zones; blocked metres = metres on reference-blocked cells; sand metres = metres on any reference sand cell (informative);
  - **crossings** = runs inside hazard zones: in-zone stretches separated by < 10 m outside a zone are merged; a merged run counts once if its in-zone metres are ≥ 10 m;
  - zones entered = distinct hazard zones touched (footnote only).
  - Metres of a step a→b (length L) are split L/2 to a, L/2 to b (same convention as the cost).
- Hazard zone (locked): 8-connected component of reference sand-or-blocked cells, area ≥ 400 m², ≥ 80 % of its cells firm or rough on the prior (R3 wording of "not marked on the prior").
- A target unreachable on any state is listed and dropped from all columns (paired table).
- Reported per state and per band: n; mean and median of each quantity; counts within budget; totals of hazard / blocked metres and crossings; paired differences (state − A) mean and median; recon share of the possible improvement = (A − B@k) / (A − REF) on the means of actual O2, hazard metres and crossings (A+ reported the same way, as the bracket).
- All outputs: derived from simulated recon and assumed parameters; sand classes `heuristic, not yet reviewed`; review pending.

**Freeze statement (2026-11-14, before the first real-terrain comparison run).** Everything that affects the T2 numbers is fixed at commit `e17452a` (`pipeline/compare_ab.py`, `pipeline/astro_plan.py`, `pipeline/rover_sim.py`, `pipeline/terrain.py`, `pipeline/sandfield.py`, the definitions above) plus these generated inputs (not in git; SHA-256):
`terrain_2m.npz` c9e14772d15c5c3d51f755814151e1317ab8b86c7e5556cb7d35e7234cd755f8 · `terrain_2m.json` 7556f85b536d46302efab452e5047a00a70b9e18c9013dbea54abcf804f03c4d · `recon_loops.json` 47791c62c0eb85c0d5aee40f487a7aec86f3ff524b386c43c01d76c3bc77ef33 · `recon_state.npz` c227832634e6fd7b93c81d1cc7ee1fc91be99b8329f334e47786567e174f7838.
From the first comparison number on, terrain classes, parameters, AOI, targets, rules and definitions are not changed; the numbers are reported as they come out, once, and not re-run. Interpretations written here before the run (flagged for manager): hazard metres count metres inside hazard zones (sand metres on any sand cell are listed separately); a merged crossing is measured by its in-zone metres (the < 10 m gaps are not added); no dwell time at the target.

#### T2 result — the single run, 2026-11-14 04:29:58 CST (8.9 s), frozen commit `e17452a`, reported as computed

63 targets (8 at 300–600 m, 31 at 600–1200 m, 24 beyond 1200 m), 0 unreachable, 156 hazard zones (one fewer than the 157 components ≥ 400 m² counted in round 5: one 28,832 m² component, on steep ground, is 21 % blocked on the prior, so only 78.7 % of it is firm/rough there and it fails the 80 % "not marked" rule). Rover had observed 0.5 / 3.2 / 5.4 / 8.9 / 11.3 % of the AOI after loops 1 / 5 / 10 / 20 / 30. A+ marks 38.5 % of the AOI as sand. Output `data_work/jezero/compare_ab.json` (+ `_paths.json`, `hazard_zones.npy`). Nothing was changed or re-run after these numbers. O2 and time in nominal minutes / minutes; every route is habitat → target → habitat. derived; sand classes heuristic, not yet reviewed.

**All targets (n = 63)**

| State | Pred O2 | Actual O2 | O2 error (min / %) | Pred / actual ≤ 384 | Pred time | Actual time | Hazard m (mean / total) | Crossings (mean / total) | Blocked m total | Sand m (mean) | Zones entered (mean) | Length m | vs A: hazard m | vs A: actual O2 | vs A: actual time | vs A: crossings | Share of possible gain O2 / hazard m / crossings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A (prior only) | 50.8 | 194.6 | +143.8 / +263 % | 63 / 63 | 50.8 | 104.6 | 1156 / 72844 | 10.78 / 679 | 0 | 1158 | 2.40 | 2116 | – | – | – | – | – |
| A+ (optimistic prior, uses reference, bracket only) | 88.2 | 176.2 | +87.9 / +93 % | 63 / 61 | 75.4 | 108.9 | 803 / 50561 | 18.68 / 1177 | 0 | 803 | 3.46 | 2823 | -354 | -18.5 | +4.3 | +7.90 | 17 % / 35 % / -111 % |
| B@1 | 51.0 | 195.7 | +144.7 / +264 % | 63 / 63 | 50.9 | 105.0 | 1165 / 73399 | 10.70 / 674 | 0 | 1166 | 2.40 | 2122 | +9 | +1.0 | +0.5 | -0.08 | -1 % / -1 % / 1 % |
| B@5 | 51.8 | 185.4 | +133.6 / +240 % | 63 / 61 | 51.5 | 101.6 | 1061 / 66820 | 9.51 / 599 | 0 | 1062 | 2.10 | 2141 | -96 | -9.3 | -3.0 | -1.27 | 8 % / 9 % / 18 % |
| B@10 | 54.1 | 175.1 | +121.0 / +201 % | 63 / 63 | 52.8 | 98.1 | 987 / 62192 | 8.86 / 558 | 0 | 988 | 1.81 | 2168 | -169 | -19.5 | -6.5 | -1.92 | 18 % / 17 % / 27 % |
| B@20 | 56.2 | 166.8 | +110.7 / +175 % | 63 / 63 | 54.2 | 95.7 | 904 / 56937 | 10.11 / 637 | 0 | 905 | 2.03 | 2210 | -252 | -27.8 | -8.9 | -0.67 | 25 % / 25 % / 9 % |
| B@30 | 58.3 | 166.5 | +108.2 / +161 % | 63 / 63 | 55.1 | 95.6 | 905 / 57043 | 9.22 / 581 | 0 | 907 | 2.02 | 2214 | -251 | -28.2 | -9.0 | -1.56 | 25 % / 25 % / 22 % |
| REF (upper bound, not B) | 83.5 | 83.5 | +0.0 / +0 % | 63 / 63 | 71.1 | 71.1 | 147 / 9266 | 3.68 / 232 | 0 | 147 | 0.83 | 2648 | -1009 | -111.1 | -33.4 | -7.10 | – |

Medians (A / B@30 / REF): actual O2 186.6 / 170.5 / 80.1; hazard m 1059 / 952 / 129; paired median B@30 − A: hazard m -167, actual O2 -19.0.

**300-600 m (n = 8)**

| State | Pred O2 | Actual O2 | O2 error (min / %) | Pred / actual ≤ 384 | Pred time | Actual time | Hazard m (mean / total) | Crossings (mean / total) | Blocked m total | Sand m (mean) | Zones entered (mean) | Length m | vs A: hazard m | vs A: actual O2 | vs A: actual time | vs A: crossings | Share of possible gain O2 / hazard m / crossings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A (prior only) | 17.4 | 49.8 | +32.4 / +187 % | 8 / 8 | 17.4 | 29.6 | 252 / 2019 | 2.88 / 23 | 0 | 252 | 1.12 | 724 | – | – | – | – | – |
| A+ (optimistic prior, uses reference, bracket only) | 31.4 | 50.9 | +19.5 / +69 % | 8 / 8 | 24.6 | 32.1 | 228 / 1827 | 3.88 / 31 | 0 | 228 | 1.12 | 857 | -24 | +1.1 | +2.5 | +1.00 | -6 % / 14 % / -50 % |
| B@1 | 17.6 | 49.9 | +32.3 / +183 % | 8 / 8 | 17.5 | 29.7 | 252 / 2015 | 2.88 / 23 | 0 | 252 | 1.12 | 729 | -1 | +0.1 | +0.1 | +0.00 | -1 % / 0 % / 0 % |
| B@5 | 18.5 | 49.5 | +30.9 / +162 % | 8 / 8 | 18.3 | 29.9 | 248 / 1987 | 2.12 / 17 | 0 | 248 | 0.88 | 755 | -4 | -0.3 | +0.3 | -0.75 | 2 % / 2 % / 38 % |
| B@10 | 20.6 | 44.1 | +23.5 / +102 % | 8 / 8 | 19.5 | 28.3 | 200 / 1604 | 1.62 / 13 | 0 | 200 | 0.75 | 785 | -52 | -5.7 | -1.3 | -1.25 | 28 % / 30 % / 62 % |
| B@20 | 22.0 | 44.3 | +22.4 / +89 % | 8 / 8 | 19.9 | 28.3 | 205 / 1636 | 2.12 / 17 | 0 | 205 | 0.88 | 780 | -48 | -5.4 | -1.3 | -0.75 | 27 % / 27 % / 38 % |
| B@30 | 24.2 | 40.5 | +16.3 / +51 % | 8 / 8 | 21.9 | 28.0 | 161 / 1284 | 1.38 / 11 | 0 | 161 | 0.75 | 856 | -92 | -9.3 | -1.6 | -1.50 | 46 % / 53 % / 75 % |
| REF (upper bound, not B) | 29.6 | 29.6 | +0.0 / +0 % | 8 / 8 | 23.6 | 23.6 | 78 / 620 | 0.88 / 7 | 0 | 78 | 0.50 | 834 | -175 | -20.2 | -6.0 | -2.00 | – |

Medians (A / B@30 / REF): actual O2 38.2 / 29.9 / 24.8; hazard m 179 / 78 / 27; paired median B@30 − A: hazard m -38, actual O2 -5.2.

**600-1200 m (n = 31)**

| State | Pred O2 | Actual O2 | O2 error (min / %) | Pred / actual ≤ 384 | Pred time | Actual time | Hazard m (mean / total) | Crossings (mean / total) | Blocked m total | Sand m (mean) | Zones entered (mean) | Length m | vs A: hazard m | vs A: actual O2 | vs A: actual time | vs A: crossings | Share of possible gain O2 / hazard m / crossings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A (prior only) | 42.3 | 145.6 | +103.3 / +238 % | 31 / 31 | 42.3 | 81.0 | 821 / 25466 | 9.03 / 280 | 0 | 823 | 2.26 | 1763 | – | – | – | – | – |
| A+ (optimistic prior, uses reference, bracket only) | 71.0 | 135.6 | +64.6 / +89 % | 31 / 31 | 60.7 | 85.4 | 593 / 18376 | 14.00 / 434 | 0 | 593 | 3.10 | 2275 | -229 | -10.0 | +4.4 | +4.97 | 13 % / 33 % / -79 % |
| B@1 | 42.5 | 146.6 | +104.1 / +239 % | 31 / 31 | 42.5 | 81.5 | 828 / 25679 | 9.06 / 281 | 0 | 830 | 2.26 | 1769 | +7 | +1.0 | +0.5 | +0.03 | -1 % / -1 % / -1 % |
| B@5 | 43.3 | 141.4 | +98.1 / +221 % | 31 / 31 | 43.0 | 79.8 | 773 / 23971 | 7.74 / 240 | 0 | 775 | 2.10 | 1784 | -48 | -4.3 | -1.2 | -1.29 | 6 % / 7 % / 21 % |
| B@10 | 45.1 | 129.7 | +84.6 / +180 % | 31 / 31 | 44.1 | 75.8 | 686 / 21268 | 6.48 / 201 | 0 | 687 | 1.61 | 1810 | -135 | -15.9 | -5.3 | -2.55 | 21 % / 19 % / 41 % |
| B@20 | 47.0 | 125.3 | +78.4 / +157 % | 31 / 31 | 45.3 | 74.7 | 642 / 19915 | 7.10 / 220 | 0 | 644 | 1.71 | 1849 | -179 | -20.3 | -6.3 | -1.94 | 27 % / 26 % / 31 % |
| B@30 | 48.4 | 123.9 | +75.5 / +145 % | 31 / 31 | 45.8 | 74.1 | 633 / 19634 | 6.52 / 202 | 0 | 635 | 1.74 | 1846 | -188 | -21.7 | -6.9 | -2.52 | 28 % / 27 % / 40 % |
| REF (upper bound, not B) | 69.1 | 69.1 | +0.0 / +0 % | 31 / 31 | 59.0 | 59.0 | 124 / 3848 | 2.77 / 86 | 0 | 124 | 0.68 | 2203 | -697 | -76.5 | -22.0 | -6.26 | – |

Medians (A / B@30 / REF): actual O2 145.0 / 125.8 / 67.8; hazard m 834 / 584 / 88; paired median B@30 − A: hazard m -159, actual O2 -19.0.

**>1200 m (n = 24)**

| State | Pred O2 | Actual O2 | O2 error (min / %) | Pred / actual ≤ 384 | Pred time | Actual time | Hazard m (mean / total) | Crossings (mean / total) | Blocked m total | Sand m (mean) | Zones entered (mean) | Length m | vs A: hazard m | vs A: actual O2 | vs A: actual time | vs A: crossings | Share of possible gain O2 / hazard m / crossings |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A (prior only) | 73.0 | 306.3 | +233.3 / +321 % | 24 / 24 | 72.9 | 160.0 | 1890 / 45360 | 15.67 / 376 | 0 | 1892 | 3.00 | 3037 | – | – | – | – | – |
| A+ (optimistic prior, uses reference, bracket only) | 129.4 | 270.3 | +140.9 / +106 % | 24 / 22 | 111.2 | 164.9 | 1265 / 30358 | 29.67 / 712 | 0 | 1265 | 4.71 | 4186 | -625 | -36.0 | +4.8 | +14.00 | 19 % / 37 % / -142 % |
| B@1 | 73.1 | 307.7 | +234.6 / +322 % | 24 / 24 | 73.0 | 160.6 | 1904 / 45706 | 15.42 / 370 | 0 | 1906 | 3.00 | 3041 | +14 | +1.4 | +0.6 | -0.25 | -1 % / -1 % / 3 % |
| B@5 | 73.9 | 287.5 | +213.6 / +291 % | 24 / 22 | 73.7 | 153.7 | 1703 / 40862 | 14.25 / 342 | 0 | 1704 | 2.50 | 3063 | -187 | -18.7 | -6.3 | -1.42 | 10 % / 11 % / 14 % |
| B@10 | 76.9 | 277.5 | +200.6 / +261 % | 24 / 24 | 75.2 | 150.2 | 1638 / 39320 | 14.33 / 344 | 0 | 1640 | 2.42 | 3090 | -252 | -28.8 | -9.9 | -1.33 | 15 % / 15 % / 14 % |
| B@20 | 79.4 | 261.2 | +181.8 / +228 % | 24 / 24 | 77.1 | 145.2 | 1474 / 35385 | 16.67 / 400 | 0 | 1476 | 2.83 | 3153 | -416 | -45.0 | -14.8 | +1.00 | 24 % / 25 % / -10 % |
| B@30 | 82.4 | 263.5 | +181.1 / +218 % | 24 / 24 | 78.0 | 145.8 | 1505 / 36125 | 15.33 / 368 | 0 | 1507 | 2.79 | 3142 | -385 | -42.8 | -14.2 | -0.33 | 23 % / 23 % / 3 % |
| REF (upper bound, not B) | 120.2 | 120.2 | +0.0 / +0 % | 24 / 24 | 102.7 | 102.7 | 200 / 4798 | 5.79 / 139 | 0 | 200 | 1.12 | 3828 | -1690 | -186.1 | -57.3 | -9.88 | – |

Medians (A / B@30 / REF): actual O2 317.4 / 272.3 / 125.3; hazard m 1953 / 1506 / 233; paired median B@30 − A: hazard m -246, actual O2 -28.9.

Observations (no change follows from them): no round trip exceeds the 384 budget on the reference under A; 2 do under B@5 ((−1500, −900) 384.5 and (−1200, −900) 393.4) and 2 under A+ ((−1500, −600) 398.6 and (−1500, −900) 413.2), all beyond 1200 m; blocked metres are 0 for every state (the 2 m astronaut-blocked cells are rare and avoided or not crossed); hazard metres ≈ sand metres. B@1 is marginally worse than A (+9 m, +1.0 min). Crossings are not monotonic in loops (B@20 has more than B@10), because routes that avoid part of a sand belt can enter it in more, shorter stretches. A+ lowers hazard metres (35 % of the possible gain) but raises crossings (−111 %): the 60 m blocks push routes around and through more belt edges.

#### T3 web: astronaut map is now the first page (`web/index.html`, `web/astronaut.js`; `pipeline/export_compare.py`)

- `index.html` = astronaut map (route A vs B); old map-data page moved to `data.html`; `astronaut.html` redirects. Recon page (`recon.html`) shows the T1 rerun; its About text updated to goal rule v2 and the rerun.
- Shows the 63 test points; for the selected one, route A, route B after 1/5/10/20/30 loops, optional A+ and reference bound, a table of the T2 quantities, and a walk replay with "Oxygen left (actual)", "Return margin, as the plan sees it" (oxygen used so far on the reference minus O2 home on the map the route was planned on) and "Return margin, true (reference)". The oxygen sliders only change the budget verdicts (routes do not depend on the budget). A panel summarises all 63 points; the full table (all states, three distance bands) is a dialog. Default test point = lattice point (600, 0) (the step-3 skeleton's first placeholder rule), not chosen by its numbers.
- Export only reformats `compare_ab*.json` (non-finite band edge written as null); nothing is recomputed. 7.4 MB (63 route files). Old skeleton data `web/data/jezero/astronaut/` removed.
- Screenshots `qa/screenshots/T3_walk_*.png` (`tools/screenshot_astronaut.py`, 0 console errors), `T1_recon_rerun_*.png`.

#### T4 documents

README (result summary, Limitations with every item listed in TECH_LEAD_BRIEF T4), `docs/PROJECT_PAGE.md` (English project-page text; NASA Data from the table above), `docs/REFERENCES.md` (added SIM 3464, MOLA PEDR, SuperCam, CRISM, samples, Horizons, Deahn, AI4MARS, parameter sources), `docs/AI_USE.md`.

#### T5 Navcam viewing directions (`pipeline/photo_heading.py`, runs after `export` in `pipeline.run`)

256 of 256 Navcam images in `web/data/jezero/photos.json` got `view` = azimuths of the rays through the centre and the left/right edges (mid-height) of the delivered frame, from the CAHV camera model rotated by the `attitude` quaternion (method of S6-2). Check against S6-2: the edge azimuths match the azimuth spans of the detected skyline in the 3 passing images within 0.0–2.1° (e.g. 245.8–293.1° vs 246.0–292.9°; the S6 spans end at the outermost skyline column used, not at the frame edge). `mast_az` / `mast_el` renamed `mast_az_rover_frame` / `mast_el_rover_frame` and no longer shown as a direction. Map-data page: 45 m wedges (layer "Navcam viewing directions", derived); photo cards show "looking toward N° from north". Front Hazcam and Mastcam-Z: no direction. Screenshots `qa/screenshots/T5_navcam_*.png`.

#### Not done this round

T6 (multi-window A vs B) and T7 (rover sensitivity: budget 8,000 / 16,000, sand ×3) were not run. Their rules stay as written (direction.md); Limitations says they have not been run.

#### T6 multi-window A vs B — settings, written here BEFORE any window run (2026-11-14)

Code `pipeline/multiwindow_ab.py` (stages terrain / recon / compare / table), tests `tests/test_multiwindow.py` (synthetic only, 3 pass). Rules: direction.md 嚴謹度 2 (locked), TECH_LEAD_BRIEF 第六次更新 T6. Nothing is tuned per window.
- Windows (−1,0), (−1,1), (−2,1), (−3,1), (−4,0) = main AOI shifted by (2400 i, 2400 j) m on the main local grid (same projection and pixel alignment). Inside a window all coordinates are relative to the window habitat = main habitat shifted by the same amount (no waypoint used), so the window AOI is again x −1700..700, y −1000..1400 m, habitat (0, 0), and the 300 m target lattice is aligned to it.
- Inputs: HiRISE ortho strip of the window (S4 download), the full HiRISE 1 m DTM mosaic (`data_raw/jezero/step2/hirise_dtm_full.tif`, same product and byte size as the main AOI's source), CTX DTM shifted by the window's own X3 global shift and vertical offset (S4 table above).
- Terrain classes: `pipeline/terrain.py` functions and PARAMS imported, its run() body repeated line for line (minus the unused v1 ripple index and the QA figures); sand = SAND_V2; roughness 0.059 m; slopes 8/15/20/25°; 3×3 majority. **Self-test:** window (0,0) through this code reproduces the main `terrain_2m.npz` exactly (class_ref, class_prior, both rover-blocked masks: 0 of 1,440,000 cells differ; slope / roughness max difference 0.0). `data_work/jezero/windows/selftest_0_0.json`.
- Recon: `rover_sim.simulate` with `rover_sim.PARAMS` unchanged (4,000, ×6, 15 m, goal rule v2, 30 loops, fixed hard energy rule). Comparison: `compare_ab.compare` unchanged (definitions frozen at `e17452a`, including the three interpretations of the T2 freeze statement that manager is reviewing — if manager changes them, the window numbers follow the same change). Each window: recon once, comparison once (the code refuses a second run).
- Outputs per window `data_work/jezero/windows/<i>_<j>/` (terrain_2m.*, recon_loops.json, recon_state.npz, compare_ab*.json, hazard_zones.npy); table `data_work/jezero/windows/t6_table.json`.
- **Stops instead of guessing** (not run until manager writes the rule down):
  1. HiRISE gap (only (−4,0), DTM cover 97.4 %): the locked rule says "gap = impassable, targets within 50 m of the gap dropped", but not in which knowledge states the gap is impassable (prior / A+ / B / REF / the rover's belief), nor whether gap cells enter the hazard-zone and blocked-metre definitions. The code records the no-data mask and refuses recon / compare on any window with a no-data cell.
  2. Habitat cell impassable on the prior: the rule says "nearest passable cell" but not whether passable for the astronaut (< 25°) or the rover (< 20°). The code stops if this happens.
  3. Cross-window statistic (BRIEF T6 "各格的差、方向一致的格數、中位數與信賴區間；6 格方向一致才報 p 值"; direction.md 嚴謹度 3): not specified which quantity, which B (loop), mean or median within a window, bootstrap scheme / CI level, one- or two-sided test. **Proposal, NOT computed** (written before any window number): per window d = mean over its targets of (B@30 − A) hazard metres (the T2 column "vs A: hazard m", all targets); secondary the same for actual O2; report the 6 values, how many are < 0, their median, and a 95 % percentile bootstrap CI of the median (resample the 6 windows with replacement, 10,000 draws, seed 20261114); Wilcoxon signed-rank, exact, two-sided, only if all 6 have the same sign. Until manager decides, only the per-window T2 tables and the descriptive signs are reported.

#### T7 rover sensitivity — settings, written here BEFORE the runs (2026-11-14)

Code `pipeline/rover_sensitivity.py`. Settings (direction.md 嚴謹度 4; decided after the locked run's coverage 11.3 % was known, before any A vs B number; each run once, listed next to the locked result, never replacing it): `budget_8000` (loop budget 8,000, sand ×6), `budget_16000` (16,000, sand ×6), `sand_x3` (4,000, sand ×3). Everything else = `rover_sim.PARAMS` (rule v2, 75 % planning + 25 % reserve, 15 m, 30 loops, rover blocked ≥ 20°, firm 1 / rough 2.5), main AOI terrain (frozen hashes above). Comparison `compare_ab.compare` unchanged; A, A+, REF do not depend on the rover and are checked equal to the frozen T2 file. Outputs `data_work/jezero/sensitivity/<setting>/`; the main recon and comparison files are not touched. Reported: coverage after loops 1/5/10/20/30, by direction and distance, and the A vs B table.

### 2026-11-14 round 7 (U1–U4, T6–T7 continued, tech-lead)

#### U1 wording (no number changed)
README step 3 now says the route is *planned* to keep enough oxygen and the page shows whether it really does; results written in the order of direction.md 主訊息 (underestimate 3.8× → recon sees 11.3 % and recovers about a quarter, near n = 8 → still underestimates by 108, loops 20–30 no gain, partial knowledge sometimes worse and why). PROJECT_PAGE summary rewritten the same way; `cheap` removed; "no server or network" → "no backend: any static file server". One oxygen unit everywhere: "nominal minutes" (short "nominal min"; time stays "min"). Home page: crossings row says they do not fall steadily with loops; budget-fit rows say they are not evidence for either route. Limitations (README and About): the three T2 definitions set by the implementer and ratified by manager after the numbers (process violation), dwell note, 63 points not independent, one AOI / one recon run, origin of the 156 hazard zones. The rover's "always keeps enough energy" (recon page) reworded to the hard rule + test.

#### U2 per-point summary of the frozen T2 numbers (`spikes/u2_pointwise.py`; reads `compare_ab.json` only, compare_ab not run)
Describes the spread of the 63 test points; **not a significance test** (shared walk out of the habitat, one recon, one AOI); added after the numbers were seen; no number changed. Rules in the script header (better / worse / same on the stored values; for the O2 error better = smaller absolute error; 10,000 resamples of the points, seed 20261114, 95 % percentile interval of the mean). Output `qa/jezero/U2_pointwise_summary.json` (all states × 4 quantities × all points and 3 bands), web copy `web/data/jezero/compare/pointwise.json` (full-table dialog section "Point by point", home-page sentence).

| B@30 − A, all 63 | better / worse / same | mean [95 % resampling interval] | median (q1, q3; min, max) |
|---|---|---|---|
| actual O2 | 56 / 6 / 1 | −28.16 [−36.37, −20.48] | −18.98 (−40.78, −5.57; −104.85, +34.76) |
| hazard m | 52 / 6 / 5 | −250.8 [−322.0, −184.9] | −167.1 (−361.5, −67.8; −942.7, +291.8) |
| O2 error (abs) | 57 / 5 / 1 | −35.61 [−43.91, −27.53] | −27.14 (−48.8, −13.1; −113.9, +31.4) |
| crossings | 39 / 14 / 10 | −1.56 [−2.57, −0.52] | −2.0 (−4.0, 0.0; −16, +8) |

Against manager's check (O2 56/6/1, mean −28.2 (−36.1 to −20.4); metres 52/6/5, −251 (−320 to −184)): counts and means identical; the interval ends differ by ≤ 2 (different resampling draws).

#### U3 home-page shortcuts
Three buttons under the test-point selector (rule shown beside them): median walk = the point whose B@30 − A actual O2 equals the median of the 63 differences (T51, (−300, −600), −19.0); most improved (T4, (−300, 1200), −104.9); most worsened (T14, (300, 900), +34.8). Default point (600, 0) unchanged. Screenshots `qa/screenshots/U3_*.png` (`tools/screenshot_u3.py`, 0 console errors).

#### U4 multi-stop walk with dwell — code and DRAFT definitions for round 7 (draft, not run)
Code `pipeline/multistop.py` (reuses `astro_plan.py` unchanged), tests `tests/test_multistop.py` (synthetic only, 5 pass). **No real-terrain number has been computed; waiting for manager to confirm the definitions below.**

Draft definitions (round 7 = "go to the places step 2 selects, several per walk"; designed after seeing round 6; round 6 stays the pre-registered main comparison):
1. Unchanged from round 6: terrain classes (sand v2, manager lock), astronaut walk model (2.5 km/h; speed 1/0.6/0.35; O2 1/1.5/2.1; ≥ 25° blocked; 480 × 0.8 = 384 usable), rover knowledge of the T1 rerun, hazard zones and every round-6 quantity definition (incl. the three ratified points).
2. Targets: the output of step 2 (not decided; Shan). A and B (and A+, REF) plan to the **same target set**. Draft target set size: all step-2 targets in one walk if they fit, else the planner drops some (see 3). No targets exist yet, so nothing can be run.
3. Order rule (same as the step-3 skeleton): visit the most targets, then the least planned O2, subject to "after the dwell at each target, planned O2 used + planned O2 home ≤ usable"; brute force over orders for ≤ 7 targets, greedy nearest-feasible beyond. Each knowledge state chooses its own order and subset (so A and B may visit different subsets — **question for manager**: alternatively force B to use A's order).
4. Dwell: 18 minutes per visited target, charged as 18 nominal minutes of O2 (rate = walking on firm ground) — **to confirm**: time and O2, and whether the O2 rate at rest should differ (no source).
5. Evaluation on the reference: the planned tour (same cells, same order, nothing replanned) walked on the reference classes (blocked charged at the sand rate, as round 6). If the actual O2 exceeds the usable budget, report how many targets were reached under two readings (manager to choose one, or both): (i) targets whose dwell ends before the actual O2 used passes the usable budget; (ii, proposed main) targets after whose dwell the astronaut could still walk home on the reference within the usable budget (true return margin ≥ 0). Also the first point where the true return margin turns negative.
6. Report per state (A, A+, B@1/5/10/20/30, REF): planned / actual O2 and time, error, targets planned, targets reached (i)/(ii), hazard metres, sand metres, crossings (round-6 definitions, on the whole tour), whether actual ≤ usable (listed, not used as evidence), differences vs A; one walk only if step 2 gives one set, so no distribution — **question**: what to report if step 2 gives several alternative sets.
7. Run once after confirmation; every place it appears says "designed after seeing round 6; round 6 is the pre-registered main comparison".

#### U7 exploratory B* — rule (manager, TECH_LEAD_BRIEF 第七次更新) and code, written BEFORE the run
Label everywhere: `exploratory, designed after seeing the first comparison`; listed next to round 6, never in a headline. Code `pipeline/bstar.py` (rule copied in its docstring), tests `tests/test_bstar.py` (synthetic only, 3 pass). B*@k = B@k except unseen, prior-not-blocked cells, which get per-metre time and O2 = (1 − p_k) × prior class value + p_k × sand value; p_k = sand share among cells seen by the end of loop k whose reference is not blocked (one number for the AOI). Predicted = least-O2 path and its time / O2 on that map; actual = same path on the reference with every round-6 quantity (`compare_ab.evaluate_path`) unchanged. Same 63 targets, T1-rerun knowledge. Run once on the main AOI after T6 and T7; output `data_work/jezero/bstar/compare_bstar.json`. No point of the rule was unclear to me.

#### T6 result — four of the five extra windows, one run each, reported as computed
Settings commit `5f6cfaf` (04:45:54); statistics code `a499bb5` (04:55:49); recon runs started 04:50–04:51, comparisons computed 04:59:34 – 05:09:46 (2026-11-14 CST). Same code path for every window; nothing changed or re-run after any number (one formatting bug in the table script, a KeyError on the band count, was fixed after the comparisons; it touched no computed value). Classes self-test: window (0,0) through this code = main classes exactly. Rover: 0 loops over the 4,000 budget in every window. Table `data_work/jezero/windows/t6_table.json`, figure `qa/jezero/multiwindow/T6_windows_A_vs_B.png`, web: full-table dialog, section "Robustness checks". derived; simulated recon; sand classes heuristic, not yet reviewed.

**(−4,0) not run (stopped, waiting for manager):** 2.58 % of its 2 m cells have no HiRISE data (one strip on the west edge, x −1700 to −1495 m, y −1000 to +467 m; 1,622 m from the habitat); 1 of its 63 lattice targets ((−1500, −900), 11.7 m from the gap) falls under the 50 m drop rule. Open point: in which knowledge states the gap is impassable (prior / A+ / B / REF / the rover's belief) and whether gap cells count as hazard-zone or blocked cells. Its terrain classes are computed (`windows/-4_0/terrain_2m.*`; sand 7.7 %, rough 72.2 %).

| Window | Sand on reference | Rover saw after 30 loops (0–600 / 600–1200 m) | Targets | Hazard zones | Actual O2 A / B@30 / REF | B@30 − A O2 | Planned O2 A / B@30 (error A / B@30) | Hazard m A / B@30 / REF | B@30 − A hazard m | Share of possible gain O2 / hazard m |
|---|---|---|---|---|---|---|---|---|---|---|
| (0,0) main (T2, frozen) | 40.3 % | 11.3 % (49.8 / 3.3) | 63 | 156 | 194.6 / 166.5 / 83.5 | −28.2 | 50.8 / 58.3 (+143.8 / +108.2) | 1156 / 905 / 147 | −251 | 25 % / 25 % |
| (−1,0) | 47.0 % | 3.0 % (15.4 / 0.0), 20.0 km | 62 | 154 | 209.0 / 186.4 / 106.0 | −22.6 | 53.5 / 74.1 (+155.5 / +112.3) | 1205 / 1003 / 271 | −202 | 22 % / 22 % |
| (−1,1) | 14.0 % | 17.3 % (59.5 / 12.6), 54.6 km | 62 | 247 | 85.7 / 76.0 / 56.0 | −9.6 | 51.7 / 52.4 (+34.0 / +23.7) | 207 / 142 / 9 | −65 | 32 % / 33 % |
| (−2,1) | 20.7 % | 17.5 % (59.7 / 13.1), 60.4 km | 63 | 249 | 126.5 / 101.7 / 65.0 | −24.8 | 51.6 / 56.4 (+74.9 / +45.3) | 427 / 242 / 16 | −185 | 40 % / 45 % |
| (−3,1) | 38.0 % | 10.1 % (50.9 / 0.3), 40.0 km | 63 | 192 | 201.4 / 180.1 / 111.2 | −21.3 | 61.8 / 70.1 (+139.6 / +110.0) | 1013 / 815 / 156 | −198 | 24 % / 23 % |

B@k − A hazard m (mean) by loops 1 / 5 / 10 / 20 / 30: (−1,0) +40 / +155 / −73 / −218 / −202; (−1,1) −2 / −17 / −38 / −8 / −65; (−2,1) −39 / −16 / −99 / −112 / −185; (−3,1) −37 / −74 / −114 / −141 / −198 (main: +9 / −96 / −169 / −252 / −251). A+ − A hazard m: (−1,0) −391, (−1,1) −26, (−2,1) −133, (−3,1) −399. Actual within 384, A / B@30: (−1,0) 59 / 62, (−1,1) 62 / 62, (−2,1) 63 / 63, (−3,1) 62 / 63 (listed, not evidence). By distance band (B@30 − A hazard m, 300–600 / 600–1200 / > 1200 m): (−1,0) −123 / −195 / −236; (−1,1) −33 / −75 / −63; (−2,1) −118 / −191 / −199; (−3,1) −115 / −154 / −283.

Window-level statistics (rules in `multiwindow_ab.STATS`; per window = mean over its targets of B@30 − A):
- Hazard metres (main), 5 windows: −251, −202, −65, −185, −198 → 5 of 5 lower than A; median −198; bootstrap 95 % interval of the median −251 to −65. Without the main AOI (4 windows): 4 of 4 lower; median −191; interval −202 to −65.
- Actual O2 (secondary), 5 windows: −28.2, −22.6, −9.6, −24.8, −21.3 → 5 of 5 lower; median −22.6; interval −28.2 to −9.6. Without the main AOI: 4 of 4; median −22.0; interval −24.8 to −9.6.
- **No p-value**: the rule needs 6 windows all of the same sign; only 5 ran ((−4,0) waits for the gap rule). With 5 windows the exact two-sided Wilcoxon cannot go below 0.0625. The bootstrap interval of a median over 4–5 values is coarse (its ends are observed window values).
Observations (no change follows): in every window B@30 keeps underestimating the walk by 24–112 nominal minutes; in (−1,0) the habitat cell is sand on the reference and the rover saw only 3.0 % (20 km in 30 loops), yet B@30 is lower than A there, while B@5 is higher than A by 155 m; the share of the possible gain is 22–45 % across windows.

#### T7 result — rover sensitivity, each setting run once, reported as computed
Settings commit `5f6cfaf` (04:45:54); all three runs started 04:46:00, comparisons computed 05:06:52 (sand ×3), 05:13:06 (8,000), 05:19:06 (16,000), 2026-11-14 CST. **Sensitivity: written after the locked run's 11.3 % coverage was seen and before any A vs B number; the locked setting (4,000, sand ×6) stays the main result.** 0 loops over budget in every run; A, A+ and REF recomputed by `compare()` equal the frozen T2 file exactly (check files in each folder). Outputs `data_work/jezero/sensitivity/<setting>/`; web: full-table dialog, "Robustness checks".

| Rover setting | km in 30 loops | Seen after 1 / 5 / 10 / 20 / 30 loops | Seen 0–600 / 600–1200 / > 1200 m | B@30 actual O2 (A 194.6, REF 83.5) | B@30 planned O2 (error) | B@30 − A O2 | B@30 hazard m (A 1156) | B@30 − A hazard m | Share of possible gain O2 / hazard m |
|---|---|---|---|---|---|---|---|---|---|
| 4,000, sand ×6 (locked, T1 rerun) | 46.5 | 0.5 / 3.2 / 5.4 / 8.9 / 11.3 % | 49.8 / 3.3 / 0.0 % | 166.5 | 58.3 (+108.2) | −28.2 | 905 | −251 | 25 % / 25 % |
| 8,000, sand ×6 | 72.8 | 0.6 / 4.6 / 8.3 / 14.8 / 19.8 % | 65.2 / 15.6 / 0.3 % | 164.5 | 59.6 (+104.9) | −30.2 | 881 | −275 | 27 % / 27 % |
| 16,000, sand ×6 | 77.9 | 0.6 / 4.7 / 8.5 / 17.0 / 24.1 % | 67.2 / 21.3 / 4.4 % | 160.8 | 60.4 (+100.4) | −33.9 | 854 | −303 | 30 % / 30 % |
| 4,000, sand ×3 | 49.7 | 0.5 / 2.4 / 5.5 / 10.3 / 14.6 % | 59.6 / 6.5 / 0.0 % | 168.1 | 56.9 (+111.2) | −26.5 | 922 | −234 | 24 % / 23 % |

B@k − A hazard m (mean) by loops 1 / 5 / 10 / 20 / 30: 8,000: +9 / −61 / −218 / −172 / −275; 16,000: +9 / −137 / −205 / −237 / −303; sand ×3: −20 / −44 / −94 / −176 / −234 (locked: +9 / −96 / −169 / −252 / −251). Near the habitat (300–600 m, n = 8) share of possible gain B@30 O2 / hazard m: 8,000 73 % / 76 %; 16,000 83 % / 86 %; sand ×3 68 % / 68 % (locked 46 % / 53 %); beyond 1,200 m: 19 % / 20 %, 23 % / 24 %, 17 % / 17 % (locked 23 % / 23 %). Within 1200 m by direction (N NE E SE S SW W NW): 8,000 29.5 51.9 37.2 30.7 31.0 24.3 30.4 22.2; 16,000 33.3 57.2 34.6 29.4 31.1 30.0 38.9 31.6; sand ×3 25.4 27.8 33.1 29.7 27.7 21.0 17.4 12.6. Goals reached: 21 / 30 / 20 of 30 (locked 12).
Observations (no change follows): doubling or quadrupling the budget raises coverage to 19.8 % / 24.1 % but the recovered share only to 27 % / 30 %, and after 30 loops route B still underestimates the walk by about 100 nominal minutes in every setting; with 8,000 the curve is not monotonic (B@20 worse than B@10). The 16,000 run drove only 5 km more than 8,000 because it reached all 30 goals and came home early.

#### U7 result — exploratory B*, run once on the main AOI (2026-11-14 05:20:00 CST, 3.4 s), `exploratory, designed after seeing the first comparison`
Code committed before the run (`1656923`), after T6 and T7. 63 targets, 0 unreachable. Output `data_work/jezero/bstar/compare_bstar.json`. Not on the web page and not in any headline (BRIEF U7).

| | p_k (sand share of seen, non-blocked cells) | Planned O2 | Actual O2 | Error | Hazard m | Crossings | Length m | Actual ≤ 384 | vs A: O2 / hazard m | vs B@k: O2 / hazard m / error |
|---|---|---|---|---|---|---|---|---|---|---|
| B*@1 | 0.486 | 162.3 | 187.6 | +25.3 | 1080 | 9.59 | 2205 | 63 | −7.1 / −77 | −8.1 / −85 / −119.4 |
| B*@5 | 0.330 | 114.1 | 166.0 | +51.9 | 900 | 9.44 | 2213 | 63 | −28.7 / −256 | −19.4 / −161 / −81.7 |
| B*@10 | 0.357 | 110.2 | 146.8 | +36.6 | 727 | 8.05 | 2299 | 63 | −47.8 / −430 | −28.3 / −261 / −84.5 |
| B*@20 | 0.363 | 108.6 | 143.3 | +34.7 | 696 | 7.60 | 2323 | 63 | −51.3 / −460 | −23.5 / −207 / −75.9 |
| B*@30 | 0.378 | 109.0 | 142.8 | +33.8 | 696 | 6.78 | 2320 | 63 | −51.8 / −460 | −23.7 / −209 / −74.4 |

For reference (frozen T2): A 50.8 / 194.6 / +143.8 / 1156; B@30 58.3 / 166.5 / +108.2 / 905; REF 83.5 / 83.5 / 0 / 147. B*@30 recovers 47 % of the possible O2 gain and 46 % of the hazard-metre gain (B@30: 25 % / 25 %). Exploratory only; the rule was written by manager after seeing round 6.

### 2026-11-14 round 8 (W0, V1, W1, W2; tech-lead; TECH_LEAD_BRIEF 第九次更新)

#### W0 top bar
All pages share one top bar: same markup (brand, `nav#pages` with Astronaut map / Step 1 · Scout rover recon / Map data / Interactive demo → `scratch/`, then page actions on the right), CSS only in `web/style.css`, current page highlighted (`aria-current`). The data page's scene switcher moved into its side panel. Test `tests/test_nav.py`; screenshots `qa/screenshots/nav_before_*` / `nav_after_*` (1600 / 1280 / 1024 px). No number involved.

#### V1 window (−4,0) — gap rule implemented, written here BEFORE its recon and comparison (run once each)
Rule: manager 2026-11-14 (direction.md 嚴謹度 2 補充定義; TECH_LEAD_BRIEF 第八次更新 裁定 1), decided after the five other windows' numbers and before any (−4,0) route number. Code (`pipeline/multiwindow_ab.py` apply_gap_rule / habitat_rc / load_T; `pipeline/compare_ab.py` `gap=` option, default None = the frozen T2 path):
- gap = the recorded no-data mask of `windows/-4_0/terrain_2m.npz` (37,095 cells of 1,440,000 = 2.576 %).
- (a) gap cells set blocked in class_prior, class_ref, and both rover-blocked masks before anything runs, so they are blocked in A, A+, B@k, REF and the rover's belief, also after sensing. Consequence of applying (a) literally (no extra branch): in the A+ rule the 60 m blocks that overlap the gap count gap cells as reference "blocked", i.e. not sand, in their ≥ 50 % sand share; and the rover's goal gain counts gap cells as unobserved area exactly like any other prior-blocked cell (rover rule v2 unchanged).
- (b) gap cells removed from the hazard-zone set before labelling; no route touches a gap cell (asserted).
- (c) every "share seen" (per loop, by direction and distance band, compare's observed share) is over non-gap cells.
- (d) lattice targets within 50 m (≤ 50 m, cell-centre distance) of the gap dropped and listed (expected: (−1500, −900), 11.7 m).
- (e) habitat impassable on the prior → nearest cell passable for rover and astronaut (tie → smallest prior slope); target lattice stays aligned to the nominal habitat. Not triggered in (−4,0) (habitat prior class firm, rover-passable).
- Synthetic tests `tests/test_multiwindow.py` (gap blocked in every state incl. the rover belief after sensing; not in hazard zones; denominators; target drop; `gap=None` reproduces the frozen code path; habitat move). All 43 tests pass.
- Then: recon once, comparison once (code refuses a second run), and the window statistics recomputed ONCE over six windows with the same `STATS` (table() refuses a second six-window run). The five-window table is kept as `data_work/jezero/windows/t6_table_5windows.json` and figure `qa/jezero/multiwindow/T6_windows_A_vs_B_5windows.png`. p-value only if all six windows have the same sign, with the note that p = 0.031 is the design minimum and equals the sign test.

#### V1 result — window (−4,0), one recon and one comparison, reported as computed
Settings commit `e1acc3a` (05:38:11); recon started 05:38:27, comparison computed 05:41:28, six-window table right after (2026-11-14 CST). Nothing changed or re-run after any number. (A first launch at 05:38 failed on argument parsing before anything ran: `--windows "-4,0"` was read as an option; relaunched as `--windows=-4,0`.) Rover: 30 loops, 47.3 km, max loop energy 3,992.1 (0 over 4,000), 21 of 30 goals reached. Gap 37,095 cells (2.576 %); habitat not moved (prior firm). Targets: 63 lattice points ≥ 300 m, 4 blocked on prior and reference by terrain (not gap), 1 dropped within 50 m of the gap ((−1500, −900)), **58 used**, 0 unreachable; 166 hazard zones.

| Window | Sand on reference | Rover saw after 30 loops (0–600 / 600–1200 m; non-gap cells) | Targets | Hazard zones | Actual O2 A / B@30 / REF | B@30 − A O2 | Planned O2 A / B@30 (error A / B@30) | Hazard m A / B@30 / REF | B@30 − A hazard m | Share of possible gain O2 / hazard m |
|---|---|---|---|---|---|---|---|---|---|---|
| (−4,0) crater rim | 7.7 % (rough 72.2 %) | 11.7 % (48.4 / 4.3), 47.3 km | 58 | 166 | 132.9 / 114.3 / 93.3 | −18.6 | 87.4 / 86.9 (+45.4 / +27.3) | 227 / 150 / 7 | −77 | 47 % / 35 % |

B@k − A hazard m by loops 1 / 5 / 10 / 20 / 30: −12 / −21 / −6 / −75 / −77; A+ − A −56. By band (B@30 − A hazard m / O2; n): 300–600 m −4 / −6.4 (8); 600–1200 m −79 / −20.9 (30); > 1200 m −103 / −20.0 (20). Actual within 384: A 58, B@30 58 (listed, not evidence). Within 1200 m by direction (N NE E SE S SW W NW): 24.2 14.1 24.0 21.9 28.2 15.7 16.9 5.1 %.

**Six-window statistics (computed once, same `STATS`; per window = mean over its targets of B@30 − A):**
- Hazard metres (main): −251, −202, −65, −185, −198, −77 → **6 of 6 lower than A**; median −191.3; bootstrap 95 % interval of the median −226.4 to −70.8; **exact two-sided Wilcoxon p = 0.031** — with six windows all of one sign this is the smallest p the design can give; it equals the sign test and says nothing about the size of the differences. Without the main AOI (5 windows): 5 of 5 lower; median −184.7; interval −202.0 to −64.9; no p (5 windows).
- Actual O2 (secondary): −28.2, −22.6, −9.6, −24.8, −21.3, −18.6 → 6 of 6 lower; median −22.0; interval −26.5 to −14.1; p = 0.031 (same note). Without the main AOI: 5 of 5; median −21.3; interval −24.8 to −9.6; no p.
- Five-window statistics (before (−4,0)) kept unchanged above (T6 result) and in `t6_table_5windows.json`.
Observations (no change follows): (−4,0) has little sand (7.7 %) and is mostly rough; B@30 still underestimates by 27.3 nominal minutes there (A by 45.4); its share of the possible gain (47 % O2, 35 % hazard m) is within or above the other windows' 22–45 %. Web: full-table dialog "Robustness checks" (six windows, five-window statistics in a fold-out, gap rule sentence); figure `qa/jezero/multiwindow/T6_windows_A_vs_B.png` now six windows (five-window figure kept as `_5windows.png`).

#### W1 step 2, option A (simplest, switchable) — rules copied here BEFORE the single run
Rules: manager 2026-11-14, direction.md "第 ② 步：A 的鎖定規則" 1–8 (Shan chose A; k rule written after the Q1 check table — not a route number — Limitations says so). Code `pipeline/step2_chem.py` (rules in its docstring), switches `config/step2.json`, tests `tests/test_step2.py` (synthetic only, 7 pass).
- Switches: `step2.enabled` (false → the pipeline writes only `web/data/jezero/step2/step2.json = {"enabled": false}`, round 7 refuses, pages show nothing of step 2); `step2.link_rule` = `i` (default) or `ii`; `step2.unlock_radius_m` = 15 (locked).
- Input: `supercam_libs_moc.csv` (PDS), SCCT* calibration targets excluded; target = (sol, target name); 8 oxide means ÷ header RMSEP.
- Location (new, S6-5): each LIBS shot's spacecraft clock → PDS SuperCam masterlist (`data_raw/jezero/step2/supercam/m2020_scam_masterlist.csv`, 32.7 MB, downloaded 2026-11-14 05:39 from pds-geosciences.wustl.edu) → site/drive from the EDR file name → waypoint. Plumbing check before any chemistry (no group looked at): of 11,609 non-calibration rows, matching by CDR file name found 11,599 (10 early rows have no target name in the masterlist CDR name), matching by clock is used instead; every site/drive is a waypoint; no target spans two site/drives. Rows without a site/drive (if any) are left out and counted. Old rule (last waypoint with sol ≤ measurement sol) computed alongside; both AOI counts reported.
- Groups: Ward on RMSEP-scaled target means; k = largest k ≤ 4 with every centroid pair ≥ 5 RMSEP apart in at least one oxide; else k = 1; < 2 targets → k = 1. Same rule on "all AOI measurements" (ii) and "unlocked by the rover" at loops 1/5/10/20/30 (T1-rerun recon; unlocked = a driven path cell within 15 m of the measurement's waypoint, the T1 report method). Group numbers are by size (presentation only).
- Candidate stops: per group the representative (nearest its centroid, Euclidean in RMSEP units) and the anomaly (farthest from its own centroid); a stop is a waypoint, so candidates at the same waypoint form one stop whose card lists every role (no tie-break needed: the stop position is the same); ≤ 8 stops. No score, no weight.
- Card: group, 8 oxides (target mean, spread between points) with RMSEP, SIM 3464 unit at the waypoint, Perseverance photos at waypoints within 15 m (local copies, credit), source level (oxides measured by Perseverance SuperCam; group and role derived; position = rover position, target within ~7 m).
- Agreement of unlocked-data groups with all-data groups (loops 1/5/10/20/30): reported as cross-tables of the unlocked targets (unlocked group × all-data group). **No summary index was specified, so none is computed** (question for manager if one is wanted).
- Validation (descriptive): the 4 AOI rock-core sites (Q2: Rochette, Brac, Issole, Sid; site position = waypoint by sol sealed, as Q2) — for each data set, the SuperCam targets named like the feature and the targets within 15 m of the sample waypoint, with their group and any candidate role. No permutation test (no ranking).
- Run once (`data_work/jezero/step2/step2_result_r15.json`; the code refuses a second run); web export `web/data/jezero/step2/step2.json`. Nothing is tuned on samples or round 7.

#### W1 result — step 2 option A, the single run (2026-11-14 05:43:43 CST, settings commit `04a0fd8` 05:43:41), reported as computed
Output `data_work/jezero/step2/step2_result_r15.json`, web `web/data/jezero/step2/step2.json`. Input: 12,130 rows, 521 calibration rows excluded, 11,609 used; every row got a site/drive and every site/drive is a waypoint.
- **Location, new vs old:** site/drive rule 208 AOI targets / 1,718 points / **64 locations**; old sol rule 207 / 1,712 / 59. 206 targets are in the AOI under both rules; 146 have the same waypoint under both (60 moved to another waypoint).
- **(ii) all AOI measurements:** 208 targets at 64 locations; min centroid-pair separation k = 2: 14.3, k = 3: 8.1, k = 4: 4.3 RMSEP → **k = 3** (the Q1 check table, made with the old locations, had k = 4 at 5.6; with the site/drive locations k = 4 falls below 5). Groups (centroid wt%; largest differences from the other groups):
  - G1: 140 targets / 50 locations; SiO2 47.7, FeOT 18.5, MgO 4.3, Al2O3 8.6, CaO 5.4, Na2O 2.7; MgO −14.6 RMSEP vs the others; SIM 3464 Njf 90, Nle 50.
  - G2: 36 / 11; SiO2 44.8, FeOT 24.5, MgO 15.8, Al2O3 4.1; between G1 and G3 (no oxide ≥ 3 RMSEP from their mean); Njf 3, Nle 33.
  - G3: 32 / 19; SiO2 44.8, FeOT 24.7, MgO 24.8, Al2O3 4.0; MgO +13.4; Njf 2, Nle 30.
  - Candidate stops (5): 5_0 (47, −526) Njf — G1 representative `cheval_blanc` sol 131; 8_64 (−440, −634) Nle — G1 anomaly `chamatte_279_scam` sol 279; 9_0 (−535, −709) Nle — G2 representative `quartier_297_scam` sol 297 and G2 anomaly `robine_hole` sol 299; 7_2050 (−493, −643) Nle — G3 representative `moustiers_sainte_mar` sol 213; 8_0 (−442, −632) Nle — G3 anomaly `chasteuil` sol 274.
- **(i) unlocked by the rover after 30 loops (product):** 62 targets at 25 locations (T1 counted 22 locations with the old rule), all in Njf; separations k = 2: 10.1, k = 3: 3.5, k = 4: 2.6 → **k = 2**. G1: 59 targets / 24 locations (MgO 3.0, SiO2 50.1, Na2O 2.9; MgO −10.1, Na2O +3.0 RMSEP); G2: 3 / 3 (MgO 14.1, FeOT 24.3). Candidate stops (4): 3_110 (3, −5) — G1 representative `tselchee` sol 15; 4_48 (75, −28) — G1 anomaly `tseebi_tsaadah` sol 88; 4_1062 (−76, −297) — G2 representative `queh_eh_scam` sol 115; 4_1422 (−83, −300) — G2 anomaly `whoosh` sol 123. All Njf. Photos within 15 m: 8 at each of the four.
- **Unlocked by loop (1 / 5 / 10 / 20 / 30):** targets 4 / 24 / 28 / 56 / 62; locations 3 / 12 / 15 / 22 / 25; k 1 / 3 / 2 / 2 / 2; all Njf. Cross-table unlocked group × all-data group: loop 1 {1|1: 4}; loop 5 {1|1: 18, 2|2: 3, 3|1: 3}; loop 10 {1|1: 25, 2|2: 3}; loop 20 {1|1: 51, 2|1: 2, 2|2: 3}; loop 30 {1|1: 59, 2|2: 3} (the unlocked groups' numbers and the all-data groups' numbers are independent labels).
- **Sample sites (descriptive; 4 AOI rock-core sites, position by sol sealed):**
  - Rochette (Montdenier, Montagnac; wp 7_0): no target named like it; (ii) 16 targets within 15 m, all G1; none is a candidate. (i): none unlocked.
  - Brac (Salette, Coulettes; wp 8_0): (ii) `brac_246`, `brac_247` both G3, not candidates; within 15 m 26 targets (G3 13, G2 7, G1 6), including the G3 anomaly `chasteuil` and the G1 anomaly `chamatte_279_scam`. (i): none unlocked.
  - Issole (Robine, Malay; wp 9_0): (ii) `issole` G2, not a candidate; within 15 m 38 targets (G2 19, G1 12, G3 7), including the G2 representative and the G2 anomaly `robine_hole` (named after the Robine drill hole). (i): none unlocked.
  - Sid (Ha'ahoni, Atsa; wp 11_108): `sid_362` G1 in both data sets, not a candidate; within 15 m 16 targets, all G1, unlocked in (i) too.
- No permutation test (no ranking). Nothing re-run; k, radius, candidate rule unchanged.

#### W2 round 7 — confirmed definitions (manager 2026-11-14; replaces the U4 draft; status: confirmed), written BEFORE the single run
Every place these numbers appear says: **designed after seeing round 6; round 6 is the pre-registered main comparison.** Pre-authorised by manager to run once after the step-2 candidates were committed (`2634433`); definitions copied without change from direction.md 第七輪定義. Code `pipeline/multistop.py` (status confirmed), `pipeline/round7.py`; tests `tests/test_multistop.py` (synthetic only, 9 pass, incl. the secondary column and reading (ii)).
1. Targets: step-2 option A candidate stops. **Table (i) (main)** = the 4 stops from the measurements unlocked by loop 30; **table (ii) (second)** = the 5 stops from all AOI measurements, labelled not brought back by this rover. A, A+, B@1/5/10/20/30, REF use the same stops; one table per set, never merged, no distribution. Fewer than 2 stops would still run.
2. Order (main column): each knowledge state picks its own order and subset — most stops, then least planned O2, subject to "after each dwell, planned O2 used + planned O2 home ≤ usable (384)"; brute force (≤ 7 stops). Secondary column: B@k keeps A's order and subset; only the legs between stops are re-planned on B's map. Both reported; main = own order.
3. Dwell: 18 min and 18 nominal minutes of O2 per visited stop (firm-ground rate), assumed.
4. Evaluation: the planned tour (same cells, same order, not replanned) walked on the reference (blocked charged at the sand rate, as round 6). Stops reached, **main reading (ii)**: stops at whose dwell end the astronaut could still get home within the usable O2 by the least-O2 way home of his own map, charged on the reference (true return margin ≥ 0); reading (i) (dwell ends before actual O2 used > usable) beside it; and the first point where that true margin turns negative.
5. Reported per state and column: planned / actual O2 and time, error, stops planned, stops reached (ii)/(i), hazard / blocked / sand metres, crossings, zones entered (round-6 definitions on the whole tour), actual ≤ usable (listed, not evidence), differences vs A (main column of A).
6. Hazard zones = round 6 zones (asserted identical). Run once (`data_work/jezero/round7/round7.json`; the code refuses a second run); refuses when `step2.enabled` is false.

#### W2 result — round 7, the single run (2026-11-14 05:46:22 CST, 42.7 s; settings commit `7b03090` 05:46:21), reported as computed
**Designed after seeing round 6; round 6 is the pre-registered main comparison.** Output `data_work/jezero/round7/round7.json`; web `web/data/jezero/compare/round7.json`. Oxygen in nominal minutes, usable 384; dwell 18 per visited stop is included in every planned and actual value. "Reached (ii)" = main reading. Diff = minus A (main column of A). Actual ≤ 384 is listed, not evidence.

Table (i) — main: the 4 stops from measurements the rover unlocked by loop 30 (3_110, 4_48, 4_1062, 4_1422)

| State | Column | Stops planned | Reached (ii) / (i) | Planned O2 | Actual O2 | Error | Planned / actual time (min) | Hazard m | Sand m | Blocked m | Crossings | Length m | Actual ≤ 384 | Order (stop index) | Diff O2 / hazard m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | own order | 4 | 4 / 4 | 90.2 | 114.6 | +24.3 | 90 / 99 | 183 | 183 | 0 | 5 | 760 | yes | [2, 3, 1, 0] | — |
| A+ | own order | 4 | 4 / 4 | 95.8 | 115.1 | +19.3 | 92 / 100 | 198 | 198 | 0 | 4 | 760 | yes | [0, 1, 2, 3] | +0.5 / +15 |
| B@1 | own order | 4 | 4 / 4 | 90.2 | 114.6 | +24.3 | 90 / 99 | 183 | 183 | 0 | 5 | 760 | yes | [2, 3, 1, 0] | +0.0 / +0 |
| B@1 | keeps A order | 4 | 4 / 4 | 90.2 | 114.6 | +24.3 | 90 / 99 | 183 | 183 | 0 | 5 | 760 | yes | [2, 3, 1, 0] | +0.0 / +0 |
| B@5 | own order | 4 | 4 / 4 | 92.9 | 121.7 | +28.8 | 92 / 102 | 256 | 256 | 0 | 4 | 780 | yes | [0, 1, 3, 2] | +7.1 / +73 |
| B@5 | keeps A order | 4 | 4 / 4 | 92.9 | 119.2 | +26.4 | 92 / 101 | 235 | 235 | 0 | 5 | 780 | yes | [2, 3, 1, 0] | +4.6 / +52 |
| B@10 | own order | 4 | 4 / 4 | 93.2 | 104.6 | +11.4 | 92 / 96 | 112 | 112 | 0 | 2 | 793 | yes | [0, 2, 3, 1] | -10.0 / -71 |
| B@10 | keeps A order | 4 | 4 / 4 | 93.2 | 104.6 | +11.4 | 92 / 96 | 112 | 112 | 0 | 2 | 794 | yes | [2, 3, 1, 0] | -9.9 / -71 |
| B@20 | own order | 4 | 4 / 4 | 94.6 | 104.1 | +9.5 | 92 / 96 | 108 | 108 | 0 | 2 | 793 | yes | [1, 2, 3, 0] | -10.4 / -74 |
| B@20 | keeps A order | 4 | 4 / 4 | 94.6 | 104.2 | +9.5 | 92 / 96 | 108 | 108 | 0 | 2 | 794 | yes | [2, 3, 1, 0] | -10.4 / -74 |
| B@30 | own order | 4 | 4 / 4 | 94.6 | 104.0 | +9.4 | 92 / 96 | 108 | 108 | 0 | 2 | 793 | yes | [1, 2, 3, 0] | -10.5 / -74 |
| B@30 | keeps A order | 4 | 4 / 4 | 94.6 | 104.1 | +9.4 | 92 / 96 | 108 | 108 | 0 | 2 | 794 | yes | [2, 3, 1, 0] | -10.5 / -74 |
| REF | own order | 4 | 4 / 4 | 96.2 | 96.2 | +0.0 | 93 / 93 | 37 | 37 | 0 | 2 | 813 | yes | [0, 2, 3, 1] | -18.4 / -145 |

True return margin never turned negative in any tour of this table (first negative point: none).

Table (ii) — second: the 5 stops from all Perseverance measurements in the AOI (5_0, 8_64, 9_0, 7_2050, 8_0); not brought back by this rover

| State | Column | Stops planned | Reached (ii) / (i) | Planned O2 | Actual O2 | Error | Planned / actual time (min) | Hazard m | Sand m | Blocked m | Crossings | Length m | Actual ≤ 384 | Order (stop index) | Diff O2 / hazard m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | own order | 5 | 5 / 5 | 141.2 | 246.4 | +105.2 | 141 / 181 | 820 | 820 | 0 | 18 | 2133 | yes | [0, 1, 4, 2, 3] | — |
| A+ | own order | 5 | 5 / 5 | 159.6 | 246.3 | +86.6 | 150 / 183 | 787 | 787 | 0 | 20 | 2285 | yes | [0, 1, 4, 3, 2] | -0.1 / -32 |
| B@1 | own order | 5 | 5 / 5 | 141.2 | 246.4 | +105.2 | 141 / 181 | 820 | 820 | 0 | 18 | 2133 | yes | [0, 1, 4, 2, 3] | +0.0 / +0 |
| B@1 | keeps A order | 5 | 5 / 5 | 141.2 | 246.4 | +105.2 | 141 / 181 | 820 | 820 | 0 | 18 | 2133 | yes | [0, 1, 4, 2, 3] | +0.0 / +0 |
| B@5 | own order | 5 | 5 / 5 | 142.2 | 250.2 | +108.0 | 142 / 182 | 864 | 864 | 0 | 16 | 2156 | yes | [0, 1, 4, 2, 3] | +3.8 / +44 |
| B@5 | keeps A order | 5 | 5 / 5 | 142.2 | 250.2 | +108.0 | 142 / 182 | 864 | 864 | 0 | 16 | 2156 | yes | [0, 1, 4, 2, 3] | +3.8 / +44 |
| B@10 | own order | 5 | 5 / 5 | 144.0 | 226.4 | +82.3 | 144 / 175 | 623 | 623 | 0 | 15 | 2230 | yes | [0, 1, 2, 3, 4] | -20.0 / -197 |
| B@10 | keeps A order | 5 | 5 / 5 | 144.1 | 230.7 | +86.7 | 144 / 176 | 692 | 692 | 0 | 15 | 2231 | yes | [0, 1, 4, 2, 3] | -15.7 / -128 |
| B@20 | own order | 5 | 5 / 5 | 144.8 | 225.9 | +81.1 | 144 / 175 | 618 | 618 | 0 | 8 | 2231 | yes | [0, 2, 3, 4, 1] | -20.4 / -201 |
| B@20 | keeps A order | 5 | 5 / 5 | 145.1 | 208.7 | +63.6 | 144 / 168 | 507 | 507 | 0 | 9 | 2245 | yes | [0, 1, 4, 2, 3] | -37.7 / -312 |
| B@30 | own order | 5 | 5 / 5 | 144.8 | 225.5 | +80.7 | 144 / 175 | 618 | 618 | 0 | 8 | 2231 | yes | [0, 2, 3, 4, 1] | -20.9 / -201 |
| B@30 | keeps A order | 5 | 5 / 5 | 145.2 | 204.9 | +59.7 | 144 / 167 | 481 | 481 | 0 | 9 | 2246 | yes | [0, 1, 4, 2, 3] | -41.5 / -339 |
| REF | own order | 5 | 5 / 5 | 153.2 | 153.2 | +0.0 | 150 / 150 | 37 | 37 | 0 | 2 | 2393 | yes | [0, 1, 4, 3, 2] | -93.2 / -783 |

True return margin never turned negative in any tour of this table (first negative point: none).

Observations (no change follows): every state plans and reaches all stops in both tables (readings (ii) and (i) agree; no true margin below zero), so round 7 does not show "A thinks it can reach all, B knows only some" for these stops — they are all within ~1 km of the habitat. Table (i) (stops 6–311 m from the habitat): B@30 − A −10.5 O2 / −74 hazard m, B@5 is worse than A (+7.1 / +73), the reference tour −18.4 / −145; error after recon +9.4 vs A +24.3. Table (ii) (stops 0.5–0.9 km south and south-west of the habitat): B@30 own order −20.9 / −201, keeping A's order −41.5 / −339; REF −93.2 / −783; A underestimates the tour by 105 nominal minutes, B@30 by 81 (own order) or 60 (A's order). In (ii) B's own order costs more on the reference than A's order on B's map at loops 10, 20 and 30: the order chosen as cheapest on B's partial map runs into unseen sand. All hazard metres are sand metres; blocked metres 0.

#### W3 rover goal rule version 3 — rules copied BEFORE any run (manager 2026-11-14, direction.md 第三版定案 R1–R8; TECH_LEAD_BRIEF 第十次更新)
**Designed after seeing version 2's coverage, repeat coverage and loop 24; version 2 (T1 rerun) and round 6 stay the pre-registered record.** Code `pipeline/rover_v3.py` (rules in its docstring), tests `tests/test_rover_v3.py` (synthetic only, 7 pass). Output will be `data_work/jezero/v3/` (version-2 files untouched). Parameters, all `assumed`, single values, never swept on real terrain: α₀ = 1, β₀ = 4, ρ = 1.5, K = 30, reselect threshold 1.5, frontier component ≥ 3 cells, candidate ≤ 20 m from a frontier cell, gain corridor 15 m. Unchanged: budget 4,000, planning share 0.75, firm 1 / rough 2.5 / sand 6, sensing / unlock 15 m, 30 loops, 2 m grid, 40 m lattice, 30 m penalty-free disc, margin floor 1.15, soft check every 20 steps, hard energy rule, return ρ = 1.5, data boundary.
- R1 expected cost (Sofman, Lin, Bagnell, Cole, Vandapel, Stentz 2006, *Improving robot navigation through self-supervised online learning*, JFR 23(11–12); Beta–Bernoulli): p_k = (s_k + 1)/(n_k + 5) per prior class firm / rough over seen cells; unseen E[c] = (1 − p_k)c_k + 6p_k; unseen prior-blocked = blocked; seen = true cost; p_k recomputed at each loop start and each (re)selection; all planning on E[c]; margin = paid ÷ expected cost of the same driven cells (floor 1.15).
- R2 repeat penalty (Burgard, Moors, Stachniss, Schneider 2005, *Coordinated multi-robot exploration*, IEEE T-RO 21(3)): c′ = E[c](1 + 1.5·seen), not within 30 m of the habitat; outbound and return planned on c′; feasibility and budget on E[c] × margin.
- R3 frontier candidates (Yamauchi 1997, *A frontier-based approach for autonomous exploration*, CIRA): frontier = seen, passable, with an unseen 8-neighbour, components ≥ 3 cells; candidate = 40 m lattice point ≤ 20 m from a frontier cell, belief-passable.
- R4 score (Singh, Krause, Guestrin, Kaiser 2009, *Efficient informative sensing using multiple robots*, JAIR 34; Bircher et al. 2016, *Receding horizon "next-best-view" planner for 3D exploration*, ICRA; González-Baños & Latombe 2002): coarse A150(q)/(E[s→q] + E[q→home]), top K = 30; loop gain G(q) = unseen area within 15 m of outbound ∪ return (each cell once); feasible if spent + (E[s→q] + E[q→home]) × margin ≤ 3,000; score G/(E[s→q] + E[q→home]); ties within 1 m² → smaller E[s→q].
- R5 loop (Bircher 2016 receding horizon; Shen et al. 2020; Betke, Rivest, Singh 1995 piecemeal learning): select from the habitat, drive, reveal, hard rule every step; every 20 steps soft turn-back, then reselect if expected remaining cost > 1.5 × estimate; impassable on the path → reselect; at the target → reselect; no feasible candidate → version-2 return rule on c′ / E[c].
- R6 not done: direction balance, orienteering, D* Lite, any tuning. Any loop over budget → stop and report.
- R7 tests (synthetic, all pass): every loop home and ≤ budget; unseen reference never read; no Perseverance file named; p_firm rises when prior-firm is all sand (and equals (s+1)/(n+5)); loop gain counts unseen cells once; candidates within 20 m of a frontier and 2-cell frontiers ignored; a cost jump triggers a reselect.
- R8 quantities (both versions side by side): coverage after 1/5/10/20/30; repeat coverage (seen cells seen by ≥ 2 loops; per loop = cells within 15 m of that loop's driven cells); new area, km, new area per km per loop; safety / soft returns, replans; loops without reaching a target (v3 target definition differs — not comparable); unlocks and units; 8 directions, 3 distance bands; p_firm / p_rough per loop; total km; loops over budget (must be 0).
- **Geometric bounds of the literature report, recomputed** from the T1 rerun: 46.5 km × 30 m swath / 5.76 km² = **24.2 %** if no swath ever overlapped; 60 habitat crossings × 30 m fill the circumference of a circle of radius 60·30/(2π) = **286.5 m**, so overlap inside ~290 m is unavoidable; 60 × 286.5 m = 17.2 km = 37.0 % of the distance driven.
- **Readings where R1–R5 are silent (tech-lead, written before any run; sent to manager — NOT run until confirmed):** (1) the rover's current cell is never a candidate (else it would "reach" it at once, forever); (2) the K = 30 shortlist is taken among feasible candidates (feasibility uses only the coarse quantities; the literal order "top 30 first, then feasibility" can end a loop although feasible candidates exist further down); (3) outbound: an impassable cell anywhere on the remaining path triggers a reselect at once (every step); version 2's "cost ×2 in the next 10 steps → replan" is not used outbound (R5's 1.5× check replaces it), but stays on the return as part of the version-2 return rule; (4) the return path in G(q) is planned on c′ as it is at selection time; (5) margin denominator = E[c] of the driven step's two cells as unseen cells with the current p_k.
- **Manager ruling on the five readings (TECH_LEAD_BRIEF 第十二次更新, before any v3 number): all five adopted as written**, with one addition to (2): first-pass feasibility uses the two coarse quantities E[s→q] (E[c] summed along the c′ shortest-path tree from the current cell) and E[q→home] (least E[c] cost home, field on E[c]); the top 30 feasible by coarse value get the loop gain; the chosen candidate (score order, ties within 1 m² → smaller E[s→q]) is re-checked with E[c] summed along its traced outbound path plus E[q→home], and if that fails the next one by score is taken. Implemented in `Selector.select` (commit below); tests still pass (8). Geometric bounds adopted for DATA_LOG and Limitations: 24.2 % with no overlap; overlap within 286.5 m unavoidable (~37 % of km).

#### W3 v3 run 1 — STOPPED after loop 1 (2026-11-14 05:57:40 start; killed by tech-lead after loop 1's log line), not a result
Loop 1 log line (`data_work/jezero/v3/run1_aborted.log`): 75 targets selected and reached, cost 3,000.0 / 4,000, 3,000 m driven, **only 1,200 m² newly seen**, p_firm 0.0166, p_rough 0.2, 1 direct return. No output file was written; nothing else of the run was looked at.
**Cause (reproduced on a synthetic flat 400 × 400 map, no real terrain):** with sensing 15 m, a 40 m candidate lattice and "candidate ≤ 20 m from a frontier cell" (R3), after the rover visits a lattice point its frontier lies ~15 m from it, so the next lattice point (40 m away; 56.6 m diagonally) is ~25 m or more from any frontier cell and never becomes a candidate. Only the four lattice points around the habitat stay candidates; once their loop gain is 0 the score is 0 for all of them, they are still feasible, and the rover shuttles between them until the 0.75 × 4,000 feasibility limit (synthetic: targets (190,190) ↔ (190,210) with gain 0 from the 6th selection on). This is the rule as written (R3 + unchanged lattice and sensing radius) plus no "gain > 0" condition; it is not a budget violation. **Stopped and reported to manager; no parameter changed, nothing re-run.** The synthetic tests passed because their budgets were small.

#### W0–W2 acceptance rulings applied (manager 2026-11-14; no number re-run)
1. **Agreement metrics (specified after the cross-tables were seen; the cross-tables are the record)**, computed by `spikes/w1_consistency.py` from the saved `step2_result_r15.json` only: adjusted Rand index (Hubert & Arabie 1985) and majority-match share, loops 1 / 5 / 10 / 20 / 30: ARI undefined (both one group; 4 targets) / 0.573 / 1.000 / 0.701 / 1.000; majority match 1.00 / 1.00 / 1.00 / 0.964 / 1.00. On the page next to the unlock curve.
2. k 4 → 3 accepted; Limitations wording added (README, About): k rule written from the old-position Q1 table (k = 4 at 5.6), site/drive positions chosen when A was adopted, both before the run; 2 more AOI targets drop k = 4 to 4.3; k = 4 not computed.
3. Round 7 not changed (stops, budget); the observation is on the astronaut page and in README; the oxygen slider is the interactive way to shrink the budget. Budget sensitivity (192, 96) only last, exploratory.
4. Gap side effects (A+ counts gap cells as non-sand; the version-2 rover counts them as unseen gain) — one sentence in Limitations.
5. Main message sentence 2: multi-window clause added (README, PROJECT_PAGE): six windows same direction, 22–47 % of the oxygen gain and 22–45 % of the hazard-metre gain per window (from the T6/V1 tables: O2 25/22/32/40/24/47 %, hazard m 25/22/33/45/23/35 %; the hazard range in direction.md reads 22–40 %, the tables give 22–45 %). p = 0.031 only in the Robustness section with its note.
Also: citation correction (Deans 2009 concept, Fong 2010 evaluation) and v3 literature in `docs/REFERENCES.md`; NTRS 20090036808 not verified yet (the fetch was refused).

#### W3 v3 candidate fix (manager 2026-11-14, TECH_LEAD_BRIEF 第十三次更新), written BEFORE the single run
**Manager ruled after seeing the stopped loop 1** (run 1: 75 targets, 3,000 / 4,000, 3,000 m, 1,200 m² new, p_firm 0.0166, p_rough 0.2; `run1_aborted.log`, `575f1f8`). The fix changes only the candidate set; no parameter changed: (b) **candidates = the frontier cells themselves** (Yamauchi 1997; seen, belief-passable, with an unseen 8-neighbour, 8-connected component ≥ 3 cells), no 40 m lattice; R4's coarse value and K = 30 apply to frontier cells; **a candidate with loop gain G(q) = 0 is not feasible**; the current cell is never a candidate. Everything else in R1–R8 and the five readings unchanged (α₀ 1, β₀ 4, ρ 1.5, K 30, 1.5×, 15 m corridor). New synthetic test: on flat ground loop 1's newly seen area grows with distance (no two-point shuttle; no target twice; every chosen gain > 0). The 1.5× reselect check is now a named helper (`needs_reselect`) tested directly (the corridor scenario no longer triggers it with frontier targets). All 63 tests pass. Then: run once.

#### X1 (a) AI4MARS crowd labels vs HiRISE classes — rules copied BEFORE the run (manager, TECH_LEAD_BRIEF 第十一次更新 A1–A8, 第十三次更新 3)
Code `pipeline/ai4mars_check.py` (rules in its docstring), geometry test `tests/test_ai4mars.py`. Data: AI4MARS merged 0.6 (Zenodo 15995036), m2020 NAV merged labels + matching ncam images, downloaded by data-curator to `data_raw/jezero/ai4mars/` (≈ 0.61 GB, Range extraction; `_tools/fetch.log`). Labels `measured (crowd labels)`; results `agreement with crowd labels, not expert accuracy`, never ground truth.
- A1: NLF-named labels, sol ≥ 13, site/drive from the file name equal to a main-AOI waypoint (base number 2,191 labels / 72 waypoints). Vgnc (SCLK only) not used in the comparison. GEO not fetched.
- A2: viewing direction = `photo_heading.heading` (Navcam CAHV model rotated by the attitude, Raw Images JSON cache); sector apex at the waypoint, edge_left → edge_right clockwise, radius 30 m (assumed). No direction → 30 m circle, reported separately.
- A3: per image sand / labelled pixels, bedrock likewise; waypoint = mean over its images (counts reported).
- A4: share of reference sand cells (2 m) in the same sector / circle; firm + rough (+ blocked, listed) = non-sand; prior share (no sand class) = 0, reported as is.
- A5: waypoint-level Spearman ρ (photo sand vs HiRISE sand; photo bedrock vs HiRISE non-sand); 2×2 at 0.5 on both sides (n, agreement, both error counts); < 5 sand-dominant waypoints → little power for sand; per-waypoint table; 8 comparison panels (`qa/jezero/ai4mars/X1_panels.png`, images spread over the photo-sand range).
- Selection uses data-curator's `data_raw/jezero/ai4mars/index.csv` (NLF, sol ≥ 13, label present; 2,331 labels on the whole traverse, the AOI filter is the exact site/drive waypoint match). **Correction (data-curator, after download): 107 of photos.json's 478 images share a name with an AI4MARS NAV label, not 241** (241 was the earlier whole-traverse probe). This does not change the A5 table (it uses every AOI label, not only photos.json images); it only affects the optional A6 model output on the remaining photos.json images, listed separately if A6 is done. Raw Images metadata (camera model + attitude) found for 2,279 of the 2,331 labels.
- Nothing here changes the sand classes, any frozen number or the rover rules. Run once after the download is complete.

#### X1 / X2 rulings before their runs (manager, TECH_LEAD_BRIEF 第十四次更新)
- X2: the six readings adopted as written (kNN on standardised features, scaler fitted on the training fold; 5 equal-count sol segments; 100 m buffer drops training waypoints near any test waypoint; balanced accuracy on pooled out-of-fold predictions; second table only inside the six windows, centres ≥ 30 m from the window edge; CTX ortho with each window's X3 shift). Added: report per fold the training waypoints left after the buffer and their sand-dominant count; the second table is named "waypoints inside the six windows" (not "whole traverse"); units outside SIM 3464 are one one-hot class "none". Slope and roughness = the 2 m `terrain_2m` grids (from the 1 m DTM; B2 rewritten accordingly).
- X1 correction: A5's photo side uses all 2,215 AOI labels (NLF, including sol 9–12 at the landing site); directions where the Raw Images JSON gives camera model and attitude, 30 m circles for the rest, reported separately. X2's answers use the same label set (A3). A6 (if done): of photos.json's 478 images, 107 have labels (compared directly) and 371 only model output, labelled separately.

#### W3 v3 run 2 (the single run after the candidate fix) — 3 loops OVER BUDGET: program bug, stopped and reported
Started 2026-11-14 08:05:53 CST (commit `337e70f`), 30 loops in 2,129.8 s. **Loops 11, 14, 18 ended at 4,029.1 / 4,365.8 / 4,161.1 (budget 4,000).** Other numbers as computed (a defective run, not a result): 64.5 km; seen after loops 1/5/10/20/30: 0.8 / 4.1 / 7.3 / 11.4 / 15.5 %; 2,422 targets selected, 2,392 reached; 3 safety returns, 30 soft turn-backs, 869 replans; p_rough stayed 0.20 every loop, p_firm 0.13–0.28 (loop 30: 0.258).
**Cause (program bug, found by replaying loop 11 from the saved path and first-seen times; no simulation re-run):** `refresh_known()` took the second return value of `MCP_Geometric.find_costs` — the traceback array (small integers) — as the cost home over seen ground, so the hard energy rule believed home was a few units away and fired only at spent ≈ 3,965 (loop 11: at t = 10,350 the true spent + known way home was 4,217). Version 2 (`field_from`) is not affected.
**Process deviation:** `compare_v3` (B_v3@k, step 3) was launched in the same command as the run summary, before I read the over-budget line, so it ran once on this defective recon: B_v3@30 actual O2 155.3 (planned 95.3, error +60.0), hazard m 806; vs A −39.3 O2 / −350 hazard m; 35 % / 35 % of the possible gain; 60 better / 3 worse. Kept as `compare_bv3_run2_defect.json`; not a result.
All run-2 outputs renamed `*_run2_defect.*` in `data_work/jezero/v3/` (kept). Fix (one line, `known_home, _ = …`) and two tests (source check; tight-budget sand map) committed; **not re-run — waiting for manager** (precedent: the version-2 budget defect, fixed and re-run once under the four conditions of 誠實原則).
