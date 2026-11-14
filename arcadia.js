// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Arcadia brain-terrain demo: ① rover recon → ② brain heat map and chosen areas → ③ astronaut route.
   Data: data/arcadia/arcadia.json + images (pipeline/arcadia_export.py). Plain JS, no build step. */
'use strict';
const D = 'data/arcadia/';
const $ = (s) => document.querySelector(s);
const abs = (u) => new URL(u, location.href).href;
const S = { step: 1, loop: 10, when: 'after', markers: [] };
const C_ROVER = '#3987e5', C_ROVER_NOW = '#f2b36b', C_ROUTE = '#38e1ff', C_TGT = '#ffd23f', C_BEFORE = '#c6a6ff';

async function init() {
  S.d = await (await fetch(D + 'arcadia.json')).json();
  const im = new Image(); im.src = D + S.d.files.seen_loop; await im.decode();
  const c = document.createElement('canvas'); c.width = im.width; c.height = im.height;
  const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0);
  const px = x.getImageData(0, 0, c.width, c.height).data;
  S.seenLoop = new Uint8Array(c.width * c.height);
  for (let i = 0; i < S.seenLoop.length; i++) S.seenLoop[i] = px[4 * i];
  const v = $('#veil'); v.width = c.width; v.height = c.height; S.veilCtx = v.getContext('2d'); S.veilImg = S.veilCtx.createImageData(c.width, c.height);
  const N = S.d.rover.loops.length;
  $('#loop').max = N; $('#loop').value = N; $('#loopMax').textContent = N; S.loop = N;
  buildMap();
}

function buildMap() {
  const d = S.d, c = d.aoi_corners;
  const map = new maplibregl.Map({
    container: 'map', bounds: [[c[0][0], c[2][1]], [c[1][0], c[0][1]]], fitBoundsOptions: { padding: 40 },
    maxZoom: 20, minZoom: 10, renderWorldCopies: false, dragRotate: false, pitchWithRotate: false,
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
    img('hirise', d.files.hirise);
    img('classes', d.files.classes, { 'raster-resampling': 'nearest' });
    img('brain_all', d.files.brain_all, { 'raster-resampling': 'nearest' });
    img('brain_seen', d.files.brain_seen, { 'raster-resampling': 'nearest' });
    map.addSource('veil', { type: 'canvas', canvas: 'veil', coordinates: c, animate: false });
    map.addLayer({ id: 'veil', type: 'raster', source: 'veil', paint: { 'raster-fade-duration': 0, 'raster-resampling': 'nearest' } });
    const gj = (features) => ({ type: 'FeatureCollection', features });
    const aoi = [...c, c[0]];
    map.addSource('aoi', { type: 'geojson', data: gj([{ type: 'Feature', geometry: { type: 'LineString', coordinates: aoi } }]) });
    map.addLayer({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.2, 'line-dasharray': [3, 2] } });
    map.addSource('rover', { type: 'geojson', data: gj(d.rover.loops.map((L) => ({ type: 'Feature', properties: { id: L.id }, geometry: { type: 'LineString', coordinates: L.path } }))) });
    map.addLayer({ id: 'rover-casing', type: 'line', source: 'rover', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 4, 'line-opacity': 0.6 } });
    map.addLayer({ id: 'rover', type: 'line', source: 'rover', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': C_ROVER, 'line-width': 2 } });
    const blocks = (lst, when) => lst.map((t) => ({ type: 'Feature', properties: { id: t.id, when }, geometry: { type: 'Polygon', coordinates: [t.block] } }));
    map.addSource('tgt', { type: 'geojson', data: gj([...blocks(d.targets.after, 'after'), ...blocks(d.targets.before, 'before')]) });
    map.addLayer({ id: 'tgt', type: 'line', source: 'tgt', paint: { 'line-color': ['match', ['get', 'when'], 'after', C_TGT, C_BEFORE], 'line-width': 2.5 } });
    map.addSource('route', { type: 'geojson', data: gj(d.route.legs.map((L, i) => ({ type: 'Feature', properties: { i }, geometry: { type: 'LineString', coordinates: L.path } }))) });
    map.addLayer({ id: 'route-casing', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 6, 'line-opacity': 0.6 } });
    map.addLayer({ id: 'route', type: 'line', source: 'route', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': C_ROUTE, 'line-width': 3 } });
    map.on('click', 'route', () => showCard('整條路線', d.route.total));
    map.on('mouseenter', 'route', () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', 'route', () => { map.getCanvas().style.cursor = ''; });
    wire();
    setStep(1);
    map.once('idle', () => { window.__mapIdle = true; });
  });
}

function wire() {
  document.querySelectorAll('.steps .btn').forEach((b) => b.onclick = () => setStep(+b.dataset.step));
  document.querySelectorAll('.seg .btn').forEach((b) => b.onclick = () => { S.when = b.dataset.when; apply(); frame(); });
  $('#loop').oninput = () => { S.loop = +$('#loop').value; apply(); };
  ['#lyrImg', '#lyrCls', '#lyrHeat'].forEach((s) => $(s).onchange = apply);
}

function setStep(n) {
  S.step = n;
  $('#lyrCls').checked = false;
  $('#lyrHeat').checked = n === 2;
  if (n === 1) { S.loop = S.d.rover.loops.length; $('#loop').value = S.loop; }
  if (n === 2) S.when = 'after';
  $('#card').hidden = true;
  apply();
  frame();
}

function frame() {
  const d = S.d, c = d.aoi_corners;
  let pts = [c[0], c[2]];
  if (S.step === 2 && S.when === 'after') pts = d.rover.loops.flatMap((L) => L.path);
  if (S.step === 3) pts = d.route.legs.flatMap((L) => L.path);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  S.map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: { top: 170, bottom: 120, left: 80, right: 80 }, duration: 0, maxZoom: 17 });
}

