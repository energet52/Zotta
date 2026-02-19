# Landing Site — zotta-lms.com

Documentation for the Zotta LMS marketing website deployed at [https://zotta-lms.com](https://zotta-lms.com).

## Architecture Overview

```
                         ┌─────────────────────┐
                         │    Route 53 (DNS)    │
                         │   zotta-lms.com      │
                         └──────────┬──────────┘
                                    │ A / AAAA alias
                         ┌──────────▼──────────┐
                         │     CloudFront       │
                         │   (CDN + HTTPS)      │
                         │  ERMO2BI8PY0UQ       │
                         └──┬───────────────┬───┘
                            │               │
                      /*    │               │  /api/*
               ┌────────────▼───┐   ┌───────▼──────────────┐
               │   S3 Bucket    │   │  API Gateway (HTTP)   │
               │ zotta-lms-     │   │  hm1eg8w92a           │
               │ landing        │   │  POST /api/contact    │
               └────────────────┘   │  POST /api/chat       │
                                    └──┬────────────────┬───┘
                                       │                │
                               ┌───────▼────┐   ┌──────▼───────┐
                               │  Lambda     │   │  Lambda      │
                               │  zotta-     │   │  zotta-      │
                               │  landing-   │   │  landing-    │
                               │  contact    │   │  chat        │
                               └──────┬─────┘   └──────┬───────┘
                                      │                 │
                               ┌──────▼─────┐   ┌──────▼───────┐
                               │ Amazon SES  │   │  OpenAI API  │
                               │ (send email)│   │  (GPT-4o-    │
                               └──────┬─────┘   │   mini)       │
                                      │         └──────────────┘
                               ┌──────▼──────────┐
                               │  Amazon WorkMail │
                               │  info@zotta-lms  │
                               │  .com             │
                               └──────────────────┘
```

## AWS Services Used

| Service | Resource | Purpose |
|---------|----------|---------|
| **Route 53** | Hosted zone `Z0555239TNRBXCB593RD` | DNS for `zotta-lms.com` — A/AAAA alias to CloudFront, MX for WorkMail, TXT for SPF/DKIM/DMARC, CNAME for ACM validation |
| **CloudFront** | Distribution `ERMO2BI8PY0UQ` (`d1cf67v7adpxpc.cloudfront.net`) | CDN and HTTPS termination. Routes `/*` to S3 and `/api/*` to API Gateway |
| **ACM** | Certificate `c5706819-0aef-467a-b557-8aadc76558d2` | TLS certificate for `zotta-lms.com` (DNS-validated via Route 53 CNAME) |
| **S3** | Bucket `zotta-lms-landing` (us-east-1) | Static file hosting for HTML, CSS, JS, and image assets. Not configured as a website — served exclusively through CloudFront OAI |
| **API Gateway** | HTTP API `hm1eg8w92a` (`zotta-landing-contact-api`) | Exposes `POST /contact` endpoint for the contact form. Proxied through CloudFront at `/api/*` |
| **Lambda** | Function `zotta-landing-contact` (Python 3.12) | Contact form backend. Receives form submissions, validates input, and sends email via SES |
| **Lambda** | Function `zotta-landing-chat` (Python 3.12) | AI chat widget backend. Receives visitor questions, calls OpenAI GPT-4o-mini with a scoped system prompt, returns answers about Zotta LMS |
| **SES** | Domain identity `zotta-lms.com` (verified) | Sends contact form emails from/to `info@zotta-lms.com`. Domain verified with SPF, DKIM, and DMARC records |
| **WorkMail** | Organization `m-34d7b055c8de4c358e8b507c72a48c61` (alias: `zotta-lms`) | Email hosting for `info@zotta-lms.com`. Receives inbound email via SES receipt rules |
| **OpenAI** | External (api.openai.com) | GPT-4o-mini powers the AI chat widget. Scoped system prompt restricts answers to lending/credit management topics only |
| **Plausible** | External (plausible.io) | Privacy-friendly website analytics — not an AWS service but included in the page `<head>` |

## DNS Records (Route 53)

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| `zotta-lms.com` | A / AAAA | Alias → `d1cf67v7adpxpc.cloudfront.net` | Website |
| `zotta-lms.com` | MX | `10 inbound-smtp.us-east-1.amazonaws.com` | WorkMail inbound |
| `zotta-lms.com` | TXT | `v=spf1 include:amazonses.com ~all` | SPF for SES |
| `_amazonses.zotta-lms.com` | TXT | `kb41rvUnmAAfl1e8ronG2fQq3EZXbO5NOXg71DGYpQ4=` | SES domain verification |
| `_dmarc.zotta-lms.com` | TXT | `v=DMARC1;p=quarantine;pct=100;fo=1` | DMARC policy |
| `autodiscover.zotta-lms.com` | CNAME | `autodiscover.mail.us-east-1.awsapps.com` | WorkMail auto-discover |
| `*._domainkey.zotta-lms.com` | CNAME (×3) | `*.dkim.amazonses.com` | DKIM signing |
| `_64641221b70bad82...` | CNAME | `*.acm-validations.aws` | ACM certificate validation |

## File Structure

```
landing/
├── index.html                      # Single-page landing site (HTML + inline CSS + JS)
├── lambda_contact.py               # Lambda function source for contact form
├── lambda_contact.zip              # Deployed Lambda package (contact)
├── lambda_chat.py                  # Lambda function source for AI chat widget
├── lambda_chat.zip                 # Deployed Lambda package (chat)
├── mockup-origination.png          # Feature mockup: Loan Origination
├── mockup-scoring.png              # Feature mockup: Credit Scoring
├── mockup-champion-challenger.png  # Feature mockup: Champion-Challenger Testing
├── mockup-decision-tree.png        # Feature mockup: Decision Tree Strategy Assignment
├── mockup-collections.png          # Feature mockup: Collections
├── mockup-customer360.png          # Feature mockup: Customer 360
├── mockup-ledger.png               # Feature mockup: General Ledger
└── mockup-reporting.png            # Feature mockup: Reporting & Analytics
```

## Deep Links (Anchors)

Every major section has an anchor ID for direct linking:

| URL | Section |
|-----|---------|
| `zotta-lms.com/#benefits` | Why Zotta — benefits grid |
| `zotta-lms.com/#features` | Feature showcases wrapper |
| `zotta-lms.com/#origination` | Loan Origination |
| `zotta-lms.com/#scoring` | Credit Scoring |
| `zotta-lms.com/#decisioning` | Champion-Challenger Decisioning (highlight) |
| `zotta-lms.com/#collections` | AI-Powered Collections |
| `zotta-lms.com/#customer360` | Customer 360 |
| `zotta-lms.com/#ledger` | General Ledger |
| `zotta-lms.com/#reporting` | Reporting & Analytics |
| `zotta-lms.com/#capabilities` | More Capabilities grid |
| `zotta-lms.com/#platform` | Full Platform (tabbed detail) |
| `zotta-lms.com/#how-it-works` | Getting Started steps |
| `zotta-lms.com/#contact` | Contact form |

## Deployment

### Update the website

```bash
# Upload updated HTML
aws s3 cp landing/index.html s3://zotta-lms-landing/index.html \
  --content-type "text/html" --region us-east-1

# Upload new images (if any)
aws s3 cp landing/mockup-new-feature.png s3://zotta-lms-landing/mockup-new-feature.png \
  --content-type "image/png" --region us-east-1

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id ERMO2BI8PY0UQ \
  --paths "/index.html" "/mockup-new-feature.png"
```

Changes propagate globally within 1–2 minutes after invalidation.

### Update the Lambda contact form

```bash
cd landing

# Package the function
zip lambda_contact.zip lambda_contact.py

# Deploy
aws lambda update-function-code \
  --function-name zotta-landing-contact \
  --zip-file fileb://lambda_contact.zip \
  --region us-east-1
```

### Update the Lambda chat function

```bash
cd landing
zip lambda_chat.zip lambda_chat.py
aws lambda update-function-code \
  --function-name zotta-landing-chat \
  --zip-file fileb://lambda_chat.zip \
  --region us-east-1
```

### Environment variables (Lambda)

**zotta-landing-contact:**

| Variable | Default | Description |
|----------|---------|-------------|
| `TO_EMAIL` | `info@zotta-lms.com` | Recipient for contact form submissions |
| `FROM_EMAIL` | `info@zotta-lms.com` | Sender address (must be SES-verified) |

**zotta-landing-chat:**

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (required) | OpenAI API key for GPT-4o-mini |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |

## Email Setup

### WorkMail

- **Web login**: https://zotta-lms.awsapps.com/mail
- **Organization ID**: `m-34d7b055c8de4c358e8b507c72a48c61`
- **User**: `info@zotta-lms.com` (role: USER, state: ENABLED)
- **Mailbox quota**: 50 GB

### SES Inbound Receipt Rules

The `INBOUND_MAIL` rule set routes inbound email to WorkMail:

| Rule | Recipients | Action |
|------|-----------|--------|
| `m-34d7b055c8de4c358e8b507c72a48c61` | `zotta-lms.awsapps.com`, `zotta-lms.com` | WorkmailAction → organization ARN |

**Important**: Both `zotta-lms.awsapps.com` and `zotta-lms.com` must be listed as recipients. If `zotta-lms.com` is missing, inbound email will bounce with `550 5.1.1 mailbox unavailable`.

### SES Suppression List

If the contact form stops delivering, check if the recipient was added to the SES suppression list (this happens automatically after a bounce):

```bash
# Check
aws sesv2 get-suppressed-destination \
  --email-address info@zotta-lms.com --region us-east-1

# Remove if present
aws sesv2 delete-suppressed-destination \
  --email-address info@zotta-lms.com --region us-east-1
```

## Request Flow

### Static pages (`GET /`, `GET /mockup-*.png`)
1. Browser → CloudFront (HTTPS, cached at edge)
2. CloudFront → S3 bucket `zotta-lms-landing` (origin access identity)
3. S3 returns `index.html` or image asset

### AI chat widget (`POST /api/chat`)
1. Browser sends JSON `{message, history}` to `/api/chat`
2. CloudFront matches `/api/*` → forwards to API Gateway
3. API Gateway → invokes Lambda `zotta-landing-chat`
4. Lambda builds OpenAI messages array (system prompt + conversation history + new message)
5. Lambda calls OpenAI GPT-4o-mini API → returns assistant reply
6. System prompt constrains responses to lending/credit management topics only

### Contact form (`POST /api/contact`)
1. Browser submits JSON `{name, email, company, message}` to `/api/contact`
2. CloudFront matches `/api/*` cache behavior → forwards to API Gateway origin
3. API Gateway (`hm1eg8w92a`) → invokes Lambda `zotta-landing-contact`
4. Lambda validates input → sends email via SES
5. SES delivers to `info@zotta-lms.com` (received by WorkMail via SES receipt rule)

### Inbound email (`*@zotta-lms.com`)
1. Sender's mail server → DNS MX lookup → `inbound-smtp.us-east-1.amazonaws.com`
2. SES receives email → matches `INBOUND_MAIL` receipt rule for `zotta-lms.com`
3. SES → WorkMail organization → `info@zotta-lms.com` mailbox

## Cost Estimate

| Service | Estimated Monthly Cost |
|---------|----------------------|
| Route 53 hosted zone | $0.50 |
| CloudFront (low traffic) | $0 – $1 (free tier covers 1TB/month) |
| S3 storage (~5 MB) | ~$0.01 |
| ACM certificate | Free |
| Lambda (low volume) | Free (1M requests/month free tier) |
| API Gateway (low volume) | Free (1M requests/month free tier for first 12 months) |
| SES (sending) | $0.10 per 1,000 emails |
| WorkMail (1 user) | $4.00/month |
| **Total** | **~$5/month** |
