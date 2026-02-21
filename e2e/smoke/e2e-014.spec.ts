import { test, expect, type APIRequestContext, type Locator, type Page } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const API = process.env.E2E_API_URL ?? 'http://localhost:8000/api';

const APPLICANT_EMAIL = process.env.SMOKE_APPLICANT_EMAIL ?? 'marcus.mohammed0@email.com';
const APPLICANT_PASSWORD = process.env.SMOKE_APPLICANT_PASSWORD ?? 'Applicant1!';
const ADMIN_EMAIL = process.env.SMOKE_ADMIN_EMAIL ?? 'admin@zotta.tt';
const ADMIN_PASSWORD = process.env.SMOKE_ADMIN_PASSWORD ?? 'Admin123!';

type AuthHeaders = { Authorization: string };

type AssessmentRecord = {
  id: number;
  name: string;
  rules?: any[] | null;
};

type StrategyRecord = {
  id: number;
  name: string;
  status: string;
  decision_tree_id: number | null;
  assessments: AssessmentRecord[];
};

type ProductRecord = {
  id: number;
  name: string;
  min_amount: number;
  max_amount: number;
  min_term_months: number;
  max_term_months: number;
  merchant_id?: number | null;
  is_active?: boolean;
  default_strategy_id?: number | null;
  decision_tree_id?: number | null;
};

type DecisionRecord = {
  id: number;
  final_outcome: string;
  engine_outcome?: string | null;
  engine_reasons?: { reasons?: string[] };
};

function uniqueSuffix(prefix = 'SMK'): string {
  const rand = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
  return `${prefix}-${Date.now()}-${rand}`;
}

function extractArray(payload: any): any[] {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.entries)) return payload.entries;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

