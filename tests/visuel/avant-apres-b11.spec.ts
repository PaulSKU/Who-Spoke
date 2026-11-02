// Captures avant et après des défauts traités en B11 (audit visuel du 02/11, §5), hors des
// captures de référence : `ETAT=avant npx playwright test avant-apres-b11` écrit b11/avant/.
import { expect, Page, test } from '@playwright/test';
import path from 'node:path';
import { analyse, AUDIO, DATA, open } from './outils';

const STAGE = process.env.ETAT;
test.skip(!STAGE, 'captures seulement avec ETAT=avant ou ETAT=apres');

const out = (name: string) => path.join(__dirname, 'b11', STAGE!, `${name}.png`);

async function shot(page: Page, selector: string, name: string) {
  const target = page.locator(selector).first();
  await target.scrollIntoViewIfNeeded();
  await target.screenshot({ path: out(name) });
}

test('Analyse vide, en-tête, après analyse (1440, clair)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, 'clair');
  await page.screenshot({ path: out('V6-V8-analyse-vide-1440') });
  await analyse(page);
  await shot(page, '.ws-card:has(.st-root)', 'V7-etapes-1440');
  await shot(page, '.wsp-toolbar', 'V5-barre-1440');
  await shot(page, '.wsp-rows', 'V9-etiquettes-reference');
  await shot(page, '.ws-card:has(table.ws-speakers)', 'V3-V13-locuteurs');
  await shot(page, '.ws-card:has(.ws-interactions)', 'V13-interactions');
  await shot(page, '.ws-pair', 'V11-temps-et-exports');
});

test('Évaluation sans chevauchement dans la référence (1440, clair)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page, 'clair');
  await analyse(page, path.join(DATA, 'reunion_synthese_reference_sans_chevauchement.rttm'));
  await shot(page, '.ws-card:has(.ws-matching)', 'V10-evaluation');
});

test('375 px, sombre', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await open(page, 'sombre');
  await page.screenshot({ path: out('V6-V8-analyse-vide-375') });
  await analyse(page);
  await shot(page, '.wsp-toolbar', 'V5-barre-375');
});

test('mode présentation, 1280 × 720, sombre', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await open(page, 'sombre', true);
  await page.screenshot({ path: out('V6-presentation-en-tete') });
  await analyse(page);
  await shot(page, '.ws-band', 'nouvelle-analyse-presentation');
  await shot(page, '.wsp-toolbar', 'V5-barre-presentation');
});
