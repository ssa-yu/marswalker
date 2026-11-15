// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Arcadia brain-terrain demo: ① rover recon → ② brain heat map and chosen areas → ③ astronaut route.
   Data: data/arcadia/arcadia.json + images (pipeline/arcadia_export.py). Plain JS, no build step.
   ③: click the map to move the astronaut's start; the multi-stop plan is recomputed in the browser on the 8 m
   per-metre kcal / minute grid (cost8.bin.gz, Shooyunn's Pandolf model) with the same order rule as Python. */
'use strict';
const D = 'data/arcadia/';
const $ = (s) => document.querySelector(s);
const abs = (u) => new URL(u, location.href).href;
const S = { step: 1, loop: 10, markers: [], start: null, plan: null, mode: 'rover', dirty: true, myT: [] };
const BRUSH_M = 100, FREE_M = 20;   // "scout it yourself": brush radius, and the ground already known around the base
const GUIDE_KEY = 'marswalker-guide-seen';
const CLASS_EN = ['Firm ground', 'Rough ground', 'Sand', 'Impassable'];
const avg = (ts) => (ts.length ? (ts.reduce((s, t) => s + t.score, 0) / ts.length).toFixed(2) : '–');
function hint(n) {
  const self = S.mode === 'self', R = S.d.targets.after;
  if (n === 1) return self ? 'Drag on the map to scout. Colour shows how brain-like the ground is: chase the bright areas. You can uncover as much ground as the rover did.'
    : 'Drag the slider to replay the rover\'s trips out from the base.';
  if (n === 2) {
    if (!self) return 'Brighter = more brain-like. Yellow boxes are the areas picked from what the rover has seen.';
    return S.myT.length ? `Yellow boxes: the ${S.myT.length} best areas in the ground you scouted, average score ${avg(S.myT)}. The rover's ${R.length} areas average ${avg(R)}.`
      : 'No area is at least half uncovered yet. Go back to step 1 and scout more ground.';
  }
  if (self && !S.myT.length) return 'No target yet. Go back to step 1 and scout more ground.';
  return 'Click a numbered stop for details, or click anywhere on the map to move the astronaut\'s start.';
}
const VEIL = 128, VEIL_SCRATCH = 170;   // mask alpha: 50 % as before; darker while scratching
const C_ROVER = '#3987e5', C_ROVER_NOW = '#f2b36b', C_ROUTE = '#38e1ff', C_TGT = '#ffd23f';

async function init() {
  S.d = await (await fetch(D + 'arcadia.json')).json();
  S.ctx = await fetch(D + 'context.json').then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const c = await pixels(D + S.d.files.seen_loop), px = c.data;
  S.seenLoop = new Uint8Array(c.width * c.height);
  for (let i = 0; i < S.seenLoop.length; i++) S.seenLoop[i] = px[4 * i];
  // "scout it yourself": brain score index (0 = none, 1..255 = 0..1), the heat map's own pixels, the class grid
  const sp = (await pixels(D + (S.d.files.brain_score || 'brain_score.png'))).data;
  S.score = new Uint8Array(S.seenLoop.length);
  for (let i = 0; i < S.score.length; i++) S.score[i] = sp[4 * i];
  S.heatPx = (await pixels(D + S.d.files.brain_all)).data;
  await classGrid();
  S.GW = c.width; S.GH = c.height; S.gres = (S.d.aoi_local_m[2] - S.d.aoi_local_m[0]) / c.width;
  S.capCells = 0; for (let i = 0; i < S.seenLoop.length; i++) if (S.seenLoop[i] > 0) S.capCells++;
  S.mySeen = new Uint8Array(S.seenLoop.length);
  const v = $('#veil'); v.width = c.width; v.height = c.height; S.veilCtx = v.getContext('2d'); S.veilImg = S.veilCtx.createImageData(c.width, c.height);
  S.cost = await loadCost(S.d);
  const N = S.d.rover.loops.length;
  $('#loop').max = N; $('#loop').value = N; $('#loopMax').textContent = N; S.loop = N;
  buildMap();
}

async function pixels(url) {
  const im = new Image(); im.src = url; await im.decode();
  const c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
  const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0);
  return x.getImageData(0, 0, c.width, c.height);
}

