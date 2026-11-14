// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Marswalk Recon — checkpoint 1 viewer. Plain JS, no build step. Data: data/<scene>/scene.json.
   MapLibre only draws: Mars lon/lat are fed in as map coordinates; all distances use the Mars sphere.
   Interface text: i18n.js (tr / trf; layer titles fall back to scene.json). Layer opacity is fixed at the scene.json value. */
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
    b.innerHTML = esc(trf('scene.' + s.id, s.title)) + (s.status && s.status !== 'active' ? `<span class="tag">(${esc(s.status)})</span>` : '');
    b.title = trf('sceneSub.' + s.id, s.subtitle || '');
    b.onclick = () => { location.hash = s.id; };
    nav.appendChild(b);
  });
  if (idx.scenes.length < 2) nav.style.display = 'none';   // one scene: no scene switcher
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
    attributionControl: { compact: true, customAttribution: tr('dt.attrib') },
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
  $('#reviewTag').textContent = tr('dt.review');
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
      // T5: Navcam viewing directions (derived: camera model rotated by the rover attitude; other cameras not drawn)
      const views = [];
      ph.waypoints.forEach((w) => w.images.forEach((im) => {
        const v = im.view; if (!v || im.camera !== 'NAVCAM_LEFT') return;
        let a0 = v.edge_left_deg, a1 = v.edge_right_deg; if (a1 < a0) a1 += 360;
        const r = 45, ring = [[w.lon, w.lat]], k = Math.cos(w.lat * Math.PI / 180), R = 3396190;
        for (let a = a0; a <= a1 + 1e-9; a += Math.max(1, (a1 - a0) / 12)) { const t = a * Math.PI / 180; ring.push([w.lon + (r * Math.sin(t)) / (R * k) * 180 / Math.PI, w.lat + (r * Math.cos(t)) / R * 180 / Math.PI]); }
        ring.push([w.lon, w.lat]);
        views.push({ type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: { id: w.id, img: im.imageid, az: v.heading_deg } });
      }));
      map.addSource('photo-views', { type: 'geojson', data: { type: 'FeatureCollection', features: views } });
      map.addLayer({ id: 'photo-views', type: 'fill', source: 'photo-views', paint: { 'fill-color': '#ffd166', 'fill-opacity': 0.12, 'fill-outline-color': 'rgba(255,209,102,0.6)' } });
      map.addSource('photos', { type: 'geojson', data: fc });
      map.addLayer({ id: 'photos', type: 'circle', source: 'photos', paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 13, 4, 18, 8], 'circle-color': '#ffd166', 'circle-stroke-color': '#3a1d00', 'circle-stroke-width': 1.5 } });
      const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 8 });
      map.on('mouseenter', 'photos', (e) => { map.getCanvas().style.cursor = 'pointer'; const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(tr('dt.wpPop', { id: esc(p.id), sol: p.sol, n: p.n })).addTo(map); });
      map.on('mouseleave', 'photos', () => { map.getCanvas().style.cursor = ''; pop.remove(); });
      map.on('click', 'photos', (e) => openPhotos(e.features[0].properties.id));
      renderPanel(sc);
    });
  }
  if (sc.geology) {
    const g = sc.geology, match = ['match', ['get', 'symbol']];
    g.units.forEach((u) => match.push(u[0], u[2])); match.push('#888');
    map.addSource('geology', { type: 'geojson', data: abs(base + g.url) });
    map.addLayer({ id: 'geology-fill', type: 'fill', source: 'geology', layout: { visibility: 'none' }, paint: { 'fill-color': match, 'fill-opacity': 0.35 } });
    map.addLayer({ id: 'geology-line', type: 'line', source: 'geology', layout: { visibility: 'none' }, paint: { 'line-color': '#000', 'line-width': 0.8, 'line-opacity': 0.7 } });
    const gp = new maplibregl.Popup({ closeButton: false, offset: 6 });
    map.on('mousemove', 'geology-fill', (e) => { const p = e.features[0].properties; gp.setLngLat(e.lngLat).setHTML(`<b>${esc(p.symbol)}</b> ${esc(trf('unit.' + p.symbol, p.name))}<br><span class="muted">${tr('dt.geoPop')}</span>`).addTo(map); });
    map.on('mouseleave', 'geology-fill', () => gp.remove());
  }
  const b = sc.base;
  map.addSource('base', { type: 'geojson', data: { type: 'Feature', geometry: { type: 'Point', coordinates: [b.lon, b.lat] }, properties: {} } });
  map.addLayer({ id: 'base', type: 'circle', source: 'base', paint: { 'circle-radius': 7, 'circle-color': '#e8743b', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
  const pop = new maplibregl.Popup({ closeButton: false, offset: 10 });
  map.on('mouseenter', 'base', (e) => pop.setLngLat(e.lngLat).setHTML(`<b>${tr('common.habitat')}</b> ${badgeHTML('assumed')}<br>${tr('dt.basePop')}`).addTo(map));
  map.on('mouseleave', 'base', () => pop.remove());
}

const VECTORS = [
  { id: 'base', label: 'assumed', layers: ['base'] },
  { id: 'aoi', label: 'derived', layers: ['aoi'] },
  { id: 'traverse', label: 'measured', layers: ['traverse', 'traverse-casing'], rover: 'traverse' },
  { id: 'waypoints', label: 'measured', layers: ['waypoints'], rover: 'waypoints' },
  { id: 'photos', label: 'measured', layers: ['photos'], rover: 'photos' },
  { id: 'photoviews', label: 'derived', layers: ['photo-views'], rover: 'photos' },
  { id: 'geology', label: 'measured', layers: ['geology-fill', 'geology-line'], geo: true, off: true },
];

function legendHTML(lg) {
  if (!lg) return '';
  return '<div class="legend">' + lg.colors.map((c, i) => `<span><i style="background:${c}"></i>${lg.edges[i]}${i === lg.colors.length - 1 ? '+' : ''}</span>`).join('') + '<span style="flex:.6">°</span></div>';
}

function renderPanel(sc) {
  $('#sceneInfo').innerHTML = `<h2>${esc(trf('scene.' + sc.scene, sc.title))}</h2><p>${esc(tr('dt.sceneSub'))}</p>`;
  const groups = {};
  sc.layers.slice().reverse().forEach((L) => (groups[L.group] = groups[L.group] || []).push(L));
  let h = '';
  const order = ['Rover ground data', 'Reference terrain (HiRISE, orbital)', 'Prior terrain (CTX, orbital)', 'Regional context'];
  const vec = VECTORS.filter((v) => (!v.rover || (sc.rover && sc.rover[v.rover])) && (!v.geo || sc.geology));
  h += `<h3>${tr('dt.vecH')}</h3>`;
  vec.forEach((v) => {
    const r = v.rover && sc.rover[v.rover];
    const extra = v.id === 'photos' && r ? ` · ${tr('dt.photoCount', { n: r.n_images })}` : '';
    const src = v.id === 'photoviews' ? tr('dt.src.photoviews') : v.id === 'photos' && r ? `${esc(r.source.title)} · ${esc(r.source.mission)}<br>${tr('dt.src.photos')}`
      : r ? `${esc(r.source.title)} · ${esc(r.source.mission)}` : v.id === 'base' ? tr('dt.src.base') : v.id === 'aoi' ? tr('dt.src.aoi')
      : v.geo ? `${esc(sc.geology.source.title)}<br>${tr('dt.src.geo')}<div class="legend line">${sc.geology.units.map((u) => `<span style="padding:0;flex:none;margin-right:8px" title="${esc(trf('unit.' + u[0], u[1]))}"><i style="position:static;display:inline-block;width:10px;height:9px;margin-right:3px;background:${u[2]}"></i>${esc(u[0])}</span>`).join('')}</div>` : '';
    h += `<div class="layer"><div class="row"><input type="checkbox" id="v_${v.id}" data-vec="${v.id}" ${v.off ? '' : 'checked'}>` +
      `<label class="name" for="v_${v.id}">${esc(tr('dt.vec.' + v.id))}${extra}</label>${badgeHTML(v.label)}</div>` +
      (src ? `<details><summary>${tr('dt.srcSum')}</summary><div class="src">${src}</div></details>` : '') + '</div>';
  });
  order.concat(Object.keys(groups).filter((g) => !order.includes(g))).forEach((g) => {
    if (!groups[g]) return;
    h += `<h3>${esc(trf('grp.' + g, g))}</h3>`;
    groups[g].forEach((L) => {
      h += `<div class="layer"><div class="row"><input type="checkbox" id="l_${L.id}" data-layer="${L.id}" ${L.visible ? 'checked' : ''}>` +
        `<label class="name" for="l_${L.id}">${esc(trf('lyr.' + L.id, L.title))}</label>${badgeHTML(L.label)}</div>` +
        legendHTML(L.legend) +
        `<details><summary>${tr('dt.srcSum')} · ${fmtBytes(L.bytes)}</summary><p>${esc(trf('lyrd.' + L.id, L.description))}</p>` +
        `<p><b>${esc(L.source.title)}</b><br>${esc(L.source.mission)}${L.source.in_resources ? ' · <i>' + tr('dt.inRes') + '</i>' : ''}<br>` +
        `<a href="${esc(L.source.url.replace('{z}/{row}/{col}', ''))}" target="_blank" rel="noopener">${tr('dt.srcLink')}</a></p></details></div>`;
    });
  });
  $('#layers').innerHTML = h;
  $('#layers').querySelectorAll('[data-layer]').forEach((el) => el.onchange = () => setVis(el.dataset.layer, el.checked));
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
  $('#scaleLabel').textContent = (nice >= 1000 ? nice / 1000 + ' km' : nice + ' m') + ' ' + tr('common.mars');
}
function showCoords(ll) {
  const b = S.scene.base, k = Math.cos(b.lat * DEG);
  const x = (ll.lng - b.lon) * DEG * R_MARS * k, y = (ll.lat - b.lat) * DEG * R_MARS;
  const lonE = ll.lng < 0 ? ll.lng + 360 : ll.lng;
  $('#coords').innerHTML = `${ll.lat.toFixed(5)}°N ${lonE.toFixed(5)}°E<br>${esc(tr('common.xy', { x: x.toFixed(0), y: y.toFixed(0) }))}`;
}

function renderChecks(sc) {
  const a = sc.alignment, x3 = a.x3;
  const yes = (v) => v ? `<span class="pass">${tr('common.pass')}</span>` : `<span class="fail">${tr('common.fail')}</span>`;
  const pr = a.prior_registration, mo = a.mola;
  let h = `<table>` +
    `<tr><td>${tr('dt.ck.x3')}</td><td>${yes(x3.pass)}</td></tr>` +
    `<tr><td>${tr('dt.ck.shift')}</td><td>${tr('dt.ck.shiftV', { e: pr.measured_shift_m[0], n: pr.measured_shift_m[1] })}</td></tr>` +
    `<tr><td>${tr('dt.ck.quad')}</td><td>${pr.quadrant_dev_m.map((v) => v.toFixed(1)).join(', ')} m ${yes(x3.checks['2_quadrants_within_20m'])}</td></tr>` +
    `<tr><td>${tr('dt.ck.hmola')}</td><td>${mo.reference_minus_mola.mean_m}, ${mo.reference_minus_mola.std_m} m (${tr('dt.ck.cells', { n: mo.reference_minus_mola.n_cells })}) ${yes(x3.checks['3_ref_vs_mola'])}</td></tr>` +
    `<tr><td>${tr('dt.ck.cmola')}</td><td>${mo.shifted_prior_minus_mola.mean_m}, ${mo.shifted_prior_minus_mola.std_m} m ${yes(x3.checks['4_prior_vs_mola_std'])}</td></tr>`;
  const pe = a.mola_pedr;
  if (pe && pe.hirise_minus_pedr) h += `<tr><td>${tr('dt.ck.pedr')}</td><td>HiRISE ${pe.hirise_minus_pedr.mean_m} ± ${pe.hirise_minus_pedr.std_m} m ${yes(pe.hirise_pass)}; CTX ${pe.ctx_shifted_minus_pedr.mean_m} ± ${pe.ctx_shifted_minus_pedr.std_m} m ${yes(pe.ctx_pass)}</td></tr>`;
  (sc.checks || []).forEach((c) => { h += `<tr><td>${esc(trf('ck:' + c.name, c.name))}</td><td>${c.pass == null ? `<span class="info">${tr('common.info')}</span>` : yes(c.pass)} ${esc(c.value)}</td></tr>`; });
  h += `</table><p class="hint">${tr('dt.ck.note', { scene: esc(sc.scene) })}</p>`;
  $('#checks').innerHTML = h;
}

function openPhotos(id) {
  const w = S.photos && S.photos.waypoints.find((x) => x.id === id); if (!w) return;
  const lonE = w.lon < 0 ? w.lon + 360 : w.lon;
  let h = `<h2>${tr('dt.wp', { id: esc(w.id) })}</h2><p class="muted">${tr('dt.wpMeta', { site: w.site, drive: w.drive, sol: w.sol })} · ${w.lat.toFixed(5)}°N ${lonE.toFixed(5)}°E · ${esc(tr('common.xy', { x: w.x.toFixed(0), y: w.y.toFixed(0) }))}</p>` +
    `<p class="muted">${tr('dt.wpNote')} ${badgeHTML('measured')}</p>`;
  w.images.forEach((im) => {
    h += `<div class="photo"><a href="${esc(im.page)}" target="_blank" rel="noopener"><img loading="lazy" src="${esc(S.base + im.local)}" alt="${esc(im.title)}" onerror="this.onerror=null;this.src='${esc(im.url_medium)}'"></a>` +
      `<div class="meta"><b>${esc(im.camera.replace(/_/g, ' '))}</b> · Sol ${im.sol} · ${esc((im.date_utc || '').slice(0, 10))} UTC` +
      `${im.view ? ` · ${tr('dt.looking', { h: im.view.heading_deg.toFixed(0), a: im.view.edge_left_deg.toFixed(0), b: im.view.edge_right_deg.toFixed(0) })} ${badgeHTML('derived')}` : ''}<br>${tr('dt.credit')}: ${esc(im.credit)} · <a href="${esc(im.page)}" target="_blank" rel="noopener">${tr('dt.rawPage')}</a> · ${esc(im.imageid)}</div></div>`;
  });
  $('#photoBody').innerHTML = h; $('#photoPanel').hidden = false; S.map.resize();
}

function renderAbout() {
  const sc = S.scene, al = sc.alignment;
  const srcs = new Map();
  sc.layers.forEach((L) => srcs.set(L.source.title, { ...L.source, label: L.label }));
  if (sc.rover) ['traverse', 'waypoints', 'photos'].forEach((k) => srcs.set(sc.rover[k].source.title, { ...sc.rover[k].source, label: 'measured' }));
  const rows = [...srcs.values()].map((s) => `<tr><td>${esc(s.title)}</td><td>${esc(s.mission)}</td><td>${badgeHTML(s.label)}</td><td>${s.in_resources ? tr('common.yes') : tr('common.no')}</td></tr>`).join('');
  const li = (k, v) => `<li>${tr(k, v)}</li>`;
  $('#aboutBody').innerHTML = `<h2>${tr('dt.ab.title')}</h2>
<p>${tr('dt.ab.intro')}</p>
<h3>${tr('dt.ab.whatH')}</h3>
<ul>${li('dt.ab.ref')}${li('dt.ab.prior')}${li('dt.ab.ground')}${li('dt.ab.base')}</ul>
<h3>${tr('common.labels')}</h3>
<p>${badgeHTML('measured')} ${tr('dt.ab.lMea')} · ${badgeHTML('derived')} ${tr('dt.ab.lDer')} · ${badgeHTML('assumed')} ${tr('dt.ab.lAss')} · ${badgeHTML('simulated')} ${tr('dt.ab.lSim')}</p>
<h3>${tr('dt.ab.srcH')}</h3>
<table><tr><th>${tr('dt.ab.thData')}</th><th>${tr('dt.ab.thMission')}</th><th>${tr('dt.ab.thLabel')}</th><th>${tr('dt.ab.thRes')}</th></tr>${rows}</table>
<p class="hint">${tr('dt.ab.refs')}</p>
<h3>${tr('common.limits')}</h3>
<ul>${li('dt.ab.L.orbital')}${li('dt.ab.L.shift', { e: al.prior_shift_m[0], n: al.prior_shift_m[1], v: al.prior_vertical_offset_m })}
${al.x3.pass ? '' : li('dt.ab.L.x3', { hm: al.mola.reference_minus_mola.mean_m, hs: al.mola.reference_minus_mola.std_m, cs: al.mola.shifted_prior_minus_mola.std_m })}
${li('dt.ab.L.wp')}${li('dt.ab.L.views')}${li('dt.ab.L.arcadia')}${li('dt.ab.L.merc')}${li('dt.ab.L.review')}</ul>`;
}

init().catch((e) => { document.body.insertAdjacentHTML('afterbegin', `<pre style="color:#f88;padding:12px">${esc(tr('common.loadFail'))}: ${esc(e.message)}\n${esc(tr('dt.serveHint'))}</pre>`); });
