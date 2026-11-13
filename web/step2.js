/* Marswalk Recon — step 2 (option A: SuperCam chemistry groups -> candidate stops) and round 7 (multi-stop walks to
   those stops) on the astronaut page. Switchable: when data/jezero/step2/step2.json says enabled: false (or is
   missing) nothing of step 2 or round 7 is shown. Data: pipeline/step2_chem.py, round7.py, export_round7.py.
   Uses globals from astronaut.js (S, $, esc, f0, f1, sg, fmtMin, fc, xyToLL, getJSON, BASE, CB). */
'use strict';
const S2 = { on: false, ds: 'i', sel: null, showWalks: true };
const GCOL = ['#2ec4b6', '#ffd166', '#ef476f', '#a0c4ff'];
const OXL = ['SiO2', 'TiO2', 'Al2O3', 'FeOT', 'MgO', 'CaO', 'Na2O', 'K2O'];

async function step2Init() {
  let D;
  try { D = await getJSON(BASE + 'step2/step2.json'); } catch (e) { return; }
  if (!D || !D.enabled) return;                       // switch off -> nothing of step 2 appears
  let R7 = null;
  try { R7 = await getJSON(CB + 'round7.json'); } catch (e) { R7 = null; }
  Object.assign(S2, { on: true, D, R7, ds: D.product });
  const baseRefresh = refresh;
  refresh = function () { baseRefresh(); if (S.map && S.map.getSource('s2')) { step2Draw(); round7Render(); } };  // eslint-disable-line no-global-assign
  $('#step2').hidden = false;
  if (R7) $('#round7').hidden = false;
  const modes = D.link_rule === 'i'
    ? [['i', 'Brought back by this rover'], ['ii', 'View all data']]
    : [['ii', 'Recon result (link rule ii)']];
  $('#s2Mode').innerHTML = modes.map(([k, n]) => `<button class="btn sm" data-ds="${k}">${esc(n)}</button>`).join('');
  document.querySelectorAll('#s2Mode button').forEach((b) => b.onclick = () => { S2.ds = b.dataset.ds; S2.sel = null; step2Render(); });
  $('#s2Walks').onchange = () => { S2.showWalks = $('#s2Walks').checked; step2Draw(); };
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
  m.on('mouseenter', 's2', (e) => { m.getCanvas().style.cursor = 'pointer'; const p = e.features[0].properties; pop.setLngLat(e.lngLat).setHTML(`<b>${esc(p.lbl)}</b> · ${esc(p.tip)}<br>click for the card`).addTo(m); });
  m.on('mouseleave', 's2', () => { m.getCanvas().style.cursor = ''; pop.remove(); });
  step2Render();
}

function dsLabel(k) {
  return k === 'i'
    ? 'Measurements the rover unlocked: Perseverance SuperCam targets within 15 m of the simulated rover\'s path by loop 30 (link rule i).'
    : (S2.D.link_rule === 'i'
      ? 'All Perseverance SuperCam measurements in the area — <b>not brought back by this rover</b>; shown for comparison only.'
      : 'All Perseverance SuperCam measurements in the area, treated as the recon result (link rule ii: the rover\'s path does not matter).');
}

function groupLine(g) {
  const d = Object.entries(g.diff_vs_other_groups_rmsep || {}).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1])).slice(0, 2);
  return `<span class="gdot" style="background:${GCOL[g.group - 1]}"></span><b>Group ${g.group}</b> · ${g.n_targets} target${g.n_targets > 1 ? 's' : ''} at ${g.n_locations} place${g.n_locations > 1 ? 's' : ''} · MgO ${f1(g['centroid_wt%'].MgO)}, SiO2 ${f1(g['centroid_wt%'].SiO2)}, FeOT ${f1(g['centroid_wt%'].FeOT)} wt%${d.length ? ` · vs the other group${S2.cur.groups.length > 2 ? 's' : ''}: ${d.map(([o, v]) => `${o} ${sg(v, f1)}×RMSEP`).join(', ')}` : ''} · SIM 3464 ${Object.entries(g.sim3464_units).map(([u, n]) => `${esc(u)} ${n}`).join(', ')}`;
}

