/* Marswalk Recon — astronaut map: route A (orbital data only) vs route B (after the simulated rover recon),
   both walked on the HiRISE reference terrain. Plain JS, no build step.
   Data: data/jezero/compare/compare.json (definitions + summary tables) and compare/routes/t<i>.json (per test point:
   each route with cumulative distance, predicted and actual time / oxygen, oxygen needed to get home on the plan's map
   and on the reference terrain, hazard flag and reference class at every kept vertex). Nothing is recomputed here
   except the budget verdicts, which follow the oxygen sliders. Source: pipeline/compare_ab.py, export_compare.py. */
'use strict';
const R_MARS = 3396190, DEG = Math.PI / 180;
const SCENE = 'jezero', BASE = `data/${SCENE}/`, CB = BASE + 'compare/';
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const abs = (u) => new URL(u, location.href).href;
const f0 = (v) => v == null || !isFinite(v) ? '–' : Math.round(v).toLocaleString('en-US');
const f1 = (v) => v == null || !isFinite(v) ? '–' : (Math.round(v * 10) / 10).toLocaleString('en-US');
const sg = (v, f = f0) => (v > 0 ? '+' : v < 0 ? '−' : '') + f(Math.abs(v));
const fmtMin = (m) => { const h = Math.floor(m / 60), r = Math.round(m - 60 * h); return h ? `${h} h ${String(r).padStart(2, '0')} min` : `${r} min`; };
const COL = { A: '#ff9f43', B: '#43b0f1', 'A+': '#c38bff', REF: '#e9e4dc' };
const CLS = ['firm', 'rough', 'sand', 'blocked'];
const S = { k: 30, tgt: 0, route: 'A', t: 0, playing: false, cache: {} };

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); }
async function bitmap(u) { return createImageBitmap(await (await fetch(u)).blob(), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' }); }
const stateOf = (r) => (r === 'B' ? `B@${S.k}` : r);
const nameOf = (r) => ({ A: 'Route A · orbital data only', B: `Route B · after ${S.k} recon loop${S.k > 1 ? 's' : ''}`, 'A+': 'A+ · optimistic prior (bracket)', REF: 'Reference upper bound (not a recon result)' }[r]);
function usable() { return +$('#cap').value * (1 - +$('#res').value / 100); }

async function init() {
  const [C, sc, PW] = await Promise.all([getJSON(CB + 'compare.json'), getJSON(BASE + 'scene.json'), getJSON(CB + 'pointwise.json')]);
  S.C = C; S.sc = sc; S.PW = PW;
  S.ks = C.states.filter((s) => s.startsWith('B@')).map((s) => +s.slice(2));
  S.k = S.ks[S.ks.length - 1];
  // default test point: the lattice point at (600, 0) m (the step-3 skeleton's first placeholder rule), else the first
  S.tgt = Math.max(0, C.rows.findIndex((r) => r.x === 600 && r.y === 0));
  $('#tSel').innerHTML = C.rows.map((r, i) => `<option value="${i}">T${r.target} · x ${f0(r.x)} m, y ${f0(r.y)} m · ${r.band} m</option>`).join('');
  $('#kBtns').innerHTML = S.ks.map((k) => `<button class="btn sm" data-k="${k}">${k}</button>`).join('') + '<span class="muted">loops</span>';
  document.querySelectorAll('#kBtns button').forEach((b) => b.onclick = () => { S.k = +b.dataset.k; refresh(); });
  // U3: three example walks, chosen by a fixed rule on B@30 - A actual oxygen (spikes/u2_pointwise.py); default point unchanged
  const SC = PW.shortcuts_B30_actual_o2, idxOf = (t) => C.rows.findIndex((r) => r.target === t.target);
  $('#shortcuts').innerHTML = [['median', 'Median walk'], ['most_improved', 'Most improved'], ['most_worsened', 'Most worsened']]
    .map(([k, n]) => `<button class="btn sm" data-sc="${k}">${n} (${sg(SC[k].diff, f1)})</button>`).join('');
  document.querySelectorAll('#shortcuts button').forEach((b) => b.onclick = () => { S.k = 30; selectTarget(idxOf(SC[b.dataset.sc])); });
  $('#shortcutRule').textContent = 'Shortcuts are picked by the change in actual oxygen, route B after 30 loops minus route A, over all 63 test points: the point at the median, the largest drop and the largest rise. Values in nominal minutes.';
  $('#tSel').onchange = () => selectTarget(+$('#tSel').value);
  $('#tPrev').onclick = () => selectTarget((S.tgt - 1 + C.rows.length) % C.rows.length);
  $('#tNext').onclick = () => selectTarget((S.tgt + 1) % C.rows.length);
  $('#cap').oninput = $('#res').oninput = () => { renderCmp(); setT(S.t); };
  $('#showAp').onchange = $('#showRef').onchange = () => { renderRouteSel(); drawRoutes(); renderCmp(); };
  $('#rSel').onchange = () => { stop(); S.route = $('#rSel').value; setT(0); drawRoutes(); };
  $('#scrub').oninput = () => { stop(); setT(+$('#scrub').value / 1000 * cur().act_t.at(-1)); };
  $('#play').onclick = () => (S.playing ? stop() : play());
  $('#aboutBtn').onclick = () => { renderAbout(); $('#about').showModal(); };
  $('#tableBtn').onclick = () => { renderTable(); renderRobust(); $('#table').showModal(); };
  for (const [id, lay] of [['showCls', 'cls'], ['showHaz', 'haz'], ['showSeen', 'seen'], ['showHi', 'hfull']])
    $('#' + id).onchange = () => S.map.setLayoutProperty(lay, 'visibility', $('#' + id).checked ? 'visible' : 'none');
  const tImg = await bitmap(CB + C.files.reveal_t);
  const c = document.createElement('canvas'); c.width = tImg.width; c.height = tImg.height;
  const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(tImg, 0, 0);
  const d = x.getImageData(0, 0, c.width, c.height).data, n = c.width * c.height, tt = new Uint32Array(n);
  for (let i = 0; i < n; i++) tt[i] = (d[4 * i] << 16) | (d[4 * i + 1] << 8) | d[4 * i + 2];
  S.revealT = tt; S.tw = c.width; S.th = c.height;
  buildMap();
}

function cur() { return S.routes.states[stateOf(S.route)]; }
function row() { return S.C.rows[S.tgt]; }

async function selectTarget(i) {
  stop(); S.tgt = i; $('#tSel').value = i;
  const r = row();
  if (!S.cache[r.target]) S.cache[r.target] = await getJSON(`${CB}routes/t${r.target}.json`);
  S.routes = S.cache[r.target];
  $('#tInfo').textContent = `Straight-line distance ${f0(r.dist_m)} m from the habitat (${r.band} m band). Test points are a fixed 300 m grid, not science targets (step 2 is not decided).`;
  refresh();
}

function refresh() {
  document.querySelectorAll('#kBtns button').forEach((b) => b.classList.toggle('active', +b.dataset.k === S.k));
  const of = S.C.observed_frac[`B@${S.k}`];
  $('#kInfo').textContent = `After ${S.k} loop${S.k > 1 ? 's' : ''} the rover had seen ${(100 * of).toFixed(1)}% of the study area. Route B uses the reference terrain only where the rover saw it, orbital data elsewhere.`;
  renderRouteSel(); renderCmp(); renderOverall(); drawSeen(); drawRoutes(); drawTargets(); setT(0);
}

function renderRouteSel() {
  const opts = ['A', 'B', ...($('#showAp').checked ? ['A+'] : []), ...($('#showRef').checked ? ['REF'] : [])];
  if (!opts.includes(S.route)) S.route = 'A';
  $('#rSel').innerHTML = opts.map((o) => `<option value="${o}" ${o === S.route ? 'selected' : ''}>${esc(nameOf(o))}</option>`).join('');
}

function renderCmp() {
  const r = row(), U = usable(), cols = ['A', 'B', ...($('#showAp').checked ? ['A+'] : []), ...($('#showRef').checked ? ['REF'] : [])];
  $('#capLbl').textContent = `${$('#cap').value}`; $('#resLbl').textContent = `${$('#res').value}%`; $('#usableLbl').textContent = f0(U);
  const v = (c) => r[stateOf(c)];
  const fits = (o2) => o2 <= U + 1e-9 ? '<span class="pass">yes</span>' : '<span class="fail">no</span>';
  const lines = [
    ['Planned oxygen', (c) => f1(v(c).pred_o2)],
    ['Actual oxygen', (c) => `<b>${f1(v(c).actual_o2)}</b>`],
    ['Error (actual − planned)', (c) => sg(v(c).o2_error, f1)],
    ['Planned walk fits budget', (c) => fits(v(c).pred_o2)],
    ['Actual walk fits budget', (c) => fits(v(c).actual_o2)],
    ['Planned time', (c) => fmtMin(v(c).pred_time_min)],
    ['Actual time', (c) => fmtMin(v(c).actual_time_min)],
    ['Metres in hazard zones', (c) => `<b>${f0(v(c).hazard_m)}</b>`],
    ['Hazard crossings', (c) => `<b>${v(c).crossings}</b>`],
    ['Metres on blocked cells', (c) => f0(v(c).blocked_m)],
    ['Walk length (m)', (c) => f0(v(c).length_m)],
  ];
  $('#cmp').innerHTML = `<table class="cmp"><thead><tr><th></th>${cols.map((c) => `<th class="c${c === 'A+' ? 'Ap' : c === 'REF' ? 'R' : c}">${c === 'B' ? 'B@' + S.k : c}</th>`).join('')}</tr></thead>
<tbody>${lines.map(([n, f]) => `<tr><td>${n}</td>${cols.map((c) => `<td>${f(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>
<p class="hint">Habitat → test point → back on the same path. Oxygen in nominal minutes. Whether a walk fits the budget is not evidence for either route (it can flip on a few minutes). Hazard zone: a patch of sand or blocked ground ≥ 400 m² on the reference terrain that the orbital map does not show; a crossing is a stretch ≥ 10 m inside one. A+ and the reference bound are context, not results.</p>`;
}

function renderOverall() {
  const s = S.C.summary.all, A = s.A, B = s[`B@${S.k}`], R = s.REF, sh = B.share_of_possible_improvement;
  const pc = (v) => v == null ? '–' : Math.round(100 * v) + '%';
  const pw = S.PW && S.PW.groups.all[`B@${S.k}`] && S.PW.groups.all[`B@${S.k}`].actual_o2;
  $('#overall').innerHTML = `<table class="cmp"><thead><tr><th>mean per walk</th><th class="cA">A</th><th class="cB">B@${S.k}</th><th class="cR">ref. bound</th></tr></thead><tbody>
<tr><td>Metres in hazard zones</td><td>${f0(A.hazard_m.mean)}</td><td><b>${f0(B.hazard_m.mean)}</b></td><td>${f0(R.hazard_m.mean)}</td></tr>
<tr><td>Hazard crossings <span class="muted">(do not fall steadily with more loops)</span></td><td>${f1(A.crossings.mean)}</td><td>${f1(B.crossings.mean)}</td><td>${f1(R.crossings.mean)}</td></tr>
<tr><td>Actual oxygen</td><td>${f1(A.actual_o2.mean)}</td><td><b>${f1(B.actual_o2.mean)}</b></td><td>${f1(R.actual_o2.mean)}</td></tr>
<tr><td>Oxygen underestimated by</td><td>${f1(A.o2_error.mean)}</td><td><b>${f1(B.o2_error.mean)}</b></td><td>${f1(R.o2_error.mean)}</td></tr></tbody></table>
<p class="hint">After ${S.k} loop${S.k > 1 ? 's' : ''} the rover's map recovers ${pc(sh.hazard_m)} of the hazard metres and ${pc(sh.actual_o2)} of the oxygen that perfect knowledge (reference bound) would save. ${pw ? `Of the ${pw.n} walks, ${pw.better} use less actual oxygen than route A, ${pw.worse} more, ${pw.same} the same.` : ''} Oxygen in nominal minutes. Details by distance: <a href="#" id="tblLink">full table</a>.</p>`;
  $('#tblLink').onclick = (e) => { e.preventDefault(); renderTable(); renderRobust(); $('#table').showModal(); };
}

/* ---------------- map ---------------- */
function fc(f) { return { type: 'FeatureCollection', features: f }; }
function xyToLL(x, y) { const b = S.C.base; return [b.lon + (x / S.C.k_coslat) / R_MARS / DEG, b.lat + y / R_MARS / DEG]; }

function buildMap() {
  const C = S.C, c = C.aoi_corners, sc = S.sc;
  const map = new maplibregl.Map({
    container: 'map', bounds: [[c[0][0], c[2][1]], [c[1][0], c[0][1]]], fitBoundsOptions: { padding: { top: 30, bottom: 30, left: 300, right: 30 } },
    maxZoom: 19, minZoom: 9, renderWorldCopies: false, dragRotate: false, pitchWithRotate: false,
    style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0d0b0a' } }] },
    attributionControl: { compact: true, customAttribution: 'NASA/JPL-Caltech/UArizona (HiRISE), NASA/JPL-Caltech/MSSS (CTX), USGS Astrogeology. Routes: derived; rover: simulated.' },
  });
  S.map = map; window.__mapIdle = false;
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.on('load', async () => {
    const L = (id) => sc.layers.find((l) => l.id === id);
    const ctx = L('ctx_ortho'), ho = L('hirise_ortho');
    map.addSource('ctx', { type: 'image', url: abs(BASE + ctx.url), coordinates: ctx.coordinates });
    map.addLayer({ id: 'ctx', type: 'raster', source: 'ctx', paint: { 'raster-fade-duration': 0, 'raster-brightness-max': 0.75, 'raster-saturation': -0.3 } });
    map.addSource('hfull', { type: 'raster', tiles: [abs(BASE) + ho.url], tileSize: 256, minzoom: ho.minzoom, maxzoom: ho.maxzoom, bounds: ho.bounds });
    map.addLayer({ id: 'hfull', type: 'raster', source: 'hfull', layout: { visibility: 'none' }, paint: { 'raster-fade-duration': 0 } });
    map.addSource('cls', { type: 'image', url: abs(CB + C.files.class_ref), coordinates: c });
    map.addLayer({ id: 'cls', type: 'raster', source: 'cls', paint: { 'raster-opacity': 0.55, 'raster-fade-duration': 0, 'raster-resampling': 'nearest' } });
    map.addSource('haz', { type: 'image', url: abs(CB + C.files.hazard_zones), coordinates: c });
    map.addLayer({ id: 'haz', type: 'raster', source: 'haz', layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.35, 'raster-fade-duration': 0, 'raster-resampling': 'nearest' } });
    map.addSource('seen', { type: 'canvas', canvas: 'seenCanvas', coordinates: c, animate: false });
    map.addLayer({ id: 'seen', type: 'raster', source: 'seen', layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.55, 'raster-fade-duration': 0 } });
    map.addSource('aoi', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [...c, c[0]] } } });
    map.addLayer({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.2, 'line-dasharray': [3, 2] } });
    map.addSource('routes', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'routes-case', type: 'line', source: 'routes', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': ['get', 'cw'], 'line-opacity': 0.75 } });
    map.addLayer({ id: 'routes', type: 'line', source: 'routes', layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': ['get', 'col'], 'line-width': ['get', 'w'] } });
    map.addLayer({ id: 'routes-haz', type: 'line', source: 'routes', filter: ['==', ['get', 'haz'], 1], layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ff2d1a', 'line-width': ['+', ['get', 'w'], 1.5], 'line-dasharray': [1, 0.8] } });
    map.addSource('tg', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'tg', type: 'circle', source: 'tg', paint: { 'circle-radius': ['case', ['get', 'sel'], 8, 4.5], 'circle-color': ['case', ['get', 'sel'], '#ffffff', 'rgba(255,255,255,0.35)'],
      'circle-stroke-color': '#000', 'circle-stroke-width': ['case', ['get', 'sel'], 2.5, 1] } });
    const b = C.base;
    map.addSource('base', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [b.lon, b.lat] } } });
    map.addLayer({ id: 'base', type: 'circle', source: 'base', paint: { 'circle-radius': 8, 'circle-color': '#e8743b', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
    S.marker = new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'astro-marker', title: 'Astronaut' }) }).setLngLat([b.lon, b.lat]).addTo(map);
    const pop = new maplibregl.Popup({ closeButton: false, offset: 8 });
    map.on('click', 'tg', (e) => selectTarget(e.features[0].properties.i));
    map.on('mouseenter', 'tg', (e) => { map.getCanvas().style.cursor = 'pointer'; const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(`Test point T${p.id}<br>${esc(p.band)} m band · click to select`).addTo(map); });
    map.on('mouseleave', 'tg', () => { map.getCanvas().style.cursor = ''; pop.remove(); });
    map.on('mouseenter', 'base', (e) => pop.setLngLat(e.lngLat).setHTML('<b>Habitat</b> <span class="badge assumed">assumed</span>').addTo(map));
    map.on('mouseleave', 'base', () => pop.remove());
    map.on('move', updateScale); map.on('mousemove', (e) => showCoords(e.lngLat));
    map.once('idle', () => { window.__mapIdle = true; });
    updateScale();
    await selectTarget(S.tgt);
  });
}

