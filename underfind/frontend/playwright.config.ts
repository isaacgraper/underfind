import { existsSync } from 'node:fs';
import path from 'node:path';
import { defineConfig } from '@playwright/test';

const PORT = 8765;
const repoRoot = path.resolve(import.meta.dirname, '..', '..');
const e2eDir = path.resolve(import.meta.dirname, 'e2e', '.data');
const chromium = process.env.PW_CHROMIUM_PATH || (existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined);

export default defineConfig({
  testDir: 'e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [['list']],
  outputDir: 'e2e/.results',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1280, height: 800 },
    locale: 'pt-BR',
    trace: 'retain-on-failure',
    launchOptions: chromium ? { executablePath: chromium, args: ['--no-sandbox'] } : {},
  },
  webServer: {
    command: 'python -m underfind.backend.e2e.server',
    cwd: repoRoot,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { E2E_DIR: e2eDir, PORT: String(PORT), PYTHONUNBUFFERED: '1' },
  },
});
