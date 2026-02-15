# Customer 360 View — Business Requirements & Logic Prompt

## What You Are Building 

You are building the **Customer Level View** (Customer 360) for an AI-first Loan Management System. This is the single most important screen in the platform. When a loan officer, collections agent, or manager opens a customer profile, they must instantly understand the full story of that individual — powered by AI intelligence, not just raw data tables.



---

## Design Philosophy



Build this like the Bloomberg Terminal of lending — dense with information but never overwhelming, because the AI layer does the synthesis that a human brain shouldn't have to do manually across dozens of data sources.

---

## 1. PAGE LAYOUT

The page has three zones:

**Header Bar** — Always visible. Shows customer identity, status, risk tier, and quick action buttons.

**AI Intelligence Panel** (Left Sidebar) — The AI brain. Always visible alongside the main content. Contains the AI-generated account summary, risk score, detected signals, recommended actions, and key stats.

**Main Content Area** — Tabbed interface showing detailed data. Tabs: Overview, Applications, Loans, Payments, Collections, Products & Purchases, Communications, Documents, Audit Trail.

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER: Customer Name, ID, Status, Risk Tier, Quick Actions       │
├──────────────────────────┬──────────────────────────────────────────┤
│                          │                                          │
│   AI INTELLIGENCE PANEL  │   MAIN CONTENT AREA (Tabbed)            │
│                          │                                          │
│   • AI Account Summary   │   [Overview] [Applications] [Loans]     │
│   • Risk Score Gauge     │   [Payments] [Collections] [Products]   │
│   • Key Signals          │   [Communications] [Documents] [Audit]  │
│   • Recommendations      │                                          │
│   • Quick Stats          │                                          │
│                          │                                          │
└──────────────────────────┴──────────────────────────────────────────┘
```

On tablets: the AI panel collapses into a top accordion. On mobile: everything stacks vertically with the AI summary card on top.

---

## 2. AI INTELLIGENCE PANEL — The Hero Feature

### 2.1 AI Account Summary

This is the single most important element on the entire page. It generates a **natural language narrative** that a loan officer can read in 10 seconds and fully understand the customer's situation. This is NOT a list of stats — it's an intelligence brief written like one colleague briefing another. Use openai API model gpt 5.2 for all AI things in this document

**What the summary must include:**
- How long the customer has been with us, how many products they've had, and their current active positions
- Their payment behavior pattern — are they reliable? Has something changed recently?
- The single most important thing the loan officer needs to know RIGHT NOW
- Whether recent activity is consistent with historical patterns, or if there's a deviation
- Any risk signals explained in plain language (not jargon or codes)
- 1-3 actionable recommendations ranked by priority
- Any compliance or regulatory flags (KYC expiry, document gaps, exposure limits)

**Example AI Summary:**
> "Marcus Williams has been a customer since March 2022 with 3 completed loans and 1 active personal loan (JMD 450,000 remaining). He has an excellent payment track record — 94% on-time over 36 months — but missed his last 2 payments in January and February 2026, which is unusual for this borrower. His credit score dropped 18 points to 687. A review of his communications shows he mentioned a job change in his last call with collections. **Recommendation:** This appears to be a temporary hardship, not a behavioral default. Consider offering a 60-day payment deferral to retain a historically strong customer."

**Summary attributes:**
- Sentiment: positive / neutral / concerning / critical (reflects overall relationship health, not just latest event)
- 3-5 key highlights as bullet points
- Risk narrative: 1-2 sentence plain-language risk assessment
- Recommended actions with priority (high/medium/low), category (retention, collections, upsell, risk mitigation, compliance), and whether the action can be executed in one click
- Confidence score: how confident the AI is in its assessment

**When the summary regenerates:**
- New loan application submitted
- Payment missed or received after being in arrears
- Credit score change detected
- Collections escalation event
- Loan restructured or written off
- Any manual trigger by an officer
- Otherwise cached and refreshed at minimum every hour

### 2.2 Risk Score Gauge

Visual display showing:
- **Internal Behavioral Score** (0-100) — calculated from payment behavior, product usage, communication patterns
- **Bureau Credit Score** — pulled from the credit bureau
- **Score Trend** — sparkline chart showing movement over last 12 months
- **Risk Tier** — color-coded: Excellent (green), Good (blue), Fair (yellow), Watch (orange), Critical (red)
- **Probability of Default** — percentage
- **Score Factors** — what's driving the score up or down (e.g., "Payment history: positive impact", "Debt-to-income: negative impact") with relative weights

### 2.3 Key Signals (AI-Detected Alerts)

The AI continuously monitors customer data and surfaces proactive alerts as dismissible cards. Each signal has a type, title, description, when it was detected, what triggered it, and an optional link to the relevant section.

**Signal types and examples:**

- ⚠️ **Warning** — "Payment Pattern Break: First missed payment in 18 months. Historical pattern suggests temporary issue."
- 💡 **Opportunity** — "Upsell Candidate: Loan is 80% repaid with perfect history. Customer pre-qualifies for credit upgrade."
- 🔔 **Compliance** — "KYC Document Expiring: National ID expires in 30 days. Trigger re-verification."
- ℹ️ **Info** — "Exposure Alert: Total exposure approaching JMD 2M policy limit across 3 active products."
- 📞 **Communication Gap** — "No outbound contact in 45 days during active collections. Escalation recommended."
- 📈 **Positive Signal** — "3 consecutive on-time payments after restructure. Recovery trajectory is on track."

Signals can be dismissed by the officer (logged with who dismissed and when).

### 2.4 Quick Stats Cards

Six compact KPI cards always visible:
1. **Total Lifetime Value** — total interest + fees paid across entire relationship
2. **Active Products** — count of active loans/products with total outstanding exposure
3. **Days Past Due** — current worst DPD across all active accounts (0 if current)
4. **Payment Success Rate** — percentage of all payments made on-time over relationship lifetime
5. **Relationship Length** — time since first product originated
6. **Last Contact** — date, channel, and direction (inbound/outbound) of most recent interaction

---

## 3. HEADER BAR & QUICK ACTIONS

### Header displays:
- Back navigation
- Customer photo (if available)
- Full name
- Customer ID
- Tax Registration Number (masked by default, click to reveal)
- Status badge: Active / Inactive / Suspended / Closed / Deceased
- Segment badge: e.g., "Prime Salaried", "Self-Employed Micro", "First-Time Borrower"
- Risk tier badge (color-coded)

### Quick Action Buttons (always visible):
- Call customer
- Send message (SMS / Email / WhatsApp selector)
- Add internal note

### Quick Action Dropdown Menu:
- Create New Application
- Record Payment
- Schedule Follow-up
- Upload Document
- Request Credit Check
- Initiate Collections Action
- Reassign Account to Different Officer
- Flag Account for Review
- Generate Customer Report (PDF export)
- **Ask AI About This Customer** (opens AI chat panel)

---

## 4. "ASK AI" CONVERSATIONAL PANEL

A slide-out panel where the officer can ask natural language questions about the customer and get intelligent, data-grounded answers.

**Example conversation:**
```
Officer: "Why did this customer's score drop last month?"

