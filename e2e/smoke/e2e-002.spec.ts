import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api';

const APPLICANT_EMAIL = process.env.SMOKE_APPLICANT_EMAIL ?? 'marcus.mohammed0@email.com';
const APPLICANT_PASSWORD = process.env.SMOKE_APPLICANT_PASSWORD ?? 'Applicant1!';
const ADMIN_EMAIL = process.env.SMOKE_ADMIN_EMAIL ?? 'admin@zotta.tt';
const ADMIN_PASSWORD = process.env.SMOKE_ADMIN_PASSWORD ?? 'Admin123!';

type AuthHeaders = { Authorization: string };

type PreApprovalAnalytics = {
  total: number;
  pre_approved: number;
  conditionally_approved: number;
  converted: number;
  conversion_rate: number;
};

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

function uniquePhone(): string {
  const raw = `${Date.now()}`.slice(-7);
  return `+1868${raw}`;
}

async function fillInputByLabel(page: Page, labelText: string, value: string) {
  const label = page.locator(`label:has-text("${labelText}")`).first();
  const input = label.locator('xpath=following-sibling::input').first();
  await input.fill(value);
}

async function selectByLabel(page: Page, labelText: string, optionLabel: string) {
  const label = page.locator(`label:has-text("${labelText}")`).first();
  const select = label.locator('xpath=following-sibling::select').first();
  await select.selectOption({ label: optionLabel });
}

function normalizePhone(value: string): string {
  return value.replace(/\D/g, '');
}

async function resolvePreApprovalReferenceByPhone(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  phone: string,
  expectedOutcome: string,
): Promise<string> {
  const targetPhone = normalizePhone(phone);
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const listRes = await request.get(`${API}/pre-approval/admin/list?limit=200&offset=0`, {
      headers: adminHeaders,
    });
    expect(listRes.status()).toBe(200);
    const rows = extractArray(await listRes.json());
    const match = rows.find((row: any) => {
      const rowPhone = normalizePhone(String(row?.phone || ''));
      const rowOutcome = String(row?.outcome || '');
      return rowPhone === targetPhone && (!expectedOutcome || rowOutcome === expectedOutcome);
    });
    if (match?.reference_code) return String(match.reference_code);
    await new Promise((resolve) => setTimeout(resolve, 900));
  }
  throw new Error(`Could not resolve pre-approval reference for phone ${phone}`);
}

async function runQuickCheckPreApproval(page: Page): Promise<{
  reference: string;
  phone: string;
  outcome: string;
}> {
  const phone = uniquePhone();

  await page.goto(`${BASE}/pre-approval`);
  await expect(page.locator('h2', { hasText: 'What are you buying?' })).toBeVisible({ timeout: 15000 });

  await page.getByPlaceholder(/Search for a store or type the name/i).fill('Ramlagan');
  await page.getByRole('button', { name: /Ramlagans Super Store/i }).first().click();
  await page.getByPlaceholder(/Samsung 65-inch TV/i).fill('Smoke E2E-002 Quick Check Item');
  await page.locator('select').first().selectOption({ label: 'Appliances' });
  await page.locator('input[placeholder="0.00"]').first().fill('5000');
  await page.getByRole('button', { name: /^Next$/ }).click();

  await expect(page.locator('h2', { hasText: 'About You' })).toBeVisible({ timeout: 10000 });
  await fillInputByLabel(page, 'First Name', 'Marcus');
  await fillInputByLabel(page, 'Last Name', 'Mohammed');
  await page.getByPlaceholder('+1 868 000 0000').fill(phone);
  await fillInputByLabel(page, 'Total Income (before tax)', '18000');
  await selectByLabel(page, 'Employment Status', 'Employed full-time');
  await selectByLabel(page, 'How long in this role?', '2 – 5 years');
  await fillInputByLabel(page, 'Monthly Living Expenses', '2500');
  await fillInputByLabel(page, 'Monthly Loan / Credit Payments', '300');
  await page.getByRole('button', { name: /^Next$/ }).click();

  await expect(page.locator('h2', { hasText: 'Almost there' })).toBeVisible({ timeout: 10000 });
  const consentChecks = page.locator('input[type="checkbox"]');
  await consentChecks.nth(0).check();
  await consentChecks.nth(1).check();
  await page.getByRole('button', { name: /Check My Eligibility/i }).click();

  await expect(page.getByText(/pre-approved/i).first()).toBeVisible({ timeout: 40000 });
  const bodyText = await page.textContent('body');
  const fullText = bodyText ?? '';
  if (/need a little more time|can.t pre-approve/i.test(fullText)) {
    throw new Error(`Quick Check did not return pre-approved outcome. Page text: ${fullText.slice(0, 2000)}`);
  }

  const outcome = /adjustment/i.test(fullText) ? 'conditionally_approved' : 'pre_approved';
  return { reference: '', phone, outcome };
}

