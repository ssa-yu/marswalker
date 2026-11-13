/* Marswalk Recon — Step 3 skeleton: astronaut walk planner. Plain JS, no build step.
   Data: data/jezero/astronaut/astronaut.json + class_prior_4m.png (prior terrain classes on a 4 m grid).
   The planner is a port of pipeline/astro_plan.py: least-oxygen paths (Dijkstra, 8-connected, a step costs the
   mean of the two cells' per-metre oxygen times the step length), then the stop order that visits the most stops
   and uses the least oxygen while always keeping enough oxygen to walk home. Planned values only, on the prior. */
'use strict';
const R_MARS = 3396190, DEG = Math.PI / 180;
const SCENE = 'jezero', BASE = `data/${SCENE}/`, AB = BASE + 'astronaut/';
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const abs = (u) => new URL(u, location.href).href;
const f0 = (v) => Math.round(v).toLocaleString('en-US');
const fmtMin = (m) => { const h = Math.floor(m / 60), r = Math.round(m - 60 * h); return h ? `${h} h ${String(r).padStart(2, '0')} min` : `${r} min`; };
const S = { t: 0, playing: false, include: null, plan: null };

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); }

/* ---------------- planner ---------------- */
class Heap { // binary min-heap of (key, value)
  constructor() { this.k = []; this.v = []; }
  push(key, val) { const k = this.k, v = this.v; let i = k.length; k.push(key); v.push(val);
    while (i > 0) { const p = (i - 1) >> 1; if (k[p] <= key) break; k[i] = k[p]; v[i] = v[p]; i = p; } k[i] = key; v[i] = val; }
  pop() { const k = this.k, v = this.v, top = v[0], topk = k[0], lk = k.pop(), lv = v.pop(); const n = k.length;
    if (n) { let i = 0; for (;;) { let c = 2 * i + 1; if (c >= n) break; if (c + 1 < n && k[c + 1] < k[c]) c++; if (k[c] >= lk) break; k[i] = k[c]; v[i] = v[c]; i = c; } k[i] = lk; v[i] = lv; }
    this.lastKey = topk; return top; }
  get size() { return this.k.length; }
}
const NB = [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]];
function dijkstra(src) {
  const { W, H, o2m, res } = S.g, n = W * H, dist = new Float64Array(n).fill(Infinity), prev = new Int32Array(n).fill(-1);
  const h = new Heap(); dist[src] = 0; h.push(0, src);
  while (h.size) {
    const u = h.pop(), du = h.lastKey; if (du > dist[u]) continue;
    const r = (u / W) | 0, c = u - r * W, cu = o2m[u];
    for (const [dr, dc] of NB) {
      const rr = r + dr, cc = c + dc; if (rr < 0 || rr >= H || cc < 0 || cc >= W) continue;
      const v = rr * W + cc, cv = o2m[v]; if (!isFinite(cv)) continue;
      const nd = du + 0.5 * (cu + cv) * res * (dr && dc ? Math.SQRT2 : 1);
      if (nd < dist[v]) { dist[v] = nd; prev[v] = u; h.push(nd, v); }
    }
  }
  return { dist, prev };
}
function legPath(a, b) { // stop index a -> stop index b, using the field rooted at a
  const p = [], pr = S.fields[a].prev; let v = S.pts[b];
  while (v !== -1) { p.push(v); if (v === S.pts[a]) break; v = pr[v]; }
  return p.reverse();
}
function permutations(arr) { if (arr.length <= 1) return [arr.slice()]; const out = []; arr.forEach((x, i) => { for (const p of permutations([...arr.slice(0, i), ...arr.slice(i + 1)])) out.push([x, ...p]); }); return out; }
function combinations(arr, k) { if (k === 0) return [[]]; if (arr.length < k) return []; const [h, ...t] = arr; return [...combinations(t, k - 1).map((c) => [h, ...c]), ...combinations(t, k)]; }
function lexLess(a, b) { for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] < b[i]; return a.length < b.length; }

