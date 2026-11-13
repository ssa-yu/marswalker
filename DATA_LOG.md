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
| Perseverance Raw Images (Navcam, Front Hazcam, Mastcam-Z left) | Mars 2020, NASA/JPL-Caltech (Mastcam-Z: ASU) | https://mars.nasa.gov/mars2020/multimedia/raw-images/ (JSON API `https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020`) | Ground photos stored locally, placed on waypoints by site/drive | measured | yes | in use |
| Habitat (base) location | — | — | Local grid origin (Octavia E. Butler Landing) | assumed | — | in use |
| USGS SIM 3464 Jezero geologic map | USGS-NASA Planetary Geologic Mapping | https://pubs.usgs.gov/sim/3464/sim3464_database.zip | Geologic units (later step) | measured | yes | planned |
| SWIM ice-consistency maps | PSI/JPL (NASA) | https://swim.psi.edu/ | Regional layer, Arcadia | measured (consistency, not detection) | no | paused (Arcadia paused 2026-11-14) |
| HiRISE DTM 061075_2195 + CTX K20_061141/061075 (Arcadia) | MRO HiRISE / CTX; USGS ARD | see `team/tech/official-sources.md` | Arcadia scene | measured | no | paused: CTX DTM + ortho downloaded; HiRISE DTM download stopped; X3 not re-run |
| HiRISE DTM 060706_2195 + CTX (Arcadia, second region) | MRO HiRISE / CTX; USGS ARD | see `team/tech/official-sources.md` | Arcadia second region | measured | no | paused (data from feasibility spike kept in `data_raw/arcadia_starship_060706/`) |
| AI4MARS | NASA JPL, Zenodo | https://zenodo.org/records/15995036 | Terrain classes on rover photos (later step) | measured labels | no | planned |
| Curiosity's Proposed Path up Mount Sharp | NASA | https://science.nasa.gov/resource/curiositys-proposed-path-up-mount-sharp/ | Design reference for route maps | — | yes | reference only |
| NASA Worldview | NASA | https://worldview.earthdata.nasa.gov/ | Design reference for layer list | — | yes | reference only |

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
