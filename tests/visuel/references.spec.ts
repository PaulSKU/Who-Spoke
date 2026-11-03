// Captures de référence. Cible d'affichage (journal du cockpit du 03/11) : ordinateur portable
// et vidéoprojecteur, 1280 × 720, 1440 × 900 et 1920 × 1080, en clair et en sombre ; plus de
// captures à 375 px. Quatre onglets en clair et en sombre à 1440 px, plus le mode présentation
// (sombre, 1280 × 720) : Analyse et Pipeline en pleine page, Avancement et Glossaire sur la
// hauteur de l'écran (pages longues, contenu tiré des documents du dépôt). Toute différence
// au-delà de 20 pixels échoue. La forme d'onde et les valeurs qui changent d'un lancement à
// l'autre (durées mesurées, périphérique, tailles et dates des exports) sont masquées.
//
// Captures à devicePixelRatio 2 (écran Retina, B14) : les coins des champs encadrés rognés en
// sombre et le double cadre de focus n'apparaissaient qu'à cette densité. Un seul test vérifie
// l'absence de débordement horizontal, à 1024 px.
// Mise à jour volontaire : `npm run captures:maj`.
import { expect, Page, test } from '@playwright/test';
import { analyse, gotoTab, Mode, open } from './outils';

type Config = { name: string; mode: Mode; width: number; height: number; presentation?: boolean };

const CONFIGS: Config[] = [
  { name: 'clair-1440', mode: 'clair', width: 1440, height: 900 },
  { name: 'sombre-1440', mode: 'sombre', width: 1440, height: 900 },
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
    for (const tab of TABS) {
      await gotoTab(page, tab);
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect(page).toHaveScreenshot(`${config.name}-${tab.toLowerCase()}.png`, {
        fullPage: tab === 'Analyse' || tab === 'Pipeline', mask: masks(page),
      });
    }
  });
}

test('aucun débordement horizontal à 1024 px', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await open(page, 'clair');
  await analyse(page);
  for (const tab of TABS) {
    await gotoTab(page, tab);
    expect(await page.evaluate(() => document.documentElement.scrollWidth), tab).toBeLessThanOrEqual(1024);
  }
});

// --- devicePixelRatio 2 -------------------------------------------------------------------

test.describe('Retina (devicePixelRatio 2)', () => {
  test.use({ deviceScaleFactor: 2 });
  // Tolérance nulle pour les champs : les entailles des coins ne couvraient que quelques
  // pixels, sous la tolérance générale de 20 ; vérifié en réinjectant l'ancien style de .form.
  const STRICT = { maxDiffPixels: 0, threshold: 0.1 };

  for (const mode of ['clair', 'sombre'] as const) {
    test(`réglages ${mode}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await open(page, mode);
      // Radio sélectionnée à un bord, Minimum et Maximum, listes, case du cache : les champs
      // dont les coins inférieurs étaient rognés.
      await page.getByText('Fourchette', { exact: true }).click();
      await page.locator('.ws-cache').getByText('Cache des résultats').click();
      await page.waitForTimeout(400);
      await expect(page.locator('.ws-card').first()).toHaveScreenshot(`dpr2-${mode}-reglages.png`, {
        ...STRICT, mask: [page.locator('.ws-cache-info')],
      });
      // Un seul anneau de focus : liste déroulante et champ numérique au clavier.
      await page.getByRole('combobox', { name: 'Moteur' }).focus();
      await page.keyboard.press('Shift+Tab');
      await page.keyboard.press('Tab');
      await page.keyboard.press('Escape');
      const engine = page.locator('.block', { has: page.getByRole('combobox', { name: 'Moteur' }) }).first();
      await expect(engine).toHaveScreenshot(`dpr2-${mode}-focus-liste.png`, STRICT);
      await page.getByRole('spinbutton', { name: 'Maximum' }).focus();
      await page.keyboard.press('Shift+Tab');
      await page.keyboard.press('Tab');
      const range = page.locator('.form', { has: page.getByRole('spinbutton', { name: 'Maximum' }) }).first();
      await expect(range).toHaveScreenshot(`dpr2-${mode}-focus-nombre.png`, STRICT);
    });
  }

  for (const [engine, short] of [['Baseline WeSpeaker', 'wespeaker'], ['pyannote community-1', 'pyannote'],
                                 ['Nemotron 3 Diarization', 'nemotron']]) {
    for (const width of [1280, 1440]) {
      test(`schéma ${short} ${width}`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await open(page, 'sombre');
        await gotoTab(page, 'Pipeline');
        await page.locator('.pl-engine input').first().click();
        await page.getByRole('option', { name: engine, exact: true }).click();
        await page.waitForTimeout(600);
        await expect(page.locator('.pl-diagram')).toHaveScreenshot(`dpr2-schema-${short}-${width}.png`);
        // Système de bout en bout : mis en regard des systèmes en cascade.
        if (short === 'nemotron') {
          await expect(page.locator('.pl-cascades')).toHaveScreenshot(`dpr2-cascades-${width}.png`);
        }
      });
    }
  }

  // Sélecteur de thème : bascule sans rechargement, dans les deux sens.
  for (const [start, target, label] of [['clair', 'sombre', 'Sombre'], ['sombre', 'clair', 'Clair']] as const) {
    test(`thème ${start} → ${target}`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await open(page, start);
      await analyse(page);
      await page.getByRole('button', { name: label, exact: true }).click();
      expect(await page.evaluate(() => document.body.classList.contains('dark'))).toBe(target === 'sombre');
      await page.waitForTimeout(500);
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect(page.locator('.ws-header')).toHaveScreenshot(`dpr2-theme-${target}-en-tete.png`, {
        mask: [page.locator('.ws-engines')],
      });
      await expect(page.locator('.wsp-root')).toHaveScreenshot(`dpr2-theme-${target}-timeline.png`, {
        mask: [page.locator('.wsp-wave'), page.locator('.wsp-minimap')],
      });
    });
  }
});
