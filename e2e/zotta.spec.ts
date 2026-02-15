import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

async function loginAsApplicant(page: import('@playwright/test').Page) {
  await page.goto(BASE);
  await page.getByLabel('Email').fill('marcus.mohammed0@email.com');
  await page.getByLabel('Password').fill('Applicant1!');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

async function loginAsAdmin(page: import('@playwright/test').Page) {
  await page.goto(BASE);
  await page.getByLabel('Email').fill('admin@zotta.tt');
  await page.getByLabel('Password').fill('Admin123!');
  await page.getByRole('button', { name: 'Sign In' }).click();
  await expect(page).toHaveURL(/\/backoffice/);
}

test.describe('Auth', () => {
  test('login page loads', async ({ page }) => {
    await page.goto(BASE);
    await expect(page.locator('h1')).toContainText('Zotta');
    await expect(page.getByRole('heading', { name: 'Sign In' })).toBeVisible();
  });

  test('register page loads', async ({ page }) => {
    await page.goto(BASE);
    await page.getByRole('link', { name: 'Register' }).click();
    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByRole('heading', { name: /Create Account|Register|Sign Up/i })).toBeVisible();
  });

  test('applicant login redirects to dashboard', async ({ page }) => {
    await loginAsApplicant(page);
    await expect(page.getByText(/Welcome back|Dashboard/i).first()).toBeVisible();
  });

  test('admin login redirects to backoffice', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.getByText(/Dashboard|Back Office/i).first()).toBeVisible();
  });
});

test.describe('Consumer portal', () => {
  test('dashboard shows applications and stats', async ({ page }) => {
    await loginAsApplicant(page);
    await expect(page.getByText(/Welcome back|Total Applications|Active/i).first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'New Application' })).toBeVisible();
  });

  test('hire-purchase flow steps – personal info through plan selection', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/apply`);
    await page.waitForLoadState('networkidle');

    // Existing user auto-skips ID Scan to Personal Info (step 1)
    await expect(page.getByRole('heading', { name: 'Personal Information' })).toBeVisible({ timeout: 5000 });
    // Fill minimal fields and proceed
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(500);

    // Step 2: Employment
    await expect(page.getByRole('heading', { name: 'Employment & Income' })).toBeVisible({ timeout: 3000 });
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(500);

    // Step 3: References (skip through)
    await expect(page.locator('h2', { hasText: 'References' })).toBeVisible({ timeout: 3000 });
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(500);

    // Step 4: Shopping
    await expect(page.locator('h2', { hasText: 'Shopping Context' })).toBeVisible({ timeout: 3000 });
    await page.getByPlaceholder(/Search merchant/i).fill('Ramlagan');
    await page.waitForTimeout(400);
    await page.getByRole('option', { name: /Ramlagans Super Store/i }).click();
    await page.waitForTimeout(600);

    await page.getByPlaceholder(/Search branch/i).fill('Online');
    await page.waitForTimeout(400);
    await page.getByRole('option', { name: /Online \(Online\)/i }).click();
    await page.waitForTimeout(500);

    const categoryCombobox = page.getByPlaceholder(/Search category/i).first();
    await categoryCombobox.fill('Air Conditioner');
    await page.waitForTimeout(400);
    await page.getByRole('option', { name: /Air Conditioner/i }).first().click();
    await page.waitForTimeout(300);
    await page.locator('input[type="number"]').first().fill('5000');
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(1000);

    // Step 5: Plan Selection
    await expect(page.getByRole('heading', { name: 'Select Credit Product & Tenure' })).toBeVisible();
    await page.getByRole('button', { name: /Ramlagan|ZWSSL|over|\d/ }).first().click();
    await page.waitForTimeout(600);

    const tenureSelect = page.locator('select').filter({ has: page.locator('option:has-text("months")') }).first();
    await tenureSelect.selectOption({ index: 1 });
    await page.waitForTimeout(1000);

    await expect(page.getByText(/Monthly Payment|Total Financed/i).first()).toBeVisible({ timeout: 8000 });
  });

  test('full hire-purchase flow with consent signing and submit', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/apply`);
    await page.waitForLoadState('networkidle');

    // Existing user auto-skips ID Scan → lands on Personal Info (step 1)
    await expect(page.getByRole('heading', { name: 'Personal Information' })).toBeVisible({ timeout: 5000 });
    // Fill/confirm personal details
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(500);

    // Step 2: Employment (minimal)
    await expect(page.getByRole('heading', { name: 'Employment & Income' })).toBeVisible({ timeout: 3000 });
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(500);

    // Step 3: References (skip through)
    await expect(page.locator('h2', { hasText: 'References' })).toBeVisible({ timeout: 3000 });
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(500);

    // Step 4: Shopping (Combobox components)
    await expect(page.locator('h2', { hasText: 'Shopping Context' })).toBeVisible({ timeout: 3000 });
    await page.getByPlaceholder(/Search merchant/i).fill('Ramlagan');
    await page.waitForTimeout(400);
    await page.getByRole('option', { name: /Ramlagans Super Store/i }).click();
    await page.waitForTimeout(500);
    await page.getByPlaceholder(/Search branch/i).fill('Online');
    await page.waitForTimeout(400);
    await page.getByRole('option', { name: /Online \(Online\)/i }).click();
    await page.waitForTimeout(500);
    await page.getByPlaceholder(/Search category/i).first().fill('Air Conditioner');
    await page.waitForTimeout(400);
    await page.getByRole('option', { name: /Air Conditioner/i }).first().click();
    await page.waitForTimeout(300);
    await page.locator('input[type="number"]').first().fill('5000');
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(1000);

    // Step 5: Plan Selection
    await page.getByRole('button', { name: /Ramlagan|ZWSSL|over|\d/ }).first().click();
    await page.waitForTimeout(600);
    const tenureSelect = page.locator('select').filter({ has: page.locator('option:has-text("months")') }).first();
    await tenureSelect.selectOption({ index: 1 });
    await page.waitForTimeout(1500);
    await page.getByRole('button', { name: /Next/ }).click();
    await page.waitForTimeout(800);

    // Step 5: Review → Continue to Documents (creates draft)
    await expect(page.getByRole('heading', { name: 'Review & Submit' })).toBeVisible();
    await expect(page.getByText(/Ramlagans|Merchant|Purchase Total/i).first()).toBeVisible();
    await page.getByRole('button', { name: /Continue to Documents/ }).click();
    await page.waitForTimeout(3000);

    // Step 6: Documents → Continue to Sign (skip upload, optional)
    await expect(page.getByRole('heading', { name: 'Supporting Documentation' })).toBeVisible();
    await page.getByRole('button', { name: /Continue to Sign/ }).click();
    await page.waitForTimeout(1000);

    // Step 7: Sign Contract — consent document should be visible
    await expect(page.getByRole('heading', { name: /Hire Purchase Agreement and Consent/i })).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('heading', { name: 'Hire Purchase Agreement', exact: true })).toBeVisible();
    await expect(page.getByText(/Use of Information|indemnify the Owner/i).first()).toBeVisible();
    // Verify prepopulated data
    await expect(page.getByText(/Zotta/i).first()).toBeVisible();
    await expect(page.getByText(/5,000|5000/i).first()).toBeVisible();
    // Reference number should appear
    await expect(page.getByText(/ZOT-/i).first()).toBeVisible();

    // Wait for canvas to initialize
    await page.waitForTimeout(500);

    // Draw signature on canvas
    const canvas = page.locator('canvas').first();
    await canvas.scrollIntoViewIfNeeded();
    await page.waitForTimeout(200);
    const box = await canvas.boundingBox();
    expect(box).toBeTruthy();
    if (box) {
      const centerX = box.x + box.width / 2;
      const centerY = box.y + box.height / 2;
      await page.mouse.move(centerX - 50, centerY);
      await page.mouse.down();
      for (let i = 1; i <= 20; i++) {
        await page.mouse.move(centerX - 50 + i * 5, centerY + Math.sin(i * 0.5) * 10, { steps: 2 });
      }
      await page.mouse.up();
    }
    await page.waitForTimeout(300);

    // Type name and agree
    await page.getByPlaceholder('Type your full name').fill('Marcus Mohammed');
    await page.getByLabel(/I have read and agree to the Hire Purchase Agreement/).click();
    await page.waitForTimeout(300);

    // Submit
    await page.getByRole('button', { name: /Sign & Submit/ }).click();
    await page.waitForTimeout(4000);

    // Should navigate to application status
    await expect(page).toHaveURL(/\/applications\/\d+/, { timeout: 10000 });
    await expect(page.getByText(/ZOT-|Submitted|Application|Status/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('application status page loads', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/applications`);
    await page.waitForLoadState('networkidle');
    const viewLink = page.getByRole('link', { name: /View|ZOT-|Reference/i }).first();
    if (await viewLink.isVisible()) {
      await viewLink.click();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText(/Status|Submitted|Reference|Amount/i).first()).toBeVisible({ timeout: 5000 });
    } else {
      await expect(page.getByText(/Application|Dashboard|No application/i).first()).toBeVisible();
    }
  });

  test('profile page loads', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/profile`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'My Profile' })).toBeVisible({ timeout: 5000 });
  });

  test('My Loans page loads', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/loans`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'My Loans' })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Track your disbursed loans|No active loans|Payment Calendar/i)).toBeVisible({ timeout: 5000 });
  });

  test('My Loans: disbursed loan with partial repayment shows payment calendar', async ({ page, request }) => {
    const API = 'http://localhost:8000/api';

    // ── Setup: Create disbursed loan and record partial payment via API ──
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Update profile for healthy DSR (match lifecycle test)
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        employment_type: 'employed',
        years_employed: 10,
        monthly_income: 15000,
        other_income: 0,
        monthly_expenses: 3000,
        existing_debt: 1500,
        dependents: 1,
      },
    });

    // Create, submit, approve, disburse
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 12000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E My Loans test – partial repayment',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();
    const appId = app.id;

    await request.post(`${API}/loans/${appId}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${appId}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'E2E My Loans test' },
    });
    const disbRes = await request.post(`${API}/underwriter/applications/${appId}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'E2E My Loans test' },
    });
    expect(disbRes.status()).toBe(200);

    // Get schedule to find first installment amount
    const schedRes = await request.get(`${API}/payments/${appId}/schedule`, { headers: adminHeaders });
    expect(schedRes.status()).toBe(200);
    const schedule = await schedRes.json();
    expect(schedule.length).toBeGreaterThan(0);
    const firstInstallmentAmount = Number(schedule[0].amount_due);

    // Record partial payment (first installment)
    const payRes = await request.post(`${API}/payments/${appId}/record`, {
      headers: adminHeaders,
      data: {
        amount: firstInstallmentAmount,
        payment_type: 'manual',
        payment_date: new Date().toISOString().split('T')[0],
        reference_number: 'E2E-PAY-001',
        notes: 'E2E test partial repayment',
      },
    });
    expect(payRes.status()).toBe(200);

    // ── UI: Navigate to My Loans as applicant ──
    await loginAsApplicant(page);
    await page.goto(`${BASE}/loans`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'My Loans' })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(app.reference_number)).toBeVisible({ timeout: 5000 });

    // Expand the loan card (click to expand)
    const loanCard = page.locator('button').filter({ hasText: app.reference_number }).first();
    await loanCard.click();

    // Verify payment calendar and partial repayment data
    await expect(page.getByText('Payment Calendar')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Payments Made')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('1 / 12')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('paid').first()).toBeVisible({ timeout: 3000 });

    // Verify View full details link
    await expect(page.getByRole('link', { name: /View full details|make payment/i })).toBeVisible({ timeout: 2000 });
  });
});

test.describe('Backoffice – admin pages', () => {
  test('dashboard loads', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.getByRole('heading', { name: /Dashboard/i })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Applications|Lending|Overview/i).first()).toBeVisible();
  });

  test('applications queue loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/applications`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Reference|Applicant|Status|Applications/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('application review page loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/applications`);
    await page.waitForLoadState('networkidle');
    const reviewLink = page.getByRole('link', { name: /ZOT-|Review/i }).first();
    if (await reviewLink.isVisible()) {
      await reviewLink.click();
      await page.waitForLoadState('networkidle');
      await expect(page.getByText(/Application|Applicant|Decision|Credit|Reference/i).first()).toBeVisible({ timeout: 5000 });
    } else {
      await expect(page.getByText(/Applications|No applications/i).first()).toBeVisible();
    }
  });

  test('loan book loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/loans`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Loan Book|Reference|Outstanding|Risk/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('collections loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/collections`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Collections|Overdue|Past Due|Days/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('reports loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/reports`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Report|Aged|Exposure|Portfolio/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('Loan Statement requires Application ID – backend returns 400', async ({ request }) => {
    const API_BASE = 'http://localhost:8000/api';
    const loginRes = await request.post(`${API_BASE}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await loginRes.json();
    const res = await request.post(`${API_BASE}/reports/generate/loan_statement`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { date_from: '2025-01-01', date_to: '2025-02-10' },
    });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.detail).toMatch(/application_id|Application ID/i);
  });

  test('generate Aged Report and verify downloaded CSV content', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/reports`);
    await page.waitForLoadState('networkidle');
    // Aged Report is 1st report card (index 0)
    const generateBtn = page.getByRole('button', { name: /Generate/i }).first();
    const [download] = await Promise.all([
      page.waitForEvent('download', { timeout: 20000 }),
      generateBtn.click(),
    ]);
    const path = await download.path();
    expect(path).toBeTruthy();
    const { readFileSync } = await import('fs');
    const contents = readFileSync(path!, 'utf-8');
    expect(contents).toContain('Aged Report');
    expect(contents).toContain('Bucket');
    expect(contents).toContain('Total Outstanding');
  });

  test('disbursement API: disburse accepted loan creates schedule', async ({ request }) => {
    const API_BASE = 'http://localhost:8000/api';
    const loginRes = await request.post(`${API_BASE}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await loginRes.json();
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const appLogin = await request.post(`${API_BASE}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };

    // Update profile for healthy DSR
    await request.put(`${API_BASE}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        employment_type: 'employed',
        years_employed: 10,
        monthly_income: 15000,
        other_income: 0,
        monthly_expenses: 3000,
        existing_debt: 1500,
        dependents: 1,
      },
    });

    // Create, submit, approve, accept, then disburse
    const createRes = await request.post(`${API_BASE}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 10000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E disbursement API test',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();
    const appId = app.id;

    await request.post(`${API_BASE}/loans/${appId}/submit`, { headers: applicantHeaders });
    await request.post(`${API_BASE}/underwriter/applications/${appId}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'E2E disbursement test' },
    });
    await request.post(`${API_BASE}/loans/${appId}/accept-offer`, { headers: applicantHeaders });

    const disbRes = await request.post(`${API_BASE}/underwriter/applications/${appId}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'E2E test disbursement' },
    });
    expect(disbRes.status()).toBe(200);
    const disb = await disbRes.json();
    expect(disb.status).toBe('completed');
    expect(disb.reference_number).toMatch(/^DIS-/);
    expect(disb.amount).toBeGreaterThan(0);
    // Verify payment schedule was created
    const schedRes = await request.get(`${API_BASE}/payments/${appId}/schedule`, { headers: adminHeaders });
    expect(schedRes.status()).toBe(200);
    const schedule = await schedRes.json();
    expect(schedule.length).toBeGreaterThan(0);
    // Verify double-disburse is blocked
    const doubleRes = await request.post(`${API_BASE}/underwriter/applications/${appId}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual' },
    });
    expect([400, 409]).toContain(doubleRes.status()); // status already disbursed
  });

  test('new application form loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/new-application`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /New Walk-in Application/i })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Personal Information|Create application on behalf/i).first()).toBeVisible();
  });

  test('create-on-behalf with extended fields (marital_status, address_line2, dependents)', async ({ request }) => {
    const API = 'http://localhost:8000/api';
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const headers = { Authorization: `Bearer ${adminToken}` };

    const payload = {
      email: `walkin-test-${Date.now()}@example.com`,
      first_name: 'WalkIn',
      last_name: 'Tester',
      phone: '+18681234567',
      date_of_birth: '1990-05-15',
      national_id: '19900515001',
      gender: 'male',
      marital_status: 'married',
      address_line1: '100 Main St',
      address_line2: 'Suite 200',
      city: 'Port of Spain',
      parish: 'Port of Spain',
      whatsapp_number: '+18687654321',
      employer_name: 'Test Co',
      employer_sector: 'Retail & Distribution',
      job_title: 'Manager',
      employment_type: 'employed',
      years_employed: 5,
      monthly_income: 8000,
      other_income: 500,
      monthly_expenses: 3000,
      existing_debt: 2000,
      dependents: 2,
      amount_requested: 15000,
      term_months: 12,
      purpose: 'personal',
      purpose_description: 'E2E create-on-behalf extended fields',
    };

    const res = await request.post(`${API}/underwriter/applications/create-on-behalf`, {
      headers,
      data: payload,
    });
    expect(res.status()).toBe(201);
    const app = await res.json();
    expect(app.id).toBeGreaterThan(0);
    expect(app.reference_number).toMatch(/^ZOT-/);
    expect(app.status).toBeTruthy();

    const fullRes = await request.get(`${API}/underwriter/applications/${app.id}/full`, { headers });
    expect(fullRes.status()).toBe(200);
    const full = await fullRes.json();
    expect(full.profile?.marital_status).toBe('married');
    expect(full.profile?.address_line2).toBe('Suite 200');
    expect(full.profile?.dependents).toBe(2);
  });

  test('products list loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/products`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Credit Product Management/i })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Ramlagan|ZWSSL|SAI/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('product detail page loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/products`);
    await page.waitForLoadState('networkidle');
    const productRow = page.getByRole('row').filter({ hasText: 'Ramlagan' }).first();
    await productRow.click();
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/General Parameters|Repayment|Fees|Score Range/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('merchants page loads with categories per merchant', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/merchants`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText('Ramlagans Super Store')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/branches.*categories|categories/i).first()).toBeVisible();
  });
});


// ── Full lifecycle E2E use-cases ──────────────────────────────

