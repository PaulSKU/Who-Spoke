// Visualiseur de l'onglet « Analyse » (D17), exécuté par gr.HTML (js_on_load).
// Forme d'onde dessinée par wavesurfer.js (embarqué dans app/static/, sans CDN) à partir de
// l'enveloppe calculée côté Python ; le son est lu en flux. Une piste par locuteur ; un clic
// sur un segment (piste ou forme d'onde) le fait écouter, de son début à sa fin.
// Zoom (D17, amendement 1) : zoom natif de wavesurfer, dont le rendu paresseux ne dessine
// que la partie visible ; pistes, axe et tête de lecture suivent son défilement.
// Couleurs (D26) : la forme d'onde est neutre ; seul le segment sélectionné (dernier
// segment cliqué) y est mis en évidence, par une bande d'encre, et entouré sur sa piste.
// Variables fournies par Gradio : element, props, watch.

const MAX_PX_PER_S = 60;   // zoom maximal : 60 px par seconde d'audio
const ZOOM_STEP = 10;      // pas des boutons et de Ctrl + molette, sur l'échelle 0–100

function fmt(t) {
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const mm = h ? String(m).padStart(2, '0') : String(m);
  return (h ? h + ':' : '') + mm + ':' + String(s).padStart(2, '0');
}

function isDark() {
  return document.documentElement.classList.contains('dark') || document.body.classList.contains('dark');
}

function tickStep(duration, width) {
  // Une graduation tous les 64 px au plus.
  const maxTicks = Math.max(2, Math.floor(width / 64));
  const steps = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
  return steps.find((s) => duration / s <= maxTicks) || 3600;
}

const $ = (selector) => element.querySelector(selector);

function destroy() {
  if (element._ws) {
    element._ws.destroy();
    element._ws = null;
  }
}

function playSegment(start, end) {
  if (element._ws) element._ws.play(start, end);
}

function selectSegment(seg) {
  element._selected = { debut: seg.debut, fin: seg.fin, locuteur: seg.locuteur };
  markSelected();
  drawSelection();
  playSegment(seg.debut, seg.fin);
}

function isSelected(seg) {
  const s = element._selected;
  return !!s && s.debut === seg.debut && s.fin === seg.fin && s.locuteur === seg.locuteur;
}