function buildMap() {
  const d = S.d, c = d.aoi_corners;
  // outer extent the user can pan/zoom out to: the Mars Trek context image (else the AOI)
  const outer = S.ctx && S.ctx.trek ? S.ctx.trek.coordinates : c;
  const map = new maplibregl.Map({
    container: 'map', bounds: [[c[0][0], c[2][1]], [c[1][0], c[0][1]]], fitBoundsOptions: { padding: 40 },
    maxZoom: 20, minZoom: S.ctx ? 6 : 10, renderWorldCopies: false,
    maxBounds: S.ctx ? [[outer[0][0], outer[2][1]], [outer[1][0], outer[0][1]]] : undefined, dragRotate: false, pitchWithRotate: false,
    style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0d0b0a' } }] },
    attributionControl: false,
  });
  S.map = map; window.__mapIdle = false;
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
  map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
  map.on('load', () => {
    const img = (id, f, paint = {}) => {
      map.addSource(id, { type: 'image', url: abs(D + f), coordinates: c });
      map.addLayer({ id, type: 'raster', source: id, paint: { 'raster-fade-duration': 0, ...paint } });
    };
    // context basemap under the study area (display only): Mars Trek THEMIS Day IR; HiRISE only inside the square
    if (S.ctx && S.ctx.trek) {
      map.addSource('trek', { type: 'image', url: abs(D + S.ctx.trek.file), coordinates: S.ctx.trek.coordinates });
      map.addLayer({ id: 'trek', type: 'raster', source: 'trek', paint: { 'raster-fade-duration': 0, 'raster-brightness-max': 0.8 } });
    }
    map.addSource('ortho', { type: 'raster', tiles: [abs(D) + d.tiles.url], tileSize: 256, minzoom: d.tiles.minzoom, maxzoom: d.tiles.maxzoom, bounds: d.tiles.bounds });
    map.addLayer({ id: 'ortho', type: 'raster', source: 'ortho', paint: { 'raster-fade-duration': 0 } });
    img('classes', d.files.classes, { 'raster-resampling': 'nearest' });
    img('brain_all', d.files.brain_all, { 'raster-resampling': 'nearest' });
    void img;
    map.addSource('veil', { type: 'canvas', canvas: 'veil', coordinates: c, animate: false });
    map.addLayer({ id: 'veil', type: 'raster', source: 'veil', paint: { 'raster-fade-duration': 0, 'raster-resampling': 'nearest' } });
    const gj = (features) => ({ type: 'FeatureCollection', features });
    const aoi = [...c, c[0]];
    map.addSource('aoi', { type: 'geojson', data: gj([{ type: 'Feature', geometry: { type: 'LineString', coordinates: aoi } }]) });
    map.addLayer({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.2, 'line-opacity': 0.9 } });
    map.addSource('rover', { type: 'geojson', data: gj(d.rover.loops.map((L) => ({ type: 'Feature', properties: { id: L.id }, geometry: { type: 'LineString', coordinates: L.path } }))) });
    map.addLayer({ id: 'rover-casing', type: 'line', source: 'rover', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 4, 'line-opacity': 0.6 } });
    map.addLayer({ id: 'rover', type: 'line', source: 'rover', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': C_ROVER, 'line-width': 2 } });
    map.addSource('tgt', { type: 'geojson', data: gj([]) });
    map.addLayer({ id: 'tgt-hit', type: 'fill', source: 'tgt', paint: { 'fill-color': '#000', 'fill-opacity': 0.01 } });
    map.addLayer({ id: 'tgt', type: 'line', source: 'tgt', filter: ['==', ['get', 'onroute'], true], paint: { 'line-color': C_TGT, 'line-width': 2.5 } });
    map.addLayer({ id: 'tgt-far', type: 'line', source: 'tgt', filter: ['!=', ['get', 'onroute'], true], paint: { 'line-color': C_TGT, 'line-width': 2, 'line-dasharray': [2, 1.5] } });
    map.addSource('route', { type: 'geojson', data: gj([]) });
    map.addLayer({ id: 'route-casing', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 6, 'line-opacity': 0.6 } });
    map.addLayer({ id: 'route', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': C_ROUTE, 'line-width': 3 } });
    map.on('click', onMapClick);
    map.on('mouseenter', 'route', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'route', () => { map.getCanvas().style.cursor = ''; });
    wire();
    resetMine();
    showPlan(null);
    setStep(1);
    map.once('idle', () => { window.__mapIdle = true; });
  });
}

function wire() {
  document.querySelectorAll('.steps .btn').forEach((b) => b.onclick = () => setStep(+b.dataset.step));
  $('#loop').oninput = () => { S.loop = +$('#loop').value; apply(); };
  ['#lyrImg', '#lyrCls', '#lyrHeat', '#lyrMask'].forEach((s) => $(s).onchange = apply);
  $('#home').onclick = () => { S.start = null; showPlan(null); $('#card').hidden = true; apply(); };
  $('#walk3d').onclick = open3d;
  $('#w3dClose').onclick = () => { $('#w3d').hidden = true; $('#w3dFrame').src = 'about:blank'; };
  const seen = () => { try { return localStorage.getItem(GUIDE_KEY); } catch { return '1'; } };
  const closeGuide = (mode) => { $('#guide').hidden = true; try { localStorage.setItem(GUIDE_KEY, '1'); } catch { /* private mode */ } S.step = 1; setMode(mode); };
  $('#help').onclick = () => { $('#guide').hidden = false; };
  $('#guideGo').onclick = () => closeGuide('rover');
  $('#guideSelf').onclick = () => closeGuide('self');
  document.querySelectorAll('#who .btn').forEach((b) => b.onclick = () => setMode(b.dataset.mode));
  $('#mineReset').onclick = () => { resetMine(); apply(); };
  $('#mineGo').onclick = $('#doneGo').onclick = () => setStep(2);
  $('#roverLbl').textContent = (100 * S.capCells / S.seenLoop.length).toFixed(1) + '%';
  wireScratch();
  if (!seen() && !new URLSearchParams(location.search).has('noguide')) $('#guide').hidden = false;
}

function setStep(n) {
  S.step = n;
  $('#lyrCls').checked = false;
  $('#lyrHeat').checked = n === 2;
  if (n === 1) { S.loop = S.d.rover.loops.length; $('#loop').value = S.loop; }
  $('#card').hidden = true;
  if (S.mode === 'self' && n >= 2) syncSelf();
  apply();
  frame();
}

// who scouted: the rover (the page's precomputed result) or the visitor (their own scratched ground, same rules)
function setMode(m) {
  S.mode = m; S.start = null; S.dirty = true;
  if (m === 'self') $('#who').classList.add('used');
  if (m === 'rover') showPlan(null);
  setStep(S.step);
}
function tgs() { return S.mode === 'self' ? S.myT : S.d.targets.after; }
function baseIdx() { const b = toXY(S.d.base); const i = xyToIdx(b[0], b[1]); return i >= 0 && isFinite(S.cost.K[i]) ? i : nearestPassable(b[0], b[1]); }
function syncSelf() {
  if (!S.dirty) return;
  S.myT = pickBlocks(S.mySeen); S.dirty = false;
  showPlan(S.start ? planFrom(S.start.idx) : null);
}

function frame() {
  const d = S.d, c = d.aoi_corners;
  let pts = [c[0], c[2]];
  if (S.step === 2 && S.mode === 'rover') pts = d.rover.loops.flatMap((L) => L.path);
  if (S.step === 3 && S.plan.legs.length) pts = S.plan.legs.flatMap((L) => L.path);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  S.map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: innerWidth >= 1100 ? { top: 40, bottom: 70, left: 500, right: S.step === 3 ? 220 : 40 } : { top: Math.min(innerHeight * 0.55, $('#box').getBoundingClientRect().bottom + 16), bottom: 120, left: 24, right: 24 }, duration: 0, maxZoom: 17 });
}

