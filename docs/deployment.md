# Zotta Deployment Guide

## Prerequisites

- AWS Account with admin permissions
- AWS CLI configured (`aws configure`)
- AWS CDK installed (`npm install -g aws-cdk`)
- Docker installed and running
- Python 3.12+
- Node.js 20+

## Local Development (Docker Compose)

```bash
# Start all services
docker compose up --build

# Seed database with test data
docker compose exec backend python seed.py

# Stop services
docker compose down

# Stop and remove volumes (clean reset)
docker compose down -v
```

### Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:5173 | React consumer portal |
| Backend | http://localhost:8000 | FastAPI API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| PostgreSQL | localhost:5432 | Database |
| Redis | localhost:6379 | Cache/queue |

## AWS Deployment

### 1. Bootstrap CDK (first time only)

```bash
cdk bootstrap aws://ACCOUNT_ID/us-east-1
```

### 2. Configure Secrets

Before deploying, update AWS Secrets Manager with real values:

```bash
# After first deploy, update the app secret with real values
aws secretsmanager put-secret-value \
  --secret-id ZottaStack-ZottaAppSecret-XXXXX \
  --secret-string '{"SECRET_KEY":"your-production-secret","OPENAI_API_KEY":"sk-...","TWILIO_ACCOUNT_SID":"AC...","TWILIO_AUTH_TOKEN":"..."}'
```

### 3. Deploy

```bash
cd infrastructure/scripts
./deploy.sh
```

Or manually:

```bash
# Build frontend
cd frontend && npm ci && npm run build && cd ..

# Deploy infrastructure
cd infrastructure/aws
pip install -r requirements.txt
cdk deploy

# Upload frontend
aws s3 sync ../../frontend/dist s3://BUCKET_NAME --delete
```

### 4. Run Database Migrations

```bash
# Connect to ECS task and run migrations
aws ecs execute-command \
  --cluster ZottaCluster \
  --task TASK_ID \
  --container api \
  --interactive \
  --command "alembic upgrade head"
```

### 5. Seed Production Data (optional)

```bash
aws ecs execute-command \
  --cluster ZottaCluster \
  --task TASK_ID \
  --container api \
  --interactive \
  --command "python seed.py"
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL async connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `CORS_ORIGINS` | Yes | Comma-separated allowed origins |
| `CREDIT_BUREAU_PROVIDER` | No | `mock` (default) or `av_knowles` |
| `OPENAI_API_KEY` | No | Required for AI chatbot |
| `TWILIO_ACCOUNT_SID` | No | Required for WhatsApp |
| `TWILIO_AUTH_TOKEN` | No | Required for WhatsApp |

## Monitoring

- ECS service logs: CloudWatch Logs (stream prefix: `zotta-api`, `zotta-worker`)
- RDS monitoring: CloudWatch RDS metrics
- ALB health checks: `/api/health` endpoint

## Rollback

```bash
# Rollback to previous CDK deployment
cdk deploy --previous

# Or redeploy specific version
git checkout <commit-hash>
./infrastructure/scripts/deploy.sh
```