async function getPreApprovalAnalytics(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
): Promise<PreApprovalAnalytics> {
  const res = await request.get(`${API}/pre-approval/admin/analytics`, { headers: adminHeaders });
  expect(res.status()).toBe(200);
  const body = await res.json();
  return {
    total: Number(body.total || 0),
    pre_approved: Number(body.pre_approved || 0),
    conditionally_approved: Number(body.conditionally_approved || 0),
    converted: Number(body.converted || 0),
    conversion_rate: Number(body.conversion_rate || 0),
  };
}

async function waitForAnalytics(
  page: Page,
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  predicate: (a: PreApprovalAnalytics) => boolean,
  waitLabel: string,
): Promise<PreApprovalAnalytics> {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const analytics = await getPreApprovalAnalytics(request, adminHeaders);
    if (predicate(analytics)) return analytics;
    await page.waitForTimeout(1000);
  }
  throw new Error(`Timed out waiting for analytics condition: ${waitLabel}`);
}

async function waitForPreApprovalRow(page: Page, referenceCode: string) {
  const row = page.locator('tbody tr', { hasText: referenceCode }).first();
  for (let attempt = 0; attempt < 10; attempt += 1) {
    if (await row.count()) return row;
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByRole('button', { name: /All Records/i }).click();
    await page.waitForTimeout(900);
  }
  await expect(row).toBeVisible({ timeout: 15000 });
  return row;
}

async function submitHirePurchaseApplication(page: Page): Promise<number> {
  await page.goto(`${BASE}/apply`);
  await page.waitForLoadState('domcontentloaded');

  await expect(page.getByRole('heading', { name: /Personal Information/i }).first()).toBeVisible({ timeout: 12000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.getByRole('heading', { name: /Employment/i }).first()).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.getByRole('heading', { name: /References/i }).first()).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.getByRole('heading', { name: /Shopping Context/i }).first()).toBeVisible({ timeout: 10000 });
  await page.getByPlaceholder(/Search merchant/i).fill('Ramlagan');
  await page.getByRole('option', { name: /Ramlagans Super Store/i }).first().click();

  const branchInput = page.getByPlaceholder(/Search branch/i);
  let branchSelected = false;
  for (let attempt = 0; attempt < 6 && !branchSelected; attempt += 1) {
    await branchInput.fill('Online');
    await page.waitForTimeout(200);

    const preferred = [
      page.getByRole('option', { name: /Online \(Online\)/i }).first(),
      page.getByRole('option', { name: /^Online$/i }).first(),
      page.getByRole('option', { name: /Online/i }).first(),
      page.locator('[role="option"]').filter({ hasText: /Online/i }).first(),
    ];

    for (const option of preferred) {
      if (await option.count()) {
        await option.click();
        branchSelected = true;
        break;
      }
    }

    if (!branchSelected) {
      await branchInput.press('ArrowDown').catch(() => undefined);
      await branchInput.press('Enter').catch(() => undefined);
      await page.waitForTimeout(250);
      branchSelected = true;
    }
  }
  expect(branchSelected).toBeTruthy();

  await page.getByPlaceholder(/Search category/i).first().fill('Air Conditioner');
  await page.getByRole('option', { name: /Air Conditioner/i }).first().click();
  await page.locator('input[type="number"]').first().fill('5000');
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.getByRole('heading', { name: /Select Credit Product & Tenure/i }).first()).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Term .* months/i }).first().click();
  await page.locator('select').first().selectOption({ index: 1 });
  await expect(page.getByText(/Monthly Payment|Total Financed/i).first()).toBeVisible({ timeout: 15000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.getByRole('heading', { name: /Review & Submit/i }).first()).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Continue to Documents/i }).click();

  await expect(page.getByRole('heading', { name: /Supporting Documentation/i }).first()).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Continue to Sign/i }).click();

  await expect(page.getByRole('heading', { name: /Hire Purchase Agreement and Consent/i }).first()).toBeVisible({ timeout: 10000 });
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
  await expect(page).toHaveURL(/\/backoffice\/loans/, { timeout: 30000 });
  await expect(page.getByText(/Loading loan book/i)).toBeHidden({ timeout: 30000 });

  const search = page.getByPlaceholder(/Search by reference or name/i);
  await expect(search).toBeVisible({ timeout: 30000 });
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

