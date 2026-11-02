// Captures de référence (audit visuel du 02/11, §7) : clair et sombre × 1440 et 375 px, plus
// le mode présentation (sombre, 1280 × 720), sur les quatre onglets : Analyse et Pipeline en
// pleine page, Avancement et Glossaire sur la hauteur de l'écran (pages longues, contenu tiré
// des documents du dépôt). Toute différence au-delà
// de 20 pixels échoue. La forme d'onde et les valeurs qui changent d'un lancement à
// l'autre (durées mesurées, périphérique, tailles et dates des exports) sont masquées.
// Mise à jour volontaire : `npm run captures:maj`.
import { expect, Page, test } from '@playwright/test';
import { analyse, gotoTab, Mode, open } from './outils';

type Config = { name: string; mode: Mode; width: number; height: number; presentation?: boolean };

const CONFIGS: Config[] = [
  { name: 'clair-1440', mode: 'clair', width: 1440, height: 900 },
  { name: 'sombre-1440', mode: 'sombre', width: 1440, height: 900 },
  { name: 'clair-375', mode: 'clair', width: 375, height: 812 },
  { name: 'sombre-375', mode: 'sombre', width: 375, height: 812 },
  { name: 'presentation', mode: 'sombre', width: 1280, height: 720, presentation: true },
];

const TABS = ['Analyse', 'Pipeline', 'Avancement', 'Glossaire'] as const;

// Contenu variable d'un lancement à l'autre.
const VARIABLE = [
  '.wsp-wave', '.wsp-minimap', '.st-head', '.ws-band-info', '.ws-pair', '.ws-engines',
  '.ws-cache-info',
];

function masks(page: Page) {
  return VARIABLE.map((selector) => page.locator(selector));
}

for (const config of CONFIGS) {
  test(`captures ${config.name}`, async ({ page }) => {
    await page.setViewportSize({ width: config.width, height: config.height });
    await open(page, config.mode, config.presentation);
    await analyse(page);
    // Aucune page ne déborde en largeur.
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(config.width);
    for (const tab of TABS) {
      await gotoTab(page, tab);
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect(page).toHaveScreenshot(`${config.name}-${tab.toLowerCase()}.png`, {
        fullPage: tab === 'Analyse' || tab === 'Pipeline', mask: masks(page),
      });
    }
  });
}