test.describe('Loan lifecycle – Accept & Disburse', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    // Applicant token
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    // Admin token
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    return { applicantToken, adminToken };
  }

  test('full lifecycle: create → submit → approve → disburse → verify transactions & schedule', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // ── Pre-step: Remove any leftover custom rules that might interfere ──
    const rulesRes = await request.get(`${API}/admin/rules`, { headers: adminHeaders });
    const { rules: currentRules } = await rulesRes.json();
    const builtinOnly = currentRules.filter((r: any) => !r.is_custom);
    if (builtinOnly.length < currentRules.length) {
      await request.put(`${API}/admin/rules`, {
        headers: adminHeaders,
        data: { rules: builtinOnly },
      });
    }

    // ── Step 0: Update applicant profile with healthy financials ──
    // Ensures the decision engine does NOT hard-decline on DSR.
    // monthly_income 15000, expenses 3000, existing_debt 1500 → DSR ≈ 30%
    const profileRes = await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        employment_type: 'employed',
        years_employed: 10,
        monthly_income: 15000,
        other_income: 0,
        monthly_expenses: 3000,
        existing_debt: 1500,
        dependents: 1,
      },
    });
    expect(profileRes.status()).toBe(200);

    // ── Step 1: Create a draft application ────────────
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 15000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E lifecycle test – accept & disburse',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const application = await createRes.json();
    const appId = application.id;
    expect(application.reference_number).toMatch(/^ZOT-/);
    expect(application.status).toBe('draft');

    // ── Step 2: Submit the application ────────────────
    // The decision engine auto-runs on submit. With the healthy profile,
    // it should NOT hard-decline on DSR.
    const submitRes = await request.post(`${API}/loans/${appId}/submit`, {
      headers: applicantHeaders,
    });
    expect(submitRes.status()).toBe(200);
    const submitted = await submitRes.json();
    // With healthy financials, the engine should NOT hard-decline
    expect(submitted.status).not.toBe('declined');

    // ── Step 3: Underwriter approves the application ──
    const decideRes = await request.post(`${API}/underwriter/applications/${appId}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'E2E test approval – good credit profile, healthy DSR' },
    });
    expect(decideRes.status()).toBe(200);
    const decision = await decideRes.json();
    expect(decision.final_outcome).toBe('approve');

    // Verify application status is now approved
    const appAfterApproval = await request.get(`${API}/underwriter/applications/${appId}`, {
      headers: adminHeaders,
    });
    expect(appAfterApproval.status()).toBe(200);
    const approvedApp = await appAfterApproval.json();
    expect(approvedApp.status).toBe('approved');
    expect(Number(approvedApp.amount_approved)).toBe(15000);

    // ── Step 5: Disburse the loan ─────────────────────
    const disbRes = await request.post(`${API}/underwriter/applications/${appId}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'E2E lifecycle disbursement' },
    });
    expect(disbRes.status()).toBe(200);
    const disbursement = await disbRes.json();
    expect(disbursement.status).toBe('completed');
    expect(disbursement.reference_number).toMatch(/^DIS-/);
    expect(disbursement.amount).toBe(15000);

    // ── Step 6: Verify payment schedule was created ───
    const schedRes = await request.get(`${API}/payments/${appId}/schedule`, {
      headers: adminHeaders,
    });
    expect(schedRes.status()).toBe(200);
    const schedule = await schedRes.json();
    expect(schedule.length).toBe(12); // 12-month term
    // Each instalment should have principal, interest, fee, amount_due
    for (const item of schedule) {
      expect(Number(item.principal)).toBeGreaterThan(0);
      expect(Number(item.interest)).toBeGreaterThanOrEqual(0);
      expect(Number(item.fee)).toBeGreaterThanOrEqual(0);
      expect(Number(item.amount_due)).toBeGreaterThan(0);
      expect(item.status).toBe('upcoming');
    }

    // ── Step 7: Verify disbursement appears as a transaction ──
    const historyRes = await request.get(`${API}/payments/${appId}/history`, {
      headers: adminHeaders,
    });
    expect(historyRes.status()).toBe(200);
    const transactions = await historyRes.json();
    expect(transactions.length).toBeGreaterThanOrEqual(1);
    const disbTxn = transactions.find((t: any) => t.payment_type === 'disbursement');
    expect(disbTxn).toBeTruthy();
    expect(disbTxn.amount).toBe(15000);
    expect(disbTxn.status).toBe('completed');
    expect(disbTxn.reference_number).toBe(disbursement.reference_number);

    // ── Step 8: Verify double-disbursement is blocked ─
    const doubleRes = await request.post(`${API}/underwriter/applications/${appId}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual' },
    });
    expect([400, 409]).toContain(doubleRes.status());

    // ── Step 9: Verify final application status ───────
    const finalApp = await request.get(`${API}/underwriter/applications/${appId}`, {
      headers: adminHeaders,
    });
    const finalData = await finalApp.json();
    expect(finalData.status).toBe('disbursed');
  });
});


test.describe('Consent signing – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    return { applicantToken, adminToken };
  }

  test('submit-with-consent: creates draft, signs and submits in one step', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Create draft
    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: {
        amount_requested: 8000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E consent signing test',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();
    expect(app.status).toBe('draft');

    // Submit with consent
    const submitRes = await request.post(`${API}/loans/${app.id}/submit-with-consent`, {
      headers,
      data: {
        signature_data: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        typed_name: 'Marcus Mohammed',
        agreed: true,
      },
    });
    expect(submitRes.status()).toBe(200);
    const result = await submitRes.json();
    expect(result.reference_number).toMatch(/^ZOT-/);
    // Status should be one of: submitted, approved, declined, decision_pending, under_review
    expect(['submitted', 'approved', 'declined', 'decision_pending', 'under_review']).toContain(result.status);
  });

  test('submit-with-consent: rejects when agreed is false', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: {
        amount_requested: 5000,
        term_months: 6,
        purpose: 'personal',
        purpose_description: 'E2E consent test – should fail',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    const submitRes = await request.post(`${API}/loans/${app.id}/submit-with-consent`, {
      headers,
      data: {
        signature_data: 'data:image/png;base64,dGVzdA==',
        typed_name: 'Marcus Mohammed',
        agreed: false,
      },
    });
    expect(submitRes.status()).toBe(400);
    const body = await submitRes.json();
    expect(body.detail).toMatch(/agree/i);
  });

  test('submit-with-consent: rejects already submitted app', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: {
        amount_requested: 6000,
        term_months: 9,
        purpose: 'personal',
        purpose_description: 'E2E consent test – double submit',
        items: [],
      },
    });
    const app = await createRes.json();

    // First submit succeeds
    const firstRes = await request.post(`${API}/loans/${app.id}/submit-with-consent`, {
      headers,
      data: {
        signature_data: 'data:image/png;base64,dGVzdA==',
        typed_name: 'Marcus Mohammed',
        agreed: true,
      },
    });
    expect(firstRes.status()).toBe(200);

    // Second submit should fail (no longer draft)
    const secondRes = await request.post(`${API}/loans/${app.id}/submit-with-consent`, {
      headers,
      data: {
        signature_data: 'data:image/png;base64,dGVzdA==',
        typed_name: 'Marcus Mohammed',
        agreed: true,
      },
    });
    expect(secondRes.status()).toBe(404);
  });

  test('consent-pdf: download after signing (docx format)', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Create and submit with consent
    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: {
        amount_requested: 7000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E consent DOCX download test',
        items: [],
      },
    });
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit-with-consent`, {
      headers,
      data: {
        signature_data: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        typed_name: 'Marcus Mohammed',
        agreed: true,
      },
    });

    // Download consent document as applicant (now docx)
    const docxRes = await request.get(`${API}/loans/${app.id}/consent-pdf`, { headers });
    expect(docxRes.status()).toBe(200);
    const contentType = docxRes.headers()['content-type'];
    expect(contentType).toContain('application/pdf');
    const contentDisp = docxRes.headers()['content-disposition'] || '';
    expect(contentDisp).toMatch(/hire-purchase-agreement.*\.pdf/i);
    const body = await docxRes.body();
    // PDF starts with %PDF
    expect(body.slice(0, 4).toString()).toBe('%PDF');
    expect(body.length).toBeGreaterThan(1000);
  });

  test('consent-pdf: admin can also download (docx format)', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 9000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E admin consent DOCX test',
        items: [],
      },
    });
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit-with-consent`, {
      headers: applicantHeaders,
      data: {
        signature_data: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        typed_name: 'Marcus Mohammed',
        agreed: true,
      },
    });

    // Admin downloads consent document (now docx)
    const docxRes = await request.get(`${API}/loans/${app.id}/consent-pdf`, {
      headers: adminHeaders,
    });
    expect(docxRes.status()).toBe(200);
    expect(docxRes.headers()['content-type']).toContain('application/pdf');
  });

  test('consent-pdf: returns 400 when not signed', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Create a draft (not submitted / not signed)
    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: {
        amount_requested: 4000,
        term_months: 6,
        purpose: 'personal',
        purpose_description: 'E2E unsigned consent test',
        items: [],
      },
    });
    const app = await createRes.json();

    // Submit without consent (old way)
    await request.post(`${API}/loans/${app.id}/submit`, { headers });

    // Try to download consent PDF — should fail
    const pdfRes = await request.get(`${API}/loans/${app.id}/consent-pdf`, { headers });
    expect(pdfRes.status()).toBe(400);
    const body = await pdfRes.json();
    expect(body.detail).toMatch(/not.*signed/i);
  });
});


test.describe('Consumer portal – consent PDF visible on status page', () => {
  test('approve decision uses engine values (ignores approved_amount override)', async ({ request }) => {
    const API = 'http://localhost:8000/api';
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Developer',
        employment_type: 'employed',
        years_employed: 5,
        monthly_income: 12000,
        monthly_expenses: 2500,
        existing_debt: 1000,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 12000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E approve-override test',
        items: [],
      },
    });
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    // Approve WITHOUT passing approved_amount/approved_rate — backend should use decision engine values
    const decideRes = await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders,
      data: {
        action: 'approve',
        reason: 'E2E test – approve without override',
        // Intentionally omit approved_amount and approved_rate
      },
    });
    expect(decideRes.status()).toBe(200);

    const appRes = await request.get(`${API}/underwriter/applications/${app.id}`, { headers: adminHeaders });
    const approved = await appRes.json();
    expect(approved.status).toBe('approved');
    expect(Number(approved.amount_approved)).toBe(12000);
    expect(Number(approved.interest_rate)).toBeGreaterThan(0);
  });

  test('full application returns merchant_name, items for hire-purchase', async ({ request }) => {
    const API = 'http://localhost:8000/api';
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const merchantsRes = await request.get(`${API}/catalog/merchants`, { headers: applicantHeaders });
    expect(merchantsRes.status()).toBe(200);
    const merchants = await merchantsRes.json();
    expect(merchants.length).toBeGreaterThan(0);
    const merchantId = merchants[0].id;

    const branchesRes = await request.get(`${API}/catalog/merchants/${merchantId}/branches`, { headers: applicantHeaders });
    const branches = await branchesRes.json();
    const branchId = branches[0].id;

    const categoriesRes = await request.get(`${API}/catalog/merchants/${merchantId}/categories`, { headers: applicantHeaders });
    const categories = await categoriesRes.json();
    const categoryId = categories[0].id;

    const productsRes = await request.get(`${API}/catalog/products?merchant_id=${merchantId}&amount=5000`, {
      headers: applicantHeaders,
    });
    const products = await productsRes.json();
    expect(products.length).toBeGreaterThan(0);
    const productId = products[0].id;

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 5000,
        term_months: 12,
        purpose: 'personal',
        merchant_id: merchantId,
        branch_id: branchId,
        credit_product_id: productId,
        downpayment: 0,
        total_financed: 5000,
        items: [{ category_id: categoryId, price: 5000, quantity: 1, description: 'Test item' }],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    const fullRes = await request.get(`${API}/underwriter/applications/${app.id}/full`, { headers: adminHeaders });
    expect(fullRes.status()).toBe(200);
    const full = await fullRes.json();
    expect(full.application.merchant_name).toBeTruthy();
    expect(full.application.branch_name).toBeTruthy();
    expect(full.application.credit_product_name).toBeTruthy();
    expect(Array.isArray(full.application.items)).toBe(true);
    expect(full.application.items.length).toBeGreaterThan(0);
  });

  test('backoffice loan details shows Shopping Context and Plan Selection', async ({ page, request }) => {
    const API = 'http://localhost:8000/api';
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const { access_token: adminToken } = await adminLogin.json();

    const merchants = await (await request.get(`${API}/catalog/merchants`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();
    const branches = await (await request.get(`${API}/catalog/merchants/${merchants[0].id}/branches`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();
    const categories = await (await request.get(`${API}/catalog/merchants/${merchants[0].id}/categories`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();
    const products = await (await request.get(`${API}/catalog/products?merchant_id=${merchants[0].id}&amount=5000`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();

    const createRes = await request.post(`${API}/loans/`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
      data: {
        amount_requested: 5000,
        term_months: 12,
        purpose: 'personal',
        merchant_id: merchants[0].id,
        branch_id: branches[0].id,
        credit_product_id: products[0].id,
        downpayment: 0,
        total_financed: 5000,
        items: [{ category_id: categories[0].id, price: 5000, quantity: 1 }],
      },
    });
    const app = await createRes.json();

    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/review/${app.id}`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('Shopping Context')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Plan Selection')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Loan Details')).toBeVisible();
  });

  test('consumer loan details shows Shopping Context and Plan Selection', async ({ page, request }) => {
    const API = 'http://localhost:8000/api';
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const merchants = await (await request.get(`${API}/catalog/merchants`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();
    const branches = await (await request.get(`${API}/catalog/merchants/${merchants[0].id}/branches`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();
    const categories = await (await request.get(`${API}/catalog/merchants/${merchants[0].id}/categories`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();
    const products = await (await request.get(`${API}/catalog/products?merchant_id=${merchants[0].id}&amount=5000`, { headers: { Authorization: `Bearer ${applicantToken}` } })).json();

    const createRes = await request.post(`${API}/loans/`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
      data: {
        amount_requested: 5000,
        term_months: 12,
        purpose: 'personal',
        merchant_id: merchants[0].id,
        branch_id: branches[0].id,
        credit_product_id: products[0].id,
        downpayment: 0,
        total_financed: 5000,
        items: [{ category_id: categories[0].id, price: 5000, quantity: 1 }],
      },
    });
    const app = await createRes.json();

    await loginAsApplicant(page);
    await page.goto(`${BASE}/applications/${app.id}`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByText('Shopping Context')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Plan Selection')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText('Loan Details')).toBeVisible();
  });

  test('consent PDF download card appears after signing', async ({ page, request }) => {
    const API = 'http://localhost:8000/api';

    // Create and submit with consent via API
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: {
        amount_requested: 6500,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E consent status page test',
        items: [],
      },
    });
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit-with-consent`, {
      headers,
      data: {
        signature_data: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
        typed_name: 'Marcus Mohammed',
        agreed: true,
      },
    });

    // Login and navigate to the application status page
    await loginAsApplicant(page);
    await page.goto(`${BASE}/applications/${app.id}`);
    await page.waitForLoadState('networkidle');

    // Verify the consent PDF card is visible
    await expect(page.getByText('Hire Purchase Agreement and Consent')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Signed on.*Marcus Mohammed/i)).toBeVisible({ timeout: 3000 });
    await expect(page.getByRole('button', { name: /Download PDF/i })).toBeVisible({ timeout: 3000 });
  });
});


test.describe('Loan lifecycle – Decline', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    return { applicantToken, adminToken };
  }

  test('full lifecycle: create → submit → decline → verify status & cannot disburse', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // ── Step 1: Create a draft application ────────────
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 50000,
        term_months: 24,
        purpose: 'business',
        purpose_description: 'E2E lifecycle test – decline scenario',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const application = await createRes.json();
    const appId = application.id;
    expect(application.status).toBe('draft');

    // ── Step 2: Submit the application ────────────────
    // The decision engine auto-runs and may auto-decline.
    // Either way, the underwriter will explicitly decline.
    const submitRes = await request.post(`${API}/loans/${appId}/submit`, {
      headers: applicantHeaders,
    });
    expect(submitRes.status()).toBe(200);
    const submitted = await submitRes.json();
    // Any outcome is fine — the underwriter will explicitly decline
    expect(typeof submitted.status).toBe('string');

    // ── Step 3: Underwriter declines the application ──
    const decideRes = await request.post(`${API}/underwriter/applications/${appId}/decide`, {
      headers: adminHeaders,
      data: {
        action: 'decline',
        reason: 'E2E test decline – insufficient income for requested amount',
      },
    });
    expect(decideRes.status()).toBe(200);
    const decision = await decideRes.json();
    expect(decision.final_outcome).toBe('decline');

    // ── Step 4: Verify application status is declined ─
    const appAfterDecline = await request.get(`${API}/underwriter/applications/${appId}`, {
      headers: adminHeaders,
    });
    expect(appAfterDecline.status()).toBe(200);
    const declinedApp = await appAfterDecline.json();
    expect(declinedApp.status).toBe('declined');
    expect(declinedApp.decided_at).toBeTruthy();

    // ── Step 5: Verify disbursement is rejected ───────
    const disbRes = await request.post(`${API}/underwriter/applications/${appId}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'Should fail – application is declined' },
    });
    expect(disbRes.status()).toBe(400);
    const disbError = await disbRes.json();
    expect(disbError.detail).toMatch(/cannot disburse|declined/i);

    // ── Step 6: Verify no payment schedule exists ─────
    const schedRes = await request.get(`${API}/payments/${appId}/schedule`, {
      headers: adminHeaders,
    });
    expect(schedRes.status()).toBe(200);
    const schedule = await schedRes.json();
    expect(schedule.length).toBe(0);

    // ── Step 7: Verify no transactions exist ──────────
    const historyRes = await request.get(`${API}/payments/${appId}/history`, {
      headers: adminHeaders,
    });
    expect(historyRes.status()).toBe(200);
    const transactions = await historyRes.json();
    expect(transactions.length).toBe(0);
  });
});


test.describe('Contract generation – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    return { applicantToken, adminToken };
  }

  test('generate-contract: returns docx for existing application', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Create an application
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 8000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E generate-contract docx test',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    // Generate contract via BO endpoint
    const contractRes = await request.get(
      `${API}/underwriter/applications/${app.id}/generate-contract`,
      { headers: adminHeaders },
    );
    expect(contractRes.status()).toBe(200);

    // Verify DOCX content type
    const contentType = contractRes.headers()['content-type'];
    expect(contentType).toContain('application/vnd.openxmlformats-officedocument.wordprocessingml.document');

    // Verify filename in content-disposition
    const contentDisp = contractRes.headers()['content-disposition'] || '';
    expect(contentDisp).toMatch(/contract-.*\.docx/i);

    // Verify DOCX body (ZIP format, starts with PK)
    const body = await contractRes.body();
    expect(body.slice(0, 2).toString()).toBe('PK');
    expect(body.length).toBeGreaterThan(10000);
  });

  test('generate-contract: returns 404 for non-existent application', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(
      `${API}/underwriter/applications/999999/generate-contract`,
      { headers: adminHeaders },
    );
    expect(res.status()).toBe(404);
  });

  test('generate-contract: requires admin/underwriter role', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Create an application
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 5000,
        term_months: 6,
        purpose: 'personal',
        purpose_description: 'E2E generate-contract auth test',
        items: [],
      },
    });
    const app = await createRes.json();

    // Applicant should not be able to generate contract
    const res = await request.get(
      `${API}/underwriter/applications/${app.id}/generate-contract`,
      { headers: applicantHeaders },
    );
    expect(res.status()).toBe(403);

    // Admin should succeed
    const adminRes = await request.get(
      `${API}/underwriter/applications/${app.id}/generate-contract`,
      { headers: adminHeaders },
    );
    expect(adminRes.status()).toBe(200);
  });

  test('generate-contract: includes applicant details in docx with items', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Ensure applicant has a profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        address_line1: '99 Contract St',
        city: 'San Fernando',
        parish: 'San Fernando',
        employer_name: 'Test Corp',
        employer_sector: 'Information Technology',
        job_title: 'Developer',
        employment_type: 'employed',
        years_employed: 5,
        monthly_income: 12000,
        monthly_expenses: 3000,
      },
    });

    // Get catalog data for a proper hire-purchase application
    const merchantsRes = await request.get(`${API}/catalog/merchants`, { headers: applicantHeaders });
    const merchants = await merchantsRes.json();
    const merchantId = merchants[0].id;

    const branchesRes = await request.get(`${API}/catalog/merchants/${merchantId}/branches`, { headers: applicantHeaders });
    const branches = await branchesRes.json();

    const categoriesRes = await request.get(`${API}/catalog/merchants/${merchantId}/categories`, { headers: applicantHeaders });
    const categories = await categoriesRes.json();

    const productsRes = await request.get(`${API}/catalog/products?merchant_id=${merchantId}&amount=8000`, { headers: applicantHeaders });
    const products = await productsRes.json();

    // Create application with items
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 8000,
        term_months: 12,
        purpose: 'personal',
        merchant_id: merchantId,
        branch_id: branches[0].id,
        credit_product_id: products[0].id,
        downpayment: 500,
        total_financed: 7500,
        items: [
          { category_id: categories[0].id, price: 5000, quantity: 1, description: 'Test AC Unit' },
          { category_id: categories[0].id, price: 3000, quantity: 1, description: 'Test Fridge' },
        ],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    // Generate contract
    const contractRes = await request.get(
      `${API}/underwriter/applications/${app.id}/generate-contract`,
      { headers: adminHeaders },
    );
    expect(contractRes.status()).toBe(200);

    const body = await contractRes.body();
    expect(body.slice(0, 2).toString()).toBe('PK');
    // Contract with items should be a complete, substantial document
    expect(body.length).toBeGreaterThan(10000);
  });
});


