// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Arcadia brain-terrain demo: ① rover recon → ② brain heat map and chosen areas → ③ astronaut route.
   Data: data/arcadia/arcadia.json + images (pipeline/arcadia_export.py). Plain JS, no build step.
   ③: click the map to move the astronaut's start; the multi-stop plan is recomputed in the browser on the 8 m
   per-metre kcal / minute grid (cost8.bin.gz, Shooyunn's Pandolf model) with the same order rule as Python. */
'use strict';
const D = 'data/arcadia/';
const $ = (s) => document.querySelector(s);
const abs = (u) => new URL(u, location.href).href;
const S = { step: 1, loop: 10, markers: [], start: null, plan: null };
const C_ROVER = '#3987e5', C_ROVER_NOW = '#f2b36b', C_ROUTE = '#38e1ff', C_TGT = '#ffd23f';

async function init() {
  S.d = await (await fetch(D + 'arcadia.json')).json();
  S.ctx = await fetch(D + 'context.json').then((r) => (r.ok ? r.json() : null)).catch(() => null);
  const im = new Image(); im.src = D + S.d.files.seen_loop; await im.decode();
  const c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
  const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0);
  const px = x.getImageData(0, 0, c.width, c.height).data;
  S.seenLoop = new Uint8Array(c.width * c.height);
  for (let i = 0; i < S.seenLoop.length; i++) S.seenLoop[i] = px[4 * i];
  const v = $('#veil'); v.width = c.width; v.height = c.height; S.veilCtx = v.getContext('2d'); S.veilImg = S.veilCtx.createImageData(c.width, c.height);
  S.cost = await loadCost(S.d);
  const N = S.d.rover.loops.length;
  $('#loop').max = N; $('#loop').value = N; $('#loopMax').textContent = N; S.loop = N;
  buildMap();
}

function buildMap() {
  const d = S.d, c = d.aoi_corners;
  // outer extent the user can pan/zoom out to: the Mars Trek context image (else the HiRISE strip, else the AOI)
  const outer = S.ctx ? (S.ctx.trek || S.ctx.strip).coordinates : c;
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
    // context basemaps under the study area (display only): Mars Trek THEMIS Day IR, then the whole HiRISE strip at 3 m
    if (S.ctx && S.ctx.trek) {
      map.addSource('trek', { type: 'image', url: abs(D + S.ctx.trek.file), coordinates: S.ctx.trek.coordinates });
      map.addLayer({ id: 'trek', type: 'raster', source: 'trek', paint: { 'raster-fade-duration': 0, 'raster-brightness-max': 0.8 } });
    }
    if (S.ctx && S.ctx.strip) {
      map.addSource('strip', { type: 'image', url: abs(D + S.ctx.strip.file), coordinates: S.ctx.strip.coordinates });
      map.addLayer({ id: 'strip', type: 'raster', source: 'strip', paint: { 'raster-fade-duration': 0 } });
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
    map.addLayer({ id: 'tgt', type: 'line', source: 'tgt', filter: ['==', ['get', 'reach'], true], paint: { 'line-color': C_TGT, 'line-width': 2.5 } });
    map.addLayer({ id: 'tgt-far', type: 'line', source: 'tgt', filter: ['!=', ['get', 'reach'], true], paint: { 'line-color': C_TGT, 'line-width': 2, 'line-dasharray': [2, 1.5] } });
    map.addSource('route', { type: 'geojson', data: gj([]) });
    map.addLayer({ id: 'route-casing', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 6, 'line-opacity': 0.6 } });
    map.addLayer({ id: 'route', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': C_ROUTE, 'line-width': 3 } });
    map.on('click', onMapClick);
    map.on('mouseenter', 'route', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'route', () => { map.getCanvas().style.cursor = ''; });
    wire();
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
}

function setStep(n) {
  S.step = n;
  $('#lyrCls').checked = false;
  $('#lyrHeat').checked = n === 2;
  if (n === 1) { S.loop = S.d.rover.loops.length; $('#loop').value = S.loop; }
  $('#card').hidden = true;
  apply();
  frame();
}

function frame() {
  const d = S.d, c = d.aoi_corners;
  let pts = [c[0], c[2]];
  if (S.step === 2) pts = d.rover.loops.flatMap((L) => L.path);
  if (S.step === 3) pts = S.plan.legs.flatMap((L) => L.path);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  S.map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: { top: 170, bottom: 120, left: 80, right: 80 }, duration: 0, maxZoom: 17 });
}