function planTour(cap, reserve, include) {
  const D = S.D, U = cap * (1 - reserve), ids = include.map((on, j) => on ? j : -1).filter((j) => j >= 0);
  const tourCost = (order) => { let used = 0, cur = 0; for (const j of order) { used += D[cur][j + 1]; if (!isFinite(used) || used + D[j + 1][0] > U + 1e-9) return Infinity; cur = j + 1; } return used + D[cur][0]; };
  let best = [], bestC = 0;
  for (let k = ids.length; k > 0; k--) {
    let found = null, fc = Infinity;
    for (const s of combinations(ids, k)) for (const o of permutations(s)) { const c = tourCost(o); if (c < fc - 1e-12 || (Math.abs(c - fc) <= 1e-12 && found && lexLess(o, found))) { fc = c; found = o; } }
    if (found && isFinite(fc)) { best = found; bestC = fc; break; }
  }
  const stops = [0, ...best.map((j) => j + 1), 0];
  let path = [S.pts[0]]; const legEnds = [];
  for (let i = 0; i + 1 < stops.length; i++) { if (stops[i] === stops[i + 1]) continue; path = path.concat(legPath(stops[i], stops[i + 1]).slice(1)); legEnds.push(path.length - 1); }
  const { W, o2m, tm, res } = S.g, home = S.fields[0].dist;
  const T = [0], O = [0], Dm = [0], Hm = [home[path[0]]];
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1], b = path[i], diag = ((a / W) | 0) !== ((b / W) | 0) && (a % W) !== (b % W), L = res * (diag ? Math.SQRT2 : 1);
    T.push(T[i - 1] + 0.5 * (tm[a] + tm[b]) * L); O.push(O[i - 1] + 0.5 * (o2m[a] + o2m[b]) * L); Dm.push(Dm[i - 1] + L); Hm.push(home[b]);
  }
  const M = O.map((o, i) => U - o - Hm[i]);
  const skipped = ids.filter((j) => !best.includes(j));
  return { U, cap, reserve, order: best, skipped, excluded: include.map((on, j) => on ? -1 : j).filter((j) => j >= 0), path, legEnds, T, O, Dm, Hm, M,
    o2: O[O.length - 1], time: T[T.length - 1], dist: Dm[Dm.length - 1], minMargin: Math.min(...M), tourC: bestC };
}

/* ---------------- geometry ---------------- */
function rcToXY(i) { const { W, res, ext } = S.g, r = (i / W) | 0, c = i - r * W; return [ext[0] + (c + 0.5) * res, ext[3] - (r + 0.5) * res]; }
function xyToLL(x, y) { const b = S.A.base; return [b.lon + (x / b.k_coslat) / R_MARS / DEG, b.lat + y / R_MARS / DEG]; }
function idxLL(i) { return xyToLL(...rcToXY(i)); }

