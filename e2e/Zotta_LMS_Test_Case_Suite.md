# ZOTTA Loan Management System — Comprehensive Test Case Suite

**Document:** QA Test Case Suite v1.0
**Prepared for:** EveryData / Zotta Platform
**Date:** February 14, 2026
**Total Test Cases:** 128 (91 Positive, 37 Negative)
**Coverage:** 17 Functional Modules

---

## Executive Summary

This document contains 128 test cases designed to provide comprehensive quality assurance coverage for the Zotta Loan Management System. The suite covers the complete loan lifecycle from application origination through credit decisioning, disbursement, repayment, collections, and closure, with specific attention to Caribbean market requirements including JMD/USD multi-currency support, BOJ regulatory reporting, TRN validation, and EveryData credit bureau integration.

Test cases include both positive (happy path) and negative (error handling, boundary, security) scenarios across 17 functional modules. Priority levels align to business impact: P1 tests cover critical financial accuracy and security controls, P2 covers important business workflows, and P3 covers edge cases and nice-to-have validations.

### Legend

| Symbol | Meaning |
|--------|---------|
| **+** | Positive test (happy path / expected behavior) |
| **−** | Negative test (error handling, boundary, security) |
| **P1** | Critical — Must pass for release |
| **P2** | Important — Should pass, may have workaround |
| **P3** | Nice to Have — Low business impact |

### Test Distribution

| Metric | Count |
|--------|-------|
| Total Test Cases | 128 |
| Positive Scenarios (+) | 91 |
| Negative Scenarios (−) | 37 |
| P1 — Critical | 82 |
| P2 — Important | 42 |
| P3 — Nice to Have | 4 |

---

## 1. User Authentication & Access Control

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-001 | Auth | Valid login with correct credentials | Enter valid email and password, click Login | User is authenticated, redirected to dashboard with correct role permissions | + | P1 | |
| TC-002 | Auth | Login with invalid password | Enter valid email with incorrect password | Error message displayed, account not locked on first attempt, login attempt logged | − | P1 | |
| TC-003 | Auth | Account lockout after max failed attempts | Enter incorrect password 5 consecutive times | Account locked after 5th attempt, lockout notification sent, admin alert generated | − | P1 | |
| TC-004 | Auth | Session timeout handling | Login successfully, remain idle for configured timeout period | Session expires, user redirected to login page, unsaved data warning displayed | − | P2 | |
| TC-005 | Auth | Role-based access control (Loan Officer) | Login as Loan Officer, attempt to access admin-only functions | Admin menus hidden/disabled, direct URL access returns 403 Forbidden | − | P1 | |
| TC-006 | Auth | Role-based access control (Admin) | Login as Admin, navigate all modules | Full access to all system functions including user management and system config | + | P1 | |
| TC-007 | Auth | Multi-factor authentication flow | Login with credentials, receive OTP, enter valid OTP | MFA verified, user granted access, MFA event logged in audit trail | + | P1 | |
| TC-008 | Auth | Expired OTP rejection | Login with credentials, wait for OTP to expire, enter expired OTP | OTP rejected with clear error, option to resend new OTP provided | − | P2 | |
| TC-009 | Auth | Concurrent session prevention | Login from Browser A, then login with same credentials from Browser B | Either first session terminated or second login blocked per policy config | − | P2 | |
| TC-010 | Auth | Password reset workflow | Click Forgot Password, enter email, follow reset link, set new password | Reset email sent within 30s, link expires after 24h, password updated successfully | + | P1 | |

---

