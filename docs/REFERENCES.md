_SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md_

# References

Keys match the `ref` field in `config/scenes/*.json` and `web/data/<scene>/scene.json`.

## Data products

| Key | Reference | Link |
|---|---|---|
| fergason2020 | Fergason, R. L., et al. (2020). Mars 2020 Terrain Relative Navigation Flight Product Generation: Digital Terrain Model and Orthorectified Image Mosaics. 51st LPSC, abstract 2020. HiRISE DTM mosaic doi:10.5066/P9REJ9JN; HiRISE orthomosaic doi:10.5066/P9QJDP48; CTX DTM mosaic doi:10.5066/P906QQT8 | https://planetarymaps.usgs.gov/mosaic/mars2020_trn/ |
| mcewen2007 | McEwen, A. S., et al. (2007). Mars Reconnaissance Orbiter's High Resolution Imaging Science Experiment (HiRISE). JGR 112, E05S02. Image credit NASA/JPL-Caltech/UArizona | https://www.uahirise.org/ |
| hirise_esp071077 | HiRISE observation ESP_071077_1985 (2021-09-24), RDR distributed as COG by USGS Astrogeology Analysis Ready Data (uncontrolled observations), CC0 | https://stac.astrogeology.usgs.gov/ (collection `mro_hirise_uncontrolled_observations`) |
| malin2007 | Malin, M. C., et al. (2007). Context Camera Investigation on board the Mars Reconnaissance Orbiter. JGR 112, E05S04 | — |
| smith2001 | Smith, D. E., et al. (2001). Mars Orbiter Laser Altimeter: Experiment summary after the first year of global mapping of Mars. JGR 106(E10), 23689–23722. MOLA MEGDR 463 m mosaic by USGS Astrogeology | https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif |
| edwards2011 | Edwards, C. S., et al. (2011). Mosaicking of global planetary image datasets: 2. Modeling of wind streak thicknesses observed in THEMIS daytime and nighttime infrared mosaics. JGR 116, E10005 (THEMIS controlled mosaics); tiles served by NASA JPL Mars Trek | https://trek.nasa.gov/mars/ |
| fergason2018 | Fergason, R. L., Hare, T. M., & Laura, J. (2018). HRSC and MOLA Blended Digital Elevation Model at 200 m v2. USGS Astrogeology Science Center; colour hillshade tiles served by NASA JPL Mars Trek | https://trek.nasa.gov/mars/ |
| m2020_mmgis | Mars 2020 mission (NASA/JPL-Caltech). Perseverance waypoints and traverse, MMGIS layers | https://mars.nasa.gov/mmgis-maps/M20/Layers/json/ |
| sun_stack2020 | Sun, V. Z., & Stack, K. M. (2020). Geologic map of Jezero crater and the Nili Planum region, Mars. USGS Scientific Investigations Map 3464, scale 1:75,000 (layer only; not registered to HiRISE) | https://pubs.usgs.gov/publication/sim3464 |
| mola_pedr | Smith, D. E., et al. MGS MOLA Precision Experiment Data Records (PEDR), queried through the PDS Geosciences Node ODE (supplementary elevation check only) | https://oderest.rsl.wustl.edu/ |
| supercam | Mars 2020 SuperCam team, PDS Geosciences Node: derived LIBS major-oxide compositions (supercam_libs_moc.csv) and Raman table (step-2 verification only; not shown on the map) | https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_supercam/ |
| crism_mtrdr | MRO CRISM Map-projected Targeted Reduced Data Records (MTRDR) summary parameters, PDS Geosciences Node (verification only; failed our registration check, not used on the map) | https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/ |
| m2020_samples | NASA Science, Mars rock samples (Perseverance sample list; verification only) | https://science.nasa.gov/mission/mars-2020-perseverance/mars-rock-samples/ |
| horizons | JPL Solar System Dynamics, Horizons system (Sun position at Jezero; stored locally, daylight check) | https://ssd.jpl.nasa.gov/horizons/ |
| deahn2026 | Deahn, M. C., et al. (2026). Mapping the Western Jezero Crater Rim From Orbit. JGR Planets 131, e2025JE009471; GIS data doi:10.5281/zenodo.20976631 (fact check of a possible second window only; not used in results) | https://doi.org/10.1029/2025JE009471 |
| ai4mars | Swan, R. M., et al. (2021). AI4Mars: A dataset for terrain-aware autonomous driving on Mars. CVPR Workshops; dataset on Zenodo (contents checked, not downloaded) | https://zenodo.org/records/15995036 |
| m2020_raw | Mars 2020 mission. Perseverance raw images (credit per image, NASA/JPL-Caltech; Mastcam-Z NASA/JPL-Caltech/ASU) | https://mars.nasa.gov/mars2020/multimedia/raw-images/ |

## Methods and parameters

