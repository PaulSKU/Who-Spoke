// Onglet « Pipeline » (D17, D26 ; schéma de l'audit visuel du 02/11, §6, B12).
// Les étapes du schéma sont des onglets (WAI-ARIA, motif « Tabs ») : clic, ou ← → ↑ ↓,
// Origine et Fin au clavier, avec activation immédiate ; la fiche de l'étape s'affiche sous
// le schéma. Les segments de la barre « naissance des erreurs » sélectionnent l'étape où
// l'erreur naît. Petit écran : liste numérotée, une étape dépliée à la fois.
// Délégation sur l'élément racine : le contenu est remplacé quand on change de moteur.
// Variables fournies par Gradio : element.

function tabs() {
  return Array.from(element.querySelectorAll('[role="tab"]'));
}

function select(stage, focus) {
  tabs().forEach((tab) => {
    const on = tab.dataset.stage === stage;
    tab.setAttribute('aria-selected', on ? 'true' : 'false');
    tab.setAttribute('tabindex', on ? '0' : '-1');
    if (on && focus) tab.focus();
  });
  element.querySelectorAll('.pl-sheet').forEach((sheet) => {
    sheet.hidden = sheet.dataset.stage !== stage;
  });
}

element.addEventListener('click', (event) => {
  const tab = event.target.closest('[role="tab"]');
  if (tab) {
    select(tab.dataset.stage, true);
    return;
  }
  const segment = event.target.closest('.pl-errseg[data-stage]');
  if (segment) {
    select(segment.dataset.stage, false);
    const sheet = element.querySelector('#pl-sheet-' + segment.dataset.stage);
    if (sheet) sheet.scrollIntoView({ block: 'nearest' });
    return;
  }
  const toggle = event.target.closest('.pl-st-toggle');
  if (toggle) {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    element.querySelectorAll('.pl-st-toggle').forEach((other) => {
      const on = other === toggle && open;
      other.setAttribute('aria-expanded', on ? 'true' : 'false');
      const panel = element.querySelector('#' + other.getAttribute('aria-controls'));
      if (panel) panel.hidden = !on;
    });
  }
});

element.addEventListener('keydown', (event) => {
  const tab = event.target.closest('[role="tab"]');
  if (!tab) return;
  const list = tabs();
  const index = list.indexOf(tab);
  const moves = { ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1, ArrowUp: index - 1,
                  Home: 0, End: list.length - 1 };
  if (!(event.key in moves)) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      select(tab.dataset.stage, true);
    }
    return;
  }
  event.preventDefault();
  const next = list[(moves[event.key] + list.length) % list.length];
  select(next.dataset.stage, true);
});
