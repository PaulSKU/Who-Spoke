// Visualiseur de l'onglet « Analyse » (D17), exécuté par gr.HTML (js_on_load).
// Forme d'onde dessinée par wavesurfer.js (embarqué dans app/static/, sans CDN) à partir de
// l'enveloppe calculée côté Python ; le son est lu en flux. Une piste par locuteur ; un clic
// sur un segment (piste ou forme d'onde) le fait écouter, de son début à sa fin.
// Zoom (D17, amendement 1) : zoom natif de wavesurfer, dont le rendu paresseux ne dessine
// que la partie visible ; pistes, axe et tête de lecture suivent son défilement.
// Couleurs (D26) : la forme d'onde est neutre ; seul le segment sélectionné (dernier
// segment cliqué) y est mis en évidence, par une bande d'encre, et entouré sur sa piste.
// Carte des erreurs (D26, I4) : avec une référence, trois rangées sous les locuteurs
// (parole manquée, fausse alarme, confusion), dans le même canevas que les pistes, donc
// soumises au même zoom ; chaque zone s'écoute au clic, comme un segment.
// Vue d'ensemble (audit R-U2, chantier B3) : greffon Minimap de wavesurfer, embarqué ; la
// fenêtre visible se déplace à la souris, au doigt ou au clavier (← →), un clic ailleurs
// y amène la lecture. La vue suit la lecture (autoScroll et autoCenter de wavesurfer),
// sauf si on la déplace à la main ; le bouton « Suivre la lecture » le rétablit.
// Appariement (R-U4) : les pistes de la référence portent la couleur et le rang (« → S2 ») du
// locuteur trouvé apparié ; un clic sur une zone d'erreur ouvre « Expliquer cette erreur »
// (catégorie principale, type, durée, locuteurs après appariement, autres constats, calculés
// côté serveur).
// Extrait typique (R-U6) : les boutons ▶ du tableau des locuteurs, hors de ce composant,
// sont écoutés sur le document et lus ici.
// Raccourcis (R-U3) : Espace, ← →, 1 à 9, 0, ? ; inactifs quand le focus est dans un champ
// de saisie, ou quand l'onglet Analyse n'est pas affiché. Pastille « parle : X » pendant
// la lecture, d'après le premier moteur.
// Segments hors de la vue (chantier B8) : masqués dès que le zoom agrandit le canevas. Sur
// 30 min, 2 moteurs et une référence (10 000 segments et zones), les laisser tous affichés
// faisait tomber la lecture suivie à 20 images/s au zoom maximal ; masqués, elle en garde 120.
// Variables fournies par Gradio : element, props, watch.

const MAX_PX_PER_S = 150;   // zoom maximal : 150 px par seconde d'audio (D17 ; B8, mesuré sur 30 min)
const ZOOM_STEP = 10;      // pas des boutons et de Ctrl + molette, sur l'échelle 0–100
const WINDOW_KEY_STEP = 0.1;   // ← → sur la fenêtre de la vue d'ensemble : 10 % de la vue

// Espace fine insécable devant les unités, comme app/formatage.py.
const NNBSP = '\u202f';

function fmt(t) {
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const mm = h ? String(m).padStart(2, '0') : String(m);
  return (h ? h + ':' : '') + mm + ':' + String(s).padStart(2, '0');
}

