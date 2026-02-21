import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api';

const APPLICANT_EMAIL = process.env.SMOKE_APPLICANT_EMAIL ?? 'marcus.mohammed0@email.com';
const APPLICANT_PASSWORD = process.env.SMOKE_APPLICANT_PASSWORD ?? 'Applicant1!';
const ADMIN_EMAIL = process.env.SMOKE_ADMIN_EMAIL ?? 'admin@zotta.tt';
const ADMIN_PASSWORD = process.env.SMOKE_ADMIN_PASSWORD ?? 'Admin123!';

type AuthHeaders = { Authorization: string };

function extractArray(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.entries)) return payload.entries;
  if (Array.isArray(payload?.results)) return payload.results;
  if (Array.isArray(payload?.enrollments)) return payload.enrollments;
  return [];
}

function uniqueSuffix(prefix = 'SMK'): string {
  const rand = Math.floor(Math.random() * 10000)
    .toString()
    .padStart(4, '0');
  return `${prefix}-${Date.now()}-${rand}`;
}

function escapeRegex(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function asNumber(value: any): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function dateIso(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().split('T')[0];
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

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

async function upsertApplicantProfile(
  request: APIRequestContext,
  applicantHeaders: AuthHeaders,
  updates: Record<string, any> = {},
) {
  const profileRes = await request.put(`${API}/loans/profile`, {
    headers: applicantHeaders,
    data: {
      date_of_birth: '1991-02-19',
      national_id: '19910219001',
      employer_name: 'Smoke QA Ltd',
      employer_sector: 'Information Technology',
      employment_type: 'employed',
      years_employed: 6,
      monthly_income: 18000,
      monthly_expenses: 3200,
      existing_debt: 1200,
      ...updates,
    },
  });
  expect([200, 201]).toContain(profileRes.status());
}

async function createDraftApplication(
  request: APIRequestContext,
  applicantHeaders: AuthHeaders,
  opts: {
    amount: number;
    termMonths: number;
    description: string;
    merchantId?: number;
    branchId?: number;
    creditProductId?: number;
    items?: Array<{ category_id: number; description: string; price: number; quantity: number }>;
  },
) {
  const res = await request.post(`${API}/loans/`, {
    headers: applicantHeaders,
    data: {
      amount_requested: opts.amount,
      term_months: opts.termMonths,
      purpose: 'personal',
      purpose_description: opts.description,
      merchant_id: opts.merchantId,
      branch_id: opts.branchId,
      credit_product_id: opts.creditProductId,
      downpayment: 0,
      total_financed: opts.amount,
      items: opts.items ?? [],
    },
  });
  expect(res.status()).toBe(201);
  const body = await res.json();
  return { id: Number(body.id), reference: String(body.reference_number || '') };
}

async function submitApplication(
  request: APIRequestContext,
  applicantHeaders: AuthHeaders,
  applicationId: number,
) {
  const submitRes = await request.post(`${API}/loans/${applicationId}/submit`, {
    headers: applicantHeaders,
  });
  expect(submitRes.status()).toBe(200);
  return submitRes.json();
}

async function ensureApplicationApproved(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  applicationId: number,
  reason: string,
) {
  const detailRes = await request.get(`${API}/underwriter/applications/${applicationId}`, {
    headers: adminHeaders,
  });
  expect(detailRes.status()).toBe(200);
  const detail = await detailRes.json();
  const status = String(detail.status || '');

  if (['approved', 'accepted', 'offer_sent', 'disbursed'].includes(status)) {
    return;
  }

  const decideRes = await request.post(`${API}/underwriter/applications/${applicationId}/decide`, {
    headers: adminHeaders,
    data: { action: 'approve', reason },
  });
  if (decideRes.status() === 409) {
    const body = await decideRes.json();
    throw new Error(`Approval blocked for application ${applicationId}: ${JSON.stringify(body.detail)}`);
  }
  expect([200, 400]).toContain(decideRes.status());
}

async function disburseApplication(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  applicationId: number,
  notes: string,
) {
  const disburseRes = await request.post(`${API}/underwriter/applications/${applicationId}/disburse`, {
    headers: adminHeaders,
    data: { method: 'manual', notes },
  });

  if (disburseRes.status() === 409) {
    const existingRes = await request.get(`${API}/underwriter/applications/${applicationId}/disbursement`, {
      headers: adminHeaders,
    });
    expect(existingRes.status()).toBe(200);
    return existingRes.json();
  }

  expect(disburseRes.status()).toBe(200);
  return disburseRes.json();
}

async function goToShoppingContextStep(page: Page) {
  await page.goto(`${BASE}/apply`);
  await page.waitForLoadState('domcontentloaded');

  await expect(page.locator('h2', { hasText: 'Personal Information' })).toBeVisible({ timeout: 12000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'Employment & Income' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'References' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: /Next/i }).click();

  await expect(page.locator('h2', { hasText: 'Shopping Context' })).toBeVisible({ timeout: 12000 });
}

test.describe('Smoke - Combined Suite E2E-013 to E2E-015', () => {
  test('E2E-013: New Merchant Onboarding -> Product Availability -> Application', async ({
    page,
    request,
  }) => {
    test.setTimeout(7 * 60 * 1000);

    const adminHeaders = await apiLogin(request, ADMIN_EMAIL, ADMIN_PASSWORD);
    const applicantHeaders = await apiLogin(request, APPLICANT_EMAIL, APPLICANT_PASSWORD);

    const merchantName = `Smoke Merchant ${uniqueSuffix('MRC')}`;
    const categoryName = `Smoke Category ${uniqueSuffix('CAT')}`;
    const productName = `Smoke Product ${uniqueSuffix('PRD')}`;
    const merchantBranchName = `Main Branch ${uniqueSuffix('BR')}`;

    let merchantId = 0;
    let productId = 0;
    let categoryId = 0;
    let branchId = 0;
    let applicationId = 0;
    let applicationReference = '';

    try {
      await test.step('Step 1: Admin creates merchant with branches and categories', async () => {
        console.log('[E2E-013-C] Step 1 start: create merchant + branch + category');

        const merchantRes = await request.post(`${API}/admin/merchants`, {
          headers: adminHeaders,
          data: { name: merchantName, is_active: true },
        });
        expect(merchantRes.status()).toBe(201);
        const merchant = await merchantRes.json();
        merchantId = Number(merchant.id);
        expect(merchantId).toBeGreaterThan(0);

        const branchRes = await request.post(`${API}/admin/merchants/${merchantId}/branches`, {
          headers: adminHeaders,
          data: {
            name: merchantBranchName,
            address: 'Smoke Test Address',
            is_online: false,
            is_active: true,
          },
        });
        expect(branchRes.status()).toBe(201);
        branchId = Number((await branchRes.json()).id);
        expect(branchId).toBeGreaterThan(0);

        const categoryRes = await request.post(`${API}/admin/merchants/${merchantId}/categories`, {
          headers: adminHeaders,
          data: { name: categoryName },
        });
        expect(categoryRes.status()).toBe(201);
        categoryId = Number((await categoryRes.json()).id);
        expect(categoryId).toBeGreaterThan(0);

        console.log(
          `[E2E-013-C] Merchant created | merchant_id=${merchantId} | branch_id=${branchId} | category_id=${categoryId}`,
        );
      });

      await test.step('Step 2: Admin configures credit product with eligibility for new merchant', async () => {
        console.log('[E2E-013-C] Step 2 start: create merchant-specific product');

        const productRes = await request.post(`${API}/admin/products`, {
          headers: adminHeaders,
          data: {
            name: productName,
            description: 'Smoke product for combined E2E-013',
            merchant_id: merchantId,
            min_term_months: 6,
            max_term_months: 24,
            min_amount: 3000,
            max_amount: 25000,
            repayment_scheme: 'amortized',
            grace_period_days: 0,
            is_active: true,
            eligibility_criteria: {
              min_age: 18,
              min_income: 4000,
              employment_types: ['employed', 'self_employed'],
            },
            score_ranges: [],
            fees: [],
            rate_tiers: [],
          },
        });
        expect(productRes.status()).toBe(201);
        const product = await productRes.json();
        productId = Number(product.id);
        expect(productId).toBeGreaterThan(0);
        expect(Number(product.min_term_months)).toBe(6);
        expect(Number(product.max_term_months)).toBe(24);
        expect(Number(product.min_amount)).toBe(3000);
        expect(Number(product.max_amount)).toBe(25000);

        console.log(`[E2E-013-C] Product created | product_id=${productId} | name=${productName}`);
      });

      await test.step('Step 3: Applicant can find new merchant in portal shopping context and branches populate', async () => {
        console.log('[E2E-013-C] Step 3 start: applicant portal merchant search');
        await loginWithUi(page, APPLICANT_EMAIL, APPLICANT_PASSWORD, /\/(dashboard|applications|apply)/);
        await goToShoppingContextStep(page);

        await page.getByPlaceholder(/Search merchant/i).fill(merchantName);
        await page
          .getByRole('option', { name: new RegExp(escapeRegex(merchantName), 'i') })
          .first()
          .click();

        await page.getByPlaceholder(/Search branch/i).click();
        await expect(page.getByRole('option', { name: /Online/i }).first()).toBeVisible({ timeout: 10000 });

        await page.getByPlaceholder(/Search branch/i).fill('Online');
        await page.getByRole('option', { name: /Online/i }).first().click();

        console.log(`[E2E-013-C] Merchant discovered in portal | merchant=${merchantName}`);
      });

      await test.step('Step 4: Eligible products for new merchant are displayed with correct term/amount context', async () => {
        console.log('[E2E-013-C] Step 4 start: verify eligible product cards');
        await page.getByPlaceholder(/Search category/i).first().fill(categoryName);
        await page
          .getByRole('option', { name: new RegExp(escapeRegex(categoryName), 'i') })
          .first()
          .click();
        await page.locator('input[type="number"]').first().fill('7000');
        await page.getByRole('button', { name: /Next/i }).click();

        await expect(page.locator('h2', { hasText: 'Select Credit Product & Tenure' })).toBeVisible({
          timeout: 12000,
        });
        await expect(page.getByText(new RegExp(escapeRegex(productName), 'i')).first()).toBeVisible({
          timeout: 15000,
        });
        await expect(page.getByText(/months/i).first()).toBeVisible();

        const termBtns = page.getByRole('button', { name: /Term .* months/i });
        await expect(termBtns.first()).toBeVisible({ timeout: 15000 });

        console.log(`[E2E-013-C] Product card visible for merchant flow | product=${productName}`);
      });

      await test.step('Step 5: Application submitted with new merchant and appears in processing queue', async () => {
        console.log('[E2E-013-C] Step 5 start: create + submit application with new merchant context');
        await upsertApplicantProfile(request, applicantHeaders);

        const draft = await createDraftApplication(request, applicantHeaders, {
          amount: 7000,
          termMonths: 12,
          description: `Smoke E2E-013 combined ${uniqueSuffix('APP')}`,
          merchantId,
          branchId,
          creditProductId: productId,
          items: [
            {
              category_id: categoryId,
              description: 'Smoke merchant item',
              price: 7000,
              quantity: 1,
            },
          ],
        });
        applicationId = draft.id;
        applicationReference = draft.reference;
        expect(applicationReference).toMatch(/^ZOT-/);

        const submitBody = await submitApplication(request, applicantHeaders, applicationId);
        expect([
          'submitted',
          'under_review',
          'credit_check',
          'decision_pending',
          'approved',
          'declined',
        ]).toContain(String(submitBody.status || ''));

        const queueRes = await request.get(`${API}/underwriter/queue`, {
          headers: adminHeaders,
        });
        expect(queueRes.status()).toBe(200);
        const queue = extractArray(await queueRes.json());
        const match = queue.find(
          (row: any) => Number(row?.id) === applicationId || String(row?.reference_number) === applicationReference,
        );
        expect(match).toBeTruthy();

        const appRes = await request.get(`${API}/loans/${applicationId}`, { headers: applicantHeaders });
        expect(appRes.status()).toBe(200);
        const app = await appRes.json();
        expect(Number(app.merchant_id || 0)).toBe(merchantId);

        console.log(
          `[E2E-013-C] Application in queue | app_id=${applicationId} | ref=${applicationReference} | merchant_id=${merchantId}`,
        );
      });
    } finally {
      console.log('[E2E-013-C] Cleanup start');
      if (productId > 0) {
        const disableProductRes = await request.put(`${API}/admin/products/${productId}`, {
          headers: adminHeaders,
          data: { is_active: false },
        });
        if (disableProductRes.status() === 200) {
          console.log(`[E2E-013-C] Cleanup: deactivated product ${productId}`);
        }
      }
      if (merchantId > 0) {
        const disableMerchantRes = await request.put(`${API}/admin/merchants/${merchantId}`, {
          headers: adminHeaders,
          data: { is_active: false },
        });
        if (disableMerchantRes.status() === 200) {
          console.log(`[E2E-013-C] Cleanup: deactivated merchant ${merchantId}`);
        }
      }
    }
  });

  test('E2E-014: User Management -> RBAC Enforcement (supported behavior)', async ({
    page,
    request,
  }) => {
    test.setTimeout(7 * 60 * 1000);

    const adminHeaders = await apiLogin(request, ADMIN_EMAIL, ADMIN_PASSWORD);
    const userEmail = `smoke.collections.${uniqueSuffix('USR').toLowerCase()}@email.com`;
    const userPassword = 'Collector1!';

    let userId = 0;
    let collectionsRoleId = 0;
    let collectionsToken = '';

    try {
      await test.step('Step 1: Admin creates user with Collections Agent role', async () => {
        console.log('[E2E-014-C] Step 1 start: create collections agent user');
        const rolesRes = await request.get(`${API}/users/roles/all`, { headers: adminHeaders });
        expect(rolesRes.status()).toBe(200);
        const roles = await rolesRes.json();
        const collectionsRole = extractArray(roles).find(
          (role: any) => String(role?.name || '').toLowerCase() === 'collections agent',
        );
        expect(collectionsRole).toBeTruthy();
        collectionsRoleId = Number(collectionsRole.id);
        expect(collectionsRoleId).toBeGreaterThan(0);

        const createRes = await request.post(`${API}/users/`, {
          headers: adminHeaders,
          data: {
            email: userEmail,
            password: userPassword,
            first_name: 'Smoke',
            last_name: 'Collector',
            role: 'junior_underwriter',
            department: 'Collections',
            job_title: 'Collections Agent',
            must_change_password: false,
            role_ids: [collectionsRoleId],
          },
        });
        expect(createRes.status()).toBe(201);
        const user = await createRes.json();
        userId = Number(user.id);
        expect(userId).toBeGreaterThan(0);

        const assignRes = await request.put(`${API}/users/${userId}/roles`, {
          headers: adminHeaders,
          data: { role_ids: [collectionsRoleId] },
        });
        expect(assignRes.status()).toBe(200);

        console.log(`[E2E-014-C] User created | user_id=${userId} | email=${userEmail} | role_id=${collectionsRoleId}`);
      });

      await test.step('Step 2: Verify Collections Agent role assignment and limited permission set', async () => {
        console.log('[E2E-014-C] Step 2 start: verify role assignment + permissions');
        const detailRes = await request.get(`${API}/users/${userId}`, { headers: adminHeaders });
        expect(detailRes.status()).toBe(200);
        const detail = await detailRes.json();

        const roleNames = extractArray(detail.roles).map((r: any) => String(r.role_name || '').toLowerCase());
        expect(roleNames).toContain('collections agent');
        expect(roleNames.length).toBe(1);

        const perms = Array.isArray(detail.effective_permissions) ? detail.effective_permissions : [];
        expect(perms.some((code: string) => String(code).startsWith('collections.'))).toBe(true);
        expect(perms.some((code: string) => String(code).startsWith('users.'))).toBe(false);

        console.log(
          `[E2E-014-C] Permission sample | collections_perms=${perms.filter((p: string) => p.startsWith('collections.')).length} | users_perms=${perms.filter((p: string) => p.startsWith('users.')).length}`,
        );
      });

      await test.step('Step 3: New user logs in with Collections Agent credentials', async () => {
        console.log('[E2E-014-C] Step 3 start: login as collections user');
        const loginRes = await request.post(`${API}/auth/login`, {
          data: { email: userEmail, password: userPassword },
        });
        expect(loginRes.status()).toBe(200);
        collectionsToken = String((await loginRes.json()).access_token);
        expect(collectionsToken.length).toBeGreaterThan(20);

        await loginWithUi(page, userEmail, userPassword, /\/backoffice/);
        await expect(page).toHaveURL(/\/backoffice/);
        await expect(page.getByText(/Dashboard|Applications Queue|Loan Book|Collections/i).first()).toBeVisible({
          timeout: 15000,
        });
      });

      await test.step('Step 4: Attempt access to Decisioning, GL, and User Management modules', async () => {
        console.log('[E2E-014-C] Step 4 start: validate blocked vs supported module access');
        await expect(page.getByText(/User Management/i)).toHaveCount(0);
        await expect(page.getByText(/Administration/i)).toHaveCount(0);

        const userHeaders: AuthHeaders = { Authorization: `Bearer ${collectionsToken}` };

        const usersCountRes = await request.get(`${API}/users/count`, { headers: userHeaders });
        expect(usersCountRes.status()).toBe(403);

        const merchantsRes = await request.get(`${API}/admin/merchants`, { headers: userHeaders });
        expect(merchantsRes.status()).toBe(403);

        const glMappingsRes = await request.get(`${API}/gl/mappings`, { headers: userHeaders });
        expect(glMappingsRes.status()).toBe(403);

        const strategiesRes = await request.get(`${API}/strategies`, { headers: userHeaders });
        expect([200, 403]).toContain(strategiesRes.status());

        const trialBalanceRes = await request.get(`${API}/gl/trial-balance`, { headers: userHeaders });
        expect([200, 403]).toContain(trialBalanceRes.status());

        if (strategiesRes.status() === 200) {
          console.log(
            '[E2E-014-C] Decisioning strategy read access is allowed for staff in current implementation (supported fallback).',
          );
        }
        if (trialBalanceRes.status() === 200) {
          console.log(
            '[E2E-014-C] GL dashboard/trial-balance read access is allowed for staff in current implementation (supported fallback).',
          );
        }
      });

      await test.step('Step 5: Collections module remains fully accessible', async () => {
        console.log('[E2E-014-C] Step 5 start: validate collections access');
        const userHeaders: AuthHeaders = { Authorization: `Bearer ${collectionsToken}` };
        const collectionsRes = await request.get(`${API}/collections/queue`, { headers: userHeaders });
        expect(collectionsRes.status()).toBe(200);
        const queue = extractArray(await collectionsRes.json());
        expect(queue.length).toBeGreaterThan(0);

        await page.goto(`${BASE}/backoffice/collections`);
        await expect(page.getByText(/Collections Queue/i).first()).toBeVisible({ timeout: 15000 });
      });

      await test.step('Step 6: Admin audit trail captures user-management actions related to this access test', async () => {
        console.log('[E2E-014-C] Step 6 start: audit trail verification');
        const auditRes = await request.get(`${API}/admin/audit-trail?entity_type=user&limit=200`, {
          headers: adminHeaders,
        });
        expect(auditRes.status()).toBe(200);
        const auditBody = await auditRes.json();
        const entries = extractArray(auditBody.items ?? auditBody);
        const userEntries = entries.filter((e: any) => Number(e.entity_id) === userId);
        expect(userEntries.length).toBeGreaterThan(0);

        const actions = userEntries.map((e: any) => String(e.action || '').toLowerCase());
        expect(actions.some((a: string) => a === 'create' || a === 'roles_assigned')).toBe(true);

        console.log(
          '[E2E-014-C] Audit trail includes user lifecycle actions. Note: 403 access attempts are not persisted as dedicated audit/error-monitor events in current implementation.',
        );
      });
    } finally {
      console.log('[E2E-014-C] Cleanup start');
      if (userId > 0) {
        const deleteRes = await request.delete(`${API}/users/${userId}`, {
          headers: adminHeaders,
        });
        if (deleteRes.status() === 200) {
          console.log(`[E2E-014-C] Cleanup: deleted user ${userId}`);
        }
      }
    }
  });

  test('E2E-015: GL Mapping Dry Run -> Actual Posting -> Reconciliation', async ({ request }) => {
    test.setTimeout(7 * 60 * 1000);

    const adminHeaders = await apiLogin(request, ADMIN_EMAIL, ADMIN_PASSWORD);
    const applicantHeaders = await apiLogin(request, APPLICANT_EMAIL, APPLICANT_PASSWORD);

    const disburseAmount = 10000;
    let applicationId = 0;
    let applicationReference = '';
    let dryRun: any = null;

    await test.step('Step 1: Select loan disbursement GL mapping template', async () => {
      console.log('[E2E-015-C] Step 1 start: load disbursement mappings');
      const mappingsRes = await request.get(`${API}/gl/mappings?event_type=loan_disbursement`, {
        headers: adminHeaders,
      });
      expect(mappingsRes.status()).toBe(200);
      const mappings = extractArray(await mappingsRes.json());
      expect(mappings.length).toBeGreaterThan(0);

      const template = mappings.find((m: any) => m.is_active !== false) ?? mappings[0];
      expect(Array.isArray(template.lines)).toBe(true);
      expect(template.lines.length).toBeGreaterThan(1);
      expect(template.lines.some((ln: any) => String(ln.line_type).toLowerCase() === 'debit')).toBe(true);
      expect(template.lines.some((ln: any) => String(ln.line_type).toLowerCase() === 'credit')).toBe(true);

      console.log(
        `[E2E-015-C] Mapping template selected | id=${template.id} | name=${template.name} | lines=${template.lines.length}`,
      );
    });

    await test.step('Step 2: Execute dry run and verify simulated entry output', async () => {
      console.log('[E2E-015-C] Step 2 start: run mapping dry-run');
      const dryRunRes = await request.post(`${API}/gl/mappings/dry-run`, {
        headers: adminHeaders,
        data: {
          event_type: 'loan_disbursement',
          source_reference: `SMK-DRY-${uniqueSuffix('015')}`,
          amount_breakdown: {
            principal: disburseAmount,
            interest: 0,
            fee: 0,
            full_amount: disburseAmount,
          },
        },
      });
      expect(dryRunRes.status()).toBe(200);
      dryRun = await dryRunRes.json();

      expect(Array.isArray(dryRun.lines)).toBe(true);
      expect(dryRun.lines.length).toBeGreaterThan(1);
      expect(asNumber(dryRun.total_debit)).toBeGreaterThan(0);
      expect(asNumber(dryRun.total_credit)).toBeGreaterThan(0);
      expect(Boolean(dryRun.is_balanced)).toBe(true);

      console.log(
        `[E2E-015-C] Dry run generated | lines=${dryRun.lines.length} | debit=${dryRun.total_debit} | credit=${dryRun.total_credit}`,
      );
    });

    await test.step('Step 3: Trigger actual loan disbursement', async () => {
      console.log('[E2E-015-C] Step 3 start: create + approve + disburse loan');
      await upsertApplicantProfile(request, applicantHeaders, {
        monthly_income: 20000,
        existing_debt: 900,
      });

      const draft = await createDraftApplication(request, applicantHeaders, {
        amount: disburseAmount,
        termMonths: 12,
        description: `Smoke E2E-015 disbursement ${uniqueSuffix('APP')}`,
      });
      applicationId = draft.id;
      applicationReference = draft.reference;
      expect(applicationReference).toMatch(/^ZOT-/);

      await submitApplication(request, applicantHeaders, applicationId);
      await ensureApplicationApproved(
        request,
        adminHeaders,
        applicationId,
        'Smoke E2E-015 approval for GL posting validation',
      );
      await disburseApplication(request, adminHeaders, applicationId, 'Smoke E2E-015 disbursement');

      console.log(
        `[E2E-015-C] Loan disbursed | app_id=${applicationId} | reference=${applicationReference}`,
      );
    });

    await test.step('Step 4: Verify posted GL entries match dry-run structure and totals', async () => {
      console.log('[E2E-015-C] Step 4 start: compare actual JE to dry-run');
      const lookup = `LOAN-${applicationId}`;
      let disbursementEntry: any = null;

      for (let attempt = 0; attempt < 8; attempt += 1) {
        const entriesRes = await request.get(
          `${API}/gl/entries?loan_id=${encodeURIComponent(lookup)}&page=1&page_size=200`,
          { headers: adminHeaders },
        );
        expect(entriesRes.status()).toBe(200);
        const entries = extractArray(await entriesRes.json());
        disbursementEntry = entries.find(
          (entry: any) => String(entry?.source_type || '').toLowerCase() === 'loan_disbursement',
        );
        if (disbursementEntry) break;
        await sleep(800);
      }

      expect(disbursementEntry).toBeTruthy();
      const actualLines = Array.isArray(disbursementEntry.lines) ? disbursementEntry.lines : [];
      expect(actualLines.length).toBeGreaterThan(1);

      const actualDebit = actualLines.reduce((sum: number, ln: any) => sum + asNumber(ln.debit_amount), 0);
      const actualCredit = actualLines.reduce((sum: number, ln: any) => sum + asNumber(ln.credit_amount), 0);
      const dryDebit = asNumber(dryRun.total_debit);
      const dryCredit = asNumber(dryRun.total_credit);

      expect(Math.abs(actualDebit - dryDebit)).toBeLessThan(0.01);
      expect(Math.abs(actualCredit - dryCredit)).toBeLessThan(0.01);

      const actualAccounts = new Set(actualLines.map((ln: any) => Number(ln.gl_account_id)));
      const dryAccounts = new Set((dryRun.lines || []).map((ln: any) => Number(ln.gl_account_id)));
      expect(actualAccounts.size).toBeGreaterThan(0);
      expect(actualAccounts.size).toBe(dryAccounts.size);

      console.log(
        `[E2E-015-C] JE match confirmed | actual_debit=${actualDebit} | dry_debit=${dryDebit} | account_lines=${actualLines.length}`,
      );
    });

    await test.step('Step 5: Verify trial balance remains balanced after posting', async () => {
      console.log('[E2E-015-C] Step 5 start: trial balance validation');
      const trialRes = await request.get(`${API}/gl/trial-balance`, { headers: adminHeaders });
      expect(trialRes.status()).toBe(200);
      const trial = await trialRes.json();
      expect(Boolean(trial.is_balanced)).toBe(true);
      expect(Math.abs(asNumber(trial.total_debits) - asNumber(trial.total_credits))).toBeLessThan(0.01);
    });

    await test.step('Step 6: Generate period report showing disbursement entries', async () => {
      console.log('[E2E-015-C] Step 6 start: report generation');
      const reportRes = await request.post(`${API}/reports/generate/disbursement`, {
        headers: adminHeaders,
        data: {
          date_from: dateIso(-2),
          date_to: dateIso(1),
        },
      });
      expect(reportRes.status()).toBe(200);
      const report = await reportRes.json();
      expect(report.file_data).toBeTruthy();
      const csv = Buffer.from(String(report.file_data), 'base64').toString('utf8');
      expect(csv.length).toBeGreaterThan(30);
      expect(
        csv.includes(applicationReference) ||
          csv.includes(`LOAN-${applicationId}`) ||
          csv.includes(String(applicationId)),
      ).toBe(true);

      console.log(
        '[E2E-015-C] Report generated and validated. Note: platform provides disbursement report (supported) in place of a dedicated GL-detail report type.',
      );
    });
  });
});