const scratching = () => S.mode === 'self' && S.step === 1;
// One pixel of the mask. Not seen = black; seen = clear, or (while scratching) the heat map's own pixel, so the
// brain score lights up where the visitor scouts.
function veilPx(i, seen, alpha, heat) {
  const px = S.veilImg.data, j = 4 * i;
  if (seen && heat) { const h = S.heatPx; px[j] = h[j]; px[j + 1] = h[j + 1]; px[j + 2] = h[j + 2]; px[j + 3] = h[j + 3]; }
  else { px[j] = 0; px[j + 1] = 0; px[j + 2] = 0; px[j + 3] = seen ? 0 : alpha; }
}
function flushVeil() {
  S.veilCtx.putImageData(S.veilImg, 0, 0);
  const src = S.map.getSource('veil'); if (src) { src.play(); src.pause(); }
}
function drawVeil(k) {
  const sl = S.seenLoop, self = S.mode === 'self', heat = scratching(), alpha = heat ? VEIL_SCRATCH : VEIL;
  for (let i = 0; i < sl.length; i++) veilPx(i, self ? S.mySeen[i] === 1 : sl[i] > 0 && sl[i] <= k, alpha, heat);
  flushVeil();
}

function vis(id, on) { S.map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); }

function apply() {
  const d = S.d, m = S.map, n = S.step;
  document.querySelectorAll('.steps .btn').forEach((b) => b.classList.toggle('active', +b.dataset.step === n));
  const self = S.mode === 'self', scr = scratching();
  document.querySelectorAll('#who .btn').forEach((b) => b.classList.toggle('active', b.dataset.mode === S.mode));
  $('#ctl1').hidden = n !== 1; $('#ctlSelf').hidden = !self; $('#ctlRover').hidden = self; $('#loop').hidden = self;
  $('#ctl3').hidden = n !== 3 || !S.start; $('#walk3d').hidden = n !== 3 || !S.plan.legs.length;
  document.querySelector('.layers').hidden = scr;
  document.body.classList.toggle('s3', n === 3);
  $('#hint').textContent = hint(n);
  if (scr) { m.dragPan.disable(); m.getCanvas().style.cursor = 'crosshair'; } else { m.dragPan.enable(); m.getCanvas().style.cursor = ''; $('#brush').hidden = true; }
  ghost(scr && !S.touched);
  updMine();
  const heat = $('#lyrHeat').checked;
  vis('ortho', $('#lyrImg').checked);
  vis('classes', $('#lyrCls').checked);
  vis('brain_all', heat && !scr);
  // unexplored mask: ground the rover has not seen yet (up to the slider's loop in ①, all loops in ② and ③), black at 50 %
  const k = n === 1 ? S.loop : d.rover.loops.length;
  const maskOn = scr || $('#lyrMask').checked;
  if (maskOn) drawVeil(k);
  vis('veil', maskOn);
  vis('rover', !self && n <= 2); vis('rover-casing', !self && n === 1);
  m.setFilter('rover', ['<=', ['get', 'id'], k]);
  m.setFilter('rover-casing', ['<=', ['get', 'id'], k]);
  m.setPaintProperty('rover', 'line-color', n === 1 ? ['case', ['==', ['get', 'id'], k], C_ROVER_NOW, C_ROVER] : C_ROVER);
  m.setPaintProperty('rover', 'line-opacity', n === 1 ? 1 : 0.45);
  m.setPaintProperty('rover', 'line-width', n === 1 ? 2 : 1.2);
  vis('tgt', n >= 2); vis('tgt-hit', n === 3); vis('tgt-far', n === 3);
  S.map.setFilter('tgt', n === 3 ? ['==', ['get', 'onroute'], true] : null);
  vis('route', n === 3); vis('route-casing', n === 3);
  $('#loopLbl').textContent = k;
  if (n === 1 && !self) {
    let s = 0; for (let i = 0; i < S.seenLoop.length; i++) if (S.seenLoop[i] > 0 && S.seenLoop[i] <= k) s++;
    $('#seenLbl').textContent = (100 * s / S.seenLoop.length).toFixed(1) + '%';
  }
  markers();
  legend();
}

function mk(ll, cls, text, onclick) {
  const el = document.createElement('div'); el.className = 'mk ' + cls; el.textContent = text;
  if (onclick) { el.style.cursor = 'pointer'; el.onclick = (e) => { e.stopPropagation(); onclick(); }; }
  const m = new maplibregl.Marker({ element: el }).setLngLat(ll).addTo(S.map);
  S.markers.push(m);
}

function markers() {
  S.markers.forEach((m) => m.remove()); S.markers = [];
  const d = S.d, n = S.step;
  mk(d.base, 'base', 'Base');
  if (n === 3 && S.start) mk(S.start.ll, 'start', 'Astronaut start');
  if (n === 2) {
    tgs().forEach((t) => mk(t.stop, 'tgt', `${t.id} ${t.score.toFixed(2)}`));
  }
  if (n === 3) {
    S.plan.legs.forEach((L, i) => {
      if (i === S.plan.legs.length - 1) return;
      const t = tgs().find((x) => x.id === L.to);
      mk(t.stop, 'stop', `${i + 1}`, () => stopCard(i));
    });
  }
}