function drawVeil(k, alpha) {
  const px = S.veilImg.data, sl = S.seenLoop;
  for (let i = 0; i < sl.length; i++) {
    const seen = sl[i] > 0 && sl[i] <= k;
    px[4 * i] = 0; px[4 * i + 1] = 0; px[4 * i + 2] = 0; px[4 * i + 3] = seen ? 0 : alpha;
  }
  S.veilCtx.putImageData(S.veilImg, 0, 0);
  const src = S.map.getSource('veil'); if (src) { src.play(); src.pause(); }
}

function vis(id, on) { S.map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); }

function apply() {
  const d = S.d, m = S.map, n = S.step;
  document.querySelectorAll('.steps .btn').forEach((b) => b.classList.toggle('active', +b.dataset.step === n));
  $('#ctl1').hidden = n !== 1; $('#ctl3').hidden = n !== 3 || !S.start;
  const heat = $('#lyrHeat').checked;
  vis('ortho', $('#lyrImg').checked);
  if (m.getLayer('strip')) vis('strip', $('#lyrImg').checked);
  vis('classes', $('#lyrCls').checked);
  vis('brain_all', heat);
  // unexplored mask: ground the rover has not seen yet (up to the slider's loop in ①, all loops in ② and ③), black at 50 %
  const k = n === 1 ? S.loop : d.rover.loops.length;
  const maskOn = $('#lyrMask').checked;
  if (maskOn) drawVeil(k, 128);
  vis('veil', maskOn);
  vis('rover', n <= 2); vis('rover-casing', n === 1);
  m.setFilter('rover', ['<=', ['get', 'id'], k]);
  m.setFilter('rover-casing', ['<=', ['get', 'id'], k]);
  m.setPaintProperty('rover', 'line-color', n === 1 ? ['case', ['==', ['get', 'id'], k], C_ROVER_NOW, C_ROVER] : C_ROVER);
  m.setPaintProperty('rover', 'line-opacity', n === 1 ? 1 : 0.45);
  m.setPaintProperty('rover', 'line-width', n === 1 ? 2 : 1.2);
  vis('tgt', n >= 2); vis('tgt-hit', n === 3); vis('tgt-far', n === 3);
  S.map.setFilter('tgt', n === 3 ? ['==', ['get', 'reach'], true] : null);
  vis('route', n === 3); vis('route-casing', n === 3);
  $('#loopLbl').textContent = k;
  if (n === 1) {
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
  mk(d.base, 'base', '基地');
  if (n === 3 && S.start) mk(S.start.ll, 'start', '太空人出發點');
  if (n === 2) {
    d.targets.after.forEach((t) => mk(t.stop, 'tgt', `${t.id} ${t.score.toFixed(2)}`));
  }
  if (n === 3) {
    S.plan.legs.forEach((L, i) => {
      if (i === S.plan.legs.length - 1) return;
      const t = d.targets.after.find((x) => x.id === L.to);
      mk(t.stop, 'stop', `${i + 1}`, () => stopCard(i));
    });
  }
}

function showCard(title, v) {
  const h = Math.floor(v.min / 60), mi = Math.round(v.min % 60);
  $('#card').innerHTML = `<h4><span>${title}</span><button aria-label="關閉" onclick="this.closest('#card').hidden=true">×</button></h4>
    <div class="kv"><span>距離</span><span>${(v.distance_m / 1000).toFixed(2)} km</span>
    <span>時間</span><span>${h ? h + ' 小時 ' : ''}${mi} 分</span>
    <span>耗能</span><span>${Math.round(v.kcal)} kcal</span>
    <span>氧氣</span><span>${Math.round(v.o2_l)} L</span></div>`;
  $('#card').hidden = false;
}

function legend() {
  const d = S.d, n = S.step, it = (sw, t) => `<div class="it">${sw}<span>${t}</span></div>`;
  let h = '';
  if ($('#lyrCls').checked) h += d.classes.map((c) => it(`<i style="background:${c.color}"></i>`, c.zh)).join('');
  if ($('#lyrHeat').checked) h += `<div class="it"><span>腦紋分數</span></div><div class="ramp"></div><div class="rl"><span>0</span><span>0.5</span><span>1</span></div>`;
  if ($('#lyrMask').checked) h += it('<i style="background:#000;opacity:.5"></i>', '未探索（自走車還沒看過）');
  if (n === 1) h += it(`<i class="ln" style="background:${C_ROVER}"></i>`, '自走車路徑') + it(`<i class="ln" style="background:${C_ROVER_NOW}"></i>`, '這一趟');
  if (n === 2) h += it(`<i style="border:2px solid ${C_TGT}"></i>`, `偵察後選的 ${d.targets.after.length} 區（60 m）`);
  if (n === 3) {
    const t = S.plan.total;
    h += it(`<i class="ln" style="background:${C_ROUTE}"></i>`, `太空人路線：${S.plan.n_stops} 站，${(t.distance_m / 1000).toFixed(2)} km，${Math.round(t.kcal)} kcal`);
  }
  h += it('<i class="pt" style="background:#fff"></i>', '基地');
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
  const tg = d.targets.after.map((t) => {
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
  const d = S.d;
  S.plan = p || pyPlan();
  const gj = (features) => ({ type: 'FeatureCollection', features });
  S.map.getSource('route').setData(gj(S.plan.legs.map((L, i) => ({ type: 'Feature', properties: { i }, geometry: { type: 'LineString', coordinates: L.path } }))));
  S.map.getSource('tgt').setData(gj(d.targets.after.map((t) => ({ type: 'Feature', properties: { id: t.id, reach: S.plan.visited.includes(t.id) || S.plan.rt[t.id] <= d.planner.usable_kcal }, geometry: { type: 'Polygon', coordinates: [t.block] } }))));
}

function stopCard(i) {
  const L = S.plan.legs[i], from = S.start ? '出發點' : '基地';
  showCard(`第 ${i + 1} 站（${L.to}）：從${from}到這裡，含停留`, { distance_m: L.cum.distance_m, min: L.cum.min, kcal: L.cum.kcal, o2_l: L.cum.kcal / S.d.planner.kcal_per_l_o2 });
}

function onMapClick(e) {
  if (S.step !== 3) return;
  const hit = S.map.queryRenderedFeatures(e.point, { layers: ['tgt-hit'] });
  if (hit.length) {
    const id = hit[0].properties.id, i = S.plan.legs.findIndex((L) => L.to === id);
    if (i >= 0) { stopCard(i); return; }
    const x = S.plan.rt[id], far = !(x <= S.d.planner.usable_kcal);
    $('#card').innerHTML = `<h4><span>${far ? '超出步行範圍：' : ''}往返需 ${isFinite(x) ? Math.round(x).toLocaleString('en-US') : '—'} kcal</span><button aria-label="關閉" onclick="this.closest('#card').hidden=true">×</button></h4>`;
    $('#card').hidden = false;
    return;
  }
  if (S.map.queryRenderedFeatures(e.point, { layers: ['route'] }).length) { showCard('整條路線', S.plan.total); return; }
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
  showCard('整條路線', S.plan.total);
}

init();
