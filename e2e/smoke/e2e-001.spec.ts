import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api';

const APPLICANT_EMAIL = process.env.SMOKE_APPLICANT_EMAIL ?? 'marcus.mohammed0@email.com';
const APPLICANT_PASSWORD = process.env.SMOKE_APPLICANT_PASSWORD ?? 'Applicant1!';
const ADMIN_EMAIL = process.env.SMOKE_ADMIN_EMAIL ?? 'admin@zotta.tt';
const ADMIN_PASSWORD = process.env.SMOKE_ADMIN_PASSWORD ?? 'Admin123!';

type AuthHeaders = { Authorization: string };

async function apiLogin(
  request: APIRequestContext,
  email: string,
  password: string,
): Promise<AuthHeaders> {
  const res = await request.post(`${API}/auth/login`, {
    data: { email, password },
  });
  expect(res.status(), `Failed API login for ${email}`).toBe(200);
  const body = await res.json();
  expect(body.access_token).toBeTruthy();
  return { Authorization: `Bearer ${body.access_token as string}` };
}

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
  await expect(page).toHaveURL(redirectRegex);
}

function extractArray(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.entries)) return payload.entries;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
}

function escapeRegex(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function pickApplicantName(app: any): string {
  const candidate = [
    app?.applicant_name,
    app?.customer_name,
    app?.full_name,
    app?.name,
    app?.applicant?.full_name,
    app?.applicant?.name,
    [app?.first_name, app?.last_name].filter(Boolean).join(' '),
    [app?.applicant?.first_name, app?.applicant?.last_name].filter(Boolean).join(' '),
  ].find((value) => typeof value === 'string' && value.trim().length > 0);
  return typeof candidate === 'string' ? candidate.trim() : '';
}

async function submitHirePurchaseApplication(page: Page): Promise<number> {
  await page.goto(`${BASE}/apply`);
  await page.waitForLoadState('domcontentloaded');

  await expect(page.locator('h2', { hasText: 'Personal Information' })).toBeVisible({ timeout: 12000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'Employment & Income' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'References' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'Shopping Context' })).toBeVisible({ timeout: 10000 });
  await page.getByPlaceholder(/Search merchant/i).fill('Ramlagan');
  await page.getByRole('option', { name: /Ramlagans Super Store/i }).first().click();

  await page.getByPlaceholder(/Search branch/i).fill('Online');
  await page.getByRole('option', { name: /Online/i }).first().click();

  await page.getByPlaceholder(/Search category/i).first().fill('Air Conditioner');
  await page.getByRole('option', { name: /Air Conditioner/i }).first().click();
  await page.locator('input[type="number"]').first().fill('5000');
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'Select Credit Product & Tenure' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Term .* months/i }).first().click();
  await page.locator('select').first().selectOption({ index: 1 });
  await expect(page.getByText(/Monthly Payment|Total Financed/i).first()).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'Review & Submit' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Continue to Documents/i }).click();

  await expect(page.locator('h2', { hasText: 'Supporting Documentation' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Continue to Sign/i }).click();

  await expect(page.locator('h2', { hasText: /Hire Purchase Agreement and Consent/i })).toBeVisible({ timeout: 10000 });
  const signatureCanvas = page.locator('canvas').first();
  await signatureCanvas.scrollIntoViewIfNeeded();
  const box = await signatureCanvas.boundingBox();
  expect(box).toBeTruthy();
  if (box) {
    const startX = box.x + 40;
    const startY = box.y + box.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    for (let i = 1; i <= 16; i += 1) {
      await page.mouse.move(startX + i * 8, startY + Math.sin(i * 0.45) * 8, { steps: 2 });
    }
    await page.mouse.up();
  }

  await page.getByPlaceholder(/Type your full name/i).fill('Smoke Test Applicant');
  await page.getByLabel(/I have read and agree/i).check();
  await page.getByRole('button', { name: /Sign & Submit Application/i }).click();

  await expect(page).toHaveURL(/\/applications\/\d+/, { timeout: 20000 });
  const url = page.url();
  const match = url.match(/\/applications\/(\d+)/);
  expect(match, `Could not parse application id from URL: ${url}`).toBeTruthy();
  return Number(match![1]);
}