/* ---------------- init ---------------- */
async function init() {
  const [A, sc] = await Promise.all([getJSON(AB + 'astronaut.json'), getJSON(BASE + 'scene.json')]);
  S.A = A; S.sc = sc;
  const img = await createImageBitmap(await (await fetch(AB + A.grid.class_png)).blob(), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
  const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height;
  const cx = cv.getContext('2d', { willReadFrequently: true }); cx.drawImage(img, 0, 0);
  const px = cx.getImageData(0, 0, img.width, img.height).data;
  const W = img.width, H = img.height, cls = new Uint8Array(W * H);
  for (let i = 0; i < W * H; i++) cls[i] = px[4 * i];
  const pm = A.per_metre, o2m = new Float64Array(W * H), tm = new Float64Array(W * H);
  for (let i = 0; i < W * H; i++) { const k = cls[i]; o2m[i] = k < 3 ? pm.o2_nominal_min[k] : Infinity; tm[i] = k < 3 ? pm.time_min[k] : Infinity; }
  S.g = { W, H, cls, o2m, tm, res: A.grid.res_m, ext: A.grid.extent_local_m };
  S.pts = [A.base.rc, ...A.targets.map((t) => t.rc)].map(([r, c]) => r * W + c);
  const t0 = performance.now();
  S.fields = S.pts.map((p) => dijkstra(p));
  S.D = S.pts.map((_, a) => S.pts.map((p) => S.fields[a].dist[p]));
  S.planMs = performance.now() - t0;
  S.include = A.targets.map(() => true);
  drawClassCanvas();
  buildMap();
  const P = A.params;
  $('#cap').value = P.o2_capacity_nominal_min; $('#res').value = Math.round(P.reserve_frac * 100);
  $('#cap').oninput = $('#res').oninput = () => replan();
  $('#scrub').oninput = () => { stop(); setT(+$('#scrub').value / 1000 * S.plan.time); };
  $('#play').onclick = () => (S.playing ? stop() : play());
  $('#showClasses').onchange = () => S.map.setLayoutProperty('classes', 'visibility', $('#showClasses').checked ? 'visible' : 'none');
  $('#aboutBtn').onclick = () => { renderAbout(); $('#about').showModal(); };
  $('#targetRule').textContent = 'Rule (fixed before running): ' + A.target_rule;
  replan();
  parityCheck();
}

function parityCheck() {
  const P = S.A.params, p = planTour(P.o2_capacity_nominal_min, P.reserve_frac, S.A.targets.map(() => true)), r = S.A.reference_plan_python;
  const d = Math.abs(p.o2 - r.o2_total), same = JSON.stringify(p.order) === JSON.stringify(r.order);
  S.parity = { js_o2: p.o2, py_o2: r.o2_total, diff: d, sameOrder: same };
  $('#parity').innerHTML = `Browser planner vs pipeline (<code>astro_plan.py</code>) at the default budget: oxygen ${p.o2.toFixed(2)} vs ${r.o2_total.toFixed(2)} min, stop order ${same ? 'identical' : 'DIFFERENT'} <span class="${d < 0.05 && same ? 'pass' : 'fail'}">${d < 0.05 && same ? 'match' : 'mismatch'}</span>. Paths computed in ${S.planMs.toFixed(0)} ms.`;
}

function drawClassCanvas() {
  const { W, H, cls } = S.g, c = $('#classCanvas'); c.width = W; c.height = H;
  const x = c.getContext('2d'), im = x.createImageData(W, H);
  const col = [null, [244, 183, 64, 150], [255, 90, 78, 160], [138, 63, 174, 220]];
  for (let i = 0; i < W * H; i++) { const k = col[cls[i]]; if (!k) continue; im.data.set(k, 4 * i); }
  x.putImageData(im, 0, 0);
}

function aoiCorners() { const e = S.g.ext; return [xyToLL(e[0], e[3]), xyToLL(e[2], e[3]), xyToLL(e[2], e[1]), xyToLL(e[0], e[1])]; }
function fc(f) { return { type: 'FeatureCollection', features: f }; }

function buildMap() {
  const c = aoiCorners(), sc = S.sc;
  const map = new maplibregl.Map({
    container: 'map', bounds: [[c[0][0], c[2][1]], [c[1][0], c[0][1]]], fitBoundsOptions: { padding: { top: 30, bottom: 30, left: 300, right: 30 } },
    maxZoom: 19, minZoom: 9, renderWorldCopies: false, dragRotate: false, pitchWithRotate: false,
    style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0d0b0a' } }] },
    attributionControl: { compact: true, customAttribution: 'NASA/JPL-Caltech/MSSS (CTX), USGS Astrogeology. Walk: planned (derived).' },
  });
  S.map = map; window.__mapIdle = false;
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.on('load', () => {
    const ctx = sc.layers.find((l) => l.id === 'ctx_ortho');
    map.addSource('ctx', { type: 'image', url: abs(BASE + ctx.url), coordinates: ctx.coordinates });
    map.addLayer({ id: 'ctx', type: 'raster', source: 'ctx', paint: { 'raster-fade-duration': 0, 'raster-brightness-max': 0.8, 'raster-saturation': -0.3 } });
    map.addSource('classes', { type: 'canvas', canvas: 'classCanvas', coordinates: c, animate: false });
    map.addLayer({ id: 'classes', type: 'raster', source: 'classes', paint: { 'raster-opacity': 0.75, 'raster-fade-duration': 0, 'raster-resampling': 'nearest' } });
    map.addSource('aoi', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [...c, c[0]] } } });
    map.addLayer({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.2, 'line-dasharray': [3, 2] } });
    map.addSource('route', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'route-case', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 5, 'line-opacity': 0.6 } });
    map.addLayer({ id: 'route-todo', type: 'line', source: 'route', filter: ['!', ['get', 'done']], layout: { 'line-join': 'round' },
      paint: { 'line-color': '#43b0f1', 'line-width': 2, 'line-opacity': 0.8, 'line-dasharray': [2, 1.5] } });
    map.addLayer({ id: 'route', type: 'line', source: 'route', filter: ['get', 'done'], layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#43b0f1', 'line-width': 3.2 } });
    map.addSource('pts', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'pts', type: 'circle', source: 'pts', paint: {
      'circle-radius': ['case', ['==', ['get', 'kind'], 'base'], 8, 7], 'circle-stroke-width': 2.5, 'circle-stroke-color': '#000',
      'circle-color': ['match', ['get', 'state'], 'base', '#f2b36b', 'visit', '#6cc28a', 'skip', '#e0625a', '#777'] } });
    S.marker = new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'astro-marker', title: 'Astronaut (planned position)' }) }).setLngLat(idxLL(S.pts[0])).addTo(map);
    map.once('idle', () => { window.__mapIdle = true; });
    drawRoute(); drawPoints(); updateScale();
  });
  map.on('move', updateScale);
  map.on('mousemove', (e) => showCoords(e.lngLat));
}

