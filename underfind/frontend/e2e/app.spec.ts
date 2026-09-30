import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';

const exportsDir = path.resolve(import.meta.dirname, '.data', 'exports');
const shots = path.resolve(import.meta.dirname, '.shots');

test.describe.configure({ mode: 'serial' });

const lane = (page: Page, title: string) => page.getByRole('region', { name: new RegExp(`^${title}`) });

async function scan(page: Page) {
  await page.goto('/#/inbox');
  const done = page.waitForResponse((r) => r.url().includes('/api/scan/'));
  await page.getByRole('button', { name: 'Buscar agora' }).first().click();
  await done;
  await expect(page.locator('tbody tr').first()).toBeVisible();
}

test('shell: navigation, AI badge and status sentence', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Underfind/);
  await expect(page.getByText('IA local', { exact: true })).toBeVisible();
  await expect(page.getByRole('status')).toHaveText('Tudo em dia');

  for (const name of ['Pipeline', 'Páginas', 'Exportados', 'Inbox']) {
    await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name }).click();
    await expect(page.getByRole('link', { name })).toHaveAttribute('aria-current', 'page');
  }

  await page.getByRole('link', { name: 'Configurações' }).click();
  await expect(page.getByRole('heading', { name: 'Configurações' })).toBeVisible();
  await expect(page.getByText('python -m underfind.backend.mcp.server').first()).toBeVisible();
  await page.getByRole('link', { name: 'Descobrir' }).click();
  await expect(page.getByRole('heading', { name: 'Descobrir' })).toBeVisible();
});

test('inbox: scan fills candidates, reject, then model one by button', async ({ page }) => {
  await page.goto('/#/inbox');
  await expect(page.getByText('Nenhum candidato novo')).toBeVisible();

  await page.getByRole('button', { name: 'Buscar agora' }).first().click();
  const rows = page.locator('tbody tr');
  await expect(rows).toHaveCount(3);
  await expect(page.getByText(/Última busca/)).toContainText('3 novos');
  await page.screenshot({ path: path.join(shots, 'inbox.png') });

  await rows.nth(2).getByRole('button', { name: 'Descartar' }).click();
  await expect(rows).toHaveCount(2);

  await rows.nth(0).getByRole('button', { name: 'Modelar' }).click();
  await expect(rows).toHaveCount(1);
  await expect(page.getByRole('link', { name: 'Pipeline' })).toBeVisible();
});

test('inbox: keyboard j, x, m models the selected candidate', async ({ page }) => {
  await scan(page);
  const rows = page.locator('tbody tr');
  const before = await rows.count();

  await page.keyboard.press('j');
  await page.keyboard.press('x');
  await expect(page.getByText('1 selecionados')).toBeVisible();
  await page.keyboard.press('m');
  await expect(rows).toHaveCount(before - 1);
});