## 2. Loan Application & Origination

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-011 | Origination | New personal loan application submission | Complete all mandatory fields, attach required docs, submit application | Application created with unique ID, status set to Pending Review, confirmation sent to applicant | + | P1 | |
| TC-012 | Origination | Application with missing mandatory fields | Leave required fields blank (name, TRN, income), attempt to submit | Inline validation errors shown for each missing field, form not submitted | − | P1 | |
| TC-013 | Origination | Duplicate applicant detection | Submit application with TRN/ID matching existing customer record | System flags duplicate, prompts user to link to existing customer or create new | − | P1 | |
| TC-014 | Origination | AI Loan Officer conversational application | Initiate loan via AI chatbot, answer guided questions for income, purpose, amount | AI correctly captures all data points, generates pre-filled application, assigns risk tier | + | P1 | |
| TC-015 | Origination | AI Loan Officer handles ambiguous income data | Provide conflicting income information (verbal vs documented) | AI flags inconsistency, requests clarification, pauses workflow until resolved | − | P1 | |
| TC-016 | Origination | Document upload — valid formats | Upload ID scan (JPG), bank statement (PDF), pay slip (PNG) | All documents accepted, OCR extracts key data, thumbnails displayed | + | P1 | |
| TC-017 | Origination | Document upload — invalid/corrupt file | Upload corrupt PDF and unsupported .exe file | Corrupt file rejected with error, .exe blocked by file type filter, valid files unaffected | − | P2 | |
| TC-018 | Origination | Loan amount below minimum threshold | Apply for JMD $500 when minimum is JMD $10,000 | Validation error: amount below minimum, application not created | − | P2 | |
| TC-019 | Origination | Loan amount above maximum threshold | Apply for JMD $50,000,000 when max is JMD $10,000,000 | Validation error: amount exceeds maximum for product type, escalation option offered | − | P2 | |
| TC-020 | Origination | Multi-currency loan application (JMD/USD) | Submit application in USD while system base currency is JMD | Exchange rate applied correctly, both USD and JMD equivalent displayed, rate locked at submission | + | P2 | |
| TC-021 | Origination | Application save as draft | Fill partial application, click Save Draft | Application saved with Draft status, all entered data preserved, resume link provided | + | P2 | |
| TC-022 | Origination | Joint application with co-borrower | Add co-borrower details, link both credit profiles | Both applicants assessed, combined DTI calculated, joint liability terms generated | + | P2 | |

---

## 3. Credit Decisioning & Risk Assessment

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-023 | Credit | Automated credit bureau pull (EveryData) | Submit application triggering credit bureau request via API | Bureau report retrieved within SLA, credit score displayed, derogatory items flagged | + | P1 | |
| TC-024 | Credit | Credit bureau timeout handling | Submit application when bureau API is unresponsive | Timeout after configured seconds, retry initiated, manual review queue if retries exhausted | − | P1 | |
| TC-025 | Credit | Scorecard auto-approval (low risk) | Submit application for applicant with score 750+, clean history, low DTI | Application auto-approved, approval letter generated, funds disbursement initiated | + | P1 | |
| TC-026 | Credit | Scorecard auto-decline (high risk) | Submit application for applicant with score below 400, multiple defaults | Application auto-declined, decline reason codes generated, adverse action notice created | + | P1 | |
| TC-027 | Credit | Scorecard referral to manual review | Submit application for applicant in grey zone (score 500-600, moderate DTI) | Application routed to manual review queue with risk summary and recommended conditions | + | P1 | |
| TC-028 | Credit | DTI ratio calculation accuracy | Submit application: monthly income JMD 200,000, existing obligations JMD 80,000, new payment JMD 30,000 | DTI calculated as 55%, flagged as exceeding 50% threshold, documented in decision log | + | P1 | |
| TC-029 | Credit | Early warning system trigger | Existing borrower credit score drops by 50+ points between monitoring cycles | EWS alert generated, account flagged for review, notification sent to relationship manager | + | P1 | |
| TC-030 | Credit | Custom scorecard for Caribbean market | Process application through JA-specific scorecard with local risk factors | Scorecard applies Caribbean-specific weights (remittance income, informal sector adjustments) | + | P1 | |
| TC-031 | Credit | Fraud detection — identity mismatch | Submit application where uploaded ID name does not match entered name | Fraud flag raised, application suspended, case routed to fraud investigation team | − | P1 | |
| TC-032 | Credit | Override auto-decline with manager approval | Manager overrides auto-decline, provides justification, approves with conditions | Override recorded in audit trail, exception report updated, conditions attached to loan | + | P2 | |

---