/* ---------------- plan / UI ---------------- */
function replan() {
  stop();
  const cap = +$('#cap').value, reserve = +$('#res').value / 100;
  $('#capLbl').textContent = `${cap} min`; $('#resLbl').textContent = `${Math.round(reserve * 100)}%`;
  $('#usableLbl').textContent = f0(cap * (1 - reserve));
  S.plan = planTour(cap, reserve, S.include);
  renderTargets(); renderSummary(); drawPoints(); setT(0);
}

function renderTargets() {
  const p = S.plan, A = S.A;
  $('#targets').innerHTML = A.targets.map((t, j) => {
    const vi = p.order.indexOf(j), on = S.include[j];
    const st = !on ? '<span class="st">left out by you</span>' : vi >= 0 ? `<span class="st ok">stop ${vi + 1} of ${p.order.length}</span>`
      : `<span class="st skip">skipped: ${isFinite(S.D[0][j + 1]) ? 'not enough oxygen to reach it and still get home' : 'no passable path on the prior'}</span>`;
    return `<label class="tgt"><input type="checkbox" data-j="${j}" ${on ? 'checked' : ''}><span class="id">${esc(t.id)}</span><span class="muted">x ${f0(t.xy_m[0])} m, y ${f0(t.xy_m[1])} m · ${esc(t.label)}</span>${st}</label>`;
  }).join('');
  document.querySelectorAll('#targets input').forEach((el) => el.onchange = () => { S.include[+el.dataset.j] = el.checked; replan(); });
}

function renderSummary() {
  const p = S.plan;
  const rows = [['Stops visited', `${p.order.length} of ${S.include.filter(Boolean).length}`], ['Distance', `${(p.dist / 1000).toFixed(2)} km`], ['Walking time', fmtMin(p.time)],
    ['Oxygen used', `${f0(p.o2)} of ${f0(p.U)} usable min`], ['Lowest return margin on the way', `${f0(p.minMargin)} min`],
    ['Reserve kept untouched', `${f0(p.cap * p.reserve)} min`]];
  $('#summary').innerHTML = `<div class="kv">${rows.map((r) => `<span>${esc(r[0])}</span><b>${esc(r[1])}</b>`).join('')}</div>
    <p class="hint">Planned on the orbital prior (CTX 20 m), before any recon. Not checked against the HiRISE reference terrain on this page; walks planned from recon data are compared later, once terrain classes are locked.</p>`;
}

