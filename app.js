/* Marswalk Recon — checkpoint 1 viewer. Plain JS, no build step. Data: data/<scene>/scene.json.
   MapLibre only draws: Mars lon/lat are fed in as map coordinates; all distances use the Mars sphere. */
'use strict';
const R_MARS = 3396190;              // m, Mars 2015 sphere used by every source product
const DEG = Math.PI / 180;
const S = { map: null, map2: null, scene: null, sceneId: null, photos: null, swipe: false, swipeX: 0.5 };
const $ = (s, el = document) => el.querySelector(s);
const abs = (u) => new URL(u, location.href).href;
const fmtBytes = (b) => b == null ? '' : b > 1e6 ? (b / 1e6).toFixed(1) + ' MB' : (b / 1e3).toFixed(0) + ' kB';
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

async function getJSON(u) { const r = await fetch(u); if (!r.ok) throw new Error(`${u}: ${r.status}`); return r.json(); }

async function init() {
  const idx = await getJSON('data/scenes.json');
  const nav = $('#scenes');
  idx.scenes.forEach((s) => {
    const b = document.createElement('button');
    b.className = 'btn'; b.dataset.scene = s.id;
    b.innerHTML = esc(s.title) + (s.status && s.status !== 'active' ? `<span class="tag">(${esc(s.status)})</span>` : '');
    b.title = s.subtitle || '';
    b.onclick = () => { location.hash = s.id; };
    nav.appendChild(b);
  });
  window.addEventListener('hashchange', () => loadScene(location.hash.slice(1)));
  const first = location.hash.slice(1) || idx.scenes[0].id;
  await loadScene(first);
  $('#aboutBtn').onclick = () => { renderAbout(); $('#about').showModal(); };
  $('#photoClose').onclick = () => { $('#photoPanel').hidden = true; S.map && S.map.resize(); };
  document.querySelectorAll('[data-preset]').forEach((b) => b.onclick = () => preset(b.dataset.preset));
}