function showCard(title, v) {
  const h = Math.floor(v.min / 60), mi = Math.round(v.min % 60);
  $('#card').innerHTML = `<h4><span>${title}</span><button aria-label="Close" onclick="this.closest('#card').hidden=true">×</button></h4>
    <div class="kv"><span>Distance</span><span>${(v.distance_m / 1000).toFixed(2)} km</span>
    <span>Time</span><span>${h ? h + ' h ' : ''}${mi} min</span>
    <span>Energy</span><span>${Math.round(v.kcal)} kcal</span>
    <span>Oxygen</span><span>${Math.round(v.o2_l)} L</span></div>`;
  $('#card').hidden = false;
}

function legend() {
  const d = S.d, n = S.step, it = (sw, t) => `<div class="it">${sw}<span>${t}</span></div>`;
  let h = '';
  if ($('#lyrCls').checked) h += d.classes.map((c, i) => it(`<i style="background:${c.color}"></i>`, CLASS_EN[i] || c.zh)).join('');
  const self = S.mode === 'self', scr = scratching();
  if ($('#lyrHeat').checked || scr) h += `<div class="it"><span>Brain-terrain score</span></div><div class="ramp"></div><div class="rl"><span>0</span><span>0.5</span><span>1</span></div>`;
  if ($('#lyrMask').checked || scr) h += it('<i style="background:#000;opacity:.5"></i>', self ? 'Not scouted yet' : 'Unexplored (not yet seen by the rover)');
  if (n === 1 && !self) h += it(`<i class="ln" style="background:${C_ROVER}"></i>`, 'Rover path') + it(`<i class="ln" style="background:${C_ROVER_NOW}"></i>`, 'Current trip');
  if (n === 2) h += it(`<i style="border:2px solid ${C_TGT}"></i>`, self ? `${tgs().length} areas picked from your scouting (60 m)` : `${tgs().length} areas picked after scouting (60 m)`);
  if (n === 3) {
    const t = S.plan.total;
    h += it(`<i class="ln" style="background:${C_ROUTE}"></i>`, `Astronaut route: ${S.plan.n_stops} stops, ${(t.distance_m / 1000).toFixed(2)} km, ${Math.round(t.kcal)} kcal`);
  }
  h += it('<i class="pt" style="background:#fff"></i>', 'Base');
  $('#legend').innerHTML = h;
}


// ---------------------------------------------------------------------------------------------- ③ start point
async function loadCost(d) {
  const r = await fetch(D + d.files.cost);
  const ds = r.body.pipeThrough(new DecompressionStream('gzip'));
  const buf = await new Response(ds).arrayBuffer();
  const P = d.planner, n = P.shape[0] * P.shape[1], u = new Uint16Array(buf);
  const K = new Float32Array(n), T = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    K[i] = u[i] === P.blocked ? Infinity : u[i] / P.scale;
    T[i] = u[n + i] === P.blocked ? Infinity : u[n + i] / P.scale;
  }
  return { K, T, H: P.shape[0], W: P.shape[1], res: P.res_m };
}

const RAD = Math.PI / 180;
function toXY(ll) { const g = S.d.geo; return [g.R * (ll[0] - g.lon0) * RAD * Math.cos(g.lat0 * RAD), g.R * (ll[1] - g.lat0) * RAD]; }
function toLL(x, y) { const g = S.d.geo; return [g.lon0 + x / (g.R * Math.cos(g.lat0 * RAD)) / RAD, g.lat0 + y / g.R / RAD]; }
function xyToIdx(x, y) {
  const a = S.d.aoi_local_m, C = S.cost;
  const r = Math.floor((a[3] - y) / C.res), c = Math.floor((x - a[0]) / C.res);
  return (r < 0 || c < 0 || r >= C.H || c >= C.W) ? -1 : r * C.W + c;
}
function idxLL(i) { const a = S.d.aoi_local_m, C = S.cost, r = Math.floor(i / C.W), c = i % C.W; return toLL(a[0] + (c + 0.5) * C.res, a[3] - (r + 0.5) * C.res); }
function nearestPassable(x, y) {
  const a = S.d.aoi_local_m, C = S.cost;
  const r0 = Math.min(C.H - 1, Math.max(0, Math.floor((a[3] - y) / C.res))), c0 = Math.min(C.W - 1, Math.max(0, Math.floor((x - a[0]) / C.res)));
  for (let k = 0; k < Math.max(C.H, C.W); k++) {
    let best = -1, bd = Infinity;
    for (let r = r0 - k; r <= r0 + k; r++) for (let c = c0 - k; c <= c0 + k; c++) {
      if (r < 0 || c < 0 || r >= C.H || c >= C.W || Math.max(Math.abs(r - r0), Math.abs(c - c0)) !== k) continue;
      const i = r * C.W + c; if (!isFinite(C.K[i])) continue;
      const dd = (r - r0) ** 2 + (c - c0) ** 2; if (dd < bd) { bd = dd; best = i; }
    }
    if (best >= 0) return best;
  }
  return -1;
}