function drawTargets() {
  if (!S.map.getSource('tg')) return;
  S.map.getSource('tg').setData(fc(S.C.rows.map((r, i) => ({ type: 'Feature', properties: { i, id: r.target, band: r.band, sel: i === S.tgt }, geometry: { type: 'Point', coordinates: xyToLL(r.x, r.y) } }))));
}

function drawRoutes() {
  if (!S.map || !S.map.getSource('routes') || !S.routes) return;
  const shown = ['REF', 'A+', 'A', 'B'].filter((r) => r === 'A' || r === 'B' || (r === 'A+' && $('#showAp').checked) || (r === 'REF' && $('#showRef').checked));
  const feats = [];
  for (const r of shown) {
    const st = S.routes.states[stateOf(r)], n = st.turn_idx + 1, sel = r === S.route;
    const w = sel ? 3.6 : (r === 'A' || r === 'B' ? 2.4 : 1.6);
    // outbound half only (the walk comes back on the same path); split by hazard flag for the red dashes
    let seg = [[st.lon[0], st.lat[0]]], hz = st.haz[0];
    for (let j = 1; j < n; j++) {
      seg.push([st.lon[j], st.lat[j]]);
      const h = st.haz[j];
      if (h !== hz || j === n - 1) { feats.push({ type: 'Feature', properties: { col: COL[r], w, cw: w + 2.5, haz: hz && h ? 1 : 0 }, geometry: { type: 'LineString', coordinates: seg } }); seg = [[st.lon[j], st.lat[j]]]; hz = h; }
    }
  }
  S.map.getSource('routes').setData(fc(feats));
}

