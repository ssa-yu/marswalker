// SI: written by an AI coding agent (Anthropic Claude via Claude Code) under the team's direction; see docs/AI_USE.md
/* Marswalk Recon — step 2 (option A: SuperCam chemistry groups -> candidate stops) and round 7 (multi-stop walks to
   those stops) on the astronaut page. Switchable: when data/jezero/step2/step2.json says enabled: false (or is
   missing) nothing of step 2 or round 7 is shown. Data: pipeline/step2_chem.py, round7.py, export_round7.py.
   Uses globals from astronaut.js (S, $, esc, f0, f1, sg, fmtMin, fc, xyToLL, getJSON, BASE, CB) and i18n.js (tr).
   Product = the version-3 rover's unlock set (i_v3); the version-2 record (i) only with ?rule=v2. */
'use strict';
const S2 = { on: false, ds: 'i', sel: null };
const GCOL = ['#2ec4b6', '#ffd166', '#ef476f', '#a0c4ff'];
const OXL = ['SiO2', 'TiO2', 'Al2O3', 'FeOT', 'MgO', 'CaO', 'Na2O', 'K2O'];
const WANT_V2 = new URLSearchParams(location.search).get('rule') === 'v2';

async function step2Init() {
  let D;
  try { D = await getJSON(BASE + 'step2/step2.json'); } catch (e) { return; }
  if (!D || !D.enabled) return;                       // switch off -> nothing of step 2 appears
  let R7 = null;
  try { R7 = await getJSON(CB + 'round7.json'); } catch (e) { R7 = null; }
  const mine = D.link_rule === 'i' ? (D.datasets.i_v3 && !WANT_V2 ? 'i_v3' : 'i') : 'ii';
  Object.assign(S2, { on: true, D, R7, ds: mine });
  const baseRefresh = refresh;
  refresh = function () { baseRefresh(); if (S.map && S.map.getSource('s2')) { step2Draw(); round7Render(); } };  // eslint-disable-line no-global-assign
  $('#step2').hidden = false;
  if (R7) $('#round7').hidden = false;
  const modes = D.link_rule === 'i' ? [[mine, tr('s2.modeMine')], ['ii', tr('s2.modeAll')]] : [['ii', tr('s2.modeII')]];
  $('#s2Mode').innerHTML = modes.map(([k, n]) => `<button class="btn sm" data-ds="${k}">${esc(n)}</button>`).join('');
  document.querySelectorAll('#s2Mode button').forEach((b) => b.onclick = () => { S2.ds = b.dataset.ds; S2.sel = null; step2Render(); });
  const wait = () => (S.map && S.map.getSource('tg') ? step2Map() : setTimeout(wait, 200));
  wait();
}