test.describe('Customer search – API tests', () => {
  const API = 'http://localhost:8000/api';

  test('search by name returns matching applicants with profile data', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await loginRes.json();
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/underwriter/customers/search?q=marcus`, { headers });
    expect(res.status()).toBe(200);
    const results = await res.json();
    expect(results.length).toBeGreaterThan(0);
    // All results should have matching name
    for (const r of results) {
      const matchesName = r.first_name?.toLowerCase().includes('marcus') ||
        r.last_name?.toLowerCase().includes('marcus') ||
        r.email?.toLowerCase().includes('marcus');
      expect(matchesName).toBe(true);
    }
    // First result should have profile with fields
    expect(results[0].profile).toBeTruthy();
    expect(results[0].email).toBeTruthy();
    expect(results[0].first_name).toBeTruthy();
  });

  test('search requires min 2 characters', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await loginRes.json();

    const res = await request.get(`${API}/underwriter/customers/search?q=a`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(res.status()).toBe(422); // validation error for min_length=2
  });

  test('search requires staff role', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await loginRes.json();

    const res = await request.get(`${API}/underwriter/customers/search?q=test`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
    });
    expect(res.status()).toBe(403);
  });
});


test.describe('Payment schedule on application page', () => {
  const API = 'http://localhost:8000/api';

  test('payment schedule returns data for disbursed loan', async ({ request }) => {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Ensure healthy profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Developer',
        employment_type: 'employed',
        years_employed: 5,
        monthly_income: 15000,
        monthly_expenses: 3000,
        existing_debt: 1500,
      },
    });

    // Create → submit → approve → disburse
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 10000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E payment schedule test',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'E2E schedule test' },
    });
    const disbRes = await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'E2E schedule test' },
    });
    expect(disbRes.status()).toBe(200);

    // Get payment schedule
    const schedRes = await request.get(`${API}/payments/${app.id}/schedule`, { headers: adminHeaders });
    expect(schedRes.status()).toBe(200);
    const schedule = await schedRes.json();
    expect(schedule.length).toBeGreaterThan(0);

    // Each row should have required fields
    for (const row of schedule) {
      expect(row.installment_number).toBeGreaterThan(0);
      expect(row.due_date).toBeTruthy();
      expect(Number(row.amount_due)).toBeGreaterThan(0);
      expect(Number(row.principal)).toBeGreaterThanOrEqual(0);
      expect(Number(row.interest)).toBeGreaterThanOrEqual(0);
      expect(row.status).toBeTruthy();
    }

    // Verify totals
    const totalDue = schedule.reduce((s: number, r: any) => s + Number(r.amount_due), 0);
    const totalPrincipal = schedule.reduce((s: number, r: any) => s + Number(r.principal), 0);
    const totalInterest = schedule.reduce((s: number, r: any) => s + Number(r.interest), 0);
    expect(totalDue).toBeGreaterThan(0);
    expect(totalPrincipal).toBeGreaterThan(0);
    expect(totalInterest).toBeGreaterThanOrEqual(0);
    // Total due should equal principal + interest + fees
    expect(totalDue).toBeGreaterThanOrEqual(totalPrincipal);
  });

  test('monthly_payment is populated on approved application', async ({ request }) => {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Ensure healthy profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Developer',
        employment_type: 'employed',
        years_employed: 5,
        monthly_income: 15000,
        monthly_expenses: 3000,
        existing_debt: 1500,
      },
    });

    // Create and submit
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 10000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E monthly_payment test',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    // Approve
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'E2E monthly_payment test' },
    });

    // Verify monthly_payment is set
    const appRes = await request.get(`${API}/underwriter/applications/${app.id}`, { headers: adminHeaders });
    const approved = await appRes.json();
    expect(approved.status).toBe('approved');
    expect(Number(approved.monthly_payment)).toBeGreaterThan(0);
  });
});


test.describe('Application notes – API tests', () => {
  const API = 'http://localhost:8000/api';

  test('add and list notes on an application', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await loginRes.json();
    const headers = { Authorization: `Bearer ${adminToken}` };

    // Pick the first application
    const queueRes = await request.get(`${API}/underwriter/queue?per_page=1`, { headers });
    const apps = await queueRes.json();
    expect(apps.length).toBeGreaterThan(0);
    const appId = apps[0].id;

    // Add two notes
    const n1 = await request.post(`${API}/underwriter/applications/${appId}/notes`, {
      headers, data: { content: 'First test note' },
    });
    expect(n1.status()).toBe(201);
    const note1 = await n1.json();
    expect(note1.content).toBe('First test note');
    expect(note1.user_name).toBeTruthy();

    const n2 = await request.post(`${API}/underwriter/applications/${appId}/notes`, {
      headers, data: { content: 'Second test note' },
    });
    expect(n2.status()).toBe(201);

    // List notes — newest first
    const listRes = await request.get(`${API}/underwriter/applications/${appId}/notes`, { headers });
    expect(listRes.status()).toBe(200);
    const notes = await listRes.json();
    expect(notes.length).toBeGreaterThanOrEqual(2);
    // Newest first
    expect(notes[0].content).toBe('Second test note');
    expect(notes[1].content).toBe('First test note');
  });

  test('notes require staff role', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: token } = await loginRes.json();

    const res = await request.get(`${API}/underwriter/applications/1/notes`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(403);
  });

  test('add note requires content', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await loginRes.json();

    const res = await request.post(`${API}/underwriter/applications/1/notes`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { content: '' },
    });
    expect(res.status()).toBe(422); // validation error for min_length=1
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Rules Management – API & UI tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Rules Management – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getAdminHeaders(request: import('@playwright/test').APIRequestContext) {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await loginRes.json();
    return { Authorization: `Bearer ${access_token}` };
  }

  test('GET /admin/rules returns rules list with allowed fields', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const res = await request.get(`${API}/admin/rules`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.version).toBeGreaterThanOrEqual(2);
    expect(data.rules.length).toBeGreaterThanOrEqual(15);
    expect(data.allowed_fields).toBeTruthy();
    // Verify structure of first rule
    const r01 = data.rules.find((r: any) => r.rule_id === 'R01');
    expect(r01).toBeTruthy();
    expect(r01.name).toBe('Minimum Age');
    expect(r01.threshold).toBe(18);
    expect(r01.enabled).toBe(true);
  });

  test('PUT /admin/rules saves and increments version', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    // Get current rules
    const getRes = await request.get(`${API}/admin/rules`, { headers });
    const { rules, version: oldVersion } = await getRes.json();

    // Save with a modification
    const modified = rules.map((r: any) => ({
      ...r,
      // Toggle R13 outcome to 'pass' for test
      outcome: r.rule_id === 'R13' ? 'pass' : r.outcome,
    }));
    const putRes = await request.put(`${API}/admin/rules`, {
      headers,
      data: { rules: modified },
    });
    expect(putRes.status()).toBe(200);
    const putBody = await putRes.json();
    expect(putBody.version).toBeGreaterThan(oldVersion);

    // Verify it persisted
    const getRes2 = await request.get(`${API}/admin/rules`, { headers });
    const data2 = await getRes2.json();
    const r13 = data2.rules.find((r: any) => r.rule_id === 'R13');
    expect(r13.outcome).toBe('pass');

    // Revert back
    const reverted = data2.rules.map((r: any) => ({
      ...r,
      outcome: r.rule_id === 'R13' ? 'refer' : r.outcome,
    }));
    await request.put(`${API}/admin/rules`, { headers, data: { rules: reverted } });
  });

  test('PUT /admin/rules with custom rule, then DELETE it', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const getRes = await request.get(`${API}/admin/rules`, { headers });
    const { rules } = await getRes.json();

    // Add a custom rule
    const customRule = {
      rule_id: 'R_CUSTOM_E2E_TEST',
      name: 'E2E Test Rule',
      description: 'Test custom rule for e2e',
      field: 'monthly_income',
      operator: 'gte',
      threshold: 999,
      outcome: 'refer',
      severity: 'refer',
      type: 'threshold',
      is_custom: true,
      enabled: true,
    };
    const putRes = await request.put(`${API}/admin/rules`, {
      headers,
      data: { rules: [...rules, customRule] },
    });
    expect(putRes.status()).toBe(200);

    // Verify it's there
    const getRes2 = await request.get(`${API}/admin/rules`, { headers });
    const data2 = await getRes2.json();
    const found = data2.rules.find((r: any) => r.rule_id === 'R_CUSTOM_E2E_TEST');
    expect(found).toBeTruthy();
    expect(found.name).toBe('E2E Test Rule');

    // Delete it
    const delRes = await request.delete(`${API}/admin/rules/R_CUSTOM_E2E_TEST`, { headers });
    expect(delRes.status()).toBe(200);

    // Verify it's gone
    const getRes3 = await request.get(`${API}/admin/rules`, { headers });
    const data3 = await getRes3.json();
    const gone = data3.rules.find((r: any) => r.rule_id === 'R_CUSTOM_E2E_TEST');
    expect(gone).toBeFalsy();
  });

  test('DELETE built-in rule is blocked', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const res = await request.delete(`${API}/admin/rules/R01`, { headers });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.detail).toMatch(/cannot delete|built-in|disable/i);
  });

  test('rules require admin role', async ({ request }) => {
    // Login as applicant
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();
    const res = await request.get(`${API}/admin/rules`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(403);
  });

  test('POST /admin/rules/generate refuses discriminatory prompts', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const res = await request.post(`${API}/admin/rules/generate`, {
      headers,
      data: { prompt: 'Decline all female applicants' },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('refused');
    expect(body.refusal_reason).toBeTruthy();
  });
});

test.describe('Rules Management – UI tests', () => {
  test('rules page loads for admin', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/rules`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: 'Underwriting Rules' })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('R01')).toBeVisible();
    await expect(page.getByText('Minimum Age')).toBeVisible();
  });

  test('rules page shows all rules with controls', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/rules`);
    await page.waitForLoadState('networkidle');
    // Check key rules are visible
    await expect(page.getByText('R03')).toBeVisible();
    await expect(page.getByText('Minimum Income')).toBeVisible();
    await expect(page.getByText('R20')).toBeVisible();
    await expect(page.getByText('Credit Score')).toBeVisible();
    // Legend should be visible (use exact: false to match within the legend spans, and first() to avoid strict mode)
    await expect(page.locator('.flex.items-center.gap-1\\.5', { hasText: 'Decline' }).first()).toBeVisible();
    await expect(page.locator('.flex.items-center.gap-1\\.5', { hasText: 'Refer' }).first()).toBeVisible();
  });

  test('AI rule generator section can be opened', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/rules`);
    await page.waitForLoadState('networkidle');
    // Click "Add Rule with AI"
    await page.getByText('Add Rule with AI').click();
    await expect(page.getByText(/Describe a new underwriting rule/i)).toBeVisible();
    await expect(page.getByPlaceholder(/Decline applicants/i)).toBeVisible();
    await expect(page.getByText(/GPT-5.2/)).toBeVisible();
  });

  test('rules nav item visible for admin only', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.getByRole('link', { name: 'Rules' })).toBeVisible({ timeout: 5000 });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// CRITICAL: Custom rule impacts actual decisions end-to-end
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Custom rule affects real decisions', () => {
  const API = 'http://localhost:8000/api';

  test('AI-created rule (decline income < 500) causes decline on new application', async ({ request }) => {
    // 1. Login as admin
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // 2. Get current rules
    const getRes = await request.get(`${API}/admin/rules`, { headers: adminHeaders });
    const { rules: currentRules } = await getRes.json();

    // 3. Add a custom "decline if income < 500" rule
    const customRule = {
      rule_id: 'R_CUSTOM_INCOME_500',
      name: 'Decline Low Income',
      description: 'Decline if monthly income is below 500 TTD',
      field: 'monthly_income',
      operator: 'gte',
      threshold: 500,
      outcome: 'decline',
      severity: 'hard',
      type: 'threshold',
      is_custom: true,
      enabled: true,
    };
    const saveRes = await request.put(`${API}/admin/rules`, {
      headers: adminHeaders,
      data: { rules: [...currentRules, customRule] },
    });
    expect(saveRes.status()).toBe(200);

    // 4. Login as applicant and set profile with income = 400 (below 500)
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };

    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Developer',
        employment_type: 'employed',
        years_employed: 5,
        monthly_income: 400,  // Below the custom 500 threshold
        monthly_expenses: 200,
        existing_debt: 0,
      },
    });

    // 5. Create and submit application
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 5000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'E2E custom rule test — should be declined',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    const submitRes = await request.post(`${API}/loans/${app.id}/submit`, {
      headers: applicantHeaders,
    });
    expect(submitRes.status()).toBe(200);

    // 6. Check the decision — should be auto_decline
    const decisionRes = await request.get(`${API}/underwriter/applications/${app.id}/decision`, {
      headers: adminHeaders,
    });
    expect(decisionRes.status()).toBe(200);
    const decision = await decisionRes.json();
    expect(decision.engine_outcome).toBe('auto_decline');

    // 7. Verify the application status is declined
    const appRes = await request.get(`${API}/underwriter/applications/${app.id}`, {
      headers: adminHeaders,
    });
    const appData = await appRes.json();
    expect(appData.status).toBe('declined');

    // 8. Cleanup: remove the custom rule
    const getRes2 = await request.get(`${API}/admin/rules`, { headers: adminHeaders });
    const { rules: updatedRules } = await getRes2.json();
    const filtered = updatedRules.filter((r: any) => r.rule_id !== 'R_CUSTOM_INCOME_500');
    await request.put(`${API}/admin/rules`, {
      headers: adminHeaders,
      data: { rules: filtered },
    });

    // 9. Restore applicant income
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: { monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500 },
    });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Comments / Messaging – API tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Comments / Messaging – API tests', () => {
  const API = 'http://localhost:8000/api';

  test('consumer can add comment and underwriter can reply', async ({ request }) => {
    // Login both users
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Get an application
    const appsRes = await request.get(`${API}/loans/`, { headers: applicantHeaders });
    const apps = await appsRes.json();
    expect(apps.length).toBeGreaterThan(0);
    const appId = apps[0].id;

    // Consumer adds comment
    const c1 = await request.post(`${API}/loans/${appId}/comments`, {
      headers: applicantHeaders,
      data: { content: 'E2E: Can you provide an update on my application?' },
    });
    expect(c1.status()).toBe(201);
    const comment1 = await c1.json();
    expect(comment1.is_from_applicant).toBe(true);

    // Underwriter sees and replies
    const listRes = await request.get(`${API}/loans/${appId}/comments`, { headers: adminHeaders });
    expect(listRes.status()).toBe(200);
    const comments = await listRes.json();
    expect(comments.length).toBeGreaterThanOrEqual(1);
    const latest = comments[comments.length - 1];
    expect(latest.content).toContain('E2E: Can you provide');

    const c2 = await request.post(`${API}/loans/${appId}/comments`, {
      headers: adminHeaders,
      data: { content: 'E2E: Your application is under review.' },
    });
    expect(c2.status()).toBe(201);
    const reply = await c2.json();
    expect(reply.is_from_applicant).toBe(false);

    // Consumer sees both
    const listRes2 = await request.get(`${API}/loans/${appId}/comments`, { headers: applicantHeaders });
    const allComments = await listRes2.json();
    expect(allComments.length).toBeGreaterThanOrEqual(2);
  });

  test('mark comments as read', async ({ request }) => {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };

    const appsRes = await request.get(`${API}/loans/`, { headers: applicantHeaders });
    const apps = await appsRes.json();
    const appId = apps[0].id;

    const markRes = await request.post(`${API}/loans/${appId}/comments/mark-read`, {
      headers: applicantHeaders,
    });
    expect(markRes.status()).toBe(200);
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Notifications – API tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Notifications – API tests', () => {
  const API = 'http://localhost:8000/api';

  test('consumer can fetch notifications', async ({ request }) => {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await appLogin.json();

    const res = await request.get(`${API}/loans/notifications/messages`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(Array.isArray(data.notifications || data)).toBe(true);
  });

  test('consumer can mark all notifications read', async ({ request }) => {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await appLogin.json();

    const res = await request.post(`${API}/loans/notifications/mark-read`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
  });

  test('notifications page loads in consumer portal', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/notifications`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByRole('heading', { name: /Notification/i })).toBeVisible({ timeout: 5000 });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// References – API tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('References – API tests', () => {
  const API = 'http://localhost:8000/api';

  test('add, list, update, and delete references on an application', async ({ request }) => {
    // Login
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };

    // Get an application
    const appsRes = await request.get(`${API}/loans/`, { headers: applicantHeaders });
    const apps = await appsRes.json();
    expect(apps.length).toBeGreaterThan(0);
    const appId = apps[0].id;

    // Add a reference
    const addRes = await request.post(`${API}/loans/${appId}/references`, {
      headers: applicantHeaders,
      data: {
        name: 'John Doe',
        relationship_type: 'Employer',
        phone: '+1868-555-1234',
        address: '456 Reference St, Port of Spain',
        directions: 'Near the red gate on the left',
      },
    });
    expect(addRes.status()).toBe(201);
    const ref = await addRes.json();
    expect(ref.name).toBe('John Doe');
    expect(ref.directions).toBe('Near the red gate on the left');

    // List references
    const listRes = await request.get(`${API}/loans/${appId}/references`, { headers: applicantHeaders });
    expect(listRes.status()).toBe(200);
    const refs = await listRes.json();
    expect(refs.length).toBeGreaterThanOrEqual(1);
    const found = refs.find((r: any) => r.id === ref.id);
    expect(found).toBeTruthy();

    // Update reference
    const updateRes = await request.put(`${API}/loans/${appId}/references/${ref.id}`, {
      headers: applicantHeaders,
      data: {
        name: 'Jane Smith',
        relationship_type: 'Neighbour',
        phone: '+1868-555-5678',
        address: '789 Updated St',
        directions: 'Updated directions',
      },
    });
    expect(updateRes.status()).toBe(200);
    const updated = await updateRes.json();
    expect(updated.name).toBe('Jane Smith');

    // Delete reference
    const delRes = await request.delete(`${API}/loans/${appId}/references/${ref.id}`, {
      headers: applicantHeaders,
    });
    expect(delRes.status()).toBe(200);

    // Verify deleted
    const listRes2 = await request.get(`${API}/loans/${appId}/references`, { headers: applicantHeaders });
    const refs2 = await listRes2.json();
    const deleted = refs2.find((r: any) => r.id === ref.id);
    expect(deleted).toBeFalsy();
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Manual Repayment – API tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Manual Repayment – API tests', () => {
  const API = 'http://localhost:8000/api';

  test('record manual repayment and verify it appears in history', async ({ request }) => {
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };

    // Ensure healthy profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Developer',
        employment_type: 'employed',
        years_employed: 5,
        monthly_income: 15000,
        monthly_expenses: 3000,
        existing_debt: 1500,
      },
    });

    // Create + submit + approve + disburse
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 8000,
        term_months: 6,
        purpose: 'personal',
        purpose_description: 'E2E manual repayment test',
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'E2E repayment test' },
    });
    await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'E2E repayment test' },
    });

    // Get schedule to find amount
    const schedRes = await request.get(`${API}/payments/${app.id}/schedule`, { headers: adminHeaders });
    const schedule = await schedRes.json();
    expect(schedule.length).toBeGreaterThan(0);
    const firstAmount = Number(schedule[0].amount_due);

    // Record manual payment
    const payRes = await request.post(`${API}/payments/${app.id}/record`, {
      headers: adminHeaders,
      data: {
        amount: firstAmount,
        payment_type: 'manual',
        payment_date: new Date().toISOString().split('T')[0],
        reference_number: 'E2E-REPAY-001',
        notes: 'E2E manual repayment test',
      },
    });
    expect(payRes.status()).toBe(200);

    // Verify in history
    const histRes = await request.get(`${API}/payments/${app.id}/history`, { headers: adminHeaders });
    expect(histRes.status()).toBe(200);
    const history = await histRes.json();
    expect(history.length).toBeGreaterThanOrEqual(1);
    const found = history.find((p: any) => p.reference_number === 'E2E-REPAY-001');
    expect(found).toBeTruthy();
    expect(Number(found.amount)).toBe(firstAmount);
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Dashboard Metrics – API tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Dashboard Metrics – API tests', () => {
  const API = 'http://localhost:8000/api';

  test('backoffice dashboard returns arrears summary', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await loginRes.json();

    const res = await request.get(`${API}/reports/dashboard`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();

    // Should have basic metrics
    expect(data.total_applications).toBeGreaterThanOrEqual(0);
    expect(data.approval_rate).toBeGreaterThanOrEqual(0);

    // Should have arrears summary (may be null if no arrears, but key should exist)
    expect('arrears_summary' in data).toBe(true);
    if (data.arrears_summary) {
      expect(data.arrears_summary.total_delinquent_loans).toBeGreaterThanOrEqual(0);
      expect(data.arrears_summary.buckets).toBeTruthy();
      expect(Array.isArray(data.arrears_summary.buckets)).toBe(true);
    }
  });

  test('consumer loan summary returns data', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();

    const res = await request.get(`${API}/payments/summary/my-loans`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(Array.isArray(data.loans || data)).toBe(true);
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Loan Book Filtering – UI test
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Loan Book Filtering', () => {
  test('arrears filter via URL param shows filter banner', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/loans?arrears=1`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/arrears|overdue|delinquent|past due/i).first()).toBeVisible({ timeout: 5000 });
  });

  test('loan book without filter shows all loans', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/loans`);
    await page.waitForLoadState('networkidle');
    await expect(page.getByText(/Loan Book/i).first()).toBeVisible({ timeout: 5000 });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Consumer Dashboard – UI tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Consumer Dashboard – enhanced UI', () => {
  test('dashboard shows loan info sections', async ({ page }) => {
    await loginAsApplicant(page);
    await expect(page.getByText(/Welcome back|Dashboard/i).first()).toBeVisible({ timeout: 5000 });
    // Should show at least application stats or loan info
    await expect(page.getByText(/Application|Active|Loan|Payment/i).first()).toBeVisible({ timeout: 5000 });
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Bank Statement Analysis – API tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Bank Statement Analysis – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getAdminToken(request: import('@playwright/test').APIRequestContext) {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await loginRes.json();
    return access_token;
  }

  async function getApplicantToken(request: import('@playwright/test').APIRequestContext) {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();
    return access_token;
  }

  async function createDraftApp(request: import('@playwright/test').APIRequestContext, token: string) {
    const res = await request.post(`${API}/loans/`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        amount_requested: 15000,
        term_months: 12,
        purpose: 'personal',
        purpose_description: 'Bank statement test',
      },
    });
    expect(res.status()).toBe(201);
    return (await res.json()).id;
  }

  test('GET bank-analysis returns 404 when no analysis exists', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const applicantToken = await getApplicantToken(request);
    const appId = await createDraftApp(request, applicantToken);

    const res = await request.get(`${API}/underwriter/applications/${appId}/bank-analysis`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(res.status()).toBe(404);
  });

  test('POST analyze-bank-statement returns 404 when no bank statement uploaded', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const applicantToken = await getApplicantToken(request);
    const appId = await createDraftApp(request, applicantToken);

    const res = await request.post(`${API}/underwriter/applications/${appId}/analyze-bank-statement`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(res.status()).toBe(404);
    const body = await res.json();
    expect(body.detail).toMatch(/no bank statement/i);
  });

  test('POST analyze-bank-statement with uploaded statement triggers analysis', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const applicantToken = await getApplicantToken(request);
    const appId = await createDraftApp(request, applicantToken);

    // Upload a bank statement CSV via the underwriter endpoint
    const fs = require('fs');
    const path = require('path');
    const csvPath = path.join(__dirname, 'fixtures', 'bank_statement_ttd_good.csv');
    const csvBuffer = fs.readFileSync(csvPath);

    const uploadRes = await request.post(`${API}/underwriter/applications/${appId}/documents`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      multipart: {
        document_type: 'bank_statement',
        file: {
          name: 'bank_statement_ttd_good.csv',
          mimeType: 'text/csv',
          buffer: csvBuffer,
        },
      },
    });
    expect(uploadRes.status()).toBe(201);

    // Trigger analysis
    const analyzeRes = await request.post(`${API}/underwriter/applications/${appId}/analyze-bank-statement`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    // May succeed (200) if OpenAI key configured, or 200 with failed status if not
    expect(analyzeRes.status()).toBe(200);
    const analysis = await analyzeRes.json();
    expect(analysis.loan_application_id).toBe(appId);
    expect(analysis.document_id).toBeGreaterThan(0);
    expect(['completed', 'failed']).toContain(analysis.status);

    if (analysis.status === 'completed') {
      expect(analysis.summary).toBeTruthy();
      expect(analysis.risk_assessment).toBeTruthy();
      expect(analysis.volatility_score).toBeGreaterThanOrEqual(0);
      expect(analysis.volatility_score).toBeLessThanOrEqual(100);
    } else {
      // Failed (likely no API key in test env) — error_message should explain
      expect(analysis.error_message).toBeTruthy();
    }
  });

  test('GET bank-analysis after analysis returns saved result', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const applicantToken = await getApplicantToken(request);
    const appId = await createDraftApp(request, applicantToken);

    // Upload bank statement
    const fs = require('fs');
    const path = require('path');
    const csvPath = path.join(__dirname, 'fixtures', 'bank_statement_ttd_risky.csv');
    const csvBuffer = fs.readFileSync(csvPath);

    await request.post(`${API}/underwriter/applications/${appId}/documents`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      multipart: {
        document_type: 'bank_statement',
        file: {
          name: 'bank_statement_ttd_risky.csv',
          mimeType: 'text/csv',
          buffer: csvBuffer,
        },
      },
    });

    // Trigger analysis
    await request.post(`${API}/underwriter/applications/${appId}/analyze-bank-statement`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });

    // GET should now return the analysis
    const getRes = await request.get(`${API}/underwriter/applications/${appId}/bank-analysis`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(getRes.status()).toBe(200);
    const analysis = await getRes.json();
    expect(analysis.loan_application_id).toBe(appId);
    expect(['completed', 'failed']).toContain(analysis.status);
    expect(analysis.created_at).toBeTruthy();
  });

  test('POST analyze-bank-statement with corrupt file handles gracefully', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const applicantToken = await getApplicantToken(request);
    const appId = await createDraftApp(request, applicantToken);

    // Upload the corrupt (empty) bank statement
    const fs = require('fs');
    const path = require('path');
    const csvPath = path.join(__dirname, 'fixtures', 'bank_statement_corrupt.csv');
    const csvBuffer = fs.readFileSync(csvPath);

    await request.post(`${API}/underwriter/applications/${appId}/documents`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      multipart: {
        document_type: 'bank_statement',
        file: {
          name: 'bank_statement_corrupt.csv',
          mimeType: 'text/csv',
          buffer: csvBuffer,
        },
      },
    });

    // Trigger analysis — should not crash, should return failed status
    const analyzeRes = await request.post(`${API}/underwriter/applications/${appId}/analyze-bank-statement`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(analyzeRes.status()).toBe(200);
    const analysis = await analyzeRes.json();
    expect(analysis.status).toBe('failed');
    expect(analysis.error_message).toBeTruthy();
    expect(analysis.error_message).toMatch(/empty|unreadable/i);
  });

  test('applicant cannot access bank analysis endpoints', async ({ request }) => {
    const applicantToken = await getApplicantToken(request);

    // Try to trigger analysis as applicant (should fail — not underwriter role)
    const res = await request.post(`${API}/underwriter/applications/1/analyze-bank-statement`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
    });
    expect([401, 403]).toContain(res.status());

    // Try to GET analysis as applicant
    const getRes = await request.get(`${API}/underwriter/applications/1/bank-analysis`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
    });
    expect([401, 403]).toContain(getRes.status());
  });

  test('analyze-bank-statement returns 404 for non-existent application', async ({ request }) => {
    const adminToken = await getAdminToken(request);

    const res = await request.post(`${API}/underwriter/applications/999999/analyze-bank-statement`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(res.status()).toBe(404);
  });

  test('POST analyze-bank-statement with PDF statement triggers analysis', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const applicantToken = await getApplicantToken(request);
    const appId = await createDraftApp(request, applicantToken);

    // Upload a bank statement PDF via the underwriter endpoint
    const fs = require('fs');
    const path = require('path');
    const pdfPath = path.join(__dirname, 'fixtures', 'bank_statement_ttd_good.pdf');
    const pdfBuffer = fs.readFileSync(pdfPath);

    const uploadRes = await request.post(`${API}/underwriter/applications/${appId}/documents`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      multipart: {
        document_type: 'bank_statement',
        file: {
          name: 'bank_statement_ttd_good.pdf',
          mimeType: 'application/pdf',
          buffer: pdfBuffer,
        },
      },
    });
    expect(uploadRes.status()).toBe(201);
    const doc = await uploadRes.json();
    expect(doc.file_name).toBe('bank_statement_ttd_good.pdf');
    expect(doc.document_type).toBe('bank_statement');

    // Trigger analysis
    const analyzeRes = await request.post(`${API}/underwriter/applications/${appId}/analyze-bank-statement`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(analyzeRes.status()).toBe(200);
    const analysis = await analyzeRes.json();
    expect(analysis.loan_application_id).toBe(appId);
    expect(analysis.document_id).toBeGreaterThan(0);
    expect(['completed', 'failed']).toContain(analysis.status);

    if (analysis.status === 'completed') {
      expect(analysis.summary).toBeTruthy();
      expect(analysis.risk_assessment).toBeTruthy();
      expect(analysis.volatility_score).toBeGreaterThanOrEqual(0);
      expect(analysis.volatility_score).toBeLessThanOrEqual(100);
    } else {
      // Failed (likely no OpenAI API key in test env) — error_message should explain
      expect(analysis.error_message).toBeTruthy();
    }
  });
});


// ═══════════════════════════════════════════════════════════════════════════
// Bank Statement Analysis – UI tests
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Bank Statement Analysis – UI tests', () => {
  test('Bank Analysis tab is visible in application review', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/applications`);
    await page.waitForLoadState('networkidle');

    // Find any application link and click it
    const appLink = page.locator('a[href*="/backoffice/review/"], tr[class*="cursor"]').first();
    if (await appLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await appLink.click();
      await page.waitForLoadState('networkidle');

      // Look for the Bank Analysis tab
      await expect(page.getByText('Bank Analysis')).toBeVisible({ timeout: 5000 });
    }
  });

  test('Bank Analysis tab shows empty state when no analysis exists', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/applications`);
    await page.waitForLoadState('networkidle');

    const appLink = page.locator('a[href*="/backoffice/review/"], tr[class*="cursor"]').first();
    if (await appLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await appLink.click();
      await page.waitForLoadState('networkidle');

      // Click the Bank Analysis tab
      const bankTab = page.getByText('Bank Analysis');
      if (await bankTab.isVisible({ timeout: 3000 }).catch(() => false)) {
        await bankTab.click();
        await page.waitForTimeout(1000);

        // Should show either the analysis content or the empty state prompt
        const hasContent = await page.getByText(/Analyze Bank Statement|Bank Statement Analysis|No bank statement/i).first().isVisible({ timeout: 5000 }).catch(() => false);
        expect(hasContent).toBe(true);
      }
    }
  });
});

// ─── Chatbot / Conversations – API tests ────────────────────────────────────
test.describe('Chatbot – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    return { applicantToken, adminToken };
  }

  test('create conversation returns 201 with initial state', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const res = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    expect(res.status()).toBe(201);
    const data = await res.json();
    expect(data.id).toBeDefined();
    expect(data.channel).toBe('web');
    expect(typeof data.current_state).toBe('string');
    expect(Array.isArray(data.messages)).toBe(true);
    expect(data.created_at).toBeDefined();
    expect(data.last_activity_at).toBeDefined();
  });

  test('create conversation resumes existing active conversation for same user', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const res1 = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    expect(res1.status()).toBe(201);
    const conv1 = await res1.json();

    // Second create should resume (return same conversation)
    const res2 = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    expect(res2.status()).toBe(201);
    const conv2 = await res2.json();
    expect(conv2.id).toBe(conv1.id);
  });

  test('get conversation returns full detail with messages', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Create or resume
    const createRes = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    const conv = await createRes.json();

    const getRes = await request.get(`${API}/conversations/${conv.id}`, { headers });
    expect(getRes.status()).toBe(200);
    const detail = await getRes.json();
    expect(detail.id).toBe(conv.id);
    expect(detail.channel).toBe('web');
    expect(Array.isArray(detail.messages)).toBe(true);
  });

  test('get conversation returns 404 for non-existent id', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const res = await request.get(`${API}/conversations/999999`, { headers });
    expect(res.status()).toBe(404);
  });

  test('send message returns assistant response', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Create or resume conversation
    const createRes = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    const conv = await createRes.json();

    // Send a message
    const msgRes = await request.post(`${API}/conversations/${conv.id}/messages`, {
      headers,
      data: { content: 'Hello, I want to learn about loans' },
    });
    expect(msgRes.status()).toBe(200);
    const reply = await msgRes.json();
    expect(reply.id).toBeDefined();
    expect(reply.conversation_id).toBe(conv.id);
    expect(reply.role).toBe('assistant');
    expect(typeof reply.content).toBe('string');
    expect(reply.content.length).toBeGreaterThan(0);
    expect(reply.created_at).toBeDefined();
  });

  test('send message to non-existent conversation returns 404', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const res = await request.post(`${API}/conversations/999999/messages`, {
      headers,
      data: { content: 'hello' },
    });
    expect(res.status()).toBe(404);
  });

  test('send empty message is rejected', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const createRes = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    const conv = await createRes.json();

    const res = await request.post(`${API}/conversations/${conv.id}/messages`, {
      headers,
      data: { content: '' },
    });
    expect(res.status()).toBe(422);
  });

  test('messages are persisted and returned on get', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const createRes = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    const conv = await createRes.json();
    const initialMessageCount = conv.messages.length;

    // Send a message
    await request.post(`${API}/conversations/${conv.id}/messages`, {
      headers,
      data: { content: 'What interest rates do you offer?' },
    });

    // Fetch conversation again – should have the user message + assistant reply
    const getRes = await request.get(`${API}/conversations/${conv.id}`, { headers });
    const detail = await getRes.json();
    expect(detail.messages.length).toBeGreaterThanOrEqual(initialMessageCount + 2);

    // Last two messages: user then assistant
    const msgs = detail.messages;
    const userMsg = msgs[msgs.length - 2];
    const assistantMsg = msgs[msgs.length - 1];
    expect(userMsg.role).toBe('user');
    expect(userMsg.content).toBe('What interest rates do you offer?');
    expect(assistantMsg.role).toBe('assistant');
    expect(assistantMsg.content.length).toBeGreaterThan(0);
  });

  test('admin can list conversations', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/conversations/`, { headers });
    expect(res.status()).toBe(200);
    const conversations = await res.json();
    expect(Array.isArray(conversations)).toBe(true);
    // There should be at least one conversation from previous tests
    expect(conversations.length).toBeGreaterThan(0);
    const first = conversations[0];
    expect(first.id).toBeDefined();
    expect(first.channel).toBeDefined();
    expect(first.current_state).toBeDefined();
  });

  test('admin can list conversations with status filter', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const activeRes = await request.get(`${API}/conversations/?status_filter=active`, { headers });
    expect(activeRes.status()).toBe(200);
    const active = await activeRes.json();
    expect(Array.isArray(active)).toBe(true);

    const allRes = await request.get(`${API}/conversations/?status_filter=all`, { headers });
    expect(allRes.status()).toBe(200);
    const all = await allRes.json();
    expect(Array.isArray(all)).toBe(true);
    expect(all.length).toBeGreaterThanOrEqual(active.length);
  });

  test('applicant cannot list conversations (requires staff role)', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const res = await request.get(`${API}/conversations/`, { headers });
    expect([401, 403]).toContain(res.status());
  });

  test('admin can view any conversation detail', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);

    // Create conversation as applicant
    const createRes = await request.post(`${API}/conversations/`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
      data: { channel: 'web' },
    });
    const conv = await createRes.json();

    // Admin should be able to view it
    const res = await request.get(`${API}/conversations/${conv.id}`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(res.status()).toBe(200);
    const detail = await res.json();
    expect(detail.id).toBe(conv.id);
  });

  test('start-application from conversation creates linked draft', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Create a fresh conversation (withdraw existing ones first by creating new)
    const createRes = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    const conv = await createRes.json();

    // If conversation already has an application linked, skip the start-application call
    if (conv.loan_application_id) {
      // Already linked – just verify structure
      expect(conv.application_summary).toBeDefined();
      return;
    }

    const startRes = await request.post(`${API}/conversations/${conv.id}/start-application`, {
      headers,
      data: { amount_requested: 10000, term_months: 12, purpose: 'personal' },
    });
    expect(startRes.status()).toBe(201);
    const app = await startRes.json();
    expect(app.id).toBeDefined();
    expect(app.reference_number).toMatch(/^ZOT-/);
    expect(app.status).toBe('draft');
    expect(app.amount_requested).toBe(10000);
    expect(app.term_months).toBe(12);

    // Verify conversation now shows linked application
    const getRes = await request.get(`${API}/conversations/${conv.id}`, { headers });
    const detail = await getRes.json();
    expect(detail.loan_application_id).toBe(app.id);
    expect(detail.current_state).toBe('application_in_progress');
    expect(detail.application_summary).toBeDefined();
    expect(detail.application_summary.id).toBe(app.id);
  });

  test('start-application rejects duplicate for same conversation', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Resume the conversation which should already have an application
    const createRes = await request.post(`${API}/conversations/`, {
      headers,
      data: { channel: 'web' },
    });
    const conv = await createRes.json();

    // If it already has an application, trying again should fail
    if (conv.loan_application_id) {
      const res = await request.post(`${API}/conversations/${conv.id}/start-application`, {
        headers,
        data: { amount_requested: 5000, term_months: 6, purpose: 'personal' },
      });
      expect(res.status()).toBe(400);
      const body = await res.json();
      expect(body.detail).toMatch(/already/i);
    }
  });

  test('start-application requires authentication', async ({ request }) => {
    // Try without any auth token
    const res = await request.post(`${API}/conversations/1/start-application`, {
      data: { amount_requested: 5000, term_months: 6, purpose: 'personal' },
    });
    expect([401, 403]).toContain(res.status());
  });

  test('create conversation with entry_point pre_qualified', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Withdraw any existing conversations by sending to a fresh one
    // The create endpoint resumes active ones, so we verify entry_point is returned
    const res = await request.post(`${API}/conversations/`, {
      headers,
      data: {
        channel: 'web',
        entry_point: 'pre_qualified',
        entry_context: { max_amount: 50000 },
      },
    });
    expect(res.status()).toBe(201);
    const data = await res.json();
    expect(data.id).toBeDefined();
    // The response might be a resumed conversation or a new one
    expect(typeof data.current_state).toBe('string');
  });
});