function drawSeen() {
  const c = $('#seenCanvas'); c.width = S.tw; c.height = S.th;
  const x = c.getContext('2d'), im = x.createImageData(S.tw, S.th), t1 = S.C.recon_t1[String(S.k)];
  for (let i = 0; i < S.revealT.length; i++) if (S.revealT[i] <= t1) { im.data[4 * i] = 88; im.data[4 * i + 1] = 180; im.data[4 * i + 2] = 255; im.data[4 * i + 3] = 200; }
  x.putImageData(im, 0, 0);
  const src = S.map && S.map.getSource('seen'); if (src) { src.play(); src.pause(); }
}

/* ---------------- replay ---------------- */
function idxAt(t) { const T = cur().act_t; let lo = 0, hi = T.length - 1; while (lo < hi) { const m = (lo + hi + 1) >> 1; if (T[m] <= t) lo = m; else hi = m - 1; } return lo; }
function lerp(a, i, f) { return i + 1 < a.length ? a[i] + (a[i + 1] - a[i]) * f : a[i]; }
function setT(t) {
  const st = cur(), T = st.act_t, tot = T.at(-1); S.t = Math.max(0, Math.min(t, tot));
  const i = idxAt(S.t), f = i + 1 < T.length && T[i + 1] > T[i] ? (S.t - T[i]) / (T[i + 1] - T[i]) : 0;
  const cap = +$('#cap').value, U = usable(), resv = cap - U;
  const used = lerp(st.act_o2, i, f), hk = lerp(st.home_k, i, f), hr = lerp(st.home_ref, i, f);
  const left = cap - used, mPlan = U - used - hk, mTrue = U - used - hr;
  $('#scrub').value = tot ? Math.round(S.t / tot * 1000) : 0;
  $('#tLbl').textContent = `${f0(S.t)} of ${f0(tot)}`;
  $('#hudRoute').innerHTML = `<span style="color:${COL[S.route]}">●</span> ${esc(nameOf(S.route))}`;
  $('#hudTerr').textContent = `${CLS[st.cls[i]]}${st.haz[i] ? ' · hazard zone' : ''}`;
  $('#o2Val').textContent = `${f0(left)} / ${f0(cap)} nominal min`;
  const ob = $('#o2Bar'); ob.querySelector('.fill').style.width = `${Math.max(0, left / cap * 100)}%`; ob.querySelector('.res').style.width = `${resv / cap * 100}%`;
  ob.classList.toggle('low', left < resv);
  const bar = (id, vid, m) => { $(vid).textContent = `${f0(m)} nominal min`; const b = $(id); b.querySelector('.fill').style.width = `${Math.max(0, Math.min(1, m / U)) * 100}%`; b.classList.toggle('crit', m < 0.15 * U); b.classList.toggle('neg', m < 0); };
  bar('#mgBar', '#mgVal', mPlan); bar('#mtBar', '#mtVal', mTrue);
  const w = $('#warn');
  if (mTrue < 0) { w.hidden = false; w.textContent = 'True return margin below zero: on the real terrain the oxygen would run into the reserve before getting home.'; }
  else if (mTrue < mPlan - 0.15 * U) { w.hidden = false; w.textContent = 'The plan overestimates the margin: the terrain costs more than the map said.'; }
  else w.hidden = true;
  $('#tdVal').textContent = `${fmtMin(S.t)} · ${(lerp(st.d, i, f) / 1000).toFixed(2)} km`;
  if (S.marker) S.marker.setLngLat([lerp(st.lon, i, f), lerp(st.lat, i, f)]);
}
function play() {
  if (S.t >= cur().act_t.at(-1)) setT(0);
  S.playing = true; $('#play').textContent = '❚❚ Pause';
  let last = performance.now();
  const step = (now) => { if (!S.playing) return; const dt = (now - last) / 1000; last = now; setT(S.t + dt * +$('#speed').value); if (S.t >= cur().act_t.at(-1)) { stop(); return; } requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
function stop() { S.playing = false; $('#play').textContent = '▶ Play'; }

/* ---------------- full table ---------------- */
function renderTable() {
  const C = S.C, G = ['all', ...Object.keys(C.definitions.bands_m)];
  const st = C.states;
  const lab = (s) => s === 'A' ? 'A · orbital only' : s === 'A+' ? 'A+ · bracket (uses reference)' : s === 'REF' ? 'Reference · upper bound' : `B · after ${s.slice(2)} loop${s.slice(2) === '1' ? '' : 's'}`;
  const share = (d, q) => d.share_of_possible_improvement && d.share_of_possible_improvement[q] != null ? Math.round(100 * d.share_of_possible_improvement[q]) + '%' : '–';
  const tbl = (g) => {
    const s = C.summary[g]; if (!s || !s.A) return `<p class="hint">No test points in this band.</p>`;
    return `<table class="full"><thead><tr><th>Knowledge used for planning</th><th>Planned O2 (mean)</th><th>Actual O2 (mean)</th><th>Error (mean)</th><th>Actual fits 384</th><th>Actual time (mean)</th><th>Hazard metres (mean / total)</th><th>Crossings (total)</th><th>Blocked m (total)</th><th>Zones entered (mean)</th><th>vs A: hazard m (mean)</th><th>vs A: actual O2 (mean)</th><th>vs A: crossings (mean)</th><th>Share of possible gain (O2 / hazard m)</th></tr></thead><tbody>
${st.map((k) => { const d = s[k], dv = d.diff_vs_A; return `<tr class="${k === `B@${S.k}` ? 'hl' : ''}"><td>${esc(lab(k))}</td><td>${f1(d.pred_o2.mean)}</td><td>${f1(d.actual_o2.mean)}</td><td>${sg(d.o2_error.mean, f1)}</td><td>${d.n_actual_within_budget} / ${d.n}</td><td>${fmtMin(d.actual_time_min.mean)}</td><td>${f0(d.hazard_m.mean)} / ${f0(d.hazard_m.total)}</td><td>${f0(d.crossings.total)}</td><td>${f0(d.blocked_m.total)}</td><td>${f1(d.zones_entered.mean)}</td><td>${dv ? sg(dv.hazard_m.mean) : '–'}</td><td>${dv ? sg(dv.actual_o2.mean, f1) : '–'}</td><td>${dv ? sg(dv.crossings.mean, f1) : '–'}</td><td>${k.startsWith('B@') || k === 'A+' ? share(d, 'actual_o2') + ' / ' + share(d, 'hazard_m') : '–'}</td></tr>`; }).join('')}</tbody></table>`;
  };
  $('#tableBody').innerHTML = `<h2>Before vs after recon: every test point <span class="badge derived">derived</span></h2>
<p>${C.rows.length} test points (300 m grid around the habitat, ≥ 300 m away, passable on both maps). For each: walk habitat → point → habitat on the least-oxygen path of the map named in the first column, then walk that same path on the HiRISE reference terrain. Oxygen in nominal minutes; usable budget 384 (480 with a 20% reserve). Computed ${esc(C.computed_at)}; definitions fixed before the first run (see DATA_LOG). Sand classes are <i>heuristic, not yet reviewed</i>.</p>
${G.map((g) => `<h3>${g === 'all' ? 'All test points' : g + ' m from the habitat'} (n = ${C.summary[g].A ? C.summary[g].A.n : 0})</h3>${tbl(g)}`).join('')}
${pointwiseTables()}
<div id="robust"></div>
<p class="hint">Share of possible gain = (A − B) / (A − reference upper bound), on the means. A+ adds the large sand belts to the orbital map using the reference terrain (60 m blocks ≥ 50% sand): it is not real pre-departure knowledge and only brackets the result. The reference upper bound is what perfect knowledge would give; it is not a recon result.</p>`;
}

async function renderRobust() {
  let R; try { R = await getJSON(CB + 'robustness.json'); } catch (e) { return; }
  const pc = (v) => v == null ? '–' : Math.round(100 * v) + '%';
  let h = '<h3>Robustness checks written before they were run <span class="badge derived">derived</span></h3>';
  if (R.t6) {
    const W = R.t6.windows;
    h += `<h4>Other 2.4 km windows of the same HiRISE mosaic (same rules, one run each)</h4><table class="full"><thead><tr><th>Window</th><th>Test points</th><th>Rover saw</th><th>Actual O2: A / B@30 / bound</th><th>B@30 − A O2</th><th>Hazard m: A / B@30 / bound</th><th>B@30 − A hazard m</th><th>Share of possible gain (O2 / hazard m)</th></tr></thead><tbody>
${Object.entries(W).map(([k, w]) => `<tr><td>(${k})${k === '0,0' ? ' main' : ''}</td><td>${w.n_targets}</td><td>${f1(w.observed_pct_after_30)}%</td><td>${f1(w.A.actual_o2_mean)} / ${f1(w['B@30'].actual_o2_mean)} / ${f1(w.REF.actual_o2_mean)}</td><td>${sg(w['B@30'].diff_vs_A.actual_o2.mean, f1)}</td><td>${f0(w.A.hazard_m_mean)} / ${f0(w['B@30'].hazard_m_mean)} / ${f0(w.REF.hazard_m_mean)}</td><td>${sg(w['B@30'].diff_vs_A.hazard_m.mean)}</td><td>${pc(w['B@30'].share.actual_o2)} / ${pc(w['B@30'].share.hazard_m)}</td></tr>`).join('')}</tbody></table>`;
    const st = R.t6.stats, line = (k, n) => { const x = st[k]; return `${n}: ${x.n_negative} of ${x.n} windows lower than A; median ${sg(x.median, f1)}${x.median_ci95_bootstrap ? ` (bootstrap 95% interval ${sg(x.median_ci95_bootstrap[0], f1)} to ${sg(x.median_ci95_bootstrap[1], f1)})` : ''}; ${x.wilcoxon_exact_two_sided_p != null ? 'Wilcoxon p = ' + x.wilcoxon_exact_two_sided_p.toFixed(3) : 'no p-value (' + esc(x.p_not_reported_because) + ')'}.`; };
    h += `<p class="hint">${line('main_hazard_m_all', 'Hazard metres, all windows')} ${line('main_hazard_m_excl_main', 'Without the main window')} ${line('secondary_actual_o2_all', 'Actual oxygen, all windows')} ${line('secondary_actual_o2_excl_main', 'Without the main window')}${Object.keys(R.t6.not_run || {}).length ? ' Not run: ' + Object.keys(R.t6.not_run).map((k) => `(${k})`).join(', ') + ' (HiRISE gap rule waiting for a decision).' : ''} Windows were chosen by a rule fixed after their HiRISE coverage was known and before any route number.</p>`;
  }
  if (R.t7) {
    h += `<h4>Rover settings (main window; written after the locked run's 11.3% coverage was seen, before any route number; the locked setting stays the result)</h4><table class="full"><thead><tr><th>Rover setting</th><th>Seen after 1 / 5 / 10 / 20 / 30 loops</th><th>B@30: actual O2</th><th>B@30 − A O2</th><th>B@30: hazard m</th><th>B@30 − A hazard m</th><th>Share of possible gain (O2 / hazard m)</th><th>Still underestimated by</th></tr></thead><tbody>
${Object.entries(R.t7).map(([k, t]) => { const b = t.summary.all['B@30']; return `<tr class="${k.startsWith('locked') ? 'hl' : ''}"><td>${esc(t.changed)}${k.startsWith('locked') ? ' (locked)' : ''}</td><td>${[1, 5, 10, 20, 30].map((i) => f1(100 * t.recon[i])).join(' / ')}%</td><td>${f1(b.actual_o2.mean)}</td><td>${sg(b.diff_vs_A.actual_o2.mean, f1)}</td><td>${f0(b.hazard_m.mean)}</td><td>${sg(b.diff_vs_A.hazard_m.mean)}</td><td>${pc(b.share_of_possible_improvement.actual_o2)} / ${pc(b.share_of_possible_improvement.hazard_m)}</td><td>${f1(b.o2_error.mean)}</td></tr>`; }).join('')}</tbody></table>`;
  }
  $('#robust').innerHTML = h;
}

function pointwiseTables() {
  const PW = S.PW; if (!PW) return '';
  const Q = [['actual_o2', 'Actual oxygen'], ['hazard_m', 'Hazard metres'], ['o2_error', 'Oxygen error (actual − planned)'], ['crossings', 'Crossings']];
  const lab = (s) => s === 'A+' ? 'A+ (bracket)' : s === 'REF' ? 'Reference bound' : `B after ${s.slice(2)}`;
  const f = (v) => (Math.abs(v) >= 100 ? f0(v) : f1(v));
  const tb = (g) => { const G = PW.groups[g]; return `<table class="full"><thead><tr><th>vs route A, per point</th>${Q.map(([, n]) => `<th>${n}: better / worse / same</th><th>mean [95% resampling interval]</th><th>median (quartiles; min, max)</th>`).join('')}</tr></thead><tbody>
${Object.keys(G).map((s) => `<tr class="${s === `B@${S.k}` ? 'hl' : ''}"><td>${esc(lab(s))}</td>${Q.map(([q]) => { const d = G[s][q]; return `<td>${d.better} / ${d.worse} / ${d.same}</td><td>${sg(d.mean, f)} [${sg(d.mean_ci95_resample_points[0], f)}, ${sg(d.mean_ci95_resample_points[1], f)}]</td><td>${sg(d.median, f)} (${sg(d.q1, f)}, ${sg(d.q3, f)}; ${sg(d.min, f)}, ${sg(d.max, f)})</td>`; }).join('')}</tr>`).join('')}</tbody></table>`; };
  return `<h3>Point by point: how the ${PW.groups.all['B@30'].actual_o2.n} walks spread</h3>
<p class="hint">Difference = route − route A for each test point. Better = lower (for the oxygen error: smaller in absolute value). The interval resamples the points 10,000 times (fixed seed). This describes the spread of these points; it is <b>not a significance test</b> — the points share the walk out of the habitat, one recon run and one study area. Added after the numbers were seen; no number was changed.</p>
${['all', '300-600', '600-1200', '>1200'].map((g) => `<h4>${g === 'all' ? 'All test points' : g + ' m'} (n = ${PW.groups[g]['B@30'].actual_o2.n})</h4>${tb(g)}`).join('')}`;
}

/* ---------------- misc ---------------- */
function marsDist(a, b) { const dlat = (b.lat - a.lat) * DEG, dlon = (b.lng - a.lng) * DEG; const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * DEG) * Math.cos(b.lat * DEG) * Math.sin(dlon / 2) ** 2; return 2 * R_MARS * Math.asin(Math.sqrt(h)); }
function updateScale() {
  const m = S.map, H = m.getContainer().clientHeight, maxPx = 120, a = m.unproject([20, H - 40]), b = m.unproject([20 + maxPx, H - 40]);
  const d = marsDist(a, b), pow = 10 ** Math.floor(Math.log10(d)), n = d / pow, nice = (n >= 5 ? 5 : n >= 2 ? 2 : 1) * pow;
  $('#scaleBar').style.width = (maxPx * nice / d) + 'px'; $('#scaleLabel').textContent = (nice >= 1000 ? nice / 1000 + ' km' : nice + ' m') + ' (Mars)';
}
function showCoords(ll) {
  const b = S.C.base, x = (ll.lng - b.lon) * DEG * R_MARS * S.C.k_coslat, y = (ll.lat - b.lat) * DEG * R_MARS;
  $('#coords').innerHTML = `${ll.lat.toFixed(5)}°N ${ll.lng.toFixed(5)}°E<br>x ${x.toFixed(0)} m E, y ${y.toFixed(0)} m N of the habitat`;
}

function renderAbout() {
  const P = S.C.astronaut_params;
  $('#aboutBody').innerHTML = `<h2>Marswalk Recon · astronaut map</h2>
<p>A scout rover leaves the habitat first and maps the ground; then an astronaut's walk is planned within the suit's oxygen budget. This page shows what that recon is worth: the same walk planned from orbital data only (route A) and from the rover's map (route B), both checked on the HiRISE reference terrain.</p>
<h3>How the numbers are made</h3>
<ul><li><b>Orbital map (prior)</b>: CTX 20 m terrain model → slope classes. It cannot see sand ripples, so it has no sand.</li>
<li><b>Reference terrain</b>: HiRISE 1 m terrain model and 0.25 m image → firm / rough / sand / blocked on a 2 m grid. It is orbital data too; we use it as the stand-in for the ground, never as ground truth.</li>
<li><b>Rover recon</b> (simulated): the rover drives loops from the habitat on its own; within 15 m of its path the reference terrain replaces the orbital map. Route B uses the rover's map after 1, 5, 10, 20 or 30 loops.</li>
<li><b>Walk model</b> (assumed): ${P.speed_kmh} km/h on firm ground; speed factor firm / rough / sand ${P.speed_factor.firm} / ${P.speed_factor.rough} / ${P.speed_factor.sand}; oxygen factor ${P.o2_factor.firm} / ${P.o2_factor.rough} / ${P.o2_factor.sand}; slopes ≥ 25° blocked; suit ${P.o2_capacity_nominal_min} nominal minutes with ${Math.round(P.reserve_frac * 100)}% reserve.</li>
<li><b>Return margin</b> = usable oxygen left − oxygen needed to walk home on the cheapest route. "As the plan sees it" uses the map the route was planned on; "true" uses the reference terrain. Oxygen used so far is always the actual (reference) value.</li></ul>
<h3>Labels</h3><p><span class="badge measured">measured</span> HiRISE, CTX (orbital) · <span class="badge derived">derived</span> classes, routes, oxygen, time · <span class="badge assumed">assumed</span> walk and rover parameters, habitat position · <span class="badge simulated">simulated</span> rover recon.</p>
<h3>Limitations</h3><ul>
<li>Sand classes are an automatic texture rule, not yet reviewed by a person (heuristic). Long bright/dark edges (scarps, albedo contacts) are sometimes called sand; thin small ripples and large ripples get the same cost.</li>
<li>The orbital map has no sand: the same texture test on the CTX image could not find the sand fields (AUC 0.48). An experienced image interpreter might guess the large sand belt from CTX; our prior does not. The A+ column brackets that case.</li>
<li>Walk speed and oxygen factors come from the team's earlier prototype; their original sources are still being checked. No physiological values are modelled.</li>
<li>Test points are a fixed grid, not science targets: where it is worth sending the astronaut (step 2) is not decided yet.</li>
<li>Routes are not replanned during the walk; route A walks into what it did not know about.</li>
<li>After recon the plan still underestimates a walk by 108 nominal minutes on average (plans 58, costs 167); loops 20 to 30 brought no further gain; knowing part of the map is sometimes worse than knowing none (a detour around seen sand can run into unseen sand).</li>
<li>Three comparison definitions (hazard metres only inside hazard zones; crossings measured by in-zone metres; no dwell time at the point) were set by the implementer before the run and ratified by the manager after the numbers were seen.</li>
<li>One study area and one recon run; the 63 test points are not independent, so no per-point p-value is given.</li>
<li>Full list: <code>README.md</code> and <code>DATA_LOG.md</code> in the repository.</li></ul>`;
}

init().catch((e) => { document.body.insertAdjacentHTML('afterbegin', `<pre style="color:#f88;padding:12px">Failed to load: ${esc(e.message)}</pre>`); console.error(e); });
