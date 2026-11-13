/* Marswalk Recon — Step 1 scout-rover recon replay. Plain JS, no build step.
   Data: data/jezero/scene.json (map layers) + data/jezero/recon/recon.json (simulation output).
   The reveal ("scratch-off") is computed in the browser from reveal_t.png: a 2 m cell is shown in HiRISE
   once the replay time passes the step at which the simulated rover first observed it. */
'use strict';
const R_MARS = 3396190, DEG = Math.PI / 180;
const SCENE = 'jezero', BASE = `data/${SCENE}/`, RB = BASE + 'recon/';
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const abs = (u) => new URL(u, location.href).href;
const pct = (v, d = 1) => v == null ? '–' : (v * 100).toFixed(d) + '%';
const S = { T: 0, loop: 0, playing: false, view: 'recon', revealT: null, imgs: {}, lastDrawT: -1 };

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); }
async function bitmap(u) {
  const b = await (await fetch(u)).blob();
  return createImageBitmap(b, { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
}

async function init() {
  const [sc, rc] = await Promise.all([getJSON(BASE + 'scene.json'), getJSON(RB + 'recon.json')]);
  S.sc = sc; S.rc = rc; S.N = rc.loops.length;
  const [tImg, hImg, cRef, cPri] = await Promise.all([bitmap(RB + rc.files.reveal_t), bitmap(RB + rc.files.hirise), bitmap(RB + rc.files.class_ref), bitmap(RB + rc.files.class_prior)]);
  S.imgs = { hirise: hImg, cref: cRef, cpri: cPri };
  const c = document.createElement('canvas'); c.width = tImg.width; c.height = tImg.height;
  const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(tImg, 0, 0);
  const d = x.getImageData(0, 0, c.width, c.height).data;
  const n = c.width * c.height, tt = new Uint32Array(n);
  for (let i = 0; i < n; i++) tt[i] = (d[4 * i] << 16) | (d[4 * i + 1] << 8) | d[4 * i + 2];
  S.revealT = tt; S.tw = c.width; S.th = c.height;
  S.mask = document.createElement('canvas'); S.mask.width = c.width; S.mask.height = c.height;
  S.maskCtx = S.mask.getContext('2d'); S.maskData = S.maskCtx.createImageData(c.width, c.height);
  S.tmp = document.createElement('canvas'); S.tmp.width = c.width; S.tmp.height = c.height;
  buildMap();
  $('#loop').max = S.N; $('#loopN').textContent = S.N;
  $('#loop').oninput = () => { stop(); setLoop(+$('#loop').value); };
  $('#prev').onclick = () => { stop(); setLoop(Math.max(0, S.loop - 1)); };
  $('#next').onclick = () => { stop(); setLoop(Math.min(S.N, S.loop + 1)); };
  $('#play').onclick = () => (S.playing ? stop() : play());
  document.querySelectorAll('input[name=view]').forEach((r) => r.onchange = () => { S.view = r.value; applyView(); });
  $('#showClasses').onchange = applyView; $('#showAll').onchange = () => drawPaths(); $('#showReplans').onchange = () => drawEvents();
  $('#aboutBtn').onclick = () => { renderAbout(); $('#about').showModal(); };
  renderChart(); renderTable(); renderChecks(); renderParams();
}

function buildMap() {
  const sc = S.sc, c = S.rc.aoi_corners;
  const bounds = [[c[0][0], c[2][1]], [c[1][0], c[0][1]]];
  const map = new maplibregl.Map({
    container: 'map', bounds, fitBoundsOptions: { padding: 30 }, maxZoom: 20, minZoom: 9, renderWorldCopies: false,
    dragRotate: false, pitchWithRotate: false,
    style: { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0d0b0a' } }] },
    attributionControl: { compact: true, customAttribution: 'NASA/JPL-Caltech/UArizona (HiRISE), NASA/JPL-Caltech/MSSS (CTX), USGS Astrogeology. Rover route: simulated.' },
  });
  S.map = map; window.__mapIdle = false;
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.on('load', () => {
    const L = (id) => sc.layers.find((l) => l.id === id);
    const ctx = L('ctx_ortho'), hs = L('ctx_hillshade'), ho = L('hirise_ortho');
    map.addSource('ctx', { type: 'image', url: abs(BASE + ctx.url), coordinates: ctx.coordinates });
    map.addLayer({ id: 'ctx', type: 'raster', source: 'ctx', paint: { 'raster-fade-duration': 0, 'raster-brightness-max': 0.7, 'raster-saturation': -0.3 } });
    map.addSource('ctxhs', { type: 'image', url: abs(BASE + hs.url), coordinates: hs.coordinates });
    map.addLayer({ id: 'ctxhs', type: 'raster', source: 'ctxhs', paint: { 'raster-opacity': 0.35, 'raster-fade-duration': 0 } });
    map.addSource('hfull', { type: 'raster', tiles: [abs(BASE) + ho.url], tileSize: 256, minzoom: ho.minzoom, maxzoom: ho.maxzoom, bounds: ho.bounds });
    map.addLayer({ id: 'hfull', type: 'raster', source: 'hfull', layout: { visibility: 'none' }, paint: { 'raster-fade-duration': 0 } });
    map.addSource('reveal', { type: 'canvas', canvas: 'revealCanvas', coordinates: c, animate: false });
    map.addLayer({ id: 'reveal', type: 'raster', source: 'reveal', paint: { 'raster-fade-duration': 0, 'raster-resampling': 'linear' } });
    map.addSource('classes', { type: 'canvas', canvas: 'classCanvas', coordinates: c, animate: false });
    map.addLayer({ id: 'classes', type: 'raster', source: 'classes', layout: { visibility: 'none' }, paint: { 'raster-opacity': 0.8, 'raster-fade-duration': 0, 'raster-resampling': 'nearest' } });
    map.addSource('aoi', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [...c, c[0]] } } });
    map.addLayer({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.2, 'line-dasharray': [3, 2] } });
    map.addSource('paths', { type: 'geojson', data: fc([]) });
    const col = ['match', ['get', 'mode'], 'out', '#3987e5', 'return', '#d95926', '#199e70'];
    map.addLayer({ id: 'paths-casing', type: 'line', source: 'paths', layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#000', 'line-opacity': ['case', ['get', 'cur'], 0.7, 0], 'line-width': ['case', ['get', 'cur'], 5, 0] } });
    map.addLayer({ id: 'paths', type: 'line', source: 'paths', filter: ['!=', ['get', 'mode'], 'forced'], layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': col, 'line-opacity': ['case', ['get', 'cur'], 1, 0.45], 'line-width': ['case', ['get', 'cur'], 2.6, 0.8] } });
    map.addLayer({ id: 'paths-forced', type: 'line', source: 'paths', filter: ['==', ['get', 'mode'], 'forced'],
      paint: { 'line-color': col, 'line-opacity': ['case', ['get', 'cur'], 1, 0.45], 'line-width': ['case', ['get', 'cur'], 2.6, 0.8], 'line-dasharray': [2, 1.2] } });
    map.addSource('events', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'replans', type: 'circle', source: 'events', filter: ['==', ['get', 'type'], 'replan'],
      paint: { 'circle-radius': 2.2, 'circle-color': '#fff', 'circle-opacity': 0.7, 'circle-stroke-width': 0 } });
    map.addLayer({ id: 'events', type: 'circle', source: 'events', filter: ['!=', ['get', 'type'], 'replan'],
      paint: { 'circle-radius': ['match', ['get', 'type'], 'goal', 8, 6], 'circle-stroke-color': ['match', ['get', 'type'], 'goal', '#ffffff', '#000000'], 'circle-stroke-width': ['match', ['get', 'type'], 'goal', 2.5, 1.5],
        'circle-color': ['match', ['get', 'type'], 'goal', 'rgba(0,0,0,0)', 'safety_return', '#e0625a', '#e9b949'] } });
    map.addSource('sense', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'sense', type: 'line', source: 'sense', paint: { 'line-color': '#fff', 'line-width': 1.2, 'line-opacity': 0.9 } });
    map.addSource('rover', { type: 'geojson', data: fc([]) });
    map.addLayer({ id: 'rover', type: 'circle', source: 'rover', paint: { 'circle-radius': 5, 'circle-color': '#ffffff', 'circle-stroke-color': '#000', 'circle-stroke-width': 2.5 } });
    const b = S.rc.base;
    map.addSource('base', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [b.lon, b.lat] } } });
    map.addLayer({ id: 'base', type: 'circle', source: 'base', paint: { 'circle-radius': 8, 'circle-color': '#e8743b', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
    const pop = new maplibregl.Popup({ closeButton: false, offset: 8 });
    map.on('mouseenter', 'events', (e) => { const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(eventText(p)).addTo(map); });
    map.on('mouseleave', 'events', () => pop.remove());
    map.on('mouseenter', 'base', (e) => pop.setLngLat(e.lngLat).setHTML(`<b>Habitat (base)</b> <span class="badge assumed">assumed</span><br>Every loop starts and ends here.`).addTo(map));
    map.on('mouseleave', 'base', () => pop.remove());
    map.on('move', updateScale); map.on('mousemove', (e) => showCoords(e.lngLat));
    map.once('idle', () => { window.__mapIdle = true; });
    updateScale(); setLoop(0); applyView();
  });
}

const fc = (f) => ({ type: 'FeatureCollection', features: f });
function eventText(p) {
  const name = { goal: 'Loop goal', turn_back: 'Turned back: planned cost home would not fit the planning budget', return_direct: 'Return switched to the cheapest known route',
    safety_return: 'Reserve rule: going home over terrain already seen', goal_unreachable: 'Goal found unreachable' }[p.type] || p.type;
  return `<b>Loop ${p.loop}</b> · ${esc(name)}${p.spent != null ? `<br>energy spent so far ${(+p.spent).toFixed(0)} units` : ''}`;
}

/* ---------- time ---------------------------------------------------------------------------- */
function loopAtT(T) { for (const L of S.rc.loops) if (T <= L.t1) return L; return S.rc.loops[S.N - 1]; }
function setLoop(k) {
  S.loop = k; S.T = k === 0 ? 0 : S.rc.loops[k - 1].t1;
  $('#loop').value = k; refresh();
}
function setT(T) {
  S.T = T;
  const L = T === 0 ? null : loopAtT(T);
  S.loop = L ? (T >= L.t1 ? L.id : L.id) : 0;
  $('#loop').value = S.loop; refresh();
}
function play() {
  if (S.loop >= S.N) setLoop(0);
  S.playing = true; $('#play').textContent = '❚❚ Pause';
  const L0 = S.rc.loops[Math.min(S.loop, S.N - 1)];
  if (S.T >= L0.t1 || S.loop === 0) S.T = S.loop === 0 ? 0 : S.rc.loops[S.loop - 1].t1;
  let last = performance.now();
  S.map.getSource('reveal').play();
  const step = (now) => {
    if (!S.playing) return;
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    const T = Math.min(S.rc.t_max, S.T + dt * +$('#speed').value);
    setT(Math.round(T));
    if (T >= S.rc.t_max) { stop(); return; }
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function stop() {
  S.playing = false; $('#play').textContent = '▶ Play';
  const s = S.map && S.map.getSource('reveal'); if (s) { s.play(); setTimeout(() => s.pause(), 60); }
  const c = S.map && S.map.getSource('classes'); if (c) { c.play(); setTimeout(() => c.pause(), 60); }
}

function refresh() {
  drawReveal(); drawPaths(); drawEvents(); drawRover(); renderLoopCard(); renderHud(); highlightChart(); renderTable();
  if (!S.playing) { const s = S.map.getSource('reveal'); if (s) { s.play(); setTimeout(() => s.pause(), 60); } const c = S.map.getSource('classes'); if (c) { c.play(); setTimeout(() => c.pause(), 60); } }
  $('#loopLbl').textContent = S.loop;
  $('#loopHint').textContent = S.loop === 0 ? '(before departure: only the orbital prior)' : (S.playing ? '(replaying)' : '(state after this loop)');
}

/* ---------- scratch-off compositing ----------------------------------------------------------- */
function drawReveal() {
  if (S.lastDrawT === S.T && !S.forceDraw) return;
  S.lastDrawT = S.T; S.forceDraw = false;
  const T = S.T, tt = S.revealT, d = S.maskData.data, all = S.view === 'all';
  for (let i = 0, n = tt.length; i < n; i++) d[4 * i + 3] = (all || tt[i] <= T) ? 255 : 0;
  S.maskCtx.putImageData(S.maskData, 0, 0);
  const cv = $('#revealCanvas'), x = cv.getContext('2d');
  x.globalCompositeOperation = 'source-over'; x.clearRect(0, 0, cv.width, cv.height);
  x.imageSmoothingEnabled = false; x.drawImage(S.mask, 0, 0, cv.width, cv.height);
  x.globalCompositeOperation = 'source-in'; x.imageSmoothingEnabled = true; x.drawImage(S.imgs.hirise, 0, 0, cv.width, cv.height);
  x.globalCompositeOperation = 'source-over';
  // belief classes = prior everywhere, reference where revealed
  const cc = $('#classCanvas'), y = cc.getContext('2d'), t2 = S.tmp.getContext('2d');
  y.clearRect(0, 0, cc.width, cc.height); y.drawImage(S.imgs.cpri, 0, 0);
  t2.globalCompositeOperation = 'source-over'; t2.clearRect(0, 0, S.tmp.width, S.tmp.height); t2.drawImage(S.mask, 0, 0);
  t2.globalCompositeOperation = 'source-in'; t2.drawImage(S.imgs.cref, 0, 0); t2.globalCompositeOperation = 'source-over';
  // where revealed, the prior colour must be replaced, not blended: punch it out first
  y.globalCompositeOperation = 'destination-out'; y.drawImage(S.mask, 0, 0); y.globalCompositeOperation = 'source-over';
  y.drawImage(S.tmp, 0, 0);
}

function partial(seg, T) {
  const c = [];
  for (let i = 0; i < seg.t.length; i++) {
    if (seg.t[i] <= T) { c.push(seg.c[i]); continue; }
    if (i > 0) { const f = (T - seg.t[i - 1]) / (seg.t[i] - seg.t[i - 1]); c.push([seg.c[i - 1][0] + f * (seg.c[i][0] - seg.c[i - 1][0]), seg.c[i - 1][1] + f * (seg.c[i][1] - seg.c[i - 1][1])]); }
    break;
  }
  return c;
}
function drawPaths() {
  if (!S.map.getSource('paths')) return;
  const T = S.T, cur = S.loop, showAll = $('#showAll').checked, feats = [];
  for (const L of S.rc.loops) {
    if (L.t0 >= T && T > 0) break;
    if (T === 0) break;
    const isCur = L.id === (S.playing ? loopAtT(T).id : cur);
    if (!showAll && !isCur) continue;
    for (const s of L.segments) {
      const c = partial(s, T); if (c.length < 2) continue;
      feats.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: c }, properties: { mode: s.mode, loop: L.id, cur: isCur } });
    }
  }
  S.map.getSource('paths').setData(fc(feats));
}
function drawEvents() {
  if (!S.map.getSource('events')) return;
  const T = S.T, feats = [];
  if (T > 0) {
    const L = S.playing ? loopAtT(T) : S.rc.loops[S.loop - 1];
    if (L) {
      feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: L.goal }, properties: { type: 'goal', loop: L.id } });
      for (const e of L.events) {
        if (e.t > T || e.type === 'goal_reached') continue;
        if (e.type === 'replan' && !$('#showReplans').checked) continue;
        feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [e.lon, e.lat] }, properties: { ...e, loop: L.id } });
      }
    }
  }
  S.map.getSource('events').setData(fc(feats));
}
function roverPos(T) {
  if (T === 0) return [S.rc.base.lon, S.rc.base.lat];
  const L = loopAtT(T);
  for (const s of L.segments) if (s.t[0] <= T && T <= s.t[s.t.length - 1]) { const c = partial(s, T); return c[c.length - 1]; }
  return [S.rc.base.lon, S.rc.base.lat];
}
function drawRover() {
  if (!S.map.getSource('rover')) return;
  const p = roverPos(S.T), r = S.rc.params.sense_radius_m, k = Math.cos(p[1] * DEG), ring = [];
  for (let a = 0; a <= 360; a += 10) ring.push([p[0] + (r * Math.cos(a * DEG)) / (R_MARS * k) / DEG, p[1] + (r * Math.sin(a * DEG)) / R_MARS / DEG]);
  S.map.getSource('rover').setData(fc([{ type: 'Feature', geometry: { type: 'Point', coordinates: p } }]));
  S.map.getSource('sense').setData(fc([{ type: 'Feature', geometry: { type: 'LineString', coordinates: ring } }]));
}