function step2Map() {
  const m = S.map;
  m.addSource('s2walk', { type: 'geojson', data: fc([]) });
  m.addLayer({ id: 's2walk-case', type: 'line', source: 's2walk', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': '#000', 'line-width': 4.5, 'line-opacity': 0.7 } });
  m.addLayer({ id: 's2walk', type: 'line', source: 's2walk', layout: { 'line-join': 'round', 'line-cap': 'round' }, paint: { 'line-color': ['get', 'col'], 'line-width': 2.4, 'line-dasharray': [2, 1.2] } });
  m.addSource('s2', { type: 'geojson', data: fc([]) });
  m.addLayer({ id: 's2', type: 'circle', source: 's2', paint: { 'circle-radius': ['case', ['get', 'sel'], 10, 7.5], 'circle-color': ['get', 'col'], 'circle-stroke-color': ['case', ['get', 'sel'], '#fff', '#000'], 'circle-stroke-width': 2 } });
  const pop = new maplibregl.Popup({ closeButton: false, offset: 10 });
  m.on('click', 's2', (e) => { S2.sel = e.features[0].properties.i; step2Render(); });
  m.on('mouseenter', 's2', (e) => { m.getCanvas().style.cursor = 'pointer'; const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(`<b>${esc(p.lbl)}</b> · ${esc(p.tip)}<br>${tr('s2.popClick')}`).addTo(m); });
  m.on('mouseleave', 's2', () => { m.getCanvas().style.cursor = ''; pop.remove(); });
  step2Render();
}

const isI = (k) => k === 'i' || k === 'i_v3';
const roleName = (r) => tr(r.role === 'representative' ? 's2.typical' : 's2.unusual');
const stopTip = (s) => s.roles.map((r) => `G${r.group} ${roleName(r)}`).join(' + ');

function groupLine(g) {
  const c = g['centroid_wt%'];
  return `<span class="gdot" style="background:${GCOL[g.group - 1]}"></span>${tr('s2.group', { g: g.group, n: g.n_targets, p: g.n_locations, mg: f1(c.MgO), si: f1(c.SiO2), fe: f1(c.FeOT) })}`;
}

function step2Render() {
  if (!S2.on) return;
  const D = S2.D, B = D.datasets[S2.ds]; S2.cur = B;
  document.querySelectorAll('#s2Mode button').forEach((b) => b.classList.toggle('active', b.dataset.ds === S2.ds));
  const ul = S2.ds === 'i_v3' ? D.unlock_by_loop_v3 : D.unlock_by_loop;
  $('#s2Info').innerHTML = `<p class="hint">${tr(isI(S2.ds) ? 's2.dsMine' : (D.link_rule === 'i' ? 's2.dsAll' : 's2.dsII'))}</p>
<p class="hint">${tr('s2.summary', { n: B.n_targets, p: B.n_locations, k: B.k })}</p>
<div class="glist">${B.groups.map((g) => `<div>${groupLine(g)}</div>`).join('')}</div>
<details class="explain"><summary>${tr('common.explain')}</summary><p class="hint">${tr('s2.rule')}</p>
${isI(S2.ds) ? `<p class="hint">${tr('s2.unlock', { loops: Object.keys(ul).join(' / '), t: Object.values(ul).map((u) => u.n_targets).join(' / '), p: Object.values(ul).map((u) => u.n_locations).join(' / '), k: Object.values(ul).map((u) => u.k).join(' / ') })}${Object.values(ul).every((u) => Object.keys(u.units).every((x) => x === 'Njf')) ? ' ' + tr('s2.allNjf') : ''}</p>` : ''}</details>`;
  $('#s2Stops').innerHTML = B.stops.map((s, i) => `<button class="btn sm stopbtn ${S2.sel === i ? 'active' : ''}" data-i="${i}"><span class="gdot" style="background:${GCOL[s.roles[0].group - 1]}"></span>S${i + 1} · ${esc(stopTip(s))}</button>`).join('');
  document.querySelectorAll('#s2Stops button').forEach((b) => b.onclick = () => { S2.sel = +b.dataset.i; step2Render(); });
  $('#s2Card').innerHTML = S2.sel == null ? `<p class="hint">${tr('s2.pick')}</p>` : stopCard(B.stops[S2.sel], S2.sel);
  $('#s2Samples').innerHTML = samplesText();
  step2Draw(); round7Render();
}

function stopCard(s, i) {
  const roleTxt = (r) => tr(r.role === 'representative' ? 's2.roleTyp' : 's2.roleUnu', { g: r.group, t: esc(r.target), sol: r.sol });
  const r0 = s.roles[0], g = S2.cur.groups.find((x) => x.group === r0.group);
  const ph = s.photos_within_15m.filter((p) => p.local);
  const more = s.photos_within_15m.find((p) => p.more);
  return `<div class="card s2card"><h4>${tr('s2.stop', { n: i + 1 })} ${badgeHTML('derived')}</h4>
${s.roles.map((r) => `<p>${roleTxt(r)}</p>`).join('')}
<table class="ox"><thead><tr><th>wt%</th>${OXL.map((o) => `<th>${o}</th>`).join('')}</tr></thead><tbody>
<tr><td>${tr('s2.oxTarget')}</td>${OXL.map((o) => `<td>${f1(r0['oxides_wt%'][o])}</td>`).join('')}</tr>
<tr><td>${tr('s2.oxCentre', { g: r0.group })}</td>${OXL.map((o) => `<td>${f1(g['centroid_wt%'][o])}</td>`).join('')}</tr>
<tr class="muted"><td>RMSEP</td>${OXL.map((o) => `<td>±${f1(r0['rmsep_wt%'][o])}</td>`).join('')}</tr></tbody></table>
<div class="kv"><span>${tr('s2.unit')}</span><span>${s.sim3464_unit ? `${esc(s.sim3464_unit.symbol)} · ${esc(trf('unit.' + s.sim3464_unit.symbol, s.sim3464_unit.name))}` : '–'}</span>
<span>${tr('s2.where')}</span><span>x ${f0(s.x)} m, y ${f0(s.y)} m</span></div>
${ph.length ? `<div class="thumbs">${ph.map((p) => `<a href="${esc(p.page)}" target="_blank" rel="noopener" title="${esc(p.camera)} · sol ${p.sol} · ${f0(p.dist_m)} m · ${esc(p.credit)}"><img loading="lazy" src="${BASE + p.local}" alt="Perseverance ${esc(p.camera)} sol ${p.sol}"></a>`).join('')}</div>
<p class="hint">${tr('s2.photos', { credit: esc(ph[0].credit) })}${more ? ' · ' + tr('s2.more', { n: more.more }) : ''} ${badgeHTML('measured')}</p>` : `<p class="hint">${tr('s2.noPhoto')}</p>`}
<details class="explain"><summary>${tr('common.explain')}</summary><p class="hint">${tr('s2.cardNote', { site: s.site, drive: s.drive })}${isI(S2.ds) ? ' ' + tr('s2.cardUnlocked') : ''}</p></details>
</div>`;
}

function samplesText() {
  const D = S2.D, key = isI(S2.ds) ? 'i_unlocked@30' : 'ii_all';
  const rows = (S2.ds === 'i_v3' ? D.samples_v3 : D.samples).map((s) => {
    const b = s.by_dataset[key], near = b.targets_within_15m_of_the_sample_waypoint;
    return `<li><b>${esc(s.feature)}</b>: ${near.n ? tr('s2.smpNear', { n: near.n, g: Object.entries(near.groups).map(([g, n]) => `G${g} ${n}`).join(', ') }) : tr('s2.smpNone')}</li>`;
  }).join('');
  return `<details><summary>${tr('s2.smpH')}</summary><ul class="hint">${rows}</ul><p class="hint">${tr('s2.smpNote')}</p></details>`;
}

// round-7 table of the version on screen: the all-data table (ii) exists only for the version-2 rover, so it is not shown with version 3
function r7Table() { const R7 = S2.R7; if (!R7) return null; if (S2.ds === 'ii' && S.rule === 'v3') return null; return R7.tables[S2.ds] || null; }
const r7Key = () => (S2.ds === 'i_v3' ? `B_v3@${S.k}` : `B@${S.k}`);

function step2Draw() {
  if (!S.map || !S.map.getSource('s2')) return;
  const B = S2.cur;
  (S2.lbls || []).forEach((mk) => mk.remove());
  S2.lbls = B.stops.map((s, i) => new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'pt-lbl', textContent: `S${i + 1}` }), offset: [0, -16] }).setLngLat(xyToLL(s.x, s.y)).addTo(S.map));
  S.map.getSource('s2').setData(fc(B.stops.map((s, i) => ({ type: 'Feature', properties: { i, sel: S2.sel === i, col: GCOL[s.roles[0].group - 1], lbl: `S${i + 1}`, tip: stopTip(s) }, geometry: { type: 'Point', coordinates: xyToLL(s.x, s.y) } }))));
  const feats = [], T = r7Table();
  if (T) {
    for (const [st, col] of [['A', COL.A], [r7Key(), COL.B]]) {
      const p = T.paths[st] && T.paths[st].main; if (!p) continue;
      feats.push({ type: 'Feature', properties: { col }, geometry: { type: 'LineString', coordinates: p.lon.map((v, j) => [v, p.lat[j]]) } });
    }
  }
  S.map.getSource('s2walk').setData(fc(feats));
}

