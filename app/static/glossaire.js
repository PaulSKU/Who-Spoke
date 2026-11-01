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