test('pipeline to exported: translation review, render review, export on disk', async ({ page }) => {
  await page.goto('/#/pipeline');

  const needs = lane(page, 'Precisa de você');
  const translate = needs.getByRole('button', { name: 'Revisar tradução' }).first();
  await expect(translate).toBeVisible({ timeout: 40_000 });
  await expect(page.getByRole('status')).toContainText(/precisa/);
  await page.screenshot({ path: path.join(shots, 'pipeline.png') });

  await translate.click();
  await expect(page.getByRole('heading', { name: 'Revisar tradução' })).toBeVisible();

  const headline = page.getByLabel('Manchete');
  await expect(headline).toHaveValue(/ROCKSTAR/);
  await headline.fill('*GTA VI* AGORA TEM MAPA CONFIRMADO');
  await expect(page.locator('.cardprev__headline')).toContainText('GTA VI AGORA TEM MAPA CONFIRMADO');
  await expect(page.locator('.cardprev .hl')).toHaveText('GTA VI');
  await page.screenshot({ path: path.join(shots, 'review-translation.png') });

  await page.getByRole('button', { name: 'Aprovar tradução' }).click();
  await expect(page).toHaveURL(/#\/(pipeline|review\/)/);

  // Render finishes, job comes back for the second review.
  await page.goto('/#/pipeline');
  const result = lane(page, 'Precisa de você').getByRole('button', { name: 'Revisar resultado' }).first();
  await expect(result).toBeVisible({ timeout: 60_000 });
  await result.click();

  await expect(page.getByRole('heading', { name: 'Revisar resultado' })).toBeVisible();
  const reel = page.getByLabel('Reel renderizado');
  await expect(reel).toBeVisible();
  // Playwright's Chromium ships without H.264, so check the served file instead of playback.
  const src = await reel.getAttribute('src');
  const served = await page.request.get(src!);
  expect(served.status()).toBe(200);
  expect(served.headers()['content-type']).toContain('video/mp4');
  expect((await served.body()).length).toBeGreaterThan(10_000);
  await page.screenshot({ path: path.join(shots, 'review-result.png') });

  const resultUrl = page.url();
  await page.getByRole('button', { name: 'Aprovar e exportar' }).click();
  await expect(page.getByText('Aprovado', { exact: true })).toBeVisible();
  await page.waitForURL((u) => u.toString() !== resultUrl); // moves on to the next post waiting for review

  await page.goto('/#/pipeline');
  await expect(lane(page, 'Pronto').locator('.jobcard')).toHaveCount(1, { timeout: 40_000 });

  const folders = readdirSync(exportsDir, { recursive: true }).map(String).filter((f) => f.endsWith('manifest.json'));
  expect(folders.length).toBe(1);
  const manifest = JSON.parse(readFileSync(path.join(exportsDir, folders[0]), 'utf8'));
  expect(manifest.headline).toContain('GTA VI AGORA TEM MAPA CONFIRMADO');
  expect(manifest.deliverables[0].kind).toBe('reel');
  expect(existsSync(path.join(exportsDir, path.dirname(folders[0]), 'caption.txt'))).toBe(true);
});

test('exports lists the delivered post', async ({ page }) => {
  await page.goto('/#/exports');
  await expect(page.getByText('GTA VI AGORA TEM MAPA CONFIRMADO')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Copiar legenda' })).toBeVisible();
});

test('pipeline: discard shows an undo toast and undo restores the post', async ({ page }) => {
  await page.goto('/#/pipeline');
  const cards = page.locator('.jobcard');
  await expect(cards.first()).toBeVisible({ timeout: 30_000 });
  const total = await page.locator('.lane:not([data-lane="done"]) .jobcard').count();
  expect(total).toBeGreaterThan(0);

  await page.locator('.lane:not([data-lane="done"]) .jobcard').first().getByRole('button', { name: 'Descartar' }).click();
  await expect(page.getByText('Post descartado')).toBeVisible();
  await expect(page.locator('.lane:not([data-lane="done"]) .jobcard')).toHaveCount(total - 1);

  await page.getByRole('button', { name: 'Desfazer' }).click();
  await expect(page.locator('.lane:not([data-lane="done"]) .jobcard')).toHaveCount(total);
});

test('pages: create with local AI on by default, edit, delete by holding', async ({ page }) => {
  await page.goto('/#/pages');
  await expect(page.getByText('GTA VI Brasil')).toBeVisible();
  await page.getByRole('button', { name: 'Nova página' }).first().click();

  await expect(page.getByLabel('Somente IA local')).toBeChecked();
  await page.getByLabel('Nome').fill('Página de teste');
  await page.getByLabel('@ do Instagram').fill('@teste');
  await page.getByLabel('Marca na manchete').fill('TESTE BR');
  await page.getByLabel('Post 4:5').check();
  await page.screenshot({ path: path.join(shots, 'pages-form.png') });
  await page.getByRole('button', { name: 'Salvar página' }).click();

  const card = page.locator('.pagecard', { hasText: 'Página de teste' });
  await expect(card).toBeVisible();
  await expect(card.getByText('post')).toBeVisible();

  await card.getByRole('button', { name: 'Editar' }).click();
  await page.getByLabel('Nome').fill('Página renomeada');
  await page.getByRole('button', { name: 'Salvar página' }).click();
  await expect(page.locator('.pagecard', { hasText: 'Página renomeada' })).toBeVisible();

  await page.locator('.pagecard', { hasText: 'Página renomeada' }).getByRole('button', { name: 'Editar' }).click();
  const hold = page.getByRole('button', { name: /Segure para excluir/ });
  const box = (await hold.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(400);
  await page.mouse.up(); // released early: nothing happens
  await expect(page.getByLabel('Nome')).toBeVisible();

  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect(page.locator('.pagecard', { hasText: 'Página renomeada' })).toHaveCount(0, { timeout: 5_000 });
  await page.mouse.up();
});

const routes = ['#/inbox', '#/pipeline', '#/pages', '#/exports', '#/discover', '#/settings'];

for (const route of routes) {
  test(`accessibility: ${route} has no serious or critical violations`, async ({ page }) => {
    await page.goto(`/${route}`);
    await page.waitForTimeout(600);
    const { violations } = await new AxeBuilder({ page }).analyze();
    const bad = violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
    expect(bad.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([]);
  });
}

test('mobile 375px: no horizontal scroll on any screen', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });

  for (const route of routes) {
    await page.goto(`/${route}`);
    await page.waitForTimeout(400);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, route).toBeLessThanOrEqual(0);
  }

  await page.goto('/#/pipeline');
  await page.screenshot({ path: path.join(shots, 'pipeline-mobile.png') });
});

test('reduced motion: no travel or scale on the arriving card and toasts', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/#/pipeline');
  const vars = await page.evaluate(() => {
    const s = getComputedStyle(document.documentElement);
    return [s.getPropertyValue('--enter-y').trim(), s.getPropertyValue('--enter-scale').trim()];
  });
  expect(vars).toEqual(['0px', '1']);
});