function round7Render() {
  const R7 = S2.R7; if (!R7) return;
  const T = r7Table();
  if (!T) { $('#r7Body').innerHTML = `<p class="hint">${tr('r7.none')}</p>`; return; }
  const k = r7Key();
  const line = (s, name, cls) => { const r = T.rows[s] && T.rows[s].main; if (!r || r.error) return ''; const d = r.diff_vs_A;
    return `<tr class="${cls}"><td>${name}</td><td>${r.stops_reached_with_safe_return} / ${r.n_planned_stops}</td><td><b>${f1(r.actual_o2)}</b></td><td>${f0(r.hazard_m)}</td><td>${d ? sg(d.actual_o2, f1) : '–'}</td></tr>`; };
  $('#r7Body').innerHTML = `<p class="hint">${tr('r7.lead', { n: T.stops.length, dwell: R7.dwell.dwell_min })}</p>
<div class="r7wrap"><table class="cmp r7"><thead><tr><th></th><th>${tr('r7.reached')}</th><th>${tr('idx.c.act')}</th><th>${tr('idx.c.haz')}</th><th>${tr('r7.vsA')}</th></tr></thead><tbody>
${line('A', tr('idx.colA'), 'cA')}${line(k, tr('idx.colB', { k: S.k }), 'cB')}</tbody></table></div>
<details class="explain"><summary>${tr('common.explain')}</summary><p class="hint">${tr('r7.notes', { u: f0(R7.usable_o2), km: f1(Math.max(...T.stops.map((x) => Math.hypot(x.x, x.y))) / 1000) })}</p></details>`;
}

document.addEventListener('DOMContentLoaded', step2Init);
