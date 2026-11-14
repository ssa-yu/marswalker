// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Scratch the map — interactive demo (NOT the analysis results). Plain JS, no build step.
   1 Scratch: a blurry CTX cover over the Jezero AOI is erased where the user drags, revealing HiRISE imagery and the
     HiRISE reference terrain classes (2 m). 2 Analyse: simple, explainable rules on the revealed cells only.
   3 Walk: least-oxygen round trip from the habitat through the targets on the user's knowledge map
     (revealed = HiRISE classes, unrevealed = orbital prior classes), replayed on the HiRISE reference classes.
   Oxygen model = pipeline/astro_plan.py PARAMS (assumed). Planning grid 4 m (2 x 2 blocks of the 2 m classes).
   Data: data/terrain.bin, data/supercam.json, data/views.json (built by build_data.py) + ../data/jezero/*.
   Interface text: ../i18n.js (tr). Fixed defaults (no longer sliders): brush radius, targets wanted, reserve, stay, replay speed. */
'use strict';
const R_MARS = 3396190, DEG = Math.PI / 180;
const D = '../data/jezero/', SD = 'data/';
const X0 = -1700, Y1 = 1400, RES = 2, N = 1200;           // 2 m class grid, row 0 = north
const M = 600, R4 = 4;                                       // 4 m planning grid
const CLS = ['firm', 'rough', 'sand', 'blocked'];
const CCOL = ['#62d6a4', '#f4b740', '#ff5a4e', '#5a2a6e'];
// pipeline/astro_plan.py PARAMS (locked by manager 2026-11-14, label assumed)
const PAR = { speed_kmh: 2.5, speed: [1, 0.6, 0.35], o2: [1, 1.5, 2.1] };
const VMIN = PAR.speed_kmh * 1000 / 60;                      // m per min on firm
const TM = [0, 1, 2].map((i) => 1 / (VMIN * PAR.speed[i])); // min per metre
const OM = TM.map((t, i) => t * PAR.o2[i]);                  // O2 nominal-min per metre
const STAY_RATE = 1.0;                                        // demo assumption
const WARN_FRAC = 0.15;                                       // astro_plan UI threshold (interface only)
const BRUSH_M = 60, N_TARGETS = 3, RESERVE_PCT = 20, STAY_MIN = 10, SPEED_MIN_PER_S = 8;   // fixed demo defaults

