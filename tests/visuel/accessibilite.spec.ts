// Contrôle d'accessibilité axe-core (audit visuel du 02/11, §7), en clair et en sombre, sur
// les quatre onglets après une analyse. Règles WCAG 2.0, 2.1 et 2.2 niveaux A et AA.
import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { analyse, gotoTab, open } from './outils';

const TABS = ['Analyse', 'Pipeline', 'Avancement', 'Glossaire'] as const;

for (const mode of ['clair', 'sombre'] as const) {
  test(`axe-core en ${mode}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await open(page, mode);
    await analyse(page);
    const found: string[] = [];
    for (const tab of TABS) {
      await gotoTab(page, tab);
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
        .disableRules(['target-size'])
        .analyze();
      // Taille des cibles (WCAG 2.2, 2.5.8) partout sauf sur les segments de la timeline : leur
      // largeur est la durée qu'ils représentent (exception « présentation essentielle »), le zoom
      // les agrandit, et ← → parcourent les tours au clavier.
      const targets = await new AxeBuilder({ page }).withRules(['target-size']).exclude('.wsp-lanes').analyze();
      for (const violation of [...results.violations, ...targets.violations]) {
        const targets = violation.nodes.map((node) => node.target.join(' ')).slice(0, 5).join(' | ');
        found.push(`${tab} : ${violation.id} (${violation.impact}, ${violation.nodes.length}) ${targets}`);
      }
    }
    expect(found, found.join('\n')).toEqual([]);
  });
}
