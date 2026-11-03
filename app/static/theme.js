// Sélecteur de thème de l'en-tête (B14) : Clair, Sombre, Système. Il remplace le bouton
// « Settings » du pied de page de Gradio, masqué depuis B1. Le thème est la classe « dark »
// de <body>, celle que pose Gradio : on la bascule sans recharger la page (le visualiseur
// observe cette classe et redessine ses couleurs). Choix mémorisé dans localStorage, lectures
// et écritures protégées (navigation privée, stockage bloqué) ; repli sur Système. Le
// paramètre d'URL ?__theme= l'emporte au chargement et suit le choix (history.replaceState),
// comme le faisait le bouton de Gradio.
(() => {
  const KEY = 'ws-theme';
  const CHOICES = ['clair', 'sombre', 'systeme'];
  const FROM_URL = { light: 'clair', dark: 'sombre' };
  const TO_URL = { clair: 'light', sombre: 'dark' };
  const media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;

  const read = () => {
    try {
      return window.localStorage.getItem(KEY);
    } catch (error) {
      return null;
    }
  };
  const write = (value) => {
    try {
      window.localStorage.setItem(KEY, value);
    } catch (error) {
      // stockage indisponible : le choix vaut pour la page ouverte
    }
  };

  const initial = () => {
    const param = new URLSearchParams(window.location.search).get('__theme');
    if (FROM_URL[param]) return FROM_URL[param];
    const stored = read();
    return CHOICES.includes(stored) ? stored : 'systeme';
  };
  let choice = initial();

  const sync = () => {
    document.querySelectorAll('.ws-theme [data-theme]').forEach((button) => {
      button.setAttribute('aria-pressed', button.dataset.theme === choice ? 'true' : 'false');
    });
  };
  const apply = () => {
    const dark = choice === 'sombre' || (choice === 'systeme' && !!media && media.matches);
    if (document.body && document.body.classList.contains('dark') !== dark) {
      document.body.classList.toggle('dark', dark);
    }
    sync();
  };

  document.addEventListener('click', (event) => {
    const button = event.target.closest('.ws-theme [data-theme]');
    if (!button) return;
    choice = button.dataset.theme;
    write(choice);
    const url = new URL(window.location.href);
    if (TO_URL[choice]) url.searchParams.set('__theme', TO_URL[choice]);
    else url.searchParams.delete('__theme');
    window.history.replaceState(window.history.state, '', url);
    apply();
  });

  // Gradio suit lui aussi le thème du système ; ce rappel passe après le sien et rétablit
  // le choix de la personne.
  if (media) media.addEventListener('change', () => setTimeout(apply));

  // Gradio pose la classe au montage et redessine l'en-tête pendant le préchauffage.
  const watch = () => {
    const header = document.querySelector('.ws-header');
    if (!header) {
      setTimeout(watch, 100);
      return;
    }
    apply();
    new MutationObserver(sync).observe(header.closest('.block') || header.parentElement,
                                       { childList: true, subtree: true });
  };
  watch();
})();