// Valeur d'un jeton de jetons.css (--ws-*) : wavesurfer et les canevas reçoivent des couleurs,
// pas des variables CSS ; elles sont lues au rendu, dans le mode en vigueur.
function token(name) {
  return getComputedStyle(element).getPropertyValue(name).trim();
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
  const mini = $('.wsp-minimap');
  if (mini) mini.innerHTML = '';
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

// Segments des locuteurs et zones de la carte des erreurs : tout ce qui se sélectionne.
// Clés uniques par groupe (moteur 1, moteur 2, référence) : « a:SPK_00 », « erreur:b:12 ».
function selectables(v) {
  const all = [];
  v.groupes.forEach((group) => {
    group.segments.forEach((seg) => all.push(segKey(group, seg)));
    (group.erreurs ? group.erreurs.zones : []).forEach((zone, index) => all.push(zoneKey(group, zone, index)));
  });
  return all;
}

function segKey(group, seg) {
  return { debut: seg.debut, fin: seg.fin, locuteur: group.id + ':' + seg.locuteur };
}

function zoneKey(group, zone, index) {
  return { debut: zone.debut, fin: zone.fin, locuteur: 'erreur:' + group.id + ':' + index };
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
  const scroll = ws ? ws.getScroll() : 0;
  $('.wsp-canvas').style.transform = 'translateX(' + -scroll + 'px)';
  cullBars(scroll);
  scheduleLayers();
}

// Premier indice de `bars` (triés par début) dont le début vaut au moins `t`.
function firstFrom(bars, t) {
  let lo = 0;
  let hi = bars.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (bars[mid]._t0 < t) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

// N'affiche que les segments et zones d'erreur proches de la partie visible : une largeur de
// vue de part et d'autre. Seuls les éléments qui entrent ou sortent de cette plage changent.
function cullBars(scroll) {
  const v = props.value;
  const bars = element._bars;
  if (!v || !bars || !bars.length) return;
  const width = viewportWidth();
  const pps = ($('.wsp-canvas').clientWidth || width) / v.duree_s;
  const span = width / pps;
  const start = scroll / pps - span;
  const lo = firstFrom(bars, start - element._barMax);
  const hi = firstFrom(bars, start + 3 * span);
  const shown = element._shown || [0, bars.length];
  for (let i = shown[0]; i < shown[1]; i += 1) if (i < lo || i >= hi) bars[i].style.display = 'none';
  for (let i = lo; i < hi; i += 1) if (i < shown[0] || i >= shown[1]) bars[i].style.display = '';
  element._shown = [lo, hi];
}

function drawAxis() {
  const v = props.value;
  const axis = $('.wsp-axis');
  axis.innerHTML = '';
  const width = $('.wsp-canvas').clientWidth || viewportWidth();
  const step = tickStep(v.duree_s, width);
  let last = null;
  for (let t = 0; t <= v.duree_s; t += step) {
    const tick = document.createElement('span');
    tick.className = 'wsp-tick';
    tick.style.left = (100 * t / v.duree_s) + '%';
    tick.textContent = fmt(t);
    axis.appendChild(tick);
    last = { tick, t };
  }
  // Dernière graduation près du bord droit : alignée à droite, pour ne pas être rognée.
  if (last && last.t > 0 && (v.duree_s - last.t) * width / v.duree_s < 32) {
    last.tick.classList.add('wsp-tick-end');
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

// --- Spectrogramme et énergie de la baseline (D28 §2, chantier B9) ------------------
// Image calculée côté serveur (app/spectrogramme.py) : pyramide de spectrogrammes mel sur
// 8 bits, lue une fois. À chaque défilement ou zoom, seule la partie visible est mise en
// couleurs et dessinée, au niveau de la pyramide qui donne au moins une trame par pixel :
// coût constant quelle que soit la durée. La forme d'onde devient transparente et reste
// au-dessus : curseur, sélection et clic pour se déplacer inchangés.

// Hauteur du spectrogramme : --wsp-spec-h de visualiseur.css (112 px, 144 en mode présentation) ;
// forme d'onde : 80 px.
function specHeight() {
  const root = $('.wsp-root');
  const height = root ? parseFloat(getComputedStyle(root).getPropertyValue('--wsp-spec-h')) : NaN;
  return height > 0 ? height : 112;
}
const ENERGY_HEIGHT = 56;   // bande d'énergie : courbe et seuil, puis 6 px pour les régions de parole

function fetchBytes(url, kind) {
  element._files = element._files || {};
  if (!element._files[url]) {
    element._files[url] = fetch(url).then((response) => {
      if (!response.ok) throw new Error(response.status + ' ' + response.statusText);
      return response.arrayBuffer();
    }).then((buffer) => (kind === 'f32' ? new Float32Array(buffer) : new Uint8Array(buffer)));
    element._files[url].catch(() => { delete element._files[url]; });
  }
  return element._files[url];
}

function scheduleLayers() {
  if (element._layersFrame) return;
  element._layersFrame = requestAnimationFrame(() => {
    element._layersFrame = 0;
    drawSpectrogram();
    drawEnergy();
  });
}

// Canevas à la taille affichée, en pixels de l'écran ; renvoie son contexte, ou null.
function fitCanvas(canvas, width, height) {
  const ratio = window.devicePixelRatio || 1;
  canvas.style.width = width + 'px';
  canvas.style.height = height + 'px';
  if (canvas.width !== Math.round(width * ratio) || canvas.height !== Math.round(height * ratio)) {
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return ctx;
}

// Partie visible : défilement (px), largeur (px), pixels par seconde.
function visibleWindow() {
  const ws = element._ws;
  const v = props.value;
  const width = $('.wsp-wave').clientWidth || viewportWidth();
  return { scroll: ws ? ws.getScroll() : 0, width, pps: ws && element._ready ? pxPerSecond() : width / v.duree_s };
}

function drawSpectrogram() {
  const v = props.value;
  const spec = v && v.spectrogramme;
  const canvas = $('.wsp-spec-canvas');
  const data = element._specData;
  if (!canvas || element._view !== 'spectro' || !spec || !data || data.url !== spec.url) return;
  const { scroll, width, pps } = visibleWindow();
  const height = specHeight();
  const ctx = fitCanvas(canvas, width, height);
  // Niveau le plus grossier qui garde au moins une trame par pixel.
  const bands = spec.bandes;
  let level = 0;
  while (level + 1 < spec.niveaux.length && 1 / (spec.pas_s * Math.pow(2, level + 1)) >= pps) level += 1;
  const { decalage, trames } = spec.niveaux[level];
  const columnS = spec.pas_s * Math.pow(2, level);
  // Trame i centrée en i × pas (librosa, center=True) : colonne j de [j·c − pas/2, (j+1)·c − pas/2[.
  const offsetS = -spec.pas_s / 2;
  const first = Math.max(0, Math.floor((scroll / pps - offsetS) / columnS));
  const last = Math.min(trames, Math.ceil(((scroll + width) / pps - offsetS) / columnS) + 1);
  const count = last - first;
  if (count <= 0) return;
  const palette = spec.palettes[isDark() ? 'sombre' : 'clair'];
  const off = element._specOff || (element._specOff = document.createElement('canvas'));
  if (off.width < count) off.width = count;
  if (off.height !== bands) off.height = bands;
  const octx = off.getContext('2d');
  const image = octx.createImageData(count, bands);
  const pixels = image.data;
  const bytes = data.bytes;
  for (let c = 0; c < count; c += 1) {
    const base = decalage + (first + c) * bands;
    for (let m = 0; m < bands; m += 1) {
      const rgb = palette[bytes[base + m]];
      const p = 4 * ((bands - 1 - m) * count + c);   // bande la plus grave en bas
      pixels[p] = rgb[0];
      pixels[p + 1] = rgb[1];
      pixels[p + 2] = rgb[2];
      pixels[p + 3] = 255;
    }
  }
  octx.putImageData(image, 0, 0);
  ctx.imageSmoothingEnabled = true;
  const x0 = (first * columnS + offsetS) * pps - scroll;
  ctx.drawImage(off, 0, 0, count, bands, x0, 0, count * columnS * pps, height);
}

function energyY(db, e) {
  const top = 3;
  const bottom = ENERGY_HEIGHT - 10;
  const ratio = (Math.min(e.max_db, Math.max(e.min_db, db)) - e.min_db) / ((e.max_db - e.min_db) || 1);
  return bottom - ratio * (bottom - top);
}

function drawEnergy() {
  const v = props.value;
  const e = v && v.detection;
  const canvas = $('.wsp-energy-canvas');
  const data = element._energyData;
  if (!canvas || !element._energy || !e || !data || data.url !== e.url) return;
  const { scroll, width, pps } = visibleWindow();
  const ctx = fitCanvas(canvas, width, ENERGY_HEIGHT);
  const styles = getComputedStyle(element);
  const ink = styles.getPropertyValue('--ws-ink').trim();
  const slate = styles.getPropertyValue('--ws-slate').trim();
  const values = data.values;
  const n = values.length;
  // Courbe : minimum et maximum de l'énergie sur chaque pixel (enveloppe), 1,5 px.
  ctx.beginPath();
  for (let x = 0; x <= width; x += 1) {
    let f0 = Math.floor((scroll + x) / pps / e.pas_s);
    let f1 = Math.floor((scroll + x + 1) / pps / e.pas_s);
    if (f0 >= n) break;
    f0 = Math.max(0, f0);
    f1 = Math.min(n - 1, Math.max(f0, f1));
    let low = Infinity;
    let high = -Infinity;
    for (let f = f0; f <= f1; f += 1) {
      if (values[f] < low) low = values[f];
      if (values[f] > high) high = values[f];
    }
    if (x === 0) ctx.moveTo(x, energyY(high, e));
    else ctx.lineTo(x, energyY(high, e));
    if (low !== high) ctx.lineTo(x, energyY(low, e));
  }
  ctx.strokeStyle = slate;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.stroke();
  // Seuil : tirets à l'encre.
  const y = Math.round(energyY(e.seuil_db, e)) + 0.5;
  ctx.beginPath();
  ctx.setLineDash([6, 4]);
  ctx.moveTo(0, y);
  ctx.lineTo(width, y);
  ctx.strokeStyle = ink;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.setLineDash([]);
  // Régions de parole retenues par la détection : bande pleine en bas.
  ctx.fillStyle = ink;
  e.regions.forEach(([start, end]) => {
    const a = start * pps - scroll;
    const b = end * pps - scroll;
    if (b < 0 || a > width) return;
    ctx.fillRect(Math.max(0, a), ENERGY_HEIGHT - 6, Math.max(1, Math.min(width, b) - Math.max(0, a)), 5);
  });
}

function decibels(value) {
  return (value < 0 ? '−' : '') + Math.abs(value).toFixed(1).replace('.', ',') + NNBSP + 'dB';
}

// Infobulle de la bande d'énergie : instant, énergie, position par rapport au seuil.
function energyTip(event) {
  const v = props.value;
  const e = v && v.detection;
  const data = element._energyData;
  const tip = $('.wsp-energy-tip');
  if (!e || !data || !tip) return;
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const { scroll, pps } = visibleWindow();
  const t = (scroll + x) / pps;
  const value = data.values[Math.min(data.values.length - 1, Math.max(0, Math.floor(t / e.pas_s)))];
  const inSpeech = e.regions.some(([a, b]) => a <= t && t < b);
  tip.textContent = fmtTenths(t) + ' : ' + decibels(value) + (value > e.seuil_db ? ', au-dessus du seuil' : ', sous le seuil')
    + (inSpeech ? ' ; parole détectée' : ' ; pas de parole détectée');
  tip.hidden = false;
  tip.style.left = Math.max(0, Math.min(rect.width - tip.offsetWidth, x + 8)) + 'px';
}

function setView(view) {
  const v = props.value;
  if (view === 'spectro' && !(v && v.spectrogramme)) view = 'onde';
  element._view = view;
  const spectro = view === 'spectro';
  const root = $('.wsp-root');
  root.classList.toggle('wsp-spec-on', spectro);
  $('.wsp-view-wave').setAttribute('aria-pressed', spectro ? 'false' : 'true');
  $('.wsp-view-spec').setAttribute('aria-pressed', spectro ? 'true' : 'false');
  const ws = element._ws;
  if (ws && element._waveOptions) {
    const current = ws.options.height;
    const wanted = spectro ? specHeight() : element._waveOptions.height;
    const options = spectro
      ? { height: wanted, waveColor: 'transparent', progressColor: 'transparent' }
      : element._waveOptions;
    if (current !== wanted || ws.options.waveColor !== options.waveColor) ws.setOptions(options);
  }
  fillSpecLegend();
  if (spectro) loadSpectrogram();
  scheduleLayers();
}

function fillSpecLegend() {
  const v = props.value;
  const spec = v && v.spectrogramme;
  const legend = $('.wsp-spec-legend');
  const axis = $('.wsp-spec-axis');
  const canvas = $('.wsp-spec-canvas');
  const spectro = element._view === 'spectro' && !!spec;
  legend.hidden = !spectro;
  axis.innerHTML = '';
  if (!spectro) return;
  (spec.graduations || []).forEach((tick) => {
    const label = document.createElement('span');
    label.className = 'wsp-spec-tick';
    label.style.top = (100 * tick.y) + '%';
    label.textContent = tick.libelle;
    axis.appendChild(label);
  });
  const palette = spec.palettes[isDark() ? 'sombre' : 'clair'];
  const css = (rgb) => 'rgb(' + rgb.join(',') + ')';
  $('.wsp-spec-swatch').style.background = 'linear-gradient(90deg, ' + css(palette[0]) + ', ' + css(palette[palette.length - 1]) + ')';
  const pending = !element._specData || element._specData.url !== spec.url;
  const text = 'Spectrogramme mel dont la baseline tire ses MFCC (' + spec.bandes + ' bandes, trames de '
    + Math.round(spec.trame_s * 1000) + ' ms tous les ' + Math.round(spec.pas_s * 1000) + ' ms), '
    + spec.plage_db + ' dB sous le maximum du fichier : ' + (isDark() ? 'plus clair' : 'plus foncé')
    + ' = plus d\'énergie.';
  $('.wsp-spec-text').textContent = element._specError ? 'Spectrogramme indisponible : ' + element._specError
    : (pending ? 'Chargement du spectrogramme… ' : '') + text;
  canvas.setAttribute('aria-label', 'Spectrogramme mel du fichier, de ' + spec.graduations[0].libelle + ' à '
    + spec.graduations[spec.graduations.length - 1].libelle + ' ; même zoom et même défilement que la timeline');
}

function loadSpectrogram() {
  const spec = props.value && props.value.spectrogramme;
  if (!spec || (element._specData && element._specData.url === spec.url)) return;
  element._specError = null;
  fetchBytes(spec.url, 'u8').then((bytes) => {
    if (!props.value || !props.value.spectrogramme || props.value.spectrogramme.url !== spec.url) return;
    element._specData = { url: spec.url, bytes };
    fillSpecLegend();
    scheduleLayers();
  }).catch((error) => {
    element._specError = String(error.message || error);
    fillSpecLegend();
  });
}

function setEnergy(on) {
  const v = props.value;
  const e = v && v.detection;
  element._energy = !!on && !!e;
  const button = $('.wsp-energy-toggle');
  button.hidden = !e;
  button.setAttribute('aria-pressed', element._energy ? 'true' : 'false');
  $('.wsp-energy').hidden = !element._energy;
  const legend = $('.wsp-energy-legend');
  legend.hidden = !element._energy;
  if (!e) return;
  button.title = 'Courbe d\'énergie et seuil de la détection de parole de ' + e.moteur + ' (D19)';
  $('.wsp-energy-sub').textContent = e.moteur + ', seuil ' + decibels(e.seuil_db);
  legend.textContent = (e.factice
    ? 'Trace factice (moteur factice) : énergie par tranche de 10 ms et seuil à la médiane, pas la détection de la baseline. '
    : 'Détection de parole de ' + e.moteur + ' (D19), lue dans la trace du moteur. ')
    + 'Courbe : énergie par trame de ' + Math.round(e.pas_s * 1000) + ' ms ; tirets : seuil ('
    + decibels(e.seuil_db) + ') ; bande du bas : parole retenue'
    + (e.factice ? '' : ' après lissage médian et durées minimales') + '.';
  $('.wsp-energy-canvas').setAttribute('aria-label', 'Énergie par trame et seuil de détection ('
    + decibels(e.seuil_db) + ') ; ' + e.regions.length + ' régions de parole');
  if (!element._energy) return;
  if (!element._energyData || element._energyData.url !== e.url) {
    fetchBytes(e.url, 'f32').then((values) => {
      if (!props.value || !props.value.detection || props.value.detection.url !== e.url) return;
      element._energyData = { url: e.url, values };
      scheduleLayers();
    }).catch((error) => { legend.textContent = 'Énergie indisponible : ' + (error.message || error); });
  }
  scheduleLayers();
}

// --- Suivi de la lecture et vue d'ensemble -----------------------------------------

function setFollow(on) {
  element._follow = on;
  const button = $('.wsp-follow');
  if (button) button.setAttribute('aria-pressed', on ? 'true' : 'false');
  const ws = element._ws;
  if (!ws || !element._ready) return;
  ws.setOptions({ autoScroll: on, autoCenter: on });
  if (on) reveal(ws.getCurrentTime(), true);
}

function pxPerSecond() {
  const ws = element._ws;
  const v = props.value;
  return ws && v ? (ws.getWrapper().clientWidth || 1) / v.duree_s : 1;
}

// Amène l'instant `t` à l'écran (au centre si `center` ou s'il est hors de la vue).
function reveal(t, center) {
  const ws = element._ws;
  if (!ws) return;
  const x = t * pxPerSecond();
  const left = ws.getScroll();
  const width = ws.getWidth();
  if (center || x < left || x > left + width) ws.setScroll(Math.max(0, x - width / 2));
}

function updateWindowLabel() {
  const overlay = element._overlay;
  const ws = element._ws;
  const v = props.value;
  if (!overlay || !ws || !v) return;
  const pps = pxPerSecond();
  const start = ws.getScroll() / pps;
  const end = Math.min(v.duree_s, start + ws.getWidth() / pps);
  overlay.setAttribute('aria-valuenow', String(Math.round(start)));
  overlay.setAttribute('aria-valuetext', 'de ' + fmt(start) + ' à ' + fmt(end));
}

// Fenêtre visible de la vue d'ensemble : le greffon la dessine sans la rendre déplaçable.
function initWindow(overlay) {
  const v = props.value;
  element._overlay = overlay;
  overlay.classList.add('wsp-window');
  overlay.style.pointerEvents = 'auto';
  overlay.style.zIndex = '10';   // au-dessus du curseur et des couches de la forme d'onde miniature
  overlay.tabIndex = 0;
  overlay.setAttribute('role', 'slider');
  overlay.setAttribute('aria-label', 'Partie visible de la timeline ; ← → pour la déplacer');
  overlay.setAttribute('aria-valuemin', '0');
  overlay.setAttribute('aria-valuemax', String(Math.round(v.duree_s)));
  overlay.addEventListener('pointerdown', (event) => {
    const ws = element._ws;
    if (!ws) return;
    event.preventDefault();
    event.stopPropagation();
    overlay.setPointerCapture(event.pointerId);
    overlay.style.transition = 'none';
    overlay.classList.add('wsp-dragging');
    setFollow(false);
    const startX = event.clientX;
    const startScroll = ws.getScroll();
    const ratio = (ws.getWrapper().clientWidth || 1) / (overlay.parentElement.clientWidth || 1);
    const move = (e) => ws.setScroll(startScroll + (e.clientX - startX) * ratio);
    const up = () => {
      overlay.removeEventListener('pointermove', move);
      overlay.removeEventListener('pointerup', up);
      overlay.removeEventListener('pointercancel', up);
      overlay.classList.remove('wsp-dragging');
      overlay.style.transition = '';
    };
    overlay.addEventListener('pointermove', move);
    overlay.addEventListener('pointerup', up);
    overlay.addEventListener('pointercancel', up);
  });
  overlay.addEventListener('click', (event) => event.stopPropagation());
  overlay.addEventListener('keydown', (event) => {
    const ws = element._ws;
    if (!ws || (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight')) return;
    event.preventDefault();
    event.stopPropagation();   // ← → déplacent la fenêtre, pas le tour en cours
    setFollow(false);
    const step = ws.getWidth() * WINDOW_KEY_STEP;
    ws.setScroll(ws.getScroll() + (event.key === 'ArrowRight' ? step : -step));
  });
  updateWindowLabel();
}

// --- Pastille « parle : X », isolement d'un locuteur, tours --------------------------

function speakingAt(t) {
  const names = [];
  (element._turns || []).forEach((seg) => {
    if (seg.debut <= t && t < seg.fin && !names.some((n) => n.id === seg.locuteur)) {
      names.push({ id: seg.locuteur, nom: seg.nom, couleur: element._colors['a:' + seg.locuteur] });
    }
  });
  return names;
}

function showSpeaking(t) {
  const pill = $('.wsp-speaking');
  if (!pill) return;
  const ws = element._ws;
  if (!ws || !ws.isPlaying()) {
    pill.hidden = true;
    return;
  }
  const who = speakingAt(t);
  pill.hidden = false;
  pill.innerHTML = '';
  if (!who.length) {
    pill.textContent = 'silence';
    pill.dataset.state = 'silence';
    return;
  }
  pill.dataset.state = 'parle';
  pill.appendChild(document.createTextNode(who.length > 1 ? 'parlent : ' : 'parle : '));
  who.forEach((spk, index) => {
    if (index) pill.appendChild(document.createTextNode(', '));
    const swatch = document.createElement('span');
    swatch.className = 'wsp-swatch';
    swatch.style.background = spk.couleur;
    pill.appendChild(swatch);
    const name = document.createElement('strong');
    name.textContent = spk.nom;
    pill.appendChild(name);
  });
}

function isolate(n) {
  const v = props.value;
  const speakers = v && v.groupes.length ? v.groupes[0].locuteurs : [];
  if (n === 0) element._iso = null;
  else if (n <= speakers.length) element._iso = speakers[n - 1].id;
  else return;
  applyIsolation();
}

// Clic sur le nom d'un locuteur du premier moteur : l'isole, ou rend tous les locuteurs
// s'il l'était déjà. Seul moyen au-delà de 9 locuteurs (touches 1 à 9).
function toggleIsolation(id) {
  element._iso = element._iso === id ? null : id;
  applyIsolation();
}

function applyIsolation() {
  const v = props.value;
  const iso = element._iso;
  const speakers = v && v.groupes.length ? v.groupes[0].locuteurs : [];
  if (iso && !speakers.some((spk) => spk.id === iso)) element._iso = null;
  Object.entries(element._rows || {}).forEach(([id, row]) => {
    const dim = !!element._iso && id !== element._iso;
    row.forEach((el) => el.classList.toggle('wsp-dim', dim));
  });
  const chip = $('.wsp-iso');
  if (!chip) return;
  const spk = speakers.find((s) => s.id === element._iso);
  chip.hidden = !spk;
  chip.textContent = spk ? 'Isolé : ' + spk.nom + ' (0 pour tous)' : '';
}

function turns() {
  const all = element._turns || [];
  return element._iso ? all.filter((seg) => seg.locuteur === element._iso) : all;
}

function jumpTurn(direction) {
  const ws = element._ws;
  const list = turns();
  if (!ws || !list.length) return;
  const t = ws.getCurrentTime();
  let target;
  if (direction > 0) {
    target = list.find((seg) => seg.debut > t + 0.05);
  } else {
    // Plus de 0,3 s après le début du tour en cours : retour à son début ; sinon tour précédent.
    const before = list.filter((seg) => seg.debut < t - 0.3);
    target = before[before.length - 1];
  }
  if (!target) return;
  element._selected = segKey({ id: 'a' }, target);
  markSelected();
  drawSelection();
  ws.setTime(target.debut);
  if (!(element._follow && ws.isPlaying())) reveal(target.debut);
  showSpeaking(target.debut);
}

// --- « Expliquer cette erreur » (R-U4) ----------------------------------------------

const ERROR_TITLES = { manquee: 'Parole manquée', fausse_alarme: 'Fausse alarme', confusion: 'Confusion' };

function seconds(value) {
  return value.toFixed(2).replace('.', ',') + NNBSP + 's';
}

// « 1:30,4 » : au dixième de seconde, pour les zones courtes.
function fmtTenths(t) {
  const tenths = Math.round(t * 10);
  return fmt(Math.floor(tenths / 10)) + ',' + (tenths % 10);
}

// Intervalle et durée d'un segment ou d'une zone : au dixième de seconde et durée au
// centième sous la seconde, pour qu'un tour de 50 ms ne s'affiche pas « 0:00 – 0:00 (0,0 s) ».
function fmtSpan(start, end) {
  const length = end - start;
  const short = length < 1;
  const shown = short ? length.toFixed(2) : length.toFixed(1);
  return {
    range: short ? fmtTenths(start) + ' – ' + fmtTenths(end) : fmt(start) + ' – ' + fmt(end),
    words: short ? fmtTenths(start) + ' à ' + fmtTenths(end) : fmt(start) + ' à ' + fmt(end),
    length: shown.replace('.', ',') + NNBSP + 's',
  };
}

function explain(group, index) {
  const panel = $('.wsp-explain');
  const errors = group && group.erreurs;
  const zone = errors && errors.zones[index];
  if (!panel || !zone) return;
  element._explained = { group: group.id, index };
  const names = {};
  group.locuteurs.forEach((spk) => { names[spk.id] = spk.nom; });
  const pairs = errors.appariement || {};
  const pairedRef = {};
  Object.entries(pairs).forEach(([ref, hyp]) => { pairedRef[hyp] = ref; });
  const refText = (ref) => {
    if (!ref) return '—';
    const hyp = pairs[ref];
    return ref + (hyp ? ' (apparié à ' + (names[hyp] || hyp) + ')' : ' (non apparié)');
  };
  const hypText = (hyp) => {
    if (!hyp) return '— (aucun locuteur trouvé sur cette parole)';
    const ref = pairedRef[hyp];
    return (names[hyp] || hyp) + (ref ? ' (apparié à ' + ref + ')' : ' (non apparié)');
  };
  const several = props.value.groupes.filter((g) => g.erreurs).length > 1;
  $('.wsp-explain-title').textContent = (several ? group.titre + ' : ' : '') + ERROR_TITLES[zone.type]
    + ', ' + fmtTenths(zone.debut) + ' – ' + fmtTenths(zone.fin);
  const facts = $('.wsp-explain-facts');
  facts.innerHTML = '';
  [['Type', ERROR_TITLES[zone.type]],
   ['Durée', seconds(zone.fin - zone.debut) + ' (de ' + fmtTenths(zone.debut) + ' à ' + fmtTenths(zone.fin) + ')'],
   ['Locuteur de référence', refText(zone.reference)],
   ['Locuteur trouvé', hypText(zone.hypothese)]].forEach(([term, value]) => {
    const dt = document.createElement('dt');
    dt.textContent = term;
    const dd = document.createElement('dd');
    dd.textContent = value;
    facts.appendChild(dt);
    facts.appendChild(dd);
  });
  // Catégorie principale (une seule, exclusive : app/sortie.py), puis les autres constats.
  $('.wsp-explain-cat-name').textContent = zone.categorie_libelle || '';
  $('.wsp-explain-cat-text').textContent = zone.categorie_texte ? '. ' + zone.categorie_texte : '';
  $('.wsp-explain-cat-tol').textContent = zone.categorie_tolerance || '';   // option b : part pardonnée
  $('.wsp-explain-cat').hidden = !zone.categorie_libelle;
  const list = $('.wsp-explain-context');
  list.innerHTML = '';
  (zone.constats || []).forEach((text) => {
    const item = document.createElement('li');
    item.textContent = text;
    list.appendChild(item);
  });
  list.hidden = !list.children.length;
  $('.wsp-explain-sub').hidden = !list.children.length;
  panel.hidden = false;
}

function closeExplain() {
  const panel = $('.wsp-explain');
  if (panel) panel.hidden = true;
  element._explained = null;
}

// Extrait typique : lu comme un segment, repéré par une bande sur la forme d'onde.
function playExcerpt(start, end) {
  const ws = element._ws;
  if (!ws) return;
  element._selected = { debut: start, fin: end, locuteur: 'extrait', extrait: true };
  markSelected();
  drawSelection();
  reveal(start);
  playSegment(start, end);
}

function toggleHelp(open) {
  const help = $('.wsp-help');
  const button = $('.wsp-help-toggle');
  if (!help) return;
  const show = open === undefined ? help.hidden : open;
  help.hidden = !show;
  if (button) button.setAttribute('aria-expanded', show ? 'true' : 'false');
}

function fillHelpSpeakers(v) {
  const list = $('.wsp-help-speakers');
  if (!list) return;
  list.innerHTML = '';
  const all = v.groupes.length ? v.groupes[0].locuteurs : [];
  const speakers = all.slice(0, 9);
  speakers.forEach((spk, index) => {
    const item = document.createElement('li');
    const key = document.createElement('kbd');
    key.textContent = String(index + 1);
    item.appendChild(key);
    item.appendChild(document.createTextNode(' ' + spk.nom));
    list.appendChild(item);
  });
  if (all.length > 9) {
    const item = document.createElement('li');
    const rest = all.length - 9;
    item.textContent = rest + (rest > 1 ? ' autres locuteurs : cliquer sur leur nom' : ' autre locuteur : cliquer sur son nom')
      + ' dans la timeline.';
    list.appendChild(item);
  }
}

// --- Dessin -----------------------------------------------------------------------

function drawSelection() {
  const v = props.value;
  const regions = element._regions;
  if (!regions || !v || !element._ready) return;
  regions.clearRegions();
  const s = element._selected;
  if (!s || (!s.extrait && !selectables(v).some(isSelected))) return;
  regions.addRegion({
    start: s.debut, end: s.fin, color: token('--ws-selection'),
    drag: false, resize: false,
  });
}

function caption(labels, lanes, text, title) {
  const label = document.createElement('div');
  label.className = 'wsp-label wsp-caption';
  label.textContent = text;
  if (title) label.title = title;
  labels.appendChild(label);
  const spacer = document.createElement('div');
  spacer.className = 'wsp-spacer';
  lanes.appendChild(spacer);
}

function addRow(labels, lanes, text, title, swatchClass, swatchColor) {
  const label = document.createElement('div');
  label.className = 'wsp-label';
  const swatch = document.createElement('span');
  swatch.className = 'wsp-swatch' + (swatchClass ? ' ' + swatchClass : '');
  if (swatchColor) swatch.style.background = swatchColor;
  label.appendChild(swatch);
  // Texte dans son propre bloc : un nom trop long finit par « … » (nom complet en info-bulle).
  const name = document.createElement('span');
  name.className = 'wsp-label-text';
  name.textContent = text;
  label.appendChild(name);
  label.title = title;
  labels.appendChild(label);
  const track = document.createElement('div');
  track.className = 'wsp-track';
  lanes.appendChild(track);
  return track;
}

// Groupes superposés dans le même canevas (D26, I5) : pistes de chaque groupe, puis la
// carte des erreurs de chaque moteur. Un seul groupe sans erreurs : pas de légende.
function drawLanes(v) {
  const labels = $('.wsp-labels');
  const lanes = $('.wsp-lanes');
  labels.innerHTML = '';
  lanes.innerHTML = '';
  const several = v.groupes.length > 1;
  element._rows = {};
  element._turns = [];
  element._bars = [];
  element._shown = null;
  v.groupes.forEach((group, groupIndex) => {
    if (several) caption(labels, lanes, group.titre, group.titre);
    const names = {};
    const tracks = {};
    group.locuteurs.forEach((spk) => {
      names[spk.id] = spk.nom;
      tracks[spk.id] = addRow(labels, lanes, spk.nom, spk.titre || spk.nom + ' (' + spk.id + ')', '',
                              element._colors[group.id + ':' + spk.id]);
      if (groupIndex === 0) {
        const label = labels.lastChild;
        element._rows[spk.id] = [label, tracks[spk.id]];
        label.classList.add('wsp-label-iso');
        label.setAttribute('role', 'button');
        label.tabIndex = 0;
        label.title = spk.nom + ' (' + spk.id + ') : cliquer pour l\'isoler, ou pour revenir à tous';
        label.addEventListener('click', () => toggleIsolation(spk.id));
        label.addEventListener('keydown', (event) => {
          if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggleIsolation(spk.id); }
        });
      }
    });
    // Aucun locuteur (silence, aucune parole trouvée) : une piste vide le dit.
    if (!group.locuteurs.length) addRow(labels, lanes, 'Aucun locuteur', 'Aucun locuteur détecté', '', '');
    if (groupIndex === 0) {
      element._turns = group.segments
        .map((seg) => ({ debut: seg.debut, fin: seg.fin, locuteur: seg.locuteur, nom: names[seg.locuteur] }))
        .sort((a, b) => a.debut - b.debut || a.fin - b.fin);
    }
    group.segments.forEach((seg) => {
      const bar = document.createElement('button');
      bar.type = 'button';
      bar.className = 'wsp-seg';
      bar.style.left = (100 * seg.debut / v.duree_s) + '%';
      bar.style.width = (100 * (seg.fin - seg.debut) / v.duree_s) + '%';
      bar.style.background = element._colors[group.id + ':' + seg.locuteur];
      const who = (several ? group.titre + ', ' : '') + names[seg.locuteur];
      const span = fmtSpan(seg.debut, seg.fin);
      bar.setAttribute('aria-label', who + ', ' + span.words);
      bar.title = who + ' : ' + span.range + ' (' + span.length + '). Cliquer pour écouter.';
      bar._seg = segKey(group, seg);
      bar._t0 = seg.debut;
      bar._t1 = seg.fin;
      element._bars.push(bar);
      bar.addEventListener('click', () => selectSegment(bar._seg));
      tracks[seg.locuteur].appendChild(bar);
    });
  });
  drawErrors(v, labels, lanes);
  element._bars.sort((a, b) => a._t0 - b._t0);
  element._barMax = element._bars.reduce((longest, bar) => Math.max(longest, bar._t1 - bar._t0), 0);
  applyIsolation();
  fillHelpSpeakers(v);
  const open = element._explained;
  const group = open && v.groupes.find((g) => g.id === open.group);
  if (group && group.erreurs && group.erreurs.zones[open.index]) explain(group, open.index);
  else closeExplain();
}

const ERROR_TEXT = {
  manquee: (z, names) => 'Parole manquée : ' + z.reference + ' (référence)',
  fausse_alarme: (z, names) => 'Fausse alarme : ' + (names[z.hypothese] || z.hypothese),
  confusion: (z, names) => 'Confusion : parole de ' + z.reference + ' (référence) attribuée à '
    + (names[z.hypothese] || z.hypothese),
};

function drawErrors(v, labels, lanes) {
  const summary = $('.wsp-errsum');
  const withErrors = v.groupes.filter((group) => group.erreurs);
  summary.innerHTML = '';
  summary.hidden = !withErrors.length;
  withErrors.forEach((group) => {
    const names = {};
    group.locuteurs.forEach((spk) => { names[spk.id] = spk.nom; });
    const errors = group.erreurs;
    // La carte est calculée sans collar seulement : l'écran le dit (D26, amendement du 01/11).
    const title = 'Erreurs sans collar' + (withErrors.length > 1 || v.groupes.length > 1 ? ', ' + group.titre : '');
    caption(labels, lanes, title, 'Après appariement optimal des locuteurs, sans collar, chevauchements comptés');
    const tracks = {};
    errors.rangees.forEach((row) => {
      tracks[row.type] = addRow(labels, lanes, row.libelle,
                                row.libelle + ' : ' + row.duree + ' (' + row.part + ' du DER sans collar)',
                                'wsp-err-' + row.type, null);
    });
    errors.zones.forEach((zone, index) => {
      const bar = document.createElement('button');
      bar.type = 'button';
      bar.className = 'wsp-seg wsp-err-' + zone.type;
      bar.style.left = (100 * zone.debut / v.duree_s) + '%';
      bar.style.width = (100 * (zone.fin - zone.debut) / v.duree_s) + '%';
      const span = fmtSpan(zone.debut, zone.fin);
      const text = (withErrors.length > 1 ? group.titre + ', ' : '') + ERROR_TEXT[zone.type](zone, names)
        + ', ' + span.range;
      bar.setAttribute('aria-label', text);
      bar.title = text + ' (' + span.length + '). Cliquer pour écouter et expliquer.';
      bar._seg = zoneKey(group, zone, index);
      bar._t0 = zone.debut;
      bar._t1 = zone.fin;
      element._bars.push(bar);
      bar.setAttribute('aria-controls', 'wsp-explain');
      bar.addEventListener('click', () => {
        selectSegment(bar._seg);
        explain(group, index);
      });
      tracks[zone.type].appendChild(bar);
    });
    const line = document.createElement('span');
    line.className = 'wsp-errline';
    line.textContent = (withErrors.length > 1 ? group.titre + ', erreurs sans collar : ' : 'Erreurs sans collar : ') + errors.rangees
      .map((row) => row.libelle.toLowerCase() + ' ' + row.duree + ' (' + row.part + ')').join(' · ') + '.';
    summary.appendChild(line);
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
  v.groupes.forEach((group) => group.locuteurs.forEach((spk) => {
    element._colors[group.id + ':' + spk.id] = dark ? spk.couleur_sombre : spk.couleur;
  }));

  const wave = $('.wsp-wave');
  let ws = element._ws;
  if (!ws || element._url !== v.audio_url || !wave.contains(ws.getWrapper())) {
    // Après un renommage, le gabarit est redessiné : même position et même zoom.
    const same = element._url === v.audio_url;
    const resume = same ? (element._t || 0) : 0;
    const zoom = same ? (element._zoom || 0) : 0;
    if (!same) {
      element._selected = null;  // nouveau fichier : aucune sélection
      element._iso = null;
      element._explained = null;
      element._specData = null;
      element._energyData = null;
      element._files = {};
    }
    if (element._follow === undefined) element._follow = true;
    destroy();
    wave.innerHTML = '';
    const regions = WaveSurfer.Regions.create();
    const minimap = WaveSurfer.Minimap.create({
      container: $('.wsp-minimap'),
      height: 32,
      waveColor: token('--ws-wave'),
      progressColor: token('--ws-wave-progress'),
      cursorColor: token('--ws-ink'),
      cursorWidth: 1,
      barWidth: 1,
      barGap: 1,
      overlayColor: token('--ws-wave-overlay'),
    });
    // Couleurs de la forme d'onde, rendues en revenant de la vue spectrogramme.
    element._waveOptions = { height: 80, waveColor: token('--ws-wave'), progressColor: token('--ws-wave-progress') };
    const spectro = element._view === 'spectro' && !!v.spectrogramme;
    ws = WaveSurfer.create({
      container: wave,
      height: spectro ? specHeight() : 80,
      waveColor: spectro ? 'transparent' : element._waveOptions.waveColor,
      progressColor: spectro ? 'transparent' : element._waveOptions.progressColor,
      cursorColor: token('--ws-ink'),
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      autoScroll: element._follow,
      autoCenter: element._follow,
      url: v.audio_url,
      peaks: [v.peaks],
      duration: v.duree_s,
      plugins: [regions, minimap],
    });
    initWindow(minimap.overlay || $('.wsp-minimap [part="minimap-overlay"]'));
    // Clic sur la vue d'ensemble hors de la fenêtre : le greffon y amène la lecture ; la vue suit.
    minimap.on('click', (relativeX) => reveal(relativeX * v.duree_s, true));
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
      showSpeaking(t);
    };
    ws.on('timeupdate', show);
    // Icône et libellé du bouton : l'icône montre l'action, le libellé aussi (« Pause » en lecture).
    const playing = (on) => {
      button.toggleAttribute('data-playing', on);
      button.querySelector('.wsp-play-text').textContent = on ? 'Pause' : 'Lecture';
    };
    ws.on('play', () => { playing(true); showSpeaking(ws.getCurrentTime()); });
    ws.on('pause', () => { playing(false); showSpeaking(ws.getCurrentTime()); });
    ws.on('scroll', () => { syncScroll(); updateWindowLabel(); });
    ws.on('zoom', () => { syncScroll(); updateWindowLabel(); });
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
  $('.wsp-view-spec').disabled = !v.spectrogramme;
  $('.wsp-view-spec').title = v.spectrogramme ? 'Spectrogramme mel, même zoom que la timeline (D28)'
    : 'Spectrogramme indisponible pour ce résultat';
  setView(element._view || 'onde');
  setEnergy(element._energy);
  setZoom(element._zoom || 0);
}

// --- Commandes ---------------------------------------------------------------------
// Délégation sur l'élément racine : Gradio peut redessiner le gabarit (renommage), les
// écouteurs posés sur les boutons eux-mêmes seraient alors perdus.

element.addEventListener('click', (event) => {
  const target = event.target.closest('button');
  if (!target || !element._ws) return;
  if (target.classList.contains('wsp-explain-close')) closeExplain();
  else if (target.classList.contains('wsp-help-toggle')) toggleHelp();
  else if (target.classList.contains('wsp-follow')) setFollow(!element._follow);
  else if (target.classList.contains('wsp-play')) element._ws.playPause();
  else if (target.classList.contains('wsp-zoom-in')) setZoom((element._zoom || 0) + ZOOM_STEP);
  else if (target.classList.contains('wsp-zoom-out')) setZoom((element._zoom || 0) - ZOOM_STEP);
  else if (target.classList.contains('wsp-zoom-fit')) setZoom(0);
  else if (target.classList.contains('wsp-zoom-toggle')) {
    // Petit écran : zoom et options d'affichage repliés derrière la loupe (V5).
    const open = !$('.wsp-root').classList.contains('wsp-zoom-open');
    $('.wsp-root').classList.toggle('wsp-zoom-open', open);
    target.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  else if (target.classList.contains('wsp-view-wave')) setView('onde');
  else if (target.classList.contains('wsp-view-spec')) setView('spectro');
  else if (target.classList.contains('wsp-energy-toggle')) setEnergy(!element._energy);
});
element.addEventListener('pointermove', (event) => {
  if (event.target.classList && event.target.classList.contains('wsp-energy-canvas')) energyTip(event);
});
element.addEventListener('pointerout', (event) => {
  if (event.target.classList && event.target.classList.contains('wsp-energy-canvas')) $('.wsp-energy-tip').hidden = true;
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
    setFollow(false);   // défilement à la main : la vue cesse de suivre la lecture
    element._ws.setScroll(element._ws.getScroll() + (event.deltaX || event.deltaY));
  }
}, { passive: false });

// --- Raccourcis clavier (R-U3) ------------------------------------------------------
// Écouteur sur le document, posé une seule fois par visualiseur. Inactif quand le focus
// est dans un champ de saisie (y compris le tableau de renommage), avec un modificateur,
// ou quand le visualiseur n'est pas affiché (autre onglet, aucun résultat).

const TYPING = 'input, textarea, select, [contenteditable=""], [contenteditable="true"], '
  + '[role="textbox"], [role="combobox"], [role="listbox"], [role="spinbutton"]';

function typing(node) {
  return node instanceof Element && !!node.closest(TYPING);
}

function onKey(event) {
  if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
  const v = props.value;
  if (!v || !v.audio_url || !element._ws || !element.isConnected || element.offsetParent === null) return;
  const active = document.activeElement;
  if (typing(event.target) || typing(active)) return;
  const inViewer = !!active && element.contains(active);
  const onControl = !!active && active !== document.body && !inViewer
    && !!active.closest('button, a, summary, [role="button"], [role="tab"], [role="radio"], [role="slider"]');
  const key = event.key;
  if (key === ' ' || key === 'Spacebar') {
    if (onControl) return;   // Espace sur un bouton hors du visualiseur : action du bouton
    event.preventDefault();
    element._ws.playPause();
  } else if (key === 'ArrowLeft' || key === 'ArrowRight') {
    if (onControl) return;
    event.preventDefault();
    jumpTurn(key === 'ArrowRight' ? 1 : -1);
  } else if (/^[0-9]$/.test(key)) {
    event.preventDefault();
    isolate(Number(key));
  } else if (key === '?') {
    event.preventDefault();
    toggleHelp();
  } else if (key === 'Escape') {
    if (!$('.wsp-help').hidden) toggleHelp(false);
    else if (!$('.wsp-explain').hidden) closeExplain();
  }
}

if (element._onKey) document.removeEventListener('keydown', element._onKey);
element._onKey = onKey;
document.addEventListener('keydown', onKey);

function onExcerpt(event) {
  const button = event.target instanceof Element && event.target.closest('.ws-excerpt[data-debut]');
  if (!button || !element._ws) return;
  playExcerpt(Number(button.dataset.debut), Number(button.dataset.fin));
}

if (element._onExcerpt) document.removeEventListener('click', element._onExcerpt);
element._onExcerpt = onExcerpt;
document.addEventListener('click', onExcerpt);

// Mode présentation basculé (presentation.js) : la colonne des noms change de largeur, et
// avec elle la largeur visible des pistes ; le zoom est recalculé.
function onPresentation() {
  if (!(props.value && props.value.audio_url && $('.wsp-viewport'))) return;
  setView(element._view || 'onde');   // hauteur du spectrogramme propre au mode présentation
  setZoom(element._zoom || 0);
}

if (element._onPresentation) document.removeEventListener('ws-presentation', element._onPresentation);
element._onPresentation = onPresentation;
document.addEventListener('ws-presentation', onPresentation);

// Thème clair ou sombre basculé : spectrogramme, légende et bande d'énergie redessinés.
if (element._themeObserver) element._themeObserver.disconnect();
element._themeObserver = new MutationObserver(() => {
  if (!props.value || !props.value.audio_url) return;
  fillSpecLegend();
  scheduleLayers();
});
[document.documentElement, document.body].forEach((node) => {
  element._themeObserver.observe(node, { attributes: true, attributeFilter: ['class'] });
});

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