## 4. Loan Disbursement

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-033 | Disbursement | Standard disbursement to borrower bank account | Approve loan, confirm disbursement, process ACH/wire transfer | Funds transferred, disbursement receipt generated, loan status changed to Active | + | P1 | |
| TC-034 | Disbursement | Disbursement with invalid bank details | Initiate disbursement with incorrect account number / routing code | Transfer fails, error captured, funds returned to holding, alert sent to operations | − | P1 | |
| TC-035 | Disbursement | Partial disbursement (phased release) | Configure 3-tranche disbursement, release first tranche only | First tranche disbursed, remaining tranches scheduled, balance reflects partial disbursement | + | P2 | |
| TC-036 | Disbursement | Disbursement hold — pending document | Attempt disbursement when required collateral document is missing | Disbursement blocked, hold reason displayed, checklist shows outstanding items | − | P1 | |
| TC-037 | Disbursement | Same-day disbursement processing | Approve and disburse within same business day before cut-off | Funds processed same day, timestamp recorded, confirmation sent within SLA | + | P2 | |
| TC-038 | Disbursement | Double-disbursement prevention | Click disbursement button twice rapidly / refresh during processing | Only one disbursement processed, idempotency key prevents duplicate, warning displayed | − | P1 | |

---

## 5. Repayment & Payment Processing

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-039 | Repayment | Scheduled monthly payment — on time | Process auto-debit for monthly installment on due date | Payment applied: principal + interest split correctly, balance updated, receipt generated | + | P1 | |
| TC-040 | Repayment | Manual payment entry by teller | Teller enters cash payment at branch: loan ID, amount, payment date | Payment posted to correct loan, receipt printed, running balance updated in real-time | + | P1 | |
| TC-041 | Repayment | Partial payment (less than scheduled) | Borrower pays JMD 15,000 when installment is JMD 25,000 | Partial payment applied per allocation rules (interest first), shortfall tracked, reminder scheduled | + | P1 | |
| TC-042 | Repayment | Overpayment handling | Borrower pays JMD 50,000 when installment is JMD 25,000 | Excess applied to principal (or held as advance) per product config, recalculated schedule offered | + | P1 | |
| TC-043 | Repayment | Payment reversal | Reverse a posted payment due to dishonoured cheque / failed ACH | Payment reversed, original balance restored, reversal fee applied if configured, audit trail created | + | P1 | |
| TC-044 | Repayment | Payment on non-business day | Submit payment on a Jamaican public holiday | Payment accepted with next-business-day value date, or queued per system config | + | P2 | |
| TC-045 | Repayment | Payment to wrong loan ID | Enter incorrect loan ID when making payment | System validates loan ID, rejects if invalid, shows confirmation screen with borrower name before posting | − | P1 | |
| TC-046 | Repayment | Bulk payment file upload (employer payroll deduction) | Upload CSV with 500 payroll deduction records | File validated, matched to loan accounts, exceptions reported, successful payments posted in batch | + | P2 | |
| TC-047 | Repayment | Auto-debit failure (insufficient funds) | Scheduled debit fails due to insufficient bank balance | Failure logged, retry scheduled per config, borrower notified via SMS/email, account flagged | − | P1 | |
| TC-048 | Repayment | Payment allocation — multiple overdue installments | Make single large payment on loan with 3 overdue installments plus fees | Payment allocated chronologically: oldest fees first, then oldest interest, then principal per waterfall rules | + | P1 | |

---

## 6. Interest Calculation & Accrual

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-049 | Interest | Fixed rate interest calculation (reducing balance) | Loan JMD 1,000,000 at 18% p.a., 12 months, reducing balance method | Monthly interest decreases each period, total interest matches amortization schedule, penny-accurate | + | P1 | |
| TC-050 | Interest | Flat rate interest calculation | Loan JMD 500,000 at 24% flat, 6 months | Equal installments, total interest = principal × rate × term / 12, schedule matches | + | P1 | |
| TC-051 | Interest | Variable rate adjustment | Rate changes from 15% to 18% mid-term per rate index update | New rate applied from effective date, remaining schedule recalculated, borrower notified | + | P1 | |
| TC-052 | Interest | Daily accrual accuracy | Verify daily interest accrual over 30-day month on JMD 2,000,000 at 20% | Daily accrual = (2,000,000 × 0.20) / 365 per day, month-end total matches to cent | + | P1 | |
| TC-053 | Interest | Leap year day-count handling | Run accrual calculation spanning Feb 28-29 in leap year | 366-day basis used for leap year, interest calculated correctly for extra day | + | P2 | |
| TC-054 | Interest | Interest on overdue balance (penalty rate) | Account 30+ days past due, penalty rate of 24% applied to overdue amount | Penalty interest calculated separately, displayed as distinct line item, compounds per product rules | + | P1 | |
| TC-055 | Interest | Zero-interest promotional period | Product configured with 3-month interest-free grace period | No interest accrued during promo period, full interest begins month 4, schedule reflects correctly | + | P2 | |