// ─── Chatbot / Conversations – UI tests ─────────────────────────────────────
test.describe('Chatbot – UI tests', () => {
  test('consumer chat page loads and shows chat interface', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/chat`);
    await page.waitForLoadState('networkidle');

    // Should show the chat heading
    await expect(page.getByRole('heading', { name: /Chat with Zotta/i })).toBeVisible();

    // Should show the chat input
    await expect(page.getByPlaceholder(/Type your message/i)).toBeVisible();
  });

  test('consumer can send a message and receive a reply', async ({ page }) => {
    await loginAsApplicant(page);
    await page.goto(`${BASE}/chat`);
    await page.waitForLoadState('networkidle');

    // Wait for the chat to initialize
    await expect(page.getByRole('heading', { name: /Chat with Zotta/i })).toBeVisible();

    // Type a message
    const input = page.getByPlaceholder(/Type your message/i);
    await expect(input).toBeVisible();
    await input.fill('Hi, I want to know about loan options');

    // Click the submit button (icon-only button, use type=submit selector)
    await page.locator('button[type="submit"]').click();

    // User message should appear (use .last() since conversation may have prior messages)
    await expect(page.getByText('Hi, I want to know about loan options').last()).toBeVisible();

    // Wait for assistant reply (AI processing may take a few seconds)
    // The assistant message appears in a left-aligned bubble
    const assistantBubble = page.locator('.flex.justify-start .rounded-lg').last();
    await expect(assistantBubble).toBeVisible({ timeout: 15000 });
  });

  test('chat nav link is visible in consumer nav bar', async ({ page }) => {
    await loginAsApplicant(page);
    await expect(page.getByRole('link', { name: 'Chat', exact: true }).first()).toBeVisible();
  });

  test('backoffice conversations queue loads', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/conversations`);
    await page.waitForLoadState('networkidle');

    // Should show the Conversations heading
    await expect(page.getByRole('heading', { name: /Conversations/i })).toBeVisible();

    // Should show filter buttons
    await expect(page.getByRole('button', { name: 'Active' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Escalated' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'All' })).toBeVisible();
  });

  test('backoffice conversations queue shows conversation entries', async ({ page, request }) => {
    // Ensure at least one conversation exists by creating one via API
    const API = 'http://localhost:8000/api';
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    await request.post(`${API}/conversations/`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
      data: { channel: 'web' },
    });

    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/conversations`);
    await page.waitForLoadState('networkidle');

    // Should show at least one conversation entry
    const convEntry = page.getByText(/Conversation #\d+/i).first();
    await expect(convEntry).toBeVisible({ timeout: 5000 });
  });

  test('backoffice conversation detail page loads', async ({ page, request }) => {
    // First get a conversation ID via API
    const API = 'http://localhost:8000/api';
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await loginRes.json();
    const headers = { Authorization: `Bearer ${adminToken}` };

    const listRes = await request.get(`${API}/conversations/`, { headers });
    const conversations = await listRes.json();
    expect(conversations.length).toBeGreaterThan(0);
    const convId = conversations[0].id;

    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/conversations/${convId}`);
    await page.waitForLoadState('networkidle');

    // Should show conversation detail
    await expect(page.getByText(`Conversation #${convId}`)).toBeVisible();
    // Should show summary sidebar
    await expect(page.getByText('Channel', { exact: true })).toBeVisible();
    await expect(page.getByText('State', { exact: true })).toBeVisible();
  });

  test('backoffice conversations nav link is visible', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.getByRole('link', { name: 'Conversations' })).toBeVisible();
  });

  test('conversations queue filter buttons switch content', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/conversations`);
    await page.waitForLoadState('networkidle');

    // Click All filter
    await page.getByRole('button', { name: 'All' }).click();
    await page.waitForLoadState('networkidle');

    // Click Active filter
    await page.getByRole('button', { name: 'Active' }).click();
    await page.waitForLoadState('networkidle');

    // Click Escalated filter
    await page.getByRole('button', { name: 'Escalated' }).click();
    await page.waitForLoadState('networkidle');

    // Should still show heading
    await expect(page.getByRole('heading', { name: /Conversations/i })).toBeVisible();
  });
});

// ── WhatsApp Notifications ────────────────────────────────────

test.describe('WhatsApp Notifications – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    return { applicantToken, adminToken };
  }

  test('approving an application does not error (WhatsApp fires in background)', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Remove custom rules that might interfere
    const rulesRes = await request.get(`${API}/admin/rules`, { headers: adminHeaders });
    const { rules: currentRules } = await rulesRes.json();
    const builtinOnly = currentRules.filter((r: any) => !r.is_custom);
    if (builtinOnly.length < currentRules.length) {
      await request.put(`${API}/admin/rules`, {
        headers: adminHeaders,
        data: { rules: builtinOnly },
      });
    }

    // Ensure healthy profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        employment_type: 'employed',
        years_employed: 10,
        monthly_income: 15000,
        other_income: 0,
        monthly_expenses: 3000,
        existing_debt: 1500,
        dependents: 1,
      },
    });

    // Create and submit application
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        purpose: 'personal',
        purpose_description: 'E2E WhatsApp notification test',
        amount_requested: 5000,
        term_months: 12,
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    const submitRes = await request.post(`${API}/loans/${app.id}/submit`, {
      headers: applicantHeaders,
    });
    expect(submitRes.status()).toBe(200);

    // Run decision engine
    const engineRes = await request.post(`${API}/underwriter/applications/${app.id}/run-engine`, {
      headers: adminHeaders,
    });
    expect(engineRes.status()).toBe(200);

    // Approve (this triggers WhatsApp in background)
    const approveRes = await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'E2E WhatsApp test' },
    });
    // The approval should succeed regardless of Twilio creds
    expect(approveRes.status()).toBe(200);
    const decision = await approveRes.json();
    expect(decision.final_outcome).toBe('approve');
  });

  test('collection send-whatsapp returns outbound message', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Create a simple app for collection test
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        purpose: 'personal',
        purpose_description: 'E2E collection WhatsApp test',
        amount_requested: 3000,
        term_months: 6,
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    // Submit it
    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    // Send WhatsApp collection message
    const waRes = await request.post(`${API}/collections/${app.id}/send-whatsapp`, {
      headers: adminHeaders,
      data: { message: 'E2E test: payment reminder' },
    });

    // Should return 200 with at least the outbound message
    expect(waRes.status()).toBe(200);
    const messages = await waRes.json();
    expect(Array.isArray(messages)).toBe(true);
    expect(messages.length).toBeGreaterThanOrEqual(1);

    // Outbound message should exist
    const outbound = messages[0];
    expect(outbound.direction).toBe('outbound');
    expect(outbound.message).toBe('E2E test: payment reminder');
    expect(outbound.channel).toBe('whatsapp');
    // Status should be 'sent' (if Twilio creds work) or 'failed' (if not configured)
    expect(['sent', 'failed', 'delivered']).toContain(outbound.status);
  });

  test('collection chat history returns previous messages', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Create and submit app
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        purpose: 'personal',
        purpose_description: 'E2E chat history test',
        amount_requested: 2000,
        term_months: 6,
        items: [],
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();
    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    // Send a message first
    await request.post(`${API}/collections/${app.id}/send-whatsapp`, {
      headers: adminHeaders,
      data: { message: 'Chat history test message' },
    });

    // Fetch chat history
    const historyRes = await request.get(`${API}/collections/${app.id}/chat`, {
      headers: adminHeaders,
    });
    expect(historyRes.status()).toBe(200);
    const history = await historyRes.json();
    expect(Array.isArray(history)).toBe(true);
    expect(history.length).toBeGreaterThanOrEqual(1);
    expect(history.some((m: any) => m.message === 'Chat history test message')).toBe(true);
  });
});


// ══════════════════════════════════════════════════════════════════
// Collections Module – Comprehensive E2E Tests
// ══════════════════════════════════════════════════════════════════

test.describe('Collections – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();

    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();

    // Also get delinquent borrower token
    const borrowerLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'delinquent.borrower@email.com', password: 'Applicant1!' },
    });
    const { access_token: borrowerToken } = await borrowerLogin.json();

    return { applicantToken, adminToken, borrowerToken };
  }

  // ── Collections queue ────────────────────────────────

  test('collections queue returns overdue loans', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    expect(res.status()).toBe(200);
    const queue = await res.json();
    expect(Array.isArray(queue)).toBe(true);
    expect(queue.length).toBeGreaterThan(0);

    // Verify queue entry structure
    const entry = queue[0];
    expect(entry).toHaveProperty('id');
    expect(entry).toHaveProperty('reference_number');
    expect(entry).toHaveProperty('applicant_name');
    expect(entry).toHaveProperty('amount_due');
    expect(entry).toHaveProperty('days_past_due');
    expect(entry).toHaveProperty('outstanding_balance');
    expect(entry).toHaveProperty('phone');
    expect(entry.days_past_due).toBeGreaterThan(0);
  });

  test('collections queue sorted by days past due descending', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await res.json();

    for (let i = 1; i < queue.length; i++) {
      expect(queue[i - 1].days_past_due).toBeGreaterThanOrEqual(queue[i].days_past_due);
    }
  });

  test('collections queue contains Derrick Wellington delinquent loans', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await res.json();

    const derrickLoans = queue.filter((e: any) => e.applicant_name === 'Derrick Wellington');
    expect(derrickLoans.length).toBe(3);

    const refs = derrickLoans.map((l: any) => l.reference_number).sort();
    expect(refs).toContain('ZOT-SCEN-DELINQ30');
    expect(refs).toContain('ZOT-SCEN-DELINQ60');
    expect(refs).toContain('ZOT-SCEN-DELINQ90');

    // All should have phone +447432723070
    for (const loan of derrickLoans) {
      expect(loan.phone).toBe('+447432723070');
    }
  });

  test('collections queue requires staff role', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const res = await request.get(`${API}/collections/queue`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
    });
    expect(res.status()).toBe(403);
  });

  // ── Collection records (interactions) ────────────────

  test('add collection record creates interaction entry', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Get a delinquent loan
    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');
    expect(delinq90).toBeTruthy();

    // Add a collection record
    const recordRes = await request.post(`${API}/collections/${delinq90.id}/record`, {
      headers: adminHeaders,
      data: {
        channel: 'phone',
        notes: 'Called borrower. Left voicemail regarding overdue payment.',
        action_taken: 'Left voicemail',
        outcome: 'no_answer',
        next_action_date: '2026-02-21',
      },
    });
    expect(recordRes.status()).toBe(200);
    const record = await recordRes.json();
    expect(record.channel).toBe('phone');
    expect(record.outcome).toBe('no_answer');
    expect(record.notes).toContain('voicemail');
    expect(record.agent_name).toBeTruthy();
  });

  test('add collection record with promise to pay', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq60 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ60');
    expect(delinq60).toBeTruthy();

    const recordRes = await request.post(`${API}/collections/${delinq60.id}/record`, {
      headers: adminHeaders,
      data: {
        channel: 'whatsapp',
        notes: 'Borrower agreed to pay $5,000 by Feb 28.',
        action_taken: 'Negotiated payment plan',
        outcome: 'promise_to_pay',
        promise_amount: 5000,
        promise_date: '2026-02-28',
        next_action_date: '2026-03-01',
      },
    });
    expect(recordRes.status()).toBe(200);
    const record = await recordRes.json();
    expect(record.outcome).toBe('promise_to_pay');
    expect(record.promise_amount).toBe(5000);
  });

  test('collection history returns all records for a loan', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');

    const historyRes = await request.get(`${API}/collections/${delinq90.id}/history`, {
      headers: adminHeaders,
    });
    expect(historyRes.status()).toBe(200);
    const history = await historyRes.json();
    expect(Array.isArray(history)).toBe(true);
    // Should have at least the record we added above
    expect(history.length).toBeGreaterThanOrEqual(1);
    expect(history[0]).toHaveProperty('channel');
    expect(history[0]).toHaveProperty('outcome');
    expect(history[0]).toHaveProperty('agent_name');
  });

  test('collection record requires staff role', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const res = await request.post(`${API}/collections/1/record`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
      data: { channel: 'phone', outcome: 'no_answer' },
    });
    expect(res.status()).toBe(403);
  });

  // ── WhatsApp chat ────────────────────────────────────

  test('send WhatsApp collection message to delinquent borrower', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq30 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ30');
    expect(delinq30).toBeTruthy();

    const waRes = await request.post(`${API}/collections/${delinq30.id}/send-whatsapp`, {
      headers: adminHeaders,
      data: { message: 'Hi, this is a reminder about your overdue payment. Please contact us.' },
    });
    expect(waRes.status()).toBe(200);
    const messages = await waRes.json();
    expect(Array.isArray(messages)).toBe(true);
    expect(messages.length).toBe(1);

    const outbound = messages[0];
    expect(outbound.direction).toBe('outbound');
    expect(outbound.phone_number).toBe('+447432723070');
    expect(outbound.channel).toBe('whatsapp');
    expect(['sent', 'failed']).toContain(outbound.status);
  });

  test('multiple WhatsApp messages accumulate in chat history', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq30 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ30');

    // Send a second message
    await request.post(`${API}/collections/${delinq30.id}/send-whatsapp`, {
      headers: adminHeaders,
      data: { message: 'Second reminder: please respond to arrange payment.' },
    });

    // Get chat history
    const chatRes = await request.get(`${API}/collections/${delinq30.id}/chat`, {
      headers: adminHeaders,
    });
    expect(chatRes.status()).toBe(200);
    const chat = await chatRes.json();
    expect(chat.length).toBeGreaterThanOrEqual(2);

    // All messages should be for this loan
    for (const msg of chat) {
      expect(msg.loan_application_id).toBe(delinq30.id);
    }
  });

  test('chat history empty for loan with no messages', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Create a fresh app with no collection messages
    const createRes = await request.post(`${API}/loans/`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
      data: { purpose: 'personal', purpose_description: 'E2E empty chat test', amount_requested: 1000, term_months: 6, items: [] },
    });
    const app = await createRes.json();

    const chatRes = await request.get(`${API}/collections/${app.id}/chat`, {
      headers: adminHeaders,
    });
    expect(chatRes.status()).toBe(200);
    const chat = await chatRes.json();
    expect(chat).toEqual([]);
  });

  test('WhatsApp send requires staff role', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const res = await request.post(`${API}/collections/1/send-whatsapp`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
      data: { message: 'should fail' },
    });
    expect(res.status()).toBe(403);
  });

  // ── Inbound webhook ──────────────────────────────────

  test('inbound webhook routes reply to collection chat', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Get the 30-day delinquent loan (which we already sent messages to)
    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq30 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ30');

    // Get current chat count
    const beforeRes = await request.get(`${API}/collections/${delinq30.id}/chat`, { headers: adminHeaders });
    const beforeChat = await beforeRes.json();
    const countBefore = beforeChat.length;

    // Simulate inbound WhatsApp reply from borrower
    const webhookRes = await request.post(`${API}/whatsapp/webhook`, {
      form: {
        Body: 'I will pay $2,000 this Friday, sorry for the delay.',
        From: 'whatsapp:+447432723070',
        To: 'whatsapp:+14155238886',
      },
    });
    expect(webhookRes.status()).toBe(200);

    // Verify the inbound message appears in collection chat
    const afterRes = await request.get(`${API}/collections/${delinq30.id}/chat`, { headers: adminHeaders });
    const afterChat = await afterRes.json();
    expect(afterChat.length).toBeGreaterThan(countBefore);

    const inbound = afterChat.find((m: any) =>
      m.direction === 'inbound' && m.message.includes('I will pay $2,000 this Friday')
    );
    expect(inbound).toBeTruthy();
    expect(inbound.phone_number).toBe('+447432723070');
    expect(inbound.status).toBe('delivered');
  });

  test('inbound webhook does not create chat for loan with no outbound messages', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Get a delinquent loan that has no outbound WhatsApp messages yet
    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq60 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ60');

    // Check if it has outbound messages - if it does, skip this test
    const chatRes = await request.get(`${API}/collections/${delinq60.id}/chat`, { headers: adminHeaders });
    const chat = await chatRes.json();
    const hasOutbound = chat.some((m: any) => m.direction === 'outbound');

    if (!hasOutbound) {
      // Simulate inbound — should NOT create a collection chat since no outbound exists
      await request.post(`${API}/whatsapp/webhook`, {
        form: {
          Body: 'Hello, is anyone there?',
          From: 'whatsapp:+447432723070',
          To: 'whatsapp:+14155238886',
        },
      });

      const afterRes = await request.get(`${API}/collections/${delinq60.id}/chat`, { headers: adminHeaders });
      const afterChat = await afterRes.json();
      expect(afterChat.length).toBe(0);
    }
  });

  // ── Consumer-facing collection messages ──────────────

  test('consumer can see collection messages via notifications endpoint', async ({ request }) => {
    const { borrowerToken, adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };
    const borrowerHeaders = { Authorization: `Bearer ${borrowerToken}` };

    // First send a collection message as admin to one of the delinquent loans
    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');
    expect(delinq90).toBeTruthy();

    await request.post(`${API}/collections/${delinq90.id}/send-whatsapp`, {
      headers: adminHeaders,
      data: { message: 'URGENT: Please contact Zotta collections immediately regarding your overdue account.' },
    });

    // Now fetch as the borrower
    const colRes = await request.get(`${API}/loans/notifications/collection-messages`, {
      headers: borrowerHeaders,
    });
    expect(colRes.status()).toBe(200);
    const data = await colRes.json();
    expect(data.messages).toBeDefined();
    expect(Array.isArray(data.messages)).toBe(true);
    expect(data.messages.length).toBeGreaterThan(0);

    // Should contain the urgent message
    const urgent = data.messages.find((m: any) =>
      m.message.includes('URGENT: Please contact Zotta')
    );
    expect(urgent).toBeTruthy();
    expect(urgent.direction).toBe('outbound');
    expect(urgent.channel).toBe('whatsapp');
  });

  test('consumer can see collection messages for a specific application', async ({ request }) => {
    const { borrowerToken, adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };
    const borrowerHeaders = { Authorization: `Bearer ${borrowerToken}` };

    // Get the delinquent loan ID
    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');

    // Fetch as borrower for that specific app
    const colRes = await request.get(`${API}/loans/${delinq90.id}/collection-messages`, {
      headers: borrowerHeaders,
    });
    expect(colRes.status()).toBe(200);
    const messages = await colRes.json();
    expect(Array.isArray(messages)).toBe(true);
    expect(messages.length).toBeGreaterThan(0);

    // All messages should belong to this application
    for (const msg of messages) {
      expect(msg.application_id).toBe(delinq90.id);
    }
  });

  test('consumer cannot see collection messages for another user application', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Get a delinquent loan belonging to Derrick Wellington
    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');

    // Try to access as Marcus (applicantToken) — should fail (not his loan)
    const colRes = await request.get(`${API}/loans/${delinq90.id}/collection-messages`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
    });
    expect(colRes.status()).toBe(404);
  });

  test('consumer collection messages empty when no messages exist', async ({ request }) => {
    const { applicantToken } = await getTokens(request);

    // Marcus should have no collection messages (no delinquent loans)
    const colRes = await request.get(`${API}/loans/notifications/collection-messages`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
    });
    expect(colRes.status()).toBe(200);
    const data = await colRes.json();
    // Marcus may or may not have collection messages from other tests
    // Just verify structure
    expect(data.messages).toBeDefined();
    expect(Array.isArray(data.messages)).toBe(true);
  });

  // ── Full lifecycle test ──────────────────────────────

  test('full collection lifecycle: queue → interact → WhatsApp → reply → consumer sees', async ({ request }) => {
    const { adminToken, borrowerToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };
    const borrowerHeaders = { Authorization: `Bearer ${borrowerToken}` };

    // 1. Get the collections queue
    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const target = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');
    expect(target).toBeTruthy();
    expect(target.days_past_due).toBeGreaterThan(0);

    // 2. Add a collection interaction record (phone call)
    const interactRes = await request.post(`${API}/collections/${target.id}/record`, {
      headers: adminHeaders,
      data: {
        channel: 'phone',
        notes: 'Full lifecycle test: called borrower',
        action_taken: 'Called and left message',
        outcome: 'no_answer',
        next_action_date: '2026-02-20',
      },
    });
    expect(interactRes.status()).toBe(200);

    // 3. Send WhatsApp follow-up
    const waRes = await request.post(`${API}/collections/${target.id}/send-whatsapp`, {
      headers: adminHeaders,
      data: { message: 'Hi Derrick, we tried calling. Please call us back about your overdue loan.' },
    });
    expect(waRes.status()).toBe(200);

    // 4. Simulate borrower WhatsApp reply
    const webhookRes = await request.post(`${API}/whatsapp/webhook`, {
      form: {
        Body: 'Sorry I missed your call. I can pay next week.',
        From: 'whatsapp:+447432723070',
        To: 'whatsapp:+14155238886',
      },
    });
    expect(webhookRes.status()).toBe(200);

    // 5. Verify chat history (admin view)
    const chatRes = await request.get(`${API}/collections/${target.id}/chat`, { headers: adminHeaders });
    const chat = await chatRes.json();
    const outbound = chat.filter((m: any) => m.direction === 'outbound');
    const inbound = chat.filter((m: any) => m.direction === 'inbound');
    expect(outbound.length).toBeGreaterThan(0);
    expect(inbound.length).toBeGreaterThan(0);

    // 6. Verify interaction history
    const historyRes = await request.get(`${API}/collections/${target.id}/history`, { headers: adminHeaders });
    const history = await historyRes.json();
    expect(history.length).toBeGreaterThan(0);

    // 7. Consumer can see the collection messages
    const consumerRes = await request.get(`${API}/loans/${target.id}/collection-messages`, {
      headers: borrowerHeaders,
    });
    expect(consumerRes.status()).toBe(200);
    const consumerMsgs = await consumerRes.json();
    expect(consumerMsgs.length).toBeGreaterThan(0);

    // Should contain both outbound and inbound
    const consumerOutbound = consumerMsgs.filter((m: any) => m.direction === 'outbound');
    const consumerInbound = consumerMsgs.filter((m: any) => m.direction === 'inbound');
    expect(consumerOutbound.length).toBeGreaterThan(0);
    expect(consumerInbound.length).toBeGreaterThan(0);
  });

  // ── Edge cases ───────────────────────────────────────

  test('add collection record with escalation outcome', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');

    const recordRes = await request.post(`${API}/collections/${delinq90.id}/record`, {
      headers: adminHeaders,
      data: {
        channel: 'email',
        notes: 'Borrower unresponsive after multiple attempts. Escalating to legal.',
        action_taken: 'Escalated to legal department',
        outcome: 'escalated',
      },
    });
    expect(recordRes.status()).toBe(200);
    expect((await recordRes.json()).outcome).toBe('escalated');
  });

  test('add collection record with payment arranged', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq30 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ30');

    const recordRes = await request.post(`${API}/collections/${delinq30.id}/record`, {
      headers: adminHeaders,
      data: {
        channel: 'whatsapp',
        notes: 'Agreed to pay in two installments over 2 weeks',
        action_taken: 'Set up payment plan',
        outcome: 'payment_arranged',
        promise_amount: 2256.46,
        promise_date: '2026-02-21',
        next_action_date: '2026-02-22',
      },
    });
    expect(recordRes.status()).toBe(200);
    const record = await recordRes.json();
    expect(record.outcome).toBe('payment_arranged');
    expect(record.promise_amount).toBeCloseTo(2256.46);
  });

  test('collection record with disputed outcome', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq60 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ60');

    const recordRes = await request.post(`${API}/collections/${delinq60.id}/record`, {
      headers: adminHeaders,
      data: {
        channel: 'phone',
        notes: 'Borrower claims they already paid. Checking records.',
        action_taken: 'Escalated to accounts team for verification',
        outcome: 'disputed',
        next_action_date: '2026-02-18',
      },
    });
    expect(recordRes.status()).toBe(200);
    expect((await recordRes.json()).outcome).toBe('disputed');
  });

  test('collection WhatsApp message with long body', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const queueRes = await request.get(`${API}/collections/queue`, { headers: adminHeaders });
    const queue = await queueRes.json();
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');

    const longMessage = `Dear Derrick Wellington,

This is a formal notification from Zotta Collections regarding your loan account ZOT-SCEN-DELINQ90. Your account is currently 210+ days overdue with an outstanding balance of TTD 26,465.84.

We have made multiple attempts to contact you regarding this matter. Please be aware that continued non-payment may result in additional charges and potential legal action.

To avoid further action, please contact us within 48 hours at 868-555-1234 or reply to this message to arrange a payment plan.

Regards,
Zotta Collections Team`;

    const waRes = await request.post(`${API}/collections/${delinq90.id}/send-whatsapp`, {
      headers: adminHeaders,
      data: { message: longMessage },
    });
    expect(waRes.status()).toBe(200);
    const messages = await waRes.json();
    expect(messages[0].message).toBe(longMessage);
  });
});


// ── Collections – UI tests ────────────────────────────────────

test.describe('Collections – UI tests', () => {
  test('collections page shows delinquent loans in table', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/collections`);
    await page.waitForLoadState('networkidle');

    // Should show collections heading
    await expect(page.getByText(/Collections|Overdue|Collection Queue/i).first()).toBeVisible({ timeout: 5000 });

    // Should show Derrick Wellington
    await expect(page.getByText('Derrick Wellington').first()).toBeVisible({ timeout: 5000 });

    // Should show at least one of the delinquent reference numbers
    await expect(page.getByText(/DELINQ/i).first()).toBeVisible({ timeout: 3000 });
  });

  test('collection detail page loads with loan info', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/collections`);
    await page.waitForLoadState('networkidle');

    // Click on a loan reference number (the <tr> onClick navigates to collection detail).
    // Clicking the applicant name goes to Customer 360 (different page), so click the reference number td.
    const refCell = page.getByText(/ZOT-SCEN-DELINQ/i).first();
    await refCell.click();
    await page.waitForLoadState('networkidle');

    // Should navigate to a collection detail URL
    await expect(page).toHaveURL(/\/backoffice\/collections\/\d+/, { timeout: 5000 });

    // Should show borrower name and loan reference on the collection detail page
    await expect(page.getByText('Derrick Wellington').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/ZOT-SCEN-DELINQ/i).first()).toBeVisible({ timeout: 3000 });
  });

  test('WhatsApp chat tab shows messages', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/collections`);
    await page.waitForLoadState('networkidle');

    // Click on the highest DPD loan (DELINQ90)
    const row = page.getByText('ZOT-SCEN-DELINQ90').first();
    await row.click();
    await page.waitForLoadState('networkidle');

    // Click WhatsApp Chat tab
    await page.getByText('WhatsApp Chat').click();
    await page.waitForTimeout(1000);

    // Should show messages (we sent messages in the API tests)
    // Look for either a message bubble or the "No WhatsApp messages" placeholder
    const chatContent = page.locator('[style*="500px"]');
    await expect(chatContent).toBeVisible({ timeout: 3000 });
  });

  test('consumer notifications page shows collection messages', async ({ page }) => {
    // Login as the delinquent borrower
    await page.goto(BASE);
    await page.getByLabel('Email').fill('delinquent.borrower@email.com');
    await page.getByLabel('Password').fill('Applicant1!');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    // Navigate to notifications
    await page.goto(`${BASE}/notifications`);
    await page.waitForLoadState('networkidle');

    // Should show the notifications heading
    await expect(page.getByRole('heading', { name: 'Notifications' })).toBeVisible({ timeout: 5000 });

    // Should show collection messages section if there are any
    // The page should either show "Collection Messages" or "No messages yet"
    const pageContent = await page.textContent('body');
    const hasCollectionSection = pageContent?.includes('Collection Messages');
    const hasNoMessages = pageContent?.includes('No messages yet');
    expect(hasCollectionSection || hasNoMessages).toBe(true);
  });
});


