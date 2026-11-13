# Marswalk Recon

Astronaut-ready layered map and walking route for Mars, built from NASA orbital and rover data.
A scout rover leaves the habitat on its own, explores, returns; its findings decide where astronauts
should go and how they get there within an oxygen budget.

**Status: checkpoint 1 — terrain maps and real imagery.** No rover simulation, analysis or routes yet.
Main scene: Jezero Crater (Perseverance ground data). Arcadia Planitia is paused.

## View the map

```
cd web && python3 -m http.server 8000
# open http://localhost:8000/
```
(`file://` cannot load the JSON data; any static server works. No build step, no network needed.)

## Rebuild the data

```
conda env create -p ./.conda-env -f environment.yml
./.conda-env/bin/python -m pipeline.run --scene jezero        # fetch -> trek -> align -> grid -> rover -> layers -> qa -> export
./.conda-env/bin/python -m pytest -q tests
./.conda-env/bin/python tools/screenshot.py                    # headless screenshots to qa/screenshots/
```
Scenes are defined in `config/scenes/<scene>.json` (base, AOI, sources); adding a site means adding a config file.

## Layout

| Path | Content |
|---|---|
| `config/scenes/` | scene configs |
| `pipeline/` | Python pipeline (see module docstrings) |
| `web/` | static viewer (HTML + vanilla JS + local MapLibre); `web/data/` is generated |
| `qa/` | positioning-check images and `checks.json`; `qa/screenshots/` |
| `DATA_LOG.md` | data summary table and processing log |
| `docs/REFERENCES.md`, `docs/AI_USE.md` | citations, AI-use statement |
| `spikes/` | feasibility scripts kept for the record |

Data credits: NASA/JPL-Caltech/UArizona (HiRISE), NASA/JPL-Caltech/MSSS (CTX), USGS Astrogeology, NASA JPL Mars Trek, NASA/JPL-Caltech (Perseverance; Mastcam-Z NASA/JPL-Caltech/ASU).
