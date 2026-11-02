// Renvois vers le glossaire (D26, I3) : un clic sur un terme lié ouvre l'onglet Glossaire
// et amène la définition à l'écran. Script de page (head), délégation sur le document :
// les liens sont créés et remplacés par Gradio au fil des mises à jour.
document.addEventListener('click', (event) => {
  const link = event.target.closest('a.gl-link, a.gl-index');
  if (!link || !link.dataset.term) return;
  event.preventDefault();
  const id = link.dataset.term;
  const tab = Array.from(document.querySelectorAll('button[role="tab"]'))
    .find((button) => button.textContent.trim() === 'Glossaire');
  if (tab && tab.getAttribute('aria-selected') !== 'true') tab.click();
  let tries = 0;
  const reveal = () => {
    const target = document.getElementById(id);
    if (target && target.offsetParent !== null) {
      target.scrollIntoView({ block: 'start' });
      target.classList.remove('gl-target');
      void target.offsetWidth;  // relance l'animation de mise en évidence
      target.classList.add('gl-target');
      target.setAttribute('tabindex', '-1');
      target.focus({ preventScroll: true });
    } else if (tries++ < 40) {
      setTimeout(reveal, 50);
    }
  };
  reveal();
});

// Boutons qui ouvrent un onglet (`data-ws-tab`, carte « Comment ça marche », V8). À 375 px,
// Gradio range les derniers onglets dans son menu « More tabs » : il est ouvert au besoin.
document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-ws-tab]');
  if (!button) return;
  const name = button.dataset.wsTab;
  const tab = Array.from(document.querySelectorAll('button[role="tab"]'))
    .find((item) => item.textContent.trim() === name && item.offsetParent !== null);
  if (tab) {
    tab.click();
  } else {
    const more = document.querySelector('button[aria-label="More tabs"]');
    if (more) more.click();
    setTimeout(() => {
      const item = Array.from(document.querySelectorAll('button')).find((b) => b.textContent.trim() === name
        && b.getAttribute('role') !== 'tab');
      if (item) item.click();
    }, 50);
  }
  window.scrollTo({ top: 0 });
});
