# Zotta API Reference

The API is built with FastAPI and provides automatic interactive documentation.

## Interactive Docs

When the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Base URL

- Local: `http://localhost:8000/api`
- Production: `https://<cloudfront-domain>/api`

## Authentication

All protected endpoints require a Bearer token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

### Endpoints

#### POST /api/auth/register
Create a new applicant account.

```json
{
  "email": "user@example.com",
  "password": "password123",
  "first_name": "John",
  "last_name": "Doe",
  "phone": "+18687001001"
}
```

#### POST /api/auth/login
Authenticate and receive tokens.

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

#### GET /api/auth/me
Get current user profile. Requires authentication.

---

### Loan Endpoints

#### POST /api/loans/
Create a new loan application (draft).

#### GET /api/loans/
List current user's applications.

#### GET /api/loans/{id}
Get application details.

#### PUT /api/loans/{id}
Update a draft application.

#### POST /api/loans/{id}/submit
Submit a draft application for review.

#### POST /api/loans/{id}/documents
Upload a document (multipart/form-data).

#### GET /api/loans/{id}/documents
List documents for an application.

#### GET /api/loans/profile
Get applicant profile.

#### PUT /api/loans/profile
Update applicant profile.

---

### Underwriter Endpoints

All require underwriter/admin role.

#### GET /api/underwriter/queue
Get the application queue. Optional `status_filter` query parameter.

#### GET /api/underwriter/applications/{id}
Get full application details.

#### GET /api/underwriter/applications/{id}/decision
Get the decision engine output for an application.

#### POST /api/underwriter/applications/{id}/assign
Assign application to current underwriter.

#### POST /api/underwriter/applications/{id}/decide
Submit underwriter decision.

```json
{
  "action": "approve",
  "reason": "Good credit profile, stable employment",
  "approved_amount": 100000,
  "approved_rate": 12.0
}
```

---

### Verification Endpoints

#### POST /api/verification/verify
Submit ID for verification.

#### GET /api/verification/status
Get current verification status.

---

### Report Endpoints

#### GET /api/reports/dashboard
Get dashboard metrics (requires staff role).

#### GET /api/reports/export/loan-book
Download loan book as CSV.

---

### WhatsApp Webhook

#### POST /api/whatsapp/webhook
Twilio webhook endpoint for incoming WhatsApp messages.

---

### Health Check

#### GET /api/health
Returns service health status.

```json
{
  "status": "healthy",
  "service": "zotta-api",
  "version": "0.1.0"
}
```