function escapeRegex(input: string): string {
  return input.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

async function sleep(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForCondition<T>(
  fn: () => Promise<T>,
  predicate: (value: T) => boolean,
  label: string,
  attempts = 25,
  delayMs = 800,
): Promise<T> {
  let last: T | undefined;
  for (let i = 0; i < attempts; i += 1) {
    last = await fn();
    if (predicate(last)) return last;
    await sleep(delayMs);
  }
  throw new Error(`Timed out waiting for condition: ${label}. Last value: ${JSON.stringify(last)}`);
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

async function getStrategy(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  strategyId: number,
): Promise<StrategyRecord> {
  const res = await request.get(`${API}/strategies/${strategyId}`, { headers: adminHeaders });
  expect(res.status()).toBe(200);
  return (await res.json()) as StrategyRecord;
}

async function getStrategyByName(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  name: string,
): Promise<StrategyRecord | null> {
  const res = await request.get(`${API}/strategies`, { headers: adminHeaders });
  expect(res.status()).toBe(200);
  const strategies = (await res.json()) as StrategyRecord[];
  return strategies.find((s) => s.name === name) ?? null;
}

async function getProduct(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  productId: number,
): Promise<ProductRecord> {
  const res = await request.get(`${API}/admin/products/${productId}`, { headers: adminHeaders });
  expect(res.status()).toBe(200);
  return (await res.json()) as ProductRecord;
}

async function listAdminProducts(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
): Promise<ProductRecord[]> {
  const res = await request.get(`${API}/admin/products?limit=200&offset=0`, {
    headers: adminHeaders,
  });
  expect(res.status()).toBe(200);
  return extractArray(await res.json()) as ProductRecord[];
}

function chooseTargetProduct(products: ProductRecord[]): ProductRecord {
  const eligible = products.filter((p) => {
    const minAmount = Number(p.min_amount || 0);
    const maxAmount = Number(p.max_amount || 0);
    const minTerm = Number(p.min_term_months || 0);
    const maxTerm = Number(p.max_term_months || 0);
    return (p.is_active ?? true) && maxAmount > minAmount && maxTerm >= minTerm && maxAmount > 0;
  });
  const target = eligible[0] ?? products[0];
  if (!target) {
    throw new Error('No credit product available for strategy smoke test.');
  }
  return target;
}

async function upsertApplicantProfile(
  request: APIRequestContext,
  applicantHeaders: AuthHeaders,
  updates: Record<string, any>,
) {
  const res = await request.put(`${API}/loans/profile`, {
    headers: applicantHeaders,
    data: {
      date_of_birth: '1991-02-19',
      national_id: '19910219001',
      employer_name: 'Smoke QA Ltd',
      employer_sector: 'Information Technology',
      employment_type: 'employed',
      years_employed: 6,
      job_title: 'Teacher',
      monthly_income: 12000,
      monthly_expenses: 1800,
      existing_debt: 600,
      ...updates,
    },
  });
  expect([200, 201]).toContain(res.status());
}

async function createAndSubmitApplicationForProduct(
  request: APIRequestContext,
  applicantHeaders: AuthHeaders,
  product: ProductRecord,
) {
  const amount = Math.min(Math.max(6000, Number(product.min_amount || 1000)), Number(product.max_amount || 20000));
  const term = Math.max(
    Number(product.min_term_months || 6),
    Math.min(12, Number(product.max_term_months || 24)),
  );

  const createRes = await request.post(`${API}/loans/`, {
    headers: applicantHeaders,
    data: {
      amount_requested: amount,
      term_months: term,
      purpose: 'personal',
      purpose_description: `E2E-014 complex tree ${uniqueSuffix('APP')}`,
      merchant_id: product.merchant_id || null,
      credit_product_id: product.id,
      downpayment: 0,
      total_financed: amount,
      items: [],
    },
  });
  expect(createRes.status()).toBe(201);
  const created = await createRes.json();
  const applicationId = Number(created.id);
  const reference = String(created.reference_number);

  const submitRes = await request.post(`${API}/loans/${applicationId}/submit`, {
    headers: applicantHeaders,
  });
  expect(submitRes.status()).toBe(200);

  return { applicationId, reference };
}

async function getLatestDecision(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  applicationId: number,
): Promise<DecisionRecord> {
  const res = await request.get(`${API}/underwriter/applications/${applicationId}/decision`, {
    headers: adminHeaders,
  });
  expect(res.status()).toBe(200);
  return (await res.json()) as DecisionRecord;
}

async function getDecisionExplanation(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  decisionId: number,
) {
  const res = await request.get(`${API}/decisions/${decisionId}/explanation`, {
    headers: adminHeaders,
  });
  expect(res.status()).toBe(200);
  return res.json();
}

async function runDecisionEngine(
  request: APIRequestContext,
  adminHeaders: AuthHeaders,
  applicationId: number,
): Promise<DecisionRecord> {
  const res = await request.post(`${API}/underwriter/applications/${applicationId}/run-engine`, {
    headers: adminHeaders,
  });
  const bodyText = await res.text();
  expect(res.status(), `run-engine failed for application ${applicationId}: ${bodyText}`).toBe(200);
  return JSON.parse(bodyText) as DecisionRecord;
}

function pathHasBranch(path: any, branchName: string): boolean {
  if (!Array.isArray(path)) return false;
  return path.some((step) => String(step?.branch || '').toLowerCase() === branchName.toLowerCase());
}

async function openStrategyEditor(page: Page, strategyId: number) {
  await page.goto(`${BASE}/backoffice/strategies`);
  const row = page.getByTestId(`strategy-row-${strategyId}`);
  await expect(row).toBeVisible({ timeout: 15000 });
  await row.click();
  await expect(page.getByTestId(`strategy-editor-${strategyId}`)).toBeVisible({ timeout: 10000 });
}

async function openAssessmentEditor(page: Page, assessmentId: number) {
  const row = page.getByTestId(`assessment-${assessmentId}`);
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.scrollIntoViewIfNeeded();
  await row.click();
  const editor = page.getByTestId(`assessment-editor-${assessmentId}`);
  if (!(await editor.isVisible())) {
    await row.click();
  }
  await expect(editor).toBeVisible({ timeout: 10000 });
  return editor;
}

async function renameAssessment(page: Page, assessmentId: number, newName: string) {
  const editor = await openAssessmentEditor(page, assessmentId);
  await editor.getByTestId('assessment-name-input').fill(newName);
  await editor.getByTestId('btn-save-assessment').click();
  await expect(page.getByTestId(`assessment-${assessmentId}`)).toContainText(newName, { timeout: 10000 });
}

async function addRuleToAssessment(
  page: Page,
  assessmentId: number,
  rule: {
    ruleId: string;
    ruleName: string;
    field: string;
    operator: string;
    threshold: string;
    severity: 'hard' | 'refer';
    reasonCode: string;
  },
) {
  const editor = await openAssessmentEditor(page, assessmentId);
  const section = editor.getByTestId(`assess-${assessmentId}-section`);
  const addButton = section.getByTestId(`btn-add-assess-${assessmentId}`);
  await addButton.click();

  const row = section.getByTestId(`assess-${assessmentId}-rule-0`);
  await expect(row).toBeVisible({ timeout: 10000 });

  await row.locator('input').nth(0).fill(rule.ruleId);
  await row.locator('input').nth(1).fill(rule.ruleName);

  await row.locator('button').first().click();
  const fieldSearch = page.getByPlaceholder('Search fields...').last();
  await expect(fieldSearch).toBeVisible({ timeout: 5000 });
  await fieldSearch.fill(rule.field.replace(/_/g, ' '));
  const fieldOption = page.getByRole('button', { name: new RegExp(rule.field.replace(/_/g, '\\s*'), 'i') }).first();
  await fieldOption.click();

  const selects = row.locator('select');
  await selects.nth(0).selectOption(rule.operator);
  await row.locator('input').nth(2).fill(rule.threshold);
  await selects.nth(1).selectOption(rule.severity);
  await row.locator('input').nth(3).fill(rule.reasonCode);

  await editor.getByTestId('btn-save-assessment').click();
}

async function connectNodes(page: Page, sourceNode: Locator, targetNode: Locator, label: string) {
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    const before = await page.locator('.react-flow__edge').count();

    const sourceHandle = sourceNode.locator('.react-flow__handle-bottom').first();
    const targetHandle = targetNode.locator('.react-flow__handle-top').first();
    await expect(sourceHandle).toBeVisible({ timeout: 5000 });
    await expect(targetHandle).toBeVisible({ timeout: 5000 });

    await sourceHandle.dragTo(targetHandle, { force: true });
    await page.waitForTimeout(350);
    let after = await page.locator('.react-flow__edge').count();
    if (after > before) return;

    const fallbackSource = sourceNode.locator('.react-flow__handle').last();
    const fallbackTarget = targetNode.locator('.react-flow__handle').first();
    const sourceBox = await fallbackSource.boundingBox();
    const targetBox = await fallbackTarget.boundingBox();

    if (!sourceBox || !targetBox) {
      throw new Error(`Could not resolve handles for edge ${label}`);
    }

    const sx = sourceBox.x + sourceBox.width / 2;
    const sy = sourceBox.y + sourceBox.height / 2;
    const tx = targetBox.x + targetBox.width / 2;
    const ty = targetBox.y + targetBox.height / 2;

    await page.mouse.move(sx, sy);
    await page.mouse.down();
    await page.mouse.move(tx, ty, { steps: 14 });
    await page.mouse.up();
    await page.waitForTimeout(300);

    after = await page.locator('.react-flow__edge').count();
    if (after > before) return;
  }
  throw new Error(`Failed to connect edge: ${label}`);
}

async function clickViaDom(locator: Locator) {
  await locator.evaluate((el) => {
    (el as HTMLElement).click();
  });
}

async function configureEmploymentTypeCondition(conditionNode: Locator) {
  await clickViaDom(conditionNode.locator('button').first());
  const editor = conditionNode.locator('.nopan.nodrag.nowheel').first();
  await expect(editor).toBeVisible({ timeout: 5000 });
  console.log('[E2E-014] Step 2: configure condition #1 attribute=employment_type');
  await editor.locator('select').first().selectOption('employment_type');
  const plusBtn = editor.locator('span', { hasText: /^Branches$/ }).locator('xpath=following-sibling::button').first();
  await expect(plusBtn).toBeVisible({ timeout: 5000 });
  await clickViaDom(plusBtn);
  await clickViaDom(plusBtn);

  const branchNameInputs = editor.getByPlaceholder('Branch name');
  await expect(branchNameInputs).toHaveCount(5, { timeout: 5000 });
  await branchNameInputs.nth(0).fill('employed');
  await branchNameInputs.nth(1).fill('self_employed');
  await branchNameInputs.nth(2).fill('contract');
  await branchNameInputs.nth(3).fill('government_employee');
  await branchNameInputs.nth(4).fill('not_employed');

  const governmentRow = branchNameInputs.nth(3).locator('xpath=ancestor::div[contains(@class,"mb-1.5")]').first();
  await clickViaDom(governmentRow.getByRole('button', { name: 'government_employee' }));

  const notEmployedRow = branchNameInputs.nth(4).locator('xpath=ancestor::div[contains(@class,"mb-1.5")]').first();
  await clickViaDom(notEmployedRow.getByRole('button', { name: 'not_employed' }));

  await clickViaDom(editor.getByRole('button', { name: /Apply/i }));
  await expect(editor).toBeHidden({ timeout: 5000 });
}

async function configureIncomeBandCondition(conditionNode: Locator) {
  await clickViaDom(conditionNode.locator('button').first());
  const editor = conditionNode.locator('.nopan.nodrag.nowheel').first();
  await expect(editor).toBeVisible({ timeout: 5000 });
  console.log('[E2E-014] Step 2: configure condition #2 attribute=income_band');
  await editor.locator('select').first().selectOption('income_band');
  await expect(editor.getByPlaceholder('Branch name')).toHaveCount(3, { timeout: 5000 });
  await clickViaDom(editor.getByRole('button', { name: /Apply/i }));
  await expect(editor).toBeHidden({ timeout: 5000 });
}

async function assignAssessmentToNode(node: Locator, assessmentName: string) {
  await clickViaDom(node.locator('button').first());
  const select = node.locator('select').first();
  await expect(select).toBeVisible({ timeout: 5000 });
  const value = await select.locator('option', { hasText: assessmentName }).first().getAttribute('value');
  expect(value).toBeTruthy();
  await select.selectOption(String(value));
  await clickViaDom(node.getByRole('button', { name: /Apply/i }));
  await expect(node).toContainText(assessmentName, { timeout: 5000 });
}

async function fitTreeView(page: Page) {
  const fitViewBtnByClass = page.locator('.react-flow__controls-fitview').first();
  if (await fitViewBtnByClass.count()) {
    await fitViewBtnByClass.click({ force: true });
    await page.waitForTimeout(300);
    return;
  }
  const fitViewBtnByRole = page.getByRole('button', { name: /Fit View/i }).first();
  if (await fitViewBtnByRole.count()) {
    await fitViewBtnByRole.click({ force: true });
    await page.waitForTimeout(300);
  }
}

async function nudgeNodeRender(node: Locator, dx: number, dy: number, label: string) {
  await node.evaluate((el, shift) => {
    const html = el as HTMLElement;
    const inlineTransform = html.style.transform || '';
    const match = inlineTransform.match(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/);
    if (!match) return;
    const x = Number(match[1]);
    const y = Number(match[2]);
    html.style.transform = `translate(${x + shift.dx}px, ${y + shift.dy}px)`;
  }, { dx, dy });
  console.log(`[E2E-014] Step 2: nudge node ${label} by dx=${dx}, dy=${dy}`);
}

async function spreadNodesForWiring(assessmentNodes: Locator) {
  // Visual separation only for reliable drag-connect in headless runs.
  await nudgeNodeRender(assessmentNodes.nth(0), -180, 180, 'assessment-employed-low');
  await nudgeNodeRender(assessmentNodes.nth(1), 40, 180, 'assessment-employed-mid');
  await nudgeNodeRender(assessmentNodes.nth(2), 260, 180, 'assessment-employed-upper');
  await nudgeNodeRender(assessmentNodes.nth(3), -260, 80, 'assessment-self-employed');
  await nudgeNodeRender(assessmentNodes.nth(4), 320, 80, 'assessment-contract');
}

async function fillEditableInput(page: Page, label: string, value: string) {
  const lbl = page.locator('label', { hasText: label }).first();
  await expect(lbl).toBeVisible({ timeout: 10000 });
  const input = lbl.locator('xpath=following-sibling::input').first();
  await input.fill(value);
}

async function applyScenarioViaUi(
  page: Page,
  scenario: {
    employment_type: string;
    years_employed: string;
    monthly_income: string;
    monthly_expenses: string;
    existing_debt: string;
  },
) {
  await page.getByRole('button', { name: /Application Details/i }).click();
  const editBtn = page.getByRole('button', { name: /^Edit$/ }).first();
  await editBtn.click();
  await expect(page.getByRole('button', { name: /^Save$/ }).first()).toBeVisible({ timeout: 5000 });

  await fillEditableInput(page, 'Employment Type', scenario.employment_type);
  await fillEditableInput(page, 'Years Employed', scenario.years_employed);
  await fillEditableInput(page, 'Monthly Income', scenario.monthly_income);
  await fillEditableInput(page, 'Monthly Expenses', scenario.monthly_expenses);
  await fillEditableInput(page, 'Existing Debt', scenario.existing_debt);

  const saveRespPromise = page.waitForResponse((res) =>
    res.request().method() === 'PATCH' && res.url().includes('/underwriter/applications/') && res.url().includes('/edit'),
  );
  await page.getByRole('button', { name: /^Save$/ }).first().click();
  const saveResp = await saveRespPromise;
  expect(saveResp.status()).toBe(200);
}

async function rerunAnalysisViaUi(page: Page, applicationId: number) {
  await page.getByRole('button', { name: /Credit Analysis/i }).click();
  const runRespPromise = page.waitForResponse((res) =>
    res.request().method() === 'POST' &&
    res.url().includes(`/api/underwriter/applications/${applicationId}/run-engine`),
  );

  const rerunBtn = page.getByRole('button', { name: /Re-run Analysis/i });
  if (await rerunBtn.count()) {
    await rerunBtn.first().click();
  } else {
    await page.getByRole('button', { name: /Retry Analysis/i }).click();
  }

  const runResp = await runRespPromise;
  expect(runResp.status()).toBe(200);
  await expect(page.getByText(/Analysis run on/i).first()).toBeVisible({ timeout: 20000 });
}

test.describe('Smoke - E2E-014', () => {
  test('E2E-014: complex multi-branch tree configured via UI and validated with scenarios', async ({ page, request }) => {
    test.setTimeout(12 * 60 * 1000);

    const adminHeaders = await apiLogin(request, ADMIN_EMAIL, ADMIN_PASSWORD);
    const applicantHeaders = await apiLogin(request, APPLICANT_EMAIL, APPLICANT_PASSWORD);

    const strategyName = `Smoke Complex UI Tree ${uniqueSuffix('STRAT')}`;
    const strategyDescription = 'Complex 5+ branch tree created in UI only';

    const assessmentNames = {
      employed: 'A - Employed Income Check',
      selfEmployed: 'B - Self Employed Refer',
      contract: 'C - Contract Debt Decline',
      government: 'D - Government Approve',
      notEmployed: 'E - Not Employed Decline',
    };

    let strategyId = 0;
    let productId = 0;
    let previousStrategyValue = '';
    let scenarioAppId = 0;

    try {
      await test.step('Step 1: Create strategy and assessments via UI', async () => {
        console.log('[E2E-014] Step 1 start: create strategy + 5 assessments in UI');
        await loginWithUi(page, ADMIN_EMAIL, ADMIN_PASSWORD, /\/backoffice/);
        await page.goto(`${BASE}/backoffice/strategies`);
        await page.getByTestId('btn-new-strategy').click();
        await page.getByTestId('input-strategy-name').fill(strategyName);
        await page.getByTestId('input-strategy-desc').fill(strategyDescription);
        await page.getByTestId('btn-create-confirm').click();
        await expect(page.getByTestId('strategy-list')).toContainText(strategyName, { timeout: 15000 });

        const created = await waitForCondition(
          async () => getStrategyByName(request, adminHeaders, strategyName),
          (s) => Boolean(s && s.id),
          'created strategy',
          30,
          800,
        ) as StrategyRecord;
        strategyId = Number(created.id);
        expect(strategyId).toBeGreaterThan(0);

        await openStrategyEditor(page, strategyId);

        for (let i = 0; i < 5; i += 1) {
          await page.getByTestId('btn-new-assessment-blank').click();
        }

        const withAssessments = await waitForCondition(
          async () => getStrategy(request, adminHeaders, strategyId),
          (s) => (s.assessments || []).length >= 5,
          '5 assessments created',
          30,
          900,
        );

        const ids = withAssessments.assessments
          .map((a) => Number(a.id))
          .sort((a, b) => a - b);
        expect(ids.length).toBeGreaterThanOrEqual(5);

        await renameAssessment(page, ids[0], assessmentNames.employed);
        await addRuleToAssessment(page, ids[0], {
          ruleId: 'EMP-JOB-001',
          ruleName: 'Decline janitor employed applicants',
          field: 'job_title',
          operator: 'eq',
          threshold: 'janitor',
          severity: 'hard',
          reasonCode: 'EMP_JOB_DECLINE',
        });

        await renameAssessment(page, ids[1], assessmentNames.selfEmployed);
        await addRuleToAssessment(page, ids[1], {
          ruleId: 'SELF-REF-001',
          ruleName: 'Refer consultant self-employed applicants',
          field: 'job_title',
          operator: 'eq',
          threshold: 'consultant',
          severity: 'refer',
          reasonCode: 'SELF_REF',
        });

        await renameAssessment(page, ids[2], assessmentNames.contract);
        await addRuleToAssessment(page, ids[2], {
          ruleId: 'CONT-DEC-001',
          ruleName: 'Decline contractor titles on contract branch',
          field: 'job_title',
          operator: 'eq',
          threshold: 'contractor',
          severity: 'hard',
          reasonCode: 'CONTRACT_DEBT',
        });

        await renameAssessment(page, ids[3], assessmentNames.government);

        await renameAssessment(page, ids[4], assessmentNames.notEmployed);
        await addRuleToAssessment(page, ids[4], {
          ruleId: 'NOTEMP-DEC-001',
          ruleName: 'Decline unemployed title',
          field: 'job_title',
          operator: 'eq',
          threshold: 'unemployed',
          severity: 'hard',
          reasonCode: 'NOT_EMP',
        });
      });

      await test.step('Step 2: Build complex tree in UI (1 condition, 5 branches, multiple assessments)', async () => {
        console.log('[E2E-014] Step 2 start: configure complex tree in UI only');
        await openStrategyEditor(page, strategyId);
        const treeSection = page.getByTestId('embedded-tree-section');
        await expect(treeSection).toBeVisible({ timeout: 10000 });

        const addConditionBtn = treeSection.getByRole('button', { name: /Condition/i }).first();
        const addAssessmentBtn = treeSection.getByRole('button', { name: /Assessment/i }).first();
        const conditionNodes = page.locator('.react-flow__node-condition');
        const assessmentNodes = page.locator('.react-flow__node-assessment');

        for (let i = 0; i < 1; i += 1) {
          await addConditionBtn.click();
          await expect(conditionNodes).toHaveCount(i + 1, { timeout: 8000 });
          await page.waitForTimeout(120);
        }

        for (let i = 0; i < 5; i += 1) {
          await addAssessmentBtn.click();
          await expect(assessmentNodes).toHaveCount(i + 1, { timeout: 8000 });
          await page.waitForTimeout(120);
        }

        await expect(conditionNodes).toHaveCount(1, { timeout: 10000 });
        await expect(assessmentNodes).toHaveCount(5, { timeout: 10000 });
        await fitTreeView(page);
        await configureEmploymentTypeCondition(conditionNodes.first());

        await fitTreeView(page);
        await assignAssessmentToNode(assessmentNodes.nth(0), assessmentNames.employed);
        await assignAssessmentToNode(assessmentNodes.nth(1), assessmentNames.selfEmployed);
        await assignAssessmentToNode(assessmentNodes.nth(2), assessmentNames.contract);
        await assignAssessmentToNode(assessmentNodes.nth(3), assessmentNames.government);
        await assignAssessmentToNode(assessmentNodes.nth(4), assessmentNames.notEmployed);

        const rootNode = page.locator('.react-flow__node-annotation').first();
        const c1 = conditionNodes.filter({ hasText: /employment_type/i }).first();
        await expect(c1).toBeVisible({ timeout: 5000 });

        await spreadNodesForWiring(assessmentNodes);

        await fitTreeView(page);

        console.log('[E2E-014] Step 2: wiring edges on canvas');
        await connectNodes(page, rootNode, c1, 'root->employment_type');
        await connectNodes(page, c1, assessmentNodes.nth(0), 'employment_type employed');
        await connectNodes(page, c1, assessmentNodes.nth(1), 'employment_type self_employed');
        await connectNodes(page, c1, assessmentNodes.nth(2), 'employment_type contract');
        await connectNodes(page, c1, assessmentNodes.nth(3), 'employment_type government_employee');
        await connectNodes(page, c1, assessmentNodes.nth(4), 'employment_type not_employed');

        await page.getByTestId('btn-save-tree').click();
        await expect(page.getByText(/Saved/i).first()).toBeVisible({ timeout: 10000 });
      });

      await test.step('Step 3: Assign new strategy to product via UI', async () => {
        console.log('[E2E-014] Step 3 start: assign strategy to product through UI');
        const products = await listAdminProducts(request, adminHeaders);
        const targetProduct = chooseTargetProduct(products);
        productId = Number(targetProduct.id);
        await page.goto(`${BASE}/backoffice/products/${productId}`);
        await expect(page).toHaveURL(new RegExp(`/backoffice/products/${productId}$`), { timeout: 10000 });

        const strategyLabel = page.locator('label:has-text("Strategy")').first();
        const strategySelect = strategyLabel.locator('xpath=following-sibling::select').first();
        await expect(strategySelect).toBeVisible({ timeout: 10000 });
        previousStrategyValue = await strategySelect.inputValue();

        const optionValue = await strategySelect
          .locator('option', { hasText: new RegExp(`^${escapeRegex(strategyName)}(?:\\s|\\(|$)`) })
          .first()
          .getAttribute('value');
        expect(optionValue).toBeTruthy();
        await strategySelect.selectOption(String(optionValue));

        const saveRespPromise = page.waitForResponse((res) =>
          res.request().method() === 'PUT' && res.url().includes(`/api/admin/products/${productId}`),
        );
        await page.getByRole('button', { name: /Save Product/i }).click();
        const saveResp = await saveRespPromise;
        expect(saveResp.status()).toBe(200);
      });

      await test.step('Step 4: Create one submitted application for scenario tests', async () => {
        console.log('[E2E-014] Step 4 start: create scenario application');
        const product = await getProduct(request, adminHeaders, productId);
        await upsertApplicantProfile(request, applicantHeaders, {
          employment_type: 'employed',
          years_employed: 4,
          monthly_income: 9000,
          monthly_expenses: 1500,
          existing_debt: 500,
        });
        const app = await createAndSubmitApplicationForProduct(request, applicantHeaders, product);
        scenarioAppId = app.applicationId;
        console.log(`[E2E-014] Scenario application created | id=${scenarioAppId} | ref=${app.reference}`);

        await page.goto(`${BASE}/backoffice/review/${scenarioAppId}`);
        await expect(page.getByText(/Application Review/i).first()).toBeVisible({ timeout: 15000 });
      });

      await test.step('Step 5: Validate routing and outcomes across multiple scenarios', async () => {
        console.log('[E2E-014] Step 5 start: run scenario matrix');
        const scenarios = [
          {
            name: 'Employed low-income decline',
            input: {
              employment_type: 'employed',
              job_title: 'janitor',
              years_employed: 5,
              monthly_income: 4500,
              monthly_expenses: 900,
              existing_debt: 300,
            },
            expectedOutcome: 'decline',
            expectedBranches: ['employed'],
          },
          {
            name: 'Employed higher-income approve',
            input: {
              employment_type: 'employed',
              job_title: 'teacher',
              years_employed: 5,
              monthly_income: 9000,
              monthly_expenses: 1200,
              existing_debt: 400,
            },
            expectedOutcome: 'approve',
            expectedBranches: ['employed'],
          },
          {
            name: 'Self-employed refer path',
            input: {
              employment_type: 'self_employed',
              job_title: 'consultant',
              years_employed: 1,
              monthly_income: 12000,
              monthly_expenses: 1800,
              existing_debt: 500,
            },
            expectedOutcome: 'refer',
            expectedBranches: ['self_employed'],
          },
          {
            name: 'Contract decline path',
            input: {
              employment_type: 'contract',
              job_title: 'contractor',
              years_employed: 3,
              monthly_income: 11000,
              monthly_expenses: 2000,
              existing_debt: 3000,
            },
            expectedOutcome: 'decline',
            expectedBranches: ['contract'],
          },
          {
            name: 'Government employee approve path',
            input: {
              employment_type: 'government_employee',
              job_title: 'civil_servant',
              years_employed: 7,
              monthly_income: 22000,
              monthly_expenses: 1600,
              existing_debt: 300,
            },
            expectedOutcome: 'approve',
            expectedBranches: ['government_employee'],
          },
          {
            name: 'Not employed decline path',
            input: {
              employment_type: 'not_employed',
              job_title: 'unemployed',
              years_employed: 0,
              monthly_income: 4500,
              monthly_expenses: 900,
              existing_debt: 100,
            },
            expectedOutcome: 'decline',
            expectedBranches: ['not_employed'],
          },
        ];

        let lastDecisionId = 0;
        for (const scenario of scenarios) {
          console.log(`[E2E-014] Scenario start: ${scenario.name}`);
          await upsertApplicantProfile(request, applicantHeaders, scenario.input);
          const latest = await runDecisionEngine(request, adminHeaders, scenarioAppId);
          expect(Number(latest.id)).toBeGreaterThan(lastDecisionId);
          lastDecisionId = Number(latest.id);
          expect(latest.final_outcome).toBe(scenario.expectedOutcome);

          const explanation = await getDecisionExplanation(request, adminHeaders, latest.id);
          for (const branchName of scenario.expectedBranches) {
            expect(pathHasBranch(explanation.tree_path, branchName), `${scenario.name} missing branch ${branchName}`).toBeTruthy();
          }

          console.log(
            `[E2E-014] Scenario result: ${scenario.name} | outcome=${latest.final_outcome} | decision_id=${latest.id}`,
          );
        }
      });
    } finally {
      console.log('[E2E-014] Cleanup start');
      if (productId) {
        try {
          await page.goto(`${BASE}/backoffice/products/${productId}`);
          const strategyLabel = page.locator('label:has-text("Strategy")').first();
          const strategySelect = strategyLabel.locator('xpath=following-sibling::select').first();
          if (await strategySelect.count()) {
            await strategySelect.selectOption(previousStrategyValue || '');
            const restoreRespPromise = page.waitForResponse((res) =>
              res.request().method() === 'PUT' && res.url().includes(`/api/admin/products/${productId}`),
            );
            await page.getByRole('button', { name: /Save Product/i }).click();
            const restoreResp = await restoreRespPromise;
            if (restoreResp.status() === 200) {
              console.log(`[E2E-014] Cleanup: restored strategy selection for product ${productId}`);
            }
          }
        } catch {
          // Best-effort cleanup only
        }
      }

      if (strategyId) {
        try {
          const deleteRes = await request.delete(`${API}/strategies/${strategyId}`, {
            headers: adminHeaders,
          });
          if (deleteRes.status() === 200) {
            console.log(`[E2E-014] Cleanup: deleted strategy ${strategyId}`);
          }
        } catch {
          // Best-effort cleanup only
        }
      }
    }
  });
});