| Key | Reference | Used for |
|---|---|---|
| mvp_prototype | Team's earlier prototype (2026, unpublished): walking speed 2.5 km/h, speed and oxygen factors per terrain class, rover cost factors | assumed parameters; original sources still being checked by teammates |
| apollo15_reserve | Apollo 15 EVA planning kept a 20 % consumables reserve (as summarised in the team's context notes; not re-verified against the original document) | 20 % oxygen reserve (assumed) |
| kirk2008 | Kirk, R. L., et al. (2008). Ultrahigh resolution topographic mapping of Mars with MRO HiRISE stereo images. JGR 113, E00A24 (effective DTM resolution ~3 × post spacing; page not re-verified) | 6 m slope baseline on the 1 m HiRISE DTM |
| skimage_mcp | scikit-image `skimage.graph.MCP_Geometric` (minimum-cost paths) | rover and astronaut path planning |

## Software

| Name | Use | Licence |
|---|---|---|
| MapLibre GL JS 4.7.1 | web map rendering (local copy in `web/lib/`) | BSD-3-Clause |
| GDAL / rasterio, NumPy, SciPy, scikit-image, Pillow, Matplotlib | pipeline | various open-source |
| Playwright (Python) | headless screenshots for QA | Apache-2.0 |

## Methods and related work

Bibliographic details follow the team's literature report (`team/tech/exploration-algorithms.md`, checked against DBLP / IEEE Xplore / DOI pages unless noted).

| Key | Reference | Used for |
|---|---|---|
| deans2009 | Deans, M., Fong, T., et al. (2009). Robotic scouting for human exploration. *Proc. AIAA SPACE 2009*, AIAA-2009-6781. https://publications.ri.cmu.edu/robotic-scouting-for-human-exploration | Concept: a robot scouts before the astronauts |
| fong2010 | Fong, T., Abercromby, A., Bualat, M. G., Deans, M. C., Hodges, K. V., Hurtado, J. M., Landis, R., Lee, P., & Schreckenghost, D. (2010). Assessment of robotic recon for human exploration of the Moon. *Acta Astronautica*, 67(9–10), 1176–1188. https://doi.org/10.1016/j.actaastro.2010.06.029 | Evaluation design: astronaut traverses planned without recon vs re-planned with recon data (our route A vs route B) |
| ntrs20090036808 | Deans, M., Fong, T., Ford, K., Heldmann, J., Helper, M., Hodges, K., Landis, R., Lee, P., Schaber, G., & Schmitt, H. H. (2009). *Robotic Recon for Human Exploration*. NASA Ames Research Center, ARC-E-DAA-TN622, NTRS 20090036808 (no venue listed in the record; checked 2026-11-14). https://ntrs.nasa.gov/citations/20090036808 | A third item, neither deans2009 nor fong2010: background only |
| yamauchi1997 | Yamauchi, B. (1997). A frontier-based approach for autonomous exploration. *Proc. IEEE CIRA'97*, 146–151. https://doi.org/10.1109/CIRA.1997.613851 | Rover v3: frontier candidates (R3) |
| burgard2005 | Burgard, W., Moors, M., Stachniss, C., & Schneider, F. E. (2005). Coordinated multi-robot exploration. *IEEE Trans. Robotics*, 21(3), 376–386. https://doi.org/10.1109/TRO.2004.839232 | Rover v3: utility reduction for already-seen ground (R2) |
| singh2009 | Singh, A., Krause, A., Guestrin, C., & Kaiser, W. J. (2009). Efficient informative sensing using multiple robots. *JAIR*, 34, 707–755. https://doi.org/10.1613/jair.2674 | Rover v3: sequential greedy gain / cost (R4) |
| bircher2016 | Bircher, A., Kamel, M., Alexis, K., Oleynikova, H., & Siegwart, R. (2016). Receding horizon "next-best-view" planner for 3D exploration. *Proc. IEEE ICRA*, 1462–1468. | Rover v3: gain along the whole path, reselection on the way (R4, R5) |
| sofman2006 | Sofman, B., Lin, E., Bagnell, J. A., Cole, J., Vandapel, N., & Stentz, A. (2006). Improving robot navigation through self-supervised online learning. *J. Field Robotics*, 23(11–12), 1059–1075. https://doi.org/10.1002/rob.20169 | Rover v3 and route B_v3: expected cost of unseen ground learned from what the rover has seen (R1) |
| koenig1997 | Koenig, S., & Smirnov, Y. (1997). Sensor-based planning with the freespace assumption. *Proc. IEEE ICRA*, 3540–3545. | Why route B (unseen = orbital class) is optimistic |
| gonzalez2002 | González-Baños, H. H., & Latombe, J.-C. (2002). Navigation strategies for exploring indoor environments. *IJRR*, 21(10–11), 829–848. (Score formula seen only in a secondary source: *citation not verified against the publisher page*.) | Concept of next-best-view with travel cost |
| shen2020 | Shen, Z., Wilson, J. P., & Gupta, S. (2020). ε*+: An online coverage path planning algorithm for energy-constrained autonomous vehicles. *Global Oceans 2020*. https://doi.org/10.1109/IEEECONF38699.2020.9389353 | Rover v3: resume from the nearest uncovered ground after returning to base (R5) |
| betke1995 | Betke, M., Rivest, R. L., & Singh, M. (1995). Piecemeal learning of an unknown environment. *Machine Learning*, 18(2–3), 231–254. https://doi.org/10.1007/BF00993411 | Theory: exploration that must return to base |
| hubert1985 | Hubert, L., & Arabie, P. (1985). Comparing partitions. *Journal of Classification*, 2, 193–218. | Adjusted Rand index (step-2 group agreement) |

## Design references (challenge Resources, not used as data)

- Curiosity's Proposed Path up Mount Sharp — https://science.nasa.gov/resource/curiositys-proposed-path-up-mount-sharp/ (route map style, later step)
- NASA Worldview — https://worldview.earthdata.nasa.gov/ (layer list with opacity controls)
