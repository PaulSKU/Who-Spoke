// Contrôle visuel de l'interface (audit visuel du 02/11, §7 ; chantier B10).
// L'application est lancée en mode factice sur une réunion de synthèse (preparer.py),
// sans préchauffage ni réseau. Navigateur : Chrome installé (channel « chrome ») ; à défaut,
// `npx playwright install chromium` puis PW_CHROMIUM=1.
import { defineConfig } from '@playwright/test';

const PORT = 7872;

export default defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.ts/,
  timeout: 120_000,
  workers: 1,                       // une seule application, des analyses l'une après l'autre
  fullyParallel: false,
  reporter: [['list']],
  expect: {
    toHaveScreenshot: { maxDiffPixels: 20, animations: 'disabled', caret: 'hide' },
  },
  snapshotPathTemplate: '{testDir}/references/{arg}{ext}',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: process.env.PW_CHROMIUM ? undefined : 'chrome',
    locale: 'fr-FR',
    timezoneId: 'Europe/Paris',
    deviceScaleFactor: 1,
  },
  webServer: {
    command: `cd ../.. && uv run python -m tests.visuel.preparer tests/visuel/.donnees && `
      + `uv run python -m app.app --factice --sans-prechauffage --factice-max-s 1 `
      + `--factice-rttm tests/visuel/.donnees/sorties --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}`,
    timeout: 120_000,
    reuseExistingServer: false,
  },
});