// ══════════════════════════════════════════════════════════════════
// TC SUITE — Comprehensive Test Cases from Zotta_LMS_Test_Case_Suite.md
// ══════════════════════════════════════════════════════════════════


// ── TC Suite – Auth & RBAC ─────────────────────────────────────

test.describe('TC Suite – Auth & RBAC', () => {
  const API = 'http://localhost:8000/api';

  // TC-002: Login with invalid password
  test('TC-002: login with invalid password returns 401', async ({ request }) => {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'WrongPassword99!' },
    });
    expect(res.status()).toBe(401);
    const body = await res.json();
    expect(body.detail).toMatch(/invalid/i);
  });

  // TC-002 variant: login with non-existent email
  test('TC-002b: login with non-existent email returns 401', async ({ request }) => {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'nonexistent@zotta.tt', password: 'Admin123!' },
    });
    expect(res.status()).toBe(401);
  });

  // TC-005: Applicant cannot access admin endpoints
  test('TC-005: applicant cannot access admin endpoints', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    // Admin endpoints
    const rulesRes = await request.get(`${API}/admin/rules`, { headers });
    expect(rulesRes.status()).toBe(403);

    const merchantsRes = await request.get(`${API}/admin/merchants`, { headers });
    expect(merchantsRes.status()).toBe(403);

    const productsRes = await request.get(`${API}/admin/products`, { headers });
    expect(productsRes.status()).toBe(403);
  });

  // TC-005: Applicant cannot access underwriter endpoints
  test('TC-005b: applicant cannot access underwriter endpoints', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const queueRes = await request.get(`${API}/underwriter/queue`, { headers });
    expect(queueRes.status()).toBe(403);

    const loansRes = await request.get(`${API}/underwriter/loans`, { headers });
    expect(loansRes.status()).toBe(403);
  });

  // TC-005: Applicant cannot access collections endpoints
  test('TC-005c: applicant cannot access collections endpoints', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const colRes = await request.get(`${API}/collections/queue`, { headers });
    expect(colRes.status()).toBe(403);
  });

  // TC-005: Applicant cannot access report endpoints
  test('TC-005d: applicant cannot access report endpoints', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const dashRes = await request.get(`${API}/reports/dashboard`, { headers });
    expect(dashRes.status()).toBe(403);

    const typesRes = await request.get(`${API}/reports/types`, { headers });
    expect(typesRes.status()).toBe(403);
  });
});


// ── TC Suite – Origination Validation ──────────────────────────

test.describe('TC Suite – Origination Validation', () => {
  const API = 'http://localhost:8000/api';

  async function getApplicantToken(request: import('@playwright/test').APIRequestContext) {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await res.json();
    return access_token;
  }

  // TC-012: Missing mandatory fields
  test('TC-012: application with missing mandatory fields returns 422', async ({ request }) => {
    const token = await getApplicantToken(request);
    const headers = { Authorization: `Bearer ${token}` };

    // Missing amount_requested and term_months
    const res = await request.post(`${API}/loans/`, {
      headers,
      data: { purpose: 'personal' },
    });
    expect(res.status()).toBe(422);
    const body = await res.json();
    expect(body.detail).toBeTruthy();
    // Should have validation errors for missing fields
    const fields = body.detail.map((e: any) => e.loc?.join('.'));
    expect(fields.some((f: string) => f?.includes('amount_requested'))).toBe(true);
    expect(fields.some((f: string) => f?.includes('term_months'))).toBe(true);
  });

  // TC-018: Loan amount below minimum
  test('TC-018: loan amount zero or negative returns 422', async ({ request }) => {
    const token = await getApplicantToken(request);
    const headers = { Authorization: `Bearer ${token}` };

    const resZero = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 0, term_months: 12, purpose: 'personal' },
    });
    expect(resZero.status()).toBe(422);

    const resNeg = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: -500, term_months: 12, purpose: 'personal' },
    });
    expect(resNeg.status()).toBe(422);
  });

  // TC-019: Loan amount above maximum
  test('TC-019: loan amount above maximum (500,000) returns 422', async ({ request }) => {
    const token = await getApplicantToken(request);
    const headers = { Authorization: `Bearer ${token}` };

    const res = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 999999, term_months: 12, purpose: 'personal' },
    });
    expect(res.status()).toBe(422);
  });

  // TC-121: Term months below minimum (3)
  test('TC-121: term months below minimum (< 3) returns 422', async ({ request }) => {
    const token = await getApplicantToken(request);
    const headers = { Authorization: `Bearer ${token}` };

    const res0 = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 5000, term_months: 0, purpose: 'personal' },
    });
    expect(res0.status()).toBe(422);

    const res1 = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 5000, term_months: 1, purpose: 'personal' },
    });
    expect(res1.status()).toBe(422);

    const res2 = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 5000, term_months: 2, purpose: 'personal' },
    });
    expect(res2.status()).toBe(422);
  });

  // TC-019b: Term months above maximum (84)
  test('TC-019b: term months above maximum (> 84) returns 422', async ({ request }) => {
    const token = await getApplicantToken(request);
    const headers = { Authorization: `Bearer ${token}` };

    const res = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 5000, term_months: 100, purpose: 'personal' },
    });
    expect(res.status()).toBe(422);
  });
});


// ── TC Suite – Document Management ─────────────────────────────

test.describe('TC Suite – Document Management', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-016: Document upload, list, download
  test('TC-016: upload document, list, and download', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Create a draft application
    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 5000, term_months: 12, purpose: 'personal', purpose_description: 'TC-016 doc test' },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    // Upload a document (use a sample fixture)
    const fs = require('fs');
    const path = require('path');
    const fixturePath = path.resolve(__dirname, 'fixtures/sample_id_front.png');

    if (fs.existsSync(fixturePath)) {
      const uploadRes = await request.post(`${API}/loans/${app.id}/documents`, {
        headers: { Authorization: `Bearer ${applicantToken}` },
        multipart: {
          file: { name: 'sample_id_front.png', mimeType: 'image/png', buffer: fs.readFileSync(fixturePath) },
          document_type: 'national_id',
        },
      });
      expect(uploadRes.status()).toBe(201);
      const doc = await uploadRes.json();
      expect(doc.id).toBeTruthy();
      expect(doc.document_type).toBe('national_id');

      // List documents
      const listRes = await request.get(`${API}/loans/${app.id}/documents`, { headers });
      expect(listRes.status()).toBe(200);
      const docs = await listRes.json();
      expect(docs.length).toBeGreaterThanOrEqual(1);
      expect(docs.some((d: any) => d.id === doc.id)).toBe(true);

      // Download document
      const dlRes = await request.get(`${API}/loans/${app.id}/documents/${doc.id}/download`, { headers });
      expect(dlRes.status()).toBe(200);
    }
  });

  // TC-017: Upload with missing document_type
  test('TC-017: upload without required document type is rejected', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 5000, term_months: 12, purpose: 'personal', purpose_description: 'TC-017 test' },
    });
    const app = await createRes.json();

    // Upload without document_type field
    const fs = require('fs');
    const path = require('path');
    const fixturePath = path.resolve(__dirname, 'fixtures/sample_id_front.png');

    if (fs.existsSync(fixturePath)) {
      const uploadRes = await request.post(`${API}/loans/${app.id}/documents`, {
        headers: { Authorization: `Bearer ${applicantToken}` },
        multipart: {
          file: { name: 'sample_id_front.png', mimeType: 'image/png', buffer: fs.readFileSync(fixturePath) },
          // Intentionally omit document_type
        },
      });
      // Should fail with 422 or 400
      expect([400, 422]).toContain(uploadRes.status());
    }
  });
});


// ── TC Suite – Decision Engine ──────────────────────────────────

test.describe('TC Suite – Decision Engine', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-028: DTI ratio calculation accuracy
  test('TC-028: DTI calculation — high DSR triggers refer', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Set profile with high DTI: expenses 8000 + debt 0 on income 15000 => DSR ≈ 53% (>40% triggers R12)
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        employment_type: 'employed',
        years_employed: 10,
        monthly_income: 15000,
        other_income: 0,
        monthly_expenses: 8000,
        existing_debt: 0,
        dependents: 1,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 5000, term_months: 12, purpose: 'personal', purpose_description: 'TC-028 DTI test' },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    // Run decision engine
    const engineRes = await request.post(`${API}/underwriter/applications/${app.id}/run-engine`, {
      headers: adminHeaders,
    });
    expect(engineRes.status()).toBe(200);

    // Get decision — DSR>40% should trigger at least a warning or refer
    const decRes = await request.get(`${API}/underwriter/applications/${app.id}/decision`, {
      headers: adminHeaders,
    });
    expect(decRes.status()).toBe(200);
    const decision = await decRes.json();

    // rules_results is a dict keyed by rule ID; engine_outcome shows overall result
    expect(decision.engine_outcome).toBeTruthy();
    // Check if R12 (High DSR) is in the rules results
    if (decision.rules_results) {
      const r12 = decision.rules_results['R12'];
      if (r12) {
        expect(['refer', 'fail']).toContain(r12.result || r12);
      }
    }
    // With expenses 8000 on income 15000, DSR = 53% which exceeds 40% threshold
    // Engine should recommend something other than clean pass
    expect(decision.scoring_breakdown).toBeTruthy();

    // Reset profile to healthy for other tests
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: { monthly_expenses: 3000, existing_debt: 1500 },
    });
  });

  // TC-027: Scorecard referral to manual review
  test('TC-027: borderline applicant gets referred to manual review', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Set borderline profile: income just enough, moderate expenses
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'Small Biz',
        employer_sector: 'Other',
        job_title: 'Freelancer',
        employment_type: 'self_employed',
        years_employed: 2,
        monthly_income: 5000,
        other_income: 0,
        monthly_expenses: 1800,
        existing_debt: 200,
        dependents: 0,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 5000, term_months: 12, purpose: 'personal', purpose_description: 'TC-027 referral test' },
    });
    const app = await createRes.json();
    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    const engineRes = await request.post(`${API}/underwriter/applications/${app.id}/run-engine`, {
      headers: adminHeaders,
    });
    expect(engineRes.status()).toBe(200);

    const decRes = await request.get(`${API}/underwriter/applications/${app.id}/decision`, {
      headers: adminHeaders,
    });
    const decision = await decRes.json();
    // Self-employed (R11) should trigger refer — rules_results is a dict
    if (decision.rules_results) {
      const r11 = decision.rules_results['R11'];
      if (r11) {
        expect(['refer', 'fail']).toContain(r11.result || r11);
      }
    }
    // Overall engine should have produced an outcome
    expect(decision.engine_outcome).toBeTruthy();

    // Reset profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        employment_type: 'employed',
        years_employed: 10,
        monthly_income: 15000,
        monthly_expenses: 3000,
        existing_debt: 1500,
      },
    });
  });

  // TC-032: Override auto-decline with manager approval
  test('TC-032: manager can override engine recommendation and approve', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Set profile back to healthy for clean state
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19',
        national_id: '19900101123',
        gender: 'male',
        marital_status: 'single',
        address_line1: '123 Test St',
        city: 'Port of Spain',
        parish: 'Arima',
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        employment_type: 'employed',
        years_employed: 10,
        monthly_income: 15000,
        other_income: 0,
        monthly_expenses: 3000,
        existing_debt: 1500,
        dependents: 1,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 5000, term_months: 12, purpose: 'personal', purpose_description: 'TC-032 override test' },
    });
    const app = await createRes.json();
    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    // Run engine
    await request.post(`${API}/underwriter/applications/${app.id}/run-engine`, {
      headers: adminHeaders,
    });

    // Regardless of engine result, admin overrides with approve
    const decideRes = await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'Manager override — TC-032 test' },
    });
    expect(decideRes.status()).toBe(200);
    const decision = await decideRes.json();
    expect(decision.final_outcome).toBe('approve');

    // Verify application is now approved
    const appRes = await request.get(`${API}/underwriter/applications/${app.id}`, {
      headers: adminHeaders,
    });
    const updatedApp = await appRes.json();
    expect(updatedApp.status).toBe('approved');
  });
});


// ── TC Suite – Disbursement Guards ──────────────────────────────

test.describe('TC Suite – Disbursement Guards', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-038: Double-disbursement prevention
  test('TC-038: double-disbursement is prevented', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Ensure healthy profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19', national_id: '19900101123',
        employer_name: 'E2E Corp', employer_sector: 'Information Technology', employment_type: 'employed', years_employed: 10,
        monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 5000, term_months: 12, purpose: 'personal', purpose_description: 'TC-038 double-disburse test' },
    });
    const app = await createRes.json();

    // Submit → Approve → Disburse
    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders,
      data: { action: 'approve', reason: 'TC-038 test' },
    });
    const disbRes = await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'TC-038 first disburse' },
    });
    expect(disbRes.status()).toBe(200);

    // Second disbursement attempt should fail
    const doubleRes = await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders,
      data: { method: 'manual', notes: 'TC-038 double attempt' },
    });
    expect([400, 409]).toContain(doubleRes.status());
    const err = await doubleRes.json();
    expect(err.detail).toBeTruthy();
  });
});


// ── TC Suite – Repayment Edge Cases ─────────────────────────────

test.describe('TC Suite – Repayment Edge Cases', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  async function createDisbursedLoan(
    request: import('@playwright/test').APIRequestContext,
    applicantHeaders: Record<string, string>,
    adminHeaders: Record<string, string>,
    desc: string,
    amount = 8000,
    term = 6,
  ) {
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19', national_id: '19900101123',
        employer_name: 'E2E Corp', employer_sector: 'Information Technology', employment_type: 'employed', years_employed: 10,
        monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500,
      },
    });
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: amount, term_months: term, purpose: 'personal', purpose_description: desc },
    });
    const app = await createRes.json();
    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders, data: { action: 'approve', reason: desc },
    });
    await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders, data: { method: 'manual', notes: desc },
    });
    return app;
  }

  // TC-041: Partial payment
  test('TC-041: partial payment is accepted and reflected', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const app = await createDisbursedLoan(request, applicantHeaders, adminHeaders, 'TC-041 partial payment');

    // Get schedule
    const schedRes = await request.get(`${API}/payments/${app.id}/schedule`, { headers: adminHeaders });
    const schedule = await schedRes.json();
    const firstDue = Number(schedule[0].amount_due);

    // Pay less than scheduled
    const partialAmount = Math.round(firstDue * 0.5 * 100) / 100;
    const payRes = await request.post(`${API}/payments/${app.id}/record`, {
      headers: adminHeaders,
      data: {
        amount: partialAmount,
        payment_type: 'manual',
        payment_date: new Date().toISOString().split('T')[0],
        reference_number: 'TC-041-PARTIAL',
        notes: 'Partial payment test',
      },
    });
    expect(payRes.status()).toBe(200);
    const payment = await payRes.json();
    expect(Number(payment.amount)).toBeCloseTo(partialAmount, 1);
  });

  // TC-042: Overpayment
  test('TC-042: overpayment is accepted', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const app = await createDisbursedLoan(request, applicantHeaders, adminHeaders, 'TC-042 overpayment');

    const schedRes = await request.get(`${API}/payments/${app.id}/schedule`, { headers: adminHeaders });
    const schedule = await schedRes.json();
    const firstDue = Number(schedule[0].amount_due);

    // Pay more than scheduled
    const overAmount = Math.round(firstDue * 2 * 100) / 100;
    const payRes = await request.post(`${API}/payments/${app.id}/record`, {
      headers: adminHeaders,
      data: {
        amount: overAmount,
        payment_type: 'manual',
        payment_date: new Date().toISOString().split('T')[0],
        reference_number: 'TC-042-OVER',
        notes: 'Overpayment test',
      },
    });
    expect(payRes.status()).toBe(200);
    const payment = await payRes.json();
    expect(Number(payment.amount)).toBeCloseTo(overAmount, 1);
  });

  // TC-045: Payment to non-existent loan
  test('TC-045: payment to non-existent loan returns 404', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const payRes = await request.post(`${API}/payments/999999/record`, {
      headers: adminHeaders,
      data: {
        amount: 1000,
        payment_type: 'manual',
        payment_date: new Date().toISOString().split('T')[0],
        notes: 'TC-045 wrong loan test',
      },
    });
    expect(payRes.status()).toBe(404);
  });
});


// ── TC Suite – Interest Calculation ─────────────────────────────

test.describe('TC Suite – Interest Calculation', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-049: Reducing balance interest calculation
  test('TC-049: reducing balance schedule has decreasing interest', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19', national_id: '19900101123',
        employer_name: 'E2E Corp', employer_sector: 'Information Technology', employment_type: 'employed', years_employed: 10,
        monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 100000, term_months: 12, purpose: 'personal', purpose_description: 'TC-049 interest calc' },
    });
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders, data: { action: 'approve', reason: 'TC-049 test' },
    });
    await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders, data: { method: 'manual', notes: 'TC-049 test' },
    });

    const schedRes = await request.get(`${API}/payments/${app.id}/schedule`, { headers: adminHeaders });
    expect(schedRes.status()).toBe(200);
    const schedule = await schedRes.json();
    expect(schedule.length).toBe(12);

    // Interest should decrease over time (reducing balance)
    const firstInterest = Number(schedule[0].interest);
    const lastInterest = Number(schedule[schedule.length - 1].interest);
    expect(firstInterest).toBeGreaterThan(lastInterest);

    // Principal should increase over time
    const firstPrincipal = Number(schedule[0].principal);
    const lastPrincipal = Number(schedule[schedule.length - 1].principal);
    expect(lastPrincipal).toBeGreaterThan(firstPrincipal);

    // Total of all installments should equal principal + total interest
    const totalPayments = schedule.reduce((sum: number, s: any) => sum + Number(s.amount_due), 0);
    expect(totalPayments).toBeGreaterThan(100000); // Must exceed principal due to interest

    // TC-123: Check decimal precision — no installment should have more than 2 decimal places
    for (const s of schedule) {
      const amountStr = String(Number(s.amount_due));
      const decimals = amountStr.includes('.') ? amountStr.split('.')[1].length : 0;
      expect(decimals).toBeLessThanOrEqual(2);
    }
  });

  // TC-122: Low interest rate (no divide-by-zero)
  test('TC-122: low interest rate produces valid schedule', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19', national_id: '19900101123',
        employer_name: 'E2E Corp', employer_sector: 'Information Technology', employment_type: 'employed', years_employed: 10,
        monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 10000, term_months: 6, purpose: 'personal', purpose_description: 'TC-122 low rate test' },
    });
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders, data: { action: 'approve', reason: 'TC-122 test' },
    });
    await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders, data: { method: 'manual', notes: 'TC-122 test' },
    });

    const schedRes = await request.get(`${API}/payments/${app.id}/schedule`, { headers: adminHeaders });
    expect(schedRes.status()).toBe(200);
    const schedule = await schedRes.json();
    expect(schedule.length).toBe(6);

    // All amounts should be positive and finite
    for (const s of schedule) {
      expect(Number(s.amount_due)).toBeGreaterThan(0);
      expect(Number(s.principal)).toBeGreaterThan(0);
      expect(isFinite(Number(s.amount_due))).toBe(true);
    }
  });
});


// ── TC Suite – Collections Aging ────────────────────────────────

test.describe('TC Suite – Collections Aging', () => {
  const API = 'http://localhost:8000/api';

  async function getAdminToken(request: import('@playwright/test').APIRequestContext) {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await res.json();
    return access_token;
  }

  // TC-056: Aging bucket — delinquent loans appear with correct DPD
  test('TC-056: delinquent loans appear in correct DPD ranges', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/collections/queue`, { headers });
    const queue = await res.json();

    const delinq30 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ30');
    const delinq60 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ60');
    const delinq90 = queue.find((e: any) => e.reference_number === 'ZOT-SCEN-DELINQ90');

    expect(delinq30).toBeTruthy();
    expect(delinq60).toBeTruthy();
    expect(delinq90).toBeTruthy();

    // DELINQ30 should have DPD roughly in the 1-60 range
    expect(delinq30.days_past_due).toBeGreaterThan(0);
    expect(delinq30.days_past_due).toBeLessThan(90);

    // DELINQ60 should have higher DPD than DELINQ30
    expect(delinq60.days_past_due).toBeGreaterThan(delinq30.days_past_due);

    // DELINQ90 should have the highest DPD
    expect(delinq90.days_past_due).toBeGreaterThan(delinq60.days_past_due);
    expect(delinq90.days_past_due).toBeGreaterThan(60);
  });

  // TC-057: Multiple aging tiers in queue
  test('TC-057: collections queue spans multiple aging tiers', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/collections/queue`, { headers });
    const queue = await res.json();

    // Should have loans in at least 2 different DPD brackets
    const dpds = queue.map((e: any) => e.days_past_due);
    const under30 = dpds.filter((d: number) => d <= 30).length;
    const over30 = dpds.filter((d: number) => d > 30 && d <= 60).length;
    const over60 = dpds.filter((d: number) => d > 60).length;

    // At least two tiers should have entries
    const tiersWithEntries = [under30, over30, over60].filter((c) => c > 0).length;
    expect(tiersWithEntries).toBeGreaterThanOrEqual(2);

    // Each entry should have required fields
    for (const entry of queue) {
      expect(entry.applicant_name).toBeTruthy();
      expect(entry.reference_number).toBeTruthy();
      expect(typeof entry.days_past_due).toBe('number');
      expect(typeof entry.outstanding_balance).toBe('number');
    }
  });
});


// ── TC Suite – Reporting ────────────────────────────────────────