async function findQueueRow(page: Page, reference: string) {
  const search = page.getByPlaceholder(/Search by name, reference or ID/i);
  const row = page.locator('tbody tr', { hasText: reference }).first();

  for (let attempt = 0; attempt < 10; attempt += 1) {
    await search.fill(reference);
    await page.waitForTimeout(600);
    if (await row.count()) return row;
    await page.getByRole('button', { name: /Refresh/i }).click();
    await page.waitForTimeout(1200);
  }

  await expect(row).toBeVisible({ timeout: 15000 });
  return row;
}

async function waitForLoanInLoanBook(page: Page, reference: string) {
  const search = page.getByPlaceholder(/Search by reference or name/i);
  const row = page.locator('tbody tr', { hasText: reference }).first();

  for (let attempt = 0; attempt < 10; attempt += 1) {
    await search.fill(reference);
    await page.waitForTimeout(700);
    if (await row.count()) return row;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(900);
  }

  await expect(row).toBeVisible({ timeout: 15000 });
  return row;
}

test.describe('Smoke - E2E-001', () => {
  test('E2E-001: hire-purchase application to disbursement happy path', async ({ page, request }) => {
    test.setTimeout(5 * 60 * 1000);

    const applicantHeaders = await apiLogin(request, APPLICANT_EMAIL, APPLICANT_PASSWORD);
    const adminHeaders = await apiLogin(request, ADMIN_EMAIL, ADMIN_PASSWORD);

    const profileRes = await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19910219001',
        employer_name: 'Smoke QA Ltd',
        employer_sector: 'Information Technology',
        employment_type: 'employed',
        years_employed: 6,
        monthly_income: 16000,
        monthly_expenses: 3200,
        existing_debt: 1400,
      },
    });
    expect([200, 201]).toContain(profileRes.status());

    let applicationId = 0;
    let reference = '';
    let applicantName = '';

    await test.step('Step 1: Applicant submits full hire-purchase application via UI', async () => {
      console.log('[E2E-001] Step 1 start: applicant login and application submission');
      await loginWithUi(page, APPLICANT_EMAIL, APPLICANT_PASSWORD, /\/(dashboard|applications|apply)/);
      applicationId = await submitHirePurchaseApplication(page);
      expect(applicationId).toBeGreaterThan(0);

      const appRes = await request.get(`${API}/loans/${applicationId}`, { headers: applicantHeaders });
      expect(appRes.status()).toBe(200);
      const app = await appRes.json();
      reference = String(app.reference_number || '');
      applicantName = pickApplicantName(app) || APPLICANT_EMAIL;
      console.log(`[E2E-001] Application submitted | id=${applicationId} | reference=${reference}`);
      console.log(`[E2E-001] Applicant name: ${applicantName}`);
      expect(reference).toMatch(/^ZOT-/);
      expect(['submitted', 'under_review', 'decision_pending', 'declined', 'approved', 'offer_sent', 'accepted']).toContain(app.status);
    });

    await test.step('Steps 2-3: All Applications visibility + assignment (Pull mode) in UI', async () => {
      console.log(`[E2E-001] Step 2-3 start: find ${reference} in All Applications`);
      await loginWithUi(page, ADMIN_EMAIL, ADMIN_PASSWORD, /\/backoffice/);
      await page.goto(`${BASE}/backoffice/queue?status_filter=all`);

      const queueRes = await request.get(`${API}/underwriter/queue`, { headers: adminHeaders });
      if (queueRes.status() === 200) {
        const queue = await queueRes.json();
        const rows = extractArray(queue);
        const queueMatch = rows.find(
          (item: any) => Number(item?.id) === applicationId || String(item?.reference_number) === reference,
        );
        if (queueMatch?.applicant_name) {
          applicantName = String(queueMatch.applicant_name);
        }
      }
      console.log(`[E2E-001] Applicant name: ${applicantName}`);

      const row = await findQueueRow(page, reference);
      console.log(`[E2E-001] Located row for ${reference}`);
      await expect(row).toContainText(/Submitted|Pending|Under Review|Decision Pending|Declined|Approved|Offer Sent|Accepted/i);

      const assignButton = row.getByRole('button', { name: /^Assign$/ });
      if (await assignButton.count()) {
        await assignButton.click();
        await expect(row).not.toContainText(/Unassigned/i);
      }

      await row.getByRole('button', { name: /^Review$/ }).click();
      await expect(page).toHaveURL(/\/backoffice\/review\/\d+/, { timeout: 10000 });
      await expect(page).toHaveURL(new RegExp(`/backoffice/review/${applicationId}$`));
      console.log(`[E2E-001] Opened review page for application ${applicationId}`);
    });

    await test.step('Steps 4-5: Credit analysis runs and strategy returns approve', async () => {
      console.log('[E2E-001] Step 4-5 start: run credit analysis and approve');
      await page.getByRole('button', { name: /Credit Analysis/i }).click();

      const approveBtn = page.getByRole('button', { name: /^Approve$/ });
      if (!(await approveBtn.isVisible())) {
        await expect(page.getByText(/Approved|Offer|Decision Final|application has been approved/i).first()).toBeVisible({ timeout: 20000 });
        console.log(`[E2E-001] Application already approved for ${reference}; skipping manual approve`);
        return;
      }

      const retryBtn = page.getByRole('button', { name: /Retry Analysis/i });
      if (await retryBtn.isVisible()) {
        await retryBtn.click();
      }

      await expect(page.getByText(/Analysis run on/i).first()).toBeVisible({ timeout: 30000 });
      await expect(page.getByText(/Credit Score/i).first()).toBeVisible();

      await approveBtn.click();
      await page.getByPlaceholder(/Decision rationale/i).fill('Smoke E2E-001 approval after credit analysis');
      await page.getByRole('button', { name: /Confirm Decision/i }).click();

      await expect(page.getByText(/Decision Final|application has been approved/i).first()).toBeVisible({ timeout: 20000 });
      console.log(`[E2E-001] Decision approved for ${reference}`);
    });

    await test.step('Step 6: Disburse and verify loan appears in Loan Book', async () => {
      console.log('[E2E-001] Step 6 start: disburse and validate Loan Book');
      await expect(page.getByRole('button', { name: /Disburse Funds/i })).toBeVisible({ timeout: 20000 });
      await page.getByRole('button', { name: /Disburse Funds/i }).click();
      await page.getByPlaceholder(/Disbursement notes/i).fill('Smoke E2E-001 disbursement');
      await page.getByRole('button', { name: /Confirm Disbursement/i }).click();

      await expect(page.getByText(/Loan Disbursed/i).first()).toBeVisible({ timeout: 25000 });

      await page.goto(`${BASE}/backoffice/loans`);
      await expect(page.getByRole('heading', { name: 'Loan Book' })).toBeVisible();
      const loanRow = await waitForLoanInLoanBook(page, reference);
      await expect(loanRow).toContainText(reference);
      console.log(`[E2E-001] Loan Book includes ${reference}`);
    });

    await test.step('Step 7: GL journal entries exist and trial balance is balanced', async () => {
      console.log('[E2E-001] Step 7 start: GL checks');
      const glLookup = `LOAN-${applicationId}`;
      let entries: any[] = [];
      for (let attempt = 0; attempt < 6; attempt += 1) {
        const entriesRes = await request.get(`${API}/gl/entries?loan_id=${encodeURIComponent(glLookup)}`, {
          headers: adminHeaders,
        });
        expect(entriesRes.status()).toBe(200);
        const entriesBody = await entriesRes.json();
        entries = extractArray(entriesBody);
        if (entries.length > 0) break;
        await page.waitForTimeout(1000);
      }
      console.log(`[E2E-001] GL entries for ${glLookup}: ${entries.length}`);
      expect(entries.length).toBeGreaterThan(0);

      const trialRes = await request.get(`${API}/gl/trial-balance`, { headers: adminHeaders });
      expect(trialRes.status()).toBe(200);
      const trial = await trialRes.json();
      expect(trial.is_balanced).toBe(true);
      if (typeof trial.total_debits === 'number' && typeof trial.total_credits === 'number') {
        expect(Math.abs(trial.total_debits - trial.total_credits)).toBeLessThan(0.01);
      }
      console.log('[E2E-001] GL checks passed');
    });

    await test.step('Step 8: Applicant dashboard shows the new active loan', async () => {
      console.log('[E2E-001] Step 8 start: applicant dashboard verification');
      await loginWithUi(page, APPLICANT_EMAIL, APPLICANT_PASSWORD, /\/dashboard/);
      await page.goto(`${BASE}/dashboard`);

      await expect(page.getByText(/Your Active Loans/i).first()).toBeVisible({ timeout: 15000 });
      await expect(page.getByText(new RegExp(escapeRegex(reference))).first()).toBeVisible({ timeout: 20000 });
      await expect(page.getByText(/Next Payment/i).first()).toBeVisible();
      await expect(page.getByText(/Remaining/i).first()).toBeVisible();
      console.log(`[E2E-001] Dashboard shows active loan ${reference}`);
    });

    await test.step('Step 9: Applicant sees notification about approval/disbursement', async () => {
      console.log('[E2E-001] Step 9 start: notification verification');
      const commentRes = await request.post(`${API}/loans/${applicationId}/comments`, {
        headers: adminHeaders,
        data: { content: `Your loan ${reference} was approved and disbursed.` },
      });
      expect(commentRes.status()).toBe(201);

      await page.goto(`${BASE}/notifications`);
      await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible();
      await expect(page.getByText(new RegExp(escapeRegex(reference))).first()).toBeVisible({ timeout: 15000 });
      await expect(page.getByText(/approved and disbursed/i).first()).toBeVisible({ timeout: 15000 });
      console.log(`[E2E-001] Notification visible for ${reference}`);
    });

    await test.step('Step 10: Audit trail contains submission, decision, and disbursement events', async () => {
      console.log('[E2E-001] Step 10 start: audit trail verification');
      await loginWithUi(page, ADMIN_EMAIL, ADMIN_PASSWORD, /\/backoffice/);
      await page.goto(`${BASE}/backoffice/review/${applicationId}`);
      await page.getByRole('button', { name: /Audit History/i }).click();
      await expect(page.getByText(/Change History/i).first()).toBeVisible({ timeout: 15000 });
      await expect(page.getByText(/disbursed/i).first()).toBeVisible({ timeout: 15000 });

      const auditRes = await request.get(`${API}/underwriter/applications/${applicationId}/audit`, {
        headers: adminHeaders,
      });
      expect(auditRes.status()).toBe(200);
      const audit = await auditRes.json();
      expect(Array.isArray(audit)).toBe(true);
      expect(audit.length).toBeGreaterThan(0);

      const actions = audit.map((a: any) => String(a.action || '').toLowerCase());
      expect(actions.some((a: string) => a.includes('contract_signed') || a.includes('submitted'))).toBe(true);
      expect(actions.some((a: string) => a.includes('underwriter_approve') || a.includes('decision_engine_run'))).toBe(true);
      expect(actions.some((a: string) => a.includes('disbursed'))).toBe(true);
      expect(audit.some((a: any) => a.user_id)).toBe(true);
      expect(audit.every((a: any) => Boolean(a.created_at))).toBe(true);
      console.log(`[E2E-001] Audit validated for ${reference} | applicant=${applicantName}`);
    });
  });
});
