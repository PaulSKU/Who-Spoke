// Onglet « Pipeline » (D17, D26) : un clic sur une étape affiche sa fiche. Délégation sur
// l'élément racine : le contenu est remplacé quand on change de moteur.
// Variables fournies par Gradio : element.

element.addEventListener('click', (event) => {
  const button = event.target.closest('.pl-step');
  if (!button) return;
  const stage = button.dataset.stage;
  element.querySelectorAll('.pl-step').forEach((b) => {
    b.setAttribute('aria-pressed', b === button ? 'true' : 'false');
  });
  element.querySelectorAll('.pl-sheet').forEach((sheet) => {
    sheet.hidden = sheet.dataset.stage !== stage;
  });
});