function applyView() {
  if (!S.map || !S.map.getLayer('hfull')) return;
  const all = S.view === 'all';
  S.map.setLayoutProperty('hfull', 'visibility', all ? 'visible' : 'none');
  S.map.setLayoutProperty('reveal', 'visibility', all ? 'none' : 'visible');
  S.map.setLayoutProperty('classes', 'visibility', $('#showClasses').checked ? 'visible' : 'none');
  S.forceDraw = true; refresh();
  $('#review').textContent = all ? 'View all data: full HiRISE reference terrain (not what the rover knows)' : 'Simulated rover · parameters proposed · review: pending';
}

/* ---------- panels ------------------------------------------------------------------------------ */
function renderHud() {
  const T = S.T;
  const L = T === 0 ? null : loopAtT(T);
  const obs = S.loop === 0 && !S.playing ? S.rc.loops[0] && 0 : null;
  const obsFrac = coveredAt(T);
  $('#hud').innerHTML = L ? `Loop <b>${L.id}</b> · step <b>${T - L.t0}</b> / ${L.t1 - L.t0}<br>Scratched off so far: <b>${pct(obsFrac)}</b> of study area`
    : `Before departure · the rover knows only the CTX prior (20 m)<br>Scratched off: <b>${pct(obsFrac)}</b> (around the habitat)`;
}
function coveredAt(T) { // cheap: count from the reveal raster
  let n = 0; const tt = S.revealT; for (let i = 0; i < tt.length; i += 7) if (tt[i] <= T) n++;
  return n / Math.ceil(S.revealT.length / 7);
}
function renderLoopCard() {
  if (S.loop === 0) {
    $('#loopCard').innerHTML = `<div class="card"><h4>Before departure</h4><p class="hint" style="margin:0">The rover plans on the CTX prior: ${pct(S.rc.initial_belief_agrees_with_reference_frac)} of cells already carry the same terrain class as the HiRISE reference; it cannot see sand or small rough patches yet. Press Play or move the slider.</p></div>`;
    return;
  }
  const L = S.rc.loops[S.loop - 1], P = S.rc.params, B = L.budget, plan = B * P.planning_frac;
  const ev = [L.n_turn_back ? `${L.n_turn_back} turn-back` : '', L.n_return_direct ? `${L.n_return_direct} return switched to cheapest route` : '', L.n_safety_return ? `${L.n_safety_return} reserve rule` : ''].filter(Boolean).join(', ') || 'none';
  $('#loopCard').innerHTML = `<div class="card"><h4><span>Loop ${L.id}</span><span class="badge simulated">simulated</span></h4>
<div class="bar" title="energy used of the loop budget"><div class="fill" style="width:${(100 * L.cost_total / B).toFixed(1)}%"></div><div class="mark" style="left:${(100 * plan / B).toFixed(1)}%"></div></div>
<div class="barlbl"><span>energy ${L.cost_total.toFixed(0)} / ${B.toFixed(0)} units</span><span>| planning limit ${plan.toFixed(0)}</span></div>
<div class="kv" style="margin-top:6px">
<span>Distance driven</span><span>${(L.length_m / 1000).toFixed(2)} km</span>
<span>New area observed</span><span>${(L.new_observed_m2 / 1e4).toFixed(1)} ha</span>
<span>Study area observed (total)</span><span>${pct(L.observed_frac_aoi)}</span>
<span>Return on the outbound track</span><span>${pct(L.overlap_ratio, 0)}</span>
<span>Goal reached</span><span>${L.goal_reached ? 'yes' : 'no (turned back)'}</span>
<span>Replans (hazard / ×2 cost ahead)</span><span>${L.n_replan}</span>
<span>Belief map = reference</span><span>${pct(L.belief_agrees_with_reference_frac)}</span>
</div><p class="hint" style="margin-top:4px">Forced-return events: ${esc(ev)}</p><p class="hint">1 energy unit = 1 m on firm ground (rough ×2.5, sand ×6; assumed). "Return on the outbound track" = share of the way home within 6 m of the way out (excluding 30 m around the habitat).</p></div>`;
}