function step2Render() {
  if (!S2.on) return;
  const D = S2.D, B = D.datasets[S2.ds]; S2.cur = B;
  document.querySelectorAll('#s2Mode button').forEach((b) => b.classList.toggle('active', b.dataset.ds === S2.ds));
  const ul = D.unlock_by_loop;
  $('#s2Info').innerHTML = `<p class="hint">${dsLabel(S2.ds)}</p>
<p class="hint">${B.n_targets} targets at ${B.n_locations} places → <b>${B.k} chemistry group${B.k > 1 ? 's' : ''}</b>. Rule fixed before any group was seen: the most groups (at most 4) whose centres all differ by at least 5× the instrument's prediction error (RMSEP) in some oxide. Candidate stops: each group's most typical target and its most unusual one — no score, no weighting.</p>
<div class="glist">${B.groups.map((g) => `<div>${groupLine(g)}</div>`).join('')}</div>
${S2.ds === 'i' ? `<p class="hint">Unlocked after loops ${Object.keys(ul).join(' / ')}: ${Object.values(ul).map((u) => u.n_targets).join(' / ')} targets at ${Object.values(ul).map((u) => u.n_locations).join(' / ')} places, ${Object.values(ul).map((u) => u.k).join(' / ')} groups; ${Object.values(ul).every((u) => Object.keys(u.units).every((x) => x === 'Njf')) ? 'all on the Jezero floor unit (Njf); none yet on the other mapped unit (Nle).' : ''}</p>` : ''}`;
  $('#s2Stops').innerHTML = B.stops.map((s, i) => `<button class="btn sm stopbtn ${S2.sel === i ? 'active' : ''}" data-i="${i}"><span class="gdot" style="background:${GCOL[s.roles[0].group - 1]}"></span>S${i + 1} · ${s.roles.map((r) => `G${r.group} ${r.role === 'representative' ? 'typical' : 'unusual'}`).join(' + ')}</button>`).join('');
  document.querySelectorAll('#s2Stops button').forEach((b) => b.onclick = () => { S2.sel = +b.dataset.i; step2Render(); });
  $('#s2Card').innerHTML = S2.sel == null ? '<p class="hint">Pick a stop (list or map) for its card.</p>' : stopCard(B.stops[S2.sel], S2.sel);
  $('#s2Samples').innerHTML = samplesText();
  step2Draw(); round7Render();
}

function stopCard(s, i) {
  const roleTxt = (r) => `${r.role === 'representative' ? 'Most typical' : 'Most unusual'} target of group ${r.group}: <b>${esc(r.target)}</b> (sol ${r.sol}, ${r.n_points} laser points, ${f1(r.dist_to_group_centroid_rmsep)} RMSEP-units from the group centre)`;
  const r0 = s.roles[0], g = S2.cur.groups.find((x) => x.group === r0.group);
  const ph = s.photos_within_15m.filter((p) => p.local);
  const more = s.photos_within_15m.find((p) => p.more);
  return `<div class="card s2card"><h4>Stop S${i + 1} <span class="badge derived">derived</span></h4>
${s.roles.map((r) => `<p>${roleTxt(r)}</p>`).join('')}
<table class="ox"><thead><tr><th>wt%</th>${OXL.map((o) => `<th>${o}</th>`).join('')}</tr></thead><tbody>
<tr><td>target</td>${OXL.map((o) => `<td>${f1(r0['oxides_wt%'][o])}</td>`).join('')}</tr>
<tr><td>group ${r0.group} centre</td>${OXL.map((o) => `<td>${f1(g['centroid_wt%'][o])}</td>`).join('')}</tr>
<tr class="muted"><td>RMSEP</td>${OXL.map((o) => `<td>±${f1(r0['rmsep_wt%'][o])}</td>`).join('')}</tr></tbody></table>
<p class="hint">Oxides: Perseverance SuperCam LIBS, PDS <span class="badge measured">measured</span>; group and role <span class="badge derived">derived</span>. Differences smaller than the RMSEP are not treated as different rock.</p>
<div class="kv"><span>Geologic unit (SIM 3464)</span><span>${s.sim3464_unit ? `${esc(s.sim3464_unit.symbol)} · ${esc(s.sim3464_unit.name)}` : '–'}</span>
<span>Where</span><span>x ${f0(s.x)} m, y ${f0(s.y)} m · site ${s.site}, drive ${s.drive}</span></div>
<p class="hint">Position = the rover's position when it fired the laser (site/drive); the rock is within about 7 m of it. Measured by Perseverance, not by our simulated rover${S2.ds === 'i' ? '; our rover unlocked it by driving within 15 m' : ''}.</p>
${ph.length ? `<div class="thumbs">${ph.map((p) => `<a href="${esc(p.page)}" target="_blank" rel="noopener" title="${esc(p.camera)} · sol ${p.sol} · ${f0(p.dist_m)} m away · ${esc(p.credit)}"><img loading="lazy" src="${BASE + p.local}" alt="Perseverance ${esc(p.camera)} image, sol ${p.sol}"></a>`).join('')}</div>
<p class="hint">Perseverance raw images taken within 15 m (credit ${esc(ph[0].credit)}; Mastcam-Z NASA/JPL-Caltech/ASU)${more ? ` · ${more.more} more` : ''}. <span class="badge measured">measured</span></p>` : '<p class="hint">No Perseverance photo within 15 m.</p>'}
</div>`;
}