---

## 7. Delinquency & Collections

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-056 | Collections | Aging bucket transition (Current → 1-30 DPD) | Payment missed, end-of-day batch runs on day 1 past due | Account moves to 1-30 DPD bucket, aging counter starts, first reminder SMS triggered | + | P1 | |
| TC-057 | Collections | Aging bucket transition (31-60, 61-90, 90+) | Account remains unpaid through multiple aging thresholds | Correct bucket transitions at day 31, 61, 91; escalating collection actions triggered at each stage | + | P1 | |
| TC-058 | Collections | Auto-generated collection letters | Account reaches 30 DPD, 60 DPD, 90 DPD milestones | Appropriate letter template generated at each stage with correct amounts, dates, and legal language | + | P1 | |
| TC-059 | Collections | Promise-to-pay recording | Collections agent records PTP: JMD 50,000 by March 15 | PTP logged with date/amount, follow-up alert scheduled, PTP status tracked (kept/broken) | + | P2 | |
| TC-060 | Collections | Broken promise-to-pay escalation | PTP date passes with no payment received | PTP marked as broken, account escalated to next collection tier, manager notification triggered | − | P2 | |
| TC-061 | Collections | Debt restructuring / rescheduling | Restructure 90+ DPD loan: extend term by 12 months, reduce rate by 2% | New schedule generated, old loan closed, new loan opened with restructured terms, regulatory flag set | + | P1 | |
| TC-062 | Collections | Write-off processing | Process write-off for 180+ DPD account with no recovery prospect | Account written off, removed from active portfolio, moved to recovery tracking, GL entries posted | + | P1 | |
| TC-063 | Collections | Recovery payment on written-off account | Receive JMD 25,000 payment on previously written-off loan | Recovery recorded, write-off partially reversed in GL, recovery rate metrics updated | + | P2 | |

---

## 8. Loan Lifecycle Management

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-064 | Lifecycle | Early full repayment (prepayment) | Borrower requests payoff quote, pays full outstanding balance + fees | Loan closed, prepayment penalty applied if applicable, closure letter generated, lien released | + | P1 | |
| TC-065 | Lifecycle | Loan top-up on existing facility | Active borrower with good history requests additional JMD 500,000 | Eligibility validated, new combined balance calculated, modified schedule generated, single account maintained | + | P2 | |
| TC-066 | Lifecycle | Loan refinancing | Replace existing 24% loan with new 18% facility, consolidate balances | Old loan settled, new loan originated, net disbursement calculated, savings summary provided to borrower | + | P2 | |
| TC-067 | Lifecycle | Moratorium / payment holiday | Grant 3-month payment holiday due to natural disaster hardship | Payments suspended for 3 months, interest continues accruing (or waived per policy), maturity extended | + | P1 | |
| TC-068 | Lifecycle | Collateral management — lien registration | Register motor vehicle lien against auto loan, link to loan record | Collateral record created, lien reference stored, valuation documented, LTV ratio calculated | + | P2 | |
| TC-069 | Lifecycle | Maturity date reached with balance outstanding | Loan reaches maturity date but JMD 150,000 remains unpaid | Account flagged as matured-unpaid, collections workflow triggered, balloon payment demand generated | − | P1 | |
| TC-070 | Lifecycle | Automatic loan renewal (revolving facility) | Revolving credit facility reaches renewal date, borrower in good standing | Facility auto-renewed, new limit confirmed, credit review completed, renewal letter generated | + | P2 | |

