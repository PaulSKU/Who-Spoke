// Outils communs aux contrôles visuels : thème, taille, analyse factice de la réunion de synthèse.
import { expect, Page } from '@playwright/test';
import path from 'node:path';

export const DATA = path.join(__dirname, '.donnees');
export const AUDIO = path.join(DATA, 'reunion_synthese.wav');
export const REFERENCE = path.join(DATA, 'reunion_synthese_reference.rttm');

export type Mode = 'clair' | 'sombre';

export async function open(page: Page, mode: Mode, presentation = false): Promise<void> {
  await page.emulateMedia({ colorScheme: mode === 'sombre' ? 'dark' : 'light', reducedMotion: 'reduce' });
  await page.goto(`/?__theme=${mode === 'sombre' ? 'dark' : 'light'}`);
  await page.locator('.ws-header').waitFor();
  if (presentation) {
    await page.locator('.ws-present').click();
    await expect(page.locator('html')).toHaveClass(/ws-presentation/);
  }
}

// Dépose l'audio et la référence, lance l'analyse, attend la timeline.
export async function analyse(page: Page, reference: string = REFERENCE): Promise<void> {
  const inputs = page.locator('input[type=file]');
  await inputs.first().setInputFiles(AUDIO);
  await expect(page.locator('.ws-estimate')).toContainText('Durée estimée', { timeout: 30_000 });
  await inputs.last().setInputFiles(reference);
  await expect(page.locator('.ws-reference')).toContainText('.rttm', { timeout: 30_000 });
  await page.getByRole('button', { name: 'Analyser', exact: true }).click();
  await page.locator('.wsp-root:not(.wsp-empty)').waitFor({ timeout: 60_000 });
  await page.waitForTimeout(500);
}

// Ouvre un onglet ; si la barre déborde, Gradio range les derniers dans son menu « More tabs ».
export async function gotoTab(page: Page, name: string): Promise<void> {
  const tab = page.getByRole('tab', { name, exact: true });
  if (!(await tab.isVisible())) {
    await page.getByRole('button', { name: 'More tabs' }).click();
    await page.getByRole('button', { name, exact: true }).or(page.getByText(name, { exact: true }).last()).first().click();
  } else {
    await tab.click();
  }
  await page.waitForTimeout(400);
}