const $ = (s) => document.querySelector(s);
const abs = (u) => new URL(u, location.href).href;
const f0 = (v) => (v == null || !isFinite(v) ? '–' : Math.round(v).toLocaleString('en-US'));
const f1 = (v) => (v == null || !isFinite(v) ? '–' : (Math.round(v * 10) / 10).toFixed(1));
const fmtMin = (m) => { if (!isFinite(m)) return '–'; const h = Math.floor(m / 60), r = Math.round(m - 60 * h); return h ? tr('fmt.hm', { h, m: String(r).padStart(2, '0') }) : tr('fmt.m', { m: r }); };
const clsName = (c) => tr('cls.' + c);
const fmtKm = (m) => (m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${Math.round(m)} m`);
const S = { rev: new Uint8Array(N * N), nRev: 0, mode: 'scratch', step: 1, targets: [], stale: false, plan: null, t: 0, playing: false, viewKey: '' };

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); }
function loadImg(u) { return new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => no(new Error(u)); i.src = u; }); }

// ---------- coordinates
let LON0, LAT0, KCOS;
const xyToLL = (x, y) => [LON0 + x / KCOS / R_MARS / DEG, LAT0 + y / R_MARS / DEG];
const llToXY = (lon, lat) => [(lon - LON0) * DEG * R_MARS * KCOS, (lat - LAT0) * DEG * R_MARS];
const rc2 = (x, y) => [Math.floor((Y1 - y) / RES), Math.floor((x - X0) / RES)];
const xy4 = (k) => { const i = (k / M) | 0, j = k % M; return [X0 + (j + 0.5) * R4, Y1 - (i + 0.5) * R4]; };
const k4 = (x, y) => { const i = Math.floor((Y1 - y) / R4), j = Math.floor((x - X0) / R4); return (i < 0 || j < 0 || i >= M || j >= M) ? -1 : i * M + j; };

async function init() {
  const [sc, buf, SC, VW, ctxImg] = await Promise.all([
    getJSON(D + 'scene.json'), fetch(SD + 'terrain.bin').then((r) => { if (!r.ok) throw new Error('terrain.bin'); return r.arrayBuffer(); }),
    getJSON(SD + 'supercam.json'), getJSON(SD + 'views.json'), loadImg(D + 'ctx_ortho.jpg')]);
  S.sc = sc; S.SC = SC; S.VW = VW; S.ctxImg = ctxImg;
  LON0 = sc.base.lon; LAT0 = sc.base.lat; KCOS = Math.cos(LAT0 * DEG);
  const raw = new Uint8Array(buf); S.ref = new Uint8Array(N * N); S.pri = new Uint8Array(N * N);
  for (let i = 0; i < N * N; i++) { S.ref[i] = raw[i] & 15; S.pri[i] = raw[i] >> 4; }
  S.baseK = k4(0, 0);
  for (const s of SC.sites) { const [r, c] = rc2(s.x, s.y); s.cell = r * N + c; }
  S.corners = sc.aoi.corners;
  paintCover();
  buildMap();
  bindUI();
  setView({ cls: 'firm', where: tr('sc.atStart'), idx: 0 });
  renderRevStats();
}

// ---------- cover (the scratch-off layer)
function paintCover() {
  const cv = $('#coverCanvas'); cv.width = N; cv.height = N;
  const g = cv.getContext('2d'); g.globalCompositeOperation = 'source-over';
  const im = S.ctxImg, cc = S.sc.layers.find((l) => l.id === 'ctx_ortho').coordinates; // context corners
  const lonA = cc[0][0], lonB = cc[1][0], latT = cc[0][1], latB = cc[2][1], a = S.corners;
  const sx = (a[0][0] - lonA) / (lonB - lonA) * im.naturalWidth, sw = (a[1][0] - a[0][0]) / (lonB - lonA) * im.naturalWidth;
  const sy = (latT - a[0][1]) / (latT - latB) * im.naturalHeight, sh = (a[0][1] - a[2][1]) / (latT - latB) * im.naturalHeight;
  const small = document.createElement('canvas'); small.width = small.height = 90;      // downsample = blur (works everywhere)
  const sg = small.getContext('2d'); sg.imageSmoothingQuality = 'high'; sg.drawImage(im, sx, sy, sw, sh, 0, 0, 90, 90);
  g.imageSmoothingEnabled = true; g.imageSmoothingQuality = 'high'; g.drawImage(small, 0, 0, N, N);
  // orbital prior classes, faint: from orbit nearly everything reads as firm
  const pc = document.createElement('canvas'); pc.width = pc.height = 300; const pg = pc.getContext('2d');
  const id = pg.createImageData(300, 300), rgb = CCOL.map((h) => [1, 3, 5].map((o) => parseInt(h.slice(o, o + 2), 16)));
  for (let i = 0; i < 300; i++) for (let j = 0; j < 300; j++) {
    const k = S.pri[(i * 4) * N + j * 4], p = 4 * (i * 300 + j), c = rgb[k];
    id.data[p] = c[0]; id.data[p + 1] = c[1]; id.data[p + 2] = c[2]; id.data[p + 3] = 26;
  }
  pg.putImageData(id, 0, 0); g.drawImage(pc, 0, 0, N, N);
  g.fillStyle = 'rgba(30,22,18,.25)'; g.fillRect(0, 0, N, N);
  // faint hatch so the cover reads as a cover
  g.strokeStyle = 'rgba(255,230,200,.06)'; g.lineWidth = 2;
  for (let d = -N; d < N; d += 24) { g.beginPath(); g.moveTo(d, 0); g.lineTo(d + N, N); g.stroke(); }
}

function coverUpdate(final) {
  const src = S.map && S.map.getSource('cover'); if (!src) return;
  if (final) { src.play(); src.pause(); S.map.triggerRepaint(); } else src.play();
}

function scratchAt(x, y) {
  const rm = BRUSH_M, rp = rm / RES;
  const [r0, c0] = [(Y1 - y) / RES, (x - X0) / RES];
  const g = $('#coverCanvas').getContext('2d');
  g.globalCompositeOperation = 'destination-out'; g.beginPath(); g.arc(c0, r0, rp, 0, 2 * Math.PI); g.fill();
  g.globalCompositeOperation = 'source-over';
  const ri = Math.ceil(rp), rr = rp * rp;
  for (let dr = -ri; dr <= ri; dr++) {
    const r = Math.floor(r0 + dr); if (r < 0 || r >= N) continue;
    for (let dc = -ri; dc <= ri; dc++) {
      const c = Math.floor(c0 + dc); if (c < 0 || c >= N) continue;
      const ddr = r + 0.5 - r0, ddc = c + 0.5 - c0;
      if (ddr * ddr + ddc * ddc > rr) continue;
      const k = r * N + c; if (!S.rev[k]) { S.rev[k] = 1; S.nRev++; }
    }
  }
}

function stroke(a, b) {
  const step = Math.max(2, BRUSH_M / 3), d = Math.hypot(b[0] - a[0], b[1] - a[1]), n = Math.max(1, Math.ceil(d / step));
  for (let i = 1; i <= n; i++) scratchAt(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n);
}

let statT = 0;
function afterScratch(final) {
  coverUpdate(final);
  const pct = 100 * S.nRev / (N * N);
  $('#revPct').textContent = `${pct.toFixed(1)} %`; $('#revFill').style.width = `${pct}%`;
  if (S.targets.length && !S.stale) { S.stale = true; renderTargets(); renderPlanOut(); }
  const now = performance.now();
  if (final || now - statT > 250) { statT = now; renderRevStats(); updateSC(); }
}

function renderRevStats() {
  const cr = [0, 0, 0, 0], cp = [0, 0, 0, 0];
  for (let i = 0; i < N * N; i++) if (S.rev[i]) { cr[S.ref[i]]++; cp[S.pri[i]]++; }
  const n = S.nRev, km2 = n * RES * RES / 1e6;
  const nSC = S.SC.sites.filter((s) => S.rev[s.cell]).length;
  if (!n) { $('#revStats').innerHTML = `<p class="hint">${tr('sc.none')}</p>`; return; }
  $('#revStats').innerHTML = `<table class="stats"><thead><tr><th>${tr('sc.inRev', { a: km2.toFixed(2) })}</th><th>${tr('sc.orbit')}</th><th>${tr('sc.hirise')}</th></tr></thead><tbody>${
    CLS.map((c, i) => `<tr><td><span class="sw" style="background:${CCOL[i]}"></span>${clsName(c)}</td><td>${(100 * cp[i] / n).toFixed(0)} %</td><td>${(100 * cr[i] / n).toFixed(0)} %</td></tr>`).join('')
  }</tbody></table><p class="hint">${tr('sc.scFound', { n: nSC, t: S.SC.sites.length })}</p>`;
}

// ---------- map
function buildMap() {
  const a = S.corners, sc = S.sc;
  const map = new maplibregl.Map({
    container: 'map', bounds: [[a[0][0], a[2][1]], [a[1][0], a[0][1]]], fitBoundsOptions: { padding: 20 },
    maxZoom: 19, minZoom: 10, renderWorldCopies: false, dragRotate: false, pitchWithRotate: false, attributionControl: false,
    style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0d0b0a' } }] },
  });
  S.map = map;
  map.touchZoomRotate.disableRotation();
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: tr('sc.attrib') }));
  map.on('load', () => {
    const L = (id) => sc.layers.find((l) => l.id === id), ctx = L('ctx_ortho'), ho = L('hirise_ortho');
    map.addSource('ctx', { type: 'image', url: abs(D + ctx.url), coordinates: ctx.coordinates });
    map.addLayer({ id: 'ctx', type: 'raster', source: 'ctx', paint: { 'raster-fade-duration': 0, 'raster-brightness-max': 0.55, 'raster-saturation': -0.4 } });
    map.addSource('hi', { type: 'raster', tiles: [abs(D) + ho.url], tileSize: 256, minzoom: ho.minzoom, maxzoom: ho.maxzoom, bounds: ho.bounds });
    map.addLayer({ id: 'hi', type: 'raster', source: 'hi', paint: { 'raster-fade-duration': 0 } });
    map.addSource('cls', { type: 'image', url: abs(D + 'recon/class_ref.png'), coordinates: a });
    map.addLayer({ id: 'cls', type: 'raster', source: 'cls', paint: { 'raster-opacity': 0.45, 'raster-fade-duration': 0, 'raster-resampling': 'nearest' } });
    map.addSource('cover', { type: 'canvas', canvas: $('#coverCanvas'), coordinates: a, animate: false });
    map.addLayer({ id: 'cover', type: 'raster', source: 'cover', paint: { 'raster-fade-duration': 0 } });
    map.addSource('aoi', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [...a, a[0]] } } });
    map.addLayer({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.5, 'line-dasharray': [3, 2] } });
    map.addSource('sc', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'sc', type: 'circle', source: 'sc', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 13, 3, 17, 6], 'circle-color': '#7fe3ff', 'circle-stroke-color': '#00303c', 'circle-stroke-width': 1.2 } });
    map.addSource('route', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'route-case', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 5, 'line-opacity': 0.6 } });
    map.addLayer({ id: 'route', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#ffffff', 'line-width': 2.5, 'line-dasharray': [2, 1.5] } });
    map.addSource('walked', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'walked', type: 'line', source: 'walked', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#43b0f1', 'line-width': 4 } });
    new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'hab-marker', title: tr('sc.habTitle') }) }).setLngLat([LON0, LAT0]).addTo(map);
    S.astro = new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'astro-marker', title: tr('common.astronaut') }) }).setLngLat([LON0, LAT0]).addTo(map);
    const pop = new maplibregl.Popup({ closeButton: false, offset: 8 });
    map.on('mousemove', 'sc', (e) => {
      if (S.mode === 'scratch' && S.down) return;
      const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(tr('sc.scPop', { sols: p.sols, t: p.targets, si: p.si, fe: p.fe, mg: p.mg, n: p.n })).addTo(map);
    });
    map.on('mouseleave', 'sc', () => pop.remove());
    map.once('idle', () => { window.__ready = true; });
    const at = document.querySelector('.maplibregl-ctrl-attrib'); if (at) at.classList.remove('maplibregl-compact-show');
  });
  setMode('scratch');
  const cont = map.getCanvasContainer();
  const toXY = (e) => { const r = cont.getBoundingClientRect(), ll = map.unproject([e.clientX - r.left, e.clientY - r.top]); return llToXY(ll.lng, ll.lat); };
  cont.addEventListener('pointerdown', (e) => {
    if (S.mode !== 'scratch' || (e.pointerType === 'mouse' && e.button !== 0)) return;
    e.preventDefault(); cont.setPointerCapture(e.pointerId); S.down = true; S.last = toXY(e);
    if (S.playing) stop();
    scratchAt(...S.last); afterScratch(false);
  });
  cont.addEventListener('pointermove', (e) => {
    if (!S.down) return; const p = toXY(e); stroke(S.last, p); S.last = p; afterScratch(false);
  });
  const end = () => { if (!S.down) return; S.down = false; afterScratch(true); };
  cont.addEventListener('pointerup', end); cont.addEventListener('pointercancel', end); cont.addEventListener('lostpointercapture', end);
}

const fc = (f) => ({ type: 'FeatureCollection', features: f });
function updateSC() {
  if (!S.map || !S.map.getSource('sc')) return;
  const on = true;   // SuperCam sites always shown where revealed
  S.map.getSource('sc').setData(fc(on ? S.SC.sites.filter((s) => S.rev[s.cell]).map((s) => ({ type: 'Feature', properties: {
    sols: s.sols.join(', '), targets: s.targets.slice(0, 4).join(', ') + (s.targets.length > 4 ? ' …' : ''), n: s.n_shots,
    si: f1(s.mean_wt_pct.SiO2), fe: f1(s.mean_wt_pct.FeOT), mg: f1(s.mean_wt_pct.MgO) }, geometry: { type: 'Point', coordinates: [s.lon, s.lat] } })) : []));
}

function setMode(m) {
  S.mode = m; const map = S.map, sc = m === 'scratch';
  $('#modeScratch').classList.toggle('active', sc); $('#modePan').classList.toggle('active', !sc);
  $('#modeScratch').setAttribute('aria-pressed', sc); $('#modePan').setAttribute('aria-pressed', !sc);
  $('#mapwrap').classList.toggle('scratching', sc);
  for (const h of [map.dragPan, map.touchZoomRotate, map.doubleClickZoom, map.boxZoom]) sc ? h.disable() : h.enable();
}

// ---------- step 2: analysis on revealed cells
function diskOffsets(rad) { const o = []; const ri = Math.ceil(rad); for (let dr = -ri; dr <= ri; dr++) for (let dc = -ri; dc <= ri; dc++) if (dr * dr + dc * dc <= rad * rad) o.push([dr, dc]); return o; }
const DK20 = diskOffsets(20), DK10 = diskOffsets(10), DK30 = diskOffsets(30);

function knowledgeGrids() {
  // 4 m cells: per-metre O2 and time = mean of the 2 x 2 cells' values; any blocked 2 m cell -> impassable.
  const kO = new Float32Array(M * M), kT = new Float32Array(M * M), aO = new Float32Array(M * M), aT = new Float32Array(M * M), aBlk = new Uint8Array(M * M);
  for (let i = 0; i < M; i++) for (let j = 0; j < M; j++) {
    let so = 0, st = 0, sao = 0, sat = 0, blk = false, ablk = 0;
    for (let a = 0; a < 2; a++) for (let b = 0; b < 2; b++) {
      const k = (2 * i + a) * N + 2 * j + b, kc = S.rev[k] ? S.ref[k] : S.pri[k], rc = S.ref[k];
      if (kc === 3) blk = true; else { so += OM[kc]; st += TM[kc]; }
      if (rc === 3) { ablk = 1; sao += OM[1]; sat += TM[1]; } else { sao += OM[rc]; sat += TM[rc]; }
    }
    const q = i * M + j;
    kO[q] = blk ? Infinity : so / 4; kT[q] = blk ? Infinity : st / 4; aO[q] = sao / 4; aT[q] = sat / 4; aBlk[q] = ablk;
  }
  return { kO, kT, aO, aT, aBlk };
}

class Heap { // binary min-heap of (key, node)
  constructor() { this.k = new Float64Array(1 << 16); this.v = new Int32Array(1 << 16); this.n = 0; }
  push(key, node) {
    if (this.n === this.k.length) { const k = new Float64Array(this.n * 2), v = new Int32Array(this.n * 2); k.set(this.k); v.set(this.v); this.k = k; this.v = v; }
    let i = this.n++; const K = this.k, V = this.v;
    while (i > 0) { const p = (i - 1) >> 1; if (K[p] <= key) break; K[i] = K[p]; V[i] = V[p]; i = p; }
    K[i] = key; V[i] = node;
  }
  pop() {
    const K = this.k, V = this.v, top = V[0], tk = K[0], key = K[--this.n], node = V[this.n];
    let i = 0; for (;;) { let c = 2 * i + 1; if (c >= this.n) break; if (c + 1 < this.n && K[c + 1] < K[c]) c++; if (K[c] >= key) break; K[i] = K[c]; V[i] = V[c]; i = c; }
    K[i] = key; V[i] = node; this.topKey = tk; return top;
  }
}
const NB = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]].map(([a, b]) => [a, b, (a && b ? Math.SQRT2 : 1) * R4]);
function dijkstra(cost, src, stops) {
  const dist = new Float64Array(M * M).fill(Infinity), prev = new Int32Array(M * M).fill(-1), h = new Heap();
  const rem = stops ? new Set(stops.filter((s) => s !== src)) : null;
  dist[src] = 0; h.push(0, src);
  while (h.n) {
    const u = h.pop(), d = h.topKey; if (d > dist[u]) continue;
    if (rem && rem.delete(u) && rem.size === 0) break;
    const i = (u / M) | 0, j = u % M, cu = cost[u];
    for (const [di, dj, L] of NB) {
      const ii = i + di, jj = j + dj; if (ii < 0 || jj < 0 || ii >= M || jj >= M) continue;
      const v = ii * M + jj, cv = cost[v]; if (cv === Infinity) continue;
      const nd = d + 0.5 * (cu + cv) * L; if (nd < dist[v]) { dist[v] = nd; prev[v] = u; h.push(nd, v); }
    }
  }
  return { dist, prev };
}
function pathTo(prev, src, dst) { const p = [dst]; let u = dst; while (u !== src) { u = prev[u]; if (u < 0) return null; p.push(u); } return p.reverse(); }

function usable() { return +$('#cap').value * (1 - RESERVE_PCT / 100); }

function analyse() {
  const want = N_TARGETS, U = usable(), stay = STAY_MIN * STAY_RATE;
  const G = knowledgeGrids(); S.G = G;
  S.F0 = dijkstra(G.kO, S.baseK, null);
  const cands = [];
  let nRevealedLattice = 0, nPass = 0, nReach = 0;
  for (let r = 5; r < N; r += 10) for (let c = 5; c < N; c += 10) {
    const k = r * N + c; if (!S.rev[k]) continue;
    let rv = 0, tot = 0;
    for (const [dr, dc] of DK20) { const rr = r + dr, cc = c + dc; if (rr < 0 || cc < 0 || rr >= N || cc >= N) continue; tot++; rv += S.rev[rr * N + cc]; }
    if (rv < 0.8 * DK20.length) continue;
    nRevealedLattice++;
    const cl = S.ref[k]; if (cl !== 0 && cl !== 1) continue;
    let sand = false;
    for (const [dr, dc] of DK10) { const rr = r + dr, cc = c + dc; if (rr < 0 || cc < 0 || rr >= N || cc >= N) continue; const q = rr * N + cc; if (S.rev[q] && S.ref[q] === 2) { sand = true; break; } }
    if (sand) continue;
    nPass++;
    const cnt = [0, 0, 0, 0]; let n = 0;
    for (const [dr, dc] of DK30) { const rr = r + dr, cc = c + dc; if (rr < 0 || cc < 0 || rr >= N || cc >= N) continue; const q = rr * N + cc; if (S.rev[q]) { cnt[S.ref[q]]++; n++; } }
    let H = 0; for (const v of cnt) if (v) { const p = v / n; H -= p * Math.log(p); }
    H /= Math.log(4);
    const x = X0 + (c + 0.5) * RES, y = Y1 - (r + 0.5) * RES;
    const sites = S.SC.sites.filter((s) => S.rev[s.cell] && Math.hypot(s.x - x, s.y - y) <= 30);
    const q4 = k4(x, y), rt = 2 * S.F0.dist[q4];
    if (!(rt + stay <= U)) continue;
    nReach++;
    cands.push({ x, y, k4: q4, cls: cl, H, shares: cnt.map((v) => v / n), sites, score: H + 0.4 * Math.min(3, sites.length), rt });
  }
  cands.sort((a, b) => b.score - a.score || a.rt - b.rt);
  const pick = [];
  for (const c of cands) { if (pick.length >= want) break; if (pick.every((p) => Math.hypot(p.x - c.x, p.y - c.y) >= 150)) pick.push(c); }
  pick.forEach((p, i) => { p.n = i + 1; p.dSand = nearestSand(p.x, p.y); });
  S.targets = pick; S.stale = false; S.analysis = { nRevealedLattice, nPass, nReach, nCand: cands.length };
  S.plan = null; stop(); clearRoute();
  drawTargets(); renderTargets(); renderPlanOut();
}
function nearestSand(x, y) { // reported only: nearest revealed sand cell within 100 m
  const [r, c] = rc2(x, y); let best = Infinity;
  for (let dr = -50; dr <= 50; dr++) for (let dc = -50; dc <= 50; dc++) {
    const rr = r + dr, cc = c + dc; if (rr < 0 || cc < 0 || rr >= N || cc >= N) continue; const q = rr * N + cc;
    if (S.rev[q] && S.ref[q] === 2) { const d = Math.hypot(dr, dc) * RES; if (d < best) best = d; }
  }
  return best <= 100 ? best : Infinity;
}
function range(a, b) { const o = []; for (let i = a; i <= b; i++) o.push(i); return o; }

function drawTargets() {
  (S.tgMarkers || []).forEach((m) => m.remove());
  S.tgMarkers = S.targets.map((t) => new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'tg-marker', textContent: t.n, title: tr('sc.target', { n: t.n }) }) }).setLngLat(xyToLL(t.x, t.y)).addTo(S.map));
}

function renderTargets() {
  const A = S.analysis, el = $('#tgList');
  if (!A) { el.innerHTML = `<p class="hint">${tr('sc.tgFirst')}</p>`; return; }
  let h = S.stale ? `<div class="msg">${tr('sc.stale')}</div>` : '';
  h += `<p class="hint">${tr('sc.funnel', { a: A.nRevealedLattice, b: A.nPass, c: A.nReach })}</p>`;
  if (!S.targets.length) h += `<div class="msg">${tr('sc.noTg')} ${S.nRev < 20000 ? tr('sc.noTgMore') : tr('sc.noTgFirm')}</div>`;
  h += S.targets.map((t) => {
    const sh = t.shares.map((v, i) => (v >= 0.01 ? `${clsName(CLS[i])} ${Math.round(100 * v)} %` : null)).filter(Boolean).join(', ');
    const sc = t.sites.length ? tr('sc.tgSc', { n: t.sites.length, t: t.sites[0].targets.slice(0, 2).join(', '), sol: t.sites[0].sols[0], si: f1(t.sites[0].mean_wt_pct.SiO2), fe: f1(t.sites[0].mean_wt_pct.FeOT) }) : tr('sc.tgNoSc');
    return `<div class="tg"><div class="h"><span class="n">${t.n}</span><b>${tr('sc.score', { s: t.score.toFixed(2) })}</b><span class="muted">${clsName(CLS[t.cls])} · x ${f0(t.x)} m, y ${f0(t.y)} m</span></div>
      <div class="why">${tr('sc.tgWhy', { h: t.H.toFixed(2), sh, sc, sand: isFinite(t.dSand) ? f0(t.dSand) + ' m' : '> 100 m', rt: f0(t.rt) })}</div></div>`;
  }).join('');
  if (S.targets.length) h += `<div class="row"><button class="btn sm" id="goWalk">${tr('sc.goWalk')}</button></div>`;
  el.innerHTML = h;
  const gw = $('#goWalk'); if (gw) gw.onclick = () => { setStep(3); planTour(); };
}

// ---------- step 3: tour + replay
function planTour() {
  stop();
  if (!S.targets.length) { S.plan = null; renderPlanOut(); return; }
  const U = usable(), stay = STAY_MIN * STAY_RATE, G = S.G, T = S.targets, n = T.length;
  const nodes = [S.baseK, ...T.map((t) => t.k4)];
  const F = [S.F0, ...T.map((t) => dijkstra(G.kO, t.k4, nodes))];
  const C = nodes.map((_, a) => nodes.map((b) => F[a].dist[b]));
  const home = S.F0.dist;
  // best order: most targets, then least O2; after each arrival the walker must still get home within the usable O2
  let best = null;
  const perms = (arr) => (arr.length <= 1 ? [arr] : arr.flatMap((x, i) => perms([...arr.slice(0, i), ...arr.slice(i + 1)]).map((p) => [x, ...p])));
  for (let mask = 1; mask < 1 << n; mask++) {
    const sub = range(1, n).filter((i) => mask & (1 << (i - 1)));
    for (const p of perms(sub)) {
      let used = 0, cur = 0, ok = true;
      for (const t of p) { used += C[cur][t] + stay; if (used + C[t][0] > U) { ok = false; break; } cur = t; }
      if (!ok) continue; used += C[cur][0];
      if (!best || p.length > best.order.length || (p.length === best.order.length && used < best.o2)) best = { order: p, o2: used };
    }
  }
  if (!best) { S.plan = { fail: true }; renderPlanOut(); clearRoute(); return; }
  // build the vertex timeline (actual = HiRISE reference classes; planned = your map)
  const legs = [], seq = [0, ...best.order, 0];
  for (let s = 0; s < seq.length - 1; s++) {
    const a = seq[s], b = seq[s + 1]; let p;
    if (a === 0) p = pathTo(S.F0.prev, nodes[0], nodes[b]); else p = pathTo(F[a].prev, nodes[a], nodes[b]);
    legs.push({ from: a, to: b, path: p });
  }
  const tl = { x: [], y: [], t: [], oa: [], op: [], d: [], tp: [], leg: [], stay: [], blk: [] };
  const push = (k, t, oa, op, d, tp, leg, st, blk) => { const [x, y] = xy4(k); tl.x.push(x); tl.y.push(y); tl.t.push(t); tl.oa.push(oa); tl.op.push(op); tl.d.push(d); tl.tp.push(tp); tl.leg.push(leg); tl.stay.push(st); tl.blk.push(blk); };
  let t = 0, oa = 0, op = 0, d = 0, tp = 0, nBlk = 0;
  push(nodes[0], 0, 0, 0, 0, 0, 0, 0, 0);
  legs.forEach((L, li) => {
    const p = L.path; L.d0 = d; L.oa0 = oa; L.op0 = op; L.t0 = t;
    for (let s = 1; s < p.length; s++) {
      const u = p[s - 1], v = p[s], len = (Math.abs(u - v) === 1 || Math.abs(u - v) === M) ? R4 : R4 * Math.SQRT2;
      t += 0.5 * (G.aT[u] + G.aT[v]) * len; oa += 0.5 * (G.aO[u] + G.aO[v]) * len;
      op += 0.5 * (G.kO[u] + G.kO[v]) * len; tp += 0.5 * (G.kT[u] + G.kT[v]) * len; d += len;
      if (G.aBlk[v]) nBlk++;
      push(v, t, oa, op, d, tp, li, 0, G.aBlk[v]);
    }
    L.d = d - L.d0; L.oa = oa - L.oa0; L.op = op - L.op0; L.t = t - L.t0;
    if (L.to !== 0 && stay > 0) { t += stay; tp += stay; oa += stay; op += stay; push(p[p.length - 1], t, oa, op, d, tp, li, L.to, 0); }
  });
  tl.home = tl.x.map((x, i) => home[k4(x, tl.y[i])]);
  const margins = tl.oa.map((o, i) => U - o - tl.home[i]);
  const mPlan = tl.op.map((o, i) => U - o - tl.home[i]);
  S.plan = { U, order: best.order, skipped: range(1, n).filter((i) => !best.order.includes(i)), legs, tl, nBlk, stay,
    o2Plan: op, o2Act: oa, tPlan: tp, tAct: t, dist: d, minMarginPlan: Math.min(...mPlan), minMarginAct: Math.min(...margins) };
  S.map.getSource('route').setData(fc([{ type: 'Feature', geometry: { type: 'LineString', coordinates: tl.x.map((x, i) => xyToLL(x, tl.y[i])) } }]));
  $('#play').disabled = false; $('#scrub').disabled = false;
  renderPlanOut(); setT(0);
}

function clearRoute() {
  if (!S.map || !S.map.getSource('route')) return;
  S.map.getSource('route').setData(fc([])); S.map.getSource('walked').setData(fc([]));
  $('#play').disabled = true; $('#scrub').disabled = true; $('#scrub').value = 0; $('#tLbl').textContent = fmtMin(0);
  S.astro && S.astro.setLngLat([LON0, LAT0]);
  setHud(null);
  setView({ cls: 'firm', where: tr('sc.atStart'), idx: 0 });
}

function renderPlanOut() {
  const el = $('#planOut'), P = S.plan;
  if (!S.targets.length) { el.innerHTML = `<div class="msg">${tr('sc.noTgYet')}</div>`; return; }
  if (!P) { el.innerHTML = `<p class="hint">${tr('sc.ready', { n: S.targets.length })}</p>`; return; }
  if (P.fail) { el.innerHTML = `<div class="msg">${tr('sc.fail')}</div>`; return; }
  const ord = P.order.map((i) => `<b>${i}</b>`).join(' → ');
  const diff = P.o2Act - P.o2Plan, rel = Math.abs(diff) / Math.max(1, P.o2Plan);
  const hab = tr('common.habitat');
  el.innerHTML = `${S.stale ? `<div class="msg">${tr('sc.planStale')}</div>` : ''}
    <p class="lead">${hab} → ${ord} → ${hab}${P.skipped.length ? ` · <span class="bad">${tr('sc.skipped', { s: P.skipped.join(', ') })}</span>` : ''}</p>
    <table class="stats"><thead><tr><th>${tr('sc.leg')}</th><th>${tr('sc.dist')}</th><th>${tr('sc.time')}</th><th>${tr('sc.o2')}</th></tr></thead><tbody>${
      P.legs.map((L) => `<tr><td>${L.from ? 'T' + L.from : hab} → ${L.to ? 'T' + L.to : hab}</td><td>${fmtKm(L.d)}</td><td>${fmtMin(L.t)}</td><td>${f0(L.oa)}</td></tr>`).join('')
    }${P.stay ? `<tr><td>${tr('sc.stays', { n: P.order.length, m: P.stay })}</td><td></td><td>${fmtMin(P.order.length * P.stay)}</td><td>${f0(P.order.length * P.stay)}</td></tr>` : ''}</tbody></table>
    <div class="kv">
      <span>${tr('sc.kTotal')}</span><b>${fmtKm(P.dist)} · ${fmtMin(P.tAct)}</b>
      <span>${tr('sc.kUsed')}</span><b>${tr('sc.kUsedV', { a: f0(P.o2Act), u: f0(P.U) })}</b>
      <span>${tr('sc.kPlan')}</span><b>${f0(P.o2Plan)}</b>
      <span>${tr('sc.kLeft')}</span><b class="${P.U - P.o2Act < 0 ? 'bad' : 'ok'}">${f0(P.U - P.o2Act)}</b>
      <span>${tr('sc.kMin')}</span><b class="${P.minMarginAct < 0 ? 'bad' : P.minMarginAct < WARN_FRAC * P.U ? 'warnc' : 'ok'}">${f0(P.minMarginAct)}</b>
    </div>
    <p class="hint">${rel > 0.05 ? tr('sc.differ', { d: (diff > 0 ? '+' : '−') + f0(Math.abs(diff)) }) : tr('sc.agree')}${P.nBlk ? ` <span class="bad">${tr('sc.steep', { n: P.nBlk })}</span>` : ''}</p>`;
}

function setHud(i) {
  const P = S.plan;
  if (i == null || !P || P.fail) { $('#o2Val').textContent = '–'; $('#mgVal').textContent = '–'; $('#tdVal').textContent = '–'; $('#o2Bar .fill').style.width = '100%'; $('#mgBar .fill').style.width = '100%'; $('#warn').hidden = true; return; }
  const cap = +$('#cap').value, resF = RESERVE_PCT / 100, tl = P.tl;
  const oa = tl._oa, left = cap - oa, mg = P.U - oa - tl._home;
  $('#o2Val').textContent = tr('sc.o2of', { l: f0(left), c: f0(cap) });
  const ob = $('#o2Bar'); ob.querySelector('.fill').style.width = `${Math.max(0, 100 * left / cap)}%`; ob.querySelector('.res').style.width = `${100 * resF}%`;
  ob.classList.toggle('low', left < cap * (resF + WARN_FRAC)); ob.classList.toggle('crit', left < cap * resF);
  $('#mgVal').textContent = tr('sc.nomMin', { v: f0(mg) });
  const mb = $('#mgBar'); mb.querySelector('.fill').style.width = `${Math.max(0, Math.min(100, 100 * mg / P.U))}%`;
  mb.classList.toggle('low', mg < WARN_FRAC * P.U); mb.classList.toggle('crit', mg < 0);
  $('#tdVal').textContent = `${fmtKm(tl._d)} · ${compName(tl._hd)}`;
  const w = $('#warn'); w.hidden = mg >= 0; w.textContent = mg < 0 ? tr('sc.warnNeg') : '';
}

const COMP = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const compName = (c) => (c === '–' ? c : tr('dir.' + c));
function setT(t) {
  const P = S.plan; if (!P || P.fail) return;
  const tl = P.tl, T = tl.t, end = T[T.length - 1];
  t = Math.max(0, Math.min(end, t)); S.t = t;
  let lo = 0, hi = T.length - 1; while (hi - lo > 1) { const m = (lo + hi) >> 1; if (T[m] <= t) lo = m; else hi = m; }
  const i = lo, j = Math.min(hi, T.length - 1), f = T[j] > T[i] ? (t - T[i]) / (T[j] - T[i]) : 0;
  const x = tl.x[i] + (tl.x[j] - tl.x[i]) * f, y = tl.y[i] + (tl.y[j] - tl.y[i]) * f;
  tl._oa = tl.oa[i] + (tl.oa[j] - tl.oa[i]) * f; tl._d = tl.d[i] + (tl.d[j] - tl.d[i]) * f; tl._home = tl.home[i] + (tl.home[j] - tl.home[i]) * f;
  // heading from the next vertex with movement
  let k = j; while (k < tl.x.length - 1 && tl.x[k] === tl.x[i] && tl.y[k] === tl.y[i]) k++;
  const dx = tl.x[k] - tl.x[i], dy = tl.y[k] - tl.y[i];
  tl._hd = dx || dy ? COMP[Math.round(((Math.atan2(dx, dy) / DEG + 360) % 360) / 45) % 8] : '–';
  S.astro.setLngLat(xyToLL(x, y));
  const walked = tl.x.slice(0, i + 1).map((xx, q) => xyToLL(xx, tl.y[q])); walked.push(xyToLL(x, y));
  S.map.getSource('walked').setData(fc(walked.length > 1 ? [{ type: 'Feature', geometry: { type: 'LineString', coordinates: walked } }] : []));
  $('#tLbl').textContent = tr('sc.tOf', { t: fmtMin(t), e: fmtMin(end) });
  if (!S.scrubbing) $('#scrub').value = Math.round(1000 * t / end);
  setHud(i);
  // where am I: stay at a target, at the habitat, or walking
  const atStay = tl.stay[j] && T[j] > T[i] && tl.x[i] === tl.x[j] && tl.y[i] === tl.y[j] ? tl.stay[j] : 0;
  const nearHab = Math.hypot(x, y) < 12;
  const cls = classAt(x, y);
  const where = atStay ? tr('sc.atTarget', { n: atStay }) : nearHab && (t === 0 || t === end) ? (t === 0 ? tr('sc.atStart') : tr('sc.back')) : tr('sc.walking', { to: nextLegTarget(tl, j), h: compName(tl._hd) });
  setView({ cls: CLS[cls], where, idx: Math.floor(tl._d / 150) });
}
function nextLegTarget(tl, j) { const L = S.plan.legs[tl.leg[j]]; return L ? (L.to ? `T${L.to}` : tr('common.habitat')) : tr('common.habitat'); }
function classAt(x, y) {
  const [r, c] = rc2(x, y), cnt = [0, 0, 0, 0];
  for (let dr = -2; dr <= 2; dr++) for (let dc = -2; dc <= 2; dc++) { const rr = r + dr, cc = c + dc; if (rr >= 0 && cc >= 0 && rr < N && cc < N) cnt[S.ref[rr * N + cc]]++; }
  return cnt.indexOf(Math.max(...cnt));
}

// ---------- right pane: front view
function setView({ cls, where, idx }) {
  $('#viewWhere').textContent = where;
  const c = $('#viewCls'); c.textContent = tr('sc.ground.' + cls); c.className = cls;
  const list = S.VW.views[cls];
  if (!list || !list.length) {
    const key = 'schem:' + cls; if (S.viewKey === key) return; S.viewKey = key;
    $('#imgA').classList.remove('on'); $('#imgB').classList.remove('on');
    const sv = $('#viewSchem'); sv.hidden = false; sv.textContent = tr('sc.schem', { c: clsName(cls) });
    $('#viewNote').textContent = tr('sc.schemNote'); $('#viewCredit').textContent = '';
    return;
  }
  $('#viewSchem').hidden = true;
  const v = list[((idx % list.length) + list.length) % list.length], key = v.src;
  $('#viewNote').textContent = tr('sc.viewNote');
  $('#viewCredit').innerHTML = tr('sc.viewCredit', { cam: v.camera === 'NAVCAM_LEFT' ? 'Navcam' : 'Front Hazcam', sol: v.sol, wp: v.waypoint, credit: v.credit, page: v.page });
  if (S.viewKey === key) return; S.viewKey = key;
  const a = $('#imgA'), b = $('#imgB'), on = a.classList.contains('on') ? a : b, off = on === a ? b : a;
  off.onload = () => { off.classList.add('on'); on.classList.remove('on'); };
  off.alt = `Perseverance ${v.camera} image, sol ${v.sol}, ${cls} terrain`; off.src = v.src;
}

// ---------- replay
function play() {
  if (!S.plan || S.plan.fail) return;
  const end = S.plan.tl.t.at(-1); if (S.t >= end) S.t = 0;
  S.playing = true; $('#play').textContent = tr('common.pause');
  let last = performance.now();
  const tick = (now) => {
    if (!S.playing) return;
    const dt = (now - last) / 1000; last = now;
    setT(S.t + dt * SPEED_MIN_PER_S);
    if (S.t >= end) { stop(); return; }
    S.raf = requestAnimationFrame(tick);
  };
  S.raf = requestAnimationFrame(tick);
}
function stop() { S.playing = false; cancelAnimationFrame(S.raf); $('#play').textContent = tr('common.play'); }

// ---------- UI
function setStep(n) {
  S.step = n;
  document.querySelectorAll('.step').forEach((b) => { const on = +b.dataset.step === n; b.classList.toggle('active', on); b.setAttribute('aria-selected', on); });
  document.querySelectorAll('.pane').forEach((p) => { p.hidden = +p.dataset.pane !== n; });
  if (n === 3) renderPlanOut();
  if (n === 2) renderTargets();
}
function bindUI() {
  document.querySelectorAll('.step').forEach((b) => (b.onclick = () => setStep(+b.dataset.step)));
  const lbl = () => { $('#capLbl').textContent = $('#cap').value; };
  lbl(); $('#play').textContent = tr('common.play'); $('#tLbl').textContent = fmtMin(0);
  $('#cap').addEventListener('input', () => { lbl(); if (S.plan) { planTour(); } });
  $('#modeScratch').onclick = () => setMode('scratch'); $('#modePan').onclick = () => setMode('pan');
  $('#showCls').onchange = () => S.map.setLayoutProperty('cls', 'visibility', $('#showCls').checked ? 'visible' : 'none');
  $('#revealAll').onclick = () => { $('#coverCanvas').getContext('2d').clearRect(0, 0, N, N); S.rev.fill(1); S.nRev = N * N; afterScratch(true); };
  $('#resetBtn').onclick = () => {
    stop(); S.rev.fill(0); S.nRev = 0; paintCover(); S.targets = []; S.analysis = null; S.plan = null; S.stale = false;
    drawTargets(); clearRoute(); afterScratch(true); renderTargets(); renderPlanOut();
  };
  $('#analyse').onclick = () => { $('#analyse').disabled = true; $('#analyse').textContent = tr('sc.analysing'); setTimeout(() => { try { analyse(); } finally { $('#analyse').disabled = false; $('#analyse').textContent = tr('sc.analyse'); } }, 20); };
  $('#plan').onclick = () => { if (S.stale && S.analysis) analyse(); planTour(); };
  $('#play').onclick = () => (S.playing ? stop() : play());
  $('#scrub').addEventListener('input', () => { stop(); S.scrubbing = true; setT(+$('#scrub').value / 1000 * S.plan.tl.t.at(-1)); S.scrubbing = false; });
  renderTargets(); renderPlanOut();
}

init().catch((e) => { console.error(e); document.body.insertAdjacentHTML('afterbegin', `<div class="msg">${tr('common.loadFail')}: ${e.message}</div>`); });