---

## 9. eKYC & Compliance

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-071 | eKYC | Full eKYC verification — happy path | Submit government ID + selfie + proof of address, all matching | Identity verified, risk score assigned, KYC status set to Verified, verification certificate stored | + | P1 | |
| TC-072 | eKYC | eKYC — ID document expired | Submit expired passport as ID document | Document rejected, clear error: ID expired on [date], prompt to upload valid document | − | P1 | |
| TC-073 | eKYC | eKYC — selfie/ID face mismatch | Upload ID photo that does not match selfie submitted | Face match score below threshold, verification failed, manual review queue, fraud alert raised | − | P1 | |
| TC-074 | eKYC | AML/CFT watchlist screening | Process application for person matching OFAC/UN sanctions list name | Potential match flagged, application suspended, compliance officer alerted, SAR workflow initiated | + | P1 | |
| TC-075 | eKYC | PEP (Politically Exposed Person) detection | Application submitted by individual flagged as PEP | Enhanced due diligence requirements triggered, additional documentation requested, senior approval required | + | P1 | |
| TC-076 | eKYC | KYC refresh — periodic re-verification | Existing customer reaches 12-month KYC review date | Re-verification task created, reminder sent to customer, account restricted if not completed within grace period | + | P2 | |
| TC-077 | eKYC | TRN (Tax Registration Number) validation | Enter TRN in valid and invalid formats | Valid TRN accepted and verified against TAJ registry, invalid format rejected with error message | + | P1 | |

---

## 10. Reporting & Analytics

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-078 | Reporting | Portfolio summary dashboard load | Login as manager, navigate to Portfolio Dashboard | Dashboard loads within 3s, displays: total book, PAR ratios, disbursement trends, collection rates | + | P1 | |
| TC-079 | Reporting | Loan tape / portfolio export | Generate full portfolio export with all active loans | CSV/Excel generated with all required fields, data matches source records, download completes within SLA | + | P1 | |
| TC-080 | Reporting | Regulatory report — BOJ prudential returns | Generate Bank of Jamaica required prudential report for quarter-end | Report populates correct figures, classifications match BOJ guidelines, totals reconcile to GL | + | P1 | |
| TC-081 | Reporting | Delinquency aging report accuracy | Run aging report, compare against individual account aging | Report totals match sum of individual accounts per bucket, no accounts misclassified | + | P1 | |
| TC-082 | Reporting | Real-time API usage monitoring dashboard | Access API monitoring dashboard showing bureau pull volume | Dashboard shows: API call counts, response times, error rates, cost tracking per bureau, real-time refresh | + | P2 | |
| TC-083 | Reporting | Report with date range filter — boundary test | Generate report from Jan 1 to Dec 31, verify boundary records included | Records from 00:00:00 on start date and 23:59:59 on end date included, timezone handled correctly | + | P2 | |
| TC-084 | Reporting | Large dataset report generation (10,000+ loans) | Generate detailed report for portfolio exceeding 10,000 active loans | Report generates without timeout, paginated or streamed, accurate totals, exportable format | + | P2 | |

---

## 11. Integration & API

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-085 | API | Credit bureau API integration (EveryData) | Trigger bureau pull via API, receive score and report | API request formatted correctly, response parsed, score and report data stored against customer record | + | P1 | |
| TC-086 | API | Core banking system integration | Post disbursement transaction to core banking via API | Transaction posted, GL entries created, confirmation received, reconciliation reference stored | + | P1 | |
| TC-087 | API | SMS notification gateway | Trigger SMS for payment reminder, verify delivery | SMS sent via gateway, delivery receipt received, communication log updated, retry on failure | + | P1 | |
| TC-088 | API | API authentication — expired token | Make API call with expired JWT token | 401 Unauthorized returned, clear error message, token refresh flow triggered | − | P1 | |
| TC-089 | API | API rate limiting | Send 1,000 requests per minute exceeding rate limit of 100/min | Rate limit enforced, 429 Too Many Requests returned after threshold, retry-after header provided | − | P2 | |
| TC-090 | API | Webhook notification delivery | Configure webhook for loan status change, approve a loan | Webhook fired within 5s of status change, payload contains all relevant fields, retry on failure | + | P2 | |
| TC-091 | API | Payment gateway integration (online payment) | Borrower initiates online payment via payment gateway | Payment page loads, transaction processed, confirmation returned, payment posted to loan | + | P1 | |
| TC-092 | API | API versioning backward compatibility | Call v1 endpoint after v2 is deployed | v1 endpoint still functional, returns expected format, deprecation header included | + | P3 | |