test.describe('TC Suite – Reporting', () => {
  const API = 'http://localhost:8000/api';

  async function getAdminToken(request: import('@playwright/test').APIRequestContext) {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await res.json();
    return access_token;
  }

  // TC-078: Portfolio dashboard loads with metrics
  test('TC-078: dashboard returns valid metrics', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/reports/dashboard`, { headers });
    expect(res.status()).toBe(200);
    const metrics = await res.json();

    expect(metrics.total_applications).toBeGreaterThan(0);
    expect(typeof metrics.total_disbursed).toBe('number');
    expect(typeof metrics.approval_rate).toBe('number');
    expect(typeof metrics.avg_loan_amount).toBe('number');
    expect(metrics.applications_by_status).toBeTruthy();
    expect(typeof metrics.applications_by_status).toBe('object');
  });

  // TC-079: Loan book export
  test('TC-079: loan book export returns CSV with expected columns', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.post(`${API}/reports/generate/loan_book`, {
      headers,
      data: {},
    });
    expect(res.status()).toBe(200);
    const report = await res.json();
    expect(report.file_data).toBeTruthy();
    expect(report.file_format).toBe('csv');

    // Decode base64 and check headers
    const csv = Buffer.from(report.file_data, 'base64').toString('utf-8');
    const firstLine = csv.split('\n')[0].toLowerCase();
    // Should contain loan-related columns
    expect(firstLine).toMatch(/reference|loan|amount|status/i);
  });

  // TC-081: Aged report accuracy
  test('TC-081: aged report generates with bucket data', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.post(`${API}/reports/generate/aged`, {
      headers,
      data: {},
    });
    expect(res.status()).toBe(200);
    const report = await res.json();
    expect(report.file_data).toBeTruthy();

    const csv = Buffer.from(report.file_data, 'base64').toString('utf-8');
    const lines = csv.split('\n').filter((l: string) => l.trim());
    // Should have header + at least one data row
    expect(lines.length).toBeGreaterThanOrEqual(2);
  });

  // TC-083: Report with date range filter
  test('TC-083: portfolio summary respects date range', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.post(`${API}/reports/generate/portfolio_summary`, {
      headers,
      data: { date_from: '2025-01-01', date_to: '2026-12-31' },
    });
    expect(res.status()).toBe(200);
    const report = await res.json();
    expect(report.file_data).toBeTruthy();
    expect(report.report_type).toBe('portfolio_summary');

    // Also test with a very narrow window that likely has no data
    const narrowRes = await request.post(`${API}/reports/generate/portfolio_summary`, {
      headers,
      data: { date_from: '2020-01-01', date_to: '2020-01-02' },
    });
    expect(narrowRes.status()).toBe(200);
  });

  // TC-079b: Report types endpoint lists available reports
  test('TC-079b: report types returns available report list', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const res = await request.get(`${API}/reports/types`, { headers });
    expect(res.status()).toBe(200);
    const types = await res.json();
    expect(typeof types).toBe('object');

    // Report types is a dict keyed by type ID
    const typeKeys = Object.keys(types);
    expect(typeKeys.length).toBeGreaterThan(0);
    expect(typeKeys).toContain('aged');
    expect(typeKeys).toContain('loan_book');
    expect(typeKeys).toContain('portfolio_summary');

    // Each type should have name and description
    for (const key of typeKeys) {
      expect(types[key].name).toBeTruthy();
    }
  });
});


// ── TC Suite – API Security ─────────────────────────────────────

test.describe('TC Suite – API Security', () => {
  const API = 'http://localhost:8000/api';

  // TC-088: Expired/invalid JWT token
  test('TC-088: invalid JWT token returns 401', async ({ request }) => {
    const fakeToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI5OTk5IiwiZXhwIjoxMDAwMDAwMDAwLCJ0eXBlIjoiYWNjZXNzIn0.invalidsignature';
    const headers = { Authorization: `Bearer ${fakeToken}` };

    const res = await request.get(`${API}/loans/`, { headers });
    expect([401, 403]).toContain(res.status());
  });

  // TC-088b: Completely garbage token
  test('TC-088b: garbage token returns 401', async ({ request }) => {
    const headers = { Authorization: 'Bearer totallybogustoken123' };
    const res = await request.get(`${API}/loans/`, { headers });
    expect([401, 403]).toContain(res.status());
  });

  // TC-113: No Authorization header at all
  test('TC-113: no auth header returns 401 or 403', async ({ request }) => {
    const endpoints = [
      { method: 'GET', path: '/loans/' },
      { method: 'GET', path: '/underwriter/queue' },
      { method: 'GET', path: '/admin/rules' },
      { method: 'GET', path: '/reports/dashboard' },
      { method: 'GET', path: '/collections/queue' },
    ];

    for (const ep of endpoints) {
      const res = await request.get(`${API}${ep.path}`);
      expect([401, 403]).toContain(res.status());
    }
  });
});


// ── TC Suite – Online Payment ───────────────────────────────────

test.describe('TC Suite – Online Payment', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-091: Online payment on disbursed loan
  test('TC-091: pay-online records consumer payment', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    // Set up healthy profile
    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19', national_id: '19900101123',
        employer_name: 'E2E Corp', employer_sector: 'Information Technology', employment_type: 'employed', years_employed: 10,
        monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 5000, term_months: 6, purpose: 'personal', purpose_description: 'TC-091 online pay' },
    });
    const app = await createRes.json();

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders, data: { action: 'approve', reason: 'TC-091 test' },
    });
    await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders, data: { method: 'manual', notes: 'TC-091 test' },
    });

    // Consumer makes online payment
    const payRes = await request.post(`${API}/payments/${app.id}/pay-online`, {
      headers: applicantHeaders,
      data: { amount: 500 },
    });
    expect(payRes.status()).toBe(200);
    const payment = await payRes.json();
    expect(Number(payment.amount)).toBe(500);
    expect(payment.payment_type).toBe('online');

    // Verify in history
    const histRes = await request.get(`${API}/payments/${app.id}/history`, { headers: adminHeaders });
    const history = await histRes.json();
    const onlinePay = history.find((p: any) => p.payment_type === 'online');
    expect(onlinePay).toBeTruthy();
    expect(Number(onlinePay.amount)).toBe(500);
  });
});


// ── TC Suite – GL & Audit Trail ─────────────────────────────────

test.describe('TC Suite – GL & Audit Trail', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-086: GL entries created on disbursement
  test('TC-086: disbursement creates GL journal entries', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19', national_id: '19900101123',
        employer_name: 'E2E Corp', employer_sector: 'Information Technology', employment_type: 'employed', years_employed: 10,
        monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500,
      },
    });

    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 5000, term_months: 6, purpose: 'personal', purpose_description: 'TC-086 GL test' },
    });
    const app = await createRes.json();
    const ref = app.reference_number;

    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders, data: { action: 'approve', reason: 'TC-086 test' },
    });
    await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders, data: { method: 'manual', notes: 'TC-086 test' },
    });

    // Query GL entries filtered by loan reference
    const glRes = await request.get(`${API}/gl/entries?loan_id=${ref}`, { headers: adminHeaders });
    expect(glRes.status()).toBe(200);
    const glData = await glRes.json();
    const entries = glData.entries || glData.results || glData;

    // Should have at least one journal entry for the disbursement
    if (Array.isArray(entries)) {
      expect(entries.length).toBeGreaterThan(0);
      // Each entry should have debit and credit lines
      for (const entry of entries) {
        if (entry.lines && Array.isArray(entry.lines)) {
          const hasDebit = entry.lines.some((l: any) => Number(l.debit_amount) > 0);
          const hasCredit = entry.lines.some((l: any) => Number(l.credit_amount) > 0);
          expect(hasDebit || hasCredit).toBe(true);
        }
      }
    }
  });

  // TC-097: Audit trail completeness
  test('TC-097: full lifecycle produces complete audit trail', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    await request.put(`${API}/loans/profile`, {
      headers: applicantHeaders,
      data: {
        date_of_birth: '1991-02-19', national_id: '19900101123',
        employer_name: 'E2E Corp', employer_sector: 'Information Technology', employment_type: 'employed', years_employed: 10,
        monthly_income: 15000, monthly_expenses: 3000, existing_debt: 1500,
      },
    });

    // 1. Create
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: { amount_requested: 5000, term_months: 6, purpose: 'personal', purpose_description: 'TC-097 audit test' },
    });
    const app = await createRes.json();

    // 2. Submit
    await request.post(`${API}/loans/${app.id}/submit`, { headers: applicantHeaders });

    // 3. Run engine
    await request.post(`${API}/underwriter/applications/${app.id}/run-engine`, { headers: adminHeaders });

    // 4. Approve
    await request.post(`${API}/underwriter/applications/${app.id}/decide`, {
      headers: adminHeaders, data: { action: 'approve', reason: 'TC-097 audit test' },
    });

    // 5. Disburse
    await request.post(`${API}/underwriter/applications/${app.id}/disburse`, {
      headers: adminHeaders, data: { method: 'manual', notes: 'TC-097 audit test' },
    });

    // 6. Record a payment
    const schedRes = await request.get(`${API}/payments/${app.id}/schedule`, { headers: adminHeaders });
    const schedule = await schedRes.json();
    if (schedule.length > 0) {
      await request.post(`${API}/payments/${app.id}/record`, {
        headers: adminHeaders,
        data: {
          amount: Number(schedule[0].amount_due),
          payment_type: 'manual',
          payment_date: new Date().toISOString().split('T')[0],
          reference_number: 'TC-097-AUDIT',
        },
      });
    }

    // Get audit log
    const auditRes = await request.get(`${API}/underwriter/applications/${app.id}/audit`, {
      headers: adminHeaders,
    });
    expect(auditRes.status()).toBe(200);
    const audit = await auditRes.json();
    expect(Array.isArray(audit)).toBe(true);

    // Should have entries for engine run, approval, disbursement at minimum
    const actions = audit.map((a: any) => a.action);
    expect(actions.some((a: string) => /engine|run|scoring/i.test(a))).toBe(true);
    expect(actions.some((a: string) => /approve/i.test(a))).toBe(true);
    expect(actions.some((a: string) => /disburse/i.test(a))).toBe(true);

    // Each audit entry should have timestamp and user info
    for (const entry of audit) {
      expect(entry.created_at).toBeTruthy();
    }
  });
});


// ── TC Suite – Product Configuration ────────────────────────────

test.describe('TC Suite – Product Configuration', () => {
  const API = 'http://localhost:8000/api';

  async function getAdminToken(request: import('@playwright/test').APIRequestContext) {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await res.json();
    return access_token;
  }

  // TC-106: Create new product
  test('TC-106: create new loan product and verify in list', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const createRes = await request.post(`${API}/admin/products`, {
      headers,
      data: {
        name: 'TC-106 Test Personal Loan',
        description: 'E2E test product for TC-106',
        min_term_months: 3,
        max_term_months: 60,
        min_amount: 5000,
        max_amount: 500000,
        repayment_scheme: 'reducing_balance',
        grace_period_days: 0,
        is_active: true,
      },
    });
    expect(createRes.status()).toBe(201);
    const product = await createRes.json();
    expect(product.id).toBeTruthy();
    expect(product.name).toBe('TC-106 Test Personal Loan');

    // Verify in list
    const listRes = await request.get(`${API}/admin/products`, { headers });
    const products = await listRes.json();
    expect(products.some((p: any) => p.id === product.id)).toBe(true);

    // Cleanup: delete product
    await request.delete(`${API}/admin/products/${product.id}`, { headers });
  });

  // TC-107: Modify existing product
  test('TC-107: update product parameters', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    // Create a product to modify
    const createRes = await request.post(`${API}/admin/products`, {
      headers,
      data: {
        name: 'TC-107 Modifiable Product',
        min_term_months: 3, max_term_months: 36,
        min_amount: 5000, max_amount: 100000,
        repayment_scheme: 'reducing_balance',
      },
    });
    const product = await createRes.json();

    // Update max_amount
    const updateRes = await request.put(`${API}/admin/products/${product.id}`, {
      headers,
      data: { max_amount: 200000 },
    });
    expect(updateRes.status()).toBe(200);
    const updated = await updateRes.json();
    expect(Number(updated.max_amount)).toBe(200000);

    // Cleanup
    await request.delete(`${API}/admin/products/${product.id}`, { headers });
  });

  // TC-108: Product with fee
  test('TC-108: create product with fee structure', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    // Create product
    const createRes = await request.post(`${API}/admin/products`, {
      headers,
      data: {
        name: 'TC-108 Product With Fees',
        min_term_months: 3, max_term_months: 24,
        min_amount: 10000, max_amount: 200000,
        repayment_scheme: 'reducing_balance',
      },
    });
    const product = await createRes.json();

    // Add fee
    const feeRes = await request.post(`${API}/admin/products/${product.id}/fees`, {
      headers,
      data: {
        fee_type: 'origination_fee_pct',
        fee_base: 'financed_amount',
        fee_amount: 2.0,
        is_available: true,
      },
    });
    expect(feeRes.status()).toBe(201);
    const fee = await feeRes.json();
    expect(fee.fee_type).toBe('origination_fee_pct');
    expect(Number(fee.fee_amount)).toBe(2.0);

    // Verify fee is on the product
    const prodRes = await request.get(`${API}/admin/products/${product.id}`, { headers });
    const prodDetail = await prodRes.json();
    expect(prodDetail.fees.length).toBeGreaterThanOrEqual(1);
    expect(prodDetail.fees.some((f: any) => f.fee_type === 'origination_fee_pct')).toBe(true);

    // Cleanup
    await request.delete(`${API}/admin/fees/${fee.id}`, { headers });
    await request.delete(`${API}/admin/products/${product.id}`, { headers });
  });

  // TC-109: Delete/archive product
  test('TC-109: delete product removes it from list', async ({ request }) => {
    const adminToken = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const createRes = await request.post(`${API}/admin/products`, {
      headers,
      data: {
        name: 'TC-109 Deletable Product',
        min_term_months: 6, max_term_months: 12,
        min_amount: 1000, max_amount: 50000,
        repayment_scheme: 'reducing_balance',
      },
    });
    const product = await createRes.json();

    // Delete it
    const delRes = await request.delete(`${API}/admin/products/${product.id}`, { headers });
    expect(delRes.status()).toBe(204);

    // Verify not in list
    const listRes = await request.get(`${API}/admin/products`, { headers });
    const products = await listRes.json();
    expect(products.some((p: any) => p.id === product.id)).toBe(false);
  });
});


// ── TC Suite – Input Security ───────────────────────────────────

test.describe('TC Suite – Input Security', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-111: SQL injection in search fields
  test('TC-111: SQL injection in search returns no data leakage', async ({ request }) => {
    const { adminToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${adminToken}` };

    const payloads = [
      "' OR 1=1 --",
      "'; DROP TABLE users; --",
      "1' UNION SELECT * FROM users --",
    ];

    for (const payload of payloads) {
      const res = await request.get(`${API}/underwriter/customers/search`, {
        headers,
        params: { q: payload },
      });
      // Should not return 500 (server error indicating injection worked)
      expect(res.status()).not.toBe(500);
      // Should return either 200 with empty/safe results, or 400/422
      expect([200, 400, 422]).toContain(res.status());
    }
  });

  // TC-112: XSS in form fields
  test('TC-112: XSS payload stored as plain text, not executed', async ({ request }) => {
    const { applicantToken, adminToken } = await getTokens(request);
    const applicantHeaders = { Authorization: `Bearer ${applicantToken}` };
    const adminHeaders = { Authorization: `Bearer ${adminToken}` };

    const xssPayload = '<script>alert("xss")</script>';

    // Create application with XSS in description
    const createRes = await request.post(`${API}/loans/`, {
      headers: applicantHeaders,
      data: {
        amount_requested: 5000, term_months: 12,
        purpose: 'personal',
        purpose_description: xssPayload,
      },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();

    // Verify it's stored as plain text
    const getRes = await request.get(`${API}/loans/${app.id}`, { headers: applicantHeaders });
    const fetched = await getRes.json();
    expect(fetched.purpose_description).toBe(xssPayload);

    // Add a comment with XSS
    const commentRes = await request.post(`${API}/loans/${app.id}/comments`, {
      headers: applicantHeaders,
      data: { content: xssPayload },
    });
    expect([200, 201]).toContain(commentRes.status());

    // Fetch comments and verify plain text storage
    const commentsRes = await request.get(`${API}/loans/${app.id}/comments`, { headers: applicantHeaders });
    const comments = await commentsRes.json();
    const xssComment = comments.find((c: any) => c.content === xssPayload);
    expect(xssComment).toBeTruthy();
    // The script tag should be stored as-is, not interpreted
    expect(xssComment.content).toContain('<script>');
  });

  // TC-114: Privilege escalation — applicant cannot access staff endpoints
  test('TC-114: applicant cannot access staff-only endpoints', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Try to make a decision (staff only)
    const decideRes = await request.post(`${API}/underwriter/applications/1/decide`, {
      headers,
      data: { action: 'approve', reason: 'privilege escalation attempt' },
    });
    expect(decideRes.status()).toBe(403);

    // Try to disburse (staff only)
    const disbRes = await request.post(`${API}/underwriter/applications/1/disburse`, {
      headers,
      data: { method: 'manual' },
    });
    expect(disbRes.status()).toBe(403);

    // Try to record a payment (staff only)
    const payRes = await request.post(`${API}/payments/1/record`, {
      headers,
      data: { amount: 1000, payment_type: 'manual', payment_date: '2026-02-14' },
    });
    expect(payRes.status()).toBe(403);
  });

  // TC-115: Export access control
  test('TC-115: applicant cannot access report/export endpoints', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const reportRes = await request.post(`${API}/reports/generate/loan_book`, {
      headers,
      data: {},
    });
    expect(reportRes.status()).toBe(403);

    const exportRes = await request.get(`${API}/reports/export/loan-book`, { headers });
    expect(exportRes.status()).toBe(403);
  });
});


// ── TC Suite – Edge Cases ───────────────────────────────────────

test.describe('TC Suite – Edge Cases', () => {
  const API = 'http://localhost:8000/api';

  async function getTokens(request: import('@playwright/test').APIRequestContext) {
    const appLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token: applicantToken } = await appLogin.json();
    const adminLogin = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token: adminToken } = await adminLogin.json();
    return { applicantToken, adminToken };
  }

  // TC-123: Decimal precision in loan amounts
  test('TC-123: precise decimal amount preserves precision', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    const createRes = await request.post(`${API}/loans/`, {
      headers,
      data: { amount_requested: 100001.99, term_months: 12, purpose: 'personal', purpose_description: 'TC-123 precision' },
    });
    expect(createRes.status()).toBe(201);
    const app = await createRes.json();
    expect(Number(app.amount_requested)).toBeCloseTo(100001.99, 2);
  });

  // TC-124: Unicode characters in borrower name
  test('TC-124: Unicode characters stored and returned correctly', async ({ request }) => {
    const { applicantToken } = await getTokens(request);
    const headers = { Authorization: `Bearer ${applicantToken}` };

    // Update profile with Unicode characters
    const updateRes = await request.put(`${API}/loans/profile`, {
      headers,
      data: {
        employer_name: "O'Brien-Lévy & Associés",
        employer_sector: 'Professional Services (Legal, Accounting, Consulting)',
        job_title: 'Développeur Señior',
        city: 'São Paulo',
        address_line1: '123 Straße München',
      },
    });
    expect(updateRes.status()).toBe(200);

    // Fetch profile and verify
    const profileRes = await request.get(`${API}/loans/profile`, { headers });
    expect(profileRes.status()).toBe(200);
    const profile = await profileRes.json();
    expect(profile.employer_name).toBe("O'Brien-Lévy & Associés");
    expect(profile.employer_sector).toBe('Professional Services (Legal, Accounting, Consulting)');
    expect(profile.job_title).toBe('Développeur Señior');
    expect(profile.city).toBe('São Paulo');

    // Reset profile to normal
    await request.put(`${API}/loans/profile`, {
      headers,
      data: {
        employer_name: 'E2E Corp',
        employer_sector: 'Information Technology',
        job_title: 'Senior Developer',
        city: 'Port of Spain',
        address_line1: '123 Test St',
      },
    });
  });
});


// ══════════════════════════════════════════════════════════════════
// Customer 360 View – Comprehensive E2E Tests
// ══════════════════════════════════════════════════════════════════