function emptyStyle() {
  return { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#0d0b0a' } }] };
}

function rasterSource(L, base) {
  if (L.kind === 'tiles') return { type: 'raster', tiles: [abs(base) + L.url], tileSize: 256, minzoom: L.minzoom, maxzoom: L.maxzoom, bounds: L.bounds };
  return { type: 'image', url: abs(base + L.url), coordinates: L.coordinates };
}

async function loadScene(id) {
  if (!id || id === S.sceneId) return;
  const base = `data/${id}/`;
  const sc = await getJSON(base + 'scene.json');
  S.scene = sc; S.sceneId = id; S.base = base; S.photos = null;
  document.querySelectorAll('#scenes .btn').forEach((b) => b.classList.toggle('active', b.dataset.scene === id));
  $('#photoPanel').hidden = true;
  if (S.map) { S.map.remove(); S.map = null; }
  if (S.map2) { S.map2.remove(); S.map2 = null; }
  setSwipe(false);
  const c = sc.aoi.corners;
  const bounds = [[c[0][0], c[2][1]], [c[1][0], c[0][1]]];
  const map = new maplibregl.Map({
    container: 'map', style: emptyStyle(), bounds, fitBoundsOptions: { padding: 30 }, maxZoom: 21, minZoom: 5,
    renderWorldCopies: false, dragRotate: false, pitchWithRotate: false,
    attributionControl: { compact: true, customAttribution: 'Mars data: NASA/JPL-Caltech/UArizona (HiRISE), NASA/JPL-Caltech/MSSS (CTX), USGS Astrogeology, NASA JPL Mars Trek. Display uses MapLibre Web Mercator; distances use the Mars sphere.' },
  });
  S.map = map; window.__mapIdle = false;
  map.once('idle', () => { window.__mapIdle = true; });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
  map.on('load', () => {
    sc.layers.forEach((L) => {
      map.addSource(L.id, rasterSource(L, base));
      map.addLayer({ id: L.id, type: 'raster', source: L.id, layout: { visibility: L.visible ? 'visible' : 'none' },
        paint: { 'raster-opacity': L.opacity, 'raster-fade-duration': 0, 'raster-resampling': 'linear' } });
    });
    addVectors(map, sc, base);
    updateScale();
  });
  map.on('move', () => { updateScale(); syncMap2(); });
  map.on('mousemove', (e) => showCoords(e.lngLat));
  renderPanel(sc);
  renderChecks(sc);
  $('#review').textContent = `Positioning & terrain reading: ${sc.review}`;
}

function addVectors(map, sc, base) {
  const c = sc.aoi.corners;
  map.addSource('aoi', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [...c, c[0]] } } });
  map.addLayer({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.5, 'line-dasharray': [3, 2] } });
  if (sc.rover) {
    map.addSource('traverse', { type: 'geojson', data: abs(base + sc.rover.traverse.url) });
    map.addLayer({ id: 'traverse-casing', type: 'line', source: 'traverse', paint: { 'line-color': '#000', 'line-width': 4, 'line-opacity': 0.5 } });
    map.addLayer({ id: 'traverse', type: 'line', source: 'traverse', paint: { 'line-color': '#5fd3f3', 'line-width': 2 } });
    map.addSource('waypoints', { type: 'geojson', data: abs(base + sc.rover.waypoints.url) });
    map.addLayer({ id: 'waypoints', type: 'circle', source: 'waypoints', paint: { 'circle-radius': 3, 'circle-color': '#5fd3f3', 'circle-stroke-color': '#000', 'circle-stroke-width': 1 } });
    getJSON(base + sc.rover.photos.url).then((ph) => {
      S.photos = ph;
      const fc = { type: 'FeatureCollection', features: ph.waypoints.map((w) => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [w.lon, w.lat] }, properties: { id: w.id, sol: w.sol, n: w.images.length } })) };
      map.addSource('photos', { type: 'geojson', data: fc });
      map.addLayer({ id: 'photos', type: 'circle', source: 'photos', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 13, 4, 18, 8], 'circle-color': '#ffd166', 'circle-stroke-color': '#3a1d00', 'circle-stroke-width': 1.5 } });
      const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
      map.on('mouseenter', 'photos', (e) => { map.getCanvas().style.cursor = 'pointer'; const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(`Waypoint ${esc(p.id)} · Sol ${p.sol}<br>${p.n} Perseverance photo(s) — click`).addTo(map); });
      map.on('mouseleave', 'photos', () => { map.getCanvas().style.cursor = ''; pop.remove(); });
      map.on('click', 'photos', (e) => openPhotos(e.features[0].properties.id));
      renderPanel(sc);
    });
  }
  const b = sc.base;
  map.addSource('base', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [b.lon, b.lat] }, properties: {} } });
  map.addLayer({ id: 'base', type: 'circle', source: 'base', paint: { 'circle-radius': 7, 'circle-color': '#e8743b', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
  const pop = new maplibregl.Popup({ closeButton: false, offset: 10 });
  map.on('mouseenter', 'base', (e) => pop.setLngLat(e.lngLat).setHTML(`<b>Habitat (base)</b> <span class="badge assumed">assumed</span><br>${esc(b.note)}`).addTo(map));
  map.on('mouseleave', 'base', () => pop.remove());
}

const VECTORS = [
  { id: 'base', title: 'Habitat (base) — local origin', label: 'assumed', layers: ['base'] },
  { id: 'aoi', title: 'Study area (AOI)', label: 'derived', layers: ['aoi'] },
  { id: 'traverse', title: 'Perseverance traverse', label: 'measured', layers: ['traverse', 'traverse-casing'], rover: 'traverse' },
  { id: 'waypoints', title: 'Perseverance waypoints', label: 'measured', layers: ['waypoints'], rover: 'waypoints' },
  { id: 'photos', title: 'Ground photos (click a yellow dot)', label: 'measured', layers: ['photos'], rover: 'photos' },
];

function legendHTML(lg) {
  if (!lg) return '';
  return '<div class="legend">' + lg.colors.map((c, i) => `<span><i style="background:${c}"></i>${lg.edges[i]}${i === lg.colors.length - 1 ? '+' : ''}</span>`).join('') + '<span style="flex:.6">°</span></div>';
}

function renderPanel(sc) {
  $('#sceneInfo').innerHTML = `<h2>${esc(sc.title)}</h2><p>${esc(sc.subtitle)}</p>` +
    `<p>Base ${sc.base.lat.toFixed(5)}°N, ${(sc.base.lon < 0 ? sc.base.lon + 360 : sc.base.lon).toFixed(5)}°E · AOI ${(sc.aoi.extent_local_m[2] - sc.aoi.extent_local_m[0]) / 1000} × ${(sc.aoi.extent_local_m[3] - sc.aoi.extent_local_m[1]) / 1000} km</p>` +
    (sc.ground_data ? `<p>${esc(sc.ground_data)}</p>` : '');
  const groups = {};
  sc.layers.slice().reverse().forEach((L) => (groups[L.group] = groups[L.group] || []).push(L));
  let h = '';
  const order = ['Rover ground data', 'Reference terrain (HiRISE, orbital)', 'Prior terrain (CTX, orbital)', 'Regional context'];
  const vec = VECTORS.filter((v) => !v.rover || (sc.rover && sc.rover[v.rover]));
  h += '<h3>Map annotations &amp; rover data</h3>';
  vec.forEach((v) => {
    const r = v.rover && sc.rover[v.rover];
    const extra = v.id === 'photos' && r ? ` — ${r.n_images} photos at ${r.n_waypoints}/${r.n_waypoints_aoi} AOI waypoints` : '';
    const src = r ? `${esc(r.source.title)} · ${esc(r.source.mission)}` : v.id === 'base' ? esc(sc.base.note) : esc(sc.aoi.rule || '');
    h += `<div class="layer"><div class="row"><input type="checkbox" id="v_${v.id}" data-vec="${v.id}" checked>` +
      `<label class="name" for="v_${v.id}">${esc(v.title)}${extra}</label><span class="badge ${v.label}">${v.label}</span></div>` +
      `<div class="src">${src}</div>` + (v.id === 'photos' && r ? `<div class="src">Placed by exact site/drive match with a waypoint. Viewing direction not drawn (camera azimuth not verified).</div>` : '') + '</div>';
  });
  order.concat(Object.keys(groups).filter((g) => !order.includes(g))).forEach((g) => {
    if (!groups[g]) return;
    h += `<h3>${esc(g)}</h3>`;
    groups[g].forEach((L) => {
      h += `<div class="layer"><div class="row"><input type="checkbox" id="l_${L.id}" data-layer="${L.id}" ${L.visible ? 'checked' : ''}>` +
        `<label class="name" for="l_${L.id}">${esc(L.title)}</label><span class="badge ${L.label}">${L.label}</span>` +
        `<input type="range" min="0" max="1" step="0.05" value="${L.opacity}" data-op="${L.id}" aria-label="Opacity"></div>` +
        legendHTML(L.legend) +
        `<details><summary>Source · ${fmtBytes(L.bytes)}${L.tiles ? ` in ${L.tiles} tiles` : ''}</summary><p>${esc(L.description)}</p>` +
        `<p><b>${esc(L.source.title)}</b><br>${esc(L.source.mission)}${L.source.in_resources ? ' · <i>challenge Resources item</i>' : ''}<br>` +
        `<a href="${esc(L.source.url.replace('{z}/{row}/{col}', ''))}" target="_blank" rel="noopener">source link</a></p></details></div>`;
    });
  });
  $('#layers').innerHTML = h;
  $('#layers').querySelectorAll('[data-layer]').forEach((el) => el.onchange = () => setVis(el.dataset.layer, el.checked));
  $('#layers').querySelectorAll('[data-op]').forEach((el) => el.oninput = () => S.map.getLayer(el.dataset.op) && S.map.setPaintProperty(el.dataset.op, 'raster-opacity', +el.value));
  $('#layers').querySelectorAll('[data-vec]').forEach((el) => el.onchange = () => {
    const v = VECTORS.find((x) => x.id === el.dataset.vec);
    v.layers.forEach((id) => S.map.getLayer(id) && S.map.setLayoutProperty(id, 'visibility', el.checked ? 'visible' : 'none'));
  });
}

function setVis(id, on) {
  const m = S.map; if (!m || !m.getLayer(id)) return;
  m.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
  const cb = $(`#l_${id}`); if (cb) cb.checked = on;
}
function setOp(id, v) {
  if (S.map.getLayer(id)) S.map.setPaintProperty(id, 'raster-opacity', v);
  const r = $(`[data-op="${id}"]`); if (r) r.value = v;
}

function preset(p) {
  const terr = ['hirise_hillshade', 'hirise_slope', 'ctx_hillshade', 'ctx_slope'];
  if (p === 'swipe') {
    setSwipe(!S.swipe);
    document.querySelectorAll('[data-preset]').forEach((b) => b.classList.toggle('active', b.dataset.preset === 'swipe' && S.swipe));
    return;
  }
  setSwipe(false);
  terr.forEach((id) => setVis(id, false));
  if (p === 'ref') { setVis('hirise_ortho', true); setVis('hirise_hillshade', true); setOp('hirise_hillshade', 1); }
  if (p === 'prior') { setVis('hirise_ortho', false); setVis('post_landing', false); setVis('ctx_hillshade', true); setOp('ctx_hillshade', 1); }
  document.querySelectorAll('[data-preset]').forEach((b) => b.classList.toggle('active', b.dataset.preset === p));
}

/* Swipe: left of the handle = HiRISE hillshade (main map), right = CTX hillshade (second map, clipped). */
function setSwipe(on) {
  S.swipe = on;
  const h = $('#swipeHandle'), m2 = $('#map2');
  $('#swipeBtn').classList.toggle('active', on);
  h.hidden = !on; m2.style.display = on ? 'block' : 'none';
  if (!on) return;
  ['ctx_hillshade', 'ctx_slope', 'hirise_slope'].forEach((id) => setVis(id, false));
  setVis('hirise_ortho', true); setVis('hirise_hillshade', true); setOp('hirise_hillshade', 1);
  if (!S.map2) {
    const sc = S.scene, L = sc.layers.find((x) => x.id === 'ctx_hillshade');
    const st = emptyStyle();
    st.sources.ctx = rasterSource(L, S.base);
    st.layers.push({ id: 'ctx', type: 'raster', source: 'ctx', paint: { 'raster-fade-duration': 0 } });
    const c = sc.aoi.corners;
    st.sources.aoi = { type: 'geojson', data: { type: 'Feature', geometry: { type: 'LineString', coordinates: [...c, c[0]] } } };
    st.layers.push({ id: 'aoi', type: 'line', source: 'aoi', paint: { 'line-color': '#f2b36b', 'line-width': 1.5, 'line-dasharray': [3, 2] } });
    S.map2 = new maplibregl.Map({ container: 'map2', style: st, center: S.map.getCenter(), zoom: S.map.getZoom(), interactive: false, attributionControl: false, renderWorldCopies: false });
  }
  S.map2.resize(); syncMap2(); placeHandle();
  const wrap = $('#mapwrap');
  h.onpointerdown = (e) => {
    h.setPointerCapture(e.pointerId);
    h.onpointermove = (ev) => { const r = wrap.getBoundingClientRect(); S.swipeX = Math.min(0.98, Math.max(0.02, (ev.clientX - r.left) / r.width)); placeHandle(); };
    h.onpointerup = () => { h.onpointermove = null; };
  };
}
function placeHandle() {
  const w = $('#mapwrap').clientWidth, x = S.swipeX * w;
  $('#swipeHandle').style.left = (x - 2) + 'px';
  $('#map2').style.clipPath = `inset(0 0 0 ${x}px)`;
}
function syncMap2() { if (S.map2 && S.swipe) S.map2.jumpTo({ center: S.map.getCenter(), zoom: S.map.getZoom() }); }

function marsDist(a, b) { // haversine on the Mars sphere, metres
  const dlat = (b.lat - a.lat) * DEG, dlon = (b.lng - a.lng) * DEG;
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(a.lat * DEG) * Math.cos(b.lat * DEG) * Math.sin(dlon / 2) ** 2;
  return 2 * R_MARS * Math.asin(Math.sqrt(h));
}
function updateScale() {
  const m = S.map; if (!m) return;
  const H = m.getContainer().clientHeight, maxPx = 120;
  const a = m.unproject([20, H - 40]), b = m.unproject([20 + maxPx, H - 40]);
  const d = marsDist(a, b);
  const pow = 10 ** Math.floor(Math.log10(d)), n = d / pow;
  const nice = (n >= 5 ? 5 : n >= 2 ? 2 : 1) * pow;
  $('#scaleBar').style.width = (maxPx * nice / d) + 'px';
  $('#scaleLabel').textContent = (nice >= 1000 ? nice / 1000 + ' km' : nice + ' m') + ' (Mars)';
}
function showCoords(ll) {
  const b = S.scene.base, k = Math.cos(b.lat * DEG);
  const x = (ll.lng - b.lon) * DEG * R_MARS * k, y = (ll.lat - b.lat) * DEG * R_MARS;
  const lonE = ll.lng < 0 ? ll.lng + 360 : ll.lng;
  $('#coords').innerHTML = `${ll.lat.toFixed(5)}°N ${lonE.toFixed(5)}°E<br>x ${x.toFixed(0)} m E, y ${y.toFixed(0)} m N of base`;
}

function renderChecks(sc) {
  const a = sc.alignment, x3 = a.x3;
  const yes = (v) => v ? '<span class="pass">pass</span>' : '<span class="fail">fail</span>';
  const pr = a.prior_registration, mo = a.mola;
  let h = `<h3>Positioning checks</h3><table>` +
    `<tr><td>X3 (locked thresholds)</td><td>${yes(x3.pass)}</td></tr>` +
    `<tr><td>CTX → HiRISE image shift (applied once)</td><td>${pr.measured_shift_m[0]} m E, ${pr.measured_shift_m[1]} m N</td></tr>` +
    `<tr><td>Quadrant deviation after shift (≤ 20 m)</td><td>${pr.quadrant_dev_m.map((v) => v.toFixed(1)).join(', ')} m ${yes(x3.checks['2_quadrants_within_20m'])}</td></tr>` +
    `<tr><td>HiRISE − MOLA (|mean|, std ≤ 10 m)</td><td>${mo.reference_minus_mola.mean_m}, ${mo.reference_minus_mola.std_m} m (${mo.reference_minus_mola.n_cells} cells) ${yes(x3.checks['3_ref_vs_mola'])}</td></tr>` +
    `<tr><td>CTX − MOLA after offset (std ≤ 10 m)</td><td>${mo.shifted_prior_minus_mola.mean_m}, ${mo.shifted_prior_minus_mola.std_m} m ${yes(x3.checks['4_prior_vs_mola_std'])}</td></tr>`;
  const pe = a.mola_pedr;
  if (pe && pe.hirise_minus_pedr) h += `<tr><td>Supplementary (rule fixed before running): DTM − 1,067 MOLA laser shots (PEDR), no shift fitted</td><td>HiRISE ${pe.hirise_minus_pedr.mean_m} ± ${pe.hirise_minus_pedr.std_m} m ${yes(pe.hirise_pass)}; CTX ${pe.ctx_shifted_minus_pedr.mean_m} ± ${pe.ctx_shifted_minus_pedr.std_m} m ${yes(pe.ctx_pass)} <span class="info">(reported next to the X3 result above, does not replace it)</span></td></tr>`;
  (sc.checks || []).forEach((c) => { h += `<tr><td>${esc(c.name)}</td><td>${c.pass == null ? '<span class="info">info</span>' : yes(c.pass)} ${esc(c.value)}</td></tr>`; });
  h += `</table><p class="hint">Check images: app/qa/${esc(sc.scene)}/ · status: ${esc(sc.review)}</p>`;
  $('#checks').innerHTML = h;
}

function openPhotos(id) {
  const w = S.photos && S.photos.waypoints.find((x) => x.id === id); if (!w) return;
  const lonE = w.lon < 0 ? w.lon + 360 : w.lon;
  let h = `<h2>Waypoint ${esc(w.id)}</h2><p class="muted">Site ${w.site}, drive ${w.drive} · arrived Sol ${w.sol} · ${w.lat.toFixed(5)}°N ${lonE.toFixed(5)}°E · ${w.x.toFixed(0)} m E, ${w.y.toFixed(0)} m N of base</p>` +
    `<p class="muted">Real images from NASA's Perseverance rover, taken while it stood at this waypoint (site/drive match). <span class="badge measured">measured</span></p>`;
  w.images.forEach((im) => {
    h += `<div class="photo"><a href="${esc(im.page)}" target="_blank" rel="noopener"><img loading="lazy" src="${esc(S.base + im.local)}" alt="${esc(im.title)}" onerror="this.onerror=null;this.src='${esc(im.url_medium)}'"></a>` +
      `<div class="meta"><b>${esc(im.camera.replace(/_/g, ' '))}</b> · Sol ${im.sol} · ${esc((im.date_utc || '').slice(0, 10))} UTC` +
      `${im.mast_az != null ? ` · mast az ${im.mast_az.toFixed(0)}° (rover frame, unverified)` : ''}<br>Credit: ${esc(im.credit)} · <a href="${esc(im.page)}" target="_blank" rel="noopener">raw image page</a> · ${esc(im.imageid)}</div></div>`;
  });
  $('#photoBody').innerHTML = h; $('#photoPanel').hidden = false; S.map.resize();
}

function renderAbout() {
  const sc = S.scene;
  const srcs = new Map();
  sc.layers.forEach((L) => srcs.set(L.source.title, { ...L.source, label: L.label, layer: L.title }));
  if (sc.rover) ['traverse', 'waypoints', 'photos'].forEach((k) => srcs.set(sc.rover[k].source.title, { ...sc.rover[k].source, label: 'measured', layer: k }));
  const rows = [...srcs.values()].map((s) => `<tr><td>${esc(s.title)}</td><td>${esc(s.mission)}</td><td><span class="badge ${s.label}">${s.label}</span></td><td>${s.in_resources ? 'yes' : 'no'}</td></tr>`).join('');
  $('#aboutBody').innerHTML = `<h2>Marswalk Recon — checkpoint 1</h2>
<p>Goal of the full project: an astronaut-ready layered map and walking route. A scout rover leaves the habitat on its own, explores, returns, and its findings decide where astronauts should go and how they get there within an oxygen budget. <b>This checkpoint only shows the maps and real imagery</b> the later steps will use; no route, rover simulation or analysis is shown yet.</p>
<h3>What you are looking at</h3>
<ul>
<li><b>Reference terrain</b>: HiRISE orthoimage (0.25 m) and DTM (1 m). It is orbital data — we call it <i>HiRISE reference terrain</i>, not ground truth.</li>
<li><b>Prior terrain</b>: the CTX DTM (20 m) a planner would have without scouting. Use <i>Compare terrain resolution</i> to see what disappears at 20 m.</li>
<li><b>Rover ground data (Jezero)</b>: Perseverance traverse, waypoints and raw images, each image attached to the waypoint whose site/drive counter it carries.</li>
<li><b>Habitat (base)</b>: an <i>assumed</i> location (Octavia E. Butler Landing at Jezero). It is the origin of the local metre grid (x east, y north).</li>
</ul>
<h3>Labels</h3>
<p><span class="badge measured">measured</span> instrument data as published · <span class="badge derived">derived</span> computed by us from measured data (hillshade, slope, AOI) · <span class="badge assumed">assumed</span> our choice, not an observation · <span class="badge simulated">simulated</span> model output (none on this page yet).</p>
<h3>Data sources (this scene)</h3>
<table><tr><th>Data</th><th>Mission / provider</th><th>Label</th><th>Challenge Resources item</th></tr>${rows}</table>
<p class="hint">Challenge Resources also used as references, not data: <i>Curiosity's Proposed Path up Mount Sharp</i> (map style for routes, later step) and <i>NASA Worldview</i> (layer list + opacity controls). Full list with links: DATA_LOG.md and docs/REFERENCES.md in the repository.</p>
<h3>Limitations</h3>
<ul>
<li>HiRISE and CTX are both orbital. Rover-scale hazards smaller than about 1 m (single rocks, soft sand texture) are not resolved even in the reference terrain.</li>
<li>The CTX prior was moved by one global image-registration shift (${sc.alignment.prior_shift_m.join(' m E, ')} m N) and a vertical offset of ${sc.alignment.prior_vertical_offset_m} m so it sits on the HiRISE frame; HiRISE is the positional reference. Thresholds (X3) were fixed after the first Arcadia measurements and before any route numbers existed.</li>
${sc.alignment.x3.pass ? '' : `<li><b>The locked X3 elevation checks against MOLA do not pass here</b> (HiRISE − MOLA ${sc.alignment.mola.reference_minus_mola.mean_m} ± ${sc.alignment.mola.reference_minus_mola.std_m} m; CTX − MOLA std ${sc.alignment.mola.shifted_prior_minus_mola.std_m} m; limits 10 m). The CTX-to-HiRISE registration itself passes. The thresholds were not relaxed and the result stays a fail. A supplementary check written down before it was run compares the DTMs directly with 1,067 individual MOLA laser shots (PEDR, no horizontal shift fitted): HiRISE − MOLA −2.6 ± 7.4 m, CTX − MOLA −3.3 ± 7.2 m, within the same limits. It is reported next to the original result, not instead of it. The same shots also disagree with the 463 m MOLA mosaic itself (best agreement when that mosaic is moved about 330 m west and 230 m north), which points at the gridded mosaic rather than at our sampling.</li>`}
<li>Perseverance waypoint elevations agree with the HiRISE DTM to centimetres because they were derived from the same terrain model; that only proves our coordinate chain, not the DTM. The independent check is a HiRISE image from 2021-09-24 (sol ~212) that shows the parked rover itself about 2 m from its published waypoint.</li>
<li>Photo viewing directions are not drawn: the mast azimuth is in the rover frame and its conversion has not been verified.</li>
<li>Arcadia Planitia (the ice-resource candidate region) is paused by team decision; it has no ground photos at all (nearest landers are more than 2,000 km away).</li>
<li>MapLibre draws Mars coordinates with Earth Web Mercator maths; the scale bar and coordinates are computed on the Mars sphere (R = 3,396.19 km). Image layers are resampled so they line up with this display.</li>
<li>Positioning checks and terrain readings are <i>${esc(sc.review)}</i> by a person.</li>
</ul>`;
}

init().catch((e) => { document.body.insertAdjacentHTML('afterbegin', `<pre style="color:#f88;padding:12px">Failed to load: ${esc(e.message)}\nServe this folder over HTTP (python -m http.server), file:// cannot fetch JSON.</pre>`); });