// Dijkstra on the 8 m grid, 8 neighbours, step cost = mean of the two cells' per-metre kcal x step length
// (same convention as skimage MCP_Geometric in pipeline/astro_plan.py). box = [r0, r1, c0, c1] or null; limit = stop cost.
function dijkstra(src, box, limit) {
  const C = S.cost, W = C.W, n = C.H * W, K = C.K;
  const dist = new Float64Array(n).fill(Infinity), prev = new Int32Array(n).fill(-1);
  const [r0, r1, c0, c1] = box || [0, C.H - 1, 0, W - 1];
  let hk = new Float64Array(1024), hv = new Int32Array(1024), hn = 0;
  const push = (k, v) => {
    if (hn === hk.length) { const a = new Float64Array(hn * 2); a.set(hk); hk = a; const b = new Int32Array(hn * 2); b.set(hv); hv = b; }
    let i = hn++; while (i > 0) { const p = (i - 1) >> 1; if (hk[p] <= k) break; hk[i] = hk[p]; hv[i] = hv[p]; i = p; } hk[i] = k; hv[i] = v;
  };
  const pop = () => {
    const v = hv[0], lk = hk[--hn], lv = hv[hn]; let i = 0;
    for (;;) { let c = 2 * i + 1; if (c >= hn) break; if (c + 1 < hn && hk[c + 1] < hk[c]) c++; if (hk[c] >= lk) break; hk[i] = hk[c]; hv[i] = hv[c]; i = c; }
    hk[i] = lk; hv[i] = lv; return v;
  };
  const DR = [-1, -1, -1, 0, 0, 1, 1, 1], DC = [-1, 0, 1, -1, 1, -1, 0, 1], L = DR.map((r, k) => C.res * (r && DC[k] ? Math.SQRT2 : 1));
  dist[src] = 0; push(0, src);
  while (hn) {
    const k0 = hk[0], u = pop();
    if (k0 > dist[u]) continue;
    if (k0 > limit) break;
    const ur = (u / W) | 0, uc = u - ur * W, ku = K[u];
    for (let q = 0; q < 8; q++) {
      const r = ur + DR[q], c = uc + DC[q];
      if (r < r0 || r > r1 || c < c0 || c > c1) continue;
      const v = r * W + c, kv = K[v];
      if (kv === Infinity) continue;
      const nd = k0 + 0.5 * (ku + kv) * L[q];
      if (nd < dist[v]) { dist[v] = nd; prev[v] = u; push(nd, v); }
    }
  }
  return { dist, prev };
}

function trace(f, to) { const p = []; for (let i = to; i >= 0; i = f.prev[i]) p.push(i); return p.reverse(); }

// Multi-stop rule of pipeline/multistop.py: most stops, then least planned kcal; after the dwell at every stop the
// kcal used + kcal home <= usable; brute force over orders for <= brute_max candidates, greedy nearest-feasible beyond.
function planFrom(srcIdx) {
  const d = S.d, P = d.planner, C = S.cost, U = P.usable_kcal, dw = P.dwell_min * P.stand_kcal_per_min;
  const t0 = performance.now();
  const f0 = dijkstra(srcIdx, null, Infinity);
  const sr = (srcIdx / C.W) | 0, scc = srcIdx % C.W, wc = Math.round(P.window_m / C.res);
  const box = [Math.max(0, sr - wc), Math.min(C.H - 1, sr + wc), Math.max(0, scc - wc), Math.min(C.W - 1, scc + wc)];
  const sxy = toXY(idxLL(srcIdx));
  const tg = tgs().map((t) => {
    let i = xyToIdx(t.xy[0], t.xy[1]); if (i < 0 || !isFinite(C.K[i])) i = nearestPassable(t.xy[0], t.xy[1]);
    return { id: t.id, idx: i, inWin: Math.max(Math.abs(t.xy[0] - sxy[0]), Math.abs(t.xy[1] - sxy[1])) <= P.window_m, rt: 2 * f0.dist[i] + dw };
  });
  const cand = tg.map((t, k) => k).filter((k) => tg[k].inWin);
  const pts = [srcIdx, ...cand.map((k) => tg[k].idx)];
  const fields = [dijkstra(srcIdx, box, U), ...cand.map((k) => dijkstra(tg[k].idx, box, U))];
  const n = cand.length, Dm = pts.map((_, i) => pts.map((q) => fields[i].dist[q]));
  const tourCost = (ord) => {
    let used = 0, cur = 0;
    for (const j of ord) { used += Dm[cur][j + 1] + dw; if (!isFinite(used) || used + Dm[j + 1][0] > U + 1e-9) return Infinity; cur = j + 1; }
    return used + Dm[cur][0];
  };
  let best = [], bestC = 0;
  if (n <= P.brute_max) {
    const perms = (arr, k) => { const out = []; const rec = (pre, rest) => { if (pre.length === k) { out.push(pre); return; } rest.forEach((x, i) => rec([...pre, x], rest.filter((_, j) => j !== i))); }; rec([], arr); return out; };
    for (let k = n; k >= 1 && !best.length; k--) {
      let bc = Infinity, bo = null;
      for (const o of perms([...Array(n).keys()], k)) { const c = tourCost(o); if (c < bc) { bc = c; bo = o; } }
      if (bo) { best = bo; bestC = bc; }
    }
  } else {
    let cur = 0, used = 0; const left = new Set([...Array(n).keys()]);
    for (;;) {
      let bj = -1, bd = Infinity;
      for (const j of left) { const dd = Dm[cur][j + 1]; if (used + dd + dw + Dm[j + 1][0] <= U + 1e-9 && dd < bd) { bd = dd; bj = j; } }
      if (bj < 0) break; used += bd + dw; cur = bj + 1; best.push(bj); left.delete(bj);
    }
    bestC = best.length ? used + Dm[cur][0] : 0;
  }
  // walk the tour: per-metre kcal and minutes, mean of the two cells x step length; dwell on arrival
  const stops = [0, ...best.map((j) => j + 1), 0], legs = [];
  const cum = { distance_m: 0, min: 0, kcal: 0 };
  for (let s = 0; s + 1 < stops.length; s++) {
    if (stops[s] === stops[s + 1]) continue;
    const path = trace(fields[stops[s]], pts[stops[s + 1]]);
    let dist = 0, mn = 0, kc = 0;
    for (let q = 1; q < path.length; q++) {
      const a = path[q - 1], b = path[q], diag = ((a / C.W) | 0) !== ((b / C.W) | 0) && a % C.W !== b % C.W;
      const Lm = C.res * (diag ? Math.SQRT2 : 1);
      dist += Lm; mn += 0.5 * (C.T[a] + C.T[b]) * Lm; kc += 0.5 * (C.K[a] + C.K[b]) * Lm;
    }
    const last = stops[s + 1] === 0, dwm = last ? 0 : P.dwell_min;
    cum.distance_m += dist; cum.min += mn + dwm; cum.kcal += kc + (last ? 0 : dw);
    legs.push({ to: last ? 'start' : tg[cand[stops[s + 1] - 1]].id, distance_m: dist, min: mn + dwm, kcal: kc + (last ? 0 : dw),
      cum: { ...cum }, path: path.map(idxLL) });
  }
  const visited = best.map((j) => tg[cand[j]].id);
  return { legs, n_stops: best.length, visited, rt: Object.fromEntries(tg.map((t) => [t.id, t.rt])), planned_kcal: bestC,
    total: { distance_m: cum.distance_m, min: cum.min, kcal: cum.kcal, o2_l: cum.kcal / P.kcal_per_l_o2 }, ms: Math.round(performance.now() - t0) };
}