AI: "Marcus's credit score dropped 18 points from 705 to 687 between December 2025
     and January 2026. The primary factor was two missed payments on his personal
     loan (#LN-2024-00892). Prior to this, he had no missed payments in 18 months.
     His debt-to-income ratio also increased from 38% to 44% when a new credit card
     appeared on his bureau file in November 2025."

Officer: "Should we offer him a restructure?"

AI: "Based on the data, a restructure may be premature. His history suggests this
     is temporary. I'd recommend: (1) A courtesy call to understand his situation,
     (2) If hardship is confirmed, offer a 60-day deferral rather than a full
     restructure to preserve his loan terms, (3) Monitor for 1 more cycle before
     escalating. His lifetime value of JMD 287,000 in interest paid makes retention
     worthwhile."
```

**Business rules for AI Chat:**
- AI has access to the full customer data context (profile, all loans, payments, communications, collections history, bureau data)
- AI must never fabricate numbers — all figures must be traceable to actual records
- AI responses are logged in the audit trail
- Officers can "pin" useful AI insights to the customer's profile for others to see
- Conversation history is maintained within the session but does not persist across logins
- AI should cite which data points it's referencing (e.g., "based on Loan #LN-2024-00892")

---

## 5. MAIN CONTENT TABS

### 5.1 Overview Tab (Default Landing)

The first thing the user sees. A dashboard-style layout combining:

#### Customer Profile Card
- **Identity:** Full name, date of birth, national ID (masked), TRN, photo
- **Contact:** Email, phone, alternate phone, full address
- **Employment:** Employer name, job title, monthly income, employment start date, whether income has been verified and when
- **KYC Status:** Verified / Pending / Expired / Incomplete, with last verification date and list of KYC documents on file
- **Segmentation:** Customer segment (AI-assisted), acquisition channel, referral source
- **Relationship:** Start date, assigned loan officer, branch

#### Financial Snapshot (Mini Dashboard)
- **Exposure breakdown** — donut chart showing total outstanding by product type (personal loan, auto, hire purchase, etc.)
- **Payment behavior** — bar chart showing last 12 months: on-time vs late vs missed per month
- **Credit score trend** — line chart showing score movement over time
- **Summary row:** Total Ever Borrowed | Total Repaid | Total Outstanding | Next Upcoming Payment (amount + date)

#### Unified Activity Timeline
A single chronological feed of **every interaction and event** across the entire customer relationship. This is the heartbeat of the Customer 360 view.

**Event categories that appear in the timeline:**
- **Applications:** submitted, approved, rejected, withdrawn, referred for manual review
- **Loans:** disbursed, restructured, closed normally, written off
- **Payments:** received, missed, late, reversed, partial, scheduled, reminder sent
- **Collections:** call made, visit conducted, letter sent, promise to pay recorded, promise broken, escalation, legal action initiated
- **Communications:** SMS sent/received, email sent/received, call inbound/outbound, WhatsApp sent/received, push notification, internal note added
- **Documents:** uploaded, requested, verified, rejected, expired
- **Products:** purchased (hire purchase), returned, warranty claim
- **Credit:** bureau check run, score changed
- **KYC:** verified, expired, document uploaded
- **System:** risk score changed, segment changed, officer reassigned, account flagged

**Timeline UX requirements:**
- Infinite scroll with smooth loading
- Filter chips at the top to toggle categories on/off (multi-select)
- Text search within the timeline
- Each event shows: timestamp, icon, title, description, who performed it (customer / officer / system / AI)
- AI-generated events are visually distinct (different accent color, sparkle icon)
- Related events cluster together (e.g., "Application #1042 → Approved → Loan Disbursed" as one expandable group)
- Each event is clickable and navigates to the full detail in the relevant tab
- AI sentiment indicator on communications (positive / neutral / negative)
- Optional AI micro-insight on significant events (e.g., on a missed payment: "First miss in 18 months — deviation from pattern")

### 5.2 Applications Tab

Shows all loan applications the customer has ever submitted.

**Columns:**
- Application ID (clickable to full detail)
- Submission Date
- Product Name
- Amount Requested
- Amount Approved (may differ)
- Status: Submitted → Under Review → Approved / Rejected / Withdrawn
- Decision Type: Automatic (scorecard) or Manual (officer override)
- Deciding Officer (if manual)
- Scorecard Result: score value + pass/fail
- Time to Decision
- AI Flags: any anomalies the AI detected during processing

**Expandable detail for each application shows:**
- Full decision waterfall: which scorecard was used, what score was produced, which policy rules triggered, what bureau data was pulled, officer notes if manually reviewed
- AI recommendation at time of decision (what did the AI suggest?)
- Supporting documents submitted with the application
- If rejected: the specific reasons, and whether the customer was given a counteroffer

### 5.3 Loans Tab

All active and historical loans/credit facilities.

**Loan record includes:**
- Loan ID, product name, product type (personal, auto, mortgage, hire purchase, microfinance, credit line)
- Status: Active, Closed, Written Off, Restructured, In Arrears, Legal Proceedings
- Currency
- Principal amount, disbursement date, maturity date
- Interest rate, term in months, payment frequency (weekly / biweekly / monthly)
- Outstanding balance, next payment date, next payment amount
- Days past due
- Total paid to date (broken into principal, interest, fees)
- Arrears amount
- Collateral details (if secured): description, valuation, valuation date, lien status
- Guarantor details: name, relationship, contact, their own credit standing
- Link to originating application

**Loan detail view includes:**
- Full amortization schedule with actual vs expected comparison (highlighting variances)
- Payment performance heatmap: calendar-style view showing each month color-coded (green = on time, yellow = late, red = missed, grey = future)
- Collateral details with current vs original valuation
- Guarantor information with their own credit summary
- Restructure history if applicable: when restructured, old terms vs new terms, reason
- AI loan assessment: "This loan is performing above/at/below expectations because..." with specific reasoning

### 5.4 Payments Tab

Complete payment history across all products.

**Payment record includes:**
- Payment ID, linked loan ID and loan name
- Payment date, original due date
- Amount (with currency)
- Payment method: bank transfer, cash, card, mobile money, cheque, direct debit, payroll deduction
- Status: completed, pending, failed, reversed, partial
- Days late (0 if on-time, negative if early)
- Receipt number
- Payment breakdown: principal portion, interest portion, fee portion, penalty portion
- Running balance after payment

**Visualizations on this tab:**
- Payment trend chart: amounts over time, color-coded by on-time vs late
- Payment method distribution: pie chart showing how the customer prefers to pay
- Monthly payment compliance rate: bar chart showing % of payments on-time per month
- Total paid vs total expected waterfall chart

### 5.5 Collections Tab

All collections activity across all accounts.

**Collections activity record includes:**
- Activity ID, linked loan ID
- Date and time
- Activity type: phone call, SMS, email, WhatsApp, field visit, letter, legal notice, promise to pay, payment arrangement, skip trace, escalation, write-off recommendation
- Outcome: contacted, no answer, promise made, promise broken, partial payment, full payment, dispute raised, hardship claim, refused to pay, wrong number, deceased
- Agent who performed the action
- Notes (free text from agent)
- Next scheduled action and date
- Promise to pay details: amount promised, date promised
- Call duration and recording link (if phone call)
- AI sentiment analysis of the interaction

**Collections dashboard elements within this tab:**
- Current collections status: which stage/queue is this account in?
- Promise-to-pay tracker: table of all promises with kept/broken status and compliance rate
- Escalation path visualization: a visual waterfall showing the stages (Reminder → Soft Call → Hard Call → Field Visit → Legal Notice → Legal Action → Write-off) and where this account currently sits
- Days spent in each collections stage
- **AI Collections Copilot panel:** "Based on 3 previous interactions, this customer responds best to empathetic tones and prefers WhatsApp over phone. They mentioned job instability on Jan 15. Suggest offering a payment plan. Best time to call based on answer history: Tuesday/Thursday 10am-12pm."

### 5.6 Products & Purchases Tab

For hire-purchase and retail lending clients (e.g., furniture stores, electronics retailers).

**Purchase record includes:**
- Purchase ID, date, store/branch
- Line items: product name, SKU, category, quantity, unit price, serial number
- Total purchase amount
- Financed amount vs down payment
- Linked loan ID
- Delivery status: pending, delivered, partially delivered, returned
- Warranty expiry date
- Returns: date, reason, refund amount, restocking status

This tab only appears if the customer has product purchases. It should be hidden for pure lending customers.

### 5.7 Communications Tab

Unified view of all communications across every channel.

**Channels:**
- **SMS** — sent and received, with delivery status (delivered, failed, pending)
- **Email** — threaded conversation view with attachments, read receipts
- **WhatsApp** — conversation view with media attachments
- **Phone Calls** — call log with direction (inbound/outbound), duration, recording playback, and AI-generated call transcript + summary
- **In-App Messages** — push notifications sent to the customer
- **Internal Notes** — officer notes (tagged, searchable, visible only to staff)

Each message shows who sent it, when, the content, and whether it was AI-drafted (flagged with an "AI" badge).

**AI features in this tab:**
- Auto-generated call summaries from call recordings/transcripts
- Sentiment indicator on each communication (positive / neutral / negative)
- Smart reply suggestions: when an officer is composing a message, AI suggests contextual responses
- **Channel preference analysis:** "This customer has a 90% WhatsApp response rate vs 23% for SMS. Recommend switching primary channel."
- **Communication gap detection:** "No outbound contact in 30 days during active arrears — flag for immediate follow-up"
- Communication frequency chart: timeline showing volume and channel distribution over time

### 5.8 Documents Tab

All documents associated with the customer.

**Document types:**
- Identity: national ID, passport, driver's license
- Address proof: utility bill
- Income: payslip, bank statement, tax return, employment letter
- Loan: loan agreement, guarantor form, collateral valuation report
- Legal: legal notices, court documents
- Correspondence: general letters and correspondence
- Other: any uncategorized document

**Document record includes:**
- Document name, type, upload date
- Expiry date (if applicable, e.g., national ID)
- Verification status: verified, pending verification, rejected, expired
- Verified by (officer name)
- File preview (inline for images and PDFs)
- Which loan or application it's linked to
- Tags for searchability
- AI-extracted data: if the system has OCR capability, show fields automatically extracted from the document (e.g., name and ID number from a national ID, income figure from a payslip)

**AI features:**
- **Document completeness checker:** "Missing for Application #1085: 2 recent payslips, proof of address less than 3 months old"
- **Expiry warnings:** "National ID expires in 30 days — trigger re-verification workflow"
- **Auto-extraction display:** Show AI-extracted fields next to the document with confidence scores

### 5.9 Audit Trail Tab

Complete, immutable log of every action taken on this customer's account.

**Each audit entry shows:**
- Exact timestamp
- User who performed the action (or "System" or "AI")
- Action description
- Entity affected (which loan, payment, document, etc.)
- Before value and after value (for data changes)
- IP address (for compliance)
- Reason (required for overrides and manual decisions)

**Business rules:**
- This tab is **read-only** — no one can edit or delete audit entries
- Accessible only to compliance officers, auditors, and administrators
- All AI interactions (summaries generated, AI chat questions asked, AI recommendations followed/ignored) are logged here
- PII field reveals (unmasking a national ID) are logged here
- All data exports are logged here
- Filterable by date range, user, action type, and entity

---

## 6. REAL-TIME BEHAVIOR

The Customer 360 view must update in real-time without requiring a page refresh:

**Events that trigger live updates:**
- Payment received or payment failed
- New application submitted
- Credit score change notification from bureau
- Collections action completed by another agent
- Document uploaded (by customer through portal or by another officer)
- New message received from customer (any channel)
- AI summary regenerated due to material event
- Account reassigned to different officer

**How it should behave:**
- Subtle toast notification appears when something changes
- The timeline auto-updates with a "New activity" indicator
- Relevant tab badges update (e.g., Payments tab shows "1 new")
- If the AI summary is regenerated while the officer is viewing the page, show a "Summary updated — click to refresh" prompt rather than replacing it without warning

---




---

## 9. PDF CUSTOMER REPORT

The "Generate Customer Report" action produces a professional PDF containing:
- Customer profile summary
- Current AI account summary (snapshot at time of generation)
- Risk score and tier
- Active loans summary table
- Payment history summary with compliance rate
- Collections status (if applicable)
- Document checklist (what's on file, what's missing)
- Generated by / date / confidentiality notice

This is used for: management reviews, board reporting, regulatory requests, and handoff between officers.

---

## 10. SEED DATA PERSONAS FOR DEVELOPMENT

Build the system with at least 5 realistic customer personas to test all scenarios:

1. **The Perfect Borrower** — 3-year relationship, zero missed payments, high credit score, 3 completed loans, 1 active. Multiple product types. Receives upsell signals.

2. **The Recovering Customer** — Had serious arrears 12 months ago (90+ DPD), went through restructure, has been paying on time since. Shows the recovery arc in the timeline. AI should recognize the positive trend.

3. **The Deteriorating Account** — Was a good customer for 2 years, recently started missing payments (last 2 months), score declining, hasn't responded to last 2 collection calls. AI should flag the behavioral deviation and recommend intervention.

4. **The New Customer** — Single application submitted last month, first loan just disbursed, minimal history. AI summary should note limited data and recommend monitoring milestones (first 3 payments).

5. **The Complex Case** — Multiple active loans (3+), one in active collections with legal action pending, a hire-purchase product with a return/dispute, guarantor relationships, communications across all channels, field visit records, promise-to-pay history with broken promises. Tests every tab and every signal type.

Each persona should have 50-200 timeline events spanning 1-3 years of realistic activity.

