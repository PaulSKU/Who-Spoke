// Captures avant et après de B13 (audit visuel du 02/11, §7) : onglets Avancement et
// Glossaire, barre d'onglets à 375 px, barre de la naissance des erreurs (retour sur B12) et
// grands écrans (1280 × 720, 1920 × 1080, vidéoprojecteur), hors des captures de référence :
// `ETAT=avant npx playwright test avant-apres-b13` écrit b13/avant/.
import { Page, test } from '@playwright/test';
import path from 'node:path';
import { analyse, gotoTab, Mode, open } from './outils';

const STAGE = process.env.ETAT;
test.skip(!STAGE, 'captures seulement avec ETAT=avant ou ETAT=apres');

const out = (name: string) => path.join(__dirname, 'b13', STAGE!, `${name}.png`);

type Case = { name: string; mode: Mode; width: number; height: number; presentation?: boolean };

const CASES: Case[] = [
  { name: 'clair-1440', mode: 'clair', width: 1440, height: 900 },
  { name: 'sombre-1440', mode: 'sombre', width: 1440, height: 900 },
  { name: 'clair-375', mode: 'clair', width: 375, height: 812 },
  { name: 'presentation', mode: 'sombre', width: 1280, height: 720, presentation: true },
];

for (const c of CASES) {
  for (const tab of ['Avancement', 'Glossaire']) {
    test(`${tab} ${c.name}`, async ({ page }) => {
      await page.setViewportSize({ width: c.width, height: c.height });
      await open(page, c.mode, c.presentation);
      await gotoTab(page, tab);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: out(`${tab.toLowerCase()}-${c.name}`), fullPage: false });
    });
  }
}

test('barre d\'onglets à 375 px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await open(page, 'clair');
  await page.screenshot({ path: out('onglets-375'), clip: { x: 0, y: 0, width: 375, height: 260 } });
  const more = page.getByRole('button', { name: 'More tabs' });
  if (await more.isVisible()) {
    await more.click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: out('onglets-375-menu'), clip: { x: 0, y: 0, width: 375, height: 360 } });
  }
});

async function pipeline(page: Page, engine: string) {
  await gotoTab(page, 'Pipeline');
  await page.locator('.pl-engine input').first().click();
  await page.getByRole('option', { name: engine, exact: true }).click();
  await page.waitForTimeout(600);
}

test('naissance des erreurs : clic sur la confusion', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, 'clair');
  await pipeline(page, 'pyannote community-1');
  await page.locator('.pl-errseg.pl-err-confusion').click();
  await page.waitForTimeout(400);
  await page.evaluate(() => window.scrollTo(0, 0));
  const root = page.locator('.pl-root');
  const box = await root.boundingBox();
  await page.screenshot({ path: out('pipeline-confusion'), fullPage: true,
    clip: { x: box!.x, y: box!.y, width: box!.width, height: Math.min(box!.height, 760) } });
});

// Grands écrans : les quatre onglets, après une analyse avec référence.
for (const [width, height] of [[1280, 720], [1920, 1080]]) {
  for (const mode of ['clair', 'sombre'] as const) {
    test(`grand écran ${width}x${height} ${mode}`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await open(page, mode);
      await analyse(page);
      for (const tab of ['Analyse', 'Pipeline', 'Avancement', 'Glossaire']) {
        await gotoTab(page, tab);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: out(`${width}x${height}-${mode}-${tab.toLowerCase()}`) });
      }
    });
  }
}