function pyPlan() {
  const d = S.d, R = d.route;
  return { legs: R.legs.map((L) => ({ to: L.to === 'base' ? 'start' : L.to, distance_m: L.distance_m, min: L.min, kcal: L.kcal, cum: L.cum, path: L.path })),
    n_stops: R.n_stops, visited: R.order, rt: Object.fromEntries(d.targets.after.map((t) => [t.id, t.rt_kcal])), total: R.total };
}

function showPlan(p) {
  S.plan = p || (S.mode === 'self' ? planFrom(baseIdx()) : pyPlan());
  const gj = (features) => ({ type: 'FeatureCollection', features });
  S.map.getSource('route').setData(gj(S.plan.legs.map((L, i) => ({ type: 'Feature', properties: { i }, geometry: { type: 'LineString', coordinates: L.path } }))));
  S.map.getSource('tgt').setData(gj(tgs().map((t) => ({ type: 'Feature', properties: { id: t.id, onroute: S.plan.visited.includes(t.id) }, geometry: { type: 'Polygon', coordinates: [t.block] } }))));
}

function stopCard(i) {
  const L = S.plan.legs[i], from = S.start ? 'the start' : 'the base';
  showCard(`Stop ${i + 1} (${L.to}): from ${from} to here, incl. time on site`, { distance_m: L.cum.distance_m, min: L.cum.min, kcal: L.cum.kcal, o2_l: L.cum.kcal / S.d.planner.kcal_per_l_o2 });
}

function onMapClick(e) {
  if (S.step !== 3) return;
  const hit = S.map.queryRenderedFeatures(e.point, { layers: ['tgt-hit'] });
  if (hit.length) {
    const id = hit[0].properties.id, i = S.plan.legs.findIndex((L) => L.to === id);
    if (i >= 0) { stopCard(i); return; }
    const x = S.plan.rt[id];
    $('#card').innerHTML = `<h4><span>Round trip needs ${isFinite(x) ? Math.round(x).toLocaleString('en-US') : '—'} kcal</span><button aria-label="Close" onclick="this.closest('#card').hidden=true">×</button></h4>`;
    $('#card').hidden = false;
    return;
  }
  if (S.map.queryRenderedFeatures(e.point, { layers: ['route'] }).length) { showCard('Whole route', S.plan.total); return; }
  setStart([e.lngLat.lng, e.lngLat.lat]);
}

function setStart(ll) {
  const xy = toXY(ll); let i = xyToIdx(xy[0], xy[1]);
  if (i < 0 || !isFinite(S.cost.K[i])) i = nearestPassable(xy[0], xy[1]);
  if (i < 0) return;
  S.start = { idx: i, ll: idxLL(i) };
  const p = planFrom(i);
  window.__lastPlanMs = p.ms;
  showPlan(p);
  apply();
  showCard('Whole route', S.plan.total);
}

