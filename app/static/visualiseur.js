// Visualiseur de l'onglet « Analyse » (D17), exécuté par gr.HTML (js_on_load).
// Forme d'onde dessinée par wavesurfer.js (embarqué dans app/static/, sans CDN) à partir de
// l'enveloppe calculée côté Python ; le son est lu en flux. Une piste par locuteur ; un clic
// sur un segment (piste ou forme d'onde) le fait écouter, de son début à sa fin.
// Variables fournies par Gradio : element, props, watch.

function fmt(t) {
  const m = Math.floor(t / 60);
  const s = Math.floor(t % 60);
  return m + ':' + String(s).padStart(2, '0');
}

function isDark() {
  return document.documentElement.classList.contains('dark') || document.body.classList.contains('dark');
}

function rgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')';
}

function tickStep(duration) {
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
  return steps.find((s) => duration / s <= 10) || 3600;
}

function destroy() {
  if (element._ws) {
    element._ws.destroy();
    element._ws = null;
  }
}

function playSegment(start, end) {
  if (element._ws) element._ws.play(start, end);
}

function drawRegions() {
  const v = props.value;
  const regions = element._regions;
  if (!regions || !v) return;
  regions.clearRegions();
  const colors = element._colors;
  v.segments.forEach((seg) => {
    regions.addRegion({
      start: seg.debut, end: seg.fin, color: rgba(colors[seg.locuteur], 0.22),
      drag: false, resize: false,
    });
  });
}

function drawLanes(v) {
  const lanes = element.querySelector('.wsp-lanes');
  const axis = element.querySelector('.wsp-axis');
  lanes.innerHTML = '';
  axis.innerHTML = '';
  const names = {};
  v.locuteurs.forEach((spk) => {
    names[spk.id] = spk.nom;
    const row = document.createElement('div');
    row.className = 'wsp-lane';
    const label = document.createElement('div');
    label.className = 'wsp-label';
    const swatch = document.createElement('span');
    swatch.className = 'wsp-swatch';
    swatch.style.background = element._colors[spk.id];
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(spk.nom));
    label.title = spk.nom + ' (' + spk.id + ')';
    const track = document.createElement('div');
    track.className = 'wsp-track';
    track.dataset.id = spk.id;
    row.appendChild(label);
    row.appendChild(track);
    lanes.appendChild(row);
  });
  const tracks = {};
  lanes.querySelectorAll('.wsp-track').forEach((t) => { tracks[t.dataset.id] = t; });
  v.segments.forEach((seg) => {
    const bar = document.createElement('button');
    bar.type = 'button';
    bar.className = 'wsp-seg';
    bar.style.left = (100 * seg.debut / v.duree_s) + '%';
    bar.style.width = (100 * (seg.fin - seg.debut) / v.duree_s) + '%';
    bar.style.background = element._colors[seg.locuteur];
    bar.title = names[seg.locuteur] + ' : ' + fmt(seg.debut) + ' – ' + fmt(seg.fin)
      + ' (' + (seg.fin - seg.debut).toFixed(1).replace('.', ',') + ' s) — cliquer pour écouter';
    bar.addEventListener('click', () => playSegment(seg.debut, seg.fin));
    tracks[seg.locuteur].appendChild(bar);
  });
  const step = tickStep(v.duree_s);
  for (let t = 0; t <= v.duree_s; t += step) {
    const tick = document.createElement('span');
    tick.className = 'wsp-tick';
    tick.style.left = (100 * t / v.duree_s) + '%';
    tick.textContent = fmt(t);
    axis.appendChild(tick);
  }
}

function render() {
  const v = props.value;
  const root = element.querySelector('.wsp-root');
  if (!root) return;
  if (!v || !v.audio_url) {
    destroy();
    root.classList.add('wsp-empty');
    return;
  }
  root.classList.remove('wsp-empty');
  const dark = isDark();
  element._colors = {};
  v.locuteurs.forEach((spk) => { element._colors[spk.id] = dark ? spk.couleur_sombre : spk.couleur; });

  const wave = element.querySelector('.wsp-wave');
  let ws = element._ws;
  if (!ws || element._url !== v.audio_url || !wave.contains(ws.getWrapper())) {
    // Après un renommage, le gabarit est redessiné : on reprend à la même position.
    const resume = element._url === v.audio_url ? (element._t || 0) : 0;
    destroy();
    wave.innerHTML = '';
    const regions = WaveSurfer.Regions.create();
    ws = WaveSurfer.create({
      container: wave,
      height: 88,
      waveColor: dark ? '#8a8985' : '#b5b4af',
      progressColor: dark ? '#c3c2b7' : '#52514e',
      cursorColor: dark ? '#f0efec' : '#0b0b0b',
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      url: v.audio_url,
      peaks: [v.peaks],
      duration: v.duree_s,
      plugins: [regions],
    });
    element._ws = ws;
    element._regions = regions;
    element._url = v.audio_url;
    regions.on('region-clicked', (region, event) => {
      event.stopPropagation();
      playSegment(region.start, region.end);
    });
    const time = element.querySelector('.wsp-time');
    const head = element.querySelector('.wsp-playhead');
    const button = element.querySelector('.wsp-play');
    const show = (t) => {
      element._t = t;
      time.textContent = fmt(t) + ' / ' + fmt(v.duree_s);
      head.style.left = (100 * t / v.duree_s) + '%';
    };
    ws.on('timeupdate', show);
    ws.on('play', () => { button.textContent = 'Pause'; });
    ws.on('pause', () => { button.textContent = 'Lecture'; });
    ws.on('decode', drawRegions);
    ws.on('ready', drawRegions);
    if (resume > 0) ws.once('ready', () => ws.setTime(resume));
    show(resume);
  }
  drawRegions();
  drawLanes(v);
}

element.querySelector('.wsp-play').addEventListener('click', () => {
  if (element._ws) element._ws.playPause();
});
render();
watch('value', render);