function drawVeil(k, alpha) {
  const px = S.veilImg.data, sl = S.seenLoop;
  for (let i = 0; i < sl.length; i++) {
    const seen = sl[i] > 0 && sl[i] <= k;
    px[4 * i] = 8; px[4 * i + 1] = 6; px[4 * i + 2] = 5; px[4 * i + 3] = seen ? 0 : alpha;
  }
  S.veilCtx.putImageData(S.veilImg, 0, 0);
  const src = S.map.getSource('veil'); if (src) { src.play(); src.pause(); }
}

function vis(id, on) { S.map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); }

function apply() {
  const d = S.d, m = S.map, n = S.step;
  document.querySelectorAll('.steps .btn').forEach((b) => b.classList.toggle('active', +b.dataset.step === n));
  document.querySelectorAll('.seg .btn').forEach((b) => b.classList.toggle('active', b.dataset.when === S.when));
  $('#ctl1').hidden = n !== 1; $('#ctl2').hidden = n !== 2;
  const before = n === 2 && S.when === 'before';
  const heat = $('#lyrHeat').checked;
  vis('hirise', $('#lyrImg').checked);
  vis('classes', $('#lyrCls').checked);
  vis('brain_all', heat && (before || n === 3));
  vis('brain_seen', heat && !before && n !== 3);
  // veil: unseen ground is dimmed in ① (up to the slider's loop) and in ② after recon
  const k = n === 1 ? S.loop : d.rover.loops.length;
  const veilOn = n === 1 || (n === 2 && !before);
  if (veilOn) drawVeil(k, n === 1 ? 110 : 150);
  vis('veil', veilOn);
  vis('rover', n === 1 || (n === 2 && !before)); vis('rover-casing', n === 1);
  m.setFilter('rover', ['<=', ['get', 'id'], k]);
  m.setFilter('rover-casing', ['<=', ['get', 'id'], k]);
  m.setPaintProperty('rover', 'line-color', n === 1 ? ['case', ['==', ['get', 'id'], k], C_ROVER_NOW, C_ROVER] : C_ROVER);
  m.setPaintProperty('rover', 'line-opacity', n === 1 ? 1 : 0.45);
  m.setPaintProperty('rover', 'line-width', n === 1 ? 2 : 1.2);
  vis('tgt', n >= 2);
  m.setFilter('tgt', ['==', ['get', 'when'], before ? 'before' : 'after']);
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
  if (n === 2) {
    const lst = S.when === 'before' ? d.targets.before : d.targets.after;
    lst.forEach((t) => mk(t.stop, S.when === 'before' ? 'tgt before' : 'tgt', `${t.id} ${t.score.toFixed(2)}`));
  }
  if (n === 3) {
    const R = d.route;
    R.legs.forEach((L, i) => {
      if (L.to === 'base') return;
      const t = d.targets.after.find((x) => x.id === L.to);
      mk(t.stop, 'stop', `${i + 1}`, () => showCard(`第 ${i + 1} 站（${L.to}）：從基地到這裡，含停留`, { distance_m: L.cum.distance_m, min: L.cum.min, kcal: L.cum.kcal, o2_l: L.cum.kcal / 5 }));
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
  if (n === 1) h += it(`<i class="ln" style="background:${C_ROVER}"></i>`, '自走車路徑') + it(`<i class="ln" style="background:${C_ROVER_NOW}"></i>`, '這一趟') + it('<i style="background:#080605;opacity:.6"></i>', '還沒看過');
  if (n === 2) h += it(`<i style="border:2px solid ${S.when === 'before' ? C_BEFORE : C_TGT}"></i>`, S.when === 'before' ? '出發前選的 4 區（60 m）' : '偵察後選的 4 區（60 m）') + (S.when === 'after' ? it('<i style="background:#080605;opacity:.7"></i>', '自走車沒看過') : '');
  if (n === 3) {
    const t = d.route.total;
    h += it(`<i class="ln" style="background:${C_ROUTE}"></i>`, `太空人路線：${d.route.n_stops} 站，${(t.distance_m / 1000).toFixed(2)} km，${Math.round(t.kcal)} kcal`);
  }
  h += it('<i class="pt" style="background:#fff"></i>', '基地');
  $('#legend').innerHTML = h;
}

init();