// ---------------------------------------------------------------------------------------------- scout it yourself
// The visitor plays the rover: dragging uncovers ground (4 m cells, BRUSH_M radius) up to the area the rover saw.
// ② then picks areas from that ground with the rule of pipeline/arcadia.py pick_blocks, ③ plans with planFrom().
function resetMine() {
  S.mySeen.fill(0); S.nMine = 0; S.dirty = true; S.touched = false; S.last = null;
  const b = toXY(S.d.base), a = S.d.aoi_local_m;
  stamp(Math.floor((a[3] - b[1]) / S.gres), Math.floor((b[0] - a[0]) / S.gres), FREE_M / S.gres, true);
}
function stamp(r0, c0, R, free) {
  const W = S.GW, H = S.GH, R2 = R * R, heat = scratching();
  for (let r = Math.max(0, Math.ceil(r0 - R)); r <= Math.min(H - 1, r0 + R); r++) {
    for (let c = Math.max(0, Math.ceil(c0 - R)); c <= Math.min(W - 1, c0 + R); c++) {
      if ((r - r0) ** 2 + (c - c0) ** 2 > R2) continue;
      const i = r * W + c; if (S.mySeen[i]) continue;
      if (!free && S.nMine >= S.capCells) return;
      S.mySeen[i] = 1; S.nMine++; veilPx(i, true, VEIL_SCRATCH, heat);
    }
  }
}
function stroke(ll) {
  const a = S.d.aoi_local_m, [x, y] = toXY(ll), R = BRUSH_M / S.gres;
  const p = [(a[3] - y) / S.gres, (x - a[0]) / S.gres], q = S.last || p;
  const n = Math.max(1, Math.ceil(Math.hypot(p[0] - q[0], p[1] - q[1]) / (R / 2))), before = S.nMine;
  for (let k = 1; k <= n; k++) stamp(Math.round(q[0] + (p[0] - q[0]) * k / n), Math.round(q[1] + (p[1] - q[1]) * k / n), R, false);
  S.last = p;
  if (S.nMine === before) return;
  S.dirty = true;
  if (!S.raf) S.raf = requestAnimationFrame(() => { S.raf = 0; flushVeil(); updMine(); });
}
function updMine() {
  const n = S.seenLoop.length, full = S.nMine >= S.capCells;
  $('#mineLbl').textContent = (100 * S.nMine / n).toFixed(1) + '%';
  $('#mineBar').style.width = Math.min(100, 100 * S.nMine / S.capCells) + '%';
  $('#done').hidden = !(scratching() && full);
}
function brushAt(pt) {
  const b = $('#brush'); if (!scratching()) { b.hidden = true; return; }
  const p0 = S.map.project(S.d.base), p1 = S.map.project(toLL(S.d.base_xy[0] + BRUSH_M, S.d.base_xy[1]));
  const d = 2 * Math.abs(p1.x - p0.x);
  b.style.width = b.style.height = d + 'px'; b.style.left = pt.x + 'px'; b.style.top = pt.y + 'px'; b.hidden = false;
}
function ghost(on) {
  const g = $('#ghost'); g.hidden = !on; if (!on) return;
  const p = S.map.project(S.d.base); g.style.left = p.x + 'px'; g.style.top = p.y + 'px';
}
function wireScratch() {
  const m = S.map;
  const down = (e) => { S.down = true; S.last = null; S.touched = true; ghost(false); stroke(e.lngLat); };
  // mouse: on the map's container, so a drag that starts on a marker (the base label) scratches too
  const box = m.getContainer(), at = (e) => { const r = box.getBoundingClientRect(), point = [e.clientX - r.left, e.clientY - r.top]; return { point: { x: point[0], y: point[1] }, lngLat: m.unproject(point).toArray() }; };
  box.addEventListener('pointerdown', (e) => {
    if (e.pointerType !== 'mouse' || e.button !== 0 || !scratching() || e.target.closest('.maplibregl-ctrl')) return;
    e.preventDefault(); down(at(e));
  });
  box.addEventListener('pointermove', (e) => { if (e.pointerType !== 'mouse') return; const q = at(e); brushAt(q.point); if (S.down && scratching()) stroke(q.lngLat); });
  box.addEventListener('pointerleave', () => { $('#brush').hidden = true; });
  window.addEventListener('pointerup', () => { S.down = false; S.last = null; });
  m.on('touchstart', (e) => { if (scratching() && e.points.length === 1) { e.preventDefault(); down({ lngLat: e.lngLat.toArray() }); } else S.down = false; });
  m.on('touchmove', (e) => { if (S.down && scratching() && e.points.length === 1) stroke(e.lngLat.toArray()); });
  m.on('touchend', () => { S.down = false; S.last = null; });
  m.on('move', () => { if (!$('#ghost').hidden) ghost(true); });
}

// Area selection, the rule of pipeline/arcadia.py pick_blocks (60 m blocks, >= 50 % seen, top 12 by mean brain score,
// centres >= 300 m apart, stop = highest-score passable cell), on the 4 m grid with the score read from brain_score.png
// (1/254 steps). seen: Uint8Array, 1 = seen.
const PICK = { block_m: 60, seen_min: 0.5, n: 12, min_sep_m: 300 };
function pickBlocks(seen) {
  const W = S.GW, H = S.GH, res = S.gres, b = Math.round(PICK.block_m / res), a = S.d.aoi_local_m, sc = S.score, cls = S.cls.g;
  const cand = [];
  for (let i = 0; i < Math.floor(H / b); i++) for (let j = 0; j < Math.floor(W / b); j++) {
    let sum = 0, cnt = 0, sf = 0, ok = false;
    for (let r = i * b; r < (i + 1) * b; r++) for (let c = j * b; c < (j + 1) * b; c++) {
      const q = r * W + c; sf += seen[q];
      if (sc[q] > 0) { cnt++; sum += (sc[q] - 1) / 254; if (cls[q] < 3) ok = true; }
    }
    if (cnt && ok && sf / (b * b) >= PICK.seen_min) cand.push([sum / cnt, i, j]);
  }
  cand.sort((p, q) => q[0] - p[0] || q[1] - p[1] || q[2] - p[2]);
  const picks = [];
  for (const [m, i, j] of cand) {
    const cy = (i + 0.5) * b, cx = (j + 0.5) * b;
    if (picks.some((p) => Math.hypot(cy - p.c[0], cx - p.c[1]) * res < PICK.min_sep_m)) continue;
    let best = -1, br = 0, bc = 0;
    for (let r = i * b; r < (i + 1) * b; r++) for (let c = j * b; c < (j + 1) * b; c++) {
      const q = r * W + c, v = sc[q] > 0 && cls[q] < 3 ? sc[q] : -1;
      if (v > best) { best = v; br = r; bc = c; }
    }
    const x = a[0] + (bc + 0.5) * res, y = a[3] - (br + 0.5) * res;
    const x0 = a[0] + j * PICK.block_m, x1 = x0 + PICK.block_m, y1 = a[3] - i * PICK.block_m, y0 = y1 - PICK.block_m;
    picks.push({ c: [cy, cx], id: `T${picks.length + 1}`, score: Math.round(m * 1e4) / 1e4, xy: [x, y], stop: toLL(x, y),
      block: [toLL(x0, y1), toLL(x1, y1), toLL(x1, y0), toLL(x0, y0), toLL(x0, y1)] });
    if (picks.length === PICK.n) break;
  }
  return picks;
}