function drawRoute() {
  if (!S.map || !S.map.getSource('route') || !S.plan) return;
  const p = S.plan, i = idxAt(S.t);
  const ll = p.path.map(idxLL);
  const done = ll.slice(0, i + 1), rest = ll.slice(i);
  S.map.getSource('route').setData(fc([
    ...(rest.length > 1 ? [{ type: 'Feature', properties: { done: false }, geometry: { type: 'LineString', coordinates: rest } }] : []),
    ...(done.length > 1 ? [{ type: 'Feature', properties: { done: true }, geometry: { type: 'LineString', coordinates: done } }] : [])]));
}


function drawPoints() {
  if (!S.map || !S.map.getSource('pts') || !S.plan) return;
  const p = S.plan;
  const pts = [{ type: 'Feature', properties: { kind: 'base', state: 'base', label: 'Habitat' }, geometry: { type: 'Point', coordinates: idxLL(S.pts[0]) } }];
  S.A.targets.forEach((t, j) => {
    const vi = p.order.indexOf(j), state = !S.include[j] ? 'off' : vi >= 0 ? 'visit' : 'skip';
    pts.push({ type: 'Feature', properties: { kind: 'target', state, label: `${t.id}${vi >= 0 ? ' · stop ' + (vi + 1) : state === 'skip' ? ' · skipped' : ''} (placeholder)` }, geometry: { type: 'Point', coordinates: idxLL(S.pts[j + 1]) } });
  });
  S.map.getSource('pts').setData(fc(pts));
  (S.lbls || []).forEach((m) => m.remove());
  S.lbls = pts.map((f) => new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'pt-lbl', textContent: f.properties.label }), anchor: 'top', offset: [0, 10] }).setLngLat(f.geometry.coordinates).addTo(S.map));
}

function idxAt(t) { const T = S.plan.T; let lo = 0, hi = T.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (T[m] <= t) lo = m; else hi = m - 1; } return lo; }

function setT(t) {
  const p = S.plan; S.t = Math.max(0, Math.min(t, p.time));
  const i = idxAt(S.t);
  $('#scrub').value = p.time ? Math.round(S.t / p.time * 1000) : 0;
  $('#tLbl').textContent = `${f0(S.t)} of ${f0(p.time)}`;
  const o2Left = p.cap - p.O[i], margin = p.M[i];
  $('#o2Val').textContent = `${f0(o2Left)} / ${f0(p.cap)} min`;
  const ob = $('#o2Bar'); ob.querySelector('.fill').style.width = `${Math.max(0, o2Left / p.cap * 100)}%`; ob.querySelector('.res').style.width = `${p.reserve * 100}%`;
  ob.classList.toggle('low', o2Left - p.cap * p.reserve < p.U * S.A.ui.margin_warn_frac);
  $('#mgVal').textContent = `${f0(margin)} min`;
  const mb = $('#mgBar'), warn = margin < p.U * S.A.ui.margin_warn_frac;
  mb.querySelector('.fill').style.width = `${Math.max(0, margin / p.U * 100)}%`; mb.classList.toggle('crit', warn);
  $('#warn').hidden = !warn || i === p.path.length - 1;
  $('#tdVal').textContent = `${fmtMin(p.T[i])} · ${(p.Dm[i] / 1000).toFixed(2)} km`;
  $('#homeVal').textContent = `${f0(p.Hm[i])} min`;
  if (S.marker) S.marker.setLngLat(idxLL(p.path[i]));
  drawRoute();
}