function renderChart() {
  const Ls = S.rc.loops, W = 300, H = 120, pl = 30, pb = 18, pt = 6, n = Ls.length;
  const ymax = Math.max(0.05, Math.ceil(Math.max(...Ls.map((l) => l.observed_frac_aoi)) * 20) / 20);
  const bw = (W - pl - 4) / n;
  let s = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
  for (let g = 0; g <= ymax + 1e-9; g += ymax / 2) {
    const y = pt + (H - pt - pb) * (1 - g / ymax);
    s += `<line x1="${pl}" x2="${W}" y1="${y}" y2="${y}" stroke="#3a312a" stroke-width="0.6"/><text x="${pl - 4}" y="${y + 3}" fill="#a8998b" font-size="8" text-anchor="end">${Math.round(g * 100)}%</text>`;
  }
  Ls.forEach((l, i) => {
    const h = (H - pt - pb) * l.observed_frac_aoi / ymax, x = pl + i * bw + 1;
    s += `<rect data-i="${i}" x="${x}" y="${H - pb - h}" width="${Math.max(1, bw - 2)}" height="${h}" rx="1.5" fill="#d6a24f"/>`;
    s += `<rect data-i="${i}" class="hit" x="${x - 1}" y="${pt}" width="${bw}" height="${H - pt - pb}" fill="transparent"/>`;
  });
  s += `<line x1="${pl}" x2="${W}" y1="${H - pb}" y2="${H - pb}" stroke="#a8998b" stroke-width="0.8"/>`;
  [1, Math.ceil(n / 2), n].forEach((k) => { s += `<text x="${pl + (k - 0.5) * bw}" y="${H - 5}" fill="#a8998b" font-size="8" text-anchor="middle">${k}</text>`; });
  s += `</svg><div class="tip" hidden></div>`;
  const el = $('#chart'); el.innerHTML = s;
  const tip = $('.tip', el);
  el.querySelectorAll('rect.hit').forEach((r) => {
    r.onmouseenter = () => { const l = Ls[+r.dataset.i], bb = r.getBoundingClientRect(), eb = el.getBoundingClientRect();
      tip.hidden = false; tip.style.left = (bb.left - eb.left + bb.width / 2) + 'px'; tip.style.top = '30px';
      tip.innerHTML = `Loop ${l.id}: ${pct(l.observed_frac_aoi)} observed (+${(l.new_observed_m2 / 1e4).toFixed(1)} ha)`; };
    r.onmouseleave = () => { tip.hidden = true; };
    r.onclick = () => { stop(); setLoop(+r.dataset.i + 1); };
    r.style.cursor = 'pointer';
  });
}
function highlightChart() {
  $('#chart').querySelectorAll('rect:not(.hit)').forEach((r) => r.setAttribute('fill', +r.dataset.i === S.loop - 1 ? '#f2b36b' : '#8a6a3a'));
}
function renderTable() {
  let h = '<table><tr><th>loop</th><th>energy</th><th>km</th><th>new ha</th><th>total</th><th>overlap</th><th>replan</th><th>forced</th></tr>';
  S.rc.loops.forEach((l) => {
    h += `<tr class="${l.id === S.loop ? 'cur' : ''}"><td>${l.id}</td><td>${l.cost_total.toFixed(0)}</td><td>${(l.length_m / 1000).toFixed(2)}</td><td>${(l.new_observed_m2 / 1e4).toFixed(1)}</td><td>${pct(l.observed_frac_aoi)}</td><td>${pct(l.overlap_ratio, 0)}</td><td>${l.n_replan}</td><td>${l.n_turn_back + l.n_return_direct + l.n_safety_return}</td></tr>`;
  });
  $('#table').innerHTML = h + '</table>';
}
function renderChecks() {
  const Ls = S.rc.loops, B = S.rc.params.loop_budget;
  const ov = Ls.map((l) => l.overlap_ratio).filter((v) => v != null).sort((a, b) => a - b);
  const med = ov.length ? ov[Math.floor((ov.length - 1) / 2)] : null;
  const ok = (v) => v ? '<span class="pass">pass</span>' : '<span class="fail">fail</span>';
  const maxc = Math.max(...Ls.map((l) => l.cost_total));
  const ac = S.rc.acceptance || {};
  $('#checks').innerHTML = `<table>
<tr><td>Every loop starts and ends at the habitat</td><td>${ac.start_end_at_base == null ? '–' : ok(ac.start_end_at_base)}</td></tr>
<tr><td>No loop over its energy budget (max ${maxc.toFixed(0)} / ${B})</td><td>${ok(maxc <= B)}</td></tr>
<tr><td>Never drives onto impassable reference terrain</td><td>${ac.no_impassable == null ? '–' : ok(ac.no_impassable)}</td></tr>
<tr><td>Planner never read reference terrain it had not observed</td><td>${ac.no_unobserved_reads == null ? '–' : ok(ac.no_unobserved_reads)}</td></tr>
<tr><td>Median return-on-outbound-track &lt; 30% (MVP target)</td><td>${pct(med, 0)} ${med == null ? '' : ok(med < 0.3)}</td></tr>
</table><p class="hint">Checked by the pipeline tests (app/tests/test_recon.py) on the exported loops.</p>`;
}
function renderParams() {
  const P = S.rc.params, TP = S.rc.terrain_params;
  const rows = [
    ['Loop energy budget', `${P.loop_budget} units (planning ${Math.round(P.planning_frac * 100)}%, reserve ${Math.round((1 - P.planning_frac) * 100)}%)`],
    ['Sensing radius', `${P.sense_radius_m} m`], ['Cost per metre firm / rough / sand', `${P.cost_factor.firm} / ${P.cost_factor.rough} / ${P.cost_factor.sand}`],
    ['Revisit penalty on the way home', `×${1 + P.revisit_penalty}`], ['Home margin (floor; learned above it)', `×${P.home_margin}`],
    P.goal_rule === 'v2_sector_band'
      ? ['Goal rule (v2)', `8 sectors in turn (${P.sector_order.join(', ')}); distance bands near 100–600 m, mid 600–1200 m, far >1200 m (8 loops each); most unseen area; cost ≤ ${Math.round(P.outbound_frac * 100)}% of planning budget`]
      : ['Goal distance', `${Math.round(P.goal_min_frac * 100)}–${Math.round(P.outbound_frac * 100)}% of planning budget`],
    ['Slope baseline / rough / rover-blocked', `${TP.slope_baseline_m} m / ≥${TP.slope_rough_deg}° / ≥${TP.slope_block_rover_deg}°`],
    TP.sand_method ? ['Sand', 'sand-field indicator v2: ripple-field texture over tens of metres, fixed thresholds (needs a person to confirm)']
      : ['Sand', `ripple index ≥ P${TP.ripple_percentile} (needs a person to confirm)`],
  ];
  $('#params').innerHTML = '<table>' + rows.map((r) => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td></tr>`).join('') + '</table><p class="hint"><span class="badge assumed">assumed</span> All values are proposals waiting to be locked; none was tuned on route comparisons.</p>';
}

function marsDist(a, b) { const dlat = (b.lat - a.lat) * DEG, dlon = (b.lng - a.lng) * DEG; const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * DEG) * Math.cos(b.lat * DEG) * Math.sin(dlon / 2) ** 2; return 2 * R_MARS * Math.asin(Math.sqrt(h)); }
function updateScale() {
  const m = S.map, H = m.getContainer().clientHeight, maxPx = 120, a = m.unproject([20, H - 40]), b = m.unproject([20 + maxPx, H - 40]);
  const d = marsDist(a, b), pow = 10 ** Math.floor(Math.log10(d)), n = d / pow, nice = (n >= 5 ? 5 : n >= 2 ? 2 : 1) * pow;
  $('#scaleBar').style.width = (maxPx * nice / d) + 'px'; $('#scaleLabel').textContent = (nice >= 1000 ? nice / 1000 + ' km' : nice + ' m') + ' (Mars)';
}
function showCoords(ll) {
  const b = S.rc.base, k = Math.cos(b.lat * DEG);
  const x = (ll.lng - b.lon) * DEG * R_MARS * k, y = (ll.lat - b.lat) * DEG * R_MARS;
  $('#coords').innerHTML = `${ll.lat.toFixed(5)}°N ${ll.lng.toFixed(5)}°E<br>x ${x.toFixed(0)} m E, y ${y.toFixed(0)} m N of base`;
}
function renderAbout() {
  const P = S.rc.params;
  $('#aboutBody').innerHTML = `<h2>Step 1 · Scout rover recon — how it works</h2>
<p><b>The rover is simulated.</b> Its loops are produced by our planner; it is not Perseverance and does not follow Perseverance's route. Perseverance's own measurements are not used on this page.</p>
<h3>What the rover knows</h3>
<ul><li><b>Before leaving</b> it has only orbital data available to any mission planner: the CTX terrain model (20 m) and image. Terrain classes from it: firm / rough / blocked by slope. CTX cannot show sand ripples.</li>
<li><b>While driving</b> it "scratches off" a disc of ${P.sense_radius_m} m around itself. Inside that disc the map switches to the <i>HiRISE reference terrain</i> (1 m terrain model, 0.25 m image). HiRISE is also orbital: it stands in for what the rover's own cameras would measure (simulated sensing). It is not ground truth.</li>
<li>The planner never reads HiRISE values it has not scratched off (enforced in code and tested).</li></ul>
<h3>One loop</h3>
<ol><li>Pick a goal (rule v2): the eight compass sectors take turns (N, S, E, W, NE, SW, SE, NW), and distance bands near 100–600 m, mid 600–1200 m, far &gt;1200 m take turns every eight loops; within that sector and band, the goal with the most unexplored area around it, at most ${Math.round(P.outbound_frac * 100)}% of the planning budget away. Terrain only: no science value and no Perseverance data are used.</li>
<li>Drive there on its current map. If a newly seen cell ahead is impassable or twice as costly as expected, replan.</li>
<li>Turn back by itself when (energy spent + planned cost home × margin) reaches the planning budget. The margin starts at ×${P.home_margin} and is raised to how much more the terrain has cost than the orbital map predicted.</li>
<li>Go home a different way: cells already seen cost ×${1 + P.revisit_penalty} on the way back.</li>
<li>Reserve rule (guarantee): it keeps enough energy to get home over terrain it has <i>already seen</i> (hard rule; tested: no loop of the recorded run exceeds its budget). When that margin runs out, it goes home that way (dashed green). So no loop can exceed its budget.</li></ol>
<h3>Labels</h3><p><span class="badge simulated">simulated</span> rover routes, events and statistics · <span class="badge assumed">assumed</span> budget, costs, radius, thresholds (proposed, review pending) · <span class="badge measured">measured</span> HiRISE and CTX data (orbital).</p>
<h3>Limitations</h3><ul><li>Terrain classes are a heuristic from slope, roughness and an image texture index; the sand class in particular (heuristic, not yet reviewed) still needs a person to check it.</li>
<li>Rover energy units are relative (1 = 1 m of firm ground), not watt-hours.</li>
<li>Budget, cost factors (firm 1, rough 2.5, sand 6) and the 15 m sensing radius are assumptions locked before the run. With sand now about 40% of the reference terrain the rover rarely gets beyond ~600 m from the habitat; this is reported as is, not tuned away.</li>
<li>The first run of this rule had a defect (5 loops ended 1.3–4.8 units over budget). It was fixed (the reserve rule keeps a margin of two steps instead of one) and the simulation was re-run once; this page shows the rerun. Both runs are listed in DATA_LOG.</li>
<li>The big difference between what the rover saw and the orbital prior comes from data resolution (CTX 20 m vs HiRISE 1 m), not from cleverness of the rover.</li></ul>`;
}

init().catch((e) => { document.body.insertAdjacentHTML('afterbegin', `<pre style="color:#f88;padding:12px">Failed to load: ${esc(e.message)}</pre>`); console.error(e); });