// ---------------------------------------------------------------------------------------------- ③ 3D walk
// Hands the current route (habitat or moved start) to arcadia3d.html (teammate Shooyunn's first-person walk page)
// in his localStorage format: coords [[lon, lat]...], levels per segment (class at the segment midpoint), waypoints.
const LEVEL = ['low', 'medium', 'high', 'blocked'];
async function classGrid() {
  if (S.cls) return S.cls;
  const im = new Image(); im.src = D + S.d.files.classes; await im.decode();
  const c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
  const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0);
  const px = x.getImageData(0, 0, c.width, c.height).data, rgb = S.d.classes.map((k) => [1, 3, 5].map((j) => parseInt(k.color.slice(j, j + 2), 16)));
  const g = new Uint8Array(c.width * c.height);
  for (let i = 0; i < g.length; i++) {
    let b = 0, bd = Infinity;
    rgb.forEach((v, k) => { const dd = (v[0] - px[4 * i]) ** 2 + (v[1] - px[4 * i + 1]) ** 2 + (v[2] - px[4 * i + 2]) ** 2; if (dd < bd) { bd = dd; b = k; } });
    g[i] = b;
  }
  S.cls = { g, W: c.width, H: c.height };
  return S.cls;
}
function levelAt(ll) {
  const a = S.d.aoi_local_m, G = S.cls, [x, y] = toXY(ll);
  const r = Math.min(G.H - 1, Math.max(0, Math.floor((a[3] - y) / (a[3] - a[1]) * G.H))), c = Math.min(G.W - 1, Math.max(0, Math.floor((x - a[0]) / (a[2] - a[0]) * G.W)));
  return LEVEL[G.g[r * G.W + c]];
}
// Route vertices plus the card's Pandolf numbers accumulated along them (same plan, same legs, same total):
// each leg's walking minutes / kcal are spread over its steps by the 8 m grid's per-metre minutes / kcal, the 18 min
// dwell is added at the stop (arrival value tA/kA vs departure value tD/kD), then everything is scaled so the last
// vertex equals S.plan.total exactly. d in m, t in min, k in kcal.
function routeCum() {
  const P = S.d.planner, C = S.cost, legs = S.plan.legs, coords = [];
  if (!legs.length) return { coords, cum: null, total: S.plan.total, kcal_per_l_o2: P.kcal_per_l_o2 };
  const c = { d: [], tA: [], tD: [], kA: [], kD: [] };
  const per = (ll) => { const [x, y] = toXY(ll), i = xyToIdx(x, y); return i < 0 ? [NaN, NaN] : [C.K[i], C.T[i]]; };
  const push = (p, d, t, k) => { coords.push(p); c.d.push(d); c.tA.push(t); c.tD.push(t); c.kA.push(k); c.kD.push(k); };
  let D0 = 0, T0 = 0, K0 = 0;
  legs.forEach((L, li) => {
    const dwm = li < legs.length - 1 ? P.dwell_min : 0, dwk = dwm * P.stand_kcal_per_min;
    const steps = L.path.slice(1).map((b, q) => {
      const a = L.path[q], [ax, ay] = toXY(a), [bx, by] = toXY(b), len = Math.hypot(bx - ax, by - ay), pa = per(a), pb = per(b);
      const wk = 0.5 * (pa[0] + pb[0]) * len, wt = 0.5 * (pa[1] + pb[1]) * len;
      return { len, wk: isFinite(wk) ? wk : len, wt: isFinite(wt) ? wt : len };
    });
    const sum = (f) => steps.reduce((s, x) => s + x[f], 0) || 1;
    const sl = sum('len'), sk = sum('wk'), st = sum('wt');
    const wMin = L.min - dwm, wKc = L.kcal - dwk;
    if (!coords.length) push(L.path[0], 0, 0, 0);
    let d = 0, t = 0, k = 0;
    steps.forEach((s, q) => {
      d += s.len / sl * L.distance_m; t += s.wt / st * wMin; k += s.wk / sk * wKc;
      const p = L.path[q + 1], last = coords[coords.length - 1];
      if (last[0] === p[0] && last[1] === p[1]) { const j = coords.length - 1; c.d[j] = D0 + d; c.tA[j] = c.tD[j] = T0 + t; c.kA[j] = c.kD[j] = K0 + k; }
      else push(p, D0 + d, T0 + t, K0 + k);
    });
    D0 += L.distance_m; T0 += L.min; K0 += L.kcal;
    const j = coords.length - 1; c.tD[j] = T0; c.kD[j] = K0;
  });
  const n = coords.length - 1, tot = S.plan.total;
  const sc = (arr, v) => { const f = arr[n] ? v / arr[n] : 1; return arr.map((x) => x * f); };
  const ft = c.tA[n] ? tot.min / c.tA[n] : 1, fk = c.kA[n] ? tot.kcal / c.kA[n] : 1, mul = (arr, f) => arr.map((x) => x * f);
  const cum = { d: sc(c.d, tot.distance_m), tA: mul(c.tA, ft), tD: mul(c.tD, ft), kA: mul(c.kA, fk), kD: mul(c.kD, fk) };
  return { coords, cum, total: { distance_m: tot.distance_m, min: tot.min, kcal: tot.kcal, o2_l: tot.kcal / P.kcal_per_l_o2 }, kcal_per_l_o2: P.kcal_per_l_o2 };
}

async function open3d() {
  await classGrid();
  const { coords, cum, total, kcal_per_l_o2 } = routeCum();
  const levels = coords.slice(0, -1).map((p, i) => levelAt([(p[0] + coords[i + 1][0]) / 2, (p[1] + coords[i + 1][1]) / 2]));
  const waypoints = S.plan.legs.slice(0, -1).map((L, i) => {
    const t = tgs().find((x) => x.id === L.to);
    return { n: `Stop ${i + 1} ${t.id}`, coords: t.stop, cls: levelAt(t.stop) };
  });
  localStorage.setItem('marswalker-arcadia-route', JSON.stringify({ coords, levels, waypoints, cum, total, kcal_per_l_o2, created: Date.now() }));
  $('#w3d').hidden = false;
  $('#w3dFrame').src = `arcadia3d.html?route=${Date.now()}`;
}

init();