function play() {
  if (S.t >= S.plan.time) setT(0);
  S.playing = true; $('#play').textContent = '❚❚ Pause';
  let last = performance.now();
  const step = (now) => { if (!S.playing) return; const dt = (now - last) / 1000; last = now; setT(S.t + dt * +$('#speed').value); if (S.t >= S.plan.time) { stop(); return; } requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
function stop() { S.playing = false; $('#play').textContent = '▶ Play'; }

function marsDist(a, b) { const dlat = (b.lat - a.lat) * DEG, dlon = (b.lng - a.lng) * DEG; const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * DEG) * Math.cos(b.lat * DEG) * Math.sin(dlon / 2) ** 2; return 2 * R_MARS * Math.asin(Math.sqrt(h)); }
function updateScale() {
  const m = S.map, H = m.getContainer().clientHeight, maxPx = 120, a = m.unproject([20, H - 40]), b = m.unproject([20 + maxPx, H - 40]);
  const d = marsDist(a, b), pow = 10 ** Math.floor(Math.log10(d)), n = d / pow, nice = (n >= 5 ? 5 : n >= 2 ? 2 : 1) * pow;
  $('#scaleBar').style.width = (maxPx * nice / d) + 'px'; $('#scaleLabel').textContent = (nice >= 1000 ? nice / 1000 + ' km' : nice + ' m') + ' (Mars)';
}
function showCoords(ll) {
  const b = S.A.base, x = (ll.lng - b.lon) * DEG * R_MARS * b.k_coslat, y = (ll.lat - b.lat) * DEG * R_MARS;
  $('#coords').innerHTML = `${ll.lat.toFixed(5)}°N ${ll.lng.toFixed(5)}°E<br>x ${x.toFixed(0)} m E, y ${y.toFixed(0)} m N of base`;
}

function renderAbout() {
  const P = S.A.params, pm = S.A.per_metre;
  $('#aboutBody').innerHTML = `<h2>Step 3 · Astronaut walk planner (skeleton)</h2>
<p><b>This page is a skeleton.</b> The stops are placeholders: where it is worth sending the astronaut is step 2, which is not decided yet. The walk is planned on the orbital prior only (CTX 20 m terrain model, before any recon). It is not checked against the HiRISE reference terrain here, and no "before vs after recon" comparison is shown.</p>
<h3>Model</h3>
<ul><li>Walking speed ${P.speed_kmh} km/h on firm ground; speed factor firm / rough / sand = ${P.speed_factor.firm} / ${P.speed_factor.rough} / ${P.speed_factor.sand}. Slopes ≥ 25° are blocked.</li>
<li>Oxygen is counted in <i>nominal minutes</i>: one minute of walking on firm ground uses 1. Oxygen-use factor firm / rough / sand = ${P.o2_factor.firm} / ${P.o2_factor.rough} / ${P.o2_factor.sand}. Per metre: ${pm.o2_nominal_min.map((v) => v.toFixed(4)).join(' / ')} nominal min.</li>
<li>Suit oxygen ${P.o2_capacity_nominal_min} nominal minutes, ${Math.round(P.reserve_frac * 100)}% kept as an emergency reserve (sliders change both).</li>
<li><b>Return margin</b> = oxygen still usable − oxygen needed to walk home from here on the cheapest route. The planner only accepts stop orders that keep this at or above zero all the way.</li>
<li>Paths: least oxygen on a 4 m grid (each 4 m cell takes the most costly 2 m class inside it). Stop order: visits the most stops, then uses the least oxygen.</li></ul>
<h3>Labels</h3><p><span class="badge derived">derived</span> planned time, distance, oxygen and margin · <span class="badge assumed">assumed</span> speed, factors, suit oxygen, reserve (locked by the team, sources being checked by teammates) · <span class="badge placeholder">placeholder</span> stops.</p>
<h3>Limitations</h3><ul><li>No physiological values: only oxygen, time, distance and return margin, all from the parameters above.</li>
<li>Oxygen factors are assumptions from the team's earlier prototype; their original sources are still being checked.</li>
<li>The prior has no sand class yet (the terrain classes are being reviewed).</li></ul>`;
}

init().catch((e) => { document.body.insertAdjacentHTML('afterbegin', `<pre style="color:#f88;padding:12px">Failed to load: ${esc(e.message)}</pre>`); console.error(e); });