---

## 12. Data Integrity & System Reliability

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-093 | System | Database transaction atomicity | Process disbursement that fails midway (e.g., GL posting fails) | Entire transaction rolled back, loan status unchanged, no partial postings, error logged | − | P1 | |
| TC-094 | System | Concurrent loan modification conflict | Two users edit same loan record simultaneously, both save | Second save blocked with conflict warning, merge or overwrite options presented, no data corruption | − | P1 | |
| TC-095 | System | End-of-day batch processing | Trigger EOD batch: interest accrual, aging, late fee calculation | All accounts processed, accruals posted, aging updated, batch log shows success/failure counts | + | P1 | |
| TC-096 | System | Batch failure recovery | EOD batch fails after processing 5,000 of 10,000 accounts | Batch restarts from failure point (not beginning), processed accounts not duplicated, alert sent | − | P1 | |
| TC-097 | System | Audit trail completeness | Perform: login, create loan, approve, disburse, receive payment, modify record | Every action logged with timestamp, user ID, IP address, before/after values, tamper-proof | + | P1 | |
| TC-098 | System | Data encryption at rest and in transit | Verify PII storage encryption, intercept API traffic | Database fields encrypted (AES-256), API traffic uses TLS 1.2+, no PII in logs or URLs | + | P1 | |
| TC-099 | System | System backup and restore | Perform full system backup, corrupt test data, restore from backup | Backup completes within window, restore successful, all data intact, zero data loss | + | P1 | |
| TC-100 | System | Horizontal scaling under load | Simulate 500 concurrent users performing mixed operations | System maintains <2s response time at P95, no errors, auto-scaling triggers correctly | + | P2 | |

---

## 13. Notifications & Communications

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-101 | Notifications | Payment due reminder (7 days before) | Automated reminder 7 days before payment due date | SMS and/or email sent with correct amount, due date, and payment channels listed | + | P1 | |
| TC-102 | Notifications | Payment confirmation notification | Process successful payment | Instant notification sent with receipt number, amount paid, remaining balance | + | P1 | |
| TC-103 | Notifications | Loan approval notification | Approve loan application | Borrower notified via preferred channel with approval amount, rate, term, next steps | + | P1 | |
| TC-104 | Notifications | Notification opt-out handling | Borrower opts out of SMS notifications | SMS notifications stopped, email continues, opt-out preference stored, regulatory notices still sent | + | P2 | |
| TC-105 | Notifications | Notification language — patois/English toggle | Configure notification language preference for Jamaican market | Notifications sent in selected language, all templates translated, fallback to English if unavailable | + | P3 | |

---

## 14. Product Configuration

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-106 | Products | Create new loan product | Configure: Personal Loan, 12-60mo term, 15-28% rate, JMD 50K-5M range | Product created, available for new applications, all parameters enforced during origination | + | P1 | |
| TC-107 | Products | Modify existing product parameters | Change max loan amount from JMD 5M to JMD 7.5M on active product | Change applied to new applications only, existing loans unaffected, change logged in audit | + | P2 | |
| TC-108 | Products | Product with custom fee structure | Configure: origination fee 2%, late fee JMD 2,500, insurance premium 1.5% | All fees calculated correctly during origination and lifecycle, displayed on statements | + | P2 | |
| TC-109 | Products | Disable/archive loan product | Deactivate a loan product no longer offered | Product hidden from new applications, existing loans on product continue servicing normally | + | P2 | |
| TC-110 | Products | Hire purchase product configuration (T&T market) | Configure HP product with asset tracking, depreciation schedule, ownership transfer rules | Product handles: down payment, asset registration, insurance requirements, title transfer at payoff | + | P2 | |

