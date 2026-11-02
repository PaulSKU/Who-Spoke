// Mode présentation (chantier B8) : vidéoprojecteur ou écran partagé, lu de loin. L'état est
// la classe ws-presentation de <html> (règles dans interface.css et visualiseur.css), posée
// au chargement par --presentation (window.WS_PRESENTATION) et basculée par le bouton
// « Mode présentation » de l'en-tête. Gradio redessine l'en-tête pendant le préchauffage :
// aria-pressed y est alors resynchronisé.
(() => {
  const root = document.documentElement;
  if (window.WS_PRESENTATION) root.classList.add('ws-presentation');

  const sync = () => {
    const on = root.classList.contains('ws-presentation');
    document.querySelectorAll('.ws-present').forEach((button) => {
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  };

  document.addEventListener('click', (event) => {
    if (!event.target.closest('.ws-present')) return;
    root.classList.toggle('ws-presentation');
    sync();
    // Colonne des noms et largeur des pistes changent : le visualiseur recalcule son zoom.
    document.dispatchEvent(new Event('ws-presentation'));
  });

  const watch = () => {
    const header = document.querySelector('.ws-header');
    if (!header) {
      setTimeout(watch, 200);
      return;
    }
    sync();
    new MutationObserver(sync).observe(header.closest('.block') || header.parentElement,
                                       { childList: true, subtree: true });
  };
  watch();
})();
