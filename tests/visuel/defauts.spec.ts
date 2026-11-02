// Captures des défauts V1, V2 et V4 de l'audit visuel (avant et après B10), hors des
// captures de référence : `DEFAUTS=avant npx playwright test defauts` écrit defauts/avant/.
import { test } from '@playwright/test';
import path from 'node:path';
import { analyse, open } from './outils';

const STAGE = process.env.DEFAUTS;
test.skip(!STAGE, 'captures des défauts seulement avec DEFAUTS=avant ou DEFAUTS=apres');

for (const mode of ['sombre', 'clair'] as const) {
  test(`défauts V1, V2, V4 en ${mode}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await open(page, mode);
    const out = (name: string) => path.join(__dirname, 'defauts', STAGE!, `${name}-${mode}.png`);
    await page.locator('fieldset', { hasText: 'Nombre de locuteurs' }).screenshot({ path: out('V1-nombre-de-locuteurs') });
    await analyse(page);
    const table = page.locator('table:has(.ws-name-input)');
    await table.scrollIntoViewIfNeeded();
    await table.screenshot({ path: out('V2-tableau-des-locuteurs') });
    const play = page.locator('.ws-excerpt').first();
    const box = await play.boundingBox();
    if (box) {
      await page.screenshot({ path: out('V4-bouton-lecture'),
        clip: { x: box.x - 12, y: box.y - 12, width: box.width + 24, height: box.height + 24 } });
    }
    await page.locator('.ws-excerpt').nth(4).scrollIntoViewIfNeeded();
  });
}