function markSelected() {
  element.querySelectorAll('.wsp-seg').forEach((bar) => {
    const on = isSelected(bar._seg);
    bar.classList.toggle('wsp-selected', on);
    bar.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
}

// --- Zoom -------------------------------------------------------------------------

function viewportWidth() {
  return $('.wsp-viewport').clientWidth || $('.wsp-wave').clientWidth || 600;
}

function maxFactor() {
  const v = props.value;
  return Math.max(1, (MAX_PX_PER_S * v.duree_s) / viewportWidth());
}

function zoomFactor(level) {
  return Math.pow(maxFactor(), level / 100);
}

function syncScroll() {
  const ws = element._ws;
  $('.wsp-canvas').style.transform = 'translateX(' + (ws ? -ws.getScroll() : 0) + 'px)';
}

function drawAxis() {
  const v = props.value;
  const axis = $('.wsp-axis');
  axis.innerHTML = '';
  const width = $('.wsp-canvas').clientWidth || viewportWidth();
  const step = tickStep(v.duree_s, width);
  for (let t = 0; t <= v.duree_s; t += step) {
    const tick = document.createElement('span');
    tick.className = 'wsp-tick';
    tick.style.left = (100 * t / v.duree_s) + '%';
    tick.textContent = fmt(t);
    axis.appendChild(tick);
  }
}

function setZoom(level) {
  const v = props.value;
  const ws = element._ws;
  level = Math.max(0, Math.min(100, Math.round(level)));
  element._zoom = level;
  const range = $('.wsp-zoom-range');
  range.value = String(level);
  const factor = zoomFactor(level);
  range.setAttribute('aria-valuetext', '× ' + factor.toFixed(1).replace('.', ','));
  $('.wsp-zoom-out').disabled = level <= 0;
  $('.wsp-zoom-in').disabled = level >= 100 || maxFactor() <= 1;
  $('.wsp-zoom-fit').disabled = level <= 0;
  $('.wsp-canvas').style.width = (factor * viewportWidth()) + 'px';
  if (ws && element._ready) {
    ws.zoom(factor <= 1.0001 ? 0 : (factor * viewportWidth()) / v.duree_s);
  }
  drawAxis();
  syncScroll();
}

// --- Dessin -----------------------------------------------------------------------

function drawSelection() {
  const v = props.value;
  const regions = element._regions;
  if (!regions || !v || !element._ready) return;
  regions.clearRegions();
  const s = element._selected;
  if (!s || !v.segments.some(isSelected)) return;
  regions.addRegion({
    start: s.debut, end: s.fin, color: isDark() ? 'rgba(236,236,233,0.16)' : 'rgba(24,25,29,0.10)',
    drag: false, resize: false,
  });
}

function drawLanes(v) {
  const labels = $('.wsp-labels');
  const lanes = $('.wsp-lanes');
  labels.innerHTML = '';
  lanes.innerHTML = '';
  const names = {};
  const tracks = {};
  v.locuteurs.forEach((spk) => {
    names[spk.id] = spk.nom;
    const label = document.createElement('div');
    label.className = 'wsp-label';
    const swatch = document.createElement('span');
    swatch.className = 'wsp-swatch';
    swatch.style.background = element._colors[spk.id];
    label.appendChild(swatch);
    label.appendChild(document.createTextNode(spk.nom));
    label.title = spk.nom + ' (' + spk.id + ')';
    labels.appendChild(label);
    const track = document.createElement('div');
    track.className = 'wsp-track';
    lanes.appendChild(track);
    tracks[spk.id] = track;
  });
  v.segments.forEach((seg) => {
    const bar = document.createElement('button');
    bar.type = 'button';
    bar.className = 'wsp-seg';
    bar.style.left = (100 * seg.debut / v.duree_s) + '%';
    bar.style.width = (100 * (seg.fin - seg.debut) / v.duree_s) + '%';
    bar.style.background = element._colors[seg.locuteur];
    bar.setAttribute('aria-label', names[seg.locuteur] + ', ' + fmt(seg.debut) + ' à ' + fmt(seg.fin));
    bar.title = names[seg.locuteur] + ' : ' + fmt(seg.debut) + ' – ' + fmt(seg.fin)
      + ' (' + (seg.fin - seg.debut).toFixed(1).replace('.', ',') + ' s). Cliquer pour écouter.';
    bar._seg = seg;
    bar.addEventListener('click', () => selectSegment(seg));
    tracks[seg.locuteur].appendChild(bar);
  });
}

function render() {
  const v = props.value;
  const root = $('.wsp-root');
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

  const wave = $('.wsp-wave');
  let ws = element._ws;
  if (!ws || element._url !== v.audio_url || !wave.contains(ws.getWrapper())) {
    // Après un renommage, le gabarit est redessiné : même position et même zoom.
    const same = element._url === v.audio_url;
    const resume = same ? (element._t || 0) : 0;
    const zoom = same ? (element._zoom || 0) : 0;
    if (!same) element._selected = null;  // nouveau fichier : aucune sélection
    destroy();
    wave.innerHTML = '';
    const regions = WaveSurfer.Regions.create();
    ws = WaveSurfer.create({
      container: wave,
      height: 80,
      waveColor: dark ? '#4a4b50' : '#c9c9c4',
      progressColor: dark ? '#a3a49e' : '#5f616a',
      cursorColor: dark ? '#ecece9' : '#18191d',
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      autoScroll: true,
      autoCenter: true,
      url: v.audio_url,
      peaks: [v.peaks],
      duration: v.duree_s,
      plugins: [regions],
    });
    element._ws = ws;
    element._ready = false;
    element._regions = regions;
    element._url = v.audio_url;
    regions.on('region-clicked', (region, event) => {
      event.stopPropagation();
      playSegment(region.start, region.end);
    });
    const time = $('.wsp-time');
    const head = $('.wsp-playhead');
    const button = $('.wsp-play');
    const show = (t) => {
      element._t = t;
      time.textContent = fmt(t) + ' / ' + fmt(v.duree_s);
      head.style.left = (100 * t / v.duree_s) + '%';
    };
    ws.on('timeupdate', show);
    ws.on('play', () => { button.textContent = 'Pause'; });
    ws.on('pause', () => { button.textContent = 'Lecture'; });
    ws.on('scroll', syncScroll);
    ws.on('zoom', syncScroll);
    ws.once('ready', () => {
      element._ready = true;
      drawSelection();
      setZoom(zoom);
      if (resume > 0) ws.setTime(resume);
    });
    element._zoom = zoom;
    show(resume);
  }
  drawLanes(v);
  markSelected();
  drawSelection();
  setZoom(element._zoom || 0);
}

// --- Commandes ---------------------------------------------------------------------
// Délégation sur l'élément racine : Gradio peut redessiner le gabarit (renommage), les
// écouteurs posés sur les boutons eux-mêmes seraient alors perdus.

element.addEventListener('click', (event) => {
  const target = event.target.closest('button');
  if (!target || !element._ws) return;
  if (target.classList.contains('wsp-play')) element._ws.playPause();
  else if (target.classList.contains('wsp-zoom-in')) setZoom((element._zoom || 0) + ZOOM_STEP);
  else if (target.classList.contains('wsp-zoom-out')) setZoom((element._zoom || 0) - ZOOM_STEP);
  else if (target.classList.contains('wsp-zoom-fit')) setZoom(0);
});
element.addEventListener('input', (event) => {
  if (event.target.classList.contains('wsp-zoom-range')) setZoom(Number(event.target.value));
});

// Ctrl (ou Cmd) + molette, ou pincement sur pavé tactile : zoom ; molette horizontale ou
// Maj + molette sur les pistes : défilement.
element.addEventListener('wheel', (event) => {
  if (!element._ws || !props.value || !event.target.closest('.wsp-wave, .wsp-viewport')) return;
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault();
    setZoom((element._zoom || 0) + (event.deltaY < 0 ? ZOOM_STEP / 2 : -ZOOM_STEP / 2));
  } else if (event.target.closest('.wsp-viewport') && (element._zoom || 0) > 0
             && (event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY))) {
    event.preventDefault();
    element._ws.setScroll(element._ws.getScroll() + (event.deltaX || event.deltaY));
  }
}, { passive: false });

if (typeof ResizeObserver === 'function') {
  let lastWidth = 0;
  new ResizeObserver(() => {
    const width = element.clientWidth;
    if (width !== lastWidth && props.value && props.value.audio_url && $('.wsp-viewport')) {
      lastWidth = width;
      setZoom(element._zoom || 0);
    }
  }).observe(element);
}

render();
watch('value', render);