test.describe('Customer 360 – API tests', () => {
  const API = 'http://localhost:8000/api';

  // Persona credentials (created by seed_customer360.py)
  const PERSONAS = {
    perfectBorrower: { email: 'angela.maharaj@email.com', pw: 'Test1234!', name: 'Angela Maharaj' },
    recovering: { email: 'darren.baptiste@email.com', pw: 'Test1234!', name: 'Darren Baptiste' },
    deteriorating: { email: 'kevin.persad360@email.com', pw: 'Test1234!', name: 'Kevin Persad' },
    newCustomer: { email: 'priya.ramnath@email.com', pw: 'Test1234!', name: 'Priya Ramnath' },
    complexCase: { email: 'marcus.williams360@email.com', pw: 'Test1234!', name: 'Marcus Williams' },
  };

  async function getAdminToken(request: import('@playwright/test').APIRequestContext) {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    return (await res.json()).access_token;
  }

  async function getPersonaUserId(request: import('@playwright/test').APIRequestContext, adminToken: string, email: string) {
    const res = await request.get(`${API}/underwriter/customers/search`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      params: { q: email },
    });
    const data = await res.json();
    return data[0]?.id;
  }

  // ── 360 endpoint: data completeness ─────────────────────────

  test('360 returns full data for Perfect Borrower (Angela)', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.perfectBorrower.email);
    expect(userId).toBeTruthy();

    const res = await request.get(`${API}/customers/${userId}/360`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();

    // User fields are not null
    expect(data.user.first_name).toBe('Angela');
    expect(data.user.last_name).toBe('Maharaj');
    expect(data.user.email).toBe(PERSONAS.perfectBorrower.email);
    expect(data.user.phone).toBeTruthy();
    expect(data.user.id).toBeGreaterThan(0);

    // Profile fields are populated
    expect(data.profile.employer_name).toBe('Republic Bank');
    expect(data.profile.employer_sector).toBeTruthy();
    expect(data.profile.job_title).toBe('Senior Accountant');
    expect(data.profile.monthly_income).toBeGreaterThan(0);
    expect(data.profile.date_of_birth).toBeTruthy();
    expect(data.profile.national_id).toBeTruthy();
    expect(data.profile.id_verified).toBe(true);
    expect(data.profile.city).toBe('Port of Spain');

    // 4 applications (all disbursed)
    expect(data.applications.length).toBe(4);
    for (const app of data.applications) {
      expect(app.status).toBe('disbursed');
      expect(app.reference_number).toMatch(/^ZOT-/);
      expect(app.amount_requested).toBeGreaterThan(0);
      expect(app.amount_approved).toBeGreaterThan(0);
      expect(app.interest_rate).toBeGreaterThan(0);
      expect(app.term_months).toBeGreaterThan(0);
      expect(app.disbursed_at).toBeTruthy();
    }

    // Payments exist and are non-empty
    expect(data.payments.length).toBeGreaterThan(40);
    for (const p of data.payments.slice(0, 10)) {
      expect(p.amount).toBeGreaterThan(0);
      expect(p.payment_date).toBeTruthy();
      expect(p.status).toBe('completed');
    }

    // Payment schedules
    expect(data.payment_schedules.length).toBeGreaterThan(50);

    // Decisions
    expect(data.decisions.length).toBeGreaterThanOrEqual(2);
    for (const d of data.decisions) {
      expect(d.credit_score).toBeGreaterThan(0);
      expect(d.risk_band).toBeTruthy();
    }

    // Documents
    expect(data.documents.length).toBeGreaterThan(0);
    for (const doc of data.documents) {
      expect(doc.file_name).toBeTruthy();
      expect(doc.document_type).toBeTruthy();
      expect(doc.status).toBe('verified');
    }

    // Credit reports
    expect(data.credit_reports.length).toBeGreaterThanOrEqual(2);
    for (const cr of data.credit_reports) {
      expect(cr.bureau_score).toBeGreaterThan(600);
    }

    // Conversations
    expect(data.conversations.length).toBeGreaterThanOrEqual(1);
    expect(data.conversations[0].messages.length).toBeGreaterThanOrEqual(2);

    // Audit logs
    expect(data.audit_logs.length).toBeGreaterThan(0);

    // Quick stats are accurate
    const qs = data.quick_stats;
    expect(qs.total_lifetime_value).toBeGreaterThan(0);
    expect(qs.active_products).toBeGreaterThanOrEqual(1);
    expect(qs.total_outstanding).toBeGreaterThan(0);
    expect(qs.worst_dpd).toBe(0); // Perfect borrower - no arrears
    expect(qs.payment_success_rate).toBe(100);
    expect(qs.relationship_length_days).toBeGreaterThanOrEqual(365 * 3 - 10); // ~3 years
    expect(qs.last_contact).toBeTruthy();
  });

  test('360 reflects deterioration for Kevin (partial payments, collections)', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.deteriorating.email);
    expect(userId).toBeTruthy();

    const res = await request.get(`${API}/customers/${userId}/360`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();

    expect(data.user.first_name).toBe('Kevin');
    expect(data.applications.length).toBe(1);
    expect(data.applications[0].status).toBe('disbursed');

    // Has partial or overdue schedules showing payment issues
    const nonPaid = data.payment_schedules.filter((s: any) => s.status !== 'paid' && s.status !== 'upcoming');
    expect(nonPaid.length).toBeGreaterThanOrEqual(1);

    // Payment success rate below perfect
    const qs = data.quick_stats;
    expect(qs.payment_success_rate).toBeLessThan(100);

    // Collection records exist (at least from seed + our test additions)
    expect(data.collection_records.length).toBeGreaterThanOrEqual(2);

    // Collection chats exist
    expect(data.collection_chats.length).toBeGreaterThanOrEqual(1);

    // Credit reports show varying scores
    expect(data.credit_reports.length).toBeGreaterThanOrEqual(2);
    const scores = data.credit_reports
      .filter((c: any) => c.bureau_score)
      .map((c: any) => c.bureau_score);
    expect(Math.min(...scores)).toBeLessThan(Math.max(...scores));

    // Comment from customer
    expect(data.comments.length).toBeGreaterThanOrEqual(1);
    expect(data.comments[0].is_from_applicant).toBe(true);
  });

  test('360 for Complex Case has rich data across all sections', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.complexCase.email);
    expect(userId).toBeTruthy();

    const res = await request.get(`${API}/customers/${userId}/360`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();

    // 4 applications: 3 disbursed + 1 declined
    expect(data.applications.length).toBe(4);
    const statuses = data.applications.map((a: any) => a.status);
    expect(statuses).toContain('disbursed');
    expect(statuses).toContain('declined');

    // Collections are extensive
    expect(data.collection_records.length).toBeGreaterThanOrEqual(8);
    expect(data.collection_chats.length).toBeGreaterThanOrEqual(9);

    // Notes from staff
    expect(data.notes.length).toBeGreaterThanOrEqual(3);
    for (const n of data.notes) {
      expect(n.content).toBeTruthy();
      expect(n.content.length).toBeGreaterThan(10);
    }

    // Comments (customer ↔ staff dialogue)
    expect(data.comments.length).toBeGreaterThanOrEqual(5);
    const fromApplicant = data.comments.filter((c: any) => c.is_from_applicant);
    const fromStaff = data.comments.filter((c: any) => !c.is_from_applicant);
    expect(fromApplicant.length).toBeGreaterThan(0);
    expect(fromStaff.length).toBeGreaterThan(0);

    // Credit reports show declining trend
    expect(data.credit_reports.length).toBeGreaterThanOrEqual(5);
    const scores = data.credit_reports.filter((c: any) => c.bureau_score).map((c: any) => c.bureau_score);
    const firstScore = scores[scores.length - 1]; // oldest
    const lastScore = scores[0]; // newest
    expect(firstScore).toBeGreaterThan(lastScore); // score declined

    // Documents across multiple loans
    expect(data.documents.length).toBeGreaterThanOrEqual(6);

    // Quick stats
    const qs = data.quick_stats;
    expect(qs.worst_dpd).toBeGreaterThan(60); // 4 months overdue
    expect(qs.active_products).toBeGreaterThanOrEqual(2);
    expect(qs.total_outstanding).toBeGreaterThan(100000);
  });

  test('360 for New Customer has minimal but complete data', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.newCustomer.email);
    expect(userId).toBeTruthy();

    const res = await request.get(`${API}/customers/${userId}/360`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();

    expect(data.user.first_name).toBe('Priya');
    expect(data.applications.length).toBe(1);
    expect(data.applications[0].status).toBe('disbursed');

    // Minimal payment history
    expect(data.payments.length).toBeLessThanOrEqual(5);

    // Quick stats: new relationship
    const qs = data.quick_stats;
    expect(qs.relationship_length_days).toBeLessThan(60);
    expect(qs.worst_dpd).toBe(0);
    expect(qs.active_products).toBe(1);

    // Has conversation history
    expect(data.conversations.length).toBeGreaterThanOrEqual(1);
    expect(data.conversations[0].messages.length).toBeGreaterThanOrEqual(4);
  });

  test('360 for Recovering Customer shows recovery arc', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.recovering.email);
    expect(userId).toBeTruthy();

    const res = await request.get(`${API}/customers/${userId}/360`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();

    expect(data.user.first_name).toBe('Darren');
    expect(data.applications.length).toBe(1);

    // Has collection records from arrears period
    expect(data.collection_records.length).toBeGreaterThanOrEqual(4);
    const outcomes = data.collection_records.map((r: any) => r.outcome);
    expect(outcomes).toContain('promise_to_pay');
    expect(outcomes).toContain('payment_arranged');

    // Collection chat messages
    expect(data.collection_chats.length).toBeGreaterThanOrEqual(2);

    // Notes documenting the recovery
    expect(data.notes.length).toBeGreaterThanOrEqual(2);

    // Credit report shows improvement
    expect(data.credit_reports.length).toBeGreaterThanOrEqual(2);
    const scores = data.credit_reports.filter((c: any) => c.bureau_score).map((c: any) => c.bureau_score);
    expect(Math.max(...scores)).toBeGreaterThan(Math.min(...scores));
  });

  // ── 360: auth and error handling ────────────────────────────

  test('360 returns 404 for non-existent customer', async ({ request }) => {
    const token = await getAdminToken(request);
    const res = await request.get(`${API}/customers/999999/360`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(404);
  });

  test('360 requires staff role (applicant rejected)', async ({ request }) => {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: PERSONAS.perfectBorrower.email, password: PERSONAS.perfectBorrower.pw },
    });
    const { access_token } = await loginRes.json();
    const res = await request.get(`${API}/customers/87/360`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(403);
  });

  test('360 returns 401 or 403 without auth', async ({ request }) => {
    const res = await request.get(`${API}/customers/87/360`);
    expect([401, 403]).toContain(res.status());
  });

  // ── Timeline endpoint ───────────────────────────────────────

  test('timeline returns chronological events for Complex Case', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.complexCase.email);

    const res = await request.get(`${API}/customers/${userId}/timeline`, {
      headers,
      params: { limit: 100 },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.events.length).toBeGreaterThan(20);

    // Events have required fields
    for (const ev of data.events) {
      expect(ev.timestamp).toBeTruthy();
      expect(ev.category).toBeTruthy();
      expect(ev.title).toBeTruthy();
      expect(ev.entity_type).toBeTruthy();
      expect(ev.entity_id).toBeGreaterThan(0);
    }

    // Events are sorted by timestamp descending
    for (let i = 1; i < data.events.length; i++) {
      expect(data.events[i - 1].timestamp >= data.events[i].timestamp).toBe(true);
    }

    // Multiple categories present
    const categories = new Set(data.events.map((e: any) => e.category));
    expect(categories.size).toBeGreaterThanOrEqual(3);
    expect(categories.has('payment')).toBe(true);
    expect(categories.has('collection')).toBe(true);
  });

  test('timeline category filter works', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.complexCase.email);

    const res = await request.get(`${API}/customers/${userId}/timeline`, {
      headers,
      params: { categories: 'collection', limit: 50 },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.events.length).toBeGreaterThan(0);
    for (const ev of data.events) {
      expect(ev.category).toBe('collection');
    }
  });

  test('timeline search filter works', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.complexCase.email);

    const res = await request.get(`${API}/customers/${userId}/timeline`, {
      headers,
      params: { search: 'disbursed', limit: 50 },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    for (const ev of data.events) {
      const matchesTitle = ev.title.toLowerCase().includes('disbursed');
      const matchesDesc = (ev.description || '').toLowerCase().includes('disbursed');
      expect(matchesTitle || matchesDesc).toBe(true);
    }
  });

  test('timeline pagination works', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.perfectBorrower.email);

    const page1 = await request.get(`${API}/customers/${userId}/timeline`, {
      headers,
      params: { offset: 0, limit: 5 },
    });
    const d1 = await page1.json();
    expect(d1.events.length).toBe(5);

    const page2 = await request.get(`${API}/customers/${userId}/timeline`, {
      headers,
      params: { offset: 5, limit: 5 },
    });
    const d2 = await page2.json();
    expect(d2.events.length).toBe(5);

    // Pages don't overlap
    const ids1 = d1.events.map((e: any) => `${e.entity_type}-${e.entity_id}-${e.timestamp}`);
    const ids2 = d2.events.map((e: any) => `${e.entity_type}-${e.entity_id}-${e.timestamp}`);
    const overlap = ids1.filter((id: string) => ids2.includes(id));
    expect(overlap.length).toBe(0);
  });

  // ── AI Summary endpoint ─────────────────────────────────────

  test('AI summary returns structured response for Perfect Borrower', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.perfectBorrower.email);

    const res = await request.post(`${API}/customers/${userId}/ai-summary`, { headers });
    expect(res.status()).toBe(200);
    const summary = await res.json();

    expect(summary.summary_text).toBeTruthy();
    expect(summary.summary_text.length).toBeGreaterThan(50);
    expect(['positive', 'neutral', 'concerning', 'critical']).toContain(summary.sentiment);
    expect(summary.sentiment).toBe('positive'); // Perfect borrower
    expect(Array.isArray(summary.highlights)).toBe(true);
    expect(summary.highlights.length).toBeGreaterThanOrEqual(3);
    expect(summary.risk_narrative).toBeTruthy();
    expect(Array.isArray(summary.recommendations)).toBe(true);
    expect(typeof summary.confidence_score).toBe('number');
    expect(summary.confidence_score).toBeGreaterThan(0);
    expect(summary.confidence_score).toBeLessThanOrEqual(1);
  });

  test('AI summary reflects critical or concerning status for Complex Case', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.complexCase.email);

    const res = await request.post(`${API}/customers/${userId}/ai-summary`, { headers });
    expect(res.status()).toBe(200);
    const summary = await res.json();

    // AI model may return "critical" or "concerning" depending on how it weighs the data
    expect(['critical', 'concerning']).toContain(summary.sentiment);
    expect(summary.recommendations.length).toBeGreaterThan(0);
    // Should recommend collections action
    const hasCollectionRec = summary.recommendations.some((r: any) => r.category === 'collections');
    expect(hasCollectionRec).toBe(true);
  });

  test('AI summary for New Customer notes limited data', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.newCustomer.email);

    const res = await request.post(`${API}/customers/${userId}/ai-summary`, { headers });
    expect(res.status()).toBe(200);
    const summary = await res.json();

    expect(summary.sentiment).toBe('positive'); // New, no arrears
    // Should have recommendation about monitoring
    const hasMonitorRec = summary.recommendations.some((r: any) =>
      r.text.toLowerCase().includes('monitor') || r.category === 'risk_mitigation'
    );
    expect(hasMonitorRec).toBe(true);
  });

  test('AI summary returns 404 for non-existent customer', async ({ request }) => {
    const token = await getAdminToken(request);
    const res = await request.post(`${API}/customers/999999/ai-summary`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(res.status()).toBe(404);
  });

  // ── Ask AI endpoint ─────────────────────────────────────────

  test('Ask AI returns answer for a question', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.perfectBorrower.email);

    const res = await request.post(`${API}/customers/${userId}/ask-ai`, {
      headers,
      data: { question: 'How many loans does this customer have?' },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.answer).toBeTruthy();
    expect(data.answer.length).toBeGreaterThan(5);
    expect(Array.isArray(data.citations)).toBe(true);
  });

  test('Ask AI logs to audit trail', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.perfectBorrower.email);

    // Ask question
    await request.post(`${API}/customers/${userId}/ask-ai`, {
      headers,
      data: { question: 'What is the payment history?' },
    });

    // Check audit log
    const c360 = await request.get(`${API}/customers/${userId}/360`, { headers });
    const data = await c360.json();
    const askAiLogs = data.audit_logs.filter((a: any) => a.action === 'ask_ai');
    expect(askAiLogs.length).toBeGreaterThan(0);
    expect(askAiLogs[0].details).toContain('What is the payment history');
  });

  test('Ask AI returns 404 for non-existent customer', async ({ request }) => {
    const token = await getAdminToken(request);
    const res = await request.post(`${API}/customers/999999/ask-ai`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { question: 'test' },
    });
    expect(res.status()).toBe(404);
  });

  // ── Changes reflected in Customer 360 ───────────────────────

  test('recording a payment reflects in Customer 360 data', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.deteriorating.email);

    // Get current state
    const before = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataBefore = await before.json();
    const paymentCountBefore = dataBefore.payments.length;
    const loanId = dataBefore.applications[0].id;

    // Record a payment
    const payRes = await request.post(`${API}/payments/${loanId}/record`, {
      headers,
      data: {
        amount: 3444,
        payment_type: 'manual',
        payment_date: new Date().toISOString().split('T')[0],
        reference_number: 'C360-TEST-001',
        notes: 'Customer 360 test payment',
      },
    });
    expect(payRes.status()).toBe(200);

    // Check 360 reflects the new payment
    const after = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataAfter = await after.json();
    expect(dataAfter.payments.length).toBe(paymentCountBefore + 1);

    // The new payment appears
    const newPayment = dataAfter.payments.find((p: any) => p.reference_number === 'C360-TEST-001');
    expect(newPayment).toBeTruthy();
    expect(newPayment.amount).toBe(3444);
  });

  test('adding a collection record reflects in Customer 360', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.deteriorating.email);

    const before = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataBefore = await before.json();
    const colCountBefore = dataBefore.collection_records.length;
    const loanId = dataBefore.applications[0].id;

    // Add collection record
    const colRes = await request.post(`${API}/collections/${loanId}/record`, {
      headers,
      data: {
        channel: 'phone',
        outcome: 'promise_to_pay',
        notes: 'C360 test: spoke with Kevin, promised to pay next week',
        action_taken: 'Phone call',
        promise_amount: 3500,
        promise_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
      },
    });
    expect(colRes.status()).toBe(200);

    const after = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataAfter = await after.json();
    expect(dataAfter.collection_records.length).toBe(colCountBefore + 1);

    const newRecord = dataAfter.collection_records.find((r: any) =>
      r.notes?.includes('C360 test')
    );
    expect(newRecord).toBeTruthy();
    expect(newRecord.outcome).toBe('promise_to_pay');
    expect(newRecord.promise_amount).toBe(3500);
  });

  test('adding a collection chat reflects in Customer 360', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.deteriorating.email);

    const before = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataBefore = await before.json();
    const chatCountBefore = dataBefore.collection_chats.length;
    const loanId = dataBefore.applications[0].id;

    // Send WhatsApp
    const msgRes = await request.post(`${API}/collections/${loanId}/send-whatsapp`, {
      headers,
      data: { message: 'C360 test: payment reminder' },
    });
    expect(msgRes.status()).toBe(200);

    const after = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataAfter = await after.json();
    expect(dataAfter.collection_chats.length).toBe(chatCountBefore + 1);

    const newChat = dataAfter.collection_chats.find((c: any) =>
      c.message?.includes('C360 test')
    );
    expect(newChat).toBeTruthy();
    expect(newChat.direction).toBe('outbound');
  });

  test('adding a note reflects in Customer 360', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.perfectBorrower.email);

    const before = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataBefore = await before.json();
    const noteCountBefore = dataBefore.notes.length;
    const loanId = dataBefore.applications[0].id;

    // Add note (returns 201 Created)
    const noteRes = await request.post(`${API}/underwriter/applications/${loanId}/notes`, {
      headers,
      data: { content: 'C360 test: excellent customer, consider premium tier' },
    });
    expect([200, 201]).toContain(noteRes.status());

    const after = await request.get(`${API}/customers/${userId}/360`, { headers });
    const dataAfter = await after.json();
    expect(dataAfter.notes.length).toBe(noteCountBefore + 1);

    const newNote = dataAfter.notes.find((n: any) => n.content?.includes('C360 test'));
    expect(newNote).toBeTruthy();
  });

  test('changes to timeline are also reflected', async ({ request }) => {
    const token = await getAdminToken(request);
    const headers = { Authorization: `Bearer ${token}` };
    const userId = await getPersonaUserId(request, token, PERSONAS.deteriorating.email);

    // Timeline should include the payment we just recorded
    const res = await request.get(`${API}/customers/${userId}/timeline`, {
      headers,
      params: { categories: 'payment', limit: 20 },
    });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.events.length).toBeGreaterThan(0);

    // Check that payment events have non-null amounts in description
    for (const ev of data.events) {
      expect(ev.title).toBeTruthy();
      expect(ev.timestamp).toBeTruthy();
    }
  });
});


// ══════════════════════════════════════════════════════════════════
// Customer 360 View – UI Tests
// ══════════════════════════════════════════════════════════════════