---

## 15. Security & Vulnerability

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-111 | Security | SQL injection attempt on search fields | Enter SQL injection payload in loan search: ' OR 1=1 -- | Input sanitized, no data leakage, attempt logged in security log, WAF blocks if configured | − | P1 | |
| TC-112 | Security | XSS attack on form fields | Enter `<script>alert('xss')</script>` in borrower name field | Script tags escaped/stripped, not executed, stored safely, displayed as plain text | − | P1 | |
| TC-113 | Security | Unauthorized API access attempt | Call API endpoint without authentication header | 401 returned, no data exposed, attempt logged with IP address | − | P1 | |
| TC-114 | Security | Privilege escalation via parameter tampering | Modify user role parameter in API request from 'officer' to 'admin' | Server-side role validation, request rejected, security alert triggered | − | P1 | |
| TC-115 | Security | Data export access control | Non-authorized user attempts to export customer PII data | Export denied, access violation logged, manager notified of attempt | − | P1 | |
| TC-116 | Security | CSRF protection on financial transactions | Craft cross-site request to initiate disbursement | CSRF token validation fails, transaction blocked, attempt logged | − | P1 | |

---

## 16. Performance & Scalability

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-117 | Performance | Dashboard load time under normal load | Access main dashboard with 50 concurrent users | Page fully renders within 3 seconds, all widgets populated, no timeout errors | + | P1 | |
| TC-118 | Performance | Loan search response time | Search by borrower name across 100,000+ records | Results returned within 2 seconds, relevant matches displayed, pagination working | + | P1 | |
| TC-119 | Performance | Bulk loan import (migration) | Import 50,000 historical loan records via bulk upload | Import completes within acceptable window, validation report generated, error records isolated | + | P2 | |
| TC-120 | Performance | Memory leak detection (72-hour soak test) | Run system under moderate load continuously for 72 hours | Memory usage stable, no gradual degradation, response times consistent, no OOM errors | + | P2 | |

---

## 17. Edge Cases & Boundary Conditions

| Test ID | Module | Scenario | Test Steps | Expected Result | +/− | Priority | Status |
|---------|--------|----------|------------|-----------------|-----|----------|--------|
| TC-121 | Edge | Loan with zero-day term (same-day maturity) | Attempt to create loan with disbursement date = maturity date | System rejects with validation error: minimum term is 1 month/day, no zero-term loans | − | P2 | |
| TC-122 | Edge | Interest rate set to 0% | Create interest-free loan product, originate and service through lifecycle | Zero interest calculated correctly, payment = principal / term, no divide-by-zero errors | + | P2 | |
| TC-123 | Edge | Maximum decimal precision in calculations | Loan of JMD 1,000,001.99 at 18.375% for 37 months | All calculations handle decimal precision, no rounding errors accumulate, penny reconciles at maturity | + | P1 | |
| TC-124 | Edge | Unicode characters in borrower name | Enter name with accents, Caribbean diacritics, apostrophes: O'Brien-Lévy | Name stored and displayed correctly throughout system, no encoding errors in letters/reports | + | P2 | |
| TC-125 | Edge | System behavior during timezone transitions | Process EOD batch during daylight savings time change | No duplicate or missed processing, correct business date applied, logs show accurate timestamps | − | P3 | |
| TC-126 | Edge | Negative amortization scenario | Payment less than monthly interest accrual on variable rate loan after rate spike | Negative amortization tracked, balance increases flagged, borrower notified, cap limits enforced | + | P2 | |
| TC-127 | Edge | Loan with 1-day delinquency then cured | Payment made 1 day late, then brought current | Account briefly ages to 1 DPD, then returns to current, history preserved, no penalty if grace period applies | + | P2 | |
| TC-128 | Edge | Concurrent batch and online transaction | User posts payment while EOD batch is running interest accrual on same account | No deadlocks, transaction isolation maintained, both operations complete correctly, data consistent | − | P1 | |

---

*CONFIDENTIAL — EveryData © 2026*
