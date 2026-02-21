import { expect, test, type Page } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const APPLICANT_EMAIL = process.env.SMOKE_APPLICANT_EMAIL ?? 'marcus.mohammed0@email.com';
const APPLICANT_PASSWORD = process.env.SMOKE_APPLICANT_PASSWORD ?? 'Applicant1!';
const ADMIN_EMAIL = process.env.SMOKE_ADMIN_EMAIL ?? 'admin@zotta.tt';
const ADMIN_PASSWORD = process.env.SMOKE_ADMIN_PASSWORD ?? 'Admin123!';

async function resetBrowserSession(page: Page) {
  await page.context().clearCookies();
  await page.goto(`${BASE}/login`);
  await page.evaluate(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });
}

async function loginWithUi(page: Page, email: string, password: string, redirectRegex: RegExp) {
  await resetBrowserSession(page);
  await page.goto(`${BASE}/login`);
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /Sign In/i }).click();
  await expect(page).toHaveURL(redirectRegex, { timeout: 20000 });
}

async function assertNoHorizontalOverflow(page: Page, routeLabel: string) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(800);
  await page.evaluate(() => window.scrollTo(0, 0));

  const metrics = await page.evaluate(() => {
    const html = document.documentElement;
    const body = document.body;
    return {
      innerWidth: window.innerWidth,
      htmlScrollWidth: html.scrollWidth,
      bodyScrollWidth: body.scrollWidth,
    };
  });

  console.log(
    `[RESPONSIVE] ${routeLabel} inner=${metrics.innerWidth} html=${metrics.htmlScrollWidth} body=${metrics.bodyScrollWidth}`,
  );

  expect(metrics.htmlScrollWidth, `Document overflows viewport on ${routeLabel}`).toBeLessThanOrEqual(
    metrics.innerWidth + 1,
  );
  expect(metrics.bodyScrollWidth, `Body overflows viewport on ${routeLabel}`).toBeLessThanOrEqual(
    metrics.innerWidth + 1,
  );
}

async function openAndCheck(page: Page, path: string, label: string) {
  await page.goto(`${BASE}${path}`, { waitUntil: 'domcontentloaded' });
  await assertNoHorizontalOverflow(page, label);
}

test.describe('Smoke - Mobile Responsiveness', () => {
  test('@responsive @mobile consumer pages render without horizontal overflow', async ({ page }) => {
    test.setTimeout(2 * 60 * 1000);

    await loginWithUi(page, APPLICANT_EMAIL, APPLICANT_PASSWORD, /\/(dashboard|applications|apply)/);

    const routes = [
      { path: '/dashboard', label: 'Consumer dashboard' },
      { path: '/apply', label: 'Consumer new application' },
      { path: '/applications', label: 'Consumer applications list' },
      { path: '/profile', label: 'Consumer profile' },
      { path: '/loans', label: 'Consumer loans' },
    ];

    for (const route of routes) {
      await test.step(route.label, async () => {
        await openAndCheck(page, route.path, route.label);
      });
    }
  });

  test('@responsive @mobile backoffice pages render without horizontal overflow', async ({ page }) => {
    test.setTimeout(2 * 60 * 1000);

    await loginWithUi(page, ADMIN_EMAIL, ADMIN_PASSWORD, /\/backoffice/);

    const routes = [
      { path: '/backoffice', label: 'Backoffice dashboard' },
      { path: '/backoffice/queue?status_filter=all', label: 'Backoffice applications queue' },
      { path: '/backoffice/loans', label: 'Backoffice loan book' },
      { path: '/backoffice/customers', label: 'Backoffice customers' },
      { path: '/backoffice/strategies', label: 'Backoffice strategies' },
      { path: '/backoffice/error-monitor', label: 'Backoffice error monitor' },
    ];

    for (const route of routes) {
      await test.step(route.label, async () => {
        await openAndCheck(page, route.path, route.label);
      });
    }
  });
});
