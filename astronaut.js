// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Marswalk Recon — astronaut map: route A (orbital data only) vs route B (after the simulated rover recon),
   both walked on the HiRISE reference terrain. Plain JS, no build step. Interface text: i18n.js (tr()).
   Data: data/jezero/compare/compare.json (definitions + summary tables) and compare/routes/t<i>.json (per test point:
   each route with cumulative distance, predicted and actual time / oxygen, oxygen needed to get home on the plan's map
   and on the reference terrain, hazard flag and reference class at every kept vertex). Nothing is recomputed here
   except the budget verdicts, which follow the oxygen slider. Source: pipeline/compare_ab.py, export_compare.py.
   Product = the version-3 chain (compare_v3.json); ?rule=v2 still loads the version-2 record (no switch on screen). */
'use strict';
const R_MARS = 3396190, DEG = Math.PI / 180;
const SCENE = 'jezero', BASE = `data/${SCENE}/`, CB = BASE + 'compare/';
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const abs = (u) => new URL(u, location.href).href;
const f0 = (v) => v == null || !isFinite(v) ? '–' : Math.round(v).toLocaleString('en-US');
const f1 = (v) => v == null || !isFinite(v) ? '–' : (Math.round(v * 10) / 10).toLocaleString('en-US');
const sg = (v, f = f0) => (v > 0 ? '+' : v < 0 ? '−' : '') + f(Math.abs(v));
const fmtMin = (m) => { const h = Math.floor(m / 60), r = Math.round(m - 60 * h); return h ? tr('fmt.hm', { h, m: String(r).padStart(2, '0') }) : tr('fmt.m', { m: r }); };
const COL = { A: '#ff9f43', B: '#43b0f1', 'A+': '#c38bff', REF: '#e9e4dc' };
const CLS = ['firm', 'rough', 'sand', 'blocked'];
// fixed display defaults (no longer user settings): emergency reserve = the pipeline's reserve_frac; replay speed
const RESERVE_PCT = 20, SPEED_MIN_PER_S = 6;
const S = { k: 30, tgt: 0, route: 'A', t: 0, playing: false, cache: {} };

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); }
async function bitmap(u) { return createImageBitmap(await (await fetch(u)).blob(), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' }); }
const bKey = (k = S.k) => (S.rule === 'v3' ? `B_v3@${k}` : `B@${k}`);
const stateOf = (r) => (r === 'B' ? bKey() : r);
const nameOf = (r) => ({ A: tr('idx.routeA'), B: tr('idx.routeB', { k: S.k }), 'A+': tr('idx.routeAp'), REF: tr('idx.routeRef') }[r]);
function usable() { return +$('#cap').value * (1 - RESERVE_PCT / 100); }

async function init() {
  const [C, sc, PW] = await Promise.all([getJSON(CB + 'compare.json'), getJSON(BASE + 'scene.json'), getJSON(CB + 'pointwise.json')]);
  S.C = C; S.sc = sc; S.PW = PW;
  // product = the version-3 chain when its files exist (decided before any v3 number); ?rule=v2 shows the record
  try { S.V3 = await getJSON(CB + 'compare_v3.json'); } catch (e) { S.V3 = null; }
  S.rule = S.V3 && new URLSearchParams(location.search).get('rule') !== 'v2' ? 'v3' : 'v2';
  if (S.V3) {
    Object.assign(C.summary.all, S.V3.summary_all);
    C.rows.forEach((r) => Object.assign(r, S.V3.rows[String(r.target)] || {}));
  }
  S.ks = C.states.filter((s) => s.startsWith('B@')).map((s) => +s.slice(2));
  S.k = S.ks[S.ks.length - 1];
  // default test point: the lattice point at (600, 0) m (the step-3 skeleton's first placeholder rule), else the first
  S.tgt = Math.max(0, C.rows.findIndex((r) => r.x === 600 && r.y === 0));
  $('#tSel').innerHTML = C.rows.map((r, i) => `<option value="${i}">${esc(tr('idx.tOpt', { id: r.target, d: f0(r.dist_m) }))}</option>`).join('');
  $('#kBtns').innerHTML = S.ks.map((k) => `<button class="btn sm" data-k="${k}">${k}</button>`).join('') + `<span class="muted">${tr('idx.loopsUnit')}</span>`;
  document.querySelectorAll('#kBtns button').forEach((b) => b.onclick = () => { S.k = +b.dataset.k; refresh(); });
  $('#tSel').onchange = () => selectTarget(+$('#tSel').value);
  $('#tPrev').onclick = () => selectTarget((S.tgt - 1 + C.rows.length) % C.rows.length);
  $('#tNext').onclick = () => selectTarget((S.tgt + 1) % C.rows.length);
  $('#cap').oninput = () => { renderCmp(); setT(S.t); };
  $('#rSel').onchange = () => { stop(); S.route = $('#rSel').value; setT(0); drawRoutes(); };
  $('#scrub').oninput = () => { stop(); setT(+$('#scrub').value / 1000 * cur().act_t.at(-1)); };
  $('#play').onclick = () => (S.playing ? stop() : play());
  $('#play').textContent = tr('common.play');
  $('#aboutBtn').onclick = () => { renderAbout(); $('#about').showModal(); };
  $('#tableBtn').onclick = () => { renderTable(); $('#table').showModal(); };
  for (const [id, lay] of [['showCls', 'cls'], ['showHaz', 'haz'], ['showSeen', 'seen'], ['showHi', 'hfull']])
    $('#' + id).onchange = () => S.map.setLayoutProperty(lay, 'visibility', $('#' + id).checked ? 'visible' : 'none');
  const tImg = await bitmap(CB + C.files.reveal_t);
  const c = document.createElement('canvas'); c.width = tImg.width; c.height = tImg.height;
  const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(tImg, 0, 0);
  const d = x.getImageData(0, 0, c.width, c.height).data, n = c.width * c.height, tt = new Uint32Array(n);
  for (let i = 0; i < n; i++) tt[i] = (d[4 * i] << 16) | (d[4 * i + 1] << 8) | d[4 * i + 2];
  S.revealT = tt; S.tw = c.width; S.th = c.height;
  if (S.rule === 'v3') {
    const vImg = await bitmap(CB + S.V3.files.reveal_t);
    x.clearRect(0, 0, c.width, c.height); x.drawImage(vImg, 0, 0);
    const d3 = x.getImageData(0, 0, c.width, c.height).data, t3 = new Uint32Array(n);
    for (let i = 0; i < n; i++) t3[i] = (d3[4 * i] << 16) | (d3[4 * i + 1] << 8) | d3[4 * i + 2];
    S.revealT = t3;
  }
  buildMap();
}

function cur() { return S.routes.states[stateOf(S.route)]; }
function row() { return S.C.rows[S.tgt]; }

async function selectTarget(i) {
  stop(); S.tgt = i; $('#tSel').value = i;
  const r = row();
  if (!S.cache[r.target]) {
    S.cache[r.target] = await getJSON(`${CB}routes/t${r.target}.json`);
    if (S.rule === 'v3') Object.assign(S.cache[r.target].states, (await getJSON(`${CB}routes_v3/t${r.target}.json`)).states);
  }
  S.routes = S.cache[r.target];
  $('#tInfo').textContent = tr('idx.tInfo', { d: f0(r.dist_m), band: r.band });
  refresh();
}

function refresh() {
  document.querySelectorAll('#kBtns button').forEach((b) => b.classList.toggle('active', +b.dataset.k === S.k));
  const of = S.rule === 'v3' ? S.V3.observed_frac[String(S.k)] : S.C.observed_frac[`B@${S.k}`];
  $('#kInfo').textContent = tr('idx.kInfo', { k: S.k, pct: (100 * of).toFixed(1) });
  renderRouteSel(); renderCmp(); renderOverall(); drawSeen(); drawRoutes(); drawTargets(); setT(0);
}

function renderRouteSel() {
  const opts = ['A', 'B'];
  if (!opts.includes(S.route)) S.route = 'A';
  $('#rSel').innerHTML = opts.map((o) => `<option value="${o}" ${o === S.route ? 'selected' : ''}>${esc(nameOf(o))}</option>`).join('');
}

function renderCmp() {
  const r = row(), U = usable(), cols = ['A', 'B'];
  $('#capLbl').textContent = `${$('#cap').value}`; $('#usableLbl').textContent = tr('idx.usable', { u: f0(U), res: RESERVE_PCT });
  const v = (c) => r[stateOf(c)];
  const fits = (o2) => o2 <= U + 1e-9 ? `<span class="pass">${tr('common.yes')}</span>` : `<span class="fail">${tr('common.no')}</span>`;
  const lines = [
    ['idx.c.pred', (c) => f1(v(c).pred_o2)],
    ['idx.c.act', (c) => `<b>${f1(v(c).actual_o2)}</b>`],
    ['idx.c.fits', (c) => fits(v(c).actual_o2)],
    ['idx.c.time', (c) => fmtMin(v(c).actual_time_min)],
    ['idx.c.haz', (c) => `<b>${f0(v(c).hazard_m)}</b>`],
    ['idx.c.len', (c) => f0(v(c).length_m)],
  ];
  $('#cmp').innerHTML = `<table class="cmp"><thead><tr><th></th>${cols.map((c) => `<th class="c${c}">${c === 'B' ? tr('idx.colB', { k: S.k }) : tr('idx.colA')}</th>`).join('')}</tr></thead>
<tbody>${lines.map(([n, f]) => `<tr><td>${tr(n)}</td>${cols.map((c) => `<td>${f(c)}</td>`).join('')}</tr>`).join('')}</tbody></table>
<p class="hint">${tr('idx.cmpHint')}</p>`;
}

function renderOverall() {
  const s = S.C.summary.all, A = s.A, B = s[bKey()], R = s.REF, sh = B.share_of_possible_improvement;
  const pc = (v) => v == null ? '–' : Math.round(100 * v) + '%';
  const pw = S.rule === 'v3' ? (B.better_worse_same_vs_A_actual_o2 && { n: B.n, better: B.better_worse_same_vs_A_actual_o2[0], worse: B.better_worse_same_vs_A_actual_o2[1] }) : S.PW && S.PW.groups.all[`B@${S.k}`] && S.PW.groups.all[`B@${S.k}`].actual_o2;
  $('#overall').innerHTML = `<table class="cmp"><thead><tr><th>${tr('idx.o.mean')}</th><th class="cA">A</th><th class="cB">B</th><th class="cR">${tr('idx.o.ref')}</th></tr></thead><tbody>
<tr><td>${tr('idx.c.haz')}</td><td>${f0(A.hazard_m.mean)}</td><td><b>${f0(B.hazard_m.mean)}</b></td><td>${f0(R.hazard_m.mean)}</td></tr>
<tr><td>${tr('idx.c.act')}</td><td>${f1(A.actual_o2.mean)}</td><td><b>${f1(B.actual_o2.mean)}</b></td><td>${f1(R.actual_o2.mean)}</td></tr>
<tr><td>${tr('idx.o.under')}</td><td>${f1(A.o2_error.mean)}</td><td><b>${f1(B.o2_error.mean)}</b></td><td>${f1(R.o2_error.mean)}</td></tr></tbody></table>
<p class="hint">${tr('idx.o.sum', { k: S.k, o2: pc(sh.actual_o2), hz: pc(sh.hazard_m) })}${pw ? ' ' + tr('idx.o.pw', { n: pw.n, better: pw.better, worse: pw.worse }) : ''}</p>`;
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
    attributionControl: { compact: true, customAttribution: tr('idx.attrib') },
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
    S.marker = new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'astro-marker', title: tr('common.astronaut') }) }).setLngLat([b.lon, b.lat]).addTo(map);
    const pop = new maplibregl.Popup({ closeButton: false, offset: 8 });
    map.on('click', 'tg', (e) => selectTarget(e.features[0].properties.i));
    map.on('mouseenter', 'tg', (e) => { map.getCanvas().style.cursor = 'pointer'; const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(esc(tr('idx.tgPop', { id: p.id, band: p.band }))).addTo(map); });
    map.on('mouseleave', 'tg', () => { map.getCanvas().style.cursor = ''; pop.remove(); });
    map.on('mouseenter', 'base', (e) => pop.setLngLat(e.lngLat).setHTML(`<b>${tr('common.habitat')}</b> ${badgeHTML('assumed')}`).addTo(map));
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
  const feats = [];
  for (const r of ['A', 'B']) {
    const st = S.routes.states[stateOf(r)], n = st.turn_idx + 1, sel = r === S.route;
    const w = sel ? 3.6 : 2.4;
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
  const x = c.getContext('2d'), im = x.createImageData(S.tw, S.th), t1 = (S.rule === 'v3' ? S.V3.recon_t1 : S.C.recon_t1)[String(S.k)];
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
  $('#tLbl').textContent = tr('idx.tOf', { t: f0(S.t), tot: f0(tot) });
  $('#hudRoute').innerHTML = `<span style="color:${COL[S.route]}">●</span> ${esc(nameOf(S.route))}`;
  $('#hudTerr').textContent = `${tr('cls.' + CLS[st.cls[i]])}${st.haz[i] ? ' · ' + tr('idx.lgHaz') : ''}`;
  $('#o2Val').textContent = tr('idx.o2of', { l: f0(left), c: f0(cap) });
  const ob = $('#o2Bar'); ob.querySelector('.fill').style.width = `${Math.max(0, left / cap * 100)}%`; ob.querySelector('.res').style.width = `${resv / cap * 100}%`;
  ob.classList.toggle('low', left < resv);
  const bar = (id, vid, m) => { $(vid).textContent = tr('idx.nomMin', { v: f0(m) }); const b = $(id); b.querySelector('.fill').style.width = `${Math.max(0, Math.min(1, m / U)) * 100}%`; b.classList.toggle('crit', m < 0.15 * U); b.classList.toggle('neg', m < 0); };
  bar('#mgBar', '#mgVal', mPlan); bar('#mtBar', '#mtVal', mTrue);
  const w = $('#warn');
  if (mTrue < 0) { w.hidden = false; w.textContent = tr('idx.warnNeg'); }
  else if (mTrue < mPlan - 0.15 * U) { w.hidden = false; w.textContent = tr('idx.warnOver'); }
  else w.hidden = true;
  $('#tdVal').textContent = `${fmtMin(S.t)} · ${(lerp(st.d, i, f) / 1000).toFixed(2)} km`;
  if (S.marker) S.marker.setLngLat([lerp(st.lon, i, f), lerp(st.lat, i, f)]);
}
function play() {
  if (S.t >= cur().act_t.at(-1)) setT(0);
  S.playing = true; $('#play').textContent = tr('common.pause');
  let last = performance.now();
  const step = (now) => { if (!S.playing) return; const dt = (now - last) / 1000; last = now; setT(S.t + dt * SPEED_MIN_PER_S); if (S.t >= cur().act_t.at(-1)) { stop(); return; } requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
function stop() { S.playing = false; $('#play').textContent = tr('common.play'); }

/* ---------------- full table (current version only; version-2 record via ?rule=v2) ---------------- */
function renderTable() {
  const C = S.C, s = C.summary.all;
  const pc = (v) => v == null ? '–' : Math.round(100 * v) + '%';
  const bws = (k) => {
    const d = s[k]; if (d && d.better_worse_same_vs_A_actual_o2) return d.better_worse_same_vs_A_actual_o2.join(' / ');
    const p = S.PW && S.PW.groups.all[k] && S.PW.groups.all[k].actual_o2; return p ? `${p.better} / ${p.worse} / ${p.same}` : '–';
  };
  const lab = (k) => k === 'A' ? tr('idx.routeA') : k === 'A+' ? tr('idx.routeAp') : k === 'REF' ? tr('idx.routeRef') : tr('idx.routeBk', { k: k.split('@')[1] });
  const keys = ['A', ...S.ks.map((k) => bKey(k)), 'A+', 'REF'];
  const rows = keys.map((k) => {
    const d = s[k]; if (!d) return '';
    const dv = d.diff_vs_A, sh = d.share_of_possible_improvement;
    return `<tr class="${k === bKey() ? 'hl' : ''}"><td>${esc(lab(k))}</td><td>${f1(d.pred_o2.mean)}</td><td>${f1(d.actual_o2.mean)}</td><td>${sg(d.o2_error.mean, f1)}</td><td>${f0(d.hazard_m.mean)}</td><td>${d.n_actual_within_budget} / ${d.n}</td><td>${fmtMin(d.actual_time_min.mean)}</td><td>${dv ? sg(dv.actual_o2.mean, f1) + ' / ' + sg(dv.hazard_m.mean) : '–'}</td><td>${sh && k !== 'REF' ? pc(sh.actual_o2) + ' / ' + pc(sh.hazard_m) : '–'}</td><td>${k === 'A' ? '–' : bws(k)}</td></tr>`;
  }).join('');
  const th = ['idx.t.map', 'idx.t.pred', 'idx.t.act', 'idx.t.err', 'idx.t.haz', 'idx.t.fits', 'idx.t.time', 'idx.t.vsA', 'idx.t.share', 'idx.t.bws'];
  $('#tableBody').innerHTML = `<h2>${tr('idx.t.title')} ${badgeHTML('derived')}</h2>
<p>${tr('idx.t.intro', { n: C.rows.length, u: f0(C.usable_o2) })}</p>
<table class="full"><thead><tr>${th.map((k) => `<th>${tr(k)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>
<details class="explain"><summary>${tr('common.explain')}</summary><p class="hint">${tr('idx.t.notes')}</p></details>
<div id="x1"></div>`;
  renderX1();
}

async function renderX1() {
  try {
    const X = await getJSON(BASE + 'ai4mars/x1.json'), g = X.groups.sector, b = g.two_by_two;
    $('#x1').innerHTML = `<h3>${tr('idx.x1.h')}</h3><p class="hint">${tr('idx.x1.body', { n: g.n_images, w: g.n_waypoints, rho: g.spearman_sand.rho.toFixed(2), agr: Math.round(b.agreement * 100), both: b.both_sand, nw: b.n })}</p>`;
  } catch (e) { /* X1 not exported */ }
}

/* ---------------- misc ---------------- */
function marsDist(a, b) { const dlat = (b.lat - a.lat) * DEG, dlon = (b.lng - a.lng) * DEG; const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * DEG) * Math.cos(b.lat * DEG) * Math.sin(dlon / 2) ** 2; return 2 * R_MARS * Math.asin(Math.sqrt(h)); }
function updateScale() {
  const m = S.map, H = m.getContainer().clientHeight, maxPx = 120, a = m.unproject([20, H - 40]), b = m.unproject([20 + maxPx, H - 40]);
  const d = marsDist(a, b), pow = 10 ** Math.floor(Math.log10(d)), n = d / pow, nice = (n >= 5 ? 5 : n >= 2 ? 2 : 1) * pow;
  $('#scaleBar').style.width = (maxPx * nice / d) + 'px'; $('#scaleLabel').textContent = (nice >= 1000 ? nice / 1000 + ' km' : nice + ' m') + ' ' + tr('common.mars');
}
function showCoords(ll) {
  const b = S.C.base, x = (ll.lng - b.lon) * DEG * R_MARS * S.C.k_coslat, y = (ll.lat - b.lat) * DEG * R_MARS;
  $('#coords').innerHTML = `${ll.lat.toFixed(5)}°N ${ll.lng.toFixed(5)}°E<br>${esc(tr('common.xy', { x: x.toFixed(0), y: y.toFixed(0) }))}`;
}

function renderAbout() {
  const P = S.C.astronaut_params, B = S.C.summary.all[bKey(30)];
  const li = (k, v) => `<li>${tr(k, v)}</li>`;
  $('#aboutBody').innerHTML = `<h2>${tr('idx.ab.title')}</h2>
<p>${tr('idx.ab.intro')}</p>
<h3>${tr('common.howMade')}</h3>
<ul>${li('idx.ab.prior')}${li('idx.ab.ref')}${li('idx.ab.rover')}${li('idx.ab.routeB')}
${li('idx.ab.walk', { v: P.speed_kmh, sf: P.speed_factor.firm, sr: P.speed_factor.rough, ss: P.speed_factor.sand, of: P.o2_factor.firm, or: P.o2_factor.rough, os: P.o2_factor.sand, cap: P.o2_capacity_nominal_min, res: Math.round(P.reserve_frac * 100) })}
${li('idx.ab.unit')}${li('idx.ab.cmp')}${li('idx.ab.haz')}${li('idx.ab.margin')}${li('idx.ab.points')}${li('idx.ab.share')}</ul>
<h3>${tr('common.labels')}</h3><p>${badgeHTML('measured')} ${tr('idx.ab.lMeasured')} · ${badgeHTML('derived')} ${tr('idx.ab.lDerived')} · ${badgeHTML('assumed')} ${tr('idx.ab.lAssumed')} · ${badgeHTML('simulated')} ${tr('idx.ab.lSimulated')}</p>
<h3>${tr('common.limits')}</h3><ul>
${li('idx.ab.L.sand')}${li('idx.ab.L.prior')}${li('idx.ab.L.params')}
${B ? li('idx.ab.L.under', { e: f0(B.o2_error.mean), p: f0(B.pred_o2.mean), a: f0(B.actual_o2.mean) }) : ''}
${li('idx.ab.L.v3')}${li('idx.ab.L.step2')}${li('idx.ab.L.stops')}${li('idx.ab.L.noReplan')}${li('idx.ab.L.defs')}${li('idx.ab.L.robust')}${li('idx.ab.L.indep')}${li('idx.ab.L.more')}</ul>`;
}

init().catch((e) => { document.body.insertAdjacentHTML('afterbegin', `<pre style="color:#f88;padding:12px">${esc(tr('common.loadFail'))}: ${esc(e.message)}</pre>`); console.error(e); });