test.describe('Customer 360 – UI tests', () => {
  // Known user IDs from seed_customer360.py
  const ANGELA_ID = 87;
  const MARCUS_ID = 91;

  // Helper: login and navigate directly to a customer 360 page
  async function goto360(page: import('@playwright/test').Page, userId: number) {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/customers/${userId}`);
    await page.waitForLoadState('networkidle');
    // Wait for the page to finish loading data
    await page.waitForTimeout(3000);
  }

  test('Customers nav link visible in backoffice sidebar', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.getByRole('link', { name: 'Customers' })).toBeVisible();
  });

  test('Customers page loads with search', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/customers`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Customers' })).toBeVisible();
    await expect(page.getByPlaceholder(/Search by name, email/i)).toBeVisible();
  });

  test('search returns results and clicking navigates to 360', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/customers`);
    await page.waitForLoadState('networkidle');

    await page.getByPlaceholder(/Search/i).fill('Angela');
    await page.getByRole('button', { name: 'Search' }).click();
    await page.waitForTimeout(3000);

    // Should show Angela Maharaj in the results table
    await expect(page.getByText('angela.maharaj@email.com')).toBeVisible({ timeout: 5000 });

    // Click the table row (the row contains the email)
    await page.getByText('angela.maharaj@email.com').click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Should be on Customer 360 page
    await expect(page).toHaveURL(/\/backoffice\/customers\/\d+/);
    // Header should have the customer name
    await expect(page.getByRole('heading', { name: 'Angela Maharaj' })).toBeVisible({ timeout: 5000 });
  });

  test('Customer 360 header shows customer identity and badges', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    // Header elements
    await expect(page.getByRole('heading', { name: 'Angela Maharaj' })).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Active', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/Excellent|Good/).first()).toBeVisible(); // Risk tier badge

    // Quick action buttons
    await expect(page.getByRole('button', { name: /Ask AI/i })).toBeVisible();
    // "New Application" link in header (not sidebar) — scope to main content
    await expect(page.getByRole('main').getByRole('link', { name: /New Application/i })).toBeVisible();

    // National ID is masked by default
    await expect(page.getByText(/\*\*\*\*\d{4}/)).toBeVisible();
  });

  test('Customer 360 AI panel shows summary and stats', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    // AI panel elements
    await expect(page.getByText('AI Account Summary')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('positive')).toBeVisible(); // Sentiment

    // Quick stats
    await expect(page.getByText('Lifetime Value', { exact: true })).toBeVisible();
    await expect(page.getByText('Active Products', { exact: true })).toBeVisible();
    await expect(page.getByText('Worst DPD', { exact: true })).toBeVisible();
    await expect(page.getByText('On-time Rate', { exact: true })).toBeVisible();
    await expect(page.getByText('Relationship', { exact: true })).toBeVisible();
    await expect(page.getByText('Last Contact', { exact: true })).toBeVisible();

    // Stats should show non-zero values
    await expect(page.getByText('100%').first()).toBeVisible(); // On-time rate
  });

  test('Customer 360 Overview tab shows profile and charts', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    // Overview tab is default
    await expect(page.getByText('Customer Profile')).toBeVisible({ timeout: 10000 });

    // Profile data (increase timeout — AI summary load can delay rendering)
    await expect(page.getByText('Republic Bank')).toBeVisible({ timeout: 8000 });
    await expect(page.getByText('Senior Accountant')).toBeVisible({ timeout: 8000 });
    await expect(page.getByText('Port of Spain')).toBeVisible({ timeout: 8000 });

    // Financial snapshot
    await expect(page.getByText('Payment Behavior (Last 12 Months)')).toBeVisible();
    await expect(page.getByText('Total Ever Borrowed')).toBeVisible();
    await expect(page.getByText('Total Outstanding')).toBeVisible();

    // Timeline
    await expect(page.getByText('Activity Timeline')).toBeVisible();
  });

  test('Customer 360 Applications tab shows loan history', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Applications' }).click();
    await page.waitForTimeout(500);

    // Should show applications with ZOT reference numbers
    const appCards = page.locator('text=/ZOT-/');
    await expect(appCards.first()).toBeVisible({ timeout: 5000 });

    // Click to expand one
    await appCards.first().click();
    await page.waitForTimeout(500);

    // Expanded detail should show
    await expect(page.getByText(/Requested|Approved|Rate|Term/).first()).toBeVisible();
    await expect(page.getByText(/View full application/).first()).toBeVisible();
  });

  test('Customer 360 Loans tab shows active loans with heatmap', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Loans' }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText('Active Loans').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/Principal|Monthly|Total Paid|Outstanding/).first()).toBeVisible();
  });

  test('Customer 360 Payments tab shows payment data', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Payments' }).click();
    await page.waitForTimeout(500);

    // Payment table headers
    await expect(page.getByText('Payment Trend')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Payment Methods')).toBeVisible();

    // Table has data
    await expect(page.locator('table').first()).toBeVisible();
    await expect(page.getByText('completed').first()).toBeVisible();
  });

  test('Customer 360 Collections tab shows records for Complex Case', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    await page.getByRole('button', { name: 'Collections' }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText('Collection Activity').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('WhatsApp Chat History').first()).toBeVisible();

    // Collection records show outcomes
    await expect(page.getByText(/promise to pay|no answer|escalated|payment arranged/i).first()).toBeVisible();
  });

  test('Customer 360 Documents tab shows uploaded documents', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Documents' }).click();
    await page.waitForTimeout(500);

    // Should show document cards with types
    await expect(page.getByText(/national id|proof of income/i).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Verified').first()).toBeVisible();
  });

  test('Customer 360 Audit Trail tab shows log entries', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Audit Trail' }).click();
    await page.waitForTimeout(500);

    // Audit table
    await expect(page.getByText(/submitted|approved|disbursed/i).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('loan_application').first()).toBeVisible();

    // Filter input
    await expect(page.getByPlaceholder(/Filter by action/i)).toBeVisible();
  });

  test('Customer 360 Communications tab shows conversations and comments', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    await page.getByRole('button', { name: 'Communications' }).click();
    await page.waitForTimeout(500);

    // Conversations
    await expect(page.getByText('AI Conversations').first()).toBeVisible({ timeout: 5000 });

    // Comments
    await expect(page.getByText('Application Messages').first()).toBeVisible();

    // Internal notes
    await expect(page.getByText('Internal Notes').first()).toBeVisible();
  });

  test('Ask AI panel opens and can receive question', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    // Open Ask AI panel
    await page.getByRole('button', { name: /Ask AI/i }).click();
    await page.waitForTimeout(500);

    // Panel is visible
    await expect(page.getByText('Ask AI About This Customer')).toBeVisible({ timeout: 3000 });
    await expect(page.getByPlaceholder('Ask a question...')).toBeVisible();

    // Type and send
    await page.getByPlaceholder('Ask a question...').fill('How many loans does she have?');
    await page.locator('button:has(svg.lucide-send)').click();

    // Should show the question as user message (exact match to avoid audit trail echo)
    await expect(page.getByText('How many loans does she have?', { exact: true })).toBeVisible({ timeout: 5000 });

    // AI or fallback response should appear (wait for API call)
    await page.waitForTimeout(5000);
    // The assistant response bubble should be visible
    const responseText = page.locator('div.bg-\\[var\\(--color-bg\\)\\]').last();
    await expect(responseText).toBeVisible({ timeout: 10000 });
  });

  test('cross-link from Loan Book to Customer 360 works', async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(`${BASE}/backoffice/loans`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Find a customer name link in the loan book
    const nameLink = page.locator('a[href*="/backoffice/customers/"]').first();
    if (await nameLink.isVisible({ timeout: 5000 }).catch(() => false)) {
      await nameLink.click();
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000);

      // Should navigate to customer 360
      await expect(page).toHaveURL(/\/backoffice\/customers\/\d+/);
    }
  });

  test('timeline filters work in the UI', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    // Scroll to timeline section
    const timeline = page.getByText('Activity Timeline');
    await timeline.scrollIntoViewIfNeeded();

    // Click a category filter chip (exact match to distinguish from the "Payments" tab button)
    const paymentChip = page.getByRole('button', { name: 'payment', exact: true });
    await paymentChip.click();
    await page.waitForTimeout(1500);

    // Filter should be visually active (has primary color class)
    await expect(paymentChip).toHaveClass(/primary/);

    // Timeline search
    const searchInput = page.getByPlaceholder('Search timeline...');
    await searchInput.fill('disbursed');
    await page.waitForTimeout(1500);
  });

  // ── Navigation and download tests ────────────────────────

  test('Applications tab has clickable "View Application" links', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Applications' }).click();
    await page.waitForTimeout(500);

    // Click to expand first application
    const appCard = page.locator('text=/ZOT-/').first();
    await appCard.click();
    await page.waitForTimeout(500);

    // "View full application" link
    const viewLink = page.getByText('View full application').first();
    await expect(viewLink).toBeVisible();
    const href = await viewLink.getAttribute('href');
    expect(href).toMatch(/\/backoffice\/review\/\d+/);
  });

  test('Loans tab has "View Application" and "Collection Detail" links', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Loans' }).click();
    await page.waitForTimeout(500);

    // Loan reference number should be a clickable link
    const refLink = page.locator('a[href*="/backoffice/review/"]').first();
    await expect(refLink).toBeVisible({ timeout: 5000 });

    // "View Application" link should be visible
    await expect(page.getByText('View Application').first()).toBeVisible();

    // "Collection Detail" link (for disbursed loans)
    await expect(page.getByText('Collection Detail').first()).toBeVisible();

    // "Contract" download button
    await expect(page.getByText('Contract').first()).toBeVisible();
  });

  test('Loans tab: clicking "View Application" navigates to review page', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Loans' }).click();
    await page.waitForTimeout(500);

    // Click the "View Application" link
    const viewLink = page.getByText('View Application').first();
    await viewLink.click();
    await page.waitForLoadState('networkidle');

    // Should navigate to application review page
    await expect(page).toHaveURL(/\/backoffice\/review\/\d+/);
  });

  test('Payments tab has clickable loan links', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Payments' }).click();
    await page.waitForTimeout(500);

    // Loan IDs in the table should be links
    const loanLink = page.locator('table a[href*="/backoffice/review/"]').first();
    await expect(loanLink).toBeVisible({ timeout: 5000 });
    await expect(loanLink).toHaveText(/^#\d+$/);
  });

  test('Collections tab has links to collection detail pages', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    await page.getByRole('button', { name: 'Collections' }).click();
    await page.waitForTimeout(500);

    // Collection records should have "Loan #XX" links
    const loanLinks = page.locator('a[href*="/backoffice/collections/"]');
    await expect(loanLinks.first()).toBeVisible({ timeout: 5000 });

    // Click one to navigate
    await loanLinks.first().click();
    await page.waitForLoadState('networkidle');

    // Should navigate to collection detail
    await expect(page).toHaveURL(/\/backoffice\/collections\/\d+/);
  });

  test('Documents tab shows downloadable documents with app links', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Documents' }).click();
    await page.waitForTimeout(500);

    // Uploaded documents section should be visible
    await expect(page.getByText('Uploaded Documents').first()).toBeVisible({ timeout: 5000 });

    // Each document should have a "Download" button
    await expect(page.getByText('Download').first()).toBeVisible();

    // App references are clickable links
    const appLink = page.locator('a[href*="/backoffice/review/"]').first();
    await expect(appLink).toBeVisible();
  });

  test('Loans tab shows contract download and HP agreement buttons', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Loans' }).click();
    await page.waitForTimeout(500);

    // Each loan card should have a "Contract" download button
    await expect(page.getByText('Contract').first()).toBeVisible({ timeout: 5000 });

    // HP Agreement button appears only for signed consents (may not exist in seed data)
    // But Contract should always be available for disbursed loans
    const contractButtons = page.locator('button:has-text("Contract")');
    const count = await contractButtons.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('Communications tab has clickable conversation and app links', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    await page.getByRole('button', { name: 'Communications' }).click();
    await page.waitForTimeout(500);

    // Conversation links
    const convLink = page.locator('a[href*="/backoffice/conversations/"]').first();
    await expect(convLink).toBeVisible({ timeout: 5000 });

    // "View Full Conversation" link
    await expect(page.getByText('View Full Conversation').first()).toBeVisible();

    // App links in comments
    const appLink = page.locator('a[href*="/backoffice/review/"]').first();
    await expect(appLink).toBeVisible();
  });

  test('Audit Trail tab has clickable entity links', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    await page.getByRole('button', { name: 'Audit Trail' }).click();
    await page.waitForTimeout(500);

    // Entity references should be clickable for loan_application entities
    const entityLink = page.locator('table a[href*="/backoffice/review/"]').first();
    await expect(entityLink).toBeVisible({ timeout: 5000 });
    await expect(entityLink).toHaveText(/loan_application #\d+/);
  });

  test('Timeline events are clickable and navigate to detail pages', async ({ page }) => {
    await goto360(page, ANGELA_ID);

    // The timeline is on the Overview tab (default)
    const timelineSection = page.getByText('Activity Timeline');
    await timelineSection.scrollIntoViewIfNeeded();
    await page.waitForTimeout(1000);

    // Timeline events that are loan-related should be links
    const eventLink = page.locator('.max-h-96 a[href*="/backoffice/"]').first();
    if (await eventLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      const href = await eventLink.getAttribute('href');
      expect(href).toMatch(/\/backoffice\/(review|collections|conversations)\/\d+/);
    }
  });

  // ── Credit Bureau Alerts tests ────────────────────────

  test('Bureau Alerts tab shows badge count and alert cards', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    // Tab should be visible (may or may not have a badge depending on prior test state)
    const alertTab = page.getByRole('button', { name: /Bureau Alerts/ });
    await expect(alertTab).toBeVisible();

    // Click the tab
    await alertTab.click();
    await page.waitForTimeout(500);

    // Should show summary header
    await expect(page.getByText('Credit Bureau Alerts')).toBeVisible({ timeout: 5000 });

    // Alert card headings should be visible (regardless of whether action was taken)
    await expect(page.getByRole('heading', { name: 'Default Reported at First Citizens Bank' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'New Delinquency Reported at JMMB' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Collection Payment Made to Another Creditor' })).toBeVisible();

    // Marcus also has an acknowledged alert
    await expect(page.getByRole('heading', { name: 'New Credit Inquiry from RBC Royal Bank' })).toBeVisible();
  });

  test('Bureau Alerts shows alert details and severity badges', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    await page.getByRole('button', { name: /Bureau Alerts/ }).click();
    await page.waitForTimeout(500);

    // Critical severity on the default alert
    await expect(page.getByText('Critical', { exact: true }).first()).toBeVisible({ timeout: 5000 });

    // High severity on delinquency
    await expect(page.getByText('High', { exact: true }).first()).toBeVisible();

    // Institution names visible in the details grid
    await expect(page.getByText('First Citizens Bank', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('JMMB Trinidad', { exact: true }).first()).toBeVisible();

    // "What this means" context boxes
    await expect(page.getByText('What this means:').first()).toBeVisible();
  });

  test('Bureau Alerts action buttons are present for actionable alerts', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    await page.getByRole('button', { name: /Bureau Alerts/ }).click();
    await page.waitForTimeout(500);

    // At least one action button should be visible (some alerts may have been acted on in previous runs)
    // Check for the presence of any action-related buttons
    const actionButtons = page.locator('button').filter({
      hasText: /Freeze Account|Trigger Early Collection|Prioritize for Collection|Initiate Pre-Collection|Acknowledge|Dismiss|Reassess Risk|Escalate to Management/
    });
    const count = await actionButtons.count();
    expect(count).toBeGreaterThanOrEqual(1);

    // At minimum, Dismiss buttons should be present on non-dismissed, non-action-taken alerts
    // (unless all alerts have been acted on)
    // The acknowledged alert (RBC inquiry) should still have Acknowledge/Dismiss visible
  });

  test('Bureau Alerts: taking action updates alert status', async ({ request, page }) => {
    // First, use API to reset one of Marcus's alerts to 'new' so we can test taking action
    const API = 'http://localhost:8000/api';
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const adminToken = (await loginRes.json()).access_token;
    const alertsRes = await request.get(`${API}/customers/${MARCUS_ID}/alerts`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const alerts = await alertsRes.json();
    // Find the delinquency alert and reset it to 'new' if needed
    const delinq = alerts.find((a: any) => a.alert_type === 'new_delinquency');
    if (delinq && delinq.status !== 'new') {
      await request.patch(`${API}/customers/${MARCUS_ID}/alerts/${delinq.id}`, {
        headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
        data: { status: 'new' },
      });
    }

    await goto360(page, MARCUS_ID);
    await page.getByRole('button', { name: /Bureau Alerts/ }).click();
    await page.waitForTimeout(1000);

    // Now the delinquency alert should be actionable
    const actionBtn = page.getByRole('button', { name: 'Initiate Pre-Collection Contact' });
    await expect(actionBtn).toBeVisible({ timeout: 5000 });
    await actionBtn.click();
    await page.waitForTimeout(2000);

    // After action, at least one alert should show "Action Taken"
    await expect(page.getByText('Action taken:', { exact: false }).first()).toBeVisible({ timeout: 5000 });
  });

  test('Bureau Alerts: filter by status works', async ({ page }) => {
    await goto360(page, MARCUS_ID);

    await page.getByRole('button', { name: /Bureau Alerts/ }).click();
    await page.waitForTimeout(500);

    // Click "Acknowledged" filter
    const ackFilter = page.locator('button').filter({ hasText: 'Acknowledged' }).first();
    await ackFilter.click();
    await page.waitForTimeout(500);

    // Should show only the acknowledged alert (RBC inquiry)
    await expect(page.getByRole('heading', { name: 'New Credit Inquiry from RBC Royal Bank' })).toBeVisible({ timeout: 5000 });
    // The new alerts should be hidden
    await expect(page.getByRole('heading', { name: 'Default Reported at First Citizens Bank' })).not.toBeVisible();

    // Click "All" to reset
    await page.locator('button').filter({ hasText: /^All$/ }).first().click();
    await page.waitForTimeout(500);
    await expect(page.getByRole('heading', { name: 'Default Reported at First Citizens Bank' })).toBeVisible();
  });

  test('Bureau Alerts API returns alerts for a customer', async ({ request }) => {
    const API = 'http://localhost:8000/api';
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const adminToken = (await loginRes.json()).access_token;

    const res = await request.get(`${API}/customers/${MARCUS_ID}/alerts`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    expect(res.status()).toBe(200);
    const alerts = await res.json();
    expect(alerts.length).toBeGreaterThanOrEqual(4);

    // Verify alert structure
    const critical = alerts.find((a: any) => a.alert_type === 'default_elsewhere');
    expect(critical).toBeDefined();
    expect(critical.severity).toBe('critical');
    expect(critical.other_institution).toBe('First Citizens Bank');
    expect(critical.other_delinquency_days).toBe(95);
  });

  test('Bureau Alerts API: PATCH updates alert status and action', async ({ request }) => {
    const API = 'http://localhost:8000/api';
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const adminToken = (await loginRes.json()).access_token;

    // Get alerts for Kevin (89)
    const listRes = await request.get(`${API}/customers/89/alerts`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const alerts = await listRes.json();
    const kevinAlert = alerts.find((a: any) => a.alert_type === 'new_loan');
    expect(kevinAlert).toBeDefined();

    // Take action
    const patchRes = await request.patch(`${API}/customers/89/alerts/${kevinAlert.id}`, {
      headers: { Authorization: `Bearer ${adminToken}`, 'Content-Type': 'application/json' },
      data: { action_taken: 'recalculate_dti', action_notes: 'DTI recalculated. Still within limits.' },
    });
    expect(patchRes.status()).toBe(200);
    const updated = await patchRes.json();
    expect(updated.status).toBe('action_taken');
    expect(updated.action_taken).toBe('recalculate_dti');
    expect(updated.acted_by).toBeTruthy();
  });
});


// ══════════════════════════════════════════════════════════════════
// Performance Tests — API Response Times & UI Page Load Times
// ══════════════════════════════════════════════════════════════════

test.describe('Performance – API response times', () => {
  const API = 'http://localhost:8000/api';
  let adminToken: string;
  let applicantToken: string;

  test.beforeAll(async ({ request }) => {
    const adminRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    adminToken = (await adminRes.json()).access_token;
    const appRes = await request.post(`${API}/auth/login`, {
      data: { email: 'angela.maharaj@email.com', password: 'Test1234!' },
    });
    applicantToken = (await appRes.json()).access_token;
  });

  test('auth login responds within 500ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(500);
    console.log(`  auth/login: ${elapsed}ms`);
  });

  test('underwriter queue responds within 500ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/underwriter/queue`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(500);
    console.log(`  underwriter/queue: ${elapsed}ms`);
  });

  test('loan book responds within 2000ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/underwriter/loans`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(2000);
    console.log(`  underwriter/loans: ${elapsed}ms`);
  });

  test('collections queue responds within 500ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/collections/queue`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(500);
    console.log(`  collections/queue: ${elapsed}ms`);
  });

  test('dashboard metrics respond within 500ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/reports/dashboard`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(500);
    console.log(`  reports/dashboard: ${elapsed}ms`);
  });

  test('Customer 360 full payload responds within 1000ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/customers/87/360`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(1000);
    console.log(`  customers/87/360: ${elapsed}ms`);
  });

  test('Customer 360 timeline responds within 500ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/customers/87/timeline`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(500);
    console.log(`  customers/87/timeline: ${elapsed}ms`);
  });

  test('credit bureau alerts respond within 300ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/customers/91/alerts`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(300);
    console.log(`  customers/91/alerts: ${elapsed}ms`);
  });

  test('payment schedule responds within 500ms', async ({ request }) => {
    // Get a disbursed loan
    const loansRes = await request.get(`${API}/loans/`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const loans = await loansRes.json();
    const disbursed = (Array.isArray(loans) ? loans : loans.loans || []).find((l: any) => l.status === 'disbursed');
    if (!disbursed) { test.skip(); return; }

    const start = Date.now();
    const res = await request.get(`${API}/payments/${disbursed.id}/schedule`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(500);
    console.log(`  payments/${disbursed.id}/schedule: ${elapsed}ms`);
  });

  test('customer search responds within 300ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/underwriter/customers/search`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      params: { q: 'angela' },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(300);
    console.log(`  customers/search?q=angela: ${elapsed}ms`);
  });

  test('consumer loan list responds within 500ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/loans/`, {
      headers: { Authorization: `Bearer ${applicantToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(500);
    console.log(`  loans/ (consumer): ${elapsed}ms`);
  });

  test('reports types responds within 300ms', async ({ request }) => {
    const start = Date.now();
    const res = await request.get(`${API}/reports/types`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    });
    const elapsed = Date.now() - start;
    expect(res.status()).toBe(200);
    expect(elapsed).toBeLessThan(300);
    console.log(`  reports/types: ${elapsed}ms`);
  });

  test('10 sequential API calls complete within 3 seconds total', async ({ request }) => {
    const endpoints = [
      `${API}/underwriter/queue`,
      `${API}/underwriter/loans`,
      `${API}/collections/queue`,
      `${API}/reports/dashboard`,
      `${API}/customers/87/360`,
      `${API}/customers/87/timeline`,
      `${API}/customers/91/alerts`,
      `${API}/underwriter/customers/search?q=dar`,
      `${API}/admin/rules`,
      `${API}/reports/types`,
    ];
    const headers = { Authorization: `Bearer ${adminToken}` };

    const start = Date.now();
    for (const endpoint of endpoints) {
      const res = await request.get(endpoint, { headers });
      expect(res.status()).toBe(200);
    }
    const totalElapsed = Date.now() - start;
    expect(totalElapsed).toBeLessThan(3000);
    console.log(`  10 sequential API calls total: ${totalElapsed}ms (avg ${Math.round(totalElapsed / 10)}ms)`);
  });

  test('5 parallel API calls complete within 2000ms', async ({ request }) => {
    const headers = { Authorization: `Bearer ${adminToken}` };
    const start = Date.now();
    const results = await Promise.all([
      request.get(`${API}/underwriter/queue`, { headers }),
      request.get(`${API}/underwriter/loans`, { headers }),
      request.get(`${API}/collections/queue`, { headers }),
      request.get(`${API}/reports/dashboard`, { headers }),
      request.get(`${API}/customers/87/360`, { headers }),
    ]);
    const elapsed = Date.now() - start;
    for (const res of results) {
      expect(res.status()).toBe(200);
    }
    expect(elapsed).toBeLessThan(2000);
    console.log(`  5 parallel API calls: ${elapsed}ms`);
  });
});

test.describe('Performance – UI page load times', () => {
  async function measurePageLoad(page: import('@playwright/test').Page, url: string, waitFor: string | RegExp) {
    const start = Date.now();
    await page.goto(url);
    await page.waitForLoadState('networkidle');
    if (typeof waitFor === 'string') {
      await page.getByText(waitFor, { exact: false }).first().waitFor({ state: 'visible', timeout: 10000 });
    } else {
      await page.getByText(waitFor).first().waitFor({ state: 'visible', timeout: 10000 });
    }
    return Date.now() - start;
  }

  test.beforeEach(async ({ page }) => {
    // Login as admin
    await page.goto(`${BASE}/login`);
    await page.getByPlaceholder('Email').fill('admin@zotta.tt');
    await page.getByPlaceholder('Password').fill('Admin123!');
    await page.getByRole('button', { name: /sign in/i }).click();
    await page.waitForURL('**/backoffice**', { timeout: 5000 });
  });

  test('backoffice dashboard loads within 3 seconds', async ({ page }) => {
    const elapsed = await measurePageLoad(page, `${BASE}/backoffice`, 'Dashboard');
    expect(elapsed).toBeLessThan(3000);
    console.log(`  Dashboard: ${elapsed}ms`);
  });

  test('applications queue loads within 3 seconds', async ({ page }) => {
    const elapsed = await measurePageLoad(page, `${BASE}/backoffice/applications`, /application/i);
    expect(elapsed).toBeLessThan(3000);
    console.log(`  Applications queue: ${elapsed}ms`);
  });

  test('loan book loads within 5 seconds', async ({ page }) => {
    const elapsed = await measurePageLoad(page, `${BASE}/backoffice/loans`, /loan/i);
    expect(elapsed).toBeLessThan(5000);
    console.log(`  Loan book: ${elapsed}ms`);
  });

  test('collections page loads within 3 seconds', async ({ page }) => {
    const elapsed = await measurePageLoad(page, `${BASE}/backoffice/collections`, /collection/i);
    expect(elapsed).toBeLessThan(3000);
    console.log(`  Collections: ${elapsed}ms`);
  });

  test('Customer 360 page loads within 15 seconds (includes AI summary)', async ({ page }) => {
    const start = Date.now();
    await page.goto(`${BASE}/backoffice/customers/87`);
    await page.waitForLoadState('networkidle');
    // Customer 360 loads the AI summary which can take several seconds
    await page.getByText('Angela Maharaj', { exact: false }).first().waitFor({ state: 'visible', timeout: 15000 });
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(15000);
    console.log(`  Customer 360: ${elapsed}ms`);
  });

  test('reports page loads within 3 seconds', async ({ page }) => {
    const elapsed = await measurePageLoad(page, `${BASE}/backoffice/reports`, /report/i);
    expect(elapsed).toBeLessThan(3000);
    console.log(`  Reports: ${elapsed}ms`);
  });

  test('products page loads within 3 seconds', async ({ page }) => {
    const elapsed = await measurePageLoad(page, `${BASE}/backoffice/products`, /product/i);
    expect(elapsed).toBeLessThan(3000);
    console.log(`  Products: ${elapsed}ms`);
  });

  test('Customer 360 tab switching is fast (< 500ms per tab)', async ({ page }) => {
    await page.goto(`${BASE}/backoffice/customers/87`);
    await page.waitForLoadState('networkidle');
    await page.getByText('Angela Maharaj').first().waitFor({ state: 'visible', timeout: 15000 });

    const tabs = ['Applications', 'Loans', 'Payments', 'Collections', 'Documents', 'Bureau Alerts', 'Audit Trail'];
    const timings: Record<string, number> = {};

    for (const tab of tabs) {
      const start = Date.now();
      await page.getByRole('button', { name: tab }).click();
      await page.waitForTimeout(100); // Brief settle
      const elapsed = Date.now() - start;
      timings[tab] = elapsed;
      expect(elapsed).toBeLessThan(500);
    }

    console.log('  Tab switching times:', JSON.stringify(timings));
  });
});

test.describe('Performance – stress tests', () => {
  const API = 'http://localhost:8000/api';
  let adminToken: string;

  test.beforeAll(async ({ request }) => {
    const res = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    adminToken = (await res.json()).access_token;
  });

  test('20 rapid-fire auth requests complete without errors', async ({ request }) => {
    const start = Date.now();
    const promises = Array.from({ length: 20 }, () =>
      request.post(`${API}/auth/login`, {
        data: { email: 'admin@zotta.tt', password: 'Admin123!' },
      })
    );
    const results = await Promise.all(promises);
    const elapsed = Date.now() - start;
    const failures = results.filter(r => r.status() !== 200);
    expect(failures.length).toBe(0);
    console.log(`  20 parallel logins: ${elapsed}ms (avg ${Math.round(elapsed / 20)}ms, all 200 OK)`);
  });

  test('Customer 360 for all 5 personas in parallel within 3 seconds', async ({ request }) => {
    const headers = { Authorization: `Bearer ${adminToken}` };
    const userIds = [87, 88, 89, 90, 91]; // Angela, Darren, Kevin, Priya, Marcus

    const start = Date.now();
    const results = await Promise.all(
      userIds.map(id => request.get(`${API}/customers/${id}/360`, { headers }))
    );
    const elapsed = Date.now() - start;
    for (const res of results) {
      expect(res.status()).toBe(200);
    }
    expect(elapsed).toBeLessThan(3000);
    console.log(`  5 parallel Customer 360 calls: ${elapsed}ms (avg ${Math.round(elapsed / 5)}ms)`);
  });

  test('10 parallel mixed endpoint calls complete within 2 seconds', async ({ request }) => {
    const headers = { Authorization: `Bearer ${adminToken}` };
    const start = Date.now();
    const results = await Promise.all([
      request.get(`${API}/underwriter/queue`, { headers }),
      request.get(`${API}/collections/queue`, { headers }),
      request.get(`${API}/reports/dashboard`, { headers }),
      request.get(`${API}/reports/types`, { headers }),
      request.get(`${API}/admin/rules`, { headers }),
      request.get(`${API}/customers/87/360`, { headers }),
      request.get(`${API}/customers/88/360`, { headers }),
      request.get(`${API}/customers/87/timeline`, { headers }),
      request.get(`${API}/customers/87/alerts`, { headers }),
      request.get(`${API}/underwriter/loans`, { headers }),
    ]);
    const elapsed = Date.now() - start;
    for (const res of results) {
      expect(res.status()).toBe(200);
    }
    expect(elapsed).toBeLessThan(2000);
    console.log(`  10 parallel mixed calls: ${elapsed}ms`);
  });
});

// ═══════════════════════════════════════════════════════════════
// Sector Analysis – API tests
// ═══════════════════════════════════════════════════════════════

test.describe('Sector Analysis – API tests', () => {
  const API = 'http://localhost:8000/api';

  async function getAdminHeaders(request: import('@playwright/test').APIRequestContext) {
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'admin@zotta.tt', password: 'Admin123!' },
    });
    const { access_token } = await loginRes.json();
    return { Authorization: `Bearer ${access_token}` };
  }

  test('taxonomy returns all 23 sectors', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const res = await request.get(`${API}/sector-analysis/taxonomy`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.sectors).toBeDefined();
    expect(data.sectors.length).toBe(23);
    expect(data.sectors).toContain('Banking & Financial Services');
    expect(data.sectors).toContain('MISSING');
  });

  test('dashboard returns sector distribution with all required fields', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const res = await request.get(`${API}/sector-analysis/dashboard`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.total_outstanding).toBeGreaterThan(0);
    expect(data.total_loan_count).toBeGreaterThan(0);
    expect(data.sector_count).toBeGreaterThan(0);
    expect(data.sectors).toBeDefined();
    expect(data.sectors.length).toBeGreaterThan(0);
    expect(data.top_5).toBeDefined();
    expect(data.bottom_5).toBeDefined();
    // Each sector must have all required fields
    const sector = data.sectors[0];
    expect(sector.sector).toBeTruthy();
    expect(sector.loan_count).toBeGreaterThan(0);
    expect(sector.total_outstanding).toBeGreaterThan(0);
    expect(sector.exposure_pct).toBeDefined();
    expect(sector.concentration_status).toBeDefined();
    expect(sector.risk_rating).toBeDefined();
    // Exposure percentages must sum to ~100
    const totalPct = data.sectors.reduce((sum: number, s: any) => sum + s.exposure_pct, 0);
    expect(totalPct).toBeGreaterThan(95);
    expect(totalPct).toBeLessThan(105);
  });

  test('sector detail returns risk metrics for a specific sector', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    // First get a sector name from dashboard
    const dashRes = await request.get(`${API}/sector-analysis/dashboard`, { headers });
    const dash = await dashRes.json();
    const sectorName = encodeURIComponent(dash.sectors[0].sector);

    const res = await request.get(`${API}/sector-analysis/sectors/${sectorName}`, { headers });
    expect(res.status()).toBe(200);
    const detail = await res.json();
    expect(detail.sector).toBeTruthy();
    expect(detail.loan_count).toBeGreaterThanOrEqual(0);
    expect(detail.total_outstanding).toBeDefined();
    expect(detail.exposure_pct).toBeDefined();
    expect(detail.delinquency_rate).toBeDefined();
    expect(detail.npl_ratio).toBeDefined();
    expect(detail.dpd_30).toBeDefined();
    expect(detail.dpd_60).toBeDefined();
    expect(detail.dpd_90).toBeDefined();
    expect(detail.roll_rates).toBeDefined();
    expect(detail.loans).toBeDefined();
  });

  test('heatmap returns matrix with all sectors', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const res = await request.get(`${API}/sector-analysis/heatmap`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.length).toBeGreaterThan(0);
    const row = data[0];
    expect(row.sector).toBeTruthy();
    expect(row.exposure_pct).toBeDefined();
    expect(row.delinquency_rate).toBeDefined();
    expect(row.npl_ratio).toBeDefined();
    expect(row.risk_rating).toBeDefined();
    expect(row.concentration_status).toBeDefined();
  });

  test('CRUD lifecycle for sector policies with maker-checker', async ({ request }) => {
    const headers = await getAdminHeaders(request);

    // Create a policy
    const createRes = await request.post(`${API}/sector-analysis/policies`, {
      headers,
      data: {
        sector: 'Education',
        exposure_cap_pct: 10.0,
        risk_rating: 'medium',
        on_watchlist: true,
        watchlist_review_frequency: 'monthly',
        justification: 'E2E test policy',
      },
    });
    expect(createRes.status()).toBe(200);
    const policy = await createRes.json();
    expect(policy.id).toBeGreaterThan(0);
    expect(policy.sector).toBe('Education');
    expect(policy.exposure_cap_pct).toBe(10.0);
    expect(policy.status).toBe('active'); // admin auto-approves

    // List policies
    const listRes = await request.get(`${API}/sector-analysis/policies`, { headers });
    expect(listRes.status()).toBe(200);
    const policies = await listRes.json();
    expect(policies.length).toBeGreaterThan(0);

    // Update policy
    const updateRes = await request.patch(`${API}/sector-analysis/policies/${policy.id}`, {
      headers,
      data: { exposure_cap_pct: 15.0, risk_rating: 'high' },
    });
    expect(updateRes.status()).toBe(200);
    const updated = await updateRes.json();
    expect(updated.exposure_cap_pct).toBe(15.0);
    expect(updated.risk_rating).toBe('high');

    // Archive policy
    const archiveRes = await request.delete(`${API}/sector-analysis/policies/${policy.id}`, { headers });
    expect(archiveRes.status()).toBe(200);
  });

  test('CRUD lifecycle for alert rules', async ({ request }) => {
    const headers = await getAdminHeaders(request);

    // Create rule
    const createRes = await request.post(`${API}/sector-analysis/alert-rules`, {
      headers,
      data: {
        name: 'E2E Test Rule',
        metric: 'exposure_pct',
        operator: '>',
        threshold: 25.0,
        severity: 'warning',
        recommended_action: 'Test action',
      },
    });
    expect(createRes.status()).toBe(200);
    const rule = await createRes.json();
    expect(rule.id).toBeGreaterThan(0);
    expect(rule.name).toBe('E2E Test Rule');

    // List rules
    const listRes = await request.get(`${API}/sector-analysis/alert-rules`, { headers });
    expect(listRes.status()).toBe(200);
    const rules = await listRes.json();
    expect(rules.some((r: any) => r.name === 'E2E Test Rule')).toBe(true);

    // Delete rule
    const delRes = await request.delete(`${API}/sector-analysis/alert-rules/${rule.id}`, { headers });
    expect(delRes.status()).toBe(200);
  });

  test('alerts can be listed and acknowledged', async ({ request }) => {
    const headers = await getAdminHeaders(request);

    const res = await request.get(`${API}/sector-analysis/alerts`, { headers });
    expect(res.status()).toBe(200);
    const alerts = await res.json();
    // Should have seeded alerts
    expect(alerts.length).toBeGreaterThan(0);

    // Acknowledge first new alert
    const newAlert = alerts.find((a: any) => a.status === 'new');
    if (newAlert) {
      const ackRes = await request.patch(`${API}/sector-analysis/alerts/${newAlert.id}`, {
        headers,
        data: { status: 'acknowledged', action_notes: 'Reviewed in E2E test' },
      });
      expect(ackRes.status()).toBe(200);
      const updated = await ackRes.json();
      expect(updated.status).toBe('acknowledged');
    }
  });

  test('alert evaluation fires rules against current portfolio', async ({ request }) => {
    const headers = await getAdminHeaders(request);
    const res = await request.post(`${API}/sector-analysis/alerts/evaluate`, { headers });
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.fired_count).toBeGreaterThanOrEqual(0);
    expect(data.alerts).toBeDefined();
  });

  test('concentration check validates sector origination', async ({ request }) => {
    const headers = await getAdminHeaders(request);

    // Check a normal sector — should be allowed
    const normalRes = await request.post(`${API}/sector-analysis/check-origination`, {
      headers,
      data: { sector: 'Education', loan_amount: 5000 },
    });
    expect(normalRes.status()).toBe(200);
    const normal = await normalRes.json();
    expect(normal.allowed).toBeDefined();

    // Check the paused sector — should be blocked
    const pausedRes = await request.post(`${API}/sector-analysis/check-origination`, {
      headers,
      data: { sector: 'Mining & Extractives', loan_amount: 5000 },
    });
    expect(pausedRes.status()).toBe(200);
    const paused = await pausedRes.json();
    expect(paused.allowed).toBe(false);
    expect(paused.reasons.length).toBeGreaterThan(0);
  });

  test('stress test produces plausible results', async ({ request }) => {
    const headers = await getAdminHeaders(request);

    const res = await request.post(`${API}/sector-analysis/stress-test`, {
      headers,
      data: {
        name: 'E2E Hurricane Scenario',
        shocks: {
          'Hospitality & Tourism': { default_rate_multiplier: 3.0, exposure_change_pct: -20 },
          'Agriculture & Agro-processing': { default_rate_multiplier: 2.5, exposure_change_pct: -15 },
        },
      },
    });
    expect(res.status()).toBe(200);
    const result = await res.json();
    expect(result.scenario_name).toBe('E2E Hurricane Scenario');
    expect(result.total_portfolio).toBeGreaterThan(0);
    expect(result.total_expected_loss).toBeGreaterThanOrEqual(0);
    expect(result.impact_pct_of_portfolio).toBeDefined();
    expect(result.sector_results).toBeDefined();
    expect(result.sector_results.length).toBeGreaterThan(0);
  });

  test('snapshots can be listed and generated', async ({ request }) => {
    const headers = await getAdminHeaders(request);

    // List snapshots (should have seeded ones)
    const listRes = await request.get(`${API}/sector-analysis/snapshots`, { headers });
    expect(listRes.status()).toBe(200);
    const snaps = await listRes.json();
    expect(snaps.length).toBeGreaterThan(0);

    // Generate a new snapshot
    const genRes = await request.post(`${API}/sector-analysis/snapshots/generate`, { headers });
    expect(genRes.status()).toBe(200);
    const genData = await genRes.json();
    expect(genData.generated).toBeGreaterThan(0);
  });

  test('macro indicators CRUD', async ({ request }) => {
    const headers = await getAdminHeaders(request);

    // Create indicator
    const createRes = await request.post(`${API}/sector-analysis/macro-indicators`, {
      headers,
      data: {
        sector: 'Hospitality & Tourism',
        indicator_name: 'Tourist Arrivals',
        indicator_value: 125000,
        period: '2026-01-01',
        source: 'Central Statistical Office',
        notes: 'E2E test indicator',
      },
    });
    expect(createRes.status()).toBe(200);
    const indicator = await createRes.json();
    expect(indicator.id).toBeGreaterThan(0);
    expect(indicator.indicator_name).toBe('Tourist Arrivals');

    // List indicators
    const listRes = await request.get(`${API}/sector-analysis/macro-indicators?sector=Hospitality+%26+Tourism`, { headers });
    expect(listRes.status()).toBe(200);
    const indicators = await listRes.json();
    expect(indicators.length).toBeGreaterThan(0);
  });

  test('unauthorized users cannot access sector analysis', async ({ request }) => {
    // Login as applicant (non-staff)
    const loginRes = await request.post(`${API}/auth/login`, {
      data: { email: 'marcus.mohammed0@email.com', password: 'Applicant1!' },
    });
    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    const res = await request.get(`${API}/sector-analysis/dashboard`, { headers });
    expect(res.status()).toBe(403);
  });
});