test.describe('Smoke - E2E-002', () => {
  test('E2E-002: quick-check to conversion and fast-track approval path', async ({ page, request }) => {
    test.setTimeout(7 * 60 * 1000);

    const applicantHeaders = await apiLogin(request, APPLICANT_EMAIL, APPLICANT_PASSWORD);
    const adminHeaders = await apiLogin(request, ADMIN_EMAIL, ADMIN_PASSWORD);

    const baselineAnalytics = await getPreApprovalAnalytics(request, adminHeaders);
    const baselineApproved = baselineAnalytics.pre_approved + baselineAnalytics.conditionally_approved;

    let preApprovalReference = '';
    let preApprovalPhone = '';
    let preApprovalOutcome = '';
    let convertedApplicationId = 0;
    let convertedApplicationReference = '';
    let processingApplicationId = 0;
    let processingApplicationReference = '';
    let processingApplicationStatus = '';

    await test.step('Step 1: Applicant uses Quick Check and receives pre-approved result', async () => {
      console.log('[E2E-002] Step 1 start: run applicant Quick Check flow');
      await loginWithUi(page, APPLICANT_EMAIL, APPLICANT_PASSWORD, /\/(dashboard|applications|apply|pre-approval)/);

      const quick = await runQuickCheckPreApproval(page);
      preApprovalPhone = quick.phone;
      preApprovalOutcome = quick.outcome;
      preApprovalReference = await resolvePreApprovalReferenceByPhone(
        request,
        adminHeaders,
        preApprovalPhone,
        preApprovalOutcome,
      );

      console.log(`[E2E-002] Quick Check outcome=${preApprovalOutcome} | ref=${preApprovalReference} | phone=${preApprovalPhone}`);
      expect(['pre_approved', 'conditionally_approved']).toContain(preApprovalOutcome);
      expect(preApprovalReference).toMatch(/^PA-/);
    });

    await test.step('Step 2: Pre-approval record appears in dashboard and metrics update', async () => {
      console.log('[E2E-002] Step 2 start: validate Pre-Approvals dashboard visibility');
      await loginWithUi(page, ADMIN_EMAIL, ADMIN_PASSWORD, /\/backoffice/);
      await page.goto(`${BASE}/backoffice/pre-approvals`);

      await expect(page.getByRole('heading', { name: 'Pre-Approvals' })).toBeVisible({ timeout: 15000 });
      await expect(page.getByText('Outcome Breakdown')).toBeVisible({ timeout: 15000 });

      await page.getByRole('button', { name: /All Records/i }).click();
      const row = await waitForPreApprovalRow(page, preApprovalReference);
      await expect(row).toContainText(preApprovalReference);

      const analyticsAfterCreate = await waitForAnalytics(
        page,
        request,
        adminHeaders,
        (a) => a.total >= baselineAnalytics.total + 1 && (a.pre_approved + a.conditionally_approved) >= baselineApproved + 1,
        'total and approved counts to include the new pre-approval',
      );
      console.log(
        `[E2E-002] Analytics after Quick Check | total=${analyticsAfterCreate.total} | approved=${analyticsAfterCreate.pre_approved + analyticsAfterCreate.conditionally_approved}`,
      );
    });

    await test.step('Step 3: Convert pre-approval to full application and validate prefilled draft context', async () => {
      console.log('[E2E-002] Step 3 start: convert pre-approval to application');

      const convertRes = await request.post(`${API}/pre-approval/${encodeURIComponent(preApprovalReference)}/convert`, {
        headers: applicantHeaders,
      });
      expect(convertRes.status()).toBe(200);
      const converted = await convertRes.json();
      convertedApplicationId = Number(converted.application_id);
      convertedApplicationReference = String(converted.reference_number || '');

      expect(convertedApplicationId).toBeGreaterThan(0);
      expect(converted.pre_approval_reference).toBe(preApprovalReference);
      console.log(`[E2E-002] Converted pre-approval ${preApprovalReference} -> app ${convertedApplicationId} (${convertedApplicationReference})`);

      await loginWithUi(page, APPLICANT_EMAIL, APPLICANT_PASSWORD, /\/(dashboard|applications|apply)/);
      await page.goto(`${BASE}/applications/${convertedApplicationId}`);
      await expect(page.getByText(convertedApplicationReference).first()).toBeVisible({ timeout: 15000 });

      const convertedAppRes = await request.get(`${API}/loans/${convertedApplicationId}`, { headers: applicantHeaders });
      expect(convertedAppRes.status()).toBe(200);
      const convertedApp = await convertedAppRes.json();
      expect(convertedApp.status).toBe('draft');
      expect(String(convertedApp.purpose_description || '')).toContain(`Pre-approval ${preApprovalReference}`);
      expect(Number(convertedApp.amount_requested)).toBeGreaterThan(0);
      expect(Number(convertedApp.term_months)).toBeGreaterThan(0);
    });

    await test.step('Step 4: Submitted application appears in All Applications queue; pre-approval-linked draft is visible', async () => {
      console.log('[E2E-002] Step 4 start: submit full application and validate queue visibility');

      await loginWithUi(page, APPLICANT_EMAIL, APPLICANT_PASSWORD, /\/(dashboard|applications|apply)/);
      processingApplicationId = await submitHirePurchaseApplication(page);
      expect(processingApplicationId).toBeGreaterThan(0);

      const procAppRes = await request.get(`${API}/loans/${processingApplicationId}`, { headers: applicantHeaders });
      expect(procAppRes.status()).toBe(200);
      const procApp = await procAppRes.json();
      processingApplicationReference = String(procApp.reference_number || '');
      processingApplicationStatus = String(procApp.status || '');
      expect(processingApplicationReference).toMatch(/^ZOT-/);
      expect(['submitted', 'under_review', 'decision_pending', 'approved', 'accepted']).toContain(processingApplicationStatus);
      console.log(`[E2E-002] Full application submitted | id=${processingApplicationId} | reference=${processingApplicationReference}`);

      await loginWithUi(page, ADMIN_EMAIL, ADMIN_PASSWORD, /\/backoffice/);
      await page.goto(`${BASE}/backoffice/queue?status_filter=all`);

      const convertedRow = await findQueueRow(page, convertedApplicationReference);
      await expect(convertedRow).toContainText(/Draft|Submitted|Pending|Under Review|Decision Pending/i);
      console.log(`[E2E-002] Pre-approval-linked application visible in queue: ${convertedApplicationReference}`);

      const processingRow = await findQueueRow(page, processingApplicationReference);
      await expect(processingRow).toContainText(/Submitted|Pending|Under Review|Decision Pending|Approved|Accepted/i);
      await page.goto(`${BASE}/backoffice/review/${processingApplicationId}`);
      await expect(page).toHaveURL(new RegExp(`/backoffice/review/${processingApplicationId}$`), { timeout: 10000 });
    });

    await test.step('Step 5: Credit analysis and champion strategy path produce approval', async () => {
      console.log('[E2E-002] Step 5 start: credit analysis and approval');
      if (processingApplicationStatus === 'approved' || processingApplicationStatus === 'accepted') {
        await expect(page.getByText(/Decision Final|application has been approved|Accepted/i).first()).toBeVisible({ timeout: 20000 });
        console.log(`[E2E-002] Application already decisioned (${processingApplicationStatus}) for ${processingApplicationReference}; skipping manual approve`);
        return;
      }

      await page.getByRole('button', { name: /Credit Analysis/i }).click();

      const retryBtn = page.getByRole('button', { name: /Retry Analysis/i });
      if (await retryBtn.isVisible()) {
        await retryBtn.click();
      }

      await expect(page.getByText(/Analysis run on/i).first()).toBeVisible({ timeout: 30000 });
      await expect(page.getByText(/Credit Score/i).first()).toBeVisible();

      await page.getByRole('button', { name: /^Approve$/ }).click();
      await page.getByPlaceholder(/Decision rationale/i).fill('Smoke E2E-002 fast-track approval after Quick Check flow');
      await page.getByRole('button', { name: /Confirm Decision/i }).click();

      await expect(page.getByText(/Decision Final|application has been approved/i).first()).toBeVisible({ timeout: 20000 });
      console.log(`[E2E-002] Decision approved for ${processingApplicationReference}`);
    });

    await test.step('Step 6: Loan is disbursed and appears in Loan Book', async () => {
      console.log('[E2E-002] Step 6 start: disbursement and Loan Book verification');
      await expect(page.getByRole('button', { name: /Disburse Funds/i })).toBeVisible({ timeout: 20000 });
      await page.getByRole('button', { name: /Disburse Funds/i }).click();
      await page.getByPlaceholder(/Disbursement notes/i).fill('Smoke E2E-002 disbursement');
      await page.getByRole('button', { name: /Confirm Disbursement/i }).click();
      await expect(page.getByText(/Loan Disbursed/i).first()).toBeVisible({ timeout: 25000 });

      await page.goto(`${BASE}/backoffice/loans`);
      const loanRow = await waitForLoanInLoanBook(page, processingApplicationReference);
      await expect(loanRow).toContainText(processingApplicationReference);
      console.log(`[E2E-002] Loan Book includes ${processingApplicationReference}`);
    });

    await test.step('Step 7: Pre-approval conversion status and dashboard conversion metric are updated', async () => {
      console.log('[E2E-002] Step 7 start: verify conversion status + metrics');

      const detailRes = await request.get(`${API}/pre-approval/admin/${encodeURIComponent(preApprovalReference)}`, {
        headers: adminHeaders,
      });
      expect(detailRes.status()).toBe(200);
      const detail = await detailRes.json();
      expect(detail.status).toBe('converted');
      expect(Number(detail.linked_application_id)).toBe(convertedApplicationId);

      const analyticsAfterConversion = await waitForAnalytics(
        page,
        request,
        adminHeaders,
        (a) => a.converted >= baselineAnalytics.converted + 1,
        'converted count increment',
      );
      expect(analyticsAfterConversion.total).toBeGreaterThanOrEqual(baselineAnalytics.total + 1);
      expect(analyticsAfterConversion.conversion_rate).toBeGreaterThanOrEqual(0);

      await loginWithUi(page, ADMIN_EMAIL, ADMIN_PASSWORD, /\/backoffice/);
      await page.goto(`${BASE}/backoffice/pre-approvals`);
      await page.getByRole('button', { name: /All Records/i }).click();
      const convertedRow = await waitForPreApprovalRow(page, preApprovalReference);
      await expect(convertedRow).toContainText(/Converted/i);

      await page.getByRole('button', { name: /^Overview$/i }).click();
      await expect(page.getByText('Outcome Breakdown')).toBeVisible({ timeout: 15000 });

      console.log(
        `[E2E-002] Conversion verified | preApproval=${preApprovalReference} | linkedApp=${convertedApplicationId} | convertedMetric=${analyticsAfterConversion.converted}`,
      );
    });
  });
});