function samplesText() {
  const D = S2.D, key = S2.ds === 'i' ? 'i_unlocked@30' : 'ii_all';
  const rows = D.samples.map((s) => {
    const b = s.by_dataset[key], near = b.targets_within_15m_of_the_sample_waypoint;
    const named = b.targets_named_like_the_feature.map((t) => `${esc(t.target)} → G${t.group}`).join(', ');
    const roles = near.candidate_roles.map((t) => `${esc(t.target)} (G${t.candidate_role[0]} ${t.candidate_role[1] === 'representative' ? 'typical' : 'unusual'})`).join(', ');
    return `<li><b>${esc(s.feature)}</b> (${s.samples.map((x) => esc(x.sample)).join(', ')}): ${near.n ? `${near.n} targets within 15 m — ${Object.entries(near.groups).map(([g, n]) => `G${g} ${n}`).join(', ')}` : 'no measurement in this data set'}${named ? `; named like the site: ${named}` : ''}${roles ? `; candidate stops among them: ${roles}` : ''}.</li>`;
  }).join('');
  return `<details><summary>Check against Perseverance's 4 sampling sites in this area (descriptive)</summary><ul class="hint">${rows}</ul>
<p class="hint">Where the mission actually drilled, and which group those rocks fall in. Only a description: the candidate stops are not ranked, so there is no test, and the sampling sites were not used to set any rule.</p></details>`;
}

function step2Draw() {
  if (!S.map || !S.map.getSource('s2')) return;
  const B = S2.cur;
  (S2.lbls || []).forEach((mk) => mk.remove());
  S2.lbls = B.stops.map((s, i) => new maplibregl.Marker({ element: Object.assign(document.createElement('div'), { className: 'pt-lbl', textContent: `S${i + 1}` }), offset: [0, -16] }).setLngLat(xyToLL(s.x, s.y)).addTo(S.map));
  S.map.getSource('s2').setData(fc(B.stops.map((s, i) => ({ type: 'Feature', properties: { i, sel: S2.sel === i, col: GCOL[s.roles[0].group - 1], lbl: `S${i + 1}`, tip: s.roles.map((r) => `G${r.group} ${r.role === 'representative' ? 'typical' : 'unusual'}`).join(' + ') }, geometry: { type: 'Point', coordinates: xyToLL(s.x, s.y) } }))));
  const feats = [];
  const T = S2.R7 && S2.R7.tables[S2.ds];
  if (T && S2.showWalks) {
    const k = `B@${S.k}`;
    for (const [st, col, c] of [['A', COL.A, 'main'], [k, COL.B, 'main']]) {
      const p = T.paths[st] && T.paths[st][c]; if (!p) continue;
      feats.push({ type: 'Feature', properties: { col }, geometry: { type: 'LineString', coordinates: p.lon.map((v, j) => [v, p.lat[j]]) } });
    }
  }
  S.map.getSource('s2walk').setData(fc(feats));
}

function round7Render() {
  const R7 = S2.R7; if (!R7) return;
  const T = R7.tables[S2.ds];
  const k = `B@${S.k}`;
  const lab = { A: 'A · orbital only', 'A+': 'A+ · bracket', REF: 'Reference bound' };
  const order = ['A', 'A+', ...Object.keys(T.rows).filter((s) => s.startsWith('B@')), 'REF'];
  const line = (s, c) => { const r = T.rows[s][c]; if (!r || r.error) return ''; const d = r.diff_vs_A;
    return `<tr class="${s === k ? 'hl' : ''}"><td>${esc(s.startsWith('B@') ? `B after ${s.slice(2)} loops${c === 'main' ? '' : ' · keeps A\'s order'}` : lab[s])}</td><td>${r.stops_reached_with_safe_return} / ${r.n_planned_stops}</td><td>${f1(r.pred_o2)}</td><td><b>${f1(r.actual_o2)}</b></td><td>${sg(r.o2_error, f1)}</td><td>${f0(r.hazard_m)}</td><td>${d ? sg(d.actual_o2, f1) + ' / ' + sg(d.hazard_m) : '–'}</td></tr>`; };
  $('#r7Body').innerHTML = `<p class="hint">${S2.ds === 'i' ? 'Main table' : 'Second table — stops <b>not brought back by this rover</b>'}: one walk from the habitat to the ${T.stops.length} stops and back, ${R7.dwell.dwell_min} minutes at each stop (counted as ${R7.dwell.dwell_min} nominal minutes of oxygen, <span class="badge assumed">assumed</span>). Each map picks its own order; the plan is then walked on the reference terrain without replanning.</p>
<div class="r7wrap"><table class="cmp r7"><thead><tr><th>Map used for planning</th><th>Stops reached / planned</th><th>Planned O2</th><th>Actual O2</th><th>Error</th><th>Hazard m</th><th>vs A: O2 / hazard m</th></tr></thead><tbody>
${order.map((s) => line(s, 'main') + (s === k ? line(s, 'secondary_A_order') : '')).join('')}</tbody></table></div>
<p class="hint">"Reached" = after the stay at a stop, walking home the plan's own way still fits the usable ${f0(R7.usable_o2)} on the reference terrain. Every map reaches every stop here: these stops are within about ${S2.ds === 'i' ? '0.3' : '0.9'} km of the habitat. Oxygen in nominal minutes. <b>This round was designed after seeing the first comparison; the 63-point comparison above stays the pre-registered main result.</b> The row "keeps A's order" (for the selected loop count) separates a better route from a better order. Map: dashed lines = this walk for route A (orange) and route B after ${S.k} loops (blue).</p>`;
}

document.addEventListener('DOMContentLoaded', step2Init);
