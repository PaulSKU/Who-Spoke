// Captures avant et après de l'onglet Pipeline (B12, audit visuel du 02/11, §6), hors des
// captures de référence : `ETAT=avant npx playwright test avant-apres-b12` écrit b12/avant/.
import { Page, test } from '@playwright/test';
import path from 'node:path';
import { gotoTab, Mode, open } from './outils';

const STAGE = process.env.ETAT;
test.skip(!STAGE, 'captures seulement avec ETAT=avant ou ETAT=apres');

async function pipeline(page: Page, engine: string) {
  await gotoTab(page, 'Pipeline');
  const select = page.locator('.pl-engine input').first();
  await select.click();
  await page.getByRole('option', { name: engine, exact: true }).click();
  await page.waitForTimeout(600);
  await page.evaluate(() => window.scrollTo(0, 0));
}

const CASES: { name: string; mode: Mode; width: number; height: number; presentation?: boolean }[] = [
  { name: 'clair-1440', mode: 'clair', width: 1440, height: 900 },
  { name: 'sombre-1440', mode: 'sombre', width: 1440, height: 900 },
  { name: 'sombre-375', mode: 'sombre', width: 375, height: 812 },
  { name: 'presentation', mode: 'sombre', width: 1280, height: 720, presentation: true },
];

for (const c of CASES) {
  for (const [engine, short] of [['pyannote community-1', 'pyannote'], ['Baseline ECAPA', 'ecapa']]) {
    test(`Pipeline ${short} ${c.name}`, async ({ page }) => {
      await page.setViewportSize({ width: c.width, height: c.height });
      await open(page, c.mode, c.presentation);
      await pipeline(page, engine);
      await page.screenshot({ path: path.join(__dirname, 'b12', STAGE!, `pipeline-${short}-${c.name}.png`),
        fullPage: c.width !== 1280 });
    });
  }
}
