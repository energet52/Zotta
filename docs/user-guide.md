# Zotta User Guide

## Consumer Portal

### Creating an Account

1. Navigate to the Zotta portal
2. Click **Register**
3. Fill in your name, email, phone number, and create a password
4. You'll be automatically logged in

### Applying for a Loan

The application process has 5 steps:

#### Step 1: Personal Information
- Full name, date of birth, national ID
- Gender, marital status
- Current address in Trinidad & Tobago

#### Step 2: Employment & Income
- Employer name and job title
- Employment type (employed, self-employed, contract)
- Monthly income and expenses
- Existing debts and dependents

#### Step 3: Loan Details
- Loan amount (TTD 5,000 - 500,000)
- Repayment term (3 - 84 months)
- Loan purpose
- An estimated monthly payment is shown

#### Step 4: Document Upload
Upload clear copies of:
- **National ID** (or passport / driver's license)
- **Proof of income** (recent pay slip or job letter)
- **Utility bill** (proof of address, less than 3 months old)

#### Step 5: Review & Submit
- Review all entered information
- Confirm and submit the application

### Tracking Your Application

- View application status on the **Dashboard**
- Click any application to see detailed progress
- Status updates: Submitted → Under Review → Credit Check → Decision
- If approved, you'll see the offer details (amount, rate, monthly payment)

### WhatsApp Support

Message our WhatsApp number to:
- Check your application status (provide your reference number: ZOT-2026-XXXXXXXX)
- Ask about loan products and eligibility
- Get guidance on required documents

---

## Back-Office Portal (Underwriters)

### Dashboard

The dashboard shows key performance indicators:
- Total applications, pending review count
- Approval rate and average loan amount
- Monthly volume chart
- Risk distribution pie chart

### Application Queue

- View all applications awaiting review
- Filter by status (Submitted, Under Review, Credit Check, etc.)
- Click **Assign to Me** to claim an application
- Click **Review** to open the full application detail

### Reviewing an Application

The review screen shows:

#### Loan Details
- Requested amount, term, purpose
- Submission date

#### Decision Engine Results
- **Credit Score** (300-850) with risk band (A-E)
- **Scoring Breakdown** - visual bars for each factor
- **Rules Evaluation** - pass/fail for each business rule
- **Engine Outcome** - auto_approve, auto_decline, or manual_review

#### Making a Decision

Choose one of four actions:
1. **Approve** - Set the approved amount and interest rate
2. **Decline** - Provide decline reason
3. **Refer** - Send to senior underwriter
4. **Request Info** - Ask applicant for additional documents

A written reason is required for all decisions (audit trail).

### Reports

Export data for analysis:
- **Loan Book Report** (CSV) - All applications with status and financials
- **Decision Audit Report** (CSV) - All decisions with engine output and overrides
- **Underwriter Performance** (CSV) - Processing metrics per underwriter

---

## Roles & Permissions

| Action | Applicant | Junior UW | Senior UW | Admin |
|--------|-----------|-----------|-----------|-------|
| Apply for loan | Yes | No | No | No |
| View own applications | Yes | No | No | No |
| View queue | No | Yes | Yes | Yes |
| Review applications | No | Yes | Yes | Yes |
| Override decisions | No | No | Yes | Yes |
| View reports | No | Yes | Yes | Yes |
| Export reports | No | No | Yes | Yes |
| Manage rules | No | No | No | Yes |
