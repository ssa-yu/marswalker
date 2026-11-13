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
| m2020_raw | Mars 2020 mission. Perseverance raw images (credit per image, NASA/JPL-Caltech; Mastcam-Z NASA/JPL-Caltech/ASU) | https://mars.nasa.gov/mars2020/multimedia/raw-images/ |

## Software

| Name | Use | Licence |
|---|---|---|
| MapLibre GL JS 4.7.1 | web map rendering (local copy in `web/lib/`) | BSD-3-Clause |
| GDAL / rasterio, NumPy, SciPy, scikit-image, Pillow, Matplotlib | pipeline | various open-source |
| Playwright (Python) | headless screenshots for QA | Apache-2.0 |

## Design references (challenge Resources, not used as data)

- Curiosity's Proposed Path up Mount Sharp — https://science.nasa.gov/resource/curiositys-proposed-path-up-mount-sharp/ (route map style, later step)
- NASA Worldview — https://worldview.earthdata.nasa.gov/ (layer list with opacity controls)
